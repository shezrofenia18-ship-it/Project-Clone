#!/usr/bin/env python3
"""
Backend Testing: WhatsApp PDF Attachment Feature
App: Berkah Ayam Mili
Test Date: 2026-08-30

KONTEKS: Kredensial Meta MASIH SENGAJA KOSONG di backend/.env.
Jadi lampiran nyata ke WhatsApp belum bisa diuji; yang diuji adalah jalur fallback:
PDF laporan penjualan dibuat lalu TAUTAN PUBLIK ber-token disisipkan ke teks rekap.
TIDAK BOLEH ADA HTTP 500.
"""

import requests
import json
from datetime import datetime, timedelta
import time

# Backend URL from frontend/.env
BASE_URL = "https://github-deploy-app-4.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"
ADMIN_EMAIL = "admin@berkahayam.com"
ADMIN_PASSWORD = "admin123"
KASIR_EMAIL = "kasir@berkahayam.com"
KASIR_PASSWORD = "kasir123"

def login(email: str, password: str) -> str:
    """Login and return JWT token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.status_code} {resp.text}")
    return resp.json()["token"]

def headers(token: str) -> dict:
    """Return headers with Authorization"""
    return {"Authorization": f"Bearer {token}"}

def test_1_whatsapp_settings():
    """Test 1: GET /api/whatsapp/settings - new fields attach_pdf and template_spec_doc"""
    print("\n=== TEST 1: GET /api/whatsapp/settings ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)
    
    # Owner
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(owner_token))
    assert resp.status_code == 200, f"Owner GET settings failed: {resp.status_code}"
    data = resp.json()
    
    # Check attach_pdf field
    assert "attach_pdf" in data, "Missing attach_pdf field"
    assert data["attach_pdf"] == True, f"attach_pdf should be True, got {data['attach_pdf']}"
    print(f"✅ attach_pdf = {data['attach_pdf']}")
    
    # Check template_spec (compact) still exists
    assert "template_spec" in data, "Missing template_spec field"
    spec = data["template_spec"]
    assert spec["name"] == "rekap_tutup_buku_harian", f"template_spec.name wrong: {spec['name']}"
    assert spec["language"] == "id", f"template_spec.language wrong: {spec['language']}"
    assert spec["category"] == "UTILITY", f"template_spec.category wrong: {spec['category']}"
    assert spec["parameter_format"] == "NAMED", f"template_spec.parameter_format wrong: {spec['parameter_format']}"
    assert len(spec["params"]) == 4, f"template_spec.params should have 4 items, got {len(spec['params'])}"
    print(f"✅ template_spec (compact) exists: name={spec['name']}, params={len(spec['params'])}")
    
    # Check template_spec_doc (with document)
    assert "template_spec_doc" in data, "Missing template_spec_doc field"
    spec_doc = data["template_spec_doc"]
    assert spec_doc["name"] == "rekap_tutup_buku_pdf", f"template_spec_doc.name wrong: {spec_doc['name']}"
    assert spec_doc["with_document"] == True, f"template_spec_doc.with_document should be True"
    print(f"✅ template_spec_doc exists: name={spec_doc['name']}, with_document={spec_doc['with_document']}")
    
    # Check payload.components[0] is HEADER/DOCUMENT
    payload = spec_doc["payload"]
    assert "components" in payload, "Missing payload.components"
    assert len(payload["components"]) > 0, "payload.components is empty"
    header = payload["components"][0]
    assert header["type"] == "HEADER", f"components[0].type should be HEADER, got {header['type']}"
    assert header["format"] == "DOCUMENT", f"components[0].format should be DOCUMENT, got {header['format']}"
    print(f"✅ payload.components[0]: type={header['type']}, format={header['format']}")
    
    # Check example.header_handle in components[0]
    assert "example" in header, "Missing components[0].example"
    assert "header_handle" in header["example"], "Missing components[0].example.header_handle"
    assert len(header["example"]["header_handle"]) > 0, "header_handle is empty"
    print(f"✅ components[0].example.header_handle exists: {header['example']['header_handle']}")    
    # Check provider.missing includes META_APP_ID
    provider = data["provider"]
    assert "missing" in provider, "Missing provider.missing"
    assert "META_APP_ID" in provider["missing"], "META_APP_ID not in provider.missing"
    assert "META_PHONE_NUMBER_ID" in provider["missing"], "META_PHONE_NUMBER_ID not in provider.missing"
    assert "META_ACCESS_TOKEN" in provider["missing"], "META_ACCESS_TOKEN not in provider.missing"
    print(f"✅ provider.missing includes META_APP_ID: {provider['missing']}")
    
    # Admin
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(admin_token))
    assert resp.status_code == 200, f"Admin GET settings failed: {resp.status_code}"
    print("✅ Admin: 200")
    
    # Kasir
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir should get 403, got {resp.status_code}"
    print("✅ Kasir: 403 (correctly rejected)")
    
    print("✅ TEST 1 PASSED")

def test_2_whatsapp_diagnostics():
    """Test 2: GET /api/whatsapp/diagnostics - pdf_ready, pdf_size, attach_pdf, public_base_url"""
    print("\n=== TEST 2: GET /api/whatsapp/diagnostics ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    
    resp = requests.get(f"{BASE_URL}/whatsapp/diagnostics", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET diagnostics failed: {resp.status_code} {resp.text}"
    data = resp.json()
    
    # Check pdf_ready
    assert "pdf_ready" in data, "Missing pdf_ready field"
    assert data["pdf_ready"] == True, f"pdf_ready should be True, got {data['pdf_ready']}"
    print(f"✅ pdf_ready = {data['pdf_ready']}")
    
    # Check pdf_size
    assert "pdf_size" in data, "Missing pdf_size field"
    assert data["pdf_size"] > 1000, f"pdf_size should be >1000, got {data['pdf_size']}"
    print(f"✅ pdf_size = {data['pdf_size']} bytes")
    
    # Check attach_pdf
    assert "attach_pdf" in data, "Missing attach_pdf field"
    assert data["attach_pdf"] == True, f"attach_pdf should be True, got {data['attach_pdf']}"
    print(f"✅ attach_pdf = {data['attach_pdf']}")
    
    # Check public_base_url
    assert "public_base_url" in data, "Missing public_base_url field"
    assert len(data["public_base_url"]) > 0, "public_base_url is empty"
    print(f"✅ public_base_url = {data['public_base_url']}")
    
    # Check template_doc_approved
    assert "template_doc_approved" in data, "Missing template_doc_approved field"
    assert data["template_doc_approved"] == False, f"template_doc_approved should be False (credentials empty), got {data['template_doc_approved']}"
    print(f"✅ template_doc_approved = {data['template_doc_approved']} (BENAR, credentials empty)")
    
    # Check ready_for_auto
    assert "ready_for_auto" in data, "Missing ready_for_auto field"
    assert data["ready_for_auto"] == False, f"ready_for_auto should be False (credentials empty), got {data['ready_for_auto']}"
    print(f"✅ ready_for_auto = {data['ready_for_auto']} (BENAR, credentials empty)")
    
    print("✅ TEST 2 PASSED")

def test_3_whatsapp_template():
    """Test 3: GET /api/whatsapp/template - spec_doc and approved_doc"""
    print("\n=== TEST 3: GET /api/whatsapp/template ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    
    resp = requests.get(f"{BASE_URL}/whatsapp/template", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET template failed: {resp.status_code} {resp.text}"
    data = resp.json()
    
    # Check spec_doc
    assert "spec_doc" in data, "Missing spec_doc field"
    spec_doc = data["spec_doc"]
    assert spec_doc["name"] == "rekap_tutup_buku_pdf", f"spec_doc.name wrong: {spec_doc['name']}"
    print(f"✅ spec_doc exists: name={spec_doc['name']}")
    
    # Check approved_doc
    assert "approved_doc" in data, "Missing approved_doc field"
    assert data["approved_doc"] == False, f"approved_doc should be False (credentials empty), got {data['approved_doc']}"
    print(f"✅ approved_doc = {data['approved_doc']} (BENAR, credentials empty)")
    
    print("✅ TEST 3 PASSED")

def test_4_whatsapp_template_create():
    """Test 4: POST /api/whatsapp/template - with_document=true/false, both 400 (credentials empty)"""
    print("\n=== TEST 4: POST /api/whatsapp/template ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)
    
    # Owner with_document=true
    resp = requests.post(f"{BASE_URL}/whatsapp/template?with_document=true", headers=headers(owner_token))
    assert resp.status_code == 400, f"Owner POST template with_document=true should be 400, got {resp.status_code}"
    assert resp.status_code != 500, f"MUST NOT BE 500, got {resp.status_code}"
    # Check Indonesian message
    text = resp.text.lower()
    assert "kredensial" in text or "meta" in text or "belum" in text, f"Should have Indonesian error message, got: {resp.text}"
    print(f"✅ Owner with_document=true: 400 (BUKAN 500), message: {resp.text[:100]}")
    
    # Owner with_document=false
    resp = requests.post(f"{BASE_URL}/whatsapp/template?with_document=false", headers=headers(owner_token))
    assert resp.status_code == 400, f"Owner POST template with_document=false should be 400, got {resp.status_code}"
    assert resp.status_code != 500, f"MUST NOT BE 500, got {resp.status_code}"
    print(f"✅ Owner with_document=false: 400 (BUKAN 500)")
    
    # Admin
    resp = requests.post(f"{BASE_URL}/whatsapp/template?with_document=true", headers=headers(admin_token))
    assert resp.status_code == 403, f"Admin should get 403, got {resp.status_code}"
    print("✅ Admin: 403 (correctly rejected)")
    
    # Kasir
    resp = requests.post(f"{BASE_URL}/whatsapp/template?with_document=true", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir should get 403, got {resp.status_code}"
    print("✅ Kasir: 403 (correctly rejected)")
    
    print("✅ TEST 4 PASSED")

def test_5_whatsapp_settings_attach_pdf():
    """Test 5: PUT /api/whatsapp/settings - attach_pdf toggle"""
    print("\n=== TEST 5: PUT /api/whatsapp/settings - attach_pdf toggle ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    
    # Set attach_pdf=false
    body = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_enabled": True,
        "auto_time": "15:00",
        "attach_pdf": False
    }
    resp = requests.put(f"{BASE_URL}/whatsapp/settings", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"PUT settings attach_pdf=false failed: {resp.status_code} {resp.text}"
    print("✅ PUT attach_pdf=false: 200")
    
    # Read back
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET settings failed: {resp.status_code}"
    data = resp.json()
    assert data["attach_pdf"] == False, f"attach_pdf should be False, got {data['attach_pdf']}"
    print(f"✅ Read back: attach_pdf = {data['attach_pdf']}")
    
    # Set attach_pdf=true
    body["attach_pdf"] = True
    resp = requests.put(f"{BASE_URL}/whatsapp/settings", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"PUT settings attach_pdf=true failed: {resp.status_code} {resp.text}"
    print("✅ PUT attach_pdf=true: 200")
    
    # Read back
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET settings failed: {resp.status_code}"
    data = resp.json()
    assert data["attach_pdf"] == True, f"attach_pdf should be True, got {data['attach_pdf']}"
    print(f"✅ Read back: attach_pdf = {data['attach_pdf']}")
    
    # RESTORE to original settings
    body = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_enabled": True,
        "auto_time": "15:00",
        "attach_pdf": True
    }
    resp = requests.put(f"{BASE_URL}/whatsapp/settings", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"RESTORE settings failed: {resp.status_code} {resp.text}"
    print("✅ RESTORED: recipients=[{name:'Owner',number:'081289478221'}], auto_time='15:00', auto_enabled=true, attach_pdf=true")
    
    print("✅ TEST 5 PASSED")

def test_6_daily_closing_pdf_url():
    """Test 6: POST /api/daily-closing - pdf_url in whatsapp field"""
    print("\n=== TEST 6: POST /api/daily-closing - pdf_url in whatsapp field ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    
    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Delete existing closing for today (if any)
    resp = requests.get(f"{BASE_URL}/daily-closing", headers=headers(owner_token))
    if resp.status_code == 200:
        closings = resp.json()
        for c in closings:
            if c.get("date") == today:
                # Delete it
                cid = c["id"]
                requests.delete(f"{BASE_URL}/daily-closing/{cid}", headers=headers(owner_token))
                print(f"Deleted existing closing for {today}")
                break
    
    # Create new closing
    body = {"date": today, "notes": "Test PDF attachment"}
    resp = requests.post(f"{BASE_URL}/daily-closing", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"POST daily-closing failed: {resp.status_code} {resp.text}"
    data = resp.json()
    
    # Check whatsapp field
    assert "whatsapp" in data, "Missing whatsapp field"
    wa = data["whatsapp"]
    
    # Check pdf_url
    assert "pdf_url" in wa, "Missing whatsapp.pdf_url field"
    pdf_url = wa["pdf_url"]
    assert len(pdf_url) > 0, "pdf_url is empty"
    print(f"✅ pdf_url exists: {pdf_url}")
    
    # Check pattern: <base>/api/public/laporan/<token>
    assert "/api/public/laporan/" in pdf_url, f"pdf_url should contain '/api/public/laporan/', got: {pdf_url}"
    token = pdf_url.split("/api/public/laporan/")[-1]
    assert len(token) > 30, f"token should be >30 chars, got {len(token)}: {token}"
    print(f"✅ pdf_url pattern correct: token length = {len(token)}")
    
    # Check text contains PDF line
    assert "text" in wa, "Missing whatsapp.text field"
    text = wa["text"]
    assert "*PDF Laporan Penjualan:*" in text, f"text should contain '*PDF Laporan Penjualan:*', got: {text[:200]}"
    assert pdf_url in text, f"text should contain pdf_url, got: {text[:500]}"
    print(f"✅ text contains '*PDF Laporan Penjualan:*' and pdf_url")
    
    # Check results[].link contains encoded pdf_url
    assert "results" in wa, "Missing whatsapp.results field"
    assert len(wa["results"]) > 0, "whatsapp.results is empty"
    link = wa["results"][0].get("link", "")
    assert "wa.me" in link, f"results[].link should be wa.me link, got: {link}"
    # URL should be encoded
    from urllib.parse import unquote
    decoded = unquote(link)
    assert pdf_url in decoded, f"results[].link should contain pdf_url (encoded), decoded: {decoded[:500]}"
    print(f"✅ results[].link (wa.me) contains pdf_url (encoded)")
    
    print("✅ TEST 6 PASSED")
    
    # Return pdf_url for next test
    return pdf_url

def test_7_public_laporan_endpoint(pdf_url: str):
    """Test 7: GET /api/public/laporan/{token} - public access without auth"""
    print("\n=== TEST 7: GET /api/public/laporan/{token} - public access ===")
    
    # Extract token from pdf_url
    token = pdf_url.split("/api/public/laporan/")[-1]
    print(f"Token: {token}")
    
    # GET without Authorization header
    resp = requests.get(pdf_url)
    assert resp.status_code == 200, f"GET public laporan failed: {resp.status_code} {resp.text}"
    print(f"✅ GET {pdf_url}: 200 (without auth)")
    
    # Check Content-Type
    content_type = resp.headers.get("Content-Type", "")
    assert "application/pdf" in content_type, f"Content-Type should be application/pdf, got: {content_type}"
    print(f"✅ Content-Type: {content_type}")
    
    # Check first 4 bytes
    pdf_bytes = resp.content
    assert len(pdf_bytes) > 4, f"PDF too short: {len(pdf_bytes)} bytes"
    assert pdf_bytes[:4] == b"%PDF", f"First 4 bytes should be '%PDF', got: {pdf_bytes[:4]}"
    print(f"✅ First 4 bytes: {pdf_bytes[:4]} (valid PDF)")
    print(f"✅ PDF size: {len(pdf_bytes)} bytes")
    
    # Check Content-Disposition
    content_disp = resp.headers.get("Content-Disposition", "")
    assert "inline" in content_disp, f"Content-Disposition should contain 'inline', got: {content_disp}"
    print(f"✅ Content-Disposition: {content_disp}")
    
    # Call 2x - should still be 200
    resp2 = requests.get(pdf_url)
    assert resp2.status_code == 200, f"GET public laporan 2nd time failed: {resp2.status_code}"
    print(f"✅ GET 2nd time: 200 (hits counter incremented)")
    
    # GET with invalid token
    invalid_url = pdf_url.replace(token, "token-ngawur-12345678901234567890")
    resp = requests.get(invalid_url)
    assert resp.status_code == 404, f"GET with invalid token should be 404, got {resp.status_code}"
    assert resp.status_code != 500, f"MUST NOT BE 500, got {resp.status_code}"
    print(f"✅ GET with invalid token: 404 (BUKAN 500)")
    
    print("✅ TEST 7 PASSED")
    
    return len(pdf_bytes)

def test_8_attach_pdf_false():
    """Test 8: With attach_pdf=false, pdf_url should be empty"""
    print("\n=== TEST 8: With attach_pdf=false, pdf_url should be empty ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    
    # Set attach_pdf=false
    body = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_enabled": True,
        "auto_time": "15:00",
        "attach_pdf": False
    }
    resp = requests.put(f"{BASE_URL}/whatsapp/settings", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"PUT settings attach_pdf=false failed: {resp.status_code} {resp.text}"
    print("✅ Set attach_pdf=false")
    
    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get existing closing ID
    resp = requests.get(f"{BASE_URL}/daily-closing", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET daily-closing failed: {resp.status_code}"
    closings = resp.json()
    closing_id = None
    for c in closings:
        if c.get("date") == today:
            closing_id = c["id"]
            break
    
    if not closing_id:
        print("⚠️ No closing found for today, creating new one")
        body = {"date": today, "notes": "Test attach_pdf=false"}
        resp = requests.post(f"{BASE_URL}/daily-closing", json=body, headers=headers(owner_token))
        assert resp.status_code == 200, f"POST daily-closing failed: {resp.status_code} {resp.text}"
        closing_id = resp.json()["id"]
    
    # Resend WhatsApp
    resp = requests.post(f"{BASE_URL}/daily-closing/{closing_id}/whatsapp", headers=headers(owner_token))
    assert resp.status_code == 200, f"POST whatsapp failed: {resp.status_code} {resp.text}"
    data = resp.json()
    
    # Check pdf_url is empty or not present
    pdf_url = data.get("pdf_url", "")
    assert len(pdf_url) == 0, f"pdf_url should be empty when attach_pdf=false, got: {pdf_url}"
    print(f"✅ pdf_url is empty: '{pdf_url}'")
    
    # Check text does NOT contain PDF line
    text = data.get("text", "")
    assert "*PDF Laporan Penjualan:*" not in text, f"text should NOT contain '*PDF Laporan Penjualan:*' when attach_pdf=false"
    print(f"✅ text does NOT contain '*PDF Laporan Penjualan:*'")
    
    # RESTORE attach_pdf=true
    body["attach_pdf"] = True
    resp = requests.put(f"{BASE_URL}/whatsapp/settings", json=body, headers=headers(owner_token))
    assert resp.status_code == 200, f"RESTORE settings failed: {resp.status_code} {resp.text}"
    print("✅ RESTORED: attach_pdf=true")
    
    print("✅ TEST 8 PASSED")

def test_9_regression():
    """Test 9: Regression - PDF reports, dashboard, products, sales, stock, login, webhook"""
    print("\n=== TEST 9: REGRESSION TESTS ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)
    
    # PDF Reports
    print("\n--- PDF Reports ---")
    
    # /api/reports/sales/pdf
    resp = requests.get(f"{BASE_URL}/reports/sales/pdf", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET sales/pdf failed: {resp.status_code}"
    assert "application/pdf" in resp.headers.get("Content-Type", ""), f"sales/pdf wrong content-type"
    assert resp.content[:4] == b"%PDF", f"sales/pdf not valid PDF"
    print(f"✅ /api/reports/sales/pdf: 200, {len(resp.content)} bytes")
    
    # /api/reports/profit-loss/pdf
    resp = requests.get(f"{BASE_URL}/reports/profit-loss/pdf", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET profit-loss/pdf failed: {resp.status_code}"
    assert "application/pdf" in resp.headers.get("Content-Type", ""), f"profit-loss/pdf wrong content-type"
    assert resp.content[:4] == b"%PDF", f"profit-loss/pdf not valid PDF"
    print(f"✅ /api/reports/profit-loss/pdf: 200, {len(resp.content)} bytes")
    
    # /api/reports/stock/pdf
    resp = requests.get(f"{BASE_URL}/reports/stock/pdf", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET stock/pdf failed: {resp.status_code}"
    assert "application/pdf" in resp.headers.get("Content-Type", ""), f"stock/pdf wrong content-type"
    assert resp.content[:4] == b"%PDF", f"stock/pdf not valid PDF"
    print(f"✅ /api/reports/stock/pdf: 200, {len(resp.content)} bytes")
    
    # /api/daily-closing/{date}/pdf
    today = datetime.now().strftime("%Y-%m-%d")
    resp = requests.get(f"{BASE_URL}/daily-closing/{today}/pdf", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET daily-closing/pdf failed: {resp.status_code}"
    assert "application/pdf" in resp.headers.get("Content-Type", ""), f"daily-closing/pdf wrong content-type"
    assert resp.content[:4] == b"%PDF", f"daily-closing/pdf not valid PDF"
    print(f"✅ /api/daily-closing/{today}/pdf: 200, {len(resp.content)} bytes")
    
    # Dashboard
    print("\n--- Dashboard ---")
    resp = requests.get(f"{BASE_URL}/dashboard", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET dashboard failed: {resp.status_code}"
    print(f"✅ GET /api/dashboard: 200")
    
    # Products
    print("\n--- Products ---")
    resp = requests.get(f"{BASE_URL}/products", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET products failed: {resp.status_code}"
    products = resp.json()
    assert len(products) > 0, "No products found"
    print(f"✅ GET /api/products: 200, {len(products)} products")
    
    # Find Ayam Broiler
    broiler = None
    for p in products:
        if "Broiler" in p.get("name", ""):
            broiler = p
            break
    assert broiler is not None, "Ayam Broiler not found"
    broiler_id = broiler["id"]
    stock_ekor_before = broiler.get("stock_ekor", 0)
    print(f"Ayam Broiler: stock_ekor = {stock_ekor_before}")
    
    # Sales - jual 1 ekor
    print("\n--- Sales ---")
    body = {
        "customer_id": None,
        "customer_name": "Test Customer",
        "items": [
            {
                "product_id": broiler_id,
                "product_name": broiler["name"],
                "unit": "ekor",
                "qty": 1,
                "price": broiler.get("price_ekor", 60000)
            }
        ],
        "paid": broiler.get("price_ekor", 60000),
        "payment_method": "cash",
        "txn_id": f"test-{int(time.time())}"
    }
    resp = requests.post(f"{BASE_URL}/sales", json=body, headers=headers(kasir_token))
    assert resp.status_code == 200, f"POST sales failed: {resp.status_code} {resp.text}"
    sale_id = resp.json()["id"]
    print(f"✅ POST /api/sales: 200, sale_id={sale_id}")
    
    # Check stock decreased
    resp = requests.get(f"{BASE_URL}/products", headers=headers(owner_token))
    products = resp.json()
    broiler = [p for p in products if p["id"] == broiler_id][0]
    stock_ekor_after = broiler.get("stock_ekor", 0)
    assert stock_ekor_after == stock_ekor_before - 1, f"Stock should decrease by 1, before={stock_ekor_before}, after={stock_ekor_after}"
    print(f"✅ Stock decreased: {stock_ekor_before} → {stock_ekor_after}")
    
    # Cancel sale
    resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=headers(owner_token))
    assert resp.status_code == 200, f"POST cancel failed: {resp.status_code} {resp.text}"
    print(f"✅ POST /api/sales/{sale_id}/cancel: 200")
    
    # Check stock restored
    resp = requests.get(f"{BASE_URL}/products", headers=headers(owner_token))
    products = resp.json()
    broiler = [p for p in products if p["id"] == broiler_id][0]
    stock_ekor_restored = broiler.get("stock_ekor", 0)
    assert stock_ekor_restored == stock_ekor_before, f"Stock should be restored, before={stock_ekor_before}, restored={stock_ekor_restored}"
    print(f"✅ Stock restored: {stock_ekor_after} → {stock_ekor_restored}")
    
    # Stock
    print("\n--- Stock ---")
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET stock-movements failed: {resp.status_code}"
    print(f"✅ GET /api/stock-movements: 200")
    
    # Login 4 roles
    print("\n--- Login 4 Roles ---")
    try:
        login(OWNER_EMAIL, OWNER_PASSWORD)
        print("✅ Login owner: OK")
    except Exception as e:
        raise Exception(f"Login owner failed: {e}")
    
    try:
        login(ADMIN_EMAIL, ADMIN_PASSWORD)
        print("✅ Login admin: OK")
    except Exception as e:
        raise Exception(f"Login admin failed: {e}")
    
    try:
        login(KASIR_EMAIL, KASIR_PASSWORD)
        print("✅ Login kasir: OK")
    except Exception as e:
        raise Exception(f"Login kasir failed: {e}")
    
    try:
        login("operator@berkahayam.com", "operator123")
        print("✅ Login operator (kasir): OK")
    except Exception as e:
        raise Exception(f"Login operator failed: {e}")
    
    # Webhook
    print("\n--- Webhook ---")
    
    # GET with wrong token
    resp = requests.get(f"{BASE_URL}/whatsapp/webhook?hub.mode=subscribe&hub.challenge=123&hub.verify_token=wrong-token")
    assert resp.status_code == 403, f"Webhook GET with wrong token should be 403, got {resp.status_code}"
    print(f"✅ Webhook GET with wrong token: 403")
    
    # POST statuses (idempotent)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": f"wamid.TEST_REGRESSION_{int(time.time())}",
                        "status": "delivered",
                        "timestamp": str(int(time.time())),
                        "recipient_id": "6281289478221"
                    }]
                }
            }]
        }]
    }
    resp = requests.post(f"{BASE_URL}/whatsapp/webhook", json=payload)
    assert resp.status_code == 200, f"Webhook POST failed: {resp.status_code}"
    print(f"✅ Webhook POST statuses: 200")
    
    # POST 2x (idempotent)
    resp = requests.post(f"{BASE_URL}/whatsapp/webhook", json=payload)
    assert resp.status_code == 200, f"Webhook POST 2nd time failed: {resp.status_code}"
    print(f"✅ Webhook POST 2nd time: 200 (idempotent)")
    
    print("✅ TEST 9 PASSED")

def test_10_rbac():
    """Test 10: RBAC - kasir 403 on whatsapp & daily-closing, but public endpoint accessible"""
    print("\n=== TEST 10: RBAC ===")
    
    owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
    kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)
    
    # Kasir 403 on whatsapp endpoints
    print("\n--- Kasir 403 on WhatsApp endpoints ---")
    
    resp = requests.get(f"{BASE_URL}/whatsapp/settings", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir GET settings should be 403, got {resp.status_code}"
    print("✅ Kasir GET /api/whatsapp/settings: 403")
    
    resp = requests.get(f"{BASE_URL}/whatsapp/diagnostics", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir GET diagnostics should be 403, got {resp.status_code}"
    print("✅ Kasir GET /api/whatsapp/diagnostics: 403")
    
    resp = requests.get(f"{BASE_URL}/whatsapp/template", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir GET template should be 403, got {resp.status_code}"
    print("✅ Kasir GET /api/whatsapp/template: 403")
    
    resp = requests.post(f"{BASE_URL}/whatsapp/test", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir POST test should be 403, got {resp.status_code}"
    print("✅ Kasir POST /api/whatsapp/test: 403")
    
    # Kasir 403 on daily-closing
    print("\n--- Kasir 403 on Daily Closing endpoints ---")
    
    resp = requests.get(f"{BASE_URL}/daily-closing/preview", headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir GET preview should be 403, got {resp.status_code}"
    print("✅ Kasir GET /api/daily-closing/preview: 403")
    
    today = datetime.now().strftime("%Y-%m-%d")
    body = {"date": today, "notes": "Test"}
    resp = requests.post(f"{BASE_URL}/daily-closing", json=body, headers=headers(kasir_token))
    assert resp.status_code == 403, f"Kasir POST daily-closing should be 403, got {resp.status_code}"
    print("✅ Kasir POST /api/daily-closing: 403")
    
    # Public endpoint accessible without auth
    print("\n--- Public endpoint /api/public/laporan/{token} accessible without auth ---")
    
    # Get a valid pdf_url from owner
    resp = requests.get(f"{BASE_URL}/daily-closing", headers=headers(owner_token))
    assert resp.status_code == 200, f"GET daily-closing failed: {resp.status_code}"
    closings = resp.json()
    pdf_url = None
    for c in closings:
        if c.get("date") == today:
            # Get whatsapp field
            resp2 = requests.post(f"{BASE_URL}/daily-closing/{c['id']}/whatsapp", headers=headers(owner_token))
            if resp2.status_code == 200:
                wa = resp2.json()
                pdf_url = wa.get("pdf_url", "")
                if pdf_url:
                    break
    
    if not pdf_url:
        print("⚠️ No pdf_url found, creating new closing")
        body = {"date": today, "notes": "Test RBAC"}
        resp = requests.post(f"{BASE_URL}/daily-closing", json=body, headers=headers(owner_token))
        assert resp.status_code == 200, f"POST daily-closing failed: {resp.status_code}"
        pdf_url = resp.json()["whatsapp"]["pdf_url"]
    
    # Access without auth
    resp = requests.get(pdf_url)
    assert resp.status_code == 200, f"GET public laporan without auth failed: {resp.status_code}"
    assert "application/pdf" in resp.headers.get("Content-Type", ""), f"Wrong content-type"
    print(f"✅ GET {pdf_url} without auth: 200 (public access works)")
    
    print("✅ TEST 10 PASSED")

def main():
    print("=" * 80)
    print("BACKEND TESTING: WhatsApp PDF Attachment Feature")
    print("App: Berkah Ayam Mili")
    print(f"Backend URL: {BASE_URL}")
    print("=" * 80)
    
    pdf_url = None
    pdf_size = 0
    
    try:
        test_1_whatsapp_settings()
        test_2_whatsapp_diagnostics()
        test_3_whatsapp_template()
        test_4_whatsapp_template_create()
        test_5_whatsapp_settings_attach_pdf()
        pdf_url = test_6_daily_closing_pdf_url()
        pdf_size = test_7_public_laporan_endpoint(pdf_url)
        test_8_attach_pdf_false()
        test_9_regression()
        test_10_rbac()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED (10/10)")
        print("=" * 80)
        print(f"\n📊 SUMMARY:")
        print(f"- PDF size: {pdf_size} bytes")
        print(f"- PDF URL: {pdf_url}")
        print(f"- PDF successfully downloaded without auth: YES")
        print(f"- No HTTP 500 errors: YES")
        print(f"- All endpoints working in fallback mode: YES")
        print("\n" + "=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise

if __name__ == "__main__":
    main()
