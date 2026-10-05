"""Real preflight API read-only, field, scope, execution and token contracts."""


import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.preflight_support import checked, payload
from tests.workbench.preflight_support import pf as pf_fixture  # noqa: F401
from tests.workbench.preflight_support import pf_legacy_schema as pf_legacy_fixture  # noqa: F401
from web.routes.workbench.preflight import resolve_preflight_input


@pytest.mark.parametrize("fixture_name,source", [("pf", "execution_ledger"), ("pf_legacy_schema", "legacy_guard_only")])
def test_read_only_zero_hours_and_unavailable_worker(request, fixture_name, source):
    pf = request.getfixturevalue(fixture_name)
    data = checked(pf)
    assert data["counts"]["ready_tasks"] == 1
    assert data["counts"]["blocked_tasks"] == 0
    assert data["calendar_check"] == "not_evaluated"
    assert data["effective_start"] == "2026-09-09T00:00:00"
    assert data["effective_end_exclusive"] == "2026-09-10T00:00:00"
    assert data["write_context"]["capabilities"]["scheduling.run"] is False
    assert data["write_context"]["write_token"] is None
    reasons = {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True and "schedule_not_computed" in reasons
    assert data["execution_projection_source"] == source
    assert ("execution_ledger_unavailable" in reasons) == (source == "legacy_guard_only")


_RECEIPT = ("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) "
            "VALUES ('preflight-receipt-0001','" + "c" * 32 + "','{}','context','" + "d" * 64 + "','{{\"result\":\"{}\"}}')")


@pytest.mark.parametrize("change,stale", [(_RECEIPT.format("dashboard.transition", "committed"), False), (_RECEIPT.format("calendar.defaults", "committed"), True)])
def test_input_ref_uses_the_run_worker_facts_scope(pf, change, stale):
    # 检查到开始之间：日志、自动维护时钟、看板处置、试调和“无改动”回执排产都不读，和排产计算同一口径，不算现场变化；
    # 其他已提交的回执仍保守地算变化。
    data = checked(pf)
    pf.conn.execute(change)
    pf.conn.commit()
    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        try:
            if stale:
                with pytest.raises(WorkbenchCommandRejected, match="有变化"):
                    resolve_preflight_input(pf.conn, data["input_ref"])
            else:
                assert resolve_preflight_input(pf.conn, data["input_ref"]) == payload(pf)
        finally:
            pf.conn.rollback()
