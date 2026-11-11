"""Exact-set bulk preview and atomic application; no partial success claims."""

import re

from core.models.workbench_batch import MAX_INTEGER, normalize_batch_input, object_fields, public_ref
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.scheduler.template_lineage import TemplateLineageWriter
from data.repositories.batch_material_repo import BatchMaterialRepository

from .projection import BatchProjection
from .scope import BatchFactScope
from .service import WorkbenchBatchService, stored_batch_values


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


class WorkbenchBatchBulkService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.domain = WorkbenchBatchService(conn, logger)

    def _prepare_changes(self, payload, preparation):
        prepared, successors = [], {}
        for ref in payload["refs"]:
            if payload["action"] == "copy":
                batch = preparation.batch(ref)
                code = self._copy_code(batch["batch_id"], preparation.used_codes, successors)
                with stored_batch_values(ref, batch, "复制"):
                    change = preparation.copy(batch, code)
            else:
                change = preparation.prepare(payload["action"], {"fields": payload["patch"]}, ref)
                batch = preparation.batches[change.business_code]
            prepared.append((ref, batch, change))
        return prepared

    def _prepare_copy_relations(self, facts, source_relations, changes):
        bindings = {row["requirement_id"]: row["operation_id"] for row in facts["BatchMaterialStages"]}
        requirements = {}
        source_operations = []
        for _ref, batch, _change in changes:
            batch_id = batch["batch_id"]
            operations = source_relations[batch_id]["operations"]
            operation_ids = {op["id"] for op in operations}
            batch_requirements = []
            for row in source_relations[batch_id]["materials"]:
                operation_id = bindings.get(row["id"])
                if operation_id is not None and operation_id not in operation_ids:
                    raise WorkbenchCommandRejected("material_stage_invalid", "物料使用工序已失效或不属于本批，请重新选择。")
                batch_requirements.append(dict(row, operation_id=operation_id))
            requirements[batch_id] = batch_requirements
            source_operations.extend(operations)
        writer = TemplateLineageWriter(self.conn)
        prepared_rows = writer.prepare_instances(source_operations, facts=facts, complete_facts=True)
        return writer, {op["id"]: ready for op, ready in zip(source_operations, prepared_rows)}, requirements

    def plan_normalized(self, scope: BatchFactScope, payload):
        facts = scope.load()
        preparation = self.domain.preparation(scope)
        prepared = self._prepare_changes(payload, preparation)
        # 关系索引由 preparation 按需建一次（删除准备时已建好，修改和复制在这里首次建），投影直接复用同一份。
        projection = BatchProjection(facts, preparation.relations)
        if payload["action"] == "copy":
            self._prepare_copy_relations(facts, projection.relations, prepared)
        rows = []
        for ref, batch, change in prepared:
            before = projection.entity(batch)
            after = None
            if payload["action"] == "update":
                after = projection.updated_entity({**batch, **change.fields}, before)
            elif payload["action"] == "copy":
                after = projection.copied_entity(batch, change.created.to_dict())
            rows.append({"entity_ref": ref, "before": before, "after": after})
        return {
            "operation": "batch.bulk_confirm",
            "action": payload["action"],
            "rows": rows,
            "count": len(rows),
            "commit_policy": "atomic",
            "warnings": (
                [{"code": "copied_materials_unconfirmed", "message": "复制时保留物料需求，到料量从 0 开始，齐套和齐套日期需要重新核对。"}]
                if payload["action"] == "copy"
                else []
            ),
        }

    @staticmethod
    def _copy_code(code, used, successors):
        """Find the nearest free suffix, sharing occupied runs within this operation."""
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

    def apply_normalized(self, scope: BatchFactScope, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("批量保存必须由工作台命令事务持有。")
        if payload["action"] in ("delete", "copy"):
            scope.load()
        preparation = self.domain.preparation(scope)
        prepared = self._prepare_changes(payload, preparation)
        if payload["action"] == "copy":
            relations = preparation.relations
            return self._copy(payload, preparation.facts, relations, prepared)
        applied = self.domain.apply_prepared_many([change for _ref, _batch, change in prepared])
        outcomes = [{**item.data, "result": item.result} for item in applied]
        result = self._outcome(payload, outcomes)
        if payload["action"] == "delete":
            result.data["deleted_refs"] = payload["refs"]
        return result

    def _copy(self, payload, facts, source_relations, changes):
        writer, prepared, requirements = self._prepare_copy_relations(facts, source_relations, changes)
        applied = self.domain.apply_prepared_many([change for _ref, _batch, change in changes])
        outcomes = []
        for (ref, batch, change), result in zip(changes, applied):
            code = change.business_code
            mapping = {
                op["id"]: writer.copy_prepared_instance(code, prepared[op["id"]])
                for op in source_relations[batch["batch_id"]]["operations"]
            }
            BatchMaterialRepository(self.conn).copy_requirements(
                code, mapping, requirements=requirements[batch["batch_id"]]
            )
            outcomes.append({**result.data, "source_ref": ref, "result": "committed"})
        return self._outcome(payload, outcomes)

    @staticmethod
    def _outcome(payload, outcomes):
        result = "committed" if any(row["result"] == "committed" for row in outcomes) else "unchanged"
        return WorkbenchCommandOutcome(
            result,
            {
                "items": outcomes,
                "count": len(outcomes),
                "commit_policy": "atomic",
                "action": payload["action"],
                "deleted_refs": [],
            },
        )
