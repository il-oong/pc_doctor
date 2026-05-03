@echo off
chcp 65001 >nul
setlocal

set "REPO=%USERPROFILE%\pc_doctor"
set "REPO_URL=https://github.com/il-oong/pc_doctor.git"

REM ── python ──────────────────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo Python이 없습니다.
    echo https://www.python.org/downloads/
    echo 설치 시 "Add Python to PATH" 반드시 체크!
    pause & exit /b 1
)

REM ── git ─────────────────────────────────────────────────────────────
where git >nul 2>nul
if errorlevel 1 (
    echo Git이 없습니다. https://git-scm.com/download/win
    pause & exit /b 1
)

REM ── 다운로드 ─────────────────────────────────────────────────────────
if not exist "%REPO%\main.py" (
    echo 다운로드 중...
    git clone "%REPO_URL%" "%REPO%"
    if errorlevel 1 ( echo 실패. & pause & exit /b 1 )
) else (
    git -C "%REPO%" pull --ff-only >nul 2>nul
)

REM ── psutil 설치 ───────────────────────────────────────────────────────
python -c "import psutil" >nul 2>nul
if errorlevel 1 python -m pip install psutil >nul

REM ── 바탕화면 바로가기 생성 ────────────────────────────────────────────
powershell -NoProfile -ExecutionPolicy Bypass -Command "$r='%REPO%'; $pw=Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'; if(-not(Test-Path $pw)){$pw=(Get-Command python).Source}; $d=[Environment]::GetFolderPath('Desktop'); $ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut($d+'\PC Doctor.lnk'); $lnk.TargetPath=$pw; $lnk.Arguments='\"'+$r+'\main.py\"'; $lnk.WorkingDirectory=$r; $lnk.Description='PC Doctor'; $lnk.Save(); Write-Host '바탕화면 바로가기 생성 완료'"

REM ── 실행 ─────────────────────────────────────────────────────────────
echo.
echo 완료! 바탕화면의 'PC Doctor' 아이콘을 더블클릭하세요.
start "" pythonw "%REPO%\main.py"
