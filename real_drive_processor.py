#!/usr/bin/env python3
"""
Real Google Drive Processor for Facetak V2
Handles actual Google Drive processing with V2 facial recognition pipeline
"""

import os
import sys
import requests
import time
import json
from urllib.parse import urlparse, parse_qs
from google_drive_handler import extract_file_id_from_url, download_drive_photo
import cv2
import numpy as np

# Import real face recognition engine
from real_face_recognition_engine import get_real_engine

# Import real progress tracker
from real_progress_tracker import progress_tracker

# Import batch downloader and cache
from batch_downloader import BatchDownloader
from local_cache import LocalCache

class RealDriveProcessor:
    def __init__(self, real_engine=None):
        self.real_engine = real_engine or get_real_engine()
        self.processed_count = 0
        self.total_files = 0
        self.errors = []
        
    def process_drive_folder(self, drive_url, access_token, user_id, force_reprocess=False, max_depth=10):
        """
        Process a Google Drive folder with real facial recognition - RECURSIVE VERSION
        Supports up to 10+ levels deep folder traversal
        """
        try:
            print(f"🔍 Starting recursive drive processing for: {drive_url}")
            print(f"📁 Maximum depth: {max_depth} levels")
            print(f"🔄 Force reprocess: {force_reprocess}")
            
            # Extract folder ID from URL
            folder_id = extract_file_id_from_url(drive_url)
            if not folder_id:
                return {'success': False, 'error': 'Could not extract folder ID from URL'}
            
            # Smart caching - check if folder already processed
            if not force_reprocess:
                from folder_cache_manager import folder_cache
                
                # Get current folder contents for fingerprint check
                all_files = self._get_folder_contents_recursive(folder_id, access_token, max_depth)
                if all_files:
                    image_files = self._filter_image_files(all_files)
                    
                    # Check if folder was already processed and unchanged
                    if folder_cache.is_folder_processed(user_id, folder_id, image_files):
                        print(f"✅ Folder already processed, loading cached results...")
                        
                        # Update progress for cached results
                        progress_tracker.start_progress()
                        progress_tracker.set_total(len(image_files))
                        progress_tracker.update_folder_info(drive_url, len(image_files), len(image_files))
                        
                        # Small delay to ensure frontend EventSource connects
                        import time
                        time.sleep(0.5)
                        
                        # Show progress through each step for cached results
                        progress_tracker.set_status('download', 'Loading cached files...')
                        progress_tracker.set_progress('download', 100)
                        time.sleep(0.3)
                        
                        progress_tracker.set_status('processing', 'Loading cached embeddings...')
                        progress_tracker.set_progress('processing', 100)
                        time.sleep(0.3)
                        
                        progress_tracker.set_status('database', 'Loading cached database...')
                        progress_tracker.set_progress('database', 100)
                        time.sleep(0.3)
                        
                        # Mark complete with search_ready flag
                        progress_tracker.complete_all_steps()
                        
                        # Return success with cached info
                        return {
                            'success': True,
                            'cached_result': True,
                            'total_files': len(image_files),
                            'processed_count': len(image_files),
                            'skipped_count': len(image_files),
                            'errors': [],
                            'message': f'Loaded cached results: {len(image_files)} files already processed'
                        }
            
            # Get ALL files recursively (including subfolders)
            all_files = self._get_folder_contents_recursive(folder_id, access_token, max_depth)
            if not all_files:
                return {'success': False, 'error': 'Could not access folder or folder is empty'}
            
            print(f"📁 Found {len(all_files)} total files across all subfolders")
            
            # Filter for image files
            image_files = self._filter_image_files(all_files)
            self.total_files = len(image_files)
            
            print(f"📁 Found {self.total_files} image files in folder")
            
            if self.total_files == 0:
                return {'success': False, 'error': 'No image files found in folder'}
            
            # Update progress tracker
            progress_tracker.set_total(self.total_files)
            progress_tracker.update_folder_info(f"Processing: {drive_url}", self.total_files, self.total_files)
            progress_tracker.set_status('download', 'Starting download...')
            progress_tracker.set_status('processing', 'Waiting for download...')
            progress_tracker.set_status('database', 'Waiting for processing...')
            
            # Create local download directory
            import os
            download_dir = os.path.join("storage", "downloads", f"{user_id}_{folder_id}")
            os.makedirs(download_dir, exist_ok=True)
            print(f"INFO: Created download directory: {download_dir}")
            
            # Phase 1: Download all images to local storage using batch downloader
            print("INFO: Phase 1: Downloading images to local storage (with caching)...")
            progress_tracker.set_status('download', 'Downloading images to local storage...')
            
            # Initialize batch downloader with caching
            batch_downloader = BatchDownloader(batch_size=5, max_concurrent=1)
            
            # Pre-filter: reuse permanently stored files to avoid re-downloads
            reused_files = []
            files_to_download = []
            try:
                from local_cache import LocalCache
                precheck_cache = LocalCache()
            except Exception:
                precheck_cache = None
            for file_info in image_files:
                try:
                    if precheck_cache:
                        cached_path = precheck_cache.get_cached_file_path(file_info, user_id)
                        if cached_path and os.path.exists(cached_path):
                            reused_files.append({
                                'file_info': file_info,
                                'local_path': cached_path,
                                'cached': True
                            })
                            if progress_tracker:
                                progress_tracker.increment('download')
                            continue
                except Exception:
                    pass
                files_to_download.append(file_info)

            # Download remaining files in batches with caching
            downloaded_files = batch_downloader.download_batch(
                files_to_download if files_to_download else [], 
                access_token, 
                download_dir, 
                user_id, 
                progress_tracker
            )
            # Combine reused + newly downloaded
            downloaded_files = reused_files + downloaded_files
            
            print(f"📥 Download complete: {len(downloaded_files)}/{self.total_files} files downloaded")
            
            # Print cache statistics
            cache_stats = batch_downloader.get_cache_stats()
            if cache_stats['total_files'] > 0:
                print(f"💾 Cache stats: {cache_stats['total_files']} files cached ({cache_stats['total_size_mb']} MB)")
            
            # Phase 2: Process downloaded images
            print("🧠 Phase 2: Processing downloaded images...")
            progress_tracker.set_status('processing', 'Processing downloaded images...')

            # Determine batch size per mode (CPU: 20, GPU: 40) - INCREASED FOR SPEED
            batch_size = 20
            gpu_available = False
            try:
                import cv2 as _cv2
                gpu_available = hasattr(_cv2, 'cuda') and _cv2.cuda.getCudaEnabledDeviceCount() > 0
            except Exception:
                try:
                    import torch as _torch
                    gpu_available = _torch.cuda.is_available()
                except Exception:
                    gpu_available = False
            if gpu_available:
                batch_size = 40
            print(f"🧩 Using batch size: {batch_size} ({'GPU' if gpu_available else 'CPU'} mode)")

            # Force reprocessing with real face recognition (no skipping)
            print(f"🚀 Force processing all images with real face recognition")

            self.processed_count = 0
            total_files_to_handle = len(downloaded_files)
            # Thread-safety primitives
            import threading
            counter_lock = threading.Lock()
            errors_lock = threading.Lock()

            for start_idx in range(0, total_files_to_handle, batch_size):
                batch = downloaded_files[start_idx:start_idx + batch_size]
                print(f"📦 Processing batch {start_idx // batch_size + 1}/{(total_files_to_handle + batch_size - 1) // batch_size} ({len(batch)} files)")
                from concurrent.futures import ThreadPoolExecutor, as_completed

                # Concurrency level: CPU 10 workers, GPU 20 workers - INCREASED FOR SPEED
                max_workers = 20 if gpu_available else 10
                max_workers = min(max_workers, len(batch))

                def process_one(index_in_batch, downloaded_file):
                    file_info = downloaded_file['file_info']
                    local_path = downloaded_file['local_path']
                    try:
                        photo_ref = f"{user_id}_{file_info['id']}"
                        # Always process with real face recognition (no skipping)

                        print(f"📸 Processing {start_idx + index_in_batch + 1}/{total_files_to_handle}: {file_info['name']}")
                        progress_tracker.set_status('processing', f'Processing {file_info["name"]}...')

                        image = self._load_image_from_local(local_path)
                        if image is None:
                            error_msg = f"Failed to load {file_info['name']} from local storage"
                            with errors_lock:
                                self.errors.append(error_msg)
                            progress_tracker.add_error(error_msg)
                            progress_tracker.increment('processing')
                            return False, error_msg

                        # Use real face recognition engine (Phase 1) - ONLY PATH
                        result = self._process_with_real_recognition(image, file_info, user_id, folder_id)
                        if result.get('successful_additions', 0) > 0 or result.get('success', False):
                            with counter_lock:
                                self.processed_count += 1
                            print(f"✅ Processed: {file_info['name']}")
                            progress_tracker.set_status('database', f'Storing {file_info["name"]}...')
                            progress_tracker.increment('database')
                        else:
                            error_msg = f"V2 processing failed for {file_info['name']}: {result.get('error', 'Unknown error')}"
                            with errors_lock:
                                self.errors.append(error_msg)
                            progress_tracker.add_error(error_msg)

                        progress_tracker.increment('processing')
                        processed_so_far = start_idx + index_in_batch + 1
                        overall_pct = int((processed_so_far) / total_files_to_handle * 100)
                        print(f"📊 Progress: {overall_pct}% ({processed_so_far}/{total_files_to_handle})")
                        return True, None
                    except Exception as e:
                        error_msg = f"Error processing {file_info['name']}: {str(e)}"
                        print(f"❌ {error_msg}")
                        with errors_lock:
                            self.errors.append(error_msg)
                        progress_tracker.add_error(error_msg)
                        return False, error_msg

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(process_one, j, df) for j, df in enumerate(batch)]
                    for _ in as_completed(futures):
                        pass
            
            # Phase 3: Keep images in cache for search and display
            print("💾 Phase 3: Images kept in cache folder for search...")
            progress_tracker.set_status('database', 'Images ready for search in cache folder...')
            
            # Create mapping file in download directory for search
            mapping_file = os.path.join(download_dir, 'file_id_mapping.json')
            file_mapping = {}
            
            try:
                import json
                
                # Create file_id -> filename mapping for search
                for downloaded_file in downloaded_files:
                    file_info = downloaded_file['file_info']
                    file_mapping[file_info['id']] = file_info['name']
                
                # Save the mapping file in cache directory
                with open(mapping_file, 'w') as f:
                    json.dump(file_mapping, f, indent=2)
                print(f"💾 Saved file mapping in cache: {mapping_file}")
                print(f"📁 Images kept in cache for search: {download_dir}")
                
            except Exception as e:
                print(f"⚠️ Warning: Could not create file mapping: {e}")
            
            # Mark all steps as complete
            progress_tracker.complete_all_steps()
            progress_tracker.set_status('download', 'Download complete!')
            progress_tracker.set_status('processing', 'Processing complete!')
            progress_tracker.set_status('database', 'Images saved for search!')
            
            # Track usage for pricing plans
            try:
                from pricing_manager import pricing_manager
                pricing_manager.track_image_usage(user_id, self.processed_count)
                print(f"📊 Tracked usage: {self.processed_count} images for user {user_id}")
            except Exception as e:
                print(f"⚠️ Usage tracking failed: {e}")
            
            # Save folder cache for future visits (only if not force reprocessing)
            if not force_reprocess:
                from folder_cache_manager import folder_cache
                processing_stats = {
                    'processed_count': self.processed_count,
                    'total_files': self.total_files,
                    'downloaded_files': len(downloaded_files),
                    'errors_count': len(self.errors)
                }
                folder_cache.save_folder_state(user_id, folder_id, image_files, processing_stats)
            
            return {
                'success': True,
                'processed_count': self.processed_count,
                'total_files': self.total_files,
                'downloaded_files': len(downloaded_files),
                'errors': self.errors[:10],  # Limit error messages
                'message': f'Successfully processed {self.processed_count}/{self.total_files} images (downloaded {len(downloaded_files)} files)'
            }
            
        except Exception as e:
            print(f"❌ Drive processing error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_folder_contents_recursive(self, folder_id, access_token, max_depth=10, current_depth=0):
        """Get contents of a Google Drive folder recursively with depth control"""
        try:
            if current_depth >= max_depth:
                print(f"⚠️  Maximum depth {max_depth} reached, stopping recursion")
                return []
            
            print(f"🔍 Scanning folder at depth {current_depth + 1}/{max_depth}")
            
            all_files = []
            page_token = None
            
            while True:
                # Get files in current folder
                url = f"https://www.googleapis.com/drive/v3/files"
                params = {
                    'q': f"'{folder_id}' in parents and trashed=false",
                    'fields': 'files(id,name,mimeType,size,webContentLink,parents),nextPageToken',
                    'pageSize': 1000
                }
                
                if page_token:
                    params['pageToken'] = page_token
                
                # Try with auth token first, fall back to public API key on 403
                headers = {'Authorization': f'Bearer {access_token}'}
                
                response = requests.get(url, params=params, headers=headers)
                
                # If 403 Forbidden, try without auth (public folder)
                if response.status_code == 403:
                    print(f"   ⚠️  Auth failed (403), trying as public folder...")
                    # Get API key from env or use a default one
                    api_key = os.getenv('GOOGLE_API_KEY', 'AIzaSyC80YzDXjtO9E6Mhkox-aYWmRQXsWiYJOM')
                    params['key'] = api_key
                    response = requests.get(url, params=params)  # No auth header
                
                response.raise_for_status()
                
                data = response.json()
                files = data.get('files', [])
                
                # Separate files and folders
                current_files = []
                subfolders = []
                
                for file_info in files:
                    if file_info.get('mimeType') == 'application/vnd.google-apps.folder':
                        subfolders.append(file_info)
                    else:
                        current_files.append(file_info)
                
                all_files.extend(current_files)
                print(f"   📄 Found {len(current_files)} files in current folder")
                
                # Process subfolders recursively
                for subfolder in subfolders:
                    print(f"   📁 Processing subfolder: {subfolder['name']}")
                    subfolder_files = self._get_folder_contents_recursive(
                        subfolder['id'], access_token, max_depth, current_depth + 1
                    )
                    all_files.extend(subfolder_files)
                
                # Check for next page
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"✅ Completed depth {current_depth + 1}: {len(all_files)} total files found")
            return all_files
            
        except Exception as e:
            print(f"❌ Error getting recursive folder contents at depth {current_depth + 1}: {e}")
            return []

    def _get_folder_contents(self, folder_id, access_token):
        """Get contents of a Google Drive folder (single level) - kept for compatibility"""
        try:
            url = f"https://www.googleapis.com/drive/v3/files"
            params = {
                'q': f"'{folder_id}' in parents and trashed=false",
                'fields': 'files(id,name,mimeType,size,webContentLink)',
                'pageSize': 1000
            }
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get('files', [])
            
        except Exception as e:
            print(f"❌ Error getting folder contents: {e}")
            return []
    
    def _filter_image_files(self, files):
        """Filter for image files only"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        image_mime_types = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
            'image/bmp', 'image/webp'
        }
        
        image_files = []
        for file_info in files:
            name = file_info.get('name', '').lower()
            mime_type = file_info.get('mimeType', '').lower()
            
            # Check by extension or MIME type
            if (any(name.endswith(ext) for ext in image_extensions) or 
                mime_type in image_mime_types):
                image_files.append(file_info)
        
        return image_files
    
    def _download_image(self, file_info, access_token):
        """Download image from Google Drive"""
        try:
            file_id = file_info['id']
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {'alt': 'media'}
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.get(url, params=params, headers=headers, stream=True)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            print(f"❌ Error downloading {file_info['name']}: {e}")
            return None
    
    def _download_image_to_local(self, file_info, access_token, download_dir):
        """Download image from Google Drive to local storage"""
        try:
            file_id = file_info['id']
            file_name = file_info['name']
            
            # Create safe filename
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            local_path = os.path.join(download_dir, safe_filename)
            
            # Download image
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {'alt': 'media'}
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.get(url, params=params, headers=headers, stream=True)
            response.raise_for_status()
            
            # Save to local file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"💾 Saved to: {local_path}")
            return local_path
            
        except Exception as e:
            print(f"❌ Error downloading {file_info['name']} to local: {e}")
            return None
    
    def _load_image_from_local(self, local_path):
        """Load image from local file with EXIF orientation fix"""
        try:
            # First, fix EXIF orientation using PIL
            from PIL import Image as PILImage
            from PIL import ExifTags
            
            # Open with PIL to handle EXIF
            pil_img = PILImage.open(local_path)
            
            # Fix orientation based on EXIF data
            try:
                exif = pil_img._getexif()
                if exif is not None:
                    for tag, value in exif.items():
                        tag_name = ExifTags.TAGS.get(tag, tag)
                        if tag_name == 'Orientation':
                            if value == 3:
                                pil_img = pil_img.rotate(180, expand=True)
                            elif value == 6:
                                pil_img = pil_img.rotate(270, expand=True)
                            elif value == 8:
                                pil_img = pil_img.rotate(90, expand=True)
                            print(f"🔄 Fixed EXIF orientation: {value}")
                            break
            except (AttributeError, KeyError, IndexError, TypeError):
                # No EXIF data or orientation tag, continue normally
                pass
            
            # Convert PIL to OpenCV format (RGB to BGR)
            import numpy as np
            image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            if image is None:
                print(f"❌ Failed to load image: {local_path}")
                return None
            
            # Resize if too large
            height, width = image.shape[:2]
            if width > 2000 or height > 2000:
                scale = min(2000/width, 2000/height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = cv2.resize(image, (new_width, new_height))
            
            return image
            
        except Exception as e:
            print(f"❌ Error loading image from {local_path}: {e}")
            return None
    
    def _bytes_to_cv2_image(self, image_data):
        """Convert bytes to OpenCV image with EXIF orientation fix"""
        try:
            # Fix EXIF orientation using PIL before converting to cv2
            from PIL import Image as PILImage
            from PIL import ExifTags
            from io import BytesIO
            import numpy as np
            
            # Open with PIL from bytes
            pil_img = PILImage.open(BytesIO(image_data))
            
            # Fix orientation based on EXIF data
            try:
                exif = pil_img._getexif()
                if exif is not None:
                    for tag, value in exif.items():
                        tag_name = ExifTags.TAGS.get(tag, tag)
                        if tag_name == 'Orientation':
                            if value == 3:
                                pil_img = pil_img.rotate(180, expand=True)
                            elif value == 6:
                                pil_img = pil_img.rotate(270, expand=True)
                            elif value == 8:
                                pil_img = pil_img.rotate(90, expand=True)
                            print(f"🔄 Fixed EXIF orientation: {value}")
                            break
            except (AttributeError, KeyError, IndexError, TypeError):
                # No EXIF data, continue normally
                pass
            
            # Convert PIL to OpenCV format (RGB to BGR)
            image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            if image is None:
                return None
            
            # Resize if too large
            height, width = image.shape[:2]
            if width > 2000 or height > 2000:
                scale = min(2000/width, 2000/height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = cv2.resize(image, (new_width, new_height))
            
            return image
            
        except Exception as e:
            print(f"❌ Error converting image: {e}")
            return None
    
    def _process_with_real_recognition(self, image, file_info, user_id, folder_id=None):
        """Process image with real face recognition engine (Phase 1)."""
        try:
            from real_face_recognition_engine import process_image_with_real_recognition
            
            # Save image temporarily for processing
            temp_path = f"temp_processing_{file_info['id']}.jpg"
            cv2.imwrite(temp_path, image)
            
            try:
                # Process with real face recognition
                person_id = f"{user_id}_{file_info['id']}"
                # Ensure folder_id is set (mandatory for scoped storage)
                if folder_id is None:
                    from google_drive_handler import extract_file_id_from_url  # safety import
                    # Fallback: try to infer folder from session is not available here; require explicit folder_id
                    pass
                result = process_image_with_real_recognition(temp_path, person_id, user_id, folder_id)
                
                # Also save to Firebase for compatibility
                if result.get('success', False) and result.get('embeddings'):
                    try:
                        from firebase_store import save_face_embedding
                        import numpy as np
                        
                        embedding = np.array(result['embeddings'][0]['embedding'])
                        photo_ref = person_id
                        firebase_success = save_face_embedding(user_id, photo_ref, embedding, folder_id)
                        
                        if firebase_success:
                            print(f"💾 Saved to Firebase with real recognition: {file_info['name']}")
                        else:
                            print(f"⚠️  Firebase save failed: {file_info['name']}")
                            
                    except Exception as e:
                        print(f"⚠️  Firebase integration error: {e}")
                
                return result
                
            finally:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Real face recognition error: {e}")
            return {'success': False, 'error': str(e)}


def process_drive_folder_and_store(user_id, url, access_token, force_reprocess=False, max_depth=10):
    """
    Main function to process Google Drive folder - RECURSIVE VERSION
    Supports up to 10+ levels deep folder traversal
    """
    try:
        processor = RealDriveProcessor()
        result = processor.process_drive_folder(url, access_token, user_id, force_reprocess, max_depth)
        return result
        
    except Exception as e:
        print(f"❌ Drive processing error: {e}")
        return {'success': False, 'error': str(e)}
