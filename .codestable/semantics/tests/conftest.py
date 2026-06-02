"""语义守卫测试的独立 conftest。

刻意放在 tests/ 之外：交付门禁跑 .venv(Python 3.8，无 hypothesis)且 testpaths=["tests"]，
若放进 tests/ 会让当前全绿的 3.8 门禁在 import hypothesis 时崩。
本目录用隔离的 .venv-semantic(Python 3.14)单独跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 仓库根 = 本文件上溯 3 层(.codestable/semantics/tests/ -> 仓库根)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hypothesis import HealthCheck, settings  # noqa: E402

settings.register_profile(
    "semantic_fast",
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "semantic_deep",
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("semantic_fast")
