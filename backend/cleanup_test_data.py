"""Bersihkan artefak data uji agar data asli owner kembali seperti semula.

Cara kerja: seluruh perubahan stok di aplikasi ini SELALU lewat apply_stock() yang
mencatat delta di stock_movements. Jadi stok dipulihkan dengan mengurangi jumlah
delta seluruh movement pada rentang waktu uji — bukan dengan angka hafalan.
Tagihan piutang/hutang LAMA yang ikut termutasi (paid/remaining/last_method)
dipulihkan dari entri array `payments` yang dibuat setelah batas waktu.

Pakai:  python cleanup_test_data.py            (simulasi, tidak mengubah apa pun)
        python cleanup_test_data.py --apply    (benar-benar menghapus)
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Toko belum punya transaksi asli pada 30 Agu 2026 (dashboard masih Rp 0 saat
# pengujian dimulai), jadi SEMUA data 30 Agu adalah data uji.
CUTOFF = "2026-08-30T00:00"
APPLY = "--apply" in sys.argv

# Nilai yang harus kembali (dibaca dari data sah: penjualan sebelum uji &
# pembelian sah 27 Agu 2026 sebesar Rp 4.640.000 untuk 100 ekor / 185 kg).
EXPECTED_STOCK = {
    "Ayam Broiler": {"kg": 225.5, "ekor": 119.0},
    "Tulang Ayam": {"kg": 3.0, "ekor": 0.0},
}
PRODUCT_RESTORE = {
    "Ayam Broiler": {
        "buy_price_kg": 24000.0,   # 4.440.000 / 185 kg
        "hpp_kg": 28000.0,         # terbukti dari hpp_unit penjualan sah 28 & 29 Agu
    },
}

COLLECTIONS = [
    "sales", "purchases", "payables", "receivables", "incomes", "expenses",
    "stock_movements", "activities", "notifications", "audit_logs",
    "daily_closings", "files", "price_history", "slaughters", "productions",
    "wa_logs",
]


async def restore_debts(db, coll: str, name_key: str, sale_link: bool):
    """Pulihkan tagihan LAMA yang ikut dibayar saat pengujian."""
    print(f"\n--- PULIHKAN {coll.upper()} YANG IKUT TERMUTASI ---")
    found = False
    async for doc in db[coll].find({"payments": {"$exists": True, "$ne": []},
                                    "created_at": {"$lt": CUTOFF}}):
        test_pays = [p for p in doc["payments"] if (p.get("at") or "") >= CUTOFF]
        if not test_pays:
            continue
        found = True
        amt = round(sum(float(p.get("amount", 0) or 0) for p in test_pays), 2)
        keep = [p for p in doc["payments"] if (p.get("at") or "") < CUTOFF]
        paid = round(float(doc.get("paid", 0) or 0) - amt, 2)
        remaining = round(float(doc.get("remaining", 0) or 0) + amt, 2)
        status = "lunas" if remaining <= 0 else "belum_lunas"
        last = keep[-1].get("method") if keep else None
        print(f"{doc.get(name_key):<18} batalkan bayar uji Rp {amt:,.0f} | "
              f"paid {doc.get('paid')} -> {paid} | sisa {doc.get('remaining')} -> {remaining} | "
              f"metode {doc.get('last_method')} -> {last or '(dihapus)'}")
        if not APPLY:
            continue
        upd = {"$set": {"paid": paid, "remaining": remaining, "status": status, "payments": keep}}
        if last:
            upd["$set"]["last_method"] = last
        else:
            upd["$unset"] = {"last_method": ""}
        await db[coll].update_one({"id": doc["id"]}, upd)
        if sale_link and doc.get("sale_id"):
            await db.sales.update_one({"id": doc["sale_id"]}, {"$set": {
                "receivable": max(0, remaining),
                "payment_status": "lunas" if remaining <= 0 else "piutang"}})
    if not found:
        print("  (tidak ada)")


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    q = {"created_at": {"$gte": CUTOFF}}

    print(f"MODE: {'APPLY (menghapus)' if APPLY else 'SIMULASI (tidak mengubah)'}")
    print(f"Batas waktu artefak uji: created_at >= {CUTOFF}\n")

    # 1) Hitung ulang stok dari delta movement pada rentang uji.
    deltas = {}
    async for m in db.stock_movements.find(q):
        d = deltas.setdefault(m["product_id"], {"name": m.get("product_name"), "kg": 0.0,
                                                "ekor": 0.0, "pcs": 0.0, "n": 0})
        d["kg"] += float(m.get("qty_kg", 0) or 0)
        d["ekor"] += float(m.get("qty_ekor", 0) or 0)
        d["pcs"] += float(m.get("qty_pcs", 0) or 0)
        d["n"] += 1

    print("--- PEMULIHAN STOK ---")
    ok = True
    planned = []
    for pid, d in deltas.items():
        p = await db.products.find_one({"id": pid})
        if not p:
            continue
        new_kg = round(float(p.get("stock_kg", 0) or 0) - d["kg"], 3)
        new_ekor = round(float(p.get("stock_ekor", 0) or 0) - d["ekor"], 3)
        new_pcs = round(float(p.get("stock_pcs", 0) or 0) - d["pcs"], 3)
        print(f"{d['name']:<16} {d['n']:>3} movement | "
              f"kg {p.get('stock_kg')} -> {new_kg} | ekor {p.get('stock_ekor')} -> {new_ekor} | "
              f"pcs {p.get('stock_pcs')} -> {new_pcs}")
        exp = EXPECTED_STOCK.get(d["name"])
        if exp:
            good = abs(new_kg - exp["kg"]) < 0.01 and abs(new_ekor - exp["ekor"]) < 0.01
            print(f"{'':<16}     cek vs nilai sebelum uji {exp}: {'COCOK' if good else 'TIDAK COCOK'}")
            ok = ok and good
        planned.append((pid, new_kg, new_ekor, new_pcs))

    if not ok:
        print("\nBERHENTI: stok hasil hitungan tidak cocok dengan nilai sebelum uji.")
        return
    if APPLY:
        for pid, kg, ekor, pcs in planned:
            await db.products.update_one({"id": pid}, {"$set": {
                "stock_kg": kg, "stock_ekor": ekor, "stock_pcs": pcs}})

    # 2) Pulihkan tagihan lama yang ikut dibayar saat pengujian.
    await restore_debts(db, "receivables", "customer_name", sale_link=True)
    await restore_debts(db, "payables", "supplier_name", sale_link=False)

    # 3) Pulihkan akumulator berat/ekor dari pembelian yang TERSISA.
    print("\n--- AKUMULATOR BERAT/EKOR (dihitung dari pembelian sah) ---")
    agg = {}
    async for pur in db.purchases.find({"created_at": {"$lt": CUTOFF}}):
        for it in pur.get("items", []):
            a = agg.setdefault(it["product_id"], {"ekor": 0.0, "kg": 0.0})
            a["ekor"] += float(it.get("ekor", 0) or 0)
            a["kg"] += float(it.get("total_weight", 0) or 0)
    for pid, a in agg.items():
        p = await db.products.find_one({"id": pid})
        avg = round(a["kg"] / a["ekor"], 3) if a["ekor"] > 0 else 0.0
        restore = PRODUCT_RESTORE.get(p["name"], {})
        hpp_kg = restore.get("hpp_kg", float(p.get("hpp_kg", 0) or 0))
        hpp_ekor = round(hpp_kg * avg, 2) if avg > 0 else 0.0
        print(f"{p['name']:<16} cum_ekor {p.get('cum_ekor_in')} -> {a['ekor']} | "
              f"cum_kg {p.get('cum_weight_in')} -> {a['kg']} | avg {p.get('avg_weight_ekor')} -> {avg} | "
              f"hpp_kg {p.get('hpp_kg')} -> {hpp_kg} | hpp_ekor {p.get('hpp_ekor')} -> {hpp_ekor}")
        if APPLY:
            upd = {"cum_ekor_in": a["ekor"], "cum_weight_in": a["kg"],
                   "avg_weight_ekor": avg, "hpp_kg": hpp_kg, "hpp_ekor": hpp_ekor}
            upd.update(restore)
            await db.products.update_one({"id": pid}, {"$set": upd})

    # 4) Hapus dokumen artefak uji.
    print("\n--- HAPUS DOKUMEN UJI ---")
    total = 0
    for col in COLLECTIONS:
        n = await db[col].count_documents(q)
        total += n
        if n:
            print(f"{col:<18} {n}")
        if APPLY and n:
            await db[col].delete_many(q)
    print(f"{'TOTAL':<18} {total}")

    print("\nSisa data:")
    for col in ("sales", "purchases", "receivables", "payables", "expenses", "incomes",
                "daily_closings", "files", "stock_movements"):
        print(f"  {col:<16} {await db[col].count_documents({})}")

    if not APPLY:
        print("\n(Simulasi selesai — belum ada yang diubah. Jalankan lagi dengan --apply.)")


asyncio.run(main())
