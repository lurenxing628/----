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

# 版本迁移注册表：target_version -> run(conn, logger=None) -> MigrationOutcome
MIGRATIONS: Dict[int, Callable[..., MigrationOutcome]] = {
    1: run_v1,
    2: run_v2,
    3: run_v3,
    4: run_v4,
    5: run_v5,
    6: run_v6,
}


def run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> MigrationOutcome:
    fn = MIGRATIONS.get(int(target_version))
    if not fn:
        raise RuntimeError(f"未知的迁移版本：{target_version}")
    return fn(conn, logger=logger)
