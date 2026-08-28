#!/usr/bin/env python3
"""
Backend Testing for Berkah Ayam Mili - FASE 1 (Mode Offline POS)
Tests POST /api/sales with offline_at field and idempotency
"""
import requests
import json
import uuid
from datetime import datetime, timezone, timedelta

# Configuration
BASE_URL = "https://project-web-viewer.preview.emergentagent.com/api"
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"

# Jakarta timezone
JKT_TZ = timezone(timedelta(hours=7))

class TestRunner:
    def __init__(self):
        self.token = None
        self.headers = {}
        self.test_results = []
        self.products = []
        self.customers = []
        
    def log(self, test_name, status, details=""):
        result = {"test": test_name, "status": status, "details": details}
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"\n{status_icon} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def login(self):
        """Login as owner and get token"""
        print("\n" + "="*80)
        print("LOGGING IN AS OWNER")
        print("="*80)
        
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": OWNER_EMAIL,
            "password": OWNER_PASSWORD
        })
        
        if resp.status_code != 200:
            self.log("Login", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        self.token = data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.log("Login", "PASS", f"Token obtained for {OWNER_EMAIL}")
        return True
    
    def get_products(self):
        """Get list of products"""
        resp = requests.get(f"{BASE_URL}/products", headers=self.headers)
        if resp.status_code == 200:
            self.products = resp.json()
            return True
        return False
    
    def get_customers(self):
        """Get list of customers"""
        resp = requests.get(f"{BASE_URL}/customers", headers=self.headers)
        if resp.status_code == 200:
            self.customers = resp.json()
            return True
        return False
    
    def find_product_with_unit(self, unit_keyword, min_stock=5.0):
        """Find a product that has the specified unit and sufficient stock"""
        for p in self.products:
            units = p.get("units", [])
            if any(unit_keyword in u for u in units):
                # Check stock based on unit
                if unit_keyword == "kg" and p.get("stock_kg", 0) >= min_stock:
                    return p
                elif unit_keyword == "ekor" and p.get("stock_ekor", 0) >= min_stock:
                    return p
                elif unit_keyword == "pcs" and p.get("stock_pcs", 0) >= min_stock:
                    return p
        return None
    
    def get_product_stock(self, product_id):
        """Get current stock of a product"""
        for p in self.products:
            if p["id"] == product_id:
                return {
                    "stock_kg": p.get("stock_kg", 0),
                    "stock_ekor": p.get("stock_ekor", 0),
                    "stock_pcs": p.get("stock_pcs", 0)
                }
        return None
    
    def refresh_products(self):
        """Refresh product list"""
        return self.get_products()
    
    def test_normal_sale(self):
        """Test 1: Normal sale without offline_at (regression test)"""
        print("\n" + "="*80)
        print("TEST 1: NORMAL SALE (REGRESSION)")
        print("="*80)
        
        # Find a product with kg unit and sufficient stock
        product = self.find_product_with_unit("kg", min_stock=10.0)
        if not product:
            self.log("Normal Sale - Find Product", "FAIL", "No product with 'kg' unit found")
            return
        
        product_id = product["id"]
        product_name = product["name"]
        price_kg = product.get("price_kg", 0)
        
        # Get stock before
        stock_before = self.get_product_stock(product_id)
        print(f"Product: {product_name}")
        print(f"Stock before: {stock_before['stock_kg']} kg")
        
        # Create sale
        txn_id = f"test-normal-{uuid.uuid4().hex[:8]}"
        sale_payload = {
            "txn_id": txn_id,
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 1.5,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": 0,
            "payment_method": "cash"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        
        if resp.status_code != 200:
            self.log("Normal Sale - Create", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        sale = resp.json()
        sale_id = sale["id"]
        
        # Verify response fields
        today = datetime.now(JKT_TZ).strftime("%Y-%m-%d")
        
        checks = []
        checks.append(("offline == False", sale.get("offline") == False))
        checks.append(("synced_at == None", sale.get("synced_at") is None))
        checks.append(("date == today", sale.get("date") == today))
        checks.append(("created_at is today", sale.get("created_at", "").startswith(today)))
        
        all_pass = all(check[1] for check in checks)
        details = ", ".join([f"{check[0]}: {check[1]}" for check in checks])
        
        if not all_pass:
            self.log("Normal Sale - Response Fields", "FAIL", details)
            return
        
        self.log("Normal Sale - Response Fields", "PASS", details)
        
        # Verify stock decreased
        self.refresh_products()
        stock_after = self.get_product_stock(product_id)
        expected_stock = round(stock_before["stock_kg"] - 1.5, 3)
        actual_stock = stock_after["stock_kg"]
        
        if abs(actual_stock - expected_stock) > 0.001:
            self.log("Normal Sale - Stock Decrease", "FAIL", 
                    f"Expected {expected_stock} kg, got {actual_stock} kg")
            return
        
        self.log("Normal Sale - Stock Decrease", "PASS", 
                f"Stock decreased from {stock_before['stock_kg']} to {actual_stock} kg")
        
        # Verify income created
        resp = requests.get(f"{BASE_URL}/incomes", headers=self.headers)
        if resp.status_code == 200:
            incomes = resp.json()
            income_found = any(inc.get("ref") == sale_id for inc in incomes)
            if income_found:
                self.log("Normal Sale - Income Created", "PASS", f"Income entry found for sale {sale_id[:8]}")
            else:
                self.log("Normal Sale - Income Created", "FAIL", f"No income entry for sale {sale_id[:8]}")
        else:
            self.log("Normal Sale - Income Created", "FAIL", f"Could not fetch incomes: {resp.status_code}")
    
    def test_offline_sale(self):
        """Test 2: Offline sale with offline_at and date"""
        print("\n" + "="*80)
        print("TEST 2: OFFLINE SALE")
        print("="*80)
        
        # Find a product with kg unit and sufficient stock
        product = self.find_product_with_unit("kg", min_stock=10.0)
        if not product:
            self.log("Offline Sale - Find Product", "FAIL", "No product with 'kg' unit found")
            return
        
        product_id = product["id"]
        product_name = product["name"]
        price_kg = product.get("price_kg", 0)
        
        print(f"Product: {product_name}")
        
        # Create offline sale with specific date
        offline_date = "2026-08-27"
        offline_at = "2026-08-27T21:15:00+07:00"
        txn_id = f"test-offline-{uuid.uuid4().hex[:8]}"
        
        sale_payload = {
            "txn_id": txn_id,
            "date": offline_date,
            "offline_at": offline_at,
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 2.0,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": 0,
            "payment_method": "cash"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        
        if resp.status_code != 200:
            self.log("Offline Sale - Create", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return
        
        sale = resp.json()
        sale_id = sale["id"]
        
        # Verify response fields
        checks = []
        checks.append(("created_at == offline_at", sale.get("created_at") == offline_at))
        checks.append(("offline == True", sale.get("offline") == True))
        checks.append(("synced_at is not None", sale.get("synced_at") is not None))
        checks.append(("date == 2026-08-27", sale.get("date") == offline_date))
        
        all_pass = all(check[1] for check in checks)
        details = ", ".join([f"{check[0]}: {check[1]}" for check in checks])
        
        if not all_pass:
            self.log("Offline Sale - Response Fields", "FAIL", details)
            print(f"   Full response: {json.dumps(sale, indent=2)}")
            return
        
        self.log("Offline Sale - Response Fields", "PASS", details)
        
        # Verify sale appears in correct date filter
        resp = requests.get(f"{BASE_URL}/sales?date={offline_date}", headers=self.headers)
        if resp.status_code == 200:
            sales = resp.json()
            found_in_offline_date = any(s["id"] == sale_id for s in sales)
            if found_in_offline_date:
                self.log("Offline Sale - Date Filter (offline date)", "PASS", 
                        f"Sale found in GET /api/sales?date={offline_date}")
            else:
                self.log("Offline Sale - Date Filter (offline date)", "FAIL", 
                        f"Sale NOT found in GET /api/sales?date={offline_date}")
        
        # Verify sale does NOT appear in today's date
        today = datetime.now(JKT_TZ).strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/sales?date={today}", headers=self.headers)
        if resp.status_code == 200:
            sales = resp.json()
            found_in_today = any(s["id"] == sale_id for s in sales)
            if not found_in_today:
                self.log("Offline Sale - Date Filter (today)", "PASS", 
                        f"Sale correctly NOT in GET /api/sales?date={today}")
            else:
                self.log("Offline Sale - Date Filter (today)", "FAIL", 
                        f"Sale incorrectly found in GET /api/sales?date={today}")
        
        # Verify activity title
        resp = requests.get(f"{BASE_URL}/activities", headers=self.headers)
        if resp.status_code == 200:
            activities = resp.json()
            offline_activity = None
            for act in activities:
                if "Penjualan Offline Tersinkron" in act.get("title", ""):
                    offline_activity = act
                    break
            
            if offline_activity:
                self.log("Offline Sale - Activity Title", "PASS", 
                        "Activity 'Penjualan Offline Tersinkron' found")
            else:
                self.log("Offline Sale - Activity Title", "FAIL", 
                        "Activity 'Penjualan Offline Tersinkron' NOT found")
        else:
            self.log("Offline Sale - Activity Title", "FAIL", 
                    f"Could not fetch activities: {resp.status_code}")
    
    def test_idempotency_cash(self):
        """Test 3a: Idempotency - same txn_id twice (cash payment)"""
        print("\n" + "="*80)
        print("TEST 3a: IDEMPOTENCY (CASH PAYMENT)")
        print("="*80)
        
        # Refresh products to get latest stock
        self.refresh_products()
        
        # Find a product with kg unit and sufficient stock
        product = self.find_product_with_unit("kg", min_stock=10.0)
        if not product:
            self.log("Idempotency Cash - Find Product", "FAIL", "No product with 'kg' unit found")
            return
        
        product_id = product["id"]
        product_name = product["name"]
        price_kg = product.get("price_kg", 0)
        
        # Get stock before
        stock_before = self.get_product_stock(product_id)
        print(f"Product: {product_name}")
        print(f"Stock before: {stock_before['stock_kg']} kg")
        
        # Create sale with specific txn_id
        txn_id = f"test-idem-cash-{uuid.uuid4().hex[:8]}"
        sale_payload = {
            "txn_id": txn_id,
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 1.0,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": 0,
            "payment_method": "cash"
        }
        
        # First POST
        resp1 = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp1.status_code != 200:
            self.log("Idempotency Cash - First POST", "FAIL", 
                    f"Status {resp1.status_code}: {resp1.text}")
            return
        
        sale1 = resp1.json()
        sale_id_1 = sale1["id"]
        print(f"First POST: sale_id = {sale_id_1}")
        
        # Second POST (identical payload)
        resp2 = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp2.status_code != 200:
            self.log("Idempotency Cash - Second POST", "FAIL", 
                    f"Status {resp2.status_code}: {resp2.text}")
            return
        
        sale2 = resp2.json()
        sale_id_2 = sale2["id"]
        print(f"Second POST: sale_id = {sale_id_2}")
        
        # Verify same ID returned
        if sale_id_1 == sale_id_2:
            self.log("Idempotency Cash - Same ID", "PASS", 
                    f"Both POSTs returned same ID: {sale_id_1[:8]}")
        else:
            self.log("Idempotency Cash - Same ID", "FAIL", 
                    f"Different IDs: {sale_id_1[:8]} vs {sale_id_2[:8]}")
            return
        
        # Verify stock decreased only once
        self.refresh_products()
        stock_after = self.get_product_stock(product_id)
        expected_stock = round(stock_before["stock_kg"] - 1.0, 3)
        actual_stock = stock_after["stock_kg"]
        
        if abs(actual_stock - expected_stock) > 0.001:
            self.log("Idempotency Cash - Stock Once", "FAIL", 
                    f"Stock: before={stock_before['stock_kg']}, expected={expected_stock}, actual={actual_stock}")
            return
        
        self.log("Idempotency Cash - Stock Once", "PASS", 
                f"Stock decreased only once: {stock_before['stock_kg']} → {actual_stock} kg")
        
        # Verify income count
        resp = requests.get(f"{BASE_URL}/incomes", headers=self.headers)
        if resp.status_code == 200:
            incomes = resp.json()
            income_count = sum(1 for inc in incomes if inc.get("ref") == sale_id_1)
            if income_count == 1:
                self.log("Idempotency Cash - Income Count", "PASS", 
                        f"Exactly 1 income entry for sale {sale_id_1[:8]}")
            else:
                self.log("Idempotency Cash - Income Count", "FAIL", 
                        f"Found {income_count} income entries (expected 1)")
        else:
            self.log("Idempotency Cash - Income Count", "FAIL", 
                    f"Could not fetch incomes: {resp.status_code}")
    
    def test_idempotency_piutang(self):
        """Test 3b: Idempotency - same txn_id twice (piutang payment)"""
        print("\n" + "="*80)
        print("TEST 3b: IDEMPOTENCY (PIUTANG PAYMENT)")
        print("="*80)
        
        # Refresh products to get latest stock
        self.refresh_products()
        
        # Find a product and customer
        product = self.find_product_with_unit("kg", min_stock=10.0)
        if not product:
            self.log("Idempotency Piutang - Find Product", "FAIL", "No product with 'kg' unit found")
            return
        
        if not self.customers:
            self.log("Idempotency Piutang - Find Customer", "FAIL", "No customers found")
            return
        
        customer = self.customers[0]
        customer_id = customer["id"]
        customer_name = customer["name"]
        
        product_id = product["id"]
        product_name = product["name"]
        price_kg = product.get("price_kg", 0)
        
        # Get stock and customer receivable before
        stock_before = self.get_product_stock(product_id)
        
        # Refresh customer data
        resp = requests.get(f"{BASE_URL}/customers", headers=self.headers)
        customers = resp.json()
        customer_before = next((c for c in customers if c["id"] == customer_id), None)
        receivable_before = customer_before.get("receivable", 0) if customer_before else 0
        
        print(f"Product: {product_name}")
        print(f"Customer: {customer_name}")
        print(f"Stock before: {stock_before['stock_kg']} kg")
        print(f"Customer receivable before: Rp {receivable_before:,.0f}")
        
        # Create sale with piutang
        txn_id = f"test-idem-piutang-{uuid.uuid4().hex[:8]}"
        total_price = price_kg * 2.0
        sale_payload = {
            "txn_id": txn_id,
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 2.0,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": total_price * 0.5,  # Pay 50%
            "payment_method": "piutang"
        }
        
        # First POST
        resp1 = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp1.status_code != 200:
            self.log("Idempotency Piutang - First POST", "FAIL", 
                    f"Status {resp1.status_code}: {resp1.text}")
            return
        
        sale1 = resp1.json()
        sale_id_1 = sale1["id"]
        print(f"First POST: sale_id = {sale_id_1}")
        
        # Second POST (identical payload)
        resp2 = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp2.status_code != 200:
            self.log("Idempotency Piutang - Second POST", "FAIL", 
                    f"Status {resp2.status_code}: {resp2.text}")
            return
        
        sale2 = resp2.json()
        sale_id_2 = sale2["id"]
        print(f"Second POST: sale_id = {sale_id_2}")
        
        # Verify same ID returned
        if sale_id_1 == sale_id_2:
            self.log("Idempotency Piutang - Same ID", "PASS", 
                    f"Both POSTs returned same ID: {sale_id_1[:8]}")
        else:
            self.log("Idempotency Piutang - Same ID", "FAIL", 
                    f"Different IDs: {sale_id_1[:8]} vs {sale_id_2[:8]}")
            return
        
        # Verify stock decreased only once
        self.refresh_products()
        stock_after = self.get_product_stock(product_id)
        expected_stock = round(stock_before["stock_kg"] - 2.0, 3)
        actual_stock = stock_after["stock_kg"]
        
        if abs(actual_stock - expected_stock) > 0.001:
            self.log("Idempotency Piutang - Stock Once", "FAIL", 
                    f"Stock: before={stock_before['stock_kg']}, expected={expected_stock}, actual={actual_stock}")
            return
        
        self.log("Idempotency Piutang - Stock Once", "PASS", 
                f"Stock decreased only once: {stock_before['stock_kg']} → {actual_stock} kg")
        
        # Verify receivable count
        resp = requests.get(f"{BASE_URL}/receivables", headers=self.headers)
        if resp.status_code == 200:
            receivables = resp.json()
            receivable_count = sum(1 for r in receivables if r.get("sale_id") == sale_id_1)
            if receivable_count == 1:
                self.log("Idempotency Piutang - Receivable Count", "PASS", 
                        f"Exactly 1 receivable entry for sale {sale_id_1[:8]}")
            else:
                self.log("Idempotency Piutang - Receivable Count", "FAIL", 
                        f"Found {receivable_count} receivable entries (expected 1)")
        else:
            self.log("Idempotency Piutang - Receivable Count", "FAIL", 
                    f"Could not fetch receivables: {resp.status_code}")
        
        # Verify customer receivable not doubled
        resp = requests.get(f"{BASE_URL}/customers", headers=self.headers)
        customers = resp.json()
        customer_after = next((c for c in customers if c["id"] == customer_id), None)
        receivable_after = customer_after.get("receivable", 0) if customer_after else 0
        
        expected_receivable = receivable_before + (total_price * 0.5)
        
        if abs(receivable_after - expected_receivable) < 0.01:
            self.log("Idempotency Piutang - Customer Receivable", "PASS", 
                    f"Customer receivable increased once: {receivable_before:,.0f} → {receivable_after:,.0f}")
        else:
            self.log("Idempotency Piutang - Customer Receivable", "FAIL", 
                    f"Expected {expected_receivable:,.0f}, got {receivable_after:,.0f}")
    
    def test_piutang_regression(self):
        """Test 4: Piutang regression - receivable created, customer updated"""
        print("\n" + "="*80)
        print("TEST 4: PIUTANG REGRESSION")
        print("="*80)
        
        # Refresh products to get latest stock
        self.refresh_products()
        
        # Find a product and customer
        product = self.find_product_with_unit("kg", min_stock=10.0)
        if not product:
            self.log("Piutang Regression - Find Product", "FAIL", "No product with 'kg' unit found")
            return
        
        if not self.customers:
            self.log("Piutang Regression - Find Customer", "FAIL", "No customers found")
            return
        
        customer = self.customers[0]
        customer_id = customer["id"]
        customer_name = customer["name"]
        
        product_id = product["id"]
        product_name = product["name"]
        price_kg = product.get("price_kg", 0)
        
        print(f"Product: {product_name}")
        print(f"Customer: {customer_name}")
        
        # Get customer receivable before
        resp = requests.get(f"{BASE_URL}/customers", headers=self.headers)
        customers = resp.json()
        customer_before = next((c for c in customers if c["id"] == customer_id), None)
        receivable_before = customer_before.get("receivable", 0) if customer_before else 0
        
        # Create piutang sale
        txn_id = f"test-piutang-{uuid.uuid4().hex[:8]}"
        total_price = price_kg * 1.5
        paid = total_price * 0.3  # Pay 30%
        
        sale_payload = {
            "txn_id": txn_id,
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 1.5,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": paid,
            "payment_method": "piutang"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp.status_code != 200:
            self.log("Piutang Regression - Create Sale", "FAIL", 
                    f"Status {resp.status_code}: {resp.text}")
            return
        
        sale = resp.json()
        sale_id = sale["id"]
        receivable_amount = sale.get("receivable", 0)
        
        self.log("Piutang Regression - Create Sale", "PASS", 
                f"Sale created with receivable Rp {receivable_amount:,.0f}")
        
        # Verify receivable created
        resp = requests.get(f"{BASE_URL}/receivables", headers=self.headers)
        if resp.status_code == 200:
            receivables = resp.json()
            receivable = next((r for r in receivables if r.get("sale_id") == sale_id), None)
            if receivable:
                self.log("Piutang Regression - Receivable Created", "PASS", 
                        f"Receivable entry created for sale {sale_id[:8]}")
            else:
                self.log("Piutang Regression - Receivable Created", "FAIL", 
                        f"No receivable entry for sale {sale_id[:8]}")
        else:
            self.log("Piutang Regression - Receivable Created", "FAIL", 
                    f"Could not fetch receivables: {resp.status_code}")
        
        # Verify customer receivable increased
        resp = requests.get(f"{BASE_URL}/customers", headers=self.headers)
        customers = resp.json()
        customer_after = next((c for c in customers if c["id"] == customer_id), None)
        receivable_after = customer_after.get("receivable", 0) if customer_after else 0
        
        expected_receivable = receivable_before + receivable_amount
        
        if abs(receivable_after - expected_receivable) < 0.01:
            self.log("Piutang Regression - Customer Updated", "PASS", 
                    f"Customer receivable: {receivable_before:,.0f} → {receivable_after:,.0f}")
        else:
            self.log("Piutang Regression - Customer Updated", "FAIL", 
                    f"Expected {expected_receivable:,.0f}, got {receivable_after:,.0f}")
        
        # Test without customer_id (should fail)
        sale_payload_no_customer = {
            "txn_id": f"test-piutang-nocust-{uuid.uuid4().hex[:8]}",
            "items": [
                {
                    "product_id": product_id,
                    "unit": "kg",
                    "qty": 1.0,
                    "price": price_kg
                }
            ],
            "discount": 0,
            "paid": 0,
            "payment_method": "piutang"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload_no_customer)
        if resp.status_code == 400:
            self.log("Piutang Regression - No Customer Rejected", "PASS", 
                    "Piutang without customer_id correctly rejected with 400")
        else:
            self.log("Piutang Regression - No Customer Rejected", "FAIL", 
                    f"Expected 400, got {resp.status_code}")
    
    def test_cancel_sale(self):
        """Test 5: Cancel sale regression - restore stock for kg, ekor, pcs"""
        print("\n" + "="*80)
        print("TEST 5: CANCEL SALE REGRESSION")
        print("="*80)
        
        # Refresh products to get latest stock
        self.refresh_products()
        
        # Find products with different units and sufficient stock
        product_kg = self.find_product_with_unit("kg", min_stock=10.0)
        product_ekor = self.find_product_with_unit("ekor", min_stock=10.0)
        product_pcs = self.find_product_with_unit("pcs", min_stock=10.0)
        
        if not (product_kg and product_ekor and product_pcs):
            self.log("Cancel Sale - Find Products", "FAIL", 
                    f"Missing products: kg={bool(product_kg)}, ekor={bool(product_ekor)}, pcs={bool(product_pcs)}")
            return
        
        print(f"Product kg: {product_kg['name']}")
        print(f"Product ekor: {product_ekor['name']}")
        print(f"Product pcs: {product_pcs['name']}")
        
        # Get stock before
        stock_kg_before = self.get_product_stock(product_kg["id"])
        stock_ekor_before = self.get_product_stock(product_ekor["id"])
        stock_pcs_before = self.get_product_stock(product_pcs["id"])
        
        print(f"Stock before: kg={stock_kg_before['stock_kg']}, ekor={stock_ekor_before['stock_ekor']}, pcs={stock_pcs_before['stock_pcs']}")
        
        # Create sale with 3 items
        txn_id = f"test-cancel-{uuid.uuid4().hex[:8]}"
        sale_payload = {
            "txn_id": txn_id,
            "items": [
                {
                    "product_id": product_kg["id"],
                    "unit": "kg",
                    "qty": 2.0,
                    "price": product_kg.get("price_kg", 0)
                },
                {
                    "product_id": product_ekor["id"],
                    "unit": "ekor",
                    "qty": 3.0,
                    "price": product_ekor.get("price_ekor", 0)
                },
                {
                    "product_id": product_pcs["id"],
                    "unit": "pcs",
                    "qty": 5.0,
                    "price": product_pcs.get("price_pcs", 0)
                }
            ],
            "discount": 0,
            "paid": 0,
            "payment_method": "cash"
        }
        
        resp = requests.post(f"{BASE_URL}/sales", headers=self.headers, json=sale_payload)
        if resp.status_code != 200:
            self.log("Cancel Sale - Create Sale", "FAIL", 
                    f"Status {resp.status_code}: {resp.text}")
            return
        
        sale = resp.json()
        sale_id = sale["id"]
        
        self.log("Cancel Sale - Create Sale", "PASS", f"Sale created: {sale_id[:8]}")
        
        # Cancel the sale
        resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=self.headers)
        if resp.status_code != 200:
            self.log("Cancel Sale - Cancel", "FAIL", 
                    f"Status {resp.status_code}: {resp.text}")
            return
        
        self.log("Cancel Sale - Cancel", "PASS", f"Sale {sale_id[:8]} cancelled")
        
        # Verify stock restored
        self.refresh_products()
        stock_kg_after = self.get_product_stock(product_kg["id"])
        stock_ekor_after = self.get_product_stock(product_ekor["id"])
        stock_pcs_after = self.get_product_stock(product_pcs["id"])
        
        checks = []
        checks.append(("kg restored", abs(stock_kg_after["stock_kg"] - stock_kg_before["stock_kg"]) < 0.001))
        checks.append(("ekor restored", abs(stock_ekor_after["stock_ekor"] - stock_ekor_before["stock_ekor"]) < 0.001))
        checks.append(("pcs restored", abs(stock_pcs_after["stock_pcs"] - stock_pcs_before["stock_pcs"]) < 0.001))
        
        all_pass = all(check[1] for check in checks)
        details = f"kg: {stock_kg_before['stock_kg']} → {stock_kg_after['stock_kg']}, " \
                 f"ekor: {stock_ekor_before['stock_ekor']} → {stock_ekor_after['stock_ekor']}, " \
                 f"pcs: {stock_pcs_before['stock_pcs']} → {stock_pcs_after['stock_pcs']}"
        
        if all_pass:
            self.log("Cancel Sale - Stock Restored", "PASS", details)
        else:
            self.log("Cancel Sale - Stock Restored", "FAIL", details)
        
        # Verify income deleted
        resp = requests.get(f"{BASE_URL}/incomes", headers=self.headers)
        if resp.status_code == 200:
            incomes = resp.json()
            income_found = any(inc.get("ref") == sale_id for inc in incomes)
            if not income_found:
                self.log("Cancel Sale - Income Deleted", "PASS", 
                        f"Income entry deleted for sale {sale_id[:8]}")
            else:
                self.log("Cancel Sale - Income Deleted", "FAIL", 
                        f"Income entry still exists for sale {sale_id[:8]}")
        
        # Verify status is 'batal'
        resp = requests.get(f"{BASE_URL}/sales", headers=self.headers)
        if resp.status_code == 200:
            sales = resp.json()
            cancelled_sale = next((s for s in sales if s["id"] == sale_id), None)
            if cancelled_sale and cancelled_sale.get("status") == "batal":
                self.log("Cancel Sale - Status", "PASS", "Sale status is 'batal'")
            else:
                self.log("Cancel Sale - Status", "FAIL", 
                        f"Sale status is '{cancelled_sale.get('status') if cancelled_sale else 'NOT FOUND'}'")
        
        # Try to cancel again (should fail)
        resp = requests.post(f"{BASE_URL}/sales/{sale_id}/cancel", headers=self.headers)
        if resp.status_code == 400:
            self.log("Cancel Sale - Double Cancel Rejected", "PASS", 
                    "Second cancel correctly rejected with 400")
        else:
            self.log("Cancel Sale - Double Cancel Rejected", "FAIL", 
                    f"Expected 400, got {resp.status_code}")
    
    def test_smoke_endpoints(self):
        """Test 6: Smoke test of main endpoints"""
        print("\n" + "="*80)
        print("TEST 6: SMOKE TEST MAIN ENDPOINTS")
        print("="*80)
        
        endpoints = [
            "/dashboard",
            "/products",
            "/customers",
            "/sales",
            "/reports/profit-loss",
            "/reports/sales",
            "/reports/stock",
            "/stock-movements",
            "/activities",
            "/notifications",
            "/receivables",
            "/payables",
            "/targets",
            "/settings",
            "/audit-logs"
        ]
        
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=self.headers)
            if resp.status_code == 200:
                self.log(f"Smoke Test - {endpoint}", "PASS", f"Status 200")
            else:
                self.log(f"Smoke Test - {endpoint}", "FAIL", 
                        f"Status {resp.status_code}: {resp.text[:100]}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        total = len(self.test_results)
        
        print(f"\nTotal: {total} tests")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.test_results:
                if r["status"] == "FAIL":
                    print(f"  - {r['test']}")
                    if r["details"]:
                        print(f"    {r['details']}")
        
        print("\n" + "="*80)
        return failed == 0

def main():
    runner = TestRunner()
    
    # Login
    if not runner.login():
        print("\n❌ Login failed. Aborting tests.")
        return False
    
    # Get products and customers
    if not runner.get_products():
        print("\n❌ Failed to get products. Aborting tests.")
        return False
    
    if not runner.get_customers():
        print("\n❌ Failed to get customers. Aborting tests.")
        return False
    
    print(f"\nFound {len(runner.products)} products and {len(runner.customers)} customers")
    
    # Run tests
    runner.test_normal_sale()
    runner.test_offline_sale()
    runner.test_idempotency_cash()
    runner.test_idempotency_piutang()
    runner.test_piutang_regression()
    runner.test_cancel_sale()
    runner.test_smoke_endpoints()
    
    # Print summary
    all_passed = runner.print_summary()
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
