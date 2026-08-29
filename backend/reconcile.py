"""Rekonsiliasi data: menjaga semua angka turunan tetap sinkron dengan sumbernya.

Masalah yang diselesaikan modul ini (dilaporkan owner 2026-08-29):
  * Pembelian yang tidak muncul di Keuangan (tidak ada catatan pengeluaran).
  * Saldo hutang / total belanja supplier tidak mengikuti data pembelian.
  * Saldo piutang / total belanja pelanggan tidak mengikuti data penjualan.
  * Transaksi masih berstatus "piutang" padahal tagihannya sudah dilunasi.
  * Penjualan yang dibatalkan meninggalkan tagihan piutang "hantu".
  * Kekurangan bayar tanpa dokumen tagihan (piutang tidak terlihat di Keuangan).
  * Catatan pemasukan yang hilang, dobel, atau yatim (transaksinya sudah dibatalkan).

SUMBER KEBENARAN (source of truth):
  penjualan   -> pemasukan pos, tagihan piutang, saldo pelanggan
  pembelian   -> pengeluaran "Pembelian Ayam", saldo supplier
  tagihan     -> sisa piutang/hutang pada dokumen penjualan & saldo mitra

STRUKTUR: setiap invarian punya SATU fungsi pemeriksa `_check_*(a: _Audit)` yang
pendek dan berdiri sendiri; `audit()` hanya memuat data lalu menjalankan daftar
pemeriksa itu. Menambah invarian baru = menambah satu fungsi + satu entri CHECKS.

Semua fungsi di sini IDEMPOTEN: dijalankan berapa kali pun hasilnya sama.
"""

import logging
import uuid
from typing import Dict, List

from finance import num

logger = logging.getLogger("berkah")

BIG = 100000
MODAL_CATEGORY = "Pembelian Ayam"
DEBT_CATEGORY = "Pembayaran Hutang"
CLOSED_BILL = ("lunas", "batal")


def _id() -> str:
    return str(uuid.uuid4())


def _eq(a, b, tol: float = 1.0) -> bool:
    """Bandingkan dua nilai uang dengan toleransi pembulatan Rp 1."""
    return abs(num(a) - num(b)) <= tol


class _Audit:
    """Wadah satu sesi pemeriksaan: data sumber, pencatat temuan, dan penghitung perbaikan."""

    def __init__(self, db, fix: bool, actor: str):
        self.db = db
        self.fix = fix
        self.actor = actor
        self.findings: List[dict] = []
        self.fixed = 0
        self.sales: List[dict] = []
        self.active_sales: List[dict] = []
        self.sale_by_id: Dict[str, dict] = {}
        self.active_ids: set = set()
        self.purchases: List[dict] = []
        self.receivables: List[dict] = []
        self.payables: List[dict] = []

    async def load(self):
        """Ambil sekali semua dokumen sumber yang dipakai pemeriksa."""
        self.sales = await self.db.sales.find().to_list(BIG)
        self.active_sales = [s for s in self.sales if s.get("status") != "batal"]
        self.sale_by_id = {s["id"]: s for s in self.sales}
        self.active_ids = {s["id"] for s in self.active_sales}
        self.purchases = await self.db.purchases.find().to_list(BIG)
        self.receivables = await self.db.receivables.find().to_list(BIG)
        self.payables = await self.db.payables.find().to_list(BIG)

    async def reload_receivables(self):
        self.receivables = await self.db.receivables.find().to_list(BIG)

    def note(self, kind: str, label: str, detail: str, amount: float = 0.0):
        self.findings.append({"kind": kind, "label": label, "detail": detail,
                              "amount": round(num(amount), 2), "fixed": self.fix})

    def counted(self) -> bool:
        """Tandai satu perbaikan dilakukan. Mengembalikan True bila mode perbaikan aktif."""
        if not self.fix:
            return False
        self.fixed += 1
        return True

    def summary(self) -> Dict:
        by_kind: Dict[str, int] = {}
        for f in self.findings:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        return {
            "checked_at": None,  # diisi pemanggil
            "issue_count": len(self.findings),
            "fixed_count": self.fixed if self.fix else 0,
            "repaired": self.fix,
            "by_kind": [{"kind": k, "count": v} for k, v in sorted(by_kind.items(), key=lambda x: -x[1])],
            "findings": self.findings[:200],
        }


# ------------------------- 1. pembelian -> pengeluaran -------------------------
async def _check_purchase_expense(a: _Audit):
    """Setiap pembelian wajib punya satu pengeluaran "Pembelian Ayam" yang nilainya cocok."""
    for p in a.purchases:
        modal = num(p.get("total_modal"))
        where = f"{p.get('date')} \u00b7 {p.get('supplier_name', '-')}"
        exp = await a.db.expenses.find_one({"ref": p["id"], "category": MODAL_CATEGORY})

        if exp is None:
            a.note("pembelian_tanpa_pengeluaran", "Pembelian tidak tercatat di Keuangan", where, modal)
            if a.counted():
                await a.db.expenses.insert_one({
                    "id": _id(), "date": p.get("date"), "category": MODAL_CATEGORY,
                    "amount": modal, "cash_amount": num(p.get("paid")),
                    "description": f"Pembelian dari {p.get('supplier_name', '-')}",
                    "ref": p["id"], "created_by": a.actor, "created_at": p.get("created_at"),
                })
            continue

        if _eq(exp.get("amount"), modal) and exp.get("cash_amount") is not None:
            continue

        a.note("pengeluaran_pembelian_tidak_cocok", "Nilai pengeluaran pembelian tidak cocok", where, modal)
        if a.counted():
            await a.db.expenses.update_one({"id": exp["id"]}, {"$set": {
                "amount": modal, "cash_amount": num(p.get("paid")), "date": p.get("date")}})


# ------------------------- 2. penanda kas keluar -------------------------
async def _check_debt_cash_flag(a: _Audit):
    """Pelunasan hutang lama tanpa `cash_amount` -> anggap kas keluar penuh."""
    async for e in a.db.expenses.find({"category": DEBT_CATEGORY, "cash_amount": None}):
        a.note("kas_keluar_belum_ditandai", "Pembayaran hutang belum bertanda kas keluar",
               e.get("description", "-"), e.get("amount"))
        if a.counted():
            await a.db.expenses.update_one({"id": e["id"]},
                                           {"$set": {"cash_amount": num(e.get("amount"))}})


# ------------------------- 3. pembayaran hutang yatim -------------------------
async def _check_orphan_debt_payment(a: _Audit):
    """Pelunasan hutang yang tagihannya sudah tidak ada (pembeliannya dibatalkan/dihapus).

    Kalau dibiarkan, catatan ini terus menambah "uang keluar" padahal pembeliannya
    sudah dianggap tidak pernah terjadi.
    """
    ids = {p.get("id") for p in a.payables}
    async for e in a.db.expenses.find({"category": DEBT_CATEGORY}):
        ref = e.get("ref")
        if not ref or ref in ids:
            continue
        a.note("pembayaran_hutang_yatim", "Pembayaran hutang tanpa tagihan (pembelian dihapus)",
               f"{e.get('date')} \u00b7 {e.get('description', '-')}", e.get("amount"))
        if a.counted():
            await a.db.expenses.delete_one({"id": e["id"]})


# ------------------------- 4. tagihan piutang vs penjualan -------------------------
async def _void_receivable_of_cancelled_sale(a: _Audit, r: dict):
    if r.get("status") == "batal" or num(r.get("remaining")) <= 0:
        return
    a.note("piutang_hantu", "Tagihan piutang dari transaksi batal",
           r.get("customer_name", "-"), r.get("remaining"))
    if a.counted():
        await a.db.receivables.update_one({"id": r["id"]},
                                          {"$set": {"status": "batal", "remaining": 0}})


async def _sync_sale_payment_status(a: _Audit, r: dict, sale: dict):
    remaining = max(num(r.get("remaining")), 0)
    status = "lunas" if remaining <= 0 else "piutang"
    if _eq(sale.get("receivable"), remaining) and sale.get("payment_status") == status:
        return
    a.note("status_transaksi_tertinggal", "Status pembayaran transaksi belum diperbarui",
           f"{sale.get('date')} \u00b7 {r.get('customer_name', '-')}",
           abs(num(sale.get("receivable")) - remaining))
    if a.counted():
        await a.db.sales.update_one({"id": sale["id"]}, {"$set": {
            "receivable": round(remaining, 2), "payment_status": status}})
        sale["receivable"] = round(remaining, 2)
        sale["payment_status"] = status


async def _check_receivable_vs_sale(a: _Audit):
    """Sisa tagihan piutang harus tercermin di dokumen penjualannya."""
    for r in a.receivables:
        sale = a.sale_by_id.get(r.get("sale_id"))
        if sale is None or sale.get("status") == "batal":
            await _void_receivable_of_cancelled_sale(a, r)
            continue
        await _sync_sale_payment_status(a, r, sale)


# ------------------------- 5. kekurangan bayar tanpa tagihan -------------------------
async def _check_sale_without_receivable(a: _Audit):
    """Kekurangan bayar tanpa dokumen tagihan = piutang tidak terlihat di Keuangan."""
    with_bill = {r.get("sale_id") for r in a.receivables}
    inserted = False
    for s in a.active_sales:
        sisa = num(s.get("receivable"))
        if sisa <= 0 or s["id"] in with_bill:
            continue
        a.note("piutang_tanpa_tagihan", "Kekurangan bayar tanpa tagihan piutang",
               f"{s.get('date')} \u00b7 {s.get('customer_name', 'Umum')}", sisa)
        if a.counted():
            await a.db.receivables.insert_one({
                "id": _id(), "customer_id": s.get("customer_id"),
                "customer_name": s.get("customer_name") or "Umum",
                "sale_id": s["id"], "amount": num(s.get("total")),
                "paid": num(s.get("paid")), "remaining": round(sisa, 2),
                "due_date": None, "status": "belum_lunas", "date": s.get("date"),
                "created_at": s.get("created_at")})
            inserted = True
    if inserted:
        # pemeriksa saldo pelanggan di bawah harus melihat tagihan yang baru dibuat
        await a.reload_receivables()


# ------------------------- 6. pemasukan vs penjualan -------------------------
async def _check_income_orphans(a: _Audit, inc_by_ref: Dict[str, List[dict]]):
    for ref, rows in inc_by_ref.items():
        if ref not in a.active_ids:
            a.note("pemasukan_yatim", "Pemasukan dari transaksi batal/hilang", str(ref)[:8],
                   sum(num(x.get("amount")) for x in rows))
            if a.counted():
                await a.db.incomes.delete_many({"ref": ref, "source": "pos"})
            continue
        if len(rows) <= 1:
            continue
        a.note("pemasukan_dobel", "Pemasukan tercatat lebih dari sekali", str(ref)[:8],
               sum(num(x.get("amount")) for x in rows[1:]))
        if a.counted():
            for extra in rows[1:]:
                await a.db.incomes.delete_one({"id": extra["id"]})


async def _check_income_of_sale(a: _Audit, s: dict, rows: List[dict]):
    kas = num(s.get("paid"))
    where = f"{s.get('date')} \u00b7 {s.get('customer_name', '-')}"
    if not rows:
        a.note("pemasukan_hilang", "Penjualan tanpa catatan pemasukan", where, kas)
        if a.counted():
            await a.db.incomes.insert_one({
                "id": _id(), "date": s.get("date"), "category": "Penjualan Ayam",
                "amount": kas, "source": "pos", "ref": s["id"],
                "created_at": s.get("created_at")})
        return
    if _eq(rows[0].get("amount"), kas):
        return
    a.note("pemasukan_tidak_cocok", "Nilai pemasukan tidak sama dengan uang diterima",
           where, abs(num(rows[0].get("amount")) - kas))
    if a.counted():
        await a.db.incomes.update_one({"id": rows[0]["id"]},
                                      {"$set": {"amount": kas, "date": s.get("date")}})


async def _check_incomes(a: _Audit):
    """Setiap penjualan aktif = tepat satu pemasukan pos sebesar uang yang diterima."""
    incomes = await a.db.incomes.find({"source": "pos"}).to_list(BIG)
    inc_by_ref: Dict[str, List[dict]] = {}
    for i in incomes:
        inc_by_ref.setdefault(i.get("ref"), []).append(i)
    await _check_income_orphans(a, inc_by_ref)
    for s in a.active_sales:
        await _check_income_of_sale(a, s, inc_by_ref.get(s["id"]) or [])


# ------------------------- 7. saldo pelanggan -------------------------
def _open_receivable_per_customer(a: _Audit) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for r in a.receivables:
        if r.get("status") in CLOSED_BILL:
            continue
        sale = a.sale_by_id.get(r.get("sale_id"))
        if sale is not None and sale.get("status") == "batal":
            continue
        cid = r.get("customer_id")
        out[cid] = out.get(cid, 0.0) + max(num(r.get("remaining")), 0)
    return out


async def _check_customer_balance(a: _Audit):
    """Saldo piutang & total belanja pelanggan = hasil hitung dari transaksinya."""
    open_recv = _open_receivable_per_customer(a)
    belanja: Dict[str, float] = {}
    for s in a.active_sales:
        cid = s.get("customer_id")
        if cid:
            belanja[cid] = belanja.get(cid, 0.0) + num(s.get("total"))

    async for c in a.db.customers.find():
        want_recv = round(open_recv.get(c["id"], 0.0), 2)
        want_buy = round(belanja.get(c["id"], 0.0), 2)
        if _eq(c.get("receivable"), want_recv) and _eq(c.get("total_purchase"), want_buy):
            continue
        a.note("saldo_pelanggan", "Saldo pelanggan tidak cocok dengan transaksi",
               c.get("name", "-"), abs(num(c.get("receivable")) - want_recv))
        if a.counted():
            await a.db.customers.update_one({"id": c["id"]}, {"$set": {
                "receivable": want_recv, "total_purchase": want_buy}})


# ------------------------- 8. saldo supplier -------------------------
async def _check_supplier_balance(a: _Audit):
    """Saldo hutang & total belanja supplier = hasil hitung dari pembeliannya."""
    open_pay: Dict[str, float] = {}
    for p in a.payables:
        if p.get("status") in CLOSED_BILL:
            continue
        sid = p.get("supplier_id")
        open_pay[sid] = open_pay.get(sid, 0.0) + max(num(p.get("remaining")), 0)

    modal: Dict[str, float] = {}
    for p in a.purchases:
        sid = p.get("supplier_id")
        modal[sid] = modal.get(sid, 0.0) + num(p.get("total_modal"))

    async for sup in a.db.suppliers.find():
        want_pay = round(open_pay.get(sup["id"], 0.0), 2)
        want_buy = round(modal.get(sup["id"], 0.0), 2)
        if _eq(sup.get("payable"), want_pay) and _eq(sup.get("total_purchase"), want_buy):
            continue
        a.note("saldo_supplier", "Saldo supplier tidak cocok dengan pembelian",
               sup.get("name", "-"), abs(num(sup.get("total_purchase")) - want_buy))
        if a.counted():
            await a.db.suppliers.update_one({"id": sup["id"]}, {"$set": {
                "payable": want_pay, "total_purchase": want_buy}})


# Urutan penting: tagihan dibereskan lebih dulu, saldo mitra dihitung terakhir.
CHECKS = (
    _check_purchase_expense,
    _check_debt_cash_flag,
    _check_orphan_debt_payment,
    _check_receivable_vs_sale,
    _check_sale_without_receivable,
    _check_incomes,
    _check_customer_balance,
    _check_supplier_balance,
)


async def audit(db, fix: bool = False, actor: str = "system") -> Dict:
    """Periksa (dan bila fix=True, perbaiki) konsistensi antar modul.

    Mengembalikan ringkasan temuan agar bisa ditampilkan ke owner.
    """
    a = _Audit(db, fix, actor)
    await a.load()
    for check in CHECKS:
        await check(a)
    return a.summary()


async def repair_on_startup(db) -> Dict:
    """Dipanggil saat backend menyala: rapikan data warisan tanpa perlu tombol."""
    res = await audit(db, fix=True, actor="system")
    if res["fixed_count"]:
        logger.info("Rekonsiliasi data: %s perbaikan (%s)", res["fixed_count"],
                    ", ".join(f"{x['kind']}={x['count']}" for x in res["by_kind"]))
    return res
