@echo off
chcp 65001 >nul
setlocal

set "REPO=%USERPROFILE%\pc_doctor"
set "REPO_URL=https://github.com/il-oong/pc_doctor.git"

echo ========================================
echo  PC Doctor Setup
echo ========================================
echo.

REM -- python check
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Install from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"!
    pause & exit /b 1
)
echo [OK] Python found.

REM -- git check
where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git not found.
    echo Install from: https://git-scm.com/download/win
    pause & exit /b 1
)
echo [OK] Git found.

REM -- clone or pull
if not exist "%REPO%\main.py" (
    echo Downloading PC Doctor...
    git clone "%REPO_URL%" "%REPO%"
    if errorlevel 1 (
        echo [ERROR] Download failed.
        pause & exit /b 1
    )
    echo [OK] Download complete.
) else (
    echo Checking for updates...
    git -C "%REPO%" pull --ff-only
)

REM -- install psutil
echo Installing dependencies...
python -m pip install psutil
echo [OK] Dependencies ready.

REM -- create desktop shortcut
echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$r='%REPO%'; $pw=Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'; if(-not(Test-Path $pw)){$pw=(Get-Command python).Source}; $d=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut($d+'\PC Doctor.lnk'); $lnk.TargetPath=$pw; $lnk.Arguments='"'+$r+'\main.py"'; $lnk.WorkingDirectory=$r; $lnk.Description='PC Doctor'; $lnk.Save(); Write-Host '[OK] Shortcut created: '+$d+'\PC Doctor.lnk'"

echo.
echo ========================================
echo  Done! Launch PC Doctor now? (y/n)
echo ========================================
set /p RUN="> "
if /i "%RUN%"=="y" start "" pythonw "%REPO%\main.py"

echo.
echo Shortcut is on your Desktop: PC Doctor
pause
