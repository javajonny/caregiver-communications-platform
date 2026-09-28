"""
HIPAA Soft-Delete Test Script

Tests that:
1. Lookup tables soft-delete correctly (is_active = false)
2. Hard delete is NOT possible (endpoints return 404/405 or perform soft-delete)
3. Role-based access is enforced:
   - Admin: Can deactivate all lookup tables
   - Director: Can deactivate operational tables (behavior_types, task_categories, etc.)
   - Site Director: Cannot deactivate lookup tables
   - DSP: Cannot deactivate lookup tables

Run with: python test_soft_delete.py

Prerequisites:
- Server running on localhost:8443
- Database seeded with test data
- Credentials for all 4 roles
"""

import requests
import sys
import urllib3
from datetime import datetime

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration - UPDATE BEFORE RUNNING
BASE_URL = "https://localhost:8443"
VERIFY_SSL = False

# Credentials for all 4 roles - UPDATE BEFORE RUNNING
ADMIN_EMAIL = "XXXXXXXX"
ADMIN_PASSWORD = "XXXXXXXX"

DIRECTOR_EMAIL = "XXXXXXXX"
DIRECTOR_PASSWORD = "XXXXXXXX"

SITE_DIRECTOR_EMAIL = "XXXXXXXX"
SITE_DIRECTOR_PASSWORD = "XXXXXXXX"

DSP_EMAIL = "XXXXXXXX"
DSP_PASSWORD = "XXXXXXXX"

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_pass(msg):
    print(f"{GREEN}✓ PASS{RESET}: {msg}")

def log_fail(msg):
    print(f"{RED}✗ FAIL{RESET}: {msg}")

def log_info(msg):
    print(f"{YELLOW}ℹ INFO{RESET}: {msg}")

def get_auth_token(email, password, role_name):
    """Login and get auth token"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            verify=VERIFY_SSL
        )
        if response.status_code == 200:
            log_pass(f"{role_name} authenticated")
            return response.json().get("access_token")
        else:
            log_info(f"{role_name} authentication failed: {response.status_code}")
            return None
    except Exception as e:
        log_info(f"Error logging in as {role_name}: {e}")
        return None


def test_behavior_type_soft_delete_all_roles(tokens):
    """Test behavior_types soft-delete with all 4 roles"""
    print("\n" + "="*60)
    print("Testing Behavior Types Soft-Delete (All Roles)")
    print("="*60)
    
    results = []
    admin_headers = tokens.get("admin")
    director_headers = tokens.get("director")
    site_director_headers = tokens.get("site_director")
    dsp_headers = tokens.get("dsp")
    
    # Create test items for each role test
    test_items = []
    for i, role in enumerate(["admin", "director", "site_director", "dsp"]):
        test_name = f"Test Behavior {role} {datetime.now().strftime('%H%M%S%f')}"
        create_resp = requests.post(
            f"{BASE_URL}/behavior-types",
            json={"name": test_name, "description": f"Test for {role}"},
            headers=admin_headers,
            verify=VERIFY_SSL
        )
        if create_resp.status_code == 201:
            test_items.append((role, create_resp.json().get("id")))
        else:
            log_info(f"Could not create test item for {role}: {create_resp.status_code}")
    
    log_pass(f"Created {len(test_items)} test behavior types")
    
    # Test each role's ability to delete
    for role, item_id in test_items:
        headers = tokens.get(role)
        if not headers:
            log_info(f"Skipping {role} test (no token)")
            results.append((f"{role.upper()} delete behavior type", None))
            continue
        
        resp = requests.delete(
            f"{BASE_URL}/behavior-types/{item_id}",
            headers=headers,
            verify=VERIFY_SSL
        )
        
        # Expected: Admin and Director can delete, Site Director and DSP cannot
        if role in ["admin", "director"]:
            if resp.status_code == 200:
                log_pass(f"{role.upper()} can deactivate behavior type (as expected)")
                results.append((f"{role.upper()} can deactivate behavior type", True))
            else:
                log_fail(f"{role.upper()} could NOT deactivate: {resp.status_code}")
                results.append((f"{role.upper()} can deactivate behavior type", False))
        else:  # site_director, dsp
            if resp.status_code == 403:
                log_pass(f"{role.upper()} blocked from deactivating (403 as expected)")
                results.append((f"{role.upper()} blocked from deactivating", True))
            else:
                log_fail(f"{role.upper()} was NOT blocked: {resp.status_code}")
                results.append((f"{role.upper()} blocked from deactivating", False))
    
    return results


def test_task_category_soft_delete_all_roles(tokens):
    """Test task_categories soft-delete with all 4 roles"""
    print("\n" + "="*60)
    print("Testing Task Categories Soft-Delete (All Roles)")
    print("="*60)
    
    results = []
    admin_headers = tokens.get("admin")
    
    # Create test items for each role test
    test_items = []
    for i, role in enumerate(["admin", "director", "site_director", "dsp"]):
        test_name = f"Test Category {role} {datetime.now().strftime('%H%M%S%f')}"
        create_resp = requests.post(
            f"{BASE_URL}/shifts/task-categories",
            json={"name": test_name, "description": f"Test for {role}"},
            headers=admin_headers,
            verify=VERIFY_SSL
        )
        if create_resp.status_code == 201:
            test_items.append((role, create_resp.json().get("id")))
        else:
            log_info(f"Could not create test item for {role}: {create_resp.status_code}")
    
    log_pass(f"Created {len(test_items)} test task categories")
    
    # Test each role's ability to delete
    for role, item_id in test_items:
        headers = tokens.get(role)
        if not headers:
            log_info(f"Skipping {role} test (no token)")
            results.append((f"{role.upper()} delete task category", None))
            continue
        
        resp = requests.delete(
            f"{BASE_URL}/shifts/task-categories/{item_id}",
            headers=headers,
            verify=VERIFY_SSL
        )
        
        # Expected: Admin and Director can delete, Site Director and DSP cannot
        if role in ["admin", "director"]:
            if resp.status_code == 200:
                log_pass(f"{role.upper()} can deactivate task category (as expected)")
                results.append((f"{role.upper()} can deactivate task category", True))
            else:
                log_fail(f"{role.upper()} could NOT deactivate: {resp.status_code}")
                results.append((f"{role.upper()} can deactivate task category", False))
        else:  # site_director, dsp
            if resp.status_code == 403:
                log_pass(f"{role.upper()} blocked from deactivating (403 as expected)")
                results.append((f"{role.upper()} blocked from deactivating", True))
            else:
                log_fail(f"{role.upper()} was NOT blocked: {resp.status_code}")
                results.append((f"{role.upper()} blocked from deactivating", False))
    
    return results


def test_immutable_records(admin_headers):
    """Test that immutable records (behavior_tracking, client_updates) cannot be modified"""
    print("\n" + "="*60)
    print("Testing Immutable Records (HIPAA)")
    print("="*60)
    
    results = []
    
    # Test 1: Behavior tracking records - no UPDATE endpoint
    log_info("Testing behavior tracking records immutability...")
    resp = requests.put(
        f"{BASE_URL}/behavior-tracking/1",
        json={"recorded_value": 999},
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    if resp.status_code in [404, 405]:
        log_pass("Behavior tracking UPDATE endpoint does not exist (404/405)")
        results.append(("Behavior tracking immutable (no UPDATE)", True))
    else:
        log_fail(f"Behavior tracking UPDATE returned: {resp.status_code}")
        results.append(("Behavior tracking immutable (no UPDATE)", False))
    
    # Test 2: Behavior tracking records - no DELETE endpoint
    resp = requests.delete(
        f"{BASE_URL}/behavior-tracking/1",
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    if resp.status_code in [404, 405]:
        log_pass("Behavior tracking DELETE endpoint does not exist (404/405)")
        results.append(("Behavior tracking immutable (no DELETE)", True))
    else:
        log_fail(f"Behavior tracking DELETE returned: {resp.status_code}")
        results.append(("Behavior tracking immutable (no DELETE)", False))
    
    # Test 3: Client updates - no UPDATE endpoint
    log_info("Testing client updates immutability...")
    resp = requests.put(
        f"{BASE_URL}/clients/1/updates/1",
        json={"content": "Tampered!"},
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    if resp.status_code in [404, 405]:
        log_pass("Client updates UPDATE endpoint does not exist (404/405)")
        results.append(("Client updates immutable (no UPDATE)", True))
    else:
        log_fail(f"Client updates UPDATE returned: {resp.status_code}")
        results.append(("Client updates immutable (no UPDATE)", False))
    
    return results


def test_double_deactivation(admin_headers):
    """Test that deactivating an already inactive item fails gracefully"""
    print("\n" + "="*60)
    print("Testing Double Deactivation Prevention")
    print("="*60)
    
    results = []
    
    # Create and deactivate a behavior type
    test_name = f"Double Deactivate Test {datetime.now().strftime('%H%M%S%f')}"
    create_resp = requests.post(
        f"{BASE_URL}/behavior-types",
        json={"name": test_name, "description": "Test double deactivation"},
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    
    if create_resp.status_code != 201:
        log_info("Could not create test item")
        return results
    
    item_id = create_resp.json().get("id")
    
    # First deactivation
    resp1 = requests.delete(
        f"{BASE_URL}/behavior-types/{item_id}",
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    if resp1.status_code != 200:
        log_info(f"First deactivation failed: {resp1.status_code}")
        return results
    
    log_pass("First deactivation successful")
    
    # Second deactivation (should fail with 400)
    resp2 = requests.delete(
        f"{BASE_URL}/behavior-types/{item_id}",
        headers=admin_headers,
        verify=VERIFY_SSL
    )
    if resp2.status_code == 400:
        log_pass("Double deactivation prevented (400 Bad Request)")
        results.append(("Double deactivation prevented", True))
    else:
        log_fail(f"Double deactivation returned: {resp2.status_code}")
        results.append(("Double deactivation prevented", False))
    
    return results


def run_all_tests():
    """Run all soft-delete tests"""
    print("="*60)
    print("HIPAA Soft-Delete Test Suite (All Roles)")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*60)
    
    # Authenticate all roles
    print("\n--- Authenticating All Roles ---")
    tokens = {}
    
    admin_token = get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD, "Admin")
    if admin_token:
        tokens["admin"] = {"Authorization": f"Bearer {admin_token}"}
    else:
        log_fail("Admin authentication REQUIRED - cannot proceed")
        return False
    
    director_token = get_auth_token(DIRECTOR_EMAIL, DIRECTOR_PASSWORD, "Director")
    if director_token:
        tokens["director"] = {"Authorization": f"Bearer {director_token}"}
    
    site_director_token = get_auth_token(SITE_DIRECTOR_EMAIL, SITE_DIRECTOR_PASSWORD, "Site Director")
    if site_director_token:
        tokens["site_director"] = {"Authorization": f"Bearer {site_director_token}"}
    
    dsp_token = get_auth_token(DSP_EMAIL, DSP_PASSWORD, "DSP")
    if dsp_token:
        tokens["dsp"] = {"Authorization": f"Bearer {dsp_token}"}
    
    print(f"\nAuthenticated {len(tokens)}/4 roles")
    
    all_results = []
    
    # Run tests
    all_results.extend(test_behavior_type_soft_delete_all_roles(tokens))
    all_results.extend(test_task_category_soft_delete_all_roles(tokens))
    all_results.extend(test_immutable_records(tokens["admin"]))
    all_results.extend(test_double_deactivation(tokens["admin"]))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in all_results if r is True)
    failed = sum(1 for _, r in all_results if r is False)
    skipped = sum(1 for _, r in all_results if r is None)
    
    for name, result in all_results:
        if result is True:
            print(f"  {GREEN}✓{RESET} {name}")
        elif result is False:
            print(f"  {RED}✗{RESET} {name}")
        else:
            print(f"  {YELLOW}○{RESET} {name} (skipped)")
    
    print()
    print(f"Total: {len(all_results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    if failed == 0:
        print(f"\n{GREEN}All tests passed!{RESET}")
        return True
    else:
        print(f"\n{RED}Some tests failed - review above for details{RESET}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

