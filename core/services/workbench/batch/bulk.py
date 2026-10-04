"""Exact-set bulk preview and atomic application; no partial success claims."""

import re

from core.models.workbench_batch import MAX_INTEGER, normalize_batch_input, object_fields, public_ref
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.workbench.calibration.template_lineage import TemplateLineageWriter
from data.repositories.batch_material_repo import BatchMaterialRepository

from .facts import BatchFacts, require_deletable
from .operations import insert_operation, operation_code
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
                code = self._copy_code(batch["batch_id"], used)
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
    def _copy_code(code, used):
        match = re.search(r"([0-9]+)$", code)
        prefix = code[:match.start()] if match else code + "-copy-"
        digits = len(match[1]) if match else 1
        serial = int(match[1]) if match else 0
        while serial < MAX_INTEGER:
            serial += 1
            candidate = prefix + str(serial).zfill(digits)
            if len(candidate) > 200:
                break
            if candidate not in used:
                return candidate
        raise WorkbenchCommandRejected("constraint_conflict", "无法为复制批次分配有效编号，请手工新增。")

    def _delete(self, payload, plan, relations):
        # 逐批走 apply 会在每删一批后重读整本批次数据；一次删完，写锁不随批数成倍拉长。
        self.domain.delete_many([row["entity_ref"] for row in plan["rows"]], relations_index=relations)
        outcomes = [{"entity_ref": row["entity_ref"], "result": "committed", "business_code": row["before"]["business_code"]}
                    for row in plan["rows"]]
        return WorkbenchCommandOutcome("committed", {"items": outcomes, "count": len(outcomes), "commit_policy": "atomic",
                                                     "action": "delete", "deleted_refs": payload["refs"]})

    def apply(self, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("批量保存必须由工作台命令事务持有。")
        payload = normalize_bulk(payload)
        # 预检和第一次写入之间没有写入，预检用的那份数据和它的关联索引就是写入前的原样。
        plan, projection = self._plan(payload)
        if payload["action"] == "delete":
            return self._delete(payload, plan, projection.relations)
        source_batches = {row["batch_id"]: row for row in projection.facts["Batches"]}
        source_relations = projection.relations
        writer = TemplateLineageWriter(self.conn)
        outcomes = []
        for row in plan["rows"]:
            ref = row["entity_ref"]
            if payload["action"] != "copy":
                body = {"fields": payload["patch"]} if payload["action"] == "update" else {}
                result = self.domain.apply(payload["action"], body, ref)
                outcomes.append({"entity_ref": ref, "result": result.result, "business_code": row["before"]["business_code"]})
            else:
                batch = source_batches[row["before"]["business_code"]]
                code = row["after"]["business_code"]
                fields = {key: batch[key] for key in ("quantity", "due_date", "priority", "remark", "part_name")}
                self.domain.domain.create(code, batch["part_no"], **fields, ready_status="no", ready_date=None)
                mapping = {op["id"]: insert_operation(self.conn, code, op, writer=writer)
                           for op in source_relations[batch["batch_id"]]["operations"]}
                BatchMaterialRepository(self.conn).copy_requirements(batch["batch_id"], code, mapping)
                identity = self.reader.identities.find_active("batch", code)
                if identity is None:
                    raise RuntimeError("复制批次缺少永久引用。")
                outcomes.append({"entity_ref": identity.ref, "source_ref": ref, "business_code": code, "result": "committed"})
        result = "committed" if any(row["result"] == "committed" for row in outcomes) else "unchanged"
        return WorkbenchCommandOutcome(result, {"items": outcomes, "count": len(outcomes), "commit_policy": "atomic", "action": payload["action"],
            "deleted_refs": payload["refs"] if payload["action"] == "delete" else []})
