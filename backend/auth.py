import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from db import db

JWT_ALGORITHM = "HS256"
JKT = timezone(timedelta(hours=7))


def now_jkt():
    return datetime.now(JKT)


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _clean_user(u: dict) -> dict:
    u = dict(u)
    u["id"] = str(u.pop("_id"))
    u.pop("password_hash", None)
    return u


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token tidak valid")
        user = await db.users.find_one({"email": payload["email"]})
        if not user:
            raise HTTPException(status_code=401, detail="User tidak ditemukan")
        return _clean_user(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Akses ditolak untuk role ini")
        return user
    return checker


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class CreateUserBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # owner, admin, kasir, operator


class UpdateUserBody(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


@router.post("/login")
async def login(body: LoginBody):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    if user.get("active") is False:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
    clean = _clean_user(user)
    token = create_access_token(clean["id"], email, user["role"])
    return {"token": token, "user": clean}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"ok": True}


@router.get("/users")
async def list_users(user: dict = Depends(require_roles("owner", "admin"))):
    users = await db.users.find().to_list(500)
    return [_clean_user(u) for u in users]


@router.post("/users")
async def create_user(body: CreateUserBody, user: dict = Depends(require_roles("owner"))):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    if body.role not in ("owner", "admin", "kasir"):
        raise HTTPException(status_code=400, detail="Role tidak valid")
    doc = {
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "active": True,
        "created_at": now_jkt().isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _clean_user(doc)


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserBody, user: dict = Depends(require_roles("owner"))):
    from bson import ObjectId
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.role is not None:
        updates["role"] = body.role
    if body.active is not None:
        updates["active"] = body.active
    if body.password:
        updates["password_hash"] = hash_password(body.password)
    if updates:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    u = await db.users.find_one({"_id": ObjectId(user_id)})
    return _clean_user(u)


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "name": "Owner Berkah Ayam Mili",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": "owner",
            "active": True,
            "created_at": now_jkt().isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password), "role": "owner"}})

    # demo staff users
    demo = [
        ("Admin Toko", "admin@berkahayam.com", "admin123", "admin"),
        ("Kasir Andi", "kasir@berkahayam.com", "kasir123", "kasir"),
        ("Kasir Budi", "operator@berkahayam.com", "operator123", "kasir"),
        ("Owner Berkah", "owner@berkahayam.com", "berkahayam1", "owner"),
    ]
    for name, email, pw, role in demo:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({
                "name": name, "email": email, "password_hash": hash_password(pw),
                "role": role, "active": True, "created_at": now_jkt().isoformat(),
            })

    # migrate any legacy operator accounts to kasir (role removed)
    await db.users.update_many({"role": "operator"}, {"$set": {"role": "kasir"}})
