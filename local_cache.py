import os
import hashlib
import json
from datetime import datetime, timedelta

class LocalCache:
    def __init__(self, cache_dir="storage/cache"):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "cache_metadata.json")
        self._ensure_cache_dir()
        self._load_metadata()
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _load_metadata(self):
        """Load cache metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = {}
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """Save cache metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache metadata: {e}")
    
    def get_file_hash(self, file_info):
        """Generate a unique hash for a file based on its properties"""
        # Use file ID, name, size, and modified time to create a unique hash
        hash_string = f"{file_info.get('id', '')}_{file_info.get('name', '')}_{file_info.get('size', 0)}_{file_info.get('modifiedTime', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def is_file_cached(self, file_info, user_id):
        """Check if a file is already cached and valid"""
        file_hash = self.get_file_hash(file_info)
        file_id = file_info.get('id', '')
        
        # Check if file exists in cache
        cache_key = f"{user_id}_{file_id}"
        if cache_key in self.metadata:
            cached_info = self.metadata[cache_key]
            
            # Check if file still exists on disk
            cached_path = cached_info.get('path', '')
            if os.path.exists(cached_path):
                # Check if file is still valid (not too old)
                cache_time = datetime.fromisoformat(cached_info.get('cached_at', ''))
                if datetime.now() - cache_time < timedelta(days=30):  # Cache valid for 30 days
                    return True, cached_path

            # Fallback: try to locate permanent stored file and refresh cache path
            permanent_path = self.find_permanent_path(file_info, user_id)
            if permanent_path and os.path.exists(permanent_path):
                # Update metadata path to permanent location and keep original cached_at
                self.metadata[cache_key]['path'] = permanent_path
                self._save_metadata()
                return True, permanent_path
        
        return False, None
    
    def cache_file(self, file_info, user_id, local_path):
        """Cache a file's information"""
        file_hash = self.get_file_hash(file_info)
        file_id = file_info.get('id', '')
        cache_key = f"{user_id}_{file_id}"
        
        self.metadata[cache_key] = {
            'file_id': file_id,
            'file_name': file_info.get('name', ''),
            'file_size': file_info.get('size', 0),
            'path': local_path,
            'cached_at': datetime.now().isoformat(),
            'file_hash': file_hash
        }
        
        self._save_metadata()
    
    def get_cached_file_path(self, file_info, user_id):
        """Get the cached file path if it exists"""
        is_cached, path = self.is_file_cached(file_info, user_id)
        return path if is_cached else None

    def find_permanent_path(self, file_info, user_id):
        """Find file path in permanent storage using mapping file.

        Looks up storage/data/{user_id}/photos/file_id_mapping.json for the file_id
        and returns the absolute path to the mapped filename if present on disk.
        """
        try:
            file_id = file_info.get('id', '')
            if not file_id:
                return None
            photos_dir = os.path.join('storage', 'data', user_id, 'photos')
            mapping_path = os.path.join(photos_dir, 'file_id_mapping.json')
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r') as f:
                    mapping = json.load(f)
                if file_id in mapping:
                    filename = mapping[file_id]
                    permanent_path = os.path.join(photos_dir, filename)
                    if os.path.exists(permanent_path):
                        return permanent_path
            # Also scan subfolders under storage/data/{user_id}/ for original filename
            original_name = file_info.get('name', '')
            if original_name:
                user_root = os.path.join('storage', 'data', user_id)
                if os.path.exists(user_root):
                    for item in os.listdir(user_root):
                        item_path = os.path.join(user_root, item)
                        if os.path.isdir(item_path):
                            candidate = os.path.join(item_path, original_name)
                            if os.path.exists(candidate):
                                return candidate
        except Exception as e:
            # Non-fatal; just return None on errors
            pass
        return None
    
    def cleanup_old_cache(self, days=30):
        """Clean up old cache entries"""
        cutoff_date = datetime.now() - timedelta(days=days)
        keys_to_remove = []
        
        for key, info in self.metadata.items():
            cache_time = datetime.fromisoformat(info.get('cached_at', ''))
            if cache_time < cutoff_date:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            # Try to delete the actual file
            try:
                if os.path.exists(self.metadata[key]['path']):
                    os.remove(self.metadata[key]['path'])
            except:
                pass
            del self.metadata[key]
        
        if keys_to_remove:
            self._save_metadata()
            print(f"🧹 Cleaned up {len(keys_to_remove)} old cache entries")
    
    def get_cache_stats(self):
        """Get cache statistics"""
        total_files = len(self.metadata)
        total_size = 0
        
        for info in self.metadata.values():
            try:
                if os.path.exists(info['path']):
                    total_size += os.path.getsize(info['path'])
            except:
                pass
        
        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': self.cache_dir
        }
