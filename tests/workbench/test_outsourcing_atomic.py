"""One transaction for inline receipt status, immutable facts and shared command receipts."""

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
)
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import (
    outsourcing_case as _outsourcing_case,  # noqa: F401
)


def test_http_read_snapshot_reuses_shared_binding_and_keeps_stale_messages(
    outsourcing_case, monkeypatch
):
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
    wrong_scope = client.get(
        path, query_string={**query, "query": "no-match", "snapshot_ref": snapshot}
    )
    assert wrong_scope.status_code == 409
    assert wrong_scope.get_json()["error"]["code"] == "snapshot_stale"
    assert wrong_scope.get_json()["error"]["message"] == messages.STALE
    outsourcing_case.conn.execute(
        "UPDATE BatchOperations SET op_type_name='Changed treatment' WHERE op_code='XO1'"
    )
    outsourcing_case.conn.commit()
    changed = client.get(path, query_string={**query, "snapshot_ref": snapshot})
    assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "snapshot_stale"
    assert (
        changed.get_json()["error"]["message"]
        == "外协来源或登记内容有变化，还没有保存；系统没有偷偷用新数据。请点「刷新」后重新核对。"
    )
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
        replay = writer.execute(
            preview["input"],
            request_key=key,
            validate_context=lambda *_: pytest.fail(
                "committed replay must not resolve expired preview"
            ),
        )
        assert replay["replayed"] is True
        assert replay["receipt_ref"] == first["receipt_ref"]
        receipt = WorkbenchCommandService(other).lookup(key)
        assert receipt is not None
        assert receipt["data"] == first["data"]
        with pytest.raises(WorkbenchCommandRejected) as conflict:
            case.confirm(
                preview, key=key, payload={**preview["input"], "reason": "different intent"}
            )
        assert conflict.value.code == "request_key_conflict"
        ref = first["data"]["outsourcing_ref"]
        update = {
            "outsourcing_ref": ref,
            "declared_operator": "Inspector",
            "reason": "Current check",
        }
        left, right = case.preview(update), case.preview(update, other)
        second = case.confirm(left)
        with pytest.raises(WorkbenchCommandRejected) as stale:
            case.confirm(right, conn=other)
        assert stale.value.code == "stale_write"
        assert case.detail(ref)["history_count"] == 2
        stored_receipt = case.conn.execute(
            "SELECT latest_fact_ref, history_count, reason FROM WorkbenchOutsourcingReceipts "
            "WHERE outsourcing_ref=?",
            (ref,),
        ).fetchone()
        assert stored_receipt["latest_fact_ref"] == second["data"]["fact_ref"]
        assert stored_receipt["history_count"] == 2
        assert stored_receipt["reason"] == "Current check"
    finally:
        other.close()


def test_receipt_write_failure_rolls_back_header_group_facts_and_receipt(outsourcing_case):
    case = outsourcing_case
    source = original_rows(case.conn)
    preview = case.preview(case.payload(merged=True))
    case.conn.execute(
        "CREATE TRIGGER injected_outsourcing_failure BEFORE INSERT ON WorkbenchCommandReceipts"
        " BEGIN SELECT RAISE(ABORT,'injected failure'); END"
    )
    case.conn.commit()
    with pytest.raises(WorkbenchCommandUncertain):
        case.confirm(preview, key="outsourcing-fault-rollback-key")
    for name in ("Receipts", "Members", "Facts"):
        assert (
            case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcing" + name).fetchone()[0]
            == 0
        )
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-fault-rollback-key") is None
    assert case.conn.in_transaction is False
    assert original_rows(case.conn) == source
    case.conn.execute("DROP TRIGGER injected_outsourcing_failure")
    case.conn.commit()
    assert case.confirm(preview, key="outsourcing-fault-rollback-key")["result"] == "committed"


def test_saved_receipt_documents_enforce_size_limit_while_unrelated_part_remark_is_not_stored(
    outsourcing_case, monkeypatch
):
    from core.models import workbench_outsourcing

    case = outsourcing_case
    monkeypatch.setattr(workbench_outsourcing, "MAX_BYTES", 1024)
    # Parts.remark is not persisted into Facts or Receipts after removing source_facts_json.
    case.conn.execute("UPDATE Parts SET remark=? WHERE part_no='XP1'", ("x" * 2048,))
    case.conn.commit()
    with case.reader.read_snapshot():
        targets = case.reader.targets(size=1, bind_snapshot=lambda _content: None)
    assert len(targets["items"]) == 1 and targets["page"]["total"] == 3
    first_preview = case.preview(case.payload())
    committed = case.confirm(first_preview, key="outsourcing-unrelated-part-remark-ok")
    assert committed["result"] == "committed"
    fact_columns = {
        row[1] for row in case.conn.execute('PRAGMA table_info("WorkbenchOutsourcingFacts")')
    }
    assert "source_facts_json" not in fact_columns

    # Oversized origin_json / identity_json (e.g. BatchOperations.op_type_name) is rejected and rolled back.
    case.conn.execute(
        "UPDATE BatchOperations SET op_type_name=? WHERE op_code='XO2'",
        ("热" * 500,),
    )
    case.conn.commit()
    second_payload = case.payload()
    second_payload["target"]["operation_refs"] = [case.operation_ref("XO2")]
    second_preview = case.preview(second_payload)
    with pytest.raises(WorkbenchCommandRejected) as oversized:
        case.confirm(second_preview, key="outsourcing-real-document-limit")
    assert oversized.value.code == "query_too_large" and oversized.value.status == 413
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingReceipts").fetchone()[0] == 1
    assert WorkbenchCommandService(case.conn).lookup("outsourcing-real-document-limit") is None


def test_http_preview_enforces_its_actual_utf8_envelope_limit(outsourcing_case, monkeypatch):
    from core.models.workbench_outsourcing import MAX_BYTES
    from tests.workbench.outsourcing_support import ROOT, api

    case = outsourcing_case
    case.conn.execute(
        "UPDATE BatchOperations SET op_type_name=? WHERE op_code='XO1'",
        ("工" * (MAX_BYTES // 3 + 1),),
    )
    case.conn.commit()
    before = original_rows(case.conn)
    response = api(case, monkeypatch).post(
        ROOT + "/receipts/preview", json={"input": case.payload()}
    )
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "query_too_large"
    assert original_rows(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0


_TIMELINE = "计划回厂和实际回厂不能早于发出时间。"


@pytest.mark.parametrize(("patch", "paths", "message"), [
    ({"declared_operator": " "}, ["declared_operator"], "请填写有效的经办人，不能留空或使用非文字内容。"),
    ({"reason": ""}, ["reason"], "请填写有效的本次核实或更正原因，不能留空或使用非文字内容。"),
    ({"sent": "2026-09-07 09:00"}, ["sent"], "登记时间格式不对，请按 2026-09-13 08:30:00 这样填写。"),
    ({"planned": "2026-02-30T12:00:00"}, ["planned"], "登记时间不是有效日期。"),
    ({"confirmedState": "lost"}, ["confirmedState"], "确认状态必须是在途、已回厂或待确认。"),
    ({"planned": "2026-09-06T12:00:00"}, ["planned"], _TIMELINE),
    ({"planned": "2026-09-06T12:00:00", "returned": "2026-09-06T10:00:00", "confirmedState": "returned"},
     ["planned", "returned"], _TIMELINE),
    ({"sent": "2026-09-11T09:00:00", "planned": "2026-09-12T09:00:00"}, ["sent"], "实际发出和实际回厂不能晚于当前时间。"),
    ({"confirmedState": "returned"}, ["confirmedState", "returned"], "已回厂状态与实际回厂时间必须同时填写；未回厂时实际回厂必须为空。"),
], ids=["operator", "reason", "time-shape", "time-day", "state", "planned-early", "both-early", "sent-future", "state-returned"])
def test_http_preview_and_confirm_point_at_the_receipt_fields(outsourcing_case, monkeypatch, patch, paths, message):
    from tests.workbench.outsourcing_support import ROOT, api

    case = outsourcing_case
    client = api(case, monkeypatch)
    token = client.post(ROOT + "/receipts/preview", json={"input": case.payload()}).get_json()["data"]["write_context"]["write_token"]
    before = original_rows(case.conn)
    for path, body in ((ROOT + "/receipts/preview", {"input": case.payload(**patch)}),
                       (ROOT + "/receipts", {"request_key": "outsourcing-field-path-01", "write_token": token,
                                             "input": case.payload(**patch)})):
        response = client.post(path, json=body)
        assert response.status_code == 422, response.get_json()
        error = response.get_json()["error"]
        assert (error["code"], error["message"]) == ("invalid_input", message)
        assert error["fields"] == [{"path": field, "message": message} for field in paths]
    assert original_rows(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
