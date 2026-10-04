"""Per-row batch import validation and the complete replacement deletion set."""

from core.errors import ValidationError
from core.models.workbench_batch import FIELDS, PRIORITIES, READY, normalize_batch_input
from core.models.workbench_batch_file import HEADER_FIELDS, HEADERS
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.enum_normalizers import batch_priority_label, ready_status_label
from core.services.common.excel_validators import get_batch_row_validate_and_normalize

from .facts import require_deletable, require_unreferenced
from .projection import BatchProjection

# 原样回导时逐格比对的列；批次号和图号另有规则。
_COMPARED = HEADERS[2:]


def file_values(entity):
    """批次在导出文件里八列的写法；回导时据此判断哪一格原样没动。"""
    values = {"business_code": entity["business_code"], "part_no": entity["relationships"]["part_no"], **entity["fields"]}
    if values["priority"] in PRIORITIES:
        values["priority"] = batch_priority_label(values["priority"])
    if values["ready_status"] in READY:
        values["ready_status"] = ready_status_label(values["ready_status"])
    return values


class BatchImportPreview:
    def __init__(self, facts, mode):
        self.facts = facts
        self.mode = mode
        self.projection = BatchProjection(facts)
        self.existing = {row["batch_id"]: row for row in facts["Batches"]}
        self.validator = get_batch_row_validate_and_normalize(
            parts_cache={row["part_no"]: row for row in facts["Parts"]})
        self.seen = set()

    def _relations(self, batch):
        """整份文件共用投影按同一份数据建好的关联索引；逐行重算会让大文件预检随行数平方变慢。"""
        return self.projection.relations[batch["batch_id"]]

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
            batch = self.existing.get(code)
            if batch is not None:
                row.update(entity_ref=self.projection.ref("batch", code), before=self.projection.entity(batch))
            kept = self._kept(parsed["values"], row["before"]) if batch is not None and self.mode == "overwrite" else ()
            source = self._validated(source, kept)
            if batch is not None and self.mode == "append":
                row["action"] = "skipped"
            else:
                row.update(self._planned(source, parsed["values"], batch, kept))
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

    def _validated(self, source, kept):
        # 原样没动的旧值不校验也不写回：带时间的交期、旧优先级 high 之类照旧保留，备注首尾空格也不被去掉。
        # 数量是必填项，没改也照常校验。
        checked = {key: None if key in kept and key != "数量" else value for key, value in source.items()}
        error = self.validator(checked)
        if error:
            raise ValidationError(error)
        return checked

    def _planned(self, source, original, batch, kept):
        action, payload = self._input(source, original, batch, kept)
        if kept and not payload["fields"]:
            return {"action": "unchanged"}  # 这一行和现有批次完全一样，确认时不写；与“只新增”模式下的跳过分开显示
        return {"action": action, "input": normalize_batch_input(action, payload)}

    @staticmethod
    def _kept(original, before):
        """文件里和导出写法一模一样的格子（类型也要相同，免得 True 和 1 算成一样）。"""
        exported = file_values(before)
        return {key for key in _COMPARED if original.get(key) not in (None, "")
                and type(original[key]) is type(exported[HEADER_FIELDS[key]]) and original[key] == exported[HEADER_FIELDS[key]]}

    def _input(self, source, original, batch, kept=()):
        create = batch is None or self.mode == "replace"
        fields = {HEADER_FIELDS[key]: value for key, value in source.items() if HEADER_FIELDS[key] in FIELDS
                  and (create or original.get(key) not in (None, "") and key not in kept)}
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
            require_unreferenced(self.facts, batch, self._relations(batch))
            if self._relations(batch)["materials"]:
                fields["ready_status"] = "no"
        if "ready_status" in fields and fields["ready_status"] != batch["ready_status"] and self._relations(batch)["materials"]:
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
            require_deletable(self.facts, batch, self._relations(batch))
        except WorkbenchCommandRejected as exc:
            item["errors"].append(str(exc))
        return item
