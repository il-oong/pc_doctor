@echo off
chcp 65001 >nul
setlocal

set "REPO=%USERPROFILE%\pc_doctor"
set "REPO_URL=https://github.com/il-oong/pc_doctor.git"

echo ========================================
echo  PC Doctor Setup
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Install: https://www.python.org/downloads/
    echo Check "Add Python to PATH" during install!
    pause & exit /b 1
)
echo [OK] Python found.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git not found.
    echo Install: https://git-scm.com/download/win
    pause & exit /b 1
)
echo [OK] Git found.

if not exist "%REPO%\main.py" (
    echo Downloading PC Doctor...
    git clone "%REPO_URL%" "%REPO%"
    if errorlevel 1 ( echo [ERROR] Download failed. & pause & exit /b 1 )
    echo [OK] Download complete.
) else (
    echo Updating...
    git -C "%REPO%" pull --ff-only
)

echo Installing dependencies...
python -m pip install psutil >nul 2>nul
echo [OK] Dependencies ready.

echo Creating desktop shortcut...
python "%REPO%\make_shortcut.py"
if errorlevel 1 ( echo [ERROR] Shortcut failed. & pause & exit /b 1 )

echo.
echo ========================================
echo  Done! Run PC Doctor now? (y/n)
echo ========================================
set /p RUN="> "
if /i "%RUN%"=="y" start "" pythonw "%REPO%\main.py"
echo.
pause
