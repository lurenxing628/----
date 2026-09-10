"""Receipt facts describe a shipment, never execution or supplier lead times."""

import math
import re
from datetime import date, datetime

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json

FACT_FIELDS = ("sent", "planned", "returned", "confirmedState")
STATES = {"in_transit": "在途", "returned": "已回厂", "awaiting_confirmation": "待确认"}
MAX_MEMBERS = 200
MAX_ROWS = 10000
MAX_BYTES = 8 * 1024 * 1024


def reject(message, code="invalid_input", status=422):
    raise WorkbenchCommandRejected(code, message, status)


def reference(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        reject("请使用原对象的永久引用，不能使用显示编号代替。", status=400)
    return value


def raw_facts(value):
    """Lossless JSON evidence, including SQLite storage values and DATE adapters."""
    if value is None or type(value) in (str, bool):
        return value
    if type(value) is int:
        return {"storage_type": "integer", "value": str(value)}
    if type(value) is float:
        return {"storage_type": "real", "hex": value.hex()}
    if type(value) is bytes:
        return {"storage_type": "blob", "hex": value.hex()}
    if type(value) in (date, datetime):
        return {"python_type": type(value).__name__, "value": value.isoformat()}
    if type(value) in (tuple, list):
        return [raw_facts(item) for item in value]
    if type(value) is dict:
        return {key: raw_facts(item) for key, item in value.items()}
    raise TypeError("Unsupported outsourcing evidence type: " + type(value).__name__)


def bounded(value):
    if len(canonical_json(value).encode("utf-8")) > MAX_BYTES:
        reject("外协读取超过8MB，请缩小范围；未截断事实或历史。", "query_too_large", 413)
    return value


def label(value):
    if value is None or type(value) in (str, bool):
        return value
    if type(value) in (int, float) and math.isfinite(value):
        return value
    return raw_facts(value)


def pagination(number, size):
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 100:
        reject("页码必须是正整数，每页数量须为1至100。", status=400)


def page(rows, number, size):
    pagination(number, size)
    start = (number - 1) * size
    return {"items": rows[start:start + size], "page": {"number": number, "size": size,
            "total": len(rows), "pages": (len(rows) + size - 1) // size}}
