"""Bandingkan hasil seed_demo versi LAMA vs BARU field-per-field.

Versi lama diambil dari salinan /tmp/seed.py.bak (ditaruh di /tmp/oldseed/seed.py),
versi baru dari /app/backend/seed.py. Keduanya menyemai database sementara yang
berbeda, lalu dokumennya dinormalkan (id & jam dibuang) dan dibandingkan.
"""

import asyncio
import importlib.util
import json
import sys

from motor.motor_asyncio import AsyncIOMotorClient

DROP = {"_id", "id", "created_at", "txn_id", "source_product_id", "product_id", "customer_id", "supplier_id", "sale_id",
        "purchase_id", "source_product_id", "ref", "txn_id"}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def norm(doc):
    out = {}
    for k, v in doc.items():
        if k in DROP:
            continue
        if isinstance(v, list):
            out[k] = [norm(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def key(doc):
    return json.dumps(norm(doc), sort_keys=True, default=str)


async def seed_into(mod, dbname):
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await client.drop_database(dbname)
    db = client[dbname]
    await mod.seed_demo(db)
    data = {}
    for name in await db.list_collection_names():
        data[name] = [norm(d) for d in await db[name].find().to_list(100000)]
    await client.drop_database(dbname)
    client.close()
    return data


async def main():
    old = load("/tmp/oldseed/seed.py", "seed_old")
    new = load("/app/backend/seed.py", "seed_new")
    a = await seed_into(old, "seed_cmp_old")
    b = await seed_into(new, "seed_cmp_new")

    for coll in sorted(set(a) | set(b)):
        rows_a = sorted(json.dumps(d, sort_keys=True, default=str) for d in a.get(coll, []))
        rows_b = sorted(json.dumps(d, sort_keys=True, default=str) for d in b.get(coll, []))
        if rows_a == rows_b:
            print(f"OK   {coll:14} {len(rows_a)} dokumen identik")
            continue
        print(f"BEDA {coll:14} {len(rows_a)} vs {len(rows_b)} dokumen")
        only_a = [r for r in rows_a if r not in rows_b]
        only_b = [r for r in rows_b if r not in rows_a]
        print(f"     hanya di LAMA: {len(only_a)} | hanya di BARU: {len(only_b)}")
        for ra, rb in list(zip(only_a, only_b))[:2]:
            da, dbb = json.loads(ra), json.loads(rb)
            diff = {k: (da.get(k), dbb.get(k)) for k in set(da) | set(dbb) if da.get(k) != dbb.get(k)}
            print("     contoh field beda:", json.dumps(diff, default=str)[:400])


if __name__ == "__main__":
    asyncio.run(main())
