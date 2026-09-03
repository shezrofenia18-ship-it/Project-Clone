#!/usr/bin/env python3
"""
Focused HPP per ekor test - handles existing data properly
"""
import requests
import json
from datetime import datetime, timezone, timedelta

BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"
ADMIN_EMAIL = "admin@berkahayam.com"
ADMIN_PASSWORD = "admin123"
KASIR_EMAIL = "kasir@berkahayam.com"
KASIR_PASSWORD = "kasir123"

JKT_TZ = timezone(timedelta(hours=7))

def login(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    return None

def get_headers(token):
    return {"Authorization": f"Bearer {token}"}

def today_str():
    return datetime.now(JKT_TZ).strftime("%Y-%m-%d")

print("="*80)
print("HPP PER EKOR - FOCUSED TEST")
print("="*80)

# Login
owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)

if not owner_token:
    print("❌ Login failed")
    exit(1)

print("✅ Logged in")

# Get products
resp = requests.get(f"{BASE_URL}/products", headers=get_headers(owner_token))
products = resp.json()

# Find broiler or kampung product
product = None
for p in products:
    if p.get("category") in ["broiler", "kampung"] and "ekor" in p.get("units", []):
        product = p
        break

if not product:
    print("❌ No broiler/kampung product found")
    exit(1)

product_id = product["id"]
product_name = product["name"]
print(f"\n📦 Testing with: {product_name} (ID: {product_id})")

# Get supplier
resp = requests.get(f"{BASE_URL}/suppliers", headers=get_headers(owner_token))
suppliers = resp.json()
if not suppliers:
    print("❌ No suppliers found")
    exit(1)
supplier_id = suppliers[0]["id"]

# Get initial state
initial_cum_ekor = product.get("cum_ekor_in", 0)
initial_cum_weight = product.get("cum_weight_in", 0)
initial_avg = product.get("avg_weight_ekor", 0)
initial_hpp_kg = product.get("hpp_kg", 0)
initial_hpp_ekor = product.get("hpp_ekor", 0)

print(f"\n📊 Initial State:")
print(f"   cum_ekor_in: {initial_cum_ekor}")
print(f"   cum_weight_in: {initial_cum_weight}")
print(f"   avg_weight_ekor: {initial_avg}")
print(f"   hpp_kg: {initial_hpp_kg}")
print(f"   hpp_ekor: {initial_hpp_ekor}")

# TEST 1: Purchase adds to accumulators
print("\n" + "="*80)
print("TEST 1: Purchase adds to accumulators")
print("="*80)

purchase_ekor = 10
purchase_weight = 15
purchase_price = 450000

purchase_body = {
    "supplier_id": supplier_id,
    "date": today_str(),
    "items": [{
        "product_id": product_id,
        "ekor": purchase_ekor,
        "total_weight": purchase_weight,
        "total_price": purchase_price
    }],
    "transport_cost": 0,
    "other_cost": 0,
    "paid": purchase_price,
    "notes": "HPP Test 1"
}

resp = requests.post(f"{BASE_URL}/purchases", json=purchase_body, headers=get_headers(owner_token))

if resp.status_code != 200:
    print(f"❌ Purchase failed: {resp.status_code}")
    print(resp.text)
    exit(1)

purchase = resp.json()
purchase_id = purchase["id"]
print(f"✅ Purchase created: {purchase_id}")

# Get product after purchase
resp = requests.get(f"{BASE_URL}/products", headers=get_headers(owner_token))
products = resp.json()
product_after = next((p for p in products if p["id"] == product_id), None)

new_cum_ekor = product_after.get("cum_ekor_in", 0)
new_cum_weight = product_after.get("cum_weight_in", 0)
new_avg = product_after.get("avg_weight_ekor", 0)
new_hpp_kg = product_after.get("hpp_kg", 0)
new_hpp_ekor = product_after.get("hpp_ekor", 0)

print(f"\n📊 After Purchase:")
print(f"   cum_ekor_in: {initial_cum_ekor} → {new_cum_ekor} (delta: {new_cum_ekor - initial_cum_ekor})")
print(f"   cum_weight_in: {initial_cum_weight} → {new_cum_weight} (delta: {new_cum_weight - initial_cum_weight})")
print(f"   avg_weight_ekor: {initial_avg} → {new_avg}")
print(f"   hpp_kg: {initial_hpp_kg} → {new_hpp_kg}")
print(f"   hpp_ekor: {initial_hpp_ekor} → {new_hpp_ekor}")

# Validate
expected_cum_ekor = initial_cum_ekor + purchase_ekor
expected_cum_weight = initial_cum_weight + purchase_weight
expected_avg = expected_cum_weight / expected_cum_ekor if expected_cum_ekor > 0 else 0
expected_hpp_kg = purchase_price / purchase_weight  # 30000
# Note: hpp_ekor = latest hpp_kg × average weight from ALL purchases
# This is correct behavior - hpp_kg is from latest purchase, avg is from all history
expected_hpp_ekor = expected_hpp_kg * expected_avg

print(f"\n📐 Expected values:")
print(f"   expected_avg: {expected_avg}")
print(f"   expected_hpp_kg: {expected_hpp_kg}")
print(f"   expected_hpp_ekor: {expected_hpp_ekor}")
print(f"   hpp_ekor diff: {abs(new_hpp_ekor - expected_hpp_ekor)}")

checks = []
checks.append(("cum_ekor_in delta", abs((new_cum_ekor - initial_cum_ekor) - purchase_ekor) < 0.01))
checks.append(("cum_weight_in delta", abs((new_cum_weight - initial_cum_weight) - purchase_weight) < 0.01))
checks.append(("avg_weight_ekor", abs(new_avg - expected_avg) < 0.01))
checks.append(("hpp_kg", abs(new_hpp_kg - expected_hpp_kg) < 0.01))
checks.append(("hpp_ekor", abs(new_hpp_ekor - expected_hpp_ekor) < 50.0))  # Allow rounding difference

print(f"\n✓ Validation:")
all_pass = True
for check_name, passed in checks:
    if passed:
        print(f"   ✅ {check_name}")
    else:
        print(f"   ❌ {check_name}")
        all_pass = False

if all_pass:
    print("\n✅ TEST 1 PASSED: Purchase correctly updates accumulators and HPP")
else:
    print("\n❌ TEST 1 FAILED")

# TEST 2: Manual override
print("\n" + "="*80)
print("TEST 2: Manual override avg_weight")
print("="*80)

override_weight = 1.8

resp = requests.post(f"{BASE_URL}/products/{product_id}/avg-weight",
                    json={"avg_weight_override": override_weight},
                    headers=get_headers(owner_token))

if resp.status_code != 200:
    print(f"❌ Override failed: {resp.status_code}")
else:
    product_after = resp.json()
    
    override_source = product_after.get("avg_weight_source")
    override_used = product_after.get("avg_weight_used", 0)
    override_hpp_ekor = product_after.get("hpp_ekor", 0)
    
    expected_hpp_ekor = new_hpp_kg * override_weight
    
    print(f"\n📊 After Override:")
    print(f"   avg_weight_source: {override_source}")
    print(f"   avg_weight_used: {override_used}")
    print(f"   hpp_ekor: {override_hpp_ekor} (expected: {expected_hpp_ekor})")
    
    checks = []
    checks.append(("source is manual", override_source == "manual"))
    checks.append(("used equals override", abs(override_used - override_weight) < 0.01))
    checks.append(("hpp_ekor correct", abs(override_hpp_ekor - expected_hpp_ekor) < 0.01))
    
    print(f"\n✓ Validation:")
    all_pass = True
    for check_name, passed in checks:
        if passed:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name}")
            all_pass = False
    
    if all_pass:
        print("\n✅ TEST 2 PASSED: Manual override working")
    else:
        print("\n❌ TEST 2 FAILED")

# TEST 3: Reset to auto
print("\n" + "="*80)
print("TEST 3: Reset to auto")
print("="*80)

resp = requests.post(f"{BASE_URL}/products/{product_id}/avg-weight",
                    json={"avg_weight_override": 0},
                    headers=get_headers(owner_token))

if resp.status_code != 200:
    print(f"❌ Reset failed: {resp.status_code}")
else:
    product_after = resp.json()
    
    reset_source = product_after.get("avg_weight_source")
    reset_used = product_after.get("avg_weight_used", 0)
    
    print(f"\n📊 After Reset:")
    print(f"   avg_weight_source: {reset_source}")
    print(f"   avg_weight_used: {reset_used}")
    
    if reset_source == "auto" and abs(reset_used - new_avg) < 0.01:
        print("\n✅ TEST 3 PASSED: Reset to auto working")
    else:
        print("\n❌ TEST 3 FAILED")

# TEST 4: Delete purchase
print("\n" + "="*80)
print("TEST 4: Delete purchase (reverse accumulators)")
print("="*80)

# Get current state
resp = requests.get(f"{BASE_URL}/products", headers=get_headers(owner_token))
products = resp.json()
product_before_delete = next((p for p in products if p["id"] == product_id), None)

before_delete_ekor = product_before_delete.get("cum_ekor_in", 0)
before_delete_weight = product_before_delete.get("cum_weight_in", 0)

resp = requests.delete(f"{BASE_URL}/purchases/{purchase_id}", headers=get_headers(owner_token))

if resp.status_code != 200:
    print(f"❌ Delete failed: {resp.status_code}")
else:
    print(f"✅ Purchase deleted: {purchase_id}")
    
    # Get product after delete
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers(owner_token))
    products = resp.json()
    product_after_delete = next((p for p in products if p["id"] == product_id), None)
    
    after_delete_ekor = product_after_delete.get("cum_ekor_in", 0)
    after_delete_weight = product_after_delete.get("cum_weight_in", 0)
    
    print(f"\n📊 After Delete:")
    print(f"   cum_ekor_in: {before_delete_ekor} → {after_delete_ekor} (delta: {after_delete_ekor - before_delete_ekor})")
    print(f"   cum_weight_in: {before_delete_weight} → {after_delete_weight} (delta: {after_delete_weight - before_delete_weight})")
    
    ekor_decreased = abs((before_delete_ekor - after_delete_ekor) - purchase_ekor) < 0.01
    weight_decreased = abs((before_delete_weight - after_delete_weight) - purchase_weight) < 0.01
    
    if ekor_decreased and weight_decreased:
        print("\n✅ TEST 4 PASSED: Delete correctly reverses accumulators")
    else:
        print("\n❌ TEST 4 FAILED")

# TEST 5: Kasir access control
print("\n" + "="*80)
print("TEST 5: Kasir access control")
print("="*80)

resp = requests.post(f"{BASE_URL}/products/{product_id}/avg-weight",
                    json={"avg_weight_override": 2.0},
                    headers=get_headers(kasir_token))

if resp.status_code == 403:
    print("✅ TEST 5 PASSED: Kasir correctly rejected with 403")
else:
    print(f"❌ TEST 5 FAILED: Got {resp.status_code} instead of 403")

print("\n" + "="*80)
print("HPP PER EKOR TESTS COMPLETE")
print("="*80)
