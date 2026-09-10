"""Frozen unguarded v29 connections and lossless collision evidence."""

import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from core.infrastructure.database import get_connection
from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.workbench_plan_identity_write_guard import contract_issues, install, objects
from tests.workbench.plan_identity_insert_collision_support import RefProbe, operation, seed_parents, source_refs
from tests.workbench.plan_identity_support import table_snapshot

ROOT = Path(__file__).resolve().parents[2]
FROZEN_SHA256 = {
    24: "023f7ae15282b1cc0523f218c2b45e1ba6cb4f036d491fe7761cbd8f1f56f03c",
    25: "18db92ca20538f45ff3c48045196ff7ff6fb37105dd9f7a4182c931008f9bc4e",
    26: "3b1565dffc6f35c6e929d0d96a9df27377865b885132ad57ffeb05e435bc2a6c",
    27: "dca9a9cd506c22096e4b4dd87e8524d31cf97c7f9dd2567564fecc5181a8e198",
    28: "2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52",
    29: "d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648",
}


def frozen_v29_connection(path):
    source = ROOT / "tests/workbench/fixtures/schema-v29.sql"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == FROZEN_SHA256[29]
    conn = get_connection(str(path))
    try:
        assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
        conn.executescript(source.read_text(encoding="utf-8"))
        set_schema_version(conn, 29)
        conn.commit()
        assert get_schema_version(conn) == 29
        assert set(contract_issues(conn)) == {"missing_workbench_plan_write_guard: " + name for name in objects()}
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        return conn
    except BaseException:
        conn.close()
        raise


def schema_snapshot(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name,type")]


def exact_snapshot(conn):
    """Keep every SQL storage class, even INTEGER 1 versus REAL 1.0."""
    tables = table_snapshot(conn)
    types = {}
    for name in tables:
        columns = [row[1] for row in conn.execute('PRAGMA table_info("' + name + '")')]
        expressions = ','.join('typeof("' + column + '")' for column in columns)
        types[name] = sorted((tuple(row) for row in conn.execute(
            'SELECT *, ' + expressions + ' FROM "' + name + '"')), key=repr)
    return {"tables": tables, "storage_types": types}


def file_hashes():
    paths = ["schema.sql", "core/infrastructure/workbench_plan_identity_schema.py",
             "data/repositories/workbench_plan_identity_repo.py",
             "tests/workbench/plan_identity_insert_collision_support.py"]
    paths += ["core/infrastructure/migrations/v" + str(version) + ".py" for version in range(24, 30)]
    paths += ["tests/workbench/fixtures/schema-v" + str(version) + ".sql" for version in FROZEN_SHA256]
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def assert_frozen_hashes():
    hashes = file_hashes()
    for version, expected in FROZEN_SHA256.items():
        assert hashes["tests/workbench/fixtures/schema-v" + str(version) + ".sql"] == expected
    return hashes


def capture_collision(directory, *, guarded, retired, recursive):
    """Disposable file DB; native seed, one forced draw, complete before/after facts."""
    path = directory / "attempt.sqlite"
    with closing(frozen_v29_connection(path)) as conn:
        conn.execute("PRAGMA recursive_triggers=" + str(recursive))
        if guarded:
            install(conn)
        seed_parents(conn)
        operation(conn, 13)
        duplicate = source_refs(conn)[0][1]
        if retired:
            conn.execute("DELETE FROM BatchOperations WHERE seq=13")
        operation(conn, 15)
        conn.commit()
        committed = exact_snapshot(conn)
        operation(conn, 14)
        before = exact_snapshot(conn)
        probe = RefProbe(conn, outputs=[bytes.fromhex(duplicate)])
        error = None
        try:
            operation(conn, 15, verb="INSERT OR REPLACE")
        except sqlite3.IntegrityError as exc:
            error = str(exc)
        after = exact_snapshot(conn)
        result = {"guarded": guarded, "retired": retired, "recursive_triggers": recursive,
                  "schema_version": get_schema_version(conn), "schema": schema_snapshot(conn),
                  "committed": committed, "before": before, "after": after,
                  "error": error, "draws": probe.draws, "attempts": probe.attempts,
                  "statement_unchanged": before == after, "transaction_open": conn.in_transaction}
        conn.rollback()
        result["rollback_unchanged"] = exact_snapshot(conn) == committed
        result["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        result["foreign_key_check"] = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
    return result


def write_evidence(directory):
    """Generate new rawfacts only; never open the prior BP failure bundle."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    hashes = assert_frozen_hashes()
    cases = []
    for guarded in (False, True):
        for retired in (False, True):
            for recursive in (0, 1):
                name = f"guarded-{int(guarded)}-retired-{int(retired)}-recursive-{recursive}"
                target = directory / name
                target.mkdir()
                result = capture_collision(target, guarded=guarded, retired=retired, recursive=recursive)
                assert result["rollback_unchanged"] and result["integrity_check"] == "ok"
                assert not result["foreign_key_check"] and len(result["draws"]) == 1
                if guarded:
                    assert result["error"] == "UNIQUE constraint failed: WorkbenchPlanSourceRefs.ref"
                    assert result["statement_unchanged"] and result["transaction_open"]
                elif recursive == 0:
                    assert result["error"] is None and not result["statement_unchanged"]
                (target / "rawfacts.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                cases.append({key: value for key, value in result.items()
                              if key not in ("schema", "committed", "before", "after")})
    manifest = {"python": sys.version, "sqlite": sqlite3.sqlite_version,
                "historical_random_failure_reproduced": False,
                "scope": "forced collision only; frozen v29 plus explicit guard helper; not current schema",
                "hashes_before": hashes, "hashes_after": assert_frozen_hashes(), "cases": cases,
                "rawfact_sha256": {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in sorted(directory.glob("*/*")) if path.is_file()}}
    assert manifest["hashes_after"] == hashes
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    write_evidence(sys.argv[1])
