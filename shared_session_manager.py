"""
Shared Session Manager for CloudFace AI
Allows admins to process photos and share access with end users
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from firebase_store import db

SESSIONS_COLLECTION = 'shared_sessions'

class SharedSessionManager:
    """Manages shared photo processing sessions"""
    
    def __init__(self):
        self.db = db
    
    def create_session(self, admin_user_id: str, folder_id: str, metadata: Dict[str, Any],
                       photo_paths: Optional[List[str]] = None) -> Optional[str]:
        """
        Create a new shared session after admin processes photos
        
        Args:
            admin_user_id: The admin who processed the photos
            folder_id: The Google Drive folder ID that was processed
            metadata: Additional info (event name, date, company, etc.)
            photo_paths: For folder_id 'uploaded', list of relative file paths in this event (so count is per-event)
        
        Returns:
            session_id: Unique session ID for sharing
        """
        try:
            print(f"🔍 Creating session - Admin: {admin_user_id}, Folder: {folder_id}")
            print(f"🔍 Firebase DB status: {self.db is not None}")
            
            if self.db is None:
                print("⚠️  No Firebase client; using local file storage for sessions")
                return self._create_local_session(admin_user_id, folder_id, metadata, photo_paths=photo_paths)
            
            # Generate unique session ID
            session_id = str(uuid.uuid4())[:12]  # Short ID like: a1b2c3d4e5f6
            print(f"🔍 Generated session ID: {session_id}")
            # For local (uploaded) events, folder_id = session_id so files go to storage/uploads/admin_id/session_id/
            if folder_id == 'uploaded':
                folder_id = session_id
                print(f"🔍 Local event: folder_id set to session_id for per-event storage")
            # Create session document
            session_data = {
                'session_id': session_id,
                'admin_user_id': admin_user_id,
                'folder_id': folder_id,
                'metadata': metadata,
                'created_at': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(days=30)).isoformat(),  # 30 days validity
                'access_count': 0,
                'status': 'active'
            }
            if photo_paths is not None:
                session_data['photo_paths'] = photo_paths
            print(f"🔍 Session data prepared: {session_data}")
            
            # Save to Firestore
            print(f"🔍 Saving to Firestore collection: {SESSIONS_COLLECTION}")
            try:
                doc_ref = self.db.collection(SESSIONS_COLLECTION).document(session_id)
                doc_ref.set(session_data)
                print(f"🔍 Document saved to Firebase")
            except Exception as firebase_error:
                print(f"❌ Firebase save failed: {firebase_error}")
                print("🔄 Falling back to local storage")
                return self._create_local_session(admin_user_id, folder_id, metadata, photo_paths=photo_paths)
            
            print(f"✅ Created shared session: {session_id}")
            print(f"   Admin: {admin_user_id}")
            print(f"   Folder: {folder_id}")
            print(f"   Event: {metadata.get('event_name', 'N/A')}")
            
            return session_id
            
        except Exception as e:
            print(f"❌ Error creating shared session: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_local_session(self, admin_user_id: str, folder_id: str, metadata: Dict[str, Any],
                              photo_paths: Optional[List[str]] = None) -> Optional[str]:
        """Create session using local file storage when Firebase is not available"""
        try:
            import os
            
            # Create sessions directory if it doesn't exist
            sessions_dir = 'storage/sessions'
            os.makedirs(sessions_dir, exist_ok=True)
            
            # Generate unique session ID
            session_id = str(uuid.uuid4())[:12]
            if folder_id == 'uploaded':
                folder_id = session_id
            # Create session data
            session_data = {
                'session_id': session_id,
                'admin_user_id': admin_user_id,
                'folder_id': folder_id,
                'metadata': metadata,
                'created_at': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'access_count': 0,
                'status': 'active'
            }
            if photo_paths is not None:
                session_data['photo_paths'] = photo_paths
            
            # Save to local file
            session_file = os.path.join(sessions_dir, f"{session_id}.json")
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            print(f"✅ Created local session: {session_id}")
            return session_id
            
        except Exception as e:
            print(f"❌ Error creating local session: {e}")
            return None
    
    def find_session_for_admin_and_folder(self, admin_user_id: str, folder_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an existing active, non‑expired session for a given admin + folder.
        Returns the session data dict if found, otherwise None.
        """
        try:
            if not admin_user_id or not folder_id:
                return None
            
            if self.db is None:
                # Fallback to local file lookup
                return self._find_local_session_for_admin_and_folder(admin_user_id, folder_id)
            
            # Query Firestore for matching sessions
            query = (
                self.db.collection(SESSIONS_COLLECTION)
                .where('admin_user_id', '==', admin_user_id)
                .where('folder_id', '==', folder_id)
            )
            docs = list(query.stream())
            
            for doc in docs:
                session_data = doc.to_dict()
                # Skip inactive sessions
                if session_data.get('status') != 'active':
                    continue
                
                # Skip expired sessions
                expires_at_str = session_data.get('expires_at')
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if datetime.utcnow() > expires_at:
                            continue
                    except Exception:
                        # If parsing fails, be safe and skip this record
                        continue
                
                # Attach Firestore document ID for convenience
                session_data.setdefault('id', doc.id)
                print(f"✅ Found existing shared session for admin={admin_user_id}, folder={folder_id}: {session_data.get('session_id') or doc.id}")
                return session_data
            
            # Nothing found
            return None
        
        except Exception as e:
            print(f"❌ Error finding session for admin/folder: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _find_local_session_for_admin_and_folder(self, admin_user_id: str, folder_id: str) -> Optional[Dict[str, Any]]:
        """Local‑file equivalent of find_session_for_admin_and_folder."""
        try:
            sessions_dir = 'storage/sessions'
            if not os.path.isdir(sessions_dir):
                return None
            
            for filename in os.listdir(sessions_dir):
                if not filename.endswith('.json'):
                    continue
                session_file = os.path.join(sessions_dir, filename)
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                except Exception:
                    continue
                
                if data.get('admin_user_id') != admin_user_id:
                    continue
                if data.get('folder_id') != folder_id:
                    continue
                if data.get('status') != 'active':
                    continue
                
                expires_at_str = data.get('expires_at')
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if datetime.utcnow() > expires_at:
                            continue
                    except Exception:
                        continue
                
                print(f"✅ Found local shared session for admin={admin_user_id}, folder={folder_id}: {data.get('session_id')}")
                return data
            
            return None
        
        except Exception as e:
            print(f"❌ Error finding local session for admin/folder: {e}")
            return None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session details by session ID
        
        Args:
            session_id: The session ID to retrieve
        
        Returns:
            Session data dict or None if not found/expired
        """
        try:
            if self.db is None:
                print("⚠️  No Firebase client; checking local files for session")
                return self._get_local_session(session_id)
            
            # Try Firebase first
            try:
                # Get session document
                doc_ref = self.db.collection(SESSIONS_COLLECTION).document(session_id)
                doc = doc_ref.get()
            
                if not doc.exists:
                    print(f"❌ Session not found in Firebase: {session_id}")
                    # Fallback to local session storage if Firebase record is missing.
                    return self._get_local_session(session_id)
            
                session_data = doc.to_dict()
            
                # Check if expired
                expires_at = datetime.fromisoformat(session_data['expires_at'])
                if datetime.utcnow() > expires_at:
                    print(f"❌ Session expired: {session_id}")
                    return None
            
                # Check if active
                if session_data.get('status') != 'active':
                    print(f"❌ Session not active: {session_id}")
                    return None
            
                # Increment access count
                doc_ref.update({'access_count': session_data.get('access_count', 0) + 1})
                
                print(f"✅ Retrieved session from Firebase: {session_id}")
                return session_data
                
            except Exception as firebase_error:
                print(f"⚠️  Firebase error, falling back to local storage: {firebase_error}")
                return self._get_local_session(session_id)
            
        except Exception as e:
            print(f"❌ Error getting session: {e}")
            return None
    
    def _get_local_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from local file storage when Firebase is not available"""
        try:
            import os
            
            session_file = os.path.join('storage/sessions', f"{session_id}.json")
            
            if not os.path.exists(session_file):
                print(f"❌ Session file not found: {session_file}")
                return None
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session_data.get('expires_at', ''))
            if datetime.utcnow() > expires_at:
                print(f"❌ Session expired: {session_id}")
                return None
            
            # Increment access count
            session_data['access_count'] = session_data.get('access_count', 0) + 1
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            print(f"✅ Retrieved local session: {session_id}")
            return session_data
            
        except Exception as e:
            print(f"❌ Error getting local session: {e}")
            return None
    
    def deactivate_session(self, session_id: str, admin_user_id: str) -> bool:
        """
        Deactivate a session (only by admin who created it)
        
        Args:
            session_id: Session to deactivate
            admin_user_id: Admin requesting deactivation
        
        Returns:
            True if successful
        """
        try:
            if self.db is None:
                return False
            
            doc_ref = self.db.collection(SESSIONS_COLLECTION).document(session_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            session_data = doc.to_dict()
            
            # Verify admin owns this session
            if session_data.get('admin_user_id') != admin_user_id:
                print(f"❌ Unauthorized: {admin_user_id} cannot deactivate session {session_id}")
                return False
            
            # Deactivate
            doc_ref.update({'status': 'inactive'})
            print(f"✅ Deactivated session: {session_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error deactivating session: {e}")
            return False
    
    def append_photo_paths_to_session(self, session_id: str, new_relative_paths: List[str]) -> bool:
        """Append photo paths to an existing session (for event-add-photos). Returns True if updated."""
        if not new_relative_paths:
            return True
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                return False
            current = list(session_data.get('photo_paths') or [])
            seen = set(current)
            for p in new_relative_paths:
                if p and p not in seen:
                    current.append(p)
                    seen.add(p)
            updated_paths = current
            if self.db is not None:
                doc_ref = self.db.collection(SESSIONS_COLLECTION).document(session_id)
                doc_ref.update({'photo_paths': updated_paths})
                print(f"✅ Updated session {session_id} photo_paths: +{len(new_relative_paths)} total {len(updated_paths)}")
                return True
            session_file = os.path.join('storage', 'sessions', f"{session_id}.json")
            if os.path.isfile(session_file):
                session_data['photo_paths'] = updated_paths
                with open(session_file, 'w') as f:
                    json.dump(session_data, f, indent=2)
                print(f"✅ Updated local session {session_id} photo_paths: +{len(new_relative_paths)} total {len(updated_paths)}")
                return True
            return False
        except Exception as e:
            print(f"❌ Error appending photo paths to session: {e}")
            return False

    def get_admin_sessions(self, admin_user_id: str) -> List[Dict[str, Any]]:
        """
        Get all sessions created by an admin
        
        Args:
            admin_user_id: The admin user ID
        
        Returns:
            List of session dictionaries
        """
        try:
            if self.db is None:
                return []
            
            # Query sessions by admin
            query = self.db.collection(SESSIONS_COLLECTION).where('admin_user_id', '==', admin_user_id)
            docs = query.stream()
            
            sessions = []
            for doc in docs:
                session_data = doc.to_dict()
                session_data['id'] = doc.id
                sessions.append(session_data)
            
            print(f"✅ Retrieved {len(sessions)} sessions for admin {admin_user_id}")
            return sessions
            
        except Exception as e:
            print(f"❌ Error getting admin sessions: {e}")
            return []

# Global instance
_session_manager = None

def get_session_manager() -> SharedSessionManager:
    """Get or create the shared session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SharedSessionManager()
    return _session_manager

