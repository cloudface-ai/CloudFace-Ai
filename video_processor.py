#!/usr/bin/env python3
"""
Video Face Recognition Engine - Separate Implementation
Based on real_face_recognition_engine.py but specialized for video processing
Completely separate from main image processing system
"""

import cv2
import numpy as np
import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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

class VideoProgressTracker:
    """Track video processing progress separately from image processing"""
    
    def __init__(self):
        self.current_progress = 0
        self.total_frames = 0
        self.processed_frames = 0
        self.current_video = ""
        self.status = "idle"
        self.faces_found = 0
        self.errors = []
        self.start_time = None
        self.lock = threading.Lock()
    
    def start_processing(self, video_name: str, total_frames: int):
        """Start processing a video"""
        with self.lock:
            self.current_video = video_name
            self.total_frames = total_frames
            self.processed_frames = 0
            self.current_progress = 0
            self.status = "processing"
            self.faces_found = 0
            self.errors = []
            self.start_time = time.time()
    
    def update_progress(self, processed_frames: int, faces_found: int = 0):
        """Update processing progress"""
        with self.lock:
            self.processed_frames = processed_frames
            self.faces_found += faces_found
            if self.total_frames > 0:
                self.current_progress = min(100, (processed_frames / self.total_frames) * 100)
    
    def complete_processing(self):
        """Mark processing as complete"""
        with self.lock:
            self.status = "completed"
            self.current_progress = 100
    
    def add_error(self, error: str):
        """Add an error to the list"""
        with self.lock:
            self.errors.append(error)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current processing status"""
        with self.lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            return {
                'status': self.status,
                'progress': round(self.current_progress, 1),
                'current_video': self.current_video,
                'processed_frames': self.processed_frames,
                'total_frames': self.total_frames,
                'faces_found': self.faces_found,
                'errors': self.errors,
                'elapsed_time': round(elapsed, 1)
            }

class VideoFaceRecognitionEngine:
    """
    Video Face Recognition Engine - Separate from image processing
    Handles video upload, frame extraction, and face recognition
    """
    
    def __init__(self):
        """Initialize video face recognition engine."""
        self.app = None
        self.faiss_index = None
        self.face_database = {}  # Store face metadata with timestamps
        self.embedding_dim = 512  # ArcFace standard
        self.progress_tracker = VideoProgressTracker()
        
        # Video-specific settings
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
        self.frame_skip = 30  # Process every 30th frame (1 frame per second at 30fps)
        
        self._initialize_models()
        self._initialize_faiss()
    
    def _initialize_models(self):
        """Initialize InsightFace models (RetinaFace + ArcFace)."""
        if not INSIGHTFACE_AVAILABLE:
            logger.error("InsightFace not available")
            return
        
        try:
            print("🔧 Initializing video face recognition models...")
            self.app = FaceAnalysis(providers=['CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            print("✅ Video face recognition models initialized")
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            self.app = None
    
    def _initialize_faiss(self):
        """Initialize FAISS index for video faces."""
        if not FAISS_AVAILABLE:
            logger.error("FAISS not available")
            return
        
        try:
            # Create separate FAISS index for video faces
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
            print("✅ Video FAISS index initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS: {e}")
    
    def extract_frames_from_video(self, video_path: str, max_frames: int = 1000) -> List[Tuple[np.ndarray, float]]:
        """
        Extract frames from video with timestamps
        Returns: List of (frame, timestamp) tuples
        """
        frames = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception(f"Could not open video: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            print(f"📹 Video info: {total_frames} frames, {fps} fps, {duration:.1f}s")
            
            # Calculate frame skip to stay under max_frames
            skip_frames = max(1, total_frames // max_frames) if max_frames > 0 else self.frame_skip
            
            frame_count = 0
            extracted_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Skip frames based on skip_frames
                if frame_count % skip_frames == 0:
                    timestamp = frame_count / fps if fps > 0 else frame_count
                    frames.append((frame, timestamp))
                    extracted_count += 1
                    
                    if extracted_count >= max_frames:
                        break
                
                frame_count += 1
            
            cap.release()
            print(f"✅ Extracted {len(frames)} frames from video")
            
        except Exception as e:
            print(f"❌ Error extracting frames: {e}")
            return []
        
        return frames
    
    def detect_faces_in_frame(self, frame: np.ndarray, timestamp: float) -> List[Dict[str, Any]]:
        """
        Detect faces in a single video frame
        Returns: List of face data with embeddings and timestamp
        """
        if self.app is None:
            return []
        
        try:
            # Detect faces using InsightFace
            faces = self.app.get(frame)
            
            face_data = []
            for i, face in enumerate(faces):
                # Extract face embedding (512D ArcFace)
                embedding = face.embedding
                
                # Normalize embedding for cosine similarity
                embedding = embedding / np.linalg.norm(embedding)
                
                # Get bounding box
                bbox = face.bbox.astype(int)
                
                face_info = {
                    'embedding': embedding,
                    'bbox': bbox.tolist(),
                    'timestamp': timestamp,
                    'confidence': float(face.det_score),
                    'face_id': f"frame_{timestamp:.2f}_face_{i}"
                }
                
                face_data.append(face_info)
            
            return face_data
            
        except Exception as e:
            print(f"❌ Error detecting faces in frame at {timestamp:.2f}s: {e}")
            return []
    
    def process_video(self, video_path: str, user_id: str, video_id: str = None) -> Dict[str, Any]:
        """
        Process entire video for face recognition
        Returns: Processing results with face count and metadata
        """
        try:
            print(f"🎬 Starting video processing: {video_path}")
            
            # Extract frames from video
            frames = self.extract_frames_from_video(video_path)
            if not frames:
                return {'success': False, 'error': 'Could not extract frames from video'}
            
            # Initialize progress tracking
            video_name = os.path.basename(video_path)
            self.progress_tracker.start_processing(video_name, len(frames))
            
            # Process frames in batches
            all_faces = []
            batch_size = 10
            
            for i in range(0, len(frames), batch_size):
                batch = frames[i:i + batch_size]
                batch_faces = []
                
                # Process batch frames
                for frame, timestamp in batch:
                    frame_faces = self.detect_faces_in_frame(frame, timestamp)
                    batch_faces.extend(frame_faces)
                
                all_faces.extend(batch_faces)
                
                # Update progress
                processed_count = min(i + batch_size, len(frames))
                self.progress_tracker.update_progress(processed_count, len(batch_faces))
                
                print(f"📊 Processed {processed_count}/{len(frames)} frames, found {len(batch_faces)} faces")
            
            # Add faces to FAISS database
            if all_faces:
                self._add_video_faces_to_database(all_faces, user_id, video_name, video_id)
            
            # Complete processing
            self.progress_tracker.complete_processing()
            
            result = {
                'success': True,
                'video_id': video_id or video_name,
                'video_name': video_name,
                'video_path': video_path,
                'total_frames': len(frames),
                'faces_found': len(all_faces),
                'processing_time': self.progress_tracker.get_status()['elapsed_time']
            }
            
            print(f"✅ Video processing complete: {len(all_faces)} faces found")
            return result
            
        except Exception as e:
            error_msg = f"Error processing video: {e}"
            print(f"❌ {error_msg}")
            self.progress_tracker.add_error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def _add_video_faces_to_database(self, faces: List[Dict[str, Any]], user_id: str, video_name: str, video_id: str = None):
        """Add video faces to FAISS database"""
        try:
            if not faces or self.faiss_index is None:
                return
            
            # Prepare embeddings for FAISS
            embeddings = np.array([face['embedding'] for face in faces]).astype('float32')
            
            # Add to FAISS index
            start_id = self.faiss_index.ntotal
            self.faiss_index.add(embeddings)
            
            # Store metadata
            for i, face in enumerate(faces):
                face_id = start_id + i
                self.face_database[face_id] = {
                    'user_id': user_id,
                    'video_id': video_id or video_name,
                    'video_name': video_name,
                    'timestamp': face['timestamp'],
                    'bbox': face['bbox'],
                    'confidence': face['confidence'],
                    'face_id': face['face_id']
                }
            
            print(f"📊 Added {len(faces)} video faces to database")
            
        except Exception as e:
            print(f"❌ Error adding faces to database: {e}")
    
    def search_video_faces(self, query_image_path: str, user_id: str, video_id: str = None, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """
        Search for similar faces in processed videos
        If video_id is provided, search only within that specific video
        Returns: List of matches with video name, timestamp, and similarity
        """
        try:
            if self.faiss_index is None or self.faiss_index.ntotal == 0:
                return []
            
            # Load and process query image
            query_image = cv2.imread(query_image_path)
            if query_image is None:
                return []
            
            # Detect face in query image
            query_faces = self.detect_faces_in_frame(query_image, 0.0)
            if not query_faces:
                return []
            
            # Use first detected face as query
            query_embedding = query_faces[0]['embedding'].reshape(1, -1).astype('float32')
            
            # Search in FAISS
            k = min(100, self.faiss_index.ntotal)  # Top 100 results
            similarities, indices = self.faiss_index.search(query_embedding, k)
            
            # Filter results by threshold and user
            matches = []
            for similarity, idx in zip(similarities[0], indices[0]):
                if similarity >= threshold and idx in self.face_database:
                    face_data = self.face_database[idx]
                    
                    # Only return faces from this user
                    if face_data['user_id'] == user_id:
                        # If video_id specified, filter by that video only
                        if video_id and face_data.get('video_id') != video_id:
                            continue
                            
                        matches.append({
                            'video_id': face_data.get('video_id', face_data['video_name']),
                            'video_name': face_data['video_name'],
                            'timestamp': face_data['timestamp'],
                            'similarity': float(similarity),
                            'bbox': face_data['bbox'],
                            'confidence': face_data['confidence'],
                            'face_id': face_data['face_id']
                        })
            
            # Sort by similarity
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            
            return matches
            
        except Exception as e:
            print(f"❌ Error searching video faces: {e}")
            return []
    
    def get_user_videos(self, user_id: str) -> List[Dict[str, Any]]:
        """Get list of processed videos for a user"""
        try:
            videos = {}
            
            # Collect unique videos from face database
            for face_id, face_data in self.face_database.items():
                if face_data['user_id'] == user_id:
                    video_id = face_data.get('video_id', face_data['video_name'])
                    video_name = face_data['video_name']
                    
                    if video_id not in videos:
                        videos[video_id] = {
                            'video_id': video_id,
                            'video_name': video_name,
                            'faces_count': 0,
                            'first_processed': face_data.get('timestamp', 0)
                        }
                    
                    videos[video_id]['faces_count'] += 1
            
            # Convert to list and sort by first processed time
            video_list = list(videos.values())
            video_list.sort(key=lambda x: x['first_processed'], reverse=True)
            
            return video_list
            
        except Exception as e:
            print(f"❌ Error getting user videos: {e}")
            return []
    
    def get_video_info(self, user_id: str, video_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific video"""
        try:
            faces_in_video = []
            timestamps = []
            
            # Collect all faces from this video
            for face_id, face_data in self.face_database.items():
                if (face_data['user_id'] == user_id and 
                    face_data.get('video_id') == video_id):
                    faces_in_video.append(face_data)
                    timestamps.append(face_data['timestamp'])
            
            if not faces_in_video:
                return {'success': False, 'error': 'Video not found'}
            
            # Calculate video statistics
            unique_timestamps = sorted(set(timestamps))
            video_name = faces_in_video[0]['video_name']
            
            return {
                'success': True,
                'video_id': video_id,
                'video_name': video_name,
                'faces_count': len(faces_in_video),
                'unique_timestamps': len(unique_timestamps),
                'duration_range': {
                    'start': min(timestamps),
                    'end': max(timestamps)
                }
            }
            
        except Exception as e:
            print(f"❌ Error getting video info: {e}")
            return {'success': False, 'error': str(e)}
    
    def save_video_database(self, user_id: str):
        """Save video face database to disk"""
        try:
            # Create video database directory
            db_dir = os.path.join('storage', 'video_faces')
            os.makedirs(db_dir, exist_ok=True)
            
            # Save FAISS index
            faiss_path = os.path.join(db_dir, f"{user_id}_video.faiss")
            if self.faiss_index and self.faiss_index.ntotal > 0:
                faiss.write_index(self.faiss_index, faiss_path)
            
            # Save metadata
            metadata_path = os.path.join(db_dir, f"{user_id}_video_metadata.json")
            with open(metadata_path, 'w') as f:
                # Convert numpy arrays to lists for JSON serialization
                serializable_db = {}
                for k, v in self.face_database.items():
                    serializable_db[k] = v.copy()
                
                json.dump(serializable_db, f, indent=2)
            
            print(f"💾 Saved video database: {len(self.face_database)} faces")
            
        except Exception as e:
            print(f"❌ Error saving video database: {e}")
    
    def load_video_database(self, user_id: str):
        """Load video face database from disk"""
        try:
            db_dir = os.path.join('storage', 'video_faces')
            
            # Load FAISS index
            faiss_path = os.path.join(db_dir, f"{user_id}_video.faiss")
            if os.path.exists(faiss_path):
                self.faiss_index = faiss.read_index(faiss_path)
                print(f"📊 Loaded video FAISS index: {self.faiss_index.ntotal} faces")
            
            # Load metadata
            metadata_path = os.path.join(db_dir, f"{user_id}_video_metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.face_database = json.load(f)
                    # Convert string keys back to integers
                    self.face_database = {int(k): v for k, v in self.face_database.items()}
                
                print(f"📊 Loaded video metadata: {len(self.face_database)} faces")
            
        except Exception as e:
            print(f"❌ Error loading video database: {e}")

# Global video processor instance
video_processor = VideoFaceRecognitionEngine()
