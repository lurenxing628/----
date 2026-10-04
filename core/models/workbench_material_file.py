"""Private material batch contracts; no HTTP tokens or database connections.

MaterialPreview.document is canonical JSON, held only in the caller's temporary
preview context. as_dict() returns a detached copy. Its digest is NOT permission
to write: the API must bind the original digest to its short-lived write context.
Use intent() as CommandService.normalized_input and replay that original intent
before resolving an expired preview. Never rebuild a preview to replay a receipt.

Document shape: {version, operation, request, commit_policy: 'atomic', rows,
summary}. Rows contain {row, business_code, action, input, expected, result,
changes, errors, requires_confirmation}; expected holds identity, every original
material column, and full BatchMaterials rows, or None for a new material.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_table_descriptor import DEFAULT_IMPORT_BYTE_LIMIT, UPSERT_ONLY

IMPORT_ROW_LIMIT = 2000
HEADERS = ("物料编号", "名称", "规格", "单位", "库存数量", "状态", "备注", "创建时间")
COLUMNS = ("business_code", "label", "spec", "unit", "stock_qty", "status", "remark", "created_at")
HEADER_FIELDS: Dict[str, str] = dict(zip(HEADERS, COLUMNS))
HEADER_FIELDS.update({key: key for key in COLUMNS})
MATERIAL_COLUMNS = ("material_id", "name", "spec", "unit", "stock_qty", "status", "remark", "created_at")
READONLY = ("created_at",)
REQUIRED = ("business_code",)
NULLABLE = ("spec", "unit", "remark")
STATUS_LABELS = {"active": "启用", "inactive": "停用"}
STATUS_VALUES = {label: key for key, label in STATUS_LABELS.items()}
ENUMS = {"status": tuple(STATUS_LABELS.values())}
_VALUE_HINTS = {
    "business_code": "物料编号，例如 MAT-001；不填就不知道改哪一条",
    "label": "名称；新增时必须填，已有的留空保持原样",
    "spec": "规格；要清除请填 \\N（大写）",
    "unit": "单位，例如 kg；要清除请填 \\N（大写）",
    "stock_qty": "库存数量，填数字，不要带单位或千分位逗号",
    "status": "填写启用或停用；兼容旧文件的 active、inactive",
    "remark": "随便写；要清除请填 \\N（大写）",
    "created_at": "导出时带出的创建时间，导入时不看这一列",
}
_ERROR_HINTS = {
    "business_code": "留空、有首尾空格、或同一份文件里出现了两次",
    "label": "新增时留空",
    "spec": "填了 \\N 以外的清除写法",
    "unit": "填了 \\N 以外的清除写法",
    "stock_qty": "不是数字，或者带了单位、「是/否」、千分位逗号",
    "status": "填了启用、停用及其旧英文代号以外的词",
    "remark": "填了 \\N 以外的清除写法",
    "created_at": "这一列不校验",
}
_GENERAL_RULES = (
    "一次最多导入 " + str(IMPORT_ROW_LIMIT) + " 行。",
    "按编号增量更新：编号已有的更新，没有的新增，文件里没写的物料完全不动，不会被删除。",
    "空格子表示这一项保持原样，不是清除；要清除规格、单位或备注请填 \\N（大写）。",
    "状态填写与页面相同的启用、停用；旧文件的英文代号仍可导入。",
    "只读列仅供参考，不导入。",
)
_SAMPLE_ROWS = (
    ("MAT-001", "45# 圆钢", "D25", "kg", "12.375", "启用", "常备料"),
    ("MAT-002", "铝板", "3mm", "张", "40", "停用", ""),
)


def table_descriptor(_kind=None):
    """模板与填写说明生成器的唯一入口，12 张表统一形状。物料只有一张表，不分 kind。"""
    columns = []
    for index, key in enumerate(COLUMNS):
        readonly = key in READONLY
        columns.append({
            "key": key,
            # 标签就是文件里真正的表头，读取器按它认列，不能在这里加后缀。
            "label": HEADERS[index],
            "required": key in REQUIRED,
            "readonly": readonly,
            "value_hint": _VALUE_HINTS[key],
            "error_hint": _ERROR_HINTS[key],
            "enum": ENUMS.get(key) if not readonly else None,
            "nullable": key in NULLABLE,
        })
    return {
        "table_id": "material",
        "display_name": "物料",
        "sheet_name": "物料",
        "file_stem": "物料",
        "columns": columns,
        "general_rules": _GENERAL_RULES,
        "sample_rows": _SAMPLE_ROWS,
        "row_limit": IMPORT_ROW_LIMIT,
        "byte_limit": DEFAULT_IMPORT_BYTE_LIMIT,
        "modes": UPSERT_ONLY,
    }


def normalize_scope(scope: Any) -> Dict[str, Any]:
    """Filter identity without pagination. {} explicitly means the full collection."""
    allowed = {"query", "status", "sort", "direction", "column_filters"}
    if type(scope) is not dict or any(type(key) is not str or key not in allowed for key in scope):
        raise ValidationError("物料范围只能包含搜索、状态、排序和列筛选，不接受页码。", field="scope")
    query = MaterialPageRequest(**scope)
    return {key: value for key, value in query.scope().items() if key not in ("kind", "size")}


def normalize_refs(refs: Any, *, allow_empty: bool = False):
    if type(refs) is not list or (not refs and not allow_empty):
        raise ValidationError("请先选择要操作的物料。", field="refs")
    if any(type(ref) is not str or len(ref) != 48 or any(c not in "0123456789abcdef" for c in ref) for ref in refs):
        raise ValidationError("物料选择已失效，请刷新后重新选择。", field="refs")
    if len(set(refs)) != len(refs):
        raise ValidationError("物料选择里有重复，请重新选择。", field="refs")
    return list(refs)


def file_request(content: Any, file_format: str, mode: str, scope: Any):
    if type(content) is not bytes:
        raise ValidationError("文件内容必须是 bytes。", field="file")
    if file_format not in ("csv", "xlsx") or type(file_format) is not str:
        raise ValidationError("物料文件仅支持 CSV 和 XLSX。", field="format")
    if mode != "upsert" or type(mode) is not str:
        raise ValidationError("物料只支持按编号增量更新，不支持整库替换。", field="mode")
    normalized = normalize_scope(scope)
    if normalized["query"] or normalized["status"] is not None or normalized.get("column_filters"):
        raise ValidationError("物料导入按文件编号操作，不支持筛选范围导入。", field="scope")
    return {"file_sha256": hashlib.sha256(content).hexdigest(), "format": file_format,
            "mode": mode, "scope": normalized}


@dataclass(frozen=True)
class MaterialPreview:
    document: str

    @classmethod
    def build(cls, operation, request, rows, notices=()):
        """notices 是整批级的告知，不是行错误；进文档让确认时的逐字比对也盖住它。"""
        summary = {key: sum(row["result"] == key for row in rows)
                   for key in ("new", "update", "unchanged", "delete", "rejected")}
        try:
            return cls(canonical_json({"version": 1, "operation": operation, "request": request,
                                       "commit_policy": "atomic", "rows": rows, "summary": summary,
                                       "notices": list(notices)}))
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("storage_failure", "这批物料数据算不出完整预检结果，没有写入任何数据。请刷新后重新预检。", 500) from exc

    def as_dict(self):
        return json.loads(self.document)

    @property
    def digest(self):
        return hashlib.sha256(self.document.encode("utf-8")).hexdigest()

    def intent(self):
        body = self.as_dict()
        return {"preview_hash": self.digest, "operation": body["operation"], "request": body["request"]}


def check_request(preview, operation, request):
    if not isinstance(preview, MaterialPreview):
        raise WorkbenchCommandRejected("stale_write", "找不到刚才的预检结果，没有写入数据。请点「重新预检」。")
    body = preview.as_dict()
    if body["operation"] != operation or canonical_json(body["request"]) != canonical_json(request):
        raise WorkbenchCommandRejected("stale_write", "文件内容、模式或选择范围已变化，请重新预检。")


def check_preview(original: MaterialPreview, current: MaterialPreview):
    if original.document != current.document:
        raise WorkbenchCommandRejected("stale_write", "物料数据已更新，没有写入数据。请点「重新预检」并核对整批内容。")
    if current.as_dict()["summary"]["rejected"]:
        raise WorkbenchCommandRejected("constraint_conflict", "预检里有不通过的行，这一批没有写入任何数据。请改好后重新预检。")


def preview_row(number, *, code=None, action=None, normalized=None, expected=None):
    return {"row": number, "business_code": code, "action": action, "input": normalized,
            "expected": expected, "result": "rejected", "changes": {}, "errors": [],
            "requires_confirmation": False}


def reject_row(row, message, *, field="business_code", code="invalid_input"):
    row["result"] = "rejected"
    row["errors"].append({"row": row["row"], "field": field, "code": code, "message": message})


@dataclass(frozen=True)
class MaterialFileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int
