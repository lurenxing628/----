"""Read only the original candidate's persisted adoption receipts and structured ScheduleHistory."""

from core.models.workbench_run_adoption import ADOPT_ACTION
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference
from core.services.workbench.facts.adoption_baseline_values import REASONS
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import bounded_size
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository


def _adoption_evidence(plan, context):
    history = context.history(plan["version"])
    if history is None:
        return None, [{"code": "adoption_evidence_missing", "message": REASONS["adoption_evidence_missing"]}]
    return history, []


def _entry(conn, row, candidate_ref, run_ref, context):
    receipt = WorkbenchCommandRepository(conn).public_result(row, replayed=True)
    data = receipt["data"]
    plan = data["official_plan"]
    reference(plan["plan_ref"], stored=True)
    audit, issues = _adoption_evidence(plan, context)
    if audit is None:
        issues.append(
            {
                "code": "official_identity_unavailable",
                "message": "原来采用的那一版计划编号已经失效，结果记录照样保留，系统没有替你打开别的版本。请到计划列表重新选择。",
            }
        )
    fields = ("reason", "declared_operator", "application_operator", "adopted_at", "baseline_ref", "baseline_version")
    return {
        "receipt_ref": row["receipt_ref"],
        "request_key": row["request_key"],
        "candidate_ref": candidate_ref,
        "run_ref": run_ref,
        "committed_at_utc": row["committed_at_utc"],
        "row_count": data["row_count"],
        "official_plan": {
            "plan_ref": plan["plan_ref"],
            "version": plan["version"],
            "label": "正式计划 v" + str(plan["version"]),
        },
        "adoption": {key: audit[key] for key in fields} if audit else None,
        "can_open": not issues,
        "evidence_gaps": issues,
    }


def read_candidate_history(conn, candidate_ref, *, bind_snapshot):
    reference(candidate_ref)
    store = CandidateStore(conn)
    receipts = WorkbenchRunCandidateRepository(conn)
    with store.snapshot():
        context = PlanReadContext(conn)
        with context.read_scope():
            return _read_candidate_history(conn, candidate_ref, store, receipts, context, bind_snapshot)


def _read_candidate_history(conn, candidate_ref, store, receipts, context, bind_snapshot):
    run_ref = store.candidate_run(candidate_ref)
    rows, byte_count = [], 0
    for row in receipts.adoption_receipts(ADOPT_ACTION, candidate_ref, 10001):
        bounded_size(len(rows) + 1, 10000)
        byte_count += len(row["outcome_json"].encode("utf-8"))
        bounded_size(byte_count, MAX_RESPONSE_BYTES)
        rows.append(row)
    items = [_entry(conn, row, candidate_ref, run_ref, context) for row in rows]
    snapshot = bind_snapshot(
        {"kind": "run-candidate-adoption-history", "candidate_ref": candidate_ref},
        {
            "read_contract_version": 1,
            "candidate_ref": candidate_ref,
            "run_ref": run_ref,
            "receipts": [
                {
                    "receipt_ref": item["receipt_ref"],
                    "can_open": item["can_open"],
                    "issue_codes": sorted(issue["code"] for issue in item["evidence_gaps"]),
                }
                for item in items
            ],
        },
    )
    data = {
        "candidate_ref": candidate_ref,
        "run_ref": run_ref,
        "items": items,
        "total": len(items),
        "state": "available" if items else "empty",
        "basis": "original_candidate_receipts_and_official_adoption_audits",
    }
    return data, snapshot
