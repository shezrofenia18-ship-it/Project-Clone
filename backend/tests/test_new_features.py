"""Backend tests for new features: Restore Deleted Products & Sync All Products."""
import os
import requests
from pathlib import Path

# Get backend URL
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    fe = Path("/app/frontend/.env").read_text()
    for line in fe.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

# Test credentials (USERNAME-based login)
OWNER_CREDS = {"username": "owner", "password": "admin123"}
ADMIN_CREDS = {"username": "admin", "password": "admin123"}

def login(username, password):
    """Login and return token."""
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    if r.status_code != 200:
        print(f"❌ Login failed for {username}: {r.status_code} {r.text}")
        return None
    data = r.json()
    return data.get("token")

def headers(token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {token}"}

def test_sync_kg_all():
    """Test sync-kg-all feature."""
    print("\n" + "="*80)
    print("TESTING: SYNC KG ALL FEATURE")
    print("="*80)
    
    owner_token = login(**OWNER_CREDS)
    admin_token = login(**ADMIN_CREDS)
    
    if not owner_token or not admin_token:
        print("❌ Failed to login")
        return False
    
    print("✅ Login successful (owner & admin)")
    
    # Get products to find Ayam Kampung and Ayam Pejantan
    r = requests.get(f"{API}/products", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Failed to get products: {r.status_code}")
        return False
    
    products = r.json()
    kampung = next((p for p in products if "Kampung" in p.get("name", "")), None)
    pejantan = next((p for p in products if "Pejantan" in p.get("name", "")), None)
    
    if not kampung or not pejantan:
        print(f"❌ Could not find Ayam Kampung or Ayam Pejantan")
        return False
    
    print(f"✅ Found products: {kampung['name']} (id: {kampung['id'][:8]}...), {pejantan['name']} (id: {pejantan['id'][:8]}...)")
    
    # Create stock discrepancy for both products (+25 kg delta)
    print("\n--- Creating stock discrepancies ---")
    for prod in [kampung, pejantan]:
        body = {
            "product_id": prod["id"],
            "delta_kg": 25,
            "delta_ekor": 0,
            "reason": "uji selisih untuk sync-kg-all"
        }
        r = requests.post(f"{API}/stock-adjustments", headers=headers(owner_token), json=body)
        if r.status_code != 200:
            print(f"❌ Failed to create adjustment for {prod['name']}: {r.status_code} {r.text}")
            return False
        print(f"✅ Created +25 kg adjustment for {prod['name']}")
    
    # Verify products are out_of_sync
    print("\n--- Verifying out_of_sync status ---")
    r = requests.get(f"{API}/products", headers=headers(owner_token))
    products = r.json()
    kampung = next((p for p in products if p["id"] == kampung["id"]), None)
    pejantan = next((p for p in products if p["id"] == pejantan["id"]), None)
    
    if not kampung or not pejantan:
        print("❌ Products not found after adjustment")
        return False
    
    kampung_sync = kampung.get("stock_sync", {})
    pejantan_sync = pejantan.get("stock_sync", {})
    
    if not kampung_sync.get("out_of_sync") or not pejantan_sync.get("out_of_sync"):
        print(f"❌ Products not marked as out_of_sync")
        print(f"   Kampung: {kampung_sync}")
        print(f"   Pejantan: {pejantan_sync}")
        return False
    
    print(f"✅ Both products marked as out_of_sync")
    print(f"   Kampung: diff_kg={kampung_sync.get('diff_kg')}, expected_kg={kampung_sync.get('expected_kg')}")
    print(f"   Pejantan: diff_kg={pejantan_sync.get('diff_kg')}, expected_kg={pejantan_sync.get('expected_kg')}")
    
    # Test admin cannot sync-kg-all (403)
    print("\n--- Testing admin 403 ---")
    r = requests.post(f"{API}/products/sync-kg-all", headers=headers(admin_token), json={})
    if r.status_code != 403:
        print(f"❌ Admin should get 403, got {r.status_code}")
        return False
    print("✅ Admin correctly blocked (403)")
    
    # Owner sync-kg-all
    print("\n--- Owner syncing all products ---")
    body = {"reason": "rapikan massal"}
    r = requests.post(f"{API}/products/sync-kg-all", headers=headers(owner_token), json=body)
    if r.status_code != 200:
        print(f"❌ Sync-kg-all failed: {r.status_code} {r.text}")
        return False
    
    result = r.json()
    print(f"✅ Sync-kg-all successful")
    print(f"   count: {result.get('count')}")
    print(f"   total_delta_kg: {result.get('total_delta_kg')}")
    print(f"   results: {len(result.get('results', []))} items")
    
    if result.get("count") != 2:
        print(f"❌ Expected count=2, got {result.get('count')}")
        return False
    
    # Verify products are now in sync
    print("\n--- Verifying products are now in sync ---")
    r = requests.get(f"{API}/products", headers=headers(owner_token))
    products = r.json()
    kampung = next((p for p in products if p["id"] == kampung["id"]), None)
    pejantan = next((p for p in products if p["id"] == pejantan["id"]), None)
    
    if kampung.get("stock_sync", {}).get("out_of_sync") or pejantan.get("stock_sync", {}).get("out_of_sync"):
        print(f"❌ Products still out_of_sync after sync-kg-all")
        return False
    
    print("✅ Both products now in sync")
    
    # Sync again should return count=0
    print("\n--- Testing second sync (should be count=0) ---")
    r = requests.post(f"{API}/products/sync-kg-all", headers=headers(owner_token), json={"reason": "test kedua"})
    if r.status_code != 200:
        print(f"❌ Second sync failed: {r.status_code}")
        return False
    
    result = r.json()
    if result.get("count") != 0:
        print(f"❌ Expected count=0 on second sync, got {result.get('count')}")
        return False
    
    print("✅ Second sync correctly returns count=0")
    
    # Verify stock movements
    print("\n--- Verifying stock movements ---")
    for prod_id, prod_name in [(kampung["id"], kampung["name"]), (pejantan["id"], pejantan["name"])]:
        r = requests.get(f"{API}/stock-movements?product_id={prod_id}", headers=headers(owner_token))
        if r.status_code != 200:
            print(f"❌ Failed to get stock movements: {r.status_code}")
            return False
        
        movements = r.json()
        penyesuaian = [m for m in movements if m.get("type") == "penyesuaian" and "rapikan massal" in m.get("ref", "")]
        if not penyesuaian:
            print(f"❌ No penyesuaian movement found for {prod_name} with 'rapikan massal'")
            return False
        print(f"✅ Found penyesuaian movement for {prod_name}")
    
    # Verify audit logs
    print("\n--- Verifying audit logs ---")
    r = requests.get(f"{API}/audit-logs", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Failed to get audit logs: {r.status_code}")
        return False
    
    logs = r.json()
    sync_kg_logs = [log for log in logs if log.get("action") == "sync_kg"]
    if len(sync_kg_logs) < 2:
        print(f"❌ Expected at least 2 sync_kg audit logs, found {len(sync_kg_logs)}")
        return False
    
    print(f"✅ Found {len(sync_kg_logs)} sync_kg audit log entries")
    
    print("\n" + "="*80)
    print("✅ SYNC KG ALL FEATURE: ALL TESTS PASSED")
    print("="*80)
    return True


def test_restore_deleted_products():
    """Test restore deleted products feature."""
    print("\n" + "="*80)
    print("TESTING: RESTORE DELETED PRODUCTS FEATURE")
    print("="*80)
    
    owner_token = login(**OWNER_CREDS)
    admin_token = login(**ADMIN_CREDS)
    
    if not owner_token or not admin_token:
        print("❌ Failed to login")
        return False
    
    print("✅ Login successful (owner & admin)")
    
    # Create test product
    print("\n--- Creating test product 'Uji Pulihkan' ---")
    body = {
        "name": "Uji Pulihkan",
        "category": "sampingan",
        "units": ["kg", "pcs"],
        "price_kg": 7000,
        "stock_kg": 3,
        "stock_pcs": 10
    }
    r = requests.post(f"{API}/products", headers=headers(owner_token), json=body)
    if r.status_code != 200:
        print(f"❌ Failed to create product: {r.status_code} {r.text}")
        return False
    
    product = r.json()
    product_id = product["id"]
    print(f"✅ Created product 'Uji Pulihkan' (id: {product_id[:8]}...)")
    
    # Delete permanently
    print("\n--- Deleting product permanently ---")
    r = requests.delete(f"{API}/products/{product_id}?permanent=true", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Failed to delete product: {r.status_code} {r.text}")
        return False
    print("✅ Product deleted permanently")
    
    # Verify product is gone
    r = requests.get(f"{API}/products", headers=headers(owner_token))
    products = r.json()
    if any(p["id"] == product_id for p in products):
        print("❌ Product still exists after permanent delete")
        return False
    print("✅ Product no longer in products list")
    
    # Get deleted products list
    print("\n--- Getting deleted products list ---")
    r = requests.get(f"{API}/audit-logs/deleted-products", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Failed to get deleted products: {r.status_code} {r.text}")
        return False
    
    deleted = r.json()
    test_product = next((d for d in deleted if d.get("name") == "Uji Pulihkan"), None)
    if not test_product:
        print("❌ 'Uji Pulihkan' not found in deleted products list")
        return False
    
    audit_id = test_product["id"]
    print(f"✅ Found 'Uji Pulihkan' in deleted products (audit_id: {audit_id[:8]}...)")
    print(f"   can_restore: {test_product.get('can_restore')}")
    print(f"   restored_at: {test_product.get('restored_at')}")
    print(f"   stock_kg: {test_product.get('stock_kg')}")
    print(f"   stock_pcs: {test_product.get('stock_pcs')}")
    
    if not test_product.get("can_restore"):
        print("❌ Product should be restorable (can_restore=true)")
        return False
    
    if test_product.get("restored_at"):
        print("❌ Product should not have restored_at yet")
        return False
    
    # Test admin cannot restore (403)
    print("\n--- Testing admin 403 ---")
    r = requests.post(f"{API}/audit-logs/deleted-products/{audit_id}/restore", headers=headers(admin_token))
    if r.status_code != 403:
        print(f"❌ Admin should get 403, got {r.status_code}")
        return False
    print("✅ Admin correctly blocked (403)")
    
    # Owner restore
    print("\n--- Owner restoring product ---")
    r = requests.post(f"{API}/audit-logs/deleted-products/{audit_id}/restore", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Restore failed: {r.status_code} {r.text}")
        return False
    
    restored = r.json()
    print(f"✅ Product restored successfully")
    print(f"   id: {restored.get('id')}")
    print(f"   name: {restored.get('name')}")
    print(f"   active: {restored.get('active')}")
    print(f"   stock_kg: {restored.get('stock_kg')}")
    print(f"   stock_pcs: {restored.get('stock_pcs')}")
    
    # Verify restored product has same ID
    if restored.get("id") != product_id:
        print(f"❌ Restored product ID mismatch: expected {product_id}, got {restored.get('id')}")
        return False
    
    if not restored.get("active"):
        print("❌ Restored product should be active")
        return False
    
    if restored.get("stock_kg") != 3 or restored.get("stock_pcs") != 10:
        print(f"❌ Stock not restored correctly: kg={restored.get('stock_kg')}, pcs={restored.get('stock_pcs')}")
        return False
    
    print("✅ Product restored with same ID, active=true, stock restored")
    
    # Verify product is back in products list
    print("\n--- Verifying product is back in list ---")
    r = requests.get(f"{API}/products", headers=headers(owner_token))
    products = r.json()
    if not any(p["id"] == product_id for p in products):
        print("❌ Restored product not found in products list")
        return False
    print("✅ Product is back in products list")
    
    # Check deleted products list - should have restored_at
    print("\n--- Checking deleted products list after restore ---")
    r = requests.get(f"{API}/audit-logs/deleted-products", headers=headers(owner_token))
    deleted = r.json()
    test_product = next((d for d in deleted if d["id"] == audit_id), None)
    
    if not test_product.get("restored_at"):
        print("❌ Deleted product entry should have restored_at")
        return False
    
    if not test_product.get("restored_by"):
        print("❌ Deleted product entry should have restored_by")
        return False
    
    if test_product.get("can_restore"):
        print("❌ Deleted product entry should have can_restore=false after restore")
        return False
    
    print(f"✅ Deleted product entry updated: restored_at={test_product.get('restored_at')[:19]}, restored_by={test_product.get('restored_by')}")
    
    # Try to restore again (should fail with 400)
    print("\n--- Testing second restore (should fail with 400) ---")
    r = requests.post(f"{API}/audit-logs/deleted-products/{audit_id}/restore", headers=headers(owner_token))
    if r.status_code != 400:
        print(f"❌ Second restore should return 400, got {r.status_code}")
        return False
    print("✅ Second restore correctly blocked (400)")
    
    # Verify audit log has restore_deleted entry
    print("\n--- Verifying audit log ---")
    r = requests.get(f"{API}/audit-logs", headers=headers(owner_token))
    logs = r.json()
    restore_log = next((log for log in logs if log.get("action") == "restore_deleted" and log.get("entity_id") == product_id), None)
    if not restore_log:
        print("❌ No restore_deleted audit log found")
        return False
    print("✅ Found restore_deleted audit log entry")
    
    # Test name conflict scenario
    print("\n--- Testing name conflict scenario ---")
    
    # Delete the restored product again
    r = requests.delete(f"{API}/products/{product_id}?permanent=true", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"❌ Failed to delete product again: {r.status_code}")
        return False
    print("✅ Deleted 'Uji Pulihkan' again")
    
    # Create a NEW product with same name
    body = {
        "name": "Uji Pulihkan",
        "category": "sampingan",
        "units": ["kg"],
        "price_kg": 8000,
        "stock_kg": 5
    }
    r = requests.post(f"{API}/products", headers=headers(owner_token), json=body)
    if r.status_code != 200:
        print(f"❌ Failed to create new product with same name: {r.status_code}")
        return False
    
    new_product = r.json()
    new_product_id = new_product["id"]
    print(f"✅ Created NEW product 'Uji Pulihkan' (different id: {new_product_id[:8]}...)")
    
    # Get deleted products - the latest delete should have can_restore=false
    r = requests.get(f"{API}/audit-logs/deleted-products", headers=headers(owner_token))
    deleted = r.json()
    latest_delete = next((d for d in deleted if d.get("name") == "Uji Pulihkan" and d.get("product_id") == product_id), None)
    
    if not latest_delete:
        print("❌ Latest delete entry not found")
        return False
    
    if latest_delete.get("can_restore"):
        print(f"❌ Latest delete should have can_restore=false due to name conflict")
        return False
    
    if latest_delete.get("blocked_reason") != "nama sudah dipakai produk aktif":
        print(f"❌ Expected blocked_reason='nama sudah dipakai produk aktif', got '{latest_delete.get('blocked_reason')}'")
        return False
    
    print(f"✅ Latest delete has can_restore=false, blocked_reason='{latest_delete.get('blocked_reason')}'")
    
    # Try to restore - should fail with 409
    latest_audit_id = latest_delete["id"]
    r = requests.post(f"{API}/audit-logs/deleted-products/{latest_audit_id}/restore", headers=headers(owner_token))
    if r.status_code != 409:
        print(f"❌ Restore with name conflict should return 409, got {r.status_code}")
        return False
    print("✅ Restore with name conflict correctly blocked (409)")
    
    # Clean up: delete the new product
    print("\n--- Cleaning up ---")
    r = requests.delete(f"{API}/products/{new_product_id}?permanent=true", headers=headers(owner_token))
    if r.status_code != 200:
        print(f"⚠️  Failed to clean up new product: {r.status_code}")
    else:
        print("✅ Cleaned up new product")
    
    # Test 404 for non-existent audit_id
    print("\n--- Testing 404 for non-existent audit_id ---")
    r = requests.post(f"{API}/audit-logs/deleted-products/tidak-ada/restore", headers=headers(owner_token))
    if r.status_code != 404:
        print(f"❌ Non-existent audit_id should return 404, got {r.status_code}")
        return False
    print("✅ Non-existent audit_id correctly returns 404")
    
    print("\n" + "="*80)
    print("✅ RESTORE DELETED PRODUCTS FEATURE: ALL TESTS PASSED")
    print("="*80)
    return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("BACKEND TESTS FOR NEW FEATURES")
    print("="*80)
    
    results = []
    
    # Test 1: Sync kg all
    try:
        results.append(("Sync Kg All", test_sync_kg_all()))
    except Exception as e:
        print(f"\n❌ EXCEPTION in test_sync_kg_all: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Sync Kg All", False))
    
    # Test 2: Restore deleted products
    try:
        results.append(("Restore Deleted Products", test_restore_deleted_products()))
    except Exception as e:
        print(f"\n❌ EXCEPTION in test_restore_deleted_products: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Restore Deleted Products", False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*80)
    
    exit(0 if all(p for _, p in results) else 1)
