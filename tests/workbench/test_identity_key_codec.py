"""SQLite/Python key parity, including embedded NUL and UTF-16 databases."""

from __future__ import annotations

import itertools
import sqlite3

import pytest

from core.infrastructure.migrations import v20
from core.infrastructure.workbench_metadata_schema import entity_key, entity_key_sql
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import business_snapshot, remove_metadata_for_v19
from tests.workbench.plan_identity_support import load_v24_schema

VALUES = ("", "a", ":", "%", "%3A", "a\0b:c%", "\u4e2d:\U0001f680", "\0", "a:b")


def expected_key(*values):
    return values[0] if len(values) == 1 else ":".join(value.translate({37: "%25", 58: "%3A"}) for value in values)


@pytest.fixture(params=("UTF-8", "UTF-16le", "UTF-16be"))
def encoded_conn(request):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA encoding = '" + request.param + "'")
    try:
        yield conn
    finally:
        conn.close()


@pytest.mark.parametrize("count", (1, 2, 3))
def test_sql_and_python_agree_without_delimiter_collisions(encoded_conn, count):
    conn = encoded_conn
    columns = tuple("c" + str(number) for number in range(count))
    conn.execute("CREATE TABLE Codec(" + ", ".join(name + " TEXT" for name in columns) + ")")
    expr = entity_key_sql(columns, "source")
    statement = "INSERT INTO Codec VALUES (" + ",".join("?" for _ in columns) + ")"
    values = list(itertools.product(VALUES, repeat=count))
    conn.executemany(statement, values)
    actual = [row[0] for row in conn.execute("SELECT " + expr + " FROM Codec AS source ORDER BY rowid")]
    expected = [expected_key(*value) for value in values]
    assert actual == expected == [entity_key(*value) for value in values]
    assert len(set(actual)) == len(values)


@pytest.mark.parametrize("backfill", (False, True))
def test_encoded_identity_survives_insert_update_delete_and_reopen(encoded_conn, schema_path, tmp_path, backfill):
    conn = encoded_conn
    if backfill:
        load_v24_schema(conn)
    else:
        with open(schema_path, encoding="utf-8") as source:
            conn.executescript(source.read())
    conn.execute("PRAGMA foreign_keys = ON")
    if backfill:
        remove_metadata_for_v19(conn)
    pairs = [(value, "d:\0%3A") for value in VALUES]
    for operator, day in pairs:
        conn.execute("INSERT INTO Operators(operator_id, name) VALUES (?, ?)", (operator, "name"))
        conn.execute("INSERT INTO OperatorCalendar(operator_id, date) VALUES (?, ?)", (operator, day))
    conn.commit()
    before = business_snapshot(conn)
    if backfill:
        v20.run(conn)
        assert business_snapshot(conn) == before
    repo = WorkbenchIdentityRepository(conn)
    keys = [expected_key(*pair) for pair in pairs]
    identities = repo.active_map("operator_calendar", keys)
    assert set(identities) == set(keys)
    assert len({identity.ref for identity in identities.values()}) == len(pairs)
    for key, (operator, day) in zip(keys, pairs):
        conn.execute("UPDATE OperatorCalendar SET date = ? WHERE operator_id = ? AND date = ?", ("next:%\0", operator, day))
        current = repo.find_active("operator_calendar", expected_key(operator, "next:%\0"))
        assert current.ref == identities[key].ref and current.revision == 2
        assert repo.find_active("operator_calendar", key) is None
    conn.commit()
    path = tmp_path / "encoded.db"
    with sqlite3.connect(str(path)) as target:
        conn.backup(target)
    with sqlite3.connect(str(path)) as reopened:
        reopened.row_factory = sqlite3.Row
        restored = WorkbenchIdentityRepository(reopened)
        for key, (operator, _) in zip(keys, pairs):
            identity = restored.get(identities[key].ref)
            assert identity.active and identity.revision == 2
            reopened.execute("DELETE FROM OperatorCalendar WHERE operator_id = ? AND date = ?", (operator, "next:%\0"))
            assert not restored.get(identity.ref).active
            reopened.execute("INSERT INTO OperatorCalendar(operator_id, date) VALUES (?, ?)", (operator, "next:%\0"))
            assert restored.find_active("operator_calendar", identity.entity_key).ref != identity.ref


@pytest.mark.parametrize("values", ((), (None,), (1,), ("a", None), (b"a", "b")))
def test_invalid_component_types_are_not_coerced(values):
    with pytest.raises(ValueError):
        entity_key(*values)
