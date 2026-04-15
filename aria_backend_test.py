#!/usr/bin/env python3
"""
Backend API Testing for GenLeadAI LMS - ARIA AI Sales Agent Features
Testing ARIA endpoints, Calendly integration, and Asset Library
"""

import requests
import json
import sys
from datetime import datetime

class AriaAPITester:
    def __init__(self, base_url="https://pipeline-pro-96.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, test_name, success, details="", response_data=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            print(f"❌ {test_name} - {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            response_data = None
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text[:200]}

            if success:
                self.log_result(name, True, f"Status: {response.status_code}", response_data)
            else:
                self.log_result(name, False, f"Expected {expected_status}, got {response.status_code}", response_data)

            return success, response_data

        except Exception as e:
            self.log_result(name, False, f"Error: {str(e)}")
            return False, {}

    def test_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": "admin@demo.com", "password": "Demo1234!"}
        )
        if success and 'token' in response:
            self.token = response['token']
            return True
        return False

    def test_aria_settings(self):
        """Test ARIA settings endpoint"""
        success, response = self.run_test(
            "ARIA Settings - GET",
            "GET",
            "api/aria/settings",
            200
        )
        
        if success:
            # Verify expected settings fields
            expected_fields = ['enabled', 'persona_name', 'founder_name', 'company_name', 'max_messages_per_lead']
            missing_fields = [field for field in expected_fields if field not in response]
            if missing_fields:
                self.log_result("ARIA Settings - Field Validation", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("ARIA Settings - Field Validation", True, "All expected fields present")
        
        return success

    def test_aria_analytics(self):
        """Test ARIA analytics endpoint"""
        success, response = self.run_test(
            "ARIA Analytics",
            "GET",
            "api/aria/analytics",
            200
        )
        
        if success:
            # Verify expected analytics fields
            expected_fields = ['total_conversations', 'reply_rate', 'booking_rate', 'meetings_booked']
            missing_fields = [field for field in expected_fields if field not in response]
            if missing_fields:
                self.log_result("ARIA Analytics - Field Validation", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("ARIA Analytics - Field Validation", True, "All expected analytics fields present")
        
        return success

    def test_aria_feed(self):
        """Test ARIA live feed endpoint"""
        success, response = self.run_test(
            "ARIA Live Feed",
            "GET",
            "api/aria/feed",
            200
        )
        
        if success and 'feed' in response:
            feed_count = len(response['feed'])
            self.log_result("ARIA Feed - Data Structure", True, f"Found {feed_count} feed items")
        
        return success

    def test_calendly_integration(self):
        """Test Calendly integration endpoints"""
        # Test Calendly user
        success1, response1 = self.run_test(
            "Calendly User Info",
            "GET",
            "api/calendly/user",
            200
        )
        
        # Test Calendly event types
        success2, response2 = self.run_test(
            "Calendly Event Types",
            "GET",
            "api/calendly/event-types",
            200
        )
        
        if success1 and 'user' in response1:
            self.log_result("Calendly User - Data Validation", True, "User data retrieved")
        
        if success2 and 'event_types' in response2:
            event_count = len(response2['event_types'])
            self.log_result("Calendly Event Types - Data Validation", True, f"Found {event_count} event types")
        
        return success1 and success2

    def test_assets_endpoint(self):
        """Test assets endpoint"""
        success, response = self.run_test(
            "Assets Library",
            "GET",
            "api/assets",
            200
        )
        
        if success and 'assets' in response:
            asset_count = len(response['assets'])
            self.log_result("Assets - Data Structure", True, f"Found {asset_count} assets")
        
        return success

    def test_aria_conversation(self, lead_id="69df622290153afe8234ab89"):
        """Test ARIA conversation endpoint with existing lead"""
        success, response = self.run_test(
            f"ARIA Conversation - Lead {lead_id}",
            "GET",
            f"api/aria/conversation/{lead_id}",
            200
        )
        
        if success:
            # Check conversation structure
            if 'conversation' in response and 'aria_state' in response:
                conversation_count = len(response['conversation'])
                aria_state = response['aria_state']
                self.log_result("ARIA Conversation - Structure", True, f"Found {conversation_count} messages, state: {aria_state}")
            else:
                self.log_result("ARIA Conversation - Structure", False, "Missing conversation or aria_state fields")
        
        return success

    def test_aria_trigger(self, lead_id="69df622290153afe8234ab89"):
        """Test ARIA trigger endpoint (careful - this sends real emails)"""
        print(f"\n⚠️  ARIA Trigger test will send real email to lead {lead_id}")
        
        # First get lead info to see current state
        lead_success, lead_response = self.run_test(
            f"Get Lead {lead_id} for ARIA Test",
            "GET",
            f"api/leads/{lead_id}",
            200
        )
        
        if not lead_success:
            self.log_result("ARIA Trigger - Lead Not Found", False, f"Cannot find lead {lead_id}")
            return False
        
        # Check if lead already has ARIA conversation
        conv_success, conv_response = self.run_test(
            f"Check ARIA State for Lead {lead_id}",
            "GET",
            f"api/aria/conversation/{lead_id}",
            200
        )
        
        if conv_success and conv_response.get('conversation'):
            self.log_result("ARIA Trigger - Skip (Already Active)", True, f"Lead already has ARIA conversation, skipping trigger test")
            return True
        
        # Trigger ARIA first touch
        success, response = self.run_test(
            "ARIA Trigger - First Touch",
            "POST",
            "api/aria/trigger",
            200,
            data={"lead_id": lead_id, "touch_type": "first_touch"}
        )
        
        if success:
            # Verify response structure
            expected_fields = ['message', 'action', 'aria_state']
            missing_fields = [field for field in expected_fields if field not in response]
            if missing_fields:
                self.log_result("ARIA Trigger - Response Structure", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("ARIA Trigger - Response Structure", True, "All expected fields present")
        
        return success

    def test_aria_reply(self, lead_id="69df622290153afe8234ab89"):
        """Test ARIA reply endpoint"""
        success, response = self.run_test(
            "ARIA Reply Processing",
            "POST",
            "api/aria/reply",
            200,
            data={"lead_id": lead_id, "message": "Hi, I'm interested in learning more about your services. What's your pricing?"}
        )
        
        if success:
            # Verify response structure
            expected_fields = ['message', 'action']
            missing_fields = [field for field in expected_fields if field not in response]
            if missing_fields:
                self.log_result("ARIA Reply - Response Structure", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("ARIA Reply - Response Structure", True, "ARIA generated response successfully")
        
        return success

    def run_all_tests(self):
        """Run comprehensive ARIA API tests"""
        print("🚀 Starting ARIA AI Sales Agent API Tests")
        print("=" * 60)
        
        # Login first
        if not self.test_login():
            print("❌ Login failed, stopping tests")
            return False
        
        # Test ARIA core endpoints
        self.test_aria_settings()
        self.test_aria_analytics()
        self.test_aria_feed()
        
        # Test integrations
        self.test_calendly_integration()
        self.test_assets_endpoint()
        
        # Test ARIA conversation features
        self.test_aria_conversation()
        
        # Test ARIA AI functionality (be careful with real API calls)
        # self.test_aria_trigger()  # Commented out to avoid sending real emails during testing
        # self.test_aria_reply()    # Commented out to avoid real AI API calls
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 ARIA API Tests Summary")
        print(f"Tests passed: {self.tests_passed}/{self.tests_run}")
        print(f"Success rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Save detailed results
        with open('/app/test_results_aria_backend.json', 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": self.tests_run,
                    "passed_tests": self.tests_passed,
                    "success_rate": f"{(self.tests_passed/self.tests_run)*100:.1f}%",
                    "timestamp": datetime.now().isoformat()
                },
                "test_results": self.test_results
            }, f, indent=2)
        
        return self.tests_passed == self.tests_run

def main():
    tester = AriaAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())