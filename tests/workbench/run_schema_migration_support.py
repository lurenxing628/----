"""Frozen v25 schema with already-recorded production facts, not a fake version tag."""

import sqlite3
from pathlib import Path

from tests.workbench.frozen_business_seed_support import seed_frozen_business

FIXTURE_V25 = Path(__file__).parent / "fixtures" / "schema-v25.sql"


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(conn):
    result = {}
    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [row[1] for row in conn.execute("PRAGMA table_info(" + quoted + ")")]
        types = ",".join('typeof("' + column.replace('"', '""') + '")' for column in columns)
        result[name] = sorted((tuple(row) for row in conn.execute("SELECT *," + types + " FROM " + quoted)), key=repr)
    return result


def source_ddl(conn):
    return [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]


def seed_v25(path):
    return seed_frozen_business(path, 25)
