"""
firebase_store.py - Save and query face embeddings and metadata in Firebase Firestore.
"""
import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np

# Load environment variables from example.env (dev/local)
load_dotenv('.env', override=True)

# Firebase configuration from environment variables
FIREBASE_CONFIG = {
    "apiKey": os.environ.get('FIREBASE_API_KEY'),
    "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN'),
    "projectId": os.environ.get('FIREBASE_PROJECT_ID'),
    "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.environ.get('FIREBASE_APP_ID'),
    "measurementId": os.environ.get('FIREBASE_MEASUREMENT_ID')
}

# Initialize Firebase Admin SDK using service account credentials
db: Optional[firestore.Client] = None

def initialize_firebase():
    global db
    if db is not None:
        return db

    try:
        if firebase_admin._apps:
            db = firestore.client()
            print("SUCCESS: Firebase Firestore client ready (existing app)")
            return db

        # Try to use JSON credentials file first
        credentials_path = os.path.join('credentials', 'firebase-adminsdk.json')
        if os.path.exists(credentials_path):
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("SUCCESS: Firebase Firestore client ready (JSON credentials)")
            return db
        
        # Fallback to environment variables
        required_vars = ['FIREBASE_PROJECT_ID', 'FIREBASE_API_KEY', 'FIREBASE_AUTH_DOMAIN']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            raise RuntimeError(f"Missing required Firebase environment variables: {missing_vars}")

        # Initialize Firebase Admin SDK with default credentials
        # This will use the environment variables for authentication
        firebase_admin.initialize_app()
        db = firestore.client()
        print("SUCCESS: Firebase Firestore client ready (environment variables)")
        return db

    except Exception as e:
        print(f"ERROR: Firebase init failed: {e}")
        return None

# Initialize on import
db = initialize_firebase()

FACES_COLLECTION = 'faces'


def save_face_embedding(user_id: str, photo_ref: str, embedding: np.ndarray, folder_id: str = None) -> bool:
    """Persist a face embedding for a photo reference under a user with folder isolation."""
    try:
        if db is None:
            print(f"WARNING: No Firebase client; simulate save for {photo_ref}")
            return True
        
        # Convert numpy array to list for Firestore
        embedding_list = embedding.tolist()
        
        # Create document data with folder isolation
        doc_data = {
            'user_id': user_id,
            'photo_reference': photo_ref,
            'face_embedding': embedding_list,
            'embedding_dimension': len(embedding_list),
            'folder_id': folder_id,  # Add folder_id for isolation
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        # Save to Firestore
        doc_ref = db.collection(FACES_COLLECTION).add(doc_data)
        print(f"SUCCESS: Saved face embedding for {photo_ref} (doc ID: {doc_ref[1].id})")
        return True
        
    except Exception as e:
        print(f"ERROR: save_face_embedding error: {e}")
        return False


def fetch_embeddings_for_user(user_id: str, folder_id: str = None) -> List[Dict[str, Any]]:
    """Fetch face records for a user, optionally filtered by folder_id for isolation."""
    try:
        if db is None:
            print(f"WARNING: No Firebase client; return empty list for {user_id}")
            return []
        
        # Query Firestore for user's face embeddings with optional folder isolation
        query = db.collection(FACES_COLLECTION).where('user_id', '==', user_id)
        
        # Add folder_id filter if specified for folder isolation
        if folder_id is not None:
            query = query.where('folder_id', '==', folder_id)
            print(f"🔍 Filtering embeddings by folder_id: {folder_id}")
        
        docs = query.stream()
        
        results = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Add document ID
            results.append(doc_data)
        
        filter_msg = f" (folder: {folder_id})" if folder_id else " (all folders)"
        print(f"SUCCESS: Fetched {len(results)} face embeddings for user {user_id}{filter_msg}")
        return results
        
    except Exception as e:
        print(f"ERROR: fetch_embeddings_for_user error: {e}")
        return []


def delete_user_face(user_id: str, face_id: str) -> bool:
    """Delete a single face row by id ensuring ownership."""
    try:
        if db is None:
            print(f"WARNING: No Firebase client; simulate delete {face_id}")
            return True
        
        # Get the document and verify ownership
        doc_ref = db.collection(FACES_COLLECTION).document(face_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            print(f"WARNING: Document {face_id} not found")
            return False
        
        doc_data = doc.to_dict()
        if doc_data.get('user_id') != user_id:
            print(f"WARNING: Document {face_id} does not belong to user {user_id}")
            return False
        
        # Delete the document
        doc_ref.delete()
        print(f"SUCCESS: Deleted face embedding {face_id}")
        return True
        
    except Exception as e:
        print(f"ERROR: delete_user_face error: {e}")
        return False


def clear_all_faces() -> bool:
    """Clear all face embeddings from Firestore."""
    try:
        if db is None:
            print("WARNING: No Firebase client; cannot clear faces")
            return False
        
        # Get all documents in the collection
        docs = db.collection(FACES_COLLECTION).stream()
        
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        print(f"SUCCESS: Cleared {deleted_count} face embeddings from Firebase")
        return True
        
    except Exception as e:
        print(f"ERROR: clear_all_faces error: {e}")
        return False


def get_firebase_stats() -> Dict[str, Any]:
    """Get Firebase collection statistics."""
    try:
        if db is None:
            return {"error": "No Firebase client"}
        
        # Count total documents
        docs = db.collection(FACES_COLLECTION).stream()
        total_docs = sum(1 for _ in docs)
        
        # Count by user
        user_counts = {}
        docs = db.collection(FACES_COLLECTION).stream()
        for doc in docs:
            user_id = doc.to_dict().get('user_id', 'unknown')
            user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        return {
            "total_faces": total_docs,
            "users": user_counts,
            "collection": FACES_COLLECTION
        }
        
    except Exception as e:
        return {"error": str(e)}
