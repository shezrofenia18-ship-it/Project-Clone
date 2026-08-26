"""Backend integration tests for Berkah Ayam Mili."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env directly
    from pathlib import Path
    fe = Path("/app/frontend/.env").read_text()
    for line in fe.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

CREDS = {
    "owner": ("shezrofenia18@gmail.com", "berkahayam1"),
    "admin": ("admin@berkahayam.com", "admin123"),
    "kasir": ("kasir@berkahayam.com", "kasir123"),
    "operator": ("operator@berkahayam.com", "operator123"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="session")
def tokens():
    out = {}
    for role, (e, p) in CREDS.items():
        r = _login(e, p)
        assert r.status_code == 200, f"login {role} failed: {r.status_code} {r.text}"
        j = r.json()
        assert "token" in j and "user" in j
        assert j["user"]["role"] == role
        out[role] = j["token"]
    return out


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


# -------- Auth --------
class TestAuth:
    def test_login_all_roles(self, tokens):
        assert set(tokens.keys()) == set(CREDS.keys())

    def test_login_wrong_password(self):
        r = _login("owner@berkahayam.com", "wrongpw")
        assert r.status_code in (400, 401)

    def test_me(self, tokens):
        r = requests.get(f"{API}/auth/me", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        assert r.json()["role"] == "owner"


# -------- RBAC --------
class TestRBAC:
    def test_kasir_cannot_dashboard(self, tokens):
        r = requests.get(f"{API}/dashboard", headers=_hdr(tokens["kasir"]))
        assert r.status_code == 403

    def test_kasir_cannot_expenses(self, tokens):
        r = requests.get(f"{API}/expenses", headers=_hdr(tokens["kasir"]))
        assert r.status_code == 403

    def test_operator_cannot_sales_create(self, tokens):
        r = requests.post(f"{API}/sales", headers=_hdr(tokens["operator"]),
                          json={"items": [], "payment_method": "cash"})
        assert r.status_code == 403

    def test_operator_can_slaughter_list(self, tokens):
        r = requests.get(f"{API}/slaughters", headers=_hdr(tokens["operator"]))
        assert r.status_code == 200

    def test_owner_only_target_set(self, tokens):
        r = requests.post(f"{API}/targets", headers=_hdr(tokens["admin"]),
                          json={"target_omzet": 1})
        assert r.status_code == 403


# -------- Dashboard --------
class TestDashboard:
    def test_dashboard_shape(self, tokens):
        r = requests.get(f"{API}/dashboard", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        d = r.json()
        for k in ["omzet", "hpp", "laba", "margin", "chart", "products_perf",
                  "critical_stock", "recent_sales", "activities", "prices", "target"]:
            assert k in d, f"missing {k}"
        assert len(d["chart"]) == 7

    def test_dashboard_has_demo_data(self, tokens):
        r = requests.get(f"{API}/dashboard", headers=_hdr(tokens["owner"]))
        d = r.json()
        # some demo data seeded; at least prices/products_perf non-empty
        assert len(d["prices"]) > 0 or d["omzet"] > 0


# -------- Products / Sale flow --------
@pytest.fixture(scope="session")
def products(tokens):
    r = requests.get(f"{API}/products", headers=_hdr(tokens["owner"]))
    assert r.status_code == 200
    return r.json()


class TestSaleFlow:
    def test_products_exist(self, products):
        assert len(products) > 0

    def test_create_sale_and_stock_decrement(self, tokens, products):
        # Find a kg product with stock
        kg_prod = next((p for p in products if "kg" in (p.get("units") or [])
                        and float(p.get("stock_kg", 0)) > 5 and float(p.get("price_kg", 0)) > 0), None)
        assert kg_prod, "no kg product with stock"
        stock_before = float(kg_prod["stock_kg"])
        txn_id = str(uuid.uuid4())
        body = {
            "txn_id": txn_id,
            "items": [{"product_id": kg_prod["id"], "unit": "kg", "qty": 1.0,
                       "price": kg_prod["price_kg"]}],
            "payment_method": "cash",
        }
        r = requests.post(f"{API}/sales", headers=_hdr(tokens["kasir"]), json=body)
        assert r.status_code == 200, r.text
        sale = r.json()
        assert sale["total"] > 0
        assert sale["payment_status"] == "lunas"
        assert sale["total_hpp"] >= 0

        # Idempotency: same txn_id returns same sale
        r2 = requests.post(f"{API}/sales", headers=_hdr(tokens["kasir"]), json=body)
        assert r2.status_code == 200
        assert r2.json()["id"] == sale["id"]

        # Stock decrement
        r3 = requests.get(f"{API}/products", headers=_hdr(tokens["kasir"]))
        prod_after = next(p for p in r3.json() if p["id"] == kg_prod["id"])
        assert abs(float(prod_after["stock_kg"]) - (stock_before - 1.0)) < 0.01

        # Store sale id for cancel test
        pytest.SALE_ID = sale["id"]
        pytest.SALE_PRODUCT_ID = kg_prod["id"]
        pytest.SALE_STOCK_AFTER = float(prod_after["stock_kg"])

    def test_insufficient_stock(self, tokens, products):
        kg_prod = next((p for p in products if "kg" in (p.get("units") or [])
                        and float(p.get("price_kg", 0)) > 0), None)
        assert kg_prod
        body = {
            "items": [{"product_id": kg_prod["id"], "unit": "kg", "qty": 999999.0,
                       "price": kg_prod["price_kg"]}],
            "payment_method": "cash",
        }
        r = requests.post(f"{API}/sales", headers=_hdr(tokens["kasir"]), json=body)
        assert r.status_code == 400
        assert "STOK" in r.text.upper() or "TIDAK MENCUKUPI" in r.text.upper()

    def test_cancel_sale_restores_stock(self, tokens):
        sid = getattr(pytest, "SALE_ID", None)
        if not sid:
            pytest.skip("no sale to cancel")
        r = requests.post(f"{API}/sales/{sid}/cancel", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        # verify stock restored by +1
        r2 = requests.get(f"{API}/products", headers=_hdr(tokens["owner"]))
        after = next(p for p in r2.json() if p["id"] == pytest.SALE_PRODUCT_ID)
        assert abs(float(after["stock_kg"]) - (pytest.SALE_STOCK_AFTER + 1.0)) < 0.01

    def test_kasir_cannot_cancel(self, tokens):
        # create then try cancel with kasir
        r = requests.get(f"{API}/sales", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        sales = r.json()
        if not sales:
            pytest.skip("no sales")
        active = next((s for s in sales if s.get("status") == "selesai"), None)
        if not active:
            pytest.skip("no active sale")
        r = requests.post(f"{API}/sales/{active['id']}/cancel", headers=_hdr(tokens["kasir"]))
        assert r.status_code == 403


# -------- Purchase / Slaughter / Production --------
class TestOperations:
    def test_create_purchase(self, tokens, products):
        r = requests.get(f"{API}/suppliers", headers=_hdr(tokens["admin"]))
        assert r.status_code == 200
        sups = r.json()
        if not sups:
            pytest.skip("no supplier")
        prod = next((p for p in products if p.get("category") in ("ayam_hidup", "karkas")), products[0])
        stock_before = float(prod["stock_kg"])
        body = {
            "supplier_id": sups[0]["id"],
            "items": [{"product_id": prod["id"], "ekor": 10, "total_weight": 15.0, "buy_price_kg": 30000}],
            "transport_cost": 20000, "other_cost": 0, "paid": 450000,
        }
        r = requests.post(f"{API}/purchases", headers=_hdr(tokens["admin"]), json=body)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["effective_cost_kg"] > 0
        # verify stock increased
        r2 = requests.get(f"{API}/products", headers=_hdr(tokens["admin"]))
        after = next(p for p in r2.json() if p["id"] == prod["id"])
        assert abs(float(after["stock_kg"]) - (stock_before + 15.0)) < 0.01

    def test_create_slaughter(self, tokens, products):
        prod = next((p for p in products if float(p.get("stock_kg", 0)) > 2), products[0])
        body = {"product_id": prod["id"], "ekor_in": 5, "live_weight": 10.0,
                "carcass_weight": 7.5, "cost_pemotongan": 5000}
        r = requests.post(f"{API}/slaughters", headers=_hdr(tokens["operator"]), json=body)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rendemen_pct"] == 75.0
        assert j["susut_weight"] == 2.5

    def test_slaughter_carcass_exceeds_live(self, tokens, products):
        prod = products[0]
        body = {"product_id": prod["id"], "live_weight": 5.0, "carcass_weight": 6.0}
        r = requests.post(f"{API}/slaughters", headers=_hdr(tokens["operator"]), json=body)
        assert r.status_code == 400


# -------- CRUD Customers/Suppliers --------
class TestCRUD:
    def test_customer_crud(self, tokens):
        body = {"name": "TEST_Cust", "phone": "0800", "type": "umum"}
        r = requests.post(f"{API}/customers", headers=_hdr(tokens["kasir"]), json=body)
        assert r.status_code == 200
        cid = r.json()["id"]
        r2 = requests.get(f"{API}/customers", headers=_hdr(tokens["kasir"]))
        assert any(c["id"] == cid for c in r2.json())
        r3 = requests.delete(f"{API}/customers/{cid}", headers=_hdr(tokens["owner"]))
        assert r3.status_code == 200

    def test_supplier_crud(self, tokens):
        body = {"name": "TEST_Sup", "phone": "0800"}
        r = requests.post(f"{API}/suppliers", headers=_hdr(tokens["admin"]), json=body)
        assert r.status_code == 200
        sid = r.json()["id"]
        r2 = requests.delete(f"{API}/suppliers/{sid}", headers=_hdr(tokens["owner"]))
        assert r2.status_code == 200


# -------- Targets, Settings, Reports --------
class TestMisc:
    def test_target_set_and_get(self, tokens):
        body = {"target_omzet": 5000000, "target_weight": 100, "target_ekor": 50, "target_laba": 1000000}
        r = requests.post(f"{API}/targets", headers=_hdr(tokens["owner"]), json=body)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/targets", headers=_hdr(tokens["owner"]))
        assert r2.status_code == 200
        assert r2.json()["target_omzet"] == 5000000

    def test_settings_toggle(self, tokens):
        r = requests.put(f"{API}/settings", headers=_hdr(tokens["owner"]),
                         json={"key": "allow_negative_stock", "value": True})
        assert r.status_code == 200
        r2 = requests.get(f"{API}/settings", headers=_hdr(tokens["owner"]))
        assert r2.json().get("allow_negative_stock") is True
        # reset
        requests.put(f"{API}/settings", headers=_hdr(tokens["owner"]),
                     json={"key": "allow_negative_stock", "value": False})

    def test_reports(self, tokens):
        for path in ["reports/profit-loss", "reports/sales", "reports/stock"]:
            r = requests.get(f"{API}/{path}", headers=_hdr(tokens["owner"]))
            assert r.status_code == 200, f"{path} failed"

    def test_audit_log(self, tokens):
        r = requests.get(f"{API}/audit-logs", headers=_hdr(tokens["admin"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_activities(self, tokens):
        r = requests.get(f"{API}/activities", headers=_hdr(tokens["kasir"]))
        assert r.status_code == 200
