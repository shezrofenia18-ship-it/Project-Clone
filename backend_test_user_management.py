#!/usr/bin/env python3
"""
Backend Test: User Management (Edit & Delete)
Testing PUT /api/auth/users/{id} and DELETE /api/auth/users/{id}

SAFETY RULES:
- Create test accounts for destructive scenarios
- DO NOT delete/deactivate: shezrofenia18@gmail.com, owner@berkahayam.com, 
  admin@berkahayam.com, kasir@berkahayam.com, operator@berkahayam.com
- Restore any changed passwords to test_credentials.md values
- Report final account list to ensure identical to initial state
"""

import requests
import sys
from typing import Optional

BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
OWNER_EMAIL = "shezrofenia18@gmail.com"
OWNER_PASSWORD = "berkahayam1"
ADMIN_EMAIL = "admin@berkahayam.com"
ADMIN_PASSWORD = "admin123"
KASIR_EMAIL = "kasir@berkahayam.com"
KASIR_PASSWORD = "kasir123"

# Protected accounts (DO NOT delete/deactivate)
PROTECTED_ACCOUNTS = [
    "shezrofenia18@gmail.com",
    "owner@berkahayam.com",
    "admin@berkahayam.com",
    "kasir@berkahayam.com",
    "operator@berkahayam.com",
]

def login(email: str, password: str) -> Optional[str]:
    """Login and return token, or None if failed."""
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code == 200:
            return r.json()["token"]
        return None
    except Exception as e:
        print(f"  ⚠️  Login exception: {e}")
        return None

def get_users(token: str) -> list:
    """Get list of all users."""
    r = requests.get(f"{BASE_URL}/auth/users", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if r.status_code == 200:
        return r.json()
    return []

def create_user(token: str, name: str, email: str, password: str, role: str) -> Optional[dict]:
    """Create a new user."""
    r = requests.post(f"{BASE_URL}/auth/users", 
                      headers={"Authorization": f"Bearer {token}"},
                      json={"name": name, "email": email, "password": password, "role": role},
                      timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def update_user(token: str, user_id: str, **kwargs) -> tuple[int, dict]:
    """Update user. Returns (status_code, response_json)."""
    r = requests.put(f"{BASE_URL}/auth/users/{user_id}",
                     headers={"Authorization": f"Bearer {token}"},
                     json=kwargs,
                     timeout=10)
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"detail": r.text}

def delete_user(token: str, user_id: str) -> tuple[int, dict]:
    """Delete user. Returns (status_code, response_json)."""
    r = requests.delete(f"{BASE_URL}/auth/users/{user_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10)
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"detail": r.text}

def get_audit_logs(token: str, entity: str = "user") -> list:
    """Get audit logs for entity."""
    # Assuming audit logs endpoint exists (common pattern)
    # If not, we'll check MongoDB directly or skip this test
    try:
        r = requests.get(f"{BASE_URL}/audit-logs?entity={entity}", 
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

def count_active_owners(token: str) -> int:
    """Count active owners."""
    users = get_users(token)
    return sum(1 for u in users if u.get("role") == "owner" and u.get("active", True))

print("=" * 80)
print("BACKEND TEST: USER MANAGEMENT (EDIT & DELETE)")
print("=" * 80)
print()

# Login as owner
print("🔐 Logging in as owner...")
owner_token = login(OWNER_EMAIL, OWNER_PASSWORD)
if not owner_token:
    print("❌ FAILED: Cannot login as owner")
    sys.exit(1)
print(f"✅ Owner logged in: {OWNER_EMAIL}")
print()

# Get initial state
print("📋 Getting initial user list...")
initial_users = get_users(owner_token)
print(f"✅ Initial users count: {len(initial_users)}")
print("Initial accounts:")
for u in initial_users:
    print(f"  - {u['name']} ({u['email']}) - {u['role']} - {'active' if u.get('active', True) else 'inactive'}")
print()

# Count initial active owners
initial_owner_count = count_active_owners(owner_token)
print(f"📊 Initial active owners: {initial_owner_count}")
print()

# Track test accounts to cleanup
test_accounts = []

print("=" * 80)
print("A. EDIT TESTS (PUT /api/auth/users/{id})")
print("=" * 80)
print()

# A1. Create test account A
print("A1. Creating test account A (role: kasir)...")
test_user_a = create_user(owner_token, "Test User A", "uji-hapus-a@berkahayam.com", "testpass123", "kasir")
if not test_user_a:
    print("❌ FAILED: Cannot create test user A")
    sys.exit(1)
test_accounts.append(test_user_a["id"])
print(f"✅ Test user A created: id={test_user_a['id']}, email={test_user_a['email']}")
print()

# A2. Change name only
print("A2. Change name only...")
status, resp = update_user(owner_token, test_user_a["id"], name="Test User A Modified")
if status == 200:
    if resp["name"] == "Test User A Modified" and resp["email"] == test_user_a["email"] and resp["role"] == "kasir":
        print(f"✅ PASS: Name changed, email/role unchanged (name={resp['name']})")
    else:
        print(f"❌ FAIL: Unexpected changes (name={resp.get('name')}, email={resp.get('email')}, role={resp.get('role')})")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

# A3. Change email to new email
print("A3. Change email to new email...")
new_email = "uji-hapus-a-new@berkahayam.com"
status, resp = update_user(owner_token, test_user_a["id"], email=new_email)
if status == 200:
    print(f"✅ Email changed to: {resp['email']}")
    # Try login with NEW email + old password
    print("  Testing login with NEW email + old password...")
    new_token = login(new_email, "testpass123")
    if new_token:
        print("  ✅ PASS: Login with new email + old password SUCCESSFUL")
    else:
        print("  ❌ FAIL: Login with new email + old password FAILED")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

# A4. Change email to duplicate email
print("A4. Change email to duplicate email (should fail)...")
status, resp = update_user(owner_token, test_user_a["id"], email=ADMIN_EMAIL)
if status == 400 and "sudah terdaftar" in resp.get("detail", "").lower():
    print(f"✅ PASS: 400 with message '{resp['detail']}'")
else:
    print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
print()

# A5. Change role (valid and invalid)
print("A5a. Change role to 'admin' (valid)...")
status, resp = update_user(owner_token, test_user_a["id"], role="admin")
if status == 200 and resp["role"] == "admin":
    print(f"✅ PASS: Role changed to 'admin'")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

print("A5b. Change role to 'superadmin' (invalid)...")
status, resp = update_user(owner_token, test_user_a["id"], role="superadmin")
if status == 400 and "tidak valid" in resp.get("detail", "").lower():
    print(f"✅ PASS: 400 with message '{resp['detail']}'")
else:
    print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
print()

# A6. Password tests
print("A6a. Update WITHOUT password field (old password should still work)...")
status, resp = update_user(owner_token, test_user_a["id"], name="Test User A v2")
if status == 200:
    print("  Testing login with old password...")
    test_token = login(new_email, "testpass123")
    if test_token:
        print("  ✅ PASS: Old password still works")
    else:
        print("  ❌ FAIL: Old password doesn't work")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

print("A6b. Update WITH new password (>=6 chars)...")
status, resp = update_user(owner_token, test_user_a["id"], password="newpass123")
if status == 200:
    print("  Testing login with NEW password...")
    test_token = login(new_email, "newpass123")
    if test_token:
        print("  ✅ PASS: New password works")
        print("  Testing login with OLD password (should fail)...")
        old_token = login(new_email, "testpass123")
        if not old_token:
            print("  ✅ PASS: Old password fails with 401")
        else:
            print("  ❌ FAIL: Old password still works (should fail)")
    else:
        print("  ❌ FAIL: New password doesn't work")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

print("A6c. Update with password 5 chars (should fail)...")
status, resp = update_user(owner_token, test_user_a["id"], password="12345")
if status == 400 and "minimal 6" in resp.get("detail", "").lower():
    print(f"✅ PASS: 400 with message '{resp['detail']}'")
else:
    print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
print()

# A7. Empty name
print("A7. Update with empty name (should fail)...")
status, resp = update_user(owner_token, test_user_a["id"], name="")
if status == 400 and "tidak boleh kosong" in resp.get("detail", "").lower():
    print(f"✅ PASS: 400 with message '{resp['detail']}'")
else:
    print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
print()

# A8. Invalid id
print("A8a. Update with invalid id 'abc123' (should be 404, NOT 500)...")
status, resp = update_user(owner_token, "abc123", name="Test")
if status == 404 and "tidak ditemukan" in resp.get("detail", "").lower():
    print(f"✅ PASS: 404 with message '{resp['detail']}' (NOT 500)")
else:
    print(f"❌ FAIL: Status {status}, expected 404. Response: {resp}")
print()

print("A8b. Update with valid ObjectId but doesn't exist...")
fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format
status, resp = update_user(owner_token, fake_id, name="Test")
if status == 404:
    print(f"✅ PASS: 404 with message '{resp.get('detail')}'")
else:
    print(f"❌ FAIL: Status {status}, expected 404. Response: {resp}")
print()

# A9. Deactivate test account
print("A9a. Deactivate test account...")
status, resp = update_user(owner_token, test_user_a["id"], active=False)
if status == 200 and resp.get("active") is False:
    print(f"✅ Account deactivated")
    print("  Testing login (should fail with 403)...")
    test_token = login(new_email, "newpass123")
    if not test_token:
        # Check if it's 403 by trying to get the error
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": new_email, "password": "newpass123"}, timeout=10)
        if r.status_code == 403 and "dinonaktifkan" in r.json().get("detail", "").lower():
            print(f"  ✅ PASS: Login failed with 403 '{r.json()['detail']}'")
        else:
            print(f"  ⚠️  Login failed but status {r.status_code}: {r.json()}")
    else:
        print("  ❌ FAIL: Login succeeded (should fail)")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

print("A9b. Reactivate test account...")
status, resp = update_user(owner_token, test_user_a["id"], active=True)
if status == 200 and resp.get("active") is True:
    print(f"✅ Account reactivated")
    print("  Testing login (should succeed)...")
    test_token = login(new_email, "newpass123")
    if test_token:
        print("  ✅ PASS: Login successful")
    else:
        print("  ❌ FAIL: Login failed (should succeed)")
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

# A10. Cannot deactivate own account
print("A10. Try to deactivate OWN account (should fail)...")
# Get owner's user id
owner_users = [u for u in get_users(owner_token) if u["email"] == OWNER_EMAIL]
if owner_users:
    owner_id = owner_users[0]["id"]
    status, resp = update_user(owner_token, owner_id, active=False)
    if status == 400 and "akun sendiri" in resp.get("detail", "").lower():
        print(f"✅ PASS: 400 with message '{resp['detail']}'")
    else:
        print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
else:
    print("⚠️  SKIP: Cannot find owner's user id")
print()

# A11. Cannot deactivate primary owner
print("A11. Try to deactivate PRIMARY OWNER (shezrofenia18@gmail.com) (should fail)...")
primary_owner = [u for u in get_users(owner_token) if u["email"] == OWNER_EMAIL]
if primary_owner:
    status, resp = update_user(owner_token, primary_owner[0]["id"], active=False)
    if status == 400 and ("utama" in resp.get("detail", "").lower() or "otomatis" in resp.get("detail", "").lower()):
        print(f"✅ PASS: 400 with message '{resp['detail']}'")
    else:
        print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
else:
    print("⚠️  SKIP: Cannot find primary owner")
print()

# A12. Owner count test
print("A12. Owner count test...")
current_owner_count = count_active_owners(owner_token)
print(f"  Current active owners: {current_owner_count}")
if current_owner_count >= 2:
    # Find a non-primary owner to test
    other_owners = [u for u in get_users(owner_token) 
                    if u["role"] == "owner" and u["email"] != OWNER_EMAIL and u.get("active", True)]
    if other_owners:
        test_owner = other_owners[0]
        print(f"  Testing with owner: {test_owner['email']}")
        print(f"  Demoting {test_owner['email']} to kasir...")
        status, resp = update_user(owner_token, test_owner["id"], role="kasir")
        if status == 200:
            new_count = count_active_owners(owner_token)
            print(f"  ✅ Demotion successful. Active owners: {current_owner_count} → {new_count}")
            # Restore
            print(f"  Restoring role to owner...")
            status2, resp2 = update_user(owner_token, test_owner["id"], role="owner")
            if status2 == 200:
                restored_count = count_active_owners(owner_token)
                print(f"  ✅ Role restored. Active owners: {restored_count}")
            else:
                print(f"  ⚠️  Failed to restore role: {status2} {resp2}")
        else:
            print(f"  ⚠️  Demotion failed: {status} {resp}")
    else:
        print("  ⚠️  No other active owners to test with")
else:
    print(f"  ⚠️  Only {current_owner_count} active owner(s), cannot safely test owner count limit")
print()

print("=" * 80)
print("B. DELETE TESTS (DELETE /api/auth/users/{id})")
print("=" * 80)
print()

# B13. Delete test account
print("B13. Delete test account A...")
status, resp = delete_user(owner_token, test_user_a["id"])
if status == 200 and resp.get("ok") is True:
    print(f"✅ PASS: 200 {{ok: true, name: '{resp.get('name')}', email: '{resp.get('email')}'}}")
    # Check not in GET /users
    users = get_users(owner_token)
    if not any(u["id"] == test_user_a["id"] for u in users):
        print("  ✅ PASS: Account not in GET /api/auth/users")
    else:
        print("  ❌ FAIL: Account still in GET /api/auth/users")
    # Try login (should fail with 401)
    test_token = login(new_email, "newpass123")
    if not test_token:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": new_email, "password": "newpass123"}, timeout=10)
        if r.status_code == 401:
            print(f"  ✅ PASS: Login failed with 401")
        else:
            print(f"  ⚠️  Login failed with status {r.status_code} (expected 401)")
    else:
        print("  ❌ FAIL: Login succeeded (should fail)")
    test_accounts.remove(test_user_a["id"])
else:
    print(f"❌ FAIL: Status {status}, expected 200. Response: {resp}")
print()

# B14. Delete own account
print("B14. Try to delete OWN account (should fail)...")
if owner_users:
    status, resp = delete_user(owner_token, owner_id)
    if status == 400 and "akun sendiri" in resp.get("detail", "").lower():
        print(f"✅ PASS: 400 with message '{resp['detail']}'")
    else:
        print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
else:
    print("⚠️  SKIP: Cannot find owner's user id")
print()

# B15. Delete primary owner
print("B15. Try to delete PRIMARY OWNER (should fail)...")
if primary_owner:
    status, resp = delete_user(owner_token, primary_owner[0]["id"])
    if status == 400 and ("utama" in resp.get("detail", "").lower() or "otomatis" in resp.get("detail", "").lower()):
        print(f"✅ PASS: 400 with message '{resp['detail']}'")
    else:
        print(f"❌ FAIL: Status {status}, expected 400. Response: {resp}")
else:
    print("⚠️  SKIP: Cannot find primary owner")
print()

# B16. Delete invalid id
print("B16. Delete invalid id...")
status, resp = delete_user(owner_token, "abc123")
if status == 404:
    print(f"✅ PASS: 404 with message '{resp.get('detail')}'")
else:
    print(f"❌ FAIL: Status {status}, expected 404. Response: {resp}")
print()

print("=" * 80)
print("C. RBAC TESTS")
print("=" * 80)
print()

# C17. Admin cannot PUT/DELETE
print("C17. Admin RBAC...")
admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
if admin_token:
    # Create a test user to try editing
    test_user_b = create_user(owner_token, "Test User B", "uji-rbac@berkahayam.com", "testpass123", "kasir")
    if test_user_b:
        test_accounts.append(test_user_b["id"])
        print("  Testing admin PUT /api/auth/users/{id}...")
        status, resp = update_user(admin_token, test_user_b["id"], name="Modified by Admin")
        if status == 403:
            print(f"  ✅ PASS: Admin PUT → 403 '{resp.get('detail')}'")
        else:
            print(f"  ❌ FAIL: Admin PUT → {status} (expected 403). Response: {resp}")
        
        print("  Testing admin DELETE /api/auth/users/{id}...")
        status, resp = delete_user(admin_token, test_user_b["id"])
        if status == 403:
            print(f"  ✅ PASS: Admin DELETE → 403 '{resp.get('detail')}'")
        else:
            print(f"  ❌ FAIL: Admin DELETE → {status} (expected 403). Response: {resp}")
    else:
        print("  ⚠️  Cannot create test user B")
else:
    print("⚠️  SKIP: Cannot login as admin")
print()

# C18. Kasir cannot PUT/DELETE/GET
print("C18. Kasir RBAC...")
kasir_token = login(KASIR_EMAIL, KASIR_PASSWORD)
if kasir_token:
    if test_user_b:
        print("  Testing kasir PUT /api/auth/users/{id}...")
        status, resp = update_user(kasir_token, test_user_b["id"], name="Modified by Kasir")
        if status == 403:
            print(f"  ✅ PASS: Kasir PUT → 403 '{resp.get('detail')}'")
        else:
            print(f"  ❌ FAIL: Kasir PUT → {status} (expected 403). Response: {resp}")
        
        print("  Testing kasir DELETE /api/auth/users/{id}...")
        status, resp = delete_user(kasir_token, test_user_b["id"])
        if status == 403:
            print(f"  ✅ PASS: Kasir DELETE → 403 '{resp.get('detail')}'")
        else:
            print(f"  ❌ FAIL: Kasir DELETE → {status} (expected 403). Response: {resp}")
    
    print("  Testing kasir GET /api/auth/users...")
    r = requests.get(f"{BASE_URL}/auth/users", headers={"Authorization": f"Bearer {kasir_token}"}, timeout=10)
    if r.status_code == 403:
        print(f"  ✅ PASS: Kasir GET /users → 403 '{r.json().get('detail')}'")
    else:
        print(f"  ❌ FAIL: Kasir GET /users → {r.status_code} (expected 403)")
else:
    print("⚠️  SKIP: Cannot login as kasir")
print()

# Cleanup test user B
if test_user_b and test_user_b["id"] in test_accounts:
    print("Cleaning up test user B...")
    delete_user(owner_token, test_user_b["id"])
    test_accounts.remove(test_user_b["id"])
    print()

print("=" * 80)
print("D. AUDIT LOG TEST")
print("=" * 80)
print()

print("D. Checking audit_logs collection...")
# Try to access audit logs via MongoDB or API
# Since there's no standard endpoint, we'll check if we can query it
# For now, we'll create and delete a test user to generate audit logs
print("  Creating and deleting a test user to generate audit logs...")
test_user_c = create_user(owner_token, "Test User C", "uji-audit@berkahayam.com", "testpass123", "kasir")
if test_user_c:
    # Update it
    update_user(owner_token, test_user_c["id"], name="Test User C Modified")
    # Delete it
    delete_user(owner_token, test_user_c["id"])
    print("  ✅ Test user created, updated, and deleted")
    print("  ⚠️  Note: Audit log verification requires direct MongoDB access or audit API endpoint")
    print("     Expected: audit_logs collection has entity='user', action='update'/'delete',")
    print("     with before/after fields, and NO password_hash in the data")
else:
    print("  ⚠️  Cannot create test user C for audit test")
print()

print("=" * 80)
print("E. REGRESSION TESTS")
print("=" * 80)
print()

# E. Regression
print("E1. POST /api/auth/users still works...")
test_user_d = create_user(owner_token, "Test User D", "uji-regression@berkahayam.com", "testpass123", "kasir")
if test_user_d:
    print(f"✅ PASS: User created successfully")
    test_accounts.append(test_user_d["id"])
    
    # Test duplicate email
    print("  Testing duplicate email...")
    test_user_dup = create_user(owner_token, "Duplicate", "uji-regression@berkahayam.com", "testpass123", "kasir")
    if not test_user_dup:
        r = requests.post(f"{BASE_URL}/auth/users",
                          headers={"Authorization": f"Bearer {owner_token}"},
                          json={"name": "Dup", "email": "uji-regression@berkahayam.com", "password": "test", "role": "kasir"},
                          timeout=10)
        if r.status_code == 400 and "sudah terdaftar" in r.json().get("detail", "").lower():
            print(f"  ✅ PASS: Duplicate email → 400 '{r.json()['detail']}'")
        else:
            print(f"  ⚠️  Duplicate email → {r.status_code}: {r.json()}")
    else:
        print("  ❌ FAIL: Duplicate email was accepted")
else:
    print("❌ FAIL: Cannot create user")
print()

print("E2. GET /api/dashboard still works...")
r = requests.get(f"{BASE_URL}/dashboard", headers={"Authorization": f"Bearer {owner_token}"}, timeout=10)
if r.status_code == 200:
    print(f"✅ PASS: Dashboard returns 200")
else:
    print(f"❌ FAIL: Dashboard returns {r.status_code}")
print()

print("E3. All demo accounts can still login...")
demo_accounts = [
    (OWNER_EMAIL, OWNER_PASSWORD, "Owner"),
    ("owner@berkahayam.com", "berkahayam1", "Owner Berkah"),
    (ADMIN_EMAIL, ADMIN_PASSWORD, "Admin"),
    (KASIR_EMAIL, KASIR_PASSWORD, "Kasir"),
    ("operator@berkahayam.com", "operator123", "Operator"),
]
all_login_ok = True
for email, password, name in demo_accounts:
    token = login(email, password)
    if token:
        print(f"  ✅ {name} ({email}): Login OK")
    else:
        print(f"  ❌ {name} ({email}): Login FAILED")
        all_login_ok = False
if all_login_ok:
    print("✅ PASS: All demo accounts can login")
else:
    print("❌ FAIL: Some demo accounts cannot login")
print()

print("=" * 80)
print("CLEANUP & FINAL VERIFICATION")
print("=" * 80)
print()

# Cleanup remaining test accounts
if test_accounts:
    print(f"Cleaning up {len(test_accounts)} remaining test account(s)...")
    for test_id in test_accounts[:]:
        delete_user(owner_token, test_id)
        test_accounts.remove(test_id)
    print("✅ All test accounts cleaned up")
    print()

# Final user list
print("📋 Final user list:")
final_users = get_users(owner_token)
print(f"Final users count: {len(final_users)}")
for u in final_users:
    status = "active" if u.get("active", True) else "inactive"
    print(f"  - {u['name']} ({u['email']}) - {u['role']} - {status}")
print()

# Compare with initial
if len(final_users) == len(initial_users):
    print("✅ User count matches initial state")
    # Check if all initial users are still there
    initial_emails = {u["email"] for u in initial_users}
    final_emails = {u["email"] for u in final_users}
    if initial_emails == final_emails:
        print("✅ All initial accounts are present")
    else:
        print("⚠️  Account list differs from initial state")
        print(f"   Missing: {initial_emails - final_emails}")
        print(f"   Added: {final_emails - initial_emails}")
else:
    print(f"⚠️  User count differs: initial={len(initial_users)}, final={len(final_users)}")
print()

final_owner_count = count_active_owners(owner_token)
print(f"📊 Final active owners: {final_owner_count} (initial: {initial_owner_count})")
if final_owner_count == initial_owner_count:
    print("✅ Owner count matches initial state")
else:
    print("⚠️  Owner count differs from initial state")
print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
