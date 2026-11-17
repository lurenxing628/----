"""Receipt facts describe a shipment, never execution or supplier lead times."""

from datetime import date, datetime
from typing import NoReturn, Sequence

from core.models.enums import OutsourcingConfirmedState
from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.refs import is_ref
from core.shared.strict_json import canonical_json
from core.shared.strict_parse import is_exact_finite_number

FACT_FIELDS = ("sent", "planned", "returned", "confirmedState")
STATES = {OutsourcingConfirmedState.IN_TRANSIT.value: "在途", OutsourcingConfirmedState.RETURNED.value: "已回厂",
          OutsourcingConfirmedState.AWAITING_CONFIRMATION.value: "待确认"}
MAX_MEMBERS = 200
# 全库计数上限：未登记的外协工序、外协登记各自的条数。看板的外协缺口和观察读的就是这两份，看板 MAX_ROWS 与它同值。
MAX_ROWS = 20000
MAX_BYTES = 8 * 1024 * 1024
# Stored BatchOperations columns of receipt evidence: member identity, then the revision fingerprint.
MEMBER_KEYS = ("op_code", "batch_id", "piece_id", "seq", "op_type_id", "op_type_name", "source", "supplier_id")
OPERATION_REVISION_KEYS = ("id", "machine_id", "operator_id", "setup_hours", "unit_hours", "ext_days", "status", "created_at")


def reject(message, code="invalid_input", status=422, *, fields: Sequence[str] = ()) -> NoReturn:
    raise WorkbenchCommandRejected(code, message, status, fields=fields)


def reference(value):
    if not is_ref(value):
        reject("这条记录已失效，请刷新后重新选择。", status=400)
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


def document_text(value):
    """Encode the actual document written to a receipt column exactly once."""
    encoded = canonical_json(value)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        reject("外协保存资料超过 8 MB，这次没有保存。请缩小登记范围。", "query_too_large", 413)
    return encoded


def label(value):
    if value is None or type(value) in (str, bool):
        return value
    if is_exact_finite_number(value):
        return value
    return raw_facts(value)


def pagination(number, size):
    if type(number) is not int or not 1 <= number <= 1000000 or type(size) is not int or not 1 <= size <= 100:
        reject("页码必须是正整数，每页数量须为1至100。", status=400)


def page_meta(number: int, size: int, total: int):
    return {
        "number": number,
        "size": size,
        "total": total,
        "pages": (total + size - 1) // size,
    }
