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
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        return "Rp 0"
    return "Rp " + f"{v:,}".replace(",", ".")


def num(n, digits=0) -> str:
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
    try:
        d = datetime.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return str(iso)
    if not 1 <= d.month <= 12:
        return str(iso)
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def tgl_singkat(iso: str) -> str:
    if not iso:
        return "-"
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
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


def sales_pdf(data, store, start=None, end=None, printed_by=""):
    W = 267 * mm  # landscape A4 minus margins
    story = _kop(store, "Laporan Penjualan", start, end, printed_by, W)

    sales = data.get("sales") or []
    total = float(data.get("total", 0) or 0)
    count = int(data.get("count", 0) or 0)
    total_hpp = sum(float(s.get("total_hpp", 0) or 0) for s in sales)
    laba = total - total_hpp if sales else 0
    rata = total / count if count else 0

    srows = [["Jumlah Transaksi", "Total Penjualan", "Rata-rata / Transaksi", "Estimasi Laba Kotor"],
             [num(count), rp(total), rp(rata), rp(laba)]]
    stt = Table(srows, colWidths=[W * 0.25] * 4)
    sst = _table_style(4, money_from=0)
    sst.add("ALIGN", (0, 0), (-1, -1), "CENTER")
    sst.add("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold")
    sst.add("FONTSIZE", (0, 1), (-1, 1), 10)
    stt.setStyle(sst)
    story.append(stt)

    half = (W - 6 * mm) / 2
    by_method = data.get("by_method") or []
    by_cashier = data.get("by_cashier") or []

    def mini(title, rows, key):
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

    m_left = mini("Rekap per Metode Pembayaran", by_method, "method")
    m_right = mini("Rekap per Kasir", by_cashier, "cashier")
    grid = Table([[m_left, m_right]], colWidths=[half + 3 * mm, half + 3 * mm])
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (0, 0), 0),
                              ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))
    story.append(grid)

    story.append(Paragraph("Rincian Transaksi", S_SEC))
    if sales:
        head = ["Tanggal", "Kasir", "Pelanggan", "Metode", "Item", "Total", "HPP", "Laba", "Margin"]
        rows = [head]
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
        story.append(t)
        if len(sales) > MAX_DETAIL_ROWS:
            story.append(Paragraph(
                f"Ditampilkan {MAX_DETAIL_ROWS} transaksi terbaru dari {len(sales)} transaksi pada periode ini. "
                "Gunakan Export CSV untuk data lengkap.", S_SMALL))
    else:
        story.append(Paragraph("Tidak ada transaksi pada periode ini.", S_SMALL))

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


# ------------------------- 4. Tutup Buku Harian -------------------------
def daily_closing_pdf(data, store, printed_by=""):
    """Rekap tutup buku satu hari: uang masuk, laba, stok sisa, piutang & hutang."""
    W = 180 * mm
    d = data.get("date") or datetime.now(JKT).strftime("%Y-%m-%d")
    story = _kop(store, "Rekap Tutup Buku Harian", d, d, printed_by, W)

    closed_at = data.get("closed_at")
    info = f"Rekap penuh transaksi tanggal {tgl(d)}."
    if closed_at:
        info += f" Ditutup oleh {data.get('closed_by') or '-'} pada {tgl(closed_at)}"
        info += f" (versi {data.get('version', 1)})."
    story.append(Paragraph(info, S_SMALL))
    story.append(Spacer(1, 6))

    omzet = float(data.get("omzet", 0) or 0)
    hpp = float(data.get("hpp", 0) or 0)
    gross = float(data.get("gross_profit", 0) or 0)
    opex = float(data.get("opex", 0) or 0)
    net = float(data.get("net_profit", 0) or 0)

    # --- Ringkasan laba ---
    story.append(Paragraph("A. Ringkasan Laba", S_SEC))
    rows = [
        ["Uraian", "Nilai", "% dari Omzet"],
        [f"Omzet Penjualan ({int(data.get('txn_count', 0) or 0)} transaksi)", rp(omzet), pct(100 if omzet else 0)],
        ["Harga Pokok Penjualan (HPP)", "(" + rp(hpp) + ")", pct(hpp / omzet * 100 if omzet else 0)],
        ["LABA KOTOR", rp(gross), pct(data.get("margin", 0))],
        ["Beban Operasional", "(" + rp(opex) + ")", pct(opex / omzet * 100 if omzet else 0)],
        ["LABA BERSIH", rp(net), pct(net / omzet * 100 if omzet else 0)],
    ]
    t = Table(rows, colWidths=[W * 0.52, W * 0.26, W * 0.22])
    st = _table_style(3)
    for r in (3, 5):
        st.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
        st.add("LINEABOVE", (0, r), (-1, r), 0.9, INK)
    st.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EEF3EF"))
    st.add("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#EEF3EF") if net >= 0 else colors.HexColor("#FBEDEB"))
    st.add("TEXTCOLOR", (1, 5), (1, 5), POS if net >= 0 else NEG)
    st.add("FONTSIZE", (0, 5), (-1, 5), 9.5)
    t.setStyle(st)
    story.append(t)

    # --- Volume & kas ---
    story.append(Paragraph("B. Volume Terjual & Uang Masuk", S_SEC))
    vol = [
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
    vt = Table(vol, colWidths=[W * 0.27, W * 0.23, W * 0.29, W * 0.21])
    vst = _table_style(4)
    vst.add("ALIGN", (0, 0), (0, -1), "LEFT")
    vst.add("ALIGN", (2, 0), (2, -1), "LEFT")
    vst.add("FONTNAME", (2, 3), (3, 3), "Helvetica-Bold")
    vt.setStyle(vst)
    story.append(vt)

    # --- Kas per metode bayar ---
    methods = data.get("by_method") or []
    if methods:
        story.append(Paragraph("C. Rincian per Metode Pembayaran", S_SEC))
        mrows = [["Metode", "Transaksi", "Nilai Penjualan", "Uang Diterima"]]
        for m in methods:
            mrows.append([PAYMENT_LABELS.get(m.get("method"), m.get("method", "-")),
                          num(m.get("count")), rp(m.get("total")), rp(m.get("kas"))])
        mrows.append(["TOTAL", num(sum(int(m.get("count", 0) or 0) for m in methods)),
                      rp(sum(float(m.get("total", 0) or 0) for m in methods)),
                      rp(sum(float(m.get("kas", 0) or 0) for m in methods))])
        mt = Table(mrows, colWidths=[W * 0.28, W * 0.16, W * 0.28, W * 0.28])
        mst = _table_style(4)
        mst.add("FONTNAME", (0, len(mrows) - 1), (-1, len(mrows) - 1), "Helvetica-Bold")
        mst.add("LINEABOVE", (0, len(mrows) - 1), (-1, len(mrows) - 1), 0.9, INK)
        mt.setStyle(mst)
        story.append(mt)

    # --- Produk terlaris ---
    tops = data.get("top_products") or []
    if tops:
        story.append(Paragraph("D. Produk Terjual Hari Ini", S_SEC))
        prows = [["Produk", "Kg", "Ekor", "Pcs", "Penjualan", "HPP", "Laba"]]
        for p in tops:
            prows.append([Paragraph(str(p.get("name", "-")), S_CELL), num(p.get("qty_kg"), 2),
                          num(p.get("qty_ekor")), num(p.get("qty_pcs")),
                          rp(p.get("penjualan")), rp(p.get("hpp")), rp(p.get("laba"))])
        pt = Table(prows, colWidths=[W * 0.24, W * 0.09, W * 0.09, W * 0.08,
                                     W * 0.17, W * 0.16, W * 0.17], repeatRows=1)
        pt.setStyle(_table_style(7))
        story.append(pt)

    # --- Pembelian & beban ---
    pur = data.get("purchase") or {}
    story.append(Paragraph("E. Pembelian & Beban", S_SEC))
    erows = [["Uraian", "Nilai"],
             [f"Pembelian ayam ({int(pur.get('count', 0) or 0)} nota, "
              f"{num(pur.get('weight'), 2)} kg / {num(pur.get('ekor'))} ekor)", rp(pur.get("total_modal"))],
             ["Hutang supplier baru hari ini", rp(pur.get("hutang_baru"))]]
    for e in (data.get("expenses_by_category") or []):
        erows.append([f"Beban: {e.get('category', '-')}", rp(e.get("amount"))])
    et = Table(erows, colWidths=[W * 0.7, W * 0.3])
    et.setStyle(_table_style(2))
    story.append(et)

    # --- Stok sisa ---
    items = data.get("stock_items") or []
    if items:
        story.append(Paragraph("F. Stok Sisa Akhir Hari", S_SEC))
        srows = [["Produk", "Ekor", "Berat (kg)", "Pcs", "Berat/ekor", "HPP/kg", "Nilai"]]
        for i in items:
            srows.append([Paragraph(str(i.get("name", "-")), S_CELL), num(i.get("stock_ekor")),
                          num(i.get("stock_kg"), 2), num(i.get("stock_pcs")),
                          num(i.get("avg_weight"), 2) + " kg", rp(i.get("hpp_kg")), rp(i.get("value"))])
        srows.append(["TOTAL NILAI STOK", "", "", "", "", "", rp(data.get("stock_value"))])
        stt = Table(srows, colWidths=[W * 0.24, W * 0.09, W * 0.13, W * 0.09,
                                      W * 0.14, W * 0.14, W * 0.17], repeatRows=1)
        sst = _table_style(7)
        sst.add("FONTNAME", (0, len(srows) - 1), (-1, len(srows) - 1), "Helvetica-Bold")
        sst.add("LINEABOVE", (0, len(srows) - 1), (-1, len(srows) - 1), 0.9, INK)
        stt.setStyle(sst)
        story.append(stt)

    # --- Posisi piutang & hutang ---
    story.append(Paragraph("G. Posisi Piutang & Hutang (kumulatif)", S_SEC))
    prows2 = [["Uraian", "Nilai"],
              ["Total piutang pelanggan belum lunas", rp(data.get("receivable_outstanding"))],
              ["Total hutang ke supplier belum lunas", rp(data.get("payable_outstanding"))]]
    pt2 = Table(prows2, colWidths=[W * 0.7, W * 0.3])
    pt2.setStyle(_table_style(2))
    story.append(pt2)

    if data.get("notes"):
        story.append(Paragraph("Catatan Owner", S_SEC))
        story.append(Paragraph(str(data["notes"]), S_CELL))

    story.append(Paragraph(
        "Catatan: Nilai stok dihitung dari berat (kg) + satuan pcs. Stok ekor tidak "
        "dinilai terpisah karena menunjuk ayam yang sama dengan stok kg. "
        "Beban Operasional tidak memasukkan \"Pembelian Ayam\" dan \"Pembayaran Hutang\".", S_SMALL))
    story += _signature(printed_by, W)
    return _build(story, store, f"Tutup Buku {d}")
