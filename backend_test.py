#!/usr/bin/env python3
"""
Lead Ingestion System Backend API Testing
Tests all new lead ingestion endpoints and existing functionality
"""

import requests
import json
import sys
from datetime import datetime

class LeadIngestionAPITester:
    def __init__(self, base_url="https://pipeline-pro-96.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.api_key = None
        self.test_lead_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            print(f"❌ {test_name} - {details}")
            self.failed_tests.append(f"{test_name}: {details}")

    def make_request(self, method, endpoint, data=None, expected_status=200, headers=None):
        """Make API request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        request_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            request_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            request_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=request_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=request_headers)
            
            success = response.status_code == expected_status
            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {"raw_response": response.text}
            
            return success, response_data, response.status_code
        except Exception as e:
            return False, {}, f"Error: {str(e)}"

    def test_login(self):
        """Test admin login"""
        success, response, status = self.make_request(
            'POST', 'auth/login', 
            {"email": "admin@demo.com", "password": "Demo1234!"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log_result("Admin Login", True)
            return True
        else:
            self.log_result("Admin Login", False, f"Status: {status}, Response: {response}")
            return False

    def test_create_api_key(self):
        """Test API key creation"""
        success, response, status = self.make_request(
            'POST', 'settings/api-keys',
            {"name": "Test Integration Key"}
        )
        if success and 'key' in response:
            self.api_key = response['key']
            self.log_result("Create API Key", True)
            return True
        else:
            self.log_result("Create API Key", False, f"Status: {status}, Response: {response}")
            return False

    def test_list_api_keys(self):
        """Test API key listing"""
        success, response, status = self.make_request('GET', 'settings/api-keys')
        if success and 'keys' in response:
            self.log_result("List API Keys", True)
            return True
        else:
            self.log_result("List API Keys", False, f"Status: {status}, Response: {response}")
            return False

    def test_api_lead_creation_with_key(self):
        """Test lead creation via API with API key"""
        if not self.api_key:
            self.log_result("API Lead Creation (with key)", False, "No API key available")
            return False
            
        lead_data = {
            "first_name": "Jane",
            "last_name": "APILead",
            "email": "jane.apilead@example.com",
            "phone": "+1987654321",
            "company_name": "API Corp",
            "source": "zapier_integration",
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "test_campaign"
        }
        
        headers = {"X-API-Key": self.api_key}
        success, response, status = self.make_request(
            'POST', 'v1/leads', lead_data, 200, headers
        )
        if success:
            self.log_result("API Lead Creation (with key)", True)
            return True
        else:
            self.log_result("API Lead Creation (with key)", False, f"Status: {status}, Response: {response}")
            return False

    def test_api_lead_creation_duplicate(self):
        """Test duplicate lead handling via API"""
        if not self.api_key:
            self.log_result("API Lead Creation (duplicate)", False, "No API key available")
            return False
            
        lead_data = {
            "first_name": "Jane",
            "last_name": "APILead",
            "email": "jane.apilead@example.com",  # Same email as previous test
            "phone": "+1987654321",
            "company_name": "API Corp",
            "source": "zapier_integration"
        }
        
        headers = {"X-API-Key": self.api_key}
        success, response, status = self.make_request(
            'POST', 'v1/leads', lead_data, 200, headers
        )
        if success and response.get('status') == 'duplicate':
            self.log_result("API Lead Creation (duplicate)", True)
            return True
        else:
            self.log_result("API Lead Creation (duplicate)", False, f"Status: {status}, Response: {response}")
            return False

    def test_api_lead_creation_without_key(self):
        """Test lead creation via API without API key (should fail)"""
        lead_data = {
            "first_name": "Unauthorized",
            "last_name": "User",
            "email": "unauthorized@example.com",
            "source": "unauthorized_attempt"
        }
        
        success, response, status = self.make_request(
            'POST', 'v1/leads', lead_data, 401
        )
        if success:  # Success means we got the expected 401
            self.log_result("API Lead Creation (no key)", True)
            return True
        else:
            self.log_result("API Lead Creation (no key)", False, f"Expected 401, got {status}")
            return False

    def test_form_submit_public(self):
        """Test public form submission (no auth needed)"""
        form_data = {
            "first_name": "Public",
            "last_name": "FormUser",
            "email": "public.form@example.com",
            "phone": "+1555123456",
            "company_name": "Form Corp",
            "message": "Interested in your services",
            "utm_source": "website",
            "utm_medium": "organic",
            "utm_campaign": "homepage"
        }
        
        # Remove auth token for this test
        temp_token = self.token
        self.token = None
        
        success, response, status = self.make_request(
            'POST', 'form/submit', form_data, 200
        )
        
        # Restore token
        self.token = temp_token
        
        if success:
            self.log_result("Form Submit (public)", True)
            return True
        else:
            self.log_result("Form Submit (public)", False, f"Status: {status}, Response: {response}")
            return False

    def test_form_submit_duplicate(self):
        """Test public form submission with duplicate email"""
        form_data = {
            "first_name": "Public",
            "last_name": "FormUser",
            "email": "public.form@example.com",  # Same email as previous test
            "phone": "+1555123456",
            "company_name": "Form Corp",
            "message": "Another submission"
        }
        
        # Remove auth token for this test
        temp_token = self.token
        self.token = None
        
        success, response, status = self.make_request(
            'POST', 'form/submit', form_data, 200
        )
        
        # Restore token
        self.token = temp_token
        
        if success:
            self.log_result("Form Submit (duplicate)", True)
            return True
        else:
            self.log_result("Form Submit (duplicate)", False, f"Status: {status}, Response: {response}")
            return False

    def test_embed_code_generation(self):
        """Test embed code generation"""
        success, response, status = self.make_request('GET', 'form/embed-code')
        if success and 'embed_code' in response:
            self.log_result("Embed Code Generation", True)
            return True
        else:
            self.log_result("Embed Code Generation", False, f"Status: {status}, Response: {response}")
            return False

    def test_calendly_webhook(self):
        """Test Calendly webhook endpoint"""
        webhook_data = {
            "event": "invitee.created",
            "payload": {
                "event_type": {
                    "name": "30 Minute Meeting"
                },
                "invitee": {
                    "name": "John Doe",
                    "email": "john.doe@example.com"
                },
                "event": {
                    "start_time": "2025-01-15T10:00:00Z",
                    "end_time": "2025-01-15T10:30:00Z"
                }
            }
        }
        
        # Remove auth token for webhook test
        temp_token = self.token
        self.token = None
        
        success, response, status = self.make_request(
            'POST', 'webhooks/calendly', webhook_data, 200
        )
        
        # Restore token
        self.token = temp_token
        
        if success:
            self.log_result("Calendly Webhook", True)
            return True
        else:
            self.log_result("Calendly Webhook", False, f"Status: {status}, Response: {response}")
            return False

    def test_meta_leads_webhook(self):
        """Test Meta Lead Ads webhook endpoint"""
        webhook_data = {
            "object": "page",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "leadgen_id": "987654321",
                        "page_id": "123456789",
                        "form_id": "456789123",
                        "adgroup_id": "789123456",
                        "ad_id": "321654987",
                        "created_time": "2025-01-15T10:00:00+0000"
                    },
                    "field": "leadgen"
                }]
            }]
        }
        
        # Remove auth token for webhook test
        temp_token = self.token
        self.token = None
        
        success, response, status = self.make_request(
            'POST', 'webhooks/meta-leads', webhook_data, 200
        )
        
        # Restore token
        self.token = temp_token
        
        if success:
            self.log_result("Meta Leads Webhook", True)
            return True
        else:
            self.log_result("Meta Leads Webhook", False, f"Status: {status}, Response: {response}")
            return False

    def test_existing_endpoints(self):
        """Test that existing endpoints still work"""
        endpoints = [
            ('GET', 'leads', None, 200),
            ('GET', 'analytics/dashboard', None, 200),
            ('GET', 'campaigns', None, 200),
            ('GET', 'leads/your-five-today', None, 200),
            ('GET', 'leads/sleeping', None, 200),
            ('GET', 'users', None, 200),
            ('GET', 'health', None, 200),
        ]
        
        for method, endpoint, data, expected_status in endpoints:
            success, response, status = self.make_request(method, endpoint, data, expected_status)
            self.log_result(f"Existing Endpoint: {endpoint}", success, f"Status: {status}" if not success else "")

    def run_all_tests(self):
        """Run all lead ingestion API tests"""
        print("🚀 Starting Lead Ingestion System API Tests")
        print("=" * 60)
        
        # Login first
        if not self.test_login():
            print("❌ Cannot proceed without login")
            return False
        
        # Test API key management
        print("\n🔑 Testing API Key Management:")
        self.test_create_api_key()
        self.test_list_api_keys()
        
        # Test API lead ingestion
        print("\n📥 Testing API Lead Ingestion:")
        self.test_api_lead_creation_with_key()
        self.test_api_lead_creation_duplicate()
        self.test_api_lead_creation_without_key()
        
        # Test public form submission
        print("\n📝 Testing Public Form Submission:")
        self.test_form_submit_public()
        self.test_form_submit_duplicate()
        self.test_embed_code_generation()
        
        # Test webhook endpoints
        print("\n🔗 Testing Webhook Endpoints:")
        self.test_calendly_webhook()
        self.test_meta_leads_webhook()
        
        # Test existing endpoints
        print("\n🔄 Testing Existing Endpoints:")
        self.test_existing_endpoints()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = LeadIngestionAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())