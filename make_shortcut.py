import ctypes, ctypes.wintypes, os, subprocess, sys, tempfile
from pathlib import Path


def get_desktop():
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
    return Path(buf.value)


def main():
    repo    = Path(__file__).parent
    main_py = repo / 'main.py'
    pythonw = Path(sys.executable).parent / 'pythonw.exe'
    if not pythonw.exists():
        pythonw = Path(sys.executable)

    lnk = get_desktop() / 'PC Doctor.lnk'

    # VBScript: Chr(34) = double-quote, no escaping headaches
    vbs = (
        'Set ws  = CreateObject("WScript.Shell")\n'
        f'Set lnk = ws.CreateShortcut("{lnk}")\n'
        f'lnk.TargetPath      = "{pythonw}"\n'
        f'lnk.Arguments       = Chr(34) & "{main_py}" & Chr(34)\n'
        f'lnk.WorkingDirectory = "{repo}"\n'
        'lnk.Description     = "PC Doctor"\n'
        'lnk.Save\n'
    )

    tmp = Path(tempfile.mktemp(suffix='.vbs'))
    tmp.write_text(vbs, encoding='ascii')
    try:
        subprocess.run(['wscript', str(tmp)], check=True)
        print(f'[OK] Desktop shortcut created: {lnk}')
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
