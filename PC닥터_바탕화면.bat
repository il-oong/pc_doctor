@echo off
chcp 65001 >nul
setlocal

REM ──────────────────────────────────────────────────────────────────────
REM  PC Doctor 바탕화면 런처
REM  - 첫 실행: GitHub에서 자동 클론 + 의존성 설치
REM  - 이후 실행: 자동 git pull + 앱 실행
REM
REM  사용법: 이 파일을 그대로 바탕화면에 복사 후 더블클릭
REM ──────────────────────────────────────────────────────────────────────

set "REPO=%USERPROFILE%\pc_doctor"
set "REPO_URL=https://github.com/il-oong/pc_doctor.git"

REM ── git 확인 ─────────────────────────────────────────────────────────
where git >nul 2>nul
if errorlevel 1 (
    echo [PC Doctor] Git이 설치되어 있지 않습니다.
    echo https://git-scm.com/download/win 에서 설치 후 다시 실행하세요.
    pause
    exit /b 1
)

REM ── python 확인 ──────────────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo [PC Doctor] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치 시 "Add Python to PATH" 체크 필수.
    pause
    exit /b 1
)

REM ── 첫 실행: 클론 ────────────────────────────────────────────────────
if not exist "%REPO%\main.py" (
    echo [PC Doctor] 첫 실행: GitHub에서 다운로드합니다...
    git clone "%REPO_URL%" "%REPO%"
    if errorlevel 1 (
        echo [PC Doctor] 다운로드 실패.
        pause
        exit /b 1
    )
)

REM ── run.bat 위임 (자동 pull + 의존성 + 실행) ────────────────────────
call "%REPO%\run.bat"
