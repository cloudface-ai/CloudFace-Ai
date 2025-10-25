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
    
    def create_session(self, admin_user_id: str, folder_id: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Create a new shared session after admin processes photos
        
        Args:
            admin_user_id: The admin who processed the photos
            folder_id: The Google Drive folder ID that was processed
            metadata: Additional info (event name, date, company, etc.)
        
        Returns:
            session_id: Unique session ID for sharing
        """
        try:
            print(f"🔍 Creating session - Admin: {admin_user_id}, Folder: {folder_id}")
            print(f"🔍 Firebase DB status: {self.db is not None}")
            
            if self.db is None:
                print("⚠️  No Firebase client; using local file storage for sessions")
                return self._create_local_session(admin_user_id, folder_id, metadata)
            
            # Generate unique session ID
            session_id = str(uuid.uuid4())[:12]  # Short ID like: a1b2c3d4e5f6
            print(f"🔍 Generated session ID: {session_id}")
            
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
            print(f"🔍 Session data prepared: {session_data}")
            
            # Save to Firestore
            print(f"🔍 Saving to Firebase collection: {SESSIONS_COLLECTION}")
            try:
                doc_ref = self.db.collection(SESSIONS_COLLECTION).document(session_id)
                doc_ref.set(session_data)
                print(f"🔍 Document saved to Firebase")
            except Exception as firebase_error:
                print(f"❌ Firebase save failed: {firebase_error}")
                print("🔄 Falling back to local storage")
                return self._create_local_session(admin_user_id, folder_id, metadata)
            
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
    
    def _create_local_session(self, admin_user_id: str, folder_id: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Create session using local file storage when Firebase is not available"""
        try:
            import os
            
            # Create sessions directory if it doesn't exist
            sessions_dir = 'storage/sessions'
            os.makedirs(sessions_dir, exist_ok=True)
            
            # Generate unique session ID
            session_id = str(uuid.uuid4())[:12]
            
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
            
            # Save to local file
            session_file = os.path.join(sessions_dir, f"{session_id}.json")
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            print(f"✅ Created local session: {session_id}")
            return session_id
            
        except Exception as e:
            print(f"❌ Error creating local session: {e}")
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
                    return None
                
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

