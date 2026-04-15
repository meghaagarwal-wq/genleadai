#!/usr/bin/env python3
"""
ARIA 3-Phase Sales PA Backend API Testing
Tests all new ARIA endpoints and existing functionality
"""

import requests
import json
import sys
from datetime import datetime

class AriaAPITester:
    def __init__(self, base_url="https://pipeline-pro-96.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
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

    def make_request(self, method, endpoint, data=None, expected_status=200):
        """Make API request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            success = response.status_code == expected_status
            return success, response.json() if success else {}, response.status_code
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
            self.log_result("Admin Login", False, f"Status: {status}")
            return False

    def test_create_test_lead(self):
        """Create a test lead for ARIA testing"""
        lead_data = {
            "lead_type": "B2B",
            "first_name": "John",
            "last_name": "TestLead",
            "email": "john.testlead@example.com",
            "phone": "+1234567890",
            "company_name": "Test Corp",
            "job_title": "CEO",
            "industry": "Technology",
            "revenue_range": "$1M-$5M",
            "city": "San Francisco",
            "state": "CA",
            "country": "USA",
            "source_channel": "website_form",
            "status": "new",
            "notes": "Test lead for ARIA functionality"
        }
        
        success, response, status = self.make_request('POST', 'leads', lead_data, 200)
        if success and 'id' in response:
            self.test_lead_id = response['id']
            self.log_result("Create Test Lead", True)
            return True
        else:
            # Debug the response
            print(f"Debug - Status: {status}, Response: {response}")
            self.log_result("Create Test Lead", False, f"Status: {status}, Response: {response}")
            return False

    def test_aria_first_touch(self):
        """Test ARIA first touch trigger"""
        if not self.test_lead_id:
            self.log_result("ARIA First Touch", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/trigger',
            {"lead_id": self.test_lead_id, "touch_type": "first_touch"}
        )
        self.log_result("ARIA First Touch", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_research(self):
        """Test pre-call research endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Research", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/research',
            {"lead_id": self.test_lead_id}
        )
        self.log_result("ARIA Research", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_pre_call_brief(self):
        """Test pre-call brief endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Pre-Call Brief", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', f'aria/pre-call-brief/{self.test_lead_id}', None
        )
        self.log_result("ARIA Pre-Call Brief", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_pause_for_call(self):
        """Test pause for call endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Pause for Call", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', f'aria/pause-for-call/{self.test_lead_id}', None
        )
        self.log_result("ARIA Pause for Call", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_call_outcome_interested(self):
        """Test call outcome - interested"""
        if not self.test_lead_id:
            self.log_result("ARIA Call Outcome (Interested)", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/call-outcome',
            {"lead_id": self.test_lead_id, "outcome": "interested", "notes": "Great call, very interested"}
        )
        self.log_result("ARIA Call Outcome (Interested)", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_call_outcome_not_fit(self):
        """Test call outcome - not a fit"""
        if not self.test_lead_id:
            self.log_result("ARIA Call Outcome (Not a Fit)", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/call-outcome',
            {"lead_id": self.test_lead_id, "outcome": "not_a_fit", "notes": "Not the right timing"}
        )
        self.log_result("ARIA Call Outcome (Not a Fit)", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_mark_proposal_sent(self):
        """Test mark proposal sent endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Mark Proposal Sent", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', f'aria/mark-proposal-sent/{self.test_lead_id}', None
        )
        self.log_result("ARIA Mark Proposal Sent", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_proposal_followup(self):
        """Test proposal follow-up endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Proposal Follow-up", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/proposal-followup',
            {"lead_id": self.test_lead_id, "step": 1}
        )
        self.log_result("ARIA Proposal Follow-up", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_founder_instruction(self):
        """Test founder instruction endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Founder Instruction", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'POST', 'aria/founder-instruction',
            {"lead_id": self.test_lead_id, "instruction": "Don't mention pricing yet, focus on value"}
        )
        self.log_result("ARIA Founder Instruction", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_lead_phase(self):
        """Test get lead phase endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Lead Phase", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'GET', f'aria/lead-phase/{self.test_lead_id}', None
        )
        self.log_result("ARIA Lead Phase", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_weekly_summary(self):
        """Test weekly summary endpoint"""
        success, response, status = self.make_request(
            'GET', 'aria/weekly-summary', None
        )
        self.log_result("ARIA Weekly Summary", success, f"Status: {status}" if not success else "")
        return success

    def test_aria_conversation(self):
        """Test get ARIA conversation endpoint"""
        if not self.test_lead_id:
            self.log_result("ARIA Conversation", False, "No test lead available")
            return False
            
        success, response, status = self.make_request(
            'GET', f'aria/conversation/{self.test_lead_id}', None
        )
        self.log_result("ARIA Conversation", success, f"Status: {status}" if not success else "")
        return success

    def test_existing_endpoints(self):
        """Test that existing endpoints still work"""
        endpoints = [
            ('GET', 'leads', None, 200),
            ('GET', 'analytics/dashboard', None, 200),
            ('GET', 'campaigns', None, 200),
            ('GET', 'leads/your-five-today', None, 200),
            ('GET', 'leads/sleeping', None, 200),
        ]
        
        for method, endpoint, data, expected_status in endpoints:
            success, response, status = self.make_request(method, endpoint, data, expected_status)
            self.log_result(f"Existing Endpoint: {endpoint}", success, f"Status: {status}" if not success else "")

    def run_all_tests(self):
        """Run all ARIA API tests"""
        print("🚀 Starting ARIA 3-Phase Sales PA API Tests")
        print("=" * 50)
        
        # Login first
        if not self.test_login():
            print("❌ Cannot proceed without login")
            return False
        
        # Create test lead
        if not self.test_create_test_lead():
            print("❌ Cannot proceed without test lead")
            return False
        
        # Test all ARIA endpoints
        print("\n📋 Testing ARIA Endpoints:")
        self.test_aria_first_touch()
        self.test_aria_research()
        self.test_aria_pre_call_brief()
        self.test_aria_pause_for_call()
        self.test_aria_call_outcome_interested()
        self.test_aria_mark_proposal_sent()
        self.test_aria_proposal_followup()
        self.test_aria_founder_instruction()
        self.test_aria_lead_phase()
        self.test_aria_weekly_summary()
        self.test_aria_conversation()
        
        # Test call outcome not a fit (reset state)
        self.test_aria_call_outcome_not_fit()
        
        # Test existing endpoints
        print("\n🔄 Testing Existing Endpoints:")
        self.test_existing_endpoints()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = AriaAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())