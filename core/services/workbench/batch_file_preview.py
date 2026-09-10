"""Per-row batch import validation and the complete replacement deletion set."""

from core.errors import ValidationError
from core.models.workbench_batch import FIELDS, normalize_batch_input
from core.models.workbench_batch_file import HEADER_FIELDS
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_validators import get_batch_row_validate_and_normalize
from core.services.workbench.batch_facts import related, require_unreferenced
from core.services.workbench.batch_projection import BatchProjection


class BatchImportPreview:
    def __init__(self, facts, mode):
        self.facts = facts
        self.mode = mode
        self.projection = BatchProjection(facts)
        self.existing = {row["batch_id"]: row for row in facts["Batches"]}
        self.validator = get_batch_row_validate_and_normalize(
            parts_cache={row["part_no"]: row for row in facts["Parts"]})
        self.seen = set()

    def row(self, parsed):
        row = {"row": parsed["row"], "business_code": parsed["values"].get("批次号"),
               "errors": list(parsed["errors"]), "action": "rejected", "input": None,
               "entity_ref": None, "before": None}
        try:
            if row["errors"]:
                raise ValidationError(row["errors"][0])
            source = self._source(parsed["values"])
            code = source["批次号"]
            row["business_code"] = code
            if code in self.seen:
                raise ValidationError("文件内有重复批次号。")
            self.seen.add(code)
            error = self.validator(source)
            if error:
                raise ValidationError(error)
            batch = self.existing.get(code)
            if batch is not None:
                row.update(entity_ref=self.projection.ref("batch", code), before=self.projection.entity(batch))
            if batch is not None and self.mode == "append":
                row["action"] = "skipped"
            else:
                action, payload = self._input(source, parsed["values"], batch)
                row.update(action=action, input=normalize_batch_input(action, payload))
        except (ValidationError, WorkbenchCommandRejected) as exc:
            row.update(action="rejected", input=None, errors=list(dict.fromkeys(row["errors"] + [str(exc)])))
        return row

    @staticmethod
    def _source(values):
        if any(type(values[key]) is not str or not values[key].strip() for key in ("批次号", "图号")):
            raise ValidationError("批次号和图号必须为文本，不能猜测丢失的前导零。")
        if type(values["数量"]) is bool:
            raise ValidationError("数量不能使用布尔值。")
        source = dict(values)
        source["批次号"], source["图号"] = source["批次号"].strip(), source["图号"].strip()
        return source

    def _input(self, source, original, batch):
        create = batch is None or self.mode == "replace"
        fields = {HEADER_FIELDS[key]: value for key, value in source.items() if HEADER_FIELDS[key] in FIELDS
                  and (create or original[key] not in (None, ""))}
        if batch is None or self.mode == "replace":
            for key in ("due_date", "ready_date", "remark"):
                fields.setdefault(key, None)
            return "create", {"business_code": source["批次号"],
                              "part_ref": self.projection.ref("part", source["图号"]), "fields": fields}
        if source["图号"] != batch["part_no"]:
            raise ValidationError("已有批次不能在普通导入中切换图号。")
        if fields.get("quantity", batch["quantity"]) != batch["quantity"]:
            require_unreferenced(self.facts, batch)
        return "update", {"fields": fields}

    def deleted(self):
        if self.mode != "replace":
            return []
        return [self._deletion(batch) for batch in self.facts["Batches"]]

    def _deletion(self, batch):
        item = {"entity_ref": self.projection.ref("batch", batch["batch_id"]),
                "before": self.projection.entity(batch), "errors": []}
        try:
            require_unreferenced(self.facts, batch)
            if related(self.facts, batch)["materials"]:
                raise WorkbenchCommandRejected("constraint_conflict", "批次有物料需求，不允许清空。")
        except WorkbenchCommandRejected as exc:
            item["errors"].append(str(exc))
        return item
