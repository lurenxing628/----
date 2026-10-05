"""Quantity lots: read-only proposal followed by one guarded atomic command."""

from decimal import Decimal

from core.models.workbench_batch import number, object_fields
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_preflight import local_date
from core.services.material.stage_availability import MaterialAvailability, covers_quantity, quantity
from core.services.workbench.calibration.template_lineage import TemplateLineageWriter
from core.services.workbench.facts.preflight_checks import stored_date
from data.repositories.batch_material_repo import BatchMaterialRepository
from data.repositories.batch_material_stage_repo import BatchMaterialStageRepository
from data.repositories.batch_repo import BatchRepository

from .bulk import WorkbenchBatchBulkService
from .facts import BatchFacts, require_unreferenced
from .materials import WorkbenchBatchMaterialService
from .operations import insert_operation
from .service import WorkbenchBatchService


def normalize_split(payload):
    object_fields(payload, ("as_of_date", "quantity"), ("as_of_date",))
    count = payload.get("quantity")
    if count is not None:
        count = number(count, "quantity", integer=True, positive=True)
    return {"as_of_date": local_date(payload["as_of_date"]).isoformat(), "quantity": count}


def allocate(row, entries, needed, day):
    """Take undated stock first, then dated arrivals; preserve every remainder."""
    initial = quantity(row["available_qty"])
    take = min(initial, needed)
    remaining = needed - take
    child, source = [], []
    for arrival in sorted(entries, key=lambda item: item["arrival_date"]):
        amount = quantity(arrival["quantity"], positive=True)
        used = min(amount, remaining) if arrival["arrival_date"] <= day else Decimal(0)
        if used:
            child.append({"arrival_date": arrival["arrival_date"], "quantity": float(used)})
        if amount > used:
            source.append({"arrival_date": arrival["arrival_date"], "quantity": float(amount - used)})
        remaining -= used
    if remaining and not covers_quantity(needed - remaining, needed):
        raise WorkbenchCommandRejected("material_not_ready", "可用物料不足，请重新预检可开工数量。")
    return float(take), float(initial - take), child, source


def _require_splittable_batch(batch, facts):
    operations = [op for op in facts["BatchOperations"] if op["batch_id"] == batch["batch_id"]]
    if batch["status"] != "pending" or not operations or any(op["status"] != "pending" or op["piece_id"] is not None for op in operations):
        raise WorkbenchCommandRejected("constraint_conflict", "仅支持已有整批工序、尚未排产和开工的待排批次拆分数量。")
    if type(batch["quantity"]) is not int or batch["quantity"] <= 1:
        raise WorkbenchCommandRejected("constraint_conflict", "批次数量必须是大于 1 的整数。")


class WorkbenchQuantitySplitService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.reader = reader if reader is not None else BatchFacts(conn, logger)

    def plan(self, ref, payload):
        payload = normalize_split(payload)
        batch, facts = self.reader.batch(ref), self.reader.load()
        require_unreferenced(facts, batch)
        _require_splittable_batch(batch, facts)
        original = batch["quantity"]
        availability = MaterialAvailability(facts)
        maximum = availability.splittable_quantity(batch, payload["as_of_date"])
        count = payload["quantity"] if payload["quantity"] is not None else maximum
        if not 0 < count < original or count > maximum:
            raise WorkbenchCommandRejected("constraint_conflict", f"当前可开工 {maximum} 件，原批 {original} 件；拆分数量须大于 0、小于原批且不超过可开工数量。")
        code = WorkbenchBatchBulkService._copy_code(batch["batch_id"], {row["batch_id"] for row in facts["Batches"]})
        materials = []
        names = {row["material_id"]: row["name"] for row in facts["Materials"]}
        for row in availability.requirements[batch["batch_id"]]:
            needed = quantity(row["required_qty"], positive=True) * Decimal(count) / Decimal(original)
            initial, remainder, child_arrivals, source_arrivals = allocate(row, availability.arrivals[row["id"]], needed, payload["as_of_date"])
            materials.append({"requirement_id": row["id"], "material_id": row["material_id"], "label": names[row["material_id"]],
                "operation_id": availability.stages.get(row["id"]), "source_required": float(quantity(row["required_qty"]) - needed),
                "child_required": float(needed), "child_available": initial, "source_available": remainder,
                "child_arrivals": child_arrivals, "source_arrivals": source_arrivals})
        return {"entity_ref": ref, "operation": "batch.split_confirm", "source_code": batch["batch_id"], "child_code": code,
                "original_quantity": original, "quantity": count, "remaining_quantity": original - count,
                "maximum_quantity": maximum, "as_of_date": payload["as_of_date"], "materials": materials,
                "commit_policy": "atomic", "warnings": []}

    def apply(self, ref, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("Quantity split requires the workbench command transaction.")
        plan = self.plan(ref, payload)
        batch, facts = self.reader.batch(ref), self.reader.load()
        code = plan["child_code"]
        fields = {key: batch[key] for key in ("due_date", "priority", "remark", "part_name")}
        source_rows, child_rows = [], []
        for row in plan["materials"]:
            for target, prefix in ((source_rows, "source"), (child_rows, "child")):
                target.append({"material_id": row["material_id"], "operation_id": row["operation_id"],
                    "required_qty": row[prefix + "_required"], "available_qty": row[prefix + "_available"],
                    "arrivals": row[prefix + "_arrivals"]})
        source_ready = WorkbenchBatchMaterialService._ready(source_rows)
        child_ready = WorkbenchBatchMaterialService._ready(child_rows)
        ready_day = stored_date(batch["ready_date"])
        if batch["ready_date"] is not None and ready_day is None:
            raise WorkbenchCommandRejected("constraint_conflict", "原批次齐套日期无效，请先核对后再拆分。")
        WorkbenchBatchService(self.conn).domain.create(code, batch["part_no"], **fields, quantity=plan["quantity"],
            ready_status=child_ready, ready_date=max(filter(None, (ready_day, plan["as_of_date"]))))
        writer = TemplateLineageWriter(self.conn)
        mapping = {op["id"]: insert_operation(self.conn, code, op, writer=writer) for op in facts["BatchOperations"] if op["batch_id"] == batch["batch_id"]}
        repo, stages = BatchMaterialRepository(self.conn), BatchMaterialStageRepository(self.conn)
        for index, row in enumerate(plan["materials"]):
            created = repo.add(code, row["material_id"], required_qty=row["child_required"], available_qty=row["child_available"],
                               ready_status=child_rows[index]["ready_status"])
            operation_id = row["operation_id"]
            if operation_id is not None:
                stages.replace_operation(created.id, mapping[operation_id])
            if row["child_arrivals"]:
                stages.replace_arrivals(created.id, row["child_arrivals"])
            stages.review(created.id, plan["quantity"])
            repo.update_qty(row["requirement_id"], required_qty=row["source_required"], available_qty=row["source_available"],
                            ready_status=source_rows[index]["ready_status"])
            stages.replace_arrivals(row["requirement_id"], row["source_arrivals"])
            stages.review(row["requirement_id"], plan["remaining_quantity"])
        BatchRepository(self.conn).update(batch["batch_id"], {"quantity": plan["remaining_quantity"], "ready_status": source_ready})
        stages.record_split(batch["batch_id"], code, plan["original_quantity"], plan["quantity"], plan["as_of_date"])
        identity = self.reader.identities.find_active("batch", code)
        if identity is None:
            raise RuntimeError("Split child is missing its permanent reference.")
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "child_ref": identity.ref, "business_code": code,
            "quantity": plan["quantity"], "remaining_quantity": plan["remaining_quantity"], "commit_policy": "atomic"})
