"""Compare saved production conditions by business responsibility and identity.

These projections read verified historical packets only. Archive revisions,
capture times and journal identities locate evidence; they are not production
conditions. Experimental settings have their own projection and objective gate.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from core.models.resource_capabilities import machine_type_index, supports_source
from core.services.capacity.plan_calendar_intervals import instant
from core.services.common.enum_normalizers import skill_rank
from core.services.workbench.trial.archived_external_context import archived_contexts
from core.shared.boolean_normalize import to_yes_no

from .conditions_source import ConditionSource

_MISSING = object()
_CATEGORIES = (("scope", "排产范围"), ("batch", "批次交期与数量"), ("requirements", "工序标准需求"),
               ("materials_outsource", "物料与外协"), ("calendar_downtime", "有效日历与停机"),
               ("resource_qualifications", "资源与人员资格"), ("execution_baseline", "报工与正式原安排"),
               ("freeze", "不重排窗口与成员"))
_CONFIG_KEYS = ("sort_strategy", "priority_weight", "due_weight", "ready_weight", "prefer_primary_skill",
                "dispatch_mode", "dispatch_rule", "ortools_enabled", "ortools_time_limit_seconds", "algo_mode",
                "time_budget_seconds", "objective", "graph_analysis_mode", "graph_block_on_cycle",
                "graph_critical_weight", "graph_impact_weight", "graph_downstream_weight",
                "graph_candidate_weight_count", "graph_selection_policy", "graph_overdue_tolerance_count",
                "graph_tardiness_tolerance_ratio")


def _reason(code="not_recorded", message="原保存资料缺少这一项，条件未知。"):
    return {"code": code, "message": message}


def _side(source, value=_MISSING, *, present=True, nullable=False, reason=None):
    known = value is not _MISSING and (value is not None or nullable or not present)
    return {"present": present, "state": "known" if known else "unknown", "value": value if known else None,
            "source": source, "reason": None if known else reason or _reason()}


class _Projection:
    def __init__(self, source):
        self.source, self.rows, self.families = source, {}, {}

    def declare(self, category, family, path, known, *, origin="environment", reason=None):
        provenance = self.source.source(path, origin)
        self.families[family] = (known, provenance, reason)
        if not known:
            self.add(category, family, "保存资料", "availability", _MISSING, path, family,
                     origin=origin, reason=reason)

    def add(self, category, entity, label, field, value, path, family, *, origin="environment", nullable=False,
            reason=None, present=True):
        self.rows[category, entity, field] = {"category": category, "entity": {"key": entity, "label": label},
            "field": field, "family": family, "side": _side(self.source.source(path, origin), value,
                nullable=nullable, reason=reason, present=present)}

    def fields(self, category, entity, label, row, fields, path, family, *, origin="environment", nullable=()):
        for field in fields:
            self.add(category, entity, label, field, row.get(field, _MISSING), path + "." + field, family,
                     origin=origin, nullable=field in nullable)

    def absent(self, row):
        known, source, reason = self.families.get(row["family"], (False, self.source.source(""), None))
        return _side(source, None if known else _MISSING, present=False, reason=reason)


def _state(counts):
    return "different" if counts["different"] else "unknown" if counts["unknown"] else "equal"


def _compare(before, after, categories):
    rows = []
    rank = {key: index for index, (key, _) in enumerate(categories)}
    summary = dict.fromkeys(("equal", "different", "unknown"), 0)
    category_counts = {key: dict(summary) for key, _ in categories}
    for key in sorted(set(before.rows) | set(after.rows), key=lambda key: (rank.get(key[0], 99), key[1:])):
        left, right = before.rows.get(key), after.rows.get(key)
        row = left or right
        previous, current = (left["side"] if left else before.absent(row)), (right["side"] if right else after.absent(row))
        state = "unknown" if "unknown" in (previous["state"], current["state"]) else (
            "equal" if (previous["present"], previous["value"]) == (current["present"], current["value"]) else "different")
        rows.append({key: row[key] for key in ("category", "entity", "field")})
        rows[-1].update(state=state, before=previous, after=current)
        summary[state] += 1
        if row["category"] in category_counts:
            category_counts[row["category"]][state] += 1
    groups = [{"key": key, "label": label, "state": _state(category_counts[key]), "summary": category_counts[key]}
              for key, label in categories]
    return {"state": _state(summary), "summary": summary, "categories": groups, "rows": rows,
            "page": {"number": 1, "size": len(rows), "total": len(rows), "has_more": False}}


def _table(source, name, *, original=False, introduced=None):
    rows = source.original_table(name) if original else source.table(name)
    if rows is None and introduced is not None and source.calendar.version is not None and source.calendar.version < introduced:
        return []
    return rows


def _reference(source, kind, key, *, original=False):
    if key is None:
        return None
    refs = source.original_entity_refs if original else source.entity_refs
    return refs.get((kind, str(key)), _MISSING)


def _ref_key(value, fallback):
    return value if type(value) is str else "unknown:" + str(fallback)


def _ref_field(projection, category, entity, label, row, field, kind, path, family, *, original=False):
    value = _reference(projection.source, kind, row[field], original=original) if field in row else _MISSING
    projection.add(category, entity, label, field, value, path + "." + field, family,
                   origin="original" if original else "environment", nullable=True)


def _config(source):
    rows = source.table("ScheduleConfig") or []
    return {row["config_key"]: (row.get("config_value", _MISSING), "tables.ScheduleConfig[" + str(index) + "].config_value")
            for index, row in enumerate(rows)}


def _scope(projection):
    source = projection.source
    selected = source.input.get("batch_refs", _MISSING) if source.kind == "run" else list(source.batches)
    known = type(selected) is list
    projection.declare("scope", "selected_batches", "batch_refs", known, origin="input")
    batches = {ref: source.batches[ref] for ref in selected if ref in source.batches} if known else {}
    batch_ids = {batch.get("batch_id") for batch in batches.values()}
    operations = {ref: row for ref, row in source.operations.items() if row.get("batch_id") in batch_ids}
    projection.declare("scope", "selected_operations", "tables.BatchOperations", known and source.original_table("BatchOperations") is not None,
                       origin="original")
    for ref in selected if known else []:
        projection.add("scope", ref, (batches.get(ref) or {}).get("batch_id", ref), "batch_member", True,
                       "batch_refs", "selected_batches", origin="input")
        if ref not in batches:
            projection.add("batch", ref, ref, "batch_facts", _MISSING, "batches." + ref, "selected_batches",
                           origin="original", reason=_reason("selected_batch_missing", "原保存范围中的批次事实缺失。"))
    for ref, row in operations.items():
        projection.add("scope", ref, row.get("op_code", ref), "operation_member", True,
                       "operations." + ref, "selected_operations", origin="original")
    for field in ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy", "material_strategy"):
        value = source.input.get(field, _MISSING)
        # Strict was the saved call contract before the material-strategy key existed.
        if field == "material_strategy" and value is _MISSING:
            value = "strict"
        projection.add("scope", "planning", "本次排产", field, value, field, "planning", origin="input")
    projection.declare("scope", "planning", "", True, origin="input")
    return batches, operations


def _work(projection, batches, operations):
    source = projection.source
    projection.declare("batch", "batch_facts", "tables.Batches", source.original_table("Batches") is not None, origin="original")
    projection.declare("requirements", "operation_facts", "tables.BatchOperations", source.original_table("BatchOperations") is not None, origin="original")
    for ref, row in batches.items():
        projection.fields("batch", ref, row.get("batch_id", ref), row,
            ("quantity", "due_date", "priority", "ready_status", "ready_date", "status"), "batches." + ref,
            "batch_facts", origin="original", nullable=("due_date", "ready_date"))
        _ref_field(projection, "batch", ref, row.get("batch_id", ref), row, "part_no", "part",
                   "batches." + ref, "batch_facts", original=True)
    for ref, row in operations.items():
        label, path = row.get("op_code", ref), "operations." + ref
        projection.fields("requirements", ref, label, row,
            ("piece_id", "seq", "source", "status"), path, "operation_facts",
            origin="original", nullable=("piece_id",))
        for field in ("setup_hours", "unit_hours"):
            value = row.get(field, _MISSING)
            # External work has a saved cycle, rather than factory standard hours.
            # A missing column still leaves the archived requirement unproven.
            external = row.get("source") == "external"
            projection.add("requirements", ref, label, field, None if external and value is not _MISSING else value,
                           path + "." + field, "operation_facts", origin="original", nullable=external)
        for field, kind in (("op_type_id", "op_type"), ("machine_id", "machine"), ("operator_id", "operator"), ("supplier_id", "supplier")):
            _ref_field(projection, "requirements", ref, label, row, field, kind, path, "operation_facts", original=True)
        if row.get("source") == "external":
            projection.add("requirements", ref, label, "ext_days", row.get("ext_days", _MISSING), path + ".ext_days",
                           "operation_facts", origin="original", nullable=True)


def _materials(projection, batches, operations):
    source, category = projection.source, "materials_outsource"
    requirements = source.table("BatchMaterials")
    projection.declare(category, "materials", "tables.BatchMaterials", requirements is not None)
    by_batch = {row["batch_id"]: ref for ref, row in batches.items()}
    by_op = {row["id"]: ref for ref, row in operations.items()}
    reviews = _table(source, "BatchMaterialReviews", introduced=36)
    stages = _table(source, "BatchMaterialStages", introduced=36)
    arrivals = _table(source, "BatchMaterialArrivals", introduced=36)
    for name, rows in (("BatchMaterialReviews", reviews), ("BatchMaterialStages", stages), ("BatchMaterialArrivals", arrivals)):
        if requirements and any(row.get("batch_id") in by_batch for row in requirements):
            projection.declare(category, name, "tables." + name, rows is not None)
    review_index = {row["requirement_id"]: (index, row) for index, row in enumerate(reviews or [])}
    stage_index = {row["requirement_id"]: (index, row) for index, row in enumerate(stages or [])}
    arrivals_by_requirement = defaultdict(list)
    for arrival in arrivals or []:
        arrivals_by_requirement[arrival.get("requirement_id")].append(arrival)
    for index, row in enumerate(requirements or []):
        batch_ref = by_batch.get(row.get("batch_id"))
        if batch_ref is None:
            continue
        material = _reference(source, "material", row.get("material_id"))
        entity = batch_ref + ":material:" + _ref_key(material, row.get("material_id"))
        label, path = row.get("material_id", entity), "tables.BatchMaterials[" + str(index) + "]"
        projection.add(category, entity, label, "material_ref", material, path + ".material_id", "materials")
        projection.fields(category, entity, label, row, ("required_qty", "available_qty", "ready_status"), path, "materials")
        review = review_index.get(row["id"])
        projection.add(category, entity, label, "reviewed_quantity", review[1].get("batch_quantity", _MISSING) if review else (
            None if reviews is not None else _MISSING), "tables.BatchMaterialReviews" + ("[" + str(review[0]) + "].batch_quantity" if review else ""),
            "materials", nullable=review is None)
        stage = stage_index.get(row["id"])
        projection.add(category, entity, label, "use_operation_ref", by_op.get(stage[1]["operation_id"], _MISSING) if stage else (
            None if stages is not None else _MISSING), "tables.BatchMaterialStages" + ("[" + str(stage[0]) + "].operation_id" if stage else ""),
            "materials", nullable=True)
        amounts = defaultdict(Decimal)
        for arrival in arrivals_by_requirement.get(row["id"], []):
            amounts[arrival["arrival_date"]] += Decimal(str(arrival["quantity"]))
        projection.declare(category, "arrivals:" + entity, "tables.BatchMaterialArrivals", arrivals is not None)
        for day, amount in sorted(amounts.items()):
            projection.add(category, entity + ":arrival:" + day, label + " " + day, "quantity", float(amount),
                           "tables.BatchMaterialArrivals", "arrivals:" + entity)
    contexts = source.original_table("BatchExternalContexts")
    external = {row["id"]: ref for ref, row in operations.items() if row.get("source") == "external"}
    context_path = "tables.BatchExternalContexts"
    if external and contexts is None:
        contexts = archived_contexts(source.original_archive, set(external))
        if contexts is not None:
            context_path = "tables"
    if external:
        projection.declare(category, "external_contexts", context_path, contexts is not None, origin="original")
        captured = {row.get("operation_id") for row in contexts or []}
        for key in set(external) - captured:
            ref = external[key]
            projection.add(category, ref, operations[ref].get("op_code", ref), "external_context", _MISSING,
                           context_path, "external_contexts", origin="original",
                           reason=_reason("external_context_not_saved", "选中外协工序的原周期与合并关系未保存。"))
    for index, row in enumerate(contexts or []):
        ref = external.get(row.get("operation_id"))
        if ref is None:
            continue
        path = context_path + "[" + str(index) + "]" if context_path != "tables" else "tables"
        label = operations[ref].get("op_code", ref)
        for field in ("part_no", "sequence", "start_sequence", "end_sequence", "merge_mode", "total_days", "group_ref"):
            projection.add(category, ref, label, field, row.get(field, _MISSING), path + "." + field if context_path != "tables" else path,
                "external_contexts", origin="original", nullable=field in ("start_sequence", "end_sequence", "merge_mode", "total_days", "group_ref"))
        supplier_ref = _reference(source, "supplier", row["supplier_id"], original=True) if "supplier_id" in row else _MISSING
        projection.add(category, ref, label, "supplier_id", supplier_ref,
                       path + ".supplier_id" if context_path != "tables" else path, "external_contexts", origin="original", nullable=True)
    suppliers = source.table("Suppliers")
    selected_suppliers = {row.get("supplier_id") for row in operations.values() if row.get("source") == "external"}
    selected_suppliers.update(row.get("supplier_id") for row in contexts or [] if row.get("operation_id") in external)
    selected_suppliers.discard(None)
    if selected_suppliers:
        projection.declare(category, "suppliers", "tables.Suppliers", suppliers is not None)
        saved_suppliers = {row.get("supplier_id") for row in suppliers or []}
        for key in selected_suppliers - saved_suppliers:
            projection.add(category, _ref_key(_reference(source, "supplier", key), key), key, "supplier_facts", _MISSING,
                           "tables.Suppliers", "suppliers", reason=_reason("supplier_not_saved", "选中外协供应商的原资料未保存。"))
    for index, row in enumerate(suppliers or []):
        if row.get("supplier_id") in selected_suppliers:
            ref = _reference(source, "supplier", row["supplier_id"])
            projection.fields(category, _ref_key(ref, row["supplier_id"]), row.get("name", row["supplier_id"]), row,
                ("status", "default_days"), "tables.Suppliers[" + str(index) + "]", "suppliers")


def _resources(projection, operations):
    source, category = projection.source, "resource_qualifications"
    machines, operators, types = source.table("Machines"), source.table("Operators"), source.table("OpTypes")
    capabilities = _table(source, "MachineOpTypes", introduced=35)
    links, profiles, skills = source.table("OperatorMachine"), source.table("WorkbenchOperatorProfiles"), source.table("OperatorSkill")
    needed = {row.get("op_type_id") for row in operations.values() if row.get("source") == "internal"}
    assigned_machines = {row.get("machine_id") for row in operations.values()} - {None}
    assigned_operators = {row.get("operator_id") for row in operations.values()} - {None}
    for name, rows in (("Machines", machines), ("Operators", operators), ("OpTypes", types), ("MachineOpTypes", capabilities),
                       ("OperatorMachine", links), ("WorkbenchOperatorProfiles", profiles), ("OperatorSkill", skills)):
        if needed:
            projection.declare(category, name, "tables." + name, rows is not None)
    type_rows = {row["op_type_id"]: row for row in types or []}
    supported = {key for key in needed if key in type_rows and supports_source(type_rows[key].get("category"), "internal")}
    for key in sorted(needed - {None}):
        row, ref = type_rows.get(key, {}), _reference(source, "op_type", key)
        projection.add(category, _ref_key(ref, key), row.get("name", key), "internal_work_type_eligible",
                       supports_source(row["category"], "internal") if "category" in row else _MISSING,
                       "tables.OpTypes", "OpTypes")
    machine_types = machine_type_index(machines or [], capabilities or [])
    relevant_machines = {row["machine_id"] for row in machines or [] if row["machine_id"] in assigned_machines or (
        row.get("status") == "active" and machine_types[row["machine_id"]] & supported)}
    profile_index = {row["operator_id"]: row for row in profiles or []}
    operator_index = {row["operator_id"]: row for row in operators or []}
    skill_index = defaultdict(set)
    for row in skills or []:
        skill_index[row["operator_id"]].add(row["op_type_id"])
    qualifications = {row["operator_id"]: (skill_index[row["operator_id"]] if skill_index[row["operator_id"]] or
        profile_index.get(row["operator_id"], {}).get("skills_declared") == 1 else None) for row in operators or []}
    relevant_links = []
    for index, row in enumerate(links or []):
        if row.get("machine_id") in relevant_machines and operator_index.get(row.get("operator_id"), {}).get("status") == "active":
            qualification = qualifications.get(row["operator_id"])
            if qualification is None or machine_types[row["machine_id"]] & supported & qualification:
                relevant_links.append((index, row))
    relevant_operators = assigned_operators | {row["operator_id"] for _, row in relevant_links}
    known = not needed or (all(rows is not None for rows in (machines, operators, types, capabilities, links, profiles, skills))
                           and None not in needed and all("category" in type_rows.get(key, {}) for key in needed))
    projection.declare(category, "resources", "tables.Machines", known)
    result = []
    for kind, rows, selected in (("machine", machines, relevant_machines), ("operator", operators, relevant_operators)):
        for index, row in enumerate(rows or []):
            saved_id = row[kind + "_id"]
            if saved_id not in selected:
                continue
            ref, label, path = _reference(source, kind, saved_id), row.get("name", saved_id), "tables." + ("Machines" if kind == "machine" else "Operators") + "[" + str(index) + "]"
            entity = _ref_key(ref, kind + ":" + saved_id)
            projection.add(category, entity, label, "resource_ref", ref, path + "." + kind + "_id", "resources")
            projection.fields(category, entity, label, row, ("status",), path, "resources")
            if ref is not _MISSING:
                result.append({"kind": kind, "ref": ref, "label": label, "saved_id": saved_id})
            if kind == "machine":
                for key in sorted(machine_types[saved_id] & supported):
                    type_ref = _reference(source, "op_type", key)
                    projection.add(category, entity + ":type:" + _ref_key(type_ref, key), label, "work_type_ref", type_ref,
                                   "tables.MachineOpTypes", "resources")
            else:
                # Legacy authorization and declared skills can permit the same
                # work. Compare that permission, rather than registration mode.
                for key in sorted(supported):
                    type_ref = _reference(source, "op_type", key)
                    eligible = (qualifications[saved_id] is None or key in qualifications[saved_id]) if profiles is not None and skills is not None else _MISSING
                    projection.add(category, entity + ":skill:" + _ref_key(type_ref, key), label, "work_type_eligible", eligible,
                                   "tables", "resources")
    projection.declare(category, "authorizations", "tables.OperatorMachine", known)
    for index, row in relevant_links:
        machine, operator = _reference(source, "machine", row["machine_id"]), _reference(source, "operator", row["operator_id"])
        entity = _ref_key(machine, row["machine_id"]) + ":operator:" + _ref_key(operator, row["operator_id"])
        path = "tables.OperatorMachine[" + str(index) + "]"
        projection.add(category, entity, row["operator_id"] + " / " + row["machine_id"], "authorization", True, path, "authorizations")
        for field, value in (("is_primary", to_yes_no(row.get("is_primary"), default="no")), ("skill_rank", skill_rank(row.get("skill_level")))):
            projection.add(category, entity, row["operator_id"], field, value, path + "." + ("skill_level" if field == "skill_rank" else field), "authorizations")
    return result, known


def _calendar(projection, resources, known, window):
    source, category = projection.source, "calendar_downtime"
    missing_window = window["start"] is None or window["end"] is None
    projection.declare(category, "calendar_resources", "tables.WorkCalendar", known and not missing_window,
        reason=_reason("history_window_start_missing", "统计时间尚未确定，请选择记录后核对资源日历。") if missing_window else None)
    if missing_window:
        return
    for resource, (_, calendar) in zip(resources, source.calendar.iter_resources(resources, window["start"], window["end"])):
        ref, label = resource["ref"], resource["label"]
        for day in calendar["days"]:
            entity = ref + ":day:" + day["date"]
            available = day["state"] == "available"
            reason = _reason("calendar_unknown", "原保存日历缺少或无法解释该资源当日有效窗口。")
            projection.declare(category, "windows:" + entity, "tables", available, reason=reason)
            projection.add(category, entity, label + " " + day["date"], "effective_hours", day["effective_hours"] if available else _MISSING,
                           "tables", "calendar_resources", reason=reason)
            # Coalesce equal adjacent actual windows; provenance and policy dates do not change capacity.
            windows = []
            for row in day.get("windows") or []:
                value = {key: row[key] for key in ("start", "end", "efficiency", "allow_normal", "allow_urgent")}
                if windows and windows[-1]["end"] == value["start"] and all(windows[-1][key] == value[key] for key in ("efficiency", "allow_normal", "allow_urgent")):
                    windows[-1]["end"] = value["end"]
                else:
                    windows.append(value)
            for row in windows:
                key = entity + ":window:" + row["start"] + ":" + row["end"]
                for field in ("start", "end", "efficiency", "allow_normal", "allow_urgent"):
                    projection.add(category, key, label, field, row[field], "tables", "windows:" + entity)
            for row in day.get("downtime_windows") or []:
                key = entity + ":downtime:" + row["start"] + ":" + row["end"]
                projection.fields(category, key, label, row, ("start", "end"), "tables.MachineDowntimes", "windows:" + entity)


def _execution(projection, operations, resources):
    source, category = projection.source, "execution_baseline"
    execution = source.execution
    projection.declare(category, "execution", "", execution is not None, origin="execution")
    refs = {resource["ref"] for resource in resources}
    relevant, outside = {}, set()
    for ref in set(operations) - set(execution or {}):
        projection.add(category, ref, operations[ref].get("op_code", ref), "execution_facts", _MISSING, ref,
                       "execution", origin="execution", reason=_reason("execution_not_saved", "选中工序的原报工投影未保存。"))
    for execution_index, (ref, row) in enumerate((execution or {}).items()):
        path = "[" + str(execution_index) + "]" if source.kind == "run" else ref
        reports = (row.get("reports") or []) + (row.get("legacy_facts") or [])
        busy = row.get("execution_state") in ("partial", "started", "processing", "paused") and any(
            report.get("actual_machine_ref") in refs or report.get("actual_operator_ref") in refs for report in reports)
        if ref not in operations and not busy:
            continue
        relevant[ref] = row
        label = operations.get(ref, {}).get("op_code", ref)
        if ref not in operations:
            outside.add(ref)
            projection.fields(category, ref, label, row, ("first_actual_start", "execution_state"),
                              path, "execution", origin="execution")
            for kind in ("machine", "operator"):
                for resource_ref in sorted({report["actual_" + kind + "_ref"] for report in reports
                        if report.get("actual_" + kind + "_ref") is not None}):
                    projection.add(category, ref + ":actual:" + resource_ref, label, "actual_" + kind + "_ref", resource_ref,
                                   path, "execution", origin="execution")
            continue
        projection.fields(category, ref, label, row, ("target_quantity", "target_basis", "known_completed_quantity", "remaining_quantity",
            "quantity_complete", "records_complete", "first_actual_start", "confirmed_finish", "execution_state"),
            path, "execution", origin="execution", nullable=("first_actual_start", "confirmed_finish"))
        # Actual report identity and journal times are bookkeeping. Their physical content is retained.
        for report_kind in ("reports", "legacy_facts"):
            physical = sorted(enumerate(row.get(report_kind) or []), key=lambda item: repr(tuple(item[1].get(field) for field in (
                "actual_start", "actual_end", "event_time", "actual_machine_ref", "actual_operator_ref", "completed_quantity", "quantity_done"))))
            fields = ("actual_start", "actual_end", "actual_machine_ref", "actual_operator_ref", "completed_quantity", "effective_processing_hours") if report_kind == "reports" else (
                "event_type", "reported_status", "event_time", "quantity_done", "quantity_scrapped", "actual_machine_ref", "actual_operator_ref")
            for ordinal, (index, report) in enumerate(physical):
                entity = ref + ":" + report_kind + ":" + str(ordinal)
                projection.fields(category, entity, label, report, fields,
                    path + "." + report_kind + "[" + str(index) + "]", "execution", origin="execution",
                    nullable=("actual_end", "actual_machine_ref", "actual_operator_ref", "effective_processing_hours", "reported_status",
                              "quantity_done", "quantity_scrapped"))
    schedule = source.table("Schedule")
    baseline = source.baseline
    known = schedule is not None and type(baseline) is dict and "version" in baseline
    projection.declare(category, "formal_arrangements", "tables.Schedule", known)
    version = baseline.get("version") if baseline else None
    latest = {}
    for row in schedule or []:
        if type(version) is int and row.get("version", 0) <= version:
            latest[row["op_id"]] = max(row["version"], latest.get(row["op_id"], 0))
    op_refs = {int(row["source_key"]): row["ref"] for row in source.table("WorkbenchPlanSourceRefs") or []
               if row.get("kind") == "operation" and row.get("active") == 1}
    op_refs.update({row.get("id"): ref for ref, row in source.operations.items()})
    arranged = defaultdict(list)
    relevant_refs = set(operations) | set(relevant)
    for index, row in enumerate(schedule or []):
        ref = op_refs.get(row.get("op_id"))
        if ref in relevant_refs and row.get("version") == latest.get(row.get("op_id")):
            arranged[ref].append((index, row))
    for ref, rows in arranged.items():
        for ordinal, (index, row) in enumerate(sorted(rows, key=lambda item: (item[1].get("start_time", ""), item[1].get("end_time", "")))):
            entity, path, label = ref + ":formal:" + str(ordinal), "tables.Schedule[" + str(index) + "]", operations.get(ref, {}).get("op_code", ref)
            if ref in outside:
                start, end = row.get("start_time"), row.get("end_time")
                duration = (instant(end) - instant(start)).total_seconds() / 3600 if start is not None and end is not None else _MISSING
                projection.add(category, entity, label, "reserved_wall_hours", duration, path, "formal_arrangements")
                continue
            for field in ("start_time", "end_time"):
                value = row.get(field, _MISSING)
                value = instant(value).isoformat() if value is not _MISSING and value is not None else value
                projection.add(category, entity, label, field, value, path + "." + field, "formal_arrangements")
            for field, kind in (("machine_id", "machine"), ("operator_id", "operator")):
                _ref_field(projection, category, entity, label, row, field, kind, path, "formal_arrangements")


def _freeze(projection, operations):
    source, category = projection.source, "freeze"
    hold, path = source.input.get("hold_window", _MISSING), source.input_path("hold_window")
    if hold is _MISSING:
        cfg = _config(source)
        enabled, days = cfg.get("freeze_window_enabled"), cfg.get("freeze_window_days")
        if enabled and days and enabled[0] in ("yes", "no"):
            if enabled[0] == "no" or int(days[0]) <= 0:
                hold = None
            elif "start_date" in source.input:
                start = datetime.fromisoformat(source.input["start_date"])
                hold = {"start": start.isoformat(), "end": (start + timedelta(days=int(days[0]))).isoformat()}
        path = enabled[1] if enabled else "tables.ScheduleConfig"
        origin = "environment"
    else:
        origin = "input"
    if type(hold) is dict and "start" in hold and "end" in hold:
        hold = {key: instant(hold[key]).isoformat() for key in ("start", "end")}
    projection.add(category, "planning", "本次不重排时段", "hold_window", hold, path or "hold_window", "freeze_policy", origin=origin, nullable=True)
    projection.declare(category, "freeze_policy", path or "hold_window", hold is not _MISSING, origin=origin)
    known, members = hold is None, set()
    if hold is not None and hold is not _MISSING:
        if source.kind == "run" and source.raw_tasks is not None:
            known = True
            members = {row["operation_ref"] for row in source.raw_tasks if row["payload"].get("locked") is True}
        elif source.kind == "trial" and source.saved is not None:
            tasks = source.saved.get("tasks")
            known = type(tasks) is list
            members = {row["operation_ref"] for row in tasks or [] if any(reason.get("code") in (
                "task_frozen", "frozen_arrangement_changed") for reason in (row.get("edit_context") or {}).get("blocked_reasons", []))}
    projection.declare(category, "frozen_members", "" if source.kind == "run" else "saved.tasks", known,
                       origin="tasks" if source.kind == "run" else "saved")
    for ref in members:
        projection.add(category, ref, operations.get(ref, {}).get("op_code", ref), "frozen_member", True,
                       "" if source.kind == "run" else "saved.tasks", "frozen_members", origin="tasks" if source.kind == "run" else "saved")


def _production(source, window):
    projection = _Projection(source)
    if not source.available:
        for category, _ in _CATEGORIES:
            projection.declare(category, category, "", False, reason=getattr(source, "issue", None) or _reason(
                "production_conditions_not_saved", "该历史记录未保存可核对的原生产条件。"))
        return projection
    batches, operations = _scope(projection)
    _work(projection, batches, operations)
    _materials(projection, batches, operations)
    resources, known = _resources(projection, operations)
    _calendar(projection, resources, known, window)
    _execution(projection, operations, resources)
    _freeze(projection, operations)
    return projection


def _saved_objective(source, packet, artifact, algo, native):
    receipt = packet.get("receipt") or {}
    selection, candidate = receipt.get("selection") or {}, packet.get("candidate") or {}
    name = artifact.get("objective_name") or artifact.get("objective", _MISSING)
    candidate_ref, selected_ref = candidate.get("candidate_ref"), selection.get("selected_candidate_ref")
    selected = candidate_ref is not None and candidate_ref == selected_ref

    def applicable(saved_name, order, *, owned=False):
        valid = (type(saved_name) is str and bool(saved_name) and type(order) is list and bool(order)
                 and all(type(field) is str and field for field in order))
        if not valid or type(name) is str and name and name != saved_name:
            return False
        if owned or selected:
            return True
        # A sibling's saved name and score must establish that this run's
        # shared scoring schema also applies to the actually adopted candidate.
        score = artifact.get("score")
        return name == saved_name and type(score) is list and len(score) == len(order)

    saved_name = (selection.get("primary_objective", name) if selection.get("selection_policy_version") == "business_objectives_v1"
                  else selection.get("objective_name", name))
    order = selection.get("objective_field_order", _MISSING)
    if selection.get("selection_policy_version") == "business_objectives_v1":
        order = order.get(saved_name, _MISSING) if type(order) is dict and type(saved_name) is str else _MISSING
    if applicable(saved_name, order):
        return _side(source.source("receipt.selection"), {"name": saved_name, "field_order": order})
    if native is not None:
        _, _, selection = native
        saved_name = selection.get("primary_objective", _MISSING)
        orders = selection.get("objective_field_order")
        order = orders.get(saved_name, _MISSING) if type(orders) is dict and type(saved_name) is str else _MISSING
        if selection.get("selection_policy_version") == "business_objectives_v1" and applicable(saved_name, order, owned=True):
            return _side(source.source("algo.candidate_comparison.selection"), {"name": saved_name, "field_order": order})
    sources = ((algo, "candidate.artifact.summary.algo", True),
               (((receipt.get("summary") or {}).get("algo") or {}), "receipt.summary.algo", False))
    for values, path, owned in sources:
        schema = values.get("best_score_schema")
        if type(schema) is not list or not schema or any(type(row) is not dict or "key" not in row for row in schema):
            continue
        order = [row["key"] for row in schema]
        saved_name = values.get("objective", name if owned else _MISSING)
        if applicable(saved_name, order, owned=owned):
            return _side(source.source(path), {"name": saved_name, "field_order": order})
    return _side(source.source("candidate.artifact"), _MISSING,
                 reason=_reason("objective_basis_not_recorded", "原记录缺少适用于该候选的目标名称或实际评分字段顺序。"))


def _native_optimization(source):
    """Native formal runs keep their saved optimization facts in the summary."""
    if source.kind != "legacy" or type(source.saved) is not dict:
        return None
    algo = source.saved.get("algo")
    if type(algo) is not dict:
        return None
    comparison = algo.get("candidate_comparison")
    comparison = comparison if type(comparison) is dict else {}
    if (comparison.get("generation_policy_version") or algo.get("generation_policy_version")) != "unified_search_v1":
        return None
    selection = comparison.get("selection")
    return algo, comparison, selection if type(selection) is dict else {}


def _native_run_options(projection, native):
    algo, comparison, selection = native
    algorithm_path, comparison_path = "algo.", "algo.candidate_comparison."
    selection_path = comparison_path + "selection."
    sources = {
        "generation_policy_version": ((comparison, comparison_path, "generation_policy_version"), (algo, algorithm_path, "generation_policy_version")),
        "selection_policy_version": ((selection, selection_path, "selection_policy_version"), (comparison, comparison_path, "selection_policy_version")),
        "primary_objective": ((selection, selection_path, "primary_objective"), (comparison, comparison_path, "primary_objective"), (algo, algorithm_path, "primary_objective")),
        "target_objectives": ((selection, selection_path, "target_objectives"), (comparison, comparison_path, "target_objectives"), (algo, algorithm_path, "target_objectives")),
        "time_budget_seconds": ((comparison, comparison_path, "run_time_budget_seconds"), (algo, algorithm_path, "time_budget_seconds")),
    }
    for field, candidates in sources.items():
        value, path = _MISSING, candidates[0][1] + candidates[0][2]
        for values, prefix, key in candidates:
            if key in values:
                value, path = values[key], prefix + key
                break
        projection.add("algorithm", "run_options", "本次保存的优化策略和预算", field, value, path, "algorithm")


def _experiments(source, packet):
    projection = _Projection(source)
    projection.declare("algorithm", "algorithm", "tables.ScheduleConfig", source.available)
    cfg = _config(source) if source.available else {}
    for key in _CONFIG_KEYS:
        if key in cfg:
            value, path = cfg[key]
            projection.add("algorithm", "archived_settings", "原保存算法设置", key, value, path, "algorithm")
    artifact = source.artifact or {}
    selection = (packet.get("receipt") or {}).get("selection") or {}
    inputs = source.input or {}
    native = _native_optimization(source)
    if native is not None:
        _native_run_options(projection, native)
    if source.available:
        for key in ("generation_policy_version", "selection_policy_version", "primary_objective", "target_objectives", "time_budget_seconds"):
            if key in inputs:
                value, path = inputs[key], "capture.input." + key
            elif key in selection:
                value, path = selection[key], "receipt.selection." + key
            elif key in artifact:
                value, path = artifact[key], "candidate.artifact." + key
            else:
                value, path = None, "capture.input." + key
            projection.add("algorithm", "run_options", "本次保存的优化策略和预算", key, value, path,
                           "algorithm", present=key in inputs or key in selection or key in artifact)
    algo = ((artifact.get("summary") or {}).get("algo") or {})
    for prefix, values, path in (("chosen", artifact, "candidate.artifact"), ("actual_summary", algo, "candidate.artifact.summary.algo"),
                               ("effective_config", algo.get("config_snapshot") or {}, "candidate.artifact.summary.algo.config_snapshot")):
        fields = _CONFIG_KEYS if prefix == "effective_config" else (
            "algo_mode", "mode", "objective", "objective_name", "time_budget_seconds", "sort_strategy", "dispatch_mode",
            "dispatch_rule", "adopted_dispatch_rule", "graph_critical_weight", "graph_impact_weight", "graph_downstream_weight", "algorithm_version")
        for key in fields:
            if key in values:
                projection.add("algorithm", prefix, "实际所选方案参数", key, values[key], path + "." + key, "algorithm")
    for key, value in (artifact.get("used_params") or {}).items():
        if type(value) in (str, int, float, bool) or value is None:
            projection.add("algorithm", "used_params", "实际策略参数", key, value, "candidate.artifact.used_params." + key, "algorithm", nullable=True)
    report = artifact.get("search_report") or {}
    projection.fields("algorithm", "search_profile", "实际搜索设置", report,
                      tuple(key for key in ("algorithm_profile", "seed", "time_budget_seconds") if key in report),
                      "candidate.artifact.search_report", "algorithm")
    profile = report.get("candidate_profile") or {}
    for key in ("profile", "enabled", "seed", "seed_source", "configured_time_budget_seconds", "effective_time_budget_seconds",
                "configured_max_iterations", "effective_max_iterations", "iteration_limit_source", "restart_after_iterations",
                "repair", "acceptance", "candidate_strategy_family", "dispatch_mode", "dispatch_rule", "ortools_warmstart_enabled", "strict_mode"):
        if key in profile:
            projection.add("algorithm", "candidate_profile", "实际搜索配置", key, profile[key],
                           "candidate.artifact.search_report.candidate_profile." + key, "algorithm")
    for key in ("neighborhoods", "configured_neighborhoods", "candidate_strategy_families"):
        for index, value in enumerate(profile.get(key) or []):
            projection.add("algorithm", "candidate_profile", "实际搜索配置", key + "[" + str(index) + "]", value,
                           "candidate.artifact.search_report.candidate_profile." + key + "[" + str(index) + "]", "algorithm")
    if not any("algorithm_version" in values for values in (artifact, algo)):
        projection.add("algorithm", "version", "实际算法版本", "algorithm_version", _MISSING, "candidate.artifact.algorithm_version", "algorithm",
                       reason=_reason("algorithm_version_not_recorded", "原记录未保存实际算法版本。"))
    return projection, _saved_objective(source, packet, artifact, algo, native)


def prepare_history_condition_source(packet):
    """Prepare the saved source, settings and objective independently of the window."""
    source = ConditionSource(packet)
    configurations, objective = _experiments(source, packet)
    return {"source": source, "configurations": configurations, "objective": objective}


def prepare_history_condition_side(prepared, window):
    """Project one saved source's production conditions for the actual window."""
    return {"conditions": _production(prepared["source"], window),
            "configurations": prepared["configurations"], "objective": prepared["objective"]}


def compare_prepared_history_conditions(before, after):
    """Compare prepared sides without changing their shared projections."""
    conditions = _compare(before["conditions"], after["conditions"], _CATEGORIES)
    configurations = _compare(before["configurations"], after["configurations"], (("algorithm", "算法实验设置"),))
    previous, current = before["objective"], after["objective"]
    objective_state = "unknown" if "unknown" in (previous["state"], current["state"]) else (
        "equal" if previous["value"] == current["value"] else "different")
    objective = {"category": "algorithm", "entity": {"key": "objective", "label": "优化目标"},
                 "state": objective_state, "field": "objective", "before": previous, "after": current}
    return {"conditions": conditions, "configurations": configurations, "objective": objective,
            "gate": {"production_state": conditions["state"], "objective_state": objective_state,
                     "state": "equal" if conditions["state"] == objective_state == "equal" else (
                         "different" if "different" in (conditions["state"], objective_state) else "unknown")}}


def compare_history_conditions(before_source, after_source, shared_window):
    """Prepare standalone inputs for this call; grouped history reads use their reader."""
    before, after = (prepare_history_condition_side(prepare_history_condition_source(packet), shared_window)
                     for packet in (before_source, after_source))
    return compare_prepared_history_conditions(before, after)
