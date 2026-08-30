"""Seed realistic, interconnected demo data for Berkah Ayam Mili."""
import uuid
import random
from datetime import datetime, timedelta, timezone

JKT = timezone(timedelta(hours=7))


def _id():
    return str(uuid.uuid4())


def _now():
    return datetime.now(JKT)


PRODUCTS = [
    # name, category, units, buy, hpp_kg, price_kg, price_ekor, stock_kg, stock_ekor, min_kg, byproduct
    ("Ayam Broiler", "broiler", ["kg", "ekor"], 24000, 28000, 34000, 55000, 225.5, 120, 30, False,
     "https://images.unsplash.com/photo-1587593810167-a84920ea0781?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Ayam Kampung", "kampung", ["kg", "ekor"], 45000, 52000, 62000, 75000, 52.8, 40, 10, False,
     "https://images.unsplash.com/photo-1672787153720-e85fe802fd9f?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Ayam Pejantan", "pejantan", ["kg", "ekor"], 30000, 33000, 40000, 48000, 95.4, 80, 15, False,
     "https://images.unsplash.com/photo-1672787153720-e85fe802fd9f?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Ayam Fillet", "fillet", ["kg"], 0, 42500, 55000, 0, 25.7, 0, 8, False,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Dada Fillet", "fillet", ["kg"], 0, 43000, 58000, 0, 12.0, 0, 5, False,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Ceker Ayam", "sampingan", ["kg"], 0, 12000, 20000, 0, 8.5, 0, 3, True,
     "https://images.unsplash.com/photo-1656412665049-52e33e42b9a6?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Kepala Ayam", "sampingan", ["kg"], 0, 8000, 15000, 0, 5.2, 0, 2, True,
     "https://images.unsplash.com/photo-1656412665049-52e33e42b9a6?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Ati Ampela", "sampingan", ["kg"], 0, 18000, 28000, 0, 6.0, 0, 2, True,
     "https://images.unsplash.com/photo-1656412665049-52e33e42b9a6?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Kulit Ayam", "sampingan", ["kg"], 0, 10000, 18000, 0, 4.0, 0, 2, True,
     "https://images.unsplash.com/photo-1656412665049-52e33e42b9a6?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Tulang Ayam", "sampingan", ["kg"], 0, 5000, 10000, 0, 3.0, 0, 1, True,
     "https://images.unsplash.com/photo-1656412665049-52e33e42b9a6?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Paha Ayam", "sampingan", ["kg"], 0, 22000, 32000, 0, 10.0, 0, 3, True,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
]

# POTONG PARTS: bagian hasil "Produksi Potong" yang bisa dijual per kg ATAU per pcs.
# Ditambahkan idempoten lewat ensure_potong_parts() supaya database yang sudah ada
# (dan sudah pernah di-seed) tetap mendapatkan produk-produk ini.
POTONG_PARTS = [
    # name, hpp_kg, price_kg, hpp_pcs, price_pcs, min_stock_kg, image
    ("Sayap Ayam", 30000, 40000, 4000, 6000, 3,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Dada Ayam", 32000, 42000, 9000, 13000, 3,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
    ("Paha Atas Ayam", 30000, 40000, 8000, 11000, 3,
     "https://images.unsplash.com/photo-1604503468506-a8da13d82791?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"),
]


async def ensure_potong_parts(db):
    """Pastikan bagian potongan (Sayap, Dada, Paha Atas) tersedia sebagai produk.

    Dipanggil setiap startup dan aman diulang: produk yang namanya sudah ada
    dilewati, harga/stok yang sudah diubah owner TIDAK ditimpa.
    """
    added = []
    for (name, hpp_kg, price_kg, hpp_pcs, price_pcs, min_kg, img) in POTONG_PARTS:
        if await db.products.find_one({"name": name}):
            continue
        await db.products.insert_one({
            "id": _id(), "name": name, "category": "potongan", "units": ["kg", "pcs"],
            "buy_price_kg": 0, "hpp_kg": hpp_kg, "hpp_ekor": 0, "hpp_pcs": hpp_pcs,
            "price_kg": price_kg, "price_ekor": 0, "price_pcs": price_pcs,
            "stock_kg": 0, "stock_ekor": 0, "stock_pcs": 0,
            "min_stock_kg": min_kg, "min_stock_ekor": 0, "min_stock_pcs": 0,
            "image_url": img, "is_byproduct": False, "active": True,
            "created_at": _now().isoformat(),
        })
        added.append(name)
    return added


CUSTOMERS = [
    ("Warung Bu Sri", "081234567001", "Jl. Melati No.1", "warung"),
    ("RM Sederhana", "081234567002", "Jl. Merdeka No.5", "rumah_makan"),
    ("Reseller Pak Joko", "081234567003", "Pasar Induk Blok C", "reseller"),
    ("Restoran Nikmat", "081234567004", "Jl. Sudirman No.10", "restoran"),
    ("Ibu Rina", "081234567005", "Perum Griya Asri", "rumah_tangga"),
]

SUPPLIERS = [
    ("Peternakan Jaya", "082111000001", "Blitar", ["broiler", "pejantan"]),
    ("CV Ayam Makmur", "082111000002", "Kediri", ["broiler", "kampung"]),
    ("Supplier Barokah", "082111000003", "Malang", ["kampung", "pejantan"]),
]


PCS_PRICE = {"Ceker Ayam": 2000, "Kepala Ayam": 3000, "Ati Ampela": 4000,
             "Kulit Ayam": 3000, "Tulang Ayam": 2000, "Paha Ayam": 8000}
PCS_STOCK = {"Ceker Ayam": 120, "Kepala Ayam": 80, "Ati Ampela": 60,
             "Kulit Ayam": 40, "Tulang Ayam": 30, "Paha Ayam": 90}
SELLABLE = [p for p in PRODUCTS if p[1] != "sampingan"]
CASHIERS = [("Kasir Andi", "kasir-andi"), ("Owner Berkah Ayam Mili", "owner")]
METHODS = ["cash", "transfer", "qris", "debit", "piutang"]


async def _seed_products(db) -> dict:
    """Katalog produk + stok awal. Mengembalikan peta nama -> id produk."""
    prod_ids = {}
    for (name, cat, units, buy, hpp, pkg, pekor, skg, sekor, minkg, byp, img) in PRODUCTS:
        pid = _id()
        u = ["kg", "pcs"] if byp else list(units)
        await db.products.insert_one({
            "id": pid, "name": name, "category": cat, "units": u,
            "buy_price_kg": buy, "hpp_kg": hpp, "hpp_ekor": 0,
            "hpp_pcs": round(hpp * 0.3) if byp else 0,
            "price_kg": pkg, "price_ekor": pekor,
            "price_pcs": PCS_PRICE.get(name, 0) if byp else 0,
            "stock_kg": skg, "stock_ekor": sekor,
            "stock_pcs": PCS_STOCK.get(name, 0) if byp else 0,
            "min_stock_kg": minkg, "min_stock_ekor": 0, "min_stock_pcs": 0,
            "image_url": img, "is_byproduct": byp, "active": True,
            "created_at": _now().isoformat(),
        })
        prod_ids[name] = pid
    return prod_ids


async def _seed_partners(db) -> list:
    """Pelanggan & supplier awal. Mengembalikan daftar dokumen pelanggan."""
    cust_docs = []
    for (name, phone, addr, ctype) in CUSTOMERS:
        c = {"id": _id(), "name": name, "phone": phone, "address": addr, "type": ctype,
             "special_prices": {}, "total_purchase": 0, "receivable": 0,
             "created_at": _now().isoformat()}
        await db.customers.insert_one(c)
        cust_docs.append(c)
    for (name, phone, addr, types) in SUPPLIERS:
        await db.suppliers.insert_one({
            "id": _id(), "name": name, "phone": phone, "address": addr,
            "chicken_types": types, "last_prices": {}, "total_purchase": 0,
            "payable": 0, "created_at": _now().isoformat()})
    return cust_docs


async def _seed_target(db, today: str):
    await db.targets.insert_one({
        "id": _id(), "date": today, "target_omzet": 10000000, "target_weight": 300,
        "target_ekor": 200, "target_laba": 2000000,
    })


def _sale_items(prod_ids: dict) -> dict:
    """1-3 baris penjualan acak beserta totalnya."""
    items = []
    subtotal = total_hpp = tw = te = 0
    for _ in range(random.randint(1, 3)):
        prod = random.choice(SELLABLE)
        name, cat = prod[0], prod[1]
        use_kg = "kg" in prod[2] and (cat == "fillet" or random.random() > 0.35)
        if use_kg:
            qty = round(random.uniform(0.8, 4.5), 2)
            price, hpp_u, unit = prod[5], prod[4], "kg"
            tw += qty
        else:
            qty = random.randint(1, 3)
            price, hpp_u, unit = prod[6], round(prod[4] * 1.4, 0), "ekor"  # approx per ekor
            te += qty
        line = round(qty * price, 2)
        ht = round(qty * hpp_u, 2)
        subtotal += line
        total_hpp += ht
        items.append({"product_id": prod_ids[name], "name": name, "unit": unit, "qty": qty,
                      "price": price, "subtotal": line, "hpp_unit": hpp_u,
                      "hpp_total": ht, "category": cat})
    return {"items": items, "subtotal": subtotal, "hpp": total_hpp, "weight": tw, "ekor": te}


def _clamp_past(dt):
    """Pastikan waktu demo TIDAK PERNAH melewati "sekarang".

    Bug yang pernah terjadi: transaksi demo hari ini diberi jam acak 7-20 tanpa
    melihat jam sekarang, sehingga ada dokumen bertanggal MASA DEPAN. Akibatnya
    penjualan ASLI kasir tertimbun di bawah baris demo pada Riwayat Transaksi
    (yang urut dari terbaru) dan terlihat seolah hilang.
    """
    now = _now()
    if dt <= now:
        return dt
    # Tarik ke dalam jam operasional yang sudah lewat pada hari itu.
    earliest = dt.replace(hour=7, minute=0, second=0, microsecond=0)
    latest = now - timedelta(minutes=1)
    if latest <= earliest:
        return latest
    span = int((latest - earliest).total_seconds())
    return earliest + timedelta(seconds=random.randint(0, span))


def _sale_payment(cust_docs: list, subtotal: float, day_offset: int) -> dict:
    """Metode bayar, uang diterima, pelanggan, kasir, dan jam transaksi."""
    method = random.choice(METHODS)
    total = round(subtotal, 2)
    paid = total if method != "piutang" else round(total * 0.6, 2)
    cust = random.choice(cust_docs) if random.random() > 0.4 else None
    cashier = random.choice(CASHIERS)
    created = _clamp_past((_now() - timedelta(days=day_offset)).replace(
        hour=random.randint(7, 20), minute=random.randint(0, 59))).isoformat()
    return {"method": method, "total": total, "paid": paid,
            "receivable": round(total - paid, 2), "cust": cust,
            "cashier": cashier, "created": created}


def _sale_doc(day: str, line: dict, pay: dict) -> dict:
    total, cust = pay["total"], pay["cust"]
    gp = round(total - line["hpp"], 2)
    sid = _id()
    return {
        "id": sid, "txn_id": sid, "date": day,
        "cashier_id": pay["cashier"][1], "cashier_name": pay["cashier"][0],
        "customer_id": cust["id"] if cust else None,
        "customer_name": cust["name"] if cust else "Umum",
        "items": line["items"], "subtotal": total, "discount": 0, "total": total,
        "paid": pay["paid"], "change": 0, "receivable": pay["receivable"],
        "payment_method": pay["method"],
        "payment_status": "lunas" if pay["receivable"] <= 0 else "piutang",
        "total_hpp": round(line["hpp"], 2), "gross_profit": gp,
        "margin_pct": round(gp / total * 100, 2) if total else 0,
        "total_weight": round(line["weight"], 3), "total_ekor": line["ekor"],
        "status": "selesai", "created_at": pay["created"],
    }


async def _save_sale(db, sale: dict, pay: dict, day: str):
    """Simpan penjualan + pemasukannya + tagihan piutang bila kurang bayar."""
    await db.sales.insert_one(sale)
    await db.incomes.insert_one({"id": _id(), "date": day, "category": "Penjualan Ayam",
                                 "amount": pay["paid"], "source": "pos", "ref": sale["id"],
                                 "created_at": pay["created"]})
    cust, receivable = pay["cust"], pay["receivable"]
    if not cust:
        return
    inc = {"total_purchase": pay["total"]}
    if receivable > 0:
        inc["receivable"] = receivable
        await db.receivables.insert_one({
            "id": _id(), "customer_id": cust["id"], "customer_name": cust["name"],
            "sale_id": sale["id"], "amount": pay["total"], "paid": pay["paid"],
            "remaining": receivable, "due_date": None, "status": "belum_lunas",
            "date": day, "created_at": pay["created"]})
    await db.customers.update_one({"id": cust["id"]}, {"$inc": inc})


async def _seed_sales(db, prod_ids: dict, cust_docs: list):
    """Riwayat penjualan 7 hari terakhir (deterministik lewat random.seed(42))."""
    random.seed(42)
    for i in range(6, -1, -1):
        day = (_now() - timedelta(days=i)).strftime("%Y-%m-%d")
        n_txn = random.randint(8, 16) if i > 0 else random.randint(10, 18)
        for _ in range(n_txn):
            line = _sale_items(prod_ids)
            pay = _sale_payment(cust_docs, line["subtotal"], i)
            await _save_sale(db, _sale_doc(day, line, pay), pay, day)


async def _seed_activities(db, today: str):
    """Umpan aktivitas toko untuk dashboard."""
    activities = []
    for s in await db.sales.find({"date": today}).sort("created_at", -1).to_list(8):
        activities.append({"id": _id(), "type": "sale", "title": "Penjualan Baru",
                           "message": f"{s['cashier_name']} - {len(s['items'])} item",
                           "amount": s["total"], "user": s["cashier_name"],
                           "date": today, "created_at": s["created_at"]})
    activities.append({"id": _id(), "type": "purchase", "title": "Ayam Masuk",
                       "message": "Peternakan Jaya - 185 kg", "amount": 4640000,
                       "user": "Admin Toko", "date": today, "created_at": _now().isoformat()})
    activities.append({"id": _id(), "type": "slaughter", "title": "Pemotongan Selesai",
                       "message": "Ayam Broiler rendemen 75%", "amount": 0,
                       "user": "Kasir Budi", "date": today, "created_at": _now().isoformat()})
    await db.activities.insert_many(activities)


async def _seed_expenses(db):
    """Beban operasional harian (bukan pembelian ayam)."""
    for i in range(7):
        day = (_now() - timedelta(days=i)).strftime("%Y-%m-%d")
        for cat, amt in (("Tenaga Kerja", 150000), ("Listrik", 50000),
                         ("Es", 40000), ("Kemasan", 30000)):
            await db.expenses.insert_one({
                "id": _id(), "date": day, "category": cat, "amount": amt,
                "description": cat, "created_by": "Admin Toko",
                "created_at": (_now() - timedelta(days=i)).isoformat()})


async def _seed_purchase(db, prod_ids: dict):
    """Satu nota pembelian ayam sebagai contoh riwayat."""
    supplier = await db.suppliers.find_one({"name": "Peternakan Jaya"})
    when = _now() - timedelta(days=2)
    await db.purchases.insert_one({
        "id": _id(), "supplier_id": supplier["id"], "supplier_name": supplier["name"],
        "date": when.strftime("%Y-%m-%d"),
        "items": [{"product_id": prod_ids["Ayam Broiler"], "name": "Ayam Broiler", "ekor": 100,
                   "total_weight": 185, "avg_weight": 1.85, "buy_price_kg": 24000,
                   "subtotal": 4440000}],
        "transport_cost": 200000, "other_cost": 0, "total_bird_value": 4440000,
        "total_weight": 185, "total_modal": 4640000, "effective_cost_kg": 25081,
        "paid": 4640000, "payable": 0, "payment_status": "lunas",
        "notes": "Demo", "created_by": "Admin Toko", "created_at": when.isoformat(),
    })


async def _seed_production(db, prod_ids: dict):
    """Contoh riwayat pemotongan & produksi potongan."""
    when = _now() - timedelta(days=1)
    await db.slaughters.insert_one({
        "id": _id(), "product_id": prod_ids["Ayam Broiler"], "product_name": "Ayam Broiler",
        "date": when.strftime("%Y-%m-%d"), "ekor_in": 100,
        "live_weight": 200, "carcass_weight": 150, "susut_weight": 50,
        "rendemen_pct": 75, "susut_pct": 25, "cost_pemotongan": 150000,
        "operator": "Kasir Budi", "notes": "Demo", "created_by": "Kasir Budi",
        "created_at": when.isoformat(),
    })
    await db.productions.insert_one({
        "id": _id(), "source_product_id": prod_ids["Ayam Broiler"], "source_name": "Ayam Broiler",
        "date": when.strftime("%Y-%m-%d"), "input_ekor": 20,
        "outputs": [{"product_id": prod_ids["Paha Ayam"], "name": "Paha Ayam", "pcs": 40},
                    {"product_id": prod_ids["Ati Ampela"], "name": "Ati Ampela", "pcs": 20},
                    {"product_id": prod_ids["Kulit Ayam"], "name": "Kulit Ayam", "pcs": 20}],
        "material_value": 928000, "labor_cost": 100000,
        "packaging_cost": 50000, "other_cost": 50000, "total_cost": 1128000,
        "operator": "Kasir Budi", "notes": "Demo", "created_by": "Kasir Budi",
        "created_at": when.isoformat(),
    })


async def _seed_settings(db):
    await db.settings.insert_one({"key": "allow_negative_stock", "value": False})
    await db.settings.insert_one({"key": "store_name", "value": "Berkah Ayam Mili"})
    await db.settings.insert_one({"key": "seeded", "value": True})


async def seed_demo(db):
    """Isi database baru dengan data contoh. Tidak melakukan apa pun bila sudah pernah diisi."""
    if await db.settings.find_one({"key": "seeded"}):
        return
    today = _now().strftime("%Y-%m-%d")
    prod_ids = await _seed_products(db)
    cust_docs = await _seed_partners(db)
    await _seed_target(db, today)
    await _seed_sales(db, prod_ids, cust_docs)
    await _seed_activities(db, today)
    await _seed_expenses(db)
    await _seed_purchase(db, prod_ids)
    await _seed_production(db, prod_ids)
    await _seed_settings(db)
