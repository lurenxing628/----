"""Revalidate exact saved arrangements against current production in one snapshot."""

from __future__ import annotations

from core.errors import AppError, ValidationError
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_trial_adoption import TrialAdoptionBlocked, TrialAdoptionEvidence
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario, schedule_rows
from core.services.workbench.run.candidate_adoption_constraints import bind_validated_schedule_outcome
from core.services.workbench.run.candidate_adoption_storage import require_official_baseline
from core.services.workbench.run.candidate_adoption_validation import require_official_scope
from core.services.workbench.run.input import prepare_business_input
from core.services.workbench.run.jobs_facts import run_execution_projections

from .facts import live_context, saved_capture
from .materials import run_window
from .validation import TrialValidator

_INPUT_UNPROVEN = (
    "scenario_constraint_unproven",
    "试调方案的排产输入没有通过核对，正式计划没有改变。请回到试调列表重新预检。",
)
# 采用复核原样保留的安排：试调核对已按同一口径保护；仍对不上时说清楚原因，不让人反复重新预检。
_INPUT_PROBLEMS = {
    "all_operations_frozen": (
        "scenario_nothing_to_adopt",
        "试调方案里的工序都按来源排产的不重排时段原样保留，和当前正式计划一样，没有可以采用的调整，正式计划没有改变。",
    ),
}


def validate_trial_adoption(conn, scenario_ref, *, data_context):
    try:
        with candidate_read_snapshot(conn), ledger_read_snapshot(conn) as ledger:
            scenario = load_saved_scenario(conn, scenario_ref)
            saved, head, rows = scenario.saved, scenario.head, scenario.rows
            admission = head["admission"]
            capture = saved_capture(conn, admission)
            live = live_context(
                conn,
                scenario.origin,
                capture,
                ledger=ledger,
                data_context=data_context,
            )
            _current_baseline(admission, live)
            _original_work(rows, live)
            validator = _scenario_validator(conn, saved, admission, rows, live)
            evaluation = validator.evaluate_constraints(check_baseline=False)
            if evaluation.issues:
                raise TrialAdoptionBlocked(
                    "scenario_constraint_unproven",
                    "试调方案没有通过当前的完整核对，正式计划没有改变。",
                    list(evaluation.issues),
                )
            return _build_trial_adoption_evidence(
                conn,
                scenario_ref=scenario_ref,
                head=head,
                admission=admission,
                rows=rows,
                capture=capture,
                live=live,
                ledger=ledger,
                validator=validator,
                evaluation=evaluation,
            )
    except CandidateAdoptionBlocked as exc:
        if exc.code == "official_scope_not_covered":
            raise TrialAdoptionBlocked(
                exc.code,
                "试调方案没有覆盖当前正式计划的全部工序。请将相关批次一起排产后再试调。",
            ) from exc
        raise TrialAdoptionBlocked(
            exc.code,
            "试调方案没有通过采用前的核对，正式计划没有改变。请回到试调列表重新预检。",
        ) from exc
    except TrialAdoptionBlocked:
        raise
    except WorkbenchCommandRejected as exc:
        if exc.code != "trial_snapshot_invalid":
            raise
        # 草稿或方案保存的资料读不出来：采用预览照样给出阻断说明，正式计划没有改变。
        raise TrialAdoptionBlocked(exc.code, str(exc)) from exc
    except CandidateRunInputError as exc:
        raise TrialAdoptionBlocked(*_INPUT_PROBLEMS.get(exc.reason, _INPUT_UNPROVEN)) from exc
    except (ValidationError, AppError) as exc:
        raise TrialAdoptionBlocked(
            "scenario_constraint_unproven",
            "试调方案的现场数据、编号或约束资料不完整，没有执行正式采用。",
        ) from exc


def _build_trial_adoption_evidence(
    conn,
    *,
    scenario_ref,
    head,
    admission,
    rows,
    capture,
    live,
    ledger,
    validator,
    evaluation,
):
    facts = live["preflight_facts"]
    latest_plan_rows = facts.latest_plan_rows(live["baseline"]["version"] or 0)
    projections = run_execution_projections(
        validator.settings,
        capture=capture,
        existing=facts.execution_projections.values(),
        ledger=ledger,
        facts=facts,
        latest_plan_rows=latest_plan_rows,
    )
    require_official_baseline(live["baseline"], projections)
    prepared = prepare_business_input(
        conn,
        validator.settings,
        projections,
        facts=facts,
        config_snapshot=facts.configuration(),
        baseline=live["baseline"],
        held=validator.held,
        admitted_piece_scope=evaluation.piece_scope,
        include_efforts=False,
    )
    _complete_scope(rows, prepared)
    outcome = bind_validated_schedule_outcome(
        prepared,
        schedule_rows(rows, evaluation.resolved_intervals_by_row),
        evaluation,
    )
    scheduled_op_ids = outcome.validated_payload.scheduled_op_ids
    if scheduled_op_ids != prepared.allowed_op_ids:
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案没有覆盖所选批次的全部工序，正式计划没有改变。")
    require_official_scope(prepared.latest_plan_rows, scheduled_op_ids)
    proof = {
        "proof_version": "content_refs_v1",
        "scenario_ref": scenario_ref,
        "draft_ref": head["draft_ref"],
        "scenario_revision": head["scenario_revision"],
        "baseline_ref": live["baseline"]["plan_ref"],
        "baseline_version": live["baseline"]["version"],
    }
    snapshot = {"proof": proof, "revisions": live["revisions"], "data_context_ref": live["data_context_ref"]}
    return TrialAdoptionEvidence(
        scenario_ref,
        head["draft_ref"],
        live["baseline"],
        snapshot,
        prepared,
        outcome,
        run_window(admission),
        proof=proof,
    )


def _current_baseline(admission, live):
    if not same(admission["baseline"], live["baseline"]):
        raise TrialAdoptionBlocked("snapshot_stale", "正式计划已更新，请基于当前正式计划重新试调。")
    if not same(admission["execution"], live["execution"]):
        raise TrialAdoptionBlocked("snapshot_stale", "建草稿之后现场数据变了，请重新核对这份试调方案。")


def _scenario_validator(conn, saved, admission, rows, live):
    mapping = {task["source_task_ref"]: task["task_ref"] for task in saved["tasks"]}
    issues = []
    for original in admission["base_issues"]:
        item = dict(original)
        for key in ("task_ref", "related_task_ref"):
            if item.get(key) in mapping:
                item[key] = mapping[item[key]]
        issues.append(item)
    return TrialValidator(conn, dict(admission, base_issues=issues), rows, live)


def _original_work(rows, live):
    capture = live["capture"]
    ops = capture.index("BatchOperations", "id")
    batches = capture.index("Batches", "batch_id")
    refs = live["preflight_facts"].refs
    for row in rows:
        original = row["original"]
        if (
            not same(original["operation"], ops.get(original["operation"]["id"]))
            or not same(original["batch"], batches.get(original["batch"]["batch_id"]))
            or refs.get(("batch", original["batch"]["batch_id"])) != original["batch_ref"]
        ):
            raise TrialAdoptionBlocked("scenario_work_changed", "试调方案里的工序、数量、工时或批次和当前资料不一致。")
        for kind in ("machine", "operator"):
            current = row["current"]
            key, ref = current[kind + "_id"], current[kind + "_ref"]
            if (key is None) != (ref is None) or (key is not None and refs.get((kind, key)) != ref):
                raise TrialAdoptionBlocked("scenario_resource_identity_changed", "试调方案中的设备或人员已删除或被替换。")


def _complete_scope(rows, prepared):
    saved = {row["operation_ref"]: row for row in rows}
    deferred = material_deferred_ids(prepared.dispositions, prepared.settings)
    expected = [item for item in prepared.dispositions if item["op_id"] not in deferred]
    if set(saved) != {item["operation_ref"] for item in expected}:
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案未覆盖批次的全部工序，无法正式采用。")
    for item in expected:
        original = saved[item["operation_ref"]]["original"]
        if (
            original["operation"]["id"] != item["op_id"]
            or original["predecessor_operation_refs"] != item["predecessor_refs"]
        ):
            raise TrialAdoptionBlocked("scenario_dependency_changed", "试调方案里的工序或前后序和当前工艺不一致。")
