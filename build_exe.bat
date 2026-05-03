@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================
echo   PC Doctor — 단독 실행 파일 빌드
echo =========================================
echo.

REM ── Python 확인 ──────────────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치 후 재시도하세요.
    pause & exit /b 1
)

REM ── PyInstaller + psutil 설치 ─────────────────────────────────────────
echo [1/3] 빌드 도구 설치 중...
python -m pip install --quiet pyinstaller psutil
if errorlevel 1 (
    echo [오류] pip 설치 실패.
    pause & exit /b 1
)

REM ── 이전 빌드 정리 ───────────────────────────────────────────────────
if exist "dist\PC닥터.exe" del /f /q "dist\PC닥터.exe"
if exist "build" rd /s /q "build" 2>nul

REM ── 빌드 ─────────────────────────────────────────────────────────────
echo [2/3] 빌드 중 (1~3분 소요)...
python -m PyInstaller pc_doctor.spec --clean --noconfirm
if errorlevel 1 (
    echo [오류] 빌드 실패. 위 오류 메시지를 확인하세요.
    pause & exit /b 1
)

if not exist "dist\PC닥터.exe" (
    echo [오류] dist\PC닥터.exe 를 찾을 수 없습니다.
    pause & exit /b 1
)

REM ── 바탕화면 경로 자동 탐지 (OneDrive 포함) ──────────────────────────
echo [3/3] 바탕화면에 복사 중...
set "DESKTOP="

REM PowerShell로 실제 바탕화면 경로를 가져옴 (가장 정확)
for /f "usebackq delims=" %%D in (
    `powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" 2^>nul`
) do set "DESKTOP=%%D"

REM PowerShell 실패 시 일반 경로 순서대로 시도
if not defined DESKTOP (
    if exist "%USERPROFILE%\OneDrive\바탕 화면"  set "DESKTOP=%USERPROFILE%\OneDrive\바탕 화면"
)
if not defined DESKTOP (
    if exist "%USERPROFILE%\OneDrive\Desktop"    set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
)
if not defined DESKTOP (
    if exist "%USERPROFILE%\Desktop"             set "DESKTOP=%USERPROFILE%\Desktop"
)
if not defined DESKTOP (
    if exist "%PUBLIC%\Desktop"                  set "DESKTOP=%PUBLIC%\Desktop"
)

if not defined DESKTOP (
    echo [오류] 바탕화면 경로를 찾을 수 없습니다.
    echo dist\PC닥터.exe 를 직접 원하는 위치에 복사하세요.
    explorer "dist"
    pause & exit /b 1
)

copy /y "dist\PC닥터.exe" "!DESKTOP!\PC닥터.exe" >nul
if errorlevel 1 (
    echo [오류] 복사 실패: !DESKTOP!\PC닥터.exe
    echo dist\PC닥터.exe 를 직접 바탕화면에 복사하세요.
    explorer "dist"
    pause & exit /b 1
)

echo.
echo =========================================
echo   완료! 바탕화면에 PC닥터.exe 생성됨
echo   경로: !DESKTOP!\PC닥터.exe
echo =========================================
echo.
echo 더블클릭하면 바로 실행됩니다. (Python 불필요)
echo.
pause
