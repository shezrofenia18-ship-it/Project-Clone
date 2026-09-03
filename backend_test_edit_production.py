#!/usr/bin/env python3
"""
Backend Test: Edit Produksi Potong + Penyesuaian Stok Pcs
Iterasi 2026-09-03

Test fokus pada 2 fitur baru:
A. PUT /api/productions/{id} - koreksi produksi potong dengan penyesuaian stok via SELISIH
B. POST /api/stock-adjustments - dukungan delta_pcs

CRITICAL: Stok harus digeser sebesar SELISIH, bukan dobel/reset.
"""

import requests
import json
from typing import Dict, Any, Optional

BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"

# ============ Helper Functions ============

def login(username: str, password: str) -> str:
    """Login dan return token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {username}: {resp.status_code} {resp.text}")
    data = resp.json()
    return data["token"]

def get_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def get_product(token: str, product_id: str) -> Dict[str, Any]:
    """Get product by ID"""
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    if resp.status_code != 200:
        raise Exception(f"Failed to get products: {resp.status_code}")
    products = resp.json()
    for p in products:
        if p["id"] == product_id:
            return p
    raise Exception(f"Product {product_id} not found")

def get_products_by_category(token: str, category: str) -> list:
    """Get products by category"""
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    if resp.status_code != 200:
        raise Exception(f"Failed to get products: {resp.status_code}")
    products = resp.json()
    return [p for p in products if p.get("category") == category]

def find_product_by_name(token: str, name: str) -> Optional[Dict[str, Any]]:
    """Find product by name (case-insensitive contains)"""
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    if resp.status_code != 200:
        return None
    products = resp.json()
    name_lower = name.lower()
    for p in products:
        if name_lower in p["name"].lower():
            return p
    return None

def round_float(val, decimals=3):
    """Round float untuk perbandingan"""
    return round(float(val or 0), decimals)

# ============ Test Functions ============

def test_a1_create_and_edit_production_increase_input():
    """
    A1. Buat produksi baru, lalu edit dengan MENAIKKAN input_ekor dan MENGUBAH pcs output.
    Verifikasi: stok berubah sebesar SELISIH, bukan dobel/reset.
    """
    print("\n" + "="*80)
    print("TEST A1: Create Production + Edit (Increase Input, Change Output Pcs)")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # 1. Cari produk sumber (ayam utuh) dan produk output (potongan)
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    if not ayam_broiler:
        print("❌ Ayam Broiler not found")
        return False
    
    # Cari produk potongan (kategori "potongan")
    potongan = get_products_by_category(token, "potongan")
    if len(potongan) < 2:
        print(f"❌ Need at least 2 potongan products, found {len(potongan)}")
        return False
    
    dada = next((p for p in potongan if "dada" in p["name"].lower()), potongan[0])
    paha = next((p for p in potongan if "paha" in p["name"].lower() and "atas" in p["name"].lower()), potongan[1])
    
    print(f"✓ Source: {ayam_broiler['name']} (id={ayam_broiler['id']})")
    print(f"✓ Output 1: {dada['name']} (id={dada['id']})")
    print(f"✓ Output 2: {paha['name']} (id={paha['id']})")
    
    # 2. Catat stok SEBELUM produksi
    stock_before = {
        "source_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "dada_pcs": round_float(dada.get("stock_pcs")),
        "paha_pcs": round_float(paha.get("stock_pcs"))
    }
    print(f"\n📊 STOCK BEFORE PRODUCTION:")
    print(f"   Source ekor: {stock_before['source_ekor']}")
    print(f"   Dada pcs: {stock_before['dada_pcs']}")
    print(f"   Paha pcs: {stock_before['paha_pcs']}")
    
    # 3. Buat produksi: 5 ekor -> Dada 10 pcs, Paha 10 pcs
    prod_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 5,
        "outputs": [
            {"product_id": dada["id"], "pcs": 10},
            {"product_id": paha["id"], "pcs": 10}
        ],
        "operator": "Test Operator"
    }
    
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token), json=prod_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create production: {resp.status_code} {resp.text}")
        return False
    
    production = resp.json()
    prod_id = production["id"]
    print(f"\n✓ Production created: id={prod_id}")
    
    # 4. Catat stok SETELAH produksi
    ayam_broiler = get_product(token, ayam_broiler["id"])
    dada = get_product(token, dada["id"])
    paha = get_product(token, paha["id"])
    
    stock_after_create = {
        "source_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "dada_pcs": round_float(dada.get("stock_pcs")),
        "paha_pcs": round_float(paha.get("stock_pcs"))
    }
    print(f"\n📊 STOCK AFTER PRODUCTION:")
    print(f"   Source ekor: {stock_after_create['source_ekor']} (delta: {stock_after_create['source_ekor'] - stock_before['source_ekor']})")
    print(f"   Dada pcs: {stock_after_create['dada_pcs']} (delta: {stock_after_create['dada_pcs'] - stock_before['dada_pcs']})")
    print(f"   Paha pcs: {stock_after_create['paha_pcs']} (delta: {stock_after_create['paha_pcs'] - stock_before['paha_pcs']})")
    
    # Verifikasi delta produksi
    if abs(stock_after_create['source_ekor'] - stock_before['source_ekor'] + 5) > 0.01:
        print(f"❌ Source ekor delta incorrect: expected -5, got {stock_after_create['source_ekor'] - stock_before['source_ekor']}")
        return False
    if abs(stock_after_create['dada_pcs'] - stock_before['dada_pcs'] - 10) > 0.01:
        print(f"❌ Dada pcs delta incorrect: expected +10, got {stock_after_create['dada_pcs'] - stock_before['dada_pcs']}")
        return False
    if abs(stock_after_create['paha_pcs'] - stock_before['paha_pcs'] - 10) > 0.01:
        print(f"❌ Paha pcs delta incorrect: expected +10, got {stock_after_create['paha_pcs'] - stock_before['paha_pcs']}")
        return False
    
    print("✓ Production stock changes correct")
    
    # 5. EDIT produksi: input_ekor 5->8, Dada 10->6, Paha 10->15
    edit_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 8,
        "outputs": [
            {"product_id": dada["id"], "pcs": 6},
            {"product_id": paha["id"], "pcs": 15}
        ],
        "operator": "Test Operator"
    }
    
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}", headers=get_headers(token), json=edit_body)
    if resp.status_code != 200:
        print(f"❌ Failed to edit production: {resp.status_code} {resp.text}")
        return False
    
    print(f"\n✓ Production edited: input_ekor 5->8, Dada 10->6, Paha 10->15")
    
    # 6. Catat stok SETELAH edit
    ayam_broiler = get_product(token, ayam_broiler["id"])
    dada = get_product(token, dada["id"])
    paha = get_product(token, paha["id"])
    
    stock_after_edit = {
        "source_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "dada_pcs": round_float(dada.get("stock_pcs")),
        "paha_pcs": round_float(paha.get("stock_pcs"))
    }
    print(f"\n📊 STOCK AFTER EDIT:")
    print(f"   Source ekor: {stock_after_edit['source_ekor']} (delta from after_create: {stock_after_edit['source_ekor'] - stock_after_create['source_ekor']})")
    print(f"   Dada pcs: {stock_after_edit['dada_pcs']} (delta from after_create: {stock_after_edit['dada_pcs'] - stock_after_create['dada_pcs']})")
    print(f"   Paha pcs: {stock_after_edit['paha_pcs']} (delta from after_create: {stock_after_edit['paha_pcs'] - stock_after_create['paha_pcs']})")
    
    # CRITICAL VERIFICATION: Stok harus berubah sebesar SELISIH, bukan dobel/reset
    # Expected deltas from after_create:
    # - Source ekor: 5->8 = -3 more (total -8 from before)
    # - Dada pcs: 10->6 = -4 (total +6 from before)
    # - Paha pcs: 10->15 = +5 (total +15 from before)
    
    delta_source = stock_after_edit['source_ekor'] - stock_after_create['source_ekor']
    delta_dada = stock_after_edit['dada_pcs'] - stock_after_create['dada_pcs']
    delta_paha = stock_after_edit['paha_pcs'] - stock_after_create['paha_pcs']
    
    print(f"\n🔍 DELTA VERIFICATION (from after_create):")
    print(f"   Source ekor delta: {delta_source} (expected: -3)")
    print(f"   Dada pcs delta: {delta_dada} (expected: -4)")
    print(f"   Paha pcs delta: {delta_paha} (expected: +5)")
    
    success = True
    if abs(delta_source + 3) > 0.01:
        print(f"❌ Source ekor delta WRONG: expected -3, got {delta_source}")
        success = False
    else:
        print("✓ Source ekor delta correct: -3")
    
    if abs(delta_dada + 4) > 0.01:
        print(f"❌ Dada pcs delta WRONG: expected -4, got {delta_dada}")
        success = False
    else:
        print("✓ Dada pcs delta correct: -4")
    
    if abs(delta_paha - 5) > 0.01:
        print(f"❌ Paha pcs delta WRONG: expected +5, got {delta_paha}")
        success = False
    else:
        print("✓ Paha pcs delta correct: +5")
    
    # Verify response fields
    updated_prod = resp.json()
    if "updated_at" not in updated_prod or "updated_by" not in updated_prod:
        print("❌ Response missing updated_at or updated_by")
        success = False
    else:
        print(f"✓ Response has updated_at={updated_prod['updated_at']}, updated_by={updated_prod['updated_by']}")
    
    if updated_prod.get("source_name") != ayam_broiler["name"]:
        print(f"❌ source_name not updated: {updated_prod.get('source_name')}")
        success = False
    else:
        print(f"✓ source_name updated: {updated_prod['source_name']}")
    
    if "material_value" not in updated_prod:
        print("❌ material_value missing")
        success = False
    else:
        print(f"✓ material_value present: {updated_prod['material_value']}")
    
    return success


def test_a2_edit_production_remove_output():
    """
    A2. Edit produksi dengan MENGHAPUS satu bagian output.
    Verifikasi: stock_pcs bagian yang dihapus kembali ke nilai sebelum produksi.
    """
    print("\n" + "="*80)
    print("TEST A2: Edit Production - Remove One Output")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # 1. Cari produk
    ayam_kampung = find_product_by_name(token, "Ayam Kampung")
    if not ayam_kampung:
        print("❌ Ayam Kampung not found")
        return False
    
    # Use sampingan products for this test (they have pcs units)
    sampingan = get_products_by_category(token, "sampingan")
    if len(sampingan) < 2:
        print(f"❌ Need at least 2 sampingan products")
        return False
    
    ceker = next((p for p in sampingan if "ceker" in p["name"].lower()), sampingan[0])
    kepala = next((p for p in sampingan if "kepala" in p["name"].lower()), sampingan[1])
    
    print(f"✓ Source: {ayam_kampung['name']}")
    print(f"✓ Output 1: {ceker['name']}")
    print(f"✓ Output 2: {kepala['name']}")
    
    # 2. Catat stok sebelum
    stock_before = {
        "ceker_pcs": round_float(ceker.get("stock_pcs")),
        "kepala_pcs": round_float(kepala.get("stock_pcs"))
    }
    print(f"\n📊 STOCK BEFORE:")
    print(f"   Ceker pcs: {stock_before['ceker_pcs']}")
    print(f"   Kepala pcs: {stock_before['kepala_pcs']}")
    
    # 3. Buat produksi: 3 ekor -> Ceker 6 pcs, Kepala 6 pcs
    prod_body = {
        "source_product_id": ayam_kampung["id"],
        "input_ekor": 3,
        "outputs": [
            {"product_id": ceker["id"], "pcs": 6},
            {"product_id": kepala["id"], "pcs": 6}
        ],
        "operator": "Test"
    }
    
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token), json=prod_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create production: {resp.status_code}")
        return False
    
    prod_id = resp.json()["id"]
    print(f"\n✓ Production created: id={prod_id}")
    
    # 4. Catat stok setelah create
    ceker = get_product(token, ceker["id"])
    kepala = get_product(token, kepala["id"])
    
    stock_after_create = {
        "ceker_pcs": round_float(ceker.get("stock_pcs")),
        "kepala_pcs": round_float(kepala.get("stock_pcs"))
    }
    print(f"\n📊 STOCK AFTER CREATE:")
    print(f"   Ceker pcs: {stock_after_create['ceker_pcs']} (delta: +{stock_after_create['ceker_pcs'] - stock_before['ceker_pcs']})")
    print(f"   Kepala pcs: {stock_after_create['kepala_pcs']} (delta: +{stock_after_create['kepala_pcs'] - stock_before['kepala_pcs']})")
    
    # 5. EDIT: hapus Kepala (hanya kirim Ceker)
    edit_body = {
        "source_product_id": ayam_kampung["id"],
        "input_ekor": 3,
        "outputs": [
            {"product_id": ceker["id"], "pcs": 6}
        ],
        "operator": "Test"
    }
    
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}", headers=get_headers(token), json=edit_body)
    if resp.status_code != 200:
        print(f"❌ Failed to edit production: {resp.status_code} {resp.text}")
        return False
    
    print(f"\n✓ Production edited: removed Kepala output")
    
    # 6. Catat stok setelah edit
    ceker = get_product(token, ceker["id"])
    kepala = get_product(token, kepala["id"])
    
    stock_after_edit = {
        "ceker_pcs": round_float(ceker.get("stock_pcs")),
        "kepala_pcs": round_float(kepala.get("stock_pcs"))
    }
    print(f"\n📊 STOCK AFTER EDIT:")
    print(f"   Ceker pcs: {stock_after_edit['ceker_pcs']} (delta from after_create: {stock_after_edit['ceker_pcs'] - stock_after_create['ceker_pcs']})")
    print(f"   Kepala pcs: {stock_after_edit['kepala_pcs']} (delta from after_create: {stock_after_edit['kepala_pcs'] - stock_after_create['kepala_pcs']})")
    
    # CRITICAL: Kepala harus kembali ke nilai SEBELUM produksi (delta -6 dari after_create)
    delta_kepala = stock_after_edit['kepala_pcs'] - stock_after_create['kepala_pcs']
    
    print(f"\n🔍 VERIFICATION:")
    print(f"   Kepala delta from after_create: {delta_kepala} (expected: -6)")
    print(f"   Kepala back to before: {stock_after_edit['kepala_pcs']} vs {stock_before['kepala_pcs']}")
    
    success = True
    if abs(delta_kepala + 6) > 0.01:
        print(f"❌ Kepala delta WRONG: expected -6, got {delta_kepala}")
        success = False
    else:
        print("✓ Kepala delta correct: -6")
    
    if abs(stock_after_edit['kepala_pcs'] - stock_before['kepala_pcs']) > 0.01:
        print(f"❌ Kepala NOT back to before: {stock_after_edit['kepala_pcs']} vs {stock_before['kepala_pcs']}")
        success = False
    else:
        print("✓ Kepala back to before value")
    
    # Ceker should remain unchanged
    if abs(stock_after_edit['ceker_pcs'] - stock_after_create['ceker_pcs']) > 0.01:
        print(f"❌ Ceker changed unexpectedly: {stock_after_edit['ceker_pcs']} vs {stock_after_create['ceker_pcs']}")
        success = False
    else:
        print("✓ Ceker unchanged (correct)")
    
    return success


def test_a3_edit_production_change_source():
    """
    A3. Edit produksi dengan MENGGANTI produk sumber.
    Verifikasi: stok ekor sumber lama kembali penuh, sumber baru berkurang penuh.
    """
    print("\n" + "="*80)
    print("TEST A3: Edit Production - Change Source Product")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # 1. Cari 2 produk sumber berbeda
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    ayam_pejantan = find_product_by_name(token, "Ayam Pejantan")
    
    if not ayam_broiler or not ayam_pejantan:
        print("❌ Need both Ayam Broiler and Ayam Pejantan")
        return False
    
    potongan = get_products_by_category(token, "potongan")
    if not potongan:
        print("❌ No potongan products")
        return False
    
    dada = next((p for p in potongan if "dada" in p["name"].lower()), potongan[0])
    
    print(f"✓ Source 1: {ayam_broiler['name']}")
    print(f"✓ Source 2: {ayam_pejantan['name']}")
    print(f"✓ Output: {dada['name']}")
    
    # 2. Catat stok sebelum
    stock_before = {
        "broiler_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "pejantan_ekor": round_float(ayam_pejantan.get("stock_ekor"))
    }
    print(f"\n📊 STOCK BEFORE:")
    print(f"   Broiler ekor: {stock_before['broiler_ekor']}")
    print(f"   Pejantan ekor: {stock_before['pejantan_ekor']}")
    
    # 3. Buat produksi dengan Broiler: 4 ekor -> Dada 8 pcs
    prod_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 4,
        "outputs": [
            {"product_id": dada["id"], "pcs": 8}
        ],
        "operator": "Test"
    }
    
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token), json=prod_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create production: {resp.status_code}")
        return False
    
    prod_id = resp.json()["id"]
    print(f"\n✓ Production created with Broiler: id={prod_id}")
    
    # 4. Catat stok setelah create
    ayam_broiler = get_product(token, ayam_broiler["id"])
    ayam_pejantan = get_product(token, ayam_pejantan["id"])
    
    stock_after_create = {
        "broiler_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "pejantan_ekor": round_float(ayam_pejantan.get("stock_ekor"))
    }
    print(f"\n📊 STOCK AFTER CREATE:")
    print(f"   Broiler ekor: {stock_after_create['broiler_ekor']} (delta: {stock_after_create['broiler_ekor'] - stock_before['broiler_ekor']})")
    print(f"   Pejantan ekor: {stock_after_create['pejantan_ekor']} (delta: {stock_after_create['pejantan_ekor'] - stock_before['pejantan_ekor']})")
    
    # 5. EDIT: ganti sumber ke Pejantan dengan input 6 ekor
    edit_body = {
        "source_product_id": ayam_pejantan["id"],
        "input_ekor": 6,
        "outputs": [
            {"product_id": dada["id"], "pcs": 8}
        ],
        "operator": "Test"
    }
    
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}", headers=get_headers(token), json=edit_body)
    if resp.status_code != 200:
        print(f"❌ Failed to edit production: {resp.status_code} {resp.text}")
        return False
    
    print(f"\n✓ Production edited: source changed from Broiler to Pejantan")
    
    # 6. Catat stok setelah edit
    ayam_broiler = get_product(token, ayam_broiler["id"])
    ayam_pejantan = get_product(token, ayam_pejantan["id"])
    
    stock_after_edit = {
        "broiler_ekor": round_float(ayam_broiler.get("stock_ekor")),
        "pejantan_ekor": round_float(ayam_pejantan.get("stock_ekor"))
    }
    print(f"\n📊 STOCK AFTER EDIT:")
    print(f"   Broiler ekor: {stock_after_edit['broiler_ekor']} (delta from after_create: {stock_after_edit['broiler_ekor'] - stock_after_create['broiler_ekor']})")
    print(f"   Pejantan ekor: {stock_after_edit['pejantan_ekor']} (delta from after_create: {stock_after_edit['pejantan_ekor'] - stock_after_create['pejantan_ekor']})")
    
    # CRITICAL: Broiler harus kembali penuh (+4), Pejantan berkurang penuh (-6)
    delta_broiler = stock_after_edit['broiler_ekor'] - stock_after_create['broiler_ekor']
    delta_pejantan = stock_after_edit['pejantan_ekor'] - stock_after_create['pejantan_ekor']
    
    print(f"\n🔍 VERIFICATION:")
    print(f"   Broiler delta from after_create: {delta_broiler} (expected: +4, restore full)")
    print(f"   Pejantan delta from after_create: {delta_pejantan} (expected: -6, deduct full)")
    print(f"   Broiler back to before: {stock_after_edit['broiler_ekor']} vs {stock_before['broiler_ekor']}")
    
    success = True
    if abs(delta_broiler - 4) > 0.01:
        print(f"❌ Broiler delta WRONG: expected +4, got {delta_broiler}")
        success = False
    else:
        print("✓ Broiler delta correct: +4 (restored)")
    
    if abs(delta_pejantan + 6) > 0.01:
        print(f"❌ Pejantan delta WRONG: expected -6, got {delta_pejantan}")
        success = False
    else:
        print("✓ Pejantan delta correct: -6 (deducted)")
    
    if abs(stock_after_edit['broiler_ekor'] - stock_before['broiler_ekor']) > 0.01:
        print(f"❌ Broiler NOT back to before: {stock_after_edit['broiler_ekor']} vs {stock_before['broiler_ekor']}")
        success = False
    else:
        print("✓ Broiler back to before value")
    
    return success


def test_a4_edit_production_error_cases():
    """
    A4. Test error cases untuk PUT /api/productions/{id}
    """
    print("\n" + "="*80)
    print("TEST A4: Edit Production - Error Cases")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    success = True
    
    # 1. PUT id ngawur -> 404
    resp = requests.put(f"{BASE_URL}/productions/ngawur-id-123", 
                       headers=get_headers(token),
                       json={"source_product_id": "x", "input_ekor": 1, "outputs": []})
    if resp.status_code != 404:
        print(f"❌ Invalid ID should return 404, got {resp.status_code}")
        success = False
    else:
        print("✓ Invalid ID returns 404")
    
    # 2. Buat produksi valid untuk test error cases
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    potongan = get_products_by_category(token, "potongan")
    if not potongan:
        print("❌ No potongan products for error test")
        return False
    dada = next((p for p in potongan if "dada" in p["name"].lower()), potongan[0])
    
    prod_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 2,
        "outputs": [{"product_id": dada["id"], "pcs": 4}],
        "operator": "Test"
    }
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token), json=prod_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create test production: {resp.status_code}")
        return False
    prod_id = resp.json()["id"]
    print(f"✓ Test production created: {prod_id}")
    
    # 3. input_ekor 0 -> 400
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}",
                       headers=get_headers(token),
                       json={"source_product_id": ayam_broiler["id"], "input_ekor": 0, 
                             "outputs": [{"product_id": dada["id"], "pcs": 4}]})
    if resp.status_code != 400:
        print(f"❌ input_ekor=0 should return 400, got {resp.status_code}")
        success = False
    else:
        print("✓ input_ekor=0 returns 400")
    
    # 4. outputs semua pcs 0 -> 400
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}",
                       headers=get_headers(token),
                       json={"source_product_id": ayam_broiler["id"], "input_ekor": 2,
                             "outputs": [{"product_id": dada["id"], "pcs": 0}]})
    if resp.status_code != 400:
        print(f"❌ outputs all pcs=0 should return 400, got {resp.status_code}")
        success = False
    else:
        print("✓ outputs all pcs=0 returns 400")
    
    # 5. product_id output ngawur -> 404
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}",
                       headers=get_headers(token),
                       json={"source_product_id": ayam_broiler["id"], "input_ekor": 2,
                             "outputs": [{"product_id": "ngawur-product-id", "pcs": 4}]})
    if resp.status_code != 404:
        print(f"❌ Invalid output product_id should return 404, got {resp.status_code}")
        success = False
    else:
        print("✓ Invalid output product_id returns 404")
    
    # 6. Tanpa token -> 401/403
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}",
                       json={"source_product_id": ayam_broiler["id"], "input_ekor": 2,
                             "outputs": [{"product_id": dada["id"], "pcs": 4}]})
    if resp.status_code not in [401, 403]:
        print(f"❌ No token should return 401/403, got {resp.status_code}")
        success = False
    else:
        print(f"✓ No token returns {resp.status_code}")
    
    return success


def test_a5_edit_production_rbac():
    """
    A5. Test RBAC: owner, admin, kasir semua boleh PUT
    """
    print("\n" + "="*80)
    print("TEST A5: Edit Production - RBAC (owner/admin/kasir)")
    print("="*80)
    
    success = True
    
    # Buat produksi sebagai owner
    token_owner = login("owner", "berkahayam1")
    ayam_broiler = find_product_by_name(token_owner, "Ayam Broiler")
    potongan = get_products_by_category(token_owner, "potongan")
    if not potongan:
        print("❌ No potongan products for RBAC test")
        return False
    dada = next((p for p in potongan if "dada" in p["name"].lower()), potongan[0])
    
    prod_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 2,
        "outputs": [{"product_id": dada["id"], "pcs": 4}],
        "operator": "Test"
    }
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token_owner), json=prod_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create production: {resp.status_code}")
        return False
    prod_id = resp.json()["id"]
    print(f"✓ Production created by owner: {prod_id}")
    
    # Test edit dengan berbagai role
    roles = [
        ("owner", "berkahayam1"),
        ("admin", "admin123"),
        ("kasir", "kasir123")
    ]
    
    for username, password in roles:
        token = login(username, password)
        edit_body = {
            "source_product_id": ayam_broiler["id"],
            "input_ekor": 2,
            "outputs": [{"product_id": dada["id"], "pcs": 5}],  # Change pcs slightly
            "operator": f"Test {username}"
        }
        resp = requests.put(f"{BASE_URL}/productions/{prod_id}", 
                           headers=get_headers(token), 
                           json=edit_body)
        if resp.status_code != 200:
            print(f"❌ {username} should be able to PUT, got {resp.status_code}")
            success = False
        else:
            print(f"✓ {username} can PUT (200)")
    
    return success


def test_a6_edit_production_movements_and_audit():
    """
    A6. Verifikasi stock movements dan audit logs untuk edit produksi
    """
    print("\n" + "="*80)
    print("TEST A6: Edit Production - Stock Movements & Audit Logs")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # Buat dan edit produksi
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    potongan = get_products_by_category(token, "potongan")
    if not potongan:
        print("❌ No potongan products for movements test")
        return False
    dada = next((p for p in potongan if "dada" in p["name"].lower()), potongan[0])
    
    prod_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 3,
        "outputs": [{"product_id": dada["id"], "pcs": 6}],
        "operator": "Test"
    }
    resp = requests.post(f"{BASE_URL}/productions", headers=get_headers(token), json=prod_body)
    prod_id = resp.json()["id"]
    print(f"✓ Production created: {prod_id}")
    
    # Edit
    edit_body = {
        "source_product_id": ayam_broiler["id"],
        "input_ekor": 5,
        "outputs": [{"product_id": dada["id"], "pcs": 10}],
        "operator": "Test"
    }
    resp = requests.put(f"{BASE_URL}/productions/{prod_id}", headers=get_headers(token), json=edit_body)
    if resp.status_code != 200:
        print(f"❌ Failed to edit: {resp.status_code}")
        return False
    print(f"✓ Production edited")
    
    success = True
    
    # Check stock movements
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ Failed to get stock movements: {resp.status_code}")
        return False
    
    movements = resp.json()
    prod_movements = [m for m in movements if m.get("ref") == prod_id and m.get("type") == "produksi"]
    
    if not prod_movements:
        print("❌ No stock movements found for production")
        success = False
    else:
        print(f"✓ Found {len(prod_movements)} stock movements with type='produksi' and ref={prod_id}")
        # Should have movements for both create and edit
        if len(prod_movements) < 2:
            print(f"⚠️  Expected at least 2 movements (create + edit), found {len(prod_movements)}")
    
    # Check audit logs
    resp = requests.get(f"{BASE_URL}/audit-logs", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ Failed to get audit logs: {resp.status_code}")
        return False
    
    logs = resp.json()
    update_logs = [l for l in logs if l.get("action") == "update" and l.get("entity") == "production" and l.get("entity_id") == prod_id]
    
    if not update_logs:
        print("❌ No audit log found for production update")
        success = False
    else:
        print(f"✓ Found audit log: action='update', entity='production', entity_id={prod_id}")
        log = update_logs[0]
        if "before" in log and "after" in log:
            print(f"✓ Audit log has before/after data")
        else:
            print("❌ Audit log missing before/after data")
            success = False
    
    return success


def test_b1_stock_adjustment_delta_pcs_positive():
    """
    B1. POST /api/stock-adjustments dengan delta_pcs positif
    """
    print("\n" + "="*80)
    print("TEST B1: Stock Adjustment - delta_pcs Positive")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # Cari produk dengan satuan pcs
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    products = resp.json()
    pcs_products = [p for p in products if "pcs" in (p.get("units") or [])]
    
    if not pcs_products:
        print("❌ No products with 'pcs' unit found")
        return False
    
    product = pcs_products[0]
    print(f"✓ Testing with product: {product['name']} (id={product['id']})")
    
    # Catat stok sebelum
    stock_before = round_float(product.get("stock_pcs"))
    print(f"\n📊 STOCK BEFORE: {stock_before} pcs")
    
    # Kirim adjustment delta_pcs +7
    adj_body = {
        "product_id": product["id"],
        "delta_pcs": 7,
        "reason": "Test adjustment +7 pcs",
        "type": "penyesuaian"
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create adjustment: {resp.status_code} {resp.text}")
        return False
    
    print("✓ Adjustment created")
    
    # Catat stok setelah
    product = get_product(token, product["id"])
    stock_after = round_float(product.get("stock_pcs"))
    print(f"\n📊 STOCK AFTER: {stock_after} pcs")
    
    delta = stock_after - stock_before
    print(f"🔍 Delta: {delta} (expected: +7)")
    
    success = True
    if abs(delta - 7) > 0.01:
        print(f"❌ Delta WRONG: expected +7, got {delta}")
        success = False
    else:
        print("✓ Delta correct: +7")
    
    # Check stock movement
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=get_headers(token))
    movements = resp.json()
    recent = [m for m in movements if m.get("product_id") == product["id"] and m.get("type") == "penyesuaian"]
    
    if not recent:
        print("❌ No stock movement found")
        success = False
    else:
        movement = recent[0]
        qty_pcs = round_float(movement.get("qty_pcs"))
        after_pcs = round_float(movement.get("after_pcs"))
        
        print(f"✓ Stock movement found: qty_pcs={qty_pcs}, after_pcs={after_pcs}")
        
        if abs(qty_pcs - 7) > 0.01:
            print(f"❌ Movement qty_pcs WRONG: expected +7, got {qty_pcs}")
            success = False
        else:
            print("✓ Movement qty_pcs correct: +7")
        
        if abs(after_pcs - stock_after) > 0.01:
            print(f"❌ Movement after_pcs WRONG: expected {stock_after}, got {after_pcs}")
            success = False
        else:
            print(f"✓ Movement after_pcs correct: {after_pcs}")
    
    return success


def test_b2_stock_adjustment_delta_pcs_negative():
    """
    B2. POST /api/stock-adjustments dengan delta_pcs negatif
    """
    print("\n" + "="*80)
    print("TEST B2: Stock Adjustment - delta_pcs Negative")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # Cari produk dengan satuan pcs
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    products = resp.json()
    pcs_products = [p for p in products if "pcs" in (p.get("units") or [])]
    
    if not pcs_products:
        print("❌ No products with 'pcs' unit found")
        return False
    
    product = pcs_products[0]
    print(f"✓ Testing with product: {product['name']}")
    
    # Catat stok sebelum
    stock_before = round_float(product.get("stock_pcs"))
    print(f"\n📊 STOCK BEFORE: {stock_before} pcs")
    
    # Kirim adjustment delta_pcs -3
    adj_body = {
        "product_id": product["id"],
        "delta_pcs": -3,
        "reason": "Test adjustment -3 pcs",
        "type": "penyesuaian"
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create adjustment: {resp.status_code} {resp.text}")
        return False
    
    print("✓ Adjustment created")
    
    # Catat stok setelah
    product = get_product(token, product["id"])
    stock_after = round_float(product.get("stock_pcs"))
    print(f"\n📊 STOCK AFTER: {stock_after} pcs")
    
    delta = stock_after - stock_before
    print(f"🔍 Delta: {delta} (expected: -3)")
    
    if abs(delta + 3) > 0.01:
        print(f"❌ Delta WRONG: expected -3, got {delta}")
        return False
    else:
        print("✓ Delta correct: -3")
        return True


def test_b3_stock_adjustment_combined_deltas():
    """
    B3. POST /api/stock-adjustments dengan kombinasi delta_kg + delta_ekor + delta_pcs
    """
    print("\n" + "="*80)
    print("TEST B3: Stock Adjustment - Combined Deltas (kg + ekor + pcs)")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # Cari produk yang punya ketiga satuan (jika ada)
    # Biasanya tidak ada, jadi kita test dengan produk yang punya pcs saja
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    products = resp.json()
    pcs_products = [p for p in products if "pcs" in (p.get("units") or [])]
    
    if not pcs_products:
        print("❌ No products with 'pcs' unit found")
        return False
    
    product = pcs_products[0]
    print(f"✓ Testing with product: {product['name']}")
    print(f"  Units: {product.get('units')}")
    
    # Catat stok sebelum
    stock_before = {
        "kg": round_float(product.get("stock_kg")),
        "ekor": round_float(product.get("stock_ekor")),
        "pcs": round_float(product.get("stock_pcs"))
    }
    print(f"\n📊 STOCK BEFORE:")
    print(f"   kg: {stock_before['kg']}")
    print(f"   ekor: {stock_before['ekor']}")
    print(f"   pcs: {stock_before['pcs']}")
    
    # Kirim adjustment dengan kombinasi
    adj_body = {
        "product_id": product["id"],
        "delta_kg": 2.5,
        "delta_ekor": 1,
        "delta_pcs": 5,
        "reason": "Test combined adjustment",
        "type": "penyesuaian"
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create adjustment: {resp.status_code} {resp.text}")
        return False
    
    print("✓ Adjustment created")
    
    # Catat stok setelah
    product = get_product(token, product["id"])
    stock_after = {
        "kg": round_float(product.get("stock_kg")),
        "ekor": round_float(product.get("stock_ekor")),
        "pcs": round_float(product.get("stock_pcs"))
    }
    print(f"\n📊 STOCK AFTER:")
    print(f"   kg: {stock_after['kg']} (delta: {stock_after['kg'] - stock_before['kg']})")
    print(f"   ekor: {stock_after['ekor']} (delta: {stock_after['ekor'] - stock_before['ekor']})")
    print(f"   pcs: {stock_after['pcs']} (delta: {stock_after['pcs'] - stock_before['pcs']})")
    
    success = True
    
    # Verify pcs (always should work)
    if abs(stock_after['pcs'] - stock_before['pcs'] - 5) > 0.01:
        print(f"❌ Pcs delta WRONG: expected +5, got {stock_after['pcs'] - stock_before['pcs']}")
        success = False
    else:
        print("✓ Pcs delta correct: +5")
    
    # Verify kg and ekor if product supports them
    if "kg" in (product.get("units") or []):
        if abs(stock_after['kg'] - stock_before['kg'] - 2.5) > 0.01:
            print(f"❌ Kg delta WRONG: expected +2.5, got {stock_after['kg'] - stock_before['kg']}")
            success = False
        else:
            print("✓ Kg delta correct: +2.5")
    
    if "ekor" in (product.get("units") or []):
        if abs(stock_after['ekor'] - stock_before['ekor'] - 1) > 0.01:
            print(f"❌ Ekor delta WRONG: expected +1, got {stock_after['ekor'] - stock_before['ekor']}")
            success = False
        else:
            print("✓ Ekor delta correct: +1")
    
    return success


def test_b4_stock_adjustment_error_cases():
    """
    B4. Test error cases untuk POST /api/stock-adjustments
    """
    print("\n" + "="*80)
    print("TEST B4: Stock Adjustment - Error Cases")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    success = True
    
    # 1. delta_pcs != 0 pada produk TANPA satuan pcs -> 400
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    if ayam_broiler and "pcs" not in (ayam_broiler.get("units") or []):
        adj_body = {
            "product_id": ayam_broiler["id"],
            "delta_pcs": 5,
            "reason": "Test invalid pcs",
            "type": "penyesuaian"
        }
        resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
        if resp.status_code != 400:
            print(f"❌ delta_pcs on non-pcs product should return 400, got {resp.status_code}")
            success = False
        else:
            print("✓ delta_pcs on non-pcs product returns 400")
            if "tidak memakai satuan pcs" in resp.text:
                print("✓ Error message correct")
    else:
        print("⚠️  Skipped: Ayam Broiler not found or has pcs unit")
    
    # 2. Semua delta 0 -> 400
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    products = resp.json()
    if products:
        adj_body = {
            "product_id": products[0]["id"],
            "delta_kg": 0,
            "delta_ekor": 0,
            "delta_pcs": 0,
            "reason": "Test all zero",
            "type": "penyesuaian"
        }
        resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
        if resp.status_code != 400:
            print(f"❌ All deltas=0 should return 400, got {resp.status_code}")
            success = False
        else:
            print("✓ All deltas=0 returns 400")
    
    # 3. Jenis penyesuaian ngawur -> 400
    if products:
        adj_body = {
            "product_id": products[0]["id"],
            "delta_kg": 1,
            "reason": "Test invalid type",
            "type": "ngawur_type"
        }
        resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
        if resp.status_code != 400:
            print(f"❌ Invalid type should return 400, got {resp.status_code}")
            success = False
        else:
            print("✓ Invalid type returns 400")
    
    # 4. Tanpa token -> 401/403
    if products:
        adj_body = {
            "product_id": products[0]["id"],
            "delta_kg": 1,
            "reason": "Test no auth",
            "type": "penyesuaian"
        }
        resp = requests.post(f"{BASE_URL}/stock-adjustments", json=adj_body)
        if resp.status_code not in [401, 403]:
            print(f"❌ No token should return 401/403, got {resp.status_code}")
            success = False
        else:
            print(f"✓ No token returns {resp.status_code}")
    
    return success


def test_b5_stock_adjustment_backward_compatibility():
    """
    B5. Regresi: penyesuaian kg/ekor lama (tanpa field delta_pcs) harus tetap jalan
    """
    print("\n" + "="*80)
    print("TEST B5: Stock Adjustment - Backward Compatibility (no delta_pcs field)")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    # Cari produk dengan satuan kg atau ekor
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    if not ayam_broiler:
        print("❌ Ayam Broiler not found")
        return False
    
    print(f"✓ Testing with: {ayam_broiler['name']}")
    
    # Catat stok sebelum
    stock_before = {
        "kg": round_float(ayam_broiler.get("stock_kg")),
        "ekor": round_float(ayam_broiler.get("stock_ekor"))
    }
    print(f"\n📊 STOCK BEFORE:")
    print(f"   kg: {stock_before['kg']}")
    print(f"   ekor: {stock_before['ekor']}")
    
    # Kirim adjustment TANPA field delta_pcs (backward compatibility)
    adj_body = {
        "product_id": ayam_broiler["id"],
        "delta_kg": 1.5,
        "delta_ekor": 1,
        "reason": "Test backward compatibility",
        "type": "penyesuaian"
        # NO delta_pcs field
    }
    
    resp = requests.post(f"{BASE_URL}/stock-adjustments", headers=get_headers(token), json=adj_body)
    if resp.status_code != 200:
        print(f"❌ Failed to create adjustment without delta_pcs: {resp.status_code} {resp.text}")
        return False
    
    print("✓ Adjustment created (without delta_pcs field)")
    
    # Catat stok setelah
    ayam_broiler = get_product(token, ayam_broiler["id"])
    stock_after = {
        "kg": round_float(ayam_broiler.get("stock_kg")),
        "ekor": round_float(ayam_broiler.get("stock_ekor"))
    }
    print(f"\n📊 STOCK AFTER:")
    print(f"   kg: {stock_after['kg']} (delta: {stock_after['kg'] - stock_before['kg']})")
    print(f"   ekor: {stock_after['ekor']} (delta: {stock_after['ekor'] - stock_before['ekor']})")
    
    success = True
    if abs(stock_after['kg'] - stock_before['kg'] - 1.5) > 0.01:
        print(f"❌ Kg delta WRONG: expected +1.5, got {stock_after['kg'] - stock_before['kg']}")
        success = False
    else:
        print("✓ Kg delta correct: +1.5")
    
    if abs(stock_after['ekor'] - stock_before['ekor'] - 1) > 0.01:
        print(f"❌ Ekor delta WRONG: expected +1, got {stock_after['ekor'] - stock_before['ekor']}")
        success = False
    else:
        print("✓ Ekor delta correct: +1")
    
    return success


def test_c_regression():
    """
    C. Regresi singkat: endpoint lain masih normal
    """
    print("\n" + "="*80)
    print("TEST C: Regression - Other Endpoints")
    print("="*80)
    
    token = login("owner", "berkahayam1")
    
    success = True
    
    # 1. GET /api/products
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ GET /api/products failed: {resp.status_code}")
        success = False
    else:
        products = resp.json()
        print(f"✓ GET /api/products: 200 ({len(products)} products)")
    
    # 2. GET /api/productions
    resp = requests.get(f"{BASE_URL}/productions", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ GET /api/productions failed: {resp.status_code}")
        success = False
    else:
        productions = resp.json()
        print(f"✓ GET /api/productions: 200 ({len(productions)} productions)")
    
    # 3. GET /api/stock-movements
    resp = requests.get(f"{BASE_URL}/stock-movements", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ GET /api/stock-movements failed: {resp.status_code}")
        success = False
    else:
        movements = resp.json()
        print(f"✓ GET /api/stock-movements: 200 ({len(movements)} movements)")
    
    # 4. POST penjualan
    ayam_broiler = find_product_by_name(token, "Ayam Broiler")
    if ayam_broiler:
        stock_before = round_float(ayam_broiler.get("stock_ekor"))
        
        sale_body = {
            "items": [
                {"product_id": ayam_broiler["id"], "unit": "ekor", "qty": 1, "price": 55000}
            ],
            "customer_name": "Test Customer",
            "payment_method": "cash",
            "paid": 55000
        }
        resp = requests.post(f"{BASE_URL}/sales", headers=get_headers(token), json=sale_body)
        if resp.status_code != 200:
            print(f"❌ POST /api/sales failed: {resp.status_code}")
            success = False
        else:
            sale = resp.json()
            sale_id = sale["id"]
            print(f"✓ POST /api/sales: 200 (id={sale_id})")
            
            # Verify stock decreased
            ayam_broiler = get_product(token, ayam_broiler["id"])
            stock_after = round_float(ayam_broiler.get("stock_ekor"))
            if abs(stock_after - stock_before + 1) > 0.01:
                print(f"❌ Stock not decreased correctly: {stock_before} -> {stock_after}")
                success = False
            else:
                print(f"✓ Stock decreased: {stock_before} -> {stock_after}")
            
            # 5. Cancel penjualan
            resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=get_headers(token))
            if resp.status_code != 200:
                print(f"❌ POST /api/sales/{sale_id}/cancel failed: {resp.status_code}")
                success = False
            else:
                print(f"✓ POST /api/sales/{sale_id}/cancel: 200")
                
                # Verify stock restored
                ayam_broiler = get_product(token, ayam_broiler["id"])
                stock_restored = round_float(ayam_broiler.get("stock_ekor"))
                if abs(stock_restored - stock_before) > 0.01:
                    print(f"❌ Stock not restored: {stock_before} -> {stock_restored}")
                    success = False
                else:
                    print(f"✓ Stock restored: {stock_restored}")
    
    # 6. Check backend logs
    print("\n📋 Checking backend logs...")
    result = requests.get("http://localhost:8001/health")  # Just to trigger any startup errors
    # We'll check logs via bash in the main function
    
    return success


# ============ Main Test Runner ============

def main():
    print("="*80)
    print("BACKEND TEST: Edit Produksi Potong + Penyesuaian Stok Pcs")
    print("Iterasi 2026-09-03")
    print("="*80)
    
    results = {}
    
    # Test A: PUT /api/productions/{id}
    print("\n" + "🔵"*40)
    print("SECTION A: PUT /api/productions/{id}")
    print("🔵"*40)
    
    try:
        results["A1"] = test_a1_create_and_edit_production_increase_input()
    except Exception as e:
        print(f"❌ A1 EXCEPTION: {e}")
        results["A1"] = False
    
    try:
        results["A2"] = test_a2_edit_production_remove_output()
    except Exception as e:
        print(f"❌ A2 EXCEPTION: {e}")
        results["A2"] = False
    
    try:
        results["A3"] = test_a3_edit_production_change_source()
    except Exception as e:
        print(f"❌ A3 EXCEPTION: {e}")
        results["A3"] = False
    
    try:
        results["A4"] = test_a4_edit_production_error_cases()
    except Exception as e:
        print(f"❌ A4 EXCEPTION: {e}")
        results["A4"] = False
    
    try:
        results["A5"] = test_a5_edit_production_rbac()
    except Exception as e:
        print(f"❌ A5 EXCEPTION: {e}")
        results["A5"] = False
    
    try:
        results["A6"] = test_a6_edit_production_movements_and_audit()
    except Exception as e:
        print(f"❌ A6 EXCEPTION: {e}")
        results["A6"] = False
    
    # Test B: POST /api/stock-adjustments dengan delta_pcs
    print("\n" + "🟢"*40)
    print("SECTION B: POST /api/stock-adjustments (delta_pcs)")
    print("🟢"*40)
    
    try:
        results["B1"] = test_b1_stock_adjustment_delta_pcs_positive()
    except Exception as e:
        print(f"❌ B1 EXCEPTION: {e}")
        results["B1"] = False
    
    try:
        results["B2"] = test_b2_stock_adjustment_delta_pcs_negative()
    except Exception as e:
        print(f"❌ B2 EXCEPTION: {e}")
        results["B2"] = False
    
    try:
        results["B3"] = test_b3_stock_adjustment_combined_deltas()
    except Exception as e:
        print(f"❌ B3 EXCEPTION: {e}")
        results["B3"] = False
    
    try:
        results["B4"] = test_b4_stock_adjustment_error_cases()
    except Exception as e:
        print(f"❌ B4 EXCEPTION: {e}")
        results["B4"] = False
    
    try:
        results["B5"] = test_b5_stock_adjustment_backward_compatibility()
    except Exception as e:
        print(f"❌ B5 EXCEPTION: {e}")
        results["B5"] = False
    
    # Test C: Regression
    print("\n" + "🟡"*40)
    print("SECTION C: Regression Tests")
    print("🟡"*40)
    
    try:
        results["C"] = test_c_regression()
    except Exception as e:
        print(f"❌ C EXCEPTION: {e}")
        results["C"] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
