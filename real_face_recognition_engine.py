#!/usr/bin/env python3
"""
Real Face Recognition Engine - Phase 1 Implementation
Uses InsightFace for real RetinaFace detection + ArcFace embeddings
Following CORE_MVP_ROADMAP.md
"""

import cv2
import numpy as np
import os
from typing import List, Dict, Any, Optional, Tuple
import logging

# Real face recognition imports
try:
    import insightface
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    print("WARNING: InsightFace not installed. Install with: pip install insightface")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("WARNING: FAISS not installed. Install with: pip install faiss-cpu")

logger = logging.getLogger(__name__)

class RealFaceRecognitionEngine:
    """
    Real Face Recognition Engine using InsightFace (RetinaFace + ArcFace)
    Phase 1 implementation following CORE_MVP_ROADMAP.md
    """
    
    def __init__(self):
        """Initialize real face recognition engine."""
        self.app = None
        self.faiss_index = None
        self.face_database = {}  # Store face metadata
        self.embedding_dim = 512  # ArcFace standard
        # Current storage scope (multi-tenant isolation)
        self.current_user_id: Optional[str] = None
        self.current_folder_id: Optional[str] = None
        # In-process locks per scope to avoid concurrent writes
        self._scope_locks: Dict[Tuple[str, str], Any] = {}
        
        self._initialize_models()
        self._initialize_faiss()
    
    def _initialize_models(self):
        """Initialize InsightFace models (RetinaFace + ArcFace)."""
        if not INSIGHTFACE_AVAILABLE:
            logger.error("InsightFace not available - using fallback")
            return
        
        try:
            print("INFO: Initializing RetinaFace detection + ArcFace embeddings...")
            
            # Initialize InsightFace app with RetinaFace + ArcFace
            self.app = FaceAnalysis(providers=['CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            
            print("SUCCESS: Real face recognition models loaded!")
            print("  INFO: RetinaFace: State-of-the-art face detection")
            print("  INFO: ArcFace: MS-Celeb-1M trained embeddings")
            
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            self.app = None
    
    def _initialize_faiss(self):
        """Initialize FAISS vector database for fast search."""
        if not FAISS_AVAILABLE:
            logger.error("FAISS not available - using linear search")
            return
        
        try:
            # Always create a fresh in-memory index; persistence handled via save/load per scope
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            print("✅ Created new FAISS index with inner product for 512D embeddings")
            
        except Exception as e:
            logger.error(f"FAISS initialization failed: {e}")
            self.faiss_index = None
    
    def detect_and_embed_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces and extract embeddings using real models.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of face data with embeddings
        """
        if not self.app:
            return self._fallback_detection_embedding(image)
        
        try:
            # Use InsightFace for detection + embedding in one step
            faces = self.app.get(image)
            
            results = []
            for face in faces:
                # Extract data from InsightFace result
                bbox = face.bbox.astype(int).tolist()  # [x1, y1, x2, y2]
                landmarks = face.kps.astype(int).tolist()  # 5 facial landmarks
                embedding = face.embedding  # 512D ArcFace embedding
                confidence = float(face.det_score)
                
                # Calculate face quality
                face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                image_area = image.shape[0] * image.shape[1]
                quality_score = min(face_area / image_area * 10, 1.0)
                
                results.append({
                    'bbox': bbox,
                    'landmarks': landmarks,
                    'embedding': embedding,
                    'confidence': confidence,
                    'quality_score': quality_score,
                    'detector': 'RetinaFace_Real',
                    'extractor': 'ArcFace_Real'
                })
            
            print(f"🔍 Detected {len(results)} faces with real RetinaFace + ArcFace")
            return results
            
        except Exception as e:
            logger.error(f"Real face recognition failed: {e}")
            return self._fallback_detection_embedding(image)
    
    def _fallback_detection_embedding(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Fallback using MediaPipe + computer vision features."""
        try:
            import mediapipe as mp
            
            results = []
            with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                detections = face_detection.process(rgb_image)
                
                if detections.detections:
                    h, w, _ = image.shape
                    for detection in detections.detections:
                        bbox_rel = detection.location_data.relative_bounding_box
                        x1 = int(bbox_rel.xmin * w)
                        y1 = int(bbox_rel.ymin * h)
                        x2 = int((bbox_rel.xmin + bbox_rel.width) * w)
                        y2 = int((bbox_rel.ymin + bbox_rel.height) * h)
                        
                        # Extract face region for embedding
                        face_region = image[y1:y2, x1:x2]
                        if face_region.size == 0:
                            continue
                        
                        # Generate embedding using computer vision features
                        embedding = self._extract_cv_features(face_region)
                        
                        results.append({
                            'bbox': [x1, y1, x2, y2],
                            'landmarks': [[x1, y1], [x2, y1], [x1, y2], [x2, y2]],  # Basic corners
                            'embedding': embedding,
                            'confidence': detection.score[0],
                            'quality_score': 0.7,
                            'detector': 'MediaPipe_Fallback',
                            'extractor': 'CV_Features'
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"Fallback detection failed: {e}")
            return []
    
    def _extract_cv_features(self, face_region: np.ndarray) -> np.ndarray:
        """Extract computer vision features from face region."""
        try:
            # Resize to standard size
            face_resized = cv2.resize(face_region, (112, 112))
            gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
            
            features = []
            
            # 1. HOG features (good for face structure)
            from skimage.feature import hog
            hog_features = hog(gray, orientations=8, pixels_per_cell=(8, 8),
                              cells_per_block=(2, 2), visualize=False)
            features.extend(hog_features)
            
            # 2. LBP features (good for texture)
            from skimage.feature import local_binary_pattern
            lbp = local_binary_pattern(gray, 8, 1, method='uniform')
            lbp_hist, _ = np.histogram(lbp.ravel(), bins=10, range=(0, 10))
            features.extend(lbp_hist)
            
            # 3. Statistical features
            features.extend([gray.mean(), gray.std(), np.median(gray)])
            
            # Convert to numpy and normalize
            features = np.array(features, dtype=np.float32)
            
            # Resize to 512D (ArcFace standard)
            if len(features) != self.embedding_dim:
                if len(features) < self.embedding_dim:
                    # Repeat pattern
                    repeat_count = self.embedding_dim // len(features) + 1
                    features = np.tile(features, repeat_count)[:self.embedding_dim]
                else:
                    # Truncate
                    features = features[:self.embedding_dim]
            
            # L2 normalize (standard for face recognition)
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm
            
            return features
            
        except Exception as e:
            logger.error(f"CV feature extraction failed: {e}")
            # Return zero vector as last resort
            return np.zeros(self.embedding_dim, dtype=np.float32)
    
    def add_face_to_database(self, face_data: Dict[str, Any], person_id: str, user_id: str, folder_id: str):
        """Add face embedding to FAISS database with duplicate prevention."""
        try:
            embedding = face_data['embedding']
            
            # Check for duplicates first
            for existing_id, existing_data in self.face_database.items():
                if (existing_data['person_id'] == person_id and 
                    existing_data['user_id'] == user_id and 
                    existing_data['folder_id'] == folder_id):
                    print(f"⚠️  Skipping duplicate: {person_id} already exists in database")
                    return False
            
            # Add to FAISS index
            if self.faiss_index is not None:
                # Normalize embedding for cosine similarity
                embedding_norm = embedding / (np.linalg.norm(embedding) + 1e-8)
                
                # FAISS expects 2D array
                embedding_2d = embedding_norm.reshape(1, -1)
                self.faiss_index.add(embedding_2d)
                
                # Store metadata
                face_id = self.faiss_index.ntotal - 1  # Index of last added
                self.face_database[face_id] = {
                    'person_id': person_id,
                    'user_id': user_id,
                    'folder_id': folder_id,
                    'bbox': face_data['bbox'],
                    'confidence': face_data['confidence'],
                    'quality_score': face_data['quality_score'],
                    'detector': face_data['detector'],
                    'extractor': face_data['extractor']
                }
                
                print(f"💾 Added face to FAISS database: {person_id}")
                return True
            else:
                print(f"⚠️  FAISS not available, skipping database add")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add face to database: {e}")
            return False

    # ===== Multi-tenant storage helpers =====
    def set_scope(self, user_id: str, folder_id: str) -> None:
        """Set active storage/search scope for this engine."""
        self.current_user_id = user_id
        self.current_folder_id = folder_id

    def _ensure_scope(self) -> Tuple[str, str]:
        if not self.current_user_id or not self.current_folder_id:
            raise RuntimeError("Storage scope not set. Call set_scope(user_id, folder_id) before load/save/search.")
        return self.current_user_id, self.current_folder_id

    def _get_paths_for_scope(self) -> Tuple[str, str]:
        user_id, folder_id = self._ensure_scope()
        base_dir = os.path.join('models', user_id, folder_id)
        os.makedirs(base_dir, exist_ok=True)
        index_path = os.path.join(base_dir, 'face_embeddings.index')
        metadata_path = os.path.join(base_dir, 'face_metadata.json')
        return index_path, metadata_path

    def _get_scope_lock(self):
        user_id, folder_id = self._ensure_scope()
        key = (user_id, folder_id)
        if key not in self._scope_locks:
            try:
                import threading
                self._scope_locks[key] = threading.Lock()
            except Exception:
                # Fallback dummy lock
                class _NoLock:
                    def __enter__(self_inner):
                        return None
                    def __exit__(self_inner, exc_type, exc, tb):
                        return False
                self._scope_locks[key] = _NoLock()
        return self._scope_locks[key]
    
    def search_similar_faces(self, query_embedding: np.ndarray, user_id: str, folder_id: str,
                           k: int = None, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar faces using FAISS."""
        try:
            if self.faiss_index is None or self.faiss_index.ntotal == 0:
                print("❌ No faces in FAISS database")
                return []
            
            # Normalize query embedding for cosine similarity
            query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
            query_2d = query_norm.reshape(1, -1)
            
            # Search FAISS index - search ALL embeddings (no artificial limits)
            search_k = k if k is not None else self.faiss_index.ntotal
            similarities, indices = self.faiss_index.search(query_2d, min(search_k, self.faiss_index.ntotal))
            
            results = []
            for sim, idx in zip(similarities[0], indices[0]):
                if idx == -1:  # Invalid index
                    continue
                
                # Convert inner product to cosine similarity (FAISS 1.7.4 compatibility)
                # Since we normalized embeddings, inner product = cosine similarity
                # But clamp to valid range just in case
                similarity_clamped = max(0.0, min(1.0, float(sim)))
                
                if similarity_clamped >= threshold:
                    # Get face metadata
                    if idx in self.face_database:
                        face_meta = self.face_database[idx]
                        
                        # Filter by user and folder
                        if (face_meta['user_id'] == user_id and 
                            face_meta['folder_id'] == folder_id):
                            
                            # Extract file_id from person_id to find photo
                            person_id = face_meta['person_id']
                            if '_' in person_id:
                                file_id = person_id.split('_', 1)[1]
                                
                                # Find photo filename using file_id and mapping
                                photo_name = self._find_photo_by_file_id(user_id, file_id, folder_id)
                                
                                # Only add if photo found (prevent unknown.jpg entries)
                                if photo_name:
                                    results.append({
                                        'similarity': similarity_clamped,
                                        'person_id': person_id,
                                        'photo_name': photo_name,
                                        'photo_path': photo_name,
                                        'confidence': f"{similarity_clamped:.2%}",
                                        'quality_score': face_meta['quality_score'],
                                        'detector': face_meta['detector'],
                                        'extractor': face_meta['extractor']
                                    })
            
            # Sort by similarity (highest first)
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            print(f"🔍 FAISS search: {len(results)} matches above {threshold} threshold")
            
            # Return results with proper limit handling
            if k is None:
                return results  # Return all results
            else:
                return results[:k]  # Return limited results
            
        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            return []
    
    def search_similar_faces_universal(self, query_embedding: np.ndarray, user_id: str,
                           k: int = None, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar faces across ALL folders for a user using FAISS."""
        try:
            if self.faiss_index is None or self.faiss_index.ntotal == 0:
                print("❌ No faces in FAISS database")
                return []
            
            # Normalize query embedding for cosine similarity
            query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
            query_2d = query_norm.reshape(1, -1)
            
            # Search FAISS index - search ALL embeddings
            search_k = k if k is not None else self.faiss_index.ntotal
            similarities, indices = self.faiss_index.search(query_2d, min(search_k, self.faiss_index.ntotal))
            
            matches = []
            print(f"🔍 Universal search found {len(indices[0])} potential matches")
            
            for i, (similarity, idx) in enumerate(zip(similarities[0], indices[0])):
                if idx in self.face_database:
                    face_meta = self.face_database[idx]
                    
                    # Convert inner product to cosine similarity (normalized embeddings)
                    cosine_sim = float(similarity)
                    
                    if cosine_sim >= threshold:
                        
                        # Filter by user only (not folder - search ALL folders)
                        if face_meta['user_id'] == user_id:
                            
                            # Extract file_id from person_id to find photo
                            person_id = face_meta['person_id']
                            
                            # Handle both Drive and uploaded file formats
                            if person_id.startswith('uploaded_'):
                                # Uploaded file format: uploaded_user_hash_filename_face_0
                                # Example: uploaded_spvinodmandan@gmail.com_1234567890abcdef_1111/ABN10404.jpg_face_0
                                print(f"🔧 DEBUG: Processing uploaded person_id: {person_id}")
                                temp = person_id.replace('uploaded_', '')
                                temp = temp.replace(f'{user_id}_', '', 1)
                                print(f"🔧 DEBUG: After removing prefixes: {temp}")
                                
                                # Remove the hash (16 chars) and underscore
                                parts = temp.split('_', 1)  # Split at first underscore after hash
                                print(f"🔧 DEBUG: Split parts: {parts}")
                                if len(parts) >= 2:
                                    # parts[1] contains: "1111/ABN10404.jpg_face_0"
                                    filename_part = parts[1]
                                    # Remove face suffix
                                    photo_name = filename_part.replace('_face_0', '').replace('_face_1', '').replace('_face_2', '')
                                    print(f"🔧 DEBUG: Final photo_name: {photo_name}")
                                else:
                                    photo_name = temp
                                    print(f"🔧 DEBUG: Fallback photo_name: {photo_name}")
                                    
                                source = "Uploaded Files"
                                folder_id = "uploaded"
                            else:
                                # Drive file format: user_file_id
                                file_id = person_id.split('_', 1)[1] if '_' in person_id else person_id
                                folder_id = face_meta['folder_id']
                                photo_name = self._find_photo_by_file_id(user_id, file_id, folder_id)
                                source = "Google Drive"
                            
                            # Only add if photo found
                            if photo_name:
                                matches.append({
                                    'photo_name': photo_name,
                                    'photo_path': photo_name,  # Frontend expects photo_path
                                    'similarity': round(cosine_sim, 3),
                                    'person_id': person_id,
                                    'bbox': face_meta['bbox'],
                                    'confidence': face_meta['confidence'],
                                    'quality_score': face_meta['quality_score'],
                                    'source': source,
                                    'folder_id': folder_id
                                })
                                print(f"✅ Match {len(matches)}: {photo_name} (similarity: {cosine_sim:.3f}, source: {source})")
                        else:
                            print(f"⚠️  Skipping match - different user: {face_meta['user_id']} vs {user_id}")
                    else:
                        print(f"⚠️  Skipping match - low similarity: {cosine_sim:.3f} < {threshold}")
                else:
                    print(f"⚠️  Invalid index: {idx} not in face_database")
            
            print(f"🎯 Universal search completed: {len(matches)} matches found above threshold {threshold}")
            return matches
            
        except Exception as e:
            logger.error(f"Universal face search failed: {e}")
            return []
    
    def save_database(self):
        """Save FAISS index and metadata to disk for current scope."""
        try:
            if self.faiss_index is None:
                return False
            index_path, metadata_path = self._get_paths_for_scope()
            lock = self._get_scope_lock()
            with lock:
                faiss.write_index(self.faiss_index, index_path)
                # Save metadata
                import json
                with open(metadata_path, "w") as f:
                    serializable_db = {}
                    for k, v in self.face_database.items():
                        serializable_db[str(k)] = {
                            key: val.tolist() if isinstance(val, np.ndarray) else val
                            for key, val in v.items()
                        }
                    json.dump(serializable_db, f, indent=2)
            print(f"💾 Saved FAISS database with {self.faiss_index.ntotal} faces -> {index_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save database: {e}")
            return False
    
    def load_database(self):
        """Load FAISS index and metadata from disk for current scope."""
        try:
            index_path, metadata_path = self._get_paths_for_scope()
            if os.path.exists(index_path):
                self.faiss_index = faiss.read_index(index_path)
                print(f"✅ Loaded FAISS index with {self.faiss_index.ntotal} faces from {index_path}")
                # Load metadata
                if os.path.exists(metadata_path):
                    import json
                    with open(metadata_path, "r") as f:
                        serializable_db = json.load(f)
                    self.face_database = {}
                    for k, v in serializable_db.items():
                        self.face_database[int(k)] = v
                    print(f"✅ Loaded face metadata for {len(self.face_database)} faces")
                else:
                    self.face_database = {}
                return True
            else:
                # Initialize empty structures for new scope
                self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
                self.face_database = {}
                return True
        except Exception as e:
            logger.error(f"Failed to load database: {e}")
            return False
    
    def _find_photo_by_file_id(self, user_id: str, file_id: str, folder_id: str) -> Optional[str]:
        """Find photo filename by file_id in cache folder."""
        try:
            cache_folder = os.path.join('storage', 'downloads', f"{user_id}_{folder_id}")
            mapping_file = os.path.join(cache_folder, 'file_id_mapping.json')
            
            if os.path.exists(mapping_file):
                import json
                with open(mapping_file, 'r') as f:
                    file_mapping = json.load(f)
                return file_mapping.get(file_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding photo: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'total_faces': self.faiss_index.ntotal if self.faiss_index else 0,
            'embedding_dimension': self.embedding_dim,
            'insightface_available': INSIGHTFACE_AVAILABLE,
            'faiss_available': FAISS_AVAILABLE,
            'detection_model': 'RetinaFace' if INSIGHTFACE_AVAILABLE else 'MediaPipe',
            'embedding_model': 'ArcFace' if INSIGHTFACE_AVAILABLE else 'CV_Features'
        }

# Global engine instance
real_engine = None

def get_real_engine():
    """Get or create the real face recognition engine."""
    global real_engine
    if real_engine is None:
        print("🚀 Initializing face recognition engine (first time only)...")
        real_engine = RealFaceRecognitionEngine()
        # Do not auto-load any scope here; scope is set per user/folder by callers
        print("✅ Face recognition engine ready!")
    return real_engine

def process_image_with_real_recognition(image_path: str, person_id: str, user_id: str, folder_id: str) -> Dict[str, Any]:
    """Process image with real face recognition."""
    try:
        engine = get_real_engine()
        # Ensure scoped storage is active for this operation
        engine.set_scope(user_id, folder_id)
        engine.load_database()
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return {'success': False, 'error': 'Could not load image'}
        
        # Detect and embed faces
        faces = engine.detect_and_embed_faces(image)
        
        if not faces:
            return {'success': False, 'error': 'No faces detected'}
        
        # Add faces to database
        added_count = 0
        for face in faces:
            if engine.add_face_to_database(face, person_id, user_id, folder_id):
                added_count += 1
        
        # Save database to scoped paths
        engine.save_database()
        
        return {
            'success': True,
            'faces_detected': len(faces),
            'faces_added': added_count,
            'embeddings': [{'embedding': face['embedding'].tolist()} for face in faces]
        }
        
    except Exception as e:
        logger.error(f"Real face recognition processing failed: {e}")
        return {'success': False, 'error': str(e)}

def search_with_real_recognition(selfie_path: str, user_id: str, folder_id: str, threshold: float = 0.7) -> Dict[str, Any]:
    """Search for faces using real face recognition - LEGACY: folder-specific search."""
    try:
        engine = get_real_engine()
        engine.set_scope(user_id, folder_id)
        engine.load_database()
        
        # Load selfie
        image = cv2.imread(selfie_path)
        if image is None:
            return {'success': False, 'error': 'Could not load selfie'}
        
        # Extract embedding from selfie
        faces = engine.detect_and_embed_faces(image)
        
        if not faces:
            return {'success': False, 'faces_detected': 0, 'matches': [], 'message': 'No face detected in selfie'}
        
        # Use first detected face for search
        query_embedding = faces[0]['embedding']
        
        # Search FAISS database (folder-specific)
        matches = engine.search_similar_faces(query_embedding, user_id, folder_id, k=None, threshold=threshold)
        
        return {
            'success': True,
            'faces_detected': len(faces),
            'matches': matches,
            'total_matches': len(matches),
            'threshold': threshold
        }
        
    except Exception as e:
        logger.error(f"Search with real recognition failed: {e}")
        return {'success': False, 'error': str(e)}

def search_with_real_recognition_universal(selfie_path: str, user_id: str, threshold: float = 0.7) -> Dict[str, Any]:
    """Search for faces across ALL user's photos (Drive + Uploaded) using real face recognition."""
    try:
        engine = get_real_engine()
        
        # Load selfie
        image = cv2.imread(selfie_path)
        if image is None:
            return {'success': False, 'error': 'Could not load selfie'}
        
        # Extract embedding from selfie
        faces = engine.detect_and_embed_faces(image)
        
        if not faces:
            return {'success': False, 'faces_detected': 0, 'matches': [], 'message': 'No face detected in selfie'}
        
        # Use first detected face for search
        query_embedding = faces[0]['embedding']
        
        # Aggregate matches across all folder scopes for this user by loading each scoped index
        all_matches = []
        try:
            user_models_dir = os.path.join('models', user_id)
            if os.path.isdir(user_models_dir):
                for folder_id in os.listdir(user_models_dir):
                    folder_path = os.path.join(user_models_dir, folder_id)
                    if not os.path.isdir(folder_path):
                        continue
                    try:
                        engine.set_scope(user_id, folder_id)
                        engine.load_database()
                        folder_matches = engine.search_similar_faces(query_embedding, user_id, folder_id, k=None, threshold=threshold)
                        for m in folder_matches:
                            m['folder_id'] = folder_id
                        all_matches.extend(folder_matches)
                    except Exception as _e:
                        print(f"⚠️  Skipping folder {folder_id} due to error: {_e}")
        except Exception as _e:
            print(f"⚠️  Universal aggregation error: {_e}")
        # Sort aggregated matches by similarity desc
        all_matches.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        matches = all_matches
        
        return {
            'success': True,
            'faces_detected': len(faces),
            'matches': matches,
            'total_matches': len(matches),
            'threshold': threshold,
            'search_type': 'universal'
        }
        
    except Exception as e:
        logger.error(f"Universal search with real recognition failed: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    # Test the real engine
    engine = RealFaceRecognitionEngine()
    stats = engine.get_stats()
    print("🚀 Real Face Recognition Engine Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
