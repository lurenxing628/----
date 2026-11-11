"""Public batch facts, never guessed scheduling or execution state."""

from typing import Any, Dict, List, Mapping, Tuple

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.workbench_batch import FIELDS, MAX_INTEGER, PRIORITIES, READY, STATUSES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import operation_code
from core.services.material.stage_availability import MaterialAvailability
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    group_from_context,
    member_index,
    merged_supplier_problem,
)
from core.services.workbench.process.projection import public_sequence
from core.shared.stored_dates import stored_date
from core.shared.strict_parse import is_exact_finite_number, is_stored_number

from .execution import batch_progress, copied_execution, operation_execution_fields
from .facts import delete_blocker, index_relations, unreferenced_blocker
from .resource_choices import BatchResourceFacts


def issue(message, code="data_gap"):
    return {"code": code, "message": message}


def numeric(value, issues, label, *, integer=False, positive=False):
    if not is_stored_number(value, positive=positive, integer=integer):
        issues.append(issue(label + ("未填写。" if value is None else "原值不合法，请核对。")))
        return None
    return value


def date_text(value, issues, label):
    if value is None:
        return None
    normalized = stored_date(value)
    if normalized is not None:
        return normalized
    issues.append(issue(label + "原值不合法，请核对。"))
    return str(value)


def _sequence_order(op):
    # 存量工序号可能混入非整数，先排整数，坏值排在后面照常展示，不让排序本身报错。
    return (0, op["seq"], op["id"]) if type(op["seq"]) is int else (1, repr(op["seq"]), op["id"])


def _active_refs(facts):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in facts["WorkbenchEntityRefs"] if row["active"]}


def _entity_ref(refs, kind, key):
    if key is None:
        return None
    value = refs.get((kind, str(key)))
    if value is None:
        raise WorkbenchCommandRejected("storage_failure", "有资料缺少系统编号，请联系维护人员核对资料。", 500)
    return value


def batch_choices(facts, links):
    refs = _active_refs(facts)
    return {"parts": [{"ref": _entity_ref(refs, "part", row["part_no"]), "business_code": row["part_no"], "label": row["part_name"]}
                      for row in facts["Parts"]],
            **{name: [{"ref": _entity_ref(refs, kind, row[key]), "business_code": row[key], "label": row["name"], "status": row["status"]}
                      for row in facts[table]]
               for name, kind, table, key in (("machines", "machine", "Machines", "machine_id"),
                                              ("operators", "operator", "Operators", "operator_id"),
                                              ("suppliers", "supplier", "Suppliers", "supplier_id"))},
            "authorizations": [{"machine_ref": _entity_ref(refs, "machine", mid), "operator_ref": _entity_ref(refs, "operator", oid)}
                               for oid, mid in sorted(links)]}


_POLICY_UNREFERENCED_MESSAGES = {
    "outsourcing": "已有外协发出或回厂登记，不能删除、重建或编辑工序，以免原登记无法继续核对回厂。",
    "protected": "已有排产、报工或执行状态记录，暂不能删除、替换或编辑工序。",
}
_POLICY_DELETE_MESSAGES = {
    "quantity_splits": "这个批次有数量拆分记录，需保留原批与子批以核对数量，不能删除。",
    "materials": "批次还挂着物料需求，不能删除。请先清除这个批次的物料需求，再删除批次。",
}


def batch_action_policy(entity: Mapping[str, Any]) -> Tuple[List[str], Dict[str, bool], List[Dict[str, str]]]:
    actions = ["batch.update", "batch.materials_update"]
    blocked: List[Dict[str, str]] = []
    relationships = entity["relationships"]
    has_outsourcing = bool(relationships["outsourcing_reference_count"])
    is_protected = entity["protected"]
    ref_blocker = unreferenced_blocker(has_outsourcing=has_outsourcing, is_protected=is_protected)
    if ref_blocker is None:
        actions.extend(("batch.sync_confirm", "batch.operation_update"))
        del_blocker = delete_blocker(
            has_outsourcing=has_outsourcing,
            is_protected=is_protected,
            has_quantity_splits=bool(relationships["quantity_split_reference_count"]),
            has_materials=bool(relationships["material_requirement_count"]),
        )
        if del_blocker is None:
            actions.append("batch.delete")
        else:
            blocked.append({"action": "batch.delete", "message": _POLICY_DELETE_MESSAGES[del_blocker]})
    else:
        reason = _POLICY_UNREFERENCED_MESSAGES[ref_blocker]
        for action in ("delete", "sync_confirm", "operation_update"):
            blocked.append({"action": "batch." + action, "message": reason})
    template = entity.get("template")
    if ref_blocker is None and template is not None and not template["complete"]:
        actions.remove("batch.sync_confirm")
        blocked.append({
            "action": "batch.sync_confirm",
            "message": "；".join(row["message"].rstrip("。") for row in template["diagnostics"]) + "。",
        })
    capabilities = {
        action: action in actions
        for action in (
            "batch.update",
            "batch.materials_update",
            "batch.delete",
            "batch.sync_confirm",
            "batch.operation_update",
        )
    }
    return actions, capabilities, blocked


class BatchProjection:
    def __init__(self, facts, relations=None):
        """relations 是同一份 facts 已建好的 index_relations 结果；调用方已有就传进来，不再建第二遍。"""
        self.facts = facts
        self.resources = BatchResourceFacts(facts)
        self.refs = _active_refs(facts)
        self.catalogs = self.resources.catalogs
        self.material_day = facts["material_day"]
        self.material_availability = MaterialAvailability(facts)
        self.relations = index_relations(facts) if relations is None else relations
        self.parts = {row["part_no"]: row for row in facts["Parts"]}
        self.external_contexts = {row["operation_id"]: row for row in facts["BatchExternalContexts"]}
        self.external_members = member_index(self.external_contexts, facts["BatchOperations"])
        self.machine_types = self.resources.machine_types

    def ref(self, kind, key):
        return _entity_ref(self.refs, kind, key)

    def resource(self, kind, key):
        if key is None:
            return None
        row = self.catalogs[kind].get(key)
        if row is None:
            return None
        return {
            "ref": self.ref(kind, key),
            "business_code": key,
            "label": row["name"],
            "status": None if kind == "op_type" else row["status"],
        }

    def internal_issues(self, row, numbers, issues):
        for key in ("setup_hours", "unit_hours"):
            numbers[key] = numeric(row[key], issues, "换型工时" if key == "setup_hours" else "单件工时")
        machine = self.catalogs["machine"].get(row["machine_id"])
        operator = self.catalogs["operator"].get(row["operator_id"])
        if machine is None or machine["status"] != "active":
            issues.append(issue("设备未补齐或不可用。"))
        if operator is None or operator["status"] != "active":
            issues.append(issue("人员未补齐或不在岗。"))
        if machine and row["op_type_id"] not in self.machine_types.get(row["machine_id"], set()):
            issues.append(issue("设备与工序工种不匹配。"))
        issues.extend(self.resources.operator_issues(row["operator_id"], row["op_type_id"], row["machine_id"]))

    def operation_issues(self, row, group, numbers):
        issues = []
        if row["source"] == "internal":
            self.internal_issues(row, numbers, issues)
        elif row["source"] == "external":
            supplier = self.catalogs["supplier"].get(row["supplier_id"])
            if supplier is None or supplier["status"] != "active":
                issues.append(issue("供应商未补齐或已停用。"))
            elif not self.resources.supplier_capable(row["supplier_id"], row["op_type_id"]):
                issues.append(issue("这家供应商没有登记这道外协工序的能力。"))
            if group and group["merge_mode"] == "merged":
                group["total_days"] = numeric(group["total_days"], issues, "整组周期", positive=True)
                # 合并组按整段周期排产，成员保留的逐序旧周期不生效，不再当工时原值校验或展示。
                numbers["ext_days"] = None
            else:
                numbers["ext_days"] = numeric(row["ext_days"], issues, "外协周期", positive=True)
        else:
            issues.append(issue("归属未明确。"))
        if row["op_type_id"] not in self.catalogs["op_type"]:
            issues.append(issue("工序工种未登记。"))
        # Hidden hours of external operations remain raw in storage, not defaulted.
        hidden_keys = (
            ("ext_days",) if row["source"] == "internal"
            else ("setup_hours", "unit_hours") if row["source"] == "external"
            else ("setup_hours", "unit_hours", "ext_days")
        )
        for key in hidden_keys:
            value = numbers[key]
            if value is not None and (not is_exact_finite_number(value) or abs(value) > MAX_INTEGER):
                issues.append(issue("工时或周期原值无效。"))
                numbers[key] = None
        return issues

    def _ledger(self, row):
        ref = self.facts["operation_refs"][row["id"]]
        return ref, self.facts["execution"]["projections"][ref]

    def _operation_values(self, batch, row, projection, *, include_details):
        group = context = None
        if row["source"] == "external":
            context = self.external_contexts.get(row["id"])
            problem = context_problem(context, operation_id=row["id"], part_no=batch["part_no"], sequence=row["seq"])
            if not problem:
                group = group_from_context(context)
                if include_details and group is not None:
                    group["start_sequence"] = public_sequence(group["start_sequence"])
                    group["end_sequence"] = public_sequence(group["end_sequence"])
        numbers = {key: row[key] for key in ("setup_hours", "unit_hours", "ext_days")}
        issues = self.operation_issues(row, group, numbers)
        if row["source"] == "external":
            if not problem:
                problem = merged_supplier_problem(context, row["supplier_id"],
                    self.external_members.get((row["batch_id"], context_group_key(context), row["piece_id"])))
            if problem:
                issues.append(issue(problem, "external_context_invalid"))
                numbers["ext_days"] = None
        execution = operation_execution_fields(row, projection, include_details=include_details)
        issues.extend(execution["data_gaps"])
        return group, numbers, execution, issues

    def operation_summary(self, batch, row):
        _, _, execution, issues = self._operation_values(batch, row, self._ledger(row)[1], include_details=False)
        return {"completed": execution["completed"], "execution_state": execution["execution_state"], "issues": issues}

    def operation(self, batch, row, protected):
        return self._operation(batch, row, protected, *self._ledger(row))

    def copied_operation(self, created, row):
        """复制出的工序：保留原工序的 id/batch_id 去核对随之复制的外协周期和合并组；执行情况是新批次里一道还没报工的新工序。"""
        copied = {**row, "op_code": operation_code(created["batch_id"], row["seq"], row["piece_id"]), "status": "pending"}
        execution = copied_execution(copied, created["quantity"], self._ledger(row)[1].plan_identity)
        return self._operation(created, copied, False, None, execution)

    def _operation(self, batch, row, protected, ref, projection):
        group, numbers, execution, issues = self._operation_values(batch, row, projection, include_details=True)
        resources = {kind: self.resource(kind, row[kind + "_id"]) for kind in ("machine", "operator", "supplier", "op_type")}
        return {"ref": ref, "operation_ref": ref, "business_code": row["op_code"], "sequence": public_sequence(row["seq"]),
                "piece_id": row["piece_id"], "label": row["op_type_name"], "source": row["source"], **execution,
                "setup_hours": numbers["setup_hours"], "unit_hours": numbers["unit_hours"],
                "external_days": numbers["ext_days"], **{kind + "_ref": item["ref"] if item else None for kind, item in resources.items()},
                "resources": resources, "external_group": group, "external_context_notice": None, "issues": issues,
                "editable": not protected and row["status"] == "pending" and row["source"] in OPERATION_SOURCES}

    def entity(self, row):
        return self._entity(row, include_operations=True, ref=self.ref("batch", row["batch_id"]))

    def summary(self, row, *, header=None):
        return self._entity(row, include_operations=False, ref=self.ref("batch", row["batch_id"]), header=header)

    def batch_header(self, row, *, readiness=None):
        part = self.parts.get(row["part_no"])
        if part is None:
            raise WorkbenchCommandRejected("storage_failure", "这个批次对应的零件已经不在了。请刷新重试；仍不行请联系维护人员。", 500)
        issues = []
        fields = {key: row[key] for key in FIELDS}
        fields["quantity"] = numeric(row["quantity"], issues, "数量", integer=True)
        for key in ("due_date", "ready_date"):
            fields[key] = date_text(row[key], issues, "交期" if key == "due_date" else "齐套日期")
        for key, allowed in (("priority", PRIORITIES), ("ready_status", READY), ("status", STATUSES)):
            if row[key] not in allowed:
                issues.append(issue("原优先级、齐套或状态标记不明确。"))
        display_ready, material_issues = (
            self.material_availability.readiness_state(row, self.material_day)
            if readiness is None
            else readiness
        )
        issues.extend(material_issues)
        return part, fields, display_ready, issues

    def updated_entity(self, row, before):
        """只改批次自身字段（优先级、交期、备注）的预览：工序投影只看零件号和工序行，直接沿用 before 的工序。"""
        return self._entity(row, include_operations=True, ref=before["ref"], operations=before["operations"])

    def copied_entity(self, source, created):
        """复制预览：新批次按提交后详情的同一套投影算出，原批次的关联和执行记录都不带过去。

        新批次的关联和齐套结果在这里单独算好显式传给 _entity，不写进本投影或共享的物料齐套索引。
        """
        source_facts = self.relations[source["batch_id"]]
        operations = [self.copied_operation(created, op) for op in sorted(source_facts["operations"], key=_sequence_order)]
        materials = source_facts["materials"]
        relations = {"operations": (), "materials": materials, "reports": (), "outsourcing_receipts": (),
                     "quantity_splits": (), "plan_reference_count": 0, "protected": False}
        # 复制出的需求行与提交后同口径：沿用需求量，到料量从 0 开始，未核对。
        copied = MaterialAvailability({"BatchMaterials": [
            {"id": index, "batch_id": created["batch_id"], "material_id": row["material_id"],
             "required_qty": row["required_qty"], "available_qty": 0, "ready_status": "no"}
            for index, row in enumerate(materials)]})
        return self._entity(created, include_operations=True, ref=None, operations=operations, relations=relations,
                            readiness=copied.readiness_state(created, self.material_day))

    def _entity(self, row, *, include_operations, ref, operations=None, relations=None, readiness=None, header=None):
        facts = self.relations[row["batch_id"]] if relations is None else relations
        part, fields, display_ready, issues = (
            self.batch_header(row, readiness=readiness) if header is None else header
        )
        if operations is not None:
            ops = operations
        elif include_operations:
            ops = [self.operation(row, op, facts["protected"]) for op in sorted(facts["operations"], key=_sequence_order)]
        else:
            # 摘要只取件数和完工统计，不需要工序顺序。
            ops = [self.operation_summary(row, op) for op in facts["operations"]]
        done, all_complete, status = batch_progress(ops, row["status"])
        if row["status"] == "completed" and (not ops or done != len(ops)):
            issues.append(issue("批次标着完成，但工序状态对不上，不能认定整批已完成。", "completion_inconsistent"))
        entity = {"ref": ref, "business_code": row["batch_id"], "label": part["part_name"],
                "status": status, "stored_status": row["status"],
                "fields": fields, "display_ready_status": display_ready, "relationships": {"part_ref": self.ref("part", row["part_no"]),
                    "part_no": row["part_no"], "part_name": part["part_name"], "operation_count": len(ops), "completed_count": done,
                    "gap_count": sum(bool(op["issues"]) for op in ops), "plan_reference_count": facts["plan_reference_count"],
                    "outsourcing_reference_count": len(facts["outsourcing_receipts"]),
                    "quantity_split_reference_count": len(facts["quantity_splits"]),
                    "execution_reference_count": len(facts["reports"]),
                    "material_requirement_count": len(facts["materials"])},
                "all_operations_complete": all_complete, "issues": issues,
                "write_context": None, "protected": facts["protected"]}
        if include_operations:
            entity["operations"] = ops
        return entity

    def materials(self, batch):
        from core.models.workbench_batch_material import material_row_key, numbered_material_requirements
        availability = self.material_availability
        materials = {row["material_id"]: row for row in self.facts["Materials"]}
        rows = []
        batch_ref = self.ref("batch", batch["batch_id"])
        for ordinal, row in numbered_material_requirements(self.relations[batch["batch_id"]]["materials"]):
            material = materials.get(row["material_id"])
            issues = []
            rows.append({"row_key": material_row_key(batch_ref, ordinal),
                         "material_ref": self.ref("material", row["material_id"]), "business_code": row["material_id"],
                         "label": material["name"] if material else None, "unit": material["unit"] if material else None,
                         "required_quantity": numeric(row["required_qty"], issues, "需求数量", positive=True),
                         "available_quantity": numeric(row["available_qty"], issues, "到料数量"),
                         "ready_status": row["ready_status"], "issues": issues,
                         "operation_ref": self.facts["operation_refs"].get(availability.stages.get(row["id"])),
                         "arrivals": [{"arrival_date": date_text(item["arrival_date"], issues, "到料日期"),
                                       "quantity": numeric(item["quantity"], issues, "分批到料数量", positive=True)}
                                      for item in availability.arrivals[row["id"]]]})
        return {"basis": "batch_material_requirements_not_stock", "requirements": rows, "count": len(rows),
                "display_status": availability.readiness_state(batch, self.material_day)[0], "display_date": date_text(batch["ready_date"], [], "齐套日期")}
