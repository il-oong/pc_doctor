@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "LOG=%~dp0build_log.txt"
echo. > "%LOG%"

echo ========================================= | tee "%LOG%"
echo   PC Doctor 빌드                         | tee -a "%LOG%"
echo ========================================= | tee -a "%LOG%"
echo. | tee -a "%LOG%"

REM ── Python 확인 ──────────────────────────────────────────────────────
echo [확인] Python 버전... | tee -a "%LOG%"
python --version >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다. >> "%LOG%"
    echo [오류] Python을 찾을 수 없습니다.
    echo https://www.python.org/downloads/ 에서 설치하세요.
    echo 로그: %LOG%
    pause & exit /b 1
)
python --version

REM ── pip 업그레이드 + 패키지 설치 ─────────────────────────────────────
echo. | tee -a "%LOG%"
echo [1/3] PyInstaller 설치 중... | tee -a "%LOG%"
python -m pip install --upgrade pip >> "%LOG%" 2>&1
python -m pip install pyinstaller psutil >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [오류] pip install 실패. 로그 확인: %LOG%
    pause & exit /b 1
)
echo 설치 완료. | tee -a "%LOG%"

REM ── 이전 빌드 정리 ───────────────────────────────────────────────────
if exist "dist\PC닥터.exe" del /f /q "dist\PC닥터.exe"
if exist "build" rd /s /q "build" 2>nul

REM ── 빌드 ─────────────────────────────────────────────────────────────
echo. | tee -a "%LOG%"
echo [2/3] 빌드 중 (1~3분)... | tee -a "%LOG%"

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "PC닥터" ^
    --hidden-import psutil ^
    --hidden-import psutil._pswindows ^
    --hidden-import winreg ^
    --hidden-import sqlite3 ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.messagebox ^
    --collect-submodules core ^
    --collect-submodules ui ^
    --collect-submodules utils ^
    --noconfirm ^
    main.py >> "%LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패!
    echo.
    echo 마지막 오류 내용:
    echo ─────────────────────────────────────
    powershell -NoProfile -Command "Get-Content '%LOG%' | Select-Object -Last 30"
    echo ─────────────────────────────────────
    echo 전체 로그: %LOG%
    pause & exit /b 1
)

if not exist "dist\PC닥터.exe" (
    echo [오류] 빌드는 됐지만 dist\PC닥터.exe 가 없습니다.
    echo 전체 로그: %LOG%
    pause & exit /b 1
)

REM ── 바탕화면 경로 자동 탐지 ──────────────────────────────────────────
echo. | tee -a "%LOG%"
echo [3/3] 바탕화면에 복사 중... | tee -a "%LOG%"
set "DESKTOP="

for /f "usebackq delims=" %%D in (
    `powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" 2^>nul`
) do set "DESKTOP=%%D"

if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\바탕 화면" set "DESKTOP=%USERPROFILE%\OneDrive\바탕 화면"
if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\Desktop"    set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not defined DESKTOP if exist "%USERPROFILE%\Desktop"             set "DESKTOP=%USERPROFILE%\Desktop"

if not defined DESKTOP (
    echo [안내] 바탕화면 경로를 자동으로 찾지 못했습니다.
    echo dist\PC닥터.exe 를 직접 바탕화면에 복사하세요.
    explorer "dist"
    pause & exit /b 0
)

copy /y "dist\PC닥터.exe" "!DESKTOP!\PC닥터.exe" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [안내] 복사 실패. dist\PC닥터.exe 를 직접 바탕화면에 복사하세요.
    explorer "dist"
    pause & exit /b 0
)

echo.
echo =========================================
echo   완료!
echo   바탕화면: !DESKTOP!\PC닥터.exe
echo =========================================
echo.
pause
