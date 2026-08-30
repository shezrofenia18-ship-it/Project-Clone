import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from db import db

JWT_ALGORITHM = "HS256"
JKT = timezone(timedelta(hours=7))

# Login memakai USERNAME (bukan email). Username & kata sandi ditentukan owner.
USERNAME_MIN = 5


def normalize_username(raw) -> str:
    """Rapikan & validasi username: huruf kecil, TANPA SPASI, minimal 5 karakter."""
    u = str(raw or "").strip().lower()
    if not u:
        raise HTTPException(status_code=400, detail="Username wajib diisi")
    if any(ch.isspace() for ch in u):
        raise HTTPException(status_code=400, detail="Username tidak boleh mengandung spasi")
    if len(u) < USERNAME_MIN:
        raise HTTPException(status_code=400, detail=f"Username minimal {USERNAME_MIN} karakter")
    return u


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


def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _clean_user(u: dict) -> dict:
    u = dict(u)
    u["id"] = str(u.pop("_id"))
    u.pop("password_hash", None)
    u.pop("email", None)  # email sudah tidak dipakai lagi
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
        # Dicari berdasarkan ID akun, BUKAN email/username. Dulu dicari lewat email,
        # sehingga owner yang mengganti email/username staf otomatis memutus sesi
        # orang itu tanpa alasan yang jelas.
        user = None
        user_id = payload.get("sub")
        if user_id:
            from bson import ObjectId
            from bson.errors import InvalidId
            try:
                user = await db.users.find_one({"_id": ObjectId(user_id)})
            except (InvalidId, TypeError, ValueError):
                user = None
        if not user:
            raise HTTPException(status_code=401, detail="User tidak ditemukan")
        # Akun yang dinonaktifkan owner langsung kehilangan akses, tidak perlu
        # menunggu tokennya kedaluwarsa.
        if user.get("active") is False:
            raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
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
    username: str
    password: str


class CreateUserBody(BaseModel):
    name: str
    username: str
    password: str
    role: str  # owner, admin, kasir


class UpdateUserBody(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


@router.post("/login")
async def login(body: LoginBody):
    # Username dirapikan (huruf kecil, tanpa spasi) TAPI tanpa validasi panjang di
    # sini: salah ketik harus menghasilkan 401 biasa, bukan pesan aturan username.
    username = str(body.username or "").strip().lower()
    user = await db.users.find_one({"username": username}) if username else None
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Username atau kata sandi salah")
    if user.get("active") is False:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")
    clean = _clean_user(user)
    token = create_access_token(clean["id"], username, user["role"])
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
    username = normalize_username(body.username)
    if await db.users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username sudah dipakai")
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Nama tidak boleh kosong")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Kata sandi minimal 6 karakter")
    doc = {
        "name": body.name.strip(),
        "username": username,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "active": True,
        "created_at": now_jkt().isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _clean_user(doc)


VALID_ROLES = ("owner", "admin", "kasir")


def _object_id_or_404(user_id: str):
    """Ubah id string jadi ObjectId. Id ngawur -> 404, BUKAN 500 seperti sebelumnya."""
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")


def primary_owner_username() -> str:
    """Username owner utama dari konfigurasi (.env ADMIN_USERNAME).

    PENTING: `seed_admin()` MEMBUAT ULANG akun ini setiap backend start. Kalau
    dihapus/dinonaktifkan dari UI, dia akan muncul kembali sendiri — terlihat
    seperti bug "hapus tapi kembali". Karena itu akun ini dilindungi.
    """
    return os.environ.get("ADMIN_USERNAME", "owner").lower().strip()


async def _count_active_owners(exclude_id=None) -> int:
    """Jumlah owner yang masih aktif, boleh mengabaikan satu id (calon korban)."""
    q: dict = {"role": "owner", "active": {"$ne": False}}
    if exclude_id is not None:
        q["_id"] = {"$ne": exclude_id}
    return await db.users.count_documents(q)


async def _audit_user(actor: dict, action: str, target_id: str, before=None, after=None) -> None:
    """Catat perubahan akun ke audit log.

    Bentuk dokumen SAMA dengan `log_audit()` di server.py, tapi ditulis lokal
    karena auth.py tidak boleh mengimpor server.py (impor sirkular).
    """
    import uuid
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user": actor.get("name") if actor else "system",
        "user_username": actor.get("username") if actor else None,
        "role": actor.get("role") if actor else None,
        "action": action, "entity": "user", "entity_id": target_id,
        "before": before, "after": after, "created_at": now_jkt().isoformat(),
    })


def _user_snapshot(u: dict) -> dict:
    """Ringkasan akun untuk audit (tanpa hash kata sandi)."""
    return {"name": u.get("name"), "username": u.get("username"),
            "role": u.get("role"), "active": u.get("active", True)}


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserBody, user: dict = Depends(require_roles("owner"))):
    """Ubah akun: nama, username, role, status aktif, dan/atau kata sandi baru.

    Kata sandi hanya diganti bila diisi (kosong = biarkan yang lama).
    """
    oid = _object_id_or_404(user_id)
    target = await db.users.find_one({"_id": oid})
    if target is None:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    is_self = str(target["_id"]) == user["id"]
    is_primary = str(target.get("username", "")).lower() == primary_owner_username()
    before = _user_snapshot(target)

    updates: dict = {}
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Nama tidak boleh kosong")
        updates["name"] = name
    if body.username is not None:
        username = normalize_username(body.username)
        if username != str(target.get("username", "")).lower():
            if is_primary:
                raise HTTPException(status_code=400,
                                    detail="Username owner utama diatur di konfigurasi sistem (ADMIN_USERNAME), tidak bisa diubah dari sini")
            if await db.users.find_one({"username": username, "_id": {"$ne": oid}}):
                raise HTTPException(status_code=400, detail="Username sudah dipakai")
            updates["username"] = username
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Role tidak valid")
        updates["role"] = body.role
    if body.active is not None:
        updates["active"] = body.active
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Kata sandi minimal 6 karakter")
        updates["password_hash"] = hash_password(body.password)

    # --- Pengaman supaya owner tidak mengunci dirinya sendiri dari aplikasi ---
    turning_off = updates.get("active") is False
    if turning_off and is_self:
        raise HTTPException(status_code=400, detail="Tidak bisa menonaktifkan akun sendiri")
    if turning_off and is_primary:
        raise HTTPException(status_code=400,
                            detail="Owner utama tidak bisa dinonaktifkan karena akan dipulihkan otomatis oleh sistem")
    demoting_owner = target.get("role") == "owner" and updates.get("role") not in (None, "owner")
    if (demoting_owner or (turning_off and target.get("role") == "owner")) \
            and await _count_active_owners(exclude_id=oid) == 0:
        raise HTTPException(status_code=400, detail="Minimal harus ada satu owner aktif")

    if updates:
        await db.users.update_one({"_id": oid}, {"$set": updates})
    u = await db.users.find_one({"_id": oid})
    if updates:
        after = _user_snapshot(u)
        after["password_changed"] = bool(body.password)
        await _audit_user(user, "update", user_id, before, after)
    return _clean_user(u)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_roles("owner"))):
    """Hapus akun PERMANEN.

    Riwayat transaksi TIDAK hilang: dokumen penjualan menyimpan `cashier_name`
    (bukan hanya id), jadi laporan lama tetap menampilkan nama kasirnya.
    Untuk menutup akses tanpa menghapus jejak, pakai "Nonaktifkan" (PUT active=false).
    """
    oid = _object_id_or_404(user_id)
    target = await db.users.find_one({"_id": oid})
    if target is None:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    if str(target["_id"]) == user["id"]:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun sendiri")
    if str(target.get("username", "")).lower() == primary_owner_username():
        raise HTTPException(status_code=400,
                            detail="Owner utama tidak bisa dihapus karena dibuat ulang otomatis oleh sistem setiap backend dinyalakan")
    if target.get("role") == "owner" and await _count_active_owners(exclude_id=oid) == 0:
        raise HTTPException(status_code=400, detail="Minimal harus ada satu owner aktif")

    await db.users.delete_one({"_id": oid})
    await _audit_user(user, "delete", user_id, _user_snapshot(target), None)
    return {"ok": True, "name": target.get("name"), "username": target.get("username")}


async def drop_legacy_email_index() -> None:
    """Buang index unik lama `email_1` — WAJIB dijalankan PALING AWAL.

    Migrasi menghapus field `email` dari semua akun. Selama index unik `email_1`
    masih ada, nilai email yang hilang dibaca sebagai `null` dan dokumen kedua
    langsung ditolak (E11000 dup key: email: null) sehingga startup backend gagal.
    """
    try:
        await db.users.drop_index("email_1")
    except Exception:
        pass  # belum pernah ada atau sudah dibuang sebelumnya


async def migrate_usernames() -> int:
    """Sekali jalan: buatkan `username` untuk akun lama, lalu BUANG field `email`.

    Login kini memakai username (keputusan owner). Username dibuat dari bagian
    depan email lama. KECUALI akun owner utama (email = ADMIN_EMAIL) yang langsung
    memakai ADMIN_USERNAME; dia diproses PALING AWAL supaya memenangkan username
    itu bila ada bentrokan. Contoh nyata: `owner@berkahayam.com` juga ingin
    "owner", tapi karena sudah dipegang owner utama dia menjadi "owner2".

    Idempoten: akun yang sudah punya username dilewati, jadi aman dijalankan
    setiap startup.
    """
    legacy_admin_email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    primary = primary_owner_username()

    rows = await db.users.find({}).to_list(1000)
    taken = {str(u["username"]).lower() for u in rows if u.get("username")}

    def pick(base: str) -> str:
        base = "".join(ch for ch in str(base).lower() if not ch.isspace()) or "pengguna"
        while len(base) < USERNAME_MIN:
            base += "1"
        if base not in taken:
            taken.add(base)
            return base
        n = 2
        while f"{base}{n}" in taken:
            n += 1
        chosen = f"{base}{n}"
        taken.add(chosen)
        return chosen

    def owner_first(u: dict) -> int:
        return 0 if legacy_admin_email and str(u.get("email", "")).lower() == legacy_admin_email else 1

    pending = sorted([u for u in rows if not u.get("username")], key=owner_first)
    made = 0
    for u in pending:
        email = str(u.get("email", "")).lower()
        if legacy_admin_email and email == legacy_admin_email and primary not in taken:
            uname = primary
            taken.add(uname)
        else:
            seed = email.split("@")[0] if "@" in email else (email or u.get("name", ""))
            uname = pick(seed)
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"username": uname}})
        made += 1

    # Email sudah tidak dipakai untuk apa pun -> dibuang dari semua akun.
    await db.users.update_many({"email": {"$exists": True}}, {"$unset": {"email": ""}})
    return made


async def ensure_user_indexes() -> None:
    """Buat index unik `username` (dipanggil SETELAH semua akun punya username)."""
    await db.users.create_index("username", unique=True)


async def seed_admin():
    admin_username = primary_owner_username()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"username": admin_username})
    if existing is None:
        await db.users.insert_one({
            "name": "Owner Berkah Ayam Mili",
            "username": admin_username,
            "password_hash": hash_password(admin_password),
            "role": "owner",
            "active": True,
            "created_at": now_jkt().isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"username": admin_username},
                                 {"$set": {"password_hash": hash_password(admin_password), "role": "owner"}})

    # Akun demo staf. Username SENGAJA sama dengan hasil migrasi dari email lama
    # supaya tidak lahir akun kembar. "owner2" karena "owner" dipegang owner utama.
    demo = [
        ("Admin Toko", "admin", "admin123", "admin"),
        ("Kasir Andi", "kasir", "kasir123", "kasir"),
        ("Kasir Budi", "operator", "operator123", "kasir"),
        ("Owner Berkah", "owner2", "berkahayam1", "owner"),
    ]
    for name, uname, pw, role in demo:
        if uname == admin_username:
            continue  # jangan menabrak owner utama
        if not await db.users.find_one({"username": uname}):
            await db.users.insert_one({
                "name": name, "username": uname, "password_hash": hash_password(pw),
                "role": role, "active": True, "created_at": now_jkt().isoformat(),
            })

    # migrate any legacy operator accounts to kasir (role removed)
    await db.users.update_many({"role": "operator"}, {"$set": {"role": "kasir"}})
