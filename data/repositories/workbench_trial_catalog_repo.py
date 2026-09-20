"""Stream bounded headers, not large admission/scenario JSON or live plan rows. Limits are decided by the caller."""

_BASE_JOINS = """LEFT JOIN WorkbenchPlanSourceRefs p ON d.base_kind='plan_ref' AND p.ref=d.base_ref
    LEFT JOIN WorkbenchRunCandidates c ON d.base_kind='candidate_ref' AND c.candidate_ref=d.base_ref
    LEFT JOIN WorkbenchRunJobs r ON r.run_ref=c.run_ref"""
_BASE_COLUMNS = """d.draft_ref,d.base_kind,d.base_ref,d.row_count,p.version AS base_version,
    p.kind AS base_plan_kind,c.sequence AS candidate_sequence,r.accepted_at AS candidate_accepted_at"""


class WorkbenchTrialCatalogRepository:
    def __init__(self, conn):
        self.conn = conn

    def iter_rows(self, scope, limit):
        """Yield catalog header rows for `scope` in directory order, at most `limit + 1` of them.

        Rows are streamed from the cursor so the caller can stop (and refuse the whole directory)
        the moment its row or byte cap is exceeded, without materialising the excess."""
        sql, params = _query(scope)
        for raw in self.conn.execute(sql + " LIMIT ?", params + [limit + 1]):
            yield dict(raw)


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
