"""Actual SQL rollback, concurrent receipt replay and adoption command resolution."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.facts.candidate_facts import TABLE_KEYS
from core.services.workbench.facts.run_data_context import restored_context_ref
from tests.workbench.run_candidate_adoption_support import BASE, INTENT, KEY, api, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import connect
from tests.workbench.trial_adoption_support import BAD_RESOURCE_NAMES


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
    from copy import deepcopy

    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption

    case = candidate_case
    ref = candidate(case)
    read = CandidateStore.capture

    def reordered(store, run_ref):
        # 列与行同步倒序违背存档内嵌 DDL 列序，在读取候选准入源头即拦截；采用预览与采用都原样报 500。
        capture = dict(read(store, run_ref))
        facts = deepcopy(capture["facts"])
        facts["columns"]["Parts"] = facts["columns"]["Parts"][::-1]
        facts["tables"]["Parts"] = [row[::-1] for row in facts["tables"]["Parts"]]
        capture["facts"] = facts
        return capture

    monkeypatch.setattr(CandidateStore, "capture", reordered)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as read_rejected:
        store = CandidateStore(case.conn)
        with store.snapshot():
            store.generation_facts(store.capture(store.candidate_run(ref)))
    assert (read_rejected.value.code, read_rejected.value.status) == ("candidate_artifact_invalid", 500)
    for adoption in (lambda: validate_adoption(case.conn, ref), lambda: service(case.conn).preview(ref)):
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            adoption()
        assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)
    response = api(case).post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "candidate_artifact_invalid"
    assert snapshot(case.conn) == before


def _drop_rows(archive, name, **match):
    columns = archive["columns"][name]
    positions = {columns.index(column): value for column, value in match.items()}
    archive["tables"][name] = [row for row in archive["tables"][name]
                               if any(row[position] != value for position, value in positions.items())]


def _swap_operation_ids(archive):
    position = archive["columns"]["WorkbenchPlanSourceRefs"].index("source_key")
    first, second = archive["tables"]["WorkbenchPlanSourceRefs"]
    first[position], second[position] = second[position], first[position]


def _rename(archive, table, key, value):
    columns = archive["columns"][table]
    (row,) = [row for row in archive["tables"][table] if row[columns.index(TABLE_KEYS[table])] == key]
    row[columns.index("name")] = value


# A stored generation archive the admission boundary takes whole, lacking one relation an adopted task records,
# naming each operation's ref with the other operation's id, or naming the arranged machine or the operations' type
# with a name readers do not show.
_ARCHIVE_DAMAGE = {
    "machine_row_missing": lambda archive: _drop_rows(archive, "Machines", machine_id="M1"),
    "machine_ref_missing": lambda archive: _drop_rows(archive, "WorkbenchEntityRefs", kind="machine", entity_key="M1"),
    "batch_row_missing": lambda archive: _drop_rows(archive, "Batches", batch_id="B1"),
    "operation_ref_misbound": _swap_operation_ids,
    **{"machine_name_" + kind: lambda archive, value=value: _rename(archive, "Machines", "M1", value)
       for kind, value in BAD_RESOURCE_NAMES.items()},
    **{"op_type_name_" + kind: lambda archive, value=value: _rename(archive, "OpTypes", "T1", value)
       for kind, value in BAD_RESOURCE_NAMES.items()},
}


@pytest.mark.parametrize("damage", sorted(_ARCHIVE_DAMAGE))
def test_adoption_reads_archive_relations_and_rejects_a_missing_misbound_or_unshowable_one(candidate_case, monkeypatch,
                                                                                         damage):
    import json

    from core.shared.strict_json import canonical_json
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    case = candidate_case
    case.operation(seq=2)
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    read = WorkbenchRunCandidateRepository.job_capture

    def damaged(repo, run_ref):
        row = dict(read(repo, run_ref))
        archive = json.loads(row["conditions_archive_json"])
        _ARCHIVE_DAMAGE[damage](archive)
        text = canonical_json(archive)
        row.update(conditions_archive_json=text, conditions_archive_bytes=len(text.encode("utf-8")))
        return row

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "job_capture", damaged)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)
    response = api(case).post(BASE + ref + "/adopt-preview", json={})
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "candidate_artifact_invalid"
    assert snapshot(case.conn) == before


def test_adoption_records_the_operation_type_name_as_the_run_archived_it(candidate_case):
    # 工种名与资源名同一准入：合法名称首尾的空白原样写进正式计划，不裁剪。
    case = candidate_case
    case.conn.execute("UPDATE OpTypes SET name=' Turning ' WHERE op_type_id='T1'")
    case.conn.commit()
    ref = candidate(case)
    service(case.conn).adopt(ref, preview(case, ref), KEY, INTENT)
    assert [row[0] for row in case.conn.execute("SELECT DISTINCT op_type_label FROM Schedule")] == [" Turning "]


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



@pytest.mark.parametrize(("field", "value"), [("reason", " "), ("declared_operator", "x" * 101)])
def test_http_candidate_adopt_rejection_points_at_the_reason_or_operator_field(candidate_case, field, value):
    case = candidate_case
    ref = candidate(case)
    client = api(case)
    token = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    before = snapshot(case.conn)
    response = client.post(BASE + ref + "/adopt", json={"write_token": token, "request_key": KEY,
                                                         "input": {**INTENT, field: value}})
    assert response.status_code == 422, response.get_json()
    error = response.get_json()["error"]
    message = "采用原因或声明操作人为空、过长或含无效字符。"
    assert (error["code"], error["message"], error["fields"]) == ("invalid_input", message, [{"path": field, "message": message}])
    assert snapshot(case.conn) == before


def test_one_adoption_records_one_reading_of_the_app_clock(candidate_case):
    import json
    from datetime import datetime, timedelta

    from web.runtime_host import install_wall_clock

    case = candidate_case
    ref = candidate(case)
    client = api(case)
    token = client.post(BASE + ref + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    readings = []

    def clock():
        # Every reading moves one second on, crossing midnight after the first.
        readings.append(datetime(2026, 10, 7, 23, 59, 59, 900000) + timedelta(seconds=len(readings)))
        return readings[-1]

    install_wall_clock(case.app, clock)
    response = client.post(BASE + ref + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 200, response.get_json()
    assert len(readings) == 1
    head = case.conn.execute("SELECT adopted_at FROM ScheduleHistory ORDER BY version DESC LIMIT 1").fetchone()[0]
    logged = json.loads(case.conn.execute(
        "SELECT detail FROM OperationLogs WHERE action='adopt_run_candidate'").fetchone()[0])["adopted_at"]
    entry = json.loads(case.conn.execute(
        "SELECT times_json FROM WorkbenchHistoryEntries WHERE request_key=?", (KEY,)).fetchone()[0])["adopted_at"]
    assert head == logged == entry == "2026-10-07T23:59:59"

def test_unreadable_archive_json_blocks_adoption_while_other_storage_failures_surface(candidate_case, monkeypatch):
    from core.models.content import StoredJsonCorrupt
    from core.models.workbench_run_adoption import CandidateAdoptionBlocked
    from core.services.workbench.run import candidate_adoption_validation

    case = candidate_case
    ref = candidate(case)
    case.conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json='{' WHERE action='scheduling.run'")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(CandidateAdoptionBlocked) as blocked:
        candidate_adoption_validation.validate_adoption(case.conn, ref)
    assert blocked.value.code == "candidate_artifact_invalid"
    assert isinstance(blocked.value.__cause__, StoredJsonCorrupt)
    checked = service(case.conn).preview(ref)
    assert checked["validation"]["can_adopt"] is False
    assert [row["code"] for row in checked["validation"]["issues"]] == ["candidate_artifact_invalid"]
    assert snapshot(case.conn) == before

    failure = WorkbenchCommandRejected("storage_failure", "注入的其他存储失败", 500)

    def other_failure(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(candidate_adoption_validation, "load_adoption_candidate", other_failure)
    with pytest.raises(WorkbenchCommandRejected) as raised:
        candidate_adoption_validation.validate_adoption(case.conn, ref)
    assert raised.value is failure
