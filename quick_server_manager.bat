@echo off
title Facetak Server Manager
color 0A

:menu
cls
echo ========================================
echo    FACETAK SERVER MANAGER
echo ========================================
echo.
echo Choose an option:
echo.
echo [1] Start All Servers
echo [2] Stop All Servers  
echo [3] Restart All Servers
echo [4] Check Server Status
echo [5] Exit
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto start_servers
if "%choice%"=="2" goto stop_servers
if "%choice%"=="3" goto restart_servers
if "%choice%"=="4" goto check_status
if "%choice%"=="5" goto exit
goto menu

:start_servers
cls
echo ========================================
echo    STARTING ALL SERVERS
echo ========================================
echo.
echo Starting servers on different ports...
echo.

echo [1/1] Starting Main App (Port 8550)...
start "Facetak Main App" cmd /k "python main_app.py"
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo    ALL SERVERS STARTED!
echo ========================================
echo.
echo Server running on:
echo - Main App: http://localhost:8550
echo.
pause
goto menu

:stop_servers
cls
echo ========================================
echo    STOPPING ALL SERVERS
echo ========================================
echo.

echo Stopping all Facetak servers...
echo.

echo [1/3] Stopping Python processes on Facetak ports...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :855') do (
    echo Stopping process on port 855%%a
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo [2/3] Force killing all Python processes...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1

echo.
echo [3/3] Cleaning up any remaining processes...
wmic process where "name='python.exe'" delete >nul 2>&1
wmic process where "name='pythonw.exe'" delete >nul 2>&1

echo.
echo ========================================
echo    ALL SERVERS STOPPED!
echo ========================================
echo.
pause
goto menu

:restart_servers
cls
echo ========================================
echo    RESTARTING ALL SERVERS
echo ========================================
echo.
echo Stopping servers first...
call :stop_servers >nul
echo.
echo Starting servers again...
call :start_servers >nul
goto menu

:check_status
cls
echo ========================================
echo    CHECKING SERVER STATUS
echo ========================================
echo.
echo Checking which servers are running...
echo.

set found=0
for /f "tokens=2,5" %%a in ('netstat -an ^| findstr :855') do (
    echo Port %%a - Status: ACTIVE
    set found=1
)

if %found%==0 (
    echo No Facetak servers are currently running.
    echo.
    echo Available port:
echo - 8550: Main App
) else (
    echo.
    echo Found %found% active server(s)
)

echo.
pause
goto menu

:exit
cls
echo ========================================
echo    GOODBYE!
echo ========================================
echo.
echo Thanks for using Facetak Server Manager!
echo.
timeout /t 2 /nobreak >nul
exit
