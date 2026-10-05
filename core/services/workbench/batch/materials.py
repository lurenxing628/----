"""Maintain batch material requirements inside the guarded command transaction."""

from collections import defaultdict
from datetime import date
from typing import cast

from core.models.enums import ReadyStatus
from core.models.workbench_batch import number
from core.models.workbench_batch_material import material_row_key, normalize_material_changes
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.material.stage_availability import covers_quantity, quantity
from data.repositories.batch_material_repo import BatchMaterialRepository
from data.repositories.batch_material_stage_repo import BatchMaterialStageRepository
from data.repositories.batch_repo import BatchRepository

from .facts import BatchFacts


class WorkbenchBatchMaterialService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.reader = reader if reader is not None else BatchFacts(conn, logger)
        self.repo = BatchMaterialRepository(conn, logger)
        self.batches = BatchRepository(conn, logger)
        self.stages = BatchMaterialStageRepository(conn, logger)

    def _proposed(self, ref, payload, batch, facts):
        requirements = [row for row in facts["BatchMaterials"] if row["batch_id"] == batch["batch_id"]]
        requirement_ids = {row["id"] for row in requirements}
        bindings = {row["requirement_id"]: row["operation_id"] for row in facts["BatchMaterialStages"]}
        arrivals = defaultdict(list)
        rows = [row for row in facts["BatchMaterialArrivals"] if row["requirement_id"] in requirement_ids]
        # Match SQLite's TEXT-before-BLOB order without comparing unrelated storage types.
        for row in sorted(rows, key=lambda row: (isinstance(row["arrival_date"], bytes), row["arrival_date"], row["id"])):
            arrivals[row["requirement_id"]].append({key: row[key] for key in ("arrival_date", "quantity")})
        old = {material_row_key(ref, row): dict(row, operation_id=bindings.get(row["id"]), arrivals=arrivals[row["id"]])
               for row in requirements}
        if set(payload["removed_keys"]) - set(old):
            raise WorkbenchCommandRejected("stale_write", "要移除的物料需求已变化，请刷新后重新核对。")
        final = {key: dict(row) for key, row in old.items() if key not in payload["removed_keys"]}
        materials = {row["material_id"]: row for row in facts["Materials"]}
        for index, item in enumerate(payload["rows"]):
            key = item["row_key"]
            final[key or "new:" + str(index)] = self._material_row(item, key, old, materials, batch, facts)
        return old, final

    def _material_row(self, item, key, old, materials, batch, facts):
        if key is not None and key not in old:
            raise WorkbenchCommandRejected("stale_write", "要修改的物料需求已变化，请刷新后重新核对。")
        identity = self.reader.resolve(item["material_ref"], "material")
        if key is not None and old[key]["material_id"] != identity.entity_key:
            raise WorkbenchCommandRejected("constraint_conflict", "已有需求不能直接更换物料，请明确移除后重新新增。")
        if key is None and materials[identity.entity_key]["status"] != "active":
            raise WorkbenchCommandRejected("constraint_conflict", "所选物料已停用，请选择启用的物料。")
        operation = self._operation_id(item, old[key]["operation_id"] if key else None, batch, facts)
        return {"id": old[key]["id"] if key else None, "operation_id": operation,
            "arrivals": item.get("arrivals", old[key]["arrivals"] if key else []),
            "batch_id": batch["batch_id"], "material_id": identity.entity_key,
            "required_qty": item["required_quantity"], "available_qty": item["available_quantity"]}

    @staticmethod
    def _operation_id(item, previous, batch, facts):
        if "operation_ref" not in item:
            return previous
        if item["operation_ref"] is None:
            return None
        match = next((row for row in facts["BatchOperations"] if row["batch_id"] == batch["batch_id"]
                      and facts["operation_refs"][row["id"]] == item["operation_ref"]), None)
        if match is None or match.get("piece_id") is not None:
            raise WorkbenchCommandRejected("constraint_conflict", "请选择本批次有效的整批用料工序。")
        return match["id"]

    @staticmethod
    def _ready(rows):
        codes, flags = set(), []
        for row in rows:
            if (row["material_id"], row["operation_id"]) in codes:
                raise WorkbenchCommandRejected("constraint_conflict", "同一物料在同一道用料工序只能保留一条需求，请合并后再保存。")
            codes.add((row["material_id"], row["operation_id"]))
            required = number(row["required_qty"], "required_quantity", positive=True)
            available = number(row["available_qty"], "available_quantity")
            if required is None or available is None:
                raise WorkbenchCommandRejected("invalid_input", "需求量和到料量不能为空，请明确填写。", 422)
            available = quantity(available) + sum(quantity(item["quantity"]) for item in row["arrivals"] if item["arrival_date"] <= date.today().isoformat())
            row["ready_status"] = ReadyStatus.YES.value if covers_quantity(available, quantity(required)) else ReadyStatus.NO.value
            flags.append((row["ready_status"] == ReadyStatus.YES.value, available > 0))
        if flags and all(flag[0] for flag in flags):
            return ReadyStatus.YES.value
        return ReadyStatus.PARTIAL.value if any(flag[1] for flag in flags) else ReadyStatus.NO.value

    def apply(self, ref, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("物料需求维护必须由工作台命令事务持有。")
        payload = normalize_material_changes(payload)
        batch, facts = self.reader.batch(ref), self.reader.load()
        if type(batch["quantity"]) is not int or batch["quantity"] < 0:
            raise WorkbenchCommandRejected("constraint_conflict", "请先在批次基础信息中填好数量，再核对物料需求。")
        old, final = self._proposed(ref, payload, batch, facts)
        ready = self._ready(list(final.values()))
        changed = bool(payload["removed_keys"])
        for key in payload["removed_keys"]:
            self.repo.delete(cast(int, old[key]["id"]))
        reviewed = {item["requirement_id"]: item["batch_quantity"] for item in facts.get("BatchMaterialReviews", [])}
        touched = {item["row_key"] for item in payload["rows"]}
        changed = self._save_requirements(batch, old, final, touched, reviewed) or changed
        if any(key not in touched and key in old and reviewed.get(row["id"], batch["quantity"]) != batch["quantity"]
               for key, row in final.items()):
            ready = "no"
        if ready != batch["ready_status"]:
            self.batches.update(batch["batch_id"], {"ready_status": ready})
            changed = True
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {
            "entity_ref": ref, "business_code": batch["batch_id"], "material_count": len(final), "ready_status": ready})

    def _save_requirements(self, batch, old, final, touched, reviewed):
        changed = False
        for key, row in final.items():
            changed = self._save_row(batch, row, old.get(key)) or changed
            if (key not in old or key in touched) and reviewed.get(row["id"]) != batch["quantity"]:
                self.stages.review(row["id"], batch["quantity"])
                changed = True
        return changed

    def _save_row(self, batch, row, previous):
        fields = {name: row[name] for name in ("required_qty", "available_qty", "ready_status")}
        if row["id"] is None:
            row["id"] = self.repo.add(batch["batch_id"], row["material_id"], **fields).id
            if row["operation_id"] is not None:
                self.stages.replace_operation(row["id"], row["operation_id"])
            if row["arrivals"]:
                self.stages.replace_arrivals(row["id"], row["arrivals"])
            return True
        changed = False
        if any(previous[name] != value for name, value in fields.items()):
            self.repo.update_qty(row["id"], **fields)
            changed = True
        if previous["operation_id"] != row["operation_id"]:
            self.stages.replace_operation(row["id"], row["operation_id"])
            changed = True
        if previous["arrivals"] != row["arrivals"]:
            self.stages.replace_arrivals(row["id"], row["arrivals"])
            changed = True
        return changed
