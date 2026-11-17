"""An admission's last official arrangement for every permanent operation."""

from collections import defaultdict

from core.models.enums import AdoptionSourceKind, LockStatus
from core.models.workbench_load_limits import MAX_RUN_RECORD_TASKS
from core.models.workbench_run_candidate import reference

from .candidate_baseline import AdmissionBaseline, invalid_baseline
from .candidate_tasks import operation_labels
from .candidate_values import bounded_size
from .history_documents import HistoryDocuments


def _last_official_rows(rows, version):
    """Retain each operation's row of its last archived official version (one Schedule row per version and operation).

    The archive admitted each row's integer ``version`` and ``op_id`` (``validate_production_archive``)."""
    latest = {}
    for row in rows:
        op, saved_version = row["op_id"], row["version"]
        if op < 1 or type(row["id"]) is not int or row["id"] < 1 or saved_version < 1:
            invalid_baseline()
        if saved_version <= version:
            latest[op] = max(saved_version, latest.get(op, 0))
    result = [row for row in rows if latest.get(row["op_id"]) == row["version"]]
    bounded_size(len(result), MAX_RUN_RECORD_TASKS)
    return sorted(result, key=lambda row: (row["op_id"], row["id"]))


def _official_sources(admission, versions):
    histories = {row["version"]: row for row in admission.history}
    result = {}
    for version in sorted(versions):
        if version not in histories:
            invalid_baseline()
        # 归档准入核过每个版本的 source_kind（production_capture.validate_production_archive）。
        history = histories[version]
        plan_ref = reference(history["plan_ref"], stored=True)
        source_kind = history["source_kind"]
        candidate_ref = None
        run_ref = None
        scenario_ref = None
        draft_ref = None
        if source_kind == AdoptionSourceKind.CANDIDATE_ADOPTION.value:
            candidate_ref = reference(history["source_ref"], stored=True)
            run_ref = reference(history["run_ref"], stored=True)
        else:
            scenario_ref = reference(history["source_ref"], stored=True)
            if history["draft_ref"] is not None:
                draft_ref = reference(history["draft_ref"], stored=True)
        result[version] = {
            "version": version,
            "plan_ref": plan_ref,
            "source_kind": source_kind,
            "source_candidate_ref": candidate_ref,
            "source_run_ref": run_ref,
            "source_scenario_ref": scenario_ref,
            "source_draft_ref": draft_ref,
            "history_record": history,
        }
    return result


def _bindings(admission, rows, sources):
    result = []
    for row in rows:
        if type(row.get("id")) is not int:
            invalid_baseline()
        ref = reference(row.get("operation_ref"), stored=True)
        task_ref = reference(row.get("task_ref"), stored=True)
        plan_ref = sources[row["version"]]["plan_ref"]
        if (
            admission.facts.operations.get(ref) != row["op_id"]
            or row["op_id"] not in admission.facts.tables["BatchOperations"]
        ):
            invalid_baseline()
        result.append(
            {
                **row,
                "row_ref": task_ref,
                "operation_ref": ref,
                "plan_ref": plan_ref,
                "task_ref": task_ref,
            }
        )
    return result


def _task(admission, row):
    labels, _ = operation_labels(admission.facts, row["operation_ref"])
    segment = admission.segment(row)
    gaps = labels["data_gaps"] + segment["data_gaps"]
    execution = labels["execution_at_generation"]
    if execution is not None:
        saved = admission.facts.execution[row["operation_ref"]]
        execution.update(
            {
                key: saved[key]
                for key in (
                    "first_actual_start",
                    "confirmed_finish",
                    "unknown_record_count",
                    "records_complete",
                    "quantity_complete",
                    "completion_basis",
                )
            }
        )
    return {
        **labels,
        **segment,
        "data_gaps": gaps,
        # 归档准入核过每行的 lock_status（production_capture.validate_production_archive）。
        "locked": row["lock_status"] == LockStatus.LOCKED.value,
        "process_type_ref": row["op_type_ref"],
        "process_type_label": row["op_type_label"],
        "plan_ref": row["plan_ref"],
        "task_ref": row["task_ref"],
        "official_version": row["version"],
    }


def _effort_source(source):
    value = {"plan_ref": source["plan_ref"], "version": source["version"]}
    if source["source_kind"] == AdoptionSourceKind.CANDIDATE_ADOPTION.value:
        return {
            **value,
            "kind": "run",
            "run_ref": source["source_run_ref"],
            "candidate_ref": source["source_candidate_ref"],
        }
    return {**value, "kind": "trial", "scenario_ref": source["source_scenario_ref"]}


def _official_identity(admission):
    baseline, version = admission.baseline, admission.baseline["version"]
    return {
        "kind": "admission_official",
        "baseline_ref": baseline["plan_ref"],
        "plan_ref": baseline["plan_ref"],
        "version": version,
        "label": "排产时的正式计划 v" + str(version) if version is not None else "排产时无正式计划",
        "state": "available" if version is not None else "absent",
        "source_candidate_ref": None,
        "source_run_ref": None,
    }


def _official_plan_rows(admission):
    version = admission.baseline["version"]
    if version is None:
        return [], {}
    rows = _last_official_rows(admission.schedule, version)
    sources = _official_sources(admission, {row["version"] for row in rows} | {version})
    return _bindings(admission, rows, sources), sources


def _row_operation_standard(row):
    return {
        "operation": {
            "source": row["source"],
            "setup_hours": row["setup_hours"],
            "unit_hours": row["unit_hours"],
        },
        "execution": {
            "target_quantity": row["quantity"],
            "remaining_quantity": row["remaining_quantity"],
        },
    }


def read_decision_baseline(capture, facts, disposition):
    """Project a verified admission directly from self-contained ScheduleHistory and Schedule."""
    admission = AdmissionBaseline(capture, facts, disposition)
    version = admission.baseline["version"]
    identity = _official_identity(admission)
    if version is None:
        return {
            "identity": identity,
            "tasks": [],
            "task_intervals": {},
            "source_states": [],
            "deferred_operation_ids": [],
            "operation_efforts": {},
            "operation_standards": {},
        }
    bound, sources = _official_plan_rows(admission)
    tasks, source_states = [], []
    deferred_ids = set()
    effort_by_ref, standards_by_ref = {}, {}
    by_version = defaultdict(list)
    for row in bound:
        by_version[row["version"]].append(row)
    for selected_version, source in sources.items():
        documents = HistoryDocuments(source["history_record"])
        source_states.append(
            {
                "plan_ref": source["plan_ref"],
                "version": selected_version,
                "source_kind": "workbench_" + source["source_kind"],
                "source_candidate_ref": source["source_candidate_ref"],
                "source_run_ref": source["source_run_ref"],
                "source_scenario_ref": source["source_scenario_ref"],
                "source_draft_ref": source["source_draft_ref"],
                "available": True,
                "issue_code": None,
            }
        )
        deferred_ids.update(documents.deferred_operation_ids)
        efforts = documents.operation_effort
        effort_source = _effort_source(source)
        for row in by_version[selected_version]:
            ref = row["operation_ref"]
            effort = None if efforts is None else efforts.get(ref)
            if effort is not None:
                effort_by_ref[ref] = {"effort": effort, "evidence_source": effort_source}
            standards_by_ref[ref] = {**_row_operation_standard(row), "evidence_source": effort_source}
            tasks.append(_task(admission, row))
        if selected_version == version:
            identity.update(
                {
                    "source_candidate_ref": source["source_candidate_ref"],
                    "source_run_ref": source["source_run_ref"],
                }
            )
    tasks.sort(key=lambda row: (row["operation_ref"], row["official_version"], row["row_ref"]))
    return {
        "identity": identity,
        "tasks": tasks,
        "task_intervals": admission.segment_intervals,
        "source_states": source_states,
        "deferred_operation_ids": sorted(deferred_ids - {row["op_id"] for row in bound}),
        "operation_efforts": effort_by_ref,
        "operation_standards": standards_by_ref,
    }
