"""Resolve archived official lineage without reading today's official rows."""

import re

from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json

from .adoption_baseline_sources import read_adoption_operation_facts
from .candidate_facts import _entity_refs, _table
from .candidate_read_source import read_candidate_source
from .candidate_store import CandidateStore
from .candidate_values import stored_json
from .delivery_completeness import archived_deferred_operation_evidence
from .preflight_dependencies import material_deferred_ids
from .trial_scenario_archive import load_saved_scenario
from .zero_duration import PointEventError
from .zero_duration_evidence import CandidatePointReader, trial_point_evidence


def _gap(code, message):
    return {"origins": {}, "point_work": None, "issue": {"code": code, "message": message}}


def _require_identity(actual, expected):
    if canonical_json(actual) != canonical_json(expected):
        raise WorkbenchCommandRejected(
            "adoption_snapshot_invalid", "此正式版本的采用来源编号与保存资料不一致。",
        )


def _proof(audit, digest_fields):
    proof = audit["proof"]
    if type(proof) is not dict:
        raise WorkbenchCommandRejected("adoption_snapshot_invalid", "此正式版本的原采用凭据字段格式无效。")
    if proof.get("proof_version") == "content_refs_v1":
        return proof
    if proof.get("proof_version") is not None or any(
            type(proof.get(field)) is not str or re.fullmatch(r"[0-9a-f]{64}", proof[field]) is None
            for field in digest_fields + tuple(field for field in ("facts_hash", "validated_hash")
                                              if field in proof and field not in digest_fields)):
        raise WorkbenchCommandRejected("adoption_snapshot_invalid", "此正式版本的原采用凭据字段格式无效。")
    return proof


def _candidate_evidence(source, audit):
    _require_identity((source.candidate["candidate_ref"], source.run["run_ref"]),
                      (audit["candidate_ref"], audit["run_ref"]))
    _require_identity((source.capture["baseline"]["plan_ref"], source.capture["baseline"]["version"]),
                      (audit["baseline_ref"], audit["baseline_version"]))
    proof = _proof(audit, ("facts_hash", "baseline_hash", "candidate_hash"))
    _require_identity((proof["candidate_ref"], proof["run_ref"], proof["baseline_ref"], proof["baseline_version"]),
                      (audit["candidate_ref"], audit["run_ref"], source.capture["baseline"]["plan_ref"],
                       source.capture["baseline"]["version"]))
    if proof.get("proof_version") is None:
        _require_identity(proof["facts_hash"], source.capture["facts_hash"])
    return {"basis": "candidate_adoption", "audit": audit,
            "arranged": [row["payload"] for row in source.raw_tasks], "generation_facts": source.facts}


def _trial_evidence(source, audit):
    saved, head, rows = source
    _require_identity((saved["scenario_ref"], head["draft_ref"]),
                      (audit["scenario_ref"], audit["draft_ref"]))
    _require_identity((saved["baseline"]["plan_ref"], saved["baseline"]["version"]),
                      (audit["baseline_ref"], audit["baseline_version"]))
    proof = _proof(audit, ("scenario_hash", "admission_hash", "execution_hash", "baseline_hash", "rows_hash"))
    _require_identity((proof["scenario_ref"], proof["draft_ref"]),
                      (audit["scenario_ref"], audit["draft_ref"]))
    if proof.get("proof_version") is None:
        _require_identity(proof["admission_hash"], head["admission_hash"])
    else:
        _require_identity((proof["scenario_revision"], proof["baseline_ref"], proof["baseline_version"]),
                          (head["scenario_revision"], saved["baseline"]["plan_ref"], saved["baseline"]["version"]))
    arranged = [{"op_id": row["original"]["operation"]["id"],
                 "machine_id": row["current"]["machine_id"], "operator_id": row["current"]["operator_id"],
                 "start_time": row["current"]["start"], "end_time": row["current"]["end"]} for row in rows]
    return {"basis": "trial_adoption", "audit": audit, "arranged": arranged, "generation_facts": None}


def _source_deferred(scope, settings):
    if scope is not None:
        return material_deferred_ids(scope.values(), settings), []
    return archived_deferred_operation_evidence({"summary": {"material_policy": settings}})


def _deferred_evidence(source, evidence):
    audit = evidence["audit"]
    if evidence["basis"] == "candidate_adoption":
        ids, issues = _source_deferred(source.disposition, source.capture["input"])
    else:
        original = source[1]["admission"]["source"]
        if "deferred_operation_ids" in original:
            ids, issues = archived_deferred_operation_evidence({"summary": original})
            issues = sorted(set(issues + original.get("deferred_operation_issues", [])))
        else:
            settings = original.get("capture", {}).get("input", original.get("material_policy", {}))
            ids, issues = _source_deferred(original.get("dispositions"), settings)
    recorded, recorded_issues = archived_deferred_operation_evidence({"summary": audit})
    if "deferred_operation_evidence_invalid" in recorded_issues:
        return [], recorded_issues
    if audit.get("deferred_operation_ids") is not None:
        if not issues and recorded != ids:
            return [], ["deferred_operation_evidence_invalid"]
        return sorted(recorded), []
    return sorted(ids), issues


def _operation_type(operation, refs, names, trace=None):
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
        names = {row["op_type_id"]: row.get("name") for row in _table(source.facts.archive, "OpTypes") or []}
        operations = {ref: source.facts.tables["BatchOperations"][op_id]
                      for ref, op_id in source.facts.operations.items() if op_id in source.facts.tables["BatchOperations"]}
        types = {ref: _operation_type(operation, source.facts.entity_refs, names, traces.get(operation["id"]))
                 for ref, operation in operations.items()}
        standards = {ref: _operation_standard(operation, source.facts.execution.get(ref))
                     for ref, operation in operations.items()}
        return (source.receipt or {}).get("operation_effort"), types, standards
    saved, head, rows = source
    original = head["admission"]["source"]
    capture = original.get("capture")
    if capture is not None:
        archive = stored_json(capture["facts_text"])
        refs = _entity_refs(archive)
        names = {row["op_type_id"]: row.get("name") for row in _table(archive, "OpTypes") or []}
    else:
        tables = head["admission"]["facts"]["tables"]
        refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables.get("WorkbenchEntityRefs", [])
                if row["active"] == 1}
        names = {row["op_type_id"]: row.get("name") for row in tables.get("OpTypes", [])}
    names_by_ref = _type_names_by_ref(refs, names)
    tables = head["admission"]["facts"]["tables"]
    slot_refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables.get("WorkbenchEntityRefs", [])
                 if row["active"] == 1}
    slot_names = {row["op_type_id"]: row.get("name") for row in tables.get("OpTypes", [])}
    slot_names_by_ref = _type_names_by_ref(slot_refs, slot_names)
    recorded, slot_types = original.get("operation_types") or {}, original.get("trial_operation_types") or {}
    ledger = {item["operation_ref"]: item for item in (saved.get("operation_effort") or {}).get("items", [])}
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
    return saved.get("operation_effort"), types, standards


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


def decision_baseline_source_resolver(conn):
    """Create one request's resolver over permanent candidate/scenario identities.

    The caller compares ``evidence.arranged`` with its captured Schedule rows.
    Sources are parsed once per permanent identity within the caller's read
    snapshot; metadata and point witnesses retain their saved source context.
    """
    sources = {}
    candidates = CandidateStore(conn)

    def resolve(*, plan_ref, version, history):
        parsed = parse_result_summary_payload(history.get("result_summary"))
        audit = parsed.payload
        if parsed.parse_failed:
            return _gap("adoption_snapshot_invalid", "此正式版本的采用摘要格式无效。")
        if audit is None or audit.get("source") not in ("workbench_candidate_adoption", "workbench_trial_adoption"):
            return _gap("adoption_not_recorded", "此正式版本没有保存候选或试排采用来源。")
        _require_identity((audit.get("version"), history.get("version")), (version, version))
        try:
            if audit["source"] == "workbench_candidate_adoption":
                key = ("candidate", audit["candidate_ref"])
                if key not in sources:
                    sources[key] = read_candidate_source(candidates, audit["candidate_ref"])
                source = sources[key]
                evidence, points = _candidate_evidence(source, audit), _candidate_points
            else:
                key = ("trial", audit["scenario_ref"])
                if key not in sources:
                    sources[key] = load_saved_scenario(conn, audit["scenario_ref"])
                source = sources[key]
                evidence, points = _trial_evidence(source, audit), _trial_points
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
