#!/usr/bin/env python3
"""
Test Fillet Cutting Feature - Berkah Ayam Mili
Tests the new pcs_after field for Ayam Fillet purchases
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

# Backend URL from frontend/.env
BASE_URL = "https://clone-preview-43.preview.emergentagent.com/api"

# Test credentials
OWNER_USERNAME = "owner"
OWNER_PASSWORD = "admin123"

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log_test(msg: str):
    print(f"{BLUE}[TEST]{RESET} {msg}")

def log_pass(msg: str):
    print(f"{GREEN}✅ PASS:{RESET} {msg}")

def log_fail(msg: str):
    print(f"{RED}❌ FAIL:{RESET} {msg}")

def log_info(msg: str):
    print(f"{YELLOW}ℹ INFO:{RESET} {msg}")

def log_section(title: str):
    print(f"\n{'='*80}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{'='*80}\n")


class FilletCuttingTest:
    def __init__(self):
        self.token = None
        self.supplier_id = None
        self.fillet_id = None
        self.broiler_id = None
        self.initial_fillet_stock = {}
        self.initial_broiler_stock = {}
        self.purchase_id = None
        self.passed = 0
        self.failed = 0
        
    def login(self) -> bool:
        """Login as owner"""
        log_test("Logging in as owner...")
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token") or data.get("token")
                if self.token:
                    log_pass(f"Login successful")
                    self.passed += 1
                    return True
                else:
                    log_fail("No token in response")
                    self.failed += 1
                    return False
            else:
                log_fail(f"Login failed: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Login exception: {e}")
            self.failed += 1
            return False
    
    def get_products(self) -> bool:
        """Get products and find Ayam Fillet and Ayam Broiler"""
        log_test("Getting products...")
        try:
            resp = requests.get(
                f"{BASE_URL}/products",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            
            if resp.status_code == 200:
                products = resp.json()
                log_pass(f"Got {len(products)} products")
                
                # Find Ayam Fillet
                fillet = next((p for p in products if p["name"] == "Ayam Fillet"), None)
                if fillet:
                    self.fillet_id = fillet["id"]
                    self.initial_fillet_stock = {
                        "stock_kg": float(fillet.get("stock_kg", 0) or 0),
                        "stock_pcs": float(fillet.get("stock_pcs", 0) or 0),
                        "stock_ekor": float(fillet.get("stock_ekor", 0) or 0)
                    }
                    log_info(f"Ayam Fillet: kg={self.initial_fillet_stock['stock_kg']}, pcs={self.initial_fillet_stock['stock_pcs']}, ekor={self.initial_fillet_stock['stock_ekor']}")
                    self.passed += 1
                else:
                    log_fail("Ayam Fillet not found")
                    self.failed += 1
                    return False
                
                # Find Ayam Broiler
                broiler = next((p for p in products if "Broiler" in p["name"]), None)
                if broiler:
                    self.broiler_id = broiler["id"]
                    self.initial_broiler_stock = {
                        "stock_kg": float(broiler.get("stock_kg", 0) or 0),
                        "stock_pcs": float(broiler.get("stock_pcs", 0) or 0),
                        "stock_ekor": float(broiler.get("stock_ekor", 0) or 0)
                    }
                    log_info(f"Ayam Broiler: kg={self.initial_broiler_stock['stock_kg']}, pcs={self.initial_broiler_stock['stock_pcs']}, ekor={self.initial_broiler_stock['stock_ekor']}")
                    self.passed += 1
                else:
                    log_fail("Ayam Broiler not found")
                    self.failed += 1
                    return False
                
                return True
            else:
                log_fail(f"Failed to get products: {resp.status_code}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception getting products: {e}")
            self.failed += 1
            return False
    
    def get_supplier(self) -> bool:
        """Get first supplier"""
        log_test("Getting suppliers...")
        try:
            resp = requests.get(
                f"{BASE_URL}/suppliers",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            
            if resp.status_code == 200:
                suppliers = resp.json()
                if suppliers:
                    self.supplier_id = suppliers[0]["id"]
                    log_pass(f"Got supplier: {suppliers[0]['name']}")
                    self.passed += 1
                    return True
                else:
                    log_fail("No suppliers found")
                    self.failed += 1
                    return False
            else:
                log_fail(f"Failed to get suppliers: {resp.status_code}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception getting suppliers: {e}")
            self.failed += 1
            return False
    
    def test_create_fillet_purchase(self) -> bool:
        """Test creating purchase with pcs_after (5 pcs supplier -> 10 pcs after cutting)"""
        log_test("Creating Ayam Fillet purchase with pcs_after (5 -> 10)...")
        try:
            payload = {
                "supplier_id": self.supplier_id,
                "items": [{
                    "product_id": self.fillet_id,
                    "ekor": 5,  # 5 pcs from supplier
                    "pcs_after": 10,  # 10 pcs after cutting
                    "total_weight": 4,
                    "total_price": 200000
                }],
                "paid": 200000
            }
            
            resp = requests.post(
                f"{BASE_URL}/purchases",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.purchase_id = data["id"]
                log_pass(f"Purchase created: {self.purchase_id}")
                
                # Verify response structure
                item = data["items"][0]
                checks = [
                    ("qty_unit", "pcs", item.get("qty_unit")),
                    ("pcs_supplier", 5, item.get("pcs_supplier")),
                    ("pcs", 10, item.get("pcs")),
                    ("avg_weight", 0.4, item.get("avg_weight")),  # 4 kg / 10 pcs
                    ("buy_price_kg", 50000, item.get("buy_price_kg")),  # 200000 / 4 kg
                    ("buy_price_pcs", 20000, item.get("buy_price_pcs")),  # 200000 / 10 pcs
                    ("subtotal", 200000, item.get("subtotal")),
                    ("total_modal", 200000, data.get("total_modal")),
                    ("total_pcs", 10, data.get("total_pcs"))
                ]
                
                all_ok = True
                for field, expected, actual in checks:
                    if isinstance(expected, float):
                        if abs(float(actual or 0) - expected) < 0.01:
                            log_info(f"  ✓ {field}: {actual} (expected {expected})")
                        else:
                            log_fail(f"  ✗ {field}: {actual} (expected {expected})")
                            all_ok = False
                    else:
                        if actual == expected:
                            log_info(f"  ✓ {field}: {actual}")
                        else:
                            log_fail(f"  ✗ {field}: {actual} (expected {expected})")
                            all_ok = False
                
                if all_ok:
                    self.passed += 1
                else:
                    self.failed += 1
                
                # Verify stock changes
                return self.verify_fillet_stock(
                    self.initial_fillet_stock["stock_kg"] + 4,
                    self.initial_fillet_stock["stock_pcs"] + 10,
                    self.initial_fillet_stock["stock_ekor"]  # ekor should not change
                )
            else:
                log_fail(f"Failed to create purchase: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception creating purchase: {e}")
            self.failed += 1
            return False
    
    def verify_fillet_stock(self, expected_kg: float, expected_pcs: float, expected_ekor: float) -> bool:
        """Verify Ayam Fillet stock"""
        log_test(f"Verifying Ayam Fillet stock (kg={expected_kg}, pcs={expected_pcs}, ekor={expected_ekor})...")
        try:
            resp = requests.get(
                f"{BASE_URL}/products",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            
            if resp.status_code == 200:
                products = resp.json()
                fillet = next((p for p in products if p["id"] == self.fillet_id), None)
                if fillet:
                    actual_kg = float(fillet.get("stock_kg", 0) or 0)
                    actual_pcs = float(fillet.get("stock_pcs", 0) or 0)
                    actual_ekor = float(fillet.get("stock_ekor", 0) or 0)
                    
                    kg_ok = abs(actual_kg - expected_kg) < 0.01
                    pcs_ok = abs(actual_pcs - expected_pcs) < 0.01
                    ekor_ok = abs(actual_ekor - expected_ekor) < 0.01
                    
                    if kg_ok and pcs_ok and ekor_ok:
                        log_pass(f"Stock correct: kg={actual_kg}, pcs={actual_pcs}, ekor={actual_ekor}")
                        self.passed += 1
                        return True
                    else:
                        log_fail(f"Stock incorrect:")
                        log_fail(f"  kg: {actual_kg} (expected {expected_kg}) {'✓' if kg_ok else '✗'}")
                        log_fail(f"  pcs: {actual_pcs} (expected {expected_pcs}) {'✓' if pcs_ok else '✗'}")
                        log_fail(f"  ekor: {actual_ekor} (expected {expected_ekor}) {'✓' if ekor_ok else '✗'}")
                        self.failed += 1
                        return False
                else:
                    log_fail("Ayam Fillet not found")
                    self.failed += 1
                    return False
            else:
                log_fail(f"Failed to get products: {resp.status_code}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception verifying stock: {e}")
            self.failed += 1
            return False
    
    def test_update_purchase(self) -> bool:
        """Test updating purchase (5 -> 8 pcs, 3 kg)"""
        log_test("Updating purchase (5 -> 8 pcs, 3 kg, 150000)...")
        try:
            payload = {
                "supplier_id": self.supplier_id,
                "items": [{
                    "product_id": self.fillet_id,
                    "ekor": 5,
                    "pcs_after": 8,
                    "total_weight": 3,
                    "total_price": 150000
                }],
                "paid": 150000
            }
            
            resp = requests.put(
                f"{BASE_URL}/purchases/{self.purchase_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                log_pass("Purchase updated")
                self.passed += 1
                # Stock should be: initial + 3 kg, + 8 pcs
                return self.verify_fillet_stock(
                    self.initial_fillet_stock["stock_kg"] + 3,
                    self.initial_fillet_stock["stock_pcs"] + 8,
                    self.initial_fillet_stock["stock_ekor"]
                )
            else:
                log_fail(f"Failed to update purchase: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception updating purchase: {e}")
            self.failed += 1
            return False
    
    def test_update_without_pcs_after(self) -> bool:
        """Test updating purchase without pcs_after (should fallback to ekor)"""
        log_test("Updating purchase without pcs_after (should use ekor=5)...")
        try:
            payload = {
                "supplier_id": self.supplier_id,
                "items": [{
                    "product_id": self.fillet_id,
                    "ekor": 5,
                    "total_weight": 3,
                    "total_price": 150000
                }],
                "paid": 150000
            }
            
            resp = requests.put(
                f"{BASE_URL}/purchases/{self.purchase_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                log_pass("Purchase updated without pcs_after")
                self.passed += 1
                # Stock should be: initial + 3 kg, + 5 pcs (fallback to ekor)
                return self.verify_fillet_stock(
                    self.initial_fillet_stock["stock_kg"] + 3,
                    self.initial_fillet_stock["stock_pcs"] + 5,
                    self.initial_fillet_stock["stock_ekor"]
                )
            else:
                log_fail(f"Failed to update purchase: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception updating purchase: {e}")
            self.failed += 1
            return False
    
    def test_delete_purchase(self) -> bool:
        """Test deleting purchase (stock should return to initial)"""
        log_test("Deleting purchase...")
        try:
            resp = requests.delete(
                f"{BASE_URL}/purchases/{self.purchase_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            
            if resp.status_code == 200:
                log_pass("Purchase deleted")
                self.passed += 1
                # Stock should return to initial
                return self.verify_fillet_stock(
                    self.initial_fillet_stock["stock_kg"],
                    self.initial_fillet_stock["stock_pcs"],
                    self.initial_fillet_stock["stock_ekor"]
                )
            else:
                log_fail(f"Failed to delete purchase: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception deleting purchase: {e}")
            self.failed += 1
            return False
    
    def test_broiler_regression(self) -> bool:
        """Test that whole chicken (Broiler) still works correctly (no pcs_after)"""
        log_test("Testing Ayam Broiler purchase (regression test)...")
        try:
            payload = {
                "supplier_id": self.supplier_id,
                "items": [{
                    "product_id": self.broiler_id,
                    "ekor": 2,
                    "total_weight": 4,
                    "total_price": 96000
                }],
                "paid": 96000
            }
            
            resp = requests.post(
                f"{BASE_URL}/purchases",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                broiler_purchase_id = data["id"]
                log_pass(f"Broiler purchase created: {broiler_purchase_id}")
                
                # Verify response
                item = data["items"][0]
                if item.get("qty_unit") == "ekor":
                    log_pass("  qty_unit is 'ekor' ✓")
                    self.passed += 1
                else:
                    log_fail(f"  qty_unit is '{item.get('qty_unit')}' (expected 'ekor')")
                    self.failed += 1
                
                # Verify stock (should increase kg and ekor, not pcs)
                resp2 = requests.get(
                    f"{BASE_URL}/products",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10
                )
                
                if resp2.status_code == 200:
                    products = resp2.json()
                    broiler = next((p for p in products if p["id"] == self.broiler_id), None)
                    if broiler:
                        actual_kg = float(broiler.get("stock_kg", 0) or 0)
                        actual_ekor = float(broiler.get("stock_ekor", 0) or 0)
                        
                        expected_kg = self.initial_broiler_stock["stock_kg"] + 4
                        expected_ekor = self.initial_broiler_stock["stock_ekor"] + 2
                        
                        kg_ok = abs(actual_kg - expected_kg) < 0.01
                        ekor_ok = abs(actual_ekor - expected_ekor) < 0.01
                        
                        if kg_ok and ekor_ok:
                            log_pass(f"  Broiler stock correct: kg={actual_kg}, ekor={actual_ekor}")
                            self.passed += 1
                        else:
                            log_fail(f"  Broiler stock incorrect: kg={actual_kg} (expected {expected_kg}), ekor={actual_ekor} (expected {expected_ekor})")
                            self.failed += 1
                
                # Clean up
                requests.delete(
                    f"{BASE_URL}/purchases/{broiler_purchase_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10
                )
                log_info("  Cleaned up Broiler purchase")
                
                return True
            else:
                log_fail(f"Failed to create Broiler purchase: {resp.status_code} - {resp.text[:200]}")
                self.failed += 1
                return False
        except Exception as e:
            log_fail(f"Exception testing Broiler: {e}")
            self.failed += 1
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        log_section("FILLET CUTTING FEATURE TEST")
        
        if not self.login():
            return False
        
        if not self.get_products():
            return False
        
        if not self.get_supplier():
            return False
        
        log_section("TEST 1: Create Fillet Purchase (5 -> 10 pcs)")
        self.test_create_fillet_purchase()
        
        log_section("TEST 2: Update Purchase (5 -> 8 pcs)")
        self.test_update_purchase()
        
        log_section("TEST 3: Update Without pcs_after (fallback to ekor)")
        self.test_update_without_pcs_after()
        
        log_section("TEST 4: Delete Purchase (stock returns to initial)")
        self.test_delete_purchase()
        
        log_section("TEST 5: Broiler Regression Test")
        self.test_broiler_regression()
        
        log_section("TEST SUMMARY")
        total = self.passed + self.failed
        print(f"Total tests: {total}")
        print(f"{GREEN}Passed: {self.passed}{RESET}")
        print(f"{RED}Failed: {self.failed}{RESET}")
        print()
        
        return self.failed == 0


if __name__ == "__main__":
    test = FilletCuttingTest()
    success = test.run_all_tests()
    
    if success:
        print(f"\n{GREEN}{'='*80}{RESET}")
        print(f"{GREEN}✅ ALL TESTS PASSED{RESET}")
        print(f"{GREEN}{'='*80}{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{RED}{'='*80}{RESET}")
        print(f"{RED}❌ SOME TESTS FAILED{RESET}")
        print(f"{RED}{'='*80}{RESET}\n")
        sys.exit(1)
