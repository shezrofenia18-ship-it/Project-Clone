"""Alat bantu verifikasi refactor PDF.

Menghasilkan 4 laporan PDF lalu mengekstrak teksnya, supaya keluaran SEBELUM dan
SESUDAH refactor bisa dibandingkan baris-per-baris (bukan asal "masih 200 OK").

Pakai: python /app/scripts/pdf_fingerprint.py <folder_tujuan>
"""

import json
import os
import sys

sys.path.insert(0, "/app/backend")

import requests  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import pdf_reports  # noqa: E402

API = "http://localhost:8001/api"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pdf_after"
START, END = "2026-08-20", "2026-08-29"


def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "shezrofenia18@gmail.com", "password": "berkahayam1"})
    return r.json()["token"]


def text_of(path):
    reader = PdfReader(path)
    pages = [p.extract_text() or "" for p in reader.pages]
    return len(reader.pages), "\n".join(pages)


def main():
    os.makedirs(OUT, exist_ok=True)
    h = {"Authorization": "Bearer " + token()}
    store = {"store_name": "Berkah Ayam Mili", "store_address": "Jl. Raya Pasar No. 12, Blitar",
             "store_phone": "081289478221"}

    # 1-3: lewat API (jalur nyata yang dipakai owner)
    for name, url in (("profit_loss", f"/reports/profit-loss/pdf?start={START}&end={END}"),
                      ("sales", f"/reports/sales/pdf?start={START}&end={END}"),
                      ("stock", "/reports/stock/pdf")):
        r = requests.get(API + url, headers=h)
        assert r.status_code == 200 and r.content[:5] == b"%PDF-", (name, r.status_code)
        open(f"{OUT}/{name}.pdf", "wb").write(r.content)

    # 4: tutup buku belum ada datanya -> panggil fungsinya langsung dengan snapshot pratinjau
    snap = requests.get(f"{API}/daily-closing/preview?date={END}", headers=h).json()
    snap = snap.get("snapshot", snap)
    snap.setdefault("notes", "Catatan uji refactor")
    pdf = pdf_reports.daily_closing_pdf(snap, store, printed_by="Tes Refactor")
    open(f"{OUT}/closing.pdf", "wb").write(pdf)

    summary = {}
    for name in ("profit_loss", "sales", "stock", "closing"):
        pages, txt = text_of(f"{OUT}/{name}.pdf")
        open(f"{OUT}/{name}.txt", "w").write(txt)
        summary[name] = {"pages": pages, "chars": len(txt), "lines": txt.count("\n") + 1}
    open(f"{OUT}/summary.json", "w").write(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
