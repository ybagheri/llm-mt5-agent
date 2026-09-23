"""Integration placeholder. Real MT5 integration tests land in Phase 01+.

Marked `integration` so CI (`-m "not integration"`) skips them by default.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_placeholder() -> None:
    assert True
