#!/usr/bin/env python3
"""
Backend Test - Code Review Follow-up Verification
Berkah Ayam Mili - WhatsApp Feature

Focus: Verify no regressions after code changes to create_wa_template and send_wa_test
"""

import requests
import json
from datetime import datetime

# Backend URL
BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"},
}

def login(role):
    """Login and return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json=CREDENTIALS[role])
    if resp.status_code != 200:
        raise Exception(f"Login {role} failed: {resp.status_code} {resp.text}")
    return resp.json()["token"]

def get_headers(token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {token}"}

def test_section(name):
    """Print test section header"""
    print(f"\n{'='*80}")
    print(f"  {name}")
    print(f"{'='*80}")

def test_item(name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"       {details}")
    return passed

# Store test results
results = {
    "passed": 0,
    "failed": 0,
    "details": []
}

def record_result(test_name, passed, details=""):
    """Record test result"""
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    results["details"].append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    return test_item(test_name, passed, details)

# ============================================================================
# MAIN TESTS
# ============================================================================

try:
    # Login all roles
    test_section("LOGIN - All Roles")
    tokens = {}
    for role in ["owner", "admin", "kasir"]:
        try:
            tokens[role] = login(role)
            record_result(f"Login {role}", True, f"Token: {tokens[role][:20]}...")
        except Exception as e:
            record_result(f"Login {role}", False, str(e))
            raise

    # ========================================================================
    # TEST 1: POST /api/whatsapp/template - CRITICAL CHANGES
    # ========================================================================
    test_section("TEST 1: POST /api/whatsapp/template - Code Review Changes")
    
    print("\nKONTEKS: Kredensial Meta SENGAJA KOSONG di backend/.env")
    print("EXPECTED: 400 (BUKAN 500, BUKAN 502) dengan pesan Bahasa Indonesia\n")
    
    # 1a. Owner with_document=false
    resp = requests.post(
        f"{BASE_URL}/whatsapp/template?with_document=false",
        headers=get_headers(tokens["owner"])
    )
    passed = (
        resp.status_code == 400 and
        "Kredensial WhatsApp belum diisi" in resp.text and
        "META_PHONE_NUMBER_ID" in resp.text and
        "META_ACCESS_TOKEN" in resp.text
    )
    record_result(
        "Owner POST /whatsapp/template?with_document=false",
        passed,
        f"Status: {resp.status_code}, Body: {resp.text[:150]}"
    )
    
    # 1b. Owner with_document=true
    resp = requests.post(
        f"{BASE_URL}/whatsapp/template?with_document=true",
        headers=get_headers(tokens["owner"])
    )
    passed = (
        resp.status_code == 400 and
        "Kredensial WhatsApp belum diisi" in resp.text
    )
    record_result(
        "Owner POST /whatsapp/template?with_document=true",
        passed,
        f"Status: {resp.status_code}, Body: {resp.text[:150]}"
    )
    
    # 1c. Admin should get 403
    resp = requests.post(
        f"{BASE_URL}/whatsapp/template?with_document=false",
        headers=get_headers(tokens["admin"])
    )
    record_result(
        "Admin POST /whatsapp/template (should be 403)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )
    
    # 1d. Kasir should get 403
    resp = requests.post(
        f"{BASE_URL}/whatsapp/template?with_document=false",
        headers=get_headers(tokens["kasir"])
    )
    record_result(
        "Kasir POST /whatsapp/template (should be 403)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    # ========================================================================
    # TEST 2: POST /api/whatsapp/test - CRITICAL CHANGES
    # ========================================================================
    test_section("TEST 2: POST /api/whatsapp/test - Code Review Changes")
    
    print("\nKONTEKS: Kredensial Meta SENGAJA KOSONG")
    print("EXPECTED: 200, mode='manual', sent_count=0, setiap result punya 'link' wa.me\n")
    
    # 2a. Owner test
    resp = requests.post(
        f"{BASE_URL}/whatsapp/test",
        headers=get_headers(tokens["owner"])
    )
    if resp.status_code == 200:
        data = resp.json()
        passed = (
            data.get("mode") == "manual" and
            data.get("sent_count") == 0 and
            len(data.get("results", [])) > 0 and
            all("link" in r and "wa.me" in r["link"] for r in data["results"])
        )
        record_result(
            "Owner POST /whatsapp/test",
            passed,
            f"mode={data.get('mode')}, sent_count={data.get('sent_count')}, results={len(data.get('results', []))}"
        )
        
        # Verify link format
        if data.get("results"):
            first_link = data["results"][0].get("link", "")
            passed = first_link.startswith("https://wa.me/") and "?text=" in first_link
            record_result(
                "wa.me link format valid",
                passed,
                f"Link: {first_link[:80]}..."
            )
    else:
        record_result(
            "Owner POST /whatsapp/test",
            False,
            f"Status: {resp.status_code}, Body: {resp.text[:200]}"
        )
    
    # 2b. Admin should get 403
    resp = requests.post(
        f"{BASE_URL}/whatsapp/test",
        headers=get_headers(tokens["admin"])
    )
    record_result(
        "Admin POST /whatsapp/test (should be 403)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )
    
    # 2c. Kasir should get 403
    resp = requests.post(
        f"{BASE_URL}/whatsapp/test",
        headers=get_headers(tokens["kasir"])
    )
    record_result(
        "Kasir POST /whatsapp/test (should be 403)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    # ========================================================================
    # TEST 3: GET /api/whatsapp/log - Data Shape Verification
    # ========================================================================
    test_section("TEST 3: GET /api/whatsapp/log - Data Shape (No Regression)")
    
    resp = requests.get(
        f"{BASE_URL}/whatsapp/log",
        headers=get_headers(tokens["owner"])
    )
    if resp.status_code == 200:
        logs = resp.json()
        if not isinstance(logs, list):
            logs = []
        
        # Find the test log we just created
        test_log = None
        for log in logs:
            if log.get("kind") == "test":
                test_log = log
                break
        
        if test_log:
            # Verify required fields exist
            required_fields = ["id", "kind", "date", "trigger", "mode", "sent_count", "configured", "results"]
            has_all_fields = all(field in test_log for field in required_fields)
            record_result(
                "Log has all required fields",
                has_all_fields,
                f"Fields: {list(test_log.keys())}"
            )
            
            # CRITICAL: Verify results do NOT contain 'link' field (privacy)
            results_list = test_log.get("results", [])
            has_link_in_results = any("link" in r for r in results_list)
            record_result(
                "Results do NOT contain 'link' field (privacy)",
                not has_link_in_results,
                f"Results fields: {list(results_list[0].keys()) if results_list else []}"
            )
        else:
            record_result(
                "Find test log entry",
                False,
                "No test log found in recent logs"
            )
    else:
        record_result(
            "GET /whatsapp/log",
            False,
            f"Status: {resp.status_code}"
        )

    # ========================================================================
    # TEST 4: REGRESSIONS - WhatsApp Settings & Diagnostics
    # ========================================================================
    test_section("TEST 4: REGRESSIONS - WhatsApp Settings & Diagnostics")
    
    # 4a. GET /api/whatsapp/settings
    resp = requests.get(
        f"{BASE_URL}/whatsapp/settings",
        headers=get_headers(tokens["owner"])
    )
    if resp.status_code == 200:
        data = resp.json()
        
        # Check attach_pdf
        passed = data.get("attach_pdf") == True
        record_result("Settings: attach_pdf=true", passed, f"attach_pdf={data.get('attach_pdf')}")
        
        # Check template_spec
        passed = "template_spec" in data and data["template_spec"].get("name") == "rekap_tutup_buku_harian"
        record_result("Settings: template_spec exists", passed, f"name={data.get('template_spec', {}).get('name')}")
        
        # Check template_spec_doc
        passed = "template_spec_doc" in data and data["template_spec_doc"].get("name") == "rekap_tutup_buku_pdf"
        record_result("Settings: template_spec_doc exists", passed, f"name={data.get('template_spec_doc', {}).get('name')}")
        
        # Check provider.api_version
        provider = data.get("provider", {})
        passed = provider.get("api_version") == "v26.0"
        record_result("Settings: provider.api_version=v26.0", passed, f"api_version={provider.get('api_version')}")
        
        # Check provider.missing contains 4 META_* env vars
        missing = provider.get("missing", [])
        expected_missing = ["META_PHONE_NUMBER_ID", "META_ACCESS_TOKEN", "META_WABA_ID", "META_APP_ID"]
        passed = all(m in missing for m in expected_missing)
        record_result("Settings: provider.missing has 4 META_* vars", passed, f"missing={missing}")
    else:
        record_result("GET /whatsapp/settings", False, f"Status: {resp.status_code}")
    
    # 4b. GET /api/whatsapp/diagnostics
    resp = requests.get(
        f"{BASE_URL}/whatsapp/diagnostics",
        headers=get_headers(tokens["owner"])
    )
    if resp.status_code == 200:
        data = resp.json()
        
        passed = data.get("pdf_ready") == True
        record_result("Diagnostics: pdf_ready=true", passed, f"pdf_ready={data.get('pdf_ready')}")
        
        passed = data.get("pdf_size", 0) > 1000
        record_result("Diagnostics: pdf_size>1000", passed, f"pdf_size={data.get('pdf_size')}")
        
        passed = data.get("ready_for_auto") == False
        record_result("Diagnostics: ready_for_auto=false", passed, f"ready_for_auto={data.get('ready_for_auto')}")
        
        passed = bool(data.get("public_base_url"))
        record_result("Diagnostics: public_base_url not empty", passed, f"public_base_url={data.get('public_base_url')}")
    else:
        record_result("GET /whatsapp/diagnostics", False, f"Status: {resp.status_code}")
    
    # 4c. GET /api/whatsapp/template
    resp = requests.get(
        f"{BASE_URL}/whatsapp/template",
        headers=get_headers(tokens["owner"])
    )
    if resp.status_code == 200:
        data = resp.json()
        
        passed = data.get("approved") == False
        record_result("Template: approved=false", passed, f"approved={data.get('approved')}")
        
        passed = data.get("approved_doc") == False
        record_result("Template: approved_doc=false", passed, f"approved_doc={data.get('approved_doc')}")
        
        passed = "spec" in data
        record_result("Template: has 'spec'", passed)
        
        passed = "spec_doc" in data
        record_result("Template: has 'spec_doc'", passed)
    else:
        record_result("GET /whatsapp/template", False, f"Status: {resp.status_code}")

    # ========================================================================
    # TEST 5: REGRESSIONS - Daily Closing & PDF
    # ========================================================================
    test_section("TEST 5: REGRESSIONS - Daily Closing & PDF")
    
    # 5a. POST /api/daily-closing (today)
    today = datetime.now().strftime("%Y-%m-%d")
    resp = requests.post(
        f"{BASE_URL}/daily-closing",
        headers=get_headers(tokens["owner"]),
        json={"date": today, "notes": "Test code review"}
    )
    if resp.status_code == 200:
        data = resp.json()
        closing_id = data.get("id")
        
        # Check whatsapp.pdf_url
        whatsapp_data = data.get("whatsapp", {})
        pdf_url = whatsapp_data.get("pdf_url", "")
        passed = bool(pdf_url) and "/api/public/laporan/" in pdf_url
        record_result("Daily closing: whatsapp.pdf_url filled", passed, f"pdf_url={pdf_url[:80]}...")
        
        # Check whatsapp.text contains PDF section
        text = whatsapp_data.get("text", "")
        passed = "*PDF Laporan Penjualan:*" in text
        record_result("Daily closing: text contains '*PDF Laporan Penjualan:*'", passed)
        
        # Check whatsapp.template_values has 4 values
        template_values = whatsapp_data.get("template_values", {})
        expected_keys = ["tanggal", "omzet", "laba_bersih", "jumlah_transaksi"]
        passed = all(k in template_values for k in expected_keys)
        record_result("Daily closing: template_values has 4 values", passed, f"keys={list(template_values.keys())}")
        
        # 5b. Test public PDF link WITHOUT auth
        if pdf_url:
            resp_pdf = requests.get(pdf_url)  # No Authorization header
            passed = (
                resp_pdf.status_code == 200 and
                resp_pdf.headers.get("Content-Type") == "application/pdf" and
                resp_pdf.content[:4] == b"%PDF"
            )
            record_result(
                "Public PDF link (no auth): 200, application/pdf, %PDF",
                passed,
                f"Status: {resp_pdf.status_code}, Type: {resp_pdf.headers.get('Content-Type')}, Size: {len(resp_pdf.content)}"
            )
            
            # 5c. Test invalid token -> 404
            fake_token = "ngawur123456789"
            resp_fake = requests.get(f"{BASE_URL}/public/laporan/{fake_token}")
            passed = resp_fake.status_code == 404
            record_result(
                "Public PDF invalid token: 404 (not 500)",
                passed,
                f"Status: {resp_fake.status_code}"
            )
    else:
        record_result("POST /daily-closing", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")

    # ========================================================================
    # TEST 6: REGRESSIONS - PDF Reports
    # ========================================================================
    test_section("TEST 6: REGRESSIONS - PDF Reports")
    
    pdf_endpoints = [
        "/reports/sales/pdf",
        "/reports/profit-loss/pdf",
        "/reports/stock/pdf",
        f"/daily-closing/{today}/pdf"
    ]
    
    for endpoint in pdf_endpoints:
        resp = requests.get(
            f"{BASE_URL}{endpoint}",
            headers=get_headers(tokens["owner"])
        )
        passed = (
            resp.status_code == 200 and
            resp.headers.get("Content-Type") == "application/pdf" and
            resp.content[:4] == b"%PDF"
        )
        record_result(
            f"GET {endpoint}",
            passed,
            f"Status: {resp.status_code}, Type: {resp.headers.get('Content-Type')}, Size: {len(resp.content)}"
        )

    # ========================================================================
    # TEST 7: REGRESSIONS - Basic Operations
    # ========================================================================
    test_section("TEST 7: REGRESSIONS - Basic Operations")
    
    # 7a. GET /api/dashboard
    resp = requests.get(f"{BASE_URL}/dashboard", headers=get_headers(tokens["owner"]))
    record_result("GET /dashboard", resp.status_code == 200, f"Status: {resp.status_code}")
    
    # 7b. GET /api/products
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(tokens["owner"]))
    if resp.status_code == 200:
        products = resp.json()
        if not isinstance(products, list):
            products = []
        record_result("GET /products", True, f"Count: {len(products)}")
        
        # Find Ayam Broiler for stock test
        broiler = None
        for p in products:
            if "Broiler" in p.get("name", ""):
                broiler = p
                break
        
        if broiler:
            original_stock_ekor = broiler.get("stock_ekor", 0)
            
            # 7c. POST /api/sales (1 ekor)
            resp = requests.post(
                f"{BASE_URL}/sales",
                headers=get_headers(tokens["kasir"]),
                json={
                    "txn_id": f"test-{datetime.now().timestamp()}",
                    "items": [
                        {
                            "product_id": broiler["id"],
                            "unit": "ekor",
                            "qty": 1,
                            "price": broiler.get("price_ekor", 60000)
                        }
                    ],
                    "payment_method": "cash",
                    "paid": broiler.get("price_ekor", 60000)
                }
            )
            if resp.status_code == 200:
                sale_id = resp.json().get("id")
                record_result("POST /sales (1 ekor)", True, f"Sale ID: {sale_id}")
                
                # Check stock decreased
                resp = requests.get(f"{BASE_URL}/products", headers=get_headers(tokens["kasir"]))
                if resp.status_code == 200:
                    products = resp.json()
                    if not isinstance(products, list):
                        products = []
                    broiler_after = next((p for p in products if p["id"] == broiler["id"]), None)
                    if broiler_after:
                        new_stock = broiler_after.get("stock_ekor", 0)
                        passed = new_stock == original_stock_ekor - 1
                        record_result(
                            "Stock decreased by 1 ekor",
                            passed,
                            f"Before: {original_stock_ekor}, After: {new_stock}"
                        )
                        
                        # 7d. POST /api/sales/{id}/cancel (use admin token, kasir can't cancel)
                        resp = requests.post(
                            f"{BASE_URL}/sales/{sale_id}/cancel",
                            headers=get_headers(tokens["admin"])
                        )
                        if resp.status_code == 200:
                            record_result("POST /sales/{id}/cancel", True)
                            
                            # Check stock restored
                            resp = requests.get(f"{BASE_URL}/products", headers=get_headers(tokens["kasir"]))
                            if resp.status_code == 200:
                                products = resp.json()
                                if not isinstance(products, list):
                                    products = []
                                broiler_restored = next((p for p in products if p["id"] == broiler["id"]), None)
                                if broiler_restored:
                                    restored_stock = broiler_restored.get("stock_ekor", 0)
                                    passed = restored_stock == original_stock_ekor
                                    record_result(
                                        "Stock restored to original",
                                        passed,
                                        f"Original: {original_stock_ekor}, Restored: {restored_stock}"
                                    )
                        else:
                            record_result("POST /sales/{id}/cancel", False, f"Status: {resp.status_code}")
            else:
                record_result("POST /sales (1 ekor)", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    else:
        record_result("GET /products", False, f"Status: {resp.status_code}")
    
    # 7e. GET /api/stock-movements
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=get_headers(tokens["owner"]))
    record_result("GET /stock-movements", resp.status_code == 200, f"Status: {resp.status_code}")

    # ========================================================================
    # TEST 8: REGRESSIONS - Webhook
    # ========================================================================
    test_section("TEST 8: REGRESSIONS - Webhook")
    
    # 8a. GET /api/whatsapp/webhook with wrong token
    resp = requests.get(
        f"{BASE_URL}/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "123"
        }
    )
    record_result(
        "Webhook GET with wrong token: 403",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )
    
    # 8b. GET /api/whatsapp/webhook with correct token
    # Read correct token from backend/.env
    correct_token = "RG70wMaTh8ja2qHnRBpFVHD_BZqS7HBt"  # From backend/.env
    resp = requests.get(
        f"{BASE_URL}/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": correct_token,
            "hub.challenge": "123"
        }
    )
    passed = resp.status_code == 200 and resp.text == "123"
    record_result(
        "Webhook GET with correct token: 200, body='123'",
        passed,
        f"Status: {resp.status_code}, Body: {resp.text}"
    )
    
    # 8c. POST /api/whatsapp/webhook (statuses) - idempotency test
    webhook_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": f"wamid.TEST_CODE_REVIEW_{datetime.now().timestamp()}",
                        "status": "delivered",
                        "timestamp": str(int(datetime.now().timestamp())),
                        "recipient_id": "6281289478221"
                    }]
                }
            }]
        }]
    }
    
    # First POST
    resp1 = requests.post(f"{BASE_URL}/whatsapp/webhook", json=webhook_payload)
    passed1 = resp1.status_code == 200
    record_result("Webhook POST statuses (1st time): 200", passed1, f"Status: {resp1.status_code}")
    
    # Second POST (same payload - should be idempotent)
    resp2 = requests.post(f"{BASE_URL}/whatsapp/webhook", json=webhook_payload)
    passed2 = resp2.status_code == 200
    record_result("Webhook POST statuses (2nd time - idempotent): 200", passed2, f"Status: {resp2.status_code}")
    
    # Check only one entry in statuses
    resp = requests.get(f"{BASE_URL}/whatsapp/statuses", headers=get_headers(tokens["owner"]))
    if resp.status_code == 200:
        statuses = resp.json()
        if not isinstance(statuses, list):
            statuses = []
        message_id = webhook_payload["entry"][0]["changes"][0]["value"]["statuses"][0]["id"]
        matching = [s for s in statuses if s.get("message_id") == message_id]
        passed = len(matching) == 1
        record_result(
            "Webhook idempotency: only 1 entry in statuses",
            passed,
            f"Found {len(matching)} entries for message_id"
        )

    # ========================================================================
    # TEST 9: REGRESSIONS - RBAC
    # ========================================================================
    test_section("TEST 9: REGRESSIONS - RBAC")
    
    # Kasir should get 403 on whatsapp endpoints
    whatsapp_endpoints = [
        ("/whatsapp/settings", "GET"),
        ("/whatsapp/diagnostics", "GET"),
        ("/whatsapp/template", "GET"),
        ("/whatsapp/test", "POST"),
        ("/whatsapp/log", "GET")
    ]
    
    for endpoint, method in whatsapp_endpoints:
        if method == "GET":
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=get_headers(tokens["kasir"]))
        else:
            resp = requests.post(f"{BASE_URL}{endpoint}", headers=get_headers(tokens["kasir"]))
        record_result(
            f"Kasir {method} {endpoint}: 403",
            resp.status_code == 403,
            f"Status: {resp.status_code}"
        )
    
    # Kasir should get 403 on daily-closing
    resp = requests.get(f"{BASE_URL}/daily-closing/preview", headers=get_headers(tokens["kasir"]))
    record_result(
        "Kasir GET /daily-closing/preview: 403",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    # ========================================================================
    # TEST 10: RESTORE SETTINGS
    # ========================================================================
    test_section("TEST 10: RESTORE SETTINGS")
    
    restore_settings = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_time": "15:00",
        "auto_enabled": True,
        "attach_pdf": True
    }
    
    resp = requests.put(
        f"{BASE_URL}/whatsapp/settings",
        headers=get_headers(tokens["owner"]),
        json=restore_settings
    )
    if resp.status_code == 200:
        record_result("Restore settings", True, "Settings restored to original values")
        
        # Verify
        resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=get_headers(tokens["owner"]))
        if resp.status_code == 200:
            data = resp.json()
            passed = (
                len(data.get("recipients", [])) == 1 and
                data.get("auto_time") == "15:00" and
                data.get("auto_enabled") == True and
                data.get("attach_pdf") == True
            )
            record_result("Verify restored settings", passed, f"Settings: {data}")
    else:
        record_result("Restore settings", False, f"Status: {resp.status_code}")

except Exception as e:
    print(f"\n❌ CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    results["failed"] += 1

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*80)
print("  TEST SUMMARY")
print("="*80)
print(f"\n✅ PASSED: {results['passed']}")
print(f"❌ FAILED: {results['failed']}")
print(f"📊 TOTAL:  {results['passed'] + results['failed']}")

if results['failed'] > 0:
    print("\n⚠️  FAILED TESTS:")
    for detail in results['details']:
        if not detail['passed']:
            print(f"  - {detail['test']}")
            if detail['details']:
                print(f"    {detail['details']}")

print("\n" + "="*80)
if results['failed'] == 0:
    print("  ✅ ALL TESTS PASSED - NO REGRESSIONS FOUND")
else:
    print(f"  ❌ {results['failed']} TEST(S) FAILED - REVIEW REQUIRED")
print("="*80)
