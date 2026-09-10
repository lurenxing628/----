"""Stream bounded headers, not large admission/scenario JSON or live plan rows."""

import hashlib

from core.models.workbench_trial import reject
from core.models.workbench_trial_catalog import MAX_CATALOG_BYTES, MAX_CATALOG_ROWS
from core.models.workbench_trial_codec import dump
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

_BASE_JOINS = """LEFT JOIN WorkbenchPlanSourceRefs p ON d.base_kind='plan_ref' AND p.ref=d.base_ref
    LEFT JOIN WorkbenchRunCandidates c ON d.base_kind='candidate_ref' AND c.candidate_ref=d.base_ref
    LEFT JOIN WorkbenchRunJobs r ON r.run_ref=c.run_ref"""
_BASE_COLUMNS = """d.draft_ref,d.base_kind,d.base_ref,d.row_count,p.version AS base_version,
    p.kind AS base_plan_kind,c.sequence AS candidate_sequence,r.accepted_at AS candidate_accepted_at"""


class WorkbenchTrialCatalogRepository:
    def __init__(self, conn):
        self.conn = conn

    def catalog(self, scope):
        WorkbenchTrialRepository(self.conn).require_schema()
        sql, params = _query(scope)
        digest, selected, total, byte_count = hashlib.sha256(), [], 0, 0
        offset = (scope.page - 1) * scope.size
        for raw in self.conn.execute(sql + " LIMIT ?", params + [MAX_CATALOG_ROWS + 1]):
            total += 1
            encoded = dump(dict(raw)).encode("utf-8")
            byte_count += len(encoded)
            if total > MAX_CATALOG_ROWS or byte_count > MAX_CATALOG_BYTES:
                reject("query_too_large", "完整目录超过100000条或32 MiB摘要上限，请用状态或明确来源缩小范围；未截断。", 413)
            digest.update(str(len(encoded)).encode("ascii") + b":" + encoded)
            if offset < total <= offset + scope.size:
                selected.append(dict(raw))
        pages = (total + scope.size - 1) // scope.size
        if scope.page > max(pages, 1):
            reject("invalid_input", "目录页码超过当前范围，请明确刷新目录。", 400)
        return selected, {"number": scope.page, "size": scope.size, "total": total, "pages": pages}, digest.hexdigest()


def _query(scope):
    where, params = [], []
    if scope.base_kind is not None:
        where += ["d.base_kind=?", "d.base_ref=?"]
        params += [scope.base_kind, scope.base_ref]
    if scope.collection == "drafts":
        if scope.status != "all":
            where.append("d.status=?")
            params.append(scope.status)
        columns = _BASE_COLUMNS + ",d.status,d.revision,d.created_at,d.updated_at,d.local_operator,d.admission_hash,s.scenario_ref,s.name AS saved_name"
        source = "WorkbenchTrialDrafts d LEFT JOIN WorkbenchTrialScenarios s ON s.draft_ref=d.draft_ref " + _BASE_JOINS
        order = "d.updated_at DESC,d.draft_ref ASC"
    else:
        columns = _BASE_COLUMNS + ",s.scenario_ref,s.name,s.revision,s.saved_at,s.local_operator,s.snapshot_hash"
        source = "WorkbenchTrialScenarios s JOIN WorkbenchTrialDrafts d ON d.draft_ref=s.draft_ref " + _BASE_JOINS
        order = "s.saved_at DESC,s.scenario_ref ASC"
    return "SELECT " + columns + " FROM " + source + " WHERE " + (" AND ".join(where) if where else "1=1") + " ORDER BY " + order, params
