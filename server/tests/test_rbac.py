
import requests
import sys
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
BASE_URL = "https://localhost:8443"
VERIFY_SSL = False

# Credentials - UPDATE THESE BEFORE RUNNING
ADMIN_EMAIL = "XXXXXXXXX"
ADMIN_PASSWORD = "XXXXXXXXX"  # Replace with actual password

DIRECTOR_EMAIL = "XXXXXXXXX"
DIRECTOR_PASSWORD = "XXXXXXXXX" 

DSP_EMAIL = "XXXXXXXXX"
DSP_PASSWORD = "XXXXXXXXX"  # Replace with actual password

SITEDIR_EMAIL = "XXXXXXXXX"
SITEDIR_PASSWORD = "XXXXXXXXX"  # Replace with actual password

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def log_pass(msg):
    print(f"{GREEN}PASS: {msg}{RESET}")

def log_fail(msg):
    print(f"{RED}FAIL: {msg}{RESET}")

def get_auth_token(email, password):
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            verify=VERIFY_SSL
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Login failed for {email}: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def test_template_creation_rbac(admin_token, director_token, dsp_token):
    print("\n--- Testing Template Creation RBAC ---")
    
    # Generate unique suffix to avoid DB constraint errors
    import time
    timestamp = int(time.time())

    # Data for new template
    data = {
        "name": f"RBAC Test Template {timestamp}",
        "description": "Should fail for DSP",
        "category_id": 1,
        "revision_interval_days": 365,
        "is_archived": False,
        "form_schema": {"type": "object", "properties": {"test": {"type": "string"}}}
    }
    
    # 1. Test as Admin (Should Succeed)
    if admin_token:
        resp = requests.post(f"{BASE_URL}/documents/templates", json=data, headers={"Authorization": f"Bearer {admin_token}"}, verify=VERIFY_SSL)
        if resp.status_code == 201:
            log_pass("Admin created template successfully")
        else:
            log_fail(f"Admin failed to create template: {resp.status_code}")

    # 2. Test as Director (Should Succeed)
    if director_token:
        # Create a slightly different template
        data["name"] = f"RBAC Test Template (Director) {timestamp}"
        resp = requests.post(f"{BASE_URL}/documents/templates", json=data, headers={"Authorization": f"Bearer {director_token}"}, verify=VERIFY_SSL)
        if resp.status_code == 201:
            log_pass("Director created template successfully")
        else:
            log_fail(f"Director failed to create template: {resp.status_code}")
    
    # 3. Test as DSP (Should Fail)
    if dsp_token:
        resp = requests.post(f"{BASE_URL}/documents/templates", json=data, headers={"Authorization": f"Bearer {dsp_token}"}, verify=VERIFY_SSL)
        if resp.status_code == 403:
            log_pass("DSP blocked from creating template (403 Forbidden)")
        else:
            log_fail(f"DSP was NOT blocked from creating template: {resp.status_code}")

def test_client_document_creation_rbac(dsp_token, client_id, template_id):
    print("\n--- Testing Client Document Creation RBAC ---")
    
    if not dsp_token:
        print("Skipping (no DSP token)")
        return

    data = {
        "template_id": template_id,
        "values": {"test": "value"},
        "revision_notes": "Attempt by DSP"
    }
    
    resp = requests.post(
        f"{BASE_URL}/clients/{client_id}/documents", 
        json=data, 
        headers={"Authorization": f"Bearer {dsp_token}"}, 
        verify=VERIFY_SSL
    )
    
    if resp.status_code == 403:
        log_pass("DSP blocked from creating client document (403 Forbidden)")
    else:
        log_fail(f"DSP was NOT blocked from creating client document: {resp.status_code} {resp.text}")

def test_client_document_review_rbac(dsp_token, client_id, document_id):
    print("\n--- Testing Client Document Review RBAC ---")
    
    if not dsp_token:
        print("Skipping (no DSP token)")
        return

    resp = requests.post(
        f"{BASE_URL}/clients/{client_id}/documents/{document_id}/review", 
        json={"notes": "Illegal review"}, 
        headers={"Authorization": f"Bearer {dsp_token}"}, 
        verify=VERIFY_SSL
    )
    
    if resp.status_code == 403:
        log_pass("DSP blocked from reviewing document (403 Forbidden)")
    else:
        log_fail(f"DSP was NOT blocked from reviewing document: {resp.status_code} {resp.text}")

def test_site_director_scoping(sitedir_token, valid_client_id, invalid_client_id):
    print("\n--- Testing Site Director Scoping ---")
    
    if not sitedir_token:
        print("Skipping (no Site Director token)")
        return

    # 1. Valid Access
    resp = requests.get(
        f"{BASE_URL}/clients/{valid_client_id}/documents",
        headers={"Authorization": f"Bearer {sitedir_token}"},
        verify=VERIFY_SSL
    )
    if resp.status_code == 200:
        log_pass(f"Site Director accessed valid client {valid_client_id}")
    else:
        log_fail(f"Site Director failed to access valid client {valid_client_id}: {resp.status_code}")

    # 2. Invalid Access (Different Location)
    # Assuming invalid_client_id corresponds to a client at a different location
    if invalid_client_id:
        resp = requests.get(
            f"{BASE_URL}/clients/{invalid_client_id}/documents",
            headers={"Authorization": f"Bearer {sitedir_token}"},
            verify=VERIFY_SSL
        )
        if resp.status_code == 403:
            log_pass(f"Site Director blocked from invalid client {invalid_client_id}")
        else:
            log_fail(f"Site Director was NOT blocked from invalid client {invalid_client_id}: {resp.status_code}")

def main():
    print("Running RBAC Tests...")
    
    # 1. Authenticate
    admin_token = get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
    director_token = get_auth_token(DIRECTOR_EMAIL, DIRECTOR_PASSWORD)
    dsp_token = get_auth_token(DSP_EMAIL, DSP_PASSWORD)
    sitedir_token = get_auth_token(SITEDIR_EMAIL, SITEDIR_PASSWORD)
    
    if not dsp_token:
        print("WARNING: Could not login as DSP. Some tests will be skipped. Update passwords in script.")
    if not director_token:
        print("WARNING: Could not login as Director. Some tests will be skipped. Ensure David Director is adding in seed data.")

    # Setup - Get a template ID and Client ID
    template_id = 1 # Assuming seed data
    client_id = 1   # Jason Miller (Scott House)
    doc_id = 1      # Jason's All About Me
    
    # RBAC Tests
    test_template_creation_rbac(admin_token, director_token, dsp_token)
    test_client_document_creation_rbac(dsp_token, client_id, template_id)
    test_client_document_review_rbac(dsp_token, client_id, doc_id)
    
    if sitedir_token:
        # 1. Site Director Scoping (Existing)
        test_site_director_scoping(sitedir_token, 1, None) 
        
        # 2. Site Director Template Creation (Should FAIL - blocked by role)
        print("\n--- Testing Site Director Template Creation (Negative) ---")
        try:
             resp = requests.post(
                 f"{BASE_URL}/documents/templates", 
                 json={"name": "SD Template", "category_id": 1, "form_schema": {}}, 
                 headers={"Authorization": f"Bearer {sitedir_token}"}, 
                 verify=VERIFY_SSL
             )
             if resp.status_code == 403:
                 log_pass("Site Director blocked from creating template (403 Forbidden)")
             else:
                 log_fail(f"Site Director NOT blocked from creating template: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

        # 3. Site Director Client Document Creation (Should PASS for assigned client)
        print("\n--- Testing Site Director Client Document Creation (Positive) ---")
        try:
             # Jason Miller (1) is at Scott House (1), where Joseph Davis is Site Director
             resp = requests.post(
                 f"{BASE_URL}/clients/1/documents", 
                 json={"template_id": 1, "values": {"test": "val"}, "revision_notes": "SD Created"}, 
                 headers={"Authorization": f"Bearer {sitedir_token}"}, 
                 verify=VERIFY_SSL
             )
             if resp.status_code == 201:
                 log_pass("Site Director created document for assigned client")
             else:
                 log_fail(f"Site Director failed to create document: {resp.status_code} {resp.text}")
        except Exception as e:
             print(f"Error: {e}") 
    
if __name__ == "__main__":
    main()
