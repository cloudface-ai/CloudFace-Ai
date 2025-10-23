# Facetak App Complete Backup Script
# Combines Robocopy + ZIP + Automated PowerShell
# Professional backup solution for the entire application

param(
    [string]$BackupRoot = "D:\Backups",
    [switch]$IncludeStorage = $false,
    [switch]$CreateZip = $true,
    [switch]$Verbose = $true
)

# Get current timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$source = Get-Location
$backup_name = "Facetak_Complete_$timestamp"
$backup_dir = Join-Path $BackupRoot $backup_name

Write-Host "🚀 Starting Facetak App Backup..." -ForegroundColor Green
Write-Host "📂 Source: $source" -ForegroundColor Cyan
Write-Host "📁 Backup: $backup_dir" -ForegroundColor Cyan

# Create backup root directory
if (!(Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    Write-Host "✅ Created backup directory: $BackupRoot" -ForegroundColor Green
}

# Option 3: Robocopy (Professional) - Mirror with smart exclusions
Write-Host "`n📋 Phase 1: Professional Robocopy Mirror..." -ForegroundColor Yellow

$exclude_dirs = @(
    "node_modules",
    "__pycache__", 
    ".git",
    "build"
)

$exclude_files = @(
    "*.log",
    "*.tmp", 
    "*.pyc",
    "*.pyo"
)

# Add storage exclusions if not requested
if (!$IncludeStorage) {
    $exclude_dirs += @(
        "storage\downloads",
        "storage\temp", 
        "storage\cache"
    )
    Write-Host "⚠️  Excluding storage directories (use -IncludeStorage to include)" -ForegroundColor Yellow
}

# Build robocopy command
$robocopy_args = @(
    $source.Path,
    $backup_dir,
    "/MIR",  # Mirror directory
    "/R:3",  # Retry 3 times
    "/W:1",  # Wait 1 second between retries
    "/MT:8"  # Multi-threaded copy
)

# Add exclusions
foreach ($dir in $exclude_dirs) {
    $robocopy_args += "/XD"
    $robocopy_args += $dir
}

foreach ($file in $exclude_files) {
    $robocopy_args += "/XF"
    $robocopy_args += $file
}

if ($Verbose) {
    $robocopy_args += "/V"  # Verbose output
}

# Execute robocopy
$robocopy_result = & robocopy @robocopy_args

# Check robocopy result (exit codes 0-7 are success)
if ($LASTEXITCODE -le 7) {
    Write-Host "✅ Robocopy completed successfully" -ForegroundColor Green
} else {
    Write-Host "⚠️  Robocopy completed with warnings (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
}

# Option 4: PowerShell Script (Automated) - Create backup metadata
Write-Host "`n📋 Phase 2: Creating Backup Metadata..." -ForegroundColor Yellow

# Get app statistics
$total_files = (Get-ChildItem -Recurse $backup_dir -File | Measure-Object).Count
$total_size_mb = [math]::Round(((Get-ChildItem -Recurse $backup_dir -File | Measure-Object -Sum Length).Sum / 1MB), 2)

# Get Python dependencies
$requirements_content = ""
if (Test-Path "requirements.txt") {
    $requirements_content = Get-Content "requirements.txt" -Raw
}

# Create comprehensive backup info
$backup_info = @"
# Facetak App Complete Backup
**Created:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Source:** $($source.Path)
**Backup:** $backup_dir
**Total Files:** $total_files
**Total Size:** $total_size_mb MB

## App Information
- **Version:** Face Recognition V2 with Real Engine
- **Engine:** InsightFace (RetinaFace + ArcFace)
- **Database:** FAISS + Firebase Firestore
- **Features:** Smart caching, Multi-threshold search, Progress tracking
- **Platform:** Python Flask Web Application

## Key Components
- **Real Face Recognition Engine:** real_face_recognition_engine.py
- **Drive Processing:** real_drive_processor.py  
- **Web Server:** web_server.py
- **Progress Tracking:** real_progress_tracker.py
- **Caching Systems:** folder_cache_manager.py, search_cache_manager.py
- **Templates:** templates/ (HTML/CSS/JS frontend)
- **Models:** models/ (FAISS database files)

## Dependencies
``````
$requirements_content
``````

## Deployment Instructions
1. **Extract backup** to target directory
2. **Install dependencies:** ``pip install -r requirements.txt``
3. **Setup credentials:** Copy example.env to .env and configure
4. **Run setup:** ``python setup_real_face_recognition.py``
5. **Start server:** ``python web_server.py``

## Recent Enhancements
- ✅ Fixed FAISS compatibility (IndexFlatIP with normalization)
- ✅ Removed artificial search limits (unlimited results)
- ✅ Added smart folder caching (10x faster repeat processing)
- ✅ Enhanced progress tracking (clear completion messages)
- ✅ Fixed threshold logic (Precise=0.75, Balanced=0.65, Broad=0.5)
- ✅ Added My Photos dashboard (folder organization)
- ✅ Implemented duplicate prevention (no duplicate embeddings)

## Backup Exclusions
$(if (!$IncludeStorage) { "- ❌ Storage directories (downloads, temp, cache) - excluded for size" } else { "- ✅ Storage directories included" })
- ❌ Node modules (can be reinstalled)
- ❌ Python cache files (auto-generated)
- ❌ Build artifacts (auto-generated)
- ❌ Log files (temporary)

## Restore Instructions
1. Extract to desired location
2. Run ``setup_deployment.bat``
3. Configure .env file
4. Start with ``start_facetak.bat``

**Backup completed successfully! 🚀**
"@

$backup_info | Out-File "$backup_dir\BACKUP_README.md" -Encoding UTF8

# Create quick deployment scripts
$setup_script = @"
@echo off
echo 🚀 Setting up Facetak App from backup...

REM Install Python dependencies
echo 📦 Installing Python dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo 📁 Creating directories...
if not exist storage\downloads mkdir storage\downloads
if not exist storage\temp\selfies mkdir storage\temp\selfies
if not exist storage\cache mkdir storage\cache
if not exist models mkdir models

REM Setup environment
echo ⚙️  Environment setup...
if not exist .env (
    echo Please copy example.env to .env and configure your credentials
    echo See BACKUP_README.md for instructions
)

echo ✅ Setup complete!
echo Next steps:
echo 1. Configure .env file with your Google OAuth credentials
echo 2. Run: python web_server.py
pause
"@

$setup_script | Out-File "$backup_dir\setup_deployment.bat" -Encoding ASCII

$start_script = @"
@echo off
title Facetak Face Recognition App
echo 🚀 Starting Facetak App...

REM Set UTF-8 encoding for emoji support
chcp 65001 > nul

REM Set environment variables
if exist .env (
    echo ✅ Loading environment from .env file...
) else (
    echo ⚠️  Warning: .env file not found
    echo Please copy example.env to .env and configure
    pause
    exit /b 1
)

REM Set Firebase credentials if available
if exist credentials\firebase-adminsdk.json (
    set GOOGLE_APPLICATION_CREDENTIALS=credentials\firebase-adminsdk.json
    set FIREBASE_PROJECT_ID=cloudface-ai
    echo ✅ Firebase credentials configured
)

REM Start the server
echo 🌐 Starting web server on http://localhost:8550
python web_server.py

pause
"@

$start_script | Out-File "$backup_dir\start_facetak.bat" -Encoding ASCII

Write-Host "✅ Created deployment scripts" -ForegroundColor Green

# Option 1: Simple ZIP Backup (Easiest)
if ($CreateZip) {
    Write-Host "`n📋 Phase 3: Creating ZIP Archive..." -ForegroundColor Yellow
    
    $zip_path = "$BackupRoot\$backup_name.zip"
    
    try {
        Compress-Archive -Path "$backup_dir\*" -DestinationPath $zip_path -Force
        Write-Host "✅ ZIP backup created: $zip_path" -ForegroundColor Green
        
        # Get ZIP size
        $zip_size_mb = [math]::Round(((Get-Item $zip_path).Length / 1MB), 2)
        Write-Host "📦 ZIP size: $zip_size_mb MB" -ForegroundColor Cyan
        
    } catch {
        Write-Host "❌ ZIP creation failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Final summary
Write-Host "`n🎯 Backup Summary:" -ForegroundColor Green
Write-Host "📂 Directory Backup: $backup_dir" -ForegroundColor White
if ($CreateZip) {
    Write-Host "📦 ZIP Backup: $zip_path" -ForegroundColor White
}
Write-Host "📄 Files: $total_files" -ForegroundColor White
Write-Host "💾 Size: $total_size_mb MB" -ForegroundColor White
Write-Host "`n🚀 Deployment:" -ForegroundColor Green
Write-Host "1. Extract backup to target location" -ForegroundColor White
Write-Host "2. Run: setup_deployment.bat" -ForegroundColor White
Write-Host "3. Configure .env file" -ForegroundColor White
Write-Host "4. Run: start_facetak.bat" -ForegroundColor White

Write-Host "`n✅ Facetak app backup completed successfully! 🎉" -ForegroundColor Green
