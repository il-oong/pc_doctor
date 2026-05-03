@echo off
chcp 65001 >nul
setlocal

set "REPO=%USERPROFILE%\pc_doctor"
set "REPO_URL=https://github.com/il-oong/pc_doctor.git"

REM ── python 확인 ──────────────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo [PC Doctor] Python이 없습니다.
    echo https://www.python.org/downloads/
    echo 설치 시 "Add Python to PATH" 반드시 체크!
    pause
    exit /b 1
)

REM ── git 확인 ─────────────────────────────────────────────────────────
where git >nul 2>nul
if errorlevel 1 (
    echo [PC Doctor] Git이 없습니다.
    echo https://git-scm.com/download/win 에서 설치 후 재실행하세요.
    pause
    exit /b 1
)

REM ── 첫 실행: 클론 ────────────────────────────────────────────────────
if not exist "%REPO%\main.py" (
    echo [PC Doctor] 처음 실행 - 다운로드 중...
    git clone "%REPO_URL%" "%REPO%"
    if errorlevel 1 (
        echo 다운로드 실패.
        pause
        exit /b 1
    )
) else (
    echo [PC Doctor] 최신 버전 확인 중...
    git -C "%REPO%" pull --ff-only >nul 2>nul
)

REM ── psutil 설치 ───────────────────────────────────────────────────────
python -c "import psutil" >nul 2>nul
if errorlevel 1 (
    echo [PC Doctor] 필수 패키지 설치 중...
    python -m pip install psutil >nul
)

REM ── 바탕화면 바로가기 생성 (.lnk) ────────────────────────────────────
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$r='%REPO%';" ^
  "$pw=Join-Path(Split-Path(Get-Command python).Source)'pythonw.exe';" ^
  "if(-not(Test-Path $pw)){$pw=(Get-Command python).Source};" ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$lnk=$ws.CreateShortcut($d+'\PC Doctor.lnk');" ^
  "$lnk.TargetPath=$pw;" ^
  "$lnk.Arguments='\"'+$r+'\main.py\"';" ^
  "$lnk.WorkingDirectory=$r;" ^
  "$lnk.Description='PC Doctor';" ^
  "$lnk.Save()" >nul 2>nul

REM ── 앱 실행 ──────────────────────────────────────────────────────────
start "" pythonw "%REPO%\main.py"
