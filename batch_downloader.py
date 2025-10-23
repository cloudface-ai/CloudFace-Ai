import asyncio
import aiohttp
import os
import time
from concurrent.futures import ThreadPoolExecutor
from local_cache import LocalCache

class BatchDownloader:
    def __init__(self, batch_size=5, max_concurrent=1):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.cache = LocalCache()
        self.download_stats = {
            'total_files': 0,
            'cached_files': 0,
            'downloaded_files': 0,
            'failed_files': 0,
            'start_time': None,
            'end_time': None
        }
    
    def _download_single_file(self, file_info, access_token, download_dir, user_id):
        """Download a single file (synchronous)"""
        try:
            # Check cache or permanent storage first
            cached_path = self.cache.get_cached_file_path(file_info, user_id)
            if cached_path and os.path.exists(cached_path):
                print(f"SUCCESS: Using cached/permanent file: {file_info.get('name', 'Unknown')}")
                self.download_stats['cached_files'] += 1
                return {
                    'file_info': file_info,
                    'local_path': cached_path,
                    'cached': True
                }
            
            # Download the file
            file_id = file_info.get('id', '')
            file_name = file_info.get('name', f'file_{file_id}')
            
            # Create local file path
            local_file_path = os.path.join(download_dir, file_name)
            
            # Download from Google Drive
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            headers = {'Authorization': f'Bearer {access_token}'}
            
            import requests
            response = requests.get(download_url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()
            
            # Save file
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Ensure file handle is fully closed and Windows releases the lock
            import time
            import gc
            gc.collect()  # Force garbage collection
            time.sleep(0.5)  # Minimal delay since no compression
            
            # Try compression with improved Windows file locking handling
            original_size = os.path.getsize(local_file_path)
            if original_size > 5 * 1024 * 1024:  # 5MB threshold
                compressed_path = None
                
                # Try compression with multiple retry attempts
                for attempt in range(3):
                    try:
                        # Wait for Windows to release the file lock
                        time.sleep(1.0 + attempt * 0.5)  # Shorter delays
                        
                        # Check if file is accessible before compression
                        with open(local_file_path, 'rb') as test_file:
                            test_file.read(1)  # Try to read 1 byte
                        
                        # File is accessible, try compression
                        compressed_path = self._compress_image(local_file_path, original_size)
                        if compressed_path and compressed_path != local_file_path:
                            local_file_path = compressed_path
                            print(f"SUCCESS: Compressed {file_name} ({original_size / (1024*1024):.1f}MB)")
                            break  # Success, exit retry loop
                        else:
                            print(f"INFO: Kept original size for {file_name} ({original_size / (1024*1024):.1f}MB)")
                            break  # No compression needed, exit retry loop
                            
                    except (PermissionError, IOError) as e:
                        if attempt == 2:  # Last attempt
                            print(f"WARNING: Could not compress {file_name} after 3 attempts - {e}")
                            print(f"INFO: Keeping original file ({original_size / (1024*1024):.1f}MB)")
                        else:
                            print(f"File locked, retrying in {1.0 + attempt * 0.5} seconds... (attempt {attempt + 1}/3)")
                    except Exception as e:
                        if attempt == 2:  # Last attempt
                            print(f"WARNING: Compression error for {file_name}: {e}")
                            print(f"INFO: Keeping original file ({original_size / (1024*1024):.1f}MB)")
                        else:
                            print(f"Compression error, retrying in {1.0 + attempt * 0.5} seconds... (attempt {attempt + 1}/3)")
            
            # Cache the file (compressed version if applicable)
            self.cache.cache_file(file_info, user_id, local_file_path)
            
            final_size = os.path.getsize(local_file_path)
            size_mb = final_size / (1024 * 1024)
            print(f"DOWNLOADED: {file_name} ({size_mb:.1f}MB)")
            self.download_stats['downloaded_files'] += 1
            
            return {
                'file_info': file_info,
                'local_path': local_file_path,
                'cached': False
            }
            
        except Exception as e:
            print(f"ERROR: Failed to download {file_info.get('name', 'Unknown')}: {e}")
            self.download_stats['failed_files'] += 1
            return None
    
    def download_batch(self, image_files, access_token, download_dir, user_id, progress_tracker=None):
        """Download files in batches with caching"""
        self.download_stats['start_time'] = time.time()
        self.download_stats['total_files'] = len(image_files)
        
        print(f"INFO: Starting batch download of {len(image_files)} files")
        print(f"INFO: Batch size: {self.batch_size}, Max concurrent: {self.max_concurrent}")
        
        downloaded_files = []
        
        # Process files in batches
        for i in range(0, len(image_files), self.batch_size):
            batch = image_files[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(image_files) + self.batch_size - 1) // self.batch_size
            
            print(f"\nINFO: Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            # Use ThreadPoolExecutor for concurrent downloads within batch
            # Reduced concurrency to prevent Windows file locking issues
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                # Submit all files in current batch
                future_to_file = {
                    executor.submit(self._download_single_file, file_info, access_token, download_dir, user_id): file_info
                    for file_info in batch
                }
                
                # Collect results as they complete
                for future in future_to_file:
                    try:
                        result = future.result(timeout=120)  # 120 second timeout per file
                        if result:
                            downloaded_files.append(result)
                            if progress_tracker:
                                progress_tracker.increment('download')
                    except Exception as e:
                        file_info = future_to_file[future]
                        print(f"ERROR: Batch download failed for {file_info.get('name', 'Unknown')}: {e}")
                        self.download_stats['failed_files'] += 1
            
            # Small delay between batches to prevent file locking conflicts on Windows
            if batch_num < total_batches:  # Don't delay after the last batch
                time.sleep(2.0)  # Increased delay for smaller batches to ensure file locks are released
        
        self.download_stats['end_time'] = time.time()
        self._print_download_summary()
        
        return downloaded_files
    
    def _print_download_summary(self):
        """Print download statistics"""
        duration = self.download_stats['end_time'] - self.download_stats['start_time']
        
        print(f"\nINFO: Download Summary:")
        print(f"   Total files: {self.download_stats['total_files']}")
        print(f"   Cached files: {self.download_stats['cached_files']} (saved time!)")
        print(f"   Downloaded files: {self.download_stats['downloaded_files']}")
        print(f"   Failed files: {self.download_stats['failed_files']}")
        print(f"   Duration: {duration:.2f} seconds")
        
        if self.download_stats['cached_files'] > 0:
            cache_savings = (self.download_stats['cached_files'] / self.download_stats['total_files']) * 100
            print(f"   Cache hit rate: {cache_savings:.1f}% (time saved!)")
    
    def _compress_image(self, image_path, original_size):
        """Compress image if larger than 5MB to speed up processing."""
        try:
            from PIL import Image
            import os
            import time
            
            # Multiple safety checks for file accessibility
            max_checks = 5
            for check in range(max_checks):
                try:
                    # Test if file is accessible
                    with open(image_path, 'rb') as f:
                        f.read(1)  # Read first byte
                    break  # File is accessible
                except (PermissionError, IOError) as e:
                    if check < max_checks - 1:
                        print(f"File locked, waiting... (check {check + 1}/{max_checks})")
                        time.sleep(1.0)
                    else:
                        print(f"File still locked after {max_checks} attempts, skipping compression")
                        return image_path
            
            # Retry mechanism for file locking issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Open image
                    with Image.open(image_path) as img:
                        # Convert to RGB if necessary
                        if img.mode in ('RGBA', 'P'):
                            img = img.convert('RGB')
                        
                        # Simple reliable compression - always compress files >5MB
                        original_mb = original_size / (1024 * 1024)
                        
                        # Simple settings: resize to 2500px max, 88% quality
                        max_size = 2500
                        quality = 88
                        
                        # Resize if needed
                        if img.width > max_size or img.height > max_size:
                            ratio = min(max_size / img.width, max_size / img.height)
                            new_width = int(img.width * ratio)
                            new_height = int(img.height * ratio)
                            # Use compatible resampling filter
                            try:
                                resample_filter = Image.Resampling.LANCZOS
                            except AttributeError:
                                try:
                                    resample_filter = Image.LANCZOS
                                except AttributeError:
                                    resample_filter = Image.ANTIALIAS
                            
                            img = img.resize((new_width, new_height), resample_filter)
                        
                        # Save compressed version with proper extension handling
                        import os
                        import tempfile
                        
                        # Use temp file to avoid file locking issues
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                            temp_path = temp_file.name
                        
                        img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                        
                        # Simple check: if compressed file is smaller, use it
                        compressed_size = os.path.getsize(temp_path)
                        compressed_mb = compressed_size / (1024 * 1024)
                        
                        if compressed_size < original_size and compressed_size > 500000:  # At least 500KB
                            # Good compression - replace original safely
                            try:
                                # Copy compressed file over original (safer than rename)
                                import shutil
                                shutil.copy2(temp_path, image_path)
                                os.unlink(temp_path)  # Remove temp file
                                
                                reduction = ((original_size - compressed_size) / original_size) * 100
                                print(f"Compressed: {reduction:.1f}% size reduction ({original_mb:.1f}MB -> {compressed_mb:.1f}MB)")
                                return image_path
                            except Exception as e:
                                # If copy fails, clean up temp and keep original
                                try:
                                    os.unlink(temp_path)
                                except:
                                    pass
                                print(f"Compression failed during copy: {e}")
                                return image_path
                        else:
                            # Keep original, clean up temp
                            try:
                                os.unlink(temp_path)
                            except:
                                pass
                            print(f"Keeping original file ({original_mb:.1f}MB)")
                            return image_path
                    
                    # If we get here, compression succeeded
                    break
                    
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        print(f"File locked, retrying in 1 second... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(1.0)  # Wait 1 second before retry
                        continue
                    else:
                        print(f"Compression failed after {max_retries} attempts: {e}")
                        return image_path
                        
        except Exception as e:
            print(f"Compression failed: {e}")
            return image_path  # Return original if compression fails
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return self.cache.get_cache_stats()
    
    def cleanup_cache(self, days=30):
        """Clean up old cache entries"""
        self.cache.cleanup_old_cache(days)
