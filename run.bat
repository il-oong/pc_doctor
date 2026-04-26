@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM ── 자동 업데이트 (git이 있고 .git 폴더가 존재할 때만) ───────────────────
if exist ".git" (
    where git >nul 2>nul
    if not errorlevel 1 (
        echo [PC Doctor] 최신 버전 확인 중...
        git pull --ff-only 2>nul
    )
)

REM ── 의존성 자동 설치 (psutil 미설치 시) ─────────────────────────────────
python -c "import psutil" 2>nul
if errorlevel 1 (
    echo [PC Doctor] 의존성 설치 중...
    python -m pip install -r requirements.txt
)

REM ── 앱 실행 ──────────────────────────────────────────────────────────────
python main.py
if errorlevel 1 pause
