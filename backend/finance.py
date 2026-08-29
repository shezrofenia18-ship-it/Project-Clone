"""Rumus keuangan TUNGGAL untuk seluruh aplikasi.

Semua halaman yang menampilkan uang (Dashboard, Laporan Laba-Rugi, Tutup Buku,
Grafik Bulanan) WAJIB memakai fungsi di modul ini supaya angkanya tidak pernah
berbeda antar halaman.

Definisi yang disetujui owner (2026-08-29):

    Laba Kotor         = Omzet - HPP
    Biaya Operasional  = semua pengeluaran KECUALI kategori modal
                         ("Pembelian Ayam", "Pembayaran Hutang")
    Laba Bersih Usaha  = Laba Kotor - Biaya Operasional

    Kas Masuk          = seluruh catatan pemasukan (tunai penjualan + pembayaran piutang)
    Kas Keluar         = Biaya Operasional + uang yang BENAR-BENAR dibayarkan
                         untuk ayam & pelunasan hutang
    Uang Bersih (Kas)  = Kas Masuk - Kas Keluar

Biaya beli ayam TIDAK dikurangi dua kali: pada jalur laba ia sudah terkandung di
HPP setiap penjualan, pada jalur kas ia dihitung sebagai kas keluar. Karena itu
pengeluaran modal dipisah dari biaya operasional.

Catatan kas untuk pembelian: dokumen pengeluaran pembelian menyimpan
``amount`` (nilai modal / akrual) dan ``cash_amount`` (uang yang dibayar saat itu).
Pelunasan hutang dicatat terpisah dengan ``cash_amount`` = jumlah bayar, sehingga
kas keluar tidak pernah dihitung dobel.
"""

from typing import Dict, Iterable, List

# Kategori pengeluaran yang merupakan MODAL (bukan biaya operasional).
MODAL_CATEGORIES = ("Pembelian Ayam", "Pembayaran Hutang")
# Nama lama, dipertahankan supaya kode yang sudah ada tetap jalan.
OPEX_EXCLUDE = MODAL_CATEGORIES

MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def num(v) -> float:
    """Ubah nilai apa pun dari database menjadi float yang aman."""
    try:
        if v is None:
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def r2(v) -> float:
    return round(num(v), 2)


def pct(part, whole) -> float:
    w = num(whole)
    return round(num(part) / w * 100, 2) if w else 0.0


# ------------------------- pengeluaran -------------------------
def expense_split(expenses: Iterable[dict]) -> Dict:
    """Pisahkan pengeluaran menjadi biaya operasional vs modal (+ kas keluarnya)."""
    opex = 0.0
    modal_value = 0.0
    modal_cash = 0.0
    by_cat: Dict[str, float] = {}
    for e in expenses:
        amt = num(e.get("amount"))
        cat = e.get("category") or "Lain-lain"
        by_cat[cat] = by_cat.get(cat, 0.0) + amt
        if cat in MODAL_CATEGORIES:
            modal_value += amt
            cash = e.get("cash_amount")
            modal_cash += num(cash) if cash is not None else amt
        else:
            opex += amt
    return {
        "opex": round(opex, 2),
        "modal_value": round(modal_value, 2),
        "modal_cash": round(modal_cash, 2),
        "expense_total": round(opex + modal_value, 2),
        "cash_out": round(opex + modal_cash, 2),
        "expenses_by_category": [{"category": k, "amount": round(v, 2)}
                                 for k, v in sorted(by_cat.items(), key=lambda x: -x[1])],
    }


# ------------------------- penjualan -------------------------
def sales_split(sales: Iterable[dict]) -> Dict:
    """Ringkas penjualan (harus sudah difilter status != batal)."""
    omzet = hpp = diskon = piutang_baru = kas_jual = 0.0
    weight = ekor = pcs = 0.0
    count = 0
    for s in sales:
        count += 1
        total = num(s.get("total"))
        s_hpp = num(s.get("total_hpp"))
        # "paid" = uang tunai yang diterima saat transaksi (tidak berubah walau
        # piutangnya dilunasi belakangan -> pelunasan dicatat sebagai pemasukan).
        kas = num(s.get("paid"))
        omzet += total
        hpp += s_hpp
        diskon += num(s.get("discount"))
        piutang_baru += max(total - kas, 0)
        kas_jual += min(kas, total)
        weight += num(s.get("total_weight"))
        ekor += num(s.get("total_ekor"))
        for it in s.get("items", []) or []:
            if it.get("unit") == "pcs":
                pcs += num(it.get("qty"))
    gross = round(omzet - hpp, 2)
    return {
        "omzet": round(omzet, 2), "hpp": round(hpp, 2), "gross_profit": gross,
        "margin": pct(gross, omzet), "diskon": round(diskon, 2),
        "txn_count": count, "weight": round(weight, 3), "ekor": round(ekor, 2),
        "pcs": round(pcs, 2),
        "piutang_baru": round(piutang_baru, 2),
        "kas_dari_penjualan": round(kas_jual, 2),
    }


# ------------------------- pemasukan -------------------------
def income_split(incomes: Iterable[dict]) -> Dict:
    total = 0.0
    bayar_piutang = 0.0
    for i in incomes:
        amt = num(i.get("amount"))
        total += amt
        if i.get("category") == "Pembayaran Piutang":
            bayar_piutang += amt
    return {"cash_in": round(total, 2), "bayar_piutang_masuk": round(bayar_piutang, 2)}


# ------------------------- gabungan -------------------------
def summarize(sales: Iterable[dict], expenses: Iterable[dict], incomes: Iterable[dict]) -> Dict:
    """Satu-satunya tempat rumus laba & kas dihitung."""
    s = sales_split(sales)
    e = expense_split(expenses)
    i = income_split(incomes)
    net_profit = round(s["gross_profit"] - e["opex"], 2)
    net_cash = round(i["cash_in"] - e["cash_out"], 2)
    out = {**s, **e, **i}
    out.update({
        "net_profit": net_profit,
        "net_margin": pct(net_profit, s["omzet"]),
        "net_cash": net_cash,
        "kas_masuk_total": i["cash_in"],
    })
    return out


# ------------------------- bulan -------------------------
def month_key(date_str: str) -> str:
    return (date_str or "")[:7]


def month_label(ym: str) -> str:
    """'2026-08' -> 'Agu 26'."""
    try:
        y, m = ym.split("-")[:2]
        return f"{MONTH_SHORT[int(m) - 1]} {y[2:]}"
    except (ValueError, IndexError):
        return ym


def month_series(year: int, month: int, months: int) -> List[str]:
    """Daftar 'YYYY-MM' berurutan yang BERAKHIR di (year, month), panjang `months`."""
    out = []
    y, m = year, month
    for _ in range(months):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))
