import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselected by default; run with -m slow or RUN_SLOW=1)")


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_SLOW", "").strip().lower() in ("1", "true", "yes"):
        return
    markexpr = config.getoption("markexpr", default="")
    if "slow" in markexpr:
        return
    skip_slow = pytest.mark.skip(reason="slow test; run with -m slow or RUN_SLOW=1")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
