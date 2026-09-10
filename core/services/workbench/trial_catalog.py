"""Readonly directory summaries never choose a default/latest draft or candidate."""

from core.models.workbench_trial import reference, reject
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench.run_input_readonly import candidate_read_snapshot
from data.repositories.workbench_trial_catalog_repo import WorkbenchTrialCatalogRepository


class WorkbenchTrialCatalogService:
    def __init__(self, conn):
        self.conn = conn

    def catalog(self, scope: TrialCatalogScope):
        with candidate_read_snapshot(self.conn):
            rows, page, fingerprint = WorkbenchTrialCatalogRepository(self.conn).catalog(scope)
            items = [_summary(row, scope.collection) for row in rows]
            return {"items": items, "page": page, "scope": scope.scope(), "state": "available" if items else "empty",
                    "selection": None, "validation_state": "not_evaluated"}, fingerprint


def _source_label(row):
    if row["base_kind"] == "candidate_ref":
        sequence = row["candidate_sequence"]
        if type(sequence) is int and sequence >= 0 and isinstance(row["candidate_accepted_at"], str):
            return "排产候选 " + str(sequence + 1) + "（" + row["candidate_accepted_at"] + "）"
        return "原排产候选（来源暂不可读）"
    version = row["base_version"]
    if type(version) is not int or version <= 0:
        return "原计划（来源暂不可读）"
    label = {"official": "正式计划", "scenario": "原场景", "selection": "代表方案"}.get(row["base_plan_kind"], "原计划")
    return label + " v" + str(version)


def _text(value):
    if type(value) is not str or not value or len(value) > 1000:
        reject("trial_catalog_invalid", "持久目录摘要字段无效；原记录未被替换。")
    return value


def _summary(row, collection):
    base_kind, base_ref = row["base_kind"], reference(row["base_ref"])
    if base_kind not in ("plan_ref", "candidate_ref") or type(row["row_count"]) is not int or row["row_count"] <= 0:
        reject("trial_catalog_invalid", "持久目录的来源或原范围不完整，未猜测内容。")
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
