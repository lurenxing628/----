from __future__ import annotations

import sqlite3
from typing import Any, Dict, Union

RowLike = Union[sqlite3.Row, Dict[str, Any]]
