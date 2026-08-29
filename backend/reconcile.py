"""Rekonsiliasi data: menjaga semua angka turunan tetap sinkron dengan sumbernya.

Masalah yang diselesaikan modul ini (dilaporkan owner 2026-08-29):
  * Pembelian yang tidak muncul di Keuangan (tidak ada catatan pengeluaran).
  * Saldo hutang / total belanja supplier tidak mengikuti data pembelian.
  * Saldo piutang / total belanja pelanggan tidak mengikuti data penjualan.
  * Transaksi masih berstatus "piutang" padahal tagihannya sudah dilunasi.
  * Penjualan yang dibatalkan meninggalkan tagihan piutang "hantu".
  * Catatan pemasukan yang hilang atau yatim (transaksinya sudah dibatalkan).

SUMBER KEBENARAN (source of truth):
  penjualan   -> pemasukan pos, tagihan piutang, saldo pelanggan
  pembelian   -> pengeluaran "Pembelian Ayam", saldo supplier
  tagihan     -> sisa piutang/hutang pada dokumen penjualan & saldo mitra

Semua fungsi di sini IDEMPOTEN: dijalankan berapa kali pun hasilnya sama.
"""

import logging
import uuid
from typing import Dict, List

from finance import num

logger = logging.getLogger("berkah")

BIG = 100000


def _id() -> str:
    return str(uuid.uuid4())


def _eq(a, b, tol: float = 1.0) -> bool:
    return abs(num(a) - num(b)) <= tol


async def audit(db, fix: bool = False, actor: str = "system") -> Dict:
    """Periksa (dan bila fix=True, perbaiki) konsistensi antar modul.

    Mengembalikan ringkasan temuan agar bisa ditampilkan ke owner.
    """
    findings: List[dict] = []
    fixed = 0

    def note(kind: str, label: str, detail: str, amount: float = 0.0):
        findings.append({"kind": kind, "label": label, "detail": detail,
                         "amount": round(num(amount), 2), "fixed": fix})

    sales = await db.sales.find().to_list(BIG)
    active_sales = [s for s in sales if s.get("status") != "batal"]
    active_ids = {s["id"] for s in active_sales}
    all_ids = {s["id"] for s in sales}
    sale_by_id = {s["id"]: s for s in sales}

    # ---------- 1. pembelian -> pengeluaran ----------
    purchases = await db.purchases.find().to_list(BIG)
    for p in purchases:
        exists = await db.expenses.find_one({"ref": p["id"], "category": "Pembelian Ayam"})
        modal = num(p.get("total_modal"))
        if exists is None:
            note("pembelian_tanpa_pengeluaran", "Pembelian tidak tercatat di Keuangan",
                 f"{p.get('date')} · {p.get('supplier_name', '-')}", modal)
            if fix:
                await db.expenses.insert_one({
                    "id": _id(), "date": p.get("date"), "category": "Pembelian Ayam",
                    "amount": modal, "cash_amount": num(p.get("paid")),
                    "description": f"Pembelian dari {p.get('supplier_name', '-')}",
                    "ref": p["id"], "created_by": actor, "created_at": p.get("created_at"),
                })
                fixed += 1
        elif not _eq(exists.get("amount"), modal) or exists.get("cash_amount") is None:
            note("pengeluaran_pembelian_tidak_cocok", "Nilai pengeluaran pembelian tidak cocok",
                 f"{p.get('date')} · {p.get('supplier_name', '-')}", modal)
            if fix:
                await db.expenses.update_one({"id": exists["id"]}, {"$set": {
                    "amount": modal, "cash_amount": num(p.get("paid")), "date": p.get("date")}})
                fixed += 1

    # pengeluaran modal lama tanpa penanda kas -> anggap kas keluar penuh
    async for e in db.expenses.find({"category": "Pembayaran Hutang", "cash_amount": None}):
        note("kas_keluar_belum_ditandai", "Pembayaran hutang belum bertanda kas keluar",
             e.get("description", "-"), e.get("amount"))
        if fix:
            await db.expenses.update_one({"id": e["id"]},
                                         {"$set": {"cash_amount": num(e.get("amount"))}})
            fixed += 1

    # ---------- 2. tagihan piutang vs penjualan ----------
    receivables = await db.receivables.find().to_list(BIG)
    for r in receivables:
        sid = r.get("sale_id")
        sale = sale_by_id.get(sid)
        # tagihan milik penjualan yang dibatalkan / hilang
        if sale is None or sale.get("status") == "batal":
            if r.get("status") != "batal" and num(r.get("remaining")) > 0:
                note("piutang_hantu", "Tagihan piutang dari transaksi batal",
                     r.get("customer_name", "-"), r.get("remaining"))
                if fix:
                    await db.receivables.update_one({"id": r["id"]},
                                                    {"$set": {"status": "batal", "remaining": 0}})
                    fixed += 1
            continue
        remaining = max(num(r.get("remaining")), 0)
        status = "lunas" if remaining <= 0 else "piutang"
        if not _eq(sale.get("receivable"), remaining) or sale.get("payment_status") != status:
            note("status_transaksi_tertinggal", "Status pembayaran transaksi belum diperbarui",
                 f"{sale.get('date')} · {r.get('customer_name', '-')}",
                 abs(num(sale.get("receivable")) - remaining))
            if fix:
                await db.sales.update_one({"id": sid}, {"$set": {
                    "receivable": round(remaining, 2), "payment_status": status}})
                sale["receivable"] = round(remaining, 2)
                sale["payment_status"] = status
                fixed += 1

    # ---------- 3. penjualan berpiutang tanpa dokumen tagihan ----------
    recv_by_sale = {r.get("sale_id") for r in receivables}
    for s in active_sales:
        sisa = num(s.get("receivable"))
        if sisa > 0 and s["id"] not in recv_by_sale:
            note("piutang_tanpa_tagihan", "Kekurangan bayar tanpa tagihan piutang",
                 f"{s.get('date')} \u00b7 {s.get('customer_name', 'Umum')}", sisa)
            if fix:
                await db.receivables.insert_one({
                    "id": _id(), "customer_id": s.get("customer_id"),
                    "customer_name": s.get("customer_name") or "Umum",
                    "sale_id": s["id"], "amount": num(s.get("total")),
                    "paid": num(s.get("paid")), "remaining": round(sisa, 2),
                    "due_date": None, "status": "belum_lunas", "date": s.get("date"),
                    "created_at": s.get("created_at")})
                fixed += 1
    if fix:
        receivables = await db.receivables.find().to_list(BIG)

    # ---------- 4. pemasukan vs penjualan ----------
    incomes = await db.incomes.find({"source": "pos"}).to_list(BIG)
    inc_by_ref: Dict[str, List[dict]] = {}
    for i in incomes:
        inc_by_ref.setdefault(i.get("ref"), []).append(i)
    for ref, rows in inc_by_ref.items():
        if ref not in all_ids or ref not in active_ids:
            note("pemasukan_yatim", "Pemasukan dari transaksi batal/hilang", str(ref)[:8],
                 sum(num(x.get("amount")) for x in rows))
            if fix:
                await db.incomes.delete_many({"ref": ref, "source": "pos"})
                fixed += 1
        elif len(rows) > 1:
            note("pemasukan_dobel", "Pemasukan tercatat lebih dari sekali", str(ref)[:8],
                 sum(num(x.get("amount")) for x in rows[1:]))
            if fix:
                for extra in rows[1:]:
                    await db.incomes.delete_one({"id": extra["id"]})
                fixed += 1
    for s in active_sales:
        rows = inc_by_ref.get(s["id"]) or []
        kas = num(s.get("paid"))
        if not rows:
            note("pemasukan_hilang", "Penjualan tanpa catatan pemasukan",
                 f"{s.get('date')} · {s.get('customer_name', '-')}", kas)
            if fix:
                await db.incomes.insert_one({
                    "id": _id(), "date": s.get("date"), "category": "Penjualan Ayam",
                    "amount": kas, "source": "pos", "ref": s["id"],
                    "created_at": s.get("created_at")})
                fixed += 1
        elif not _eq(rows[0].get("amount"), kas):
            note("pemasukan_tidak_cocok", "Nilai pemasukan tidak sama dengan uang diterima",
                 f"{s.get('date')} · {s.get('customer_name', '-')}",
                 abs(num(rows[0].get("amount")) - kas))
            if fix:
                await db.incomes.update_one({"id": rows[0]["id"]},
                                            {"$set": {"amount": kas, "date": s.get("date")}})
                fixed += 1

    # ---------- 5. saldo pelanggan ----------
    open_recv: Dict[str, float] = {}
    for r in receivables:
        if r.get("status") in ("lunas", "batal"):
            continue
        sale = sale_by_id.get(r.get("sale_id"))
        if sale is not None and sale.get("status") == "batal":
            continue
        open_recv[r.get("customer_id")] = open_recv.get(r.get("customer_id"), 0.0) + max(num(r.get("remaining")), 0)
    belanja: Dict[str, float] = {}
    for s in active_sales:
        cid = s.get("customer_id")
        if cid:
            belanja[cid] = belanja.get(cid, 0.0) + num(s.get("total"))
    customers = await db.customers.find().to_list(BIG)
    for c in customers:
        want_recv = round(open_recv.get(c["id"], 0.0), 2)
        want_buy = round(belanja.get(c["id"], 0.0), 2)
        if not _eq(c.get("receivable"), want_recv) or not _eq(c.get("total_purchase"), want_buy):
            note("saldo_pelanggan", "Saldo pelanggan tidak cocok dengan transaksi",
                 c.get("name", "-"), abs(num(c.get("receivable")) - want_recv))
            if fix:
                await db.customers.update_one({"id": c["id"]}, {"$set": {
                    "receivable": want_recv, "total_purchase": want_buy}})
                fixed += 1

    # ---------- 6. saldo supplier ----------
    payables = await db.payables.find().to_list(BIG)
    open_pay: Dict[str, float] = {}
    for p in payables:
        if p.get("status") in ("lunas", "batal"):
            continue
        open_pay[p.get("supplier_id")] = open_pay.get(p.get("supplier_id"), 0.0) + max(num(p.get("remaining")), 0)
    modal_by_sup: Dict[str, float] = {}
    for p in purchases:
        sid = p.get("supplier_id")
        modal_by_sup[sid] = modal_by_sup.get(sid, 0.0) + num(p.get("total_modal"))
    suppliers = await db.suppliers.find().to_list(BIG)
    for sup in suppliers:
        want_pay = round(open_pay.get(sup["id"], 0.0), 2)
        want_buy = round(modal_by_sup.get(sup["id"], 0.0), 2)
        if not _eq(sup.get("payable"), want_pay) or not _eq(sup.get("total_purchase"), want_buy):
            note("saldo_supplier", "Saldo supplier tidak cocok dengan pembelian",
                 sup.get("name", "-"), abs(num(sup.get("total_purchase")) - want_buy))
            if fix:
                await db.suppliers.update_one({"id": sup["id"]}, {"$set": {
                    "payable": want_pay, "total_purchase": want_buy}})
                fixed += 1

    by_kind: Dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1

    return {
        "checked_at": None,  # diisi pemanggil
        "issue_count": len(findings),
        "fixed_count": fixed if fix else 0,
        "repaired": fix,
        "by_kind": [{"kind": k, "count": v} for k, v in sorted(by_kind.items(), key=lambda x: -x[1])],
        "findings": findings[:200],
    }


async def repair_on_startup(db) -> Dict:
    """Dipanggil saat backend menyala: rapikan data warisan tanpa perlu tombol."""
    res = await audit(db, fix=True, actor="system")
    if res["fixed_count"]:
        logger.info("Rekonsiliasi data: %s perbaikan (%s)", res["fixed_count"],
                    ", ".join(f"{x['kind']}={x['count']}" for x in res["by_kind"]))
    return res
