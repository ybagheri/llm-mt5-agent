"""Package smoke tests."""

from __future__ import annotations

import mt5_agent


def test_version_present() -> None:
    assert mt5_agent.__version__ == "0.12.0"
