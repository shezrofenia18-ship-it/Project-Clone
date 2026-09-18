"""
Backend API Testing for Berkah Ayam Mili - KG-EKOR Sync & Product Deletion Features
Tests the two new features:
1. KG-EKOR synchronization in production (cutting chickens)
2. Permanent product deletion with soft delete/restore
"""
import requests
import sys
import os
from datetime import datetime

# Get backend URL from frontend .env
BACKEND_URL = "https://repo-sync-128.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.failures = []

    def log(self, msg, level="INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {msg}")

    def test(self, name, func):
        """Run a single test"""
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
        """Make API call with auth"""
        url = f"{BACKEND_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers.setdefault("Content-Type", "application/json")
        
        response = requests.request(method, url, headers=headers, **kwargs)
        return response

    def summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(f"TEST SUMMARY")
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
    
    # Store test data
    test_data = {
        "broiler_id": None,
        "broiler_stock_kg_before": 0,
        "broiler_stock_ekor_before": 0,
        "broiler_avg_weight": 0,
        "production_id": None,
        "output_product_id": None,
        "test_product_id": None,
        "admin_token": None
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
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "owner", f"Expected owner role, got {data['user']['role']}"
        runner.token = data["token"]
        runner.log(f"Logged in as owner: {data['user']['name']}")

    runner.test("BACKEND: Login as owner", test_login_owner)

    # ==================== GET PRODUCTS & PREPARE ====================
    def test_get_products():
        """Get products and find Ayam Broiler"""
        response = runner.api_call("GET", "/products")
        assert response.status_code == 200, f"Failed to get products: {response.status_code}"
        products = response.json()
        assert isinstance(products, list), "Products should be a list"
        
        # Find Ayam Broiler
        broiler = next((p for p in products if "Broiler" in p["name"]), None)
        assert broiler is not None, "Ayam Broiler not found in products"
        
        # Check required fields
        assert "kg" in broiler.get("units", []), "Broiler should have kg unit"
        assert "ekor" in broiler.get("units", []), "Broiler should have ekor unit"
        
        # Store data
        test_data["broiler_id"] = broiler["id"]
        test_data["broiler_stock_kg_before"] = float(broiler.get("stock_kg", 0))
        test_data["broiler_stock_ekor_before"] = float(broiler.get("stock_ekor", 0))
        test_data["broiler_avg_weight"] = float(broiler.get("avg_weight_used", 0))
        
        runner.log(f"Found Ayam Broiler: {broiler['name']}")
        runner.log(f"  Stock: {test_data['broiler_stock_kg_before']} kg, {test_data['broiler_stock_ekor_before']} ekor")
        runner.log(f"  Avg weight: {test_data['broiler_avg_weight']} kg/ekor")
        
        assert test_data["broiler_avg_weight"] > 0, "Broiler avg_weight_used should be > 0"
        
        # Find an output product (potongan/sampingan category)
        output = next((p for p in products if p.get("category") in ["potongan", "sampingan"] and "pcs" in p.get("units", [])), None)
        assert output is not None, "No output product found for production"
        test_data["output_product_id"] = output["id"]
        runner.log(f"Found output product: {output['name']}")

    runner.test("BACKEND: GET /api/products - Get Ayam Broiler", test_get_products)

    # ==================== PRODUCTION WITH KG SYNC ====================
    def test_create_production():
        """Test POST /api/productions with kg sync"""
        input_ekor = 2
        expected_kg = round(input_ekor * test_data["broiler_avg_weight"], 3)
        
        response = runner.api_call("POST", "/productions", json={
            "source_product_id": test_data["broiler_id"],
            "input_ekor": input_ekor,
            "outputs": [
                {"product_id": test_data["output_product_id"], "pcs": 4}
            ]
        })
        
        assert response.status_code == 200, f"Failed to create production: {response.status_code} - {response.text}"
        data = response.json()
        
        # Check response has input_weight_kg
        assert "input_weight_kg" in data, "Response should have input_weight_kg"
        assert "avg_weight_used" in data, "Response should have avg_weight_used"
        
        actual_kg = float(data["input_weight_kg"])
        runner.log(f"Production created: {input_ekor} ekor → {actual_kg} kg")
        
        # Verify kg calculation (tolerance 0.001)
        assert abs(actual_kg - expected_kg) < 0.001, f"Expected {expected_kg} kg, got {actual_kg} kg"
        
        test_data["production_id"] = data["id"]
        
        # Verify stock changes
        response = runner.api_call("GET", "/products")
        products = response.json()
        broiler = next((p for p in products if p["id"] == test_data["broiler_id"]), None)
        
        new_stock_kg = float(broiler.get("stock_kg", 0))
        new_stock_ekor = float(broiler.get("stock_ekor", 0))
        
        expected_stock_kg = test_data["broiler_stock_kg_before"] - expected_kg
        expected_stock_ekor = test_data["broiler_stock_ekor_before"] - input_ekor
        
        runner.log(f"Stock after production:")
        runner.log(f"  Kg: {test_data['broiler_stock_kg_before']} → {new_stock_kg} (expected {expected_stock_kg})")
        runner.log(f"  Ekor: {test_data['broiler_stock_ekor_before']} → {new_stock_ekor} (expected {expected_stock_ekor})")
        
        assert abs(new_stock_kg - expected_stock_kg) < 0.001, f"Stock kg mismatch: expected {expected_stock_kg}, got {new_stock_kg}"
        assert abs(new_stock_ekor - expected_stock_ekor) < 0.001, f"Stock ekor mismatch: expected {expected_stock_ekor}, got {new_stock_ekor}"
        
        # Update stored values for next test
        test_data["broiler_stock_kg_after_create"] = new_stock_kg
        test_data["broiler_stock_ekor_after_create"] = new_stock_ekor

    runner.test("BACKEND: POST /api/productions - Create with kg sync", test_create_production)

    # ==================== UPDATE PRODUCTION ====================
    def test_update_production():
        """Test PUT /api/productions - Update and verify stock adjustment"""
        new_input_ekor = 1
        new_pcs = 2
        expected_kg = round(new_input_ekor * test_data["broiler_avg_weight"], 3)
        
        response = runner.api_call("PUT", f"/productions/{test_data['production_id']}", json={
            "source_product_id": test_data["broiler_id"],
            "input_ekor": new_input_ekor,
            "outputs": [
                {"product_id": test_data["output_product_id"], "pcs": new_pcs}
            ]
        })
        
        assert response.status_code == 200, f"Failed to update production: {response.status_code} - {response.text}"
        data = response.json()
        
        actual_kg = float(data["input_weight_kg"])
        runner.log(f"Production updated: {new_input_ekor} ekor → {actual_kg} kg")
        
        assert abs(actual_kg - expected_kg) < 0.001, f"Expected {expected_kg} kg, got {actual_kg} kg"
        
        # Verify stock adjustment (should return +1 ekor and +1.85 kg from after_create)
        response = runner.api_call("GET", "/products")
        products = response.json()
        broiler = next((p for p in products if p["id"] == test_data["broiler_id"]), None)
        
        new_stock_kg = float(broiler.get("stock_kg", 0))
        new_stock_ekor = float(broiler.get("stock_ekor", 0))
        
        # Net change from original: -1 ekor, -1.85 kg (reduced from -2 ekor, -3.7 kg)
        expected_stock_kg = test_data["broiler_stock_kg_before"] - expected_kg
        expected_stock_ekor = test_data["broiler_stock_ekor_before"] - new_input_ekor
        
        runner.log(f"Stock after update:")
        runner.log(f"  Kg: {test_data['broiler_stock_kg_after_create']} → {new_stock_kg} (expected {expected_stock_kg})")
        runner.log(f"  Ekor: {test_data['broiler_stock_ekor_after_create']} → {new_stock_ekor} (expected {expected_stock_ekor})")
        
        assert abs(new_stock_kg - expected_stock_kg) < 0.001, f"Stock kg mismatch: expected {expected_stock_kg}, got {new_stock_kg}"
        assert abs(new_stock_ekor - expected_stock_ekor) < 0.001, f"Stock ekor mismatch: expected {expected_stock_ekor}, got {new_stock_ekor}"

    runner.test("BACKEND: PUT /api/productions - Update with stock adjustment", test_update_production)

    # ==================== STOCK MOVEMENTS ====================
    def test_stock_movements():
        """Test GET /api/stock-movements - Verify production movements"""
        response = runner.api_call("GET", "/stock-movements", params={
            "product_id": test_data["broiler_id"]
        })
        
        assert response.status_code == 200, f"Failed to get stock movements: {response.status_code}"
        movements = response.json()
        
        # Find production movements
        prod_movements = [m for m in movements if m.get("type") == "produksi" and m.get("ref") == test_data["production_id"]]
        
        runner.log(f"Found {len(prod_movements)} production movements for broiler")
        
        # Should have at least one movement with negative qty_ekor and qty_kg
        assert len(prod_movements) > 0, "No production movements found"
        
        # Check the movements have qty_kg recorded
        for m in prod_movements:
            runner.log(f"  Movement: {m.get('qty_ekor')} ekor, {m.get('qty_kg')} kg")
            if m.get("qty_ekor") and m.get("qty_ekor") < 0:
                assert m.get("qty_kg") is not None, "Movement should have qty_kg"
                assert m.get("qty_kg") < 0, "qty_kg should be negative for production"

    runner.test("BACKEND: GET /api/stock-movements - Verify production movements", test_stock_movements)

    # ==================== PRODUCT DELETION TESTS ====================
    def test_create_test_product():
        """Create a test product for deletion"""
        response = runner.api_call("POST", "/products", json={
            "name": "Produk Uji Hapus",
            "category": "sampingan",
            "units": ["kg"],
            "price_kg": 1000
        })
        
        assert response.status_code == 200, f"Failed to create test product: {response.status_code} - {response.text}"
        data = response.json()
        test_data["test_product_id"] = data["id"]
        runner.log(f"Created test product: {data['name']} (ID: {data['id']})")

    runner.test("BACKEND: POST /api/products - Create test product", test_create_test_product)

    def test_product_usage():
        """Test GET /api/products/{id}/usage"""
        response = runner.api_call("GET", f"/products/{test_data['test_product_id']}/usage")
        
        assert response.status_code == 200, f"Failed to get product usage: {response.status_code}"
        data = response.json()
        
        assert "has_stock" in data, "Response should have has_stock"
        assert "has_history" in data, "Response should have has_history"
        assert "usage" in data, "Response should have usage"
        
        assert data["has_stock"] == False, "New product should have no stock"
        assert data["has_history"] == False, "New product should have no history"
        
        usage = data["usage"]
        assert usage["sales"] == 0, "Should have 0 sales"
        assert usage["purchases"] == 0, "Should have 0 purchases"
        assert usage["productions"] == 0, "Should have 0 productions"
        assert usage["movements"] == 0, "Should have 0 movements"
        
        runner.log(f"Product usage verified: no stock, no history")

    runner.test("BACKEND: GET /api/products/{id}/usage - Check usage info", test_product_usage)

    def test_soft_delete():
        """Test DELETE /api/products/{id} - Soft delete"""
        response = runner.api_call("DELETE", f"/products/{test_data['test_product_id']}")
        
        assert response.status_code == 200, f"Failed to soft delete: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data["ok"] == True, "Response should have ok=true"
        assert data["permanent"] == False, "Should be soft delete (permanent=false)"
        
        # Verify product is inactive
        response = runner.api_call("GET", "/products")
        products = response.json()
        product = next((p for p in products if p["id"] == test_data["test_product_id"]), None)
        
        assert product is not None, "Product should still exist"
        assert product["active"] == False, "Product should be inactive"
        
        runner.log(f"Product soft deleted (active=false)")

    runner.test("BACKEND: DELETE /api/products/{id} - Soft delete", test_soft_delete)

    def test_restore_product():
        """Test POST /api/products/{id}/restore"""
        response = runner.api_call("POST", f"/products/{test_data['test_product_id']}/restore")
        
        assert response.status_code == 200, f"Failed to restore: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data["active"] == True, "Product should be active after restore"
        
        runner.log(f"Product restored (active=true)")

    runner.test("BACKEND: POST /api/products/{id}/restore - Restore product", test_restore_product)

    def test_login_admin():
        """Login as admin for permission test"""
        response = runner.api_call("POST", "/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        
        # If admin doesn't exist, skip this test
        if response.status_code != 200:
            runner.log("Admin account not found, skipping admin permission test", "WARN")
            return
        
        data = response.json()
        test_data["admin_token"] = data["token"]
        runner.log(f"Logged in as admin: {data['user']['name']}")

    runner.test("BACKEND: Login as admin", test_login_admin)

    def test_permanent_delete_as_admin():
        """Test DELETE /api/products/{id}?permanent=true as admin - Should return 403"""
        if not test_data.get("admin_token"):
            runner.log("Skipping admin permission test (no admin token)", "SKIP")
            return
        
        # Temporarily use admin token
        original_token = runner.token
        runner.token = test_data["admin_token"]
        
        response = runner.api_call("DELETE", f"/products/{test_data['test_product_id']}", params={"permanent": "true"})
        
        # Restore owner token
        runner.token = original_token
        
        assert response.status_code == 403, f"Admin should get 403, got {response.status_code}"
        runner.log(f"Admin correctly denied permanent delete (403)")

    runner.test("BACKEND: DELETE permanent as admin - Should return 403", test_permanent_delete_as_admin)

    def test_permanent_delete_as_owner():
        """Test DELETE /api/products/{id}?permanent=true as owner"""
        response = runner.api_call("DELETE", f"/products/{test_data['test_product_id']}", params={"permanent": "true"})
        
        assert response.status_code == 200, f"Failed to permanently delete: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data["ok"] == True, "Response should have ok=true"
        assert data["permanent"] == True, "Should be permanent delete"
        
        # Verify product is gone
        response = runner.api_call("GET", "/products")
        products = response.json()
        product = next((p for p in products if p["id"] == test_data["test_product_id"]), None)
        
        assert product is None, "Product should not exist after permanent delete"
        
        # Verify usage endpoint returns 404
        response = runner.api_call("GET", f"/products/{test_data['test_product_id']}/usage")
        assert response.status_code == 404, "Usage endpoint should return 404 for deleted product"
        
        runner.log(f"Product permanently deleted")

    runner.test("BACKEND: DELETE permanent as owner - Delete permanently", test_permanent_delete_as_owner)

    def test_delete_nonexistent():
        """Test DELETE /api/products/tidak-ada - Should return 404"""
        response = runner.api_call("DELETE", "/products/tidak-ada-product-id-123")
        
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        runner.log(f"Correctly returned 404 for nonexistent product")

    runner.test("BACKEND: DELETE nonexistent product - Should return 404", test_delete_nonexistent)

    # ==================== SALES REGRESSION TEST ====================
    def test_sales_regression():
        """Test POST /api/sales - Verify ekor sale reduces both ekor and kg"""
        # Get current stock
        response = runner.api_call("GET", "/products")
        products = response.json()
        broiler = next((p for p in products if p["id"] == test_data["broiler_id"]), None)
        
        stock_kg_before = float(broiler.get("stock_kg", 0))
        stock_ekor_before = float(broiler.get("stock_ekor", 0))
        avg_weight = float(broiler.get("avg_weight_used", 0))
        
        # Create a sale
        import uuid
        response = runner.api_call("POST", "/sales", json={
            "txn_id": str(uuid.uuid4()),
            "items": [
                {
                    "product_id": test_data["broiler_id"],
                    "unit": "ekor",
                    "qty": 1,
                    "price": 34000
                }
            ],
            "payment_method": "cash",
            "paid": 34000
        })
        
        assert response.status_code == 200, f"Failed to create sale: {response.status_code} - {response.text}"
        
        # Verify stock changes
        response = runner.api_call("GET", "/products")
        products = response.json()
        broiler = next((p for p in products if p["id"] == test_data["broiler_id"]), None)
        
        stock_kg_after = float(broiler.get("stock_kg", 0))
        stock_ekor_after = float(broiler.get("stock_ekor", 0))
        
        expected_kg = stock_kg_before - avg_weight
        expected_ekor = stock_ekor_before - 1
        
        runner.log(f"Sale regression test:")
        runner.log(f"  Kg: {stock_kg_before} → {stock_kg_after} (expected {expected_kg})")
        runner.log(f"  Ekor: {stock_ekor_before} → {stock_ekor_after} (expected {expected_ekor})")
        
        assert abs(stock_kg_after - expected_kg) < 0.001, f"Stock kg mismatch: expected {expected_kg}, got {stock_kg_after}"
        assert abs(stock_ekor_after - expected_ekor) < 0.001, f"Stock ekor mismatch: expected {expected_ekor}, got {stock_ekor_after}"

    runner.test("BACKEND: POST /api/sales - Sales regression (ekor reduces kg)", test_sales_regression)

    # Print summary
    success = runner.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
