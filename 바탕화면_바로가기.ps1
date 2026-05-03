# PC Doctor 바탕화면 바로가기 생성기
$src = Split-Path -Parent $MyInvocation.MyCommand.Path

# pythonw (콘솔창 없음) 우선, 없으면 python
$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $pythonw = (Get-Command python).Source
}

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop "PC Doctor.lnk"

$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath     = $pythonw
$lnk.Arguments      = "`"$src\main.py`""
$lnk.WorkingDirectory = $src
$lnk.Description    = "PC Doctor - PC 건강 진단"
$lnk.WindowStyle    = 1
$lnk.Save()

Write-Host ""
Write-Host "바탕화면에 'PC Doctor' 바로가기가 생성됐습니다."
Write-Host "위치: $lnkPath"
Write-Host ""
Read-Host "Enter 키를 누르면 닫힙니다"
