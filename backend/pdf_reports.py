"""Laporan PDF berkop toko untuk Berkah Ayam Mili (reportlab).

Semua PDF dibuat di server supaya hasil cetaknya konsisten (tidak tergantung
browser/printer kasir) dan enak dibagikan ke owner lewat WhatsApp/email.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

JKT = timezone(timedelta(hours=7))

BRAND = colors.HexColor("#DB371A")
INK = colors.HexColor("#1F2938")
MUTED = colors.HexColor("#6B7280")
ZEBRA = colors.HexColor("#F7F7F8")
LINE = colors.HexColor("#D8DBE0")
POS = colors.HexColor("#4F7D5F")
NEG = colors.HexColor("#C0392B")

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

S_TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK)
S_STORE = ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=BRAND)
S_SMALL = ParagraphStyle("sm", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)
S_SMALL_R = ParagraphStyle("smr", parent=S_SMALL, alignment=TA_RIGHT)
S_META = ParagraphStyle("m", fontName="Helvetica", fontSize=9, leading=12, textColor=INK, alignment=TA_RIGHT)
S_SEC = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK,
                       spaceBefore=10, spaceAfter=4)
S_CELL = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)
S_SIGN = ParagraphStyle("sg", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK,
                        alignment=TA_CENTER)


# ------------------------- formatting helpers -------------------------
def rp(n) -> str:
    v = 0
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        return "Rp 0"
    return "Rp " + f"{v:,}".replace(",", ".")


def num(n, digits=0) -> str:
    v = 0.0
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return "0"
    s = f"{v:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(n) -> str:
    return f"{num(n, 2)}%"


def tgl(iso: str) -> str:
    """'2026-08-28' -> '28 Agustus 2026'. Nilai aneh dikembalikan apa adanya."""
    if not iso:
        return "-"
    d = None
    try:
        d = datetime.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        d = None
    if d is None or not 1 <= d.month <= 12:
        return str(iso)
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def tgl_singkat(iso: str) -> str:
    if not iso:
        return "-"
    d = None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        d = None
    if d is None:
        return str(iso)[:10]
    return d.strftime("%d/%m/%Y")


def _periode(start, end) -> str:
    if start and end:
        return f"{tgl(start)} — {tgl(end)}"
    return "Seluruh periode"


# ------------------------- document skeleton -------------------------
def _footer(store_name):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        cetak = datetime.now(JKT).strftime("%d/%m/%Y %H:%M")
        canvas.drawString(15 * mm, 9.5 * mm, f"{store_name} · dicetak {cetak} WIB")
        canvas.drawRightString(w - 15 * mm, 9.5 * mm, f"Halaman {canvas.getPageNumber()}")
        canvas.restoreState()
    return draw


def _kop(store, title, start=None, end=None, printed_by="", width=180 * mm):
    """Kop surat: identitas toko di kiri, judul + periode di kanan."""
    left = [Paragraph(store.get("name") or "Berkah Ayam Mili", S_STORE)]
    tagline = store.get("tagline") or "Ayam Potong & Fillet"
    left.append(Paragraph(tagline, S_SMALL))
    if store.get("address"):
        left.append(Paragraph(store["address"], S_SMALL))
    if store.get("phone"):
        left.append(Paragraph(f"Telp/WA: {store['phone']}", S_SMALL))

    right = [Paragraph(title.upper(), ParagraphStyle("tr", parent=S_TITLE, alignment=TA_RIGHT))]
    right.append(Paragraph(f"Periode: {_periode(start, end)}", S_META))
    if printed_by:
        right.append(Paragraph(f"Dicetak oleh: {printed_by}", S_SMALL_R))

    t = Table([[left, right]], colWidths=[width * 0.52, width * 0.48])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRAND),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    return [t, Spacer(1, 10)]


def _signature(printed_by, width=180 * mm):
    """Blok tanda tangan supaya laporan bisa diarsipkan/ditandatangani owner."""
    col = width / 2
    rows = [
        [Paragraph("Dibuat oleh", S_SIGN), Paragraph("Disetujui oleh", S_SIGN)],
        [Spacer(1, 22 * mm), Spacer(1, 22 * mm)],
        [Paragraph(f"( {printed_by or '________________'} )", S_SIGN),
         Paragraph("( ________________ )", S_SIGN)],
        [Paragraph("Petugas", S_SMALL_R.clone("x", alignment=TA_CENTER)),
         Paragraph("Owner", S_SMALL_R.clone("y", alignment=TA_CENTER))],
    ]
    t = Table(rows, colWidths=[col, col])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return [Spacer(1, 12), KeepTogether(t)]


def _build(story, store, title, orientation="portrait"):
    buf = BytesIO()
    size = landscape(A4) if orientation == "landscape" else A4
    doc = SimpleDocTemplate(
        buf, pagesize=size,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
        title=title, author=store.get("name") or "Berkah Ayam Mili",
    )
    draw = _footer(store.get("name") or "Berkah Ayam Mili")
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buf.getvalue()


def _table_style(ncols, money_from=1, header_bg=INK):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (money_from, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ])


# ------------------------- 1. Laba Rugi -------------------------
def profit_loss_pdf(data, store, start=None, end=None, printed_by=""):
    W = 180 * mm
    story = _kop(store, "Laporan Laba Rugi", start, end, printed_by, W)

    omzet = data.get("omzet", 0)
    hpp = data.get("hpp", 0)
    gross = data.get("gross_profit", 0)
    opex = data.get("opex", 0)
    net = data.get("net_profit", 0)

    rows = [
        ["Uraian", "Nilai", "% dari Omzet"],
        ["Omzet Penjualan", rp(omzet), pct(100 if omzet else 0)],
        ["Harga Pokok Penjualan (HPP)", "(" + rp(hpp) + ")", pct(hpp / omzet * 100 if omzet else 0)],
        ["LABA KOTOR", rp(gross), pct(data.get("gross_margin", 0))],
        ["Beban Operasional", "(" + rp(opex) + ")", pct(opex / omzet * 100 if omzet else 0)],
        ["LABA BERSIH", rp(net), pct(data.get("net_margin", 0))],
    ]
    t = Table(rows, colWidths=[W * 0.52, W * 0.26, W * 0.22])
    st = _table_style(3)
    st.add("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold")
    st.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EEF3EF"))
    st.add("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold")
    st.add("FONTSIZE", (0, 5), (-1, 5), 9.5)
    st.add("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#EEF3EF") if net >= 0 else colors.HexColor("#FBEDEB"))
    st.add("TEXTCOLOR", (1, 5), (1, 5), POS if net >= 0 else NEG)
    st.add("LINEABOVE", (0, 3), (-1, 3), 0.9, INK)
    st.add("LINEABOVE", (0, 5), (-1, 5), 0.9, INK)
    t.setStyle(st)
    story.append(t)

    exps = data.get("expenses_by_category") or []
    story.append(Paragraph("Rincian Beban per Kategori", S_SEC))
    if exps:
        erows = [["Kategori", "Jumlah"]]
        for e in sorted(exps, key=lambda x: -float(x.get("amount", 0) or 0)):
            erows.append([e.get("category", "-"), rp(e.get("amount"))])
        erows.append(["TOTAL BEBAN (termasuk pembelian & bayar hutang)",
                      rp(sum(float(e.get("amount", 0) or 0) for e in exps))])
        et = Table(erows, colWidths=[W * 0.7, W * 0.3])
        est = _table_style(2)
        est.add("FONTNAME", (0, len(erows) - 1), (-1, len(erows) - 1), "Helvetica-Bold")
        est.add("LINEABOVE", (0, len(erows) - 1), (-1, len(erows) - 1), 0.9, INK)
        et.setStyle(est)
        story.append(et)
    else:
        story.append(Paragraph("Tidak ada beban tercatat pada periode ini.", S_SMALL))

    story.append(Paragraph(
        "Catatan: Laba Kotor = Omzet − HPP. Beban Operasional tidak memasukkan "
        "\"Pembelian Ayam\" dan \"Pembayaran Hutang\" karena keduanya sudah diperhitungkan "
        "sebagai modal/HPP, bukan biaya usaha.", S_SMALL))
    story += _signature(printed_by, W)
    return _build(story, store, "Laporan Laba Rugi")


# ------------------------- 2. Penjualan -------------------------
MAX_DETAIL_ROWS = 400
PAYMENT_LABELS = {"cash": "Tunai", "transfer": "Transfer", "qris": "QRIS",
                  "debit": "Debit", "ewallet": "E-Wallet", "piutang": "Piutang"}


def _sales_summary_table(data, sales, W):
    """Baris ringkasan: jumlah transaksi, total, rata-rata, laba kotor."""
    total = float(data.get("total", 0) or 0)
    count = int(data.get("count", 0) or 0)
    total_hpp = sum(float(s.get("total_hpp", 0) or 0) for s in sales)
    laba = total - total_hpp if sales else 0
    rata = total / count if count else 0

    rows = [["Jumlah Transaksi", "Total Penjualan", "Rata-rata / Transaksi", "Estimasi Laba Kotor"],
            [num(count), rp(total), rp(rata), rp(laba)]]
    t = Table(rows, colWidths=[W * 0.25] * 4)
    st = _table_style(4, money_from=0)
    st.add("ALIGN", (0, 0), (-1, -1), "CENTER")
    st.add("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold")
    st.add("FONTSIZE", (0, 1), (-1, 1), 10)
    t.setStyle(st)
    return t


def _sales_mini_recap(title, rows, key, half):
    """Satu kolom rekap kecil: per metode pembayaran atau per kasir."""
    out = [Paragraph(title, S_SEC)]
    if not rows:
        out.append(Paragraph("Tidak ada data.", S_SMALL))
        return out
    body = [[key.title(), "Total", "Porsi"]]
    tot = sum(float(r.get("total", 0) or 0) for r in rows) or 1
    for r in sorted(rows, key=lambda x: -float(x.get("total", 0) or 0)):
        label = r.get(key, "-")
        if key == "method":
            label = PAYMENT_LABELS.get(label, label)
        body.append([label, rp(r.get("total")), pct(float(r.get("total", 0) or 0) / tot * 100)])
    t = Table(body, colWidths=[half * 0.44, half * 0.34, half * 0.22])
    t.setStyle(_table_style(3))
    out.append(t)
    return out


def _sales_recap_grid(data, W):
    """Dua rekap kecil berdampingan (metode bayar | kasir)."""
    half = (W - 6 * mm) / 2
    left = _sales_mini_recap("Rekap per Metode Pembayaran", data.get("by_method") or [], "method", half)
    right = _sales_mini_recap("Rekap per Kasir", data.get("by_cashier") or [], "cashier", half)
    grid = Table([[left, right]], colWidths=[half + 3 * mm, half + 3 * mm])
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (0, 0), 0),
                              ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))
    return grid


def _sales_detail(sales, W):
    """Rincian transaksi, dibatasi MAX_DETAIL_ROWS baris supaya PDF tidak meledak."""
    out = [Paragraph("Rincian Transaksi", S_SEC)]
    if not sales:
        out.append(Paragraph("Tidak ada transaksi pada periode ini.", S_SMALL))
        return out

    rows = [["Tanggal", "Kasir", "Pelanggan", "Metode", "Item", "Total", "HPP", "Laba", "Margin"]]
    for s in sales[:MAX_DETAIL_ROWS]:
        t_ = float(s.get("total", 0) or 0)
        h_ = float(s.get("total_hpp", 0) or 0)
        rows.append([
            tgl_singkat(s.get("date") or s.get("created_at")),
            Paragraph(str(s.get("cashier_name", "-")), S_CELL),
            Paragraph(str(s.get("customer_name", "Umum")), S_CELL),
            PAYMENT_LABELS.get(s.get("payment_method"), s.get("payment_method", "-")),
            num(len(s.get("items") or [])),
            rp(t_), rp(h_), rp(t_ - h_), pct((t_ - h_) / t_ * 100 if t_ else 0),
        ])
    widths = [W * 0.09, W * 0.13, W * 0.16, W * 0.09, W * 0.05,
              W * 0.12, W * 0.12, W * 0.12, W * 0.12]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(_table_style(9, money_from=3))
    out.append(t)

    if len(sales) > MAX_DETAIL_ROWS:
        out.append(Paragraph(
            f"Ditampilkan {MAX_DETAIL_ROWS} transaksi terbaru dari {len(sales)} transaksi pada periode ini. "
            "Gunakan Export CSV untuk data lengkap.", S_SMALL))
    return out


def sales_pdf(data, store, start=None, end=None, printed_by=""):
    """Laporan penjualan: ringkasan -> rekap metode/kasir -> rincian transaksi."""
    W = 267 * mm  # landscape A4 minus margins
    sales = data.get("sales") or []
    story = _kop(store, "Laporan Penjualan", start, end, printed_by, W)
    story.append(_sales_summary_table(data, sales, W))
    story.append(_sales_recap_grid(data, W))
    story += _sales_detail(sales, W)
    story += _signature(printed_by, W)
    return _build(story, store, "Laporan Penjualan", orientation="landscape")


# ------------------------- 3. Nilai Stok -------------------------
def stock_pdf(data, store, printed_by=""):
    W = 180 * mm
    hari_ini = datetime.now(JKT).strftime("%Y-%m-%d")
    story = _kop(store, "Laporan Nilai Stok", hari_ini, hari_ini, printed_by, W)
    story.append(Paragraph(
        f"Posisi stok per {tgl(hari_ini)} (diambil langsung dari data stok terkini).", S_SMALL))
    story.append(Spacer(1, 6))

    items = data.get("items") or []
    has_pcs = any(float(i.get("stock_pcs", 0) or 0) for i in items)

    head = ["Produk", "Kategori", "Ekor", "Berat (kg)"]
    if has_pcs:
        head.append("Pcs")
    head += ["HPP/kg", "Nilai Stok (kg)"]
    rows = [head]
    for i in items:
        r = [Paragraph(str(i.get("name", "-")), S_CELL),
             Paragraph(str(i.get("category", "-")), S_CELL),
             num(i.get("stock_ekor")), num(i.get("stock_kg"), 2)]
        if has_pcs:
            r.append(num(i.get("stock_pcs")))
        r += [rp(i.get("hpp_kg")), rp(i.get("value"))]
        rows.append(r)

    total_kg = float(data.get("total_value", 0) or 0)
    foot = ["TOTAL", "", "", ""]
    if has_pcs:
        foot.append("")
    foot += ["", rp(total_kg)]
    rows.append(foot)

    if has_pcs:
        widths = [W * 0.26, W * 0.15, W * 0.09, W * 0.12, W * 0.09, W * 0.14, W * 0.15]
    else:
        widths = [W * 0.30, W * 0.17, W * 0.10, W * 0.13, W * 0.15, W * 0.15]
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = _table_style(len(head), money_from=2)
    st.add("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold")
    st.add("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.9, INK)
    t.setStyle(st)
    story.append(t)

    total_pcs_val = float(data.get("total_value_pcs", 0) or 0)
    if total_pcs_val:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Informasi tambahan: nilai stok satuan pcs (potongan/produk sampingan) "
            f"sebesar <b>{rp(total_pcs_val)}</b> belum termasuk dalam TOTAL di atas, "
            f"karena TOTAL dihitung dari berat (kg) agar tidak terjadi hitung ganda.", S_SMALL))

    story += _signature(printed_by, W)
    return _build(story, store, "Laporan Nilai Stok")


# ------------------------- 3b. Laba Rugi BULANAN (arsip pembukuan) -------------------------
def _m_pl_summary(data, W):
    omzet = float(data.get("omzet", 0) or 0)
    hpp = float(data.get("hpp", 0) or 0)
    gross = float(data.get("gross_profit", 0) or 0)
    opex = float(data.get("opex", 0) or 0)
    net = float(data.get("net_profit", 0) or 0)
    rows = [
        ["Uraian", "Nilai", "% dari Omzet"],
        ["Omzet Penjualan", rp(omzet), pct(100 if omzet else 0)],
        ["Harga Pokok Penjualan (HPP)", "(" + rp(hpp) + ")", pct(hpp / omzet * 100 if omzet else 0)],
        ["LABA KOTOR", rp(gross), pct(data.get("gross_margin", 0))],
        ["Beban Operasional", "(" + rp(opex) + ")", pct(opex / omzet * 100 if omzet else 0)],
        ["LABA BERSIH USAHA", rp(net), pct(data.get("net_margin", 0))],
    ]
    t = Table(rows, colWidths=[W * 0.5, W * 0.28, W * 0.22])
    st = _table_style(3)
    st.add("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold")
    st.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EEF3EF"))
    st.add("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold")
    st.add("FONTSIZE", (0, 5), (-1, 5), 9.5)
    st.add("BACKGROUND", (0, 5), (-1, 5),
           colors.HexColor("#EEF3EF") if net >= 0 else colors.HexColor("#FBEDEB"))
    st.add("TEXTCOLOR", (1, 5), (1, 5), POS if net >= 0 else NEG)
    st.add("LINEABOVE", (0, 3), (-1, 3), 0.9, INK)
    st.add("LINEABOVE", (0, 5), (-1, 5), 0.9, INK)
    t.setStyle(st)
    return t


def _m_compare(data, W):
    """Perbandingan dengan bulan sebelumnya — inti laporan bulanan untuk owner."""
    prev = data.get("prev") or {}
    g = data.get("growth") or {}
    plabel = prev.get("label") or "Bulan Lalu"

    def row(label, now_v, prev_v, growth_v=None):
        now_v, prev_v = float(now_v or 0), float(prev_v or 0)
        selisih = now_v - prev_v
        naik = "-" if growth_v is None else f"{'+' if growth_v >= 0 else ''}{num(growth_v, 1)}%"
        return [label, rp(now_v), rp(prev_v), ("+" if selisih >= 0 else "-") + rp(abs(selisih)), naik]

    rows = [["Uraian", data.get("label", "Bulan Ini"), plabel, "Selisih", "Naik/Turun"],
            row("Omzet", data.get("omzet"), prev.get("omzet"), g.get("omzet")),
            row("Laba Kotor", data.get("gross_profit"), prev.get("gross_profit")),
            row("Beban Operasional", data.get("opex"), prev.get("opex")),
            row("Laba Bersih Usaha", data.get("net_profit"), prev.get("net_profit"), g.get("net_profit")),
            ["Jumlah Transaksi", num(data.get("txn_count")), num(prev.get("txn_count")),
             num(float(data.get("txn_count") or 0) - float(prev.get("txn_count") or 0)), "-"]]
    t = Table(rows, colWidths=[W * 0.24, W * 0.2, W * 0.2, W * 0.2, W * 0.16], repeatRows=1)
    st = _table_style(5)
    st.add("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold")
    st.add("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#EEF3EF"))
    t.setStyle(st)
    return t


def _m_daily(data, W):
    daily = data.get("daily") or []
    out = [Paragraph("Rincian Harian", S_SEC)]
    if not daily:
        out.append(Paragraph("Tidak ada aktivitas pada bulan ini.", S_SMALL))
        return out
    rows = [["Tanggal", "Trx", "Berat (kg)", "Ekor", "Omzet", "HPP", "Laba Kotor",
             "Beban", "Laba Bersih"]]
    for d in daily:
        rows.append([tgl_singkat(d.get("date")), num(d.get("txn_count")),
                     num(d.get("weight"), 2), num(d.get("ekor")),
                     rp(d.get("omzet")), rp(d.get("hpp")), rp(d.get("gross_profit")),
                     rp(d.get("opex")), rp(d.get("net_profit"))])
    rows.append(["TOTAL BULAN", num(data.get("txn_count")), num(data.get("weight"), 2),
                 num(data.get("ekor")), rp(data.get("omzet")), rp(data.get("hpp")),
                 rp(data.get("gross_profit")), rp(data.get("opex")), rp(data.get("net_profit"))])
    widths = [W * 0.1, W * 0.05, W * 0.09, W * 0.06, W * 0.14, W * 0.13, W * 0.14,
              W * 0.13, W * 0.16]
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = _table_style(9, money_from=1)
    last = len(rows) - 1
    st.add("FONTNAME", (0, last), (-1, last), "Helvetica-Bold")
    st.add("BACKGROUND", (0, last), (-1, last), colors.HexColor("#EEF3EF"))
    st.add("LINEABOVE", (0, last), (-1, last), 0.9, INK)
    t.setStyle(st)
    out.append(t)
    return out


def _m_expenses(data, W):
    exps = data.get("expenses_by_category") or []
    half = (W - 6 * mm) / 2
    left = [Paragraph("Rincian Beban per Kategori", S_SEC)]
    if exps:
        rows = [["Kategori", "Jumlah"]]
        for e in exps:
            rows.append([Paragraph(str(e.get("category", "-")), S_CELL), rp(e.get("amount"))])
        rows.append(["TOTAL (termasuk pembelian & bayar hutang)", rp(data.get("expense_total"))])
        t = Table(rows, colWidths=[half * 0.62, half * 0.38], repeatRows=1)
        st = _table_style(2)
        st.add("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold")
        st.add("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.9, INK)
        t.setStyle(st)
        left.append(t)
    else:
        left.append(Paragraph("Tidak ada beban tercatat pada bulan ini.", S_SMALL))

    right = [Paragraph("Arus Kas Bulan Ini", S_SEC)]
    krows = [["Uraian", "Nilai"],
             ["Uang Masuk", rp(data.get("cash_in"))],
             ["Uang Keluar (termasuk beli ayam)", "(" + rp(data.get("cash_out")) + ")"],
             ["UANG BERSIH (KAS)", rp(data.get("net_cash"))],
             ["Modal ayam bulan ini", rp(data.get("modal_value"))],
             ["Piutang baru bulan ini", rp(data.get("piutang_baru"))]]
    kt = Table(krows, colWidths=[half * 0.62, half * 0.38])
    kst = _table_style(2)
    kst.add("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold")
    kst.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EEF3EF"))
    kst.add("LINEABOVE", (0, 3), (-1, 3), 0.9, INK)
    kt.setStyle(kst)
    right.append(kt)

    grid = Table([[left, right]], colWidths=[half + 3 * mm, half + 3 * mm])
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (0, 0), 0),
                              ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))
    return grid


def _m_products(data, W):
    prods = (data.get("products") or [])[:15]
    out = [Paragraph("Performa Produk (15 teratas)", S_SEC)]
    if not prods:
        out.append(Paragraph("Belum ada penjualan produk pada bulan ini.", S_SMALL))
        return out
    rows = [["Produk", "Kg", "Ekor", "Pcs", "Omzet", "HPP", "Laba", "Margin"]]
    for p in prods:
        om = float(p.get("omzet", 0) or 0)
        rows.append([Paragraph(str(p.get("name", "-")), S_CELL), num(p.get("kg"), 2),
                     num(p.get("ekor")), num(p.get("pcs")), rp(om), rp(p.get("hpp")),
                     rp(p.get("laba")), pct(float(p.get("laba", 0) or 0) / om * 100 if om else 0)])
    widths = [W * 0.24, W * 0.08, W * 0.07, W * 0.07, W * 0.15, W * 0.13, W * 0.13, W * 0.13]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(_table_style(8, money_from=1))
    out.append(t)
    return out


def monthly_pl_pdf(data, store, printed_by=""):
    """Laporan laba rugi SATU bulan penuh, siap dicetak & diarsipkan owner."""
    W = 267 * mm  # landscape A4 minus margins
    start, end = data.get("start"), data.get("end")
    story = _kop(store, "Laporan Laba Rugi Bulanan", start, end, printed_by, W)
    story.append(Paragraph(
        f"Bulan <b>{data.get('label', '-')}</b> · {int(data.get('active_days') or 0)} hari ada transaksi · "
        f"rata-rata omzet {rp(data.get('avg_omzet_per_day'))}/hari aktif · "
        f"{num(data.get('txn_count'))} transaksi · {num(data.get('weight'), 2)} kg · "
        f"{num(data.get('ekor'))} ekor.", S_SMALL))
    story.append(Spacer(1, 6))

    half = (W - 6 * mm) / 2
    ringkas = [Paragraph("Ringkasan Laba Rugi", S_SEC), _m_pl_summary(data, half)]
    banding = [Paragraph("Perbandingan Bulan Sebelumnya", S_SEC), _m_compare(data, half)]
    top = Table([[ringkas, banding]], colWidths=[half + 3 * mm, half + 3 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (0, 0), 0),
                             ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))
    story.append(top)

    story += _m_daily(data, W)
    story.append(_m_expenses(data, W))
    story += _m_products(data, W)
    story.append(Paragraph(
        "Catatan: Laba Kotor = Omzet − HPP; Laba Bersih Usaha = Laba Kotor − Beban Operasional. "
        "\"Pembelian Ayam\" dan \"Pembayaran Hutang\" tidak dihitung sebagai beban usaha karena "
        "sudah termasuk di HPP/modal — keduanya hanya muncul di Arus Kas. Angka pada laporan ini "
        "memakai rumus yang sama dengan Dashboard dan Tutup Buku Harian.", S_SMALL))
    story += _signature(printed_by, W)
    return _build(story, store, f"Laporan Laba Rugi Bulanan {data.get('label', '')}",
                  orientation="landscape")


# ------------------------- 4. Tutup Buku Harian -------------------------
def _dc_intro(data, d):
    """Kalimat pembuka: siapa yang menutup buku dan kapan."""
    info = f"Rekap penuh transaksi tanggal {tgl(d)}."
    if data.get("closed_at"):
        info += f" Ditutup oleh {data.get('closed_by') or '-'} pada {tgl(data['closed_at'])}"
        info += f" (versi {data.get('version', 1)})."
    return [Paragraph(info, S_SMALL), Spacer(1, 6)]


def _f(v) -> float:
    """Ambil nilai uang/angka dari dict laporan dengan aman."""
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _share(part, omzet) -> str:
    """Porsi sebuah angka terhadap omzet, dalam persen."""
    return pct(_f(part) / omzet * 100 if omzet else 0)


def _dc_profit_rows(data, omzet, hpp, opex, net):
    return [
        ["Uraian", "Nilai", "% dari Omzet"],
        [f"Omzet Penjualan ({int(_f(data.get('txn_count')))} transaksi)", rp(omzet), pct(100 if omzet else 0)],
        ["Harga Pokok Penjualan (HPP)", "(" + rp(hpp) + ")", _share(hpp, omzet)],
        ["LABA KOTOR", rp(data.get("gross_profit")), pct(data.get("margin", 0))],
        ["Beban Operasional", "(" + rp(opex) + ")", _share(opex, omzet)],
        ["LABA BERSIH", rp(net), _share(net, omzet)],
    ]


def _dc_profit_style(net):
    st = _table_style(3)
    for r in (3, 5):
        st.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
        st.add("LINEABOVE", (0, r), (-1, r), 0.9, INK)
    untung = net >= 0
    st.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EEF3EF"))
    st.add("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#EEF3EF") if untung else colors.HexColor("#FBEDEB"))
    st.add("TEXTCOLOR", (1, 5), (1, 5), POS if untung else NEG)
    st.add("FONTSIZE", (0, 5), (-1, 5), 9.5)
    return st


def _dc_profit(data, W):
    """A. Ringkasan laba: omzet -> HPP -> laba kotor -> beban -> laba bersih."""
    omzet, hpp = _f(data.get("omzet")), _f(data.get("hpp"))
    opex, net = _f(data.get("opex")), _f(data.get("net_profit"))
    t = Table(_dc_profit_rows(data, omzet, hpp, opex, net),
              colWidths=[W * 0.52, W * 0.26, W * 0.22])
    t.setStyle(_dc_profit_style(net))
    return [Paragraph("A. Ringkasan Laba", S_SEC), t]


def _dc_volume(data, W):
    """B. Volume terjual & uang masuk (dua kolom berpasangan)."""
    rows = [
        ["Keterangan", "Jumlah", "Keterangan", "Jumlah"],
        ["Berat terjual", num(data.get("weight"), 2) + " kg",
         "Kas dari penjualan", rp(data.get("kas_dari_penjualan"))],
        ["Ayam terjual", num(data.get("ekor")) + " ekor",
         "Pembayaran piutang masuk", rp(data.get("bayar_piutang_masuk"))],
        ["Potongan terjual", num(data.get("pcs")) + " pcs",
         "TOTAL UANG MASUK", rp(data.get("kas_masuk_total"))],
        ["Transaksi dibatalkan", num(data.get("cancelled_count")) + " transaksi",
         "Piutang baru hari ini", rp(data.get("piutang_baru"))],
        ["Diskon diberikan", rp(data.get("diskon")),
         "Total pengeluaran tercatat", rp(data.get("expense_total"))],
    ]
    t = Table(rows, colWidths=[W * 0.27, W * 0.23, W * 0.29, W * 0.21])
    st = _table_style(4)
    st.add("ALIGN", (0, 0), (0, -1), "LEFT")
    st.add("ALIGN", (2, 0), (2, -1), "LEFT")
    st.add("FONTNAME", (2, 3), (3, 3), "Helvetica-Bold")
    t.setStyle(st)
    return [Paragraph("B. Volume Terjual & Uang Masuk", S_SEC), t]


def _dc_debt_methods(data, W):
    """Pelunasan piutang & hutang per metode bayar (tunai/transfer/QRIS/dll)."""
    rec = data.get("piutang_by_method") or []
    pay = data.get("hutang_by_method") or []
    if not rec and not pay:
        return []
    rows = [["Jenis", "Metode", "Jumlah", "Nilai"]]
    for m in rec:
        rows.append(["Piutang masuk", PAYMENT_LABELS.get(m.get("method"), m.get("method", "-")),
                     num(m.get("count")) + "x", rp(m.get("amount"))])
    for m in pay:
        rows.append(["Hutang dibayar", PAYMENT_LABELS.get(m.get("method"), m.get("method", "-")),
                     num(m.get("count")) + "x", rp(m.get("amount"))])
    t = Table(rows, colWidths=[W * 0.28, W * 0.24, W * 0.16, W * 0.32])
    t.setStyle(_table_style(4))
    return [Spacer(1, 5 * mm),
            Paragraph("C2. Pelunasan Piutang & Hutang per Metode Bayar", S_SEC), t]


def _dc_methods(data, W):
    """C. Rincian per metode pembayaran (dilewati bila tidak ada transaksi)."""
    methods = data.get("by_method") or []
    if not methods:
        return _dc_debt_methods(data, W)
    rows = [["Metode", "Transaksi", "Nilai Penjualan", "Uang Diterima"]]
    for m in methods:
        rows.append([PAYMENT_LABELS.get(m.get("method"), m.get("method", "-")),
                     num(m.get("count")), rp(m.get("total")), rp(m.get("kas"))])
    rows.append(["TOTAL", num(sum(_f(m.get("count")) for m in methods)),
                 rp(sum(_f(m.get("total")) for m in methods)),
                 rp(sum(_f(m.get("kas")) for m in methods))])
    t = Table(rows, colWidths=[W * 0.28, W * 0.16, W * 0.28, W * 0.28])
    st = _table_style(4)
    st.add("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold")
    st.add("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.9, INK)
    t.setStyle(st)
    return ([Paragraph("C. Rincian per Metode Pembayaran", S_SEC), t]
            + _dc_debt_methods(data, W))


def _dc_products(data, W):
    """D. Produk terjual hari ini (dilewati bila kosong)."""
    tops = data.get("top_products") or []
    if not tops:
        return []
    rows = [["Produk", "Kg", "Ekor", "Pcs", "Penjualan", "HPP", "Laba"]]
    for p in tops:
        rows.append([Paragraph(str(p.get("name", "-")), S_CELL), num(p.get("qty_kg"), 2),
                     num(p.get("qty_ekor")), num(p.get("qty_pcs")),
                     rp(p.get("penjualan")), rp(p.get("hpp")), rp(p.get("laba"))])
    t = Table(rows, colWidths=[W * 0.24, W * 0.09, W * 0.09, W * 0.08,
                               W * 0.17, W * 0.16, W * 0.17], repeatRows=1)
    t.setStyle(_table_style(7))
    return [Paragraph("D. Produk Terjual Hari Ini", S_SEC), t]


def _dc_purchase(data, W):
    """E. Pembelian ayam & beban per kategori."""
    pur = data.get("purchase") or {}
    rows = [["Uraian", "Nilai"],
            [f"Pembelian ayam ({int(pur.get('count', 0) or 0)} nota, "
             f"{num(pur.get('weight'), 2)} kg / {num(pur.get('ekor'))} ekor)", rp(pur.get("total_modal"))],
            ["Hutang supplier baru hari ini", rp(pur.get("hutang_baru"))]]
    for e in (data.get("expenses_by_category") or []):
        rows.append([f"Beban: {e.get('category', '-')}", rp(e.get("amount"))])
    t = Table(rows, colWidths=[W * 0.7, W * 0.3])
    t.setStyle(_table_style(2))
    return [Paragraph("E. Pembelian & Beban", S_SEC), t]


def _dc_stock(data, W):
    """F. Stok sisa akhir hari (dilewati bila tidak ada produk)."""
    items = data.get("stock_items") or []
    if not items:
        return []
    rows = [["Produk", "Ekor", "Berat (kg)", "Pcs", "Berat/ekor", "HPP/kg", "Nilai"]]
    for i in items:
        rows.append([Paragraph(str(i.get("name", "-")), S_CELL), num(i.get("stock_ekor")),
                     num(i.get("stock_kg"), 2), num(i.get("stock_pcs")),
                     num(i.get("avg_weight"), 2) + " kg", rp(i.get("hpp_kg")), rp(i.get("value"))])
    rows.append(["TOTAL NILAI STOK", "", "", "", "", "", rp(data.get("stock_value"))])
    t = Table(rows, colWidths=[W * 0.24, W * 0.09, W * 0.13, W * 0.09,
                               W * 0.14, W * 0.14, W * 0.17], repeatRows=1)
    st = _table_style(7)
    st.add("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold")
    st.add("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.9, INK)
    t.setStyle(st)
    return [Paragraph("F. Stok Sisa Akhir Hari", S_SEC), t]


def _dc_debts(data, W):
    """G. Posisi piutang & hutang kumulatif."""
    rows = [["Uraian", "Nilai"],
            ["Total piutang pelanggan belum lunas", rp(data.get("receivable_outstanding"))],
            ["Total hutang ke supplier belum lunas", rp(data.get("payable_outstanding"))]]
    t = Table(rows, colWidths=[W * 0.7, W * 0.3])
    t.setStyle(_table_style(2))
    return [Paragraph("G. Posisi Piutang & Hutang (kumulatif)", S_SEC), t]


def _dc_notes(data):
    """Catatan owner (bila ada) + catatan metode perhitungan."""
    out = []
    if data.get("notes"):
        out.append(Paragraph("Catatan Owner", S_SEC))
        out.append(Paragraph(str(data["notes"]), S_CELL))
    out.append(Paragraph(
        "Catatan: Nilai stok dihitung dari berat (kg) + satuan pcs. Stok ekor tidak "
        "dinilai terpisah karena menunjuk ayam yang sama dengan stok kg. "
        "Beban Operasional tidak memasukkan \"Pembelian Ayam\" dan \"Pembayaran Hutang\".", S_SMALL))
    return out


# Bagian A-G tutup buku, dirakit berurutan. Menambah bagian baru = tambah 1 fungsi di sini.
_DC_SECTIONS = (_dc_profit, _dc_volume, _dc_methods, _dc_products,
                _dc_purchase, _dc_stock, _dc_debts)


def daily_closing_pdf(data, store, printed_by=""):
    """Rekap tutup buku satu hari: uang masuk, laba, stok sisa, piutang & hutang."""
    W = 180 * mm
    d = data.get("date") or datetime.now(JKT).strftime("%Y-%m-%d")
    story = _kop(store, "Rekap Tutup Buku Harian", d, d, printed_by, W)
    story += _dc_intro(data, d)
    for section in _DC_SECTIONS:
        story += section(data, W)
    story += _dc_notes(data)
    story += _signature(printed_by, W)
    return _build(story, store, f"Tutup Buku {d}")
