"""Uji simulasi production: jalankan startup() terhadap DB uji terpisah dengan
RAILWAY_ENVIRONMENT diset, lalu pastikan TIDAK ADA seed yang terjadi."""
import asyncio, os, sys, importlib

os.environ["DB_NAME"] = "prodguard_test_db"
os.environ["RAILWAY_ENVIRONMENT"] = "production"
os.environ["ADMIN_USERNAME"] = "owner"
os.environ["ADMIN_PASSWORD"] = "admin123"
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo["prodguard_test_db"]
    await mongo.drop_database("prodguard_test_db")

    import env_guard
    assert env_guard.is_production(), "env_guard harus mendeteksi production"
    print("[1] deteksi production:", env_guard.production_reason())

    import server
    from auth import hash_password, verify_password

    # --- Skenario A: DB kosong (deploy pertama) ---
    await server.startup()
    n_prod = await db.products.count_documents({})
    n_cust = await db.customers.count_documents({})
    n_sales = await db.sales.count_documents({})
    seeded = await db.settings.find_one({"key": "seeded"})
    users = [u["username"] for u in await db.users.find({}, {"username": 1}).to_list(100)]
    print(f"[A] DB kosong -> produk={n_prod} pelanggan={n_cust} penjualan={n_sales} seeded_flag={seeded is not None} users={users}")
    assert n_prod == 0 and n_cust == 0 and n_sales == 0 and seeded is None, "SEED DEMO BOCOR di production!"
    assert users == ["owner"], "Hanya owner bootstrap yang boleh ada, tanpa akun demo"

    # --- Skenario B: owner ganti password & hapus produk, lalu restart ---
    await db.users.update_one({"username": "owner"}, {"$set": {"password_hash": hash_password("RahasiaBaru!")}})
    await db.products.insert_one({"id": "p1", "name": "Ayam Broiler", "image_url": "https://live/foto.jpg", "active": True})
    await server.startup()
    owner = await db.users.find_one({"username": "owner"})
    assert verify_password("RahasiaBaru!", owner["password_hash"]), "PASSWORD OWNER TER-RESET!"
    names = sorted([p["name"] for p in await db.products.find({}, {"name": 1}).to_list(100)])
    assert names == ["Ayam Broiler"], f"Produk potongan hidup lagi: {names}"
    img = (await db.products.find_one({"id": "p1"}))["image_url"]
    assert img == "https://live/foto.jpg", "Gambar produk berubah!"
    users = sorted([u["username"] for u in await db.users.find({}, {"username": 1}).to_list(100)])
    assert users == ["owner"], f"Akun demo muncul lagi: {users}"
    print(f"[B] restart production -> password owner tetap, produk={names}, users={users}, gambar tetap")

    await mongo.drop_database("prodguard_test_db")
    print("\nSEMUA UJI PRODUCTION LULUS: auto-seed terblokir total.")


asyncio.run(main())
