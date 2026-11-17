"""Revalidate exact saved arrangements against current production in one snapshot."""

from __future__ import annotations

from core.errors import AppError, ValidationError
from core.models.content import StoredJsonCorrupt, same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_trial_adoption import TrialAdoptionBlocked, TrialAdoptionEvidence
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.workbench.facts.candidate_projection import baseline_capture
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_origin import OfficialTrialSource, invalid_trial_snapshot
from core.services.workbench.facts.trial_scenario_archive import (
    load_verified_scenario,
    scenario_issue_refs,
    schedule_rows,
)
from core.services.workbench.plan.official_persistence import (
    NO_RESOURCE,
    adopted_label,
    adopted_resource,
    archived_resources,
    build_task_snapshot,
    generation_resource,
)
from core.services.workbench.run.candidate_adoption_constraints import bind_validated_schedule_outcome
from core.services.workbench.run.candidate_adoption_storage import require_official_baseline
from core.services.workbench.run.candidate_adoption_validation import require_official_scope
from core.services.workbench.run.input import prepare_business_input
from core.services.workbench.run.jobs_facts import run_execution_projections

from .facts import live_context, saved_capture
from .materials import run_window
from .preparation import ScenarioLabels, new_slot
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
            try:
                scenario = load_verified_scenario(conn, scenario_ref)
            except StoredJsonCorrupt as exc:
                # 已保存方案的存档读不出来，按“不能采用”提示；活表（日历等）读不出来照常 500。
                raise TrialAdoptionBlocked("trial_snapshot_invalid", "试调数据读不出来，正式计划没有改变。请刷新后重试。") from exc
            head, rows = scenario.head, scenario.rows
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
            validator = _scenario_validator(admission, rows, live)
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
                scenario=scenario,
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
        raise TrialAdoptionBlocked(exc.code, str(exc)) from exc
    except CandidateRunInputError as exc:
        raise TrialAdoptionBlocked(*_INPUT_PROBLEMS.get(exc.reason, _INPUT_UNPROVEN)) from exc
    except (ValidationError, AppError) as exc:
        raise TrialAdoptionBlocked(
            "scenario_constraint_unproven",
            "试调方案的现场数据、编号或约束资料不完整，没有执行正式采用。",
        ) from exc


def _resource(index, kind, key):
    """One resource of an adoption's ``(kind, key)`` index of trial-stored refs and names; a task without one
    (``key`` empty) has none."""
    if not key:
        return NO_RESOURCE
    ref, name = index[(kind, key)]
    return adopted_resource(ref, name, invalid_trial_snapshot)


class _AdoptionResources:
    """The resources a scenario's adopted tasks record.

    A new slot is arranged on machines and operators saved with the scenario (``scenario_resources_snapshot``, every
    one with its ref); any other arrangement on its draft's archived ones. A supplier is the source's: an official
    plan source's recorded supplier while the operation keeps it, otherwise the draft archive's; a candidate
    source's generation facts. A name the trial stored is admitted as that archive's (``invalid_trial_snapshot``).
    """

    def __init__(self, scenario):
        self.source = scenario.origin.source
        self.draft = archived_resources(scenario.origin.tables)
        self.saved = {
            (kind, row["business_code"]): (row["ref"], row["label"])
            for kind, bucket in (("machine", "machines"), ("operator", "operators"))
            for row in scenario.resources[bucket]
        }

    def assigned(self, row, kind, key):
        return _resource(self.saved if new_slot(row) else self.draft, kind, key)

    def supplier(self, row):
        key = row["original"]["operation"]["supplier_id"]
        if not isinstance(self.source, OfficialTrialSource):
            return generation_resource(self.source.facts, "supplier", key)
        recorded = self.source.document["suppliers"][row["operation_ref"]]
        if key and key == recorded["supplier_id"]:
            return adopted_resource(recorded["ref"], recorded["label"], invalid_trial_snapshot)
        return _resource(self.draft, "supplier", key)


def _provenance_and_snapshots(scenario_ref, scenario, outcome):
    saved, head, rows = scenario.saved, scenario.head, scenario.rows
    admission = head["admission"]
    base_meta = baseline_capture(admission["baseline"], head["created_at"], kind="trial_creation_official")
    provenance = {
        "source_kind": "trial_adoption",
        "source_ref": scenario_ref,
        "source_label": saved["name"],
        "run_ref": None,
        "draft_ref": head["draft_ref"],
        "accepted_at": head["created_at"],
        "finished_at": saved["saved_at"],
        "algorithm_json": None,
        "baseline_version": base_meta["version"],
        "baseline_ref": base_meta["baseline_ref"],
        "baseline_kind": base_meta["kind"],
        "baseline_captured_at": base_meta["captured_at"],
        "baseline_captured_task_count": int(base_meta["captured_task_count"]),
        "operation_effort": saved["operation_effort"],
    }
    labels = ScenarioLabels(scenario.origin, scenario.resources)
    resources = _AdoptionResources(scenario)
    rows_by_op_id = {item["original"]["operation"]["id"]: item for item in rows}
    task_snapshots = {}
    for sched_row in outcome.validated_payload.schedule_rows:
        trial_row = rows_by_op_id[sched_row.op_id]
        orig = trial_row["original"]
        op_type_ref, op_type_label = labels.operation_type(trial_row, current=True)
        # 试调存下的工种名可以没有：来源正式计划的任务本就没记，或保存场景前删掉了新槽位的工种。有名称就按
        # 资源名同一准入，不合法是试调存档损坏。
        if op_type_label is not None:
            op_type_label = adopted_label(op_type_label, invalid_trial_snapshot)
        task_snapshots[sched_row.op_id] = build_task_snapshot(
            operation=orig["operation"],
            batch=orig["batch"],
            execution=orig["execution"],
            quantity_basis="trial_creation",
            op_type_ref=op_type_ref,
            op_type_label=op_type_label,
            machine=resources.assigned(trial_row, "machine", sched_row.machine_id),
            operator=resources.assigned(trial_row, "operator", sched_row.operator_id),
            supplier=resources.supplier(trial_row),
        )
    return provenance, task_snapshots


def _build_trial_adoption_evidence(
    conn,
    *,
    scenario_ref,
    scenario,
    capture,
    live,
    ledger,
    validator,
    evaluation,
):
    head, rows = scenario.head, scenario.rows
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
    binding = {
        "scenario_ref": scenario_ref,
        "draft_ref": head["draft_ref"],
        "scenario_revision": head["scenario_revision"],
        "baseline_ref": live["baseline"]["plan_ref"],
        "baseline_version": live["baseline"]["version"],
    }
    snapshot = {
        "binding": binding,
        "revisions": live["revisions"],
        "data_context_ref": live["data_context_ref"],
    }
    provenance, task_snapshots = _provenance_and_snapshots(
        scenario_ref,
        scenario,
        outcome,
    )
    return TrialAdoptionEvidence(
        scenario_ref,
        head["draft_ref"],
        live["baseline"],
        snapshot,
        prepared,
        outcome,
        run_window(scenario.origin.source),
        provenance=provenance,
        task_snapshots=task_snapshots,
    )


def _current_baseline(admission, live):
    if not same(admission["baseline"], live["baseline"]):
        raise TrialAdoptionBlocked("snapshot_stale", "正式计划已更新，请基于当前正式计划重新试调。")
    if not same(admission["execution"], live["execution"]):
        raise TrialAdoptionBlocked("snapshot_stale", "建草稿之后现场数据变了，请重新核对这份试调方案。")


def _scenario_validator(admission, rows, live):
    """The draft's base issues name its draft tasks; the scenario's validator reads them under its own tasks."""
    mapping = {row["draft_task_ref"]: row["task_ref"] for row in rows}
    return TrialValidator(dict(admission, base_issues=scenario_issue_refs(admission["base_issues"], mapping)), rows, live)


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
