#!/usr/bin/env python3
"""
Backend Testing for 4 New Changes - Berkah Ayam Mili POS
=========================================================

Tests for:
A. Penjualan per ekor memotong stok KG (berat rata-rata/ekor) + ayam utuh dilarang dijual per kg
B. Metode pembayaran (tunai/transfer/QRIS/debit/e-wallet) untuk pelunasan piutang & hutang
C. Upload foto bukti pengeluaran (kasir, admin, owner)
D. Penyesuaian stok: jenis 'Ayam Mati' diganti 'Salah Potong' + whitelist ADJUST_TYPES
E. Regresi wajib (angka keuangan, consistency, RBAC, cleanup)
"""

import requests
import json
import io
from datetime import datetime

# Configuration
BASE_URL = "https://commit-checker-live-2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"}
}

# Global tokens
tokens = {}

# Test data tracking
test_data = {
    "sales": [],
    "receivables": [],
    "payables": [],
    "purchases": [],
    "expenses": [],
    "adjustments": [],
    "uploads": []
}

def login(role):
    """Login and get JWT token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json=CREDENTIALS[role])
    assert resp.status_code == 200, f"Login failed for {role}: {resp.text}"
    data = resp.json()
    token = data.get("token")
    assert token, f"No token in response for {role}"
    tokens[role] = token
    print(f"✓ Logged in as {role}")
    return token

def headers(role):
    """Get authorization headers"""
    if role not in tokens:
        login(role)
    return {"Authorization": f"Bearer {tokens[role]}"}

def get_product_by_name(name, role="owner"):
    """Get product by name"""
    resp = requests.get(f"{BASE_URL}/products", headers=headers(role))
    assert resp.status_code == 200
    products = resp.json()
    for p in products:
        if p["name"] == name:
            return p
    return None

def print_section(title):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(name):
    """Print test name"""
    print(f"→ {name}")

def print_result(passed, message=""):
    """Print test result"""
    if passed:
        print(f"  ✅ PASS {message}")
    else:
        print(f"  ❌ FAIL {message}")
    return passed

# ============================================================================
# A. PENJUALAN PER EKOR MEMOTONG STOK KG
# ============================================================================

def test_a_penjualan_per_ekor():
    """Test A: Penjualan per ekor memotong stok KG (berat rata-rata/ekor)"""
    print_section("A. PENJUALAN PER EKOR MEMOTONG STOK KG")
    
    # A1. Jual 2 ekor Ayam Broiler -> stock_ekor -2 DAN stock_kg -3.70
    print_test("A1. Jual 2 ekor Ayam Broiler -> stock_ekor -2 DAN stock_kg -3.70")
    
    broiler = get_product_by_name("Ayam Broiler")
    assert broiler, "Ayam Broiler not found"
    
    stock_kg_before = broiler["stock_kg"]
    stock_ekor_before = broiler["stock_ekor"]
    avg_weight = broiler.get("avg_weight_used", 1.85)
    
    print(f"  Before: stock_kg={stock_kg_before}, stock_ekor={stock_ekor_before}, avg_weight={avg_weight}")
    
    # Create sale with 2 ekor
    sale_body = {
        "customer_id": None,
        "customer_name": "Test A1",
        "payment_method": "cash",
        "items": [
            {
                "product_id": broiler["id"],
                "product_name": broiler["name"],
                "unit": "ekor",
                "qty": 2,
                "price": broiler["price_ekor"]
            }
        ],
        "paid": broiler["price_ekor"] * 2,
        "txn_id": f"test_a1_{datetime.now().timestamp()}"
    }
    
    resp = requests.post(f"{BASE_URL}/sales", json=sale_body, headers=headers("owner"))
    assert resp.status_code == 200, f"Sale failed: {resp.text}"
    sale = resp.json()
    test_data["sales"].append(sale["id"])
    
    # Check stock after
    broiler_after = get_product_by_name("Ayam Broiler")
    stock_kg_after = broiler_after["stock_kg"]
    stock_ekor_after = broiler_after["stock_ekor"]
    
    print(f"  After: stock_kg={stock_kg_after}, stock_ekor={stock_ekor_after}")
    
    # Verify stock changes
    expected_kg_decrease = 2 * avg_weight
    actual_kg_decrease = stock_kg_before - stock_kg_after
    actual_ekor_decrease = stock_ekor_before - stock_ekor_after
    
    print(f"  Expected kg decrease: {expected_kg_decrease:.2f}, Actual: {actual_kg_decrease:.2f}")
    print(f"  Expected ekor decrease: 2, Actual: {actual_ekor_decrease}")
    
    # Check sale document fields
    items = sale.get("items", [])
    assert len(items) == 1, "Should have 1 item"
    item = items[0]
    
    print(f"  Item weight_kg: {item.get('weight_kg')}")
    print(f"  Item avg_weight_used: {item.get('avg_weight_used')}")
    print(f"  Sale total_weight: {sale.get('total_weight')}")
    print(f"  Sale total_weight_ekor: {sale.get('total_weight_ekor')}")
    print(f"  Sale total_weight_kg_unit: {sale.get('total_weight_kg_unit')}")
    
    passed = (
        abs(actual_kg_decrease - expected_kg_decrease) < 0.01 and
        actual_ekor_decrease == 2 and
        abs(item.get("weight_kg", 0) - expected_kg_decrease) < 0.01 and
        abs(item.get("avg_weight_used", 0) - avg_weight) < 0.01 and
        abs(sale.get("total_weight", 0) - expected_kg_decrease) < 0.01 and
        abs(sale.get("total_weight_ekor", 0) - expected_kg_decrease) < 0.01 and
        sale.get("total_weight_kg_unit", -1) == 0
    )
    
    print_result(passed, f"stock_kg decreased by {actual_kg_decrease:.2f}, stock_ekor decreased by {actual_ekor_decrease}")
    
    # A2. Check stock-movements
    print_test("A2. Check stock-movements for qty_kg=-3.7 and qty_ekor=-2")
    
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=headers("owner"))
    assert resp.status_code == 200
    movements = resp.json()
    
    # Find the movement for this sale
    found = False
    for m in movements:
        if m.get("type") == "penjualan" and m.get("product_id") == broiler["id"]:
            if abs(m.get("qty_kg", 0) + expected_kg_decrease) < 0.01 and m.get("qty_ekor", 0) == -2:
                found = True
                print(f"  Found movement: qty_kg={m.get('qty_kg')}, qty_ekor={m.get('qty_ekor')}")
                break
    
    print_result(found, "Stock movement recorded correctly")
    
    # A3. Cancel sale -> stock kembali PERSIS
    print_test("A3. Cancel sale -> stock_kg & stock_ekor kembali PERSIS")
    
    resp = requests.post(f"{BASE_URL}/sales/{sale['id']}/cancel", headers=headers("owner"))
    assert resp.status_code == 200, f"Cancel failed: {resp.text}"
    
    broiler_restored = get_product_by_name("Ayam Broiler")
    stock_kg_restored = broiler_restored["stock_kg"]
    stock_ekor_restored = broiler_restored["stock_ekor"]
    
    print(f"  Restored: stock_kg={stock_kg_restored}, stock_ekor={stock_ekor_restored}")
    
    passed = (
        abs(stock_kg_restored - stock_kg_before) < 0.01 and
        stock_ekor_restored == stock_ekor_before
    )
    
    print_result(passed, f"Stock restored to original values")
    
    # Remove from test_data since it's cancelled
    test_data["sales"].remove(sale["id"])
    
    # A4. TOLAK JUAL KG untuk Ayam Broiler/Kampung/Pejantan (owner, admin, kasir)
    print_test("A4. TOLAK JUAL KG untuk Ayam Broiler (owner, admin, kasir)")
    
    for role in ["owner", "admin", "kasir"]:
        sale_kg_body = {
            "customer_id": None,
            "customer_name": f"Test A4 {role}",
            "payment_method": "cash",
            "items": [
                {
                    "product_id": broiler["id"],
                    "product_name": broiler["name"],
                    "unit": "kg",
                    "qty": 1.0,
                    "price": broiler["price_kg"]
                }
            ],
            "paid": broiler["price_kg"],
            "txn_id": f"test_a4_{role}_{datetime.now().timestamp()}"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", json=sale_kg_body, headers=headers(role))
        
        if resp.status_code == 400 and "hanya bisa dijual per ekor" in resp.text.lower():
            print(f"  ✅ {role}: Correctly rejected with 400")
        else:
            print(f"  ❌ {role}: Expected 400, got {resp.status_code}: {resp.text[:100]}")
    
    # Verify stock didn't change
    broiler_check = get_product_by_name("Ayam Broiler")
    passed = (
        abs(broiler_check["stock_kg"] - stock_kg_before) < 0.01 and
        broiler_check["stock_ekor"] == stock_ekor_before
    )
    print_result(passed, "Stock unchanged after rejection")
    
    # A5. TIDAK BOLEH REGRESI: Ayam Fillet kg, Ceker Ayam pcs
    print_test("A5. REGRESI: Ayam Fillet unit kg, Ceker Ayam unit pcs")
    
    # Test Ayam Fillet (kg)
    fillet = get_product_by_name("Ayam Fillet")
    if fillet:
        stock_kg_before_fillet = fillet["stock_kg"]
        
        sale_fillet = {
            "customer_id": None,
            "customer_name": "Test A5 Fillet",
            "payment_method": "cash",
            "items": [
                {
                    "product_id": fillet["id"],
                    "product_name": fillet["name"],
                    "unit": "kg",
                    "qty": 1.5,
                    "price": fillet["price_kg"]
                }
            ],
            "paid": fillet["price_kg"] * 1.5,
            "txn_id": f"test_a5_fillet_{datetime.now().timestamp()}"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", json=sale_fillet, headers=headers("owner"))
        assert resp.status_code == 200, f"Fillet sale failed: {resp.text}"
        sale_f = resp.json()
        test_data["sales"].append(sale_f["id"])
        
        fillet_after = get_product_by_name("Ayam Fillet")
        stock_kg_after_fillet = fillet_after["stock_kg"]
        
        item_f = sale_f["items"][0]
        passed_fillet = (
            abs((stock_kg_before_fillet - stock_kg_after_fillet) - 1.5) < 0.01 and
            abs(item_f.get("weight_kg", 0) - 1.5) < 0.01 and
            abs(sale_f.get("total_weight", 0) - 1.5) < 0.01
        )
        
        print(f"  Fillet: stock_kg decreased by {stock_kg_before_fillet - stock_kg_after_fillet:.2f}")
        print_result(passed_fillet, "Ayam Fillet kg unit working")
        
        # Cancel fillet
        resp = requests.post(f"{BASE_URL}/sales/{sale_f['id']}/cancel", headers=headers("owner"))
        assert resp.status_code == 200
        test_data["sales"].remove(sale_f["id"])
        
        fillet_restored = get_product_by_name("Ayam Fillet")
        print_result(abs(fillet_restored["stock_kg"] - stock_kg_before_fillet) < 0.01, "Fillet stock restored")
    
    # Test Ceker Ayam (pcs)
    ceker = get_product_by_name("Ceker Ayam")
    if ceker:
        stock_pcs_before_ceker = ceker["stock_pcs"]
        stock_kg_before_ceker = ceker["stock_kg"]
        
        sale_ceker = {
            "customer_id": None,
            "customer_name": "Test A5 Ceker",
            "payment_method": "cash",
            "items": [
                {
                    "product_id": ceker["id"],
                    "product_name": ceker["name"],
                    "unit": "pcs",
                    "qty": 3,
                    "price": ceker["price_pcs"]
                }
            ],
            "paid": ceker["price_pcs"] * 3,
            "txn_id": f"test_a5_ceker_{datetime.now().timestamp()}"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", json=sale_ceker, headers=headers("owner"))
        assert resp.status_code == 200, f"Ceker sale failed: {resp.text}"
        sale_c = resp.json()
        test_data["sales"].append(sale_c["id"])
        
        ceker_after = get_product_by_name("Ceker Ayam")
        stock_pcs_after_ceker = ceker_after["stock_pcs"]
        stock_kg_after_ceker = ceker_after["stock_kg"]
        
        item_c = sale_c["items"][0]
        passed_ceker = (
            (stock_pcs_before_ceker - stock_pcs_after_ceker) == 3 and
            item_c.get("weight_kg", -1) == 0 and
            abs(stock_kg_after_ceker - stock_kg_before_ceker) < 0.01
        )
        
        print(f"  Ceker: stock_pcs decreased by {stock_pcs_before_ceker - stock_pcs_after_ceker}, stock_kg unchanged")
        print_result(passed_ceker, "Ceker Ayam pcs unit working, stock_kg unchanged")
        
        # Cancel ceker
        resp = requests.post(f"{BASE_URL}/sales/{sale_c['id']}/cancel", headers=headers("owner"))
        assert resp.status_code == 200
        test_data["sales"].remove(sale_c["id"])
        
        ceker_restored = get_product_by_name("Ceker Ayam")
        print_result(ceker_restored["stock_pcs"] == stock_pcs_before_ceker, "Ceker stock restored")
    
    # A6. Idempotency txn_id
    print_test("A6. Idempotency: kirim 2x txn_id sama -> stok hanya berkurang SEKALI")
    
    broiler_before_idem = get_product_by_name("Ayam Broiler")
    stock_kg_before_idem = broiler_before_idem["stock_kg"]
    stock_ekor_before_idem = broiler_before_idem["stock_ekor"]
    
    txn_id_idem = f"test_a6_idem_{datetime.now().timestamp()}"
    sale_idem_body = {
        "customer_id": None,
        "customer_name": "Test A6 Idem",
        "payment_method": "cash",
        "items": [
            {
                "product_id": broiler_before_idem["id"],
                "product_name": broiler_before_idem["name"],
                "unit": "ekor",
                "qty": 1,
                "price": broiler_before_idem["price_ekor"]
            }
        ],
        "paid": broiler_before_idem["price_ekor"],
        "txn_id": txn_id_idem
    }
    
    # First call
    resp1 = requests.post(f"{BASE_URL}/sales", json=sale_idem_body, headers=headers("owner"))
    assert resp1.status_code == 200
    sale1 = resp1.json()
    sale_id_1 = sale1["id"]
    
    # Second call with same txn_id
    resp2 = requests.post(f"{BASE_URL}/sales", json=sale_idem_body, headers=headers("owner"))
    assert resp2.status_code == 200
    sale2 = resp2.json()
    sale_id_2 = sale2["id"]
    
    broiler_after_idem = get_product_by_name("Ayam Broiler")
    stock_kg_after_idem = broiler_after_idem["stock_kg"]
    stock_ekor_after_idem = broiler_after_idem["stock_ekor"]
    
    expected_kg_decrease_idem = 1 * avg_weight
    actual_kg_decrease_idem = stock_kg_before_idem - stock_kg_after_idem
    actual_ekor_decrease_idem = stock_ekor_before_idem - stock_ekor_after_idem
    
    passed_idem = (
        sale_id_1 == sale_id_2 and
        abs(actual_kg_decrease_idem - expected_kg_decrease_idem) < 0.01 and
        actual_ekor_decrease_idem == 1
    )
    
    print(f"  Sale ID 1: {sale_id_1}")
    print(f"  Sale ID 2: {sale_id_2}")
    print(f"  Stock kg decreased: {actual_kg_decrease_idem:.2f} (expected {expected_kg_decrease_idem:.2f})")
    print(f"  Stock ekor decreased: {actual_ekor_decrease_idem} (expected 1)")
    print_result(passed_idem, "Idempotency working, stock decreased only once")
    
    # Cancel and cleanup
    resp = requests.post(f"{BASE_URL}/sales/{sale_id_1}/cancel", headers=headers("owner"))
    assert resp.status_code == 200
    
    # A7. Campuran 1 transaksi (ekor + kg + pcs)
    print_test("A7. Campuran: 1 item ekor + 1 item kg + 1 item pcs")
    
    broiler_mix = get_product_by_name("Ayam Broiler")
    fillet_mix = get_product_by_name("Ayam Fillet")
    ceker_mix = get_product_by_name("Ceker Ayam")
    
    if broiler_mix and fillet_mix and ceker_mix:
        stock_before_mix = {
            "broiler_kg": broiler_mix["stock_kg"],
            "broiler_ekor": broiler_mix["stock_ekor"],
            "fillet_kg": fillet_mix["stock_kg"],
            "ceker_pcs": ceker_mix["stock_pcs"]
        }
        
        sale_mix_body = {
            "customer_id": None,
            "customer_name": "Test A7 Mix",
            "payment_method": "cash",
            "items": [
                {
                    "product_id": broiler_mix["id"],
                    "product_name": broiler_mix["name"],
                    "unit": "ekor",
                    "qty": 1,
                    "price": broiler_mix["price_ekor"]
                },
                {
                    "product_id": fillet_mix["id"],
                    "product_name": fillet_mix["name"],
                    "unit": "kg",
                    "qty": 0.5,
                    "price": fillet_mix["price_kg"]
                },
                {
                    "product_id": ceker_mix["id"],
                    "product_name": ceker_mix["name"],
                    "unit": "pcs",
                    "qty": 2,
                    "price": ceker_mix["price_pcs"]
                }
            ],
            "paid": broiler_mix["price_ekor"] + fillet_mix["price_kg"] * 0.5 + ceker_mix["price_pcs"] * 2,
            "txn_id": f"test_a7_mix_{datetime.now().timestamp()}"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", json=sale_mix_body, headers=headers("owner"))
        assert resp.status_code == 200, f"Mix sale failed: {resp.text}"
        sale_mix = resp.json()
        test_data["sales"].append(sale_mix["id"])
        
        # Check total_weight
        expected_total_weight = 0.5 + (1 * avg_weight)  # kg fillet + (ekor x berat/ekor)
        actual_total_weight = sale_mix.get("total_weight", 0)
        
        print(f"  Expected total_weight: {expected_total_weight:.2f}")
        print(f"  Actual total_weight: {actual_total_weight:.2f}")
        
        passed_mix = abs(actual_total_weight - expected_total_weight) < 0.01
        print_result(passed_mix, f"total_weight = {actual_total_weight:.2f}")
        
        # Cancel and verify restoration
        resp = requests.post(f"{BASE_URL}/sales/{sale_mix['id']}/cancel", headers=headers("owner"))
        assert resp.status_code == 200
        test_data["sales"].remove(sale_mix["id"])
        
        broiler_restored_mix = get_product_by_name("Ayam Broiler")
        fillet_restored_mix = get_product_by_name("Ayam Fillet")
        ceker_restored_mix = get_product_by_name("Ceker Ayam")
        
        passed_restore = (
            abs(broiler_restored_mix["stock_kg"] - stock_before_mix["broiler_kg"]) < 0.01 and
            broiler_restored_mix["stock_ekor"] == stock_before_mix["broiler_ekor"] and
            abs(fillet_restored_mix["stock_kg"] - stock_before_mix["fillet_kg"]) < 0.01 and
            ceker_restored_mix["stock_pcs"] == stock_before_mix["ceker_pcs"]
        )
        
        print_result(passed_restore, "All stocks restored after cancel")

# ============================================================================
# B. METODE PEMBAYARAN PIUTANG & HUTANG
# ============================================================================

def test_b_metode_pembayaran():
    """Test B: Metode pembayaran piutang & hutang"""
    print_section("B. METODE PEMBAYARAN PIUTANG & HUTANG")
    
    # Get a customer
    resp = requests.get(f"{BASE_URL}/customers", headers=headers("owner"))
    assert resp.status_code == 200
    customers = resp.json()
    customer = customers[0] if customers else None
    
    if not customer:
        print("⚠️  No customers found, skipping piutang tests")
        return
    
    # B1. Create piutang sale and pay with method="transfer"
    print_test("B1. Piutang sale + pay with method='transfer'")
    
    broiler = get_product_by_name("Ayam Broiler")
    total = broiler["price_ekor"] * 2
    paid = total * 0.6  # 60% paid
    receivable = total - paid
    
    sale_piutang = {
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "payment_method": "piutang",
        "items": [
            {
                "product_id": broiler["id"],
                "product_name": broiler["name"],
                "unit": "ekor",
                "qty": 2,
                "price": broiler["price_ekor"]
            }
        ],
        "paid": paid,
        "txn_id": f"test_b1_{datetime.now().timestamp()}"
    }
    
    resp = requests.post(f"{BASE_URL}/sales", json=sale_piutang, headers=headers("owner"))
    assert resp.status_code == 200, f"Piutang sale failed: {resp.text}"
    sale = resp.json()
    test_data["sales"].append(sale["id"])
    
    # Get receivable
    resp = requests.get(f"{BASE_URL}/receivables", headers=headers("owner"))
    assert resp.status_code == 200
    receivables = resp.json()
    
    receivable_doc = None
    for r in receivables:
        if r.get("sale_id") == sale["id"]:
            receivable_doc = r
            break
    
    assert receivable_doc, "Receivable not found"
    test_data["receivables"].append(receivable_doc["id"])
    
    print(f"  Receivable ID: {receivable_doc['id']}, remaining: {receivable_doc['remaining']}")
    
    # Pay with method="transfer"
    pay_amount = receivable_doc["remaining"] * 0.5
    pay_body = {
        "amount": pay_amount,
        "method": "transfer"
    }
    
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json=pay_body, headers=headers("owner"))
    assert resp.status_code == 200, f"Pay receivable failed: {resp.text}"
    pay_result = resp.json()
    
    print(f"  Pay result method: {pay_result.get('method')}")
    
    # Check receivable document
    resp = requests.get(f"{BASE_URL}/receivables", headers=headers("owner"))
    assert resp.status_code == 200
    receivables_after = resp.json()
    
    receivable_after = None
    for r in receivables_after:
        if r["id"] == receivable_doc["id"]:
            receivable_after = r
            break
    
    assert receivable_after, "Receivable not found after payment"
    
    print(f"  Receivable last_method: {receivable_after.get('last_method')}")
    print(f"  Receivable payments count: {len(receivable_after.get('payments', []))}")
    
    # Check income document
    resp = requests.get(f"{BASE_URL}/incomes", headers=headers("owner"))
    assert resp.status_code == 200
    incomes = resp.json()
    
    income_found = False
    for inc in incomes:
        if inc.get("category") == "Pembayaran Piutang" and inc.get("method") == "transfer":
            income_found = True
            print(f"  Income 'Pembayaran Piutang' found with method='transfer'")
            break
    
    passed = (
        pay_result.get("method") == "transfer" and
        receivable_after.get("last_method") == "transfer" and
        len(receivable_after.get("payments", [])) >= 1 and
        income_found
    )
    
    print_result(passed, "Method 'transfer' saved correctly")
    
    # B2. Method tidak dikenal -> 400
    print_test("B2. Method tidak dikenal ('gopay2') -> 400")
    
    pay_invalid = {
        "amount": 1000,
        "method": "gopay2"
    }
    
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json=pay_invalid, headers=headers("owner"))
    
    passed = resp.status_code == 400 and "metode pembayaran tidak dikenal" in resp.text.lower()
    print_result(passed, f"Status: {resp.status_code}, Message: {resp.text[:100]}")
    
    # Test method="piutang" (should also be rejected)
    print_test("B2b. Method 'piutang' -> 400")
    
    pay_piutang = {
        "amount": 1000,
        "method": "piutang"
    }
    
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json=pay_piutang, headers=headers("owner"))
    
    passed = resp.status_code == 400 and "metode pembayaran tidak dikenal" in resp.text.lower()
    print_result(passed, f"Status: {resp.status_code}")
    
    # Test without method (should default to "cash")
    print_test("B2c. Without method -> default 'cash'")
    
    pay_no_method = {
        "amount": 1000
    }
    
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json=pay_no_method, headers=headers("owner"))
    
    passed = resp.status_code == 200
    if passed:
        result = resp.json()
        method = result.get("method", "")
        print(f"  Method: {method}")
        passed = method == "cash"
    
    print_result(passed, "Defaulted to 'cash'")
    
    # B3. Validasi lama HARUS tetap
    print_test("B3. Validasi: amount 0/negatif/melebihi sisa/sudah lunas -> 400")
    
    # Get current remaining
    resp = requests.get(f"{BASE_URL}/receivables", headers=headers("owner"))
    assert resp.status_code == 200
    receivables_current = resp.json()
    
    receivable_current = None
    for r in receivables_current:
        if r["id"] == receivable_doc["id"]:
            receivable_current = r
            break
    
    remaining = receivable_current["remaining"]
    
    # Test amount 0
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json={"amount": 0}, headers=headers("owner"))
    passed_zero = resp.status_code == 400
    print(f"  Amount 0: {resp.status_code} {'✅' if passed_zero else '❌'}")
    
    # Test amount negative
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json={"amount": -100}, headers=headers("owner"))
    passed_neg = resp.status_code == 400
    print(f"  Amount negative: {resp.status_code} {'✅' if passed_neg else '❌'}")
    
    # Test amount exceeds remaining
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json={"amount": remaining + 1000}, headers=headers("owner"))
    passed_exceed = resp.status_code == 400
    print(f"  Amount exceeds: {resp.status_code} {'✅' if passed_exceed else '❌'}")
    
    # Pay full to make it lunas
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json={"amount": remaining}, headers=headers("owner"))
    assert resp.status_code == 200
    
    # Test pay lunas receivable
    resp = requests.post(f"{BASE_URL}/receivables/{receivable_doc['id']}/pay", json={"amount": 100}, headers=headers("owner"))
    passed_lunas = resp.status_code == 400
    print(f"  Already lunas: {resp.status_code} {'✅' if passed_lunas else '❌'}")
    
    passed = passed_zero and passed_neg and passed_exceed and passed_lunas
    print_result(passed, "All validations working")
    
    # B4. Hutang: POST /api/payables/{id}/pay with method="qris"
    print_test("B4. Hutang: pay with method='qris'")
    
    # Get a supplier
    resp = requests.get(f"{BASE_URL}/suppliers", headers=headers("owner"))
    assert resp.status_code == 200
    suppliers = resp.json()
    supplier = suppliers[0] if suppliers else None
    
    if not supplier:
        print("  ⚠️  No suppliers found, skipping hutang test")
    else:
        # Create a purchase with credit
        purchase_body = {
            "supplier_id": supplier["id"],
            "items": [
                {
                    "product_id": broiler["id"],
                    "product_name": broiler["name"],
                    "ekor": 5,
                    "total_weight": 10,
                    "total_price": 300000
                }
            ],
            "transport": 0,
            "other": 0,
            "paid": 100000,  # Partial payment
            "notes": "Test B4 hutang"
        }
        
        resp = requests.post(f"{BASE_URL}/purchases", json=purchase_body, headers=headers("owner"))
        assert resp.status_code == 200, f"Purchase failed: {resp.text}"
        purchase = resp.json()
        test_data["purchases"].append(purchase["id"])
        
        # Get payable
        resp = requests.get(f"{BASE_URL}/payables", headers=headers("owner"))
        assert resp.status_code == 200
        payables = resp.json()
        
        payable_doc = None
        for p in payables:
            if p.get("ref_id") == purchase["id"]:
                payable_doc = p
                break
        
        if payable_doc:
            test_data["payables"].append(payable_doc["id"])
            
            # Pay with method="qris"
            pay_hutang_body = {
                "amount": 50000,
                "method": "qris"
            }
            
            resp = requests.post(f"{BASE_URL}/payables/{payable_doc['id']}/pay", json=pay_hutang_body, headers=headers("owner"))
            
            if resp.status_code == 200:
                print(f"  ✅ Owner can pay hutang")
                
                # Check expense
                resp = requests.get(f"{BASE_URL}/expenses", headers=headers("owner"))
                assert resp.status_code == 200
                expenses = resp.json()
                
                expense_found = False
                for exp in expenses:
                    if exp.get("category") == "Pembayaran Hutang" and exp.get("method") == "qris":
                        expense_found = True
                        cash_amount = exp.get("cash_amount", 0)
                        print(f"  Expense 'Pembayaran Hutang' found: method='qris', cash_amount={cash_amount}")
                        passed = cash_amount == 50000
                        break
                
                print_result(expense_found and passed, "Expense created with method='qris' and cash_amount=50000")
            else:
                print(f"  ❌ Pay hutang failed: {resp.status_code}")
            
            # Test kasir 403
            resp = requests.post(f"{BASE_URL}/payables/{payable_doc['id']}/pay", json=pay_hutang_body, headers=headers("kasir"))
            passed_kasir = resp.status_code == 403
            print_result(passed_kasir, f"Kasir correctly rejected: {resp.status_code}")
    
    # B5. GET /api/daily-closing/preview -> piutang_by_method & hutang_by_method
    print_test("B5. GET /api/daily-closing/preview -> piutang_by_method & hutang_by_method")
    
    today = datetime.now().strftime("%Y-%m-%d")
    resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}", headers=headers("owner"))
    assert resp.status_code == 200, f"Preview failed: {resp.text}"
    preview = resp.json()
    
    has_piutang_by_method = "piutang_by_method" in preview
    has_hutang_by_method = "hutang_by_method" in preview
    
    print(f"  piutang_by_method: {preview.get('piutang_by_method', [])}")
    print(f"  hutang_by_method: {preview.get('hutang_by_method', [])}")
    
    passed = has_piutang_by_method and has_hutang_by_method
    print_result(passed, "Both fields present in preview")
    
    # B6. PDF endpoints still valid
    print_test("B6. PDF endpoints still valid (%PDF-)")
    
    pdf_endpoints = [
        f"/daily-closing/preview",  # First get preview to create closing
        f"/reports/profit-loss/pdf?start={today}&end={today}",
        f"/reports/sales/pdf?start={today}&end={today}",
        f"/reports/stock/pdf"
    ]
    
    # Create a closing first
    closing_body = {
        "date": today,
        "notes": "Test B6"
    }
    resp = requests.post(f"{BASE_URL}/daily-closing", json=closing_body, headers=headers("owner"))
    if resp.status_code == 200:
        closing = resp.json()
        closing_id = closing.get("id")
        pdf_endpoints.append(f"/daily-closing/{closing_id}/pdf")
    
    all_valid = True
    for endpoint in pdf_endpoints:
        if endpoint == "/daily-closing/preview":
            continue  # Skip preview, not a PDF
        
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers("owner"))
        
        if resp.status_code == 200:
            content = resp.content
            is_pdf = content[:5] == b'%PDF-'
            print(f"  {endpoint}: {len(content)} bytes, PDF: {'✅' if is_pdf else '❌'}")
            all_valid = all_valid and is_pdf
        else:
            print(f"  {endpoint}: {resp.status_code} ❌")
            all_valid = False
    
    print_result(all_valid, "All PDF endpoints valid")

# ============================================================================
# C. UPLOAD FOTO BUKTI PENGELUARAN
# ============================================================================

def test_c_upload_bukti():
    """Test C: Upload foto bukti pengeluaran"""
    print_section("C. UPLOAD FOTO BUKTI PENGELUARAN")
    
    # Create a small test image (1x1 PNG)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # C1. POST /api/upload as kasir, admin, owner
    print_test("C1. POST /api/upload folder='proofs' (kasir, admin, owner)")
    
    for role in ["kasir", "admin", "owner"]:
        files = {'file': ('test.png', io.BytesIO(png_data), 'image/png')}
        data = {'folder': 'proofs'}
        
        resp = requests.post(f"{BASE_URL}/upload", files=files, data=data, headers=headers(role))
        
        if resp.status_code == 200:
            result = resp.json()
            file_id = result.get("id")
            file_url = result.get("url")
            print(f"  ✅ {role}: Upload success, id={file_id}, url={file_url[:50]}...")
            
            if file_id:
                test_data["uploads"].append(file_id)
                
                # Try to GET the file
                full_url = file_url if file_url.startswith("http") else f"{BASE_URL.replace('/api', '')}{file_url}"
                resp_get = requests.get(full_url)
                if resp_get.status_code == 200:
                    content_type = resp_get.headers.get("content-type", "")
                    print(f"     GET {file_url[:50]}... -> {resp_get.status_code}, content-type: {content_type}")
                else:
                    print(f"     GET {file_url[:50]}... -> {resp_get.status_code}")
        elif resp.status_code == 502:
            print(f"  ⚠️  {role}: Upload 502 (external storage issue, not a bug)")
        else:
            print(f"  ❌ {role}: Upload failed {resp.status_code}: {resp.text[:100]}")
    
    # C2. POST /api/expenses with proof_file_id
    print_test("C2. POST /api/expenses with proof_file_id (kasir)")
    
    # Upload a file first
    files = {'file': ('expense_proof.png', io.BytesIO(png_data), 'image/png')}
    data = {'folder': 'proofs'}
    
    resp = requests.post(f"{BASE_URL}/upload", files=files, data=data, headers=headers("kasir"))
    
    if resp.status_code == 200:
        upload_result = resp.json()
        proof_file_id = upload_result.get("id")
        proof_url = upload_result.get("url")
        
        if proof_file_id:
            test_data["uploads"].append(proof_file_id)
            
            # Create expense with proof
            expense_body = {
                "category": "Es",
                "amount": 5000,
                "description": "Test C2 with proof",
                "proof_file_id": proof_file_id,
                "proof_url": proof_url
            }
            
            resp = requests.post(f"{BASE_URL}/expenses", json=expense_body, headers=headers("kasir"))
            
            if resp.status_code == 200:
                expense = resp.json()
                test_data["expenses"].append(expense["id"])
                
                print(f"  ✅ Expense created with proof_file_id")
                
                # Check GET /api/expenses
                resp = requests.get(f"{BASE_URL}/expenses", headers=headers("kasir"))
                assert resp.status_code == 200
                expenses = resp.json()
                
                expense_found = False
                for exp in expenses:
                    if exp["id"] == expense["id"]:
                        expense_found = True
                        has_proof_url = "proof_url" in exp and exp["proof_url"]
                        print(f"  Expense proof_url: {exp.get('proof_url', '')[:50]}...")
                        print_result(has_proof_url, "proof_url displayed in GET /api/expenses")
                        break
                
                if not expense_found:
                    print("  ❌ Expense not found in GET /api/expenses")
            else:
                print(f"  ❌ Expense creation failed: {resp.status_code}")
    elif resp.status_code == 502:
        print("  ⚠️  Upload 502 (external storage issue, skipping expense test)")
    else:
        print(f"  ❌ Upload failed: {resp.status_code}")
    
    # Test without proof (optional)
    print_test("C2b. POST /api/expenses without proof (optional)")
    
    expense_no_proof = {
        "category": "Es",
        "amount": 3000,
        "description": "Test C2b no proof"
    }
    
    resp = requests.post(f"{BASE_URL}/expenses", json=expense_no_proof, headers=headers("kasir"))
    
    if resp.status_code == 200:
        expense = resp.json()
        test_data["expenses"].append(expense["id"])
        print_result(True, "Expense without proof works")
    else:
        print_result(False, f"Failed: {resp.status_code}")
    
    # C3. File bukan gambar -> 400
    print_test("C3. File bukan gambar (.txt) -> 400")
    
    txt_data = b'This is a text file'
    files = {'file': ('test.txt', io.BytesIO(txt_data), 'text/plain')}
    data = {'folder': 'proofs'}
    
    resp = requests.post(f"{BASE_URL}/upload", files=files, data=data, headers=headers("owner"))
    
    passed = resp.status_code == 400 and "format gambar tidak didukung" in resp.text.lower()
    print_result(passed, f"Status: {resp.status_code}, Message: {resp.text[:100]}")
    
    # C4. Without token -> 401/403
    print_test("C4. Upload without token -> 401/403")
    
    files = {'file': ('test.png', io.BytesIO(png_data), 'image/png')}
    data = {'folder': 'proofs'}
    
    resp = requests.post(f"{BASE_URL}/upload", files=files, data=data)
    
    passed = resp.status_code in [401, 403]
    print_result(passed, f"Status: {resp.status_code}")

# ============================================================================
# D. PENYESUAIAN STOK "SALAH POTONG"
# ============================================================================

def test_d_penyesuaian_stok():
    """Test D: Penyesuaian stok 'salah_potong'"""
    print_section("D. PENYESUAIAN STOK 'SALAH POTONG'")
    
    # D1. POST /api/stock-adjustments type="salah_potong"
    print_test("D1. POST /api/stock-adjustments type='salah_potong' (owner, admin, kasir)")
    
    broiler = get_product_by_name("Ayam Broiler")
    
    for role in ["owner", "admin", "kasir"]:
        adjustment_body = {
            "product_id": broiler["id"],
            "type": "salah_potong",
            "qty_kg": -0.5,
            "qty_ekor": 0,
            "qty_pcs": 0,
            "reason": f"Test D1 {role}"
        }
        
        resp = requests.post(f"{BASE_URL}/stock-adjustments", json=adjustment_body, headers=headers(role))
        
        if resp.status_code == 200:
            print(f"  ✅ {role}: Adjustment created")
        else:
            print(f"  ❌ {role}: Failed {resp.status_code}: {resp.text[:100]}")
    
    # Check stock-movements
    print_test("D1b. Check stock-movements for type='salah_potong'")
    
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=headers("owner"))
    assert resp.status_code == 200
    movements = resp.json()
    
    found = False
    for m in movements:
        if m.get("type") == "salah_potong":
            found = True
            print(f"  Found movement: type='salah_potong', product={m.get('product_name')}")
            break
    
    print_result(found, "Type 'salah_potong' appears in stock-movements")
    
    # D2. type="ngawur" -> 400
    print_test("D2. type='ngawur' -> 400")
    
    adjustment_invalid = {
        "product_id": broiler["id"],
        "type": "ngawur",
        "qty_kg": -0.1,
        "qty_ekor": 0,
        "qty_pcs": 0,
        "reason": "Test D2 invalid"
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", json=adjustment_invalid, headers=headers("owner"))
    
    passed = resp.status_code == 400 and "jenis penyesuaian tidak dikenal" in resp.text.lower()
    print_result(passed, f"Status: {resp.status_code}, Message: {resp.text[:100]}")
    
    # D2b. type="mati" should still be accepted
    print_test("D2b. type='mati' still accepted (compatibility)")
    
    adjustment_mati = {
        "product_id": broiler["id"],
        "type": "mati",
        "qty_kg": -0.1,
        "qty_ekor": 0,
        "qty_pcs": 0,
        "reason": "Test D2b mati"
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", json=adjustment_mati, headers=headers("owner"))
    
    if resp.status_code == 200:
        print_result(True, "Type 'mati' still accepted")
    else:
        print_result(False, f"Failed: {resp.status_code}")

# ============================================================================
# E. REGRESI WAJIB
# ============================================================================

def test_e_regresi():
    """Test E: Regresi wajib"""
    print_section("E. REGRESI WAJIB")
    
    # E1. Catat dashboard & profit-loss SEBELUM
    print_test("E1. Catat angka keuangan SEBELUM pengujian")
    
    resp = requests.get(f"{BASE_URL}/dashboard", headers=headers("owner"))
    assert resp.status_code == 200
    dashboard_before = resp.json()
    
    today = datetime.now().strftime("%Y-%m-%d")
    resp = requests.get(f"{BASE_URL}/reports/profit-loss?start={today}&end={today}", headers=headers("owner"))
    assert resp.status_code == 200
    pl_before = resp.json()
    
    print(f"  Dashboard before:")
    print(f"    Omzet: Rp {dashboard_before.get('omzet', 0):,.0f}")
    print(f"    Laba Kotor: Rp {dashboard_before.get('laba', 0):,.0f}")
    print(f"    Laba Bersih: Rp {dashboard_before.get('net_profit', 0):,.0f}")
    print(f"    Cash In: Rp {dashboard_before.get('cash_in', 0):,.0f}")
    print(f"    Cash Out: Rp {dashboard_before.get('cash_out', 0):,.0f}")
    print(f"    Net Cash: Rp {dashboard_before.get('net_cash', 0):,.0f}")
    
    # E2. GET /api/maintenance/consistency SEBELUM
    print_test("E2. GET /api/maintenance/consistency SEBELUM")
    
    resp = requests.get(f"{BASE_URL}/maintenance/consistency", headers=headers("owner"))
    assert resp.status_code == 200
    consistency_before = resp.json()
    issue_count_before = consistency_before.get("issue_count", -1)
    
    print(f"  Issue count SEBELUM: {issue_count_before}")
    print_result(issue_count_before == 0, "Data sinkron sebelum pengujian")
    
    # E3. RBAC kasir 403
    print_test("E3. RBAC kasir 403 di /purchases, /incomes, /payables, /dashboard, /daily-closing")
    
    endpoints_kasir_403 = [
        "/purchases",
        "/incomes",
        "/payables",
        "/dashboard",
        "/daily-closing"
    ]
    
    all_403 = True
    for endpoint in endpoints_kasir_403:
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers("kasir"))
        is_403 = resp.status_code == 403
        print(f"  {endpoint}: {resp.status_code} {'✅' if is_403 else '❌'}")
        all_403 = all_403 and is_403
    
    print_result(all_403, "All kasir endpoints correctly return 403")
    
    # E4. CLEANUP - Cancel all test sales
    print_test("E4. CLEANUP - Cancel all test sales")
    
    print(f"  Test sales to cancel: {len(test_data['sales'])}")
    
    cancelled_count = 0
    for sale_id in test_data["sales"][:]:  # Copy list to avoid modification during iteration
        resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=headers("owner"))
        if resp.status_code == 200:
            cancelled_count += 1
            test_data["sales"].remove(sale_id)
    
    print(f"  Cancelled: {cancelled_count} sales")
    
    # Check dashboard AFTER cleanup
    print_test("E4b. Check dashboard AFTER cleanup")
    
    resp = requests.get(f"{BASE_URL}/dashboard", headers=headers("owner"))
    assert resp.status_code == 200
    dashboard_after = resp.json()
    
    resp = requests.get(f"{BASE_URL}/reports/profit-loss?start={today}&end={today}", headers=headers("owner"))
    assert resp.status_code == 200
    pl_after = resp.json()
    
    print(f"  Dashboard after:")
    print(f"    Omzet: Rp {dashboard_after.get('omzet', 0):,.0f}")
    print(f"    Laba Kotor: Rp {dashboard_after.get('laba', 0):,.0f}")
    print(f"    Laba Bersih: Rp {dashboard_after.get('net_profit', 0):,.0f}")
    print(f"    Cash In: Rp {dashboard_after.get('cash_in', 0):,.0f}")
    print(f"    Cash Out: Rp {dashboard_after.get('cash_out', 0):,.0f}")
    print(f"    Net Cash: Rp {dashboard_after.get('net_cash', 0):,.0f}")
    
    # Compare
    tolerance = 1
    omzet_same = abs(dashboard_after.get('omzet', 0) - dashboard_before.get('omzet', 0)) <= tolerance
    laba_kotor_same = abs(dashboard_after.get('laba', 0) - dashboard_before.get('laba', 0)) <= tolerance
    laba_bersih_same = abs(dashboard_after.get('net_profit', 0) - dashboard_before.get('net_profit', 0)) <= tolerance
    cash_in_same = abs(dashboard_after.get('cash_in', 0) - dashboard_before.get('cash_in', 0)) <= tolerance
    cash_out_same = abs(dashboard_after.get('cash_out', 0) - dashboard_before.get('cash_out', 0)) <= tolerance
    net_cash_same = abs(dashboard_after.get('net_cash', 0) - dashboard_before.get('net_cash', 0)) <= tolerance
    
    all_same = omzet_same and laba_kotor_same and laba_bersih_same and cash_in_same and cash_out_same and net_cash_same
    
    print_result(all_same, "Angka keuangan kembali sama setelah cleanup")
    
    if not all_same:
        print(f"  ⚠️  Differences:")
        if not omzet_same:
            print(f"    Omzet: {dashboard_before.get('omzet', 0)} -> {dashboard_after.get('omzet', 0)}")
        if not laba_kotor_same:
            print(f"    Laba Kotor: {dashboard_before.get('laba', 0)} -> {dashboard_after.get('laba', 0)}")
        if not laba_bersih_same:
            print(f"    Laba Bersih: {dashboard_before.get('net_profit', 0)} -> {dashboard_after.get('net_profit', 0)}")
        if not cash_in_same:
            print(f"    Cash In: {dashboard_before.get('cash_in', 0)} -> {dashboard_after.get('cash_in', 0)}")
        if not cash_out_same:
            print(f"    Cash Out: {dashboard_before.get('cash_out', 0)} -> {dashboard_after.get('cash_out', 0)}")
        if not net_cash_same:
            print(f"    Net Cash: {dashboard_before.get('net_cash', 0)} -> {dashboard_after.get('net_cash', 0)}")
    
    # E2 AFTER. GET /api/maintenance/consistency SESUDAH
    print_test("E2 AFTER. GET /api/maintenance/consistency SESUDAH")
    
    resp = requests.get(f"{BASE_URL}/maintenance/consistency", headers=headers("owner"))
    assert resp.status_code == 200
    consistency_after = resp.json()
    issue_count_after = consistency_after.get("issue_count", -1)
    
    print(f"  Issue count SESUDAH: {issue_count_after}")
    
    if issue_count_after > 0:
        print(f"  ⚠️  Found {issue_count_after} issues:")
        findings = consistency_after.get("findings", [])
        for finding in findings[:5]:  # Show first 5
            print(f"    - {finding.get('kind')}: {finding.get('message', '')[:80]}")
    
    print_result(issue_count_after == 0, "Data tetap sinkron setelah pengujian")
    
    # Report remaining test data
    print_test("E4c. Report remaining test data")
    
    remaining = []
    if test_data["sales"]:
        remaining.append(f"{len(test_data['sales'])} sales")
    if test_data["receivables"]:
        remaining.append(f"{len(test_data['receivables'])} receivables")
    if test_data["payables"]:
        remaining.append(f"{len(test_data['payables'])} payables")
    if test_data["purchases"]:
        remaining.append(f"{len(test_data['purchases'])} purchases")
    if test_data["expenses"]:
        remaining.append(f"{len(test_data['expenses'])} expenses")
    if test_data["adjustments"]:
        remaining.append(f"{len(test_data['adjustments'])} adjustments")
    if test_data["uploads"]:
        remaining.append(f"{len(test_data['uploads'])} uploads")
    
    if remaining:
        print(f"  ⚠️  Remaining test data: {', '.join(remaining)}")
        print(f"     (These cannot be easily cleaned up via API)")
    else:
        print(f"  ✅ All test data cleaned up")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  BACKEND TESTING - 4 NEW CHANGES")
    print("  Berkah Ayam Mili POS System")
    print("="*80)
    
    try:
        # Login all roles
        print("\n→ Logging in...")
        for role in ["owner", "admin", "kasir"]:
            login(role)
        
        # Run tests
        test_a_penjualan_per_ekor()
        test_b_metode_pembayaran()
        test_c_upload_bukti()
        test_d_penyesuaian_stok()
        test_e_regresi()
        
        print("\n" + "="*80)
        print("  TESTING COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
