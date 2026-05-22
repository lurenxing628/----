from __future__ import annotations

import sqlite3
from typing import Callable, Dict

from .common import MigrationOutcome
from .v1 import run as run_v1
from .v2 import run as run_v2
from .v3 import run as run_v3
from .v4 import run as run_v4
from .v5 import run as run_v5
from .v6 import run as run_v6
from .v7 import run as run_v7
from .v8 import run as run_v8
from .v9 import run as run_v9
from .v10 import run as run_v10
from .v11 import run as run_v11
from .v12 import run as run_v12

# 版本迁移注册表：target_version -> run(conn, logger=None) -> MigrationOutcome
MIGRATIONS: Dict[int, Callable[..., MigrationOutcome]] = {
    1: run_v1,
    2: run_v2,
    3: run_v3,
    4: run_v4,
    5: run_v5,
    6: run_v6,
    7: run_v7,
    8: run_v8,
    9: run_v9,
    10: run_v10,
    11: run_v11,
    12: run_v12,
}


def run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> MigrationOutcome:
    fn = MIGRATIONS.get(int(target_version))
    if not fn:
        raise RuntimeError(f"未知的迁移版本：{target_version}")
    return fn(conn, logger=logger)
