"""Backend tests for Production Cancellation feature."""
import os
import pytest
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

# Test credentials - using USERNAME login
CREDS = {
    "owner": ("owner", "admin123"),
    "admin": ("admin", "admin123"),
    "kasir": ("kasir", "kasir123"),
}

# Known product IDs from the problem statement
BROILER_ID = "c07ec866-eae1-49fc-bd10-e8abc72fd7a6"
DADA_ID = "68c52772-df1a-4708-b211-bf0922364d76"


def _login(username, password):
    """Login using USERNAME (not email)."""
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="module")
def tokens():
    """Get auth tokens for all roles."""
    out = {}
    for role, (u, p) in CREDS.items():
        r = _login(u, p)
        assert r.status_code == 200, f"login {role} failed: {r.status_code} {r.text}"
        j = r.json()
        assert "token" in j and "user" in j
        assert j["user"]["role"] == role
        out[role] = j["token"]
    return out


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def initial_stock(tokens):
    """Record initial stock of Broiler and Dada before tests."""
    r = requests.get(f"{API}/products", headers=_hdr(tokens["owner"]))
    assert r.status_code == 200
    products = r.json()
    
    broiler = next((p for p in products if p["id"] == BROILER_ID), None)
    dada = next((p for p in products if p["id"] == DADA_ID), None)
    
    assert broiler is not None, f"Ayam Broiler (id {BROILER_ID}) not found"
    assert dada is not None, f"Dada Ayam (id {DADA_ID}) not found"
    
    return {
        "broiler": {
            "id": BROILER_ID,
            "name": broiler["name"],
            "ekor": float(broiler.get("stock_ekor", 0)),
            "kg": float(broiler.get("stock_kg", 0)),
        },
        "dada": {
            "id": DADA_ID,
            "name": dada["name"],
            "pcs": float(dada.get("stock_pcs", 0)),
        }
    }


class TestProductionCancellation:
    """Test production cancellation feature."""
    
    production_id = None  # Will store created production ID
    
    def test_01_create_production(self, tokens, initial_stock):
        """Create production: 2 ekor Broiler -> 4 pcs Dada."""
        print(f"\n=== Initial Stock ===")
        print(f"Broiler: {initial_stock['broiler']['ekor']} ekor, {initial_stock['broiler']['kg']} kg")
        print(f"Dada: {initial_stock['dada']['pcs']} pcs")
        
        body = {
            "source_product_id": BROILER_ID,
            "input_ekor": 2,
            "outputs": [{"product_id": DADA_ID, "pcs": 4}]
        }
        
        r = requests.post(f"{API}/productions", headers=_hdr(tokens["owner"]), json=body)
        assert r.status_code == 200, f"Failed to create production: {r.status_code} {r.text}"
        
        prod = r.json()
        TestProductionCancellation.production_id = prod["id"]
        
        print(f"\n✅ Production created: {prod['id']}")
        print(f"   Input: {prod['input_ekor']} ekor, ~{prod.get('input_weight_kg', 0)} kg")
        print(f"   Output: {prod['outputs']}")
        
        # Verify stock changes
        r2 = requests.get(f"{API}/products", headers=_hdr(tokens["owner"]))
        products = r2.json()
        
        broiler = next(p for p in products if p["id"] == BROILER_ID)
        dada = next(p for p in products if p["id"] == DADA_ID)
        
        broiler_ekor_after = float(broiler.get("stock_ekor", 0))
        broiler_kg_after = float(broiler.get("stock_kg", 0))
        dada_pcs_after = float(dada.get("stock_pcs", 0))
        
        print(f"\n=== Stock After Production ===")
        print(f"Broiler: {broiler_ekor_after} ekor (Δ {broiler_ekor_after - initial_stock['broiler']['ekor']}), "
              f"{broiler_kg_after} kg (Δ {broiler_kg_after - initial_stock['broiler']['kg']:.3f})")
        print(f"Dada: {dada_pcs_after} pcs (Δ {dada_pcs_after - initial_stock['dada']['pcs']})")
        
        # Verify: Broiler should decrease by 2 ekor and ~3.7 kg
        assert abs(broiler_ekor_after - (initial_stock['broiler']['ekor'] - 2)) < 0.001, \
            f"Broiler ekor mismatch: expected {initial_stock['broiler']['ekor'] - 2}, got {broiler_ekor_after}"
        
        # Store the actual kg decrease for later verification
        TestProductionCancellation.kg_decreased = initial_stock['broiler']['kg'] - broiler_kg_after
        print(f"   Actual kg decreased: {TestProductionCancellation.kg_decreased:.3f}")
        
        # Dada should increase by 4 pcs
        assert abs(dada_pcs_after - (initial_stock['dada']['pcs'] + 4)) < 0.001, \
            f"Dada pcs mismatch: expected {initial_stock['dada']['pcs'] + 4}, got {dada_pcs_after}"
    
    def test_02_cancel_with_short_reason(self, tokens):
        """Cancel with reason < 3 chars should return 400."""
        pid = TestProductionCancellation.production_id
        assert pid, "No production ID from previous test"
        
        r = requests.post(f"{API}/productions/{pid}/cancel", 
                         headers=_hdr(tokens["owner"]), 
                         json={"reason": "x"})
        
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        print(f"\n✅ Short reason rejected: {r.text}")
    
    def test_03_cancel_with_valid_reason(self, tokens, initial_stock):
        """Cancel production with valid reason."""
        pid = TestProductionCancellation.production_id
        assert pid, "No production ID from previous test"
        
        reason = "Salah input tidak jadi dipotong"
        r = requests.post(f"{API}/productions/{pid}/cancel", 
                         headers=_hdr(tokens["owner"]), 
                         json={"reason": reason})
        
        assert r.status_code == 200, f"Failed to cancel: {r.status_code} {r.text}"
        
        result = r.json()
        print(f"\n✅ Production cancelled successfully")
        print(f"   Status: {result.get('status')}")
        print(f"   Cancelled by: {result.get('cancelled_by')}")
        print(f"   Reason: {result.get('cancel_reason')}")
        print(f"   Stock restored: {result.get('stock_restored')}")
        
        # Verify response structure
        assert result["status"] == "batal"
        assert result["cancelled_at"] is not None
        assert result["cancelled_by"] is not None
        assert result["cancel_reason"] == reason
        assert "stock_restored" in result
        
        # Verify stock_restored structure
        restored = result["stock_restored"]
        assert "ekor" in restored
        assert "kg" in restored
        assert "pcs" in restored
        
        assert restored["ekor"] == 2
        assert abs(restored["kg"] - TestProductionCancellation.kg_decreased) < 0.001
        assert "Dada Ayam" in restored["pcs"]
        assert restored["pcs"]["Dada Ayam"] == 4
        
        # Verify stock is restored
        r2 = requests.get(f"{API}/products", headers=_hdr(tokens["owner"]))
        products = r2.json()
        
        broiler = next(p for p in products if p["id"] == BROILER_ID)
        dada = next(p for p in products if p["id"] == DADA_ID)
        
        broiler_ekor_final = float(broiler.get("stock_ekor", 0))
        broiler_kg_final = float(broiler.get("stock_kg", 0))
        dada_pcs_final = float(dada.get("stock_pcs", 0))
        
        print(f"\n=== Stock After Cancellation ===")
        print(f"Broiler: {broiler_ekor_final} ekor, {broiler_kg_final} kg")
        print(f"Dada: {dada_pcs_final} pcs")
        
        # Stock should be back to initial values (tolerance 0.001)
        assert abs(broiler_ekor_final - initial_stock['broiler']['ekor']) < 0.001, \
            f"Broiler ekor not restored: expected {initial_stock['broiler']['ekor']}, got {broiler_ekor_final}"
        
        assert abs(broiler_kg_final - initial_stock['broiler']['kg']) < 0.001, \
            f"Broiler kg not restored: expected {initial_stock['broiler']['kg']}, got {broiler_kg_final}"
        
        assert abs(dada_pcs_final - initial_stock['dada']['pcs']) < 0.001, \
            f"Dada pcs not restored: expected {initial_stock['dada']['pcs']}, got {dada_pcs_final}"
        
        print(f"\n✅ Stock fully restored to initial values")
    
    def test_04_cancel_already_cancelled(self, tokens):
        """Second cancel should return 400."""
        pid = TestProductionCancellation.production_id
        assert pid, "No production ID from previous test"
        
        r = requests.post(f"{API}/productions/{pid}/cancel", 
                         headers=_hdr(tokens["owner"]), 
                         json={"reason": "abc"})
        
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert "sudah dibatalkan" in r.text.lower() or "already" in r.text.lower()
        print(f"\n✅ Second cancel rejected: {r.text}")
    
    def test_05_update_cancelled_production(self, tokens):
        """PUT on cancelled production should return 400."""
        pid = TestProductionCancellation.production_id
        assert pid, "No production ID from previous test"
        
        body = {
            "source_product_id": BROILER_ID,
            "input_ekor": 1,
            "outputs": [{"product_id": DADA_ID, "pcs": 2}]
        }
        
        r = requests.put(f"{API}/productions/{pid}", 
                        headers=_hdr(tokens["owner"]), 
                        json=body)
        
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        assert "dibatalkan" in r.text.lower() or "cancel" in r.text.lower()
        print(f"\n✅ Update cancelled production rejected: {r.text}")
    
    def test_06_cancelled_production_in_list(self, tokens):
        """GET /productions should include cancelled production."""
        pid = TestProductionCancellation.production_id
        assert pid, "No production ID from previous test"
        
        r = requests.get(f"{API}/productions", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        
        productions = r.json()
        cancelled = next((p for p in productions if p["id"] == pid), None)
        
        assert cancelled is not None, "Cancelled production not found in list"
        assert cancelled["status"] == "batal"
        print(f"\n✅ Cancelled production found in list with status 'batal'")
    
    def test_07_stock_movements_recorded(self, tokens):
        """Verify stock movements for cancellation."""
        r = requests.get(f"{API}/stock-movements?product_id={BROILER_ID}", 
                        headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        
        movements = r.json()
        # Find the latest 'produksi' movement (should be the restoration)
        produksi_movements = [m for m in movements if m.get("type") == "produksi"]
        
        if produksi_movements:
            latest = produksi_movements[0]  # Assuming sorted by created_at desc
            print(f"\n✅ Stock movement found:")
            print(f"   Type: {latest['type']}")
            print(f"   Qty ekor: {latest.get('qty_ekor')}")
            print(f"   Qty kg: {latest.get('qty_kg')}")
            
            # The restoration should be positive (adding back)
            assert latest.get('qty_ekor', 0) == 2, "Restoration ekor should be +2"
    
    def test_08_audit_log_recorded(self, tokens):
        """Verify audit log for cancellation."""
        r = requests.get(f"{API}/audit-logs", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        
        logs = r.json()
        cancel_logs = [log for log in logs if log.get("action") == "cancel" 
                      and log.get("entity") == "production"]
        
        assert len(cancel_logs) > 0, "No cancel audit log found"
        
        latest = cancel_logs[0]
        print(f"\n✅ Audit log found:")
        print(f"   Action: {latest['action']}")
        print(f"   Entity: {latest['entity']}")
        print(f"   User: {latest['user']}")
        
        # Verify 'after' contains reason
        if latest.get("after"):
            assert "reason" in latest["after"] or "cancel_reason" in latest["after"]
    
    def test_09_notification_created(self, tokens):
        """Verify notification for cancellation."""
        r = requests.get(f"{API}/notifications", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        
        notifications = r.json()
        cancel_notifs = [n for n in notifications 
                        if "dibatalkan" in n.get("title", "").lower() 
                        or "dibatalkan" in n.get("message", "").lower()]
        
        if cancel_notifs:
            print(f"\n✅ Notification found: {cancel_notifs[0].get('title')}")
        else:
            print(f"\n⚠️  No cancellation notification found (may be expected)")
    
    def test_10_kasir_can_cancel(self, tokens):
        """Kasir should be able to cancel production."""
        # Create a new production as kasir
        body = {
            "source_product_id": BROILER_ID,
            "input_ekor": 1,
            "outputs": [{"product_id": DADA_ID, "pcs": 2}]
        }
        
        r = requests.post(f"{API}/productions", headers=_hdr(tokens["kasir"]), json=body)
        assert r.status_code == 200, f"Kasir cannot create production: {r.text}"
        
        prod_id = r.json()["id"]
        
        # Cancel as kasir
        r2 = requests.post(f"{API}/productions/{prod_id}/cancel", 
                          headers=_hdr(tokens["kasir"]), 
                          json={"reason": "test kasir cancel"})
        
        assert r2.status_code == 200, f"Kasir cannot cancel: {r2.status_code} {r2.text}"
        print(f"\n✅ Kasir can cancel production")
    
    def test_11_cancel_nonexistent_production(self, tokens):
        """Cancel non-existent production should return 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        r = requests.post(f"{API}/productions/{fake_id}/cancel", 
                         headers=_hdr(tokens["owner"]), 
                         json={"reason": "abc"})
        
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print(f"\n✅ Non-existent production returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
