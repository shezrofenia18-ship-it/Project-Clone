from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import asyncio
import re
import logging
import requests
from datetime import timedelta
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, WebSocket
from fastapi.responses import Response
from starlette.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from db import db, client
from auth import (
    router as auth_router,
    get_current_user,
    require_roles,
    seed_admin,
    now_jkt,
)
from seed import seed_demo, ensure_potong_parts
from realtime import manager as rt_manager, emit as rt_emit, ws_handler
import whatsapp
import pdf_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("berkah")

# ------------------------- object storage -------------------------
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "berkah-ayam-mili"
MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "gif": "image/gif", "webp": "image/webp"}
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type},
                            data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

app = FastAPI(title="Berkah Ayam Mili API")
api = APIRouter(prefix="/api")


# ------------------------- helpers -------------------------
def new_id() -> str:
    return str(uuid.uuid4())


def today_str() -> str:
    return now_jkt().strftime("%Y-%m-%d")


def iso_now() -> str:
    return now_jkt().isoformat()


def clean(doc: dict) -> dict:
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def get_setting(key: str, default=None):
    s = await db.settings.find_one({"key": key})
    return s["value"] if s else default


async def add_activity(atype: str, title: str, message: str, amount: float = 0, user: str = "system"):
    await db.activities.insert_one({
        "id": new_id(), "type": atype, "title": title, "message": message,
        "amount": amount, "user": user, "date": today_str(), "created_at": iso_now(),
    })
    # Setiap aktivitas bisnis (jual/beli/potong/bayar) mengubah angka dashboard.
    await rt_emit(["dashboard", "activities"], {"title": title})


async def add_notification(ntype: str, title: str, message: str, level: str = "info"):
    await db.notifications.insert_one({
        "id": new_id(), "type": ntype, "title": title, "message": message,
        "level": level, "read": False, "created_at": iso_now(),
    })
    await rt_emit(["notifications"], {"title": title, "level": level})


async def log_audit(user: dict, action: str, entity: str, entity_id: str, before=None, after=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "user": user.get("name") if user else "system",
        "user_email": user.get("email") if user else None, "role": user.get("role") if user else None,
        "action": action, "entity": entity, "entity_id": entity_id,
        "before": before, "after": after, "created_at": iso_now(),
    })


async def record_movement(product_id, product_name, mtype, qty_ekor, qty_kg,
                          before_ekor, before_kg, after_ekor, after_kg, user, ref="",
                          qty_pcs=0, before_pcs=0, after_pcs=0):
    await db.stock_movements.insert_one({
        "id": new_id(), "product_id": product_id, "product_name": product_name, "type": mtype,
        "qty_ekor": qty_ekor, "qty_kg": qty_kg, "qty_pcs": qty_pcs,
        "before_ekor": before_ekor, "before_kg": before_kg, "before_pcs": before_pcs,
        "after_ekor": after_ekor, "after_kg": after_kg, "after_pcs": after_pcs,
        "user": user, "ref": ref, "date": today_str(), "created_at": iso_now(),
    })


async def apply_stock(product, delta_ekor, delta_kg, mtype, user, ref, allow_negative=False, delta_pcs=0):
    before_ekor = float(product.get("stock_ekor", 0) or 0)
    before_kg = float(product.get("stock_kg", 0) or 0)
    before_pcs = float(product.get("stock_pcs", 0) or 0)
    after_ekor = round(before_ekor + delta_ekor, 3)
    after_kg = round(before_kg + delta_kg, 3)
    after_pcs = round(before_pcs + delta_pcs, 3)
    if not allow_negative and (after_kg < -0.0001 or after_ekor < -0.0001 or after_pcs < -0.0001):
        raise HTTPException(status_code=400, detail=f"STOK TIDAK MENCUKUPI untuk {product['name']}")
    await db.products.update_one({"id": product["id"]}, {"$set": {"stock_ekor": after_ekor, "stock_kg": after_kg, "stock_pcs": after_pcs}})
    await record_movement(product["id"], product["name"], mtype, delta_ekor, delta_kg,
                          before_ekor, before_kg, after_ekor, after_kg, user, ref,
                          qty_pcs=delta_pcs, before_pcs=before_pcs, after_pcs=after_pcs)
    product["stock_ekor"] = after_ekor
    product["stock_kg"] = after_kg
    product["stock_pcs"] = after_pcs
    min_kg = float(product.get("min_stock_kg", 0) or 0)
    if min_kg > 0 and after_kg <= min_kg and delta_kg < 0:
        await add_activity("stock_low", "Stok Menipis", f"Stok {product['name']} tersisa {after_kg} kg", 0, user)
        await add_notification("stock_low", "Stok Menipis", f"Stok {product['name']} tersisa {after_kg} kg", "warning")
    # POS & halaman stok langsung ikut berubah tanpa menunggu polling.
    await rt_emit(["stock", "products"], {"product_id": product["id"]})
    return product


# ------------------- HPP per ekor berbasis berat perkiraan -------------------
# Toko menjual ayam PER EKOR dengan harga tertentu, sedangkan pembelian selalu
# ditimbang. Jadi HPP/ekor dihitung: HPP/kg x berat perkiraan per ekor.
# Berat perkiraan diambil dari rata-rata seluruh ayam yang pernah MASUK STOK
# (akumulator cum_weight_in / cum_ekor_in), atau dari override manual owner.
#
# Urutan prioritas berat efektif per ekor:
#   1. override manual owner        -> source "manual"
#   2. rata-rata dari pembelian     -> source "auto"
#   3. BERAT PERKIRAAN BAWAAN       -> source "perkiraan"  (fallback, agar HPP/ekor
#      tidak pernah 0 walau owner belum pernah mengisi apa pun)
DEFAULT_AVG_WEIGHT = (
    ("broiler", 1.8),
    ("kampung", 1.2),
    ("pejantan", 1.1),
    ("petelur", 1.6),
    ("ayam", 1.5),
)
DEFAULT_AVG_WEIGHT_FALLBACK = 1.5


def sells_per_ekor(product: dict) -> bool:
    """Produk yang relevan punya berat/ekor: dijual atau distok per ekor."""
    units = product.get("units") or []
    return bool(
        "ekor" in units
        or float(product.get("price_ekor", 0) or 0) > 0
        or float(product.get("stock_ekor", 0) or 0) > 0
        or float(product.get("cum_ekor_in", 0) or 0) > 0
    )


def default_avg_weight(product: dict) -> float:
    """Berat perkiraan bawaan berdasarkan jenis ayam pada nama produk."""
    if not sells_per_ekor(product):
        return 0.0
    name = (product.get("name") or "").lower()
    for key, val in DEFAULT_AVG_WEIGHT:
        if key in name:
            return val
    return DEFAULT_AVG_WEIGHT_FALLBACK


def resolve_avg_weight(product: dict, auto_avg: Optional[float] = None) -> tuple:
    """Kembalikan (berat_dipakai, sumber, berat_bawaan)."""
    ov = float(product.get("avg_weight_override", 0) or 0)
    auto = float(product.get("avg_weight_ekor", 0) or 0) if auto_avg is None else float(auto_avg)
    dflt = default_avg_weight(product)
    if ov > 0:
        return round(ov, 3), "manual", dflt
    if auto > 0:
        return round(auto, 3), "auto", dflt
    if dflt > 0:
        return round(dflt, 3), "perkiraan", dflt
    return 0.0, "auto", dflt


def effective_avg_weight(product: dict) -> float:
    return resolve_avg_weight(product)[0]


async def recompute_avg_weight(product_id: str, add_ekor: float = 0.0, add_weight: float = 0.0,
                               set_hpp_kg: Optional[float] = None) -> dict:
    """Perbarui akumulator ayam masuk lalu hitung ulang berat rata-rata & HPP/ekor.

    add_ekor/add_weight boleh negatif (mis. saat pembelian dikoreksi/dihapus).
    """
    p = await db.products.find_one({"id": product_id})
    if not p:
        return {}
    cum_ekor = max(round(float(p.get("cum_ekor_in", 0) or 0) + add_ekor, 3), 0.0)
    cum_weight = max(round(float(p.get("cum_weight_in", 0) or 0) + add_weight, 3), 0.0)
    auto_avg = round(cum_weight / cum_ekor, 3) if cum_ekor > 0 else 0.0
    hpp_kg = float(p.get("hpp_kg", 0) or 0) if set_hpp_kg is None else float(set_hpp_kg)
    probe = {**p, "cum_ekor_in": cum_ekor, "cum_weight_in": cum_weight}
    avg_used, source, dflt = resolve_avg_weight(probe, auto_avg)
    updates = {
        "cum_ekor_in": cum_ekor,
        "cum_weight_in": cum_weight,
        "avg_weight_ekor": auto_avg,
        "avg_weight_used": avg_used,
        "avg_weight_source": source,
        "avg_weight_default": dflt,
        # true = angka masih perkiraan bawaan sistem, belum dikonfirmasi owner
        "avg_weight_is_estimate": source == "perkiraan",
        "hpp_kg": round(hpp_kg, 2),
        # Kalau belum ada data berat sama sekali, jangan hapus HPP/ekor yang
        # sudah diisi manual oleh owner.
        "hpp_ekor": round(hpp_kg * avg_used, 2) if avg_used > 0 else round(float(p.get("hpp_ekor", 0) or 0), 2),
    }
    await db.products.update_one({"id": product_id}, {"$set": updates})
    return {**p, **updates}


async def migrate_avg_weights():
    """Sekali jalan: bangun akumulator berat/ekor dari seluruh riwayat pembelian."""
    # Bagian ini aman dijalankan berulang: memastikan semua produk punya field berat.
    for field, default in (("avg_weight_override", 0), ("avg_weight_ekor", 0),
                           ("avg_weight_used", 0), ("avg_weight_source", "auto"),
                           ("avg_weight_default", 0), ("avg_weight_is_estimate", False),
                           ("cum_ekor_in", 0), ("cum_weight_in", 0)):
        await db.products.update_many({field: {"$exists": False}}, {"$set": {field: default}})
    if await get_setting("avg_weight_migrated_v1", False):
        return
    agg: Dict[str, List[float]] = {}
    purchases = await db.purchases.find({}).to_list(100000)
    for pur in purchases:
        for it in pur.get("items", []) or []:
            a = agg.setdefault(it.get("product_id"), [0.0, 0.0])
            a[0] += float(it.get("ekor", 0) or 0)
            a[1] += float(it.get("total_weight", 0) or 0)
    await db.products.update_many({}, {"$set": {"cum_ekor_in": 0, "cum_weight_in": 0}})
    for pid, (e, w) in agg.items():
        if not pid:
            continue
        await recompute_avg_weight(pid, add_ekor=e, add_weight=w)
    await db.settings.update_one({"key": "avg_weight_migrated_v1"},
                                 {"$set": {"value": True}}, upsert=True)
    logger.info("Migrasi berat rata-rata/ekor selesai untuk %s produk", len(agg))


async def refresh_all_avg_weights():
    """Hitung ulang berat/ekor + HPP/ekor semua produk (aman dijalankan berulang).

    Dipakai saat startup supaya produk yang belum pernah dibeli per ekor langsung
    memakai BERAT PERKIRAAN BAWAAN (hpp_ekor tidak lagi 0).
    """
    ids = [p["id"] for p in await db.products.find({}, {"id": 1}).to_list(1000) if p.get("id")]
    for pid in ids:
        await recompute_avg_weight(pid)
    logger.info("Berat/ekor & HPP/ekor disegarkan untuk %s produk", len(ids))


# ------------------------- models -------------------------
class ProductBody(BaseModel):
    name: str
    category: str = "sampingan"
    units: List[str] = ["kg"]
    buy_price_kg: float = 0
    hpp_kg: float = 0
    hpp_ekor: float = 0
    hpp_pcs: float = 0
    price_kg: float = 0
    price_ekor: float = 0
    price_pcs: float = 0
    stock_kg: float = 0
    stock_ekor: float = 0
    stock_pcs: float = 0
    min_stock_kg: float = 0
    min_stock_ekor: float = 0
    min_stock_pcs: float = 0
    image_url: str = ""
    is_byproduct: bool = False
    active: bool = True
    # Berat perkiraan per ekor yang di-set manual owner. None = jangan diubah,
    # 0 = kembali ke perhitungan otomatis dari rata-rata pembelian.
    avg_weight_override: Optional[float] = None


class CustomerBody(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
    type: str = "umum"
    special_prices: Dict[str, float] = {}


class SupplierBody(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
    chicken_types: List[str] = []


class PurchaseItem(BaseModel):
    product_id: str
    ekor: float = 0
    total_weight: float = 0
    total_price: float = 0


class PurchaseBody(BaseModel):
    supplier_id: str
    date: Optional[str] = None
    items: List[PurchaseItem]
    transport_cost: float = 0
    other_cost: float = 0
    paid: float = 0
    due_date: Optional[str] = None
    notes: str = ""


class SlaughterBody(BaseModel):
    product_id: str
    date: Optional[str] = None
    ekor_in: float = 0
    live_weight: float
    carcass_weight: float
    cost_pemotongan: float = 0
    operator: str = ""
    notes: str = ""


class ProdOutput(BaseModel):
    product_id: str
    pcs: float


class ProductionBody(BaseModel):
    source_product_id: str
    date: Optional[str] = None
    input_ekor: float
    outputs: List[ProdOutput]
    labor_cost: float = 0
    packaging_cost: float = 0
    other_cost: float = 0
    operator: str = ""
    notes: str = ""


class SaleItem(BaseModel):
    product_id: str
    unit: str
    qty: float
    price: float


class SaleBody(BaseModel):
    txn_id: Optional[str] = None
    date: Optional[str] = None
    offline_at: Optional[str] = None
    customer_id: Optional[str] = None
    items: List[SaleItem]
    discount: float = 0
    paid: float = 0
    payment_method: str = "cash"


class ExpenseBody(BaseModel):
    date: Optional[str] = None
    category: str
    amount: float
    description: str = ""


class TargetBody(BaseModel):
    date: Optional[str] = None
    target_omzet: float = 0
    target_weight: float = 0
    target_ekor: float = 0
    target_laba: float = 0


class PayBody(BaseModel):
    amount: float


class AdjustBody(BaseModel):
    product_id: str
    delta_ekor: float = 0
    delta_kg: float = 0
    reason: str
    type: str = "penyesuaian"


class SettingBody(BaseModel):
    key: str
    value: Any


# ------------------------- Products -------------------------
@api.get("/products")
async def list_products(user: dict = Depends(get_current_user)):
    prods = await db.products.find().sort("name", 1).to_list(1000)
    return [clean(p) for p in prods]


@api.get("/products/weight-guidance")
async def products_weight_guidance(user: dict = Depends(require_roles("owner", "admin"))):
    """Panduan berat/ekor: produk mana yang masih memakai perkiraan bawaan sistem.

    Dipakai frontend untuk memandu owner mengonfirmasi berat rata-rata per ekor.
    Selama belum dikonfirmasi, sistem TETAP memakai berat perkiraan (hpp_ekor != 0).
    """
    prods = await db.products.find({"active": {"$ne": False}}).sort("name", 1).to_list(1000)
    items = []
    for p in prods:
        if not sells_per_ekor(p):
            continue
        used, source, dflt = resolve_avg_weight(p)
        hpp_kg = float(p.get("hpp_kg", 0) or 0)
        hpp_ekor = round(hpp_kg * used, 2) if used > 0 else float(p.get("hpp_ekor", 0) or 0)
        price_ekor = float(p.get("price_ekor", 0) or 0)
        profit = round(price_ekor - hpp_ekor, 2) if price_ekor > 0 else 0.0
        items.append({
            "id": p.get("id"), "name": p.get("name"),
            "avg_weight_used": used, "avg_weight_source": source,
            "avg_weight_default": dflt,
            "avg_weight_override": float(p.get("avg_weight_override", 0) or 0),
            "avg_weight_auto": float(p.get("avg_weight_ekor", 0) or 0),
            "is_estimate": source == "perkiraan",
            "hpp_kg": hpp_kg, "hpp_ekor": hpp_ekor, "price_ekor": price_ekor,
            "profit_ekor": profit,
            "margin_ekor": round(profit / price_ekor * 100, 2) if price_ekor > 0 else 0.0,
            # laba per ekor sangat tipis / minus -> perlu ditinjau owner
            "thin_margin": bool(price_ekor > 0 and (profit / price_ekor) < 0.05),
        })
    return {
        "total": len(items),
        "need_confirm": sum(1 for i in items if i["is_estimate"]),
        "thin_margin_count": sum(1 for i in items if i["thin_margin"]),
        "items": items,
        "defaults": {k: v for k, v in DEFAULT_AVG_WEIGHT},
    }


@api.post("/products")
async def create_product(body: ProductBody, user: dict = Depends(require_roles("owner", "admin"))):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = iso_now()
    doc["avg_weight_override"] = float(doc.get("avg_weight_override") or 0)
    doc.setdefault("cum_ekor_in", 0)
    doc.setdefault("cum_weight_in", 0)
    doc.setdefault("avg_weight_ekor", 0)
    await db.products.insert_one(doc)
    await recompute_avg_weight(doc["id"])
    await log_audit(user, "create", "product", doc["id"], None, {"name": doc["name"]})
    await rt_emit(["products", "stock", "dashboard"])
    return clean(await db.products.find_one({"id": doc["id"]}))


@api.put("/products/{pid}")
async def update_product(pid: str, body: ProductBody, user: dict = Depends(require_roles("owner", "admin"))):
    existing = await db.products.find_one({"id": pid})
    if not existing:
        raise HTTPException(404, "Produk tidak ditemukan")
    updates = body.model_dump(exclude_none=True)
    for f in ["buy_price_kg", "hpp_kg", "price_kg", "price_ekor"]:
        if f in updates and existing.get(f) != updates.get(f):
            await db.price_history.insert_one({
                "id": new_id(), "product_id": pid, "product_name": existing["name"], "field": f,
                "old_value": existing.get(f, 0), "new_value": updates.get(f, 0),
                "date": today_str(), "created_at": iso_now(), "user": user["name"],
            })
    await db.products.update_one({"id": pid}, {"$set": updates})
    # HPP/ekor selalu diturunkan dari HPP/kg x berat perkiraan supaya konsisten.
    await recompute_avg_weight(pid)
    await log_audit(user, "update", "product", pid, clean(existing), updates)
    await rt_emit(["products", "stock", "dashboard"])
    return clean(await db.products.find_one({"id": pid}))


class AvgWeightBody(BaseModel):
    # 0 (atau kosong) = kembali ke otomatis
    avg_weight_override: float = 0


@api.post("/products/{pid}/avg-weight")
async def set_product_avg_weight(pid: str, body: AvgWeightBody,
                                 user: dict = Depends(require_roles("owner", "admin"))):
    """Set / reset berat perkiraan per ekor. Kirim 0 untuk kembali otomatis."""
    existing = await db.products.find_one({"id": pid})
    if not existing:
        raise HTTPException(404, "Produk tidak ditemukan")
    ov = max(float(body.avg_weight_override or 0), 0.0)
    await db.products.update_one({"id": pid}, {"$set": {"avg_weight_override": round(ov, 3)}})
    updated = await recompute_avg_weight(pid)
    await log_audit(user, "update", "product_avg_weight", pid,
                    {"avg_weight_override": existing.get("avg_weight_override", 0)},
                    {"avg_weight_override": ov, "hpp_ekor": updated.get("hpp_ekor")})
    await rt_emit(["products", "dashboard"])
    return clean(await db.products.find_one({"id": pid}))


@api.delete("/products/{pid}")
async def delete_product(pid: str, user: dict = Depends(require_roles("owner", "admin"))):
    await db.products.update_one({"id": pid}, {"$set": {"active": False}})
    await log_audit(user, "delete", "product", pid)
    return {"ok": True}


# ------------------------- Customers -------------------------
@api.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    c = await db.customers.find().sort("name", 1).to_list(2000)
    return [clean(x) for x in c]


@api.post("/customers")
async def create_customer(body: CustomerBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    doc = body.model_dump()
    doc.update({"id": new_id(), "total_purchase": 0, "receivable": 0, "created_at": iso_now()})
    await db.customers.insert_one(doc)
    return clean(doc)


@api.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerBody, user: dict = Depends(require_roles("owner", "admin"))):
    await db.customers.update_one({"id": cid}, {"$set": body.model_dump()})
    return clean(await db.customers.find_one({"id": cid}))


@api.delete("/customers/{cid}")
async def delete_customer(cid: str, user: dict = Depends(require_roles("owner", "admin"))):
    await db.customers.delete_one({"id": cid})
    return {"ok": True}


# ------------------------- Suppliers -------------------------
@api.get("/suppliers")
async def list_suppliers(user: dict = Depends(get_current_user)):
    s = await db.suppliers.find().sort("name", 1).to_list(1000)
    return [clean(x) for x in s]


@api.post("/suppliers")
async def create_supplier(body: SupplierBody, user: dict = Depends(require_roles("owner", "admin"))):
    doc = body.model_dump()
    doc.update({"id": new_id(), "last_prices": {}, "total_purchase": 0, "payable": 0, "created_at": iso_now()})
    await db.suppliers.insert_one(doc)
    return clean(doc)


@api.put("/suppliers/{sid}")
async def update_supplier(sid: str, body: SupplierBody, user: dict = Depends(require_roles("owner", "admin"))):
    await db.suppliers.update_one({"id": sid}, {"$set": body.model_dump()})
    return clean(await db.suppliers.find_one({"id": sid}))


@api.delete("/suppliers/{sid}")
async def delete_supplier(sid: str, user: dict = Depends(require_roles("owner", "admin"))):
    await db.suppliers.delete_one({"id": sid})
    return {"ok": True}


# ------------------------- Purchases -------------------------
@api.get("/purchases")
async def list_purchases(user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    p = await db.purchases.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


async def _persist_purchase(body: "PurchaseBody", user: dict, pid: str):
    supplier = await db.suppliers.find_one({"id": body.supplier_id})
    if not supplier:
        raise HTTPException(404, "Supplier tidak ditemukan")
    items_out = []
    total_bird_value = 0.0
    total_weight_all = 0.0
    total_ekor_all = 0.0
    for it in body.items:
        product = await db.products.find_one({"id": it.product_id})
        if not product:
            raise HTTPException(404, "Produk tidak ditemukan")
        computed_kg = round(it.total_price / it.total_weight, 2) if it.total_weight else 0
        avg_w = round(it.total_weight / it.ekor, 3) if it.ekor else 0
        total_bird_value += it.total_price
        total_weight_all += it.total_weight
        total_ekor_all += it.ekor
        items_out.append({"product_id": it.product_id, "name": product["name"], "ekor": it.ekor,
                          "total_weight": it.total_weight, "avg_weight": avg_w,
                          "buy_price_kg": computed_kg, "subtotal": round(it.total_price, 2)})
    total_modal = round(total_bird_value + body.transport_cost + body.other_cost, 2)
    eff_cost_kg = round(total_modal / total_weight_all, 2) if total_weight_all else 0
    eff_cost_ekor = round(total_modal / total_ekor_all, 2) if total_ekor_all else 0
    payable_amt = round(total_modal - body.paid, 2)
    doc = {
        "id": pid, "supplier_id": body.supplier_id, "supplier_name": supplier["name"],
        "date": body.date or today_str(), "items": items_out,
        "transport_cost": body.transport_cost, "other_cost": body.other_cost,
        "total_bird_value": round(total_bird_value, 2), "total_weight": round(total_weight_all, 3),
        "total_ekor": total_ekor_all,
        "total_modal": total_modal, "effective_cost_kg": eff_cost_kg, "effective_cost_ekor": eff_cost_ekor,
        "paid": body.paid, "payable": max(0, payable_amt),
        "payment_status": "lunas" if payable_amt <= 0 else "kredit",
        "notes": body.notes, "created_by": user["name"], "created_at": iso_now(),
    }
    await db.purchases.insert_one(doc)
    last_prices = supplier.get("last_prices", {}) or {}
    for it in body.items:
        product = await db.products.find_one({"id": it.product_id})
        await apply_stock(product, it.ekor, it.total_weight, "pembelian", user["name"], pid)
        share = round(total_modal * (it.total_price / total_bird_value), 2) if total_bird_value else it.total_price
        item_hpp_kg = round(share / it.total_weight, 2) if it.total_weight else eff_cost_kg
        item_buy_kg = round(it.total_price / it.total_weight, 2) if it.total_weight else 0
        await db.products.update_one({"id": it.product_id}, {"$set": {"buy_price_kg": item_buy_kg}})
        # Berat/ekor diakumulasi dari semua ayam masuk → HPP/ekor otomatis.
        await recompute_avg_weight(it.product_id, add_ekor=it.ekor,
                                   add_weight=it.total_weight, set_hpp_kg=item_hpp_kg)
        last_prices[product["category"]] = item_buy_kg
    await db.suppliers.update_one({"id": body.supplier_id}, {
        "$set": {"last_prices": last_prices},
        "$inc": {"total_purchase": total_modal, "payable": max(0, payable_amt)}})
    if payable_amt > 0:
        await db.payables.insert_one({
            "id": new_id(), "supplier_id": body.supplier_id, "supplier_name": supplier["name"],
            "purchase_id": pid, "amount": total_modal, "paid": body.paid, "remaining": payable_amt,
            "due_date": body.due_date, "status": "belum_lunas", "date": doc["date"], "created_at": iso_now()})
    await db.expenses.insert_one({
        "id": new_id(), "date": doc["date"], "category": "Pembelian Ayam", "amount": total_modal,
        "description": f"Pembelian dari {supplier['name']}", "ref": pid,
        "created_by": user["name"], "created_at": iso_now()})
    return doc, total_weight_all, total_modal


async def _reverse_purchase(purchase: dict):
    for it in purchase.get("items", []):
        product = await db.products.find_one({"id": it["product_id"]})
        if product:
            await apply_stock(product, -it.get("ekor", 0), -it.get("total_weight", 0),
                              "koreksi", "system", purchase["id"], allow_negative=True)
            # Tarik kembali kontribusinya ke rata-rata berat/ekor.
            await recompute_avg_weight(it["product_id"], add_ekor=-float(it.get("ekor", 0) or 0),
                                       add_weight=-float(it.get("total_weight", 0) or 0))
    await db.expenses.delete_many({"ref": purchase["id"], "category": "Pembelian Ayam"})
    await db.payables.delete_many({"purchase_id": purchase["id"]})
    await db.suppliers.update_one({"id": purchase["supplier_id"]}, {"$inc": {
        "total_purchase": -purchase.get("total_modal", 0), "payable": -purchase.get("payable", 0)}})


@api.post("/purchases")
async def create_purchase(body: PurchaseBody, user: dict = Depends(require_roles("owner", "admin"))):
    pid = new_id()
    doc, tw, total_modal = await _persist_purchase(body, user, pid)
    await add_activity("purchase", "Ayam Masuk", f"Pembelian dari {doc['supplier_name']} - {round(tw,1)} kg", total_modal, user["name"])
    await add_notification("purchase", "Pembelian Baru", f"{doc['supplier_name']} - {round(tw,1)} kg", "info")
    await log_audit(user, "create", "purchase", pid, None, {"total_modal": total_modal})
    return clean(doc)


@api.put("/purchases/{pid}")
async def update_purchase(pid: str, body: PurchaseBody, user: dict = Depends(require_roles("owner"))):
    existing = await db.purchases.find_one({"id": pid})
    if not existing:
        raise HTTPException(404, "Pembelian tidak ditemukan")
    await _reverse_purchase(existing)
    await db.purchases.delete_one({"id": pid})
    doc, tw, total_modal = await _persist_purchase(body, user, pid)
    await add_activity("purchase", "Pembelian Diubah", f"{doc['supplier_name']} - {round(tw,1)} kg", total_modal, user["name"])
    await log_audit(user, "update", "purchase", pid, clean(existing), {"total_modal": total_modal})
    return clean(doc)


@api.delete("/purchases/{pid}")
async def delete_purchase(pid: str, user: dict = Depends(require_roles("owner"))):
    existing = await db.purchases.find_one({"id": pid})
    if not existing:
        raise HTTPException(404, "Pembelian tidak ditemukan")
    await _reverse_purchase(existing)
    await db.purchases.delete_one({"id": pid})
    await add_activity("cancel", "Pembelian Dihapus", f"{existing['supplier_name']} dihapus", existing.get("total_modal", 0), user["name"])
    await log_audit(user, "delete", "purchase", pid, clean(existing), None)
    return {"ok": True}


# ------------------------- Slaughter -------------------------
@api.get("/slaughters")
async def list_slaughters(user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    s = await db.slaughters.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in s]


@api.post("/slaughters")
async def create_slaughter(body: SlaughterBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    product = await db.products.find_one({"id": body.product_id})
    if not product:
        raise HTTPException(404, "Produk tidak ditemukan")
    if body.carcass_weight > body.live_weight:
        raise HTTPException(400, "Berat karkas tidak boleh melebihi berat hidup")
    susut = round(body.live_weight - body.carcass_weight, 3)
    rendemen = round(body.carcass_weight / body.live_weight * 100, 2) if body.live_weight else 0
    sid = new_id()
    doc = {
        "id": sid, "product_id": body.product_id, "product_name": product["name"],
        "date": body.date or today_str(), "ekor_in": body.ekor_in,
        "live_weight": body.live_weight, "carcass_weight": body.carcass_weight,
        "susut_weight": susut, "rendemen_pct": rendemen, "susut_pct": round(100 - rendemen, 2),
        "cost_pemotongan": body.cost_pemotongan, "operator": body.operator or user["name"],
        "notes": body.notes, "created_by": user["name"], "created_at": iso_now(),
    }
    await db.slaughters.insert_one(doc)
    await apply_stock(product, 0, -susut, "pemotongan", user["name"], sid, allow_negative=True)
    if body.cost_pemotongan:
        await db.expenses.insert_one({"id": new_id(), "date": doc["date"], "category": "Biaya Pemotongan",
                                      "amount": body.cost_pemotongan, "description": f"Pemotongan {product['name']}",
                                      "ref": sid, "created_by": user["name"], "created_at": iso_now()})
    await add_activity("slaughter", "Pemotongan Selesai", f"{product['name']} rendemen {rendemen}%", 0, doc["operator"])
    await add_notification("slaughter", "Pemotongan Selesai", f"{product['name']} - {body.carcass_weight} kg karkas (rendemen {rendemen}%)", "info")
    await log_audit(user, "create", "slaughter", sid, None, {"rendemen": rendemen})
    return clean(doc)


# ------------------------- Production -------------------------
@api.get("/productions")
async def list_productions(user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    p = await db.productions.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


@api.post("/productions")
async def create_production(body: ProductionBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    source = await db.products.find_one({"id": body.source_product_id})
    if not source:
        raise HTTPException(404, "Produk sumber tidak ditemukan")
    total_output = sum(o.pcs for o in body.outputs)
    material_value = round(body.input_ekor * float(source.get("hpp_ekor", 0) or 0), 2)
    total_cost = round(material_value + body.labor_cost + body.packaging_cost + body.other_cost, 2)
    pid = new_id()
    outputs_out = []
    for o in body.outputs:
        op = await db.products.find_one({"id": o.product_id})
        outputs_out.append({"product_id": o.product_id, "name": op["name"] if op else "", "pcs": o.pcs})
    doc = {
        "id": pid, "source_product_id": body.source_product_id, "source_name": source["name"],
        "date": body.date or today_str(), "input_ekor": body.input_ekor, "outputs": outputs_out,
        "material_value": material_value, "labor_cost": body.labor_cost,
        "packaging_cost": body.packaging_cost, "other_cost": body.other_cost, "total_cost": total_cost,
        "operator": body.operator or user["name"], "notes": body.notes,
        "created_by": user["name"], "created_at": iso_now(),
    }
    await db.productions.insert_one(doc)
    await apply_stock(source, -body.input_ekor, 0, "produksi", user["name"], pid, allow_negative=True)
    main_out = body.outputs[0] if body.outputs else None
    for o in body.outputs:
        op = await db.products.find_one({"id": o.product_id})
        if not op:
            continue
        await apply_stock(op, 0, 0, "produksi", user["name"], pid, delta_pcs=o.pcs)
        if main_out and o.product_id == main_out.product_id and o.pcs:
            await db.products.update_one({"id": o.product_id}, {"$set": {"hpp_pcs": round(total_cost / o.pcs, 2)}})
    await add_activity("production", "Produksi Potong Selesai", f"{source['name']} {body.input_ekor} ekor -> {total_output} pcs", 0, doc["operator"])
    await log_audit(user, "create", "production", pid, None, {"total_cost": total_cost})
    return clean(doc)


# ------------------------- Sales -------------------------
@api.get("/sales")
async def list_sales(date: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if date:
        q["date"] = date
    if user["role"] == "kasir":
        q["cashier_id"] = user["id"]
    s = await db.sales.find(q).sort("created_at", -1).to_list(2000)
    return [clean(x) for x in s]


@api.post("/sales")
async def create_sale(body: SaleBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    txn_id = body.txn_id or new_id()
    existing = await db.sales.find_one({"txn_id": txn_id})
    if existing:
        return clean(existing)
    if not body.items:
        raise HTTPException(400, "Keranjang kosong")
    if body.payment_method == "piutang" and not body.customer_id:
        raise HTTPException(400, "Transaksi piutang harus memilih pelanggan")
    allow_neg = bool(await get_setting("allow_negative_stock", False))
    customer = await db.customers.find_one({"id": body.customer_id}) if body.customer_id else None

    items_out = []
    subtotal = total_hpp = total_weight = total_ekor = 0.0
    products_cache = {}
    for it in body.items:
        product = await db.products.find_one({"id": it.product_id})
        if not product:
            raise HTTPException(404, "Produk tidak ditemukan")
        products_cache[it.product_id] = product
        line = round(it.qty * it.price, 2)
        if it.unit == "kg":
            hpp_unit = float(product.get("hpp_kg", 0) or 0)
            total_weight += it.qty
        elif it.unit == "ekor":
            hpp_unit = float(product.get("hpp_ekor", 0) or 0)
            total_ekor += it.qty
        else:
            hpp_unit = float(product.get("hpp_pcs", 0) or 0)
        hpp_total = round(hpp_unit * it.qty, 2)
        subtotal += line
        total_hpp += hpp_total
        items_out.append({"product_id": it.product_id, "name": product["name"], "unit": it.unit,
                          "qty": it.qty, "price": it.price, "subtotal": line,
                          "hpp_unit": hpp_unit, "hpp_total": hpp_total, "category": product["category"]})
    total = round(subtotal - body.discount, 2)
    paid = body.paid if body.paid else 0
    if body.payment_method != "piutang" and paid == 0:
        paid = total
    receivable = round(total - paid, 2)
    change = round(paid - total, 2) if paid > total else 0
    if receivable < 0:
        receivable = 0
    gross_profit = round(total - total_hpp, 2)
    margin = round(gross_profit / total * 100, 2) if total else 0

    sid = new_id()
    doc = {
        "id": sid, "txn_id": txn_id, "date": body.date or today_str(),
        "cashier_id": user["id"], "cashier_name": user["name"],
        "customer_id": body.customer_id, "customer_name": customer["name"] if customer else "Umum",
        "items": items_out, "subtotal": round(subtotal, 2), "discount": body.discount,
        "total": total, "paid": paid, "change": change, "receivable": receivable,
        "payment_method": body.payment_method, "payment_status": "lunas" if receivable <= 0 else "piutang",
        "total_hpp": round(total_hpp, 2), "gross_profit": gross_profit, "margin_pct": margin,
        "total_weight": round(total_weight, 3), "total_ekor": total_ekor,
        "status": "selesai", "created_at": body.offline_at or iso_now(),
        "offline": bool(body.offline_at),
        "synced_at": iso_now() if body.offline_at else None,
    }
    for it in body.items:
        product = products_cache[it.product_id]
        d_ekor = -it.qty if it.unit == "ekor" else 0
        d_kg = -it.qty if it.unit == "kg" else 0
        d_pcs = -it.qty if it.unit == "pcs" else 0
        await apply_stock(product, d_ekor, d_kg, "penjualan", user["name"], sid, allow_negative=allow_neg, delta_pcs=d_pcs)
    await db.sales.insert_one(doc)
    await db.incomes.insert_one({"id": new_id(), "date": doc["date"], "category": "Penjualan Ayam",
                                 "amount": paid, "source": "pos", "ref": sid, "created_at": iso_now()})
    if customer:
        await db.customers.update_one({"id": customer["id"]}, {"$inc": {"total_purchase": total, "receivable": receivable}})
        if receivable > 0:
            await db.receivables.insert_one({"id": new_id(), "customer_id": customer["id"], "customer_name": customer["name"],
                                             "sale_id": sid, "amount": total, "paid": paid, "remaining": receivable,
                                             "due_date": None, "status": "belum_lunas", "date": doc["date"], "created_at": iso_now()})
    if body.offline_at:
        await add_activity("sale", "Penjualan Offline Tersinkron",
                           f"{user['name']} menjual {len(items_out)} item (dibuat saat offline)", total, user["name"])
        await add_notification("offline_sync", "Transaksi Offline Tersinkron",
                               f"Rp {int(total):,} oleh {user['name']}", "info")
    else:
        await add_activity("sale", "Penjualan Baru", f"{user['name']} menjual {len(items_out)} item", total, user["name"])
    if total >= 1000000:
        await add_notification("big_sale", "Transaksi Besar", f"{user['name']} - Rp {int(total):,}", "success")
    await log_audit(user, "create", "sale", sid, None, {"total": total})
    await rt_emit(["sales", "dashboard", "stock", "receivables"], {"total": total, "id": sid})
    return clean(doc)


@api.post("/sales/{sid}/cancel")
async def cancel_sale(sid: str, user: dict = Depends(require_roles("owner", "admin"))):
    sale = await db.sales.find_one({"id": sid})
    if not sale:
        raise HTTPException(404, "Transaksi tidak ditemukan")
    if sale.get("status") == "batal":
        raise HTTPException(400, "Transaksi sudah dibatalkan")
    for it in sale["items"]:
        product = await db.products.find_one({"id": it["product_id"]})
        if not product:
            continue
        d_ekor = it["qty"] if it["unit"] == "ekor" else 0
        d_kg = it["qty"] if it["unit"] == "kg" else 0
        d_pcs = it["qty"] if it["unit"] == "pcs" else 0
        await apply_stock(product, d_ekor, d_kg, "retur", user["name"], sid, allow_negative=True, delta_pcs=d_pcs)
    await db.sales.update_one({"id": sid}, {"$set": {"status": "batal"}})
    await db.incomes.delete_many({"ref": sid})
    await add_activity("cancel", "Transaksi Dibatalkan", f"Transaksi {sid[:8]} dibatalkan", sale["total"], user["name"])
    await add_notification("cancel", "Transaksi Dibatalkan", f"Rp {int(sale['total']):,} oleh {user['name']}", "danger")
    await log_audit(user, "cancel", "sale", sid, {"status": "selesai"}, {"status": "batal"})
    await rt_emit(["sales", "dashboard", "stock", "receivables"], {"id": sid})
    return {"ok": True}


# ------------------------- Stock -------------------------
@api.get("/stock-movements")
async def list_movements(product_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"product_id": product_id} if product_id else {}
    m = await db.stock_movements.find(q).sort("created_at", -1).to_list(1000)
    return [clean(x) for x in m]


@api.post("/stock-adjustments")
async def create_adjustment(body: AdjustBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    product = await db.products.find_one({"id": body.product_id})
    if not product:
        raise HTTPException(404, "Produk tidak ditemukan")
    await apply_stock(product, body.delta_ekor, body.delta_kg, body.type, user["name"], body.reason, allow_negative=True)
    await log_audit(user, "adjust", "stock", body.product_id, None,
                    {"delta_kg": body.delta_kg, "delta_ekor": body.delta_ekor, "reason": body.reason})
    await add_activity("adjust", "Penyesuaian Stok", f"{product['name']}: {body.reason}", 0, user["name"])
    return {"ok": True}


# ------------------------- Expenses & Incomes -------------------------
@api.get("/expenses")
async def list_expenses(user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    e = await db.expenses.find().sort("created_at", -1).to_list(2000)
    if user["role"] == "kasir":
        e = [x for x in e if x.get("category") not in ("Pembelian Ayam", "Pembayaran Hutang")]
    return [clean(x) for x in e]


@api.post("/expenses")
async def create_expense(body: ExpenseBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    doc = body.model_dump()
    doc.update({"id": new_id(), "date": body.date or today_str(), "created_by": user["name"], "created_at": iso_now()})
    await db.expenses.insert_one(doc)
    await log_audit(user, "create", "expense", doc["id"], None, {"amount": body.amount})
    await rt_emit(["expenses", "dashboard"])
    return clean(doc)


@api.get("/incomes")
async def list_incomes(user: dict = Depends(require_roles("owner", "admin"))):
    i = await db.incomes.find().sort("created_at", -1).to_list(2000)
    return [clean(x) for x in i]


# ------------------------- Receivables & Payables -------------------------
@api.get("/receivables")
async def list_receivables(user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    r = await db.receivables.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in r]


@api.post("/receivables/{rid}/pay")
async def pay_receivable(rid: str, body: PayBody, user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    r = await db.receivables.find_one({"id": rid})
    if not r:
        raise HTTPException(404, "Piutang tidak ditemukan")
    remaining = round(r["remaining"] - body.amount, 2)
    status = "lunas" if remaining <= 0 else "belum_lunas"
    await db.receivables.update_one({"id": rid}, {"$set": {"remaining": max(0, remaining), "status": status}, "$inc": {"paid": body.amount}})
    await db.customers.update_one({"id": r["customer_id"]}, {"$inc": {"receivable": -body.amount}})
    await db.incomes.insert_one({"id": new_id(), "date": today_str(), "category": "Pembayaran Piutang",
                                 "amount": body.amount, "source": "receivable", "ref": rid, "created_at": iso_now()})
    await add_activity("payment", "Pembayaran Piutang", f"{r['customer_name']} bayar", body.amount, user["name"])
    return {"ok": True, "remaining": max(0, remaining)}


@api.get("/payables")
async def list_payables(user: dict = Depends(require_roles("owner", "admin"))):
    p = await db.payables.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


@api.post("/payables/{pid}/pay")
async def pay_payable(pid: str, body: PayBody, user: dict = Depends(require_roles("owner", "admin"))):
    p = await db.payables.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Hutang tidak ditemukan")
    remaining = round(p["remaining"] - body.amount, 2)
    status = "lunas" if remaining <= 0 else "belum_lunas"
    await db.payables.update_one({"id": pid}, {"$set": {"remaining": max(0, remaining), "status": status}, "$inc": {"paid": body.amount}})
    await db.suppliers.update_one({"id": p["supplier_id"]}, {"$inc": {"payable": -body.amount}})
    await db.expenses.insert_one({"id": new_id(), "date": today_str(), "category": "Pembayaran Hutang",
                                  "amount": body.amount, "description": f"Bayar ke {p['supplier_name']}",
                                  "ref": pid, "created_by": user["name"], "created_at": iso_now()})
    await add_activity("payment", "Pembayaran Supplier", f"{p['supplier_name']}", body.amount, user["name"])
    return {"ok": True, "remaining": max(0, remaining)}


# ------------------------- Targets -------------------------
@api.get("/targets")
async def get_target(date: Optional[str] = None, user: dict = Depends(get_current_user)):
    d = date or today_str()
    t = await db.targets.find_one({"date": d})
    return clean(t) if t else {"date": d, "target_omzet": 0, "target_weight": 0, "target_ekor": 0, "target_laba": 0}


@api.post("/targets")
async def set_target(body: TargetBody, user: dict = Depends(require_roles("owner"))):
    d = body.date or today_str()
    doc = body.model_dump()
    doc["date"] = d
    await db.targets.update_one({"date": d}, {"$set": doc}, upsert=True)
    await rt_emit(["dashboard", "targets"])
    return clean(await db.targets.find_one({"date": d}))


# ------------------------- Activities & Notifications -------------------------
@api.get("/activities")
async def list_activities(limit: int = 30, user: dict = Depends(get_current_user)):
    a = await db.activities.find().sort("created_at", -1).to_list(limit)
    return [clean(x) for x in a]


@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    n = await db.notifications.find().sort("created_at", -1).to_list(50)
    return [clean(x) for x in n]


@api.post("/notifications/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"read": False}, {"$set": {"read": True}})
    await rt_emit(["notifications"])
    return {"ok": True}


# ------------------------- Audit & Price history -------------------------
@api.get("/audit-logs")
async def list_audit(user: dict = Depends(require_roles("owner", "admin"))):
    a = await db.audit_logs.find().sort("created_at", -1).to_list(500)
    return [clean(x) for x in a]


@api.get("/price-history")
async def price_history(product_id: Optional[str] = None, user: dict = Depends(require_roles("owner", "admin"))):
    q = {"product_id": product_id} if product_id else {}
    h = await db.price_history.find(q).sort("created_at", 1).to_list(1000)
    return [clean(x) for x in h]


# ------------------------- Settings -------------------------
@api.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    s = await db.settings.find().to_list(50)
    return {x["key"]: x["value"] for x in s}


@api.put("/settings")
async def put_setting(body: SettingBody, user: dict = Depends(require_roles("owner"))):
    await db.settings.update_one({"key": body.key}, {"$set": {"value": body.value}}, upsert=True)
    return {"ok": True}


# ------------------------- Dashboard -------------------------
@api.get("/dashboard")
async def dashboard(user: dict = Depends(require_roles("owner", "admin"))):
    d = today_str()
    sales_today = await db.sales.find({"date": d, "status": {"$ne": "batal"}}).to_list(5000)
    omzet = sum(s["total"] for s in sales_today)
    hpp = sum(s["total_hpp"] for s in sales_today)
    weight = sum(s.get("total_weight", 0) for s in sales_today)
    ekor = sum(s.get("total_ekor", 0) for s in sales_today)
    laba = round(omzet - hpp, 2)
    margin = round(laba / omzet * 100, 2) if omzet else 0
    exp_today = await db.expenses.find({"date": d}).to_list(2000)
    expense = sum(e["amount"] for e in exp_today)
    net_profit = round(laba - expense, 2)
    target = await db.targets.find_one({"date": d}) or {}
    t_omzet = target.get("target_omzet", 0)
    achievement = round(omzet / t_omzet * 100, 2) if t_omzet else 0

    chart = []
    for i in range(6, -1, -1):
        day = (now_jkt() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_sales = await db.sales.find({"date": day, "status": {"$ne": "batal"}}).to_list(5000)
        chart.append({"date": day, "label": (now_jkt() - timedelta(days=i)).strftime("%d/%m"),
                      "omzet": round(sum(s["total"] for s in day_sales), 2),
                      "laba": round(sum(s["total"] - s["total_hpp"] for s in day_sales), 2)})

    all_sales = await db.sales.find({"status": {"$ne": "batal"}}).to_list(10000)
    perf = {}
    for s in all_sales:
        for it in s["items"]:
            cat = it.get("category", "sampingan")
            p = perf.setdefault(cat, {"penjualan": 0, "weight": 0, "ekor": 0, "pcs": 0, "hpp": 0})
            p["penjualan"] += it["subtotal"]
            p["hpp"] += it["hpp_total"]
            if it["unit"] == "kg":
                p["weight"] += it["qty"]
            elif it["unit"] == "ekor":
                p["ekor"] += it["qty"]
            elif it["unit"] == "pcs":
                p["pcs"] += it["qty"]
    products_perf = []
    for cat, p in perf.items():
        laba_p = round(p["penjualan"] - p["hpp"], 2)
        products_perf.append({"category": cat, "penjualan": round(p["penjualan"], 2),
                              "weight": round(p["weight"], 2), "ekor": p["ekor"], "pcs": p["pcs"], "laba": laba_p,
                              "margin": round(laba_p / p["penjualan"] * 100, 2) if p["penjualan"] else 0})
    products_perf.sort(key=lambda x: x["penjualan"], reverse=True)

    prods = await db.products.find({"active": True}).to_list(1000)
    critical = []
    stock_value = 0
    for p in prods:
        stock_value += float(p.get("stock_kg", 0) or 0) * float(p.get("hpp_kg", 0) or 0)
        min_kg = float(p.get("min_stock_kg", 0) or 0)
        if min_kg > 0 and float(p.get("stock_kg", 0) or 0) <= min_kg:
            critical.append({"name": p["name"], "stock_kg": p.get("stock_kg", 0), "min_stock_kg": min_kg})

    recent = sorted(sales_today, key=lambda s: s["created_at"], reverse=True)[:8]
    activities = await db.activities.find().sort("created_at", -1).to_list(12)
    prices = [{"name": p["name"], "category": p["category"], "price_kg": p.get("price_kg", 0),
               "buy_price_kg": p.get("buy_price_kg", 0), "hpp_kg": p.get("hpp_kg", 0)}
              for p in prods if p["category"] != "sampingan"][:8]

    return {"omzet": round(omzet, 2), "hpp": round(hpp, 2), "laba": laba, "margin": margin,
            "weight": round(weight, 2), "ekor": ekor, "txn_count": len(sales_today),
            "expense": round(expense, 2), "net_profit": net_profit,
            "target": {"omzet": t_omzet, "weight": target.get("target_weight", 0),
                       "ekor": target.get("target_ekor", 0), "laba": target.get("target_laba", 0),
                       "achievement": achievement},
            "chart": chart, "products_perf": products_perf, "critical_stock": critical,
            "stock_value": round(stock_value, 2), "recent_sales": [clean(r) for r in recent],
            "activities": [clean(a) for a in activities], "prices": prices}


# ------------------------- Reports -------------------------
@api.get("/reports/profit-loss")
async def report_pl(start: Optional[str] = None, end: Optional[str] = None,
                    user: dict = Depends(require_roles("owner", "admin"))):
    q = {"status": {"$ne": "batal"}}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    sales = await db.sales.find(q).to_list(20000)
    omzet = sum(s["total"] for s in sales)
    hpp = sum(s["total_hpp"] for s in sales)
    gross = round(omzet - hpp, 2)
    eq = {}
    if start and end:
        eq["date"] = {"$gte": start, "$lte": end}
    exps = await db.expenses.find(eq).to_list(20000)
    opex = sum(e["amount"] for e in exps if e.get("category") not in ("Pembelian Ayam", "Pembayaran Hutang"))
    net = round(gross - opex, 2)
    by_cat = {}
    for e in exps:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]
    return {"omzet": round(omzet, 2), "hpp": round(hpp, 2), "gross_profit": gross, "opex": round(opex, 2),
            "net_profit": net, "gross_margin": round(gross / omzet * 100, 2) if omzet else 0,
            "net_margin": round(net / omzet * 100, 2) if omzet else 0,
            "expenses_by_category": [{"category": k, "amount": round(v, 2)} for k, v in by_cat.items()]}


@api.get("/reports/sales")
async def report_sales(start: Optional[str] = None, end: Optional[str] = None,
                       user: dict = Depends(require_roles("owner", "admin"))):
    q = {"status": {"$ne": "batal"}}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    sales = await db.sales.find(q).sort("created_at", -1).to_list(20000)
    by_method, by_cashier = {}, {}
    for s in sales:
        by_method[s["payment_method"]] = by_method.get(s["payment_method"], 0) + s["total"]
        by_cashier[s["cashier_name"]] = by_cashier.get(s["cashier_name"], 0) + s["total"]
    return {"sales": [clean(x) for x in sales[:500]], "count": len(sales),
            "total": round(sum(x["total"] for x in sales), 2),
            "by_method": [{"method": k, "total": round(v, 2)} for k, v in by_method.items()],
            "by_cashier": [{"cashier": k, "total": round(v, 2)} for k, v in by_cashier.items()]}


@api.get("/reports/stock")
async def report_stock(user: dict = Depends(get_current_user)):
    prods = await db.products.find({"active": True}).sort("name", 1).to_list(1000)
    out = []
    for p in prods:
        val = float(p.get("stock_kg", 0) or 0) * float(p.get("hpp_kg", 0) or 0)
        val_pcs = float(p.get("stock_pcs", 0) or 0) * float(p.get("hpp_pcs", 0) or 0)
        out.append({"name": p["name"], "category": p["category"], "stock_ekor": p.get("stock_ekor", 0),
                    "stock_kg": p.get("stock_kg", 0), "stock_pcs": p.get("stock_pcs", 0),
                    "hpp_kg": p.get("hpp_kg", 0), "hpp_pcs": p.get("hpp_pcs", 0),
                    "value": round(val, 2), "value_pcs": round(val_pcs, 2)})
    return {"items": out, "total_value": round(sum(x["value"] for x in out), 2),
            "total_value_pcs": round(sum(x["value_pcs"] for x in out), 2)}


# ------------------------- Reports: PDF (kop toko) -------------------------
async def _store_info() -> dict:
    s = await db.settings.find().to_list(50)
    kv = {x["key"]: x["value"] for x in s}
    return {
        "name": kv.get("store_name") or "Berkah Ayam Mili",
        "tagline": kv.get("store_tagline") or "Ayam Potong & Fillet",
        "address": kv.get("store_address") or "",
        "phone": kv.get("store_phone") or "",
    }


def _pdf_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
            # supaya nama file tetap terbaca oleh frontend (CORS)
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


def _range_tag(start: Optional[str], end: Optional[str]) -> str:
    if start and end:
        return f"{start}_sd_{end}"
    return "semua-periode"


@api.get("/reports/profit-loss/pdf")
async def report_pl_pdf(start: Optional[str] = None, end: Optional[str] = None,
                        user: dict = Depends(require_roles("owner", "admin"))):
    data = await report_pl(start, end, user)
    store = await _store_info()
    pdf = await run_in_threadpool(pdf_reports.profit_loss_pdf, data, store, start, end, user["name"])
    return _pdf_response(pdf, f"laba-rugi_{_range_tag(start, end)}.pdf")


@api.get("/reports/sales/pdf")
async def report_sales_pdf(start: Optional[str] = None, end: Optional[str] = None,
                           user: dict = Depends(require_roles("owner", "admin"))):
    data = await report_sales(start, end, user)
    store = await _store_info()
    pdf = await run_in_threadpool(pdf_reports.sales_pdf, data, store, start, end, user["name"])
    return _pdf_response(pdf, f"penjualan_{_range_tag(start, end)}.pdf")


@api.get("/reports/stock/pdf")
async def report_stock_pdf(user: dict = Depends(require_roles("owner", "admin"))):
    data = await report_stock(user)
    store = await _store_info()
    pdf = await run_in_threadpool(pdf_reports.stock_pdf, data, store, user["name"])
    return _pdf_response(pdf, f"nilai-stok_{today_str()}.pdf")


# ------------------------- Tutup Buku Harian -------------------------
# Beban yang BUKAN biaya usaha (sudah masuk modal/HPP) — sama seperti laporan laba rugi.
OPEX_EXCLUDE = ("Pembelian Ayam", "Pembayaran Hutang")


class ClosingBody(BaseModel):
    date: Optional[str] = None
    notes: str = ""


async def _closing_snapshot(d: str) -> dict:
    """Hitung ringkasan tutup buku untuk satu tanggal. Semua angka dari database."""
    sales = await db.sales.find({"date": d, "status": {"$ne": "batal"}}).to_list(20000)
    cancelled = await db.sales.count_documents({"date": d, "status": "batal"})

    omzet = hpp = diskon = piutang_baru = kas_masuk_jual = 0.0
    weight = ekor = pcs = 0.0
    by_method: Dict[str, dict] = {}
    by_cashier: Dict[str, dict] = {}
    per_product: Dict[str, dict] = {}
    for s in sales:
        total = float(s.get("total", 0) or 0)
        s_hpp = float(s.get("total_hpp", 0) or 0)
        recv = float(s.get("receivable", 0) or 0)
        omzet += total
        hpp += s_hpp
        diskon += float(s.get("discount", 0) or 0)
        piutang_baru += recv
        kas_masuk_jual += max(total - recv, 0)
        weight += float(s.get("total_weight", 0) or 0)
        ekor += float(s.get("total_ekor", 0) or 0)
        m = by_method.setdefault(s.get("payment_method", "cash"),
                                 {"method": s.get("payment_method", "cash"), "count": 0, "total": 0.0, "kas": 0.0})
        m["count"] += 1
        m["total"] += total
        m["kas"] += max(total - recv, 0)
        c = by_cashier.setdefault(s.get("cashier_name", "-"),
                                  {"cashier": s.get("cashier_name", "-"), "count": 0, "total": 0.0, "laba": 0.0})
        c["count"] += 1
        c["total"] += total
        c["laba"] += total - s_hpp
        for it in s.get("items", []) or []:
            if it.get("unit") == "pcs":
                pcs += float(it.get("qty", 0) or 0)
            p = per_product.setdefault(it.get("name", "-"), {"name": it.get("name", "-"), "qty_kg": 0.0,
                                                             "qty_ekor": 0.0, "qty_pcs": 0.0,
                                                             "penjualan": 0.0, "hpp": 0.0})
            unit = it.get("unit")
            qty = float(it.get("qty", 0) or 0)
            if unit == "kg":
                p["qty_kg"] += qty
            elif unit == "ekor":
                p["qty_ekor"] += qty
            else:
                p["qty_pcs"] += qty
            p["penjualan"] += float(it.get("subtotal", 0) or 0)
            p["hpp"] += float(it.get("hpp_total", 0) or 0)

    gross = round(omzet - hpp, 2)

    incomes = await db.incomes.find({"date": d}).to_list(20000)
    bayar_piutang = sum(float(i.get("amount", 0) or 0) for i in incomes
                        if i.get("category") == "Pembayaran Piutang")
    income_total = sum(float(i.get("amount", 0) or 0) for i in incomes)

    expenses = await db.expenses.find({"date": d}).to_list(20000)
    exp_by_cat: Dict[str, float] = {}
    opex = 0.0
    for e in expenses:
        amt = float(e.get("amount", 0) or 0)
        exp_by_cat[e.get("category", "Lain-lain")] = exp_by_cat.get(e.get("category", "Lain-lain"), 0) + amt
        if e.get("category") not in OPEX_EXCLUDE:
            opex += amt
    expense_total = sum(float(e.get("amount", 0) or 0) for e in expenses)

    purchases = await db.purchases.find({"date": d}).to_list(5000)
    beli_modal = sum(float(p.get("total_modal", 0) or 0) for p in purchases)
    beli_kg = sum(float(p.get("total_weight", 0) or 0) for p in purchases)
    beli_ekor = sum(float(p.get("total_ekor", 0) or 0) for p in purchases)
    hutang_baru = sum(float(p.get("payable", 0) or 0) for p in purchases)

    prods = await db.products.find({"active": True}).sort("name", 1).to_list(1000)
    stock_items = []
    stock_value = 0.0
    for p in prods:
        s_kg = float(p.get("stock_kg", 0) or 0)
        s_pcs = float(p.get("stock_pcs", 0) or 0)
        # Catatan: stok ekor & kg menggambarkan ayam yang SAMA (dua satuan),
        # jadi nilai stok dihitung dari kg saja + pcs, supaya tidak dobel.
        val = round(s_kg * float(p.get("hpp_kg", 0) or 0) + s_pcs * float(p.get("hpp_pcs", 0) or 0), 2)
        stock_value += val
        if s_kg or s_pcs or float(p.get("stock_ekor", 0) or 0):
            stock_items.append({
                "name": p["name"], "category": p.get("category", "-"),
                "stock_kg": round(s_kg, 3), "stock_ekor": round(float(p.get("stock_ekor", 0) or 0), 2),
                "stock_pcs": round(s_pcs, 2), "hpp_kg": float(p.get("hpp_kg", 0) or 0),
                "hpp_ekor": float(p.get("hpp_ekor", 0) or 0),
                "avg_weight": float(p.get("avg_weight_used", 0) or p.get("avg_weight_ekor", 0) or 0),
                "value": val,
            })

    receivables_open = await db.receivables.find({"status": "belum_lunas"}).to_list(5000)
    payables_open = await db.payables.find({"status": "belum_lunas"}).to_list(5000)

    target = await db.targets.find_one({"date": d}) or {}
    t_omzet = float(target.get("target_omzet", 0) or 0)

    top = sorted(per_product.values(), key=lambda x: -x["penjualan"])[:12]
    for p in top:
        p["laba"] = round(p["penjualan"] - p["hpp"], 2)
        p["penjualan"] = round(p["penjualan"], 2)
        p["hpp"] = round(p["hpp"], 2)
        p["qty_kg"] = round(p["qty_kg"], 3)

    return {
        "date": d,
        "omzet": round(omzet, 2), "hpp": round(hpp, 2), "gross_profit": gross,
        "margin": round(gross / omzet * 100, 2) if omzet else 0,
        "opex": round(opex, 2), "net_profit": round(gross - opex, 2),
        "diskon": round(diskon, 2),
        "txn_count": len(sales), "cancelled_count": cancelled,
        "weight": round(weight, 3), "ekor": round(ekor, 2), "pcs": round(pcs, 2),
        "kas_dari_penjualan": round(kas_masuk_jual, 2),
        "piutang_baru": round(piutang_baru, 2),
        "bayar_piutang_masuk": round(bayar_piutang, 2),
        "kas_masuk_total": round(kas_masuk_jual + bayar_piutang, 2),
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "expenses_by_category": [{"category": k, "amount": round(v, 2)} for k, v in
                                 sorted(exp_by_cat.items(), key=lambda x: -x[1])],
        "by_method": sorted([{**v, "total": round(v["total"], 2), "kas": round(v["kas"], 2)}
                             for v in by_method.values()], key=lambda x: -x["total"]),
        "by_cashier": sorted([{**v, "total": round(v["total"], 2), "laba": round(v["laba"], 2)}
                              for v in by_cashier.values()], key=lambda x: -x["total"]),
        "top_products": top,
        "purchase": {"count": len(purchases), "total_modal": round(beli_modal, 2),
                     "weight": round(beli_kg, 3), "ekor": round(beli_ekor, 2),
                     "hutang_baru": round(hutang_baru, 2)},
        "stock_items": stock_items, "stock_value": round(stock_value, 2),
        "receivable_outstanding": round(sum(float(r.get("remaining", 0) or 0) for r in receivables_open), 2),
        "payable_outstanding": round(sum(float(p.get("remaining", 0) or 0) for p in payables_open), 2),
        "target_omzet": t_omzet,
        "target_achievement": round(omzet / t_omzet * 100, 2) if t_omzet else 0,
    }


@api.get("/daily-closing/preview")
async def closing_preview(date: Optional[str] = None, user: dict = Depends(require_roles("owner", "admin"))):
    d = date or today_str()
    data = await _closing_snapshot(d)
    existing = await db.daily_closings.find_one({"date": d})
    data["already_closed"] = bool(existing)
    data["closed_at"] = existing.get("closed_at") if existing else None
    data["closed_by"] = existing.get("closed_by") if existing else None
    data["version"] = existing.get("version", 0) if existing else 0
    return data


@api.get("/daily-closing")
async def list_closings(limit: int = 60, user: dict = Depends(require_roles("owner", "admin"))):
    docs = await db.daily_closings.find().sort("date", -1).to_list(max(1, min(limit, 365)))
    out = []
    for c in docs:
        out.append({
            "id": c["id"], "date": c["date"], "omzet": c.get("omzet", 0), "hpp": c.get("hpp", 0),
            "gross_profit": c.get("gross_profit", 0), "net_profit": c.get("net_profit", 0),
            "margin": c.get("margin", 0), "txn_count": c.get("txn_count", 0),
            "stock_value": c.get("stock_value", 0), "piutang_baru": c.get("piutang_baru", 0),
            "kas_masuk_total": c.get("kas_masuk_total", 0), "expense_total": c.get("expense_total", 0),
            "closed_by": c.get("closed_by"), "closed_at": c.get("closed_at"),
            "version": c.get("version", 1), "notes": c.get("notes", ""),
        })
    return out


@api.post("/daily-closing")
async def create_closing(body: ClosingBody, user: dict = Depends(require_roles("owner"))):
    """Tutup buku: simpan snapshot angka hari itu. Bisa diulang (versi bertambah)."""
    d = body.date or today_str()
    doc = await _save_closing(d, body.notes, user["name"])
    await log_audit(user, "closing", "daily_closing", doc["id"], None,
                    {"date": d, "omzet": doc["omzet"], "net_profit": doc["net_profit"]})
    out = await _dispatch_closing_whatsapp(doc, body.notes)
    result = clean(await db.daily_closings.find_one({"date": d}))
    result["whatsapp"] = out
    return result


async def _save_closing(d: str, notes: str, actor: str) -> dict:
    """Simpan/segarkan snapshot tutup buku untuk tanggal d (idempotent per tanggal)."""
    snap = await _closing_snapshot(d)
    existing = await db.daily_closings.find_one({"date": d})
    doc = {
        **snap,
        "id": existing["id"] if existing else new_id(),
        "notes": notes or (existing.get("notes", "") if existing else ""),
        "closed_by": actor, "closed_at": iso_now(),
        "version": int(existing.get("version", 1)) + 1 if existing else 1,
        "created_at": existing.get("created_at") if existing else iso_now(),
    }
    await db.daily_closings.update_one({"date": d}, {"$set": doc}, upsert=True)
    label = "Tutup Buku Diperbarui" if existing else "Tutup Buku Harian"
    await add_activity("closing", label, f"{d} · omzet Rp {int(snap['omzet']):,} · laba Rp {int(snap['net_profit']):,}",
                       snap["omzet"], actor)
    await add_notification("closing", label, f"{d} · laba bersih Rp {int(snap['net_profit']):,}", "success")
    await rt_emit(["closing", "dashboard"], {"date": d})
    return doc


async def _wa_recipients() -> List[dict]:
    recs = await get_setting("wa_recipients", None)
    if not recs:
        return []
    out = []
    for r in recs:
        if isinstance(r, str):
            r = {"name": "", "number": r}
        number = whatsapp.normalize_number(r.get("number"))
        if number:
            out.append({"name": r.get("name") or number, "number": number})
    return out


async def _dispatch_closing_whatsapp(closing: dict, notes: str = "", trigger: str = "manual") -> dict:
    """Kirim rekap tutup buku ke WhatsApp. Tidak boleh menggagalkan tutup buku."""
    try:
        recipients = await _wa_recipients()
        store = await _store_info()
        if not recipients:
            await add_notification("whatsapp", "Nomor WhatsApp Belum Diisi",
                                   "Tambahkan nomor penerima rekap di Pengaturan → Rekap WhatsApp", "warning")
            return {"text": whatsapp.build_closing_text(clean(closing), store, notes),
                    "provider": whatsapp.provider_info(), "results": [], "sent_count": 0, "mode": "manual"}
        out = await whatsapp.send_closing(clean(closing), store, recipients, notes)
        upd = {"wa_status": out["mode"], "wa_results": out["results"], "wa_attempt_at": iso_now()}
        if out["sent_count"]:
            upd["wa_sent_at"] = iso_now()
        await db.daily_closings.update_one({"date": closing["date"]}, {"$set": upd})
        if out["sent_count"]:
            await add_notification("whatsapp", "Rekap WhatsApp Terkirim",
                                   f"{closing['date']} · terkirim ke {out['sent_count']} nomor", "success")
        else:
            await add_notification("whatsapp", "Rekap WhatsApp Siap Dikirim",
                                   f"{closing['date']} · tekan tombol Kirim ke WhatsApp di halaman Tutup Buku", "info")
        await _wa_log("closing", closing.get("date", ""), out, trigger)
        return out
    except Exception as e:
        logger.error("Dispatch rekap WhatsApp gagal: %s", e)
        return {"text": "", "provider": whatsapp.provider_info(), "results": [],
                "sent_count": 0, "mode": "manual", "error": str(e)[:200]}


async def _wa_log(kind: str, date: str, out: dict, trigger: str = "manual"):
    """Catat setiap upaya kirim rekap supaya owner bisa audit & kirim ulang."""
    try:
        await db.wa_logs.insert_one({
            "id": new_id(), "kind": kind, "date": date, "trigger": trigger,
            "mode": out.get("mode"), "sent_count": out.get("sent_count", 0),
            "results": [{k: v for k, v in r.items() if k != "link"} for r in (out.get("results") or [])],
            "provider": (out.get("provider") or {}).get("provider"),
            "configured": bool((out.get("provider") or {}).get("configured")),
            "error": out.get("error"),
            "created_at": iso_now(),
        })
        await rt_emit(["whatsapp"])
    except Exception as e:
        logger.warning("Gagal mencatat log WhatsApp: %s", e)


class WaSettingsBody(BaseModel):
    recipients: List[Dict[str, str]] = []
    auto_enabled: bool = True
    auto_time: str = "21:00"


@api.get("/whatsapp/settings")
async def get_wa_settings(user: dict = Depends(require_roles("owner", "admin"))):
    return {
        "recipients": await _wa_recipients(),
        "auto_enabled": bool(await get_setting("wa_auto_enabled", True)),
        "auto_time": str(await get_setting("wa_auto_time", "21:00"))[:5],
        "provider": whatsapp.provider_info(),
    }


@api.put("/whatsapp/settings")
async def put_wa_settings(body: WaSettingsBody, user: dict = Depends(require_roles("owner"))):
    recs = []
    for r in body.recipients:
        number = whatsapp.normalize_number(r.get("number", ""))
        if not number:
            continue
        if len(number) < 10:
            raise HTTPException(400, f"Nomor WhatsApp tidak valid: {r.get('number')}")
        recs.append({"name": (r.get("name") or "").strip() or number, "number": number})
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", body.auto_time or ""):
        raise HTTPException(400, "Jam kirim harus format HH:MM (24 jam), mis. 21:00")
    await db.settings.update_one({"key": "wa_recipients"}, {"$set": {"value": recs}}, upsert=True)
    await db.settings.update_one({"key": "wa_auto_enabled"}, {"$set": {"value": bool(body.auto_enabled)}}, upsert=True)
    await db.settings.update_one({"key": "wa_auto_time"}, {"$set": {"value": body.auto_time}}, upsert=True)
    await log_audit(user, "update", "whatsapp_settings", "wa", None,
                    {"count": len(recs), "auto_enabled": body.auto_enabled, "auto_time": body.auto_time})
    return await get_wa_settings(user)


@api.get("/whatsapp/log")
async def get_wa_log(limit: int = 30, user: dict = Depends(require_roles("owner", "admin"))):
    """Riwayat upaya pengiriman rekap (otomatis maupun manual)."""
    rows = await db.wa_logs.find().sort("created_at", -1).to_list(max(min(limit, 100), 1))
    return [clean(r) for r in rows]


@api.post("/whatsapp/test")
async def send_wa_test(user: dict = Depends(require_roles("owner"))):
    """Kirim pesan uji ke semua nomor penerima.

    Bila kredensial provider belum diisi, kembalikan tautan wa.me 1-tap
    supaya owner tetap bisa memastikan nomornya benar.
    """
    recipients = await _wa_recipients()
    if not recipients:
        raise HTTPException(400, "Belum ada nomor penerima. Tambahkan dulu di Pengaturan.")
    store = await _store_info()
    nama = (store or {}).get("name") or "Berkah Ayam Mili"
    text = (f"*UJI COBA REKAP — {nama.upper()}*\n"
            "Pesan ini dikirim untuk memastikan nomor WhatsApp penerima sudah benar.\n"
            f"Rekap tutup buku harian akan dikirim otomatis setiap hari jam "
            f"{str(await get_setting('wa_auto_time', '21:00'))[:5]} WIB.\n\n"
            "_Dikirim oleh sistem Berkah Ayam Mili_")
    results = []
    configured = whatsapp.is_configured()
    for rec in recipients:
        item = {"name": rec["name"], "number": rec["number"],
                "link": whatsapp.wa_me_link(rec["number"], text), "sent": False, "error": None}
        if configured:
            try:
                res = await whatsapp.send_text(rec["number"], text)
                item["sent"] = True
                item["message_id"] = (res.get("messages") or [{}])[0].get("id")
            except Exception as e:
                item["error"] = str(e)[:300]
        results.append(item)
    sent = sum(1 for r in results if r["sent"])
    out = {"text": text, "provider": whatsapp.provider_info(), "results": results,
           "sent_count": sent, "mode": "auto" if (configured and sent) else "manual"}
    await _wa_log("test", today_str(), out, "uji coba")
    return out


@api.post("/daily-closing/{cid}/whatsapp")
async def send_closing_whatsapp(cid: str, user: dict = Depends(require_roles("owner", "admin"))):
    """Siapkan/kirim rekap. Kalau provider belum dikonfigurasi, kembalikan tautan 1-tap."""
    c = await db.daily_closings.find_one({"id": cid}) or await db.daily_closings.find_one({"date": cid})
    if not c:
        raise HTTPException(404, "Tutup buku tidak ditemukan")
    return await _dispatch_closing_whatsapp(c, c.get("notes", ""))


async def auto_closing_worker():
    """Tutup buku + kirim rekap otomatis pada jam yang diatur owner (WIB)."""
    await asyncio.sleep(20)
    last_done = None
    while True:
        try:
            await asyncio.sleep(30)
            if not bool(await get_setting("wa_auto_enabled", True)):
                continue
            target = str(await get_setting("wa_auto_time", "21:00"))[:5]
            now = now_jkt()
            if now.strftime("%H:%M") != target:
                continue
            d = now.strftime("%Y-%m-%d")
            if last_done == d:
                continue
            existing = await db.daily_closings.find_one({"date": d})
            if existing and existing.get("wa_sent_at"):
                last_done = d
                continue
            logger.info("Tutup buku otomatis dijalankan untuk %s", d)
            doc = await _save_closing(d, "", "Sistem (Otomatis)")
            await _dispatch_closing_whatsapp(doc, trigger="otomatis")
            last_done = d
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Penjadwal tutup buku otomatis error: %s", e)



@api.get("/daily-closing/{cid}")
async def get_closing(cid: str, user: dict = Depends(require_roles("owner", "admin"))):
    c = await db.daily_closings.find_one({"id": cid}) or await db.daily_closings.find_one({"date": cid})
    if not c:
        raise HTTPException(404, "Tutup buku tidak ditemukan")
    return clean(c)


@api.get("/daily-closing/{cid}/pdf")
async def get_closing_pdf(cid: str, user: dict = Depends(require_roles("owner", "admin"))):
    c = await db.daily_closings.find_one({"id": cid}) or await db.daily_closings.find_one({"date": cid})
    if not c:
        raise HTTPException(404, "Tutup buku tidak ditemukan")
    store = await _store_info()
    pdf = await run_in_threadpool(pdf_reports.daily_closing_pdf, clean(c), store, user["name"])
    return _pdf_response(pdf, f"tutup-buku_{c['date']}.pdf")


# ------------------------- Realtime (WebSocket) -------------------------
@api.websocket("/ws")
async def realtime_socket(websocket: WebSocket):
    await ws_handler(websocket)


@api.get("/realtime/status")
async def realtime_status(user: dict = Depends(get_current_user)):
    return {"clients": rt_manager.count}


# ------------------------- File upload / serving -------------------------
@api.post("/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_roles("owner", "admin"))):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    if ext not in MIME_TYPES:
        raise HTTPException(400, "Format gambar tidak didukung (jpg, png, webp, gif)")
    fid = new_id()
    path = f"{APP_NAME}/products/{fid}.{ext}"
    data = await file.read()
    ct = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    try:
        result = put_object(path, data, ct)
    except Exception as e:
        logger.error(f"Upload gagal: {e}")
        raise HTTPException(502, "Gagal mengunggah gambar ke penyimpanan")
    await db.files.insert_one({"id": fid, "storage_path": result["path"], "content_type": ct,
                               "original_filename": file.filename, "size": result.get("size", len(data)),
                               "is_deleted": False, "created_at": iso_now()})
    return {"id": fid, "url": f"/api/files/{fid}"}


@api.get("/files/{fid}")
async def serve_file(fid: str):
    rec = await db.files.find_one({"id": fid, "is_deleted": False})
    if not rec:
        raise HTTPException(404, "File tidak ditemukan")
    try:
        data, ct = get_object(rec["storage_path"])
    except Exception as e:
        logger.error(f"Ambil file gagal: {e}")
        raise HTTPException(502, "Gagal memuat gambar")
    return Response(content=data, media_type=rec.get("content_type", ct),
                    headers={"Cache-Control": "public, max-age=86400"})


# ------------------------- wiring -------------------------
app.include_router(auth_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.sales.create_index("txn_id", unique=True, sparse=True)
    await db.sales.create_index("date")
    await db.daily_closings.create_index("date", unique=True)
    await seed_admin()
    await seed_demo(db)
    added = await ensure_potong_parts(db)
    if added:
        logger.info("Produk potongan ditambahkan: %s", ", ".join(added))
    try:
        await migrate_avg_weights()
        await refresh_all_avg_weights()
    except Exception as e:
        logger.error(f"Migrasi berat rata-rata gagal: {e}")
    # Nomor penerima rekap WhatsApp default (bisa diubah owner di Pengaturan).
    if await db.settings.find_one({"key": "wa_recipients"}) is None:
        await db.settings.update_one({"key": "wa_recipients"}, {"$set": {"value": [
            {"name": "Owner", "number": "6281289478221"}]}}, upsert=True)
    app.state.auto_closing_task = asyncio.create_task(auto_closing_worker())
    logger.info("Penjadwal tutup buku otomatis aktif (jam %s WIB)",
                str(await get_setting("wa_auto_time", "21:00"))[:5])
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    logger.info("Berkah Ayam Mili API started")


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "auto_closing_task", None)
    if task:
        task.cancel()
    client.close()
