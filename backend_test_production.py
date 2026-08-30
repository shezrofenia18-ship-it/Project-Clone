#!/usr/bin/env python3
"""
Backend Test: Produksi Potong (Production Cutting)
===================================================
CRITICAL: Production should NOT modify hpp_pcs of any product.
This was a bug where all chicken value was assigned to the FIRST output only.

Test scenarios:
1. Record hpp_pcs BEFORE testing
2. Create production with multiple outputs
3. Verify hpp_pcs UNCHANGED after production
4. Verify response structure (material_value, total_cost, NO cost fields)
5. Verify stock movements (ekor decreased, pcs increased)
6. Lines with pcs=0 should be IGNORED
7. Validations (input_ekor <= 0, all pcs=0, invalid product_id)
8. Old body with cost fields should still work (ignored)
9. GET /api/productions
10. Regression tests (dashboard, sales, cancel)
11. RBAC (kasir can create production)
"""

import requests
import json
from typing import Dict, List, Any

# Backend URL from frontend/.env
BASE_URL = "https://github-deploy-app-4.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
OWNER_CREDS = {"username": "owner", "password": "berkahayam1"}
KASIR_CREDS = {"username": "kasir", "password": "kasir123"}

def login(creds: dict) -> str:
    """Login and return token"""
    r = requests.post(f"{BASE_URL}/auth/login", json=creds)
    if r.status_code != 200:
        raise Exception(f"Login failed: {r.status_code} {r.text}")
    return r.json()["token"]

def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def get_products(token: str) -> List[Dict]:
    """Get all products"""
    r = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    if r.status_code != 200:
        raise Exception(f"Get products failed: {r.status_code} {r.text}")
    return r.json()

def get_stock(token: str) -> List[Dict]:
    """Get stock (same as products)"""
    return get_products(token)

def create_production(token: str, body: dict) -> tuple:
    """Create production, return (status_code, response_json)"""
    r = requests.post(f"{BASE_URL}/productions", json=body, headers=get_headers(token))
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"error": r.text}

def get_productions(token: str) -> List[Dict]:
    """Get all productions"""
    r = requests.get(f"{BASE_URL}/productions", headers=get_headers(token))
    if r.status_code != 200:
        raise Exception(f"Get productions failed: {r.status_code} {r.text}")
    return r.json()

def create_sale(token: str, body: dict) -> tuple:
    """Create sale, return (status_code, response_json)"""
    r = requests.post(f"{BASE_URL}/sales", json=body, headers=get_headers(token))
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"error": r.text}

def cancel_sale(token: str, sale_id: str) -> tuple:
    """Cancel sale, return (status_code, response_json)"""
    r = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=get_headers(token))
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"error": r.text}

def get_dashboard(token: str) -> dict:
    """Get dashboard"""
    r = requests.get(f"{BASE_URL}/dashboard", headers=get_headers(token))
    if r.status_code != 200:
        raise Exception(f"Get dashboard failed: {r.status_code} {r.text}")
    return r.json()

def print_section(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(num: str, desc: str):
    print(f"\n--- TEST {num}: {desc} ---\n")

def main():
    print_section("BACKEND TEST: PRODUKSI POTONG")
    
    # Login
    print("Logging in as owner...")
    owner_token = login(OWNER_CREDS)
    print("✓ Owner logged in")
    
    print("\nLogging in as kasir...")
    kasir_token = login(KASIR_CREDS)
    print("✓ Kasir logged in")
    
    # Get all products
    print("\nFetching products...")
    products = get_products(owner_token)
    print(f"✓ Found {len(products)} products")
    
    # Find relevant products
    ayam_broiler = next((p for p in products if p["name"] == "Ayam Broiler"), None)
    if not ayam_broiler:
        raise Exception("Ayam Broiler not found")
    
    # Find cutting products (fillet, potongan, sampingan)
    cutting_products = [p for p in products if p["category"] in ["fillet", "potongan", "sampingan"]]
    print(f"✓ Found {len(cutting_products)} cutting products")
    
    # Find specific products for testing
    sayap = next((p for p in cutting_products if "Sayap" in p["name"]), None)
    dada = next((p for p in cutting_products if "Dada" in p["name"]), None)
    ceker = next((p for p in cutting_products if "Ceker" in p["name"]), None)
    kepala = next((p for p in cutting_products if "Kepala" in p["name"]), None)
    kulit = next((p for p in cutting_products if "Kulit" in p["name"]), None)
    
    if not all([sayap, dada, ceker]):
        raise Exception("Required cutting products not found (Sayap, Dada, Ceker)")
    
    # =========================================================================
    # TEST 1: RECORD hpp_pcs BEFORE TESTING (MOST IMPORTANT)
    # =========================================================================
    print_test("1", "RECORD hpp_pcs BEFORE TESTING")
    
    hpp_before = {}
    stock_before = {}
    
    print("HPP_PCS BEFORE TESTING:")
    print(f"{'Product':<30} {'hpp_pcs':>15} {'stock_ekor':>12} {'stock_pcs':>12}")
    print("-" * 70)
    
    # Record Ayam Broiler
    hpp_before[ayam_broiler["id"]] = ayam_broiler.get("hpp_pcs", 0)
    stock_before[ayam_broiler["id"]] = {
        "stock_ekor": ayam_broiler.get("stock_ekor", 0),
        "stock_pcs": ayam_broiler.get("stock_pcs", 0)
    }
    print(f"{ayam_broiler['name']:<30} {ayam_broiler.get('hpp_pcs', 0):>15.2f} {ayam_broiler.get('stock_ekor', 0):>12.1f} {ayam_broiler.get('stock_pcs', 0):>12.1f}")
    
    # Record all cutting products
    for p in cutting_products:
        hpp_before[p["id"]] = p.get("hpp_pcs", 0)
        stock_before[p["id"]] = {
            "stock_ekor": p.get("stock_ekor", 0),
            "stock_pcs": p.get("stock_pcs", 0)
        }
        print(f"{p['name']:<30} {p.get('hpp_pcs', 0):>15.2f} {p.get('stock_ekor', 0):>12.1f} {p.get('stock_pcs', 0):>12.1f}")
    
    print("\n✓ Recorded hpp_pcs and stock for all products")
    
    # =========================================================================
    # TEST 2: CREATE PRODUCTION WITH MULTIPLE OUTPUTS
    # =========================================================================
    print_test("2", "CREATE PRODUCTION WITH MULTIPLE OUTPUTS")
    
    production_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 2,
        "outputs": [
            {"product_id": sayap["id"], "pcs": 4},
            {"product_id": dada["id"], "pcs": 2},
            {"product_id": ceker["id"], "pcs": 2}
        ],
        "operator": "Testing Agent",
        "notes": "Test production - multiple outputs"
    }
    
    print(f"Creating production: {ayam_broiler['name']} 2 ekor -> Sayap 4 pcs, Dada 2 pcs, Ceker 2 pcs")
    status, response = create_production(owner_token, production_body)
    
    if status != 200:
        raise Exception(f"Create production failed: {status} {response}")
    
    print(f"✓ Production created: {response['id']}")
    production_id = response["id"]
    
    # =========================================================================
    # TEST 3: VERIFY hpp_pcs UNCHANGED (CRITICAL!)
    # =========================================================================
    print_test("3", "VERIFY hpp_pcs UNCHANGED (CRITICAL!)")
    
    # Fetch products again
    products_after = get_products(owner_token)
    
    print("HPP_PCS AFTER PRODUCTION:")
    print(f"{'Product':<30} {'Before':>15} {'After':>15} {'Changed?':>10}")
    print("-" * 70)
    
    all_unchanged = True
    
    # Check Ayam Broiler
    ayam_after = next((p for p in products_after if p["id"] == ayam_broiler["id"]), None)
    hpp_after_broiler = ayam_after.get("hpp_pcs", 0) if ayam_after else 0
    changed = "YES ❌" if hpp_after_broiler != hpp_before[ayam_broiler["id"]] else "NO ✓"
    if hpp_after_broiler != hpp_before[ayam_broiler["id"]]:
        all_unchanged = False
    print(f"{ayam_broiler['name']:<30} {hpp_before[ayam_broiler['id']]:>15.2f} {hpp_after_broiler:>15.2f} {changed:>10}")
    
    # Check all cutting products
    for p in cutting_products:
        p_after = next((x for x in products_after if x["id"] == p["id"]), None)
        hpp_after = p_after.get("hpp_pcs", 0) if p_after else 0
        changed = "YES ❌" if hpp_after != hpp_before[p["id"]] else "NO ✓"
        if hpp_after != hpp_before[p["id"]]:
            all_unchanged = False
        print(f"{p['name']:<30} {hpp_before[p['id']]:>15.2f} {hpp_after:>15.2f} {changed:>10}")
    
    if not all_unchanged:
        raise Exception("❌ CRITICAL BUG: hpp_pcs CHANGED after production!")
    
    print("\n✅ CRITICAL TEST PASSED: hpp_pcs UNCHANGED for all products")
    
    # =========================================================================
    # TEST 4: VERIFY RESPONSE STRUCTURE
    # =========================================================================
    print_test("4", "VERIFY RESPONSE STRUCTURE")
    
    print("Checking response fields...")
    
    # Should have material_value and total_cost
    if "material_value" not in response:
        raise Exception("Response missing 'material_value'")
    if "total_cost" not in response:
        raise Exception("Response missing 'total_cost'")
    
    print(f"✓ material_value: Rp {response['material_value']:,.2f}")
    print(f"✓ total_cost: Rp {response['total_cost']:,.2f}")
    
    # They should be equal
    if response["material_value"] != response["total_cost"]:
        raise Exception(f"material_value ({response['material_value']}) != total_cost ({response['total_cost']})")
    print("✓ material_value == total_cost")
    
    # Calculate expected value
    expected_value = 2 * ayam_broiler.get("hpp_ekor", 0)
    if abs(response["material_value"] - expected_value) > 0.01:
        raise Exception(f"material_value ({response['material_value']}) != expected ({expected_value})")
    print(f"✓ material_value matches expected: 2 × {ayam_broiler.get('hpp_ekor', 0)} = {expected_value}")
    
    # Should NOT have labor_cost, packaging_cost, other_cost
    if "labor_cost" in response:
        raise Exception("Response should NOT have 'labor_cost'")
    if "packaging_cost" in response:
        raise Exception("Response should NOT have 'packaging_cost'")
    if "other_cost" in response:
        raise Exception("Response should NOT have 'other_cost'")
    print("✓ NO labor_cost, packaging_cost, other_cost (correct)")
    
    # =========================================================================
    # TEST 5: VERIFY STOCK MOVEMENTS
    # =========================================================================
    print_test("5", "VERIFY STOCK MOVEMENTS")
    
    stock_after = get_stock(owner_token)
    
    print("STOCK CHANGES:")
    print(f"{'Product':<30} {'Before Ekor':>12} {'After Ekor':>12} {'Before Pcs':>12} {'After Pcs':>12}")
    print("-" * 90)
    
    # Check Ayam Broiler (should decrease by 2 ekor)
    ayam_stock_after = next((p for p in stock_after if p["id"] == ayam_broiler["id"]), None)
    ekor_before = stock_before[ayam_broiler["id"]]["stock_ekor"]
    ekor_after = ayam_stock_after.get("stock_ekor", 0) if ayam_stock_after else 0
    print(f"{ayam_broiler['name']:<30} {ekor_before:>12.1f} {ekor_after:>12.1f} {'-':>12} {'-':>12}")
    
    if abs(ekor_after - (ekor_before - 2)) > 0.01:
        raise Exception(f"Ayam Broiler stock_ekor should decrease by 2: {ekor_before} -> {ekor_after}")
    print(f"✓ Ayam Broiler stock_ekor decreased by 2")
    
    # Check cutting products (should increase pcs)
    expected_increases = {
        sayap["id"]: 4,
        dada["id"]: 2,
        ceker["id"]: 2
    }
    
    for prod_id, expected_increase in expected_increases.items():
        prod = next((p for p in cutting_products if p["id"] == prod_id), None)
        prod_after = next((p for p in stock_after if p["id"] == prod_id), None)
        
        pcs_before = stock_before[prod_id]["stock_pcs"]
        pcs_after = prod_after.get("stock_pcs", 0) if prod_after else 0
        
        print(f"{prod['name']:<30} {'-':>12} {'-':>12} {pcs_before:>12.1f} {pcs_after:>12.1f}")
        
        if abs(pcs_after - (pcs_before + expected_increase)) > 0.01:
            raise Exception(f"{prod['name']} stock_pcs should increase by {expected_increase}: {pcs_before} -> {pcs_after}")
    
    print(f"✓ All cutting products stock_pcs increased correctly")
    
    # =========================================================================
    # TEST 6: LINES WITH pcs=0 SHOULD BE IGNORED
    # =========================================================================
    print_test("6", "LINES WITH pcs=0 SHOULD BE IGNORED")
    
    if not kepala or not kulit:
        print("⚠ Skipping test (Kepala or Kulit not found)")
    else:
        # Record stock before
        kepala_before = next((p for p in stock_after if p["id"] == kepala["id"]), None)
        kulit_before = next((p for p in stock_after if p["id"] == kulit["id"]), None)
        kepala_pcs_before = kepala_before.get("stock_pcs", 0) if kepala_before else 0
        kulit_pcs_before = kulit_before.get("stock_pcs", 0) if kulit_before else 0
        
        production_body_with_zeros = {
            "source_product_id": ayam_broiler["id"],
            "input_ekor": 1,
            "outputs": [
                {"product_id": sayap["id"], "pcs": 3},
                {"product_id": kepala["id"], "pcs": 0},
                {"product_id": kulit["id"], "pcs": 0}
            ],
            "operator": "Testing Agent",
            "notes": "Test with pcs=0"
        }
        
        print(f"Creating production with pcs=0: Sayap 3 pcs, Kepala 0 pcs, Kulit 0 pcs")
        status, response = create_production(owner_token, production_body_with_zeros)
        
        if status != 200:
            raise Exception(f"Create production failed: {status} {response}")
        
        print(f"✓ Production created: {response['id']}")
        production_id_2 = response["id"]
        
        # Check outputs in response
        outputs = response.get("outputs", [])
        output_ids = [o["product_id"] for o in outputs]
        
        print(f"Outputs in response: {[o['name'] for o in outputs]}")
        
        if kepala["id"] in output_ids:
            raise Exception("Kepala (pcs=0) should NOT be in outputs")
        if kulit["id"] in output_ids:
            raise Exception("Kulit (pcs=0) should NOT be in outputs")
        if sayap["id"] not in output_ids:
            raise Exception("Sayap (pcs=3) should be in outputs")
        
        print("✓ Only non-zero outputs in response")
        
        # Check stock
        stock_after_2 = get_stock(owner_token)
        kepala_after = next((p for p in stock_after_2 if p["id"] == kepala["id"]), None)
        kulit_after = next((p for p in stock_after_2 if p["id"] == kulit["id"]), None)
        kepala_pcs_after = kepala_after.get("stock_pcs", 0) if kepala_after else 0
        kulit_pcs_after = kulit_after.get("stock_pcs", 0) if kulit_after else 0
        
        if kepala_pcs_after != kepala_pcs_before:
            raise Exception(f"Kepala stock_pcs should NOT change: {kepala_pcs_before} -> {kepala_pcs_after}")
        if kulit_pcs_after != kulit_pcs_before:
            raise Exception(f"Kulit stock_pcs should NOT change: {kulit_pcs_before} -> {kulit_pcs_after}")
        
        print("✓ Stock unchanged for products with pcs=0")
    
    # =========================================================================
    # TEST 7: VALIDATIONS
    # =========================================================================
    print_test("7", "VALIDATIONS")
    
    # 7a. input_ekor = 0
    print("7a. Testing input_ekor = 0...")
    body_zero = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 0,
        "outputs": [{"product_id": sayap["id"], "pcs": 2}]
    }
    status, response = create_production(owner_token, body_zero)
    if status != 400:
        raise Exception(f"Should reject input_ekor=0 with 400, got {status}")
    if "Jumlah ayam harus lebih dari 0" not in str(response):
        raise Exception(f"Wrong error message: {response}")
    print("✓ input_ekor=0 rejected with 400")
    
    # 7b. input_ekor < 0
    print("7b. Testing input_ekor < 0...")
    body_negative = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": -1,
        "outputs": [{"product_id": sayap["id"], "pcs": 2}]
    }
    status, response = create_production(owner_token, body_negative)
    if status != 400:
        raise Exception(f"Should reject input_ekor<0 with 400, got {status}")
    print("✓ input_ekor<0 rejected with 400")
    
    # 7c. All outputs pcs = 0
    print("7c. Testing all outputs pcs = 0...")
    body_all_zero = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 1,
        "outputs": [
            {"product_id": sayap["id"], "pcs": 0},
            {"product_id": dada["id"], "pcs": 0}
        ]
    }
    status, response = create_production(owner_token, body_all_zero)
    if status != 400:
        raise Exception(f"Should reject all pcs=0 with 400, got {status}")
    if "Isi jumlah pcs minimal satu bagian" not in str(response):
        raise Exception(f"Wrong error message: {response}")
    print("✓ All pcs=0 rejected with 400")
    
    # 7d. Empty outputs
    print("7d. Testing empty outputs...")
    body_empty = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 1,
        "outputs": []
    }
    status, response = create_production(owner_token, body_empty)
    if status != 400:
        raise Exception(f"Should reject empty outputs with 400, got {status}")
    print("✓ Empty outputs rejected with 400")
    
    # 7e. Invalid product_id in outputs
    print("7e. Testing invalid product_id in outputs...")
    body_invalid_output = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 1,
        "outputs": [{"product_id": "invalid-product-id-xyz", "pcs": 2}]
    }
    status, response = create_production(owner_token, body_invalid_output)
    if status != 404:
        raise Exception(f"Should reject invalid product_id with 404, got {status}")
    if "Produk hasil potong tidak ditemukan" not in str(response):
        raise Exception(f"Wrong error message: {response}")
    print("✓ Invalid product_id rejected with 404")
    
    # 7f. Invalid source_product_id
    print("7f. Testing invalid source_product_id...")
    body_invalid_source = {
        "source_product_id": "invalid-source-id-xyz",
        "input_ekor": 1,
        "outputs": [{"product_id": sayap["id"], "pcs": 2}]
    }
    status, response = create_production(owner_token, body_invalid_source)
    if status != 404:
        raise Exception(f"Should reject invalid source_product_id with 404, got {status}")
    if "Produk sumber tidak ditemukan" not in str(response):
        raise Exception(f"Wrong error message: {response}")
    print("✓ Invalid source_product_id rejected with 404")
    
    # =========================================================================
    # TEST 8: OLD BODY WITH COST FIELDS SHOULD STILL WORK
    # =========================================================================
    print_test("8", "OLD BODY WITH COST FIELDS SHOULD STILL WORK")
    
    # Record hpp before
    products_before_old = get_products(owner_token)
    hpp_before_old = {p["id"]: p.get("hpp_pcs", 0) for p in products_before_old}
    
    body_old = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 1,
        "outputs": [{"product_id": sayap["id"], "pcs": 2}],
        "labor_cost": 5000,  # Should be ignored
        "packaging_cost": 3000,  # Should be ignored
        "other_cost": 2000  # Should be ignored
    }
    
    print("Creating production with old body (labor_cost, packaging_cost, other_cost)...")
    status, response = create_production(owner_token, body_old)
    
    if status != 200:
        raise Exception(f"Old body should still work, got {status}: {response}")
    
    print(f"✓ Production created: {response['id']}")
    
    # Check that cost fields are NOT in response
    if "labor_cost" in response:
        raise Exception("Response should NOT have 'labor_cost'")
    if "packaging_cost" in response:
        raise Exception("Response should NOT have 'packaging_cost'")
    if "other_cost" in response:
        raise Exception("Response should NOT have 'other_cost'")
    print("✓ Cost fields ignored (not in response)")
    
    # Check hpp_pcs unchanged
    products_after_old = get_products(owner_token)
    for p in products_after_old:
        hpp_after_old = p.get("hpp_pcs", 0)
        if hpp_after_old != hpp_before_old[p["id"]]:
            raise Exception(f"hpp_pcs changed for {p['name']}: {hpp_before_old[p['id']]} -> {hpp_after_old}")
    print("✓ hpp_pcs unchanged after old body")
    
    # =========================================================================
    # TEST 9: GET /api/productions
    # =========================================================================
    print_test("9", "GET /api/productions")
    
    productions = get_productions(owner_token)
    print(f"✓ Found {len(productions)} productions")
    
    # Find our test production
    test_prod = next((p for p in productions if p["id"] == production_id), None)
    if not test_prod:
        raise Exception(f"Test production {production_id} not found in list")
    
    print(f"✓ Test production found in list")
    
    # Check outputs structure
    if "outputs" not in test_prod:
        raise Exception("Production missing 'outputs'")
    
    outputs = test_prod["outputs"]
    if len(outputs) != 3:
        raise Exception(f"Expected 3 outputs, got {len(outputs)}")
    
    for output in outputs:
        if "product_id" not in output:
            raise Exception("Output missing 'product_id'")
        if "name" not in output:
            raise Exception("Output missing 'name'")
        if "pcs" not in output:
            raise Exception("Output missing 'pcs'")
    
    output_desc = [f"{o['name']} {o['pcs']} pcs" for o in outputs]
    print(f"✓ Outputs structure correct: {output_desc}")
    
    # =========================================================================
    # TEST 10: REGRESSION TESTS
    # =========================================================================
    print_test("10", "REGRESSION TESTS")
    
    # 10a. Dashboard
    print("10a. Testing GET /api/dashboard...")
    dashboard = get_dashboard(owner_token)
    if "products_perf" not in dashboard:
        raise Exception("Dashboard missing 'products_perf'")
    if "stock_value" not in dashboard:
        raise Exception("Dashboard missing 'stock_value'")
    print(f"✓ Dashboard OK (products_perf: {len(dashboard['products_perf'])} items, stock_value: Rp {dashboard['stock_value']:,.2f})")
    
    # 10b. Create sale from cutting product
    print("10b. Testing create sale from cutting product...")
    
    # Get current stock
    stock_before_sale = get_stock(owner_token)
    sayap_before_sale = next((p for p in stock_before_sale if p["id"] == sayap["id"]), None)
    sayap_pcs_before_sale = sayap_before_sale.get("stock_pcs", 0) if sayap_before_sale else 0
    
    sale_body = {
        "items": [
            {
                "product_id": sayap["id"],
                "unit": "pcs",
                "qty": 2,
                "price": sayap.get("price_pcs", 10000)
            }
        ],
        "paid": 20000,
        "payment_method": "cash"
    }
    
    status, sale_response = create_sale(owner_token, sale_body)
    if status != 200:
        raise Exception(f"Create sale failed: {status} {sale_response}")
    
    sale_id = sale_response["id"]
    print(f"✓ Sale created: {sale_id}")
    
    # Check stock decreased
    stock_after_sale = get_stock(owner_token)
    sayap_after_sale = next((p for p in stock_after_sale if p["id"] == sayap["id"]), None)
    sayap_pcs_after_sale = sayap_after_sale.get("stock_pcs", 0) if sayap_after_sale else 0
    
    if abs(sayap_pcs_after_sale - (sayap_pcs_before_sale - 2)) > 0.01:
        raise Exception(f"Stock should decrease by 2: {sayap_pcs_before_sale} -> {sayap_pcs_after_sale}")
    print(f"✓ Stock decreased: {sayap_pcs_before_sale} -> {sayap_pcs_after_sale}")
    
    # 10c. Cancel sale
    print("10c. Testing cancel sale...")
    status, cancel_response = cancel_sale(owner_token, sale_id)
    if status != 200:
        raise Exception(f"Cancel sale failed: {status} {cancel_response}")
    
    print(f"✓ Sale cancelled")
    
    # Check stock restored
    stock_after_cancel = get_stock(owner_token)
    sayap_after_cancel = next((p for p in stock_after_cancel if p["id"] == sayap["id"]), None)
    sayap_pcs_after_cancel = sayap_after_cancel.get("stock_pcs", 0) if sayap_after_cancel else 0
    
    if abs(sayap_pcs_after_cancel - sayap_pcs_before_sale) > 0.01:
        raise Exception(f"Stock should be restored: {sayap_pcs_before_sale} vs {sayap_pcs_after_cancel}")
    print(f"✓ Stock restored: {sayap_pcs_after_cancel}")
    
    # =========================================================================
    # TEST 11: RBAC - KASIR CAN CREATE PRODUCTION
    # =========================================================================
    print_test("11", "RBAC - KASIR CAN CREATE PRODUCTION")
    
    production_body_kasir = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 1,
        "outputs": [{"product_id": sayap["id"], "pcs": 2}],
        "operator": "Kasir Test",
        "notes": "Test by kasir"
    }
    
    print("Creating production as kasir...")
    status, response = create_production(kasir_token, production_body_kasir)
    
    if status != 200:
        raise Exception(f"Kasir should be able to create production, got {status}: {response}")
    
    print(f"✓ Kasir can create production: {response['id']}")
    
    # =========================================================================
    # FINAL: VERIFY hpp_pcs UNCHANGED AFTER ALL TESTS
    # =========================================================================
    print_section("FINAL VERIFICATION: hpp_pcs UNCHANGED")
    
    products_final = get_products(owner_token)
    
    print("HPP_PCS COMPARISON (BEFORE vs AFTER ALL TESTS):")
    print(f"{'Product':<30} {'Before':>15} {'After':>15} {'Changed?':>10}")
    print("-" * 70)
    
    all_unchanged_final = True
    
    for prod_id, hpp_before_val in hpp_before.items():
        prod = next((p for p in products_final if p["id"] == prod_id), None)
        if not prod:
            continue
        
        hpp_after_val = prod.get("hpp_pcs", 0)
        changed = "YES ❌" if hpp_after_val != hpp_before_val else "NO ✓"
        if hpp_after_val != hpp_before_val:
            all_unchanged_final = False
        
        print(f"{prod['name']:<30} {hpp_before_val:>15.2f} {hpp_after_val:>15.2f} {changed:>10}")
    
    if not all_unchanged_final:
        raise Exception("❌ CRITICAL: hpp_pcs CHANGED during testing!")
    
    print("\n✅ FINAL VERIFICATION PASSED: hpp_pcs UNCHANGED for all products")
    
    # =========================================================================
    # CLEANUP & FINAL STOCK REPORT
    # =========================================================================
    print_section("CLEANUP & FINAL STOCK REPORT")
    
    print("Note: Test productions and sales created during testing.")
    print("Owner can clean up from the UI if needed.\n")
    
    print("FINAL STOCK:")
    print(f"{'Product':<30} {'stock_ekor':>12} {'stock_pcs':>12}")
    print("-" * 55)
    
    for p in products_final:
        if p["category"] in ["ayam", "fillet", "potongan", "sampingan"]:
            print(f"{p['name']:<30} {p.get('stock_ekor', 0):>12.1f} {p.get('stock_pcs', 0):>12.1f}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_section("TEST SUMMARY")
    
    print("✅ ALL TESTS PASSED (11/11)")
    print()
    print("1. ✅ Recorded hpp_pcs before testing")
    print("2. ✅ Created production with multiple outputs")
    print("3. ✅ CRITICAL: hpp_pcs UNCHANGED after production")
    print("4. ✅ Response structure correct (material_value, total_cost, no cost fields)")
    print("5. ✅ Stock movements correct (ekor decreased, pcs increased)")
    print("6. ✅ Lines with pcs=0 ignored")
    print("7. ✅ All validations working (input_ekor, pcs, product_id)")
    print("8. ✅ Old body with cost fields still works (fields ignored)")
    print("9. ✅ GET /api/productions working")
    print("10. ✅ Regression tests passed (dashboard, sales, cancel)")
    print("11. ✅ RBAC: kasir can create production")
    print()
    print("✅ FINAL: hpp_pcs IDENTICAL before and after all tests")
    print()
    print("CONCLUSION: Production cutting feature FULLY WORKING.")
    print("Bug fixed: Production NO LONGER modifies hpp_pcs.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
