#!/usr/bin/env python3
"""
Google Drive Handler for Facetak
Handles downloading photos from Google Drive URLs and caching them locally
"""

import os
import requests
import time
from urllib.parse import urlparse, parse_qs
import json

def extract_file_id_from_url(drive_url):
    """Extract Google Drive file ID from various URL formats."""
    try:
        print(f"🔍 Extracting file ID from: {drive_url}")
        
        # Handle different Google Drive URL formats
        if 'drive.google.com' in drive_url:
            # Format 1: https://drive.google.com/file/d/FILE_ID/view
            if '/file/d/' in drive_url:
                file_id = drive_url.split('/file/d/')[1].split('/')[0]
                print(f"✅ Found file ID (format 1): {file_id}")
                return file_id
            
            # Format 2: https://drive.google.com/open?id=FILE_ID
            elif 'id=' in drive_url:
                parsed = urlparse(drive_url)
                file_id = parse_qs(parsed.query)['id'][0]
                print(f"✅ Found file ID (format 2): {file_id}")
                return file_id
            
            # Format 3: https://drive.google.com/drive/folders/FILE_ID
            elif '/drive/folders/' in drive_url:
                file_id = drive_url.split('/drive/folders/')[1].split('/')[0]
                print(f"✅ Found folder ID (format 3): {file_id}")
                return file_id
            
            # Format 3b: https://drive.google.com/drive/u/1/folders/FILE_ID
            elif '/drive/u/' in drive_url and '/folders/' in drive_url:
                file_id = drive_url.split('/folders/')[1].split('/')[0]
                print(f"✅ Found folder ID (format 3b): {file_id}")
                return file_id
            
            # Format 4: https://drive.google.com/uc?id=FILE_ID
            elif '/uc?id=' in drive_url:
                file_id = drive_url.split('/uc?id=')[1].split('&')[0]
                print(f"✅ Found file ID (format 4): {file_id}")
                return file_id
            
            # Format 5: https://drive.google.com/viewer?srcid=FILE_ID
            elif 'srcid=' in drive_url:
                file_id = drive_url.split('srcid=')[1].split('&')[0]
                print(f"✅ Found file ID (format 5): {file_id}")
                return file_id
            
            else:
                print(f"❌ Unrecognized Drive URL format: {drive_url}")
                return None
        else:
            print(f"❌ Not a Google Drive URL: {drive_url}")
            return None
    except Exception as e:
        print(f"❌ Error extracting file ID: {e}")
        return None

def download_drive_photo(drive_url, access_token, cache_dir="storage/cache"):
    """Download a photo from Google Drive and cache it locally."""
    try:
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Extract file ID from URL
        file_id = extract_file_id_from_url(drive_url)
        if not file_id:
            print(f"❌ Could not extract file ID from: {drive_url}")
            return None
        
        # Download file using Google Drive API
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'Facetak-Photo-Processor/1.0'
        }
        
        print(f"🔄 Downloading photo from Drive: {file_id}")
        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"drive_photo_{file_id}_{timestamp}.jpg"
        filepath = os.path.join(cache_dir, filename)
        
        # Save file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Photo downloaded and cached: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error downloading Drive photo: {e}")
        return None

def get_drive_file_info(drive_url, access_token):
    """Get information about a Google Drive file."""
    try:
        file_id = extract_file_id_from_url(drive_url)
        if not file_id:
            return None
        
        # Get file metadata
        info_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'Facetak-Photo-Processor/1.0'
        }
        
        response = requests.get(info_url, headers=headers)
        response.raise_for_status()
        
        file_info = response.json()
        return {
            'id': file_info.get('id'),
            'name': file_info.get('name'),
            'mimeType': file_info.get('mimeType'),
            'size': file_info.get('size'),
            'createdTime': file_info.get('createdTime')
        }
        
    except Exception as e:
        print(f"❌ Error getting file info: {e}")
        return None

def validate_drive_url(drive_url):
    """Validate if a URL is a valid Google Drive photo URL."""
    try:
        if not drive_url or 'drive.google.com' not in drive_url:
            return False, "Not a valid Google Drive URL"
        
        file_id = extract_file_id_from_url(drive_url)
        if not file_id:
            return False, "Could not extract file ID from URL"
        
        return True, "Valid Google Drive URL"
        
    except Exception as e:
        return False, f"Error validating URL: {e}"

def list_folder_contents(folder_url, access_token):
    """List all photos in a Google Drive folder."""
    try:
        folder_id = extract_file_id_from_url(folder_url)
        if not folder_id:
            print(f"❌ Could not extract folder ID from: {folder_url}")
            return None
        
        # List files in the folder
        list_url = f"https://www.googleapis.com/drive/v3/files"
        params = {
            'q': f"'{folder_id}' in parents and (mimeType contains 'image/' or mimeType contains 'video/')",
            'fields': 'files(id,name,mimeType,size,createdTime,webViewLink)',
            'orderBy': 'createdTime desc'
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'Facetak-Photo-Processor/1.0'
        }
        
        print(f"🔍 Listing photos in folder: {folder_id}")
        response = requests.get(list_url, headers=headers, params=params)
        response.raise_for_status()
        
        files_data = response.json()
        photos = files_data.get('files', [])
        
        print(f"✅ Found {len(photos)} photos in folder")
        for photo in photos:
            print(f"   📸 {photo['name']} ({photo['mimeType']})")
        
        return photos
        
    except Exception as e:
        print(f"❌ Error listing folder contents: {e}")
        return None

def download_folder_photos(folder_url, access_token, cache_dir="storage/cache"):
    """Download all photos from a Google Drive folder."""
    try:
        photos = list_folder_contents(folder_url, access_token)
        if not photos:
            return []
        
        downloaded_paths = []
        for photo in photos:
            photo_url = f"https://drive.google.com/file/d/{photo['id']}/view"
            downloaded_path = download_drive_photo(photo_url, access_token, cache_dir)
            if downloaded_path:
                downloaded_paths.append(downloaded_path)
        
        print(f"✅ Downloaded {len(downloaded_paths)} photos from folder")
        return downloaded_paths
        
    except Exception as e:
        print(f"❌ Error downloading folder photos: {e}")
        return []

def clear_cache(cache_dir="storage/cache"):
    """Clear cached photos to free up space."""
    try:
        if os.path.exists(cache_dir):
            for filename in os.listdir(cache_dir):
                if filename.startswith("drive_photo_"):
                    filepath = os.path.join(cache_dir, filename)
                    os.remove(filepath)
                    print(f"🗑️ Cleared cached photo: {filename}")
            print("✅ Cache cleared successfully")
        else:
            print("ℹ️ Cache directory doesn't exist")
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
