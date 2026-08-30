#!/usr/bin/env python3
"""
Test 3 perubahan backend baru untuk Berkah Ayam Mili (2026-08-30):
1. GET /api/sales dibatasi 7 hari untuk KASIR + endpoint /api/sales/access
2. Pengeluaran per akun (kasir hanya lihat milik sendiri, owner lihat semua)
3. Laporan bulanan baru /api/reports/monthly & /api/reports/monthly/pdf

Backend URL: https://github-app-launcher.preview.emergentagent.com/api
Credentials:
- Owner: shezrofenia18@gmail.com / berkahayam1
- Kasir: kasir@berkahayam.com / kasir123
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Optional

BASE_URL = "https://github-app-launcher.preview.emergentagent.com/api"

# ============================================================================
# Helper Functions
# ============================================================================

def login(email: str, password: str) -> str:
    """Login dan return token JWT"""
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data, f"No token in response: {data}"
    return data["token"]

def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def today_wib() -> str:
    """Hari ini dalam WIB (UTC+7)"""
    from datetime import timezone
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib).date().isoformat()

def days_ago_wib(n: int) -> str:
    """n hari yang lalu dalam WIB"""
    from datetime import timezone
    wib = timezone(timedelta(hours=7))
    return (datetime.now(wib).date() - timedelta(days=n)).isoformat()

def current_month_wib() -> str:
    """Bulan berjalan YYYY-MM dalam WIB"""
    from datetime import timezone
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib).strftime("%Y-%m")

def prev_month_wib() -> str:
    """Bulan lalu YYYY-MM dalam WIB"""
    from datetime import timezone
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)
    m = now.month - 1
    y = now.year
    if m == 0:
        m, y = 12, y - 1
    return f"{y:04d}-{m:02d}"

def month_bounds(ym: str) -> tuple:
    """Return (start_date, end_date) untuk bulan YYYY-MM"""
    y, m = int(ym[:4]), int(ym[5:7])
    start = f"{y:04d}-{m:02d}-01"
    # end date: last day of month
    if m == 12:
        next_y, next_m = y + 1, 1
    else:
        next_y, next_m = y, m + 1
    from datetime import date
    end = (date(next_y, next_m, 1) - timedelta(days=1)).isoformat()
    return start, end

# ============================================================================
# Test 1: GET /api/sales dibatasi 7 hari untuk KASIR
# ============================================================================

def test_1_sales_7day_limit():
    print("\n" + "="*80)
    print("TEST 1: GET /api/sales dibatasi 7 hari untuk KASIR")
    print("="*80)
    
    owner_token = login("shezrofenia18@gmail.com", "berkahayam1")
    kasir_token = login("kasir@berkahayam.com", "kasir123")
    
    today = today_wib()
    day_20_ago = days_ago_wib(20)
    day_30_ago = days_ago_wib(30)
    min_date_7days = days_ago_wib(6)  # 7 hari terakhir = hari ini - 6 hari
    
    print(f"\n📅 Today (WIB): {today}")
    print(f"📅 Min date for 7-day limit: {min_date_7days}")
    print(f"📅 20 days ago: {day_20_ago}")
    print(f"📅 30 days ago: {day_30_ago}")
    
    # 1a. GET /api/sales/access sebagai KASIR
    print("\n--- 1a. GET /api/sales/access sebagai KASIR ---")
    r = requests.get(f"{BASE_URL}/sales/access", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    access = r.json()
    print(f"✅ Kasir access: {json.dumps(access, indent=2)}")
    assert access["limited"] == True, f"Expected limited=True, got {access['limited']}"
    assert access["days"] == 7, f"Expected days=7, got {access['days']}"
    assert access["min_date"] == min_date_7days, f"Expected min_date={min_date_7days}, got {access['min_date']}"
    
    # 1b. GET /api/sales/access sebagai OWNER
    print("\n--- 1b. GET /api/sales/access sebagai OWNER ---")
    r = requests.get(f"{BASE_URL}/sales/access", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    access = r.json()
    print(f"✅ Owner access: {json.dumps(access, indent=2)}")
    assert access["limited"] == False, f"Expected limited=False, got {access['limited']}"
    assert access["days"] is None, f"Expected days=None, got {access['days']}"
    
    # 1c. GET /api/sales sebagai KASIR tanpa ?date (harus dibatasi 7 hari)
    print("\n--- 1c. GET /api/sales sebagai KASIR tanpa ?date ---")
    r = requests.get(f"{BASE_URL}/sales", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_kasir = r.json()
    print(f"✅ Kasir sales count: {len(sales_kasir)}")
    
    # Verifikasi SEMUA hasil harus date >= min_date_7days DAN cashier_id = kasir
    kasir_user = requests.get(f"{BASE_URL}/auth/me", headers=headers(kasir_token)).json()
    kasir_id = kasir_user["id"]
    print(f"   Kasir ID: {kasir_id}")
    
    for sale in sales_kasir:
        sale_date = sale.get("date", "")
        sale_cashier = sale.get("cashier_id", "")
        assert sale_date >= min_date_7days, f"❌ Sale {sale['id']} date {sale_date} < {min_date_7days}"
        assert sale_cashier == kasir_id, f"❌ Sale {sale['id']} cashier_id {sale_cashier} != {kasir_id}"
    
    print(f"✅ All {len(sales_kasir)} sales have date >= {min_date_7days} and cashier_id = {kasir_id}")
    
    # 1d. GET /api/sales?date=<20-30 hari lalu> sebagai KASIR (harus return [])
    print(f"\n--- 1d. GET /api/sales?date={day_20_ago} sebagai KASIR ---")
    r = requests.get(f"{BASE_URL}/sales?date={day_20_ago}", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_old = r.json()
    print(f"✅ Result: {sales_old}")
    assert sales_old == [], f"Expected empty array [], got {sales_old}"
    
    print(f"\n--- 1e. GET /api/sales?date={day_30_ago} sebagai KASIR ---")
    r = requests.get(f"{BASE_URL}/sales?date={day_30_ago}", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_old = r.json()
    print(f"✅ Result: {sales_old}")
    assert sales_old == [], f"Expected empty array [], got {sales_old}"
    
    # 1f. GET /api/sales?date=<hari ini> sebagai KASIR (boleh berisi data)
    print(f"\n--- 1f. GET /api/sales?date={today} sebagai KASIR ---")
    r = requests.get(f"{BASE_URL}/sales?date={today}", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_today = r.json()
    print(f"✅ Today sales count: {len(sales_today)}")
    
    # 1g. REGRESI PENTING: GET /api/sales sebagai OWNER tanpa date harus TIDAK dibatasi 7 hari
    print("\n--- 1g. GET /api/sales sebagai OWNER tanpa ?date (REGRESI) ---")
    r = requests.get(f"{BASE_URL}/sales", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_owner = r.json()
    print(f"✅ Owner sales count: {len(sales_owner)}")
    
    # Verifikasi owner TIDAK dibatasi 7 hari (bisa lihat semua tanggal)
    # Cek apakah ada transaksi di luar 7 hari terakhir
    old_sales = [s for s in sales_owner if s.get("date", "") < min_date_7days]
    print(f"   Owner has {len(old_sales)} sales older than 7 days (date < {min_date_7days})")
    
    # Yang penting: owner harus bisa lihat LEBIH BANYAK dari kasir (karena tidak dibatasi)
    # Kasir hanya lihat transaksi sendiri dalam 7 hari, owner lihat SEMUA transaksi
    assert len(sales_owner) >= len(sales_kasir), f"❌ Owner sales {len(sales_owner)} < kasir sales {len(sales_kasir)}"
    print(f"✅ Owner NOT limited: sees {len(sales_owner)} sales (kasir only sees {len(sales_kasir)})")
    
    # Test dengan tanggal lama: owner harus bisa query tanggal lama (tidak return [])
    print(f"\n--- 1h. GET /api/sales?date={day_20_ago} sebagai OWNER (should work) ---")
    r = requests.get(f"{BASE_URL}/sales?date={day_20_ago}", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    sales_owner_old = r.json()
    print(f"✅ Owner can query old date {day_20_ago}: {len(sales_owner_old)} sales (may be empty if no data)")
    # Owner tidak dibatasi, jadi harus return 200 (bukan error), meskipun mungkin kosong
    
    print("\n✅ TEST 1 PASSED: Sales 7-day limit for KASIR working correctly")
    print(f"   - Kasir limited to 7 days: {len(sales_kasir)} sales")
    print(f"   - Kasir query old date returns []")
    print(f"   - Owner NOT limited: {len(sales_owner)} sales (can query any date)")

# ============================================================================
# Test 2: Pengeluaran per akun (kasir hanya lihat milik sendiri)
# ============================================================================

def test_2_expenses_per_account():
    print("\n" + "="*80)
    print("TEST 2: Pengeluaran per akun (kasir hanya lihat milik sendiri)")
    print("="*80)
    
    owner_token = login("shezrofenia18@gmail.com", "berkahayam1")
    kasir_token = login("kasir@berkahayam.com", "kasir123")
    
    # 2a. GET /api/reports/profit-loss & /api/dashboard sebagai owner SEBELUM
    print("\n--- 2a. Baseline: profit-loss & dashboard SEBELUM pengeluaran kasir ---")
    r = requests.get(f"{BASE_URL}/reports/profit-loss?start={today_wib()}&end={today_wib()}", 
                     headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    pl_before = r.json()
    opex_before = pl_before.get("opex", 0)
    expense_total_before = pl_before.get("expense_total", 0)
    net_profit_before = pl_before.get("net_profit", 0)
    print(f"   Profit-loss BEFORE: opex={opex_before}, expense_total={expense_total_before}, net_profit={net_profit_before}")
    
    r = requests.get(f"{BASE_URL}/dashboard", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    dash_before = r.json()
    dash_opex_before = dash_before.get("opex", 0)
    dash_expense_before = dash_before.get("expense", 0)  # field lama = opex
    print(f"   Dashboard BEFORE: opex={dash_opex_before}, expense={dash_expense_before}")
    
    # 2b. Login kasir, POST /api/expenses
    print("\n--- 2b. POST /api/expenses sebagai KASIR ---")
    expense_body = {
        "category": "Es",
        "amount": 15000,
        "description": "uji agent - pengeluaran kasir"
    }
    r = requests.post(f"{BASE_URL}/expenses", json=expense_body, headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    expense_created = r.json()
    expense_id = expense_created["id"]
    print(f"✅ Expense created: id={expense_id}, amount={expense_created['amount']}")
    print(f"   created_by={expense_created.get('created_by')}, created_by_id={expense_created.get('created_by_id')}")
    
    # 2c. GET /api/expenses sebagai KASIR (hanya milik sendiri)
    print("\n--- 2c. GET /api/expenses sebagai KASIR ---")
    r = requests.get(f"{BASE_URL}/expenses", headers=headers(kasir_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    expenses_kasir = r.json()
    print(f"✅ Kasir expenses count: {len(expenses_kasir)}")
    
    # Verifikasi HANYA berisi pengeluaran kasir (tidak ada "Pembelian Ayam", tidak ada pengeluaran owner)
    kasir_user = requests.get(f"{BASE_URL}/auth/me", headers=headers(kasir_token)).json()
    kasir_id = kasir_user["id"]
    kasir_name = kasir_user["name"]
    
    for exp in expenses_kasir:
        created_by_id = exp.get("created_by_id")
        created_by = exp.get("created_by")
        # Harus milik kasir (by id atau by name untuk dokumen lama)
        is_kasir = (created_by_id == kasir_id) or (created_by == kasir_name)
        assert is_kasir, f"❌ Expense {exp['id']} bukan milik kasir: created_by_id={created_by_id}, created_by={created_by}"
    
    print(f"✅ All {len(expenses_kasir)} expenses belong to kasir (created_by_id={kasir_id} or created_by={kasir_name})")
    
    # Verifikasi TIDAK ADA "Pembelian Ayam"
    pembelian_ayam = [e for e in expenses_kasir if e.get("category") == "Pembelian Ayam"]
    assert len(pembelian_ayam) == 0, f"❌ Kasir should NOT see 'Pembelian Ayam', found {len(pembelian_ayam)}"
    print(f"✅ Kasir does NOT see 'Pembelian Ayam' (correct)")
    
    # Verifikasi pengeluaran yang baru dibuat ada di list
    found = [e for e in expenses_kasir if e["id"] == expense_id]
    assert len(found) == 1, f"❌ Expense {expense_id} not found in kasir's list"
    print(f"✅ Newly created expense {expense_id} found in kasir's list")
    
    # 2d. GET /api/expenses sebagai OWNER (harus memuat SEMUA termasuk kasir)
    print("\n--- 2d. GET /api/expenses sebagai OWNER ---")
    r = requests.get(f"{BASE_URL}/expenses", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    expenses_owner = r.json()
    print(f"✅ Owner expenses count: {len(expenses_owner)}")
    
    # Verifikasi pengeluaran kasir tadi ADA di list owner
    found_in_owner = [e for e in expenses_owner if e["id"] == expense_id]
    assert len(found_in_owner) == 1, f"❌ Expense {expense_id} NOT found in owner's list"
    print(f"✅ Kasir's expense {expense_id} found in owner's list")
    
    # Verifikasi ada "Pembelian Ayam" di list owner
    pembelian_ayam_owner = [e for e in expenses_owner if e.get("category") == "Pembelian Ayam"]
    print(f"✅ Owner sees {len(pembelian_ayam_owner)} 'Pembelian Ayam' expenses")
    
    # 2e. REGRESI: profit-loss & dashboard owner SETELAH (harus bertambah 15000)
    print("\n--- 2e. REGRESI: profit-loss & dashboard SETELAH pengeluaran kasir ---")
    r = requests.get(f"{BASE_URL}/reports/profit-loss?start={today_wib()}&end={today_wib()}", 
                     headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    pl_after = r.json()
    opex_after = pl_after.get("opex", 0)
    expense_total_after = pl_after.get("expense_total", 0)
    net_profit_after = pl_after.get("net_profit", 0)
    print(f"   Profit-loss AFTER: opex={opex_after}, expense_total={expense_total_after}, net_profit={net_profit_after}")
    
    r = requests.get(f"{BASE_URL}/dashboard", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    dash_after = r.json()
    dash_opex_after = dash_after.get("opex", 0)
    dash_expense_after = dash_after.get("expense", 0)
    print(f"   Dashboard AFTER: opex={dash_opex_after}, expense={dash_expense_after}")
    
    # Verifikasi opex/expense bertambah tepat 15000
    opex_delta = opex_after - opex_before
    expense_total_delta = expense_total_after - expense_total_before
    dash_opex_delta = dash_opex_after - dash_opex_before
    
    print(f"\n   Delta opex (profit-loss): {opex_delta} (expected 15000)")
    print(f"   Delta expense_total (profit-loss): {expense_total_delta} (expected 15000)")
    print(f"   Delta opex (dashboard): {dash_opex_delta} (expected 15000)")
    
    assert abs(opex_delta - 15000) <= 1, f"❌ REGRESI: opex delta {opex_delta} != 15000"
    assert abs(expense_total_delta - 15000) <= 1, f"❌ REGRESI: expense_total delta {expense_total_delta} != 15000"
    assert abs(dash_opex_delta - 15000) <= 1, f"❌ REGRESI: dashboard opex delta {dash_opex_delta} != 15000"
    
    print(f"✅ REGRESI PASSED: opex/expense bertambah tepat 15000 (pengeluaran kasir masuk pembukuan owner)")
    
    # 2f. Report test expense (no DELETE endpoint available)
    print(f"\n--- 2f. Test expense created (for manual cleanup if needed) ---")
    print(f"   Expense ID: {expense_id}")
    print(f"   Category: Es, Amount: 15000, Description: 'uji agent - pengeluaran kasir'")
    print(f"   Note: No DELETE endpoint available, expense remains in database")
    
    print("\n✅ TEST 2 PASSED: Expenses per account working correctly")
    print(f"   - Kasir only sees own expenses: {len(expenses_kasir)} items")
    print(f"   - Owner sees all expenses: {len(expenses_owner)} items (including kasir's)")
    print(f"   - Kasir's expense correctly added to owner's profit-loss & dashboard")
    print(f"   - Test expense ID: {expense_id} (category: Es, amount: 15000)")

# ============================================================================
# Test 3: Laporan bulanan /api/reports/monthly & /api/reports/monthly/pdf
# ============================================================================

def test_3_monthly_report():
    print("\n" + "="*80)
    print("TEST 3: Laporan bulanan /api/reports/monthly & /api/reports/monthly/pdf")
    print("="*80)
    
    owner_token = login("shezrofenia18@gmail.com", "berkahayam1")
    kasir_token = login("kasir@berkahayam.com", "kasir123")
    
    current_month = current_month_wib()
    prev_month = prev_month_wib()
    
    print(f"\n📅 Current month (WIB): {current_month}")
    print(f"📅 Previous month (WIB): {prev_month}")
    
    # 3a. GET /api/reports/monthly (tanpa param) sebagai OWNER
    print("\n--- 3a. GET /api/reports/monthly (tanpa param) sebagai OWNER ---")
    r = requests.get(f"{BASE_URL}/reports/monthly", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    monthly = r.json()
    print(f"✅ Monthly report received")
    
    # Verifikasi field wajib
    required_fields = ["month", "label", "start", "end", "omzet", "hpp", "gross_profit", 
                       "opex", "net_profit", "daily", "products", "prev", "growth"]
    for field in required_fields:
        assert field in monthly, f"❌ Missing field: {field}"
    print(f"✅ All required fields present: {', '.join(required_fields)}")
    
    # Verifikasi bulan = current month
    assert monthly["month"] == current_month, f"Expected month={current_month}, got {monthly['month']}"
    print(f"✅ Month: {monthly['month']} (correct)")
    
    # Verifikasi konsistensi angka
    omzet = monthly["omzet"]
    hpp = monthly["hpp"]
    gross_profit = monthly["gross_profit"]
    opex = monthly["opex"]
    net_profit = monthly["net_profit"]
    daily = monthly["daily"]
    txn_count = monthly["txn_count"]
    
    print(f"\n   Omzet: Rp {omzet:,.0f}")
    print(f"   HPP: Rp {hpp:,.0f}")
    print(f"   Gross Profit: Rp {gross_profit:,.0f}")
    print(f"   Opex: Rp {opex:,.0f}")
    print(f"   Net Profit: Rp {net_profit:,.0f}")
    print(f"   Txn Count: {txn_count}")
    print(f"   Daily entries: {len(daily)}")
    
    # Konsistensi 1: gross_profit == omzet - hpp
    assert abs(gross_profit - (omzet - hpp)) <= 1, f"❌ gross_profit {gross_profit} != omzet {omzet} - hpp {hpp}"
    print(f"✅ Konsistensi: gross_profit == omzet - hpp")
    
    # Konsistensi 2: net_profit == gross_profit - opex
    assert abs(net_profit - (gross_profit - opex)) <= 1, f"❌ net_profit {net_profit} != gross_profit {gross_profit} - opex {opex}"
    print(f"✅ Konsistensi: net_profit == gross_profit - opex")
    
    # Konsistensi 3: sum(daily[].omzet) == omzet (toleransi 1 rupiah)
    daily_omzet_sum = sum(d["omzet"] for d in daily)
    assert abs(daily_omzet_sum - omzet) <= 1, f"❌ sum(daily.omzet) {daily_omzet_sum} != omzet {omzet}"
    print(f"✅ Konsistensi: sum(daily[].omzet) == omzet (sum={daily_omzet_sum}, omzet={omzet})")
    
    # Konsistensi 4: sum(daily[].txn_count) == txn_count
    daily_txn_sum = sum(d["txn_count"] for d in daily)
    assert daily_txn_sum == txn_count, f"❌ sum(daily.txn_count) {daily_txn_sum} != txn_count {txn_count}"
    print(f"✅ Konsistensi: sum(daily[].txn_count) == txn_count (sum={daily_txn_sum}, txn_count={txn_count})")
    
    # Verifikasi prev & growth
    prev_data = monthly["prev"]
    growth_data = monthly["growth"]
    print(f"\n   Prev month: {prev_data.get('month')}, omzet={prev_data.get('omzet', 0):,.0f}, net_profit={prev_data.get('net_profit', 0):,.0f}")
    print(f"   Growth: omzet={growth_data.get('omzet')}%, net_profit={growth_data.get('net_profit')}%")
    
    # 3b. GET /api/reports/monthly?month=<bulan lalu>
    print(f"\n--- 3b. GET /api/reports/monthly?month={prev_month} ---")
    r = requests.get(f"{BASE_URL}/reports/monthly?month={prev_month}", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    monthly_prev = r.json()
    print(f"✅ Previous month report received: month={monthly_prev['month']}")
    assert monthly_prev["month"] == prev_month, f"Expected month={prev_month}, got {monthly_prev['month']}"
    
    # 3c. GET /api/reports/monthly?month=abc (invalid) -> 400
    print("\n--- 3c. GET /api/reports/monthly?month=abc (invalid) ---")
    r = requests.get(f"{BASE_URL}/reports/monthly?month=abc", headers=headers(owner_token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    print(f"✅ Invalid month 'abc' rejected with 400")
    
    # 3d. GET /api/reports/monthly?month=2026-13 (invalid) -> 400
    print("\n--- 3d. GET /api/reports/monthly?month=2026-13 (invalid) ---")
    r = requests.get(f"{BASE_URL}/reports/monthly?month=2026-13", headers=headers(owner_token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    print(f"✅ Invalid month '2026-13' rejected with 400")
    
    # 3e. Cross-check: /api/reports/profit-loss?start=<start>&end=<end> harus sama
    print(f"\n--- 3e. Cross-check: /api/reports/profit-loss vs /api/reports/monthly ---")
    start_date, end_date = month_bounds(current_month)
    r = requests.get(f"{BASE_URL}/reports/profit-loss?start={start_date}&end={end_date}", 
                     headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    pl = r.json()
    
    pl_omzet = pl.get("omzet", 0)
    pl_hpp = pl.get("hpp", 0)
    pl_net_profit = pl.get("net_profit", 0)
    
    print(f"   Profit-loss: omzet={pl_omzet:,.0f}, hpp={pl_hpp:,.0f}, net_profit={pl_net_profit:,.0f}")
    print(f"   Monthly:     omzet={omzet:,.0f}, hpp={hpp:,.0f}, net_profit={net_profit:,.0f}")
    
    assert abs(pl_omzet - omzet) <= 1, f"❌ profit-loss omzet {pl_omzet} != monthly omzet {omzet}"
    assert abs(pl_hpp - hpp) <= 1, f"❌ profit-loss hpp {pl_hpp} != monthly hpp {hpp}"
    assert abs(pl_net_profit - net_profit) <= 1, f"❌ profit-loss net_profit {pl_net_profit} != monthly net_profit {net_profit}"
    
    print(f"✅ Cross-check PASSED: profit-loss == monthly (same period)")
    
    # 3f. GET /api/reports/monthly/pdf sebagai OWNER
    print("\n--- 3f. GET /api/reports/monthly/pdf sebagai OWNER ---")
    r = requests.get(f"{BASE_URL}/reports/monthly/pdf", headers=headers(owner_token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    pdf_data = r.content
    print(f"✅ PDF received: {len(pdf_data)} bytes")
    
    # Verifikasi content-type
    content_type = r.headers.get("Content-Type", "")
    assert "application/pdf" in content_type, f"❌ Expected application/pdf, got {content_type}"
    print(f"✅ Content-Type: {content_type}")
    
    # Verifikasi ukuran > 1000 bytes
    assert len(pdf_data) > 1000, f"❌ PDF too small: {len(pdf_data)} bytes"
    print(f"✅ PDF size > 1000 bytes")
    
    # Verifikasi PDF header
    assert pdf_data[:4] == b'%PDF', f"❌ Invalid PDF header: {pdf_data[:4]}"
    print(f"✅ PDF header valid: {pdf_data[:4]}")
    
    # Verifikasi Content-Disposition
    content_disp = r.headers.get("Content-Disposition", "")
    assert "attachment" in content_disp, f"❌ Expected attachment, got {content_disp}"
    print(f"✅ Content-Disposition: {content_disp}")
    
    # 3g. GET /api/reports/monthly sebagai KASIR -> 403
    print("\n--- 3g. GET /api/reports/monthly sebagai KASIR (should be 403) ---")
    r = requests.get(f"{BASE_URL}/reports/monthly", headers=headers(kasir_token))
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    print(f"✅ Kasir correctly rejected with 403")
    
    # 3h. GET /api/reports/monthly/pdf sebagai KASIR -> 403
    print("\n--- 3h. GET /api/reports/monthly/pdf sebagai KASIR (should be 403) ---")
    r = requests.get(f"{BASE_URL}/reports/monthly/pdf", headers=headers(kasir_token))
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    print(f"✅ Kasir correctly rejected with 403")
    
    print("\n✅ TEST 3 PASSED: Monthly report working correctly")
    print(f"   - Monthly report fields complete and consistent")
    print(f"   - Cross-check with profit-loss: SAME values")
    print(f"   - PDF generation working: {len(pdf_data)} bytes")
    print(f"   - RBAC enforced: kasir 403")

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("BACKEND TESTING: 3 Perubahan Baru (2026-08-30)")
    print("Berkah Ayam Mili - FastAPI Backend")
    print("="*80)
    
    try:
        test_1_sales_7day_limit()
        test_2_expenses_per_account()
        test_3_monthly_report()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED (3/3)")
        print("="*80)
        print("\n1. ✅ Sales 7-day limit for KASIR + /api/sales/access")
        print("2. ✅ Expenses per account (kasir only sees own)")
        print("3. ✅ Monthly report + PDF")
        print("\n" + "="*80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
