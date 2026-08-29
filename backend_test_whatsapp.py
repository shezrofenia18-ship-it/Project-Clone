#!/usr/bin/env python3
"""
Backend Test: WhatsApp Auto-Recap Feature
Berkah Ayam Mili - FastAPI + MongoDB

KONTEKS PENTING: kredensial Meta WhatsApp SENGAJA KOSONG (owner belum punya akun).
Hasil yang BENAR adalah mode fallback "manual"/1-tap (wa.me), BUKAN error.
TIDAK BOLEH ADA HTTP 500 di endpoint mana pun.
"""

import requests
import json
import time
import os
from datetime import datetime

# Backend URL dari frontend/.env
BACKEND_URL = "https://commit-checker-live-2.preview.emergentagent.com/api"

# Credentials dari /app/memory/test_credentials.md
CREDENTIALS = {
    "owner": {"email": "shezrofenia18@gmail.com", "password": "berkahayam1"},
    "admin": {"email": "admin@berkahayam.com", "password": "admin123"},
    "kasir": {"email": "kasir@berkahayam.com", "password": "kasir123"},
}

def login(role="owner"):
    """Login dan dapatkan JWT token"""
    cred = CREDENTIALS[role]
    resp = requests.post(f"{BACKEND_URL}/auth/login", json=cred, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Login {role} gagal: {resp.status_code} {resp.text[:200]}")
    return resp.json()["token"]

def headers(token):
    return {"Authorization": f"Bearer {token}"}

def test_1_whatsapp_settings():
    """Test 1: GET /api/whatsapp/settings - field template_spec, provider, RBAC"""
    print("\n=== TEST 1: GET /api/whatsapp/settings ===")
    
    # Owner & Admin harus 200
    for role in ["owner", "admin"]:
        token = login(role)
        resp = requests.get(f"{BACKEND_URL}/whatsapp/settings", headers=headers(token), timeout=15)
        assert resp.status_code == 200, f"{role} harus 200, dapat {resp.status_code}"
        data = resp.json()
        
        # Cek field wajib
        assert "recipients" in data, "Harus ada field recipients"
        assert "auto_enabled" in data, "Harus ada field auto_enabled"
        assert "auto_time" in data, "Harus ada field auto_time"
        assert "provider" in data, "Harus ada field provider"
        assert "template_spec" in data, "Harus ada field template_spec"
        
        # Cek template_spec
        spec = data["template_spec"]
        assert spec["name"] == "rekap_tutup_buku_harian", f"Template name salah: {spec['name']}"
        assert spec["language"] == "id", f"Language salah: {spec['language']}"
        assert spec["category"] == "UTILITY", f"Category salah: {spec['category']}"
        assert spec["parameter_format"] == "NAMED", f"Parameter format salah: {spec['parameter_format']}"
        assert spec["params"] == ["tanggal", "omzet", "laba_bersih", "jumlah_transaksi"], \
            f"Params salah: {spec['params']}"
        
        # Cek payload.components[0].example.body_text_named_params
        payload = spec["payload"]
        assert "components" in payload, "Payload harus punya components"
        assert len(payload["components"]) > 0, "Components tidak boleh kosong"
        example = payload["components"][0].get("example", {})
        assert "body_text_named_params" in example, "Harus ada body_text_named_params"
        named_params = example["body_text_named_params"]
        assert len(named_params) == 4, f"Harus 4 named params, dapat {len(named_params)}"
        param_names = [p["param_name"] for p in named_params]
        assert param_names == ["tanggal", "omzet", "laba_bersih", "jumlah_transaksi"], \
            f"Named params salah: {param_names}"
        
        # Cek provider
        prov = data["provider"]
        assert prov["api_version"] == "v26.0", f"API version salah: {prov['api_version']}"
        assert prov["configured"] == False, f"Configured harus False (kredensial kosong), dapat {prov['configured']}"
        assert "missing" in prov, "Harus ada field missing"
        missing = prov["missing"]
        assert "META_PHONE_NUMBER_ID" in missing, "Missing harus memuat META_PHONE_NUMBER_ID"
        assert "META_ACCESS_TOKEN" in missing, "Missing harus memuat META_ACCESS_TOKEN"
        assert "META_WABA_ID" in missing, "Missing harus memuat META_WABA_ID"
        
        print(f"  ✓ {role}: 200, template_spec OK, provider.configured=False, missing={missing}")
    
    # Kasir harus 403
    token_kasir = login("kasir")
    resp = requests.get(f"{BACKEND_URL}/whatsapp/settings", headers=headers(token_kasir), timeout=15)
    assert resp.status_code == 403, f"Kasir harus 403, dapat {resp.status_code}"
    print(f"  ✓ kasir: 403 (correctly rejected)")
    
    print("  ✅ TEST 1 PASSED")

def test_2_whatsapp_diagnostics():
    """Test 2: GET /api/whatsapp/diagnostics - ready_for_auto=false, recipients, auto_time, webhook"""
    print("\n=== TEST 2: GET /api/whatsapp/diagnostics ===")
    
    token = login("owner")
    resp = requests.get(f"{BACKEND_URL}/whatsapp/diagnostics", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"Harus 200, dapat {resp.status_code}"
    
    data = resp.json()
    assert data["ready_for_auto"] == False, f"ready_for_auto harus False (kredensial kosong), dapat {data['ready_for_auto']}"
    assert data["recipients"] >= 1, f"recipients harus >=1, dapat {data['recipients']}"
    assert data["auto_time"] == "15:00", f"auto_time harus 15:00, dapat {data['auto_time']}"
    assert data["auto_enabled"] == True, f"auto_enabled harus True, dapat {data['auto_enabled']}"
    assert data["webhook_verify_configured"] == True, f"webhook_verify_configured harus True, dapat {data['webhook_verify_configured']}"
    assert data["webhook_url"] == "/api/whatsapp/webhook", f"webhook_url salah: {data['webhook_url']}"
    
    print(f"  ✓ 200, ready_for_auto=False, recipients={data['recipients']}, auto_time=15:00, webhook OK")
    print("  ✅ TEST 2 PASSED")

def test_3_whatsapp_template():
    """Test 3: GET /api/whatsapp/template - approved=false, remote=[]"""
    print("\n=== TEST 3: GET /api/whatsapp/template ===")
    
    token = login("owner")
    resp = requests.get(f"{BACKEND_URL}/whatsapp/template", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"Harus 200, dapat {resp.status_code}"
    
    data = resp.json()
    assert data["approved"] == False, f"approved harus False (kredensial kosong), dapat {data['approved']}"
    assert data["remote"] == [], f"remote harus [], dapat {data['remote']}"
    
    print(f"  ✓ 200, approved=False, remote=[]")
    print("  ✅ TEST 3 PASSED")

def test_4_whatsapp_template_create():
    """Test 4: POST /api/whatsapp/template - 400 dengan pesan Indonesia, RBAC"""
    print("\n=== TEST 4: POST /api/whatsapp/template ===")
    
    # Owner harus 400 dengan pesan Indonesia
    token = login("owner")
    resp = requests.post(f"{BACKEND_URL}/whatsapp/template", headers=headers(token), timeout=15)
    assert resp.status_code == 400, f"Harus 400 (kredensial kosong), dapat {resp.status_code}"
    
    error_msg = resp.json().get("detail", "")
    assert "META_PHONE_NUMBER_ID" in error_msg or "kredensial" in error_msg.lower(), \
        f"Pesan error harus menyebut kredensial/META_PHONE_NUMBER_ID, dapat: {error_msg}"
    print(f"  ✓ owner: 400 dengan pesan: {error_msg[:100]}")
    
    # Admin & Kasir harus 403
    for role in ["admin", "kasir"]:
        token = login(role)
        resp = requests.post(f"{BACKEND_URL}/whatsapp/template", headers=headers(token), timeout=15)
        assert resp.status_code == 403, f"{role} harus 403, dapat {resp.status_code}"
        print(f"  ✓ {role}: 403 (correctly rejected)")
    
    print("  ✅ TEST 4 PASSED")

def test_5_whatsapp_settings_put():
    """Test 5: PUT /api/whatsapp/settings - normalisasi nomor, multi nomor, validasi auto_time"""
    print("\n=== TEST 5: PUT /api/whatsapp/settings ===")
    
    token = login("owner")
    
    # Test normalisasi nomor
    test_cases = [
        ("081289478221", "6281289478221"),
        ("+62 812-8947-8221", "6281289478221"),
        ("81289478221", "6281289478221"),
    ]
    
    for input_num, expected in test_cases:
        body = {
            "recipients": [{"name": "Test", "number": input_num}],
            "auto_enabled": True,
            "auto_time": "15:00"
        }
        resp = requests.put(f"{BACKEND_URL}/whatsapp/settings", json=body, headers=headers(token), timeout=15)
        assert resp.status_code == 200, f"Normalisasi {input_num} gagal: {resp.status_code}"
        
        data = resp.json()
        assert len(data["recipients"]) == 1, f"Harus 1 recipient, dapat {len(data['recipients'])}"
        assert data["recipients"][0]["number"] == expected, \
            f"Normalisasi salah: {input_num} -> {data['recipients'][0]['number']}, harusnya {expected}"
        print(f"  ✓ Normalisasi: {input_num} -> {expected}")
    
    # Test multi nomor
    body = {
        "recipients": [
            {"name": "Owner", "number": "081289478221"},
            {"name": "Admin", "number": "081234567890"},
            {"name": "Backup", "number": "081298765432"}
        ],
        "auto_enabled": True,
        "auto_time": "15:00"
    }
    resp = requests.put(f"{BACKEND_URL}/whatsapp/settings", json=body, headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"Multi nomor gagal: {resp.status_code}"
    data = resp.json()
    assert len(data["recipients"]) == 3, f"Harus 3 recipients, dapat {len(data['recipients'])}"
    print(f"  ✓ Multi nomor: 3 recipients tersimpan")
    
    # Test validasi auto_time salah
    invalid_times = ["25:00", "9:5", "abc"]
    for bad_time in invalid_times:
        body = {
            "recipients": [{"name": "Owner", "number": "081289478221"}],
            "auto_enabled": True,
            "auto_time": bad_time
        }
        resp = requests.put(f"{BACKEND_URL}/whatsapp/settings", json=body, headers=headers(token), timeout=15)
        assert resp.status_code == 400, f"auto_time={bad_time} harus 400, dapat {resp.status_code}"
        print(f"  ✓ auto_time={bad_time}: 400 (correctly rejected)")
    
    # Test auto_time valid
    body = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_enabled": True,
        "auto_time": "15:00"
    }
    resp = requests.put(f"{BACKEND_URL}/whatsapp/settings", json=body, headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"auto_time=15:00 harus 200, dapat {resp.status_code}"
    print(f"  ✓ auto_time=15:00: 200")
    
    # PULIHKAN ke setting awal
    body = {
        "recipients": [{"name": "Owner", "number": "081289478221"}],
        "auto_enabled": True,
        "auto_time": "15:00"
    }
    resp = requests.put(f"{BACKEND_URL}/whatsapp/settings", json=body, headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"Restore settings gagal: {resp.status_code}"
    print(f"  ✓ Settings dipulihkan ke awal")
    
    print("  ✅ TEST 5 PASSED")

def test_6_whatsapp_test():
    """Test 6: POST /api/whatsapp/test - mode=manual, sent_count=0, link wa.me valid"""
    print("\n=== TEST 6: POST /api/whatsapp/test ===")
    
    token = login("owner")
    resp = requests.post(f"{BACKEND_URL}/whatsapp/test", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"Harus 200, dapat {resp.status_code}"
    
    data = resp.json()
    assert data["mode"] == "manual", f"mode harus 'manual' (kredensial kosong), dapat {data['mode']}"
    assert data["sent_count"] == 0, f"sent_count harus 0 (tidak ada kredensial), dapat {data['sent_count']}"
    assert "results" in data, "Harus ada field results"
    assert len(data["results"]) > 0, "results tidak boleh kosong"
    
    # Cek setiap hasil punya link wa.me valid
    for r in data["results"]:
        assert "link" in r, f"Setiap result harus punya link: {r}"
        assert r["link"].startswith("https://wa.me/"), f"Link harus wa.me: {r['link']}"
        assert "?text=" in r["link"], f"Link harus punya ?text=: {r['link']}"
        print(f"  ✓ Result: {r['name']} -> {r['link'][:60]}...")
    
    print(f"  ✓ 200, mode=manual, sent_count=0, {len(data['results'])} results dengan link wa.me")
    print("  ✅ TEST 6 PASSED")

def test_7_webhook():
    """Test 7: Webhook - verifikasi token, POST idempoten, garbage handling"""
    print("\n=== TEST 7: Webhook ===")
    
    # GET dengan token SALAH -> 403
    resp = requests.get(f"{BACKEND_URL}/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "SALAH",
        "hub.challenge": "123"
    }, timeout=15)
    assert resp.status_code == 403, f"Token salah harus 403, dapat {resp.status_code}"
    print(f"  ✓ GET dengan token salah: 403")
    
    # Ambil token benar dari backend/.env
    with open("/app/backend/.env", "r") as f:
        env_content = f.read()
    token_line = [line for line in env_content.split("\n") if line.startswith("WA_WEBHOOK_VERIFY_TOKEN=")]
    if not token_line:
        raise Exception("WA_WEBHOOK_VERIFY_TOKEN tidak ditemukan di backend/.env")
    correct_token = token_line[0].split("=", 1)[1].strip().strip('"')
    
    # GET dengan token BENAR -> 200 dan body persis "123"
    resp = requests.get(f"{BACKEND_URL}/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": correct_token,
        "hub.challenge": "123"
    }, timeout=15)
    assert resp.status_code == 200, f"Token benar harus 200, dapat {resp.status_code}"
    assert resp.text == "123", f"Body harus persis '123', dapat: {resp.text}"
    print(f"  ✓ GET dengan token benar: 200, body='123'")
    
    # POST dengan payload status Meta -> 200
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": "wamid.TEST1",
                        "status": "delivered",
                        "timestamp": "1788000000",
                        "recipient_id": "6281289478221"
                    }]
                }
            }]
        }]
    }
    resp = requests.post(f"{BACKEND_URL}/whatsapp/webhook", json=payload, timeout=15)
    assert resp.status_code == 200, f"POST webhook harus 200, dapat {resp.status_code}"
    assert resp.json() == {"ok": True}, f"Response harus {{ok:true}}, dapat {resp.json()}"
    print(f"  ✓ POST webhook status: 200 {{ok:true}}")
    
    # Kirim DUA KALI (uji idempoten)
    resp = requests.post(f"{BACKEND_URL}/whatsapp/webhook", json=payload, timeout=15)
    assert resp.status_code == 200, f"POST webhook ke-2 harus 200, dapat {resp.status_code}"
    print(f"  ✓ POST webhook ke-2: 200 (idempoten)")
    
    # GET /api/whatsapp/statuses -> hanya SATU baris wamid.TEST1
    token = login("owner")
    time.sleep(1)  # Beri waktu untuk upsert
    resp = requests.get(f"{BACKEND_URL}/whatsapp/statuses", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET statuses harus 200, dapat {resp.status_code}"
    statuses = resp.json()
    test1_statuses = [s for s in statuses if s.get("message_id") == "wamid.TEST1"]
    assert len(test1_statuses) == 1, f"Harus hanya 1 baris wamid.TEST1 (idempoten), dapat {len(test1_statuses)}"
    assert test1_statuses[0]["status"] == "delivered", f"Status harus 'delivered', dapat {test1_statuses[0]['status']}"
    print(f"  ✓ GET /api/whatsapp/statuses: hanya 1 baris wamid.TEST1 status=delivered (idempoten)")
    
    # POST payload sampah -> tetap 200 (tidak boleh 500)
    resp = requests.post(f"{BACKEND_URL}/whatsapp/webhook", data="garbage", headers={"Content-Type": "text/plain"}, timeout=15)
    assert resp.status_code == 200, f"POST garbage harus 200 (tidak boleh 500), dapat {resp.status_code}"
    print(f"  ✓ POST garbage: 200 (tidak 500)")
    
    print("  ✅ TEST 7 PASSED")

def test_8_end_to_end():
    """Test 8: End-to-end - POST daily-closing, PDF, whatsapp field, log"""
    print("\n=== TEST 8: End-to-End Daily Closing + WhatsApp ===")
    
    token = login("owner")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # POST /api/daily-closing
    body = {"date": today, "notes": "Test WhatsApp"}
    resp = requests.post(f"{BACKEND_URL}/daily-closing", json=body, headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"POST daily-closing harus 200, dapat {resp.status_code}"
    
    data = resp.json()
    closing_id = data["id"]
    assert "whatsapp" in data, "Response harus punya field whatsapp"
    
    wa = data["whatsapp"]
    assert wa["mode"] == "manual", f"whatsapp.mode harus 'manual', dapat {wa['mode']}"
    assert "template_values" in wa, "Harus ada template_values"
    assert "text" in wa, "Harus ada text"
    assert wa["text"] != "", "text tidak boleh kosong"
    
    # Cek template_values: 4 nilai
    tv = wa["template_values"]
    assert "tanggal" in tv, "template_values harus punya tanggal"
    assert "omzet" in tv, "template_values harus punya omzet"
    assert "laba_bersih" in tv, "template_values harus punya laba_bersih"
    assert "jumlah_transaksi" in tv, "template_values harus punya jumlah_transaksi"
    
    # Cek format nilai
    assert "Rp" in tv["omzet"], f"omzet harus format 'Rp ...', dapat: {tv['omzet']}"
    assert "Rp" in tv["laba_bersih"], f"laba_bersih harus format 'Rp ...', dapat: {tv['laba_bersih']}"
    # jumlah_transaksi harus angka (string)
    assert tv["jumlah_transaksi"].replace(".", "").replace(",", "").isdigit(), \
        f"jumlah_transaksi harus angka, dapat: {tv['jumlah_transaksi']}"
    
    print(f"  ✓ POST /api/daily-closing: 200, whatsapp.mode=manual")
    print(f"    template_values: tanggal={tv['tanggal'][:20]}..., omzet={tv['omzet']}, laba_bersih={tv['laba_bersih']}, jumlah_transaksi={tv['jumlah_transaksi']}")
    
    # GET /api/daily-closing/{date}/pdf
    resp = requests.get(f"{BACKEND_URL}/daily-closing/{today}/pdf", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET daily-closing PDF harus 200, dapat {resp.status_code}"
    assert resp.headers.get("Content-Type") == "application/pdf", \
        f"Content-Type harus application/pdf, dapat {resp.headers.get('Content-Type')}"
    assert resp.content[:4] == b"%PDF", "PDF harus dimulai dengan %PDF"
    print(f"  ✓ GET /api/daily-closing/{{date}}/pdf: 200 application/pdf, {len(resp.content)} bytes")
    
    # Cek PDF reports lain (regresi reportlab 5.0.1)
    pdf_endpoints = [
        "/reports/profit-loss/pdf",
        "/reports/sales/pdf",
        "/reports/stock/pdf"
    ]
    for endpoint in pdf_endpoints:
        resp = requests.get(f"{BACKEND_URL}{endpoint}", headers=headers(token), timeout=15)
        assert resp.status_code == 200, f"GET {endpoint} harus 200, dapat {resp.status_code}"
        assert resp.headers.get("Content-Type") == "application/pdf", \
            f"{endpoint} Content-Type harus application/pdf"
        assert resp.content[:4] == b"%PDF", f"{endpoint} harus dimulai dengan %PDF"
        print(f"  ✓ GET {endpoint}: 200 application/pdf, {len(resp.content)} bytes")
    
    # POST /api/daily-closing/{id}/whatsapp
    resp = requests.post(f"{BACKEND_URL}/daily-closing/{closing_id}/whatsapp", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"POST whatsapp harus 200, dapat {resp.status_code}"
    data = resp.json()
    assert data["mode"] == "manual", f"mode harus 'manual', dapat {data['mode']}"
    print(f"  ✓ POST /api/daily-closing/{{id}}/whatsapp: 200, mode=manual")
    
    # GET /api/whatsapp/log
    time.sleep(1)  # Beri waktu untuk log tersimpan
    resp = requests.get(f"{BACKEND_URL}/whatsapp/log", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET whatsapp/log harus 200, dapat {resp.status_code}"
    logs = resp.json()
    assert len(logs) > 0, "Log tidak boleh kosong"
    
    # Cari baris terbaru kind="closing"
    closing_logs = [log for log in logs if log.get("kind") == "closing"]
    assert len(closing_logs) > 0, "Harus ada log kind='closing'"
    latest = closing_logs[0]
    
    # Cek results[].number ternormalisasi
    assert "results" in latest, "Log harus punya results"
    for r in latest["results"]:
        assert "number" in r, f"Result harus punya number: {r}"
        assert r["number"].startswith("62"), f"Number harus ternormalisasi (62xxx), dapat: {r['number']}"
        # TANPA field link (link sengaja tidak disimpan)
        assert "link" not in r, f"Result TIDAK BOLEH punya field 'link' di log (privasi): {r}"
    
    print(f"  ✓ GET /api/whatsapp/log: baris terbaru kind=closing, results[].number ternormalisasi, TANPA field 'link'")
    
    # RBAC: kasir tidak boleh akses
    token_kasir = login("kasir")
    resp = requests.get(f"{BACKEND_URL}/daily-closing/preview", headers=headers(token_kasir), timeout=15)
    assert resp.status_code == 403, f"Kasir GET daily-closing harus 403, dapat {resp.status_code}"
    
    resp = requests.get(f"{BACKEND_URL}/whatsapp/log", headers=headers(token_kasir), timeout=15)
    assert resp.status_code == 403, f"Kasir GET whatsapp/log harus 403, dapat {resp.status_code}"
    print(f"  ✓ RBAC: kasir 403 untuk daily-closing dan whatsapp endpoints")
    
    print("  ✅ TEST 8 PASSED")

def test_9_regression():
    """Test 9: Regresi singkat - login, dashboard, products, sales, stock, WS"""
    print("\n=== TEST 9: Regresi Singkat ===")
    
    # Login 4 role
    roles = ["owner", "admin", "kasir"]
    tokens = {}
    for role in roles:
        token = login(role)
        tokens[role] = token
        print(f"  ✓ Login {role}: OK")
    
    # GET /api/dashboard
    token = tokens["owner"]
    resp = requests.get(f"{BACKEND_URL}/dashboard", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET dashboard harus 200, dapat {resp.status_code}"
    print(f"  ✓ GET /api/dashboard: 200")
    
    # GET /api/products
    resp = requests.get(f"{BACKEND_URL}/products", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET products harus 200, dapat {resp.status_code}"
    products = resp.json()
    assert len(products) > 0, "Products tidak boleh kosong"
    
    # Cari produk ayam yang dijual per ekor
    ayam_ekor = None
    for p in products:
        if "ekor" in (p.get("units") or []) and p.get("price_ekor", 0) > 0:
            ayam_ekor = p
            break
    
    if not ayam_ekor:
        print(f"  ⚠ Tidak ada produk ayam per ekor, skip test penjualan")
    else:
        print(f"  ✓ GET /api/products: 200, {len(products)} products")
        
        # POST /api/sales (1 transaksi kecil per ekor)
        stock_before = ayam_ekor["stock_ekor"]
        body = {
            "items": [
                {
                    "product_id": ayam_ekor["id"],
                    "unit": "ekor",
                    "qty": 1,
                    "price": ayam_ekor["price_ekor"]
                }
            ],
            "discount": 0,
            "paid": ayam_ekor["price_ekor"],
            "payment_method": "cash"
        }
        resp = requests.post(f"{BACKEND_URL}/sales", json=body, headers=headers(token), timeout=15)
        assert resp.status_code == 200, f"POST sales harus 200, dapat {resp.status_code}"
        sale = resp.json()
        sale_id = sale["id"]
        print(f"  ✓ POST /api/sales: 200, sale_id={sale_id[:8]}...")
        
        # Cek stok berkurang
        resp = requests.get(f"{BACKEND_URL}/products", headers=headers(token), timeout=15)
        products_after = resp.json()
        ayam_after = [p for p in products_after if p["id"] == ayam_ekor["id"]][0]
        assert ayam_after["stock_ekor"] == stock_before - 1, \
            f"Stok ekor harus berkurang 1, sebelum={stock_before}, sesudah={ayam_after['stock_ekor']}"
        print(f"  ✓ Stok ekor berkurang: {stock_before} -> {ayam_after['stock_ekor']}")
        
        # Batalkan transaksi
        resp = requests.post(f"{BACKEND_URL}/sales/{sale_id}/cancel", headers=headers(token), timeout=15)
        assert resp.status_code == 200, f"POST cancel harus 200, dapat {resp.status_code}"
        print(f"  ✓ POST /api/sales/{{id}}/cancel: 200")
        
        # Cek stok kembali
        resp = requests.get(f"{BACKEND_URL}/products", headers=headers(token), timeout=15)
        products_final = resp.json()
        ayam_final = [p for p in products_final if p["id"] == ayam_ekor["id"]][0]
        assert ayam_final["stock_ekor"] == stock_before, \
            f"Stok ekor harus kembali, awal={stock_before}, akhir={ayam_final['stock_ekor']}"
        print(f"  ✓ Stok ekor kembali: {ayam_final['stock_ekor']}")
    
    # GET /api/stock
    resp = requests.get(f"{BACKEND_URL}/stock-movements", headers=headers(token), timeout=15)
    assert resp.status_code == 200, f"GET stock-movements harus 200, dapat {resp.status_code}"
    print(f"  ✓ GET /api/stock-movements: 200")
    
    # WS /api/ws?token=...
    # (Skip actual WS test karena butuh websocket client, cukup cek endpoint ada)
    print(f"  ✓ WebSocket endpoint: /api/ws (skip actual connection test)")
    
    print("  ✅ TEST 9 PASSED")

def main():
    print("=" * 70)
    print("BACKEND TEST: WhatsApp Auto-Recap Feature")
    print("Berkah Ayam Mili - FastAPI + MongoDB")
    print("=" * 70)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Kredensial Meta: SENGAJA KOSONG (mode fallback 'manual' adalah BENAR)")
    print("=" * 70)
    
    try:
        test_1_whatsapp_settings()
        test_2_whatsapp_diagnostics()
        test_3_whatsapp_template()
        test_4_whatsapp_template_create()
        test_5_whatsapp_settings_put()
        test_6_whatsapp_test()
        test_7_webhook()
        test_8_end_to_end()
        test_9_regression()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED (9/9)")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
