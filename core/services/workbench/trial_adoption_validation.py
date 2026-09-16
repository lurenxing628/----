"""Revalidate exact saved arrangements against current production in one snapshot."""

from datetime import datetime

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import durable_value
from core.models.workbench_trial_adoption import TrialAdoptionBlocked, TrialAdoptionEvidence
from core.models.workbench_trial_codec import fingerprint
from core.services.scheduler.schedule_service import ScheduleService

from .run_candidate_adoption_storage import _require_official_baseline, require_adoption_schema
from .run_candidate_adoption_validation import _require_official_scope, validate_adoption_payload
from .run_compute_validation import validate_candidate
from .run_input_readonly import candidate_read_snapshot
from .run_jobs_facts import run_execution_projections
from .trial_adoption_input import prepare_trial_adoption_input
from .trial_adoption_storage import load_saved_scenario, schedule_rows
from .trial_facts import live_context
from .trial_validation import TrialValidator


def validate_trial_adoption(conn, scenario_ref):
    try:
        with candidate_read_snapshot(conn):
            require_adoption_schema(conn)
            saved, head, rows = load_saved_scenario(conn, scenario_ref)
            admission = head["admission"]
            live = live_context(conn, [row["operation_ref"] for row in rows])
            _current_baseline(conn, admission, live)
            _original_work(rows, live)
            checked = _scenario_validation(conn, saved, admission, rows, live)
            issues = [row for row in checked["issues"] if row["code"] != "scenario_adoption_not_connected"]
            if issues:
                raise TrialAdoptionBlocked("scenario_constraint_unproven", "试调方案没有通过当前的完整核对，正式计划没有改变。", issues)
            settings = _settings(rows)
            projections = run_execution_projections(conn, settings)
            _require_official_baseline(live["baseline"], projections)
            prepared = prepare_trial_adoption_input(conn, settings, projections, live)
            _complete_scope(rows, prepared)
            payload = validate_candidate(prepared, schedule_rows(rows), [])
            if payload.scheduled_op_ids != {op.id for op in prepared.operations}:
                raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案没有覆盖所选批次的全部工序，正式计划没有改变。")
            svc = ScheduleService(conn)
            _require_official_scope(svc, prepared.prev_version, payload.scheduled_op_ids)
            validate_adoption_payload(conn, prepared, payload)
            proof = {"scenario_ref": scenario_ref, "draft_ref": head["draft_ref"],
                     "scenario_hash": fingerprint(saved), "admission_hash": head["admission_hash"],
                     "facts_hash": live["facts_hash"], "execution_hash": fingerprint(live["execution"]),
                     "baseline_hash": fingerprint(live["baseline"]),
                     "rows_hash": fingerprint(rows), "validated_hash": fingerprint(durable_value(payload))}
            return TrialAdoptionEvidence(scenario_ref, head["draft_ref"], live["baseline"], proof, prepared, payload)
    except TrialAdoptionBlocked:
        raise
    except CandidateAdoptionBlocked as exc:
        if exc.code == "official_scope_not_covered":
            raise TrialAdoptionBlocked(exc.code,
                "试调方案没有覆盖当前正式计划的全部工序。请将相关批次一起排产后再试调。") from exc
        raise TrialAdoptionBlocked(
            exc.code, "试调方案没有通过采用前的核对，正式计划没有改变。请回到试调列表重新预检。") from exc
    except WorkbenchCommandRejected:
        raise
    except CandidateRunInputError as exc:
        raise TrialAdoptionBlocked(
            "scenario_constraint_unproven",
            "试调方案的排产输入没有通过核对，正式计划没有改变。请回到试调列表重新预检。") from exc
    except (AppError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise TrialAdoptionBlocked("scenario_constraint_unproven", "试调方案的现场数据、编号或约束资料不完整，没有执行正式采用。") from exc


def _current_baseline(conn, admission, live):
    if fingerprint(admission["baseline"]) != fingerprint(live["baseline"]):
        raise TrialAdoptionBlocked("snapshot_stale", "正式计划已更新，请基于当前正式计划重新试调。")
    if conn.execute("SELECT 1 FROM Schedule s WHERE NOT EXISTS "
                    "(SELECT 1 FROM ScheduleHistory h WHERE h.version=s.version) LIMIT 1").fetchone():
        raise TrialAdoptionBlocked("official_history_inconsistent", "正式安排缺少所属历史版本，不能采用。")
    if fingerprint(admission["execution"]) != fingerprint(live["execution"]):
        raise TrialAdoptionBlocked("snapshot_stale", "建草稿之后现场数据变了，请重新核对这份试调方案。")


def _scenario_validation(conn, saved, admission, rows, live):
    mapping = {task["source_task_ref"]: task["task_ref"] for task in saved["tasks"]}
    issues = []
    for original in admission["base_issues"]:
        item = dict(original)
        for key in ("task_ref", "related_task_ref"):
            if item.get(key) in mapping:
                item[key] = mapping[item[key]]
        issues.append(item)
    return TrialValidator(conn, dict(admission, base_issues=issues), rows, live).evaluate()


def _original_work(rows, live):
    tables = live["facts"]["tables"]
    ops = {row["id"]: row for row in tables["BatchOperations"]}
    batches = {row["batch_id"]: row for row in tables["Batches"]}
    refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    for row in rows:
        original = row["original"]
        if (fingerprint(original["operation"]) != fingerprint(ops.get(original["operation"]["id"]))
                or fingerprint(original["batch"]) != fingerprint(batches.get(original["batch"]["batch_id"]))
                or refs.get(("batch", original["batch"]["batch_id"])) != original["batch_ref"]):
            raise TrialAdoptionBlocked("scenario_work_changed", "试调方案里的工序、数量、工时或批次和当前资料不一致。")
        for kind in ("machine", "operator"):
            current = row["current"]
            key, ref = current[kind + "_id"], current[kind + "_ref"]
            if (key is None) != (ref is None) or (key is not None and refs.get((kind, key)) != ref):
                raise TrialAdoptionBlocked("scenario_resource_identity_changed", "试调方案中的设备或人员已删除或被替换。")


def _settings(rows):
    return {"batch_refs": sorted({row["original"]["batch_ref"] for row in rows}),
            "start_date": min(datetime.fromisoformat(row["current"]["start"]).date() for row in rows).isoformat(),
            "end_date": max(datetime.fromisoformat(row["current"]["end"]).date() for row in rows).isoformat(),
            "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"}


def _complete_scope(rows, prepared):
    saved = {row["operation_ref"]: row for row in rows}
    if set(saved) != {item["operation_ref"] for item in prepared.dispositions}:
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案未覆盖批次的全部工序，无法正式采用。")
    for item in prepared.dispositions:
        original = saved[item["operation_ref"]]["original"]
        if (original["operation"]["id"] != item["op_id"]
                or original["predecessor_operation_refs"] != item["predecessor_refs"]):
            raise TrialAdoptionBlocked("scenario_dependency_changed", "试调方案里的工序或前后序和当前工艺不一致。")
