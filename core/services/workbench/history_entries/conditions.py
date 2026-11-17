"""Compare saved production conditions by business responsibility and identity.

These projections read verified historical packets only. Archive revisions,
capture times and journal identities locate evidence; they are not production
conditions. Experimental settings have their own projection and objective gate.

``_MISSING`` (an unknown row) only states a business unknown: a permanent
identity the source never recorded, a referenced record outside the saved
scope (a selected batch, a stage's operation, a removed work type or
supplier), a setting the source kind does not record, a calendar day without
effective windows, a statistics window not yet fixed, a source issue, or an
objective basis that does not apply. Tables, columns and keys every saved
source carries are indexed directly: one missing is a corrupt archive and
fails the read, never an unknown condition.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import MutableMapping

from core.models.enums import SKILL_LEVEL_RANKS
from core.models.resource_capabilities import machine_type_index, supports_source
from core.services.capacity.plan_calendar_intervals import instant, wire
from core.shared.local_datetime import row_interval
from core.shared.strict_json import canonical_json

from .conditions_source import ConditionSource
from .packets import RunPacket

_MISSING = object()
_CATEGORIES = (("scope", "排产范围"), ("batch", "批次交期与数量"), ("requirements", "工序标准需求"), ("materials_outsource", "物料与外协"), ("calendar_downtime", "有效日历与停机"), ("resource_qualifications", "资源与人员资格"), ("execution_baseline", "报工与正式原安排"), ("freeze", "不重排窗口与成员"))
_CONFIG_KEYS = ("sort_strategy", "priority_weight", "due_weight", "ready_weight", "dispatch_mode", "dispatch_rule", "algo_mode", "time_budget_seconds", "objective", "graph_analysis_mode", "graph_block_on_cycle", "graph_critical_weight", "graph_impact_weight", "graph_downstream_weight")
_SELECTION_OPTION_KEYS = ("primary_objective", "target_objectives")
# The chosen candidate's own settings, as its artifact records them (candidate_artifact.PLAN_FIELDS).
_CHOSEN_KEYS = ("algo_mode", "objective_name", "time_budget_seconds", "sort_strategy", "dispatch_mode")
_PLANNING_FIELDS = ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy", "material_strategy")
def _reason(code="not_recorded", message="原保存资料缺少这一项，条件未知。"):
    return {"code": code, "message": message}
def _side(source, value, *, present=True, nullable=False, reason=None):
    known = value is not _MISSING and (value is not None or nullable or not present)
    return {"present": present, "state": "known" if known else "unknown", "value": value if known else None, "source": source, "reason": None if known else reason or _reason()}

class _Projection:
    def __init__(self, source: ConditionSource):
        self.source = source
        self.rows: MutableMapping = {}
        self.families: MutableMapping = {}
    def declare(self, category, family, path, known, *, origin="environment", reason=None):
        self.families[family] = (bool(known), path, origin, reason)
        if not known:
            self.add(category, family, "保存资料", "availability", _MISSING, path, family, origin=origin, reason=reason)
    def add(self, category, entity, label, field, value, path, family, *, origin="environment", nullable=False, reason=None, present=True, dot_field=False):
        known = bool(value is not _MISSING and (value is not None or nullable or not present))
        clean_value = value if known else None
        self.rows[category, entity, field] = (known, clean_value, bool(present), family, label, path, origin, reason, bool(dot_field))
    def fields(self, category, entity, label, row, fields, path, family, *, origin="environment", nullable=()):
        for field in fields:
            self.add(category, entity, label, field, row[field], path, family, origin=origin, nullable=field in nullable, dot_field=True)
    def absent(self, family_key):
        family = self.families.get(family_key)
        if family is None:
            known, source, reason = False, self.source.source(""), None
        else:
            known, path, origin, reason = family
            source = self.source.source(path, origin)
        return {"present": False, "state": "known" if known else "unknown", "value": None, "source": source, "reason": None if known else reason or _reason()}
def _state(counts):
    return "different" if counts["different"] else "unknown" if counts["unknown"] else "equal"
def _materialize_cell(projection: _Projection, row_tuple, field, fallback_family):
    if row_tuple is None:
        return projection.absent(fallback_family)
    known, clean_value, present, _family, _label, path, origin, reason, dot_field = row_tuple
    full_path = f"{path}.{field}" if dot_field else path
    return {"present": present, "state": "known" if known else "unknown", "value": clean_value, "source": projection.source.source(full_path, origin), "reason": None if known else reason or _reason()}
def _materialize_row(before: _Projection, after: _Projection, key, state):
    category, entity, field = key
    left, right = before.rows.get(key), after.rows.get(key)
    row = left if left is not None else after.rows[key]
    family, label = row[3], row[4]
    return {"category": category, "entity": {"key": entity, "label": label}, "field": field, "state": state, "before": _materialize_cell(before, left, field, family), "after": _materialize_cell(after, right, field, family)}
def _analyze_comparison(before: _Projection, after: _Projection, categories):
    summary = {"equal": 0, "different": 0, "unknown": 0}
    category_order = tuple(key for key, _ in categories)
    category_counts = {key: {"equal": 0, "different": 0, "unknown": 0} for key in category_order}
    buckets = {state: {key: [] for key in category_order} for state in ("different", "unknown", "equal")}
    extra_buckets = {state: [] for state in ("different", "unknown", "equal")}
    b_rows, a_rows = before.rows, after.rows
    b_families, a_families = before.families, after.families
    matched_in_a = 0
    for key, left in b_rows.items():
        right = a_rows.get(key)
        b_known, b_val, b_present = left[0], left[1], left[2]
        if right is not None:
            matched_in_a += 1
            a_known, a_val, a_present = right[0], right[1], right[2]
        else:
            a_family = a_families.get(left[3])
            a_known = a_family[0] if a_family is not None else False
            a_val, a_present = None, False
        equal = b_present == a_present and (type(b_val) is bool) == (type(a_val) is bool) and b_val == a_val
        state = "unknown" if not (b_known and a_known) else ("equal" if equal else "different")
        summary[state] += 1
        cat = key[0]
        if cat in category_counts:
            category_counts[cat][state] += 1
            buckets[state][cat].append(key)
        else:
            extra_buckets[state].append(key)
    if matched_in_a < len(a_rows):
        for key, right in a_rows.items():
            if key in b_rows:
                continue
            a_known, a_val, a_present = right[0], right[1], right[2]
            b_family = b_families.get(right[3])
            b_known = b_family[0] if b_family is not None else False
            b_val, b_present = None, False
            state = "unknown" if not (b_known and a_known) else ("equal" if b_present == a_present and b_val == a_val else "different")
            summary[state] += 1
            cat = key[0]
            if cat in category_counts:
                category_counts[cat][state] += 1
                buckets[state][cat].append(key)
            else:
                extra_buckets[state].append(key)
    groups = [{"key": key, "label": label, "state": _state(category_counts[key]), "summary": category_counts[key]} for key, label in categories]
    return {"state": _state(summary), "summary": summary, "categories": groups, "buckets": buckets, "extra_buckets": extra_buckets, "category_order": category_order, "total": sum(summary.values())}
def _materialize_comparison(before: _Projection, after: _Projection, analysis, *, page=1, size=None, all_rows=True):
    buckets, extra_buckets, category_order, total = analysis["buckets"], analysis["extra_buckets"], analysis["category_order"], analysis["total"]
    rows = []
    if all_rows:
        for cat in category_order:
            cat_items = [(key, state) for state in ("different", "unknown", "equal") for key in buckets[state][cat]]
            cat_items.sort(key=lambda item: item[0])
            for key, state in cat_items:
                rows.append(_materialize_row(before, after, key, state))
        extra_items = [(key, state) for state in ("different", "unknown", "equal") for key in extra_buckets[state]]
        if extra_items:
            extra_items.sort(key=lambda item: item[0][1:])
            for key, state in extra_items:
                rows.append(_materialize_row(before, after, key, state))
        page_size = len(rows) if size is None else size
        has_more = False
    else:
        page_size = 20 if size is None else size
        start, end = (page - 1) * page_size, page * page_size
        offset = 0
        for state in ("different", "unknown", "equal"):
            state_buckets = buckets[state]
            for bucket, sort_key in (*((state_buckets[cat], None) for cat in category_order), (extra_buckets[state], lambda key: key[1:])):
                count = len(bucket)
                if not count:
                    continue
                next_offset = offset + count
                if next_offset > start and offset < end:
                    bucket_sorted = sorted(bucket) if sort_key is None else sorted(bucket, key=sort_key)
                    for key in bucket_sorted[max(0, start - offset):min(count, end - offset)]:
                        rows.append(_materialize_row(before, after, key, state))
                offset = next_offset
                if offset >= end:
                    break
            if offset >= end:
                break
        has_more = end < total
    return {"state": analysis["state"], "summary": analysis["summary"], "categories": analysis["categories"], "rows": rows, "page": {"number": page, "size": page_size, "total": total, "has_more": has_more}}
def _compare(before, after, categories):
    return _materialize_comparison(before, after, _analyze_comparison(before, after, categories), all_rows=True)
def _reference(source, kind, key, *, original=False):
    if key is None:
        return None
    refs = source.original_entity_refs if original else source.entity_refs
    return refs.get((kind, str(key)), _MISSING)
def _ref_key(value, fallback):
    return value if type(value) is str else "unknown:" + str(fallback)
def _ref_field(projection: _Projection, category, entity, label, row, field, kind, path, family, *, original=False):
    value = _reference(projection.source, kind, row[field], original=original)
    projection.add(category, entity, label, field, value, path, family, origin="original" if original else "environment", nullable=True, dot_field=True)
def _config(source: ConditionSource):
    rows = source.table("ScheduleConfig")
    return {row["config_key"]: (row["config_value"], "tables.ScheduleConfig[" + str(index) + "].config_value") for index, row in enumerate(rows)}
def _scope(projection: _Projection):
    source = projection.source
    inputs = source.input
    selected = inputs["batch_refs"] if source.kind == "run" else list(source.batches)
    projection.declare("scope", "selected_batches", "batch_refs", True, origin="input")
    batches = {ref: source.batches[ref] for ref in selected if ref in source.batches}
    batch_ids = {batch["batch_id"] for batch in batches.values()}
    operations = {ref: row for ref, row in source.operations.items() if row["batch_id"] in batch_ids}
    projection.declare("scope", "selected_operations", "tables.BatchOperations", True, origin="original")
    for ref in selected:
        projection.add("scope", ref, batches[ref]["batch_id"] if ref in batches else ref, "batch_member", True, "batch_refs", "selected_batches", origin="input")
        if ref not in batches:
            projection.add("batch", ref, ref, "batch_facts", _MISSING, "batches." + ref, "selected_batches", origin="original", reason=_reason("selected_batch_missing", "原保存范围中的批次事实缺失。"))
    for ref, row in operations.items():
        projection.add("scope", ref, row["op_code"], "operation_member", True, "operations." + ref, "selected_operations", origin="original")
    for field in _PLANNING_FIELDS:
        # A run input carries every planning field. A trial reads its source's settings, and an official plan
        # source records only the material policy and run dates: its two run policies are not recorded.
        value = inputs[field] if source.kind == "run" or field in inputs else _MISSING
        projection.add("scope", "planning", "本次排产", field, value, field, "planning", origin="input")
    projection.declare("scope", "planning", "", True, origin="input")
    return batches, operations
def _work(projection: _Projection, batches, operations):
    projection.declare("batch", "batch_facts", "tables.Batches", True, origin="original")
    projection.declare("requirements", "operation_facts", "tables.BatchOperations", True, origin="original")
    for ref, row in batches.items():
        projection.fields("batch", ref, row["batch_id"], row, ("quantity", "due_date", "priority", "ready_status", "ready_date", "status"), "batches." + ref, "batch_facts", origin="original", nullable=("due_date", "ready_date"))
        _ref_field(projection, "batch", ref, row["batch_id"], row, "part_no", "part", "batches." + ref, "batch_facts", original=True)
    for ref, row in operations.items():
        label, path = row["op_code"], "operations." + ref
        projection.fields("requirements", ref, label, row, ("piece_id", "seq", "source", "status"), path, "operation_facts", origin="original", nullable=("piece_id",))
        # External work has a saved cycle, rather than factory standard hours.
        external = row["source"] == "external"
        for field in ("setup_hours", "unit_hours"):
            projection.add("requirements", ref, label, field, None if external else row[field], path, "operation_facts", origin="original", nullable=external, dot_field=True)
        for field, kind in (("op_type_id", "op_type"), ("machine_id", "machine"), ("operator_id", "operator"), ("supplier_id", "supplier")):
            _ref_field(projection, "requirements", ref, label, row, field, kind, path, "operation_facts", original=True)
        if external:
            projection.add("requirements", ref, label, "ext_days", row["ext_days"], path, "operation_facts", origin="original", nullable=True, dot_field=True)
def _materials(projection: _Projection, batches, operations):
    source, category = projection.source, "materials_outsource"
    requirements = source.table("BatchMaterials")
    projection.declare(category, "materials", "tables.BatchMaterials", True)
    by_batch = {row["batch_id"]: ref for ref, row in batches.items()}
    by_op = {row["id"]: ref for ref, row in operations.items()}
    review_index = {row["requirement_id"]: (index, row) for index, row in enumerate(source.table("BatchMaterialReviews"))}
    stage_index = {row["requirement_id"]: (index, row) for index, row in enumerate(source.table("BatchMaterialStages"))}
    arrivals_by_requirement = defaultdict(list)
    for arrival in source.table("BatchMaterialArrivals"):
        arrivals_by_requirement[arrival["requirement_id"]].append(arrival)
    for index, row in enumerate(requirements):
        batch_ref = by_batch.get(row["batch_id"])
        if batch_ref is None:
            continue
        material = _reference(source, "material", row["material_id"])
        entity = batch_ref + ":material:" + _ref_key(material, row["material_id"])
        label, path = row["material_id"], "tables.BatchMaterials[" + str(index) + "]"
        projection.add(category, entity, label, "material_ref", material, path + ".material_id", "materials")
        projection.fields(category, entity, label, row, ("required_qty", "available_qty", "ready_status"), path, "materials")
        review = review_index.get(row["id"])
        projection.add(category, entity, label, "reviewed_quantity", review[1]["batch_quantity"] if review else None, "tables.BatchMaterialReviews" + ("[" + str(review[0]) + "].batch_quantity" if review else ""), "materials", nullable=review is None)
        stage = stage_index.get(row["id"])
        # A stage bound to an operation outside the saved scope cannot be compared.
        projection.add(category, entity, label, "use_operation_ref", by_op.get(stage[1]["operation_id"], _MISSING) if stage else None, "tables.BatchMaterialStages" + ("[" + str(stage[0]) + "].operation_id" if stage else ""), "materials", nullable=True)
        amounts = defaultdict(Decimal)
        for arrival in arrivals_by_requirement[row["id"]]:
            amounts[arrival["arrival_date"]] += Decimal(str(arrival["quantity"]))
        projection.declare(category, "arrivals:" + entity, "tables.BatchMaterialArrivals", True)
        for day, amount in sorted(amounts.items()):
            projection.add(category, entity + ":arrival:" + day, label + " " + day, "quantity", float(amount), "tables.BatchMaterialArrivals", "arrivals:" + entity)
    contexts = source.original_table("BatchExternalContexts")
    external = {row["id"]: ref for ref, row in operations.items() if row["source"] == "external"}
    context_path = "tables.BatchExternalContexts"
    if external:
        projection.declare(category, "external_contexts", context_path, True, origin="original")
    # Creating an external operation, or turning one external, records its context (schema triggers), and an
    # archive keeps every selected operation's context.
    positions = {row["operation_id"]: index for index, row in enumerate(contexts)}
    for key, ref in external.items():
        index = positions[key]
        row, path = contexts[index], context_path + "[" + str(index) + "]"
        label = operations[ref]["op_code"]
        for field in ("part_no", "sequence", "start_sequence", "end_sequence", "merge_mode", "total_days", "group_ref"):
            projection.add(category, ref, label, field, row[field], path + "." + field, "external_contexts", origin="original", nullable=field in ("start_sequence", "end_sequence", "merge_mode", "total_days", "group_ref"))
        projection.add(category, ref, label, "supplier_id", _reference(source, "supplier", row["supplier_id"], original=True), path + ".supplier_id", "external_contexts", origin="original", nullable=True)
    suppliers = source.table("Suppliers")
    selected_suppliers = {row["supplier_id"] for row in operations.values() if row["source"] == "external"}
    selected_suppliers.update(contexts[positions[key]]["supplier_id"] for key in external)
    selected_suppliers.discard(None)
    if selected_suppliers:
        projection.declare(category, "suppliers", "tables.Suppliers", True)
        # A context keeps the supplier of its creation, which need not still exist.
        saved_suppliers = {row["supplier_id"] for row in suppliers}
        for key in selected_suppliers - saved_suppliers:
            projection.add(category, _ref_key(_reference(source, "supplier", key), key), key, "supplier_facts", _MISSING, "tables.Suppliers", "suppliers", reason=_reason("supplier_not_saved", "选中外协供应商的原资料未保存。"))
    for index, row in enumerate(suppliers):
        if row["supplier_id"] in selected_suppliers:
            ref = _reference(source, "supplier", row["supplier_id"])
            projection.fields(category, _ref_key(ref, row["supplier_id"]), row["name"], row, ("status", "default_days"), "tables.Suppliers[" + str(index) + "]", "suppliers")
def _resources(projection: _Projection, operations):
    source, category = projection.source, "resource_qualifications"
    machines, operators, types = source.table("Machines"), source.table("Operators"), source.table("OpTypes")
    capabilities = source.table("MachineOpTypes")
    links, profiles, skills = source.table("OperatorMachine"), source.table("WorkbenchOperatorProfiles"), source.table("OperatorSkill")
    needed = {row["op_type_id"] for row in operations.values() if row["source"] == "internal"}
    assigned_machines = {row["machine_id"] for row in operations.values()} - {None}
    assigned_operators = {row["operator_id"] for row in operations.values()} - {None}
    if needed:
        projection.declare(category, "OpTypes", "tables.OpTypes", True)
    type_rows = {row["op_type_id"]: row for row in types}
    supported = {key for key in needed if key in type_rows and supports_source(type_rows[key]["category"], "internal")}
    for key in sorted(needed - {None}):
        # An operation's work type has no foreign key; one no longer saved cannot prove internal work.
        row, ref = type_rows.get(key), _reference(source, "op_type", key)
        eligible = supports_source(row["category"], "internal") if row is not None else _MISSING
        projection.add(category, _ref_key(ref, key), row["name"] if row is not None else key, "internal_work_type_eligible", eligible, "tables.OpTypes", "OpTypes")
    machine_types = machine_type_index(machines, capabilities)
    relevant_machines = {row["machine_id"] for row in machines if row["machine_id"] in assigned_machines or (row["status"] == "active" and machine_types[row["machine_id"]] & supported)}
    profile_index = {row["operator_id"]: row for row in profiles}
    operator_index = {row["operator_id"]: row for row in operators}
    skill_index = defaultdict(set)
    for row in skills:
        skill_index[row["operator_id"]].add(row["op_type_id"])
    qualifications = {}
    for row in operators:
        operator_id = row["operator_id"]
        declared = operator_id in profile_index and profile_index[operator_id]["skills_declared"] == 1
        qualifications[operator_id] = skill_index[operator_id] if skill_index[operator_id] or declared else None
    relevant_links = []
    for index, row in enumerate(links):
        if row["machine_id"] in relevant_machines and operator_index[row["operator_id"]]["status"] == "active":
            qualification = qualifications[row["operator_id"]]
            if qualification is None or machine_types[row["machine_id"]] & supported & qualification:
                relevant_links.append((index, row))
    relevant_operators = assigned_operators | {row["operator_id"] for _, row in relevant_links}
    # An internal operation without a saved work type leaves its eligible resources unknown.
    known = None not in needed and all(key in type_rows for key in needed)
    projection.declare(category, "resources", "tables.Machines", known)
    result = []
    for kind, rows, selected in (("machine", machines, relevant_machines), ("operator", operators, relevant_operators)):
        for index, row in enumerate(rows):
            saved_id = row[kind + "_id"]
            if saved_id not in selected:
                continue
            ref, label, path = _reference(source, kind, saved_id), row["name"], "tables." + ("Machines" if kind == "machine" else "Operators") + "[" + str(index) + "]"
            entity = _ref_key(ref, kind + ":" + saved_id)
            projection.add(category, entity, label, "resource_ref", ref, path + "." + kind + "_id", "resources")
            projection.fields(category, entity, label, row, ("status",), path, "resources")
            if ref is not _MISSING:
                result.append({"kind": kind, "ref": ref, "label": label, "saved_id": saved_id})
            if kind == "machine":
                for key in sorted(machine_types[saved_id] & supported):
                    type_ref = _reference(source, "op_type", key)
                    projection.add(category, entity + ":type:" + _ref_key(type_ref, key), label, "work_type_ref", type_ref, "tables.MachineOpTypes", "resources")
            else:
                # Legacy authorization and declared skills can permit the same work. Compare that permission, rather than registration mode.
                for key in sorted(supported):
                    type_ref = _reference(source, "op_type", key)
                    eligible = qualifications[saved_id] is None or key in qualifications[saved_id]
                    projection.add(category, entity + ":skill:" + _ref_key(type_ref, key), label, "work_type_eligible", eligible, "tables", "resources")
    projection.declare(category, "authorizations", "tables.OperatorMachine", known)
    for index, row in relevant_links:
        machine, operator = _reference(source, "machine", row["machine_id"]), _reference(source, "operator", row["operator_id"])
        entity = _ref_key(machine, row["machine_id"]) + ":operator:" + _ref_key(operator, row["operator_id"])
        path = "tables.OperatorMachine[" + str(index) + "]"
        projection.add(category, entity, row["operator_id"] + " / " + row["machine_id"], "authorization", True, path, "authorizations")
        for field, value in (("is_primary", row["is_primary"]), ("skill_rank", SKILL_LEVEL_RANKS[row["skill_level"]])):
            projection.add(category, entity, row["operator_id"], field, value, path + "." + ("skill_level" if field == "skill_rank" else field), "authorizations")
    return result, known
def _calendar(projection: _Projection, resources, known, window):
    source, category = projection.source, "calendar_downtime"
    missing_window = window["start"] is None or window["end"] is None
    projection.declare(category, "calendar_resources", "tables.WorkCalendar", known and not missing_window, reason=_reason("history_window_start_missing", "统计时间尚未确定，请选择记录后核对资源日历。") if missing_window else None)
    if missing_window:
        return
    for resource, (_, calendar) in zip(resources, source.calendar.iter_resources(resources, window["start"], window["end"])):
        ref, label = resource["ref"], resource["label"]
        for day in calendar["days"]:
            entity = ref + ":day:" + day["date"]
            available = day["state"] == "available"
            reason = _reason("calendar_unknown", "原保存日历缺少或无法解释该资源当日有效窗口。")
            projection.declare(category, "windows:" + entity, "tables", available, reason=reason)
            projection.add(category, entity, label + " " + day["date"], "effective_hours", day["effective_hours"] if available else _MISSING, "tables", "calendar_resources", reason=reason)
            if not available:
                # An unavailable day has no windows (plan_calendar_windows.unavailable).
                continue
            # Coalesce equal adjacent actual windows; provenance and policy dates do not change capacity.
            windows = []
            for row in day["windows"]:
                value = {key: row[key] for key in ("start", "end", "efficiency", "allow_normal", "allow_urgent")}
                if windows and windows[-1]["end"] == value["start"] and all(windows[-1][key] == value[key] for key in ("efficiency", "allow_normal", "allow_urgent")):
                    windows[-1]["end"] = value["end"]
                else:
                    windows.append(value)
            for row in windows:
                wired_row = {**row, "start": wire(row["start"]), "end": wire(row["end"])}
                key = entity + ":window:" + wired_row["start"] + ":" + wired_row["end"]
                for field in ("start", "end", "efficiency", "allow_normal", "allow_urgent"):
                    projection.add(category, key, label, field, wired_row[field], "tables", "windows:" + entity)
            for row in day["downtime_windows"]:
                wired_row = {"start": wire(row["start"]), "end": wire(row["end"])}
                key = entity + ":downtime:" + wired_row["start"] + ":" + wired_row["end"]
                projection.fields(category, key, label, wired_row, ("start", "end"), "tables.MachineDowntimes", "windows:" + entity)
def _report_sort_value(report, field):
    """Null, booleans and numbers stay distinct; int and float compare exactly as numbers."""
    value = report[field]
    if value is None:
        return (1, 0, "")
    value_type = type(value)
    if value_type is bool:
        return (2, value, "")
    if value_type is int or value_type is float:
        return (3, value, "")
    if value_type is str:
        return (5, 0, value)
    return (6, 0, f"{value_type.__qualname__}:{value!r}")


def _execution(projection: _Projection, operations, resources):
    source, category = projection.source, "execution_baseline"
    execution = source.execution
    projection.declare(category, "execution", "", True, origin="execution")
    refs = {resource["ref"] for resource in resources}
    # Admission saves the execution of every selected operation (run_execution_projections, trial live_context);
    # outside the selection only work in progress on a selected resource is relevant.
    selected = {ref: execution[ref] for ref in operations}
    outside = {ref: row for ref, row in execution.items() if ref not in selected and row["execution_state"] in ("partial", "started")
               and any(report["actual_machine_ref"] in refs or report["actual_operator_ref"] in refs for report in row["reports"])}
    positions = {ref: index for index, ref in enumerate(execution)}
    for ref, row in outside.items():
        path = "[" + str(positions[ref]) + "]" if source.kind == "run" else ref
        projection.fields(category, ref, ref, row, ("first_actual_start", "execution_state"), path, "execution", origin="execution")
        for kind in ("machine", "operator"):
            for resource_ref in sorted({report["actual_" + kind + "_ref"] for report in row["reports"] if report["actual_" + kind + "_ref"] is not None}):
                projection.add(category, ref + ":actual:" + resource_ref, ref, "actual_" + kind + "_ref", resource_ref, path, "execution", origin="execution")
    # Actual report identity and journal times are bookkeeping. Their physical content is retained.
    fields = ("actual_start", "actual_end", "actual_machine_ref", "actual_operator_ref", "completed_quantity", "effective_processing_hours")
    for ref, row in selected.items():
        path, label = "[" + str(positions[ref]) + "]" if source.kind == "run" else ref, operations[ref]["op_code"]
        projection.fields(category, ref, label, row, ("target_quantity", "target_basis", "known_completed_quantity", "remaining_quantity", "quantity_complete", "records_complete", "first_actual_start", "confirmed_finish", "execution_state"), path, "execution", origin="execution", nullable=("first_actual_start", "confirmed_finish"))
        physical = sorted(enumerate(row["reports"]), key=lambda item: tuple(_report_sort_value(item[1], field) for field in fields))
        for ordinal, (index, report) in enumerate(physical):
            entity = ref + ":reports:" + str(ordinal)
            projection.fields(category, entity, label, report, fields, path + ".reports[" + str(index) + "]", "execution", origin="execution", nullable=("actual_end", "actual_machine_ref", "actual_operator_ref", "effective_processing_hours"))
    schedule = source.table("Schedule")
    projection.declare(category, "formal_arrangements", "tables.Schedule", True)
    version, latest = source.baseline["version"], {}
    # Work admitted before any official plan has no baseline version.
    if version is not None:
        for row in schedule:
            if row["version"] <= version:
                latest[row["op_id"]] = max(row["version"], latest.get(row["op_id"], 0))
    if latest:
        op_refs = dict(source.refs_by_op_id)
        op_refs.update({row["id"]: ref for ref, row in source.operations.items()})
        arranged = defaultdict(list)
        for index, row in enumerate(schedule):
            ref = op_refs.get(row["op_id"]) or row["operation_ref"]
            if (ref in selected or ref in outside) and row["version"] == latest.get(row["op_id"]):
                arranged[ref].append((index, row))
        for ref, rows in arranged.items():
            # The stored microseconds are a saved arrangement's only instants (its text columns only display them):
            # order, reserved hours (zero for a point event) and the compared times all come from start_us/end_us.
            for ordinal, (index, row) in enumerate(sorted(rows, key=lambda item: (item[1]["start_us"], item[1]["end_us"]))):
                entity, path = ref + ":formal:" + str(ordinal), "tables.Schedule[" + str(index) + "]"
                start, end = row_interval(row)
                if ref in outside:
                    duration = (end - start).total_seconds() / 3600
                    projection.add(category, entity, ref, "reserved_wall_hours", duration, path, "formal_arrangements")
                    continue
                label = operations[ref]["op_code"]
                for field, value in (("start_time", start), ("end_time", end)):
                    projection.add(category, entity, label, field, value.isoformat(), path, "formal_arrangements", dot_field=True)
                for field, kind in (("machine_id", "machine"), ("operator_id", "operator")):
                    _ref_field(projection, category, entity, label, row, field, kind, path, "formal_arrangements")
def _freeze(projection: _Projection, operations):
    source, category = projection.source, "freeze"
    inputs = source.input
    if "hold_window" in inputs:
        hold, path, origin = inputs["hold_window"], source.input_path("hold_window"), "input"
    else:
        # Without a hold window in the input, the run derived it from its delivery settings; either
        # setting row may be absent from the saved ScheduleConfig.
        cfg, hold, origin = _config(source), _MISSING, "environment"
        enabled, days = cfg.get("freeze_window_enabled"), cfg.get("freeze_window_days")
        if enabled and days and enabled[0] in ("yes", "no"):
            if enabled[0] == "no" or int(days[0]) <= 0:
                hold = None
            else:
                start = datetime.fromisoformat(inputs["start_date"])
                hold = {"start": start.isoformat(), "end": (start + timedelta(days=int(days[0]))).isoformat()}
        path = enabled[1] if enabled else "tables.ScheduleConfig"
    # ``hold`` is a window, None (no window) or _MISSING (the settings deriving it were not saved).
    if type(hold) is dict:
        hold = {key: instant(hold[key]).isoformat() for key in ("start", "end")}
    projection.add(category, "planning", "本次不重排时段", "hold_window", hold, path, "freeze_policy", origin=origin, nullable=True)
    projection.declare(category, "freeze_policy", path, hold is not _MISSING, origin=origin)
    known, members = hold is None, set()
    if hold is not None and hold is not _MISSING:
        if source.kind == "trial":
            # A saved scenario records the arrangements it kept for the hold window (trial.service.save).
            known = True
            members = set(source.saved["frozen_operation_refs"])
        elif source.raw_tasks is not None:
            # Only a run with a saved result shows which arrangements the window kept.
            known = True
            members = {row["operation_ref"] for row in source.raw_tasks if row["locked"]}
    path, origin = ("", "tasks") if source.kind == "run" else ("saved.frozen_operation_refs", "saved")
    projection.declare(category, "frozen_members", path, known, origin=origin)
    for ref in members:
        projection.add(category, ref, operations[ref]["op_code"] if ref in operations else ref, "frozen_member", True, path, "frozen_members", origin=origin)
def production_conditions(source):
    projection = _Projection(source)
    if not source.available:
        for category, _ in _CATEGORIES:
            projection.declare(category, category, "", False, reason=source.issue or _reason("production_conditions_not_saved", "该历史记录未保存可核对的原生产条件。"))
        return projection, [], False
    batches, operations = _scope(projection)
    _work(projection, batches, operations)
    _materials(projection, batches, operations)
    resources, known = _resources(projection, operations)
    _execution(projection, operations, resources)
    _freeze(projection, operations)
    return projection, resources, known
def saved_objective(source, packet):
    """The objective the source's saved candidate was scored by.

    Only a run with saved results has candidates, and every one of them is scored by the run's primary objective
    (schedule_candidate_runner); the receipt's selection records that objective and its score field order.
    """
    selection = packet.selection if isinstance(packet, RunPacket) and packet.candidate is not None else None
    if selection is None:
        # A trial, a run without this entry's saved candidate and an unavailable source score no candidate.
        return _side(source.source("candidate.artifact"), _MISSING, reason=_reason("objective_basis_not_recorded", "原记录缺少适用于该候选的目标名称或实际评分字段顺序。"))
    name = selection["primary_objective"]
    return _side(source.source("receipt.selection"), {"name": name, "field_order": selection["objective_field_order"][name]})
def _run_options(projection: _Projection, packet):
    source = projection.source
    # Only a run whose results were saved records its business selection; failed and pending runs have none.
    selection = packet.selection if isinstance(packet, RunPacket) else None
    for key in _SELECTION_OPTION_KEYS:
        if selection is None:
            projection.add("algorithm", "run_options", "本次保存的优化策略和预算", key, None, source.source(key, "input")["path"], "algorithm", present=False)
            continue
        value = selection[key]
        projection.add("algorithm", "run_options", "本次保存的优化策略和预算", key, value, "receipt.selection." + key, "algorithm")
    # Every run input records its budget; an official plan source's material policy records none.
    if "time_budget_seconds" in source.input:
        projection.add("algorithm", "run_options", "本次保存的优化策略和预算", "time_budget_seconds", source.input["time_budget_seconds"], source.input_path("time_budget_seconds"), "algorithm")
    else:
        projection.add("algorithm", "run_options", "本次保存的优化策略和预算", "time_budget_seconds", None, source.source("time_budget_seconds", "input")["path"], "algorithm", present=False)
def _experiments(source, packet):
    projection = _Projection(source)
    projection.declare("algorithm", "algorithm", "tables.ScheduleConfig", source.available)
    if source.available:
        cfg = _config(source)
        for key in _CONFIG_KEYS:
            if key in cfg:
                value, path = cfg[key]
                projection.add("algorithm", "archived_settings", "原保存算法设置", key, value, path, "algorithm")
        _run_options(projection, packet)
    # A trial and a run without a saved result have no chosen candidate.
    artifact = source.artifact
    if artifact is not None:
        for key in _CHOSEN_KEYS:
            projection.add("algorithm", "chosen", "实际所选方案参数", key, artifact[key], "candidate.artifact." + key, "algorithm")
        for key, value in artifact["used_params"].items():
            # Only scalar strategy parameters become comparison rows.
            if type(value) in (str, int, float, bool) or value is None:
                projection.add("algorithm", "used_params", "实际策略参数", key, value, "candidate.artifact.used_params." + key, "algorithm", nullable=True)
    return projection, saved_objective(source, packet)
def prepare_history_condition_source(packet):
    """Prepare the saved source, settings and objective independently of the window."""
    source = ConditionSource(packet)
    configurations, objective = _experiments(source, packet)
    return {"source": source, "production": None, "configurations": configurations, "objective": objective}
def prepare_history_condition_side(prepared, window):
    """Project one saved source's production conditions for the actual window."""
    if prepared["production"] is None:
        prepared["production"] = production_conditions(prepared["source"])
    baseline, resources, known = prepared["production"]
    conditions = _Projection(prepared["source"])
    if prepared["source"].available:
        _calendar(conditions, resources, known, window)
    conditions.rows = {**baseline.rows, **conditions.rows}
    conditions.families = {**baseline.families, **conditions.families}
    return {"conditions": conditions, "configurations": prepared["configurations"], "objective": prepared["objective"]}
def objective_comparison_state(previous, current):
    if "unknown" in (previous["state"], current["state"]):
        return "unknown"
    return "equal" if previous["value"] == current["value"] else "different"
def _canonical_condition_value(value):
    if value is None:
        return ["null"]
    value_type = type(value)
    if value_type is bool:
        return ["bool", value]
    if value_type is int:
        return ["num_int", str(value)]
    if value_type is float:
        if value.is_integer():
            return ["num_int", str(int(value))]
        return ["num_float", repr(value)]
    if value_type is str:
        return ["str", value]
    if isinstance(value, (list, tuple)):
        return ["list", [_canonical_condition_value(item) for item in value]]
    if isinstance(value, dict):
        return ["dict", [[str(key), _canonical_condition_value(item)] for key, item in sorted(value.items())]]
    return ["other", f"{value_type.__qualname__}:{value!r}"]
def projection_condition_digest(projection: _Projection):
    if any(not fam[0] for fam in projection.families.values()):
        return None
    items = []
    for (category, entity, field), row in sorted(projection.rows.items()):
        known, clean_value, present = row[0], row[1], row[2]
        if not known:
            return None
        items.append([category, entity, field, present, _canonical_condition_value(clean_value)])
    return canonical_json(items)
def calendar_condition_digest_from_source(source: ConditionSource, resources, known: bool, window):
    if not source.available or not known or window["start"] is None or window["end"] is None:
        return None
    cal_projection = _Projection(source)
    _calendar(cal_projection, resources, known, window)
    return projection_condition_digest(cal_projection)
def extract_entry_condition_digests(packet, window):
    source = ConditionSource(packet)
    objective = saved_objective(source, packet)
    static_proj, resources, known = production_conditions(source)
    static_digest = projection_condition_digest(static_proj)
    cal_digest = calendar_condition_digest_from_source(source, resources, known, window)
    return objective, static_digest, cal_digest
def compare_history_configurations(before, after):
    configurations = _compare(before["configurations"], after["configurations"], (("algorithm", "算法实验设置"),))
    previous, current = before["objective"], after["objective"]
    objective_state = objective_comparison_state(previous, current)
    objective = {"category": "algorithm", "entity": {"key": "objective", "label": "优化目标"}, "state": objective_state, "field": "objective", "before": previous, "after": current}
    return configurations, objective
def analyze_prepared_history_conditions(before, after, *, include_configurations=True):
    """Analyze prepared sides without materializing full production condition rows."""
    cond_analysis = _analyze_comparison(before["conditions"], after["conditions"], _CATEGORIES)
    configurations, objective = compare_history_configurations(before, after) if include_configurations else (None, None)
    return before, after, cond_analysis, configurations, objective
def materialize_history_conditions(before, after, cond_analysis, *, condition_page=1, condition_size=None, all_rows=True):
    """Materialize the requested page or all rows of production conditions."""
    return _materialize_comparison(before["conditions"], after["conditions"], cond_analysis, page=condition_page, size=condition_size, all_rows=all_rows)
