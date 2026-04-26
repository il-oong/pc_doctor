"""Cross-platform notification adapter with graceful fallback."""
from __future__ import annotations

import shutil
import subprocess

from .platform import IS_LINUX, IS_MACOS, IS_WINDOWS


def notify(title: str, message: str) -> bool:
    """Show a desktop notification. Returns True if dispatched."""
    try:
        if IS_LINUX and shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                timeout=3,
            )
            return True
        if IS_MACOS and shutil.which("osascript"):
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(
                ["osascript", "-e", script],
                check=False,
                timeout=3,
            )
            return True
        if IS_WINDOWS:
            try:
                from winotify import Notification  # type: ignore

                Notification(app_id="PC Doctor", title=title, msg=message).show()
                return True
            except ImportError:
                return False
    except (OSError, subprocess.SubprocessError):
        return False
    return False
