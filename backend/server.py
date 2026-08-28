from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import logging
from datetime import timedelta
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, APIRouter, Depends, HTTPException
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import db, client
from auth import (
    router as auth_router,
    get_current_user,
    require_roles,
    seed_admin,
    now_jkt,
)
from seed import seed_demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("berkah")

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


async def add_notification(ntype: str, title: str, message: str, level: str = "info"):
    await db.notifications.insert_one({
        "id": new_id(), "type": ntype, "title": title, "message": message,
        "level": level, "read": False, "created_at": iso_now(),
    })


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
    return product


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
    weight: float


class ProductionBody(BaseModel):
    source_product_id: str
    date: Optional[str] = None
    input_weight: float
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


@api.post("/products")
async def create_product(body: ProductBody, user: dict = Depends(require_roles("owner", "admin"))):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = iso_now()
    await db.products.insert_one(doc)
    await log_audit(user, "create", "product", doc["id"], None, {"name": doc["name"]})
    return clean(doc)


@api.put("/products/{pid}")
async def update_product(pid: str, body: ProductBody, user: dict = Depends(require_roles("owner", "admin"))):
    existing = await db.products.find_one({"id": pid})
    if not existing:
        raise HTTPException(404, "Produk tidak ditemukan")
    updates = body.model_dump()
    for f in ["buy_price_kg", "hpp_kg", "price_kg", "price_ekor"]:
        if existing.get(f) != updates.get(f):
            await db.price_history.insert_one({
                "id": new_id(), "product_id": pid, "product_name": existing["name"], "field": f,
                "old_value": existing.get(f, 0), "new_value": updates.get(f, 0),
                "date": today_str(), "created_at": iso_now(), "user": user["name"],
            })
    await db.products.update_one({"id": pid}, {"$set": updates})
    await log_audit(user, "update", "product", pid, clean(existing), updates)
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
async def list_purchases(user: dict = Depends(require_roles("owner", "admin", "operator"))):
    p = await db.purchases.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


@api.post("/purchases")
async def create_purchase(body: PurchaseBody, user: dict = Depends(require_roles("owner", "admin"))):
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
    pid = new_id()
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
        item_hpp_ekor = round(share / it.ekor, 2) if it.ekor else 0
        item_buy_kg = round(it.total_price / it.total_weight, 2) if it.total_weight else 0
        await db.products.update_one({"id": it.product_id}, {"$set": {
            "buy_price_kg": item_buy_kg, "hpp_kg": item_hpp_kg, "hpp_ekor": item_hpp_ekor}})
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
    await add_activity("purchase", "Ayam Masuk", f"Pembelian dari {supplier['name']} - {round(total_weight_all,1)} kg", total_modal, user["name"])
    await add_notification("purchase", "Pembelian Baru", f"{supplier['name']} - {round(total_weight_all,1)} kg", "info")
    await log_audit(user, "create", "purchase", pid, None, {"total_modal": total_modal})
    return clean(doc)


# ------------------------- Slaughter -------------------------
@api.get("/slaughters")
async def list_slaughters(user: dict = Depends(require_roles("owner", "admin", "operator"))):
    s = await db.slaughters.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in s]


@api.post("/slaughters")
async def create_slaughter(body: SlaughterBody, user: dict = Depends(require_roles("owner", "admin", "operator"))):
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
async def list_productions(user: dict = Depends(require_roles("owner", "admin", "operator"))):
    p = await db.productions.find().sort("created_at", -1).to_list(1000)
    return [clean(x) for x in p]


@api.post("/productions")
async def create_production(body: ProductionBody, user: dict = Depends(require_roles("owner", "admin", "operator"))):
    source = await db.products.find_one({"id": body.source_product_id})
    if not source:
        raise HTTPException(404, "Produk sumber tidak ditemukan")
    total_output = sum(o.weight for o in body.outputs)
    susut = round(body.input_weight - total_output, 3)
    material_value = round(body.input_weight * float(source.get("hpp_kg", 0) or 0), 2)
    total_cost = round(material_value + body.labor_cost + body.packaging_cost + body.other_cost, 2)
    pid = new_id()
    outputs_out = []
    for o in body.outputs:
        op = await db.products.find_one({"id": o.product_id})
        outputs_out.append({"product_id": o.product_id, "name": op["name"] if op else "", "weight": o.weight})
    doc = {
        "id": pid, "source_product_id": body.source_product_id, "source_name": source["name"],
        "date": body.date or today_str(), "input_weight": body.input_weight, "outputs": outputs_out,
        "susut_weight": susut, "material_value": material_value, "labor_cost": body.labor_cost,
        "packaging_cost": body.packaging_cost, "other_cost": body.other_cost, "total_cost": total_cost,
        "operator": body.operator or user["name"], "notes": body.notes,
        "created_by": user["name"], "created_at": iso_now(),
    }
    await db.productions.insert_one(doc)
    await apply_stock(source, 0, -body.input_weight, "produksi", user["name"], pid, allow_negative=True)
    main_out = body.outputs[0] if body.outputs else None
    for o in body.outputs:
        op = await db.products.find_one({"id": o.product_id})
        if not op:
            continue
        await apply_stock(op, 0, o.weight, "produksi", user["name"], pid)
        if main_out and o.product_id == main_out.product_id and o.weight:
            await db.products.update_one({"id": o.product_id}, {"$set": {"hpp_kg": round(total_cost / o.weight, 2)}})
    await add_activity("production", "Produksi Potong Selesai", f"{source['name']} -> {total_output} kg produk", 0, doc["operator"])
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
        "status": "selesai", "created_at": iso_now(),
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
    await add_activity("sale", "Penjualan Baru", f"{user['name']} menjual {len(items_out)} item", total, user["name"])
    if total >= 1000000:
        await add_notification("big_sale", "Transaksi Besar", f"{user['name']} - Rp {int(total):,}", "success")
    await log_audit(user, "create", "sale", sid, None, {"total": total})
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
    return {"ok": True}


# ------------------------- Stock -------------------------
@api.get("/stock-movements")
async def list_movements(product_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"product_id": product_id} if product_id else {}
    m = await db.stock_movements.find(q).sort("created_at", -1).to_list(1000)
    return [clean(x) for x in m]


@api.post("/stock-adjustments")
async def create_adjustment(body: AdjustBody, user: dict = Depends(require_roles("owner", "admin", "operator"))):
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
async def list_expenses(user: dict = Depends(require_roles("owner", "admin"))):
    e = await db.expenses.find().sort("created_at", -1).to_list(2000)
    return [clean(x) for x in e]


@api.post("/expenses")
async def create_expense(body: ExpenseBody, user: dict = Depends(require_roles("owner", "admin"))):
    doc = body.model_dump()
    doc.update({"id": new_id(), "date": body.date or today_str(), "created_by": user["name"], "created_at": iso_now()})
    await db.expenses.insert_one(doc)
    await log_audit(user, "create", "expense", doc["id"], None, {"amount": body.amount})
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
            p = perf.setdefault(cat, {"penjualan": 0, "weight": 0, "ekor": 0, "hpp": 0})
            p["penjualan"] += it["subtotal"]
            p["hpp"] += it["hpp_total"]
            if it["unit"] == "kg":
                p["weight"] += it["qty"]
            elif it["unit"] == "ekor":
                p["ekor"] += it["qty"]
    products_perf = []
    for cat, p in perf.items():
        laba_p = round(p["penjualan"] - p["hpp"], 2)
        products_perf.append({"category": cat, "penjualan": round(p["penjualan"], 2),
                              "weight": round(p["weight"], 2), "ekor": p["ekor"], "laba": laba_p,
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
        out.append({"name": p["name"], "category": p["category"], "stock_ekor": p.get("stock_ekor", 0),
                    "stock_kg": p.get("stock_kg", 0), "hpp_kg": p.get("hpp_kg", 0), "value": round(val, 2)})
    return {"items": out, "total_value": round(sum(x["value"] for x in out), 2)}


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
    await seed_admin()
    await seed_demo(db)
    logger.info("Berkah Ayam Mili API started")


@app.on_event("shutdown")
async def shutdown():
    client.close()
