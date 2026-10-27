"""Resolve archived official lineage without reading today's official rows."""

from core.infrastructure.read_evidence import verified_read
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.plan.adoption_baseline import read_adoption_record
from core.shared.strict_json import canonical_json

from .adoption_baseline_sources import (
    read_adoption_operation_facts,
    trial_adoption_facts,
)
from .adoption_baseline_values import REASONS, AdoptionBaselineUnavailable
from .candidate_read_source import read_candidate_source
from .candidate_store import CandidateStore
from .material_deferral_evidence import archived_deferred_payload_evidence
from .preflight_dependencies import material_deferred_ids
from .zero_duration import PointEventError
from .zero_duration_evidence import CandidatePointReader, trial_point_evidence


def _gap(code, message):
    return {"origins": {}, "point_work": None, "issue": {"code": code, "message": message}}


def _require_identity(actual, expected):
    if canonical_json(actual) != canonical_json(expected):
        raise WorkbenchCommandRejected(
            "adoption_snapshot_invalid", "此正式版本的采用来源编号与保存资料不一致。",
        )


def candidate_evidence(source, audit):
    _require_identity((source.candidate["candidate_ref"], source.run["run_ref"]),
                      (audit["candidate_ref"], audit["run_ref"]))
    _require_identity((source.capture["baseline"]["plan_ref"], source.capture["baseline"]["version"]),
                      (audit["baseline_ref"], audit["baseline_version"]))
    proof = audit["proof"]
    _require_identity((proof["candidate_ref"], proof["run_ref"], proof["baseline_ref"], proof["baseline_version"]),
                      (audit["candidate_ref"], audit["run_ref"], source.capture["baseline"]["plan_ref"],
                       source.capture["baseline"]["version"]))
    return {"basis": "candidate_adoption", "audit": audit,
            "arranged": [row["payload"] for row in source.raw_tasks], "generation_facts": source.facts}


def trial_evidence(source, audit):
    saved, head, rows = source
    _require_identity((saved["scenario_ref"], head["draft_ref"]),
                      (audit["scenario_ref"], audit["draft_ref"]))
    _require_identity((saved["baseline"]["plan_ref"], saved["baseline"]["version"]),
                      (audit["baseline_ref"], audit["baseline_version"]))
    proof = audit["proof"]
    _require_identity((proof["scenario_ref"], proof["draft_ref"], proof["scenario_revision"],
                       proof["baseline_ref"], proof["baseline_version"]),
                      (audit["scenario_ref"], audit["draft_ref"], head["scenario_revision"],
                       saved["baseline"]["plan_ref"], saved["baseline"]["version"]))
    arranged = [{"op_id": row["original"]["operation"]["id"],
                 "machine_id": row["current"]["machine_id"], "operator_id": row["current"]["operator_id"],
                 "start_time": row["current"]["start"], "end_time": row["current"]["end"]} for row in rows]
    return {"basis": "trial_adoption", "audit": audit, "arranged": arranged, "generation_facts": None}


def _deferred_evidence(source, evidence):
    """The audit's recorded pending operations, checked against the immutable adoption source."""
    recorded, recorded_issues = archived_deferred_payload_evidence(evidence["audit"])
    if recorded_issues:
        return [], recorded_issues
    if evidence["basis"] == "candidate_adoption":
        ids, issues = material_deferred_ids(source.disposition.values(), source.capture["input"]), []
    else:
        original = source[1]["admission"]["source"]
        if "capture" in original:
            # 以候选为基础的试调来源保存了候选运行的 capture 与全部工序处置。
            ids, issues = material_deferred_ids(original["dispositions"].values(), original["capture"]["input"]), []
        else:
            # 以正式计划为基础的试调来源在创建时记下了原计划的待料工序编号与缺口。
            ids, issues = archived_deferred_payload_evidence(original)
            issues = issues or original["deferred_operation_issues"]
    if not issues and recorded != ids:
        return [], ["deferred_operation_evidence_invalid"]
    return sorted(recorded), []


def _operation_type(operation, refs, names, trace):
    key = (trace or {}).get("op_type_id", operation.get("op_type_id"))
    label = names.get(key)
    return {"ref": refs.get(("op_type", key)),
            "label": label if type(label) is str and label.strip() else None}


def _operation_standard(operation, execution):
    return {"operation": {key: operation.get(key) for key in ("source", "setup_hours", "unit_hours")},
            "execution": {key: (execution or {}).get(key) for key in ("target_quantity", "remaining_quantity")}}


def _type_names_by_ref(refs, names):
    return {refs[("op_type", key)]: label if type(label) is str and label.strip() else None
            for key, label in names.items() if ("op_type", key) in refs}


def _operation_metadata(source, evidence):
    if evidence["basis"] == "candidate_adoption":
        traces = {row["op_id"]: row for row in source.candidate["artifact"].get("results", [])}
        names = {row["op_type_id"]: row.get("name") for row in source.facts.table("OpTypes") or []}
        operations = {ref: source.facts.tables["BatchOperations"][op_id]
                      for ref, op_id in source.facts.operations.items() if op_id in source.facts.tables["BatchOperations"]}
        types = {ref: _operation_type(operation, source.facts.entity_refs, names, traces.get(operation["id"]))
                 for ref, operation in operations.items()}
        standards = {ref: _operation_standard(operation, source.facts.execution.get(ref))
                     for ref, operation in operations.items()}
        return source.receipt.get("operation_effort"), types, standards
    saved, head, rows = source
    original = head["admission"]["source"]
    prepared = evidence["trial_source"]
    refs = prepared.resources.entity_refs
    names = {key: row.get("name") for key, row in prepared.resources.tables["OpTypes"].items()}
    names_by_ref = _type_names_by_ref(refs, names)
    slot_refs = prepared.assigned_resources.entity_refs
    slot_names = {key: row.get("name") for key, row in prepared.assigned_resources.tables["OpTypes"].items()}
    slot_names_by_ref = _type_names_by_ref(slot_refs, slot_names)
    recorded, slot_types = original.get("operation_types") or {}, original["trial_operation_types"]
    ledger = {item["operation_ref"]: item for item in (saved["operation_effort"] or {}).get("items", [])}
    types = {}
    for row in rows:
        ref = row["operation_ref"]
        new_slot = "operation_effort" in row.get("current", {}) or ledger.get(ref, {}).get("requirement_role") == "new_schedule"
        value = (slot_types if new_slot else recorded).get(ref) or {}
        type_ref = value.get("ref")
        types[ref] = {"ref": type_ref, "label": (slot_names_by_ref if new_slot else names_by_ref).get(type_ref)}
    standards = {row["operation_ref"]: _operation_standard(row["original"]["operation"], row["original"].get("execution"))
                 for row in rows}
    # A trial owns its saved current ledger. Its base ledger describes an earlier
    # arrangement; old saved trials retain an explicit missing decomposition.
    return saved["operation_effort"], types, standards


def _candidate_points(source):
    reader = CandidatePointReader(source.candidate, source.facts)
    return {row["payload"]["op_id"]: reader.work(row["operation_ref"], row["payload"])
            for row in source.raw_tasks if row["payload"]["start_time"] == row["payload"]["end_time"]}


def _trial_points(source):
    return {row["original"]["operation"]["id"]: {
                "witness": trial_point_evidence(row["original"], row["current"]),
                **{key: row["original"][key] for key in ("operation", "batch", "execution")}}
            for row in source[2] if row["current"]["start"] == row["current"]["end"]}


def _point_loader(source, load):
    def points():
        try:
            return load(source)
        except PointEventError as exc:
            raise WorkbenchCommandRejected("point_evidence_unproven", str(exc)) from exc
    return points


def decision_baseline_source_resolver(conn, *, candidate_provider=None):
    return verified_read(conn, ("decision_baseline_resolver", candidate_provider),
        lambda: _decision_baseline_source_resolver(conn, candidate_provider=candidate_provider))


def _decision_baseline_source_resolver(conn, *, candidate_provider):
    """Create one request's resolver over permanent candidate/scenario identities.

    The caller compares ``evidence.arranged`` with its captured Schedule rows.
    Sources are parsed once per permanent identity within the caller's read
    snapshot; metadata and point witnesses retain their saved source context.
    """
    sources = {}
    candidates = CandidateStore(conn)

    def resolve(*, plan_ref, version, history):
        key = ("decision_baseline_source", plan_ref, version, history.get("version"), history.get("result_summary"))
        return verified_read(conn, key, lambda: load(plan_ref=plan_ref, version=version, history=history))

    def load(*, plan_ref, version, history):
        # Every official version is written by a candidate or trial adoption together with its audit.
        _require_identity(history.get("version"), version)
        try:
            _, audit, _ = read_adoption_record(conn, plan_ref=plan_ref, version=version, history=history)
        except AdoptionBaselineUnavailable as exc:
            raise WorkbenchCommandRejected("adoption_snapshot_invalid", REASONS[exc.code]) from exc
        try:
            if audit["source"] == "workbench_candidate_adoption":
                key = ("candidate", audit["candidate_ref"])
                if key not in sources:
                    prepared = candidate_provider(audit["candidate_ref"]) if candidate_provider is not None else None
                    sources[key] = prepared if prepared is not None else read_candidate_source(candidates, audit["candidate_ref"])
                source = sources[key]
                evidence, points = candidate_evidence(source, audit), _candidate_points
            else:
                key = ("trial", audit["scenario_ref"])
                if key not in sources:
                    sources[key] = trial_adoption_facts(conn, audit["scenario_ref"])
                prepared = sources[key]
                source = prepared.source
                evidence, points = trial_evidence(source, audit), _trial_points
                evidence["trial_source"] = prepared
            deferred, deferred_issues = _deferred_evidence(source, evidence)
            effort, types, standards = _operation_metadata(source, evidence)
            return {"evidence": evidence, "origins": read_adoption_operation_facts(conn, evidence),
                    "point_work": _point_loader(source, points), "deferred_operation_ids": deferred,
                    "deferred_issues": deferred_issues, "operation_effort": effort, "operation_types": types,
                    "operation_standards": standards}
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            return _gap("adoption_source_archived", "此正式版本的原候选、试排场景或草稿已归档或删除。")
        except (KeyError, TypeError) as exc:
            raise WorkbenchCommandRejected(
                "adoption_snapshot_invalid", "此正式版本的采用资料缺少来源编号或原始安排字段。",
            ) from exc

    return resolve
