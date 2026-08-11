@echo off
setlocal enabledelayedexpansion
title StoryVoice AI Control Panel

:: Change directory to the folder where this batch file is located
cd /d "%~dp0"

:: Set UI color (Light Aqua on Black background)
color 0B

:main_menu
cls
echo =====================================================================
echo                StoryVoice AI - Control Panel
echo =====================================================================
echo  StoryVoice AI is an offline-capable multi-voice audiobook generator.
echo  This panel manages the Next.js frontend and FastAPI backend.
echo =====================================================================
echo.
echo  [1] Start Both Services (Frontend + Backend)
echo  [2] Start Backend Server Only (FastAPI)
echo  [3] Start Frontend App Only (Next.js)
echo  [4] Install/Update Dependencies (Setup environment)
echo  [5] Stop Running Services
echo  [6] Exit
echo.
echo =====================================================================
set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" goto start_both
if "%choice%"=="2" goto start_backend
if "%choice%"=="3" goto start_frontend
if "%choice%"=="4" goto run_setup
if "%choice%"=="5" goto stop_services
if "%choice%"=="6" goto exit_script
goto main_menu

:start_both
cls
echo =====================================================================
echo                  Starting StoryVoice AI Services
echo =====================================================================
echo.

:: Check backend venv
if not exist "backend\venv" (
    echo [!] Backend virtual environment not found at backend\venv.
    choice /m "Would you like to run the environment setup first?"
    if errorlevel 2 goto cancel_launch
    call :setup_env
)

:: Check frontend node_modules
if not exist "frontend\node_modules" (
    echo [!] Frontend node_modules not found at frontend\node_modules.
    choice /m "Would you like to run the environment setup first?"
    if errorlevel 2 goto cancel_launch
    call :setup_env
)

echo Starting Backend Server in a new window...
start "StoryVoice AI - Backend Server" cmd /k "title StoryVoice AI - Backend Server && cd backend && echo [BACKEND] Starting server... && venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting Frontend App in a new window...
start "StoryVoice AI - Frontend App" cmd /k "title StoryVoice AI - Frontend App && cd frontend && echo [FRONTEND] Starting dev server... && npm run dev"

:: Give servers a few seconds to start up
timeout /t 3 >nul

:running_status
cls
echo =====================================================================
echo                  StoryVoice AI is Running!
echo =====================================================================
echo.
echo   * Frontend App:  http://localhost:3000
echo   * Backend API:   http://localhost:8000
echo   * API Docs:      http://localhost:8000/docs
echo.
echo =====================================================================
echo   [S] Stop all services and return to menu
echo   [R] Restart all services
echo   [M] Keep services running and return to menu
echo   [X] Stop services and Exit
echo =====================================================================
echo.

choice /c SRMX /n /m "Select action: "
if errorlevel 4 goto stop_and_exit
if errorlevel 3 goto main_menu
if errorlevel 2 goto restart_services
if errorlevel 1 goto stop_services_from_status
goto running_status

:cancel_launch
echo.
echo Launch cancelled. Returning to main menu.
timeout /t 2 >nul
goto main_menu

:restart_services
echo.
echo Restarting services...
call :stop_only
timeout /t 2 >nul
goto start_both

:stop_services_from_status
echo.
call :stop_only
pause
goto main_menu

:stop_and_exit
echo.
call :stop_only
goto exit_script

:stop_services
cls
echo =====================================================================
echo                   Stopping StoryVoice AI Services
echo =====================================================================
echo.
call :stop_only
echo.
pause
goto main_menu

:stop_only
echo Stopping Backend Server...
taskkill /FI "WINDOWTITLE eq StoryVoice AI - Backend Server*" /T /F >nul 2>&1
echo Stopping Frontend App...
taskkill /FI "WINDOWTITLE eq StoryVoice AI - Frontend App*" /T /F >nul 2>&1
echo All services stopped successfully.
exit /b

:start_backend
cls
echo =====================================================================
echo                  Starting Backend Server Only
echo =====================================================================
echo.
if not exist "backend\venv" (
    echo [!] Backend virtual environment not found.
    choice /m "Would you like to run the environment setup first?"
    if errorlevel 2 goto cancel_launch
    call :setup_env
)
start "StoryVoice AI - Backend Server" cmd /k "title StoryVoice AI - Backend Server && cd backend && echo [BACKEND] Starting server... && venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo Backend started in a separate window.
echo API Docs: http://localhost:8000/docs
echo.
pause
goto main_menu

:start_frontend
cls
echo =====================================================================
echo                  Starting Frontend App Only
echo =====================================================================
echo.
if not exist "frontend\node_modules" (
    echo [!] Frontend node_modules not found.
    choice /m "Would you like to run the environment setup first?"
    if errorlevel 2 goto cancel_launch
    call :setup_env
)
start "StoryVoice AI - Frontend App" cmd /k "title StoryVoice AI - Frontend App && cd frontend && echo [FRONTEND] Starting dev server... && npm run dev"
echo Frontend started in a separate window.
echo Frontend App: http://localhost:3000
echo.
pause
goto main_menu

:run_setup
call :setup_env
goto main_menu

:setup_env
cls
echo =====================================================================
echo               StoryVoice AI - Environment Setup
echo =====================================================================
echo.
echo This utility will configure virtual environments and install dependencies
echo for both frontend and backend directories.
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.11+ and try again.
    pause
    exit /b
)

:: Check for Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in system PATH.
    echo Please install Node.js and try again.
    pause
    exit /b
)

:: Backend Venv Setup
echo [1/3] Checking Backend virtual environment...
if not exist "backend\venv" (
    echo Creating Python virtual environment in backend\venv...
    python -m venv backend\venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)
echo.

:: Backend Pip Setup
echo [2/3] Installing Backend dependencies...
echo Upgrading pip...
backend\venv\Scripts\python.exe -m pip install --upgrade pip
echo Installing requirements...
backend\venv\Scripts\pip.exe install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install backend requirements.
    pause
    exit /b
)
echo.

:: Frontend Npm Setup
echo [3/3] Installing Frontend dependencies...
cd frontend
echo Running npm install...
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend npm packages.
    cd ..
    pause
    exit /b
)
cd ..
echo.
echo =====================================================================
echo               Environment Configured Successfully!
echo =====================================================================
echo.
pause
exit /b

:exit_script
cls
echo =====================================================================
echo             Thank you for using StoryVoice AI Control Panel!
echo =====================================================================
echo.
timeout /t 2 >nul
exit
