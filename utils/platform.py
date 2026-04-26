"""OS detection helpers."""
from __future__ import annotations

import platform
import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def os_name() -> str:
    if IS_WINDOWS:
        return f"Windows {platform.release()}"
    if IS_MACOS:
        return f"macOS {platform.mac_ver()[0]}"
    if IS_LINUX:
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return f"Linux {platform.release()}"
    return platform.platform()


def hostname() -> str:
    return platform.node() or "unknown-host"


def architecture() -> str:
    return platform.machine() or platform.architecture()[0]
