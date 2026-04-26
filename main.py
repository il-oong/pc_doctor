"""PC Doctor entry point."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
sys.path.insert(0, str(Path(__file__).parent))

from ui.app import run

if __name__ == "__main__":
    run()
