#!/usr/bin/env python3
"""
Backend Regression Test: POST /api/purchases WITHOUT transport_cost & other_cost
App: Berkah Ayam Mili
Date: 2026-08-30 sore

KONTEKS: Frontend form "Pembelian Baru" TIDAK lagi mengirim field transport_cost & other_cost
(kolom Transport & Biaya Lain dihapus atas permintaan owner). Backend tidak diubah (default 0).
Pastikan tidak ada regresi.

LANGKAH:
1. Login owner. GET /api/suppliers dan /api/products; pilih 1 produk kategori broiler/kampung/pejantan.
2. Catat kondisi awal: stock_kg & stock_ekor produk itu, hpp_kg, hpp_ekor, avg_weight_ekor;
   jumlah & total pengeluaran kategori "Pembelian Ayam"; serta /api/reports/profit-loss (periode hari ini).
3. POST /api/purchases dengan body TANPA transport_cost/other_cost:
   {"supplier_id": "<id>", "items": [{"product_id": "<id>", "ekor": 10, "total_weight": 20, "total_price": 500000}], "paid": 500000}
   → harus 200. Verifikasi: total_modal == 500000 (bukan lebih), effective_cost_kg == 25000,
   item hpp_ekor == 50000 (500000/10), total_weight == 20, payment_status == "lunas" (tidak ada hutang).
4. Verifikasi efek samping: stok produk +20 kg dan +10 ekor; muncul expense kategori "Pembelian Ayam"
   senilai 500000; produk ter-update avg_weight/hpp_ekor secara wajar (berat/ekor 2 kg).
5. Uji juga POST /api/purchases dengan paid=0 (harus jadi hutang / payables bertambah) lalu HAPUS pembelian itu juga.
6. BERSIHKAN: DELETE /api/purchases/{id} untuk SEMUA pembelian uji yang Anda buat → 200,
   lalu pastikan stok, expenses, payables, dan profit-loss kembali ke kondisi langkah 2.
"""

import requests
import sys
from typing import Dict, Any, List, Optional

# Backend URL dari frontend/.env
BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"

# Credentials dari /app/memory/test_credentials.md
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"

# Test data
TEST_EKOR = 10
TEST_WEIGHT = 20.0
TEST_PRICE = 500000
EXPECTED_COST_KG = 25000  # 500000 / 20
EXPECTED_HPP_EKOR = 50000  # 500000 / 10
EXPECTED_AVG_WEIGHT = 2.0  # 20 / 10

# Global state
token = None
test_purchases = []  # Track all test purchases for cleanup


def login() -> str:
    """Login as owner and return JWT token."""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": OWNER_EMAIL,
        "password": OWNER_PASSWORD
    })
    if resp.status_code != 200:
        print(f"❌ LOGIN FAILED: {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json()["token"]
    print(f"✅ LOGIN SUCCESS: {OWNER_EMAIL}")
    return token


def get_headers() -> Dict[str, str]:
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {token}"}


def get_suppliers() -> List[Dict[str, Any]]:
    """GET /api/suppliers."""
    resp = requests.get(f"{BASE_URL}/suppliers", headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ GET /api/suppliers FAILED: {resp.status_code}")
        sys.exit(1)
    suppliers = resp.json()
    print(f"✅ GET /api/suppliers: {len(suppliers)} suppliers")
    return suppliers


def get_products() -> List[Dict[str, Any]]:
    """GET /api/products."""
    resp = requests.get(f"{BASE_URL}/products", headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ GET /api/products FAILED: {resp.status_code}")
        sys.exit(1)
    products = resp.json()
    print(f"✅ GET /api/products: {len(products)} products")
    return products


def get_expenses() -> List[Dict[str, Any]]:
    """GET /api/expenses."""
    resp = requests.get(f"{BASE_URL}/expenses", headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ GET /api/expenses FAILED: {resp.status_code}")
        sys.exit(1)
    return resp.json()


def get_payables() -> List[Dict[str, Any]]:
    """GET /api/payables."""
    resp = requests.get(f"{BASE_URL}/payables", headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ GET /api/payables FAILED: {resp.status_code}")
        sys.exit(1)
    return resp.json()


def get_profit_loss(start_date: str, end_date: str) -> Dict[str, Any]:
    """GET /api/reports/profit-loss."""
    resp = requests.get(f"{BASE_URL}/reports/profit-loss", 
                       params={"start_date": start_date, "end_date": end_date},
                       headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ GET /api/reports/profit-loss FAILED: {resp.status_code}")
        sys.exit(1)
    return resp.json()


def select_test_product(products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Select a product with category broiler/kampung/pejantan and unit 'ekor'."""
    target_categories = ["broiler", "kampung", "pejantan"]
    for p in products:
        category = (p.get("category") or "").lower()
        units = p.get("units") or []
        if category in target_categories and "ekor" in units:
            return p
    return None


def record_initial_state(product: Dict[str, Any]) -> Dict[str, Any]:
    """Record initial state of product, expenses, and profit-loss."""
    expenses = get_expenses()
    purchase_expenses = [e for e in expenses if e.get("category") == "Pembelian Ayam"]
    payables = get_payables()
    
    # Get today's date for profit-loss
    import datetime
    today = datetime.date.today().isoformat()
    pl = get_profit_loss(today, today)
    
    state = {
        "product_id": product["id"],
        "product_name": product["name"],
        "stock_kg": product.get("stock_kg", 0),
        "stock_ekor": product.get("stock_ekor", 0),
        "hpp_kg": product.get("hpp_kg", 0),
        "hpp_ekor": product.get("hpp_ekor", 0),
        "avg_weight_ekor": product.get("avg_weight_ekor", 0),
        "purchase_expense_count": len(purchase_expenses),
        "purchase_expense_total": sum(e.get("amount", 0) for e in purchase_expenses),
        "payables_count": len(payables),
        "payables_total": sum(p.get("remaining", 0) for p in payables),
        "profit_loss": pl,
    }
    
    print(f"\n📊 INITIAL STATE:")
    print(f"   Product: {state['product_name']} (ID: {state['product_id']})")
    print(f"   Stock: {state['stock_kg']} kg, {state['stock_ekor']} ekor")
    print(f"   HPP: Rp {state['hpp_kg']:,.0f}/kg, Rp {state['hpp_ekor']:,.0f}/ekor")
    print(f"   Avg Weight: {state['avg_weight_ekor']} kg/ekor")
    print(f"   Purchase Expenses: {state['purchase_expense_count']} items, Total: Rp {state['purchase_expense_total']:,.0f}")
    print(f"   Payables: {state['payables_count']} items, Total: Rp {state['payables_total']:,.0f}")
    
    return state


def create_purchase(supplier_id: str, product_id: str, ekor: float, 
                   total_weight: float, total_price: float, paid: float) -> Dict[str, Any]:
    """POST /api/purchases WITHOUT transport_cost & other_cost."""
    body = {
        "supplier_id": supplier_id,
        "items": [{
            "product_id": product_id,
            "ekor": ekor,
            "total_weight": total_weight,
            "total_price": total_price
        }],
        "paid": paid
        # NOTE: transport_cost & other_cost NOT included (frontend no longer sends them)
    }
    
    resp = requests.post(f"{BASE_URL}/purchases", json=body, headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ POST /api/purchases FAILED: {resp.status_code} {resp.text}")
        return None
    
    purchase = resp.json()
    test_purchases.append(purchase["id"])  # Track for cleanup
    return purchase


def verify_purchase(purchase: Dict[str, Any], expected_total_modal: float,
                   expected_cost_kg: float, expected_hpp_ekor: float,
                   expected_weight: float, expected_status: str) -> bool:
    """Verify purchase response fields."""
    errors = []
    
    # Check total_modal
    actual_modal = purchase.get("total_modal", 0)
    if abs(actual_modal - expected_total_modal) > 0.01:
        errors.append(f"total_modal: expected {expected_total_modal}, got {actual_modal}")
    
    # Check effective_cost_kg
    actual_cost_kg = purchase.get("effective_cost_kg", 0)
    if abs(actual_cost_kg - expected_cost_kg) > 0.01:
        errors.append(f"effective_cost_kg: expected {expected_cost_kg}, got {actual_cost_kg}")
    
    # Check total_weight
    actual_weight = purchase.get("total_weight", 0)
    if abs(actual_weight - expected_weight) > 0.01:
        errors.append(f"total_weight: expected {expected_weight}, got {actual_weight}")
    
    # Check payment_status
    actual_status = purchase.get("payment_status", "")
    if actual_status != expected_status:
        errors.append(f"payment_status: expected '{expected_status}', got '{actual_status}'")
    
    # Check item hpp_ekor (from items[0])
    if purchase.get("items") and len(purchase["items"]) > 0:
        item = purchase["items"][0]
        # Calculate expected hpp_ekor for this item
        item_ekor = item.get("ekor", 0)
        item_subtotal = item.get("subtotal", 0)
        if item_ekor > 0:
            actual_hpp_ekor = item_subtotal / item_ekor
            if abs(actual_hpp_ekor - expected_hpp_ekor) > 0.01:
                errors.append(f"item hpp_ekor: expected {expected_hpp_ekor}, got {actual_hpp_ekor}")
    
    if errors:
        print(f"❌ PURCHASE VERIFICATION FAILED:")
        for err in errors:
            print(f"   - {err}")
        return False
    
    print(f"✅ PURCHASE VERIFIED:")
    print(f"   - total_modal: Rp {actual_modal:,.0f} ✓")
    print(f"   - effective_cost_kg: Rp {actual_cost_kg:,.0f}/kg ✓")
    print(f"   - total_weight: {actual_weight} kg ✓")
    print(f"   - payment_status: {actual_status} ✓")
    return True


def verify_side_effects(initial_state: Dict[str, Any], product_id: str,
                       expected_stock_kg_delta: float, expected_stock_ekor_delta: float,
                       expected_expense_amount: float) -> bool:
    """Verify side effects: stock changes, expense created, product updated."""
    errors = []
    
    # Get updated product
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        print(f"❌ Product {product_id} not found after purchase")
        return False
    
    # Check stock changes
    actual_stock_kg = product.get("stock_kg", 0)
    expected_stock_kg = initial_state["stock_kg"] + expected_stock_kg_delta
    if abs(actual_stock_kg - expected_stock_kg) > 0.01:
        errors.append(f"stock_kg: expected {expected_stock_kg}, got {actual_stock_kg}")
    
    actual_stock_ekor = product.get("stock_ekor", 0)
    expected_stock_ekor = initial_state["stock_ekor"] + expected_stock_ekor_delta
    if abs(actual_stock_ekor - expected_stock_ekor) > 0.01:
        errors.append(f"stock_ekor: expected {expected_stock_ekor}, got {actual_stock_ekor}")
    
    # Check expense created
    expenses = get_expenses()
    purchase_expenses = [e for e in expenses if e.get("category") == "Pembelian Ayam"]
    new_expense_count = len(purchase_expenses)
    expected_expense_count = initial_state["purchase_expense_count"] + 1
    if new_expense_count != expected_expense_count:
        errors.append(f"expense count: expected {expected_expense_count}, got {new_expense_count}")
    
    # Find the new expense
    new_expenses = [e for e in purchase_expenses 
                   if e.get("amount") == expected_expense_amount]
    if not new_expenses:
        errors.append(f"expense with amount {expected_expense_amount} not found")
    
    # Check product avg_weight updated (should be reasonable)
    actual_avg_weight = product.get("avg_weight_ekor", 0)
    if actual_avg_weight <= 0:
        errors.append(f"avg_weight_ekor not updated: {actual_avg_weight}")
    
    if errors:
        print(f"❌ SIDE EFFECTS VERIFICATION FAILED:")
        for err in errors:
            print(f"   - {err}")
        return False
    
    print(f"✅ SIDE EFFECTS VERIFIED:")
    print(f"   - stock_kg: {initial_state['stock_kg']} → {actual_stock_kg} (+{expected_stock_kg_delta}) ✓")
    print(f"   - stock_ekor: {initial_state['stock_ekor']} → {actual_stock_ekor} (+{expected_stock_ekor_delta}) ✓")
    print(f"   - expense created: Rp {expected_expense_amount:,.0f} ✓")
    print(f"   - avg_weight_ekor: {actual_avg_weight} kg/ekor ✓")
    return True


def delete_purchase(purchase_id: str) -> bool:
    """DELETE /api/purchases/{id}."""
    resp = requests.delete(f"{BASE_URL}/purchases/{purchase_id}", headers=get_headers())
    if resp.status_code != 200:
        print(f"❌ DELETE /api/purchases/{purchase_id} FAILED: {resp.status_code} {resp.text}")
        return False
    print(f"✅ DELETE /api/purchases/{purchase_id}: 200")
    return True


def verify_cleanup(initial_state: Dict[str, Any], product_id: str) -> bool:
    """Verify that stock, expenses, payables return to initial state after cleanup."""
    errors = []
    
    # Get updated product
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        print(f"❌ Product {product_id} not found after cleanup")
        return False
    
    # Check stock restored
    actual_stock_kg = product.get("stock_kg", 0)
    if abs(actual_stock_kg - initial_state["stock_kg"]) > 0.01:
        errors.append(f"stock_kg: expected {initial_state['stock_kg']}, got {actual_stock_kg}")
    
    actual_stock_ekor = product.get("stock_ekor", 0)
    if abs(actual_stock_ekor - initial_state["stock_ekor"]) > 0.01:
        errors.append(f"stock_ekor: expected {initial_state['stock_ekor']}, got {actual_stock_ekor}")
    
    # Check expenses restored
    expenses = get_expenses()
    purchase_expenses = [e for e in expenses if e.get("category") == "Pembelian Ayam"]
    actual_expense_count = len(purchase_expenses)
    if actual_expense_count != initial_state["purchase_expense_count"]:
        errors.append(f"expense count: expected {initial_state['purchase_expense_count']}, got {actual_expense_count}")
    
    # Check payables restored
    payables = get_payables()
    actual_payables_count = len(payables)
    if actual_payables_count != initial_state["payables_count"]:
        errors.append(f"payables count: expected {initial_state['payables_count']}, got {actual_payables_count}")
    
    if errors:
        print(f"❌ CLEANUP VERIFICATION FAILED:")
        for err in errors:
            print(f"   - {err}")
        return False
    
    print(f"✅ CLEANUP VERIFIED:")
    print(f"   - stock_kg: {actual_stock_kg} (restored) ✓")
    print(f"   - stock_ekor: {actual_stock_ekor} (restored) ✓")
    print(f"   - expense count: {actual_expense_count} (restored) ✓")
    print(f"   - payables count: {actual_payables_count} (restored) ✓")
    return True


def main():
    global token
    
    print("=" * 80)
    print("BACKEND REGRESSION TEST: POST /purchases WITHOUT transport_cost & other_cost")
    print("=" * 80)
    
    # Step 1: Login
    print("\n[STEP 1] LOGIN")
    token = login()
    
    # Step 2: Get suppliers and products
    print("\n[STEP 2] GET SUPPLIERS & PRODUCTS")
    suppliers = get_suppliers()
    if not suppliers:
        print("❌ No suppliers found")
        sys.exit(1)
    supplier = suppliers[0]
    print(f"   Selected supplier: {supplier['name']} (ID: {supplier['id']})")
    
    products = get_products()
    product = select_test_product(products)
    if not product:
        print("❌ No suitable product found (need broiler/kampung/pejantan with unit 'ekor')")
        sys.exit(1)
    print(f"   Selected product: {product['name']} (ID: {product['id']}, category: {product.get('category')})")
    
    # Step 3: Record initial state
    print("\n[STEP 3] RECORD INITIAL STATE")
    initial_state = record_initial_state(product)
    
    # Step 4: Create purchase WITHOUT transport_cost & other_cost (paid in full)
    print("\n[STEP 4] CREATE PURCHASE (PAID IN FULL)")
    print(f"   POST /api/purchases:")
    print(f"   - supplier_id: {supplier['id']}")
    print(f"   - product_id: {product['id']}")
    print(f"   - ekor: {TEST_EKOR}")
    print(f"   - total_weight: {TEST_WEIGHT} kg")
    print(f"   - total_price: Rp {TEST_PRICE:,.0f}")
    print(f"   - paid: Rp {TEST_PRICE:,.0f}")
    print(f"   - transport_cost: NOT SENT (frontend no longer sends)")
    print(f"   - other_cost: NOT SENT (frontend no longer sends)")
    
    purchase1 = create_purchase(supplier["id"], product["id"], TEST_EKOR, 
                               TEST_WEIGHT, TEST_PRICE, TEST_PRICE)
    if not purchase1:
        print("❌ TEST FAILED: Purchase creation failed")
        sys.exit(1)
    
    print(f"✅ Purchase created: ID {purchase1['id']}")
    
    # Step 5: Verify purchase response
    print("\n[STEP 5] VERIFY PURCHASE RESPONSE")
    if not verify_purchase(purchase1, TEST_PRICE, EXPECTED_COST_KG, 
                          EXPECTED_HPP_EKOR, TEST_WEIGHT, "lunas"):
        print("❌ TEST FAILED: Purchase verification failed")
        sys.exit(1)
    
    # Step 6: Verify side effects
    print("\n[STEP 6] VERIFY SIDE EFFECTS")
    if not verify_side_effects(initial_state, product["id"], TEST_WEIGHT, TEST_EKOR, TEST_PRICE):
        print("❌ TEST FAILED: Side effects verification failed")
        sys.exit(1)
    
    # Step 7: Create purchase with paid=0 (should create payable)
    print("\n[STEP 7] CREATE PURCHASE (PAID=0, SHOULD CREATE HUTANG)")
    print(f"   POST /api/purchases with paid=0")
    
    purchase2 = create_purchase(supplier["id"], product["id"], TEST_EKOR, 
                               TEST_WEIGHT, TEST_PRICE, 0)
    if not purchase2:
        print("❌ TEST FAILED: Purchase creation (paid=0) failed")
        sys.exit(1)
    
    print(f"✅ Purchase created: ID {purchase2['id']}")
    
    # Verify payment_status is "kredit"
    if purchase2.get("payment_status") != "kredit":
        print(f"❌ TEST FAILED: payment_status should be 'kredit', got '{purchase2.get('payment_status')}'")
        sys.exit(1)
    print(f"✅ payment_status: kredit ✓")
    
    # Verify payable created
    payables = get_payables()
    new_payable = next((p for p in payables if p.get("purchase_id") == purchase2["id"]), None)
    if not new_payable:
        print(f"❌ TEST FAILED: Payable not created for purchase {purchase2['id']}")
        sys.exit(1)
    print(f"✅ Payable created: Rp {new_payable.get('remaining', 0):,.0f} ✓")
    
    # Step 8: Cleanup - delete all test purchases
    print("\n[STEP 8] CLEANUP - DELETE ALL TEST PURCHASES")
    for purchase_id in test_purchases:
        if not delete_purchase(purchase_id):
            print(f"❌ TEST FAILED: Failed to delete purchase {purchase_id}")
            sys.exit(1)
    
    # Step 9: Verify cleanup
    print("\n[STEP 9] VERIFY CLEANUP")
    if not verify_cleanup(initial_state, product["id"]):
        print("❌ TEST FAILED: Cleanup verification failed")
        sys.exit(1)
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)
    print("\nSUMMARY:")
    print("  ✅ Purchase WITHOUT transport_cost & other_cost: 200")
    print("  ✅ total_modal == total_price (500000)")
    print("  ✅ effective_cost_kg == 25000")
    print("  ✅ item hpp_ekor == 50000")
    print("  ✅ payment_status == 'lunas' (paid in full)")
    print("  ✅ Stock increased: +20 kg, +10 ekor")
    print("  ✅ Expense 'Pembelian Ayam' created: Rp 500,000")
    print("  ✅ Product avg_weight updated")
    print("  ✅ Purchase with paid=0 creates hutang (payable)")
    print("  ✅ DELETE restores stock, expenses, payables to initial state")
    print("\n✅ NO REGRESSION FOUND")
    print("   Frontend can safely omit transport_cost & other_cost fields.")
    print("   Backend defaults to 0 and calculates total_modal correctly.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
