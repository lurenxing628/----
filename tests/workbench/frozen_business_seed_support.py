"""Replay fixed historical business facts without invoking current application services.

The data was recorded by the original seed_v25/v26/v27/v28/v29/v30 helpers from
commit 7034b87303ec10e5d2f40ea704aee0b98770cf9c in an isolated checkout. Its
existing frozen schema assertions and foreign-key checks passed before capture.
Do not regenerate these archives with current service/schema implementations.
"""

import sqlite3
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
ARCHIVE_VERSIONS = (25, 26, 27, 28, 29, 30)


def _archive(prefix, version):
    content = (FIXTURES / (prefix + "-v" + str(version) + ".sql")).read_bytes()
    return content.decode("utf-8")


def _ddl(conn):
    return list(map(tuple, conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")))


def seed_frozen_business(path, version):
    """Create only a new disposable old database, preserving exact archived DDL.

    Triggers would invent additional identity rows while replaying already-recorded
    facts. Remove them only inside this fixture-loading transaction and restore
    their exact archived definitions before validating and committing the fixture.
    No current-schema extensions are ever installed into the historical database.
    """
    if version not in ARCHIVE_VERSIONS:
        raise KeyError(version)
    schema = _archive("schema", version)
    data = _archive("business-seed", version)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        assert not _ddl(conn), "Historical fixtures require a new empty database"
        conn.executescript(schema)
        expected_ddl = _ddl(conn)
        triggers = [(row[1], row[3]) for row in expected_ddl if row[0] == "trigger"]
        conn.execute("PRAGMA foreign_keys=OFF")
        statements = ["BEGIN;"]
        statements.extend('DROP TRIGGER "' + name.replace('"', '""') + '";' for name, _ in triggers)
        statements.append(data)
        statements.extend(sql + ";" for _, sql in triggers)
        conn.executescript("\n".join(statements))
        assert _ddl(conn) == expected_ddl
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == version
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception:
        conn.rollback()
        conn.close()
        raise
