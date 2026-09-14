"""Read only the original candidate's persisted adoption receipts and audits."""

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_run_adoption import ADOPT_ACTION
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference, reject
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .plan_adoption_baseline import read_adoption_baseline
from .plan_adoption_baseline_values import REASONS, AdoptionBaselineUnavailable
from .run_candidate_storage import CandidateStore
from .run_candidate_values import bounded_size


def _invalid():
    reject("candidate_adoption_history_invalid", "这个候选方案的采用结果和它的来源或正式计划对不上，没有改去查别的采用记录。请到「排产记录」重新选择。", 500)


def _adoption_evidence(conn, row, plan, candidate_ref, run_ref):
    histories = list(conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (plan["version"],)))
    issues, facts, audit = [], {}, None
    try:
        if len(histories) != 1:
            raise AdoptionBaselineUnavailable("adoption_evidence_missing", "ScheduleHistory")
        read_adoption_baseline(conn, plan_ref=plan["plan_ref"], version=plan["version"],
                               history={"result_summary": histories[0][0]}, facts=facts)
    except AdoptionBaselineUnavailable as exc:
        if exc.code != "no_adoption_baseline":
            issues.append({"code": exc.code, "message": REASONS[exc.code]})
    if facts.get("adoption"):
        recorded = facts["adoption"]
        audit = recorded["audit"]
        if (recorded["basis"] != "candidate_adoption" or audit["candidate_ref"] != candidate_ref
                or audit["run_ref"] != run_ref or audit["request_key"] != row["request_key"]
                or recorded["receipt"]["receipt_ref"] != row["receipt_ref"]):
            _invalid()
    elif not issues:
        _invalid()
    return audit, issues


def _entry(conn, row, candidate_ref, run_ref):
    receipt = WorkbenchCommandRepository.public_result(row, replayed=True)
    data = receipt["data"]
    if (receipt["result"] != "committed" or data["candidate_ref"] != candidate_ref or data["run_ref"] != run_ref
            or data["official_plan"]["source_run_ref"] != run_ref):
        _invalid()
    plan = data["official_plan"]
    reference(plan["plan_ref"], stored=True)
    if type(plan["version"]) is not int or plan["version"] < 1 or plan["kind"] != "official":
        _invalid()
    audit, issues = _adoption_evidence(conn, row, plan, candidate_ref, run_ref)
    try:
        if WorkbenchPlanIdentityRepository(conn).resolve_plan(plan["plan_ref"]) != WorkbenchPlanLocator(plan["version"], "adopted"):
            _invalid()
    except WorkbenchPlanReferenceError:
        issues.append({"code": "official_identity_unavailable", "message": "原来采用的那一版计划编号已经失效，结果记录照样保留，系统没有替你打开别的版本。请到计划列表重新选择。"})
    fields = ("reason", "declared_operator", "application_operator", "adopted_at", "baseline_ref", "baseline_version")
    return {"receipt_ref": row["receipt_ref"], "request_key": row["request_key"], "candidate_ref": candidate_ref,
            "run_ref": run_ref, "committed_at_utc": row["committed_at_utc"], "row_count": data["row_count"],
            "official_plan": {"plan_ref": plan["plan_ref"], "version": plan["version"], "label": "正式计划 v" + str(plan["version"])},
            "adoption": {key: audit.get(key) for key in fields} if audit else None,
            "can_open": not issues, "evidence_gaps": issues}


def read_candidate_history(conn, candidate_ref):
    reference(candidate_ref)
    store = CandidateStore(conn)
    with store.snapshot():
        run_ref = store.candidate_run(candidate_ref)
        sizes = conn.execute("SELECT COUNT(*),COALESCE(SUM(length(CAST(outcome_json AS BLOB))),0) "
                             "FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=?", (ADOPT_ACTION, candidate_ref)).fetchone()
        bounded_size(sizes[0], 10000)
        bounded_size(sizes[1], MAX_RESPONSE_BYTES)
        rows = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=? "
                                                "ORDER BY committed_at_utc,request_key", (ADOPT_ACTION, candidate_ref))]
        try:
            items = [_entry(conn, row, candidate_ref, run_ref) for row in rows]
            if len({item["official_plan"]["plan_ref"] for item in items}) != len(items):
                _invalid()
        except WorkbenchCommandRejected:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            _invalid()
        data = {"candidate_ref": candidate_ref, "run_ref": run_ref, "items": items,
                "total": len(items), "state": "available" if items else "empty",
                "basis": "original_candidate_receipts_and_official_adoption_audits"}
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, input_fingerprint(data)
