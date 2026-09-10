from __future__ import annotations

import sqlite3
from typing import Callable, Dict

from ..migration_common import MigrationOutcome
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
from .v13 import run as run_v13
from .v14 import run as run_v14
from .v15 import run as run_v15
from .v16 import run as run_v16
from .v17 import run as run_v17
from .v18 import run as run_v18
from .v19 import run as run_v19
from .v20 import run as run_v20
from .v21 import run as run_v21
from .v22 import run as run_v22
from .v23 import run as run_v23
from .v24 import run as run_v24
from .v25 import run as run_v25
from .v26 import run as run_v26
from .v27 import run as run_v27
from .v28 import run as run_v28
from .v29 import run as run_v29
from .v30 import run as run_v30
from .v31 import run as run_v31

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
    13: run_v13,
    14: run_v14,
    15: run_v15,
    16: run_v16,
    17: run_v17,
    18: run_v18,
    19: run_v19,
    20: run_v20,
    21: run_v21,
    22: run_v22,
    23: run_v23,
    24: run_v24,
    25: run_v25,
    26: run_v26,
    27: run_v27,
    28: run_v28,
    29: run_v29,
    30: run_v30,
    31: run_v31,
}


def run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> MigrationOutcome:
    fn = MIGRATIONS.get(int(target_version))
    if not fn:
        raise RuntimeError(f"未知的迁移版本：{target_version}")
    return fn(conn, logger=logger)
