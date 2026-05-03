@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================
echo   PC Doctor 빌드
echo =========================================
echo.

REM ── Python 확인 ──────────────────────────────────────────────────────
python --version >nul 2>nul
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/
    echo 설치 시 "Add Python to PATH" 반드시 체크하세요.
    pause & exit /b 1
)
echo Python 버전:
python --version
echo.

REM ── PyInstaller + psutil 설치 ─────────────────────────────────────────
echo [1/3] 패키지 설치 중...
python -m pip install pyinstaller psutil
if errorlevel 1 (
    echo.
    echo [오류] pip install 실패했습니다.
    pause & exit /b 1
)
echo.

REM ── 이전 빌드 정리 ───────────────────────────────────────────────────
if exist "dist\PC닥터.exe" del /f /q "dist\PC닥터.exe"
if exist "build" rd /s /q "build" 2>nul

REM ── 빌드 ─────────────────────────────────────────────────────────────
echo [2/3] 빌드 중 (1~3분 소요)...
echo.
python -m PyInstaller --onefile --windowed --name "PC닥터" --hidden-import psutil --hidden-import psutil._pswindows --hidden-import winreg --hidden-import sqlite3 --hidden-import tkinter --hidden-import tkinter.ttk --hidden-import tkinter.messagebox --collect-submodules core --collect-submodules ui --collect-submodules utils --noconfirm main.py

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패! 위 오류 메시지를 확인하세요.
    pause & exit /b 1
)

if not exist "dist\PC닥터.exe" (
    echo [오류] dist\PC닥터.exe 파일이 없습니다.
    pause & exit /b 1
)

REM ── 바탕화면 경로 탐지 ───────────────────────────────────────────────
echo [3/3] 바탕화면에 복사 중...
set "DESKTOP="
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" 2^>nul`) do set "DESKTOP=%%D"
if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\바탕 화면" set "DESKTOP=%USERPROFILE%\OneDrive\바탕 화면"
if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\Desktop"    set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not defined DESKTOP if exist "%USERPROFILE%\Desktop"             set "DESKTOP=%USERPROFILE%\Desktop"

if not defined DESKTOP (
    echo 바탕화면 경로를 찾지 못했습니다. dist 폴더를 열어드립니다.
    explorer "dist"
    pause & exit /b 0
)

copy /y "dist\PC닥터.exe" "!DESKTOP!\PC닥터.exe"
if errorlevel 1 (
    echo 복사 실패. dist 폴더에서 직접 가져가세요.
    explorer "dist"
    pause & exit /b 0
)

echo.
echo =========================================
echo   완료! 바탕화면에 PC닥터.exe 생성됨
echo   !DESKTOP!\PC닥터.exe
echo =========================================
echo.
pause
