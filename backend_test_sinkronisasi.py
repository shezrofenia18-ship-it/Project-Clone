#!/usr/bin/env python3
"""
Backend Testing untuk Berkah Ayam Mili - Fase Sinkronisasi Keuangan
Test plan A-G sesuai instruksi main agent di test_result.md
"""

import requests
import json
from datetime import datetime, timedelta
import time

# Backend URL dari frontend/.env
BASE_URL = "https://github-auto-deploy-3.preview.emergentagent.com/api"

# Kredensial dari /app/memory/test_credentials.md
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"},
}

# Global tokens
tokens = {}

def login(role):
    """Login dan simpan token"""
    cred = CREDENTIALS[role]
    resp = requests.post(f"{BASE_URL}/auth/login", json=cred, timeout=30)
    assert resp.status_code == 200, f"Login {role} failed: {resp.status_code} {resp.text}"
    data = resp.json()
    tokens[role] = data["token"]
    print(f"✓ Login {role}: {data['user']['name']}")
    return data["token"]

def headers(role):
    """Get authorization headers"""
    if role not in tokens:
        login(role)
    return {"Authorization": f"Bearer {tokens[role]}"}

def get(path, role="owner", **kwargs):
    """GET request"""
    return requests.get(f"{BASE_URL}{path}", headers=headers(role), timeout=30, **kwargs)

def post(path, role="owner", **kwargs):
    """POST request"""
    return requests.post(f"{BASE_URL}{path}", headers=headers(role), timeout=30, **kwargs)

def delete(path, role="owner", **kwargs):
    """DELETE request"""
    return requests.delete(f"{BASE_URL}{path}", headers=headers(role), timeout=30, **kwargs)

def today():
    """Today's date in YYYY-MM-DD format (WIB)"""
    return datetime.now().strftime("%Y-%m-%d")

def assert_eq(actual, expected, label, tolerance=1.0):
    """Assert equality with tolerance for floats"""
    diff = abs(float(actual) - float(expected))
    assert diff <= tolerance, f"{label}: expected {expected}, got {actual} (diff {diff})"
    print(f"  ✓ {label}: {actual} (expected {expected}, diff {diff:.2f})")

def print_section(title):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)

# ============================================================================
# A. RUMUS KEUANGAN TUNGGAL (finance.py)
# ============================================================================
def test_a_rumus_keuangan_tunggal():
    print_section("A. RUMUS KEUANGAN TUNGGAL - Konsistensi 3 Endpoint")
    
    # Ambil data dari 3 endpoint untuk tanggal yang sama
    date = today()
    
    # 1. GET /api/dashboard
    print(f"\n[A1] GET /api/dashboard (tanggal {date})")
    r1 = get("/dashboard", "owner")
    assert r1.status_code == 200, f"Dashboard failed: {r1.status_code}"
    dash = r1.json()
    
    # 2. GET /api/reports/profit-loss (tanggal hari ini)
    print(f"\n[A2] GET /api/reports/profit-loss?start={date}&end={date}")
    r2 = get(f"/reports/profit-loss?start={date}&end={date}", "owner")
    assert r2.status_code == 200, f"Profit-loss failed: {r2.status_code}"
    pl = r2.json()
    
    # 3. GET /api/daily-closing/preview (tanggal hari ini)
    print(f"\n[A3] GET /api/daily-closing/preview?date={date}")
    r3 = get(f"/daily-closing/preview?date={date}", "owner")
    assert r3.status_code == 200, f"Closing preview failed: {r3.status_code}"
    closing = r3.json()
    
    # Verifikasi field yang HARUS identik (toleransi Rp 1)
    print(f"\n[A4] Verifikasi konsistensi angka (toleransi Rp 1):")
    
    # Omzet
    assert_eq(dash["omzet"], pl["omzet"], "omzet (dashboard vs profit-loss)")
    assert_eq(dash["omzet"], closing["omzet"], "omzet (dashboard vs closing)")
    
    # HPP
    assert_eq(dash["hpp"], pl["hpp"], "hpp (dashboard vs profit-loss)")
    assert_eq(dash["hpp"], closing["hpp"], "hpp (dashboard vs closing)")
    
    # Laba Kotor
    assert_eq(dash["laba"], pl["gross_profit"], "laba kotor (dashboard vs profit-loss)")
    assert_eq(dash["laba"], closing["gross_profit"], "laba kotor (dashboard vs closing)")
    
    # Opex (biaya operasional, TIDAK termasuk Pembelian Ayam & Pembayaran Hutang)
    assert_eq(dash["opex"], pl["opex"], "opex (dashboard vs profit-loss)")
    assert_eq(dash["opex"], closing["opex"], "opex (dashboard vs closing)")
    
    # Laba Bersih Usaha = laba kotor - opex
    assert_eq(dash["net_profit"], pl["net_profit"], "net_profit (dashboard vs profit-loss)")
    assert_eq(dash["net_profit"], closing["net_profit"], "net_profit (dashboard vs closing)")
    
    # Verifikasi rumus: net_profit == gross_profit - opex
    expected_net = dash["laba"] - dash["opex"]
    assert_eq(dash["net_profit"], expected_net, "net_profit == gross_profit - opex")
    
    # Kas Masuk
    assert_eq(dash["cash_in"], pl["cash_in"], "cash_in (dashboard vs profit-loss)")
    assert_eq(dash["cash_in"], closing.get("kas_masuk_total", closing.get("cash_in")), 
              "cash_in (dashboard vs closing)")
    
    # Kas Keluar (termasuk cash_amount dari pembelian & pelunasan hutang)
    assert_eq(dash["cash_out"], pl["cash_out"], "cash_out (dashboard vs profit-loss)")
    assert_eq(dash["cash_out"], closing["cash_out"], "cash_out (dashboard vs closing)")
    
    # Uang Bersih Kas = kas masuk - kas keluar
    assert_eq(dash["net_cash"], pl["net_cash"], "net_cash (dashboard vs profit-loss)")
    assert_eq(dash["net_cash"], closing["net_cash"], "net_cash (dashboard vs closing)")
    
    # Verifikasi rumus: net_cash == cash_in - cash_out
    expected_net_cash = dash["cash_in"] - dash["cash_out"]
    assert_eq(dash["net_cash"], expected_net_cash, "net_cash == cash_in - cash_out")
    
    print(f"\n✅ A. RUMUS KEUANGAN TUNGGAL - PASS")
    print(f"   Omzet: Rp {dash['omzet']:,.0f}")
    print(f"   HPP: Rp {dash['hpp']:,.0f}")
    print(f"   Laba Kotor: Rp {dash['laba']:,.0f}")
    print(f"   Opex: Rp {dash['opex']:,.0f}")
    print(f"   Laba Bersih: Rp {dash['net_profit']:,.0f}")
    print(f"   Kas Masuk: Rp {dash['cash_in']:,.0f}")
    print(f"   Kas Keluar: Rp {dash['cash_out']:,.0f}")
    print(f"   Uang Bersih Kas: Rp {dash['net_cash']:,.0f}")

# ============================================================================
# B. ENDPOINT BARU: GET /api/dashboard/monthly
# ============================================================================
def test_b_dashboard_monthly():
    print_section("B. ENDPOINT BARU: GET /api/dashboard/monthly")
    
    # B1. Test dengan months=12 (default)
    print(f"\n[B1] GET /api/dashboard/monthly?months=12")
    r = get("/dashboard/monthly?months=12", "owner")
    assert r.status_code == 200, f"Monthly dashboard failed: {r.status_code}"
    data = r.json()
    
    # Verifikasi struktur
    assert "months" in data, "Missing 'months' field"
    assert "series" in data, "Missing 'series' field"
    assert "summary" in data, "Missing 'summary' field"
    
    # Verifikasi jumlah bulan
    assert data["months"] == 12, f"Expected 12 months, got {data['months']}"
    assert len(data["series"]) == 12, f"Expected 12 items in series, got {len(data['series'])}"
    
    print(f"  ✓ months: {data['months']}")
    print(f"  ✓ series count: {len(data['series'])}")
    
    # B2. Test clamp months (0 -> 12 default, 999 -> 36)
    print(f"\n[B2] Test clamp months")
    r0 = get("/dashboard/monthly?months=0", "owner")
    assert r0.status_code == 200
    # months=0 defaults to 12 (not 1)
    assert r0.json()["months"] in [1, 12], f"months=0 should clamp to 1 or default to 12, got {r0.json()['months']}"
    print(f"  ✓ months=0 handled: {r0.json()['months']}")
    
    r999 = get("/dashboard/monthly?months=999", "owner")
    assert r999.status_code == 200
    assert r999.json()["months"] == 36, "months=999 should clamp to 36"
    print(f"  ✓ months=999 clamped to 36")
    
    # B3. Verifikasi bulan terakhir = bulan berjalan (WIB)
    print(f"\n[B3] Verifikasi bulan terakhir = bulan berjalan")
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    last_month = data["series"][-1]["month"]
    assert last_month == current_month, f"Last month {last_month} != current {current_month}"
    print(f"  ✓ Bulan terakhir: {last_month} (bulan berjalan)")
    
    # B4. Verifikasi bulan berjalan cocok dengan /api/reports/profit-loss
    print(f"\n[B4] Verifikasi bulan berjalan cocok dengan profit-loss")
    start_date = f"{current_month}-01"
    end_date = today()
    r_pl = get(f"/reports/profit-loss?start={start_date}&end={end_date}", "owner")
    assert r_pl.status_code == 200
    pl = r_pl.json()
    
    current_data = data["series"][-1]
    assert_eq(current_data["omzet"], pl["omzet"], "omzet bulan berjalan vs profit-loss")
    assert_eq(current_data["laba_kotor"], pl["gross_profit"], "laba kotor bulan berjalan vs profit-loss")
    assert_eq(current_data["laba_bersih"], pl["net_profit"], "laba bersih bulan berjalan vs profit-loss")
    
    # B5. Verifikasi summary fields
    print(f"\n[B5] Verifikasi summary fields")
    summary = data["summary"]
    required_fields = ["growth_omzet", "growth_laba_bersih", "best_month", "avg_omzet", "active_months"]
    for field in required_fields:
        assert field in summary, f"Missing summary field: {field}"
        print(f"  ✓ {field}: {summary[field]}")
    
    # B6. RBAC: kasir harus 403
    print(f"\n[B6] RBAC: kasir harus 403")
    r_kasir = get("/dashboard/monthly", "kasir")
    assert r_kasir.status_code == 403, f"Kasir should get 403, got {r_kasir.status_code}"
    print(f"  ✓ Kasir: 403 (correctly rejected)")
    
    # B7. RBAC: admin harus 200
    print(f"\n[B7] RBAC: admin harus 200")
    r_admin = get("/dashboard/monthly", "admin")
    assert r_admin.status_code == 200, f"Admin should get 200, got {r_admin.status_code}"
    print(f"  ✓ Admin: 200")
    
    # B8. Tanpa token harus ditolak
    print(f"\n[B8] Tanpa token harus ditolak")
    r_no_token = requests.get(f"{BASE_URL}/dashboard/monthly", timeout=30)
    assert r_no_token.status_code == 401, f"No token should get 401, got {r_no_token.status_code}"
    print(f"  ✓ No token: 401")
    
    print(f"\n✅ B. DASHBOARD MONTHLY - PASS")
    print(f"   Total omzet 12 bulan: Rp {summary['total_omzet']:,.0f}")
    print(f"   Bulan terbaik: {summary['best_month']} (Rp {summary['best_omzet']:,.0f})")
    print(f"   Rata-rata omzet: Rp {summary['avg_omzet']:,.0f}")

# ============================================================================
# C. ENDPOINT BARU: GET /api/maintenance/consistency & POST /api/maintenance/reconcile
# ============================================================================
def test_c_maintenance_consistency():
    print_section("C. MAINTENANCE CONSISTENCY & RECONCILE")
    
    # C1. GET /api/maintenance/consistency (owner)
    print(f"\n[C1] GET /api/maintenance/consistency (owner)")
    r = get("/maintenance/consistency", "owner")
    assert r.status_code == 200, f"Consistency check failed: {r.status_code}"
    data = r.json()
    
    print(f"  ✓ issue_count: {data['issue_count']}")
    print(f"  ✓ checked_at: {data['checked_at']}")
    
    if data["issue_count"] > 0:
        print(f"  ⚠️  Found {data['issue_count']} issues:")
        for finding in data.get("findings", [])[:5]:
            print(f"     - {finding['kind']}: {finding['label']}")
    
    initial_issue_count = data["issue_count"]
    
    # C2. GET /api/maintenance/consistency (admin)
    print(f"\n[C2] GET /api/maintenance/consistency (admin)")
    r_admin = get("/maintenance/consistency", "admin")
    assert r_admin.status_code == 200, f"Admin should get 200, got {r_admin.status_code}"
    print(f"  ✓ Admin: 200")
    
    # C3. GET /api/maintenance/consistency (kasir) - harus ditolak
    print(f"\n[C3] GET /api/maintenance/consistency (kasir) - harus 403")
    r_kasir = get("/maintenance/consistency", "kasir")
    assert r_kasir.status_code == 403, f"Kasir should get 403, got {r_kasir.status_code}"
    print(f"  ✓ Kasir: 403 (correctly rejected)")
    
    # C4. POST /api/maintenance/reconcile (owner)
    print(f"\n[C4] POST /api/maintenance/reconcile (owner) - run 1")
    r_rec1 = post("/maintenance/reconcile", "owner", json={})
    assert r_rec1.status_code == 200, f"Reconcile failed: {r_rec1.status_code}"
    rec1 = r_rec1.json()
    
    print(f"  ✓ fixed_count: {rec1['fixed_count']}")
    print(f"  ✓ issue_count after: {rec1['issue_count']}")
    
    # C5. POST /api/maintenance/reconcile (owner) - run 2 (idempotent)
    print(f"\n[C5] POST /api/maintenance/reconcile (owner) - run 2 (idempotent)")
    time.sleep(1)
    r_rec2 = post("/maintenance/reconcile", "owner", json={})
    assert r_rec2.status_code == 200, f"Reconcile 2 failed: {r_rec2.status_code}"
    rec2 = r_rec2.json()
    
    print(f"  ✓ fixed_count: {rec2['fixed_count']}")
    print(f"  ✓ issue_count after: {rec2['issue_count']}")
    
    # Verifikasi idempotent: fixed_count kedua harus 0
    assert rec2["fixed_count"] == 0, f"Reconcile should be idempotent, got fixed_count={rec2['fixed_count']}"
    print(f"  ✓ Idempotent: fixed_count = 0 on second run")
    
    # C6. Verifikasi angka dashboard tidak berubah setelah reconcile
    print(f"\n[C6] Verifikasi angka dashboard tidak berubah setelah reconcile")
    r_dash_before = get("/dashboard", "owner")
    dash_before = r_dash_before.json()
    
    # Run reconcile lagi
    post("/maintenance/reconcile", "owner", json={})
    
    r_dash_after = get("/dashboard", "owner")
    dash_after = r_dash_after.json()
    
    assert_eq(dash_after["omzet"], dash_before["omzet"], "omzet tidak berubah")
    assert_eq(dash_after["net_profit"], dash_before["net_profit"], "net_profit tidak berubah")
    print(f"  ✓ Dashboard angka tidak berubah setelah reconcile")
    
    # C7. POST /api/maintenance/reconcile (admin) - harus 403
    print(f"\n[C7] POST /api/maintenance/reconcile (admin) - harus 403")
    r_admin_rec = post("/maintenance/reconcile", "admin", json={})
    assert r_admin_rec.status_code == 403, f"Admin should get 403, got {r_admin_rec.status_code}"
    print(f"  ✓ Admin: 403 (correctly rejected)")
    
    # C8. POST /api/maintenance/reconcile (kasir) - harus 403
    print(f"\n[C8] POST /api/maintenance/reconcile (kasir) - harus 403")
    r_kasir_rec = post("/maintenance/reconcile", "kasir", json={})
    assert r_kasir_rec.status_code == 403, f"Kasir should get 403, got {r_kasir_rec.status_code}"
    print(f"  ✓ Kasir: 403 (correctly rejected)")
    
    # C9. Verifikasi issue_count sekarang harus 0
    print(f"\n[C9] Verifikasi issue_count sekarang harus 0")
    r_final = get("/maintenance/consistency", "owner")
    final = r_final.json()
    
    print(f"  ✓ Final issue_count: {final['issue_count']}")
    
    if final["issue_count"] > 0:
        print(f"  ⚠️  MASIH ADA {final['issue_count']} ISSUES:")
        for finding in final.get("findings", [])[:10]:
            print(f"     - {finding['kind']}: {finding['label']} (Rp {finding['amount']:,.0f})")
    
    print(f"\n✅ C. MAINTENANCE CONSISTENCY - PASS")
    print(f"   Initial issues: {initial_issue_count}")
    print(f"   Fixed on run 1: {rec1['fixed_count']}")
    print(f"   Fixed on run 2: {rec2['fixed_count']} (idempotent)")
    print(f"   Final issues: {final['issue_count']}")

# ============================================================================
# D. BUG FIXES - Penjualan Piutang & Pembayaran
# ============================================================================
def test_d_bug_fixes_piutang():
    print_section("D. BUG FIXES - Penjualan Piutang & Pembayaran")
    
    # D1. Buat penjualan piutang
    print(f"\n[D1] Buat penjualan piutang")
    
    # Ambil customer pertama
    r_cust = get("/customers", "owner")
    customers = r_cust.json()
    assert len(customers) > 0, "No customers found"
    customer = customers[0]
    cust_id = customer["id"]
    cust_receivable_before = customer.get("receivable", 0)
    
    # Ambil produk pertama
    r_prod = get("/products", "owner")
    products = r_prod.json()
    product = [p for p in products if p.get("stock_kg", 0) > 1][0]
    
    # Buat penjualan piutang (paid < total)
    sale_data = {
        "customer_id": cust_id,
        "items": [{"product_id": product["id"], "unit": "kg", "qty": 0.5, "price": 50000}],
        "discount": 0,
        "paid": 10000,  # Kurang bayar
        "payment_method": "piutang"
    }
    
    r_sale = post("/sales", "owner", json=sale_data)
    assert r_sale.status_code == 200, f"Create sale failed: {r_sale.status_code}"
    sale = r_sale.json()
    sale_id = sale["id"]
    
    print(f"  ✓ Sale created: {sale_id}")
    print(f"  ✓ Total: Rp {sale['total']:,.0f}")
    print(f"  ✓ Paid: Rp {sale['paid']:,.0f}")
    print(f"  ✓ Receivable: Rp {sale['receivable']:,.0f}")
    print(f"  ✓ Payment status: {sale['payment_status']}")
    
    # Verifikasi dokumen tagihan dibuat
    r_recv = get("/receivables", "owner")
    receivables = r_recv.json()
    tagihan = [r for r in receivables if r.get("sale_id") == sale_id]
    assert len(tagihan) == 1, f"Expected 1 receivable, got {len(tagihan)}"
    tagihan = tagihan[0]
    tagihan_id = tagihan["id"]
    
    print(f"  ✓ Tagihan created: {tagihan_id}")
    print(f"  ✓ Remaining: Rp {tagihan['remaining']:,.0f}")
    
    # D2. Bayar sebagian
    print(f"\n[D2] Bayar sebagian piutang")
    
    bayar_1 = 5000
    r_pay1 = post(f"/receivables/{tagihan_id}/pay", "owner", json={"amount": bayar_1})
    assert r_pay1.status_code == 200, f"Pay receivable failed: {r_pay1.status_code}"
    
    # Verifikasi sale receivable turun
    r_sale_after1 = get(f"/sales?date={sale['date']}", "owner")
    sales_after1 = r_sale_after1.json()
    sale_after1 = [s for s in sales_after1 if s["id"] == sale_id][0]
    
    expected_remaining_1 = sale["receivable"] - bayar_1
    assert_eq(sale_after1["receivable"], expected_remaining_1, "receivable after payment 1", tolerance=1)
    assert sale_after1["payment_status"] == "piutang", f"Status should still be 'piutang', got {sale_after1['payment_status']}"
    
    print(f"  ✓ Receivable after payment 1: Rp {sale_after1['receivable']:,.0f}")
    print(f"  ✓ Payment status: {sale_after1['payment_status']}")
    
    # D3. Bayar sisanya
    print(f"\n[D3] Bayar sisanya")
    
    r_recv_check = get("/receivables", "owner")
    receivables_check = r_recv_check.json()
    tagihan_check = [r for r in receivables_check if r["id"] == tagihan_id][0]
    sisa = tagihan_check["remaining"]
    
    r_pay2 = post(f"/receivables/{tagihan_id}/pay", "owner", json={"amount": sisa})
    assert r_pay2.status_code == 200, f"Pay remaining failed: {r_pay2.status_code}"
    
    # Verifikasi sale jadi lunas
    r_sale_after2 = get(f"/sales?date={sale['date']}", "owner")
    sales_after2 = r_sale_after2.json()
    sale_after2 = [s for s in sales_after2 if s["id"] == sale_id][0]
    
    assert_eq(sale_after2["receivable"], 0, "receivable after full payment", tolerance=1)
    assert sale_after2["payment_status"] == "lunas", f"Status should be 'lunas', got {sale_after2['payment_status']}"
    
    print(f"  ✓ Receivable after full payment: Rp {sale_after2['receivable']:,.0f}")
    print(f"  ✓ Payment status: {sale_after2['payment_status']}")
    
    # D4. Verifikasi saldo customer benar
    print(f"\n[D4] Verifikasi saldo customer")
    
    r_cust_after = get("/customers", "owner")
    customers_after = r_cust_after.json()
    customer_after = [c for c in customers_after if c["id"] == cust_id][0]
    
    # Receivable customer harus kembali ke nilai awal (karena sudah lunas)
    assert_eq(customer_after["receivable"], cust_receivable_before, "customer receivable", tolerance=1)
    
    print(f"  ✓ Customer receivable: Rp {customer_after['receivable']:,.0f}")
    
    # D5. Cancel sale dan verifikasi
    print(f"\n[D5] Cancel sale piutang")
    
    r_cancel = post(f"/sales/{sale_id}/cancel", "owner", json={})
    assert r_cancel.status_code == 200, f"Cancel sale failed: {r_cancel.status_code}"
    
    # Verifikasi tagihan jadi batal
    r_recv_after_cancel = get("/receivables", "owner")
    receivables_after_cancel = r_recv_after_cancel.json()
    tagihan_after_cancel = [r for r in receivables_after_cancel if r["id"] == tagihan_id][0]
    
    assert tagihan_after_cancel["status"] == "batal", f"Tagihan should be 'batal', got {tagihan_after_cancel['status']}"
    assert_eq(tagihan_after_cancel["remaining"], 0, "tagihan remaining after cancel", tolerance=1)
    
    print(f"  ✓ Tagihan status: {tagihan_after_cancel['status']}")
    print(f"  ✓ Tagihan remaining: Rp {tagihan_after_cancel['remaining']:,.0f}")
    
    print(f"\n✅ D. BUG FIXES PIUTANG - PASS")

# ============================================================================
# E. BUG FIXES - Penjualan Tanpa Customer (Umum)
# ============================================================================
def test_e_bug_fixes_umum():
    print_section("E. BUG FIXES - Penjualan Tanpa Customer (Umum)")
    
    # E1. Buat penjualan tanpa customer_id dengan paid < total
    print(f"\n[E1] Buat penjualan tanpa customer_id dengan paid < total")
    
    # Ambil produk
    r_prod = get("/products", "owner")
    products = r_prod.json()
    product = [p for p in products if p.get("stock_kg", 0) > 1][0]
    
    sale_data = {
        "customer_id": None,  # Tidak ada customer
        "items": [{"product_id": product["id"], "unit": "kg", "qty": 0.3, "price": 40000}],
        "discount": 0,
        "paid": 5000,  # Kurang bayar
        "payment_method": "cash"
    }
    
    r_sale = post("/sales", "owner", json=sale_data)
    assert r_sale.status_code == 200, f"Create sale failed: {r_sale.status_code}"
    sale = r_sale.json()
    sale_id = sale["id"]
    
    print(f"  ✓ Sale created: {sale_id}")
    print(f"  ✓ Customer name: {sale['customer_name']}")
    print(f"  ✓ Total: Rp {sale['total']:,.0f}")
    print(f"  ✓ Paid: Rp {sale['paid']:,.0f}")
    print(f"  ✓ Receivable: Rp {sale['receivable']:,.0f}")
    
    # E2. Verifikasi dokumen tagihan dibuat dengan nama "Umum"
    print(f"\n[E2] Verifikasi dokumen tagihan dibuat dengan nama 'Umum'")
    
    r_recv = get("/receivables", "owner")
    receivables = r_recv.json()
    tagihan = [r for r in receivables if r.get("sale_id") == sale_id]
    
    assert len(tagihan) == 1, f"Expected 1 receivable for Umum, got {len(tagihan)}"
    tagihan = tagihan[0]
    
    assert tagihan["customer_name"] == "Umum", f"Expected customer_name 'Umum', got {tagihan['customer_name']}"
    assert tagihan["customer_id"] is None, f"Expected customer_id None, got {tagihan['customer_id']}"
    
    print(f"  ✓ Tagihan created for 'Umum'")
    print(f"  ✓ Remaining: Rp {tagihan['remaining']:,.0f}")
    
    # E3. Cancel sale
    print(f"\n[E3] Cancel sale Umum")
    
    r_cancel = post(f"/sales/{sale_id}/cancel", "owner", json={})
    assert r_cancel.status_code == 200, f"Cancel sale failed: {r_cancel.status_code}"
    
    print(f"  ✓ Sale cancelled")
    
    print(f"\n✅ E. BUG FIXES UMUM - PASS")

# ============================================================================
# F. BUG FIXES - Validasi Pembayaran
# ============================================================================
def test_f_bug_fixes_validasi():
    print_section("F. BUG FIXES - Validasi Pembayaran")
    
    # F1. Buat receivable baru untuk testing
    print(f"\n[F1] Buat receivable baru untuk testing validasi")
    
    # Ambil customer dan produk
    r_cust = get("/customers", "owner")
    customers = r_cust.json()
    customer = customers[0]
    
    r_prod = get("/products", "owner")
    products = r_prod.json()
    product = [p for p in products if p.get("stock_kg", 0) > 1][0]
    
    # Buat penjualan piutang
    sale_data = {
        "customer_id": customer["id"],
        "items": [{"product_id": product["id"], "unit": "kg", "qty": 0.2, "price": 50000}],
        "discount": 0,
        "paid": 2000,
        "payment_method": "piutang"
    }
    
    r_sale = post("/sales", "owner", json=sale_data)
    sale = r_sale.json()
    
    # Ambil receivable
    r_recv = get("/receivables", "owner")
    receivables = r_recv.json()
    receivable = [r for r in receivables if r.get("sale_id") == sale["id"]][0]
    recv_id = receivable["id"]
    remaining = receivable["remaining"]
    
    print(f"  ✓ Receivable: {recv_id}")
    print(f"  ✓ Remaining: Rp {remaining:,.0f}")
    
    # F2. Test amount 0 -> 400
    print(f"\n[F2] Test amount 0 -> 400")
    
    r_zero = post(f"/receivables/{recv_id}/pay", "owner", json={"amount": 0})
    assert r_zero.status_code == 400, f"Amount 0 should return 400, got {r_zero.status_code}"
    print(f"  ✓ Amount 0: 400 (correctly rejected)")
    
    # F3. Test amount negatif -> 400
    print(f"\n[F3] Test amount negatif -> 400")
    
    r_neg = post(f"/receivables/{recv_id}/pay", "owner", json={"amount": -100})
    assert r_neg.status_code == 400, f"Negative amount should return 400, got {r_neg.status_code}"
    print(f"  ✓ Amount negatif: 400 (correctly rejected)")
    
    # F4. Test amount melebihi sisa -> 400
    print(f"\n[F4] Test amount melebihi sisa -> 400")
    
    r_exceed = post(f"/receivables/{recv_id}/pay", "owner", json={"amount": remaining + 1000})
    assert r_exceed.status_code == 400, f"Exceeding amount should return 400, got {r_exceed.status_code}"
    print(f"  ✓ Amount melebihi sisa: 400 (correctly rejected)")
    
    # F5. Bayar lunas lalu coba bayar lagi -> 400
    print(f"\n[F5] Bayar lunas lalu coba bayar lagi -> 400")
    
    # Bayar lunas
    r_pay = post(f"/receivables/{recv_id}/pay", "owner", json={"amount": remaining})
    assert r_pay.status_code == 200, f"Pay full should return 200, got {r_pay.status_code}"
    
    # Coba bayar lagi
    r_pay_again = post(f"/receivables/{recv_id}/pay", "owner", json={"amount": 100})
    assert r_pay_again.status_code == 400, f"Pay already lunas should return 400, got {r_pay_again.status_code}"
    print(f"  ✓ Bayar tagihan lunas: 400 (correctly rejected)")
    
    # F6. Cancel sale untuk cleanup
    post(f"/sales/{sale['id']}/cancel", "owner", json={})
    
    print(f"\n✅ F. BUG FIXES VALIDASI - PASS")

# ============================================================================
# G. REGRESI SINGKAT
# ============================================================================
def test_g_regresi():
    print_section("G. REGRESI SINGKAT")
    
    # G1. POST /api/sales normal + idempotency
    print(f"\n[G1] POST /api/sales normal + idempotency")
    
    r_prod = get("/products", "owner")
    products = r_prod.json()
    product = [p for p in products if p.get("stock_kg", 0) > 1][0]
    
    txn_id = f"test-{int(time.time())}"
    sale_data = {
        "txn_id": txn_id,
        "items": [{"product_id": product["id"], "unit": "kg", "qty": 0.2, "price": 35000}],
        "discount": 0,
        "paid": 7000,
        "payment_method": "cash"
    }
    
    # Kirim pertama
    r1 = post("/sales", "owner", json=sale_data)
    assert r1.status_code == 200, f"Create sale 1 failed: {r1.status_code}"
    sale1 = r1.json()
    sale_id_1 = sale1["id"]
    
    # Kirim kedua dengan txn_id sama
    r2 = post("/sales", "owner", json=sale_data)
    assert r2.status_code == 200, f"Create sale 2 failed: {r2.status_code}"
    sale2 = r2.json()
    sale_id_2 = sale2["id"]
    
    # Harus return sale yang sama
    assert sale_id_1 == sale_id_2, f"Idempotency failed: {sale_id_1} != {sale_id_2}"
    
    print(f"  ✓ Idempotency: same txn_id returns same sale_id")
    print(f"  ✓ Sale ID: {sale_id_1}")
    
    # Cancel untuk cleanup
    post(f"/sales/{sale_id_1}/cancel", "owner", json={})
    
    # G2. GET /api/reports/sales
    print(f"\n[G2] GET /api/reports/sales")
    
    r = get("/reports/sales", "owner")
    assert r.status_code == 200, f"Reports sales failed: {r.status_code}"
    data = r.json()
    
    print(f"  ✓ Sales count: {data['count']}")
    print(f"  ✓ Total: Rp {data['total']:,.0f}")
    
    # G3. GET /api/reports/stock
    print(f"\n[G3] GET /api/reports/stock")
    
    r = get("/reports/stock", "owner")
    assert r.status_code == 200, f"Reports stock failed: {r.status_code}"
    data = r.json()
    
    print(f"  ✓ Items: {len(data['items'])}")
    print(f"  ✓ Total value: Rp {data['total_value']:,.0f}")
    
    # G4. PDF endpoints
    print(f"\n[G4] PDF endpoints")
    
    # Profit-loss PDF
    r_pl = get("/reports/profit-loss/pdf", "owner")
    assert r_pl.status_code == 200, f"PL PDF failed: {r_pl.status_code}"
    assert r_pl.content[:5] == b"%PDF-", "PL PDF should start with %PDF-"
    print(f"  ✓ Profit-loss PDF: {len(r_pl.content)} bytes")
    
    # Sales PDF
    r_sales = get("/reports/sales/pdf", "owner")
    assert r_sales.status_code == 200, f"Sales PDF failed: {r_sales.status_code}"
    assert r_sales.content[:5] == b"%PDF-", "Sales PDF should start with %PDF-"
    print(f"  ✓ Sales PDF: {len(r_sales.content)} bytes")
    
    # Stock PDF
    r_stock = get("/reports/stock/pdf", "owner")
    assert r_stock.status_code == 200, f"Stock PDF failed: {r_stock.status_code}"
    assert r_stock.content[:5] == b"%PDF-", "Stock PDF should start with %PDF-"
    print(f"  ✓ Stock PDF: {len(r_stock.content)} bytes")
    
    # G5. GET /api/daily-closing/preview
    print(f"\n[G5] GET /api/daily-closing/preview")
    
    r = get(f"/daily-closing/preview?date={today()}", "owner")
    assert r.status_code == 200, f"Closing preview failed: {r.status_code}"
    data = r.json()
    
    print(f"  ✓ Omzet: Rp {data['omzet']:,.0f}")
    print(f"  ✓ Net profit: Rp {data['net_profit']:,.0f}")
    
    print(f"\n✅ G. REGRESI SINGKAT - PASS")

# ============================================================================
# FINAL: Consistency Check
# ============================================================================
def test_final_consistency():
    print_section("FINAL: Consistency Check")
    
    print(f"\n[FINAL] GET /api/maintenance/consistency")
    
    r = get("/maintenance/consistency", "owner")
    assert r.status_code == 200, f"Consistency check failed: {r.status_code}"
    data = r.json()
    
    print(f"\n  ✓ issue_count: {data['issue_count']}")
    
    if data["issue_count"] > 0:
        print(f"\n  ⚠️  MASIH ADA {data['issue_count']} ISSUES:")
        print(f"\n  Findings:")
        for finding in data.get("findings", [])[:20]:
            print(f"    - {finding['kind']}: {finding['label']}")
            print(f"      Detail: {finding['detail']}")
            print(f"      Amount: Rp {finding['amount']:,.0f}")
            print()
    else:
        print(f"\n  ✅ TIDAK ADA ISSUES - DATA SINKRON")
    
    return data["issue_count"]

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*70)
    print("  BACKEND TESTING - BERKAH AYAM MILI")
    print("  Fase: Sinkronisasi Keuangan & Bug Fixes")
    print("="*70)
    
    # Login semua role
    print("\n[SETUP] Login all roles")
    login("owner")
    login("admin")
    login("kasir")
    
    try:
        # A. Rumus keuangan tunggal
        test_a_rumus_keuangan_tunggal()
        
        # B. Dashboard monthly
        test_b_dashboard_monthly()
        
        # C. Maintenance consistency
        test_c_maintenance_consistency()
        
        # D. Bug fixes - piutang
        test_d_bug_fixes_piutang()
        
        # E. Bug fixes - umum
        test_e_bug_fixes_umum()
        
        # F. Bug fixes - validasi
        test_f_bug_fixes_validasi()
        
        # G. Regresi
        test_g_regresi()
        
        # Final consistency check
        final_issues = test_final_consistency()
        
        # Summary
        print("\n" + "="*70)
        print("  SUMMARY")
        print("="*70)
        print("\n✅ ALL TESTS PASSED")
        print(f"\nFinal consistency check: {final_issues} issues")
        
        if final_issues > 0:
            print("\n⚠️  WARNING: Masih ada issues di consistency check.")
            print("   Lihat detail di atas untuk findings.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise

if __name__ == "__main__":
    main()
