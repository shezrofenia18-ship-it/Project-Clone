"""
Backend API Testing for Berkah Ayam Mili - Three New Features
Tests:
1. SINKRONKAN KG (Sync KG): stock_sync field, preview, and sync endpoints
2. PERINGATAN SELISIH (Gap Warning): out_of_sync detection
3. RIWAYAT PRODUK TERHAPUS (Deleted Products History): deleted products endpoint
"""
import requests
import sys
from datetime import datetime

BACKEND_URL = "https://repo-sync-128.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.failures = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {msg}")

    def test(self, name, func):
        self.tests_run += 1
        self.log(f"Testing: {name}")
        try:
            func()
            self.tests_passed += 1
            self.log(f"✅ PASSED: {name}", "PASS")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.failures.append({"test": name, "error": str(e)})
            self.log(f"❌ FAILED: {name} - {str(e)}", "FAIL")
            return False
        except Exception as e:
            self.tests_failed += 1
            self.failures.append({"test": name, "error": f"Exception: {str(e)}"})
            self.log(f"❌ ERROR: {name} - {str(e)}", "ERROR")
            return False

    def api_call(self, method, endpoint, **kwargs):
        url = f"{BACKEND_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers.setdefault("Content-Type", "application/json")
        response = requests.request(method, url, headers=headers, **kwargs)
        return response

    def summary(self):
        print("\n" + "="*60)
        print(f"TEST SUMMARY - Three New Features")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed} ✅")
        print(f"Failed: {self.tests_failed} ❌")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failures:
            print("\n" + "="*60)
            print("FAILED TESTS:")
            print("="*60)
            for f in self.failures:
                print(f"❌ {f['test']}")
                print(f"   Error: {f['error']}")
        
        return self.tests_failed == 0


def main():
    runner = TestRunner()
    
    # Test data storage
    test_data = {
        "kampung_id": "54204ab3-513c-4c67-a368-46f66d246e86",
        "ati_ampela_id": None,
        "test_product_id": None,
        "admin_token": None,
        "kampung_stock_kg_before": 0,
        "kampung_stock_ekor_before": 0,
        "kampung_expected_kg": 0,
    }

    # ==================== AUTHENTICATION ====================
    def test_login_owner():
        """Test login as owner"""
        response = runner.api_call("POST", "/auth/login", json={
            "username": "owner",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        runner.token = data["token"]
        runner.log(f"Owner logged in successfully")

    runner.test("Login as owner", test_login_owner)

    # ==================== FEATURE 1: STOCK_SYNC FIELD ====================
    def test_get_products_stock_sync():
        """Test GET /api/products returns stock_sync field"""
        response = runner.api_call("GET", "/products")
        assert response.status_code == 200, f"Failed to get products: {response.status_code}"
        products = response.json()
        
        # Find Ayam Kampung
        kampung = None
        for p in products:
            if p.get("id") == test_data["kampung_id"]:
                kampung = p
                break
        
        assert kampung is not None, f"Ayam Kampung not found with id {test_data['kampung_id']}"
        runner.log(f"Found Ayam Kampung: {kampung.get('name')}")
        
        # Check stock_sync field exists and is not null
        assert "stock_sync" in kampung, "stock_sync field missing"
        assert kampung["stock_sync"] is not None, "stock_sync should not be null for whole chicken"
        
        sync_info = kampung["stock_sync"]
        assert "avg_weight" in sync_info, "avg_weight missing in stock_sync"
        assert "expected_kg" in sync_info, "expected_kg missing in stock_sync"
        assert "diff_kg" in sync_info, "diff_kg missing in stock_sync"
        assert "diff_pct" in sync_info, "diff_pct missing in stock_sync"
        assert "implied_avg" in sync_info, "implied_avg missing in stock_sync"
        assert "out_of_sync" in sync_info, "out_of_sync missing in stock_sync"
        assert "reason" in sync_info, "reason missing in stock_sync"
        
        runner.log(f"stock_sync: avg_weight={sync_info['avg_weight']}, expected_kg={sync_info['expected_kg']}, diff_kg={sync_info['diff_kg']}, out_of_sync={sync_info['out_of_sync']}")
        
        # Store current stock for later tests
        test_data["kampung_stock_kg_before"] = kampung.get("stock_kg", 0)
        test_data["kampung_stock_ekor_before"] = kampung.get("stock_ekor", 0)
        test_data["kampung_expected_kg"] = sync_info.get("expected_kg")
        
        # Find Ati Ampela (non-whole chicken product)
        ati = None
        for p in products:
            if "ati" in p.get("name", "").lower() and "ampela" in p.get("name", "").lower():
                ati = p
                test_data["ati_ampela_id"] = p.get("id")
                break
        
        if ati:
            runner.log(f"Found Ati Ampela: {ati.get('name')}, id={ati.get('id')}")
            assert ati.get("stock_sync") is None, "Ati Ampela stock_sync should be null (not whole chicken)"
            runner.log("Ati Ampela correctly has stock_sync=null")

    runner.test("GET /api/products returns stock_sync field", test_get_products_stock_sync)

    # ==================== CREATE GAP FOR TESTING ====================
    def test_create_stock_gap():
        """Create stock gap by adjusting kg only"""
        response = runner.api_call("POST", "/stock-adjustments", json={
            "product_id": test_data["kampung_id"],
            "delta_kg": 20,
            "delta_ekor": 0,
            "reason": "Test: create gap for sync testing"
        })
        assert response.status_code == 200, f"Failed to create adjustment: {response.status_code} - {response.text}"
        runner.log("Created +20 kg adjustment to create gap")

    runner.test("Create stock gap via adjustment", test_create_stock_gap)

    # ==================== VERIFY OUT_OF_SYNC ====================
    def test_verify_out_of_sync():
        """Verify product is now out_of_sync"""
        response = runner.api_call("GET", "/products")
        assert response.status_code == 200, f"Failed to get products: {response.status_code}"
        products = response.json()
        
        kampung = None
        for p in products:
            if p.get("id") == test_data["kampung_id"]:
                kampung = p
                break
        
        assert kampung is not None, "Ayam Kampung not found"
        sync_info = kampung.get("stock_sync")
        assert sync_info is not None, "stock_sync is null"
        
        runner.log(f"After adjustment: diff_kg={sync_info['diff_kg']}, diff_pct={sync_info['diff_pct']}, out_of_sync={sync_info['out_of_sync']}")
        
        # Should be out of sync now (diff > 0.5 kg AND pct > 15%)
        assert sync_info["out_of_sync"] == True, f"Expected out_of_sync=true, got {sync_info['out_of_sync']}"
        assert abs(sync_info["diff_kg"]) > 0.5, f"diff_kg should be > 0.5, got {sync_info['diff_kg']}"
        assert "kg lebih besar dari perkiraan" in sync_info.get("reason", ""), f"Expected reason about kg being larger, got: {sync_info.get('reason')}"

    runner.test("Verify product is out_of_sync after adjustment", test_verify_out_of_sync)

    # ==================== PREVIEW SYNC ====================
    def test_preview_sync_kg():
        """Test GET /api/products/{id}/sync-kg preview"""
        response = runner.api_call("GET", f"/products/{test_data['kampung_id']}/sync-kg")
        assert response.status_code == 200, f"Failed to preview sync: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "expected_kg" in data, "expected_kg missing in preview"
        assert "stock_kg" in data, "stock_kg missing in preview"
        assert "stock_ekor" in data, "stock_ekor missing in preview"
        
        runner.log(f"Preview sync: stock_kg={data['stock_kg']}, expected_kg={data['expected_kg']}, stock_ekor={data['stock_ekor']}")
        
        # Expected should be ekor * avg_weight (1.2)
        expected_calc = data["stock_ekor"] * 1.2
        assert abs(data["expected_kg"] - expected_calc) < 0.1, f"Expected kg calculation mismatch: {data['expected_kg']} vs {expected_calc}"

    runner.test("GET /api/products/{id}/sync-kg preview", test_preview_sync_kg)

    # ==================== ADMIN CANNOT SYNC ====================
    def test_admin_cannot_sync():
        """Test admin gets 403 when trying to sync"""
        # Login as admin
        response = runner.api_call("POST", "/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Admin login failed: {response.status_code}"
        test_data["admin_token"] = response.json()["token"]
        
        # Try to sync as admin
        old_token = runner.token
        runner.token = test_data["admin_token"]
        
        response = runner.api_call("POST", f"/products/{test_data['kampung_id']}/sync-kg", json={})
        assert response.status_code == 403, f"Expected 403 for admin, got {response.status_code}"
        runner.log("Admin correctly blocked from syncing (403)")
        
        # Restore owner token
        runner.token = old_token

    runner.test("Admin cannot POST sync-kg (403)", test_admin_cannot_sync)

    # ==================== OWNER SYNC KG ====================
    def test_owner_sync_kg():
        """Test owner can sync kg"""
        response = runner.api_call("POST", f"/products/{test_data['kampung_id']}/sync-kg", json={
            "reason": "Test sync from automated test"
        })
        assert response.status_code == 200, f"Failed to sync: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Sync should return ok=true"
        assert data.get("changed") == True, "Sync should return changed=true"
        assert "delta_kg" in data, "delta_kg missing"
        assert data["delta_kg"] < 0, f"delta_kg should be negative (removing excess), got {data['delta_kg']}"
        
        runner.log(f"Sync successful: delta_kg={data['delta_kg']}, stock_kg={data['stock_kg']}, expected_kg={data['expected_kg']}")
        
        # Verify stock_kg now equals expected_kg
        assert abs(data["stock_kg"] - data["expected_kg"]) < 0.01, f"stock_kg should equal expected_kg after sync"

    runner.test("Owner POST /api/products/{id}/sync-kg", test_owner_sync_kg)

    # ==================== VERIFY SYNC RESULT ====================
    def test_verify_sync_result():
        """Verify product is no longer out_of_sync"""
        response = runner.api_call("GET", "/products")
        assert response.status_code == 200, f"Failed to get products: {response.status_code}"
        products = response.json()
        
        kampung = None
        for p in products:
            if p.get("id") == test_data["kampung_id"]:
                kampung = p
                break
        
        assert kampung is not None, "Ayam Kampung not found"
        sync_info = kampung.get("stock_sync")
        assert sync_info is not None, "stock_sync is null"
        
        runner.log(f"After sync: stock_kg={kampung['stock_kg']}, expected_kg={sync_info['expected_kg']}, out_of_sync={sync_info['out_of_sync']}")
        
        # Should NOT be out of sync anymore
        assert sync_info["out_of_sync"] == False, f"Expected out_of_sync=false after sync, got {sync_info['out_of_sync']}"
        
        # stock_kg should equal ekor * 1.2
        expected = kampung.get("stock_ekor", 0) * 1.2
        assert abs(kampung["stock_kg"] - expected) < 0.1, f"stock_kg should be {expected}, got {kampung['stock_kg']}"

    runner.test("Verify product no longer out_of_sync", test_verify_sync_result)

    # ==================== SYNC AGAIN (NO CHANGE) ====================
    def test_sync_again_no_change():
        """Test syncing again returns changed=false"""
        response = runner.api_call("POST", f"/products/{test_data['kampung_id']}/sync-kg", json={})
        assert response.status_code == 200, f"Failed to sync: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Sync should return ok=true"
        assert data.get("changed") == False, "Sync should return changed=false (already synced)"
        assert data.get("delta_kg") == 0, f"delta_kg should be 0, got {data['delta_kg']}"
        
        runner.log("Second sync correctly returns changed=false, delta_kg=0")

    runner.test("Sync again returns changed=false", test_sync_again_no_change)

    # ==================== VERIFY STOCK MOVEMENT ====================
    def test_verify_stock_movement():
        """Verify stock movement was created with type 'penyesuaian'"""
        response = runner.api_call("GET", f"/stock-movements?product_id={test_data['kampung_id']}")
        assert response.status_code == 200, f"Failed to get movements: {response.status_code}"
        
        movements = response.json()
        assert len(movements) > 0, "No stock movements found"
        
        # Find the sync movement (should be recent)
        sync_movement = None
        for m in movements:
            if m.get("type") == "penyesuaian" and "Sinkronisasi" in m.get("ref", ""):
                sync_movement = m
                break
        
        assert sync_movement is not None, "No penyesuaian movement with 'Sinkronisasi' found"
        runner.log(f"Found sync movement: type={sync_movement['type']}, qty_kg={sync_movement.get('qty_kg')}, ref={sync_movement.get('ref')}")
        
        # qty_kg should be negative (removing excess)
        assert sync_movement.get("qty_kg", 0) < 0, f"Sync movement qty_kg should be negative, got {sync_movement.get('qty_kg')}"

    runner.test("Verify stock movement type 'penyesuaian' created", test_verify_stock_movement)

    # ==================== VERIFY AUDIT LOG ====================
    def test_verify_audit_log():
        """Verify audit log has action 'sync_kg'"""
        response = runner.api_call("GET", "/audit-logs")
        assert response.status_code == 200, f"Failed to get audit logs: {response.status_code}"
        
        logs = response.json()
        
        # Find sync_kg action
        sync_log = None
        for log in logs:
            if log.get("action") == "sync_kg" and log.get("entity") == "stock":
                sync_log = log
                break
        
        assert sync_log is not None, "No audit log with action='sync_kg' found"
        runner.log(f"Found sync_kg audit log: entity={sync_log['entity']}, entity_id={sync_log.get('entity_id')}")

    runner.test("Verify audit log action 'sync_kg'", test_verify_audit_log)

    # ==================== NON-WHOLE CHICKEN SYNC ====================
    def test_non_whole_chicken_sync():
        """Test syncing non-whole chicken product returns 400"""
        if test_data["ati_ampela_id"]:
            response = runner.api_call("POST", f"/products/{test_data['ati_ampela_id']}/sync-kg", json={})
            assert response.status_code == 400, f"Expected 400 for non-whole chicken, got {response.status_code}"
            runner.log("Non-whole chicken correctly returns 400")
        else:
            runner.log("Skipping: Ati Ampela not found")

    runner.test("POST sync-kg on non-whole chicken returns 400", test_non_whole_chicken_sync)

    # ==================== NON-EXISTENT PRODUCT ====================
    def test_non_existent_product_sync():
        """Test syncing non-existent product returns 404"""
        response = runner.api_call("POST", "/products/tidak-ada-id-123/sync-kg", json={})
        assert response.status_code == 404, f"Expected 404 for non-existent product, got {response.status_code}"
        runner.log("Non-existent product correctly returns 404")

    runner.test("POST sync-kg on non-existent product returns 404", test_non_existent_product_sync)

    # ==================== FEATURE 3: DELETED PRODUCTS ====================
    def test_create_and_delete_product():
        """Create test product and delete it permanently"""
        # Create product
        response = runner.api_call("POST", "/products", json={
            "name": "Uji Riwayat Hapus",
            "category": "sampingan",
            "units": ["kg"],
            "price_kg": 5000,
            "active": True
        })
        assert response.status_code == 200, f"Failed to create product: {response.status_code} - {response.text}"
        
        product = response.json()
        test_data["test_product_id"] = product.get("id")
        runner.log(f"Created test product: {product.get('name')}, id={test_data['test_product_id']}")
        
        # Delete permanently
        response = runner.api_call("DELETE", f"/products/{test_data['test_product_id']}?permanent=true")
        assert response.status_code == 200, f"Failed to delete product: {response.status_code} - {response.text}"
        runner.log("Deleted product permanently")

    runner.test("Create and delete product permanently", test_create_and_delete_product)

    # ==================== GET DELETED PRODUCTS ====================
    def test_get_deleted_products():
        """Test GET /api/audit-logs/deleted-products"""
        response = runner.api_call("GET", "/audit-logs/deleted-products")
        assert response.status_code == 200, f"Failed to get deleted products: {response.status_code} - {response.text}"
        
        deleted = response.json()
        assert isinstance(deleted, list), "Response should be a list"
        
        # Find our test product
        test_deleted = None
        for d in deleted:
            if d.get("name") == "Uji Riwayat Hapus":
                test_deleted = d
                break
        
        assert test_deleted is not None, "Test product not found in deleted products"
        runner.log(f"Found deleted product: {test_deleted.get('name')}")
        
        # Verify fields
        assert test_deleted.get("deleted_by") is not None, "deleted_by should not be null"
        assert "owner" in test_deleted.get("deleted_by", "").lower(), f"deleted_by should contain 'owner', got {test_deleted.get('deleted_by')}"
        assert test_deleted.get("deleted_by_role") == "owner", f"deleted_by_role should be 'owner', got {test_deleted.get('deleted_by_role')}"
        assert test_deleted.get("deleted_at") is not None, "deleted_at should not be null"
        assert test_deleted.get("price_kg") == 5000, f"price_kg should be 5000, got {test_deleted.get('price_kg')}"
        
        # Check usage fields
        usage = test_deleted.get("usage", {})
        assert usage.get("total_sold_kg", 0) == 0, "usage.total_sold_kg should be 0"
        
        runner.log(f"Deleted product details: deleted_by={test_deleted['deleted_by']}, role={test_deleted['deleted_by_role']}, price_kg={test_deleted['price_kg']}")

    runner.test("GET /api/audit-logs/deleted-products", test_get_deleted_products)

    # ==================== ADMIN CAN GET DELETED PRODUCTS ====================
    def test_admin_can_get_deleted():
        """Test admin can also GET deleted products"""
        old_token = runner.token
        runner.token = test_data["admin_token"]
        
        response = runner.api_call("GET", "/audit-logs/deleted-products")
        assert response.status_code == 200, f"Admin should be able to get deleted products, got {response.status_code}"
        runner.log("Admin can successfully GET deleted products")
        
        runner.token = old_token

    runner.test("Admin can GET deleted products", test_admin_can_get_deleted)

    # ==================== KASIR CANNOT GET DELETED PRODUCTS ====================
    def test_kasir_cannot_get_deleted():
        """Test kasir gets 403 for deleted products"""
        # Login as kasir
        response = runner.api_call("POST", "/auth/login", json={
            "username": "kasir",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            kasir_token = response.json()["token"]
            old_token = runner.token
            runner.token = kasir_token
            
            response = runner.api_call("GET", "/audit-logs/deleted-products")
            assert response.status_code == 403, f"Kasir should get 403, got {response.status_code}"
            runner.log("Kasir correctly blocked from getting deleted products (403)")
            
            runner.token = old_token
        else:
            runner.log("Skipping: kasir login failed (may not exist)")

    runner.test("Kasir cannot GET deleted products (403)", test_kasir_cannot_get_deleted)

    # ==================== SUMMARY ====================
    success = runner.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
