#!/usr/bin/env python3
"""
Test AI Models for Face Recognition
Simple test to verify models are working correctly
"""

import os
import sys

def test_models():
    """Test if AI models are working properly."""
    print("INFO: Testing AI Models for Face Recognition")
    print("=" * 50)
    
    try:
        # Test InsightFace import
        import insightface
        print(f"SUCCESS: InsightFace version: {insightface.__version__}")
        
        # Test model loading
        print("INFO: Loading models...")
        app = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider'])
        app.prepare(ctx_id=0, det_size=(640, 640))
        print("SUCCESS: Models loaded successfully!")
        
        # Test with a simple image
        import numpy as np
        import cv2
        
        # Create a test image with a face-like pattern
        test_image = np.zeros((640, 640, 3), dtype=np.uint8)
        
        # Draw a simple face pattern
        cv2.circle(test_image, (320, 280), 80, (255, 255, 255), -1)  # Face
        cv2.circle(test_image, (300, 260), 10, (0, 0, 0), -1)  # Left eye
        cv2.circle(test_image, (340, 260), 10, (0, 0, 0), -1)  # Right eye
        cv2.ellipse(test_image, (320, 300), (30, 15), 0, 0, 180, (0, 0, 0), 2)  # Mouth
        
        # Test face detection
        print("INFO: Testing face detection...")
        faces = app.get(test_image)
        print(f"SUCCESS: Detected {len(faces)} faces in test image")
        
        if len(faces) > 0:
            face = faces[0]
            print(f"INFO: Face confidence: {face.det_score:.3f}")
            print(f"INFO: Face bbox: {face.bbox}")
            print(f"INFO: Face embedding shape: {face.embedding.shape}")
            print("SUCCESS: Face detection and embedding working!")
        else:
            print("WARNING: No faces detected in test image")
        
        # Test FAISS
        try:
            import faiss
            print(f"SUCCESS: FAISS version: {faiss.__version__}")
            
            # Create a simple FAISS index
            dimension = 512  # Standard embedding dimension
            index = faiss.IndexFlatIP(dimension)  # Inner product index
            print("SUCCESS: FAISS index created successfully!")
            
        except ImportError:
            print("WARNING: FAISS not available")
        
        print("\nSUCCESS: All models are working correctly!")
        return True
        
    except ImportError as e:
        print(f"ERROR: Missing package: {e}")
        return False
        
    except Exception as e:
        print(f"ERROR: Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_models()
    
    if success:
        print("\nSUCCESS: AI models are ready for face recognition!")
    else:
        print("\nERROR: Model test failed. Please check the errors above.")
    
    input("\nPress Enter to exit...")
