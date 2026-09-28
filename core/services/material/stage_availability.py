"""Read-only release dates shared by preview and candidate input admission."""

import math
import sys
from collections import defaultdict
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from core.models.batch_external_context import context_group_key
from core.models.workbench_command import WorkbenchCommandRejected


def quantity(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise WorkbenchCommandRejected("material_unknown", "物料需求量或到料量无效，请先核对物料需求。")
    return Decimal(str(value))


def covers_quantity(available, required):
    """Compare REAL-backed amounts, allowing only binary64 representation noise.

    Positive arrival sums and proportional splits can differ by a final bit on
    their separate SQLite/JSON round trips. Never round stored stock or treat a
    missing whole unit as available; two epsilons cover these round trips.
    """
    if available >= required:
        return True
    if available == available.to_integral_value() and required == required.to_integral_value():
        return False
    return required - available <= max(abs(available), abs(required)) * Decimal(str(sys.float_info.epsilon)) * 2


def arrival_day(value):
    if not isinstance(value, str):
        raise WorkbenchCommandRejected("material_unknown", "到料日期无效，请先核对物料需求。")
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return value
    except ValueError:
        pass
    raise WorkbenchCommandRejected("material_unknown", "到料日期无效，请先核对物料需求。")


class MaterialAvailability:
    def __init__(self, tables):
        self.reviews = {row["requirement_id"]: row["batch_quantity"] for row in tables.get("BatchMaterialReviews", [])}
        self.requirements = defaultdict(list)
        self.arrivals = defaultdict(list)
        self.stages = {row["requirement_id"]: row["operation_id"] for row in tables.get("BatchMaterialStages", [])}
        self.operations = {row["id"]: row for row in tables.get("BatchOperations", [])}
        self.contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
        for row in tables.get("BatchMaterials", []):
            self.requirements[row["batch_id"]].append(row)
        for row in tables.get("BatchMaterialArrivals", []):
            self.arrivals[row["requirement_id"]].append(row)

    def use_sequence(self, requirement):
        op_id = self.stages.get(requirement["id"])
        if op_id is None:
            return 0
        op = self.operations.get(op_id)
        if op is None or op["batch_id"] != requirement["batch_id"]:
            raise WorkbenchCommandRejected("material_stage_invalid", "物料使用工序已失效或不属于本批，请重新选择。")
        if op.get("piece_id") is not None:
            raise WorkbenchCommandRejected("material_stage_invalid", "分阶段用料请选择整批工序，单件分支须先合并核对。")
        context = self.contexts.get(op_id)
        if context and context["merge_mode"] == "merged":
            key = context_group_key(context)
            return min(item["seq"] for item in self.operations.values() if item["batch_id"] == op["batch_id"]
                       and item["id"] in self.contexts and context_group_key(self.contexts[item["id"]]) == key)
        return op["seq"]

    def entries(self, requirement):
        return sorted([(arrival_day(row["arrival_date"]), quantity(row["quantity"], positive=True))
                       for row in self.arrivals[requirement["id"]]])

    def available(self, requirement, day):
        return quantity(requirement["available_qty"]) + sum(amount for at, amount in self.entries(requirement) if at <= day)

    def release(self, requirement):
        needed = quantity(requirement["required_qty"], positive=True)
        available = quantity(requirement["available_qty"])
        if covers_quantity(available, needed):
            return "1900-01-01" if requirement["id"] in self.reviews or requirement["ready_status"] == "yes" else None
        for day, amount in self.entries(requirement):
            available += amount
            if covers_quantity(available, needed):
                return day
        return None

    def verify_review(self, batch, *, required=False):
        for row in self.requirements[batch["batch_id"]]:
            reviewed = self.reviews.get(row["id"])
            if (reviewed is not None and reviewed != batch["quantity"]) or (required and reviewed is None):
                raise WorkbenchCommandRejected("material_review_required", "批次数量或用料口径尚未核对，请在物料需求中核对并保存后再排产或拆批。")

    def readiness_state(self, batch, day):
        rows = self.requirements[batch["batch_id"]]
        if not any(row["id"] in self.reviews for row in rows):
            return batch["ready_status"], []
        try:
            self.verify_review(batch)
            amounts = [(self.available(row, day), quantity(row["required_qty"], positive=True)) for row in rows]
        except WorkbenchCommandRejected as exc:
            return None, [{"code": exc.code, "message": str(exc)}]
        return ("yes" if all(covers_quantity(available, required) for available, required in amounts) else
                "partial" if any(available > 0 for available, _required in amounts) else "no"), []

    def operation_release(self, batch, operation, strategy):
        self.verify_review(batch)
        rows = self.requirements[batch["batch_id"]]
        if strategy == "stage":
            rows = [row for row in rows if self.use_sequence(row) <= operation["seq"]]
        else:
            for row in rows:
                self.use_sequence(row)
        releases = [self.release(row) for row in rows]
        if any(day is None for day in releases):
            return None
        return max([day for day in releases if day is not None] or ["1900-01-01"])

    def splittable_quantity(self, batch, day):
        self.verify_review(batch, required=True)
        rows = self.requirements[batch["batch_id"]]
        if not rows:
            raise WorkbenchCommandRejected("material_requirements_missing", "请先登记物料需求，再预览可开工数量。")
        total = quantity(batch["quantity"], positive=True)
        for row in rows:
            self.use_sequence(row)
        maximum = min(self.available(row, day) * total / quantity(row["required_qty"], positive=True) for row in rows)
        count = min(int(total), int(maximum.to_integral_value(rounding=ROUND_FLOOR)))
        if count < total and all(covers_quantity(self.available(row, day),
                quantity(row["required_qty"], positive=True) * (count + 1) / total) for row in rows):
            count += 1
        return count
