"""Readonly directory summaries never choose a default/latest draft or candidate."""

import hashlib

from core.models.workbench_trial import reference, reject
from core.models.workbench_trial_catalog import MAX_CATALOG_BYTES, MAX_CATALOG_ROWS, TrialCatalogScope
from core.models.workbench_trial_codec import dump
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_policy import require_trial_schema
from data.repositories.workbench_trial_catalog_repo import WorkbenchTrialCatalogRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository


class WorkbenchTrialCatalogService:
    def __init__(self, conn):
        self.conn = conn

    def catalog(self, scope: TrialCatalogScope):
        with candidate_read_snapshot(self.conn):
            require_trial_schema(WorkbenchTrialRepository(self.conn))
            rows, page, fingerprint = _bounded_page(WorkbenchTrialCatalogRepository(self.conn), scope)
            items = [_summary(row, scope.collection) for row in rows]
            return {"items": items, "page": page, "scope": scope.scope(), "state": "available" if items else "empty",
                    "selection": None, "validation_state": "not_evaluated"}, fingerprint


def _bounded_page(repo, scope):
    """One page of header rows plus a digest of the whole directory; refuses directories past the row/byte caps."""
    digest, selected, total, byte_count = hashlib.sha256(), [], 0, 0
    offset = (scope.page - 1) * scope.size
    for row in repo.iter_rows(scope, MAX_CATALOG_ROWS):
        total += 1
        encoded = dump(row).encode("utf-8")
        byte_count += len(encoded)
        if total > MAX_CATALOG_ROWS or byte_count > MAX_CATALOG_BYTES:
            reject("query_too_large", "完整目录超过100000条或32 MiB摘要上限，请用状态或明确来源缩小范围；未截断。", 413)
        digest.update(str(len(encoded)).encode("ascii") + b":" + encoded)
        if offset < total <= offset + scope.size:
            selected.append(row)
    pages = (total + scope.size - 1) // scope.size
    if scope.page > max(pages, 1):
        reject("invalid_input", "目录页码超过当前范围，请明确刷新目录。", 400)
    return selected, {"number": scope.page, "size": scope.size, "total": total, "pages": pages}, digest.hexdigest()


def _source_label(row):
    if row["base_kind"] == "candidate_ref":
        sequence = row["candidate_sequence"]
        if type(sequence) is int and sequence >= 0 and isinstance(row["candidate_accepted_at"], str):
            return "候选方案 " + str(sequence + 1) + "（" + row["candidate_accepted_at"].replace("T", " ")[:16] + "）"
        return "候选方案（来源读不到）"
    version = row["base_version"]
    if type(version) is not int or version <= 0:
        return "计划（来源读不到）"
    label = {"official": "正式计划", "scenario": "试调方案", "selection": "候选方案"}.get(row["base_plan_kind"], "计划")
    return label + " v" + str(version)


def _text(value):
    if type(value) is not str or not value or len(value) > 1000:
        reject("trial_catalog_invalid", "试调列表里这条记录的内容不对，原记录没有改动。请刷新后重试。")
    return value


def _summary(row, collection):
    base_kind, base_ref = row["base_kind"], reference(row["base_ref"])
    if base_kind not in ("plan_ref", "candidate_ref") or type(row["row_count"]) is not int or row["row_count"] <= 0:
        reject("trial_catalog_invalid", "试调列表里这条记录的来源或范围不完整，这里不猜内容。请刷新后重试。")
    source = _source_label(row)
    is_draft = collection == "drafts"
    ref = reference(row["draft_ref"] if is_draft else row["scenario_ref"])
    status = row["status"] if is_draft else "saved"
    title = row["saved_name"] or source + "的试调" if is_draft else row["name"]
    target_key = "draft_ref" if is_draft else "scenario_ref"
    result = {target_key: ref, "display_name": _text(title), "status": status, "base": {base_kind: base_ref},
              "base_display_name": source, "task_count": row["row_count"], "local_operator": _text(row["local_operator"]),
              "created_at": _text(row["created_at"] if is_draft else row["saved_at"]),
              "updated_at": _text(row["updated_at"] if is_draft else row["saved_at"]),
              "open_target": {"kind": "draft" if is_draft else "scenario", target_key: ref},
              "detail_target": "/api/workbench/v1/trial/" + collection + "/" + ref,
              "capabilities": {"view": True, "edit_draft": is_draft and status == "editing", "adopt": False},
              "validation_state": "not_evaluated"}
    if is_draft:
        result["scenario_ref"] = row["scenario_ref"]
    else:
        result["source_draft_ref"] = row["draft_ref"]
    return result
