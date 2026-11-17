"""Service-side rulings over dashboard storage facts; the repository only reads and writes rows."""

from core.models.content import read_stored_json
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_ROWS, bounded, reference


def mapped_anchors(loaded, refs):
    """loaded 是读快照里按候选来源读出的映射；这次真正评估到的来源必须每条都有映射。"""
    result = {ref: loaded[ref] for ref in refs if ref in loaded}
    if set(result) != set(refs):
        raise WorkbenchCommandRejected("identity_missing", "值班台条目关联缺失，请联系维护人员核对。")
    return result


def read_receipt_mappings(repo, refs):
    loaded = {row["outsourcing_ref"]: row for row in bounded(repo.external_items(MAX_ROWS))}
    return mapped_anchors(loaded, refs)


def read_stored(repo):
    """Decode every stored handling state."""
    result, identities, count = {}, {}, 0
    for row in repo.stored_rows(MAX_ROWS):
        count += 1
        bounded(range(count), MAX_ROWS)
        identity = row.pop("_identity")
        row["handling"] = read_stored_json(row.pop("handling_json"), dict)
        row["origin"] = read_stored_json(row.pop("origin_json"), dict)
        result[row["item_ref"]] = row
        identities[row["item_ref"]] = identity
    return result, identities


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
        before, after = read_stored_json(row["before_json"], dict), read_stored_json(row["after_json"], dict)
        source = read_stored_json(row["source_json"], dict)
        public.append(
            {
                "history_ref": row["history_ref"],
                "sequence": row["sequence"],
                "action": row["action"],
                "before": before,
                "after": after,
                "reason": row["reason"],
                "local_operator": row["local_operator"],
                "recorded_at": row["recorded_at"],
                "receipt_ref": row["receipt_ref"],
                "source_snapshot": {
                    "snapshot_ref": row["history_ref"],
                    "as_of": row["recorded_at"],
                    "time_basis": "factory_local",
                    "source": source,
                },
            }
        )
    return {
        "items": public,
        "page": {
            "number": number,
            "size": size,
            "total": total,
            "pages": pages,
            "sort": [{"field": "sequence", "direction": "desc"}],
        },
    }

