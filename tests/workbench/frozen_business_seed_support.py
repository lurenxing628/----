"""Replay fixed historical business facts without invoking current application services.

The data was recorded by the original seed_v25/v26/v27/v28/v29/v30 helpers from
commit 7034b87303ec10e5d2f40ea704aee0b98770cf9c in an isolated checkout. Its
existing frozen schema assertions and foreign-key checks passed before capture.
Do not regenerate these archives with current service/schema implementations.
"""

import hashlib
import sqlite3
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
ARCHIVES = {
    25: ("18db92ca20538f45ff3c48045196ff7ff6fb37105dd9f7a4182c931008f9bc4e",
         "ddb39b6d15cdf2d948d23cd71ea35b982b8b8cab87190cc400d1936324979a8f"),
    26: ("3b1565dffc6f35c6e929d0d96a9df27377865b885132ad57ffeb05e435bc2a6c",
         "d97a09aaa09bc2439dd2e3dbc35d89782d85633dac304f0a283a53566ec16334"),
    27: ("dca9a9cd506c22096e4b4dd87e8524d31cf97c7f9dd2567564fecc5181a8e198",
         "e005b872e1c9f72ed882703effc10d88ccf0c1bf96e61122313f26448325483a"),
    28: ("2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52",
         "d593d5eace49b4744bea43f420049042a6734b21584d7311ebc7490430981ac7"),
    29: ("d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648",
         "2f31ef073cb19edbb3c2f42bd7d26c3709e2de55039ced3dcd7aa46c91fc9896"),
    30: ("16460ac6d0f95373eca466b101cfcc46097187760e2438fb3a8c292c28761b2e",
         "a27a19446f6d7ab56c470d6f8d9ad726b26b65beff2a783dc61ad8524f8889b8"),
}


def _archive(prefix, version, expected):
    content = (FIXTURES / (prefix + "-v" + str(version) + ".sql")).read_bytes()
    assert hashlib.sha256(content).hexdigest() == expected
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
    schema_hash, data_hash = ARCHIVES[version]
    schema = _archive("schema", version, schema_hash)
    data = _archive("business-seed", version, data_hash)
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
    data = _archive("business-seed", "30-external-handling",
                    "4d2100921093b27ce67e0918df12bb8eaf4a9842b21f4a8e151a2fd935397168")
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
