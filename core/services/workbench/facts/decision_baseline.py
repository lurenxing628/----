"""An admission's last official arrangement for every permanent operation.

The original admission baseline still describes the latest version only. This
projection keeps that capture intact and selects each operation's last version
from its archived Schedule rows. Optional adoption evidence is resolved by those
archived plan identities, never by a current business-entity lookup.
"""

from collections import defaultdict

from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_run_candidate import MAX_TASKS, local_time, reference
from core.services.workbench.facts.adoption_baseline_values import REASONS, AdoptionBaselineUnavailable
from core.services.workbench.facts.delivery_completeness import archived_deferred_operation_evidence

from .candidate_baseline import AdmissionBaseline, ArchivedAdmissionPlan, invalid_baseline
from .candidate_facts import _index
from .candidate_tasks import operation_labels
from .candidate_values import bounded_size, gap
from .operation_effort_evidence import saved_operation_efforts


def _last_official_rows(rows, version):
    """Retain all segments of each operation's last archived official version."""
    _index(rows, "id")
    latest = {}
    for row in rows:
        op, saved_version = row.get("op_id"), row.get("version")
        if (type(op) is not int or op < 1 or type(row["id"]) is not int or row["id"] < 1
                or type(saved_version) is not int or saved_version < 1):
            invalid_baseline()
        if saved_version <= version:
            latest[op] = max(saved_version, latest.get(op, 0))
    result = [row for row in rows if latest.get(row["op_id"]) == row["version"]]
    bounded_size(len(result), MAX_TASKS)
    return sorted(result, key=lambda row: (row["op_id"], row["id"]))


def _official_sources(admission, versions):
    plans, histories = defaultdict(list), defaultdict(list)
    for row in admission.sources:
        if row.get("kind") == "official" and row.get("active") == 1:
            plans[row.get("version")].append(row)
    for row in admission.history:
        histories[row["version"]].append(row)
    result = {}
    for version in sorted(versions):
        if len(plans[version]) != 1 or len(histories[version]) != 1:
            invalid_baseline()
        plan, history = plans[version][0], histories[version][0]
        plan_ref = reference(plan.get("ref"), stored=True)
        result[version] = {"version": version, "plan_ref": plan_ref, "history_record": {
            "version": version, "result_summary": history.get("result_summary"),
            "result_status": history.get("result_status")}}
    return result


def _adoption_identity(source):
    parsed = parse_result_summary_payload(source["history_record"]["result_summary"])
    audit, gaps = parsed.payload, []
    candidate, run = None, None
    if parsed.parse_failed:
        gaps.append({"field": "history_record.result_summary", "code": "completion_summary_invalid",
                     "message": "此正式版本的结果摘要格式无效。"})
    elif audit is None:
        gaps.append({"field": "history_record.result_summary", "code": "completion_summary_missing",
                     "message": "此正式版本没有保存结果摘要。"})
    elif audit.get("source") == "workbench_candidate_adoption":
        candidate = reference(audit.get("candidate_ref"), stored=True)
        run = reference(audit.get("run_ref"), stored=True)
    return {**source, "source_candidate_ref": candidate, "source_run_ref": run, "data_gaps": gaps}, audit


def _arrangement(row):
    return (row["op_id"], row.get("machine_id"), row.get("operator_id"),
            local_time(row["start_time"].replace(" ", "T", 1)),
            local_time(row["end_time"].replace(" ", "T", 1)))


def _same_arrangements(saved, arranged):
    if type(arranged) is not list or len(saved) != len(arranged):
        return False
    try:
        # Multiple segments of the same operation remain separate arrangements.
        return sorted((_arrangement(row) for row in saved), key=repr) == sorted(
            (_arrangement(row) for row in arranged), key=repr)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _resolved_source(source, audit, resolver, saved):
    missing = {"code": "adoption_not_recorded", "message": "此正式版本缺少可核对的原采用资料。"}
    if resolver is None:
        return {"available": False, "origins": {}, "point_work": None, "issue": missing}
    try:
        value = resolver(plan_ref=source["plan_ref"], version=source["version"], history=source["history_record"])
    except AdoptionBaselineUnavailable as exc:
        return {"available": False, "origins": {}, "point_work": None,
                "issue": {"code": exc.code, "message": REASONS[exc.code], "missing_fact": exc.gap}}
    except WorkbenchCommandRejected as exc:
        if exc.code not in ("entity_not_found", "adoption_source_archived", "adoption_snapshot_invalid"):
            raise
        code = "adoption_source_archived" if exc.code == "entity_not_found" else exc.code
        return {"available": False, "origins": {}, "point_work": None,
                "issue": {"code": code, "message": REASONS[code]}}
    evidence = value.get("evidence")
    if evidence is not None and (canonical_json(evidence.get("audit")) != canonical_json(audit)
                                 or evidence["audit"].get("version") != source["version"]):
        invalid_baseline()
    if evidence is not None and not _same_arrangements(saved, evidence.get("arranged")):
        return {"available": False, "origins": {}, "point_work": None,
                "issue": {"code": "adoption_plan_drift", "message": REASONS["adoption_plan_drift"]}}
    return {"available": evidence is not None, "origins": value.get("origins", {}) if evidence is not None else {},
            "point_work": value.get("point_work") if evidence is not None else None,
            "deferred_operation_ids": value.get("deferred_operation_ids") if evidence is not None else None,
            "deferred_issues": value.get("deferred_issues", []) if evidence is not None else [],
            "operation_effort": value.get("operation_effort") if evidence is not None else None,
            "operation_types": value.get("operation_types", {}) if evidence is not None else {},
            "operation_standards": value.get("operation_standards", {}) if evidence is not None else {},
            "issue": value.get("issue") or missing}


def _deferred_source(source, resolved):
    ids, issues = archived_deferred_operation_evidence({"summary": source["history_record"]["result_summary"]})
    original, source_issues = resolved.get("deferred_operation_ids"), resolved.get("deferred_issues", [])
    if "deferred_operation_evidence_invalid" in issues + source_issues:
        ids, issues = set(), ["deferred_operation_evidence_invalid"]
    elif original is not None:
        if type(original) not in (list, set, tuple) or any(type(value) is not int or value < 1 for value in original):
            invalid_baseline()
        ids |= set(original)
        issues = [code for code in issues if code != "deferred_operation_evidence_missing"] + source_issues
    messages = {"deferred_operation_evidence_invalid": "此正式版本的待料工序编号与原采用资料不一致或格式无效。",
                "deferred_operation_evidence_missing": "此正式版本声明分段待料，但缺少原采用时的待排工序编号。",
                "deferred_operation_evidence_unavailable": "此正式版本的原待料工序资料读取失败。"}
    source["deferred_operation_ids"] = sorted(ids)
    source["data_gaps"].extend({"field": "deferred_operation_ids", "code": code, "message": messages[code]}
                               for code in sorted(set(issues)))
    return ids


def _bindings(admission, rows, sources):
    saved, tasks = admission._schedule_bindings, admission.tasks
    task_pairs = {(row.get("plan_ref"), row.get("row_ref")): row["ref"] for row in tasks.values()}
    if len(task_pairs) != len(tasks):
        invalid_baseline()
    result = []
    for row in rows:
        if type(row.get("id")) is not int:
            invalid_baseline()
        matches = saved[(row["version"], str(row["id"]))]
        if len(matches) != 1:
            invalid_baseline()
        binding = matches[0]
        ref, row_ref = (reference(binding.get(key), stored=True) for key in ("operation_ref", "ref"))
        plan_ref = sources[row["version"]]["plan_ref"]
        task_ref = task_pairs.get((plan_ref, row_ref))
        if (admission.facts.operations.get(ref) != row["op_id"]
                or row["op_id"] not in admission.facts.tables["BatchOperations"]
                or binding.get("operation_id") != row["op_id"] or binding.get("source_table") != "schedule"
                or task_ref is None):
            invalid_baseline()
        result.append({**row, "row_ref": row_ref, "operation_ref": ref,
                       "plan_ref": plan_ref, "task_ref": reference(task_ref, stored=True)})
    return result


def _locked(row, gaps):
    value = row.get("lock_status")
    if value not in ("locked", "unlocked"):
        gaps.append(gap("locked", "not_recorded" if value is None else "invalid_stored_value"))
        return None
    return value == "locked"


def _adopted_resource_identity(segment, origin, gaps):
    for kind in ("machine", "operator"):
        adopted, admitted = origin.get(kind), segment[kind]
        if adopted is None or adopted.get("ref") is None:
            continue
        if admitted is not None and adopted["ref"] == admitted.get("ref"):
            continue
        segment[kind] = {"ref": adopted["ref"], "label": adopted.get("label")}
        resolved_fields = {kind, kind + ".ref"}
        if adopted.get("label") is not None:
            resolved_fields.add(kind + ".label")
        gaps[:] = [item for item in gaps if item["field"] not in resolved_fields]
        if adopted.get("label") is None and not any(item["field"] == kind + ".label" for item in gaps):
            gaps.append(gap(kind + ".label", "source_missing"))
        name = "设备" if kind == "machine" else "人员"
        gaps.append({"field": kind + ".admission_identity", "code": "resource_identity_changed_before_admission",
                     "message": "受理资料缺少原" + name + "身份，此处保留原采用资料中的编号和名称。"})


def _task(admission, row, operation_type):
    labels, _ = operation_labels(admission.facts, row["operation_ref"])
    segment = admission._segment(row)
    gaps = labels["data_gaps"] + segment["data_gaps"]
    _adopted_resource_identity(segment, admission._origins.get(row["op_id"], {}), gaps)
    execution = labels["execution_at_generation"]
    if execution is not None:
        saved = admission.facts.execution[row["operation_ref"]]
        execution.update({key: saved[key] for key in (
            "first_actual_start", "confirmed_finish", "unknown_record_count", "records_complete",
            "quantity_complete", "completion_basis")})
    return {**labels, **segment, "data_gaps": gaps, "locked": _locked(row, gaps),
            "process_type_ref": operation_type.get("ref"), "process_type_label": operation_type.get("label"),
            "plan_ref": row["plan_ref"], "task_ref": row["task_ref"], "official_version": row["version"]}


def _effort_source(source, audit):
    value = {"plan_ref": source["plan_ref"], "version": source["version"]}
    if type(audit) is dict and audit.get("source") == "workbench_candidate_adoption":
        return {**value, "kind": "run", "run_ref": source["source_run_ref"], "candidate_ref": source["source_candidate_ref"]}
    if type(audit) is dict and audit.get("source") == "workbench_trial_adoption":
        return {**value, "kind": "trial", "scenario_ref": audit.get("scenario_ref")}
    return {**value, "kind": "admission_official"}


def _official_identity(admission):
    baseline, version = admission.baseline, admission.baseline["version"]
    return {"kind": "admission_official", "baseline_ref": baseline["plan_ref"],
            "plan_ref": baseline["plan_ref"], "version": version,
            "label": "排产时的正式计划 v" + str(version) if version is not None else "排产时无正式计划",
            "state": "available" if version is not None else "absent",
            "source_candidate_ref": None, "source_run_ref": None}


def _official_plan_rows(admission):
    version = admission.baseline["version"]
    if version is None:
        return [], {}
    rows = _last_official_rows(admission.schedule, version)
    sources = _official_sources(admission, {row["version"] for row in rows} | {version})
    return _bindings(admission, rows, sources), sources


def read_decision_baseline_members(capture, facts):
    """Read verified permanent official members without rebuilding execution DTOs."""
    admission = ArchivedAdmissionPlan(capture, facts)
    identity = _official_identity(admission)
    rows, sources = _official_plan_rows(admission)
    for version, source in sources.items():
        source, _ = _adoption_identity(source)
        if version == admission.baseline["version"]:
            identity.update({key: source[key] for key in ("source_candidate_ref", "source_run_ref")})
    return {"identity": identity, "operation_refs": sorted({row["operation_ref"] for row in rows})}


def read_decision_baseline(capture, facts, disposition, accepted_at, *, source_resolver=None):
    """Project a verified admission without mutating it or consulting live entities.

    ``source_resolver`` is called once per archived version with keyword arguments
    ``plan_ref``, ``version``, ``history``. It returns ``evidence`` from the existing
    adoption reader, ``origins`` from its operation-facts reader and ``point_work``
    from its point reader (a mapping or deferred callable). Missing original
    sources are reported as task data gaps; permanent binding mismatches reject
    the archive. Labels use admission metadata; replaced resource identities keep
    their recorded adoption identities and names with an explicit data gap. Source,
    supplier and point witnesses use original adoption work. The caller owns any
    resolver's read snapshot.
    """
    admission = AdmissionBaseline(capture, facts, disposition, accepted_at)
    version = admission.baseline["version"]
    identity = _official_identity(admission)
    if version is None:
        return {"identity": identity, "tasks": [], "source_refs": [], "source_states": [], "deferred_operation_ids": [],
                "operation_efforts": {}, "operation_standards": {}, "operation_types": {}}
    schedule = admission.schedule
    bound, sources = _official_plan_rows(admission)
    tasks, source_refs = [], []
    source_states = []
    deferred_ids = set()
    effort_by_ref, standards_by_ref, types_by_ref = {}, {}, {}
    by_version = defaultdict(list)
    for row in bound:
        by_version[row["version"]].append(row)
    for selected_version, source in sources.items():
        source, audit = _adoption_identity(source)
        saved = [row for row in schedule if row["version"] == selected_version]
        resolved = _resolved_source(source, audit, source_resolver, saved)
        source_states.append({"plan_ref": source["plan_ref"], "version": selected_version,
            "source_kind": audit.get("source") if isinstance(audit, dict) else "legacy_official",
            "source_candidate_ref": source.get("source_candidate_ref"), "source_run_ref": source.get("source_run_ref"),
            "source_scenario_ref": audit.get("scenario_ref") if isinstance(audit, dict) else None,
            "source_draft_ref": audit.get("draft_ref") if isinstance(audit, dict) else None,
            "available": resolved["available"], "issue_code": None if resolved["available"] else resolved["issue"]["code"]})
        deferred_ids.update(_deferred_source(source, resolved))
        admission._origins, admission._origin_issue = resolved["origins"], resolved["issue"]
        work = resolved["point_work"]
        admission._point_work_loader = work if callable(work) else lambda work=work: work or {}
        admission._point_work = None
        efforts = saved_operation_efforts(resolved.get("operation_effort"))
        effort_source = _effort_source(source, audit)
        types, standards = resolved.get("operation_types", {}), resolved.get("operation_standards", {})
        for row in by_version[selected_version]:
            ref = row["operation_ref"]
            effort = efforts.get(ref)
            if effort is not None:
                if effort["op_id"] != row["op_id"]:
                    invalid_baseline()
                effort_by_ref[ref] = {"effort": effort, "evidence_source": effort_source}
            if ref in standards:
                standards_by_ref[ref] = {**standards[ref], "evidence_source": effort_source}
            if ref in types:
                types_by_ref[ref] = types[ref]
            tasks.append(_task(admission, row, types.get(ref, {})))
        source_refs.append(source)
        if selected_version == version:
            identity.update({key: source[key] for key in ("source_candidate_ref", "source_run_ref")})
    tasks.sort(key=lambda row: (row["operation_ref"], row["official_version"], row["row_ref"]))
    return {"identity": identity, "tasks": tasks, "source_refs": source_refs, "source_states": source_states,
            "deferred_operation_ids": sorted(deferred_ids), "operation_efforts": effort_by_ref,
            "operation_standards": standards_by_ref, "operation_types": types_by_ref}
