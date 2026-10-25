"""One transaction for immutable facts and shared command receipts."""


import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def test_http_read_snapshot_reuses_shared_binding_and_keeps_stale_messages(outsourcing_case, monkeypatch):
    from core.services.workbench import messages
    from tests.workbench.outsourcing_support import ROOT, api
    from web import public_token_registry
    from web.routes.workbench import read_context

    client = api(outsourcing_case, monkeypatch)
    path, query = ROOT + "/targets", {"size": 1}
    initial = client.get(path, query_string=query)
    assert initial.status_code == 200, initial.get_json()
    snapshot = initial.get_json()["meta"]["snapshot_ref"]
    resolves, original_resolve = [], read_context.resolve_public_token

    def resolved(*args, **kwargs):
        resolves.append(args[1])
        return original_resolve(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(read_context, "resolve_public_token", resolved)
        repeated = client.get(path, query_string={**query, "snapshot_ref": snapshot})
    assert repeated.status_code == 200, repeated.get_json()
    assert repeated.get_json()["data"] == initial.get_json()["data"]
    assert repeated.get_json()["meta"]["as_of"] == initial.get_json()["meta"]["as_of"]
    assert resolves == [snapshot]
    wrong_scope = client.get(path, query_string={**query, "query": "no-match", "snapshot_ref": snapshot})
    assert wrong_scope.status_code == 409
    assert wrong_scope.get_json()["error"]["code"] == "snapshot_stale"
    assert wrong_scope.get_json()["error"]["message"] == messages.STALE
    outsourcing_case.conn.execute("UPDATE BatchOperations SET op_type_name='Changed treatment' WHERE op_code='XO1'")
    outsourcing_case.conn.commit()
    changed = client.get(path, query_string={**query, "snapshot_ref": snapshot})
    assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "snapshot_stale"
    assert changed.get_json()["error"]["message"] == "外协来源或登记内容有变化，还没有保存；系统没有偷偷用新数据。请点「刷新」后重新核对。"
    now = public_token_registry.time.time()
    with monkeypatch.context() as patch:
        patch.setattr(public_token_registry.time, "time", lambda: now + 901)
        expired = client.get(path, query_string={**query, "snapshot_ref": snapshot})
    assert expired.status_code == 409 and expired.get_json()["error"]["code"] == "snapshot_stale"
    assert expired.get_json()["error"]["message"] == messages.STALE


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
        receipt = WorkbenchCommandService(other).lookup(key)
        assert receipt is not None
        assert receipt["data"] == first["data"]
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


@pytest.mark.parametrize('stage', ['receipt'])
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


def test_internal_source_size_is_checked_only_when_its_document_is_saved(outsourcing_case, monkeypatch):
    from core.models import workbench_outsourcing

    case = outsourcing_case
    monkeypatch.setattr(workbench_outsourcing, "MAX_BYTES", 1024)
    case.conn.execute("UPDATE Parts SET remark=? WHERE part_no='XP1'", ("x" * 2048,))
    case.conn.commit()
    with case.reader.read_snapshot():
        targets = case.reader.targets(size=1)
    assert len(targets["items"]) == 1 and targets["page"]["total"] == 3
    preview = case.preview(case.payload())
    with pytest.raises(WorkbenchCommandRejected) as oversized:
        case.confirm(preview, key="outsourcing-real-document-limit")
    assert oversized.value.code == "query_too_large" and oversized.value.status == 413
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingReceipts").fetchone()[0] == 0
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-real-document-limit") is None


def test_http_preview_enforces_its_actual_utf8_envelope_limit(outsourcing_case, monkeypatch):
    from core.models.workbench_outsourcing import MAX_BYTES
    from tests.workbench.outsourcing_support import ROOT, api

    case = outsourcing_case
    case.conn.execute("UPDATE BatchOperations SET op_type_name=? WHERE op_code='XO1'", ("工" * (MAX_BYTES // 3 + 1),))
    case.conn.commit()
    before = original_rows(case.conn)
    response = api(case, monkeypatch).post(ROOT + "/receipts/preview", json={"input": case.payload()})
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "query_too_large"
    assert original_rows(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
