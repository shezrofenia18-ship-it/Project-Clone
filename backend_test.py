#!/usr/bin/env python3
"""
Backend test untuk fitur Rekap WhatsApp Tutup Buku - Berkah Ayam Mili
Testing agent iteration: WhatsApp feature testing
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# Base URL dari frontend/.env
BASE_URL = "https://commit-inspector.preview.emergentagent.com/api"

# Credentials dari /app/memory/test_credentials.md
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"},
}

# Test results
results = []
tokens = {}


def log(msg, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {msg}")


def login(role):
    """Login and get JWT token"""
    log(f"Login sebagai {role}...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json=CREDENTIALS[role],
        timeout=10
    )
    if resp.status_code != 200:
        log(f"Login {role} gagal: {resp.status_code} {resp.text}", "ERROR")
        return None
    data = resp.json()
    token = data.get("token")
    tokens[role] = token
    log(f"Login {role} berhasil, token: {token[:20]}...")
    return token


def headers(role):
    """Get authorization headers for role"""
    return {"Authorization": f"Bearer {tokens.get(role)}"}


def test_result(test_num, description, passed, details=""):
    """Record test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append({
        "test": test_num,
        "description": description,
        "status": status,
        "passed": passed,
        "details": details
    })
    log(f"TEST {test_num}: {description} - {status}")
    if details:
        log(f"  Details: {details}")


def main():
    log("=" * 80)
    log("BACKEND TEST: Rekap WhatsApp Tutup Buku")
    log("=" * 80)
    
    # Login all roles
    for role in ["owner", "admin", "kasir"]:
        if not login(role):
            log(f"FATAL: Tidak bisa login sebagai {role}", "ERROR")
            sys.exit(1)
    
    log("\n" + "=" * 80)
    log("TEST 1: GET /api/whatsapp/settings - Access Control & Default Values")
    log("=" * 80)
    
    # Test 1a: Owner can access
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Check default values
            recipients = data.get("recipients", [])
            auto_enabled = data.get("auto_enabled")
            auto_time = data.get("auto_time")
            provider = data.get("provider", {})
            
            checks = []
            checks.append(("recipients exists", recipients is not None))
            checks.append(("default recipient", len(recipients) > 0 and recipients[0].get("number") == "6281289478221"))
            checks.append(("auto_enabled", auto_enabled == True))
            checks.append(("auto_time", auto_time == "21:00"))
            checks.append(("provider.configured", provider.get("configured") == False))
            checks.append(("provider.mode", provider.get("mode") == "manual"))
            
            all_passed = all(c[1] for c in checks)
            details = "; ".join([f"{c[0]}={c[1]}" for c in checks])
            test_result("1a", "GET /api/whatsapp/settings as OWNER → 200 with correct defaults", all_passed, details)
        else:
            test_result("1a", "GET /api/whatsapp/settings as OWNER → 200", False, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("1a", "GET /api/whatsapp/settings as OWNER", False, str(e))
    
    # Test 1b: Admin can access
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers("admin"), timeout=10)
        test_result("1b", "GET /api/whatsapp/settings as ADMIN → 200", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("1b", "GET /api/whatsapp/settings as ADMIN", False, str(e))
    
    # Test 1c: Kasir cannot access
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers("kasir"), timeout=10)
        test_result("1c", "GET /api/whatsapp/settings as KASIR → 403", resp.status_code == 403, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("1c", "GET /api/whatsapp/settings as KASIR → 403", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 2: PUT /api/whatsapp/settings - Number Normalization")
    log("=" * 80)
    
    # Test 2a: Update settings with various number formats
    try:
        payload = {
            "recipients": [
                {"name": "Owner", "number": "081289478221"},  # Should normalize to 6281289478221
                {"name": "Manajer", "number": "+628123456789"}  # Should normalize to 628123456789
            ],
            "auto_enabled": True,
            "auto_time": "20:30"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            recipients = data.get("recipients", [])
            
            checks = []
            checks.append(("count", len(recipients) == 2))
            if len(recipients) >= 2:
                checks.append(("first normalized", recipients[0].get("number") == "6281289478221"))
                checks.append(("second normalized", recipients[1].get("number") == "628123456789"))
            checks.append(("auto_time updated", data.get("auto_time") == "20:30"))
            
            all_passed = all(c[1] for c in checks)
            details = "; ".join([f"{c[0]}={c[1]}" for c in checks])
            test_result("2a", "PUT /api/whatsapp/settings with normalization → 200", all_passed, details)
        else:
            test_result("2a", "PUT /api/whatsapp/settings", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        test_result("2a", "PUT /api/whatsapp/settings", False, str(e))
    
    # Test 2b: Verify normalization persisted
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            recipients = data.get("recipients", [])
            
            checks = []
            if len(recipients) >= 2:
                checks.append(("first persisted", recipients[0].get("number") == "6281289478221"))
                checks.append(("second persisted", recipients[1].get("number") == "628123456789"))
            
            all_passed = all(c[1] for c in checks)
            details = f"Recipients: {json.dumps(recipients)}"
            test_result("2b", "GET /api/whatsapp/settings verifies normalization persisted", all_passed, details)
        else:
            test_result("2b", "GET /api/whatsapp/settings verification", False, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("2b", "GET /api/whatsapp/settings verification", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 3: PUT /api/whatsapp/settings - Validation")
    log("=" * 80)
    
    # Test 3a: Invalid number (too short)
    try:
        payload = {
            "recipients": [{"name": "Test", "number": "123"}],
            "auto_enabled": True,
            "auto_time": "21:00"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), json=payload, timeout=10)
        test_result("3a", "PUT with invalid number '123' → 400", resp.status_code == 400, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("3a", "PUT with invalid number", False, str(e))
    
    # Test 3b: Invalid time format (25:00)
    try:
        payload = {
            "recipients": [{"name": "Owner", "number": "081289478221"}],
            "auto_enabled": True,
            "auto_time": "25:00"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), json=payload, timeout=10)
        test_result("3b", "PUT with invalid time '25:00' → 400", resp.status_code == 400, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("3b", "PUT with invalid time 25:00", False, str(e))
    
    # Test 3c: Invalid time format (9pm)
    try:
        payload = {
            "recipients": [{"name": "Owner", "number": "081289478221"}],
            "auto_enabled": True,
            "auto_time": "9pm"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), json=payload, timeout=10)
        test_result("3c", "PUT with invalid time '9pm' → 400", resp.status_code == 400, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("3c", "PUT with invalid time 9pm", False, str(e))
    
    # Test 3d: Admin cannot PUT
    try:
        payload = {
            "recipients": [{"name": "Admin", "number": "081234567890"}],
            "auto_enabled": True,
            "auto_time": "21:00"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("admin"), json=payload, timeout=10)
        test_result("3d", "PUT as ADMIN → 403", resp.status_code == 403, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("3d", "PUT as ADMIN → 403", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 4: Restore Settings to Default")
    log("=" * 80)
    
    # Restore to default
    try:
        payload = {
            "recipients": [{"name": "Owner", "number": "081289478221"}],
            "auto_enabled": True,
            "auto_time": "21:00"
        }
        resp = requests.put(f"{BASE_URL}/whatsapp/settings", headers=headers("owner"), json=payload, timeout=10)
        test_result("4", "Restore settings to default", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("4", "Restore settings", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 5: POST /api/daily-closing/{cid}/whatsapp")
    log("=" * 80)
    
    # Get existing closing or create one
    closing_id = None
    closing_date = None
    
    try:
        # Get list of closings
        resp = requests.get(f"{BASE_URL}/daily-closing", headers=headers("owner"), timeout=10)
        if resp.status_code == 200:
            closings = resp.json()
            if closings and len(closings) > 0:
                closing_id = closings[0].get("id")
                closing_date = closings[0].get("date")
                log(f"Found existing closing: id={closing_id}, date={closing_date}")
            else:
                log("No existing closings found, will create one")
        
        # If no closing exists, create one for today
        if not closing_id:
            today = datetime.now().strftime("%Y-%m-%d")
            resp = requests.post(
                f"{BASE_URL}/daily-closing",
                headers=headers("owner"),
                json={"date": today, "notes": "Test closing for WhatsApp"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                closing_id = data.get("id")
                closing_date = data.get("date")
                log(f"Created new closing: id={closing_id}, date={closing_date}")
            else:
                log(f"Failed to create closing: {resp.status_code}", "ERROR")
    except Exception as e:
        log(f"Error getting/creating closing: {e}", "ERROR")
    
    # Test 5a: POST with closing ID
    if closing_id:
        try:
            resp = requests.post(f"{BASE_URL}/daily-closing/{closing_id}/whatsapp", headers=headers("owner"), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                
                checks = []
                checks.append(("mode", data.get("mode") == "manual"))
                checks.append(("sent_count", data.get("sent_count") == 0))
                
                text = data.get("text", "")
                checks.append(("text has REKAP TUTUP BUKU", "REKAP TUTUP BUKU" in text))
                checks.append(("text has LABA BERSIH", "LABA BERSIH" in text))
                
                results_list = data.get("results", [])
                checks.append(("results count", len(results_list) == 1))  # Should have 1 recipient
                
                if results_list:
                    link = results_list[0].get("link", "")
                    checks.append(("link starts with wa.me/62", link.startswith("https://wa.me/62")))
                    checks.append(("link has ?text=", "?text=" in link))
                
                all_passed = all(c[1] for c in checks)
                details = "; ".join([f"{c[0]}={c[1]}" for c in checks])
                test_result("5a", f"POST /api/daily-closing/{closing_id}/whatsapp as OWNER → 200", all_passed, details)
            else:
                test_result("5a", f"POST /api/daily-closing/{closing_id}/whatsapp", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
        except Exception as e:
            test_result("5a", "POST /api/daily-closing/{id}/whatsapp", False, str(e))
    else:
        test_result("5a", "POST /api/daily-closing/{id}/whatsapp", False, "No closing ID available")
    
    # Test 5b: POST with date
    if closing_date:
        try:
            resp = requests.post(f"{BASE_URL}/daily-closing/{closing_date}/whatsapp", headers=headers("owner"), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                checks = []
                checks.append(("mode", data.get("mode") == "manual"))
                checks.append(("sent_count", data.get("sent_count") == 0))
                
                all_passed = all(c[1] for c in checks)
                details = "; ".join([f"{c[0]}={c[1]}" for c in checks])
                test_result("5b", f"POST /api/daily-closing/{closing_date}/whatsapp (by date) → 200", all_passed, details)
            else:
                test_result("5b", f"POST /api/daily-closing/{closing_date}/whatsapp", False, f"Status: {resp.status_code}")
        except Exception as e:
            test_result("5b", "POST /api/daily-closing/{date}/whatsapp", False, str(e))
    else:
        test_result("5b", "POST /api/daily-closing/{date}/whatsapp", False, "No closing date available")
    
    # Test 5c: POST with invalid cid
    try:
        resp = requests.post(f"{BASE_URL}/daily-closing/invalid-id-12345/whatsapp", headers=headers("owner"), timeout=10)
        test_result("5c", "POST /api/daily-closing/invalid-id/whatsapp → 404", resp.status_code == 404, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("5c", "POST with invalid cid → 404", False, str(e))
    
    # Test 5d: POST as kasir (should be rejected)
    if closing_id:
        try:
            resp = requests.post(f"{BASE_URL}/daily-closing/{closing_id}/whatsapp", headers=headers("kasir"), timeout=10)
            test_result("5d", "POST /api/daily-closing/{id}/whatsapp as KASIR → 403", resp.status_code == 403, f"Status: {resp.status_code}")
        except Exception as e:
            test_result("5d", "POST as KASIR → 403", False, str(e))
    else:
        test_result("5d", "POST as KASIR → 403", False, "No closing ID available")
    
    log("\n" + "=" * 80)
    log("TEST 6: POST /api/daily-closing includes whatsapp field")
    log("=" * 80)
    
    # Create a new closing and check whatsapp field
    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        resp = requests.post(
            f"{BASE_URL}/daily-closing",
            headers=headers("owner"),
            json={"date": tomorrow, "notes": "Test closing with WhatsApp field"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            
            checks = []
            checks.append(("has whatsapp field", "whatsapp" in data))
            
            if "whatsapp" in data:
                wa = data["whatsapp"]
                checks.append(("whatsapp.mode", wa.get("mode") == "manual"))
                checks.append(("whatsapp.sent_count", wa.get("sent_count") == 0))
                checks.append(("whatsapp.text exists", bool(wa.get("text"))))
            
            all_passed = all(c[1] for c in checks)
            details = "; ".join([f"{c[0]}={c[1]}" for c in checks])
            test_result("6", "POST /api/daily-closing includes whatsapp field", all_passed, details)
        else:
            test_result("6", "POST /api/daily-closing", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    except Exception as e:
        test_result("6", "POST /api/daily-closing with whatsapp field", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 7: Backend Logs - Scheduler Active")
    log("=" * 80)
    
    # Check backend logs for scheduler message
    try:
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.out.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logs = result.stdout
        
        checks = []
        checks.append(("scheduler active message", "Penjadwal tutup buku otomatis aktif" in logs))
        
        # Check for repeated tracebacks (should not exist)
        traceback_count = logs.count("Traceback (most recent call last)")
        checks.append(("no repeated tracebacks", traceback_count < 3))  # Allow up to 2 tracebacks
        
        all_passed = all(c[1] for c in checks)
        details = f"Traceback count: {traceback_count}; Scheduler message found: {'Penjadwal tutup buku otomatis aktif' in logs}"
        test_result("7", "Backend logs show scheduler active, no repeated errors", all_passed, details)
    except Exception as e:
        test_result("7", "Backend logs check", False, str(e))
    
    log("\n" + "=" * 80)
    log("TEST 8: Regression Tests")
    log("=" * 80)
    
    # Test 8a: Login 3 roles
    try:
        all_logged_in = all(role in tokens for role in ["owner", "admin", "kasir"])
        test_result("8a", "Login 3 roles (owner, admin, kasir)", all_logged_in, f"Tokens: {list(tokens.keys())}")
    except Exception as e:
        test_result("8a", "Login 3 roles", False, str(e))
    
    # Test 8b: GET /api/dashboard
    try:
        resp = requests.get(f"{BASE_URL}/dashboard", headers=headers("owner"), timeout=10)
        test_result("8b", "GET /api/dashboard → 200", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("8b", "GET /api/dashboard", False, str(e))
    
    # Test 8c: GET /api/products
    try:
        resp = requests.get(f"{BASE_URL}/products", headers=headers("owner"), timeout=10)
        if resp.status_code == 200:
            products = resp.json()
            test_result("8c", "GET /api/products → 200", True, f"Count: {len(products)}")
        else:
            test_result("8c", "GET /api/products", False, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("8c", "GET /api/products", False, str(e))
    
    # Test 8d: POST /api/sales (kg unit) + idempotency
    try:
        # Get a product
        resp = requests.get(f"{BASE_URL}/products", headers=headers("kasir"), timeout=10)
        products = resp.json()
        product = next((p for p in products if "kg" in p.get("units", [])), None)
        
        if product:
            txn_id = f"test-txn-{datetime.now().timestamp()}"
            sale_payload = {
                "txn_id": txn_id,
                "items": [
                    {
                        "product_id": product["id"],
                        "unit": "kg",
                        "qty": 0.5,
                        "price": product.get("price_kg", 10000)
                    }
                ],
                "discount": 0,
                "paid": 0,
                "payment_method": "cash"
            }
            
            # First POST
            resp1 = requests.post(f"{BASE_URL}/sales", headers=headers("kasir"), json=sale_payload, timeout=10)
            sale_id_1 = resp1.json().get("id") if resp1.status_code == 200 else None
            
            # Second POST with same txn_id (idempotency test)
            resp2 = requests.post(f"{BASE_URL}/sales", headers=headers("kasir"), json=sale_payload, timeout=10)
            sale_id_2 = resp2.json().get("id") if resp2.status_code == 200 else None
            
            checks = []
            checks.append(("first POST 200", resp1.status_code == 200))
            checks.append(("second POST 200", resp2.status_code == 200))
            checks.append(("same sale_id", sale_id_1 == sale_id_2))
            
            all_passed = all(c[1] for c in checks)
            details = f"sale_id_1={sale_id_1}, sale_id_2={sale_id_2}"
            test_result("8d", "POST /api/sales (kg) + idempotency with same txn_id", all_passed, details)
        else:
            test_result("8d", "POST /api/sales", False, "No product with kg unit found")
    except Exception as e:
        test_result("8d", "POST /api/sales + idempotency", False, str(e))
    
    # Test 8e: GET /api/daily-closing/preview
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}", headers=headers("owner"), timeout=10)
        test_result("8e", "GET /api/daily-closing/preview → 200", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("8e", "GET /api/daily-closing/preview", False, str(e))
    
    # Test 8f: GET /api/daily-closing/{id}/pdf
    if closing_id:
        try:
            resp = requests.get(f"{BASE_URL}/daily-closing/{closing_id}/pdf", headers=headers("owner"), timeout=10)
            if resp.status_code == 200:
                content = resp.content
                is_pdf = content[:4] == b'%PDF'
                test_result("8f", "GET /api/daily-closing/{id}/pdf → 200 and starts with %PDF-", is_pdf, f"Size: {len(content)} bytes, PDF: {is_pdf}")
            else:
                test_result("8f", "GET /api/daily-closing/{id}/pdf", False, f"Status: {resp.status_code}")
        except Exception as e:
            test_result("8f", "GET /api/daily-closing/{id}/pdf", False, str(e))
    else:
        test_result("8f", "GET /api/daily-closing/{id}/pdf", False, "No closing ID available")
    
    # Test 8g: WebSocket connection (basic check - just verify endpoint exists)
    try:
        # We can't easily test WebSocket in this script, but we can verify the endpoint exists
        # by checking if the realtime status endpoint works
        resp = requests.get(f"{BASE_URL}/realtime/status", headers=headers("owner"), timeout=10)
        test_result("8g", "GET /api/realtime/status → 200 (WebSocket infrastructure)", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        test_result("8g", "WebSocket infrastructure check", False, str(e))
    
    # Print summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    log(f"\nTotal Tests: {total}")
    log(f"Passed: {passed}")
    log(f"Failed: {total - passed}")
    log(f"Success Rate: {passed/total*100:.1f}%\n")
    
    # Print detailed results
    for r in results:
        status_icon = "✅" if r["passed"] else "❌"
        log(f"{status_icon} TEST {r['test']}: {r['description']}")
        if r["details"]:
            log(f"   {r['details']}")
    
    # Print failures in detail
    failures = [r for r in results if not r["passed"]]
    if failures:
        log("\n" + "=" * 80)
        log("FAILED TESTS DETAIL")
        log("=" * 80)
        for r in failures:
            log(f"\n❌ TEST {r['test']}: {r['description']}")
            log(f"   {r['details']}")
    
    log("\n" + "=" * 80)
    log("BACKEND TEST COMPLETE")
    log("=" * 80)
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
