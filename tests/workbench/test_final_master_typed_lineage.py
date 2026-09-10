"""The browser bridge must not invent SQLite storage types for lineage checks."""

import sqlite3
from contextlib import closing

import pytest

from tests.workbench.final_master_metadata_guard_support import typed_events


def fixture(tmp_path):
    (tmp_path / "db").mkdir()
    with closing(sqlite3.connect(str(tmp_path / "db/aps-live.db"))) as conn:
        conn.execute("CREATE TABLE WorkbenchTemplateLineageEvents (event_id INTEGER PRIMARY KEY, operation_ref TEXT, hours REAL)")
        conn.executemany("INSERT INTO WorkbenchTemplateLineageEvents VALUES (?, ?, ?)", [(1, "ref", 0.0), (2, "ref", 1.5)])
        conn.commit()
    return [{"__oracle_rowid__": 1, "event_id": 1, "operation_ref": "ref", "hours": 0}]


def test_real_type_is_read_from_same_immutable_event_not_inferred(tmp_path):
    rows = fixture(tmp_path)
    events = typed_events(rows, tmp_path)
    assert type(events["ref"][0]["hours"]) is float
    assert events["ref"][0]["hours"] == 0.0
    assert len(events["ref"]) == 1


@pytest.mark.parametrize("fault", ["value", "identity", "column", "duplicate", "omitted_history"])
def test_changed_saved_evidence_is_rejected(tmp_path, fault):
    rows = fixture(tmp_path)
    if fault == "value":
        rows[0]["hours"] = 0.1
    elif fault == "identity":
        rows[0]["operation_ref"] = "other"
    elif fault == "column":
        rows[0]["ignored"] = True
    elif fault == "duplicate":
        rows.append(dict(rows[0]))
    else:
        rows[0].update(__oracle_rowid__=2, event_id=2, hours=1.5)
    with pytest.raises(AssertionError):
        typed_events(rows, tmp_path)


def test_nonempty_evidence_cannot_skip_database(tmp_path):
    rows = fixture(tmp_path)
    with pytest.raises(AssertionError):
        typed_events(rows, None)
