#!/usr/bin/env python3
"""
BACKEND REGRESSION TEST - Code Review Round 2
Tests G1-G5 after pdf_reports.py and server.py fixes
"""
import requests
import json
import time
import uuid
from datetime import datetime, timedelta

# Base URL from frontend/.env
BASE_URL = "https://github-app-preview-5.preview.emergentagent.com/api"

# Test credentials
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"}
}

# Store tokens
tokens = {}

def login(role):
    """Login and store token"""
    creds = CREDENTIALS[role]
    resp = requests.post(f"{BASE_URL}/auth/login", json=creds)
    assert resp.status_code == 200, f"Login {role} failed: {resp.status_code}"
    data = resp.json()
    tokens[role] = data["token"]
    print(f"✓ Login {role} successful")
    return data

def headers(role):
    """Get auth headers for role"""
    return {"Authorization": f"Bearer {tokens[role]}"}

def test_g1_pdf_endpoints():
    """G1: 4 PDF endpoints must return 200, start with %PDF-, size > 1000 bytes"""
    print("\n=== G1: PDF ENDPOINTS ===")
    
    # Get date range for testing
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    pdf_tests = [
        ("Profit-Loss PDF", f"/reports/profit-loss/pdf?start={week_ago}&end={today}"),
        ("Sales PDF", f"/reports/sales/pdf?start={week_ago}&end={today}"),
        ("Stock PDF", "/reports/stock/pdf"),
    ]
    
    results = []
    for name, endpoint in pdf_tests:
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers("owner"))
        
        status_ok = resp.status_code == 200
        is_pdf = resp.content[:5] == b'%PDF-'
        size_ok = len(resp.content) > 1000
        
        results.append({
            "name": name,
            "status": resp.status_code,
            "is_pdf": is_pdf,
            "size": len(resp.content),
            "pass": status_ok and is_pdf and size_ok
        })
        
        print(f"  {name}:")
        print(f"    Status: {resp.status_code} {'✓' if status_ok else '✗'}")
        print(f"    Starts with %PDF-: {is_pdf} {'✓' if is_pdf else '✗'}")
        print(f"    Size: {len(resp.content)} bytes {'✓' if size_ok else '✗'}")
    
    # Test daily-closing PDF (need to get a closing ID first)
    preview_resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}", headers=headers("owner"))
    if preview_resp.status_code == 200:
        preview_data = preview_resp.json()
        # Try to get or create a closing for today
        closing_resp = requests.get(f"{BASE_URL}/daily-closing/{today}", headers=headers("owner"))
        
        if closing_resp.status_code == 200:
            closing_id = closing_resp.json()["id"]
        else:
            # Create closing
            create_resp = requests.post(f"{BASE_URL}/daily-closing", 
                                       json={"date": today, "notes": "Test closing for PDF"},
                                       headers=headers("owner"))
            if create_resp.status_code == 200:
                closing_id = create_resp.json()["id"]
            else:
                closing_id = None
        
        if closing_id:
            pdf_resp = requests.get(f"{BASE_URL}/daily-closing/{closing_id}/pdf", headers=headers("owner"))
            status_ok = pdf_resp.status_code == 200
            is_pdf = pdf_resp.content[:5] == b'%PDF-'
            size_ok = len(pdf_resp.content) > 1000
            
            results.append({
                "name": "Daily-Closing PDF",
                "status": pdf_resp.status_code,
                "is_pdf": is_pdf,
                "size": len(pdf_resp.content),
                "pass": status_ok and is_pdf and size_ok
            })
            
            print(f"  Daily-Closing PDF:")
            print(f"    Status: {pdf_resp.status_code} {'✓' if status_ok else '✗'}")
            print(f"    Starts with %PDF-: {is_pdf} {'✓' if is_pdf else '✗'}")
            print(f"    Size: {len(pdf_resp.content)} bytes {'✓' if size_ok else '✗'}")
    
    all_pass = all(r["pass"] for r in results)
    print(f"\n  G1 Result: {'✓ PASS' if all_pass else '✗ FAIL'}")
    return all_pass, results

def test_g2_payable_outstanding():
    """G2: Verify payable_outstanding field is numerically correct"""
    print("\n=== G2: PAYABLE_OUTSTANDING VERIFICATION ===")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get payables to calculate expected total
    payables_resp = requests.get(f"{BASE_URL}/payables", headers=headers("owner"))
    assert payables_resp.status_code == 200, "Failed to get payables"
    
    payables = payables_resp.json()
    # Calculate total remaining debt from open payables
    expected_outstanding = round(sum(float(p.get("remaining", 0) or 0) for p in payables if p.get("status") == "open"), 2)
    
    print(f"  Expected payable_outstanding (from /api/payables): Rp {expected_outstanding:,.2f}")
    
    # Test preview endpoint
    preview_resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}", headers=headers("owner"))
    assert preview_resp.status_code == 200, "Failed to get preview"
    
    preview_data = preview_resp.json()
    preview_outstanding = preview_data.get("payable_outstanding", 0)
    
    print(f"  Preview payable_outstanding: Rp {preview_outstanding:,.2f}")
    
    preview_match = abs(preview_outstanding - expected_outstanding) < 0.01
    print(f"  Preview matches expected: {preview_match} {'✓' if preview_match else '✗'}")
    
    # Test POST endpoint (create/update closing)
    post_resp = requests.post(f"{BASE_URL}/daily-closing",
                             json={"date": today, "notes": "Test G2 verification"},
                             headers=headers("owner"))
    assert post_resp.status_code == 200, "Failed to POST closing"
    
    post_data = post_resp.json()
    post_outstanding = post_data.get("payable_outstanding", 0)
    
    print(f"  POST payable_outstanding: Rp {post_outstanding:,.2f}")
    
    post_match = abs(post_outstanding - expected_outstanding) < 0.01
    print(f"  POST matches expected: {post_match} {'✓' if post_match else '✗'}")
    
    all_pass = preview_match and post_match
    print(f"\n  G2 Result: {'✓ PASS' if all_pass else '✗ FAIL'}")
    
    return all_pass, {
        "expected": expected_outstanding,
        "preview": preview_outstanding,
        "post": post_outstanding,
        "preview_match": preview_match,
        "post_match": post_match
    }

def test_g3_weight_guidance():
    """G3: Verify weight-guidance endpoint returns correct values"""
    print("\n=== G3: WEIGHT-GUIDANCE ENDPOINT ===")
    
    # Test as owner
    resp = requests.get(f"{BASE_URL}/products/weight-guidance", headers=headers("owner"))
    assert resp.status_code == 200, "Owner should access weight-guidance"
    
    data = resp.json()
    items = {item["name"]: item for item in data.get("items", [])}
    
    # Expected values
    expected = {
        "Ayam Kampung": {"avg_weight_used": 1.2, "hpp_ekor": 62400, "is_estimate": True},
        "Ayam Pejantan": {"avg_weight_used": 1.1, "hpp_ekor": 36300, "is_estimate": True},
        "Ayam Broiler": {"avg_weight_used": 1.85, "hpp_ekor": 51800, "source": "auto"}
    }
    
    results = []
    for name, exp in expected.items():
        if name in items:
            item = items[name]
            weight_ok = abs(item.get("avg_weight_used", 0) - exp["avg_weight_used"]) < 0.01
            hpp_ok = abs(item.get("hpp_ekor", 0) - exp["hpp_ekor"]) < 1
            
            if "is_estimate" in exp:
                estimate_ok = item.get("is_estimate") == exp["is_estimate"]
            else:
                estimate_ok = item.get("avg_weight_source") == exp.get("source", "")
            
            pass_test = weight_ok and hpp_ok and estimate_ok
            
            results.append({
                "name": name,
                "weight": item.get("avg_weight_used"),
                "hpp_ekor": item.get("hpp_ekor"),
                "is_estimate": item.get("is_estimate"),
                "source": item.get("avg_weight_source"),
                "pass": pass_test
            })
            
            print(f"  {name}:")
            print(f"    Weight: {item.get('avg_weight_used')} kg (expected {exp['avg_weight_used']}) {'✓' if weight_ok else '✗'}")
            print(f"    HPP/ekor: Rp {item.get('hpp_ekor'):,.0f} (expected Rp {exp['hpp_ekor']:,.0f}) {'✓' if hpp_ok else '✗'}")
            if "is_estimate" in exp:
                print(f"    Is estimate: {item.get('is_estimate')} (expected {exp['is_estimate']}) {'✓' if estimate_ok else '✗'}")
            else:
                print(f"    Source: {item.get('avg_weight_source')} (expected {exp.get('source')}) {'✓' if estimate_ok else '✗'}")
        else:
            results.append({"name": name, "pass": False})
            print(f"  {name}: NOT FOUND ✗")
    
    # Test kasir access (should be 403)
    kasir_resp = requests.get(f"{BASE_URL}/products/weight-guidance", headers=headers("kasir"))
    kasir_blocked = kasir_resp.status_code == 403
    print(f"  Kasir access: {kasir_resp.status_code} {'✓ (correctly blocked)' if kasir_blocked else '✗ (should be 403)'}")
    
    all_pass = all(r["pass"] for r in results) and kasir_blocked
    print(f"\n  G3 Result: {'✓ PASS' if all_pass else '✗ FAIL'}")
    
    return all_pass, results

def test_g4_core_regression():
    """G4: Core regression tests"""
    print("\n=== G4: CORE REGRESSION ===")
    
    results = {}
    
    # 1. Login 3 roles (already done, verify tokens exist)
    print("  1. Login 3 roles:")
    for role in ["owner", "admin", "kasir"]:
        has_token = role in tokens and tokens[role]
        results[f"login_{role}"] = has_token
        print(f"    {role}: {'✓' if has_token else '✗'}")
    
    # 2. Dashboard
    print("  2. Dashboard:")
    dash_resp = requests.get(f"{BASE_URL}/dashboard", headers=headers("owner"))
    dash_ok = dash_resp.status_code == 200
    results["dashboard"] = dash_ok
    print(f"    GET /api/dashboard: {dash_resp.status_code} {'✓' if dash_ok else '✗'}")
    
    # 3. POST /api/sales per kg
    print("  3. Sales per kg:")
    # Get a product that sells per kg
    products_resp = requests.get(f"{BASE_URL}/products", headers=headers("kasir"))
    products = products_resp.json()
    kg_product = next((p for p in products if "kg" in p.get("units", [])), None)
    
    if kg_product:
        initial_stock = kg_product.get("stock_kg", 0)
        sale_kg_data = {
            "txn_id": str(uuid.uuid4()),
            "items": [{
                "product_id": kg_product["id"],
                "unit": "kg",
                "qty": 0.5,
                "price": kg_product.get("price_kg", 50000)
            }],
            "payment_method": "tunai",
            "amount_paid": 25000
        }
        
        sale_kg_resp = requests.post(f"{BASE_URL}/sales", json=sale_kg_data, headers=headers("kasir"))
        sale_kg_ok = sale_kg_resp.status_code == 200
        results["sale_kg"] = sale_kg_ok
        
        if sale_kg_ok:
            sale_kg_id = sale_kg_resp.json()["id"]
            # Verify stock decreased
            products_after = requests.get(f"{BASE_URL}/products", headers=headers("kasir")).json()
            product_after = next((p for p in products_after if p["id"] == kg_product["id"]), None)
            stock_decreased = product_after["stock_kg"] < initial_stock
            results["sale_kg_stock"] = stock_decreased
            print(f"    POST /api/sales (kg): {sale_kg_resp.status_code} {'✓' if sale_kg_ok else '✗'}")
            print(f"    Stock decreased: {stock_decreased} {'✓' if stock_decreased else '✗'}")
            
            # Test idempotency
            idempotent_resp = requests.post(f"{BASE_URL}/sales", json=sale_kg_data, headers=headers("kasir"))
            same_id = idempotent_resp.json()["id"] == sale_kg_id
            results["idempotency"] = same_id
            print(f"    Idempotency (same txn_id): {same_id} {'✓' if same_id else '✗'}")
            
            # Cancel sale
            cancel_resp = requests.post(f"{BASE_URL}/sales/{sale_kg_id}/cancel", headers=headers("owner"))
            cancel_ok = cancel_resp.status_code == 200
            results["cancel_sale"] = cancel_ok
            
            if cancel_ok:
                # Verify stock restored
                products_final = requests.get(f"{BASE_URL}/products", headers=headers("kasir")).json()
                product_final = next((p for p in products_final if p["id"] == kg_product["id"]), None)
                stock_restored = abs(product_final["stock_kg"] - initial_stock) < 0.01
                results["cancel_stock_restore"] = stock_restored
                print(f"    Cancel sale: {cancel_resp.status_code} {'✓' if cancel_ok else '✗'}")
                print(f"    Stock restored: {stock_restored} {'✓' if stock_restored else '✗'}")
    
    # 4. POST /api/sales per ekor
    print("  4. Sales per ekor:")
    ekor_product = next((p for p in products if "ekor" in p.get("units", []) and p.get("stock_ekor", 0) > 0), None)
    
    if ekor_product:
        initial_stock_ekor = ekor_product.get("stock_ekor", 0)
        sale_ekor_data = {
            "txn_id": str(uuid.uuid4()),
            "items": [{
                "product_id": ekor_product["id"],
                "unit": "ekor",
                "qty": 1,
                "price": ekor_product.get("price_ekor", 50000)
            }],
            "payment_method": "tunai",
            "amount_paid": 50000
        }
        
        sale_ekor_resp = requests.post(f"{BASE_URL}/sales", json=sale_ekor_data, headers=headers("kasir"))
        sale_ekor_ok = sale_ekor_resp.status_code == 200
        results["sale_ekor"] = sale_ekor_ok
        
        if sale_ekor_ok:
            sale_ekor_id = sale_ekor_resp.json()["id"]
            # Verify stock decreased
            products_after = requests.get(f"{BASE_URL}/products", headers=headers("kasir")).json()
            product_after = next((p for p in products_after if p["id"] == ekor_product["id"]), None)
            stock_decreased = product_after["stock_ekor"] < initial_stock_ekor
            results["sale_ekor_stock"] = stock_decreased
            print(f"    POST /api/sales (ekor): {sale_ekor_resp.status_code} {'✓' if sale_ekor_ok else '✗'}")
            print(f"    Stock decreased: {stock_decreased} {'✓' if stock_decreased else '✗'}")
            
            # Cancel to restore
            cancel_resp = requests.post(f"{BASE_URL}/sales/{sale_ekor_id}/cancel", headers=headers("owner"))
            if cancel_resp.status_code == 200:
                products_final = requests.get(f"{BASE_URL}/products", headers=headers("kasir")).json()
                product_final = next((p for p in products_final if p["id"] == ekor_product["id"]), None)
                stock_restored = abs(product_final["stock_ekor"] - initial_stock_ekor) < 0.01
                print(f"    Stock restored after cancel: {stock_restored} {'✓' if stock_restored else '✗'}")
    
    # 5. WhatsApp log
    print("  5. WhatsApp log:")
    wa_log_resp = requests.get(f"{BASE_URL}/whatsapp/log", headers=headers("owner"))
    wa_log_ok = wa_log_resp.status_code == 200
    results["whatsapp_log"] = wa_log_ok
    print(f"    GET /api/whatsapp/log: {wa_log_resp.status_code} {'✓' if wa_log_ok else '✗'}")
    
    # 6. WebSocket hello (test via HTTP first, WS requires websocket library)
    print("  6. WebSocket:")
    try:
        import websocket
        ws_url = f"wss://github-live-preview-6.preview.emergentagent.com/api/ws?token={tokens['owner']}"
        ws = websocket.create_connection(ws_url, timeout=5)
        msg = ws.recv()
        ws_data = json.loads(msg)
        ws_ok = ws_data.get("type") == "hello"
        ws.close()
        results["websocket"] = ws_ok
        print(f"    WebSocket hello: {'✓' if ws_ok else '✗'}")
    except Exception as e:
        print(f"    WebSocket: ✗ (error: {str(e)})")
        results["websocket"] = False
    
    all_pass = all(results.values())
    print(f"\n  G4 Result: {'✓ PASS' if all_pass else '✗ FAIL'}")
    
    return all_pass, results

def test_g5_backend_logs():
    """G5: Check for new tracebacks in backend logs"""
    print("\n=== G5: BACKEND ERROR LOGS ===")
    
    import subprocess
    
    # Check backend error log
    result = subprocess.run(
        ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
        capture_output=True,
        text=True
    )
    
    log_content = result.stdout
    
    # Look for tracebacks
    has_traceback = "Traceback" in log_content
    
    if has_traceback:
        print("  ✗ TRACEBACKS FOUND in backend.err.log:")
        # Print last 20 lines if traceback found
        lines = log_content.split("\n")
        for line in lines[-20:]:
            if line.strip():
                print(f"    {line}")
    else:
        print("  ✓ No tracebacks found in last 100 lines")
    
    print(f"\n  G5 Result: {'✓ PASS' if not has_traceback else '✗ FAIL'}")
    
    return not has_traceback, {"has_traceback": has_traceback}

def main():
    print("=" * 70)
    print("BACKEND REGRESSION TEST - Code Review Round 2")
    print("Testing G1-G5 after pdf_reports.py and server.py fixes")
    print("=" * 70)
    
    # Login all roles
    print("\n=== AUTHENTICATION ===")
    for role in ["owner", "admin", "kasir"]:
        login(role)
    
    # Run all tests
    results = {}
    
    try:
        results["g1"] = test_g1_pdf_endpoints()
    except Exception as e:
        print(f"G1 ERROR: {e}")
        results["g1"] = (False, str(e))
    
    try:
        results["g2"] = test_g2_payable_outstanding()
    except Exception as e:
        print(f"G2 ERROR: {e}")
        results["g2"] = (False, str(e))
    
    try:
        results["g3"] = test_g3_weight_guidance()
    except Exception as e:
        print(f"G3 ERROR: {e}")
        results["g3"] = (False, str(e))
    
    try:
        results["g4"] = test_g4_core_regression()
    except Exception as e:
        print(f"G4 ERROR: {e}")
        results["g4"] = (False, str(e))
    
    try:
        results["g5"] = test_g5_backend_logs()
    except Exception as e:
        print(f"G5 ERROR: {e}")
        results["g5"] = (False, str(e))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for test_name, result in results.items():
        if isinstance(result, tuple):
            passed, _ = result
            print(f"{test_name.upper()}: {'✓ PASS' if passed else '✗ FAIL'}")
        else:
            print(f"{test_name.upper()}: ✗ ERROR - {result}")
    
    all_passed = all(isinstance(r, tuple) and r[0] for r in results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 70)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
