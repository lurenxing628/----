from __future__ import annotations

import sys
from pathlib import Path

# 让 tests 可以直接 import core/data/web（不要求 pip install -e .）
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

