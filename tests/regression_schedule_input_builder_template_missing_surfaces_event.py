from __future__ import annotations

from types import SimpleNamespace

from core.services.scheduler.schedule_input_builder import build_algo_operations


class _NullRepo:
    def get(self, *args, **kwargs):
        return None


class _StubSvc:
    def __init__(self):
        self.part_op_repo = _NullRepo()
        self.group_repo = _NullRepo()
        self._aps_schedule_input_cache = {}

    @staticmethod
    def _get_batch_or_raise(batch_id: str):
        return SimpleNamespace(part_no="P001")


def test_schedule_input_builder_template_missing_surfaces_event() -> None:
    svc = _StubSvc()
    external = SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=20,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="external",
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days=2.0,
    )

    outcome = build_algo_operations(svc, [external], strict_mode=False, return_outcome=True)
    assert outcome.has_events is True, "模板缺失应产出结构化退化事件"
    codes = [event.code for event in outcome.events]
    assert "template_missing" in codes, f"模板缺失事件未透出：{codes!r}"

    algo_op = outcome.value[0]
    assert algo_op.merge_context_degraded is True, f"组合并语义退化标记缺失：{algo_op!r}"
    merge_codes = [str(event.get("code") or "") for event in algo_op.merge_context_events]
    assert "template_missing" in merge_codes, f"merge_context_events 未保留 template_missing：{algo_op.merge_context_events!r}"
    assert float(algo_op.ext_days or 0.0) == 2.0, f"模板缺失时仍应按逐道外协周期继续：{algo_op.ext_days!r}"
