"""Exact-set bulk preview and atomic application; no partial success claims."""

import re

from core.models.workbench_batch import MAX_INTEGER, normalize_batch_input, object_fields, public_ref
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.workbench.batch_facts import BatchFacts, index_relations, related, require_unreferenced
from core.services.workbench.batch_operations import insert_operation, operation_code
from core.services.workbench.batch_projection import BatchProjection
from core.services.workbench.batches import WorkbenchBatchService


def normalize_bulk(payload):
    object_fields(payload, ("action", "refs", "patch"), ("action", "refs"))
    if payload["action"] not in ("update", "delete", "copy"):
        raise WorkbenchCommandRejected("invalid_input", "不支持的批量操作。", 400)
    refs = payload["refs"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 5000:
        raise WorkbenchCommandRejected("invalid_input", "请明确选择1至5000个批次。", 400)
    refs = [public_ref(ref) for ref in refs]
    if len(set(refs)) != len(refs):
        raise WorkbenchCommandRejected("invalid_input", "批次选择存在重复引用。", 400)
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
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.reader = BatchFacts(conn, logger)
        self.domain = WorkbenchBatchService(conn, logger)

    def plan(self, payload):
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
                require_unreferenced(facts, batch)
                if related(facts, batch)["materials"]:
                    raise WorkbenchCommandRejected("constraint_conflict", "所选批次仍有物料需求，未执行任何删除。")
            elif payload["action"] == "update":
                after = {**before, "fields": {**before["fields"], **payload["patch"]}}
            else:
                code = self._copy_code(batch["batch_id"], used)
                used.add(code)
                operations = [copied_operation(op, code) for op in before["operations"]]
                after = {**before, "ref": None, "business_code": code, "status": "pending", "stored_status": "pending",
                         "protected": False, "all_operations_complete": False,
                         "relationships": {**before["relationships"], "completed_count": 0, "plan_reference_count": 0,
                                           "gap_count": sum(bool(op["issues"]) for op in operations),
                                           "report_count": 0, "legacy_fact_count": 0,
                                           "execution_reference_count": 0, "material_requirement_count": 0},
                         "operations": operations,
                         "issues": [issue for issue in before["issues"] if issue["code"] != "completion_inconsistent"]}
            rows.append({"entity_ref": ref, "before": before, "after": after})
        return {"operation": "batch.bulk_confirm", "action": payload["action"], "rows": rows, "count": len(rows), "commit_policy": "atomic"}

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

    def apply(self, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("批量保存必须由工作台命令事务持有。")
        payload = normalize_bulk(payload)
        plan = self.plan(payload)
        source_facts = self.reader.load()
        source_batches = {row["batch_id"]: row for row in source_facts["Batches"]}
        source_relations = index_relations(source_facts)
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
                self.domain.domain.create(code, batch["part_no"], **{key: batch[key] for key in ("quantity", "due_date", "priority", "ready_status", "ready_date", "remark", "part_name")})
                for op in source_relations[batch["batch_id"]]["operations"]:
                    insert_operation(self.conn, code, op)
                identity = self.reader.identities.find_active("batch", code)
                if identity is None:
                    raise RuntimeError("复制批次缺少永久引用。")
                outcomes.append({"entity_ref": identity.ref, "source_ref": ref, "business_code": code, "result": "committed"})
        result = "committed" if any(row["result"] == "committed" for row in outcomes) else "unchanged"
        return WorkbenchCommandOutcome(result, {"items": outcomes, "count": len(outcomes), "commit_policy": "atomic", "action": payload["action"],
            "deleted_refs": payload["refs"] if payload["action"] == "delete" else []})
