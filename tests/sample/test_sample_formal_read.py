"""Bounded public HTTP scopes preserve full plan rows, points and segment snapshots."""
import copy
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from web.bootstrap.sample_exercise import _formal
from web.bootstrap.sample_http import SampleAPIError

PLAN = "a" * 48


def candidate_rows():
    periods = (("00:00:00", "04:00:00"), ("00:00:00", "01:00:00"),
               ("03:00:00", "04:00:00"), ("04:00:00", "04:00:00"))
    return [{"operation_ref": str(index) * 48, "start": "2026-10-10T" + start,
             "end": "2026-10-10T" + end, "machine": {"ref": "m" * 48}, "operator": {"ref": "o" * 48},
             "supplier": None, "batch_label": "batch-1", "sequence": index, "process_label": "process",
             "quantity": 3, "batch_quantity": 3, "piece_id": None}
            for index, (start, end) in enumerate(periods, 1)]


class BoundedClient:
    def __init__(self, *, fault=None, whole=False):
        self.expected = candidate_rows()
        self.rows = [dict(operation_ref=row["operation_ref"], task_ref=str(index + 4) * 48,
                         plan_ref=PLAN, start=row["start"], end=row["end"], machine_ref="m" * 48,
                         operator_ref="o" * 48, supplier_ref=None, batch_id=row["batch_label"],
                         **{key: row[key] for key in ("sequence", "process_label", "quantity", "batch_quantity", "piece_id")})
                     for index, row in enumerate(self.expected, 1)]
        self.fault, self.whole, self.calls = fault, whole, []

    def document(self, path):
        self.calls.append(path)
        query = {key: values[0] for key, values in parse_qs(urlsplit(path).query).items()}
        if not query and not self.whole:
            raise SampleAPIError(path, 413, {"ok": False, "error": {"code": "query_too_large"}})
        if query:
            low, high = (datetime.fromisoformat(query[key]) for key in ("range_start", "range_end"))
            rows = [row for row in self.rows if (low <= datetime.fromisoformat(row["start"]) < high
                    if row["start"] == row["end"] else datetime.fromisoformat(row["start"]) < high
                    and datetime.fromisoformat(row["end"]) > low)]
        else:
            rows = self.rows
        if len(rows) > 3 and not self.whole:
            raise SampleAPIError(path, 413, {"ok": False, "error": {"code": "query_too_large"}})
        span = {"start": self.expected[0]["start"], "end": self.expected[-1]["end"], "end_inclusive": True}
        scope = dict(source="production", kind="plan_workspace", plan_ref=PLAN,
                     range_start=query.get("range_start"), range_end=query.get("range_end"))
        time_scope = dict(range_start=query.get("range_start", span["start"]),
                          range_end=query.get("range_end", span["end"]),
                          selection="overlap", boundary="half_open", time_basis="factory_local")
        document = {"ok": True, "schema_version": 1,
                    "data": {"plan": {"plan_ref": PLAN, "kind": "official", "version": 1,
                                      "is_current_official": True}, "plan_span": span,
                             "tasks": copy.deepcopy(rows), "task_count": len(rows), "tasks_complete": True,
                             "scope": scope, "time_scope": time_scope,
                             "resources": [{"kind": "machine", "ref": "m" * 48, "label": "machine"}],
                             "projections": {"delivery_risks": {"scope": copy.deepcopy(scope), "items": []},
                                             "occupancy": {"scope": copy.deepcopy(scope), "busy_hours": len(rows)}}},
                    "meta": {"source": "production", "as_of": "2026-10-10T12:00:00",
                             "snapshot_ref": "only-this-scope-" + str(len(self.calls))}}
        if self.fault is not None:
            self.fault(document)
        return document


def test_range_assembly_keeps_point_overlap_rows_and_individual_snapshots():
    client = BoundedClient()
    result = _formal(client, PLAN, client.expected)
    assembly = result["assembly"]
    assert result["meta"]["snapshot_ref"] is result["meta"]["as_of"] is None
    assert result["data"]["task_count"] == assembly["unique_task_count"] == 4
    assert assembly["segment_count"] == 2 and assembly["duplicate_overlap_count"] == 1
    assert len({row["operation_ref"] for row in result["data"]["tasks"]}) == 4
    assert result["data"]["tasks"][-1]["start"] == result["data"]["tasks"][-1]["end"]
    assert len(assembly["rejected_scopes"]) == 2
    assert len({item["meta"]["snapshot_ref"] for item in assembly["segments"]}) == 2
    for item, read in zip(assembly["segments"], assembly["reads"]):
        assert item["data"]["scope"] == read["scope"]
        assert item["meta"]["snapshot_ref"] == read["snapshot_ref"]
        assert read["canonical_bytes"] > 0
        assert item["data"]["projections"]["occupancy"]["busy_hours"] == len(item["data"]["tasks"])
    assert result["data"]["projections"]["kind"] == "segmented_http"
    assert "delivery_risks" not in result["data"]["projections"]


def test_small_single_response_stays_a_real_single_snapshot():
    client = BoundedClient(whole=True)
    result = _formal(client, PLAN, client.expected)
    assert len(client.calls) == 1
    assert "assembly" not in result
    assert result["meta"]["snapshot_ref"] is not None


@pytest.mark.parametrize("fault,reason", [
    (lambda document: document["data"]["scope"].update(range_end="2026-10-11T00:00:00"), "范围对不上"),
    (lambda document: document["data"].update(task_count=999), "条数不符"),
    (lambda document: document["meta"].update(snapshot_ref=None), "公共接口快照"),
    (lambda document: document["data"]["plan"].update(plan_ref="b" * 48), "范围对不上"),
])
def test_segment_contract_mismatch_is_not_assembled(fault, reason):
    client = BoundedClient(fault=fault)
    with pytest.raises(RuntimeError, match=reason):
        _formal(client, PLAN, client.expected)


def test_plan_version_change_between_ranges_is_rejected():
    def change(document):
        if document["data"]["scope"]["range_start"] > "2026-10-10T00:00:00":
            document["data"]["plan"]["version"] = 2
    client = BoundedClient(fault=change)
    with pytest.raises(RuntimeError, match="版本、身份"):
        _formal(client, PLAN, client.expected)


def test_boundary_rows_must_keep_full_task_times():
    def clip(document):
        low = document["data"]["scope"]["range_start"]
        for row in document["data"]["tasks"]:
            row["start"] = max(row["start"], low)
    client = BoundedClient(fault=clip)
    with pytest.raises(RuntimeError, match="同一工序或资源内容发生变化"):
        _formal(client, PLAN, client.expected)


def test_duplicate_in_one_segment_and_missing_operation_do_not_pass():
    def duplicate(document):
        document["data"]["tasks"].append(copy.deepcopy(document["data"]["tasks"][0]))
        document["data"]["task_count"] += 1
    client = BoundedClient(fault=duplicate)
    with pytest.raises(RuntimeError, match="唯一身份"):
        _formal(client, PLAN, client.expected)
    client = BoundedClient()
    client.rows = client.rows[:-1]
    with pytest.raises(RuntimeError, match="重复或遗漏"):
        _formal(client, PLAN, client.expected)


def test_non_capacity_http_error_is_not_retried_or_split():
    class StaleClient:
        calls = 0

        def document(self, path):
            self.calls += 1
            raise SampleAPIError(path, 409, {"ok": False, "error": {"code": "snapshot_stale"}})
    client = StaleClient()
    with pytest.raises(SampleAPIError) as error:
        _formal(client, PLAN, candidate_rows())
    assert error.value.status == 409 and client.calls == 1


def test_unchanged_times_do_not_hide_wrong_quantity_or_batch_assignment():
    for field, value in (("quantity", 99), ("batch_id", "other-batch"), ("supplier_ref", "unexpected-supplier")):
        client = BoundedClient(whole=True)
        client.rows[0][field] = value
        with pytest.raises(RuntimeError, match="改动、重复或遗漏"):
            _formal(client, PLAN, client.expected)
