"""
Test script for the updated email verification system

Run this script to test:
1. Registration with permanent verification tokens
2. Login attempt with unverified account (auto-resend)
3. Email verification
4. Successful login after verification
5. Manual resend verification email

Usage:
    python test_verification_system.py
"""

import requests
import json
import time
from datetime import datetime

# API Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/auth"

# Test user data
TEST_EMAIL = f"test_{int(time.time())}@example.com"
TEST_USERNAME = f"testuser_{int(time.time())}"
TEST_PASSWORD = "TestPass123"

def print_section(title):
    """Print a formatted section title"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def print_result(success, message, data=None):
    """Print a formatted result"""
    status = "✅ SUCCESS" if success else "❌ FAILED"
    print(f"{status}: {message}")
    if data:
        print(f"Data: {json.dumps(data, indent=2)}")
    print()

def test_registration():
    """Test user registration"""
    print_section("TEST 1: User Registration")
    
    payload = {
        "email": TEST_EMAIL,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "password_confirm": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{API_BASE}/register", json=payload)
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print_result(True, "User registered successfully", data)
            print(f"📧 Check email: {TEST_EMAIL}")
            print(f"⏰ Token valid for: 10 years (permanent)")
            return True
        else:
            print_result(False, f"Registration failed: {data.get('detail', 'Unknown error')}", data)
            return False
    except Exception as e:
        print_result(False, f"Registration error: {str(e)}")
        return False

def test_login_unverified():
    """Test login attempt with unverified account"""
    print_section("TEST 2: Login with Unverified Account (Auto-Resend)")
    
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{API_BASE}/login", json=payload)
        data = response.json()
        
        # Expected: 403 error with verification message
        if response.status_code == 403:
            print_result(True, "Correctly blocked unverified user", data)
            print("📧 New verification email should be sent automatically")
            return True
        else:
            print_result(False, f"Unexpected response: {response.status_code}", data)
            return False
    except Exception as e:
        print_result(False, f"Login error: {str(e)}")
        return False

def test_manual_resend():
    """Test manual verification email resend"""
    print_section("TEST 3: Manual Resend Verification Email")
    
    payload = {
        "email": TEST_EMAIL
    }
    
    try:
        response = requests.post(f"{API_BASE}/resend-verification", json=payload)
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print_result(True, "Verification email resent", data)
            return True
        else:
            print_result(False, f"Resend failed: {data.get('detail', 'Unknown error')}", data)
            return False
    except Exception as e:
        print_result(False, f"Resend error: {str(e)}")
        return False

def test_verification(token):
    """Test email verification with token"""
    print_section("TEST 4: Email Verification")
    
    try:
        response = requests.get(f"{API_BASE}/verify-email?token={token}")
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print_result(True, "Email verified successfully", data)
            return True
        else:
            print_result(False, f"Verification failed: {data.get('detail', 'Unknown error')}", data)
            return False
    except Exception as e:
        print_result(False, f"Verification error: {str(e)}")
        return False

def test_login_verified():
    """Test login with verified account"""
    print_section("TEST 5: Login with Verified Account")
    
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{API_BASE}/login", json=payload)
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print_result(True, "Login successful", data)
            return True
        else:
            print_result(False, f"Login failed: {data.get('detail', 'Unknown error')}", data)
            return False
    except Exception as e:
        print_result(False, f"Login error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "🧪" * 30)
    print("  EMAIL VERIFICATION SYSTEM TEST SUITE")
    print("  Testing permanent tokens + auto-resend functionality")
    print("🧪" * 30)
    
    print(f"\n📝 Test User Details:")
    print(f"   Email: {TEST_EMAIL}")
    print(f"   Username: {TEST_USERNAME}")
    print(f"   Password: {TEST_PASSWORD}")
    
    # Run tests
    results = []
    
    # Test 1: Registration
    results.append(("Registration", test_registration()))
    
    if not results[0][1]:
        print("\n❌ Cannot continue tests - registration failed")
        return
    
    # Wait a moment for database operations
    time.sleep(1)
    
    # Test 2: Login unverified (should auto-resend)
    results.append(("Login Unverified", test_login_unverified()))
    
    # Test 3: Manual resend
    results.append(("Manual Resend", test_manual_resend()))
    
    # Test 4 & 5 require manual verification
    print_section("MANUAL STEP REQUIRED")
    print("⏸️  Tests paused. Please complete the following steps:")
    print("\n1. Check the email inbox (or backend logs if SendGrid not configured)")
    print("2. Find the verification token from the email")
    print("3. Enter the token below to continue testing")
    print("\n💡 Token format: 64-character random string")
    print("💡 Example: abc123xyz456...")
    print()
    
    token = input("Enter verification token (or 'skip' to end tests): ").strip()
    
    if token.lower() == 'skip':
        print("\n⏭️  Skipping verification tests")
    else:
        # Test 4: Verification
        results.append(("Email Verification", test_verification(token)))
        
        # Test 5: Login verified
        if results[-1][1]:
            time.sleep(1)
            results.append(("Login Verified", test_login_verified()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}\n")
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print("\n" + "=" * 60)
    
    if passed == total:
        print("🎉 All tests passed! Email verification system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
    
    print("=" * 60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
