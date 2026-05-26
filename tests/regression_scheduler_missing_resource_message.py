from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from flask import Flask, g, get_flashed_messages

from core.algorithms.dispatch_rules import DispatchRule
from core.algorithms.greedy.dispatch.sgs_scoring import _score_internal_candidate
from core.algorithms.greedy.run_state import ScheduleRunState
from core.infrastructure.errors import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_scheduler_route_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)


def _missing_resource_error(
    *,
    machine_id: str = "",
    operator_id: str = "",
    batch_id: str = "BNX-MISS-101",
    op_code: str = "BNX-MISS-101_10",
    op_type_name: str = "压测数车",
    part_no: str = "P-NX-01",
    part_name: str = "压测泵体",
    piece_id: str = "BNX-MISS-101-1",
) -> ValidationError:
    op = SimpleNamespace(
        id=131,
        op_code=op_code,
        batch_id=batch_id,
        piece_id=piece_id,
        seq=10,
        source="internal",
        machine_id=machine_id,
        operator_id=operator_id,
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OTNX-TURN",
        op_type_name=op_type_name,
    )
    batch = SimpleNamespace(
        batch_id=batch_id,
        part_no=part_no,
        part_name=part_name,
        priority="normal",
        due_date=date(2026, 1, 10),
        quantity=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        _score_internal_candidate(
            ctx=SimpleNamespace(),
            state=ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0)),
            op=op,
            batch=batch,
            batch_id="BNX-MISS-101",
            batch_order={"BNX-MISS-101": 0},
            dispatch_rule=DispatchRule.ATC,
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
            avg_proc_hours=1.0,
            strict_mode=False,
        )
    return exc_info.value


@pytest.mark.parametrize(
    ("machine_id", "operator_id", "missing_text", "missing_fields"),
    [
        ("", "", "缺少设备、人员", ["设备", "人员"]),
        ("MC-OK", "", "缺少人员", ["人员"]),
        ("", "OP-OK", "缺少设备", ["设备"]),
    ],
)
def test_sgs_missing_resource_validation_message_names_business_context(
    machine_id: str,
    operator_id: str,
    missing_text: str,
    missing_fields: List[str],
) -> None:
    exc = _missing_resource_error(machine_id=machine_id, operator_id=operator_id)
    visible = str((exc.details or {}).get("user_message") or "")

    assert exc.field == "resource"
    assert exc.message == visible
    assert "批次 BNX-MISS-101" in visible
    assert "工序 BNX-MISS-101_10" in visible
    assert "顺序 10" in visible
    assert "工种 压测数车" in visible
    assert "图号 P-NX-01" in visible
    assert "零件 压测泵体" in visible
    assert "件号 BNX-MISS-101-1" in visible
    assert missing_text in visible
    assert "工序编号=131" not in visible
    assert (exc.details or {}).get("missing_fields") == missing_fields
    assert (exc.details or {}).get("part_no") == "P-NX-01"
    assert (exc.details or {}).get("part_name") == "压测泵体"
    assert (exc.details or {}).get("piece_id") == "BNX-MISS-101-1"


def test_sgs_auto_assign_failure_message_does_not_blame_batch_details() -> None:
    from core.algorithms.greedy.run_context import ScheduleRunContext

    batch_id = "BNX-AUTO-101"
    op = SimpleNamespace(
        id=132,
        op_code="BNX-AUTO-101_10",
        batch_id=batch_id,
        piece_id="BNX-AUTO-101-1",
        seq=10,
        source="internal",
        machine_id="",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OTNX-TURN",
        op_type_name="压测数车",
    )
    batch = SimpleNamespace(
        batch_id=batch_id,
        part_no="P-NX-01",
        part_name="压测泵体",
        priority="normal",
        due_date=date(2026, 1, 10),
        quantity=1,
    )
    ctx = ScheduleRunContext(calendar=None, logger=None, algo_stats={"fallback_counts": {}})

    with pytest.raises(ValidationError) as exc_info:
        _score_internal_candidate(
            ctx=ctx,
            state=ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0)),
            op=op,
            batch=batch,
            batch_id=batch_id,
            batch_order={batch_id: 0},
            dispatch_rule=DispatchRule.ATC,
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=True,
            resource_pool={
                "machines_by_op_type": {"OTNX-TURN": ["MC-1"]},
                "operators_by_machine": {"MC-1": []},
                "machines_by_operator": {},
                "pair_rank": {},
            },
            avg_proc_hours=1.0,
            strict_mode=False,
        )

    details = exc_info.value.details or {}
    visible = str(details.get("user_message") or "")
    assert exc_info.value.field == "resource"
    assert "没有找到可用的自动分配设备和人员组合" in visible
    assert "请到批次详情补齐" not in visible
    assert details.get("reason") == "auto_assign_no_resource_combination"
    assert details.get("auto_assign_reason") == "auto_assign_no_operator_candidate"
    assert (ctx.algo_stats.get("fallback_counts") or {}) == {}


@pytest.mark.parametrize(
    ("auto_assign_reason", "expected_public_reason", "expected_text"),
    [
        ("auto_assign_missing_op_type_id", "auto_assign_inputs_missing", "缺少自动派工所需工种信息"),
        ("auto_assign_missing_machine_pool", "auto_assign_resource_pool_incomplete", "自动派工资料不完整"),
        ("invalid_internal_hours", "invalid_internal_work_hours", "工时不合法"),
        ("auto_assign_no_machine_candidate", "auto_assign_no_resource_combination", "没有找到可用的自动分配设备和人员组合"),
        ("auto_assign_no_operator_candidate", "auto_assign_no_resource_combination", "没有找到可用的自动分配设备和人员组合"),
        ("auto_assign_no_feasible_pair", "auto_assign_no_resource_combination", "没有找到可用的自动分配设备和人员组合"),
    ],
)
def test_sgs_auto_assign_public_reason_names_match_public_error_codes(
    auto_assign_reason: str,
    expected_public_reason: str,
    expected_text: str,
) -> None:
    from core.algorithms.greedy.dispatch.resource_validation import (
        RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE,
        internal_resource_validation_message,
    )

    batch_id = "BNX-AUTO-102"
    op = SimpleNamespace(
        id=133,
        op_code="BNX-AUTO-102_10",
        batch_id=batch_id,
        piece_id="BNX-AUTO-102-1",
        seq=10,
        source="internal",
        machine_id="",
        operator_id="",
        op_type_name="压测数车",
    )
    batch = SimpleNamespace(batch_id=batch_id, part_no="P-NX-02", part_name="压测端盖")
    message, details = internal_resource_validation_message(
        batch=batch,
        op=op,
        meta={"op_id": op.id, "batch_id": batch_id, "seq": op.seq},
        machine_id="",
        operator_id="",
        reason=RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE,
        auto_assign_reason=auto_assign_reason,
    )

    assert expected_text in message
    assert details.get("user_message") == message
    assert details.get("reason") == expected_public_reason
    assert details.get("auto_assign_reason") == auto_assign_reason


@pytest.mark.parametrize(
    ("module_name", "handler_name", "path"),
    [
        ("web.routes.scheduler_run", "run_schedule", "/scheduler/run"),
        ("web.routes.scheduler_week_plan", "simulate_schedule", "/scheduler/simulate"),
    ],
)
def test_scheduler_pages_flash_sgs_missing_resource_user_message(
    module_name: str,
    handler_name: str,
    path: str,
) -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()
    route_mod = __import__(module_name, fromlist=[handler_name])

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            raise _missing_resource_error()

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-missing-resource-message"
        with app.test_request_context(path, method="POST", data={"batch_ids": ["BNX-MISS-101"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = getattr(route_mod, handler_name)()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        error_messages = [msg for cat, msg in flashes if cat == "error"]
        assert len(error_messages) == 1
        assert "批次 BNX-MISS-101" in error_messages[0]
        assert "工序 BNX-MISS-101_10" in error_messages[0]
        assert "工种 压测数车" in error_messages[0]
        assert "图号 P-NX-01" in error_messages[0]
        assert "零件 压测泵体" in error_messages[0]
        assert "件号 BNX-MISS-101-1" in error_messages[0]
        assert "缺少设备、人员" in error_messages[0]
        assert "工序编号=131" not in error_messages[0]
    finally:
        route_mod.url_for = old_url_for


@pytest.mark.parametrize(
    ("module_name", "handler_name", "path"),
    [
        ("web.routes.scheduler_run", "run_schedule", "/scheduler/run"),
        ("web.routes.scheduler_week_plan", "simulate_schedule", "/scheduler/simulate"),
    ],
)
def test_scheduler_pages_flash_sgs_missing_resource_sanitizes_dirty_context(
    module_name: str,
    handler_name: str,
    path: str,
) -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()
    route_mod = __import__(module_name, fromlist=[handler_name])

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            raise _missing_resource_error(
                batch_id="BNX-MISS-101\nSECRET_TOKEN=abc",
                op_code="OP-10 Traceback hidden",
                op_type_name="压测数车 /tmp/private.db",
                part_no="P-NX-01 SECRET_TOKEN",
                part_name="压测泵体 Traceback hidden",
                piece_id="BNX-MISS-101-1 /tmp/private.db",
            )

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-missing-resource-dirty-context"
        with app.test_request_context(path, method="POST", data={"batch_ids": ["BNX-MISS-101"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = getattr(route_mod, handler_name)()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        error_messages = [msg for cat, msg in flashes if cat == "error"]
        assert len(error_messages) == 1
        visible = error_messages[0]
        assert "缺少设备、人员" in visible
        assert "请到批次详情补齐后再排产" in visible
        assert "SECRET_TOKEN" not in visible
        assert "Traceback" not in visible
        assert "/tmp/private.db" not in visible
    finally:
        route_mod.url_for = old_url_for
