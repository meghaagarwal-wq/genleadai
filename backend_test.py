import requests
import sys
import json
from datetime import datetime

class GenLeadAITester:
    def __init__(self, base_url="https://pipeline-pro-96.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                self.log_test(name, True)
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                self.log_test(name, False, f"Expected {expected_status}, got {response.status_code} - {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log_test(name, False, f"Request failed: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_login(self, email="admin@demo.com", password="Demo1234!"):
        """Test login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": email, "password": password}
        )
        
        if success and 'token' in response:
            self.token = response['token']
            print(f"🔑 Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "api/auth/me",
            200
        )
        return success

    def test_get_leads(self):
        """Test get leads endpoint"""
        success, response = self.run_test(
            "Get Leads",
            "GET",
            "api/leads?limit=10",
            200
        )
        
        if success and 'leads' in response:
            lead_count = len(response['leads'])
            total = response.get('total', 0)
            print(f"📊 Found {lead_count} leads (total: {total})")
            return True, response
        return False, {}

    def test_create_lead(self):
        """Test create lead"""
        test_lead = {
            "lead_type": "B2B",
            "first_name": "Test",
            "last_name": "Lead",
            "email": f"test.lead.{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+1234567890",
            "company_name": "Test Company",
            "job_title": "CEO",
            "industry": "Technology",
            "source_channel": "website_form",
            "notes": "Test lead created by automation"
        }
        
        success, response = self.run_test(
            "Create Lead",
            "POST",
            "api/leads",
            200,
            data=test_lead
        )
        
        if success and 'id' in response:
            print(f"📝 Created lead with ID: {response['id']}")
            return True, response['id']
        return False, None

    def test_get_lead_detail(self, lead_id):
        """Test get single lead"""
        success, response = self.run_test(
            "Get Lead Detail",
            "GET",
            f"api/leads/{lead_id}",
            200
        )
        return success

    def test_update_lead(self, lead_id):
        """Test update lead"""
        update_data = {
            "status": "contacted",
            "notes": "Updated by automation test"
        }
        
        success, response = self.run_test(
            "Update Lead",
            "PATCH",
            f"api/leads/{lead_id}",
            200,
            data=update_data
        )
        return success

    def test_create_activity(self, lead_id):
        """Test create activity"""
        activity_data = {
            "lead_id": lead_id,
            "activity_type": "call",
            "subject": "Test call",
            "body": "Automated test call activity",
            "outcome": "positive",
            "duration_minutes": 15
        }
        
        success, response = self.run_test(
            "Create Activity",
            "POST",
            "api/activities",
            200,
            data=activity_data
        )
        return success

    def test_get_lead_activities(self, lead_id):
        """Test get lead activities"""
        success, response = self.run_test(
            "Get Lead Activities",
            "GET",
            f"api/leads/{lead_id}/activities",
            200
        )
        return success

    def test_get_campaigns(self):
        """Test get campaigns"""
        success, response = self.run_test(
            "Get Campaigns",
            "GET",
            "api/campaigns",
            200
        )
        
        if success and 'campaigns' in response:
            campaign_count = len(response['campaigns'])
            print(f"🎯 Found {campaign_count} campaigns")
            return True
        return False

    def test_create_campaign(self):
        """Test create campaign"""
        campaign_data = {
            "name": f"Test Campaign {datetime.now().strftime('%H%M%S')}",
            "description": "Automated test campaign",
            "channel": "linkedin",
            "lead_type": "B2B",
            "status": "draft",
            "budget": 5000,
            "target_audience": "SaaS companies",
            "goal_leads": 100
        }
        
        success, response = self.run_test(
            "Create Campaign",
            "POST",
            "api/campaigns",
            200,
            data=campaign_data
        )
        return success

    def test_get_users(self):
        """Test get users"""
        success, response = self.run_test(
            "Get Users",
            "GET",
            "api/users",
            200
        )
        
        if success and 'users' in response:
            user_count = len(response['users'])
            print(f"👥 Found {user_count} users")
            return True
        return False

    def test_dashboard_analytics(self):
        """Test dashboard analytics"""
        success, response = self.run_test(
            "Dashboard Analytics",
            "GET",
            "api/analytics/dashboard",
            200
        )
        
        if success:
            total_leads = response.get('total_leads', 0)
            print(f"📈 Analytics: {total_leads} total leads")
            return True
        return False

    def test_ai_score_lead(self, lead_id):
        """Test AI scoring (may take time)"""
        print("🤖 Testing AI scoring (this may take 10-15 seconds)...")
        
        success, response = self.run_test(
            "AI Score Lead",
            "POST",
            "api/ai/score",
            200,
            data={"lead_id": lead_id}
        )
        
        if success:
            score = response.get('score', 0)
            tier = response.get('tier', 'unknown')
            print(f"🎯 AI Score: {score} ({tier})")
            return True
        return False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NEW MODULE TESTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def test_your_five_today(self):
        """Test Your 5 Today endpoint"""
        success, response = self.run_test(
            "Your 5 Today",
            "GET",
            "api/leads/your-five-today",
            200
        )
        
        if success and 'leads' in response:
            leads = response['leads']
            print(f"⚡ Your 5 Today: {len(leads)} leads returned")
            
            # Verify each lead has required AI fields
            for i, lead in enumerate(leads[:3]):  # Check first 3
                if '_reason' not in lead:
                    self.log_test(f"Your 5 Today - Lead {i+1} missing _reason", False, "Missing AI reason field")
                    return False
                if '_suggested_action' not in lead:
                    self.log_test(f"Your 5 Today - Lead {i+1} missing _suggested_action", False, "Missing suggested action field")
                    return False
                print(f"  Lead {i+1}: {lead.get('first_name', 'Unknown')} - {lead.get('_reason', 'No reason')[:50]}...")
            
            return True
        return False

    def test_sleeping_leads(self):
        """Test Sleeping Leads endpoint"""
        success, response = self.run_test(
            "Sleeping Leads",
            "GET",
            "api/leads/sleeping?threshold_days=14",
            200
        )
        
        if success and 'leads' in response:
            leads = response['leads']
            segments = response.get('segments', {})
            print(f"😴 Sleeping Leads: {len(leads)} total")
            print(f"  Segments: sleeping={segments.get('sleeping', 0)}, at_risk={segments.get('at_risk', 0)}, cold_vault={segments.get('cold_vault', 0)}")
            
            # Verify leads have required fields
            for i, lead in enumerate(leads[:2]):  # Check first 2
                if '_days_asleep' not in lead:
                    self.log_test(f"Sleeping Leads - Lead {i+1} missing _days_asleep", False, "Missing days asleep field")
                    return False
                if '_segment' not in lead:
                    self.log_test(f"Sleeping Leads - Lead {i+1} missing _segment", False, "Missing segment field")
                    return False
            
            return True
        return False

    def test_revival_campaign(self, lead_ids):
        """Test Revival Campaign endpoint"""
        if not lead_ids:
            print("⚠️  No lead IDs available for revival campaign test")
            return True
        
        campaign_data = {
            "lead_ids": lead_ids[:2],  # Test with max 2 leads
            "angle": "check_in",
            "channel": "email"
        }
        
        success, response = self.run_test(
            "Revival Campaign",
            "POST",
            "api/leads/revival-campaign",
            200,
            data=campaign_data
        )
        
        if success:
            sent = response.get('sent', 0)
            failed = response.get('failed', 0)
            print(f"🚀 Revival Campaign: {sent} sent, {failed} failed")
            return True
        return False

    def test_intent_signals(self, lead_id):
        """Test Intent Signals endpoint"""
        if not lead_id:
            print("⚠️  No lead ID available for intent signals test")
            return True
        
        # Test firing an intent signal
        signal_data = {
            "lead_id": lead_id,
            "signal_type": "email_opened",
            "metadata": {"campaign_id": "test_campaign"}
        }
        
        success, response = self.run_test(
            "Fire Intent Signal",
            "POST",
            "api/intent-signals",
            200,
            data=signal_data
        )
        
        if success:
            print(f"📡 Intent Signal fired: {response.get('message', 'Success')}")
            
            # Test getting recent signals
            success2, response2 = self.run_test(
                "Get Recent Intent Signals",
                "GET",
                "api/intent-signals/recent",
                200
            )
            
            if success2 and 'signals' in response2:
                signals = response2['signals']
                print(f"📊 Recent signals: {len(signals)} found")
                return True
        
        return False

    def test_broadcast_preview(self):
        """Test Broadcast Preview endpoint"""
        preview_data = {
            "name": "Test Broadcast Campaign",
            "template": "Hi {{first_name}}, checking in about {{company_name}}",
            "channel": "email",
            "filters": {"icp_tier": "hot", "status": "contacted"}
        }
        
        success, response = self.run_test(
            "Broadcast Preview",
            "POST",
            "api/broadcasts/preview",
            200,
            data=preview_data
        )
        
        if success and 'previews' in response:
            previews = response['previews']
            total = response.get('total_in_segment', 0)
            print(f"📢 Broadcast Preview: {len(previews)} previews generated, {total} total in segment")
            for i, preview in enumerate(previews[:2]):
                print(f"  Preview {i+1}: {preview.get('message', 'No message')[:50]}...")
            return True
        return False

    def test_no_show_recovery(self, lead_id):
        """Test No-Show Recovery endpoint"""
        if not lead_id:
            print("⚠️  No lead ID available for no-show recovery test")
            return True
        
        recovery_data = {
            "lead_id": lead_id,
            "step": 1,
            "meeting_type": "discovery_call"
        }
        
        success, response = self.run_test(
            "No-Show Recovery",
            "POST",
            "api/leads/no-show-recovery",
            200,
            data=recovery_data
        )
        
        if success:
            print(f"🔄 No-Show Recovery: {response.get('message', 'Success')}")
            return True
        return False

    def test_aria_endpoints(self, lead_id):
        """Test ARIA endpoints"""
        if not lead_id:
            print("⚠️  No lead ID available for ARIA tests")
            return True
        
        # Test ARIA trigger
        trigger_data = {
            "lead_id": lead_id,
            "touch_type": "first_touch"
        }
        
        success, response = self.run_test(
            "ARIA Trigger",
            "POST",
            "api/aria/trigger",
            200,
            data=trigger_data
        )
        
        if success:
            print(f"🤖 ARIA Trigger: {response.get('message', 'No message')[:50]}...")
            
            # Test ARIA conversation
            success2, response2 = self.run_test(
                "ARIA Conversation",
                "GET",
                f"api/aria/conversation/{lead_id}",
                200
            )
            
            if success2:
                conversation = response2.get('conversation', [])
                print(f"💬 ARIA Conversation: {len(conversation)} messages")
                return True
        
        return False

    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting GenLeadAI LMS Backend Tests")
        print("=" * 50)
        
        # Health check
        if not self.test_health_check():
            print("❌ Health check failed - stopping tests")
            return False
        
        # Authentication
        if not self.test_login():
            print("❌ Login failed - stopping tests")
            return False
        
        if not self.test_get_me():
            print("❌ Get current user failed")
            return False
        
        # Leads
        leads_success, leads_data = self.test_get_leads()
        if not leads_success:
            print("❌ Get leads failed")
            return False
        
        # Create and test lead operations
        create_success, lead_id = self.test_create_lead()
        if create_success and lead_id:
            self.test_get_lead_detail(lead_id)
            self.test_update_lead(lead_id)
            self.test_create_activity(lead_id)
            self.test_get_lead_activities(lead_id)
            
            # Test AI scoring if we have a lead
            self.test_ai_score_lead(lead_id)
        
        # Campaigns
        self.test_get_campaigns()
        self.test_create_campaign()
        
        # Users and Analytics
        self.test_get_users()
        self.test_dashboard_analytics()
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # NEW MODULE TESTS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n🆕 Testing New Modules...")
        print("-" * 30)
        
        # Test Your 5 Today
        self.test_your_five_today()
        
        # Test Sleeping Leads
        self.test_sleeping_leads()
        
        # Get some lead IDs for testing
        lead_ids = []
        if leads_data and 'leads' in leads_data:
            lead_ids = [lead.get('id') for lead in leads_data['leads'][:3] if lead.get('id')]
        if create_success and lead_id:
            lead_ids.append(lead_id)
        
        # Test Revival Campaign
        if lead_ids:
            self.test_revival_campaign(lead_ids)
        
        # Test Intent Signals
        if lead_ids:
            self.test_intent_signals(lead_ids[0])
        
        # Test Broadcast Preview
        self.test_broadcast_preview()
        
        # Test No-Show Recovery
        if lead_ids:
            self.test_no_show_recovery(lead_ids[0])
        
        # Test ARIA endpoints
        if lead_ids:
            self.test_aria_endpoints(lead_ids[0])
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return False

def main():
    tester = GenLeadAITester()
    success = tester.run_comprehensive_test()
    
    # Save test results
    with open('/app/test_results_backend.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'tests_run': tester.tests_run,
            'tests_passed': tester.tests_passed,
            'success_rate': tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0,
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())