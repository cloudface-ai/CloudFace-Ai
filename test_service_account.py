#!/usr/bin/env python3
"""
Test script for service account setup
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env', override=True)

def test_service_account():
    """Test if service account is properly configured"""
    try:
        from service_account_drive import get_service_account_access_token, get_bot_service_account_email
        
        print("🔍 Testing service account setup...")
        
        # Check environment variables
        json_path = os.getenv('SERVICE_ACCOUNT_JSON_PATH')
        bot_email = os.getenv('BOT_SERVICE_ACCOUNT_EMAIL')
        
        print(f"📁 Service account JSON path: {json_path}")
        print(f"📧 Bot email from env: {bot_email}")
        
        # Check if JSON file exists
        if not json_path or not os.path.exists(json_path):
            print("❌ Service account JSON file not found!")
            print("   Please:")
            print("   1. Create a service account in Google Cloud Console")
            print("   2. Download the JSON key file")
            print("   3. Save it as 'service-account.json' in this directory")
            print("   4. Update SERVICE_ACCOUNT_JSON_PATH in .env")
            return False
        
        # Try to get bot email from JSON
        try:
            bot_email_from_json = get_bot_service_account_email()
            print(f"📧 Bot email from JSON: {bot_email_from_json}")
        except Exception as e:
            print(f"⚠️  Could not read bot email from JSON: {e}")
        
        # Try to get access token
        try:
            print("🔑 Getting access token...")
            token = get_service_account_access_token()
            print(f"✅ Access token obtained: {token[:20]}...")
            return True
        except Exception as e:
            print(f"❌ Failed to get access token: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Run: pip install google-auth==2.35.0 google-auth-httplib2==0.2.0 google-auth-oauthlib==1.2.1")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_drive_access():
    """Test if we can access Google Drive with service account"""
    try:
        from service_account_drive import get_service_account_access_token
        import requests
        
        print("\n🔍 Testing Google Drive access...")
        
        token = get_service_account_access_token()
        
        # Test Drive API access
        url = "https://www.googleapis.com/drive/v3/about"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'fields': 'user'}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Drive access successful!")
            print(f"   User: {data.get('user', {}).get('emailAddress', 'Unknown')}")
            return True
        else:
            print(f"❌ Drive access failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Drive access error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 CloudFace AI - Service Account Test")
    print("=" * 50)
    
    # Test 1: Service account setup
    if not test_service_account():
        print("\n❌ Service account setup failed!")
        sys.exit(1)
    
    # Test 2: Drive access
    if not test_drive_access():
        print("\n❌ Drive access failed!")
        sys.exit(1)
    
    print("\n✅ All tests passed! Service account is ready to use.")
    print("\n📋 Next steps:")
    print("   1. Share a Google Drive folder with your bot email")
    print("   2. Test the new endpoint: /process_drive_shared")
    print("   3. Use the folder URL in your app")
