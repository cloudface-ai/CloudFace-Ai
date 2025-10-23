"""
Build CloudFace AI as a standalone .exe file using PyInstaller
This script will create a distributable Windows executable
"""

import os
import subprocess
import sys
import shutil

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
        return True
    except ImportError:
        print("📦 Installing PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✅ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install PyInstaller")
            return False

def create_spec_file():
    """Create a custom .spec file for PyInstaller"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['web_server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('favicon.ico', '.'),
        ('apple-touch-icon.png', '.'),
        ('favicon-32x32.png', '.'),
        ('favicon-16x16.png', '.'),
        ('og-image.jpg', '.'),
        ('twitter-image.jpg', '.'),
        ('manifest.json', '.'),
        ('sw.js', '.'),
        ('robots.txt', '.'),
        ('sitemap.xml', '.'),
        ('google149ef140e8719d8c.html', '.'),
    ],
    hiddenimports=[
        'flask',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
        'blinker',
        'cv2',
        'numpy',
        'PIL',
        'requests',
        'firebase_admin',
        'google.auth',
        'google.oauth2',
        'googleapiclient',
        'faiss',
        'insightface',
        'torch',
        'torchvision',
        'tensorflow',
        'scikit-learn',
        'mediapipe',
        'face_recognition',
        'facenet_pytorch',
        'deepface',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CloudFace_AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico'
)
'''
    
    with open('CloudFace_AI.spec', 'w') as f:
        f.write(spec_content)
    
    print("✅ Created CloudFace_AI.spec file")

def build_executable():
    """Build the executable using PyInstaller"""
    print("🔨 Building CloudFace AI executable...")
    
    try:
        # Use the custom spec file
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", "CloudFace_AI.spec"]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Executable built successfully!")
            print(f"📁 Output: dist/CloudFace_AI.exe")
            return True
        else:
            print("❌ Build failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error building executable: {e}")
        return False

def create_startup_script():
    """Create a simple startup script"""
    startup_content = '''@echo off
echo Starting CloudFace AI...
echo.
echo The application will open in your default web browser.
echo If it doesn't open automatically, go to: http://localhost:8550
echo.
echo Press Ctrl+C to stop the application
echo.
CloudFace_AI.exe
pause
'''
    
    with open('Start_CloudFace_AI.bat', 'w') as f:
        f.write(startup_content)
    
    print("✅ Created Start_CloudFace_AI.bat")

def main():
    """Main build process"""
    print("🚀 CloudFace AI - Building Executable")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('web_server.py'):
        print("❌ Error: web_server.py not found!")
        print("Please run this script from the CloudFace AI project directory")
        return False
    
    # Step 1: Install PyInstaller
    if not install_pyinstaller():
        return False
    
    # Step 2: Create spec file
    create_spec_file()
    
    # Step 3: Build executable
    if not build_executable():
        return False
    
    # Step 4: Create startup script
    create_startup_script()
    
    print("\n🎉 SUCCESS!")
    print("=" * 50)
    print("✅ CloudFace AI executable created successfully!")
    print("📁 Location: dist/CloudFace_AI.exe")
    print("🚀 Startup script: Start_CloudFace_AI.bat")
    print("\n📋 Next Steps:")
    print("1. Test the executable: Run dist/CloudFace_AI.exe")
    print("2. The app will open at http://localhost:8550")
    print("3. Distribute the entire 'dist' folder to users")
    print("\n💡 Tip: Users can run Start_CloudFace_AI.bat for easy startup")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
