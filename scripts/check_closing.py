"""Sanity check internal (bukan HTTP): snapshot tutup buku + render PDF."""
import asyncio
import sys

sys.path.insert(0, "/app/backend")
import server  # noqa: E402  (memuat .env)
import pdf_reports  # noqa: E402


async def main():
    d = server.today_str()
    snap = await server._closing_snapshot(d)
    print("date:", snap["date"], "omzet:", snap["omzet"], "hpp:", snap["hpp"],
          "gross:", snap["gross_profit"], "net:", snap["net_profit"])
    print("txn:", snap["txn_count"], "kas:", snap["kas_masuk_total"],
          "piutang_baru:", snap["piutang_baru"], "stock_value:", snap["stock_value"])
    print("methods:", snap["by_method"])
    print("stock_items:", len(snap["stock_items"]), "top:", len(snap["top_products"]))
    store = await server._store_info()
    pdf = pdf_reports.daily_closing_pdf({**snap, "closed_by": "Owner", "closed_at": server.iso_now(),
                                         "version": 1, "notes": "uji coba"}, store, "Owner")
    print("PDF bytes:", len(pdf), "header:", pdf[:5])
    # produk: cek berat rata-rata
    prods = await server.db.products.find({}).to_list(50)
    for p in prods[:4]:
        print(" -", p["name"], "hpp_kg", p.get("hpp_kg"), "avg", p.get("avg_weight_used"),
              "hpp_ekor", p.get("hpp_ekor"))


asyncio.run(main())
