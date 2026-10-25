"""Service-side rulings over dashboard storage facts; the repositories only read and write rows."""

import json

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import HANDLING_FIELDS, MAX_BYTES, MAX_ROWS, STATUSES, bounded, reference


def corrupt():
    raise WorkbenchCommandRejected("dashboard_storage_invalid", "处置记录或关联记录不完整，请联系维护人员核对。", 409)


def _load_object(raw):
    """存储边界只解码一次：不是合法 JSON 对象就按存储损坏拒绝。"""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        corrupt()
    if type(value) is not dict:
        corrupt()
    return value


def load_handling(raw):
    value = _load_object(raw)
    if (set(value) != {"status"} | set(HANDLING_FIELDS) or value["status"] not in STATUSES
            or any(value[key] is not None and type(value[key]) is not str for key in HANDLING_FIELDS)):
        corrupt()
    return value


def require_dashboard_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("dashboard_unavailable", "值班台所需数据未准备完整，请联系维护人员处理。", 503)


def require_external_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("dashboard_external_unavailable", "外协处置所需数据未准备完整，请联系维护人员处理。", 503)


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
    result, identities, size, count = {}, {}, 0, 0
    for row in repo.stored_rows(MAX_ROWS):
        count += 1
        bounded(range(count), MAX_ROWS)
        size += row.pop("_stored_body_bytes")
        bounded(range(size), MAX_BYTES)
        identity = row.pop("_identity")
        tail_after, receipt = row.pop("_tail_after_json"), row.pop("_receipt_ref")
        row["handling"] = load_handling(row.pop("handling_json"))
        row["origin"] = _load_object(row.pop("origin_json"))
        if (receipt is None or load_handling(tail_after) != row["handling"]
                or row["origin"].get("item_ref") != row["item_ref"] or row["origin"].get("category") != row["category"]
                or type(row["origin"].get("source")) is not dict):
            corrupt()
        result[row["item_ref"]] = row
        identities[row["item_ref"]] = identity
    return result, identities


def read_external_stored(repo, receipts):
    stored, identities = read_stored(repo)
    for ref, row in stored.items():
        source = row["origin"]["source"]
        outsourcing_ref = identities[ref]["outsourcing_ref"]
        captured = receipts.get(outsourcing_ref)
        members = captured["header"]["target"]["operation_refs"] if captured is not None else []
        if source.get("outsourcing_ref") != outsourcing_ref or source.get("operation_refs") != members or not members:
            corrupt()
    return stored, identities


def require_identity(repo, item_ref):
    if not repo.has_item(reference(item_ref)):
        raise WorkbenchCommandRejected("entity_not_found", "这条处置记录已失效，请刷新后重新选择。", 404)


def read_history(repo, item_ref, number, size):
    total = repo.history_count(item_ref)
    pages = max(1, (total + size - 1) // size)
    if number > pages:
        raise WorkbenchCommandRejected("invalid_input", "历史页码超过范围。", 400)
    public = []
    for row in repo.history_rows(item_ref, size, (number - 1) * size):
        source, before, after = history_contents(row)
        public.append({"history_ref": row["history_ref"], "sequence": row["sequence"], "action": row["action"],
                       "before": before, "after": after,
                       "reason": row["reason"], "local_operator": row["local_operator"], "recorded_at": row["recorded_at"],
                       "receipt_ref": row["receipt_ref"], "source_snapshot": {
                           "snapshot_ref": row["history_ref"], "as_of": row["recorded_at"],
                           "time_basis": "factory_local", "source": source}})
    return {"items": public, "page": {"number": number, "size": size, "total": total, "pages": pages,
                                       "sort": [{"field": "sequence", "direction": "desc"}]}}


def history_contents(row):
    """Bind archived source/guard contents to the original command outcome and history identity."""
    before, after = load_handling(row["before_json"]), load_handling(row["after_json"])
    source = _load_object(row["source_json"])
    facts = _load_object(row["source_facts_json"])
    outcome = _load_object(row["receipt_outcome_json"])
    if (set(facts) != {"facts", "guard"} or type(facts["facts"]) is not dict or type(facts["guard"]) is not dict
            or type(outcome.get("data")) is not dict):
        corrupt()
    guard, data = facts["guard"], outcome["data"]
    identity = guard.get("identity")
    if (row["receipt_ref"] is None or row["receipt_action"] != "dashboard." + row["action"]
            or row["receipt_context_ref"] != row["item_ref"] or outcome.get("result") != "committed"
            or data.get("history_ref") != row["history_ref"] or data.get("item_ref") != row["item_ref"]
            or source.get("item_ref") != row["item_ref"] or type(identity) is not dict
            or identity.get("item_ref") != row["item_ref"] or identity.get("category") != source.get("category")
            or not same(guard.get("revision"), row["sequence"] - 1)
            or not same(data.get("handling"), after) or not same(guard.get("handling"), before)
            or not same(data.get("source"), source.get("source")) or not same(guard.get("source"), source.get("source"))
            or not same(data.get("risk"), source.get("risk")) or not same(guard.get("risk"), source.get("risk"))):
        corrupt()
    return source, before, after


def entity_refs_from_rows(rows, keys):
    result = {}
    for row in rows:
        if row["entity_key"] in result:
            raise WorkbenchCommandRejected("identity_missing", "来源关联资料重复，暂时无法评估，请联系维护人员核对。")
        result[row["entity_key"]] = row
    if set(result) != set(keys):
        raise WorkbenchCommandRejected("identity_missing", "来源关联资料缺失，暂时无法评估，请联系维护人员核对。")
    return result
