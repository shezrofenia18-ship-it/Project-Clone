from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import asyncio
import re
import secrets
import logging
import requests
from datetime import timedelta
from typing import List, Optional, Any, Dict

from fastapi import (FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form,
                     WebSocket, Request, Query)
from fastapi.responses import Response, PlainTextResponse
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
import finance
import reconcile
import maintenance
from finance import MODAL_CATEGORIES, OPEX_EXCLUDE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("berkah")

# ------------------------- object storage -------------------------
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "berkah-ayam-mili"
MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "gif": "image/gif", "webp": "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
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


async def record_movement(product: dict, mtype: str, delta: dict, before: dict, after: dict,
                          user: str, ref: str = ""):
    """Catat satu pergerakan stok.

    `delta`/`before`/`after` masing-masing berisi kunci "ekor", "kg", "pcs" —
    dulu fungsi ini menerima 14 argumen terpisah yang mudah tertukar urutannya.
    """
    await db.stock_movements.insert_one({
        "id": new_id(), "product_id": product["id"], "product_name": product["name"], "type": mtype,
        "qty_ekor": delta["ekor"], "qty_kg": delta["kg"], "qty_pcs": delta["pcs"],
        "before_ekor": before["ekor"], "before_kg": before["kg"], "before_pcs": before["pcs"],
        "after_ekor": after["ekor"], "after_kg": after["kg"], "after_pcs": after["pcs"],
        "user": user, "ref": ref, "date": today_str(), "created_at": iso_now(),
    })


async def _warn_low_stock(product: dict, after_kg: float, delta_kg: float, user: str):
    """Peringatan stok menipis (hanya saat stok berkurang, bukan saat ditambah)."""
    min_kg = float(product.get("min_stock_kg", 0) or 0)
    if not (min_kg > 0 and after_kg <= min_kg and delta_kg < 0):
        return
    pesan = f"Stok {product['name']} tersisa {after_kg} kg"
    await add_activity("stock_low", "Stok Menipis", pesan, 0, user)
    await add_notification("stock_low", "Stok Menipis", pesan, "warning")


async def apply_stock(product, delta_ekor, delta_kg, mtype, user, ref, allow_negative=False, delta_pcs=0):
    before = {"ekor": float(product.get("stock_ekor", 0) or 0),
              "kg": float(product.get("stock_kg", 0) or 0),
              "pcs": float(product.get("stock_pcs", 0) or 0)}
    delta = {"ekor": delta_ekor, "kg": delta_kg, "pcs": delta_pcs}
    after = {k: round(before[k] + delta[k], 3) for k in before}
    if not allow_negative and any(v < -0.0001 for v in after.values()):
        raise HTTPException(status_code=400, detail=f"STOK TIDAK MENCUKUPI untuk {product['name']}")
    await db.products.update_one({"id": product["id"]}, {"$set": {
        "stock_ekor": after["ekor"], "stock_kg": after["kg"], "stock_pcs": after["pcs"]}})
    await record_movement(product, mtype, delta, before, after, user, ref)
    product["stock_ekor"] = after["ekor"]
    product["stock_kg"] = after["kg"]
    product["stock_pcs"] = after["pcs"]
    await _warn_low_stock(product, after["kg"], delta_kg, user)
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


def is_whole_chicken(product: dict) -> bool:
    """Ayam utuh = produk yang punya satuan 'ekor' (Broiler/Kampung/Pejantan).

    Keputusan owner: ayam utuh HANYA dijual per ekor di POS. Owner membeli dengan
    ditimbang (mis. 15 ekor = 30 kg -> 2 kg/ekor), jadi saat satu ekor terjual,
    stok kg ikut berkurang sebesar berat rata-rata/ekor supaya angka kg & ekor
    tidak pernah berbeda lagi. Produk sampingan/potongan/fillet tidak terpengaruh
    (tetap boleh kg atau pcs).
    """
    return "ekor" in (product.get("units") or [])


def sale_line_weight(product: dict, unit: str, qty: float) -> float:
    """Berat (kg) yang benar-benar keluar dari stok untuk satu baris penjualan."""
    if unit == "kg":
        return round(float(qty), 3)
    if unit == "ekor":
        return round(float(qty) * effective_avg_weight(product), 3)
    return 0.0


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
    # Foto bukti pengeluaran (opsional) — diunggah lewat POST /api/upload?folder=proofs
    proof_file_id: str = ""
    proof_url: str = ""


class TargetBody(BaseModel):
    date: Optional[str] = None
    target_omzet: float = 0
    target_weight: float = 0
    target_ekor: float = 0
    target_laba: float = 0


# Metode pembayaran yang dipakai untuk pelunasan piutang & hutang. "piutang"
# sengaja TIDAK ada di sini: membayar piutang dengan piutang tidak masuk akal.
PAY_METHODS = ("cash", "transfer", "qris", "debit", "ewallet")
PAY_LABELS = {"cash": "Tunai", "transfer": "Transfer", "qris": "QRIS",
              "debit": "Kartu Debit", "ewallet": "E-Wallet"}

# Jenis penyesuaian stok. "mati" dipertahankan HANYA agar riwayat lama tetap
# terbaca; pilihan barunya adalah "salah_potong" (permintaan owner).
ADJUST_TYPES = ("penyesuaian", "rusak", "salah_potong", "susut", "mati")


class PayBody(BaseModel):
    amount: float
    method: str = "cash"
    note: str = ""


def check_pay_method(method: str) -> str:
    m = (method or "cash").strip().lower()
    if m not in PAY_METHODS:
        raise HTTPException(400, "Metode pembayaran tidak dikenal")
    return m


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


def _weight_guidance_item(p: dict) -> dict:
    """Satu baris panduan berat/ekor untuk sebuah produk (dipisah agar mudah diuji)."""
    used, source, dflt = resolve_avg_weight(p)
    hpp_kg = float(p.get("hpp_kg", 0) or 0)
    hpp_ekor = round(hpp_kg * used, 2) if used > 0 else float(p.get("hpp_ekor", 0) or 0)
    price_ekor = float(p.get("price_ekor", 0) or 0)
    profit = round(price_ekor - hpp_ekor, 2) if price_ekor > 0 else 0.0
    return {
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
    }


@api.get("/products/weight-guidance")
async def products_weight_guidance(user: dict = Depends(require_roles("owner", "admin"))):
    """Panduan berat/ekor: produk mana yang masih memakai perkiraan bawaan sistem.

    Dipakai frontend untuk memandu owner mengonfirmasi berat rata-rata per ekor.
    Selama belum dikonfirmasi, sistem TETAP memakai berat perkiraan (hpp_ekor != 0).
    """
    prods = await db.products.find({"active": {"$ne": False}}).sort("name", 1).to_list(1000)
    items = [_weight_guidance_item(p) for p in prods if sells_per_ekor(p)]
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
async def list_purchases(user: dict = Depends(require_roles("owner", "admin"))):
    p = await db.purchases.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


async def _purchase_lines(body: "PurchaseBody"):
    """Susun baris pembelian + totalnya, sekaligus memastikan produknya ada."""
    items_out, products = [], {}
    bird_value = weight_all = ekor_all = 0.0
    for it in body.items:
        product = await db.products.find_one({"id": it.product_id})
        if not product:
            raise HTTPException(404, "Produk tidak ditemukan")
        products[it.product_id] = product
        bird_value += it.total_price
        weight_all += it.total_weight
        ekor_all += it.ekor
        items_out.append({"product_id": it.product_id, "name": product["name"], "ekor": it.ekor,
                          "total_weight": it.total_weight,
                          "avg_weight": round(it.total_weight / it.ekor, 3) if it.ekor else 0,
                          "buy_price_kg": round(it.total_price / it.total_weight, 2) if it.total_weight else 0,
                          "subtotal": round(it.total_price, 2)})
    return items_out, products, bird_value, weight_all, ekor_all


def _purchase_totals(body: "PurchaseBody", bird_value: float, weight_all: float, ekor_all: float) -> dict:
    """Modal total (ayam + transport + biaya lain) dan biaya efektifnya."""
    total_modal = round(bird_value + body.transport_cost + body.other_cost, 2)
    return {
        "total_modal": total_modal,
        "eff_cost_kg": round(total_modal / weight_all, 2) if weight_all else 0,
        "eff_cost_ekor": round(total_modal / ekor_all, 2) if ekor_all else 0,
        "payable": round(total_modal - body.paid, 2),
    }


def _purchase_doc(body, supplier, pid, items_out, bird_value, weight_all, ekor_all, tot, created_by) -> dict:
    payable_amt = tot["payable"]
    return {
        "id": pid, "supplier_id": body.supplier_id, "supplier_name": supplier["name"],
        "date": body.date or today_str(), "items": items_out,
        "transport_cost": body.transport_cost, "other_cost": body.other_cost,
        "total_bird_value": round(bird_value, 2), "total_weight": round(weight_all, 3),
        "total_ekor": ekor_all,
        "total_modal": tot["total_modal"], "effective_cost_kg": tot["eff_cost_kg"],
        "effective_cost_ekor": tot["eff_cost_ekor"],
        "paid": body.paid, "payable": max(0, payable_amt),
        "payment_status": "lunas" if payable_amt <= 0 else "kredit",
        "notes": body.notes, "created_by": created_by, "created_at": iso_now(),
    }


async def _apply_purchase_to_stock(body, user, pid, supplier, products, bird_value, tot) -> dict:
    """Tambah stok, perbarui harga beli & HPP/ekor tiap produk. Kembalikan harga terakhir supplier."""
    last_prices = supplier.get("last_prices", {}) or {}
    for it in body.items:
        product = products[it.product_id]
        await apply_stock(product, it.ekor, it.total_weight, "pembelian", user["name"], pid)
        share = round(tot["total_modal"] * (it.total_price / bird_value), 2) if bird_value else it.total_price
        item_hpp_kg = round(share / it.total_weight, 2) if it.total_weight else tot["eff_cost_kg"]
        item_buy_kg = round(it.total_price / it.total_weight, 2) if it.total_weight else 0
        await db.products.update_one({"id": it.product_id}, {"$set": {"buy_price_kg": item_buy_kg}})
        # Berat/ekor diakumulasi dari semua ayam masuk → HPP/ekor otomatis.
        await recompute_avg_weight(it.product_id, add_ekor=it.ekor,
                                   add_weight=it.total_weight, set_hpp_kg=item_hpp_kg)
        last_prices[product["category"]] = item_buy_kg
    return last_prices


async def _record_purchase_ledger(body, user, pid, supplier, doc, tot, last_prices):
    """Sisi keuangan pembelian: saldo supplier, tagihan hutang, dan pengeluaran modal."""
    payable_amt = tot["payable"]
    await db.suppliers.update_one({"id": body.supplier_id}, {
        "$set": {"last_prices": last_prices},
        "$inc": {"total_purchase": tot["total_modal"], "payable": max(0, payable_amt)}})
    if payable_amt > 0:
        await db.payables.insert_one({
            "id": new_id(), "supplier_id": body.supplier_id, "supplier_name": supplier["name"],
            "purchase_id": pid, "amount": tot["total_modal"], "paid": body.paid,
            "remaining": payable_amt, "due_date": body.due_date, "status": "belum_lunas",
            "date": doc["date"], "created_at": iso_now()})
    await db.expenses.insert_one({
        "id": new_id(), "date": doc["date"], "category": "Pembelian Ayam",
        "amount": tot["total_modal"],
        # cash_amount = uang yang benar-benar keluar saat ini (sisanya jadi hutang,
        # dicatat sebagai kas keluar saat dilunasi) -> kas tidak dihitung dobel.
        "cash_amount": round(float(body.paid or 0), 2),
        "description": f"Pembelian dari {supplier['name']}", "ref": pid,
        "created_by": user["name"], "created_at": iso_now()})


async def _persist_purchase(body: "PurchaseBody", user: dict, pid: str):
    """Simpan satu pembelian: baris & total -> dokumen -> stok -> keuangan."""
    supplier = await db.suppliers.find_one({"id": body.supplier_id})
    if not supplier:
        raise HTTPException(404, "Supplier tidak ditemukan")
    items_out, products, bird_value, weight_all, ekor_all = await _purchase_lines(body)
    tot = _purchase_totals(body, bird_value, weight_all, ekor_all)
    doc = _purchase_doc(body, supplier, pid, items_out, bird_value, weight_all, ekor_all,
                        tot, user["name"])
    await db.purchases.insert_one(doc)
    last_prices = await _apply_purchase_to_stock(body, user, pid, supplier, products, bird_value, tot)
    await _record_purchase_ledger(body, user, pid, supplier, doc, tot, last_prices)
    return doc, weight_all, tot["total_modal"]


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
    await rt_emit(["purchases", "expenses", "payables", "suppliers", "stock", "products", "dashboard"], {"id": pid})
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
    await rt_emit(["purchases", "expenses", "payables", "suppliers", "stock", "products", "dashboard"], {"id": pid})
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
    await rt_emit(["purchases", "expenses", "payables", "suppliers", "stock", "products", "dashboard"], {"id": pid})
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
    weight_from_ekor = 0.0
    products_cache = {}
    for it in body.items:
        product = await db.products.find_one({"id": it.product_id})
        if not product:
            raise HTTPException(404, "Produk tidak ditemukan")
        products_cache[it.product_id] = product
        # Ayam utuh hanya boleh dijual per ekor (keputusan owner). Dikunci di server
        # supaya transaksi offline lama / klien lain tidak bisa menyelipkan jual kg.
        if it.unit == "kg" and is_whole_chicken(product):
            raise HTTPException(400, f"{product['name']} hanya bisa dijual per ekor, bukan per kg")
        line = round(it.qty * it.price, 2)
        avg_w = 0.0
        if it.unit == "kg":
            hpp_unit = float(product.get("hpp_kg", 0) or 0)
            total_weight += it.qty
        elif it.unit == "ekor":
            hpp_unit = float(product.get("hpp_ekor", 0) or 0)
            total_ekor += it.qty
            avg_w = effective_avg_weight(product)
        else:
            hpp_unit = float(product.get("hpp_pcs", 0) or 0)
        # Berat nyata yang keluar dari stok. Untuk per-ekor = qty x berat rata-rata/ekor,
        # DISIMPAN di baris penjualan supaya pembatalan mengembalikan angka yang sama
        # walaupun berat rata-rata sudah berubah karena pembelian baru.
        line_weight = sale_line_weight(product, it.unit, it.qty)
        if it.unit == "ekor":
            weight_from_ekor += line_weight
        hpp_total = round(hpp_unit * it.qty, 2)
        subtotal += line
        total_hpp += hpp_total
        items_out.append({"product_id": it.product_id, "name": product["name"], "unit": it.unit,
                          "qty": it.qty, "price": it.price, "subtotal": line,
                          "hpp_unit": hpp_unit, "hpp_total": hpp_total, "category": product["category"],
                          "weight_kg": line_weight, "avg_weight_used": avg_w})
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
        # total_weight = berat TERUKUR yang keluar dari stok: item per-kg + hasil
        # konversi item per-ekor (qty x berat rata-rata/ekor). Dipecah agar tetap
        # bisa ditelusuri dari mana kg-nya berasal.
        "total_weight": round(total_weight + weight_from_ekor, 3),
        "total_weight_kg_unit": round(total_weight, 3),
        "total_weight_ekor": round(weight_from_ekor, 3),
        "total_ekor": total_ekor,
        "status": "selesai", "created_at": body.offline_at or iso_now(),
        "offline": bool(body.offline_at),
        "synced_at": iso_now() if body.offline_at else None,
    }
    for it, out in zip(body.items, items_out):
        product = products_cache[it.product_id]
        d_ekor = -it.qty if it.unit == "ekor" else 0
        # Jual 1 ekor -> stok ekor -1 DAN stok kg berkurang sebesar berat/ekor,
        # sehingga kedua angka stok selalu bergerak bersama.
        d_kg = -float(out.get("weight_kg", 0) or 0)
        d_pcs = -it.qty if it.unit == "pcs" else 0
        await apply_stock(product, d_ekor, d_kg, "penjualan", user["name"], sid, allow_negative=allow_neg, delta_pcs=d_pcs)
    await db.sales.insert_one(doc)
    await db.incomes.insert_one({"id": new_id(), "date": doc["date"], "category": "Penjualan Ayam",
                                 "amount": paid, "source": "pos", "ref": sid, "created_at": iso_now()})
    if customer:
        await db.customers.update_one({"id": customer["id"]}, {"$inc": {"total_purchase": total, "receivable": receivable}})
    if receivable > 0:
        # Setiap kekurangan bayar WAJIB punya tagihan, walau pembelinya "Umum".
        # Tanpa ini, piutang hanya tercatat di dokumen penjualan dan tidak pernah
        # muncul di modul Keuangan (pernah terjadi: selisih Rp 242.536).
        await db.receivables.insert_one({"id": new_id(),
                                         "customer_id": customer["id"] if customer else None,
                                         "customer_name": customer["name"] if customer else "Umum",
                                         "sale_id": sid, "amount": total, "paid": paid, "remaining": receivable,
                                         "due_date": None, "status": "belum_lunas", "date": doc["date"],
                                         "created_at": iso_now()})
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
    await rt_emit(["sales", "dashboard", "stock", "receivables", "incomes", "customers"], {"total": total, "id": sid})
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
        # Kembalikan kg PERSIS seperti saat penjualan (tersimpan di baris item).
        # Transaksi lama tidak punya "weight_kg": untuk item per-kg berartinya qty,
        # untuk item per-ekor berartinya 0 karena dulu stok kg memang tidak dipotong.
        w = it.get("weight_kg")
        if w is None:
            w = it["qty"] if it["unit"] == "kg" else 0
        d_kg = float(w or 0)
        d_pcs = it["qty"] if it["unit"] == "pcs" else 0
        await apply_stock(product, d_ekor, d_kg, "retur", user["name"], sid, allow_negative=True, delta_pcs=d_pcs)
    await db.sales.update_one({"id": sid}, {"$set": {"status": "batal"}})
    await db.incomes.delete_many({"ref": sid})
    # Piutang & saldo pelanggan HARUS ikut dikoreksi, kalau tidak akan tertinggal
    # tagihan "hantu" di Keuangan dan laporan piutang jadi salah.
    sisa_piutang = 0.0
    async for r in db.receivables.find({"sale_id": sid}):
        sisa_piutang += float(r.get("remaining", 0) or 0)
        await db.receivables.update_one({"id": r["id"]},
                                        {"$set": {"status": "batal", "remaining": 0}})
    if sale.get("customer_id"):
        await db.customers.update_one({"id": sale["customer_id"]}, {"$inc": {
            "total_purchase": -float(sale.get("total", 0) or 0),
            "receivable": -round(sisa_piutang, 2)}})
    await add_activity("cancel", "Transaksi Dibatalkan", f"Transaksi {sid[:8]} dibatalkan", sale["total"], user["name"])
    await add_notification("cancel", "Transaksi Dibatalkan", f"Rp {int(sale['total']):,} oleh {user['name']}", "danger")
    await log_audit(user, "cancel", "sale", sid, {"status": "selesai"}, {"status": "batal"})
    await rt_emit(["sales", "dashboard", "stock", "receivables", "incomes", "customers"], {"id": sid})
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
    if body.type not in ADJUST_TYPES:
        raise HTTPException(400, "Jenis penyesuaian tidak dikenal")
    await apply_stock(product, body.delta_ekor, body.delta_kg, body.type, user["name"], body.reason, allow_negative=True)
    await log_audit(user, "adjust", "stock", body.product_id, None,
                    {"delta_kg": body.delta_kg, "delta_ekor": body.delta_ekor, "reason": body.reason})
    await add_activity("adjust", "Penyesuaian Stok", f"{product['name']}: {body.reason}", 0, user["name"])
    await rt_emit(["stock", "products", "dashboard"], {"id": body.product_id})
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
    if doc.get("proof_file_id") and not doc.get("proof_url"):
        doc["proof_url"] = f"/api/files/{doc['proof_file_id']}"
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
    if r.get("status") == "batal":
        raise HTTPException(400, "Tagihan ini sudah dibatalkan")
    amount = round(float(body.amount or 0), 2)
    method = check_pay_method(body.method)
    sisa = round(float(r.get("remaining", 0) or 0), 2)
    if amount <= 0:
        raise HTTPException(400, "Jumlah bayar harus lebih dari nol")
    if sisa <= 0:
        raise HTTPException(400, "Piutang ini sudah lunas")
    if amount > sisa + 0.01:
        raise HTTPException(400, f"Jumlah bayar melebihi sisa piutang (Rp {int(sisa):,})".replace(",", "."))
    remaining = round(sisa - amount, 2)
    status = "lunas" if remaining <= 0 else "belum_lunas"
    entry = {"id": new_id(), "amount": amount, "method": method, "note": body.note,
             "date": today_str(), "by": user["name"], "at": iso_now()}
    await db.receivables.update_one({"id": rid}, {
        "$set": {"remaining": max(0, remaining), "status": status, "last_method": method},
        "$inc": {"paid": amount},
        "$push": {"payments": entry}})
    await db.customers.update_one({"id": r["customer_id"]}, {"$inc": {"receivable": -amount}})
    # Transaksi aslinya ikut diperbarui supaya Riwayat Transaksi & laporan
    # tidak lagi menampilkan piutang yang sebetulnya sudah dibayar.
    if r.get("sale_id"):
        await db.sales.update_one({"id": r["sale_id"]}, {"$set": {
            "receivable": max(0, remaining),
            "payment_status": "lunas" if remaining <= 0 else "piutang"}})
    await db.incomes.insert_one({"id": new_id(), "date": today_str(), "category": "Pembayaran Piutang",
                                 "amount": amount, "source": "receivable", "ref": rid,
                                 "method": method, "note": body.note, "created_at": iso_now()})
    await add_activity("payment", "Pembayaran Piutang",
                       f"{r['customer_name']} bayar via {PAY_LABELS[method]}", amount, user["name"])
    await log_audit(user, "pay", "receivable", rid, {"remaining": sisa},
                    {"remaining": max(0, remaining), "method": method})
    await rt_emit(["receivables", "incomes", "sales", "customers", "dashboard"], {"id": rid})
    return {"ok": True, "remaining": max(0, remaining), "method": method}


@api.get("/payables")
async def list_payables(user: dict = Depends(require_roles("owner", "admin"))):
    p = await db.payables.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


@api.post("/payables/{pid}/pay")
async def pay_payable(pid: str, body: PayBody, user: dict = Depends(require_roles("owner", "admin"))):
    p = await db.payables.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Hutang tidak ditemukan")
    if p.get("status") == "batal":
        raise HTTPException(400, "Hutang ini sudah dibatalkan")
    amount = round(float(body.amount or 0), 2)
    method = check_pay_method(body.method)
    sisa = round(float(p.get("remaining", 0) or 0), 2)
    if amount <= 0:
        raise HTTPException(400, "Jumlah bayar harus lebih dari nol")
    if sisa <= 0:
        raise HTTPException(400, "Hutang ini sudah lunas")
    if amount > sisa + 0.01:
        raise HTTPException(400, f"Jumlah bayar melebihi sisa hutang (Rp {int(sisa):,})".replace(",", "."))
    remaining = round(sisa - amount, 2)
    status = "lunas" if remaining <= 0 else "belum_lunas"
    entry = {"id": new_id(), "amount": amount, "method": method, "note": body.note,
             "date": today_str(), "by": user["name"], "at": iso_now()}
    await db.payables.update_one({"id": pid}, {
        "$set": {"remaining": max(0, remaining), "status": status, "last_method": method},
        "$inc": {"paid": amount},
        "$push": {"payments": entry}})
    await db.suppliers.update_one({"id": p["supplier_id"]}, {"$inc": {"payable": -amount}})
    await db.expenses.insert_one({"id": new_id(), "date": today_str(), "category": "Pembayaran Hutang",
                                  "amount": amount, "cash_amount": amount, "method": method,
                                  "description": f"Bayar ke {p['supplier_name']} via {PAY_LABELS[method]}",
                                  "note": body.note,
                                  "ref": pid, "created_by": user["name"], "created_at": iso_now()})
    await add_activity("payment", "Pembayaran Supplier",
                       f"{p['supplier_name']} via {PAY_LABELS[method]}", amount, user["name"])
    await log_audit(user, "pay", "payable", pid, {"remaining": sisa},
                    {"remaining": max(0, remaining), "method": method})
    await rt_emit(["payables", "expenses", "suppliers", "purchases", "dashboard"], {"id": pid})
    return {"ok": True, "remaining": max(0, remaining), "method": method}


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


# ------------------------- Pemeliharaan data (sinkronisasi) -------------------------
@api.get("/maintenance/consistency")
async def check_consistency(user: dict = Depends(require_roles("owner", "admin"))):
    """Periksa apakah angka turunan (pengeluaran, saldo, status bayar) masih cocok
    dengan sumbernya (penjualan & pembelian). Tidak mengubah apa pun."""
    res = await reconcile.audit(db, fix=False)
    res["checked_at"] = iso_now()
    return res


@api.post("/maintenance/reconcile")
async def run_reconcile(user: dict = Depends(require_roles("owner"))):
    """Perbaiki ketidaksinkronan data. Aman dijalankan berulang kali."""
    res = await reconcile.audit(db, fix=True, actor=user["name"])
    res["checked_at"] = iso_now()
    if res["fixed_count"]:
        await add_activity("adjust", "Sinkronisasi Data",
                           f"{res['fixed_count']} data dirapikan", 0, user["name"])
        await log_audit(user, "reconcile", "maintenance", "-", None, {"fixed": res["fixed_count"]})
        await rt_emit(["dashboard", "sales", "expenses", "incomes", "receivables",
                       "payables", "customers", "suppliers", "purchases"], {"fixed": res["fixed_count"]})
    return res


# ------------------------- Dashboard -------------------------
@api.get("/dashboard")
async def dashboard(user: dict = Depends(require_roles("owner", "admin"))):
    d = today_str()
    sales_today = await db.sales.find({"date": d, "status": {"$ne": "batal"}}).to_list(5000)
    exp_today = await db.expenses.find({"date": d}).to_list(2000)
    inc_today = await db.incomes.find({"date": d}).to_list(2000)
    # SATU rumus untuk Dashboard, Laporan, & Tutup Buku (lihat finance.py).
    fin = finance.summarize(sales_today, exp_today, inc_today)
    omzet, hpp, laba, margin = fin["omzet"], fin["hpp"], fin["gross_profit"], fin["margin"]
    weight, ekor = fin["weight"], fin["ekor"]
    net_profit = fin["net_profit"]
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
            # "expense" = biaya operasional saja (beli ayam sudah masuk HPP, tidak dikurangi 2x)
            "expense": fin["opex"], "opex": fin["opex"], "expense_total": fin["expense_total"],
            "net_profit": net_profit, "net_margin": fin["net_margin"],
            # arus kas: di sinilah uang beli ayam & pelunasan hutang ikut dihitung
            "cash_in": fin["cash_in"], "cash_out": fin["cash_out"], "net_cash": fin["net_cash"],
            "modal_value": fin["modal_value"], "modal_cash": fin["modal_cash"],
            "piutang_baru": fin["piutang_baru"], "kas_dari_penjualan": fin["kas_dari_penjualan"],
            "target": {"omzet": t_omzet, "weight": target.get("target_weight", 0),
                       "ekor": target.get("target_ekor", 0), "laba": target.get("target_laba", 0),
                       "achievement": achievement},
            "chart": chart, "products_perf": products_perf, "critical_stock": critical,
            "stock_value": round(stock_value, 2), "recent_sales": [clean(r) for r in recent],
            "activities": [clean(a) for a in activities], "prices": prices}


@api.get("/dashboard/monthly")
async def dashboard_monthly(months: int = 12, user: dict = Depends(require_roles("owner", "admin"))):
    """Tren bulanan omzet, laba kotor, laba bersih usaha, & uang bersih (kas).

    Rumus identik dengan Dashboard harian, Laporan, dan Tutup Buku (finance.py),
    sehingga total 12 bulan selalu cocok dengan jumlah laporan hariannya.
    """
    months = max(1, min(int(months or 12), 36))
    now = now_jkt()
    keys = finance.month_series(now.year, now.month, months)
    start = keys[0] + "-01"

    sales = await db.sales.find({"date": {"$gte": start}, "status": {"$ne": "batal"}}).to_list(100000)
    expenses = await db.expenses.find({"date": {"$gte": start}}).to_list(100000)
    incomes = await db.incomes.find({"date": {"$gte": start}}).to_list(100000)

    buckets: Dict[str, Dict[str, list]] = {k: {"sales": [], "expenses": [], "incomes": []} for k in keys}
    for coll, rows in (("sales", sales), ("expenses", expenses), ("incomes", incomes)):
        for row in rows:
            b = buckets.get(finance.month_key(row.get("date", "")))
            if b is not None:
                b[coll].append(row)

    series = []
    for k in keys:
        b = buckets[k]
        fin = finance.summarize(b["sales"], b["expenses"], b["incomes"])
        series.append({
            "month": k, "label": finance.month_label(k),
            "omzet": fin["omzet"], "hpp": fin["hpp"], "laba_kotor": fin["gross_profit"],
            "opex": fin["opex"], "laba_bersih": fin["net_profit"], "margin": fin["margin"],
            "cash_in": fin["cash_in"], "cash_out": fin["cash_out"], "net_cash": fin["net_cash"],
            "modal": fin["modal_value"],
            "txn_count": fin["txn_count"], "weight": fin["weight"], "ekor": fin["ekor"],
        })

    filled = [m for m in series if m["omzet"] or m["txn_count"]]
    total_omzet = round(sum(m["omzet"] for m in series), 2)
    total_kotor = round(sum(m["laba_kotor"] for m in series), 2)
    total_bersih = round(sum(m["laba_bersih"] for m in series), 2)
    best = max(series, key=lambda m: m["omzet"]) if series else None
    this_m = series[-1] if series else None
    prev_m = series[-2] if len(series) > 1 else None

    def growth(cur, prev):
        if not prev:
            return None
        return round((cur - prev) / abs(prev) * 100, 2)

    return {
        "months": months, "series": series,
        "summary": {
            "total_omzet": total_omzet, "total_laba_kotor": total_kotor,
            "total_laba_bersih": total_bersih,
            "avg_omzet": round(total_omzet / len(filled), 2) if filled else 0,
            "avg_laba_bersih": round(total_bersih / len(filled), 2) if filled else 0,
            "active_months": len(filled),
            "this_month": this_m["label"] if this_m else None,
            "this_omzet": this_m["omzet"] if this_m else 0,
            "this_laba_bersih": this_m["laba_bersih"] if this_m else 0,
            "growth_omzet": growth(this_m["omzet"], prev_m["omzet"]) if this_m and prev_m else None,
            "growth_laba_bersih": growth(this_m["laba_bersih"], prev_m["laba_bersih"]) if this_m and prev_m else None,
            "prev_month": prev_m["label"] if prev_m else None,
            "best_month": best["label"] if best and best["omzet"] else None,
            "best_omzet": best["omzet"] if best else 0,
        },
    }



# ------------------------- Reports -------------------------
@api.get("/reports/profit-loss")
async def report_pl(start: Optional[str] = None, end: Optional[str] = None,
                    user: dict = Depends(require_roles("owner", "admin"))):
    q = {"status": {"$ne": "batal"}}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    sales = await db.sales.find(q).to_list(20000)
    eq = {}
    if start and end:
        eq["date"] = {"$gte": start, "$lte": end}
    exps = await db.expenses.find(eq).to_list(20000)
    incs = await db.incomes.find(eq).to_list(20000)
    # SATU rumus untuk semua halaman (finance.py) — sama dengan Dashboard & Tutup Buku.
    fin = finance.summarize(sales, exps, incs)
    return {"omzet": fin["omzet"], "hpp": fin["hpp"], "gross_profit": fin["gross_profit"],
            "opex": fin["opex"], "net_profit": fin["net_profit"],
            "gross_margin": fin["margin"], "net_margin": fin["net_margin"],
            "expense_total": fin["expense_total"],
            "modal_value": fin["modal_value"], "modal_cash": fin["modal_cash"],
            "cash_in": fin["cash_in"], "cash_out": fin["cash_out"], "net_cash": fin["net_cash"],
            "txn_count": fin["txn_count"], "weight": fin["weight"], "ekor": fin["ekor"],
            "expenses_by_category": fin["expenses_by_category"]}


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


# ------------------------- Tautan PDF publik (untuk lampiran WhatsApp) -------------------------
# WhatsApp mode 1-tap (wa.me) TIDAK bisa melampirkan file, jadi PDF dibagikan
# sebagai URL ber-token acak: panjang 43 karakter, kedaluwarsa, dan hanya
# mengizinkan SATU laporan tertentu. Tidak ada data sensitif di dalam URL.
async def _create_share_link(kind: str, ref: str, days: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    now = now_jkt()
    await db.share_links.insert_one({
        "id": new_id(), "token": token, "kind": kind, "ref": ref,
        "created_at": now.isoformat(), "expires_at": (now + timedelta(days=days)).isoformat(),
        "hits": 0,
    })
    return token


async def _sales_pdf_for_date(date: str) -> bytes:
    """PDF Laporan Penjualan untuk satu tanggal (dipakai lampiran rekap WhatsApp)."""
    data = await report_sales(date, date, {"name": "Sistem (Otomatis)", "role": "owner"})
    store = await _store_info()
    return await run_in_threadpool(pdf_reports.sales_pdf, data, store, date, date,
                                  "Sistem (Otomatis)")


@api.get("/public/laporan/{token}")
async def public_report_pdf(token: str):
    """Unduh PDF laporan lewat tautan ber-token. TANPA login (dibuka dari WhatsApp)."""
    row = await db.share_links.find_one({"token": token})
    if not row:
        raise HTTPException(404, "Tautan tidak ditemukan atau sudah dicabut")
    if str(row.get("expires_at") or "") < iso_now():
        raise HTTPException(410, "Tautan sudah kedaluwarsa. Minta tautan baru dari aplikasi.")
    if row.get("kind") != "sales":
        raise HTTPException(404, "Jenis laporan tidak dikenal")
    date = str(row.get("ref") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(404, "Tanggal laporan tidak valid")
    await db.share_links.update_one({"token": token},
                                    {"$inc": {"hits": 1}, "$set": {"last_hit_at": iso_now()}})
    pdf = await _sales_pdf_for_date(date)
    return Response(content=pdf, media_type="application/pdf", headers={
        # inline supaya langsung terbaca di WhatsApp/browser HP
        "Content-Disposition": f'inline; filename="laporan-penjualan_{date}.pdf"',
        "Content-Length": str(len(pdf)),
        "Cache-Control": "no-store",
    })


# ------------------------- Tutup Buku Harian -------------------------
# Rumus laba & kas ada di finance.py (satu sumber untuk semua halaman).


class ClosingBody(BaseModel):
    date: Optional[str] = None
    notes: str = ""


def _group_by_method(rows: list) -> list:
    """Kelompokkan catatan pembayaran (income/expense) berdasarkan metode bayar."""
    out: Dict[str, dict] = {}
    for r in rows:
        m = (r.get("method") or "cash").lower()
        e = out.setdefault(m, {"method": m, "label": PAY_LABELS.get(m, m),
                               "count": 0, "amount": 0.0})
        e["count"] += 1
        e["amount"] += float(r.get("amount", 0) or 0)
    for e in out.values():
        e["amount"] = round(e["amount"], 2)
    return sorted(out.values(), key=lambda x: -x["amount"])


async def _closing_snapshot(d: str) -> dict:
    """Hitung ringkasan tutup buku untuk satu tanggal. Semua angka dari database."""
    sales = await db.sales.find({"date": d, "status": {"$ne": "batal"}}).to_list(20000)
    cancelled = await db.sales.count_documents({"date": d, "status": "batal"})

    by_method: Dict[str, dict] = {}
    by_cashier: Dict[str, dict] = {}
    per_product: Dict[str, dict] = {}
    for s in sales:
        total = float(s.get("total", 0) or 0)
        s_hpp = float(s.get("total_hpp", 0) or 0)
        # kas = uang yang diterima saat transaksi; pelunasan piutang dicatat
        # terpisah sebagai pemasukan supaya kas tidak dihitung dua kali.
        kas = min(float(s.get("paid", 0) or 0), total)
        m = by_method.setdefault(s.get("payment_method", "cash"),
                                 {"method": s.get("payment_method", "cash"), "count": 0, "total": 0.0, "kas": 0.0})
        m["count"] += 1
        m["total"] += total
        m["kas"] += max(kas, 0)
        c = by_cashier.setdefault(s.get("cashier_name", "-"),
                                  {"cashier": s.get("cashier_name", "-"), "count": 0, "total": 0.0, "laba": 0.0})
        c["count"] += 1
        c["total"] += total
        c["laba"] += total - s_hpp
        for it in s.get("items", []) or []:
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

    incomes = await db.incomes.find({"date": d}).to_list(20000)
    expenses = await db.expenses.find({"date": d}).to_list(20000)
    # SATU rumus untuk semua halaman (lihat finance.py).
    fin = finance.summarize(sales, expenses, incomes)
    omzet, hpp, gross = fin["omzet"], fin["hpp"], fin["gross_profit"]
    diskon, piutang_baru = fin["diskon"], fin["piutang_baru"]
    kas_masuk_jual = fin["kas_dari_penjualan"]
    weight, ekor, pcs = fin["weight"], fin["ekor"], fin["pcs"]
    opex, expense_total = fin["opex"], fin["expense_total"]
    income_total, bayar_piutang = fin["cash_in"], fin["bayar_piutang_masuk"]
    exp_by_cat = {x["category"]: x["amount"] for x in fin["expenses_by_category"]}

    # Rincian pelunasan piutang & hutang PER METODE (permintaan owner: mau tahu
    # uang yang masuk/keluar itu tunai, transfer, QRIS, debit, atau e-wallet).
    piutang_by_method = _group_by_method(
        [x for x in incomes if x.get("category") == "Pembayaran Piutang"])
    hutang_by_method = _group_by_method(
        [x for x in expenses if x.get("category") == "Pembayaran Hutang"])

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
        "net_margin": fin["net_margin"],
        # arus kas (biaya beli ayam & pelunasan hutang dihitung di sini, bukan di laba)
        "cash_in": fin["cash_in"], "cash_out": fin["cash_out"], "net_cash": fin["net_cash"],
        "modal_value": fin["modal_value"], "modal_cash": fin["modal_cash"],
        "diskon": round(diskon, 2),
        "txn_count": len(sales), "cancelled_count": cancelled,
        "weight": round(weight, 3), "ekor": round(ekor, 2), "pcs": round(pcs, 2),
        "kas_dari_penjualan": round(kas_masuk_jual, 2),
        "piutang_baru": round(piutang_baru, 2),
        "bayar_piutang_masuk": round(bayar_piutang, 2),
        "piutang_by_method": piutang_by_method,
        "hutang_by_method": hutang_by_method,
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
        "payable_outstanding": round(sum(float(pay.get("remaining", 0) or 0) for pay in payables_open), 2),
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
    """Kirim rekap tutup buku + PDF Laporan Penjualan. Tidak boleh menggagalkan tutup buku."""
    try:
        recipients = await _wa_recipients()
        store = await _store_info()
        date = str(closing.get("date") or today_str())

        # PDF Laporan Penjualan hari itu. Dibuat sekali: dipakai sebagai lampiran
        # (media Meta) DAN sebagai tautan publik untuk mode 1-tap.
        pdf, pdf_url, pdf_name = None, "", f"laporan-penjualan_{date}.pdf"
        if bool(await get_setting("wa_attach_pdf", True)):
            try:
                pdf = await _sales_pdf_for_date(date)
                base = await _public_base_url()
                token = await _create_share_link("sales", date)
                if base:
                    pdf_url = f"{base}/api/public/laporan/{token}"
            except Exception as e:
                logger.warning("PDF laporan penjualan %s gagal dibuat: %s", date, e)
                pdf, pdf_url = None, ""

        if not recipients:
            await add_notification("whatsapp", "Nomor WhatsApp Belum Diisi",
                                   "Tambahkan nomor penerima rekap di Pengaturan → Rekap WhatsApp", "warning")
            return {"text": whatsapp.build_closing_text(clean(closing), store, notes, pdf_url=pdf_url),
                    "provider": whatsapp.provider_info(), "results": [], "sent_count": 0,
                    "mode": "manual", "pdf_url": pdf_url}
        out = await whatsapp.send_closing(clean(closing), store, recipients, notes,
                                          pdf=pdf, pdf_filename=pdf_name, pdf_url=pdf_url)
        upd = {"wa_status": out["mode"], "wa_results": out["results"], "wa_attempt_at": iso_now(),
               "wa_pdf_url": out.get("pdf_url") or ""}
        if out["sent_count"]:
            upd["wa_sent_at"] = iso_now()
        await db.daily_closings.update_one({"date": closing["date"]}, {"$set": upd})
        if out["sent_count"]:
            lampiran = " + PDF" if any(r.get("pdf_attached") for r in out["results"]) else ""
            await add_notification("whatsapp", "Rekap WhatsApp Terkirim",
                                   f"{closing['date']} · terkirim ke {out['sent_count']} nomor{lampiran}", "success")
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
    attach_pdf: bool = True


@api.get("/whatsapp/settings")
async def get_wa_settings(user: dict = Depends(require_roles("owner", "admin"))):
    return {
        "recipients": await _wa_recipients(),
        "auto_enabled": bool(await get_setting("wa_auto_enabled", True)),
        "auto_time": str(await get_setting("wa_auto_time", "21:00"))[:5],
        "attach_pdf": bool(await get_setting("wa_attach_pdf", True)),
        "provider": whatsapp.provider_info(),
        # Spesifikasi template siap dicopy owner ke Meta (atau disubmit 1 klik).
        "template_spec": whatsapp.template_spec(),
        "template_spec_doc": whatsapp.template_spec(with_document=True),
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
    await db.settings.update_one({"key": "wa_attach_pdf"}, {"$set": {"value": bool(body.attach_pdf)}}, upsert=True)
    await log_audit(user, "update", "whatsapp_settings", "wa", None,
                    {"count": len(recs), "auto_enabled": body.auto_enabled,
                     "auto_time": body.auto_time, "attach_pdf": body.attach_pdf})
    return await get_wa_settings(user)


@api.get("/whatsapp/log")
async def get_wa_log(limit: int = 30, user: dict = Depends(require_roles("owner", "admin"))):
    """Riwayat upaya pengiriman rekap (otomatis maupun manual)."""
    rows = await db.wa_logs.find().sort("created_at", -1).to_list(max(min(limit, 100), 1))
    return [clean(r) for r in rows]


# ------------------------- Aktivasi provider (template & diagnostik) -------------------------
@api.get("/whatsapp/template")
async def get_wa_template(user: dict = Depends(require_roles("owner", "admin"))):
    """Spesifikasi template + statusnya di akun WhatsApp Business.

    Selalu 200: bila kredensial belum ada, `remote` kosong dan owner tetap bisa
    menyalin spesifikasi template untuk disubmit manual di Meta Business Manager.
    """
    spec = whatsapp.template_spec()
    spec_doc = whatsapp.template_spec(with_document=True)
    out = {"spec": spec, "spec_doc": spec_doc, "provider": whatsapp.provider_info(),
           "remote": [], "approved": False, "approved_doc": False, "error": None}
    if whatsapp.is_configured() and whatsapp.provider_info()["waba_configured"]:
        try:
            rows = await whatsapp.list_templates()
            out["remote"] = rows
            out["approved"] = any(
                (t.get("name") == spec["name"]) and (t.get("status") == "APPROVED")
                for t in rows)
            out["approved_doc"] = any(
                (t.get("name") == spec_doc["name"]) and (t.get("status") == "APPROVED")
                for t in rows)
        except whatsapp.WaError as e:
            out["error"] = e.as_dict()
        except Exception as e:
            out["error"] = {"message": str(e)[:300]}
    return out


@api.post("/whatsapp/template")
async def create_wa_template(with_document: bool = False,
                             user: dict = Depends(require_roles("owner"))):
    """Submit template rekap ke Meta sekali klik (butuh META_WABA_ID + token).

    `with_document=true` membuat template BERLAMPIRAN PDF (header DOCUMENT);
    Meta mewajibkan contoh PDF, jadi laporan penjualan hari ini diunggah sebagai
    contoh lewat Resumable Upload API (butuh META_APP_ID).
    """
    if not whatsapp.is_configured():
        raise HTTPException(400, "Kredensial WhatsApp belum diisi. Isi META_PHONE_NUMBER_ID "
                                 "dan META_ACCESS_TOKEN di backend/.env terlebih dahulu.")
    sample = None
    if with_document:
        try:
            sample = await _sales_pdf_for_date(today_str())
        except Exception as e:
            raise HTTPException(500, f"Gagal membuat contoh PDF laporan penjualan: {str(e)[:200]}")
    # `res` diinisialisasi lebih dulu supaya tidak ada jalur eksekusi yang bisa
    # memakainya sebelum ditugaskan (dan agar analisis statis tidak ambigu).
    res: dict = {}
    try:
        res = await whatsapp.create_template(with_document=with_document, sample_pdf=sample)
    except whatsapp.WaError as e:
        d = e.as_dict()
        raise HTTPException(400, f"{d['message']}{(' — ' + d['hint']) if d['hint'] else ''}")
    except Exception as e:
        raise HTTPException(502, f"Gagal menghubungi Meta: {str(e)[:200]}")
    if not isinstance(res, dict):
        res = {}
    spec = whatsapp.template_spec(with_document=with_document)
    await log_audit(user, "create", "whatsapp_template", str(res.get("id") or "-"), None,
                    {"name": spec["name"], "with_document": with_document,
                     "status": res.get("status")})
    return {"ok": True, "result": res, "spec": spec}


@api.get("/whatsapp/diagnostics")
async def wa_diagnostics(user: dict = Depends(require_roles("owner", "admin"))):
    """Cek kesiapan: kredensial, nomor bisnis, template disetujui, penerima, jadwal."""
    prov = whatsapp.provider_info()
    recipients = await _wa_recipients()
    out = {
        "provider": prov,
        "recipients": len(recipients),
        "auto_enabled": bool(await get_setting("wa_auto_enabled", True)),
        "auto_time": str(await get_setting("wa_auto_time", "21:00"))[:5],
        "attach_pdf": bool(await get_setting("wa_attach_pdf", True)),
        "public_base_url": await _public_base_url(),
        "webhook_url": "/api/whatsapp/webhook",
        "webhook_verify_configured": bool((os.environ.get("WA_WEBHOOK_VERIFY_TOKEN") or "").strip()),
        "phone": None, "template_approved": False, "template_doc_approved": False, "errors": [],
    }
    # PDF laporan penjualan harus benar-benar bisa dibuat, bukan sekadar diasumsikan.
    try:
        pdf = await _sales_pdf_for_date(today_str())
        out["pdf_ready"] = bool(pdf and pdf[:4] == b"%PDF")
        out["pdf_size"] = len(pdf or b"")
    except Exception as e:
        out["pdf_ready"] = False
        out["errors"].append({"step": "pdf_laporan", "message": str(e)[:250]})
    if prov["configured"]:
        try:
            out["phone"] = await whatsapp.phone_status()
        except Exception as e:
            out["errors"].append({"step": "nomor_bisnis", "message": str(e)[:250]})
        if prov["waba_configured"]:
            try:
                spec = whatsapp.template_spec()
                spec_doc = whatsapp.template_spec(with_document=True)
                rows = await whatsapp.list_templates()
                out["template_approved"] = any(
                    t.get("name") == spec["name"] and t.get("status") == "APPROVED" for t in rows)
                out["template_doc_approved"] = any(
                    t.get("name") == spec_doc["name"] and t.get("status") == "APPROVED" for t in rows)
                out["templates"] = [{"name": t.get("name"), "status": t.get("status"),
                                     "language": t.get("language")} for t in rows][:20]
            except Exception as e:
                out["errors"].append({"step": "template", "message": str(e)[:250]})
    # Siap otomatis bila minimal template ringkas disetujui; lampiran PDF butuh
    # template dokumen (kalau owner mengaktifkan lampiran).
    ready = bool(prov["configured"] and out["recipients"] and out["auto_enabled"]
                 and (out["template_doc_approved"] if out["attach_pdf"] else out["template_approved"]))
    out["ready_for_auto"] = ready
    return out


# ------------------------- Webhook status pengiriman -------------------------
# Dipanggil oleh Meta (tanpa auth aplikasi) -> diverifikasi lewat WA_WEBHOOK_VERIFY_TOKEN.
@api.get("/whatsapp/webhook")
async def verify_wa_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    expected = (os.environ.get("WA_WEBHOOK_VERIFY_TOKEN") or "").strip()
    if hub_mode == "subscribe" and expected and hub_verify_token == expected:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "Verifikasi webhook gagal")


@api.post("/whatsapp/webhook")
async def receive_wa_webhook(request: Request):
    """Simpan status pengiriman (sent/delivered/read/failed) per message_id.

    Idempoten (upsert per message_id) karena Meta melakukan retry sampai 7 hari
    bila respons bukan 2xx. Selalu balas 200 supaya tidak memicu retry beruntun.
    """
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    try:
        touched = 0
        for entry in (body.get("entry") or []):
            for change in (entry.get("changes") or []):
                value = (change.get("value") or {})
                for st in (value.get("statuses") or []):
                    wamid = st.get("id")
                    if not wamid:
                        continue
                    doc = {"status": st.get("status"), "recipient": st.get("recipient_id"),
                           "timestamp": st.get("timestamp"), "errors": st.get("errors") or [],
                           "updated_at": iso_now()}
                    await db.wa_statuses.update_one(
                        {"message_id": wamid},
                        {"$set": doc, "$setOnInsert": {"message_id": wamid, "created_at": iso_now()}},
                        upsert=True)
                    # Cerminkan status ke baris log agar owner lihat "dibaca/gagal".
                    await db.wa_logs.update_one(
                        {"results.message_id": wamid},
                        {"$set": {"results.$.status": st.get("status"),
                                  "results.$.status_at": iso_now()}})
                    touched += 1
        if touched:
            await rt_emit(["whatsapp"])
    except Exception as e:
        logger.warning("Webhook WhatsApp gagal diproses: %s", e)
    return {"ok": True}


@api.get("/whatsapp/statuses")
async def get_wa_statuses(limit: int = 50, user: dict = Depends(require_roles("owner", "admin"))):
    rows = await db.wa_statuses.find().sort("updated_at", -1).to_list(max(min(limit, 200), 1))
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
    # Nilai uji untuk template (template = jalur yang dipakai rekap malam otomatis,
    # jadi uji coba harus melewati jalur yang SAMA agar benar-benar membuktikan).
    test_values = {"tanggal": whatsapp.tanggal_panjang(today_str()),
                   "omzet": "(uji coba)", "laba_bersih": "(uji coba)",
                   "jumlah_transaksi": "0"}
    for rec in recipients:
        item = {"name": rec["name"], "number": rec["number"],
                "link": whatsapp.wa_me_link(rec["number"], text), "sent": False,
                "error": None, "via": None}
        res: dict = {}
        if configured:
            try:
                res = await whatsapp.send_template(rec["number"], test_values)
                item["via"] = "template"
            except whatsapp.WaError as e:
                item["error_detail"] = e.as_dict()
                if e.code in (132000, 132001, 132015, 132016, None):
                    try:
                        res = await whatsapp.send_text(rec["number"], text)
                        item["via"] = "text"
                    except Exception as e2:
                        item["error"] = f"{e}; teks biasa juga gagal: {e2}"[:400]
                        item["hint"] = e.hint
                        results.append(item)
                        continue
                else:
                    item["error"] = str(e)[:300]
                    item["hint"] = e.hint
                    results.append(item)
                    continue
            except Exception as e:
                item["error"] = str(e)[:300]
                results.append(item)
                continue
            item["sent"] = True
            item["message_id"] = (res.get("messages") or [{}])[0].get("id")
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
    """Tutup buku + kirim rekap otomatis pada jam yang diatur owner (WIB).

    Memakai perbandingan "sudah melewati jam target" (bukan cocok HH:MM persis)
    supaya rekap TIDAK HILANG bila backend sempat restart tepat di menit itu —
    saat backend hidup kembali, rekap hari itu langsung dikejar (catch-up).
    Anti-dobel: `last_done` per proses + `wa_sent_at`/`wa_attempt_at` di dokumen
    tutup buku hari tersebut.
    """
    await asyncio.sleep(20)
    last_done = None
    while True:
        try:
            await asyncio.sleep(30)
            if not bool(await get_setting("wa_auto_enabled", True)):
                continue
            target = str(await get_setting("wa_auto_time", "21:00"))[:5]
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", target):
                target = "21:00"
            now = now_jkt()
            th, tm = int(target[:2]), int(target[3:5])
            if (now.hour * 60 + now.minute) < (th * 60 + tm):
                continue  # belum waktunya hari ini
            d = now.strftime("%Y-%m-%d")
            if last_done == d:
                continue
            existing = await db.daily_closings.find_one({"date": d})
            if existing and (existing.get("wa_sent_at") or existing.get("wa_attempt_at")):
                last_done = d  # sudah pernah dikirim/dicoba hari ini
                continue
            logger.info("Tutup buku otomatis dijalankan untuk %s (jadwal %s WIB)", d, target)
            doc = await _save_closing(d, "", "Sistem (Otomatis)")
            out = await _dispatch_closing_whatsapp(doc, trigger="otomatis")
            logger.info("Rekap otomatis %s: mode=%s terkirim=%s", d,
                        out.get("mode"), out.get("sent_count"))
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
async def upload_file(file: UploadFile = File(...), folder: str = Form("products"),
                     user: dict = Depends(require_roles("owner", "admin", "kasir"))):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    if ext not in MIME_TYPES:
        raise HTTPException(400, "Format gambar tidak didukung (jpg, png, webp, gif)")
    # Kasir hanya boleh mengunggah bukti pengeluaran, bukan mengganti foto produk.
    folder = folder if folder in ("products", "proofs") else "products"
    if user["role"] == "kasir":
        folder = "proofs"
    fid = new_id()
    path = f"{APP_NAME}/{folder}/{fid}.{ext}"
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Ukuran gambar maksimal 10 MB")
    ct = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    try:
        result = put_object(path, data, ct)
    except Exception as e:
        logger.error(f"Upload gagal: {e}")
        raise HTTPException(502, "Gagal mengunggah gambar ke penyimpanan")
    await db.files.insert_one({"id": fid, "storage_path": result["path"], "content_type": ct,
                               "original_filename": file.filename, "size": result.get("size", len(data)),
                               "folder": folder, "uploaded_by": user["name"],
                               "is_deleted": False, "created_at": iso_now()})
    return {"id": fid, "url": f"/api/files/{fid}"}


@api.get("/files/{fid}")
async def serve_file(fid: str):
    rec = await db.files.find_one({"id": fid, "is_deleted": False})
    if not rec:
        raise HTTPException(404, "File tidak ditemukan")
    try:
        data, ct = get_object(rec["storage_path"])
        return Response(content=data, media_type=rec.get("content_type", ct),
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        logger.error(f"Ambil file gagal: {e}")
        raise HTTPException(502, "Gagal memuat gambar")


# ------------------------- wiring -------------------------
app.include_router(auth_router)
app.include_router(api)


# URL publik backend TIDAK di-hardcode: direkam sekali dari header permintaan
# pertama yang masuk (lewat ingress), lalu disimpan agar penjadwal malam —
# yang tidak punya objek Request — bisa membuat tautan PDF yang bisa dibuka HP.
_public_base = {"url": (os.environ.get("PUBLIC_BASE_URL") or "").strip()}


@app.middleware("http")
async def capture_public_base(request: Request, call_next):
    try:
        if not _public_base["url"]:
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
            if host and not any(h in host for h in ("localhost", "127.0.0.1", "0.0.0.0")):
                _public_base["url"] = f"{proto}://{host.split(',')[0].strip()}"
                await db.settings.update_one({"key": "public_base_url"},
                                             {"$set": {"value": _public_base["url"]}}, upsert=True)
                logger.info("URL publik terdeteksi: %s", _public_base["url"])
    except Exception as e:  # pragma: no cover
        logger.warning("Gagal merekam URL publik: %s", e)
    return await call_next(request)


async def _public_base_url() -> str:
    """URL publik backend, dicari berurutan tanpa hardcoding:
    1) env PUBLIC_BASE_URL, 2) hasil rekaman dari header permintaan (settings),
    3) REACT_APP_BACKEND_URL pada frontend/.env (sumber kebenaran URL app ini).
    """
    if _public_base["url"]:
        return _public_base["url"]
    saved = await get_setting("public_base_url", "")
    if saved:
        _public_base["url"] = str(saved)
        return _public_base["url"]
    try:
        fe = Path(__file__).resolve().parent.parent / "frontend" / ".env"
        if fe.exists():
            for line in fe.read_text().splitlines():
                if line.strip().startswith("REACT_APP_BACKEND_URL"):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val.startswith("http"):
                        _public_base["url"] = val.rstrip("/")
                        break
    except Exception as e:  # pragma: no cover
        logger.warning("Gagal membaca URL publik dari frontend/.env: %s", e)
    return _public_base["url"]

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
    # Rapikan data warisan supaya Penjualan/Pembelian/Keuangan/Laporan selalu sinkron.
    try:
        await reconcile.repair_on_startup(db)
    except Exception as e:
        logger.error(f"Rekonsiliasi data gagal: {e}")
    # Dokumen bertanggal MASA DEPAN (mis. jam demo 20:00 padahal sekarang 10:50)
    # membuat transaksi asli kasir tertimbun di Riwayat Transaksi. Idempoten.
    try:
        await maintenance.repair_future_timestamps(db)
    except Exception as e:
        logger.error(f"Perbaikan waktu masa depan gagal: {e}")
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
