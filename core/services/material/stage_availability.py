"""Read-only release dates shared by preview and candidate input admission."""

import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from core.models.batch_external_context import context_group_key
from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_parse import is_exact_non_negative_number


def quantity(value, *, positive=False):
    if not is_exact_non_negative_number(value, positive=positive):
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
        self._readiness = {}
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

    def _group_bounds(self, batch_id):
        if batch_id not in self._group_sequences:
            lows, highs, keys = {}, {}, {}
            for item in self.operations_by_batch[batch_id]:
                member_context = self.contexts.get(item["id"])
                if member_context is not None and member_context["merge_mode"] == "merged":
                    key = context_group_key(member_context)
                    keys[item["id"]] = key
                    lows[key] = min(lows.get(key, item["seq"]), item["seq"])
                    piece_key = item.get("piece_id"), key
                    highs[piece_key] = max(highs.get(piece_key, item["seq"]), item["seq"])
            self._group_sequences[batch_id] = lows, highs, keys
        return self._group_sequences[batch_id]

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
            lows, _highs, keys = self._group_bounds(op["batch_id"])
            return lows[keys[op_id]]
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
        diagnosis = self.readiness_diagnostics(batch, day)
        problems = diagnosis["batch_problems"] + [problem for row in diagnosis["requirements"].values()
                                                   for problem in row["problems"]]
        return diagnosis["status"], problems

    def readiness_diagnostics(self, batch, day):
        """Keep requirement defects separate from shared batch evidence.

        This is a display/preflight assessment, independent of the lazy release
        checks: inspecting a later requirement must not block an earlier stage.
        Unreviewed requirements retain the original batch readiness mark, but an
        invalid quantity makes effective readiness unknown for every raw mark.
        """
        key = batch["batch_id"], batch["quantity"], batch["ready_status"], day
        if key in self._readiness:
            return self._readiness[key]
        rows = self.requirements[batch["batch_id"]]
        reviewed = any(row["id"] in self.reviews for row in rows)
        batch_problems = []
        if reviewed:
            try:
                self.verify_review(batch)
            except WorkbenchCommandRejected as exc:
                batch_problems.append({"code": exc.code, "message": str(exc)})
        requirements = {}
        for row in rows:
            row_reviewed = row["id"] in self.reviews
            amounts, problems = {}, []
            for field, positive in (("required_qty", True), ("available_qty", False)):
                try:
                    amounts[field] = self._amount(row, field, positive=positive)
                except WorkbenchCommandRejected as exc:
                    amounts[field] = None
                    problems.append({"code": exc.code, "message": str(exc), "field": field})
            available, required = amounts["available_qty"], amounts["required_qty"]
            if row_reviewed and available is not None:
                try:
                    available = self.available(row, day)
                except WorkbenchCommandRejected as exc:
                    available = None
                    problems.append({"code": exc.code, "message": str(exc), "field": "arrivals"})
            requirements[row["id"]] = {"available": available, "required": required, "problems": problems,
                "ready": not problems and covers_quantity(available, required) and (row_reviewed or row["ready_status"] == "yes")}
        if batch_problems or any(item["problems"] for item in requirements.values()):
            status = None
        elif not reviewed and (batch["ready_status"] != "yes" or not rows):
            status = batch["ready_status"]
        elif all(item["ready"] for item in requirements.values()):
            status = "yes"
        else:
            status = "partial" if any(item["available"] > 0 for item in requirements.values()) else "no"
        result = {"status": status, "batch_problems": batch_problems, "requirements": requirements}
        self._readiness[key] = result
        return result

    def operation_release(self, batch, operation, strategy):
        self.verify_review(batch)
        batch_id = batch["batch_id"]
        if strategy == "stage":
            op_id = operation.get("id")
            context = self.contexts.get(op_id) if op_id is not None else None
            seq = operation["seq"]
            if context and context["merge_mode"] == "merged":
                _lows, highs, keys = self._group_bounds(batch_id)
                seq = highs.get((operation.get("piece_id"), keys[op_id]), seq)
            return self._stage_release(batch_id, seq)
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
