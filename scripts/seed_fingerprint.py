"""Cap jempol hasil seed_demo, untuk membuktikan refactor tidak mengubah data demo.

seed_demo memakai random.seed(42) sehingga hasilnya deterministik. Skrip ini
menyemai database SEMENTARA (bukan database produksi), lalu mencetak ringkasan
yang stabil: jumlah dokumen per koleksi + nilai-nilai numerik yang diurutkan.
Field yang wajar berbeda (id acak, jam pembuatan) sengaja diabaikan.

Pakai: python /app/scripts/seed_fingerprint.py <file_keluaran.json>
"""

import asyncio
import hashlib
import json
import sys

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from seed import seed_demo  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/seed_after.json"
SCRATCH_DB = "seed_fingerprint_scratch"
SKIP_FIELDS = {"_id", "id", "created_at", "closed_at", "product_id", "customer_id",
               "supplier_id", "sale_id", "purchase_id", "ref", "created_by"}


def digest(docs):
    """Ringkas daftar dokumen jadi satu sidik jari yang tidak bergantung urutan/id."""
    rows = []
    for d in docs:
        flat = []
        for k in sorted(d.keys()):
            if k in SKIP_FIELDS:
                continue
            v = d[k]
            if isinstance(v, (int, float)):
                flat.append(f"{k}={round(float(v), 4)}")
            elif isinstance(v, str):
                flat.append(f"{k}={v}")
            elif isinstance(v, list):
                flat.append(f"{k}=[{len(v)}]")
        rows.append("|".join(flat))
    rows.sort()
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]


async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await client.drop_database(SCRATCH_DB)
    db = client[SCRATCH_DB]
    await seed_demo(db)

    out = {}
    for name in sorted(await db.list_collection_names()):
        docs = await db[name].find().to_list(100000)
        totals = {}
        for field in ("total", "total_hpp", "amount", "total_modal", "stock_kg", "stock_ekor",
                      "price_kg", "hpp_kg", "remaining", "paid"):
            vals = [float(d[field]) for d in docs if isinstance(d.get(field), (int, float))]
            if vals:
                totals[field] = round(sum(vals), 2)
        out[name] = {"count": len(docs), "sums": totals, "digest": digest(docs)}

    await client.drop_database(SCRATCH_DB)
    client.close()
    open(OUT, "w").write(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
