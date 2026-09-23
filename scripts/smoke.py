"""Smoke entry: validates config + logging without any trading."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
