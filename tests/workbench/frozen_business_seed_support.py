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


def append_v31_handling_fact(conn):
    """Replay one genuine historical handling after v31.install on seed_v30.

    The new extension must contain mappings only. Freeze those disposable random
    mappings to the archive's original mappings so the original receipt hashes,
    source snapshots and item references remain byte-for-byte genuine. No old
    v30 row is replaced; no existing handling is allowed to be present.
    """
    assert not conn.in_transaction
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 30
    for table in ("WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"):
        assert conn.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0] == 0
    refs = [row[0] for row in conn.execute(
        "SELECT outsourcing_ref FROM WorkbenchDashboardExternalItems ORDER BY outsourcing_ref")]
    assert refs == ["311cdad559428b94cf2bc0ad69b55ad850c0a9f775c7646d",
                    "7c4cc4e28b0846f43fa66c2e0eae804482022d4ff0f79ff5",
                    "e1f1e7383c8afe2f05499f99e999f196f6073ec5d91311d9"]
    data = _archive("business-seed", "30-external-handling")
    before = _ddl(conn)
    guard = conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_dashboard_external_items_no_delete'").fetchone()[0]
    try:
        conn.executescript("BEGIN;\nDROP TRIGGER wb_dashboard_external_items_no_delete;\n" + data + "\n" + guard + ";")
        assert _ddl(conn) == before
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
