from __future__ import annotations

from types import SimpleNamespace

from web.routes.scheduler_batch_detail import _build_view_ops


class _Model(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


class _FastMergeHintService:
    def __init__(self, calls):
        self._calls = calls

    def get_external_merge_hint_for_op(self, op):
        self._calls["fast"] += 1
        return {
            "is_external": True,
            "template_ext_group_id": f"G_{op.id}",
            "merge_mode": "merged",
            "group_total_days": 3.0,
        }

    def get_external_merge_hint(self, op_id):
        self._calls["slow"] += 1
        return {
            "is_external": True,
            "template_ext_group_id": f"SLOW_{op_id}",
            "merge_mode": "merged",
            "group_total_days": 9.0,
        }


class _FallbackMergeHintService:
    def __init__(self, calls):
        self._calls = calls

    def get_external_merge_hint(self, op_id):
        self._calls["slow"] += 1
        return {
            "is_external": True,
            "template_ext_group_id": f"G_{op_id}",
            "merge_mode": None,
        }


def test_build_view_ops_uses_fast_merge_hint_path_for_external_ops_only() -> None:
    calls = {"fast": 0, "slow": 0}
    service = _FastMergeHintService(calls)

    ops = [
        _Model(id=1, batch_id="B001", source="internal", machine_id="M1", operator_id="O1"),
        _Model(id=2, batch_id="B001", source="external", supplier_id="S1", ext_days=2.0),
    ]

    view_ops = _build_view_ops(ops, service)

    assert calls == {"fast": 1, "slow": 0}
    assert view_ops[0]["merge_hint"] == {"is_external": False}
    assert view_ops[1]["merge_hint"]["template_ext_group_id"] == "G_2"
    assert view_ops[1]["merge_hint"]["merge_mode"] == "merged"


def test_build_view_ops_fallback_path_skips_internal_query() -> None:
    calls = {"slow": 0}
    service = _FallbackMergeHintService(calls)

    ops = [
        _Model(id=11, batch_id="B002", source="internal", machine_id="M1", operator_id="O1"),
        _Model(id=12, batch_id="B002", source="external", supplier_id="S2", ext_days=1.0),
    ]

    view_ops = _build_view_ops(ops, service)

    assert calls == {"slow": 1}
    assert view_ops[0]["merge_hint"] == {"is_external": False}
    assert view_ops[1]["merge_hint"]["template_ext_group_id"] == "G_12"
