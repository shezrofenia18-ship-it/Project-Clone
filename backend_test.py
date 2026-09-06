#!/usr/bin/env python3
"""
Backend API Test for Fillet Product Detection Feature
Tests the revised fillet detection logic in purchases.
"""
import requests
import sys
import json
from datetime import datetime

BASE_URL = "https://clone-deploy-51.preview.emergentagent.com/api"

class FilletPurchaseAPITester:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_products_created = []
        self.test_purchases_created = []
        self.baseline_stocks = {}

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASSED - {name} (Status: {response.status_code})", "PASS")
            else:
                self.log(f"❌ FAILED - {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                self.log(f"Response: {response.text[:500]}", "FAIL")

            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {}
            
            return success, response_data, response.status_code

        except Exception as e:
            self.log(f"❌ FAILED - {name} - Error: {str(e)}", "FAIL")
            return False, {}, 0

    def test_login(self):
        """Test login with owner credentials"""
        self.log("\n=== TEST 1: Authentication ===")
        success, response, _ = self.run_test(
            "Login as owner",
            "POST",
            "/auth/login",
            200,
            data={"username": "owner", "password": "admin123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log(f"Token obtained: {self.token[:20]}...", "INFO")
            return True
        return False

    def test_get_products_with_new_fields(self):
        """Test GET /api/products returns new fields: is_fillet, is_purchasable, purchase_unit"""
        self.log("\n=== TEST 2: GET /api/products - New Fields ===")
        success, products, _ = self.run_test(
            "GET /api/products",
            "GET",
            "/products",
            200
        )
        
        if not success or not products:
            return False
        
        # Find specific products and verify their fields
        ayam_fillet = next((p for p in products if p.get('name') == 'Ayam Fillet'), None)
        dada_fillet = next((p for p in products if p.get('name') == 'Dada Fillet'), None)
        ayam_broiler = next((p for p in products if p.get('name') == 'Ayam Broiler'), None)
        ceker = next((p for p in products if 'Ceker' in p.get('name', '')), None)
        dada_ayam = next((p for p in products if p.get('name') == 'Dada Ayam'), None)
        
        all_passed = True
        
        # Test Ayam Fillet
        if ayam_fillet:
            self.log(f"Ayam Fillet: is_fillet={ayam_fillet.get('is_fillet')}, is_purchasable={ayam_fillet.get('is_purchasable')}, purchase_unit={ayam_fillet.get('purchase_unit')}")
            if ayam_fillet.get('is_fillet') == True and ayam_fillet.get('is_purchasable') == True and ayam_fillet.get('purchase_unit') == 'pcs':
                self.log("✅ Ayam Fillet fields correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Ayam Fillet fields incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Test Dada Fillet
        if dada_fillet:
            self.log(f"Dada Fillet: is_fillet={dada_fillet.get('is_fillet')}, is_purchasable={dada_fillet.get('is_purchasable')}, purchase_unit={dada_fillet.get('purchase_unit')}")
            if dada_fillet.get('is_fillet') == True and dada_fillet.get('is_purchasable') == True and dada_fillet.get('purchase_unit') == 'pcs':
                self.log("✅ Dada Fillet fields correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Dada Fillet fields incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Test Ayam Broiler
        if ayam_broiler:
            self.log(f"Ayam Broiler: is_fillet={ayam_broiler.get('is_fillet')}, is_purchasable={ayam_broiler.get('is_purchasable')}, purchase_unit={ayam_broiler.get('purchase_unit')}")
            if ayam_broiler.get('is_fillet') == False and ayam_broiler.get('is_purchasable') == True and ayam_broiler.get('purchase_unit') == 'ekor':
                self.log("✅ Ayam Broiler fields correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Ayam Broiler fields incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Test Ceker Ayam (non-purchasable)
        if ceker:
            self.log(f"Ceker Ayam: is_fillet={ceker.get('is_fillet')}, is_purchasable={ceker.get('is_purchasable')}, purchase_unit={ceker.get('purchase_unit')}")
            if ceker.get('is_purchasable') == False and ceker.get('purchase_unit') is None:
                self.log("✅ Ceker Ayam fields correct (not purchasable)", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Ceker Ayam should not be purchasable", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Test Dada Ayam (non-purchasable)
        if dada_ayam:
            self.log(f"Dada Ayam: is_fillet={dada_ayam.get('is_fillet')}, is_purchasable={dada_ayam.get('is_purchasable')}, purchase_unit={dada_ayam.get('purchase_unit')}")
            if dada_ayam.get('is_purchasable') == False and dada_ayam.get('purchase_unit') is None:
                self.log("✅ Dada Ayam fields correct (not purchasable)", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Dada Ayam should not be purchasable", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        return all_passed

    def test_create_fillet_products(self):
        """Create test fillet products with name and category matching"""
        self.log("\n=== TEST 3: Create Test Fillet Products ===")
        
        # Test 1: Product with 'fillet' in name but non-fillet category
        success1, product1, _ = self.run_test(
            "Create 'Paha FILLET Test' (name match)",
            "POST",
            "/products",
            200,
            data={
                "name": "Paha FILLET Test",
                "category": "potongan",
                "units": ["kg"],
                "buy_price_kg": 50000,
                "hpp_kg": 50000,
                "price_kg": 60000
            }
        )
        if success1:
            self.test_products_created.append(product1.get('id'))
            self.log(f"Created product ID: {product1.get('id')}")
        
        # Test 2: Product with category 'fillet' but name without 'fillet'
        success2, product2, _ = self.run_test(
            "Create 'Tenderloin Test' (category match)",
            "POST",
            "/products",
            200,
            data={
                "name": "Tenderloin Test",
                "category": "fillet",
                "units": ["kg"],
                "buy_price_kg": 55000,
                "hpp_kg": 55000,
                "price_kg": 65000
            }
        )
        if success2:
            self.test_products_created.append(product2.get('id'))
            self.log(f"Created product ID: {product2.get('id')}")
        
        # Verify both products are detected as fillet
        if success1 and success2:
            success, products, _ = self.run_test(
                "Verify test products are fillet",
                "GET",
                "/products",
                200
            )
            if success:
                paha = next((p for p in products if p.get('id') == product1.get('id')), None)
                tender = next((p for p in products if p.get('id') == product2.get('id')), None)
                
                if paha and paha.get('is_fillet') == True:
                    self.log("✅ Paha FILLET Test detected as fillet (name match)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Paha FILLET Test not detected as fillet", "FAIL")
                self.tests_run += 1
                
                if tender and tender.get('is_fillet') == True:
                    self.log("✅ Tenderloin Test detected as fillet (category match)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Tenderloin Test not detected as fillet", "FAIL")
                self.tests_run += 1
        
        return success1 and success2

    def capture_baseline_stocks(self):
        """Capture current stock levels before purchase tests"""
        self.log("\n=== Capturing Baseline Stocks ===")
        success, products, _ = self.run_test(
            "Get products for baseline",
            "GET",
            "/products",
            200
        )
        if success:
            for p in products:
                self.baseline_stocks[p['id']] = {
                    'stock_kg': p.get('stock_kg', 0),
                    'stock_pcs': p.get('stock_pcs', 0),
                    'stock_ekor': p.get('stock_ekor', 0),
                    'name': p.get('name')
                }
            self.log(f"Captured baseline for {len(self.baseline_stocks)} products")
            return True
        return False

    def test_create_multi_fillet_purchase(self):
        """Test POST /api/purchases with multiple fillet lines + whole chicken"""
        self.log("\n=== TEST 4: Create Purchase with Multiple Fillet Lines ===")
        
        # Get supplier
        success, suppliers, _ = self.run_test(
            "Get suppliers",
            "GET",
            "/suppliers",
            200
        )
        if not success or not suppliers:
            self.log("❌ No suppliers found", "FAIL")
            return False
        
        supplier_id = suppliers[0]['id']
        self.log(f"Using supplier: {suppliers[0]['name']}")
        
        # Get products
        success, products, _ = self.run_test(
            "Get products for purchase",
            "GET",
            "/products",
            200
        )
        if not success:
            return False
        
        dada_fillet = next((p for p in products if p.get('name') == 'Dada Fillet'), None)
        ayam_fillet = next((p for p in products if p.get('name') == 'Ayam Fillet'), None)
        ayam_broiler = next((p for p in products if p.get('name') == 'Ayam Broiler'), None)
        
        if not all([dada_fillet, ayam_fillet, ayam_broiler]):
            self.log("❌ Required products not found", "FAIL")
            return False
        
        # Create purchase with 2 fillet lines + 1 whole chicken
        purchase_data = {
            "supplier_id": supplier_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {
                    "product_id": dada_fillet['id'],
                    "ekor": 5,  # 5 pcs from supplier
                    "pcs_after": 10,  # 10 pcs after cutting
                    "total_weight": 4,
                    "total_price": 200000
                },
                {
                    "product_id": ayam_fillet['id'],
                    "ekor": 3,  # 3 pcs from supplier
                    "pcs_after": None,  # no additional cutting
                    "total_weight": 2.4,
                    "total_price": 100000
                },
                {
                    "product_id": ayam_broiler['id'],
                    "ekor": 10,
                    "total_weight": 20,
                    "total_price": 400000
                }
            ],
            "paid": 700000
        }
        
        success, purchase, _ = self.run_test(
            "Create multi-fillet purchase",
            "POST",
            "/purchases",
            200,
            data=purchase_data
        )
        
        if not success:
            return False
        
        self.test_purchases_created.append(purchase['id'])
        self.log(f"Created purchase ID: {purchase['id']}")
        
        # Verify response items
        items = purchase.get('items', [])
        all_passed = True
        
        # Check Dada Fillet item
        dada_item = next((i for i in items if i['product_id'] == dada_fillet['id']), None)
        if dada_item:
            self.log(f"Dada Fillet item: qty_unit={dada_item.get('qty_unit')}, pcs_supplier={dada_item.get('pcs_supplier')}, pcs={dada_item.get('pcs')}, buy_price_pcs={dada_item.get('buy_price_pcs')}")
            if (dada_item.get('qty_unit') == 'pcs' and 
                dada_item.get('pcs_supplier') == 5 and 
                dada_item.get('pcs') == 10 and
                abs(dada_item.get('buy_price_pcs', 0) - 20000) < 1):
                self.log("✅ Dada Fillet item correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Dada Fillet item incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Check Ayam Fillet item
        ayam_item = next((i for i in items if i['product_id'] == ayam_fillet['id']), None)
        if ayam_item:
            self.log(f"Ayam Fillet item: qty_unit={ayam_item.get('qty_unit')}, pcs_supplier={ayam_item.get('pcs_supplier')}, pcs={ayam_item.get('pcs')}, buy_price_pcs={ayam_item.get('buy_price_pcs')}")
            if (ayam_item.get('qty_unit') == 'pcs' and 
                ayam_item.get('pcs_supplier') == 3 and 
                ayam_item.get('pcs') == 3 and
                abs(ayam_item.get('buy_price_pcs', 0) - 33333.33) < 1):
                self.log("✅ Ayam Fillet item correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Ayam Fillet item incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Check Ayam Broiler item
        broiler_item = next((i for i in items if i['product_id'] == ayam_broiler['id']), None)
        if broiler_item:
            self.log(f"Ayam Broiler item: qty_unit={broiler_item.get('qty_unit')}, ekor={broiler_item.get('ekor')}")
            if broiler_item.get('qty_unit') == 'ekor' and broiler_item.get('ekor') == 10:
                self.log("✅ Ayam Broiler item correct", "PASS")
                self.tests_passed += 1
            else:
                self.log("❌ Ayam Broiler item incorrect", "FAIL")
                all_passed = False
            self.tests_run += 1
        
        # Verify stock changes
        success, products_after, _ = self.run_test(
            "Get products after purchase",
            "GET",
            "/products",
            200
        )
        
        if success:
            dada_after = next((p for p in products_after if p['id'] == dada_fillet['id']), None)
            ayam_after = next((p for p in products_after if p['id'] == ayam_fillet['id']), None)
            broiler_after = next((p for p in products_after if p['id'] == ayam_broiler['id']), None)
            
            # Check Dada Fillet stock
            if dada_after:
                baseline = self.baseline_stocks.get(dada_fillet['id'], {})
                kg_increase = dada_after.get('stock_kg', 0) - baseline.get('stock_kg', 0)
                pcs_increase = dada_after.get('stock_pcs', 0) - baseline.get('stock_pcs', 0)
                ekor_change = dada_after.get('stock_ekor', 0) - baseline.get('stock_ekor', 0)
                
                self.log(f"Dada Fillet stock: kg +{kg_increase}, pcs +{pcs_increase}, ekor +{ekor_change}")
                if abs(kg_increase - 4) < 0.01 and abs(pcs_increase - 10) < 0.01 and abs(ekor_change) < 0.01:
                    self.log("✅ Dada Fillet stock correct (+4 kg, +10 pcs, ekor unchanged)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Dada Fillet stock incorrect", "FAIL")
                    all_passed = False
                self.tests_run += 1
            
            # Check Ayam Fillet stock
            if ayam_after:
                baseline = self.baseline_stocks.get(ayam_fillet['id'], {})
                kg_increase = ayam_after.get('stock_kg', 0) - baseline.get('stock_kg', 0)
                pcs_increase = ayam_after.get('stock_pcs', 0) - baseline.get('stock_pcs', 0)
                ekor_change = ayam_after.get('stock_ekor', 0) - baseline.get('stock_ekor', 0)
                
                self.log(f"Ayam Fillet stock: kg +{kg_increase}, pcs +{pcs_increase}, ekor +{ekor_change}")
                if abs(kg_increase - 2.4) < 0.01 and abs(pcs_increase - 3) < 0.01 and abs(ekor_change) < 0.01:
                    self.log("✅ Ayam Fillet stock correct (+2.4 kg, +3 pcs, ekor unchanged)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Ayam Fillet stock incorrect", "FAIL")
                    all_passed = False
                self.tests_run += 1
            
            # Check Ayam Broiler stock
            if broiler_after:
                baseline = self.baseline_stocks.get(ayam_broiler['id'], {})
                kg_increase = broiler_after.get('stock_kg', 0) - baseline.get('stock_kg', 0)
                ekor_increase = broiler_after.get('stock_ekor', 0) - baseline.get('stock_ekor', 0)
                
                self.log(f"Ayam Broiler stock: kg +{kg_increase}, ekor +{ekor_increase}")
                if abs(kg_increase - 20) < 0.01 and abs(ekor_increase - 10) < 0.01:
                    self.log("✅ Ayam Broiler stock correct (+20 kg, +10 ekor)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Ayam Broiler stock incorrect", "FAIL")
                    all_passed = False
                self.tests_run += 1
        
        return all_passed

    def test_update_purchase(self):
        """Test PUT /api/purchases/{id} (Koreksi)"""
        self.log("\n=== TEST 5: Update Purchase (Koreksi) ===")
        
        if not self.test_purchases_created:
            self.log("❌ No test purchase to update", "FAIL")
            return False
        
        purchase_id = self.test_purchases_created[0]
        
        # Get current purchase
        success, purchases, _ = self.run_test(
            "Get purchases",
            "GET",
            "/purchases",
            200
        )
        if not success:
            return False
        
        purchase = next((p for p in purchases if p['id'] == purchase_id), None)
        if not purchase:
            self.log("❌ Purchase not found", "FAIL")
            return False
        
        # Get products
        success, products, _ = self.run_test(
            "Get products",
            "GET",
            "/products",
            200
        )
        if not success:
            return False
        
        dada_fillet = next((p for p in products if p.get('name') == 'Dada Fillet'), None)
        
        # Capture stock before update
        stock_before = {
            'kg': dada_fillet.get('stock_kg', 0),
            'pcs': dada_fillet.get('stock_pcs', 0)
        }
        
        # Update purchase - change Dada Fillet to ekor=5, pcs_after=12, total_weight=4.5
        update_data = {
            "supplier_id": purchase['supplier_id'],
            "date": purchase['date'],
            "items": [
                {
                    "product_id": dada_fillet['id'],
                    "ekor": 5,
                    "pcs_after": 12,  # Changed from 10 to 12
                    "total_weight": 4.5,  # Changed from 4 to 4.5
                    "total_price": 200000
                }
            ] + [item for item in purchase['items'] if item['product_id'] != dada_fillet['id']],
            "paid": purchase['paid']
        }
        
        success, updated, _ = self.run_test(
            "Update purchase (Koreksi)",
            "PUT",
            f"/purchases/{purchase_id}",
            200,
            data=update_data
        )
        
        if not success:
            return False
        
        # Verify stock adjustment
        success, products_after, _ = self.run_test(
            "Get products after update",
            "GET",
            "/products",
            200
        )
        
        if success:
            dada_after = next((p for p in products_after if p['id'] == dada_fillet['id']), None)
            if dada_after:
                # Net change should be +0.5 kg and +2 pcs from original baseline
                baseline = self.baseline_stocks.get(dada_fillet['id'], {})
                kg_total = dada_after.get('stock_kg', 0) - baseline.get('stock_kg', 0)
                pcs_total = dada_after.get('stock_pcs', 0) - baseline.get('stock_pcs', 0)
                
                self.log(f"Dada Fillet stock after update: kg +{kg_total}, pcs +{pcs_total} (from baseline)")
                if abs(kg_total - 4.5) < 0.01 and abs(pcs_total - 12) < 0.01:
                    self.log("✅ Stock adjusted correctly (+4.5 kg, +12 pcs from baseline)", "PASS")
                    self.tests_passed += 1
                else:
                    self.log("❌ Stock adjustment incorrect", "FAIL")
                self.tests_run += 1
        
        return success

    def test_delete_purchase(self):
        """Test DELETE /api/purchases/{id}"""
        self.log("\n=== TEST 6: Delete Purchase ===")
        
        if not self.test_purchases_created:
            self.log("❌ No test purchase to delete", "FAIL")
            return False
        
        purchase_id = self.test_purchases_created[0]
        
        success, _, _ = self.run_test(
            "Delete purchase",
            "DELETE",
            f"/purchases/{purchase_id}",
            200
        )
        
        if not success:
            return False
        
        # Verify stocks returned to baseline
        success, products, _ = self.run_test(
            "Get products after delete",
            "GET",
            "/products",
            200
        )
        
        if success:
            all_passed = True
            for product_id, baseline in self.baseline_stocks.items():
                product = next((p for p in products if p['id'] == product_id), None)
                if product and baseline.get('name') in ['Dada Fillet', 'Ayam Fillet', 'Ayam Broiler']:
                    kg_diff = abs(product.get('stock_kg', 0) - baseline.get('stock_kg', 0))
                    pcs_diff = abs(product.get('stock_pcs', 0) - baseline.get('stock_pcs', 0))
                    ekor_diff = abs(product.get('stock_ekor', 0) - baseline.get('stock_ekor', 0))
                    
                    if kg_diff < 0.01 and pcs_diff < 0.01 and ekor_diff < 0.01:
                        self.log(f"✅ {baseline['name']} stock restored to baseline", "PASS")
                    else:
                        self.log(f"❌ {baseline['name']} stock not restored (kg diff: {kg_diff}, pcs diff: {pcs_diff}, ekor diff: {ekor_diff})", "FAIL")
                        all_passed = False
            
            if all_passed:
                self.tests_passed += 1
            self.tests_run += 1
            
            return all_passed
        
        return False

    def test_non_purchasable_rejection(self):
        """Test POST /api/purchases with non-purchasable product returns 400"""
        self.log("\n=== TEST 7: Non-Purchasable Product Rejection ===")
        
        # Get supplier
        success, suppliers, _ = self.run_test(
            "Get suppliers",
            "GET",
            "/suppliers",
            200
        )
        if not success or not suppliers:
            return False
        
        supplier_id = suppliers[0]['id']
        
        # Get products
        success, products, _ = self.run_test(
            "Get products",
            "GET",
            "/products",
            200
        )
        if not success:
            return False
        
        # Find non-purchasable product (Ceker Ayam or Dada Ayam)
        non_purchasable = next((p for p in products if 'Ceker' in p.get('name', '') or p.get('name') == 'Dada Ayam'), None)
        
        if not non_purchasable:
            self.log("⚠️ No non-purchasable product found to test", "WARN")
            return True
        
        self.log(f"Testing with non-purchasable product: {non_purchasable['name']}")
        
        # Try to create purchase with non-purchasable product
        purchase_data = {
            "supplier_id": supplier_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {
                    "product_id": non_purchasable['id'],
                    "ekor": 5,
                    "total_weight": 2,
                    "total_price": 50000
                }
            ],
            "paid": 50000
        }
        
        success, response, status = self.run_test(
            f"Create purchase with {non_purchasable['name']} (should fail)",
            "POST",
            "/purchases",
            400,
            data=purchase_data
        )
        
        if success:
            # Check if error message mentions fillet in Indonesian
            error_msg = response.get('detail', '')
            if 'fillet' in error_msg.lower() or 'tidak bisa dicatat' in error_msg.lower():
                self.log(f"✅ Correct error message: {error_msg}", "PASS")
                self.tests_passed += 1
            else:
                self.log(f"⚠️ Error message doesn't mention fillet: {error_msg}", "WARN")
            self.tests_run += 1
        
        return success

    def cleanup(self):
        """Clean up test data"""
        self.log("\n=== Cleanup ===")
        
        # Delete test purchases (already done in test_delete_purchase)
        for purchase_id in self.test_purchases_created[1:]:  # Skip first one as it's already deleted
            self.run_test(
                f"Delete test purchase {purchase_id}",
                "DELETE",
                f"/purchases/{purchase_id}",
                200
            )
        
        # Delete test products
        for product_id in self.test_products_created:
            self.run_test(
                f"Delete test product {product_id}",
                "DELETE",
                f"/products/{product_id}",
                200
            )
        
        self.log("Cleanup completed")

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*60)
        self.log("TEST SUMMARY")
        self.log("="*60)
        self.log(f"Total Tests Run: {self.tests_run}")
        self.log(f"Tests Passed: {self.tests_passed}")
        self.log(f"Tests Failed: {self.tests_run - self.tests_passed}")
        self.log(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "N/A")
        self.log("="*60)
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = FilletPurchaseAPITester()
    
    try:
        # Run tests in sequence
        if not tester.test_login():
            print("❌ Login failed, stopping tests")
            return 1
        
        tester.test_get_products_with_new_fields()
        tester.test_create_fillet_products()
        tester.capture_baseline_stocks()
        tester.test_create_multi_fillet_purchase()
        tester.test_update_purchase()
        tester.test_delete_purchase()
        tester.test_non_purchasable_rejection()
        
        # Cleanup
        tester.cleanup()
        
        # Print summary
        return tester.print_summary()
        
    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
