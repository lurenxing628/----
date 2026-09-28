"""Per-row batch import validation and the complete replacement deletion set."""

from core.errors import ValidationError
from core.models.workbench_batch import FIELDS, normalize_batch_input
from core.models.workbench_batch_file import HEADER_FIELDS, HEADERS
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_validators import get_batch_row_validate_and_normalize

from .facts import related, require_deletable, require_unreferenced
from .projection import BatchProjection


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

    def _source(self, values):
        code = values.get("批次号")
        if type(code) is not str or not code.strip():
            raise ValidationError("请将批次号和图号设为文本格式，保留前导零。")
        source = {key: values.get(key) for key in HEADERS}
        stored = self.existing.get(code.strip())
        if stored is not None and self.mode != "replace":
            for label, field in (("图号", "part_no"), ("数量", "quantity")):
                if source[label] in (None, ""):
                    source[label] = stored[field]
        if type(source["图号"]) is not str or not source["图号"].strip():
            raise ValidationError("新增批次必须填写图号，请按文本填写并保留前导零。")
        if type(source["数量"]) is bool:
            raise ValidationError("数量要填数字，不能填「是/否」。")
        source["批次号"], source["图号"] = source["批次号"].strip(), source["图号"].strip()
        return source

    def _input(self, source, original, batch):
        create = batch is None or self.mode == "replace"
        fields = {HEADER_FIELDS[key]: value for key, value in source.items() if HEADER_FIELDS[key] in FIELDS
                  and (create or original.get(key) not in (None, ""))}
        if batch is None or self.mode == "replace":
            for key in ("due_date", "ready_date", "remark"):
                fields.setdefault(key, None)
            return "create", {"business_code": source["批次号"],
                              "part_ref": self.projection.ref("part", source["图号"]), "fields": fields}
        if source["图号"] != batch["part_no"]:
            raise ValidationError("已有批次不能在普通导入中切换图号。")
        return "update", {"fields": self._readiness(fields, batch)}

    def _readiness(self, fields, batch):
        if fields.get("quantity", batch["quantity"]) != batch["quantity"]:
            require_unreferenced(self.facts, batch)
            if related(self.facts, batch)["materials"]:
                fields["ready_status"] = "no"
        if "ready_status" in fields and fields["ready_status"] != batch["ready_status"] and related(self.facts, batch)["materials"]:
            if fields.get("quantity", batch["quantity"]) == batch["quantity"]:
                raise ValidationError("此批次的齐套按物料需求计算，请在物料需求中核对后保存。")
        return fields

    def deleted(self):
        if self.mode != "replace":
            return []
        return [self._deletion(batch) for batch in self.facts["Batches"]]

    def _deletion(self, batch):
        item = {"entity_ref": self.projection.ref("batch", batch["batch_id"]),
                "before": self.projection.entity(batch), "errors": []}
        try:
            require_deletable(self.facts, batch)
        except WorkbenchCommandRejected as exc:
            item["errors"].append(str(exc))
        return item
