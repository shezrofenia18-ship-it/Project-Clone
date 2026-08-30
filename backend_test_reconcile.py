#!/usr/bin/env python3
"""
Backend test untuk REFACTOR modul reconcile.py - Berkah Ayam Mili
Uji 12 jenis deteksi kerusakan data + RBAC + idempotency + auto-repair + regresi keuangan
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from typing import Dict, List

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

# Konfigurasi
BASE_URL = "https://github-app-launcher.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

# Kredensial
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"
ADMIN_EMAIL = "admin@berkahayam.com"
ADMIN_PASSWORD = "admin123"
KASIR_EMAIL = "kasir@berkahayam.com"
KASIR_PASSWORD = "kasir123"

# State global untuk tracking
test_results = []
tokens = {}
db = None
backup_data = {}


def log(msg: str):
    """Log dengan timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def record(test_name: str, passed: bool, detail: str = ""):
    """Catat hasil test"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": test_name, "passed": passed, "detail": detail})
    log(f"{status} - {test_name}" + (f": {detail}" if detail else ""))


async def login(email: str, password: str) -> str:
    """Login dan dapatkan token"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            raise Exception(f"Login gagal untuk {email}: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("token")


async def api_get(endpoint: str, token: str = None, expect_status: int = 200) -> Dict:
    """GET request ke API"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}{endpoint}", headers=headers)
        if resp.status_code != expect_status:
            raise Exception(f"GET {endpoint} expected {expect_status}, got {resp.status_code}: {resp.text}")
        return resp.json() if resp.status_code == 200 else {}


async def api_post(endpoint: str, data: Dict, token: str = None, expect_status: int = 200) -> Dict:
    """POST request ke API"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}{endpoint}", json=data, headers=headers)
        if resp.status_code != expect_status:
            raise Exception(f"POST {endpoint} expected {expect_status}, got {resp.status_code}: {resp.text}")
        return resp.json() if resp.status_code == 200 else {}


async def setup():
    """Setup: login semua role dan koneksi MongoDB"""
    global tokens, db
    log("=== SETUP ===")
    
    # Login
    tokens["owner"] = await login(OWNER_EMAIL, OWNER_PASSWORD)
    tokens["admin"] = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
    tokens["kasir"] = await login(KASIR_EMAIL, KASIR_PASSWORD)
    log(f"✓ Login berhasil untuk 3 role")
    
    # MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    log(f"✓ Koneksi MongoDB: {MONGO_URL}/{DB_NAME}")


async def test_rbac():
    """Test 1-2: RBAC untuk consistency dan reconcile"""
    log("\n=== TEST 1-2: RBAC ===")
    
    # Test 1: GET consistency
    try:
        # Owner - harus 200
        result = await api_get("/maintenance/consistency", tokens["owner"], 200)
        record("1a. GET consistency - Owner", True, f"issue_count={result.get('issue_count', 0)}")
        
        # Admin - harus 200
        result = await api_get("/maintenance/consistency", tokens["admin"], 200)
        record("1b. GET consistency - Admin", True, f"issue_count={result.get('issue_count', 0)}")
        
        # Kasir - harus 403
        try:
            await api_get("/maintenance/consistency", tokens["kasir"], 403)
            record("1c. GET consistency - Kasir", True, "403 (correctly rejected)")
        except Exception as e:
            record("1c. GET consistency - Kasir", False, str(e))
    except Exception as e:
        record("1. GET consistency RBAC", False, str(e))
    
    # Test 2: POST reconcile
    try:
        # Owner - harus 200
        result = await api_post("/maintenance/reconcile", {}, tokens["owner"], 200)
        record("2a. POST reconcile - Owner", True, f"fixed_count={result.get('fixed_count', 0)}")
        
        # Admin - harus 403
        try:
            await api_post("/maintenance/reconcile", {}, tokens["admin"], 403)
            record("2b. POST reconcile - Admin", True, "403 (correctly rejected)")
        except Exception as e:
            record("2b. POST reconcile - Admin", False, str(e))
        
        # Kasir - harus 403
        try:
            await api_post("/maintenance/reconcile", {}, tokens["kasir"], 403)
            record("2c. POST reconcile - Kasir", True, "403 (correctly rejected)")
        except Exception as e:
            record("2c. POST reconcile - Kasir", False, str(e))
    except Exception as e:
        record("2. POST reconcile RBAC", False, str(e))


async def test_idempotency():
    """Test 3: Idempotency - reconcile 2x harus fixed_count=0 pada run kedua"""
    log("\n=== TEST 3: IDEMPOTENCY ===")
    
    try:
        # Ambil dashboard sebelum
        dashboard_before = await api_get("/dashboard", tokens["owner"])
        omzet_before = dashboard_before.get("omzet", 0)
        
        # Run pertama
        result1 = await api_post("/maintenance/reconcile", {}, tokens["owner"])
        fixed1 = result1.get("fixed_count", 0)
        
        # Run kedua
        result2 = await api_post("/maintenance/reconcile", {}, tokens["owner"])
        fixed2 = result2.get("fixed_count", 0)
        
        # Dashboard setelah
        dashboard_after = await api_get("/dashboard", tokens["owner"])
        omzet_after = dashboard_after.get("omzet", 0)
        
        # Verifikasi
        passed = (fixed2 == 0) and (omzet_before == omzet_after)
        detail = f"Run1: {fixed1} fixes, Run2: {fixed2} fixes, Omzet unchanged: {omzet_before == omzet_after}"
        record("3. Idempotency", passed, detail)
    except Exception as e:
        record("3. Idempotency", False, str(e))


async def backup_collection(collection_name: str, query: Dict = None):
    """Backup dokumen dari collection"""
    query = query or {}
    docs = await db[collection_name].find(query).to_list(1000)
    backup_data[collection_name] = docs
    return docs


async def restore_collection(collection_name: str):
    """Restore dokumen ke collection"""
    if collection_name not in backup_data:
        return
    docs = backup_data[collection_name]
    if docs:
        await db[collection_name].delete_many({})
        await db[collection_name].insert_many(docs)


async def test_detection_kind_a():
    """Test 4a: pembelian_tanpa_pengeluaran"""
    log("\n=== TEST 4a: pembelian_tanpa_pengeluaran ===")
    
    try:
        # Ambil 1 pembelian
        purchase = await db.purchases.find_one()
        if not purchase:
            record("4a. pembelian_tanpa_pengeluaran", False, "Tidak ada pembelian untuk diuji")
            return
        
        # Backup pengeluaran terkait
        expense = await db.expenses.find_one({"ref": purchase["id"], "category": "Pembelian Ayam"})
        if not expense:
            record("4a. pembelian_tanpa_pengeluaran", False, "Pengeluaran pembelian tidak ditemukan")
            return
        
        backup_data["expense_a"] = expense
        
        # RUSAK: hapus pengeluaran
        await db.expenses.delete_one({"id": expense["id"]})
        log(f"  Dihapus: expense {expense['id'][:8]} untuk purchase {purchase['id'][:8]}")
        
        # Verifikasi deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pembelian_tanpa_pengeluaran", 0) >= 1
        
        if not detected:
            record("4a. pembelian_tanpa_pengeluaran", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            # Restore manual
            await db.expenses.insert_one(expense)
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pembelian_tanpa_pengeluaran')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi perbaikan
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4a. pembelian_tanpa_pengeluaran", fixed, 
               f"Detected: {detected}, Fixed: {fixed}, issue_count after: {result_after.get('issue_count')}")
    except Exception as e:
        record("4a. pembelian_tanpa_pengeluaran", False, str(e))
        # Restore jika ada
        if "expense_a" in backup_data:
            await db.expenses.insert_one(backup_data["expense_a"])


async def test_detection_kind_b():
    """Test 4b: pengeluaran_pembelian_tidak_cocok"""
    log("\n=== TEST 4b: pengeluaran_pembelian_tidak_cocok ===")
    
    try:
        # Ambil 1 pembelian dengan pengeluaran
        purchase = await db.purchases.find_one()
        if not purchase:
            record("4b. pengeluaran_pembelian_tidak_cocok", False, "Tidak ada pembelian")
            return
        
        expense = await db.expenses.find_one({"ref": purchase["id"], "category": "Pembelian Ayam"})
        if not expense:
            record("4b. pengeluaran_pembelian_tidak_cocok", False, "Pengeluaran tidak ditemukan")
            return
        
        # Backup
        backup_data["expense_b"] = {"id": expense["id"], "amount": expense.get("amount")}
        
        # RUSAK: ubah amount jadi 1
        await db.expenses.update_one({"id": expense["id"]}, {"$set": {"amount": 1}})
        log(f"  Diubah: expense {expense['id'][:8]} amount → 1 (seharusnya {expense.get('amount')})")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pengeluaran_pembelian_tidak_cocok", 0) >= 1
        
        if not detected:
            record("4b. pengeluaran_pembelian_tidak_cocok", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.expenses.update_one({"id": expense["id"]}, {"$set": {"amount": backup_data["expense_b"]["amount"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pengeluaran_pembelian_tidak_cocok')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4b. pengeluaran_pembelian_tidak_cocok", fixed,
               f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4b. pengeluaran_pembelian_tidak_cocok", False, str(e))


async def test_detection_kind_c():
    """Test 4c: kas_keluar_belum_ditandai"""
    log("\n=== TEST 4c: kas_keluar_belum_ditandai ===")
    
    try:
        # Buat pembelian kredit + bayar hutang dulu
        log("  Membuat pembelian kredit untuk testing...")
        
        # Ambil supplier
        supplier = await db.suppliers.find_one()
        if not supplier:
            record("4c. kas_keluar_belum_ditandai", False, "Tidak ada supplier")
            return
        
        # Ambil produk
        product = await db.products.find_one({"units": {"$in": ["kg"]}})
        if not product:
            record("4c. kas_kelur_belum_ditandai", False, "Tidak ada produk")
            return
        
        # Buat pembelian kredit via API
        purchase_data = {
            "supplier_id": supplier["id"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [{"product_id": product["id"], "total_weight": 10, "ekor": 0, "total_price": 500000}],
            "transport_cost": 0,
            "other_cost": 0,
            "paid": 200000,  # Bayar sebagian (total 500000, sisa 300000)
            "notes": "Test kredit untuk kas_keluar_belum_ditandai"
        }
        
        purchase_resp = await api_post("/purchases", purchase_data, tokens["owner"])
        purchase_id = purchase_resp.get("id")
        log(f"  Pembelian kredit dibuat: {purchase_id[:8]}")
        
        # Ambil payable
        payable = await db.payables.find_one({"purchase_id": purchase_id})
        if not payable:
            record("4c. kas_keluar_belum_ditandai", False, "Payable tidak dibuat")
            return
        
        # Bayar hutang via API
        pay_resp = await api_post(f"/payables/{payable['id']}/pay", {"amount": 50000}, tokens["owner"])
        log(f"  Hutang dibayar: Rp 50,000")
        
        # Ambil pengeluaran pembayaran hutang
        debt_expense = await db.expenses.find_one({"category": "Pembayaran Hutang", "ref": payable["id"]})
        if not debt_expense:
            record("4c. kas_keluar_belum_ditandai", False, "Pengeluaran pembayaran hutang tidak dibuat")
            return
        
        # Backup
        backup_data["debt_expense_c"] = {"id": debt_expense["id"], "cash_amount": debt_expense.get("cash_amount")}
        
        # RUSAK: unset cash_amount
        await db.expenses.update_one({"id": debt_expense["id"]}, {"$unset": {"cash_amount": ""}})
        log(f"  Dirusak: expense {debt_expense['id'][:8]} cash_amount di-unset")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("kas_keluar_belum_ditandai", 0) >= 1
        
        if not detected:
            record("4c. kas_keluar_belum_ditandai", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.expenses.update_one({"id": debt_expense["id"]}, 
                                        {"$set": {"cash_amount": backup_data["debt_expense_c"]["cash_amount"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('kas_keluar_belum_ditandai')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4c. kas_keluar_belum_ditandai", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4c. kas_keluar_belum_ditandai", False, str(e))


async def test_detection_kind_d():
    """Test 4d: status_transaksi_tertinggal"""
    log("\n=== TEST 4d: status_transaksi_tertinggal ===")
    
    try:
        # Cari penjualan piutang
        sale = await db.sales.find_one({"payment_status": "piutang", "status": {"$ne": "batal"}})
        if not sale:
            record("4d. status_transaksi_tertinggal", False, "Tidak ada penjualan piutang untuk diuji")
            return
        
        receivable = await db.receivables.find_one({"sale_id": sale["id"]})
        if not receivable:
            record("4d. status_transaksi_tertinggal", False, "Receivable tidak ditemukan")
            return
        
        # Backup
        backup_data["sale_d"] = {"id": sale["id"], "receivable": sale.get("receivable")}
        
        # RUSAK: ubah sale.receivable jadi berbeda dari receivable.remaining
        new_receivable = receivable.get("remaining", 0) + 10000
        await db.sales.update_one({"id": sale["id"]}, {"$set": {"receivable": new_receivable}})
        log(f"  Dirusak: sale {sale['id'][:8]} receivable → {new_receivable} (seharusnya {receivable.get('remaining')})")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("status_transaksi_tertinggal", 0) >= 1
        
        if not detected:
            record("4d. status_transaksi_tertinggal", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.sales.update_one({"id": sale["id"]}, {"$set": {"receivable": backup_data["sale_d"]["receivable"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('status_transaksi_tertinggal')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4d. status_transaksi_tertinggal", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4d. status_transaksi_tertinggal", False, str(e))


async def test_detection_kind_e():
    """Test 4e: piutang_tanpa_tagihan"""
    log("\n=== TEST 4e: piutang_tanpa_tagihan ===")
    
    try:
        # Cari penjualan piutang dengan tagihan
        sale = await db.sales.find_one({"payment_status": "piutang", "status": {"$ne": "batal"}})
        if not sale:
            record("4e. piutang_tanpa_tagihan", False, "Tidak ada penjualan piutang")
            return
        
        receivable = await db.receivables.find_one({"sale_id": sale["id"]})
        if not receivable:
            record("4e. piutang_tanpa_tagihan", False, "Receivable tidak ditemukan")
            return
        
        # Backup
        backup_data["receivable_e"] = receivable
        
        # RUSAK: hapus receivable
        await db.receivables.delete_one({"id": receivable["id"]})
        log(f"  Dihapus: receivable {receivable['id'][:8]} untuk sale {sale['id'][:8]}")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("piutang_tanpa_tagihan", 0) >= 1
        
        if not detected:
            record("4e. piutang_tanpa_tagihan", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.receivables.insert_one(receivable)
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('piutang_tanpa_tagihan')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4e. piutang_tanpa_tagihan", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4e. piutang_tanpa_tagihan", False, str(e))


async def test_detection_kind_f():
    """Test 4f: piutang_hantu"""
    log("\n=== TEST 4f: piutang_hantu ===")
    
    try:
        # Buat penjualan piutang baru untuk dibatalkan
        log("  Membuat penjualan piutang untuk testing...")
        
        customer = await db.customers.find_one()
        product = await db.products.find_one({"units": {"$in": ["kg"]}})
        
        if not customer or not product:
            record("4f. piutang_hantu", False, "Customer atau produk tidak ditemukan")
            return
        
        # Buat penjualan piutang
        sale_data = {
            "customer_id": customer["id"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_method": "piutang",
            "items": [{"product_id": product["id"], "unit": "kg", "qty": 0.5, "price": product.get("price_kg", 20000)}],
            "paid": 5000,
            "txn_id": f"test_f_{int(time.time())}"
        }
        
        sale_resp = await api_post("/sales", sale_data, tokens["owner"])
        sale_id = sale_resp.get("id")
        log(f"  Penjualan piutang dibuat: {sale_id[:8]}")
        
        # Batalkan via API
        await api_post(f"/sales/{sale_id}/cancel", {}, tokens["owner"])
        log(f"  Penjualan dibatalkan")
        
        # Ambil receivable
        receivable = await db.receivables.find_one({"sale_id": sale_id})
        if not receivable:
            record("4f. piutang_hantu", False, "Receivable tidak ditemukan setelah cancel")
            return
        
        # Backup
        backup_data["receivable_f"] = {"id": receivable["id"], "status": receivable.get("status"), 
                                       "remaining": receivable.get("remaining")}
        
        # RUSAK: kembalikan receivable ke status belum_lunas
        await db.receivables.update_one({"id": receivable["id"]}, 
                                       {"$set": {"status": "belum_lunas", "remaining": 5000}})
        log(f"  Dirusak: receivable {receivable['id'][:8]} status → belum_lunas, remaining → 5000")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("piutang_hantu", 0) >= 1
        
        if not detected:
            record("4f. piutang_hantu", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.receivables.update_one({"id": receivable["id"]}, 
                                           {"$set": {"status": "batal", "remaining": 0}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('piutang_hantu')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4f. piutang_hantu", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4f. piutang_hantu", False, str(e))


async def test_detection_kind_g():
    """Test 4g: pemasukan_hilang"""
    log("\n=== TEST 4g: pemasukan_hilang ===")
    
    try:
        # Cari penjualan aktif dengan income
        sale = await db.sales.find_one({"status": {"$ne": "batal"}})
        if not sale:
            record("4g. pemasukan_hilang", False, "Tidak ada penjualan aktif")
            return
        
        income = await db.incomes.find_one({"ref": sale["id"], "source": "pos"})
        if not income:
            record("4g. pemasukan_hilang", False, "Income tidak ditemukan")
            return
        
        # Backup
        backup_data["income_g"] = income
        
        # RUSAK: hapus income
        await db.incomes.delete_one({"id": income["id"]})
        log(f"  Dihapus: income {income['id'][:8]} untuk sale {sale['id'][:8]}")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pemasukan_hilang", 0) >= 1
        
        if not detected:
            record("4g. pemasukan_hilang", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.incomes.insert_one(income)
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pemasukan_hilang')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4g. pemasukan_hilang", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4g. pemasukan_hilang", False, str(e))


async def test_detection_kind_h():
    """Test 4h: pemasukan_dobel"""
    log("\n=== TEST 4h: pemasukan_dobel ===")
    
    try:
        # Cari penjualan dengan income
        sale = await db.sales.find_one({"status": {"$ne": "batal"}})
        if not sale:
            record("4h. pemasukan_dobel", False, "Tidak ada penjualan")
            return
        
        income = await db.incomes.find_one({"ref": sale["id"], "source": "pos"})
        if not income:
            record("4h. pemasukan_dobel", False, "Income tidak ditemukan")
            return
        
        # RUSAK: duplikat income dengan id baru
        import uuid
        duplicate_income = {k: v for k, v in income.items() if k != "_id"}  # Exclude _id
        duplicate_income["id"] = str(uuid.uuid4())
        await db.incomes.insert_one(duplicate_income)
        log(f"  Diduplikat: income untuk sale {sale['id'][:8]} (id baru: {duplicate_income['id'][:8]})")
        
        backup_data["duplicate_income_h"] = duplicate_income["id"]
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pemasukan_dobel", 0) >= 1
        
        if not detected:
            record("4h. pemasukan_dobel", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.incomes.delete_one({"id": duplicate_income["id"]})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pemasukan_dobel')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4h. pemasukan_dobel", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4h. pemasukan_dobel", False, str(e))


async def test_detection_kind_i():
    """Test 4i: pemasukan_yatim"""
    log("\n=== TEST 4i: pemasukan_yatim ===")
    
    try:
        # RUSAK: buat income dengan ref id acak
        import uuid
        orphan_income = {
            "id": str(uuid.uuid4()),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": "Penjualan Ayam",
            "amount": 50000,
            "source": "pos",
            "ref": str(uuid.uuid4()),  # ID acak yang tidak ada
            "created_at": datetime.now().isoformat()
        }
        await db.incomes.insert_one(orphan_income)
        log(f"  Dibuat: income yatim {orphan_income['id'][:8]} dengan ref acak {orphan_income['ref'][:8]}")
        
        backup_data["orphan_income_i"] = orphan_income["id"]
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pemasukan_yatim", 0) >= 1
        
        if not detected:
            record("4i. pemasukan_yatim", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.incomes.delete_one({"id": orphan_income["id"]})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pemasukan_yatim')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4i. pemasukan_yatim", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4i. pemasukan_yatim", False, str(e))


async def test_detection_kind_j():
    """Test 4j: pemasukan_tidak_cocok"""
    log("\n=== TEST 4j: pemasukan_tidak_cocok ===")
    
    try:
        # Cari penjualan dengan income
        sale = await db.sales.find_one({"status": {"$ne": "batal"}})
        if not sale:
            record("4j. pemasukan_tidak_cocok", False, "Tidak ada penjualan")
            return
        
        income = await db.incomes.find_one({"ref": sale["id"], "source": "pos"})
        if not income:
            record("4j. pemasukan_tidak_cocok", False, "Income tidak ditemukan")
            return
        
        # Backup
        backup_data["income_j"] = {"id": income["id"], "amount": income.get("amount")}
        
        # RUSAK: ubah amount income jadi berbeda dari sale.paid
        new_amount = sale.get("paid", 0) + 10000
        await db.incomes.update_one({"id": income["id"]}, {"$set": {"amount": new_amount}})
        log(f"  Dirusak: income {income['id'][:8]} amount → {new_amount} (seharusnya {sale.get('paid')})")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("pemasukan_tidak_cocok", 0) >= 1
        
        if not detected:
            record("4j. pemasukan_tidak_cocok", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.incomes.update_one({"id": income["id"]}, 
                                       {"$set": {"amount": backup_data["income_j"]["amount"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('pemasukan_tidak_cocok')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4j. pemasukan_tidak_cocok", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4j. pemasukan_tidak_cocok", False, str(e))


async def test_detection_kind_k():
    """Test 4k: saldo_pelanggan"""
    log("\n=== TEST 4k: saldo_pelanggan ===")
    
    try:
        # Ambil customer
        customer = await db.customers.find_one()
        if not customer:
            record("4k. saldo_pelanggan", False, "Tidak ada customer")
            return
        
        # Backup
        backup_data["customer_k"] = {"id": customer["id"], "receivable": customer.get("receivable"), 
                                     "total_purchase": customer.get("total_purchase")}
        
        # RUSAK: ubah saldo jadi angka ngawur
        await db.customers.update_one({"id": customer["id"]}, 
                                     {"$set": {"receivable": 999999, "total_purchase": 888888}})
        log(f"  Dirusak: customer {customer.get('name')} receivable → 999999, total_purchase → 888888")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("saldo_pelanggan", 0) >= 1
        
        if not detected:
            record("4k. saldo_pelanggan", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.customers.update_one({"id": customer["id"]}, 
                                         {"$set": {"receivable": backup_data["customer_k"]["receivable"],
                                                  "total_purchase": backup_data["customer_k"]["total_purchase"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('saldo_pelanggan')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4k. saldo_pelanggan", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4k. saldo_pelanggan", False, str(e))


async def test_detection_kind_l():
    """Test 4l: saldo_supplier"""
    log("\n=== TEST 4l: saldo_supplier ===")
    
    try:
        # Ambil supplier
        supplier = await db.suppliers.find_one()
        if not supplier:
            record("4l. saldo_supplier", False, "Tidak ada supplier")
            return
        
        # Backup
        backup_data["supplier_l"] = {"id": supplier["id"], "payable": supplier.get("payable"),
                                     "total_purchase": supplier.get("total_purchase")}
        
        # RUSAK: ubah saldo jadi angka ngawur
        await db.suppliers.update_one({"id": supplier["id"]},
                                     {"$set": {"payable": 777777, "total_purchase": 666666}})
        log(f"  Dirusak: supplier {supplier.get('name')} payable → 777777, total_purchase → 666666")
        
        # Deteksi
        result = await api_get("/maintenance/consistency", tokens["owner"])
        by_kind = {k["kind"]: k["count"] for k in result.get("by_kind", [])}
        detected = by_kind.get("saldo_supplier", 0) >= 1
        
        if not detected:
            record("4l. saldo_supplier", False, f"TIDAK TERDETEKSI. by_kind: {by_kind}")
            await db.suppliers.update_one({"id": supplier["id"]},
                                         {"$set": {"payable": backup_data["supplier_l"]["payable"],
                                                  "total_purchase": backup_data["supplier_l"]["total_purchase"]}})
            return
        
        log(f"  ✓ Terdeteksi: {by_kind.get('saldo_supplier')} temuan")
        
        # Perbaiki
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Verifikasi
        result_after = await api_get("/maintenance/consistency", tokens["owner"])
        fixed = result_after.get("issue_count", 0) == 0
        
        record("4l. saldo_supplier", fixed, f"Detected: {detected}, Fixed: {fixed}")
    except Exception as e:
        record("4l. saldo_supplier", False, str(e))


async def test_auto_repair_startup():
    """Test 5: Auto-repair saat startup"""
    log("\n=== TEST 5: AUTO-REPAIR SAAT STARTUP ===")
    
    try:
        # Rusak 1 data (saldo customer)
        customer = await db.customers.find_one()
        if not customer:
            record("5. Auto-repair startup", False, "Tidak ada customer")
            return
        
        backup_data["customer_startup"] = {"id": customer["id"], "receivable": customer.get("receivable")}
        
        await db.customers.update_one({"id": customer["id"]}, {"$set": {"receivable": 555555}})
        log(f"  Dirusak: customer {customer.get('name')} receivable → 555555")
        
        # Restart backend
        log("  Restarting backend...")
        os.system("sudo supervisorctl restart backend > /dev/null 2>&1")
        
        # Tunggu 15 detik
        log("  Menunggu 15 detik untuk auto-repair...")
        await asyncio.sleep(15)
        
        # Cek consistency
        result = await api_get("/maintenance/consistency", tokens["owner"])
        issue_count = result.get("issue_count", -1)
        
        passed = issue_count == 0
        record("5. Auto-repair startup", passed, 
               f"issue_count after restart: {issue_count} (expected: 0)")
    except Exception as e:
        record("5. Auto-repair startup", False, str(e))


async def test_financial_regression():
    """Test 6: Regresi rumus keuangan"""
    log("\n=== TEST 6: REGRESI RUMUS KEUANGAN ===")
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Ambil 3 endpoint
        dashboard = await api_get("/dashboard", tokens["owner"])
        profit_loss = await api_get(f"/reports/profit-loss?start={today}&end={today}", tokens["owner"])
        closing = await api_get(f"/daily-closing/preview?date={today}", tokens["owner"])
        
        # Ekstrak angka
        d_omzet = dashboard.get("omzet", 0)
        d_hpp = dashboard.get("hpp", 0)
        d_laba_kotor = dashboard.get("laba", 0)
        d_opex = dashboard.get("opex", 0)
        d_net_profit = dashboard.get("net_profit", 0)
        d_cash_out = dashboard.get("cash_out", 0)
        d_net_cash = dashboard.get("net_cash", 0)
        
        pl_omzet = profit_loss.get("omzet", 0)
        pl_hpp = profit_loss.get("hpp", 0)
        pl_laba_kotor = profit_loss.get("gross_profit", 0)
        pl_opex = profit_loss.get("opex", 0)
        pl_net_profit = profit_loss.get("net_profit", 0)
        pl_cash_out = profit_loss.get("cash_out", 0)
        pl_net_cash = profit_loss.get("net_cash", 0)
        
        c_omzet = closing.get("omzet", 0)
        c_hpp = closing.get("hpp", 0)
        c_laba_kotor = closing.get("gross_profit", 0)
        c_opex = closing.get("opex", 0)
        c_net_profit = closing.get("net_profit", 0)
        c_cash_out = closing.get("expense_total", 0)  # Closing uses expense_total for cash_out
        c_net_cash = closing.get("net_cash", 0)
        
        # Verifikasi konsistensi (toleransi Rp 1)
        def eq(a, b):
            return abs(a - b) <= 1
        
        omzet_ok = eq(d_omzet, pl_omzet) and eq(pl_omzet, c_omzet)
        hpp_ok = eq(d_hpp, pl_hpp) and eq(pl_hpp, c_hpp)
        laba_kotor_ok = eq(d_laba_kotor, pl_laba_kotor) and eq(pl_laba_kotor, c_laba_kotor)
        opex_ok = eq(d_opex, pl_opex) and eq(pl_opex, c_opex)
        net_profit_ok = eq(d_net_profit, pl_net_profit) and eq(pl_net_profit, c_net_profit)
        net_cash_ok = eq(d_net_cash, pl_net_cash) and eq(pl_net_cash, c_net_cash)
        
        # Verifikasi rumus
        rumus_net_profit_ok = eq(d_net_profit, d_laba_kotor - d_opex)
        rumus_net_cash_ok = eq(d_net_cash, dashboard.get("cash_in", 0) - d_cash_out)
        
        all_ok = (omzet_ok and hpp_ok and laba_kotor_ok and opex_ok and 
                  net_profit_ok and net_cash_ok and rumus_net_profit_ok and rumus_net_cash_ok)
        
        detail = f"""
Dashboard: omzet={d_omzet}, hpp={d_hpp}, laba_kotor={d_laba_kotor}, opex={d_opex}, net_profit={d_net_profit}, net_cash={d_net_cash}
Profit-Loss: omzet={pl_omzet}, hpp={pl_hpp}, laba_kotor={pl_laba_kotor}, opex={pl_opex}, net_profit={pl_net_profit}, net_cash={pl_net_cash}
Closing: omzet={c_omzet}, hpp={c_hpp}, laba_kotor={c_laba_kotor}, opex={c_opex}, net_profit={c_net_profit}, net_cash={c_net_cash}
Konsistensi: omzet={omzet_ok}, hpp={hpp_ok}, laba_kotor={laba_kotor_ok}, opex={opex_ok}, net_profit={net_profit_ok}, net_cash={net_cash_ok}
Rumus: net_profit={rumus_net_profit_ok}, net_cash={rumus_net_cash_ok}
        """.strip()
        
        record("6a. Konsistensi angka keuangan", all_ok, detail)
        
        # Test monthly endpoint
        monthly = await api_get("/dashboard/monthly?months=12", tokens["owner"])
        series = monthly.get("series", [])
        
        monthly_ok = len(series) == 12
        record("6b. Monthly endpoint", monthly_ok, f"series length: {len(series)} (expected: 12)")
        
    except Exception as e:
        record("6. Regresi keuangan", False, str(e))


async def final_check():
    """Test 7: Pemeriksaan akhir - data harus bersih"""
    log("\n=== TEST 7: PEMERIKSAAN AKHIR ===")
    
    try:
        # Jalankan reconcile sekali lagi untuk memastikan semua bersih
        await api_post("/maintenance/reconcile", {}, tokens["owner"])
        
        # Cek consistency
        result = await api_get("/maintenance/consistency", tokens["owner"])
        issue_count = result.get("issue_count", -1)
        
        # Ambil dashboard untuk laporan akhir
        dashboard = await api_get("/dashboard", tokens["owner"])
        
        passed = issue_count == 0
        detail = f"""
issue_count: {issue_count} (expected: 0)
Dashboard akhir:
  Omzet: Rp {dashboard.get('omzet', 0):,.0f}
  Laba Kotor: Rp {dashboard.get('laba', 0):,.0f}
  Opex: Rp {dashboard.get('opex', 0):,.0f}
  Laba Bersih: Rp {dashboard.get('net_profit', 0):,.0f}
        """.strip()
        
        record("7. Pemeriksaan akhir", passed, detail)
        
        # Catat angka dashboard untuk laporan
        log(f"\n📊 ANGKA DASHBOARD AKHIR:")
        log(f"  Omzet: Rp {dashboard.get('omzet', 0):,.0f}")
        log(f"  Laba Kotor: Rp {dashboard.get('laba', 0):,.0f}")
        log(f"  Opex: Rp {dashboard.get('opex', 0):,.0f}")
        log(f"  Laba Bersih: Rp {dashboard.get('net_profit', 0):,.0f}")
        
    except Exception as e:
        record("7. Pemeriksaan akhir", False, str(e))


async def main():
    """Main test runner"""
    log("=" * 80)
    log("BACKEND TEST - REFACTOR RECONCILE.PY")
    log("Berkah Ayam Mili - POS Application")
    log("=" * 80)
    
    try:
        # Setup
        await setup()
        
        # Test RBAC
        await test_rbac()
        
        # Test Idempotency
        await test_idempotency()
        
        # Test 12 detection kinds
        await test_detection_kind_a()
        await test_detection_kind_b()
        await test_detection_kind_c()
        await test_detection_kind_d()
        await test_detection_kind_e()
        await test_detection_kind_f()
        await test_detection_kind_g()
        await test_detection_kind_h()
        await test_detection_kind_i()
        await test_detection_kind_j()
        await test_detection_kind_k()
        await test_detection_kind_l()
        
        # Test auto-repair
        await test_auto_repair_startup()
        
        # Test financial regression
        await test_financial_regression()
        
        # Final check
        await final_check()
        
        # Summary
        log("\n" + "=" * 80)
        log("TEST SUMMARY")
        log("=" * 80)
        
        passed = sum(1 for t in test_results if t["passed"])
        failed = sum(1 for t in test_results if not t["passed"])
        total = len(test_results)
        
        log(f"\nTotal: {total} tests")
        log(f"✅ Passed: {passed}")
        log(f"❌ Failed: {failed}")
        
        if failed > 0:
            log("\n❌ FAILED TESTS:")
            for t in test_results:
                if not t["passed"]:
                    log(f"  - {t['name']}: {t['detail']}")
        
        log("\n" + "=" * 80)
        
        if failed == 0:
            log("🎉 ALL TESTS PASSED - REFACTOR VERIFIED")
        else:
            log(f"⚠️  {failed} TEST(S) FAILED - REVIEW NEEDED")
        
        log("=" * 80)
        
    except Exception as e:
        log(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
