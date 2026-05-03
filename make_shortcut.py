"""Create a desktop shortcut for PC Doctor."""
import sys
import subprocess
from pathlib import Path


def get_desktop() -> Path:
    import ctypes
    import ctypes.wintypes
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
    return Path(buf.value)


def main():
    repo = Path(__file__).parent
    main_py = repo / "main.py"

    # Prefer pythonw.exe (no console window)
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)

    desktop = get_desktop()
    lnk = desktop / "PC Doctor.lnk"

    ps_script = f"""
$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut('{lnk}')
$lnk.TargetPath      = '{pythonw}'
$lnk.Arguments       = '"'{main_py}'"'
$lnk.WorkingDirectory = '{repo}'
$lnk.Description     = 'PC Doctor'
$lnk.Save()
Write-Host 'OK: ' + $lnk.FullName
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[OK] 바탕화면 바로가기 생성: {lnk}")
    else:
        print("[ERROR] 바로가기 생성 실패:")
        print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
