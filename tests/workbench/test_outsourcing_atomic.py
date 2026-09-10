"""One transaction for immutable facts and shared command receipts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from flask import current_app

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401
from web.routes.workbench.write_context import validate_write_context


def test_double_connection_stale_and_replay_before_expired_context(outsourcing_case):
    case = outsourcing_case
    other = get_connection(str(case.path))
    try:
        preview = case.preview(case.payload())
        key = "outsourcing-double-connection-key"
        first = case.confirm(preview, conn=other, key=key)
        writer = case.writer()
        replay = writer.execute(preview["input"], request_key=key,
            validate_context=lambda *_: pytest.fail("committed replay must not resolve expired preview"))
        assert replay["replayed"] is True
        assert replay["receipt_ref"] == first["receipt_ref"]
        assert WorkbenchCommandService(other).lookup(key)["data"] == first["data"]
        with pytest.raises(WorkbenchCommandRejected) as conflict:
            case.confirm(preview, key=key, payload={**preview["input"], "reason": "different intent"})
        assert conflict.value.code == "request_key_conflict"
        ref = first["data"]["outsourcing_ref"]
        update = {"outsourcing_ref": ref, "declared_operator": "Inspector", "reason": "Current check"}
        left, right = case.preview(update), case.preview(update, other)
        case.confirm(left)
        with pytest.raises(WorkbenchCommandRejected) as stale:
            case.confirm(right, conn=other)
        assert stale.value.code == "stale_write"
        assert case.detail(ref)["history_count"] == 2
    finally:
        other.close()


@pytest.mark.parametrize("different", [False, True])
def test_simultaneous_same_key_serializes_without_duplicate_facts(outsourcing_case, different):
    case = outsourcing_case
    first = case.preview(case.payload())
    second = case.preview(case.payload(reason="Other declared intent")) if different else first
    app, ready = current_app._get_current_object(), Barrier(2)

    def send(preview):
        conn = get_connection(str(case.path))
        try:
            with app.app_context():
                ready.wait(timeout=5)
                return case.writer(conn).execute(preview["input"], request_key="outsourcing-concurrent-same-key",
                    validate_context=lambda subject, action, snapshot: validate_write_context(
                        preview["write_context"]["write_token"], subject, action, snapshot))
        except WorkbenchCommandRejected as exc:
            return exc.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, [first, second]))
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE action='outsourcing.confirm'").fetchone()[0] == 1
    if different:
        assert sum(result == "request_key_conflict" for result in results) == 1
    else:
        assert sorted(result["replayed"] for result in results) == [False, True]
        assert results[0]["receipt_ref"] == results[1]["receipt_ref"]


@pytest.mark.parametrize("stage", ["members", "fact", "receipt"])
def test_failure_rolls_back_header_group_facts_and_receipt(outsourcing_case, stage):
    case = outsourcing_case
    source = original_rows(case.conn)
    preview = case.preview(case.payload(merged=True))
    table = {"members": "WorkbenchOutsourcingMembers", "fact": "WorkbenchOutsourcingFacts", "receipt": "WorkbenchCommandReceipts"}[stage]
    case.conn.execute("CREATE TRIGGER injected_outsourcing_failure BEFORE INSERT ON " + table +
                      " BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandUncertain):
        case.confirm(preview, key="outsourcing-fault-rollback-key")
    for name in ("Receipts", "Members", "Facts"):
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcing" + name).fetchone()[0] == 0
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-fault-rollback-key") is None
    assert case.conn.in_transaction is False
    assert original_rows(case.conn) == source
    case.conn.execute("DROP TRIGGER injected_outsourcing_failure")
    case.conn.commit()
    assert case.confirm(preview, key="outsourcing-fault-rollback-key")["result"] == "committed"


def test_caller_transaction_and_client_actor_cannot_claim_commit(outsourcing_case):
    case = outsourcing_case
    preview = case.preview(case.payload())
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="最外层事务"):
        case.confirm(preview)
    assert case.conn.in_transaction is True
    case.conn.rollback()
    writer = case.writer()
    writer.actor_provider = lambda: ""
    with pytest.raises(WorkbenchCommandUncertain):
        writer.execute(preview["input"], request_key="outsourcing-empty-actor-key", validate_context=lambda *_: None)
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-empty-actor-key") is None


def test_preview_binds_payload_not_only_object(outsourcing_case):
    case = outsourcing_case
    preview = case.preview(case.payload())
    with pytest.raises(WorkbenchCommandRejected) as stale:
        case.confirm(preview, payload={**preview["input"], "planned": "2026-09-12T12:00:00"})
    assert stale.value.code == "stale_write"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0


def test_failed_append_preserves_existing_return_and_original_receipt(outsourcing_case):
    case = outsourcing_case
    first = case.confirm(case.preview(case.payload(returned="2026-09-09T11:00:00", confirmedState="returned")))
    ref = first["data"]["outsourcing_ref"]
    old = case.detail(ref)
    draft = case.preview({"outsourcing_ref": ref, "returned": "2026-09-09T11:30:00", "reason": "Correct unloading time",
                          "declared_operator": "Receiver"})
    case.conn.execute("CREATE TRIGGER fail_append_receipt BEFORE INSERT ON WorkbenchCommandReceipts BEGIN SELECT RAISE(ABORT,'fixture'); END")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandUncertain):
        case.confirm(draft, key="outsourcing-append-failure-key")
    assert case.detail(ref) == old
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-append-failure-key") is None


def test_member_order_is_normalized_for_same_intent(outsourcing_case):
    case = outsourcing_case
    draft = case.preview(case.payload(merged=True))
    first = case.confirm(draft, key="outsourcing-normalized-members-key")
    reordered = {**draft["input"], "target": {**draft["input"]["target"],
                  "operation_refs": list(reversed(draft["input"]["target"]["operation_refs"]))}}
    replay = case.writer().execute(reordered, request_key="outsourcing-normalized-members-key", validate_context=lambda *_: None)
    assert replay["receipt_ref"] == first["receipt_ref"]
    assert replay["replayed"] is True
