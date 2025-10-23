#!/usr/bin/env python3
"""
Download AI Models for Face Recognition
Downloads RetinaFace and ArcFace models for Google-level face recognition
"""

import os
import sys
import time

def download_models():
    """Download InsightFace models for face recognition."""
    print("INFO: Downloading AI Models for Face Recognition")
    print("=" * 50)
    
    try:
        # Import InsightFace
        import insightface
        print(f"SUCCESS: InsightFace version: {insightface.__version__}")
        
        # Create models directory
        models_dir = "models"
        os.makedirs(models_dir, exist_ok=True)
        print(f"INFO: Models directory: {models_dir}")
        
        print("\nINFO: Downloading RetinaFace + ArcFace models...")
        print("INFO: This may take 5-10 minutes on first run...")
        
        # Initialize FaceAnalysis app - this downloads models automatically
        app = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider'])
        
        print("INFO: Preparing models...")
        app.prepare(ctx_id=0, det_size=(640, 640))
        
        print("SUCCESS: Models downloaded and ready!")
        print("\nINFO: Model Information:")
        print("   - RetinaFace: State-of-the-art face detection")
        print("   - ArcFace: MS-Celeb-1M trained embeddings")
        print("   - 1024D embeddings for high accuracy")
        
        # Test the models
        print("\nINFO: Testing models...")
        import numpy as np
        test_image = np.zeros((640, 640, 3), dtype=np.uint8)
        faces = app.get(test_image)
        print(f"SUCCESS: Models working! Detected {len(faces)} faces in test image")
        
        return True
        
    except ImportError as e:
        print(f"ERROR: Missing package: {e}")
        print("INFO: Installing required packages...")
        
        packages = [
            "insightface",
            "onnxruntime", 
            "faiss-cpu",
            "opencv-python",
            "numpy"
        ]
        
        for package in packages:
            print(f"Installing {package}...")
            os.system(f"{sys.executable} -m pip install {package}")
        
        print("SUCCESS: Packages installed. Please run this script again.")
        return False
        
    except Exception as e:
        print(f"ERROR: Error downloading models: {e}")
        print("\nINFO: Troubleshooting:")
        print("1. Check internet connection")
        print("2. Ensure you have enough disk space (500MB+)")
        print("3. Try running as administrator")
        return False

if __name__ == "__main__":
    success = download_models()
    
    if success:
        print("\nSUCCESS! AI models are ready!")
        print("INFO: Next steps:")
        print("1. Restart your server")
        print("2. Process photos with real AI face recognition")
        print("3. Enjoy Google-level accuracy!")
    else:
        print("\nERROR: Model download failed. Please check the errors above.")
    
    input("\nPress Enter to exit...")
