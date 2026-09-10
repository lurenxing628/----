"""Full-directory scope/facts invalidation and actual WAL concurrent-reader evidence."""

import threading
from types import SimpleNamespace

import pytest

from tests.workbench.test_run_history_support import BASE, api, connect, edit_receipt, read, seed
from tests.workbench.test_run_history_support import history_case as _history_case


@pytest.mark.parametrize("change", ["new_off_page_run", "off_page_state", "off_page_manifest", "filter", "date", "sort", "order", "size"])
def test_snapshot_binds_entire_directory_and_query_not_current_page(history_case, change):
    case = history_case
    old = seed(case, "complete", accepted="2026-09-08T00:00:00")
    seed(case, "queued", accepted="2026-09-10T00:00:00")
    pending = seed(case, "running", accepted="2026-09-07T00:00:00") if change == "off_page_state" else None
    client, _ = api(case)
    first = read(client, size=1)
    query = {"size": 1, "snapshot_ref": first["meta"]["snapshot_ref"]}
    if change == "new_off_page_run":
        seed(case, accepted="2026-09-01T00:00:00")
    elif change == "off_page_state":
        case.conn.execute("UPDATE WorkbenchRunJobs SET stage='awaiting_reconciliation' WHERE run_ref=?", (pending,))
        case.conn.commit()
    elif change == "off_page_manifest":
        edit_receipt(case, old, lambda receipt: receipt["candidates"][0].update(label="Reconciled label"))
    else:
        query.update({"filter": {"state": "queued"}, "date": {"accepted_from": "2026-09-10", "accepted_to": "2026-09-10"},
                      "sort": {"sort": "started_at"}, "order": {"order": "asc"}, "size": {"size": 2}}[change])
    response = client.get(BASE, query_string=query)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_clock_changes_do_not_create_a_directory_fingerprint(history_case, monkeypatch):
    from web import public_token_registry

    case = history_case
    seed(case)
    client, _ = api(case)
    first = read(client)
    now = public_token_registry.time.time()
    monkeypatch.setattr(public_token_registry.time, "time", lambda: now + 10)
    same = read(client, snapshot_ref=first["meta"]["snapshot_ref"])
    assert same["data"] == first["data"] and same["meta"]["as_of"] == first["meta"]["as_of"]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: now + 1000)
    assert client.get(BASE, query_string={"snapshot_ref": first["meta"]["snapshot_ref"]}).status_code == 409


def test_wal_writer_commit_between_directory_reads_never_mixes_snapshots(history_case, monkeypatch):
    from core.services.workbench.run_history_storage import RunHistoryStore

    case = history_case
    first_ref = seed(case, "complete")
    client, _ = api(case)
    settings, errors, created = case.settings(), [], []
    original = RunHistoryStore._capacity

    def write():
        conn = connect(case.path)
        try:
            writer = SimpleNamespace(conn=conn, settings=lambda: settings)
            created.append(seed(writer, "complete"))
        except Exception as exc:
            errors.append(exc)
        finally:
            conn.close()

    def interleave(store):
        original(store)
        worker = threading.Thread(target=write)
        worker.start()
        worker.join(10)
        assert not worker.is_alive() and not errors and created

    monkeypatch.setattr(RunHistoryStore, "_capacity", interleave)
    first = read(client)
    assert [row["run_ref"] for row in first["data"]["runs"]] == [first_ref]
    monkeypatch.setattr(RunHistoryStore, "_capacity", original)
    assert client.get(BASE, query_string={"snapshot_ref": first["meta"]["snapshot_ref"]}).status_code == 409
    assert {row["run_ref"] for row in read(client)["data"]["runs"]} == {first_ref, created[0]}
