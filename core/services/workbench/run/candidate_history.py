"""Read only the original candidate's persisted adoption receipts and audits."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_run_adoption import ADOPT_ACTION
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference, reject
from core.services.workbench.facts.adoption_baseline_values import REASONS, AdoptionBaselineUnavailable
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import bounded_size
from core.services.workbench.plan.adoption_baseline import read_adoption_record, read_adoption_source
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository


def _invalid():
    reject("candidate_adoption_history_invalid", "这个候选方案的采用结果和它的来源或正式计划对不上，没有改去查别的采用记录。请到「排产记录」重新选择。", 500)


def _adoption_evidence(conn, row, plan, candidate_ref, run_ref, context, receipt_result):
    histories = context.history_rows(plan["version"])
    issues, recorded, audit = [], None, None
    try:
        if len(histories) != 1:
            raise AdoptionBaselineUnavailable("adoption_evidence_missing", "ScheduleHistory")
        history = histories[0]
        recorded = read_adoption_record(conn, plan_ref=plan["plan_ref"], version=plan["version"], history=history,
                                        receipt=row, receipt_result=receipt_result)
        if recorded is not None:
            audit = recorded[1]
            read_adoption_source(conn, plan_ref=plan["plan_ref"], version=plan["version"],
                                 history=history, recorded=recorded, context=context)
    except AdoptionBaselineUnavailable as exc:
        issues.append({"code": exc.code, "message": REASONS[exc.code]})
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        issues.append({"code": "adoption_snapshot_invalid", "message": REASONS["adoption_snapshot_invalid"]})
    except WorkbenchPlanReferenceError:
        issues.append({"code": "adoption_reference_invalid", "message": REASONS["adoption_reference_invalid"]})
    except (KeyError, TypeError, ValueError, OverflowError):
        issues.append({"code": "adoption_snapshot_invalid", "message": REASONS["adoption_snapshot_invalid"]})
    if recorded is not None:
        if (recorded[0] != "candidate_adoption" or recorded[1]["candidate_ref"] != candidate_ref
                or recorded[1]["run_ref"] != run_ref or recorded[1]["request_key"] != row["request_key"]
                or recorded[2]["receipt_ref"] != row["receipt_ref"]):
            _invalid()
    elif not issues:
        _invalid()
    return audit, issues


def _entry(conn, row, candidate_ref, run_ref, context):
    receipt = WorkbenchCommandRepository.public_result(row, replayed=True)
    data = receipt["data"]
    if (receipt["result"] != "committed" or data["candidate_ref"] != candidate_ref or data["run_ref"] != run_ref
            or data["official_plan"]["source_run_ref"] != run_ref):
        _invalid()
    plan = data["official_plan"]
    reference(plan["plan_ref"], stored=True)
    if type(plan["version"]) is not int or plan["version"] < 1 or plan["kind"] != "official":
        _invalid()
    audit, issues = _adoption_evidence(conn, row, plan, candidate_ref, run_ref, context, receipt)
    try:
        if context.resolve(plan["plan_ref"]) != WorkbenchPlanLocator(plan["version"], "adopted"):
            _invalid()
        if not issues:
            context.selected(plan["plan_ref"])
    except WorkbenchPlanReferenceError:
        issues.append({"code": "official_identity_unavailable", "message": "原来采用的那一版计划编号已经失效，结果记录照样保留，系统没有替你打开别的版本。请到计划列表重新选择。"})
    except WorkbenchCommandRejected as exc:
        if exc.status == 413 or exc.code == "candidate_adoption_history_invalid":
            raise
        issues.append({"code": "official_identity_unavailable", "message": "此次采用生成的正式计划暂时无法读取，请到计划列表核对。"})
    fields = ("reason", "declared_operator", "application_operator", "adopted_at", "baseline_ref", "baseline_version")
    return {"receipt_ref": row["receipt_ref"], "request_key": row["request_key"], "candidate_ref": candidate_ref,
            "run_ref": run_ref, "committed_at_utc": row["committed_at_utc"], "row_count": data["row_count"],
            "official_plan": {"plan_ref": plan["plan_ref"], "version": plan["version"], "label": "正式计划 v" + str(plan["version"])},
            "adoption": {key: audit.get(key) for key in fields} if audit else None,
            "can_open": not issues, "evidence_gaps": issues}


def read_candidate_history(conn, candidate_ref):
    reference(candidate_ref)
    store = CandidateStore(conn)
    receipts = WorkbenchRunCandidateRepository(conn)
    with store.snapshot():
        with read_evidence_scope(conn):
            context = PlanReadContext(conn)
            with context.read_scope():
                return _read_candidate_history(conn, candidate_ref, store, receipts, context)


def _read_candidate_history(conn, candidate_ref, store, receipts, context):
    run_ref = store.candidate_run(candidate_ref)
    rows, byte_count = [], 0
    for row in receipts.adoption_receipts(ADOPT_ACTION, candidate_ref, 10001):
        bounded_size(len(rows) + 1, 10000)
        if type(row["outcome_json"]) is not str:
            _invalid()
        byte_count += len(row["outcome_json"].encode("utf-8"))
        bounded_size(byte_count, MAX_RESPONSE_BYTES)
        rows.append(row)
    try:
        items = [_entry(conn, row, candidate_ref, run_ref, context) for row in rows]
        if len({item["official_plan"]["plan_ref"] for item in items}) != len(items):
            _invalid()
    except WorkbenchCommandRejected:
        raise
    except (KeyError, TypeError, ValueError, OverflowError):
        _invalid()
    data = {"candidate_ref": candidate_ref, "run_ref": run_ref, "items": items,
            "total": len(items), "state": "available" if items else "empty",
            "basis": "original_candidate_receipts_and_official_adoption_audits"}
    state = {"read_contract_version": 1, "candidate_ref": candidate_ref, "run_ref": run_ref,
             "receipts": [{"receipt_ref": item["receipt_ref"], "can_open": item["can_open"],
                           "issue_codes": sorted(issue["code"] for issue in item["evidence_gaps"])}
                          for item in items]}
    return data, state
