@echo off
echo ========================================
echo CloudFace AI - Building Executable
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if web_server.py exists
if not exist "web_server.py" (
    echo ❌ Error: web_server.py not found!
    echo Please run this script from the CloudFace AI project directory
    pause
    exit /b 1
)

echo ✅ Python found
echo ✅ Project files found
echo.

REM Install PyInstaller
echo 📦 Installing PyInstaller...
python -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo ❌ Failed to install PyInstaller
    pause
    exit /b 1
)

echo ✅ PyInstaller installed
echo.

REM Run the build script
echo 🔨 Starting build process...
python build_exe.py

if errorlevel 1 (
    echo ❌ Build failed!
    pause
    exit /b 1
)

echo.
echo 🎉 Build completed successfully!
echo 📁 Your executable is in the 'dist' folder
echo 🚀 Run 'Start_CloudFace_AI.bat' to start the app
echo.
pause
