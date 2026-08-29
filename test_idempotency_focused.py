#!/usr/bin/env python3
"""
Focused test for idempotency issue
"""
import requests
import json
import uuid

BASE_URL = "https://commit-checker-live-2.preview.emergentagent.com/api"
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"

# Login
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "email": OWNER_EMAIL,
    "password": OWNER_PASSWORD
})
token = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# Get products
resp = requests.get(f"{BASE_URL}/products", headers=headers)
products = resp.json()

# Find product with good stock
product = None
for p in products:
    if "kg" in p.get("units", []) and p.get("stock_kg", 0) > 10:
        product = p
        break

if not product:
    print("❌ No product with sufficient stock found")
    exit(1)

product_id = product["id"]
product_name = product["name"]
price_kg = product.get("price_kg", 0)

print(f"Testing with product: {product_name}")
print(f"Stock before: {product['stock_kg']} kg")

# Create sale with unique txn_id
txn_id = f"test-idem-focused-{uuid.uuid4().hex[:8]}"
sale_payload = {
    "txn_id": txn_id,
    "items": [
        {
            "product_id": product_id,
            "unit": "kg",
            "qty": 0.5,
            "price": price_kg
        }
    ],
    "discount": 0,
    "paid": 0,
    "payment_method": "cash"
}

# First POST
print("\n1st POST...")
resp1 = requests.post(f"{BASE_URL}/sales", headers=headers, json=sale_payload)
if resp1.status_code != 200:
    print(f"❌ First POST failed: {resp1.status_code} - {resp1.text}")
    exit(1)

sale1 = resp1.json()
print(f"✅ First POST success: sale_id = {sale1['id']}")

# Get stock after first POST
resp = requests.get(f"{BASE_URL}/products", headers=headers)
products = resp.json()
product_after_1 = next((p for p in products if p["id"] == product_id), None)
stock_after_1 = product_after_1["stock_kg"]
print(f"Stock after 1st POST: {stock_after_1} kg")

# Second POST (same payload)
print("\n2nd POST (same txn_id)...")
resp2 = requests.post(f"{BASE_URL}/sales", headers=headers, json=sale_payload)
if resp2.status_code != 200:
    print(f"❌ Second POST failed: {resp2.status_code} - {resp2.text}")
    exit(1)

sale2 = resp2.json()
print(f"✅ Second POST success: sale_id = {sale2['id']}")

# Get stock after second POST
resp = requests.get(f"{BASE_URL}/products", headers=headers)
products = resp.json()
product_after_2 = next((p for p in products if p["id"] == product_id), None)
stock_after_2 = product_after_2["stock_kg"]
print(f"Stock after 2nd POST: {stock_after_2} kg")

# Verify
print("\n" + "="*60)
print("VERIFICATION:")
print("="*60)

if sale1["id"] == sale2["id"]:
    print(f"✅ Same sale ID returned: {sale1['id']}")
else:
    print(f"❌ Different sale IDs: {sale1['id']} vs {sale2['id']}")

stock_before = product["stock_kg"]
expected_stock = round(stock_before - 0.5, 3)
actual_stock = stock_after_2

print(f"\nStock before: {stock_before} kg")
print(f"Expected after (decrease once): {expected_stock} kg")
print(f"Actual after: {actual_stock} kg")

if abs(actual_stock - expected_stock) < 0.001:
    print("✅ Stock decreased only ONCE (idempotency working)")
else:
    print(f"❌ Stock decreased incorrectly (idempotency BROKEN)")
    print(f"   Stock after 1st POST: {stock_after_1} kg")
    print(f"   Stock after 2nd POST: {stock_after_2} kg")
    if abs(stock_after_1 - stock_after_2) > 0.001:
        print(f"   ⚠️  Stock changed between 1st and 2nd POST!")
