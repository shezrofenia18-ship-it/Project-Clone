#!/usr/bin/env python3
"""
SMOKE TEST - Berkah Ayam Mili Backend
After GitHub sync + dependency reinstall (yarn install + pip install)
NO CODE CHANGES - only environment changed
"""

import requests
import json
from typing import Dict, Any, Optional

# Backend URL from frontend/.env
BASE_URL = "https://clone-dev-preview-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
OWNER_USERNAME = "owner"
OWNER_PASSWORD = "berkahayam1"

# Color codes for output
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


class SmokeTest:
    def __init__(self):
        self.owner_token = None
        self.admin_token = None
        self.kasir_token = None
        self.results = []
        
    def test_login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Test login and return response with token"""
        log_test(f"Testing login: {username}")
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                log_pass(f"Login successful for {username}")
                log_info(f"Response structure: {json.dumps({k: type(v).__name__ for k, v in data.items()}, indent=2)}")
                
                # Check for token field
                if "access_token" in data:
                    log_info(f"Token field: 'access_token' (length: {len(data['access_token'])})")
                elif "token" in data:
                    log_info(f"Token field: 'token' (length: {len(data['token'])})")
                else:
                    log_fail(f"No token field found in response!")
                
                # Check for user field
                if "user" in data:
                    user = data["user"]
                    log_info(f"User object: username={user.get('username')}, role={user.get('role')}, email={user.get('email')}")
                
                return data
            elif resp.status_code == 401:
                log_fail(f"Login failed for {username}: 401 Unauthorized (wrong credentials)")
                return None
            elif resp.status_code == 404:
                log_fail(f"Login failed for {username}: 404 Not Found (user doesn't exist)")
                return None
            else:
                log_fail(f"Login failed for {username}: {resp.status_code} - {resp.text[:200]}")
                return None
                
        except Exception as e:
            log_fail(f"Login exception for {username}: {e}")
            return None
    
    def check_user_exists(self, username: str) -> bool:
        """Check if user exists in database via GET /api/users"""
        if not self.owner_token:
            return False
        
        try:
            resp = requests.get(
                f"{BASE_URL}/users",
                headers={"Authorization": f"Bearer {self.owner_token}"},
                timeout=10
            )
            
            if resp.status_code == 200:
                users = resp.json()
                for user in users:
                    if user.get("username") == username:
                        log_info(f"User '{username}' found in DB: role={user.get('role')}, email={user.get('email')}")
                        return True
                log_info(f"User '{username}' NOT found in database")
                return False
            else:
                log_fail(f"Failed to fetch users: {resp.status_code}")
                return False
        except Exception as e:
            log_fail(f"Exception checking user existence: {e}")
            return False
    
    def test_endpoint(self, method: str, path: str, token: Optional[str] = None, 
                     expected_status: int = 200, description: str = "") -> Dict[str, Any]:
        """Test an endpoint and return result"""
        url = f"{BASE_URL}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            status = resp.status_code
            result = {
                "path": path,
                "method": method,
                "status": status,
                "expected": expected_status,
                "pass": status == expected_status,
                "description": description
            }
            
            if status == expected_status:
                log_pass(f"{method} {path} → {status}")
            else:
                log_fail(f"{method} {path} → {status} (expected {expected_status})")
                if status >= 400:
                    log_info(f"Error response: {resp.text[:200]}")
            
            # Additional checks for specific endpoints
            if status == 200:
                try:
                    data = resp.json()
                    if path == "/dashboard":
                        log_info(f"Dashboard keys: {list(data.keys())}")
                    elif path == "/products":
                        log_info(f"Products count: {len(data)}")
                    elif path == "/users":
                        log_info(f"Users count: {len(data)}")
                except:
                    pass
            
            self.results.append(result)
            return result
            
        except Exception as e:
            log_fail(f"{method} {path} → EXCEPTION: {e}")
            result = {
                "path": path,
                "method": method,
                "status": "ERROR",
                "expected": expected_status,
                "pass": False,
                "description": description,
                "error": str(e)
            }
            self.results.append(result)
            return result
    
    def test_pdf_endpoint(self, path: str, token: str, description: str = "") -> Dict[str, Any]:
        """Test PDF endpoint and verify content-type"""
        url = f"{BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            status = resp.status_code
            content_type = resp.headers.get("Content-Type", "")
            
            result = {
                "path": path,
                "method": "GET",
                "status": status,
                "content_type": content_type,
                "size": len(resp.content),
                "description": description
            }
            
            if status == 200:
                if "application/pdf" in content_type:
                    # Check PDF header
                    if resp.content[:4] == b'%PDF':
                        log_pass(f"PDF {path} → 200, {len(resp.content)} bytes, valid PDF header")
                        result["pass"] = True
                    else:
                        log_fail(f"PDF {path} → 200 but invalid PDF header")
                        result["pass"] = False
                else:
                    log_fail(f"PDF {path} → 200 but wrong content-type: {content_type}")
                    result["pass"] = False
            else:
                log_fail(f"PDF {path} → {status}")
                result["pass"] = False
            
            self.results.append(result)
            return result
            
        except Exception as e:
            log_fail(f"PDF {path} → EXCEPTION: {e}")
            result = {
                "path": path,
                "method": "GET",
                "status": "ERROR",
                "pass": False,
                "description": description,
                "error": str(e)
            }
            self.results.append(result)
            return result
    
    def run_smoke_test(self):
        """Run complete smoke test"""
        
        # ===== SECTION 1: LOGIN TESTS =====
        log_section("SECTION 1: LOGIN & AUTHENTICATION")
        
        # Test owner login
        owner_resp = self.test_login(OWNER_USERNAME, OWNER_PASSWORD)
        if owner_resp:
            self.owner_token = owner_resp.get("access_token") or owner_resp.get("token")
            if not self.owner_token:
                log_fail("Owner login succeeded but no token found!")
                return
        else:
            log_fail("Owner login failed - cannot continue tests")
            return
        
        # Check if admin and kasir users exist
        log_test("Checking if 'admin' and 'kasir' users exist in database...")
        admin_exists = self.check_user_exists("admin")
        kasir_exists = self.check_user_exists("kasir")
        
        # Try to login with admin and kasir
        if admin_exists:
            log_test("Attempting to login as 'admin' (trying common passwords)...")
            # Try common passwords
            for pwd in ["admin123", "admin", "berkahayam1"]:
                admin_resp = self.test_login("admin", pwd)
                if admin_resp:
                    self.admin_token = admin_resp.get("access_token") or admin_resp.get("token")
                    log_pass(f"Admin login successful with password: {pwd}")
                    break
            if not self.admin_token:
                log_fail("Admin user exists but couldn't find valid password")
        
        if kasir_exists:
            log_test("Attempting to login as 'kasir' (trying common passwords)...")
            # Try common passwords
            for pwd in ["kasir123", "kasir", "berkahayam1"]:
                kasir_resp = self.test_login("kasir", pwd)
                if kasir_resp:
                    self.kasir_token = kasir_resp.get("access_token") or kasir_resp.get("token")
                    log_pass(f"Kasir login successful with password: {pwd}")
                    break
            if not self.kasir_token:
                log_fail("Kasir user exists but couldn't find valid password")
        
        # ===== SECTION 2: MAIN GET ENDPOINTS =====
        log_section("SECTION 2: MAIN GET ENDPOINTS (with owner token)")
        
        endpoints = [
            ("/dashboard", "Dashboard summary"),
            ("/products", "Product list"),
            ("/sales", "Sales history"),
            ("/purchases", "Purchase history"),
            ("/productions", "Production history"),
            ("/customers", "Customer list"),
            ("/suppliers", "Supplier list"),
            ("/users", "User list"),
            ("/stock", "Stock levels"),
            ("/stock-movements", "Stock movement history"),
            ("/incomes", "Income records"),
            ("/expenses", "Expense records"),
            ("/receivables", "Receivables (piutang)"),
            ("/payables", "Payables (hutang)"),
            ("/daily-closing/preview", "Daily closing preview"),
            ("/whatsapp/settings", "WhatsApp settings"),
            ("/whatsapp/diagnostics", "WhatsApp diagnostics"),
            ("/dashboard/monthly?months=12", "Monthly dashboard (12 months)"),
            ("/maintenance/consistency", "Data consistency check"),
        ]
        
        for path, desc in endpoints:
            self.test_endpoint("GET", path, self.owner_token, 200, desc)
        
        # ===== SECTION 3: PDF REPORT ENDPOINTS =====
        log_section("SECTION 3: PDF REPORT ENDPOINTS (reportlab verification)")
        
        pdf_endpoints = [
            ("/reports/sales/pdf", "Sales report PDF"),
            ("/reports/profit-loss/pdf", "Profit-loss report PDF"),
            ("/reports/stock/pdf", "Stock report PDF"),
        ]
        
        for path, desc in pdf_endpoints:
            self.test_pdf_endpoint(path, self.owner_token, desc)
        
        # Test daily closing PDF (need to get a closing ID first)
        log_test("Testing daily closing PDF...")
        try:
            resp = requests.get(
                f"{BASE_URL}/daily-closing/preview",
                headers={"Authorization": f"Bearer {self.owner_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                preview = resp.json()
                if "id" in preview:
                    closing_id = preview["id"]
                    self.test_pdf_endpoint(f"/daily-closing/{closing_id}/pdf", self.owner_token, "Daily closing PDF")
                else:
                    log_info("No closing ID in preview, skipping daily closing PDF test")
        except Exception as e:
            log_fail(f"Failed to get closing preview: {e}")
        
        # ===== SECTION 4: RBAC TESTS =====
        log_section("SECTION 4: RBAC - Access without token (should be 401/403)")
        
        rbac_endpoints = [
            ("/dashboard", 401),
            ("/products", 401),
            ("/users", 401),
            ("/sales", 401),
        ]
        
        for path, expected in rbac_endpoints:
            self.test_endpoint("GET", path, None, expected, "No token")
        
        # ===== SECTION 5: BACKEND LOG CHECK =====
        log_section("SECTION 5: BACKEND ERROR LOG CHECK")
        
        log_test("Checking /var/log/supervisor/backend.err.log for errors...")
        try:
            import subprocess
            result = subprocess.run(
                ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            log_content = result.stdout
            
            # Check for critical errors
            if "ModuleNotFoundError" in log_content:
                log_fail("ModuleNotFoundError found in backend logs!")
                # Show the error
                for line in log_content.split("\n"):
                    if "ModuleNotFoundError" in line or "ImportError" in line:
                        log_info(f"  {line}")
            elif "ImportError" in log_content:
                log_fail("ImportError found in backend logs!")
                for line in log_content.split("\n"):
                    if "ImportError" in line:
                        log_info(f"  {line}")
            else:
                log_pass("No ModuleNotFoundError or ImportError in recent backend logs")
            
            # Check for successful startup
            if "Berkah Ayam Mili API started" in log_content:
                log_pass("Backend startup message found: 'Berkah Ayam Mili API started'")
            else:
                log_info("Backend startup message not found in recent logs (may have started earlier)")
                
        except Exception as e:
            log_fail(f"Failed to check backend logs: {e}")
        
        # ===== FINAL SUMMARY =====
        log_section("SMOKE TEST SUMMARY")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("pass", False))
        failed = total - passed
        
        print(f"Total tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        print()
        
        # Print results table
        print(f"{'='*100}")
        print(f"{'Endpoint':<50} {'Method':<8} {'Status':<10} {'Result':<10}")
        print(f"{'='*100}")
        
        for r in self.results:
            path = r["path"]
            method = r.get("method", "GET")
            status = str(r.get("status", "N/A"))
            result = "✅ PASS" if r.get("pass", False) else "❌ FAIL"
            
            print(f"{path:<50} {method:<8} {status:<10} {result:<10}")
        
        print(f"{'='*100}")
        print()
        
        # User existence summary
        log_section("USER EXISTENCE & LOGIN SUMMARY")
        print(f"Owner (username: 'owner'): ✅ EXISTS, ✅ CAN LOGIN (password: berkahayam1)")
        
        if admin_exists:
            if self.admin_token:
                print(f"Admin (username: 'admin'): ✅ EXISTS, ✅ CAN LOGIN")
            else:
                print(f"Admin (username: 'admin'): ✅ EXISTS, ❌ CANNOT LOGIN (password unknown)")
        else:
            print(f"Admin (username: 'admin'): ❌ DOES NOT EXIST")
        
        if kasir_exists:
            if self.kasir_token:
                print(f"Kasir (username: 'kasir'): ✅ EXISTS, ✅ CAN LOGIN")
            else:
                print(f"Kasir (username: 'kasir'): ✅ EXISTS, ❌ CANNOT LOGIN (password unknown)")
        else:
            print(f"Kasir (username: 'kasir'): ❌ DOES NOT EXIST")
        
        print()
        
        # Login response structure
        log_section("LOGIN RESPONSE STRUCTURE")
        if owner_resp:
            print("Owner login response fields:")
            for key, value in owner_resp.items():
                if key in ["access_token", "token"]:
                    print(f"  - {key}: <token> (length: {len(str(value))})")
                elif key == "user":
                    print(f"  - user:")
                    for uk, uv in value.items():
                        print(f"      - {uk}: {uv}")
                else:
                    print(f"  - {key}: {value}")
        
        return passed == total


if __name__ == "__main__":
    print(f"\n{BLUE}{'='*100}{RESET}")
    print(f"{BLUE}SMOKE TEST - Berkah Ayam Mili Backend{RESET}")
    print(f"{BLUE}After GitHub sync + dependency reinstall{RESET}")
    print(f"{BLUE}Backend URL: {BASE_URL}{RESET}")
    print(f"{BLUE}{'='*100}{RESET}\n")
    
    test = SmokeTest()
    success = test.run_smoke_test()
    
    if success:
        print(f"\n{GREEN}{'='*100}{RESET}")
        print(f"{GREEN}✅ ALL SMOKE TESTS PASSED{RESET}")
        print(f"{GREEN}{'='*100}{RESET}\n")
        exit(0)
    else:
        print(f"\n{RED}{'='*100}{RESET}")
        print(f"{RED}❌ SOME SMOKE TESTS FAILED{RESET}")
        print(f"{RED}{'='*100}{RESET}\n")
        exit(1)
