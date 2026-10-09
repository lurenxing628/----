"""Read full sample plans through the existing bounded public time-range API."""
from datetime import datetime, timedelta
from urllib.parse import urlencode

from core.models.workbench_command import canonical_json

from .sample_constraint_checks import require
from .sample_http import BASE, SampleAPIError


def _too_large(error):
    return error.status == 413 and error.body.get("error", {}).get("code") == "query_too_large"


def _segment(client, path, low, high, rejected):
    query = {"range_start": low.isoformat(), "range_end": high.isoformat()}
    scoped_path = path + "?" + urlencode(query)
    try:
        document = client.document(scoped_path)
    except SampleAPIError as error:
        if not _too_large(error):
            raise
        rejected.append({"path": scoped_path, "status": error.status, "response": error.body})
        middle = low + (high - low) / 2
        require(low < middle < high, "正式计划的最小时间范围仍超过公共接口上限，无法完整读取；保留413失败。")
        return (_segment(client, path, low, middle, rejected)
                + _segment(client, path, middle, high, rejected))
    _require_segment(document, query, low, high)
    return [document]


def _require_segment(document, query, low, high):
    data = document["data"]
    require(data["scope"] == dict(query, source="production", kind="plan_workspace", plan_ref=data["plan"]["plan_ref"])
            and data["time_scope"] == dict(query, selection="overlap", boundary="half_open", time_basis="factory_local"),
            "正式计划分段响应的真实读取范围对不上请求。")
    rows = data["tasks"]
    require(data["tasks_complete"] is True and data["task_count"] == len(rows)
            and len({row["task_ref"] for row in rows}) == len(rows),
            "正式计划分段响应没有返回完整的本段工序、唯一身份或条数不符。")
    require(all(_in_segment(row, data["plan"]["plan_ref"], low, high) for row in rows),
            "正式计划分段包含其他计划或时间范围外的工序。")
    require(document["meta"]["source"] == "production" and bool(document["meta"]["snapshot_ref"])
            and bool(document["meta"]["as_of"]), "正式计划分段缺少原公共接口快照。")


def _in_segment(row, plan_ref, low, high):
    start, end = datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["end"])
    overlap = low <= start < high if start == end else start < high and end > low
    return row["plan_ref"] == plan_ref and start <= end and overlap


def _union(documents, field, identity):
    indexed = {}
    for document in documents:
        for row in document["data"][field]:
            key = identity(row)
            previous = indexed.setdefault(key, row)
            require(previous == row, "正式计划分段之间同一工序或资源内容发生变化，不能拼成完整结果。")
    return list(indexed.values())


def _assembled(plan_ref, expected, documents, rejected, low, high):
    plan, span = documents[0]["data"]["plan"], documents[0]["data"]["plan_span"]
    require(plan["plan_ref"] == plan_ref and all(document["data"]["plan"] == plan
            and document["data"]["plan_span"] == span for document in documents),
            "正式计划分段的版本、身份或完整计划时间范围发生变化。")
    require(datetime.fromisoformat(span["start"]) == low
            and datetime.fromisoformat(span["end"]) == max(datetime.fromisoformat(row["end"]) for row in expected),
            "正式计划完整时间范围与候选不一致，不能只验收其中一段。")
    tasks = _union(documents, "tasks", lambda row: row["task_ref"])
    resources = _union(documents, "resources", lambda row: (row["kind"], row["ref"]))
    reads = [{"scope": document["data"]["scope"], "task_count": document["data"]["task_count"],
              "canonical_bytes": len(canonical_json(document).encode("utf-8")),
              "snapshot_ref": document["meta"]["snapshot_ref"], "as_of": document["meta"]["as_of"]}
             for document in documents]
    return {"ok": True, "schema_version": 1,
            "data": {"plan": plan, "tasks": tasks, "task_count": len(tasks), "tasks_complete": True,
                     "resources": resources, "scope": {"kind": "sample_assembled_plan_workspace", "plan_ref": plan_ref},
                     "plan_span": span, "projections": {"kind": "segmented_http", "source": "assembly.segments[].data.projections"}},
            "meta": {"source": "production", "snapshot_ref": None, "as_of": None},
            "assembly": {"kind": "segmented_http", "segments": documents, "reads": reads, "rejected_scopes": rejected,
                         "requested_span": {"range_start": low.isoformat(), "range_end": high.isoformat()},
                         "unique_task_count": len(tasks), "segment_count": len(documents),
                         "duplicate_overlap_count": sum(row["task_count"] for row in reads) - len(tasks),
                         "resource_scope": "union_of_segment_identity_directories_without_global_metrics",
                         "snapshot_rule": "Each original snapshot belongs only to its exact segment scope; no global snapshot was issued."}}


def read_formal(client, plan_ref, expected):
    path = BASE + "/plans/" + plan_ref + "/workspace"
    try:
        return client.document(path)
    except SampleAPIError as error:
        if not _too_large(error):
            raise
        rejected = [{"path": path, "status": error.status, "response": error.body}]
    low = min(datetime.fromisoformat(row["start"]) for row in expected)
    high = max(datetime.fromisoformat(row["end"]) for row in expected) + timedelta(microseconds=1)
    documents = _segment(client, path, low, high, rejected)
    return _assembled(plan_ref, expected, documents, rejected, low, high)
