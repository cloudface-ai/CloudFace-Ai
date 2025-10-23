"""
Folder Cache Manager - Smart Processing Cache System
Prevents reprocessing of already processed Google Drive folders
"""
import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional

class FolderCacheManager:
    """Manages folder-level caching to avoid reprocessing same Drive folders"""
    
    def __init__(self, cache_dir: str = "storage/folder_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_file_path(self, user_id: str, folder_id: str) -> str:
        """Get cache file path for user/folder combination"""
        return os.path.join(self.cache_dir, f"{user_id}_{folder_id}.json")
    
    def _create_folder_fingerprint(self, files: List[Dict]) -> str:
        """Create unique fingerprint of folder contents"""
        # Sort files by ID for consistent fingerprint
        sorted_files = sorted(files, key=lambda x: x.get('id', ''))
        
        # Create fingerprint from file IDs and modification times
        fingerprint_data = []
        for file_info in sorted_files:
            fingerprint_data.append({
                'id': file_info.get('id', ''),
                'name': file_info.get('name', ''),
                'size': file_info.get('size', 0),
                'modified': file_info.get('modifiedTime', '')
            })
        
        # Hash the fingerprint
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()
    
    def is_folder_processed(self, user_id: str, folder_id: str, current_files: List[Dict]) -> bool:
        """Check if folder was already processed and hasn't changed"""
        try:
            cache_file = self._get_cache_file_path(user_id, folder_id)
            
            if not os.path.exists(cache_file):
                print(f"📂 No cache found for folder {folder_id}")
                return False
            
            # Load cache data
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check cache age (expire after 7 days)
            cache_age_hours = (time.time() - cache_data.get('processed_at', 0)) / 3600
            if cache_age_hours > 168:  # 7 days
                print(f"📂 Cache expired for folder {folder_id} ({cache_age_hours/24:.1f} days old)")
                return False
            
            # Check if folder contents changed
            current_fingerprint = self._create_folder_fingerprint(current_files)
            cached_fingerprint = cache_data.get('folder_fingerprint', '')
            
            if current_fingerprint != cached_fingerprint:
                print(f"📂 Folder changed for {folder_id} - new files detected")
                return False
            
            print(f"✅ Folder {folder_id} already processed ({len(current_files)} files unchanged)")
            return True
            
        except Exception as e:
            print(f"❌ Error checking folder cache: {e}")
            return False
    
    def save_folder_state(self, user_id: str, folder_id: str, files: List[Dict], 
                         processing_stats: Dict[str, Any]) -> bool:
        """Save folder processing state for future cache checks"""
        try:
            cache_file = self._get_cache_file_path(user_id, folder_id)
            
            cache_data = {
                'user_id': user_id,
                'folder_id': folder_id,
                'processed_at': time.time(),
                'processed_date': datetime.now().isoformat(),
                'folder_fingerprint': self._create_folder_fingerprint(files),
                'file_count': len(files),
                'processing_stats': processing_stats,
                'cache_version': '1.0'
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"💾 Saved folder cache for {folder_id}: {len(files)} files")
            return True
            
        except Exception as e:
            print(f"❌ Error saving folder cache: {e}")
            return False
    
    def get_folder_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about cached folders for this user"""
        try:
            stats = {
                'cached_folders': 0,
                'total_files': 0,
                'cache_size_mb': 0,
                'folders': []
            }
            
            # Scan cache directory for user's folders
            for filename in os.listdir(self.cache_dir):
                if filename.startswith(f"{user_id}_") and filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    try:
                        with open(cache_file, 'r') as f:
                            cache_data = json.load(f)
                        
                        stats['cached_folders'] += 1
                        stats['total_files'] += cache_data.get('file_count', 0)
                        
                        # Calculate file size
                        file_size = os.path.getsize(cache_file)
                        stats['cache_size_mb'] += file_size / (1024 * 1024)
                        
                        stats['folders'].append({
                            'folder_id': cache_data.get('folder_id', ''),
                            'file_count': cache_data.get('file_count', 0),
                            'processed_date': cache_data.get('processed_date', ''),
                            'processing_stats': cache_data.get('processing_stats', {})
                        })
                        
                    except Exception as e:
                        print(f"⚠️ Error reading cache file {filename}: {e}")
            
            stats['cache_size_mb'] = round(stats['cache_size_mb'], 2)
            return stats
            
        except Exception as e:
            print(f"❌ Error getting folder stats: {e}")
            return {'error': str(e)}
    
    def clear_folder_cache(self, user_id: str, folder_id: str = None) -> bool:
        """Clear cache for specific folder or all user folders"""
        try:
            if folder_id:
                # Clear specific folder
                cache_file = self._get_cache_file_path(user_id, folder_id)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print(f"🗑️ Cleared cache for folder {folder_id}")
                    return True
            else:
                # Clear all user folders
                cleared_count = 0
                for filename in os.listdir(self.cache_dir):
                    if filename.startswith(f"{user_id}_") and filename.endswith('.json'):
                        cache_file = os.path.join(self.cache_dir, filename)
                        os.remove(cache_file)
                        cleared_count += 1
                print(f"🗑️ Cleared {cleared_count} cached folders for user {user_id}")
                return True
                
        except Exception as e:
            print(f"❌ Error clearing folder cache: {e}")
            return False

# Global instance
folder_cache = FolderCacheManager()
