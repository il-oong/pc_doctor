"""PC Doctor standalone EXE builder. Run: python build.py"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent

def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

def main():
    print("=" * 40)
    print(" PC Doctor EXE Builder")
    print("=" * 40)

    # Install deps
    print("\n[1/3] Installing PyInstaller + psutil...")
    pip_install("pyinstaller")
    pip_install("psutil")

    # Clean previous build
    for d in ["build", "dist"]:
        if (ROOT / d).exists():
            shutil.rmtree(ROOT / d)

    # Build
    print("\n[2/3] Building (1~3 min)...")
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "PC",
        "--hidden-import", "psutil",
        "--hidden-import", "psutil._pswindows",
        "--hidden-import", "winreg",
        "--hidden-import", "sqlite3",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.messagebox",
        "--collect-submodules", "core",
        "--collect-submodules", "ui",
        "--collect-submodules", "utils",
        "--noconfirm",
        "main.py",
    ]
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        print("\n[ERROR] Build failed. Check messages above.")
        input("Press Enter to close...")
        sys.exit(1)

    exe = ROOT / "dist" / "PC.exe"
    if not exe.exists():
        print("\n[ERROR] dist/PC.exe not found.")
        input("Press Enter to close...")
        sys.exit(1)

    # Find Desktop
    import ctypes.wintypes
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
    desktop = Path(buf.value) if buf.value else Path.home() / "Desktop"

    dst = desktop / "PC Doctor.exe"
    shutil.copy2(exe, dst)

    print("\n" + "=" * 40)
    print(f" Done! Saved to:\n {dst}")
    print("=" * 40)
    input("\nPress Enter to close...")

if __name__ == "__main__":
    main()
