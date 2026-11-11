"""Actual SQL rollback, concurrent receipt replay and adoption command resolution."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.facts.run_data_context import restored_context_ref
from tests.workbench.run_candidate_adoption_support import BASE, INTENT, KEY, api, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import connect


def test_receipt_insert_failure_rolls_back_candidate_adoption(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    case.conn.commit()
    # Install fault before admission so it is part of the exact facts schema.
    case.conn.execute(
        'CREATE TRIGGER bx_inject BEFORE INSERT ON "WorkbenchCommandReceipts"'
        " WHEN NEW.action='scheduling.candidate.adopt'"
        " BEGIN SELECT RAISE(ABORT,'injected storage failure'); END"
    )
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert snapshot(case.conn) == before
    assert not case.conn.in_transaction
    svc = service(case.conn)
    assert svc.commands.lookup(KEY, action=svc._action, context_ref=ref) is None


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
    assert evidence.outcome.validated_payload.scheduled_op_ids == {case.op_id}
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
    pending = adopter.resolve_command(ref, KEY, run_ref=checked["run_ref"], data_context_ref=current)
    assert pending == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": True,
        "resolution": "unresolved",
        "data_context_ref": current,
    }
    assert reads == [True]
    other = restored_context_ref("another-database", [])
    for candidate_ref, options in (
        ("f" * 48, {"data_context_ref": current}),
        (ref, {"run_ref": "e" * 48, "data_context_ref": current}),
        (ref, {"data_context_ref": other}),
    ):
        replaced = adopter.resolve_command(candidate_ref, KEY, **options)
        assert replaced == {
            "state": "not_observed",
            "receipt": None,
            "may_be_in_flight": False,
            "resolution": "context_replaced",
            "data_context_ref": current,
        }
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
    resolved = adopter.resolve_command(ref, KEY, run_ref="e" * 48, data_context_ref=other)
    assert resolved == {
        "state": "recorded",
        "receipt": {**adopted, "replayed": True},
        "may_be_in_flight": False,
        "resolution": "recorded",
        "data_context_ref": other,
    }
    assert adopter.adopt(ref, "", KEY, INTENT)["receipt_ref"] == adopted["receipt_ref"]
    with pytest.raises(WorkbenchCommandRejected) as exc:
        adopter.resolve_command("f" * 48, KEY, data_context_ref=other)
    assert exc.value.code == "request_key_conflict"
    with pytest.raises(RuntimeError, match="maintenance journal unavailable"):
        adopter.resolve_command(ref, "candidate-adoption-not-recorded", data_context_ref=other)


def test_candidate_adoption_resolution_route_is_read_only_and_not_cached(candidate_case):
    case = candidate_case
    ref = candidate(case)
    before = snapshot(case.conn)

    def read_only_connection(path):
        conn = connect(path)
        conn.execute("PRAGMA query_only=ON")
        return conn

    client = api(case, connection_factory=read_only_connection)
    preview_response = client.post(BASE + ref + "/adopt-preview", json={})
    assert preview_response.status_code == 200, preview_response.get_data(as_text=True)
    assert preview_response.headers["Cache-Control"] == "no-store"
    preview_payload = preview_response.get_json()
    assert preview_payload["meta"]["snapshot_ref"] is None and "." not in preview_payload["meta"]["as_of"]
    checked = preview_payload["data"]
    response = client.get(BASE + ref + "/adoption-commands/" + KEY,
                          query_string={"run_ref": checked["run_ref"], "data_context_ref": checked["data_context_ref"]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json() == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": True,
        "resolution": "unresolved",
        "data_context_ref": checked["data_context_ref"],
    }
    replaced = client.get(BASE + "f" * 48 + "/adoption-commands/" + KEY,
                          query_string={"data_context_ref": checked["data_context_ref"]})
    assert replaced.status_code == 200 and replaced.get_json() == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": False,
        "resolution": "context_replaced",
        "data_context_ref": checked["data_context_ref"],
    }
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


def test_archive_column_order_corruption_is_rejected_at_admission_boundary(candidate_case, monkeypatch):
    import json

    from core.models.workbench_run_adoption import CandidateAdoptionBlocked
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption
    from core.shared.strict_json import canonical_json

    case = candidate_case
    ref = candidate(case)
    read = CandidateStore.capture

    def reordered(store, run_ref):
        # 列与行同步倒序违背存档内嵌 DDL 列序，在读取候选准入源头即拦截并阻断采用。
        capture = dict(read(store, run_ref))
        facts = json.loads(capture["facts_text"])
        facts["columns"]["Parts"] = facts["columns"]["Parts"][::-1]
        facts["tables"]["Parts"] = [row[::-1] for row in facts["tables"]["Parts"]]
        capture["facts_text"] = canonical_json(facts)
        return capture

    monkeypatch.setattr(CandidateStore, "capture", reordered)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as read_rejected:
        store = CandidateStore(case.conn)
        with store.snapshot():
            store.generation_facts(store.capture(store.candidate_run(ref)))
    assert (read_rejected.value.code, read_rejected.value.status) == ("candidate_artifact_invalid", 500)
    with pytest.raises(CandidateAdoptionBlocked) as blocked:
        validate_adoption(case.conn, ref)
    assert blocked.value.code == "candidate_artifact_invalid"
    assert isinstance(blocked.value.__cause__, ValueError)
    checked = service(case.conn).preview(ref)
    assert checked["validation"]["can_adopt"] is False
    assert [row["code"] for row in checked["validation"]["issues"]] == ["candidate_artifact_invalid"]
    assert snapshot(case.conn) == before


def test_http_candidate_adopt_binds_adoption_command_result_target_on_lost_ack(candidate_case):
    from flask import g, request

    from tests.workbench.trial_support import CommitFailureConnection
    from tests.workbench.trial_support import connect as trial_connect

    case = candidate_case
    ref = candidate(case)
    client = api(case, connection_factory=lambda path: trial_connect(path, factory=CommitFailureConnection))

    @case.app.before_request
    def lose_ack():
        if request.method == "POST" and request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    invalid_ref_resp = client.post(
        BASE + "not-a-valid-ref/adopt",
        json={"write_token": "unused", "request_key": KEY, "input": INTENT},
    )
    assert invalid_ref_resp.status_code == 400
    invalid_payload = invalid_ref_resp.get_json()
    assert invalid_payload["committed"] is False
    assert "result_target" not in invalid_payload["error"]

    preview_data = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]
    response = client.post(
        BASE + ref + "/adopt",
        json={
            "write_token": preview_data["write_context"]["write_token"],
            "request_key": KEY,
            "input": INTENT,
        },
    )
    assert response.status_code == 500
    value = response.get_json()
    expected_target = BASE + ref + "/adoption-commands/" + KEY
    assert value["committed"] == "unknown"
    assert value["error"]["request_key"] == KEY
    assert value["error"]["result_target"] == expected_target
    assert value["error"]["retryable"] is False

    resolved = client.get(
        value["error"]["result_target"],
        query_string={
            "run_ref": preview_data["run_ref"],
            "data_context_ref": preview_data["data_context_ref"],
        },
    )
    assert resolved.status_code == 200
    receipt = resolved.get_json()
    assert receipt["state"] == "recorded" and receipt["may_be_in_flight"] is False and receipt["resolution"] == "recorded"
    assert receipt["receipt"]["data"]["candidate_ref"] == ref
