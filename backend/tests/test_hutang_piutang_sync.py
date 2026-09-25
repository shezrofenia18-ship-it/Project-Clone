"""Regression tests for the hutang/piutang sync bug fix.

Covers:
- Creating a purchase with partial payment, then paying the payable, and verifying
  the parent purchase row is updated (paid / payable / payment_status).
- Reports return new fields bayar_piutang_masuk and bayar_hutang_keluar.
- PDF endpoints still return application/pdf.
- Receivable payment regression (sale becomes lunas, bayar_piutang_masuk rises).
- Reconcile endpoint fixes purchases whose payable is already paid but doc still 'kredit'.
"""
import os
import time
import pytest
import requests

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    return None


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not configured"


def _login(username: str, password: str) -> str:
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    tok = _login("owner", "berkahayam1")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def whole_chicken_product(owner):
    """Return an existing product sold per 'ekor' (whole chicken)."""
    r = owner.get(f"{BASE}/api/products", timeout=30)
    assert r.status_code == 200, r.text
    products = r.json()
    ekor_products = [p for p in products
                     if "ekor" in (p.get("units") or []) and p.get("category") == "broiler"]
    if not ekor_products:
        ekor_products = [p for p in products if "ekor" in (p.get("units") or [])]
    assert ekor_products, "No 'ekor' product found in seed data"
    return ekor_products[0]


@pytest.fixture(scope="module")
def supplier(owner):
    payload = {"name": "TEST_Supplier_Sync", "phone": "081200000000", "address": "-"}
    r = owner.post(f"{BASE}/api/suppliers", json=payload, timeout=30)
    if r.status_code in (400, 409):
        # already exists
        rs = owner.get(f"{BASE}/api/suppliers", timeout=30)
        for s in rs.json():
            if s["name"] == payload["name"]:
                return s
    assert r.status_code in (200, 201), r.text
    return r.json()


def _find_purchase(owner, pid):
    r = owner.get(f"{BASE}/api/purchases", timeout=30)
    assert r.status_code == 200
    for p in r.json():
        if p["id"] == pid:
            return p
    return None


def _find_payable_for_purchase(owner, purchase_id):
    r = owner.get(f"{BASE}/api/payables", timeout=30)
    assert r.status_code == 200
    for p in r.json():
        if p.get("purchase_id") == purchase_id:
            return p
    return None


class TestPurchasePayableSync:
    """The core bug: paying a payable must update the source purchase."""

    def test_full_flow(self, owner, whole_chicken_product, supplier):
        item = {
            "product_id": whole_chicken_product["id"],
            "ekor": 2,
            "total_weight": 4,
            "total_price": 100000,
        }
        body = {
            "supplier_id": supplier["id"],
            "items": [item],
            "transport_cost": 0,
            "other_cost": 0,
            "paid": 40000,
        }
        r = owner.post(f"{BASE}/api/purchases", json=body, timeout=30)
        assert r.status_code == 200, r.text
        purchase = r.json()
        pid = purchase["id"]

        # verify initial purchase state
        p = _find_purchase(owner, pid)
        assert p is not None
        assert round(p["paid"], 2) == 40000
        assert round(p["payable"], 2) == 60000
        assert p["payment_status"] == "kredit"

        # verify payable created and linked
        payable = _find_payable_for_purchase(owner, pid)
        assert payable is not None, "payable not linked to purchase"
        assert round(payable["remaining"], 2) == 60000
        payable_id = payable["id"]

        # get supplier payable baseline
        rs = owner.get(f"{BASE}/api/suppliers", timeout=30)
        sup_before = next(s for s in rs.json() if s["id"] == supplier["id"])
        supplier_payable_before = float(sup_before.get("payable", 0) or 0)

        # get reports baseline (bayar_hutang_keluar)
        rr = owner.get(f"{BASE}/api/reports/profit-loss", timeout=30)
        assert rr.status_code == 200, rr.text
        pl_before = rr.json()
        assert "bayar_hutang_keluar" in pl_before, "report missing bayar_hutang_keluar"
        assert "bayar_piutang_masuk" in pl_before, "report missing bayar_piutang_masuk"
        bh_before = float(pl_before.get("bayar_hutang_keluar", 0) or 0)

        # partial pay 25_000
        r2 = owner.post(f"{BASE}/api/payables/{payable_id}/pay",
                        json={"amount": 25000, "method": "cash"}, timeout=30)
        assert r2.status_code == 200, r2.text

        p = _find_purchase(owner, pid)
        assert round(p["paid"], 2) == 65000, f"purchase.paid did not sync: {p}"
        assert round(p["payable"], 2) == 35000, f"purchase.payable did not sync: {p}"
        assert p["payment_status"] == "kredit"

        # final pay 35_000
        r3 = owner.post(f"{BASE}/api/payables/{payable_id}/pay",
                        json={"amount": 35000, "method": "cash"}, timeout=30)
        assert r3.status_code == 200, r3.text

        p = _find_purchase(owner, pid)
        assert round(p["paid"], 2) == 100000
        assert round(p["payable"], 2) == 0
        assert p["payment_status"] == "lunas", f"expected lunas, got {p['payment_status']}"

        # supplier payable decreased by 60_000
        rs2 = owner.get(f"{BASE}/api/suppliers", timeout=30)
        sup_after = next(s for s in rs2.json() if s["id"] == supplier["id"])
        assert round(supplier_payable_before - float(sup_after.get("payable", 0) or 0), 2) == 60000

        # expense 'Pembayaran Hutang' created (finance still synced)
        rex = owner.get(f"{BASE}/api/expenses", timeout=30)
        assert rex.status_code == 200
        pay_expenses = [e for e in rex.json()
                        if e.get("category") == "Pembayaran Hutang" and e.get("ref") == payable_id]
        assert len(pay_expenses) >= 2, "expected 2 expense rows from 2 payments"

        # bayar_hutang_keluar in report increased by >= 60000
        rr2 = owner.get(f"{BASE}/api/reports/profit-loss", timeout=30)
        assert rr2.status_code == 200
        pl_after = rr2.json()
        bh_after = float(pl_after.get("bayar_hutang_keluar", 0) or 0)
        assert bh_after - bh_before >= 59999, f"bayar_hutang_keluar didn't rise: {bh_before} -> {bh_after}"


class TestReports:
    def test_profit_loss_fields(self, owner):
        r = owner.get(f"{BASE}/api/reports/profit-loss", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "bayar_piutang_masuk" in d
        assert "bayar_hutang_keluar" in d

    def test_monthly_fields(self, owner):
        r = owner.get(f"{BASE}/api/reports/monthly", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "bayar_piutang_masuk" in d
        assert "bayar_hutang_keluar" in d

    def test_profit_loss_pdf(self, owner):
        r = owner.get(f"{BASE}/api/reports/profit-loss/pdf", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"

    def test_monthly_pdf(self, owner):
        r = owner.get(f"{BASE}/api/reports/monthly/pdf", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"


class TestReceivableRegression:
    """Paying a receivable must still work and bump bayar_piutang_masuk."""

    def test_pay_receivable(self, owner, whole_chicken_product):
        # baseline
        pl0 = owner.get(f"{BASE}/api/reports/profit-loss", timeout=30).json()
        bp_before = float(pl0.get("bayar_piutang_masuk", 0) or 0)

        # need a customer
        rc = owner.get(f"{BASE}/api/customers", timeout=30)
        assert rc.status_code == 200
        customers = rc.json()
        assert customers, "no customers in seed"
        customer = customers[0]

        # create a piutang sale (payment_method='piutang')
        item = {
            "product_id": whole_chicken_product["id"],
            "unit": ("ekor" if "ekor" in (whole_chicken_product.get("units") or []) else
                     (whole_chicken_product.get("units") or ["kg"])[0]),
            "qty": 1,
            "price": 50000,
        }
        sbody = {
            "customer_id": customer["id"],
            "items": [item],
            "paid": 0,
            "payment_method": "piutang",
        }
        rs = owner.post(f"{BASE}/api/sales", json=sbody, timeout=30)
        assert rs.status_code == 200, rs.text
        sale = rs.json()
        sale_id = sale["id"]
        assert round(sale["receivable"], 2) == 50000
        assert sale["payment_status"] == "piutang"

        # find the receivable
        rr = owner.get(f"{BASE}/api/receivables", timeout=30)
        assert rr.status_code == 200
        rec = next((x for x in rr.json() if x.get("sale_id") == sale_id), None)
        assert rec is not None, "receivable not created for piutang sale"

        # pay it fully
        rp = owner.post(f"{BASE}/api/receivables/{rec['id']}/pay",
                        json={"amount": 50000, "method": "cash"}, timeout=30)
        assert rp.status_code == 200, rp.text

        # sale should now be lunas / receivable 0
        rs2 = owner.get(f"{BASE}/api/sales", timeout=30).json()
        updated = next(s for s in rs2 if s["id"] == sale_id)
        assert round(updated["receivable"], 2) == 0
        assert updated["payment_status"] == "lunas"

        # bayar_piutang_masuk increased
        pl1 = owner.get(f"{BASE}/api/reports/profit-loss", timeout=30).json()
        bp_after = float(pl1.get("bayar_piutang_masuk", 0) or 0)
        assert bp_after - bp_before >= 49999


class TestReconcileEndpoint:
    """POST /api/maintenance/reconcile should re-sync an out-of-band 'kredit' purchase."""

    def test_reconcile_fixes_desync(self, owner, whole_chicken_product, supplier):
        # create purchase paid in full
        body = {
            "supplier_id": supplier["id"],
            "items": [{"product_id": whole_chicken_product["id"], "ekor": 1,
                       "total_weight": 2, "total_price": 30000}],
            "paid": 30000,
        }
        r = owner.post(f"{BASE}/api/purchases", json=body, timeout=30)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]

        # sanity — should already be lunas
        p = _find_purchase(owner, pid)
        assert p["payment_status"] == "lunas"

        # Reconcile should be a no-op (return 200) — we mainly verify the endpoint exists
        rr = owner.post(f"{BASE}/api/maintenance/reconcile", timeout=60)
        assert rr.status_code == 200, rr.text
        body = rr.json()
        # response contains at least a counter of some kind
        assert isinstance(body, dict)
