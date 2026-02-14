#!/usr/bin/env python3
"""
Local Folder Processor for Facetak V2
Handles local folder processing with V2 facial recognition pipeline
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading

# Import real face recognition engine
from real_face_recognition_engine import get_real_engine

# Import real progress tracker
from real_progress_tracker import progress_tracker

# Import Firebase store for database integration
from firebase_store import save_face_embedding


def _event_photos_dir(event_id: str) -> str:
    """Canonical event photo storage path: storage/events/{event_id}/photos/"""
    return os.path.join('storage', 'events', event_id, 'photos')

class LocalFolderProcessor:
    def __init__(self, real_engine=None):
        self.real_engine = real_engine or get_real_engine()
        self.processed_count = 0
        self.total_files = 0
        self.errors = []
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
        self.batch_size = 8  # Process 8 images concurrently
        self.lock = threading.Lock()  # For thread-safe counter updates
        self.max_folder_depth = 5  # Maximum folder nesting depth for safety
        
    def _process_single_file(self, file_obj, user_id, file_index, session_id=None):
        """Process a single uploaded file - thread-safe. session_id = event/session folder (per-event storage)."""
        try:
            file_name = file_obj.filename
            
            print(f"📷 Processing {file_index+1}/{self.total_files}: {file_name}")
            print(f"🔧 DEBUG: Raw filename: {repr(file_name)}")
            print(f"🔧 DEBUG: File object type: {type(file_obj)}")
            
            # Create unique photo reference for uploaded files
            photo_reference = f"uploaded_{user_id}_{hashlib.md5(file_name.encode()).hexdigest()[:16]}_{file_name}"
            
            # Save to canonical event folder when session_id provided: storage/events/{event_id}/photos/
            if session_id:
                upload_folder = _event_photos_dir(session_id)
            else:
                upload_folder = os.path.join('storage', 'uploads', user_id)
            print(f"🔧 DEBUG: Upload folder: {upload_folder}")
            
            # Handle nested folder structure in filename (e.g., "1111/ABN10404.jpg")
            file_path = os.path.join(upload_folder, file_name)
            print(f"🔧 DEBUG: Full file path: {repr(file_path)}")
            
            # Create all necessary directories
            dir_path = os.path.dirname(file_path)
            print(f"🔧 DEBUG: Directory path: {repr(dir_path)}")
            os.makedirs(dir_path, exist_ok=True)
            print(f"🔧 DEBUG: Created directories successfully")
            
            # Read image bytes BEFORE saving (file pointer is at start)
            file_bytes = file_obj.read()
            file_obj.seek(0)  # Reset for saving
            
            file_obj.save(file_path)
            print(f"💾 Saved uploaded file: {file_path}")
            
            # file_bytes now contains the image data
            
            # Convert bytes to opencv image
            nparr = np.frombuffer(file_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                print(f"⚠️  Could not decode image: {file_name}")
                with self.lock:
                    self.errors.append(f"Could not decode: {file_name}")
                return
            
            # Detect and embed faces using real engine
            faces = self.real_engine.detect_and_embed_faces(image)
            
            if not faces:
                print(f"⚠️  No faces detected in: {file_name}")
                return
            
            # Save each detected face to database
            faces_processed = 0
            for face_idx, face in enumerate(faces):
                embedding = face['embedding']
                
                # Create unique reference for each face
                face_reference = f"{photo_reference}_face_{face_idx}"
                
                # Save to Firebase
                success = save_face_embedding(user_id, face_reference, embedding)
                
                if success:
                    # Also add to FAISS database for search (scope = session_id for per-event, else "uploaded")
                    folder_scope = session_id if session_id else "uploaded"
                    self.real_engine.add_face_to_database(face, face_reference, user_id, folder_scope)
                    print(f"✅ Saved face {face_idx+1} from {file_name} (Firebase + FAISS)")
                    faces_processed += 1
                else:
                    print(f"❌ Failed to save face from {file_name}")
                    with self.lock:
                        self.errors.append(f"Failed to save face from: {file_name}")
            
            # Update counters thread-safely
            with self.lock:
                self.processed_count += faces_processed
            
            # Update progress
            with self.lock:
                progress = ((file_index + 1) / self.total_files) * 100
                progress_tracker.set_progress('processing', int(progress))
                
        except Exception as e:
            print(f"❌ Error processing {file_obj.filename}: {e}")
            with self.lock:
                self.errors.append(f"Error processing {file_obj.filename}: {str(e)}")

    def _process_single_file_from_path(self, file_path, user_id, upload_folder, file_index, folder_scope="uploaded"):
        """Process a single file from disk path (canonical event folder or legacy uploads folder)."""
        try:
            file_name = os.path.basename(file_path)
            if not os.path.isfile(file_path):
                return
            photo_reference = f"uploaded_{user_id}_{hashlib.md5(file_name.encode()).hexdigest()[:16]}_{file_name}"
            file_bytes = open(file_path, 'rb').read()
            nparr = np.frombuffer(file_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                with self.lock:
                    self.errors.append(f"Could not decode: {file_name}")
                return
            faces = self.real_engine.detect_and_embed_faces(image)
            if not faces:
                return
            faces_processed = 0
            for face_idx, face in enumerate(faces):
                face_reference = f"{photo_reference}_face_{face_idx}"
                success = save_face_embedding(user_id, face_reference, face['embedding'])
                if success:
                    self.real_engine.add_face_to_database(face, face_reference, user_id, folder_scope)
                    faces_processed += 1
            with self.lock:
                self.processed_count += faces_processed
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            with self.lock:
                self.errors.append(f"Error processing {os.path.basename(file_path)}: {str(e)}")

    def process_uploaded_files_from_paths(self, user_id, file_paths, session_id=None):
        """Process file paths under storage/events/{event_id}/photos/ or legacy uploads path."""
        try:
            self.processed_count = 0
            self.errors = []
            self.total_files = len(file_paths)
            if self.total_files == 0:
                return {'success': True, 'total_files': 0, 'processed_count': 0, 'errors': [], 'message': 'No files to process'}
            if session_id:
                upload_folder = os.path.abspath(_event_photos_dir(session_id))
                folder_scope = session_id
            else:
                upload_folder = os.path.abspath(os.path.join('storage', 'uploads', user_id))
                folder_scope = "uploaded"
            self.real_engine.set_scope(user_id, folder_scope)
            self.real_engine.load_database()
            for i, path in enumerate(file_paths):
                abs_path = os.path.abspath(path)
                if os.path.isfile(abs_path) and (abs_path == upload_folder or abs_path.startswith(upload_folder + os.sep)):
                    self._process_single_file_from_path(abs_path, user_id, upload_folder, i, folder_scope=folder_scope)
            if self.processed_count > 0:
                try:
                    self.real_engine.save_database()
                    print(f"💾 Saved FAISS database (append) with {self.processed_count} new faces")
                except Exception as e:
                    print(f"⚠️ Could not save FAISS database: {e}")
            return {
                'success': True,
                'total_files': self.total_files,
                'processed_count': self.processed_count,
                'errors': self.errors,
                'message': f'Successfully processed {self.processed_count} faces from {self.total_files} images'
            }
        except Exception as e:
            print(f"❌ Error in process_uploaded_files_from_paths: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def process_uploaded_files(self, uploaded_files, user_id, force_reprocess=False, session_id=None):
        """
        Process uploaded files with real facial recognition.
        session_id = event/session folder: files saved to storage/uploads/user_id/session_id/ and FAISS scope = session_id.
        """
        try:
            print(f"🔍 Starting uploaded files processing")
            print(f"📁 Number of files: {len(uploaded_files)}")
            print(f"🔄 Force reprocess: {force_reprocess}")
            print(f"📁 Session (event) ID: {session_id or 'none (legacy uploaded)'}")
            
            # Filter for image files
            image_files = self._filter_uploaded_image_files(uploaded_files)
            self.total_files = len(image_files)
            
            print(f"📁 Found {self.total_files} image files in folder")
            
            if self.total_files == 0:
                return {'success': False, 'error': 'No supported image files found'}
            
            # Initialize progress tracking
            progress_tracker.start_progress()
            progress_tracker.set_total(self.total_files)
            progress_tracker.update_folder_info("Uploaded Files", self.total_files, 0)

            # FAISS scope: per-event (session_id) or legacy "uploaded"
            folder_scope = session_id if session_id else "uploaded"
            self.real_engine.set_scope(user_id, folder_scope)
            self.real_engine.load_database()
            
            # Process images with batch processing
            progress_tracker.set_status('processing', 'Processing uploaded images...')
            print(f"🚀 Starting batch processing with {self.batch_size} concurrent threads")
            
            with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                # Submit all files for processing
                futures = []
                for i, file_obj in enumerate(image_files):
                    future = executor.submit(self._process_single_file, file_obj, user_id, i, session_id)
                    futures.append(future)
                
                # Wait for all to complete
                for future in futures:
                    try:
                        future.result()  # This will raise any exceptions from the thread
                    except Exception as e:
                        print(f"❌ Batch processing error: {e}")
            
            print(f"🏁 Batch processing completed!")
            
            # Complete processing
            progress_tracker.set_status('database', 'Finalizing database...')
            progress_tracker.set_progress('database', 100)
            
            # Save FAISS database after processing
            if self.processed_count > 0:
                try:
                    self.real_engine.save_database()
                    print(f"💾 Saved FAISS database with {self.processed_count} new faces")
                except Exception as e:
                    print(f"⚠️  Warning: Could not save FAISS database: {e}")
            
            # Track usage for pricing plans
            try:
                from pricing_manager import pricing_manager
                pricing_manager.track_image_usage(user_id, self.processed_count)
            except ImportError:
                print("⚠️  Pricing manager not available")
            
            # Complete all progress steps
            progress_tracker.complete_all_steps()
            
            print(f"✅ Local folder processing completed!")
            print(f"📊 Processed: {self.processed_count} faces from {self.total_files} files")
            print(f"❌ Errors: {len(self.errors)}")
            
            return {
                'success': True,
                'total_files': self.total_files,
                'processed_count': self.processed_count,
                'errors': self.errors,
                'message': f'Successfully processed {self.processed_count} faces from {self.total_files} uploaded images'
            }
            
        except Exception as e:
            print(f"❌ Critical error in uploaded files processing: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': f'Processing failed: {str(e)}'}
    
    def _filter_uploaded_image_files(self, uploaded_files):
        """Filter uploaded files to only include supported image formats with folder depth safety"""
        image_files = []
        folder_stats = {}
        
        for file_obj in uploaded_files:
            if hasattr(file_obj, 'filename') and file_obj.filename:
                filename = file_obj.filename
                
                # Check folder depth for security
                folder_depth = len(Path(filename).parts) - 1  # -1 because filename itself is not a folder
                if folder_depth > self.max_folder_depth:
                    print(f"⚠️  Skipping file with excessive folder depth ({folder_depth}): {filename}")
                    continue
                
                # Check file extension
                file_ext = Path(filename).suffix.lower()
                if file_ext in self.supported_extensions:
                    image_files.append(file_obj)
                    
                    # Track folder structure for stats
                    folder_path = str(Path(filename).parent) if Path(filename).parent != Path('.') else 'root'
                    folder_stats[folder_path] = folder_stats.get(folder_path, 0) + 1
        
        # Print folder structure stats
        if folder_stats:
            print(f"📁 Folder structure detected:")
            for folder, count in sorted(folder_stats.items()):
                print(f"   📂 {folder}: {count} images")
        
        print(f"📷 Filtered to {len(image_files)} image files from {len(uploaded_files)} total files")
        return image_files

# Global processor instance
local_processor = LocalFolderProcessor()

def process_uploaded_files_and_store(user_id, uploaded_files, force_reprocess=False, session_id=None):
    """
    Main function to process uploaded files and store faces.
    session_id = event folder (storage/uploads/user_id/session_id/ and FAISS scope session_id).
    """
    return local_processor.process_uploaded_files(uploaded_files, user_id, force_reprocess, session_id=session_id)

if __name__ == "__main__":
    # Test the processor
    if len(sys.argv) < 3:
        print("Usage: python local_folder_processor.py <folder_path> <user_id>")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    user_id = sys.argv[2]
    
    result = process_local_folder_and_store(user_id, folder_path)
    print(f"Result: {result}")
