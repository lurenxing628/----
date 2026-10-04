"""Service-side rulings over dashboard storage facts; the repositories only read and write rows."""

import json

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_dashboard import HANDLING_FIELDS, MAX_BYTES, MAX_ROWS, STATUSES, bounded, reference


def corrupt():
    raise WorkbenchCommandRejected("dashboard_storage_invalid", "处置台账或来源身份不完整，请核对存储；本次未自动修补。", 409)


def load_handling(raw):
    try:
        value = json.loads(raw)
        if (type(value) is not dict or set(value) != {"status"} | set(HANDLING_FIELDS)
                or value["status"] not in STATUSES
                or any(value[key] is not None and type(value[key]) is not str for key in HANDLING_FIELDS)):
            corrupt()
        return value
    except (TypeError, ValueError):
        corrupt()


def require_dashboard_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("dashboard_unavailable", "值班台台账未安装或结构不完整，需由主线完成明确迁移；本次没有补表。", 503)


def require_external_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("dashboard_external_unavailable", "外协处置台账未安装或结构不完整，需由主线明确迁移；未补表。", 503)


def mapped_anchors(loaded, refs):
    """loaded 是读快照里按候选来源读出的映射；这次真正评估到的来源必须每条都有映射。"""
    result = {ref: loaded[ref] for ref in refs if ref in loaded}
    if set(result) != set(refs):
        corrupt()
    return result


def read_receipt_mappings(repo, refs):
    result = {row["outsourcing_ref"]: row for row in bounded(repo.external_items(MAX_ROWS))}
    if set(result) != set(refs):
        corrupt()
    if repo.shares_item_ref_with_dashboard_items():
        corrupt()
    return result


def read_stored(repo):
    """Decode and cross-check every stored handling state against its history tail and receipt."""
    bounded(range(repo.stored_bytes()), MAX_BYTES)
    result = bounded(repo.stored_rows(MAX_ROWS))
    for row in result:
        row["handling"] = load_handling(row.pop("handling_json"))
        row["origin"] = json.loads(row.pop("origin_json"))
    by_ref = {row["item_ref"]: row for row in repo.state_tails()}
    for row in result:
        tail = by_ref.get(row["item_ref"])
        if (tail is None or tail["receipt_ref"] is None or tail["count"] != row["revision"] or load_handling(tail["after_json"]) != row["handling"]
                or row["origin"].get("item_ref") != row["item_ref"] or row["origin"].get("category") != row["category"]):
            corrupt()
    return {row["item_ref"]: row for row in result}


def read_external_stored(repo):
    stored = read_stored(repo)
    for row in stored.values():
        source = row["origin"].get("source", {})
        members = repo.outsourcing_member_refs(row["outsourcing_ref"])
        if source.get("outsourcing_ref") != row["outsourcing_ref"] or source.get("operation_refs") != members or not members:
            corrupt()
    return stored


def require_identity(repo, item_ref):
    return found_identity(repo.identity(reference(item_ref)))


def found_identity(row):
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "条目不存在，未改指其他来源。", 404)
    return row


def read_history(repo, item_ref, number, size):
    total = repo.history_count(item_ref)
    pages = max(1, (total + size - 1) // size)
    if number > pages:
        raise WorkbenchCommandRejected("invalid_input", "历史页码超过范围。", 400)
    public = []
    for row in repo.history_rows(item_ref, size, (number - 1) * size):
        if row["receipt_ref"] is None or input_fingerprint(json.loads(row["source_facts_json"])) != row["source_hash"]:
            corrupt()
        public.append({"history_ref": row["history_ref"], "sequence": row["sequence"], "action": row["action"],
                       "before": load_handling(row["before_json"]), "after": load_handling(row["after_json"]),
                       "reason": row["reason"], "local_operator": row["local_operator"], "recorded_at": row["recorded_at"],
                       "receipt_ref": row["receipt_ref"], "source_snapshot": {
                           "snapshot_ref": row["history_ref"], "as_of": row["recorded_at"],
                           "time_basis": "factory_local", "source": json.loads(row["source_json"])}})
    return {"items": public, "page": {"number": number, "size": size, "total": total, "pages": pages,
                                       "sort": [{"field": "sequence", "direction": "desc"}]}}


def read_entity_refs(repo, kind, keys):
    result = {}
    for row in repo.entity_ref_rows(kind, keys):
        if row["entity_key"] in result:
            raise WorkbenchCommandRejected("identity_missing", "来源关联资料重复，暂时无法评估，请联系维护人员核对。")
        result[row["entity_key"]] = row
    if set(result) != set(keys):
        raise WorkbenchCommandRejected("identity_missing", "来源关联资料缺失，暂时无法评估，请联系维护人员核对。")
    return result
