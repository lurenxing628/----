"""Verified outsourcing source instances: judgement over exact repository facts.

Source binding resolves the current batch relation without manufacturing
historical birth records; readable labels are nullable projections of verified,
snapshot-local instances. The repository only reads; every rejection is here.
"""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing import MAX_ROWS, bounded, label, raw_facts, reject
from data.repositories.workbench_outsourcing_source_repo import WorkbenchOutsourcingSourceRepository

MEMBER_KEYS = ("op_code", "batch_id", "piece_id", "seq", "op_type_id", "op_type_name", "source", "supplier_id")


def _target_text(value):
    return value if type(value) is str and value.strip() and "\x00" not in value else None


def resolve_source_binding(repo, operation_ref, origin, batch_ref):
    confirmation = repo.source_confirmation(operation_ref)
    if confirmation is not None:
        valid = repo.confirmation_matches_receipt(operation_ref, confirmation["batch_ref"], confirmation["fact_ref"])
        if origin["batch_ref"] is not None or not valid:
            reject("工序的来源确认与原外协登记不一致，请核对原登记。", "identity_drift", 409)
    if origin["batch_ref"] is not None:
        resolved_ref, basis = origin["batch_ref"], "birth_record"
    elif confirmation is not None:
        resolved_ref, basis = confirmation["batch_ref"], "registration_confirmation"
    else:
        if repo.has_membership(operation_ref):
            reject("已有外协登记缺少原批次的确认记录，请先核对原登记。", "identity_missing", 409)
        resolved_ref, basis = batch_ref, "current_relation"
    if resolved_ref != batch_ref:
        reject("工序所属批次实例已变化，请核对批次与工序关联。", "identity_drift", 409)
    return {"batch_ref": resolved_ref, "confirmation": confirmation,
            "source_resolution": {"basis": basis, "confirmation_ref": confirmation["fact_ref"] if confirmation is not None else None}}


def source_resolution(operations):
    resolutions = [op["binding"]["source_resolution"] for op in operations]
    basis = ("current_relation" if any(item["basis"] == "current_relation" for item in resolutions)
             else "registration_confirmation" if any(item["basis"] == "registration_confirmation" for item in resolutions)
             else "birth_record")
    refs = {item["confirmation_ref"] for item in resolutions if item["confirmation_ref"] is not None}
    if len(refs) > 1:
        reject("所选工序已分别登记，不能合成另一条登记。", "constraint_conflict", 409)
    return {"basis": basis, "confirmation_ref": next(iter(refs)) if refs else None}


class WorkbenchOutsourcingSourceService:
    def __init__(self, conn):
        self.repo = WorkbenchOutsourcingSourceRepository(conn)

    def entity(self, ref, kind):
        identity = self.repo.entity_identity(ref, kind)
        if identity is None:
            reject("原批次、零件或供应商已删除，请刷新重选。", "entity_not_found", 404)
        source = self.repo.source_row(kind, identity["entity_key"])
        if source is None:
            reject("原关联记录不存在，请联系维护人员核对。", "identity_missing", 409)
        return {"identity": identity, "row": source}

    def _active_ref(self, kind, key):
        ref = self.repo.active_ref(kind, key)
        if ref is None:
            reject("来源关联资料缺失，请联系维护人员核对。", "identity_missing", 409)
        return ref

    def operation(self, ref):
        identity = self.repo.operation_identity(ref)
        if identity is None:
            reject("原工序已删除，请刷新重选。", "entity_not_found", 404)
        row = self.repo.source_row("operation", identity["source_key"])
        origin = self.repo.operation_origin(ref)
        if row is None or origin is None:
            raise WorkbenchCommandRejected("identity_missing", "工序与批次的关联资料缺失，无法核对外协状态，请联系维护人员。", 409)
        batch_ref = self._active_ref("batch", row["batch_id"])
        binding = resolve_source_binding(self.repo, ref, origin, batch_ref)
        return {"identity": identity, "origin": origin, "row": row, "binding": binding}

    def require_contiguous(self, operations):
        """Validate new shipment membership; historical receipts keep their original membership."""
        if len(operations) < 2:
            return
        first = operations[0]["row"]
        route = self.repo.route_rows(first["batch_id"], first["piece_id"])
        selected = {op["row"]["id"] for op in operations}
        positions = [index for index, row in enumerate(route) if row["id"] in selected]
        if len(positions) != len(selected):
            reject("所选工序的工艺顺序已变化，请刷新后重新选择。", "identity_drift", 409)
        between = route[min(positions):max(positions) + 1]
        if any(row["id"] not in selected for row in between):
            reject("合并发出必须选择同一次外协的连续工序，不能跨过自制工序或漏选中间工序。请按实际发出阶段分别登记。", "constraint_conflict", 409)

    def load(self, target, *, new_registration=False):
        batch = self.entity(target["batch_ref"], "batch")
        supplier = self.entity(target["supplier_ref"], "supplier")
        part = self.entity(self._active_ref("part", batch["row"]["part_no"]), "part")
        operations = [self.operation(ref) for ref in target["operation_refs"]]
        for op in operations:
            row = op["row"]
            if row["source"] != "external" or op["binding"]["batch_ref"] != target["batch_ref"]:
                reject("登记成员必须是所选批次的真实外协工序。", "constraint_conflict", 409)
            if row["supplier_id"] != supplier["row"]["supplier_id"]:
                reject("登记供应商与工序承接供应商不一致，请核对。", "constraint_conflict", 409)
        if len({op["row"]["piece_id"] for op in operations}) != 1:
            reject("合并发出的工序须属于同一批次分件。", "constraint_conflict", 409)
        if new_registration:
            self.require_contiguous(operations)
        identity = {"batch_ref": target["batch_ref"], "part_ref": part["identity"]["ref"],
                    "supplier_ref": target["supplier_ref"], "members": [
                        {"operation_ref": op["identity"]["ref"], **{key: op["row"][key] for key in MEMBER_KEYS}}
                        for op in operations]}
        public = {**target, "grouping_basis": "explicit_receipt_membership", "source_resolution": source_resolution(operations),
                  "part": {"ref": part["identity"]["ref"], "business_code": _target_text(part["row"]["part_no"]),
                           "label": _target_text(part["row"]["part_name"])},
                  "batch": {"ref": target["batch_ref"], "business_code": label(batch["row"]["batch_id"]),
                            "label": label(batch["row"]["part_name"])},
                  "supplier": {"ref": target["supplier_ref"], "business_code": label(supplier["row"]["supplier_id"]),
                               "label": label(supplier["row"]["name"])},
                  "operations": [{"operation_ref": op["identity"]["ref"], "business_code": label(op["row"]["op_code"]),
                                  "sequence": label(op["row"]["seq"]), "piece": label(op["row"]["piece_id"]),
                                  "label": label(op["row"]["op_type_name"])} for op in operations]}
        clock = self.repo.plan_identity_revision()
        return {"public": bounded(public), "identity": raw_facts(identity),
                "source_confirmations": [op["identity"]["ref"] for op in operations
                                         if op["binding"]["source_resolution"]["basis"] == "current_relation"],
                "facts": bounded(raw_facts({"batch": batch, "part": part, "supplier": supplier,
                                           "operations": operations, "source_clock": clock}))}

    @staticmethod
    def _target_entity_labels(row, kind, source):
        ref = row[kind + "_ref"]
        # A registered member must not display a same-number replacement as its original object.
        if row["outsourcing_ref"] is not None and row["receipt_" + kind + "_ref"] != ref:
            return None
        public = source["public"][kind]
        return {"ref": ref, "business_code": _target_text(public["business_code"]), "label": _target_text(public["label"])}

    def targets(self, batch_ref=None, query=""):
        """Add nullable batch/supplier {ref, business_code, label}; unknown text stays null."""
        return [item for item, source in self.load_targets(batch_ref, query)]

    def load_targets(self, batch_ref=None, query=""):
        """Read each target and its verified source once in the caller's snapshot."""
        batch_id = None
        if batch_ref is not None:
            batch_id = self.entity(batch_ref, "batch")["row"]["batch_id"]
        rows = self.repo.external_operation_rows(batch_id, MAX_ROWS, query)
        if len(rows) > MAX_ROWS:
            reject("外协工序超过10000项，请按批次号或工序查找，缩小范围。", "query_too_large", 413)
        result = []
        for row in rows:
            source = None
            item = {"operation_ref": row["operation_ref"], "business_code": label(row["op_code"]),
                    "sequence": label(row["seq"]), "piece": label(row["piece_id"]),
                    "label": label(row["op_type_name"]), "batch_ref": row["batch_ref"], "supplier_ref": row["supplier_ref"],
                    "outsourcing_ref": row["outsourcing_ref"], "can_register": False, "issues": [],
                    "batch": None, "supplier": None, "part": None, "source_resolution": None}
            if any(row[key] is None for key in ("operation_ref", "batch_ref", "supplier_ref")):
                item["issues"] = [{"code": "identity_missing", "message": "工序或供应商关联资料缺失，无法登记，请联系维护人员。"}]
            else:
                # Known per-row identity gaps stay visible; storage failures propagate.
                try:
                    source = self.load({"kind": "single", "batch_ref": row["batch_ref"], "supplier_ref": row["supplier_ref"],
                                        "operation_refs": [row["operation_ref"]]})
                    item["can_register"] = row["outsourcing_ref"] is None
                    item["batch"] = self._target_entity_labels(row, "batch", source)
                    item["supplier"] = self._target_entity_labels(row, "supplier", source)
                    item["part"] = source["public"]["part"]
                    item["source_resolution"] = source["public"]["source_resolution"]
                except WorkbenchCommandRejected as exc:
                    item["issues"] = [{"code": exc.code, "message": str(exc)}]
            result.append((item, source))
        bounded([item for item, source in result])
        return result
