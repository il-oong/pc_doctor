@echo off
chcp 65001 >nul
setlocal
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

REM ── 바탕화면으로 복사 ────────────────────────────────────────────────
echo [3/3] 바탕화면에 복사 중...
if exist "dist\PC닥터.exe" (
    copy /y "dist\PC닥터.exe" "%USERPROFILE%\Desktop\PC닥터.exe" >nul
    echo.
    echo =========================================
    echo   완료! 바탕화면에 PC닥터.exe 생성됨
    echo =========================================
) else (
    echo [오류] dist\PC닥터.exe 를 찾을 수 없습니다.
    pause & exit /b 1
)

echo.
echo 바탕화면의 PC닥터.exe 를 더블클릭하면 바로 실행됩니다.
echo (Python 설치 불필요)
echo.
pause
