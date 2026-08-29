"""Skrip sekali-jalan: pecah sales_pdf & daily_closing_pdf jadi fungsi per bagian.

Memakai ast untuk menemukan batas fungsi lama, jadi tidak bergantung pada nomor
baris yang mudah bergeser. Keluaran PDF harus TETAP SAMA (dibuktikan dengan
pdf_fingerprint.py sebelum/sesudah).
"""

import ast

PATH = "/app/backend/pdf_reports.py"

SALES_NEW = '''def _sales_summary_table(data, sales, W):
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
'''

CLOSING_NEW = '''def _dc_intro(data, d):
    """Kalimat pembuka: siapa yang menutup buku dan kapan."""
    info = f"Rekap penuh transaksi tanggal {tgl(d)}."
    if data.get("closed_at"):
        info += f" Ditutup oleh {data.get('closed_by') or '-'} pada {tgl(data['closed_at'])}"
        info += f" (versi {data.get('version', 1)})."
    return [Paragraph(info, S_SMALL), Spacer(1, 6)]


def _dc_profit(data, W):
    """A. Ringkasan laba: omzet -> HPP -> laba kotor -> beban -> laba bersih."""
    omzet = float(data.get("omzet", 0) or 0)
    hpp = float(data.get("hpp", 0) or 0)
    opex = float(data.get("opex", 0) or 0)
    net = float(data.get("net_profit", 0) or 0)
    rows = [
        ["Uraian", "Nilai", "% dari Omzet"],
        [f"Omzet Penjualan ({int(data.get('txn_count', 0) or 0)} transaksi)", rp(omzet), pct(100 if omzet else 0)],
        ["Harga Pokok Penjualan (HPP)", "(" + rp(hpp) + ")", pct(hpp / omzet * 100 if omzet else 0)],
        ["LABA KOTOR", rp(data.get("gross_profit")), pct(data.get("margin", 0))],
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


def _dc_methods(data, W):
    """C. Rincian per metode pembayaran (dilewati bila tidak ada transaksi)."""
    methods = data.get("by_method") or []
    if not methods:
        return []
    rows = [["Metode", "Transaksi", "Nilai Penjualan", "Uang Diterima"]]
    for m in methods:
        rows.append([PAYMENT_LABELS.get(m.get("method"), m.get("method", "-")),
                     num(m.get("count")), rp(m.get("total")), rp(m.get("kas"))])
    rows.append(["TOTAL", num(sum(int(m.get("count", 0) or 0) for m in methods)),
                 rp(sum(float(m.get("total", 0) or 0) for m in methods)),
                 rp(sum(float(m.get("kas", 0) or 0) for m in methods))])
    t = Table(rows, colWidths=[W * 0.28, W * 0.16, W * 0.28, W * 0.28])
    st = _table_style(4)
    st.add("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold")
    st.add("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.9, INK)
    t.setStyle(st)
    return [Paragraph("C. Rincian per Metode Pembayaran", S_SEC), t]


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
        "Beban Operasional tidak memasukkan \\"Pembelian Ayam\\" dan \\"Pembayaran Hutang\\".", S_SMALL))
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
'''


def replace_func(src: str, name: str, new_text: str) -> str:
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    lines = src.split("\n")
    start = node.lineno - 1
    end = node.end_lineno  # eksklusif
    return "\n".join(lines[:start] + new_text.rstrip("\n").split("\n") + lines[end:])


def main():
    src = open(PATH).read()
    src = replace_func(src, "sales_pdf", SALES_NEW)
    src = replace_func(src, "daily_closing_pdf", CLOSING_NEW)
    open(PATH, "w").write(src)
    print("pdf_reports.py diperbarui")


if __name__ == "__main__":
    main()
