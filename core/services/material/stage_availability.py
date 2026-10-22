"""Read-only release dates shared by preview and candidate input admission."""

import math
import sys
from bisect import bisect_right
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
    """Derived facts for one captured, read-only tables collection.

    Callers create a new instance after material or operation facts change.
    Preparations stay lazy so later-stage arrivals are checked when consumed.
    """

    def __init__(self, tables):
        self.reviews = {row["requirement_id"]: row["batch_quantity"] for row in tables.get("BatchMaterialReviews", [])}
        self.requirements = defaultdict(list)
        self.arrivals = defaultdict(list)
        self.stages = {row["requirement_id"]: row["operation_id"] for row in tables.get("BatchMaterialStages", [])}
        self.operations = {row["id"]: row for row in tables.get("BatchOperations", [])}
        self.operations_by_batch = defaultdict(list)
        self.contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
        self._amounts = {}
        self._arrival_data = {}
        self._release_dates = {}
        self._use_sequences = {}
        self._group_sequences = {}
        self._review_checks = set()
        self._strict_releases = {}
        self._stage_releases = {}
        for row in self.operations.values():
            self.operations_by_batch[row["batch_id"]].append(row)
        for row in tables.get("BatchMaterials", []):
            self.requirements[row["batch_id"]].append(row)
        for row in tables.get("BatchMaterialArrivals", []):
            self.arrivals[row["requirement_id"]].append(row)

    def use_sequence(self, requirement):
        requirement_id = requirement["id"]
        if requirement_id not in self._use_sequences:
            self._use_sequences[requirement_id] = self._use_sequence(requirement)
        return self._use_sequences[requirement_id]

    def _use_sequence(self, requirement):
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
            batch_id = op["batch_id"]
            if batch_id not in self._group_sequences:
                groups, keys = {}, {}
                for item in self.operations_by_batch[batch_id]:
                    member_context = self.contexts.get(item["id"])
                    if member_context is not None:
                        key = context_group_key(member_context)
                        keys[item["id"]] = key
                        groups[key] = min(groups.get(key, item["seq"]), item["seq"])
                self._group_sequences[batch_id] = groups, keys
            groups, keys = self._group_sequences[batch_id]
            return groups[keys[op_id]]
        return op["seq"]

    def _amount(self, requirement, field, *, positive=False):
        key = requirement["id"], field
        if key not in self._amounts:
            self._amounts[key] = quantity(requirement[field], positive=positive)
        return self._amounts[key]

    def _prepared_arrivals(self, requirement):
        requirement_id = requirement["id"]
        if requirement_id not in self._arrival_data:
            entries = sorted((arrival_day(row["arrival_date"]), quantity(row["quantity"], positive=True))
                             for row in self.arrivals[requirement_id])
            prefix = [Decimal(0)]
            for _day, amount in entries:
                prefix.append(prefix[-1] + amount)
            self._arrival_data[requirement_id] = entries, [day for day, _amount in entries], prefix
        return self._arrival_data[requirement_id]

    def available(self, requirement, day):
        available = self._amount(requirement, "available_qty")
        _entries, days, prefix = self._prepared_arrivals(requirement)
        return available + prefix[bisect_right(days, day)]

    def release(self, requirement):
        requirement_id = requirement["id"]
        if requirement_id not in self._release_dates:
            self._release_dates[requirement_id] = self._release(requirement)
        return self._release_dates[requirement_id]

    def _release(self, requirement):
        needed = self._amount(requirement, "required_qty", positive=True)
        available = self._amount(requirement, "available_qty")
        if covers_quantity(available, needed):
            return "1900-01-01" if requirement["id"] in self.reviews or requirement["ready_status"] == "yes" else None
        entries, _days, _prefix = self._prepared_arrivals(requirement)
        for day, amount in entries:
            available += amount
            if covers_quantity(available, needed):
                return day
        return None

    def verify_review(self, batch, *, required=False):
        key = batch["batch_id"], batch["quantity"], required
        if key in self._review_checks:
            return
        for row in self.requirements[batch["batch_id"]]:
            reviewed = self.reviews.get(row["id"])
            captured = row["id"] in self.reviews
            if (captured and (reviewed is None or reviewed != batch["quantity"])) or (required and not captured):
                raise WorkbenchCommandRejected("material_review_required", "批次数量或用料口径尚未核对，请在物料需求中核对并保存后再排产或拆批。")
        self._review_checks.add(key)

    def readiness_state(self, batch, day):
        rows = self.requirements[batch["batch_id"]]
        if not any(row["id"] in self.reviews for row in rows):
            return self._unreviewed_state(batch, rows)
        try:
            self.verify_review(batch)
            amounts = [(self.available(row, day), self._amount(row, "required_qty", positive=True)) for row in rows]
        except WorkbenchCommandRejected as exc:
            return None, [{"code": exc.code, "message": str(exc)}]
        return ("yes" if all(covers_quantity(available, required) for available, required in amounts) else
                "partial" if any(available > 0 for available, _required in amounts) else "no"), []

    def _unreviewed_state(self, batch, rows):
        """未核对（v36 前）的需求与排产检查同一规则：批次标记为齐套，且每条需求都已到齐。

        这类需求没有分次到料记录，只看保存的到料数量和需求自身的齐套标记。
        """
        if batch["ready_status"] != "yes" or not rows:
            return batch["ready_status"], []
        try:
            amounts = [(self._amount(row, "available_qty"), self._amount(row, "required_qty", positive=True)) for row in rows]
        except WorkbenchCommandRejected as exc:
            return None, [{"code": exc.code, "message": str(exc)}]
        if all(covers_quantity(available, required) and row["ready_status"] == "yes"
               for row, (available, required) in zip(rows, amounts)):
            return "yes", []
        return ("partial" if any(available > 0 for available, _required in amounts) else "no"), []

    def operation_release(self, batch, operation, strategy):
        self.verify_review(batch)
        batch_id = batch["batch_id"]
        if strategy == "stage":
            return self._stage_release(batch_id, operation["seq"])
        if batch_id not in self._strict_releases:
            rows = self.requirements[batch_id]
            for row in rows:
                self.use_sequence(row)
            result = "1900-01-01"
            for row in rows:
                day = self.release(row)
                result = None if result is None or day is None else max(result, day)
            self._strict_releases[batch_id] = result
        return self._strict_releases[batch_id]

    def _stage_release(self, batch_id, sequence):
        if batch_id not in self._stage_releases:
            ordered = sorted(((self.use_sequence(row), row) for row in self.requirements[batch_id]),
                             key=lambda item: item[0])
            self._stage_releases[batch_id] = ([row for _seq, row in ordered],
                                             [seq for seq, _row in ordered], ["1900-01-01"])
        rows, sequences, prefix = self._stage_releases[batch_id]
        count = bisect_right(sequences, sequence)
        for index in range(len(prefix) - 1, count):
            day = self.release(rows[index])
            previous = prefix[-1]
            prefix.append(None if previous is None or day is None else max(previous, day))
        return prefix[count]

    def splittable_quantity(self, batch, day):
        self.verify_review(batch, required=True)
        rows = self.requirements[batch["batch_id"]]
        if not rows:
            raise WorkbenchCommandRejected("material_requirements_missing", "请先登记物料需求，再预览可开工数量。")
        total = quantity(batch["quantity"], positive=True)
        for row in rows:
            self.use_sequence(row)
        amounts = [(self.available(row, day), self._amount(row, "required_qty", positive=True)) for row in rows]
        maximum = min(available * total / required for available, required in amounts)
        count = min(int(total), int(maximum.to_integral_value(rounding=ROUND_FLOOR)))
        if count < total and all(covers_quantity(available, required * (count + 1) / total)
                                 for available, required in amounts):
            count += 1
        return count
