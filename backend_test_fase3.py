#!/usr/bin/env python3
"""
Backend Testing for Berkah Ayam Mili - FASE 3
Tests: HPP per ekor, Tutup Buku Harian, Realtime WebSocket, Regression
"""
import requests
import json
import uuid
import time
import websocket
from datetime import datetime, timezone, timedelta
from typing import Optional

# Configuration
BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"
WS_BASE_URL = "wss://commit-inspector.preview.emergentagent.com/api"
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"
ADMIN_EMAIL = "admin@berkahayam.com"
ADMIN_PASSWORD = "admin123"
KASIR_EMAIL = "kasir@berkahayam.com"
KASIR_PASSWORD = "kasir123"

# Jakarta timezone
JKT_TZ = timezone(timedelta(hours=7))

class TestRunner:
    def __init__(self):
        self.owner_token = None
        self.admin_token = None
        self.kasir_token = None
        self.test_results = []
        self.products = []
        self.customers = []
        self.test_product_id = None
        self.test_purchase_ids = []
        
    def log(self, test_name, status, details=""):
        result = {"test": test_name, "status": status, "details": details}
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"\n{status_icon} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def login(self, email, password):
        """Login and get token"""
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": password
        })
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        return data.get("access_token") or data.get("token")
    
    def setup_auth(self):
        """Setup authentication for all roles"""
        print("\n" + "="*80)
        print("SETTING UP AUTHENTICATION")
        print("="*80)
        
        self.owner_token = self.login(OWNER_EMAIL, OWNER_PASSWORD)
        if not self.owner_token:
            self.log("Owner Login", "FAIL", "Could not login as owner")
            return False
        print(f"✅ Owner logged in")
        
        self.admin_token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if not self.admin_token:
            self.log("Admin Login", "FAIL", "Could not login as admin")
            return False
        print(f"✅ Admin logged in")
        
        self.kasir_token = self.login(KASIR_EMAIL, KASIR_PASSWORD)
        if not self.kasir_token:
            self.log("Kasir Login", "FAIL", "Could not login as kasir")
            return False
        print(f"✅ Kasir logged in")
        
        return True
    
    def get_headers(self, token):
        return {"Authorization": f"Bearer {token}"}
    
    def load_products(self):
        """Load products for testing"""
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        if resp.status_code == 200:
            self.products = resp.json()
            print(f"✅ Loaded {len(self.products)} products")
            return True
        return False
    
    def get_product_by_category(self, category):
        """Get first product by category"""
        for p in self.products:
            if p.get("category") == category and "ekor" in p.get("units", []):
                return p
        return None
    
    def today_str(self):
        return datetime.now(JKT_TZ).strftime("%Y-%m-%d")
    
    def iso_now(self):
        return datetime.now(JKT_TZ).isoformat()
    
    # ==================== TEST 1: HPP PER EKOR ====================
    
    def test_hpp_per_ekor(self):
        """Test HPP per ekor calculation from average weight"""
        print("\n" + "="*80)
        print("TEST 1: HPP PER EKOR DARI BERAT RATA-RATA")
        print("="*80)
        
        # Find a broiler or kampung product
        product = self.get_product_by_category("broiler") or self.get_product_by_category("kampung")
        if not product:
            self.log("HPP Test Setup", "FAIL", "No broiler/kampung product found")
            return
        
        self.test_product_id = product["id"]
        product_name = product["name"]
        print(f"\n📦 Testing with product: {product_name} (ID: {self.test_product_id})")
        
        # Get supplier
        resp = requests.get(f"{BASE_URL}/suppliers", headers=self.get_headers(self.owner_token))
        suppliers = resp.json()
        if not suppliers:
            self.log("HPP Test Setup", "FAIL", "No suppliers found")
            return
        supplier_id = suppliers[0]["id"]
        
        # TEST 1a: First purchase
        print("\n--- Test 1a: First Purchase (10 ekor, 15 kg, Rp 450,000) ---")
        purchase1_body = {
            "supplier_id": supplier_id,
            "date": self.today_str(),
            "items": [{
                "product_id": self.test_product_id,
                "ekor": 10,
                "total_weight": 15,
                "total_price": 450000
            }],
            "transport_cost": 0,
            "other_cost": 0,
            "paid": 450000,
            "notes": "Test HPP 1a"
        }
        
        resp = requests.post(f"{BASE_URL}/purchases", 
                           json=purchase1_body,
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1a: First Purchase", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        purchase1 = resp.json()
        self.test_purchase_ids.append(purchase1["id"])
        
        # Check product after first purchase
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product_after = next((p for p in products if p["id"] == self.test_product_id), None)
        
        if not product_after:
            self.log("Test 1a: Product Check", "FAIL", "Product not found after purchase")
            return
        
        # Expected values
        expected_cum_ekor = 10
        expected_cum_weight = 15
        expected_avg_weight = 1.5
        expected_hpp_kg = 30000
        expected_hpp_ekor = 45000
        
        actual_cum_ekor = product_after.get("cum_ekor_in", 0)
        actual_cum_weight = product_after.get("cum_weight_in", 0)
        actual_avg_weight = product_after.get("avg_weight_ekor", 0)
        actual_hpp_kg = product_after.get("hpp_kg", 0)
        actual_hpp_ekor = product_after.get("hpp_ekor", 0)
        
        checks = [
            ("cum_ekor_in", expected_cum_ekor, actual_cum_ekor),
            ("cum_weight_in", expected_cum_weight, actual_cum_weight),
            ("avg_weight_ekor", expected_avg_weight, actual_avg_weight),
            ("hpp_kg", expected_hpp_kg, actual_hpp_kg),
            ("hpp_ekor", expected_hpp_ekor, actual_hpp_ekor)
        ]
        
        all_pass = True
        for field, expected, actual in checks:
            if abs(float(expected) - float(actual)) < 0.01:
                print(f"   ✅ {field}: {actual} (expected {expected})")
            else:
                print(f"   ❌ {field}: {actual} (expected {expected})")
                all_pass = False
        
        if all_pass:
            self.log("Test 1a: First Purchase", "PASS", 
                    f"cum_ekor={actual_cum_ekor}, cum_weight={actual_cum_weight}, avg={actual_avg_weight}, hpp_kg={actual_hpp_kg}, hpp_ekor={actual_hpp_ekor}")
        else:
            self.log("Test 1a: First Purchase", "FAIL", "Values don't match expected")
            return
        
        # TEST 1b: Second purchase (different weight per ekor)
        print("\n--- Test 1b: Second Purchase (10 ekor, 25 kg, Rp 875,000) ---")
        purchase2_body = {
            "supplier_id": supplier_id,
            "date": self.today_str(),
            "items": [{
                "product_id": self.test_product_id,
                "ekor": 10,
                "total_weight": 25,
                "total_price": 875000
            }],
            "transport_cost": 0,
            "other_cost": 0,
            "paid": 875000,
            "notes": "Test HPP 1b"
        }
        
        resp = requests.post(f"{BASE_URL}/purchases", 
                           json=purchase2_body,
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1b: Second Purchase", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        purchase2 = resp.json()
        self.test_purchase_ids.append(purchase2["id"])
        
        # Check product after second purchase
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product_after = next((p for p in products if p["id"] == self.test_product_id), None)
        
        # Expected: cum_ekor=20, cum_weight=40, avg=2.0
        # hpp_kg from second purchase = 875000/25 = 35000
        # hpp_ekor = 35000 * 2.0 = 70000
        expected_cum_ekor = 20
        expected_cum_weight = 40
        expected_avg_weight = 2.0
        expected_hpp_kg = 35000
        expected_hpp_ekor = 70000
        
        actual_cum_ekor = product_after.get("cum_ekor_in", 0)
        actual_cum_weight = product_after.get("cum_weight_in", 0)
        actual_avg_weight = product_after.get("avg_weight_ekor", 0)
        actual_hpp_kg = product_after.get("hpp_kg", 0)
        actual_hpp_ekor = product_after.get("hpp_ekor", 0)
        
        checks = [
            ("cum_ekor_in", expected_cum_ekor, actual_cum_ekor),
            ("cum_weight_in", expected_cum_weight, actual_cum_weight),
            ("avg_weight_ekor", expected_avg_weight, actual_avg_weight),
            ("hpp_kg", expected_hpp_kg, actual_hpp_kg),
            ("hpp_ekor", expected_hpp_ekor, actual_hpp_ekor)
        ]
        
        all_pass = True
        for field, expected, actual in checks:
            if abs(float(expected) - float(actual)) < 0.01:
                print(f"   ✅ {field}: {actual} (expected {expected})")
            else:
                print(f"   ❌ {field}: {actual} (expected {expected})")
                all_pass = False
        
        if all_pass:
            self.log("Test 1b: Second Purchase", "PASS", 
                    f"cum_ekor={actual_cum_ekor}, cum_weight={actual_cum_weight}, avg={actual_avg_weight}, hpp_ekor={actual_hpp_ekor}")
        else:
            self.log("Test 1b: Second Purchase", "FAIL", "Values don't match expected")
        
        # TEST 1c: Set manual override
        print("\n--- Test 1c: Set Manual Override (1.8 kg) ---")
        resp = requests.post(f"{BASE_URL}/products/{self.test_product_id}/avg-weight",
                           json={"avg_weight_override": 1.8},
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1c: Manual Override", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        product_after = resp.json()
        
        expected_source = "manual"
        expected_used = 1.8
        expected_hpp_ekor = 35000 * 1.8  # 63000
        
        actual_source = product_after.get("avg_weight_source")
        actual_used = product_after.get("avg_weight_used", 0)
        actual_hpp_ekor = product_after.get("hpp_ekor", 0)
        
        checks = [
            ("avg_weight_source", expected_source, actual_source),
            ("avg_weight_used", expected_used, actual_used),
            ("hpp_ekor", expected_hpp_ekor, actual_hpp_ekor)
        ]
        
        all_pass = True
        for field, expected, actual in checks:
            if field == "avg_weight_source":
                if expected == actual:
                    print(f"   ✅ {field}: {actual}")
                else:
                    print(f"   ❌ {field}: {actual} (expected {expected})")
                    all_pass = False
            else:
                if abs(float(expected) - float(actual)) < 0.01:
                    print(f"   ✅ {field}: {actual} (expected {expected})")
                else:
                    print(f"   ❌ {field}: {actual} (expected {expected})")
                    all_pass = False
        
        if all_pass:
            self.log("Test 1c: Manual Override", "PASS", 
                    f"source={actual_source}, used={actual_used}, hpp_ekor={actual_hpp_ekor}")
        else:
            self.log("Test 1c: Manual Override", "FAIL", "Values don't match expected")
        
        # TEST 1d: Reset to auto
        print("\n--- Test 1d: Reset to Auto (override=0) ---")
        resp = requests.post(f"{BASE_URL}/products/{self.test_product_id}/avg-weight",
                           json={"avg_weight_override": 0},
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1d: Reset to Auto", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        product_after = resp.json()
        
        expected_source = "auto"
        expected_used = 2.0  # Back to automatic average
        
        actual_source = product_after.get("avg_weight_source")
        actual_used = product_after.get("avg_weight_used", 0)
        
        if actual_source == expected_source and abs(actual_used - expected_used) < 0.01:
            print(f"   ✅ avg_weight_source: {actual_source}")
            print(f"   ✅ avg_weight_used: {actual_used}")
            self.log("Test 1d: Reset to Auto", "PASS", f"source={actual_source}, used={actual_used}")
        else:
            print(f"   ❌ avg_weight_source: {actual_source} (expected {expected_source})")
            print(f"   ❌ avg_weight_used: {actual_used} (expected {expected_used})")
            self.log("Test 1d: Reset to Auto", "FAIL", "Values don't match expected")
        
        # TEST 1e: Update product without touching override
        print("\n--- Test 1e: Update Product (override should persist) ---")
        # First set override again
        resp = requests.post(f"{BASE_URL}/products/{self.test_product_id}/avg-weight",
                           json={"avg_weight_override": 1.9},
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1e: Set Override", "FAIL", f"Status {resp.status_code}")
            return
        
        # Now update product without avg_weight_override field
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product_current = next((p for p in products if p["id"] == self.test_product_id), None)
        
        update_body = {
            "name": product_current["name"],
            "category": product_current["category"],
            "units": product_current["units"],
            "price_kg": product_current.get("price_kg", 0),
            "price_ekor": product_current.get("price_ekor", 0) + 100,  # Small change
            "price_pcs": product_current.get("price_pcs", 0),
            "buy_price_kg": product_current.get("buy_price_kg", 0),
            "hpp_kg": product_current.get("hpp_kg", 0),
            "hpp_ekor": product_current.get("hpp_ekor", 0),
            "hpp_pcs": product_current.get("hpp_pcs", 0),
            "stock_kg": product_current.get("stock_kg", 0),
            "stock_ekor": product_current.get("stock_ekor", 0),
            "stock_pcs": product_current.get("stock_pcs", 0),
            "min_stock_kg": product_current.get("min_stock_kg", 0),
            "min_stock_ekor": product_current.get("min_stock_ekor", 0),
            "min_stock_pcs": product_current.get("min_stock_pcs", 0),
            "image_url": product_current.get("image_url", ""),
            "is_byproduct": product_current.get("is_byproduct", False),
            "active": product_current.get("active", True)
            # Note: NOT including avg_weight_override
        }
        
        resp = requests.put(f"{BASE_URL}/products/{self.test_product_id}",
                          json=update_body,
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1e: Update Product", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        product_after = resp.json()
        
        actual_override = product_after.get("avg_weight_override", 0)
        actual_source = product_after.get("avg_weight_source")
        
        if actual_override == 1.9 and actual_source == "manual":
            print(f"   ✅ avg_weight_override: {actual_override} (persisted)")
            print(f"   ✅ avg_weight_source: {actual_source}")
            self.log("Test 1e: Update Product", "PASS", "Override persisted after update")
        else:
            print(f"   ❌ avg_weight_override: {actual_override} (expected 1.9)")
            print(f"   ❌ avg_weight_source: {actual_source} (expected manual)")
            self.log("Test 1e: Update Product", "FAIL", "Override was reset")
        
        # TEST 1f: Delete purchase
        print("\n--- Test 1f: Delete Purchase (should decrease accumulators) ---")
        if len(self.test_purchase_ids) < 2:
            self.log("Test 1f: Delete Purchase", "FAIL", "Not enough purchases to delete")
            return
        
        # Get current values
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product_before = next((p for p in products if p["id"] == self.test_product_id), None)
        
        cum_ekor_before = product_before.get("cum_ekor_in", 0)
        cum_weight_before = product_before.get("cum_weight_in", 0)
        
        # Delete first purchase (10 ekor, 15 kg)
        resp = requests.delete(f"{BASE_URL}/purchases/{self.test_purchase_ids[0]}",
                             headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 1f: Delete Purchase", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        # Check product after deletion
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product_after = next((p for p in products if p["id"] == self.test_product_id), None)
        
        cum_ekor_after = product_after.get("cum_ekor_in", 0)
        cum_weight_after = product_after.get("cum_weight_in", 0)
        
        # Expected: decreased by 10 ekor and 15 kg
        expected_cum_ekor = cum_ekor_before - 10
        expected_cum_weight = cum_weight_before - 15
        
        if abs(cum_ekor_after - expected_cum_ekor) < 0.01 and abs(cum_weight_after - expected_cum_weight) < 0.01:
            print(f"   ✅ cum_ekor_in: {cum_ekor_before} → {cum_ekor_after} (decreased by 10)")
            print(f"   ✅ cum_weight_in: {cum_weight_before} → {cum_weight_after} (decreased by 15)")
            self.log("Test 1f: Delete Purchase", "PASS", 
                    f"Accumulators decreased correctly: ekor {cum_ekor_before}→{cum_ekor_after}, weight {cum_weight_before}→{cum_weight_after}")
        else:
            print(f"   ❌ cum_ekor_in: {cum_ekor_after} (expected {expected_cum_ekor})")
            print(f"   ❌ cum_weight_in: {cum_weight_after} (expected {expected_cum_weight})")
            self.log("Test 1f: Delete Purchase", "FAIL", "Accumulators not decreased correctly")
        
        # TEST 1g: Kasir access control
        print("\n--- Test 1g: Kasir Access Control (should be 403) ---")
        resp = requests.post(f"{BASE_URL}/products/{self.test_product_id}/avg-weight",
                           json={"avg_weight_override": 2.0},
                           headers=self.get_headers(self.kasir_token))
        
        if resp.status_code == 403:
            print(f"   ✅ Kasir correctly rejected with 403")
            self.log("Test 1g: Kasir Access Control", "PASS", "Kasir cannot set avg weight")
        else:
            print(f"   ❌ Status: {resp.status_code} (expected 403)")
            self.log("Test 1g: Kasir Access Control", "FAIL", f"Got {resp.status_code} instead of 403")
    
    # ==================== TEST 2: TUTUP BUKU HARIAN ====================
    
    def test_tutup_buku(self):
        """Test daily closing functionality"""
        print("\n" + "="*80)
        print("TEST 2: TUTUP BUKU HARIAN")
        print("="*80)
        
        today = self.today_str()
        
        # TEST 2a: Preview as owner
        print("\n--- Test 2a: Preview as Owner ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 2a: Preview Owner", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        preview = resp.json()
        
        # Check required fields
        required_fields = [
            "omzet", "hpp", "gross_profit", "net_profit", "margin", "opex",
            "kas_dari_penjualan", "piutang_baru", "bayar_piutang_masuk", "kas_masuk_total",
            "by_method", "by_cashier", "top_products", "stock_items", "stock_value",
            "receivable_outstanding", "payable_outstanding", "already_closed"
        ]
        
        missing_fields = [f for f in required_fields if f not in preview]
        
        if missing_fields:
            self.log("Test 2a: Preview Owner", "FAIL", f"Missing fields: {missing_fields}")
            return
        
        # Verify calculations
        omzet = preview.get("omzet", 0)
        hpp = preview.get("hpp", 0)
        gross_profit = preview.get("gross_profit", 0)
        opex = preview.get("opex", 0)
        net_profit = preview.get("net_profit", 0)
        kas_jual = preview.get("kas_dari_penjualan", 0)
        bayar_piutang = preview.get("bayar_piutang_masuk", 0)
        kas_total = preview.get("kas_masuk_total", 0)
        
        calc_checks = []
        
        # Check: gross_profit == omzet - hpp
        expected_gross = omzet - hpp
        if abs(gross_profit - expected_gross) < 0.01:
            calc_checks.append(("gross_profit", True, f"{gross_profit} == {omzet} - {hpp}"))
        else:
            calc_checks.append(("gross_profit", False, f"{gross_profit} != {expected_gross} (omzet {omzet} - hpp {hpp})"))
        
        # Check: net_profit == gross_profit - opex
        expected_net = gross_profit - opex
        if abs(net_profit - expected_net) < 0.01:
            calc_checks.append(("net_profit", True, f"{net_profit} == {gross_profit} - {opex}"))
        else:
            calc_checks.append(("net_profit", False, f"{net_profit} != {expected_net} (gross {gross_profit} - opex {opex})"))
        
        # Check: kas_masuk_total == kas_dari_penjualan + bayar_piutang_masuk
        expected_kas = kas_jual + bayar_piutang
        if abs(kas_total - expected_kas) < 0.01:
            calc_checks.append(("kas_masuk_total", True, f"{kas_total} == {kas_jual} + {bayar_piutang}"))
        else:
            calc_checks.append(("kas_masuk_total", False, f"{kas_total} != {expected_kas} (kas_jual {kas_jual} + bayar_piutang {bayar_piutang})"))
        
        all_pass = True
        for field, passed, msg in calc_checks:
            if passed:
                print(f"   ✅ {field}: {msg}")
            else:
                print(f"   ❌ {field}: {msg}")
                all_pass = False
        
        if all_pass and not missing_fields:
            self.log("Test 2a: Preview Owner", "PASS", 
                    f"All fields present, calculations correct. Omzet: {omzet}, Gross: {gross_profit}, Net: {net_profit}")
        else:
            self.log("Test 2a: Preview Owner", "FAIL", "Some checks failed")
            return
        
        # TEST 2b: Preview as admin
        print("\n--- Test 2b: Preview as Admin ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}",
                          headers=self.get_headers(self.admin_token))
        
        if resp.status_code == 200:
            print(f"   ✅ Admin can access preview")
            self.log("Test 2b: Preview Admin", "PASS", "Admin can access preview")
        else:
            print(f"   ❌ Status: {resp.status_code}")
            self.log("Test 2b: Preview Admin", "FAIL", f"Status {resp.status_code}")
        
        # TEST 2c: Preview as kasir (should be 403)
        print("\n--- Test 2c: Preview as Kasir (should be 403) ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/preview?date={today}",
                          headers=self.get_headers(self.kasir_token))
        
        if resp.status_code == 403:
            print(f"   ✅ Kasir correctly rejected with 403")
            self.log("Test 2c: Preview Kasir", "PASS", "Kasir cannot access preview")
        else:
            print(f"   ❌ Status: {resp.status_code} (expected 403)")
            self.log("Test 2c: Preview Kasir", "FAIL", f"Got {resp.status_code} instead of 403")
        
        # TEST 2d: POST closing as owner (first time)
        print("\n--- Test 2d: POST Closing as Owner (version 1) ---")
        resp = requests.post(f"{BASE_URL}/daily-closing",
                           json={"date": today, "notes": "Test closing v1"},
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 2d: POST Closing v1", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        closing1 = resp.json()
        closing_id = closing1.get("id")
        version1 = closing1.get("version", 0)
        
        if version1 == 1:
            print(f"   ✅ Version: {version1}")
            print(f"   ✅ ID: {closing_id}")
            self.log("Test 2d: POST Closing v1", "PASS", f"Created with version 1, ID: {closing_id}")
        else:
            print(f"   ❌ Version: {version1} (expected 1)")
            self.log("Test 2d: POST Closing v1", "FAIL", f"Version is {version1}, expected 1")
        
        # TEST 2e: POST closing again (should increment version)
        print("\n--- Test 2e: POST Closing Again (version 2) ---")
        time.sleep(1)  # Small delay
        resp = requests.post(f"{BASE_URL}/daily-closing",
                           json={"date": today, "notes": "Test closing v2"},
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 2e: POST Closing v2", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        closing2 = resp.json()
        closing_id2 = closing2.get("id")
        version2 = closing2.get("version", 0)
        
        if closing_id2 == closing_id and version2 == 2:
            print(f"   ✅ Same ID: {closing_id2}")
            print(f"   ✅ Version incremented: {version2}")
            self.log("Test 2e: POST Closing v2", "PASS", f"Version incremented to 2, same ID (upsert)")
        else:
            print(f"   ❌ ID: {closing_id2} (expected {closing_id})")
            print(f"   ❌ Version: {version2} (expected 2)")
            self.log("Test 2e: POST Closing v2", "FAIL", "Not properly upserted")
        
        # TEST 2f: Check only one document for this date
        print("\n--- Test 2f: Check Single Document per Date ---")
        resp = requests.get(f"{BASE_URL}/daily-closing",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 2f: List Closings", "FAIL", f"Status {resp.status_code}")
            return
        
        closings = resp.json()
        today_closings = [c for c in closings if c.get("date") == today]
        
        if len(today_closings) == 1:
            print(f"   ✅ Only 1 closing for {today}")
            self.log("Test 2f: Single Document", "PASS", f"Only 1 closing for {today}")
        else:
            print(f"   ❌ Found {len(today_closings)} closings for {today}")
            self.log("Test 2f: Single Document", "FAIL", f"Found {len(today_closings)} closings")
        
        # TEST 2g: POST as admin (should be 403)
        print("\n--- Test 2g: POST as Admin (should be 403) ---")
        resp = requests.post(f"{BASE_URL}/daily-closing",
                           json={"date": today, "notes": "Admin test"},
                           headers=self.get_headers(self.admin_token))
        
        if resp.status_code == 403:
            print(f"   ✅ Admin correctly rejected with 403")
            self.log("Test 2g: POST Admin", "PASS", "Admin cannot POST closing")
        else:
            print(f"   ❌ Status: {resp.status_code} (expected 403)")
            self.log("Test 2g: POST Admin", "FAIL", f"Got {resp.status_code} instead of 403")
        
        # TEST 2h: GET by ID
        print("\n--- Test 2h: GET Closing by ID ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/{closing_id}",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code == 200:
            closing = resp.json()
            if closing.get("id") == closing_id:
                print(f"   ✅ Retrieved closing by ID: {closing_id}")
                self.log("Test 2h: GET by ID", "PASS", f"Retrieved closing {closing_id}")
            else:
                print(f"   ❌ Wrong closing returned")
                self.log("Test 2h: GET by ID", "FAIL", "Wrong closing returned")
        else:
            print(f"   ❌ Status: {resp.status_code}")
            self.log("Test 2h: GET by ID", "FAIL", f"Status {resp.status_code}")
        
        # TEST 2i: GET by date
        print("\n--- Test 2i: GET Closing by Date ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/{today}",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code == 200:
            closing = resp.json()
            if closing.get("date") == today:
                print(f"   ✅ Retrieved closing by date: {today}")
                self.log("Test 2i: GET by Date", "PASS", f"Retrieved closing for {today}")
            else:
                print(f"   ❌ Wrong closing returned")
                self.log("Test 2i: GET by Date", "FAIL", "Wrong closing returned")
        else:
            print(f"   ❌ Status: {resp.status_code}")
            self.log("Test 2i: GET by Date", "FAIL", f"Status {resp.status_code}")
        
        # TEST 2j: GET PDF
        print("\n--- Test 2j: GET Closing PDF ---")
        resp = requests.get(f"{BASE_URL}/daily-closing/{closing_id}/pdf",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code != 200:
            self.log("Test 2j: GET PDF", "FAIL", f"Status {resp.status_code}")
            return
        
        content_type = resp.headers.get("Content-Type", "")
        content_length = len(resp.content)
        is_pdf = resp.content[:4] == b'%PDF'
        
        checks = [
            ("Status", resp.status_code == 200),
            ("Content-Type", content_type == "application/pdf"),
            ("PDF header", is_pdf),
            ("Size > 2KB", content_length > 2048)
        ]
        
        all_pass = True
        for check_name, passed in checks:
            if passed:
                print(f"   ✅ {check_name}")
            else:
                print(f"   ❌ {check_name}")
                all_pass = False
        
        if all_pass:
            print(f"   📄 PDF size: {content_length} bytes")
            self.log("Test 2j: GET PDF", "PASS", f"PDF generated successfully ({content_length} bytes)")
        else:
            self.log("Test 2j: GET PDF", "FAIL", "PDF validation failed")
    
    # ==================== TEST 3: REALTIME WEBSOCKET ====================
    
    def test_realtime_websocket(self):
        """Test realtime WebSocket functionality"""
        print("\n" + "="*80)
        print("TEST 3: REALTIME WEBSOCKET")
        print("="*80)
        
        # TEST 3a: Connect with valid token
        print("\n--- Test 3a: Connect with Valid Token ---")
        ws_url = f"{WS_BASE_URL}/ws?token={self.owner_token}"
        
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            
            # Receive hello message
            msg = ws.recv()
            data = json.loads(msg)
            
            if data.get("type") == "hello":
                print(f"   ✅ Received hello message")
                print(f"   ✅ Role: {data.get('role')}")
                print(f"   ✅ Clients: {data.get('clients')}")
                self.log("Test 3a: Connect Valid Token", "PASS", 
                        f"Connected successfully, role={data.get('role')}, clients={data.get('clients')}")
            else:
                print(f"   ❌ Unexpected message type: {data.get('type')}")
                self.log("Test 3a: Connect Valid Token", "FAIL", f"Got {data.get('type')} instead of hello")
                ws.close()
                return
            
            # TEST 3b: Trigger invalidation event
            print("\n--- Test 3b: Trigger Invalidation Event ---")
            
            # Create a small sale to trigger event
            resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
            products = resp.json()
            product = next((p for p in products if p.get("stock_kg", 0) > 1), None)
            
            if not product:
                print(f"   ⚠️  No product with sufficient stock")
                self.log("Test 3b: Trigger Event", "SKIP", "No product with stock")
                ws.close()
                return
            
            # Create sale
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [{
                    "product_id": product["id"],
                    "unit": "kg",
                    "qty": 0.5,
                    "price": product.get("price_kg", 0)
                }],
                "discount": 0,
                "paid": product.get("price_kg", 0) * 0.5,
                "payment_method": "cash"
            }
            
            resp = requests.post(f"{BASE_URL}/sales",
                               json=sale_body,
                               headers=self.get_headers(self.owner_token))
            
            if resp.status_code != 200:
                print(f"   ❌ Sale creation failed: {resp.status_code}")
                self.log("Test 3b: Trigger Event", "FAIL", f"Sale failed: {resp.status_code}")
                ws.close()
                return
            
            print(f"   ✅ Sale created")
            
            # Wait for invalidation message (max 10 seconds)
            received_invalidate = False
            topics_received = []
            
            ws.settimeout(10)
            try:
                for _ in range(20):  # Try up to 20 messages
                    msg = ws.recv()
                    data = json.loads(msg)
                    
                    if data.get("type") == "invalidate":
                        received_invalidate = True
                        topics_received = data.get("topics", [])
                        print(f"   ✅ Received invalidate message")
                        print(f"   ✅ Topics: {topics_received}")
                        break
                    elif data.get("type") in ["ping", "pong"]:
                        # Heartbeat, continue
                        continue
            except websocket.WebSocketTimeoutException:
                pass
            
            if received_invalidate:
                # Check if topics contain at least one of: dashboard, stock, sales
                expected_topics = ["dashboard", "stock", "sales"]
                has_expected = any(t in topics_received for t in expected_topics)
                
                if has_expected:
                    print(f"   ✅ Topics contain expected values")
                    self.log("Test 3b: Trigger Event", "PASS", 
                            f"Received invalidate with topics: {topics_received}")
                else:
                    print(f"   ❌ Topics don't contain expected values")
                    self.log("Test 3b: Trigger Event", "FAIL", 
                            f"Topics {topics_received} don't contain dashboard/stock/sales")
            else:
                print(f"   ❌ No invalidate message received within 10 seconds")
                self.log("Test 3b: Trigger Event", "FAIL", "No invalidate message received")
            
            ws.close()
            
        except Exception as e:
            print(f"   ❌ WebSocket error: {e}")
            self.log("Test 3a: Connect Valid Token", "FAIL", f"Error: {e}")
            return
        
        # TEST 3c: Connect with invalid token
        print("\n--- Test 3c: Connect with Invalid Token ---")
        ws_url_bad = f"{WS_BASE_URL}/ws?token=invalid_token_12345"
        
        try:
            ws = websocket.create_connection(ws_url_bad, timeout=5)
            # If we get here, connection was accepted (should not happen)
            ws.close()
            print(f"   ❌ Connection accepted with invalid token")
            self.log("Test 3c: Invalid Token", "FAIL", "Connection accepted")
        except websocket.WebSocketBadStatusException as e:
            if "403" in str(e):
                print(f"   ✅ Connection rejected with 403")
                self.log("Test 3c: Invalid Token", "PASS", "Connection rejected with 403")
            else:
                print(f"   ⚠️  Connection rejected but not 403: {e}")
                self.log("Test 3c: Invalid Token", "PARTIAL", f"Rejected but: {e}")
        except Exception as e:
            # WebSocket might close with code 1008
            if "1008" in str(e) or "403" in str(e):
                print(f"   ✅ Connection rejected (close code 1008 or 403)")
                self.log("Test 3c: Invalid Token", "PASS", "Connection rejected")
            else:
                print(f"   ⚠️  Unexpected error: {e}")
                self.log("Test 3c: Invalid Token", "PARTIAL", f"Error: {e}")
        
        # TEST 3d: Realtime status
        print("\n--- Test 3d: Realtime Status ---")
        resp = requests.get(f"{BASE_URL}/realtime/status",
                          headers=self.get_headers(self.owner_token))
        
        if resp.status_code == 200:
            status = resp.json()
            clients = status.get("clients")
            if isinstance(clients, int) and clients >= 0:
                print(f"   ✅ Status endpoint working")
                print(f"   ✅ Clients: {clients}")
                self.log("Test 3d: Realtime Status", "PASS", f"Clients: {clients}")
            else:
                print(f"   ❌ Invalid clients value: {clients}")
                self.log("Test 3d: Realtime Status", "FAIL", f"Invalid clients: {clients}")
        else:
            print(f"   ❌ Status: {resp.status_code}")
            self.log("Test 3d: Realtime Status", "FAIL", f"Status {resp.status_code}")
        
        # TEST 3e: Sale without WebSocket (should still work)
        print("\n--- Test 3e: Sale Without WebSocket (best-effort) ---")
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        product = next((p for p in products if p.get("stock_kg", 0) > 1), None)
        
        if not product:
            print(f"   ⚠️  No product with sufficient stock")
            self.log("Test 3e: Sale Without WS", "SKIP", "No product with stock")
            return
        
        sale_body = {
            "txn_id": str(uuid.uuid4()),
            "items": [{
                "product_id": product["id"],
                "unit": "kg",
                "qty": 0.3,
                "price": product.get("price_kg", 0)
            }],
            "discount": 0,
            "paid": product.get("price_kg", 0) * 0.3,
            "payment_method": "cash"
        }
        
        resp = requests.post(f"{BASE_URL}/sales",
                           json=sale_body,
                           headers=self.get_headers(self.owner_token))
        
        if resp.status_code == 200:
            print(f"   ✅ Sale succeeded without WebSocket")
            self.log("Test 3e: Sale Without WS", "PASS", "Sale succeeded (broadcast is best-effort)")
        else:
            print(f"   ❌ Sale failed: {resp.status_code}")
            self.log("Test 3e: Sale Without WS", "FAIL", f"Status {resp.status_code}")
    
    # ==================== TEST 4: REGRESSION ====================
    
    def test_regression(self):
        """Test regression - ensure existing features still work"""
        print("\n" + "="*80)
        print("TEST 4: REGRESSION TESTS")
        print("="*80)
        
        # TEST 4a: Login all roles
        print("\n--- Test 4a: Login All Roles ---")
        roles_ok = self.owner_token and self.admin_token and self.kasir_token
        if roles_ok:
            print(f"   ✅ All roles can login")
            self.log("Test 4a: Login Roles", "PASS", "Owner, Admin, Kasir all logged in")
        else:
            print(f"   ❌ Some roles failed to login")
            self.log("Test 4a: Login Roles", "FAIL", "Login failed for some roles")
        
        # TEST 4b: GET endpoints
        print("\n--- Test 4b: GET Endpoints ---")
        endpoints = [
            "/products",
            "/dashboard",
            "/reports/profit-loss",
            "/reports/sales",
            "/reports/stock"
        ]
        
        all_ok = True
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}",
                              headers=self.get_headers(self.owner_token))
            if resp.status_code == 200:
                print(f"   ✅ {endpoint}: 200")
            else:
                print(f"   ❌ {endpoint}: {resp.status_code}")
                all_ok = False
        
        if all_ok:
            self.log("Test 4b: GET Endpoints", "PASS", "All endpoints return 200")
        else:
            self.log("Test 4b: GET Endpoints", "FAIL", "Some endpoints failed")
        
        # TEST 4c: PDF endpoints
        print("\n--- Test 4c: PDF Endpoints ---")
        pdf_endpoints = [
            "/reports/profit-loss/pdf",
            "/reports/sales/pdf",
            "/reports/stock/pdf"
        ]
        
        all_ok = True
        for endpoint in pdf_endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}",
                              headers=self.get_headers(self.owner_token))
            is_pdf = resp.status_code == 200 and resp.content[:4] == b'%PDF'
            if is_pdf:
                print(f"   ✅ {endpoint}: PDF ({len(resp.content)} bytes)")
            else:
                print(f"   ❌ {endpoint}: {resp.status_code}")
                all_ok = False
        
        if all_ok:
            self.log("Test 4c: PDF Endpoints", "PASS", "All PDF endpoints working")
        else:
            self.log("Test 4c: PDF Endpoints", "FAIL", "Some PDF endpoints failed")
        
        # TEST 4d: Sale per kg/ekor/pcs
        print("\n--- Test 4d: Sale per kg/ekor/pcs ---")
        resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
        products = resp.json()
        
        # Find products for each unit
        product_kg = next((p for p in products if "kg" in p.get("units", []) and p.get("stock_kg", 0) > 1), None)
        product_ekor = next((p for p in products if "ekor" in p.get("units", []) and p.get("stock_ekor", 0) > 1), None)
        product_pcs = next((p for p in products if "pcs" in p.get("units", []) and p.get("stock_pcs", 0) > 1), None)
        
        units_tested = []
        
        if product_kg:
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [{
                    "product_id": product_kg["id"],
                    "unit": "kg",
                    "qty": 0.5,
                    "price": product_kg.get("price_kg", 0)
                }],
                "discount": 0,
                "paid": product_kg.get("price_kg", 0) * 0.5,
                "payment_method": "cash"
            }
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code == 200:
                sale = resp.json()
                # Check HPP calculation
                item = sale.get("items", [])[0] if sale.get("items") else {}
                hpp_total = item.get("hpp_total", 0)
                expected_hpp = product_kg.get("hpp_kg", 0) * 0.5
                if abs(hpp_total - expected_hpp) < 0.01:
                    print(f"   ✅ Sale per kg: HPP correct ({hpp_total})")
                    units_tested.append("kg")
                else:
                    print(f"   ❌ Sale per kg: HPP wrong ({hpp_total} vs {expected_hpp})")
            else:
                print(f"   ❌ Sale per kg failed: {resp.status_code}")
        
        if product_ekor:
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [{
                    "product_id": product_ekor["id"],
                    "unit": "ekor",
                    "qty": 1,
                    "price": product_ekor.get("price_ekor", 0)
                }],
                "discount": 0,
                "paid": product_ekor.get("price_ekor", 0),
                "payment_method": "cash"
            }
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code == 200:
                sale = resp.json()
                item = sale.get("items", [])[0] if sale.get("items") else {}
                hpp_total = item.get("hpp_total", 0)
                expected_hpp = product_ekor.get("hpp_ekor", 0)
                if abs(hpp_total - expected_hpp) < 0.01:
                    print(f"   ✅ Sale per ekor: HPP correct ({hpp_total})")
                    units_tested.append("ekor")
                else:
                    print(f"   ❌ Sale per ekor: HPP wrong ({hpp_total} vs {expected_hpp})")
            else:
                print(f"   ❌ Sale per ekor failed: {resp.status_code}")
        
        if product_pcs:
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [{
                    "product_id": product_pcs["id"],
                    "unit": "pcs",
                    "qty": 2,
                    "price": product_pcs.get("price_pcs", 0)
                }],
                "discount": 0,
                "paid": product_pcs.get("price_pcs", 0) * 2,
                "payment_method": "cash"
            }
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code == 200:
                sale = resp.json()
                item = sale.get("items", [])[0] if sale.get("items") else {}
                hpp_total = item.get("hpp_total", 0)
                expected_hpp = product_pcs.get("hpp_pcs", 0) * 2
                if abs(hpp_total - expected_hpp) < 0.01:
                    print(f"   ✅ Sale per pcs: HPP correct ({hpp_total})")
                    units_tested.append("pcs")
                else:
                    print(f"   ❌ Sale per pcs: HPP wrong ({hpp_total} vs {expected_hpp})")
            else:
                print(f"   ❌ Sale per pcs failed: {resp.status_code}")
        
        if len(units_tested) >= 2:
            self.log("Test 4d: Sale Units", "PASS", f"Tested units: {units_tested}")
        else:
            self.log("Test 4d: Sale Units", "PARTIAL", f"Only tested: {units_tested}")
        
        # TEST 4e: Idempotency
        print("\n--- Test 4e: Idempotency ---")
        if not product_kg:
            print(f"   ⚠️  No product for idempotency test")
            self.log("Test 4e: Idempotency", "SKIP", "No product available")
        else:
            txn_id = str(uuid.uuid4())
            sale_body = {
                "txn_id": txn_id,
                "items": [{
                    "product_id": product_kg["id"],
                    "unit": "kg",
                    "qty": 0.3,
                    "price": product_kg.get("price_kg", 0)
                }],
                "discount": 0,
                "paid": product_kg.get("price_kg", 0) * 0.3,
                "payment_method": "cash"
            }
            
            # First POST
            resp1 = requests.post(f"{BASE_URL}/sales", json=sale_body,
                                headers=self.get_headers(self.owner_token))
            if resp1.status_code != 200:
                print(f"   ❌ First sale failed: {resp1.status_code}")
                self.log("Test 4e: Idempotency", "FAIL", "First sale failed")
            else:
                sale1 = resp1.json()
                sale_id1 = sale1.get("id")
                
                # Get stock after first sale
                resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
                products_after1 = resp.json()
                product_after1 = next((p for p in products_after1 if p["id"] == product_kg["id"]), None)
                stock_after1 = product_after1.get("stock_kg", 0)
                
                # Second POST with same txn_id
                resp2 = requests.post(f"{BASE_URL}/sales", json=sale_body,
                                    headers=self.get_headers(self.owner_token))
                if resp2.status_code != 200:
                    print(f"   ❌ Second sale failed: {resp2.status_code}")
                    self.log("Test 4e: Idempotency", "FAIL", "Second sale failed")
                else:
                    sale2 = resp2.json()
                    sale_id2 = sale2.get("id")
                    
                    # Get stock after second sale
                    resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
                    products_after2 = resp.json()
                    product_after2 = next((p for p in products_after2 if p["id"] == product_kg["id"]), None)
                    stock_after2 = product_after2.get("stock_kg", 0)
                    
                    if sale_id1 == sale_id2 and stock_after1 == stock_after2:
                        print(f"   ✅ Same sale ID: {sale_id1}")
                        print(f"   ✅ Stock unchanged: {stock_after1}")
                        self.log("Test 4e: Idempotency", "PASS", "Idempotency working correctly")
                    else:
                        print(f"   ❌ Sale ID: {sale_id1} vs {sale_id2}")
                        print(f"   ❌ Stock: {stock_after1} vs {stock_after2}")
                        self.log("Test 4e: Idempotency", "FAIL", "Duplicate detected")
        
        # TEST 4f: Offline sale
        print("\n--- Test 4f: Offline Sale ---")
        if not product_kg:
            print(f"   ⚠️  No product for offline test")
            self.log("Test 4f: Offline Sale", "SKIP", "No product available")
        else:
            offline_date = "2026-08-27"
            offline_at = "2026-08-27T21:15:00+07:00"
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "date": offline_date,
                "offline_at": offline_at,
                "items": [{
                    "product_id": product_kg["id"],
                    "unit": "kg",
                    "qty": 0.2,
                    "price": product_kg.get("price_kg", 0)
                }],
                "discount": 0,
                "paid": product_kg.get("price_kg", 0) * 0.2,
                "payment_method": "cash"
            }
            
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code == 200:
                sale = resp.json()
                if sale.get("offline") == True and sale.get("created_at") == offline_at:
                    print(f"   ✅ Offline sale created")
                    print(f"   ✅ created_at: {sale.get('created_at')}")
                    print(f"   ✅ offline: {sale.get('offline')}")
                    self.log("Test 4f: Offline Sale", "PASS", "Offline sale working")
                else:
                    print(f"   ❌ Offline fields incorrect")
                    self.log("Test 4f: Offline Sale", "FAIL", "Offline fields wrong")
            else:
                print(f"   ❌ Offline sale failed: {resp.status_code}")
                self.log("Test 4f: Offline Sale", "FAIL", f"Status {resp.status_code}")
        
        # TEST 4g: Cancel sale (stock restoration)
        print("\n--- Test 4g: Cancel Sale (stock restoration) ---")
        # Create a sale with multiple units
        product_for_cancel = None
        for p in products:
            if ("kg" in p.get("units", []) and p.get("stock_kg", 0) > 1 and
                "pcs" in p.get("units", []) and p.get("stock_pcs", 0) > 2):
                product_for_cancel = p
                break
        
        if not product_for_cancel:
            print(f"   ⚠️  No product with kg and pcs stock")
            self.log("Test 4g: Cancel Sale", "SKIP", "No suitable product")
        else:
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [
                    {
                        "product_id": product_for_cancel["id"],
                        "unit": "kg",
                        "qty": 0.5,
                        "price": product_for_cancel.get("price_kg", 0)
                    },
                    {
                        "product_id": product_for_cancel["id"],
                        "unit": "pcs",
                        "qty": 2,
                        "price": product_for_cancel.get("price_pcs", 0)
                    }
                ],
                "discount": 0,
                "paid": product_for_cancel.get("price_kg", 0) * 0.5 + product_for_cancel.get("price_pcs", 0) * 2,
                "payment_method": "cash"
            }
            
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code != 200:
                print(f"   ❌ Sale creation failed: {resp.status_code}")
                self.log("Test 4g: Cancel Sale", "FAIL", "Sale creation failed")
            else:
                sale = resp.json()
                sale_id = sale.get("id")
                
                # Get stock before cancel
                resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
                products_before = resp.json()
                product_before = next((p for p in products_before if p["id"] == product_for_cancel["id"]), None)
                stock_kg_before = product_before.get("stock_kg", 0)
                stock_pcs_before = product_before.get("stock_pcs", 0)
                
                # Cancel sale
                resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel",
                                   headers=self.get_headers(self.owner_token))
                if resp.status_code != 200:
                    print(f"   ❌ Cancel failed: {resp.status_code}")
                    self.log("Test 4g: Cancel Sale", "FAIL", f"Cancel failed: {resp.status_code}")
                else:
                    # Get stock after cancel
                    resp = requests.get(f"{BASE_URL}/products", headers=self.get_headers(self.owner_token))
                    products_after = resp.json()
                    product_after = next((p for p in products_after if p["id"] == product_for_cancel["id"]), None)
                    stock_kg_after = product_after.get("stock_kg", 0)
                    stock_pcs_after = product_after.get("stock_pcs", 0)
                    
                    # Check restoration
                    kg_restored = abs((stock_kg_after - stock_kg_before) - 0.5) < 0.01
                    pcs_restored = abs((stock_pcs_after - stock_pcs_before) - 2) < 0.01
                    
                    if kg_restored and pcs_restored:
                        print(f"   ✅ kg restored: {stock_kg_before} → {stock_kg_after}")
                        print(f"   ✅ pcs restored: {stock_pcs_before} → {stock_pcs_after}")
                        self.log("Test 4g: Cancel Sale", "PASS", "Stock restored correctly")
                    else:
                        print(f"   ❌ kg: {stock_kg_before} → {stock_kg_after}")
                        print(f"   ❌ pcs: {stock_pcs_before} → {stock_pcs_after}")
                        self.log("Test 4g: Cancel Sale", "FAIL", "Stock not restored correctly")
        
        # TEST 4h: Insufficient stock
        print("\n--- Test 4h: Insufficient Stock (should be 400) ---")
        if not product_kg:
            print(f"   ⚠️  No product for stock test")
            self.log("Test 4h: Insufficient Stock", "SKIP", "No product available")
        else:
            sale_body = {
                "txn_id": str(uuid.uuid4()),
                "items": [{
                    "product_id": product_kg["id"],
                    "unit": "kg",
                    "qty": 999999,  # Impossible amount
                    "price": product_kg.get("price_kg", 0)
                }],
                "discount": 0,
                "paid": product_kg.get("price_kg", 0) * 999999,
                "payment_method": "cash"
            }
            
            resp = requests.post(f"{BASE_URL}/sales", json=sale_body,
                               headers=self.get_headers(self.owner_token))
            if resp.status_code == 400:
                print(f"   ✅ Correctly rejected with 400")
                self.log("Test 4h: Insufficient Stock", "PASS", "Stock control working")
            else:
                print(f"   ❌ Status: {resp.status_code} (expected 400)")
                self.log("Test 4h: Insufficient Stock", "FAIL", f"Got {resp.status_code} instead of 400")
    
    # ==================== MAIN ====================
    
    def run_all_tests(self):
        """Run all test suites"""
        print("\n" + "="*80)
        print("BERKAH AYAM MILI - BACKEND TESTING FASE 3")
        print("="*80)
        print(f"Base URL: {BASE_URL}")
        print(f"WebSocket URL: {WS_BASE_URL}")
        print(f"Time: {datetime.now(JKT_TZ).isoformat()}")
        
        # Setup
        if not self.setup_auth():
            print("\n❌ Authentication setup failed. Aborting tests.")
            return
        
        if not self.load_products():
            print("\n❌ Failed to load products. Aborting tests.")
            return
        
        # Run test suites
        try:
            self.test_hpp_per_ekor()
        except Exception as e:
            print(f"\n❌ HPP test suite failed with exception: {e}")
            self.log("HPP Test Suite", "FAIL", f"Exception: {e}")
        
        try:
            self.test_tutup_buku()
        except Exception as e:
            print(f"\n❌ Tutup Buku test suite failed with exception: {e}")
            self.log("Tutup Buku Test Suite", "FAIL", f"Exception: {e}")
        
        try:
            self.test_realtime_websocket()
        except Exception as e:
            print(f"\n❌ WebSocket test suite failed with exception: {e}")
            self.log("WebSocket Test Suite", "FAIL", f"Exception: {e}")
        
        try:
            self.test_regression()
        except Exception as e:
            print(f"\n❌ Regression test suite failed with exception: {e}")
            self.log("Regression Test Suite", "FAIL", f"Exception: {e}")
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.test_results if r["status"] in ["SKIP", "PARTIAL"])
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Skipped/Partial: {skipped}")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.test_results:
                if r["status"] == "FAIL":
                    print(f"  - {r['test']}: {r['details']}")
        
        print("\n" + "="*80)
        if failed == 0:
            print("✅ ALL TESTS PASSED")
        else:
            print(f"❌ {failed} TEST(S) FAILED")
        print("="*80)

if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests()
