"""
Smart Search Result Caching System
Caches face search results per Google Drive folder to avoid re-processing
"""
import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class SearchCacheManager:
    def __init__(self, cache_base_dir: str = "storage/search_cache"):
        self.cache_base_dir = cache_base_dir
        os.makedirs(cache_base_dir, exist_ok=True)
    
    def _get_cache_dir(self, user_id: str, folder_id: str) -> str:
        """Get cache directory for specific user and folder"""
        return os.path.join(self.cache_base_dir, user_id, folder_id)
    
    def _get_cache_files(self, user_id: str, folder_id: str) -> Dict[str, str]:
        """Get paths to all cache files"""
        cache_dir = self._get_cache_dir(user_id, folder_id)
        return {
            'results': os.path.join(cache_dir, 'search_results.json'),
            'metadata': os.path.join(cache_dir, 'cache_metadata.json'),
            'folder_snapshot': os.path.join(cache_dir, 'folder_snapshot.json')
        }
    
    def _create_folder_fingerprint(self, folder_files: List[Dict]) -> str:
        """Create fingerprint of folder contents to detect changes"""
        # Sort files by ID for consistent fingerprint
        sorted_files = sorted(folder_files, key=lambda x: x.get('id', ''))
        
        # Create fingerprint from file IDs, sizes, and modification times
        fingerprint_data = []
        for file_info in sorted_files:
            fingerprint_data.append({
                'id': file_info.get('id', ''),
                'name': file_info.get('name', ''),
                'size': file_info.get('size', 0),
                'modified': file_info.get('modifiedTime', '')
            })
        
        # Hash the fingerprint data
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()
    
    def is_cache_valid(self, user_id: str, folder_id: str, current_folder_files: List[Dict]) -> bool:
        """Check if cached results are still valid"""
        try:
            cache_files = self._get_cache_files(user_id, folder_id)
            
            # Check if cache files exist
            if not all(os.path.exists(f) for f in cache_files.values()):
                print(f"📂 Cache files missing for {folder_id}")
                return False
            
            # Load cache metadata
            with open(cache_files['metadata'], 'r') as f:
                cache_metadata = json.load(f)
            
            # Check cache age (expire after 24 hours)
            cache_age_hours = (time.time() - cache_metadata['created_at']) / 3600
            if cache_age_hours > 24:
                print(f"📂 Cache expired for {folder_id} ({cache_age_hours:.1f} hours old)")
                return False
            
            # Check folder fingerprint
            current_fingerprint = self._create_folder_fingerprint(current_folder_files)
            cached_fingerprint = cache_metadata.get('folder_fingerprint', '')
            
            if current_fingerprint != cached_fingerprint:
                print(f"📂 Folder changed for {folder_id} (fingerprint mismatch)")
                return False
            
            print(f"✅ Cache valid for {folder_id} ({len(current_folder_files)} files)")
            return True
            
        except Exception as e:
            print(f"❌ Error checking cache validity: {e}")
            return False
    
    def get_cached_results(self, user_id: str, folder_id: str) -> Optional[Dict[str, Any]]:
        """Get cached search results if valid"""
        try:
            cache_files = self._get_cache_files(user_id, folder_id)
            
            if not os.path.exists(cache_files['results']):
                return None
            
            with open(cache_files['results'], 'r') as f:
                cached_results = json.load(f)
            
            print(f"📂 Loaded cached results: {len(cached_results.get('matches', []))} matches")
            return cached_results
            
        except Exception as e:
            print(f"❌ Error loading cached results: {e}")
            return None
    
    def save_search_results(self, user_id: str, folder_id: str, search_results: Dict[str, Any], 
                          folder_files: List[Dict], selfie_embedding: Any) -> bool:
        """Save search results to cache"""
        try:
            cache_dir = self._get_cache_dir(user_id, folder_id)
            os.makedirs(cache_dir, exist_ok=True)
            
            cache_files = self._get_cache_files(user_id, folder_id)
            
            # Save search results
            cache_data = {
                'search_results': search_results,
                'selfie_embedding': selfie_embedding.tolist() if hasattr(selfie_embedding, 'tolist') else selfie_embedding,
                'cached_at': datetime.now().isoformat(),
                'folder_id': folder_id,
                'user_id': user_id
            }
            
            with open(cache_files['results'], 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            # Save cache metadata
            metadata = {
                'created_at': time.time(),
                'folder_id': folder_id,
                'user_id': user_id,
                'file_count': len(folder_files),
                'match_count': len(search_results.get('matches', [])),
                'folder_fingerprint': self._create_folder_fingerprint(folder_files),
                'cache_version': '1.0'
            }
            
            with open(cache_files['metadata'], 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save folder snapshot for debugging
            with open(cache_files['folder_snapshot'], 'w') as f:
                json.dump({
                    'files': folder_files[:10],  # Sample of files
                    'total_files': len(folder_files),
                    'fingerprint': metadata['folder_fingerprint'],
                    'snapshot_time': datetime.now().isoformat()
                }, f, indent=2)
            
            print(f"💾 Cached search results for {folder_id}: {len(search_results.get('matches', []))} matches")
            return True
            
        except Exception as e:
            print(f"❌ Error saving search results to cache: {e}")
            return False
    
    def clear_cache(self, user_id: str, folder_id: str = None) -> bool:
        """Clear cache for specific folder or all user cache"""
        try:
            if folder_id:
                # Clear specific folder cache
                cache_dir = self._get_cache_dir(user_id, folder_id)
                if os.path.exists(cache_dir):
                    import shutil
                    shutil.rmtree(cache_dir)
                    print(f"🗑️ Cleared cache for folder {folder_id}")
            else:
                # Clear all user cache
                user_cache_dir = os.path.join(self.cache_base_dir, user_id)
                if os.path.exists(user_cache_dir):
                    import shutil
                    shutil.rmtree(user_cache_dir)
                    print(f"🗑️ Cleared all cache for user {user_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self, user_id: str) -> Dict[str, Any]:
        """Get cache statistics for user"""
        try:
            user_cache_dir = os.path.join(self.cache_base_dir, user_id)
            if not os.path.exists(user_cache_dir):
                return {'cached_folders': 0, 'total_matches': 0, 'cache_size_mb': 0}
            
            stats = {
                'cached_folders': 0,
                'total_matches': 0,
                'cache_size_mb': 0,
                'folders': []
            }
            
            # Calculate cache size
            total_size = 0
            for root, dirs, files in os.walk(user_cache_dir):
                for file in files:
                    total_size += os.path.getsize(os.path.join(root, file))
            
            stats['cache_size_mb'] = round(total_size / (1024 * 1024), 2)
            
            # Count cached folders and matches
            for folder_name in os.listdir(user_cache_dir):
                folder_path = os.path.join(user_cache_dir, folder_name)
                if os.path.isdir(folder_path):
                    metadata_file = os.path.join(folder_path, 'cache_metadata.json')
                    if os.path.exists(metadata_file):
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            stats['cached_folders'] += 1
                            stats['total_matches'] += metadata.get('match_count', 0)
                            # Create better folder names for search sessions
                            if folder_name.startswith('search_'):
                                folder_display_name = f"Face Search Session"
                                folder_subtitle = f"Found {metadata.get('match_count', 0)} matches"
                            else:
                                folder_display_name = f"Folder {folder_name[:8]}" if len(folder_name) > 8 else folder_name
                                folder_subtitle = f"{metadata.get('file_count', 0)} files processed"
                            
                            # Get cover photo from search results
                            cover_photo = None
                            try:
                                folder_cache_dir = self._get_cache_dir(user_id, folder_name)
                                results_file = os.path.join(folder_cache_dir, 'search_results.json')
                                if os.path.exists(results_file):
                                    with open(results_file, 'r') as f:
                                        results_data = json.load(f)
                                        matches = results_data.get('search_results', {}).get('matches', [])
                                        if matches:
                                            # Use first match as cover photo
                                            cover_photo = matches[0].get('photo_path', matches[0].get('photo_reference', ''))
                            except Exception as e:
                                print(f"⚠️ Could not get cover photo for {folder_name}: {e}")
                            
                            # Get actual photo count from search results
                            actual_photo_count = 0
                            try:
                                folder_cache_dir = self._get_cache_dir(user_id, folder_name)
                                results_file = os.path.join(folder_cache_dir, 'search_results.json')
                                if os.path.exists(results_file):
                                    with open(results_file, 'r') as f:
                                        results_data = json.load(f)
                                        matches = results_data.get('search_results', {}).get('matches', [])
                                        actual_photo_count = len(matches)
                            except Exception as e:
                                print(f"⚠️ Could not get actual photo count for {folder_name}: {e}")
                                actual_photo_count = metadata.get('match_count', 0)  # Fallback to match count
                            
                            stats['folders'].append({
                                'folder_id': folder_name,
                                'folder_name': folder_display_name,
                                'folder_subtitle': folder_subtitle,
                                'file_count': actual_photo_count,  # Use actual photo count instead of file_count
                                'match_count': metadata.get('match_count', 0),
                                'cached_at': datetime.fromtimestamp(metadata.get('created_at', 0)).isoformat(),
                                'cover_photo': cover_photo
                            })
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting cache stats: {e}")
            return {'error': str(e)}

# Global cache manager instance
cache_manager = SearchCacheManager()
