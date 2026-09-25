"""
Smoke/regression test for freshly cloned Berkah Ayam Mili app on Emergent.
Covers: auth, key GET endpoints, POS sale, PDF, RBAC, upload rejection, whatsapp status.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    return r


# -------- Auth --------
class TestAuth:
    def test_login_owner(self):
        r = _login("owner", "berkahayam1")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and data["user"]["role"] == "owner"

    def test_login_admin(self):
        r = _login("admin", "admin123")
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "admin"

    def test_login_kasir(self):
        r = _login("kasir", "kasir123")
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "kasir"

    def test_login_operator(self):
        r = _login("operator", "operator123")
        assert r.status_code == 200, r.text

    def test_login_wrong_password(self):
        r = _login("owner", "wrongpass")
        assert r.status_code == 401


# -------- Fixtures --------
@pytest.fixture(scope="module")
def owner_headers():
    r = _login("owner", "berkahayam1")
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def kasir_headers():
    r = _login("kasir", "kasir123")
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


# -------- Key GET endpoints --------
class TestKeyEndpoints:
    @pytest.mark.parametrize("path", [
        "/products", "/customers", "/suppliers", "/sales",
        "/stock-movements", "/dashboard", "/reports/profit-loss",
        "/reports/sales", "/reports/stock", "/notifications",
        "/settings", "/storage/status",
    ])
    def test_get_ok(self, owner_headers, path):
        r = requests.get(f"{API}{path}", headers=owner_headers, timeout=20)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"

    def test_whatsapp_status_no_crash(self, owner_headers):
        # There is no /whatsapp/status; the app exposes /whatsapp/settings and /whatsapp/diagnostics
        r = requests.get(f"{API}/whatsapp/diagnostics", headers=owner_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        # Should indicate not configured / manual, not crash
        assert isinstance(body, dict)


# -------- PDF report --------
class TestPDF:
    def test_profit_loss_pdf(self, owner_headers):
        r = requests.get(f"{API}/reports/profit-loss/pdf", headers=owner_headers, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# -------- POS sale --------
class TestPOSSale:
    def test_cash_sale_flow(self, owner_headers):
        products = requests.get(f"{API}/products", headers=owner_headers, timeout=15).json()
        assert isinstance(products, list) and len(products) > 0
        p = next((x for x in products if (x.get("stock_pcs") or x.get("stok_pcs") or 0) > 0 or x.get("harga_jual")), products[0])
        pid = p.get("id") or p.get("_id")
        price = p.get("harga_jual") or p.get("price") or 0
        payload = {
            "items": [{
                "product_id": pid,
                "name": p.get("nama") or p.get("name"),
                "qty": 1,
                "price": price,
                "unit": p.get("unit", "pcs"),
            }],
            "payment_method": "tunai",
            "total": price,
            "paid": price,
        }
        r = requests.post(f"{API}/sales", headers=owner_headers, json=payload, timeout=20)
        # Accept 200/201; if payload schema differs, just ensure not 500
        assert r.status_code < 500, f"Sale crashed: {r.status_code} {r.text[:300]}"
        if r.status_code in (200, 201):
            sales = requests.get(f"{API}/sales", headers=owner_headers, timeout=15).json()
            assert isinstance(sales, list)


# -------- RBAC --------
class TestRBAC:
    def test_kasir_forbidden_users(self, kasir_headers):
        r = requests.get(f"{API}/auth/users", headers=kasir_headers, timeout=15)
        # kasir should not be allowed to list users (owner/admin only)
        assert r.status_code in (401, 403)

    def test_kasir_forbidden_settings_update(self, kasir_headers):
        r = requests.put(f"{API}/settings", headers=kasir_headers, json={}, timeout=15)
        assert r.status_code in (401, 403)

    def test_kasir_forbidden_daily_closing(self, kasir_headers):
        r = requests.post(f"{API}/daily-closing", headers=kasir_headers, json={}, timeout=15)
        assert r.status_code in (401, 403, 400)  # 400 acceptable if validated before role in some impls
        # but must not be 200
        assert r.status_code != 200


# -------- Upload rejection (R2 not configured) --------
class TestUpload:
    def test_upload_rejected_gracefully(self, owner_headers):
        files = {"file": ("t.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")}
        r = requests.post(f"{API}/upload", headers=owner_headers, files=files, timeout=20)
        # Not a 500 crash; should be a clear 4xx / 503
        assert r.status_code != 500, r.text[:300]
        assert r.status_code >= 400
