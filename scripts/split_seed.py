"""Skrip sekali-jalan: pecah seed_demo() jadi fungsi per jenis data.

URUTAN pemanggilan random DIJAGA SAMA PERSIS, karena seed_demo memakai
random.seed(42) sehingga data demo harus tetap identik (dibuktikan dengan
seed_fingerprint.py sebelum/sesudah).
"""

import ast

PATH = "/app/backend/seed.py"

NEW = '''PCS_PRICE = {"Ceker Ayam": 2000, "Kepala Ayam": 3000, "Ati Ampela": 4000,
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


def _sale_payment(cust_docs: list, subtotal: float, day_offset: int) -> dict:
    """Metode bayar, uang diterima, pelanggan, kasir, dan jam transaksi."""
    method = random.choice(METHODS)
    total = round(subtotal, 2)
    paid = total if method != "piutang" else round(total * 0.6, 2)
    cust = random.choice(cust_docs) if random.random() > 0.4 else None
    cashier = random.choice(CASHIERS)
    created = (_now() - timedelta(days=day_offset)).replace(
        hour=random.randint(7, 20), minute=random.randint(0, 59)).isoformat()
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
'''


def main():
    src = open(PATH).read()
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "seed_demo")
    lines = src.split("\n")
    out = lines[:node.lineno - 1] + NEW.rstrip("\n").split("\n") + lines[node.end_lineno:]
    open(PATH, "w").write("\n".join(out))
    print("seed.py diperbarui")


if __name__ == "__main__":
    main()
