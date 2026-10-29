"""Actual SQL rollback and COMMIT ACK injection; concurrent intent uses one receipt."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.facts.run_data_context import restored_context_ref
from tests.workbench.run_candidate_adoption_support import BASE, INTENT, KEY, api, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import connect


@pytest.mark.parametrize("table", ["WorkbenchCommandReceipts"])
def test_failure_after_real_writes_rolls_back_every_table(candidate_case, table):
    case = candidate_case
    case.operation(seq=2)
    case.conn.commit()
    # Install fault before admission so it is part of the exact facts schema.
    condition = "NEW.version>0 AND (SELECT COUNT(*) FROM Schedule)>0" if table == "Schedule" else (
        "NEW.action='scheduling.candidate.adopt'" if table == "WorkbenchCommandReceipts" else "1")
    case.conn.execute('CREATE TRIGGER bx_inject BEFORE INSERT ON "' + table + '" WHEN ' + condition
                      + " BEGIN SELECT RAISE(ABORT,'injected storage failure'); END")
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert snapshot(case.conn) == before
    assert not case.conn.in_transaction
    assert service(case.conn).lookup(ref, KEY) is None


def test_two_connections_concurrently_replay_one_adoption(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    barrier = Barrier(2)

    def adopt():
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return service(conn).adopt(ref, token, KEY, INTENT)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(adopt) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(row["replayed"] for row in results) == [False, True]
    assert len({row["receipt_ref"] for row in results}) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='adopt_run_candidate'").fetchone()[0] == 1


def test_adoption_reuses_one_capture_through_input_and_constraints(candidate_case, monkeypatch):
    from collections import Counter

    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

    case = candidate_case
    ref = candidate(case)
    counts = Counter()
    initialize, read = ProductionFactsCapture.__init__, WorkbenchPreflightFactsRepository.capture_table

    def capture_once(capture, conn):
        counts["capture"] += 1
        initialize(capture, conn)

    def table_once(repo, name):
        counts[name] += 1
        return read(repo, name)

    monkeypatch.setattr(ProductionFactsCapture, "__init__", capture_once)
    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", table_once)
    evidence = validate_adoption(case.conn, ref)
    assert evidence.payload.scheduled_op_ids == {case.op_id}
    assert counts and set(counts.values()) == {1}


def test_adoption_command_resolution_keeps_live_pending_and_identifies_replaced_context(candidate_case, monkeypatch):
    case = candidate_case
    ref = candidate(case)
    adopter = service(case.conn)
    checked = adopter.preview(ref)
    current = checked["data_context_ref"]
    reads = []

    def context_ref():
        reads.append(case.conn.in_transaction)
        return current

    monkeypatch.setattr(adopter.data_context, "ref", context_ref)
    state, pending = adopter.resolve_command(ref, KEY, run_ref=checked["run_ref"], data_context_ref=current)
    assert state == "not_recorded"
    assert pending["may_be_in_flight"] is True and pending["resolution"] == "unresolved"
    assert pending["request_key"] == KEY and pending["data_context_ref"] == current
    assert reads == [True]
    other = restored_context_ref("another-database", [])
    for candidate_ref, options in (
        ("f" * 48, {"data_context_ref": current}),
        (ref, {"run_ref": "e" * 48, "data_context_ref": current}),
        (ref, {"data_context_ref": other}),
    ):
        state, replaced = adopter.resolve_command(candidate_ref, KEY, **options)
        assert state == "not_recorded" and replaced["result"] == "not_recorded"
        assert replaced["may_be_in_flight"] is False and replaced["resolution"] == "context_replaced"
        assert replaced["data_context_ref"] == current
    assert not case.conn.in_transaction
    # A bare 64-hex digest is not a data generation that production ever issued.
    for options in ({"run_ref": "invalid", "data_context_ref": current}, {"data_context_ref": "f" * 48},
                    {"data_context_ref": "a" * 64}):
        with pytest.raises(WorkbenchCommandRejected) as exc:
            adopter.resolve_command(ref, KEY, **options)
        assert exc.value.code == "invalid_input" and exc.value.status == 400
    assert reads == [True] * 4


def test_candidate_preview_does_not_read_data_context_for_missing_candidate(candidate_case, monkeypatch):
    adopter = service(candidate_case.conn)

    def unexpected_context():
        raise AssertionError("missing candidates must not read the maintenance journal")

    monkeypatch.setattr(adopter.data_context, "ref", unexpected_context)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        adopter.preview("f" * 48)
    assert exc.value.code == "entity_not_found" and exc.value.status == 404


@pytest.mark.parametrize("enabled", [True, False])
def test_candidate_preview_maps_data_context_failure_to_storage_failure(candidate_case, monkeypatch, enabled):
    from core.services.workbench.facts.run_data_context import RunDataContext

    case = candidate_case
    ref = candidate(case)

    def unavailable_context(self, *args, **kwargs):
        raise RuntimeError("maintenance journal unavailable")

    monkeypatch.setattr(RunDataContext, "ref", unavailable_context)
    response = api(case, enabled=enabled).post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 500, response.get_data(as_text=True)
    assert response.get_json()["error"]["code"] == "storage_failure"


def test_recorded_adoption_replays_before_reading_the_data_context(candidate_case, monkeypatch):
    case = candidate_case
    ref = candidate(case)
    adopter = service(case.conn)
    checked = adopter.preview(ref)

    def unavailable_context():
        raise RuntimeError("maintenance journal unavailable")

    monkeypatch.setattr(adopter.data_context, "ref", unavailable_context)
    adopted = adopter.adopt(ref, checked["write_context"]["write_token"], KEY, INTENT)
    other = restored_context_ref("another-database", [])
    state, replayed = adopter.resolve_command(ref, KEY, run_ref="e" * 48, data_context_ref=other)
    assert state == "recorded" and replayed["replayed"] is True
    assert replayed["receipt_ref"] == adopted["receipt_ref"]
    assert adopter.adopt(ref, "", KEY, INTENT)["receipt_ref"] == adopted["receipt_ref"]
    with pytest.raises(WorkbenchCommandRejected) as exc:
        adopter.resolve_command("f" * 48, KEY, data_context_ref=other)
    assert exc.value.code == "request_key_conflict"
    with pytest.raises(RuntimeError, match="maintenance journal unavailable"):
        adopter.resolve_command(ref, "candidate-adoption-not-recorded", data_context_ref=other)


def test_candidate_adoption_resolution_route_is_read_only_and_not_cached(candidate_case):
    case = candidate_case
    ref = candidate(case)
    checked = service(case.conn).preview(ref)
    before = snapshot(case.conn)

    def read_only_connection(path):
        conn = connect(path)
        conn.execute("PRAGMA query_only=ON")
        return conn

    client = api(case, connection_factory=read_only_connection)
    response = client.get(BASE + ref + "/adoption-commands/" + KEY,
                          query_string={"run_ref": checked["run_ref"], "data_context_ref": checked["data_context_ref"]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json()["resolution"] == "unresolved"
    replaced = client.get(BASE + "f" * 48 + "/adoption-commands/" + KEY,
                          query_string={"data_context_ref": checked["data_context_ref"]})
    assert replaced.status_code == 200 and replaced.get_json()["resolution"] == "context_replaced"
    for query in ({}, {"run_ref": checked["run_ref"]}, {"data_context_ref": "a" * 64}):
        rejected = client.get(BASE + ref + "/adoption-commands/" + KEY, query_string=query)
        assert rejected.status_code == 400 and rejected.get_json()["error"]["code"] == "invalid_input"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("failure", [KeyError("missing internal field"), TypeError("invalid internal call")])
def test_internal_adoption_proof_errors_remain_system_failures(candidate_case, monkeypatch, failure):
    from core.services.workbench.run import candidate_adoption_validation

    case = candidate_case
    ref = candidate(case)

    def broken_proof(*args, **kwargs):
        raise failure

    monkeypatch.setattr(candidate_adoption_validation, "validate_adoption_constraints", broken_proof)
    with pytest.raises(type(failure)) as raw:
        candidate_adoption_validation.validate_adoption(case.conn, ref)
    assert raw.value is failure
    with pytest.raises(type(failure)) as preview_failure:
        service(case.conn).preview(ref)
    assert preview_failure.value is failure
    response = api(case).post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "storage_failure"
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0
