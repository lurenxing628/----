from __future__ import annotations

import inspect
from types import SimpleNamespace

import web.routes.scheduler_excel_batches as route_mod


class _ListStub:
    def __init__(self, rows):
        self._rows = list(rows)
        self.calls = []

    def list(self):
        self.calls.append("list")
        return list(self._rows)


class _PartServiceStub(_ListStub):
    def __init__(self, rows, *, route_parse_snapshot=None):
        super().__init__(rows)
        self.route_parse_snapshot = list(route_parse_snapshot or [])
        self.route_parse_calls = []

    def build_route_parse_baseline_snapshot(self, *, part_nos, parts_cache=None):
        cache_keys = sorted(list((parts_cache or {}).keys())) if isinstance(parts_cache, dict) else []
        self.route_parse_calls.append({"part_nos": list(part_nos), "parts_cache_keys": cache_keys})
        return list(self.route_parse_snapshot)


class _TemplateQueryStub:
    def __init__(self, result):
        self.result = list(result)
        self.calls = []

    def list_template_snapshot_for_parts(self, part_nos):
        self.calls.append(list(part_nos))
        return list(self.result)


def test_scheduler_excel_batches_helper_signatures_are_service_injected() -> None:
    parts_cache_sig = inspect.signature(route_mod._build_parts_cache)
    template_sig = inspect.signature(route_mod._build_template_ops_snapshot)
    baseline_sig = inspect.signature(route_mod._batch_baseline_extra_state)

    assert list(parts_cache_sig.parameters) == ["part_svc"]
    assert list(template_sig.parameters) == ["part_operation_query_svc", "rows"]
    assert list(baseline_sig.parameters) == [
        "part_svc",
        "part_operation_query_svc",
        "parts_cache",
        "auto_generate_ops",
        "strict_mode",
        "rows",
    ]
    assert "conn" not in baseline_sig.parameters


def test_scheduler_excel_batches_baseline_only_tracks_uploaded_parts() -> None:
    part_rows = [
        SimpleNamespace(part_no="P1", part_name="零件1", route_raw="10车削"),
        SimpleNamespace(part_no="P2", part_name="零件2", route_raw="20磨削"),
    ]
    part_svc = _PartServiceStub(part_rows)
    query_svc = _TemplateQueryStub([{"part_no": "P1", "seq": 10}])

    parts_cache = route_mod._build_parts_cache(part_svc)
    baseline = route_mod._batch_baseline_extra_state(
        part_svc=part_svc,
        part_operation_query_svc=query_svc,
        parts_cache=parts_cache,
        auto_generate_ops=True,
        strict_mode=True,
        rows=[{"图号": "P1"}],
    )

    assert part_svc.calls == ["list"]
    assert baseline["strict_mode"] is True
    assert baseline["parts_snapshot"] == [{"part_no": "P1", "part_name": "零件1"}]
    assert baseline["template_ops_snapshot"] == [{"part_no": "P1", "seq": 10}]
    assert baseline["autobuild_parts_snapshot"] == []
    assert baseline["autobuild_route_parse_snapshot"] == []
    assert query_svc.calls == [["P1"]]
    assert part_svc.route_parse_calls == []


def test_scheduler_excel_batches_baseline_delegates_autobuild_route_snapshot_to_part_service() -> None:
    part_rows = [
        SimpleNamespace(part_no="P1", part_name="零件1", route_raw="10表处理"),
        SimpleNamespace(part_no="P2", part_name="零件2", route_raw="20磨削"),
    ]
    route_snapshot = [
        {
            "part_no": "P1",
            "route_op_types": [{"name": "表处理", "matched_op_type_id": "OT_EXT", "source": "external"}],
            "suppliers": [
                {
                    "supplier_id": "SUP1",
                    "op_type_id": "OT_EXT",
                    "op_type_name": "表处理",
                    "default_days": 2.0,
                }
            ],
        }
    ]
    part_svc = _PartServiceStub(part_rows, route_parse_snapshot=route_snapshot)
    query_svc = _TemplateQueryStub([])

    parts_cache = route_mod._build_parts_cache(part_svc)
    baseline = route_mod._batch_baseline_extra_state(
        part_svc=part_svc,
        part_operation_query_svc=query_svc,
        parts_cache=parts_cache,
        auto_generate_ops=True,
        strict_mode=False,
        rows=[{"图号": "P1"}],
    )

    assert baseline["parts_snapshot"] == [{"part_no": "P1", "part_name": "零件1"}]
    assert baseline["template_ops_snapshot"] == []
    assert baseline["autobuild_parts_snapshot"] == [{"part_no": "P1", "route_raw": "10表处理"}]
    assert baseline["autobuild_route_parse_snapshot"] == route_snapshot
    assert query_svc.calls == [["P1"]]
    assert part_svc.route_parse_calls == [{"part_nos": ["P1"], "parts_cache_keys": ["P1", "P2"]}]


def test_scheduler_excel_batches_baseline_skips_autobuild_snapshot_when_auto_generate_disabled() -> None:
    part_svc = _PartServiceStub([SimpleNamespace(part_no="P1", part_name="零件1", route_raw="10车削")])
    query_svc = _TemplateQueryStub([{"part_no": "P1", "seq": 10}])

    baseline = route_mod._batch_baseline_extra_state(
        part_svc=part_svc,
        part_operation_query_svc=query_svc,
        parts_cache={"P1": SimpleNamespace(part_name="零件1", route_raw="10车削")},
        auto_generate_ops=False,
        strict_mode=False,
        rows=[{"图号": "P1"}],
    )

    assert baseline["parts_snapshot"] == [{"part_no": "P1", "part_name": "零件1"}]
    assert baseline["template_ops_snapshot"] == []
    assert baseline["autobuild_parts_snapshot"] == []
    assert baseline["autobuild_route_parse_snapshot"] == []
    assert query_svc.calls == []
    assert part_svc.route_parse_calls == []
