from __future__ import annotations

import sqlite3
from typing import Callable, Dict

from .v1 import run as run_v1
from .v2 import run as run_v2
from .v3 import run as run_v3

# 版本迁移注册表：target_version -> run(conn, logger=None)
MIGRATIONS: Dict[int, Callable[..., None]] = {
    1: run_v1,
    2: run_v2,
    3: run_v3,
}


def run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> None:
    fn = MIGRATIONS.get(int(target_version))
    if not fn:
        raise RuntimeError(f"未知的迁移版本：{target_version}")
    fn(conn, logger=logger)

