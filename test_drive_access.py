#!/usr/bin/env python3
"""
Test Google Drive access with service account
"""

import os
import requests
from dotenv import load_dotenv
from service_account_drive import get_service_account_access_token

load_dotenv('.env', override=True)

def test_folder_access():
    """Test if we can access a specific folder"""
    folder_id = "1-Xq16DoPaHTmca7Mpi36zIz677dCmbv6"
    
    try:
        token = get_service_account_access_token()
        print(f"✅ Got token: {token[:20]}...")
        
        # Test 1: Try to get folder metadata
        print(f"\n🔍 Testing folder metadata access...")
        url = f"https://www.googleapis.com/drive/v3/files/{folder_id}"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'fields': 'id,name,mimeType,parents,permissions'}
        
        response = requests.get(url, headers=headers, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Folder found: {data.get('name')}")
            print(f"📁 Type: {data.get('mimeType')}")
            print(f"👥 Permissions: {len(data.get('permissions', []))}")
            
            # Test 2: Try to list folder contents
            print(f"\n🔍 Testing folder contents access...")
            url = "https://www.googleapis.com/drive/v3/files"
            params = {
                'q': f"'{folder_id}' in parents and trashed=false",
                'fields': 'files(id,name,mimeType)',
                'pageSize': 10
            }
            
            response = requests.get(url, headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                files = data.get('files', [])
                print(f"✅ Found {len(files)} files in folder")
                for file in files[:3]:  # Show first 3 files
                    print(f"   📄 {file['name']} ({file['mimeType']})")
            else:
                print(f"❌ Cannot list folder contents")
        else:
            print(f"❌ Cannot access folder")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_shared_files():
    """Test if we can see any shared files"""
    try:
        token = get_service_account_access_token()
        print(f"\n🔍 Testing shared files access...")
        
        url = "https://www.googleapis.com/drive/v3/files"
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'q': 'sharedWithMe=true',
            'fields': 'files(id,name,mimeType)',
            'pageSize': 10
        }
        
        response = requests.get(url, headers=headers, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Found {len(files)} shared files")
            for file in files[:3]:
                print(f"   📄 {file['name']} ({file['mimeType']})")
        else:
            print(f"❌ Cannot access shared files")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Testing Google Drive Access with Service Account")
    print("=" * 60)
    
    test_folder_access()
    test_shared_files()
    
    print("\n" + "=" * 60)
    print("💡 If both tests fail, the service account needs to be granted access")
    print("   to the Google Drive API and the specific folder.")
