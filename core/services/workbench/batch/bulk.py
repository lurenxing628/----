"""Exact-set bulk preview and atomic application; no partial success claims."""

import re
from collections import defaultdict

from core.models.workbench_batch import MAX_INTEGER, normalize_batch_input, object_fields, public_ref
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_template_lineage import operation_code
from core.services.workbench.calibration.template_lineage import TemplateLineageWriter
from data.repositories.batch_material_repo import BatchMaterialRepository

from .facts import BatchFacts, require_deletable
from .projection import BatchProjection
from .service import WorkbenchBatchService


def normalize_bulk(payload):
    object_fields(payload, ("action", "refs", "patch"), ("action", "refs"))
    if payload["action"] not in ("update", "delete", "copy"):
        raise WorkbenchCommandRejected("invalid_input", "不支持这种批量操作。", 400)
    refs = payload["refs"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 5000:
        raise WorkbenchCommandRejected("invalid_input", "请选择 1 到 5000 批。", 400)
    refs = [public_ref(ref) for ref in refs]
    if len(set(refs)) != len(refs):
        raise WorkbenchCommandRejected("invalid_input", "选中的批次里有重复，请重新选择。", 400)
    patch = object_fields(payload.get("patch", {}), ("priority", "due_date", "remark") if payload["action"] == "update" else ())
    if payload["action"] == "update":
        patch = normalize_batch_input("update", {"fields": patch})["fields"]
    return {"action": payload["action"], "refs": sorted(refs), "patch": patch}


def copied_operation(op, code):
    return {**op, "ref": None, "operation_ref": None, "status": "pending", "stored_status": "pending", "completed": False,
            "execution": None, "execution_state": "unreported", "data_quality": "incomplete", "data_gaps": [],
            "issues": [row for row in op["issues"] if row not in op["data_gaps"]],
            "editable": op["source"] in ("internal", "external"),
            "business_code": operation_code(code, op["sequence"], op["piece_id"])}


class WorkbenchBatchBulkService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.reader = reader if reader is not None else BatchFacts(conn, logger)
        self.domain = WorkbenchBatchService(conn, logger, facts=self.reader)

    def plan(self, payload):
        return self._plan(payload)[0]

    def _plan(self, payload):
        """预检结果连同算它用的投影一起返回：确认时直接沿用投影里那份关联索引，不再按同一份数据重建。"""
        payload = normalize_bulk(payload)
        facts = self.reader.load()
        projection = BatchProjection(facts)
        used = {row["batch_id"] for row in facts["Batches"]}
        successors = {}
        rows = []
        for ref in payload["refs"]:
            batch = self.reader.batch(ref)
            before = projection.entity(batch)
            after = None
            if payload["action"] == "delete":
                require_deletable(facts, batch, projection.relations[batch["batch_id"]])
            elif payload["action"] == "update":
                after = {**before, "fields": {**before["fields"], **payload["patch"]}}
            else:
                code = self._copy_code(batch["batch_id"], used, successors)
                used.add(code)
                operations = [copied_operation(op, code) for op in before["operations"]]
                after = {**before, "ref": None, "business_code": code, "status": "pending", "stored_status": "pending",
                         "fields": {**before["fields"], "ready_status": "no", "ready_date": None},
                         "protected": False, "all_operations_complete": False,
                         "relationships": {**before["relationships"], "completed_count": 0, "plan_reference_count": 0,
                                           "outsourcing_reference_count": 0,
                                           "gap_count": sum(bool(op["issues"]) for op in operations),
                                           "report_count": 0, "legacy_fact_count": 0,
                                           "execution_reference_count": 0},
                         "operations": operations,
                         "issues": [issue for issue in before["issues"] if issue["code"] != "completion_inconsistent"]}
            rows.append({"entity_ref": ref, "before": before, "after": after})
        return {"operation": "batch.bulk_confirm", "action": payload["action"], "rows": rows, "count": len(rows), "commit_policy": "atomic",
                "warnings": ([{"code": "copied_materials_unconfirmed", "message": "复制时保留物料需求，到料量从 0 开始，齐套和齐套日期需要重新核对。"}]
                             if payload["action"] == "copy" else [])}, projection

    @staticmethod
    def _copy_code(code, used, successors=None):
        """Find the nearest free suffix, sharing occupied runs within this operation."""
        successors = {} if successors is None else successors
        match = re.search(r"([0-9]+)$", code)
        prefix = code[:match.start()] if match else code + "-copy-"
        digits = len(match[1]) if match else 1
        serial = (int(match[1]) if match else 0) + 1
        following, visited = successors.setdefault((prefix, digits), {}), []
        while serial <= MAX_INTEGER:
            if serial in following:
                visited.append(serial)
                serial = following[serial]
                continue
            candidate = prefix + str(serial).zfill(digits)
            if len(candidate) > 200:
                break
            if candidate not in used:
                # Only occupied suffixes are cached. Another padding width may claim
                # this candidate later; the shared used set remains authoritative.
                for occupied in visited:
                    following[occupied] = serial
                return candidate
            visited.append(serial)
            serial += 1
        raise WorkbenchCommandRejected("constraint_conflict", "无法为复制批次分配有效编号，请手工新增。")

    def apply(self, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("批量保存必须由工作台命令事务持有。")
        payload = normalize_bulk(payload)
        facts = self.reader.load()
        preparation = self.domain.preparation(facts)
        prepared, successors = [], {}
        for ref in payload["refs"]:
            batch = preparation.batch(ref)
            if payload["action"] == "copy":
                code = self._copy_code(batch["batch_id"], preparation.used_codes, successors)
                change = preparation.copy(batch, code)
            else:
                change = preparation.prepare(payload["action"], {"fields": payload["patch"]}, ref)
            prepared.append((ref, batch, change))
        if payload["action"] == "copy":
            return self._copy(payload, facts, preparation.relations, prepared)
        outcomes = []
        for _ref, _batch, change in prepared:
            result = self.domain.apply_prepared(change)
            outcomes.append({**result.data, "result": result.result})
        result = self._outcome(payload, outcomes)
        if payload["action"] == "delete":
            result.data["deleted_refs"] = payload["refs"]
        return result

    def _copy(self, payload, facts, source_relations, changes):
        requirements = defaultdict(list)
        bindings = {row["requirement_id"]: row["operation_id"] for row in facts["BatchMaterialStages"]}
        for row in facts["BatchMaterials"]:
            requirements[row["batch_id"]].append(dict(row, operation_id=bindings.get(row["id"])))
        writer = TemplateLineageWriter(self.conn)
        source_operations = [op for _ref, batch, _change in changes
                             for op in source_relations[batch["batch_id"]]["operations"]]
        prepared_rows = writer.prepare_instances(source_operations, facts=facts)
        prepared = {op["id"]: ready for op, ready in zip(source_operations, prepared_rows)}
        outcomes = []
        for ref, batch, change in changes:
            code = change.business_code
            result = self.domain.apply_prepared(change)
            mapping = {op["id"]: writer.copy_prepared_instance(code, prepared[op["id"]])
                       for op in source_relations[batch["batch_id"]]["operations"]}
            BatchMaterialRepository(self.conn).copy_requirements(batch["batch_id"], code, mapping,
                                                               requirements=requirements[batch["batch_id"]])
            outcomes.append({**result.data, "source_ref": ref, "result": "committed"})
        return self._outcome(payload, outcomes)

    @staticmethod
    def _outcome(payload, outcomes):
        result = "committed" if any(row["result"] == "committed" for row in outcomes) else "unchanged"
        return WorkbenchCommandOutcome(result, {"items": outcomes, "count": len(outcomes), "commit_policy": "atomic", "action": payload["action"],
                                               "deleted_refs": []})
