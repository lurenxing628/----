from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.scheduler_public_errors import infer_legacy_public_code, legacy_public_error_message

AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES = (
    "自动派工没有找到可用的设备和人员组合：工序 ",
    "自动派工资料不完整，本次无法自动补齐设备和人员：工序 ",
    "自制工序缺少自动派工所需工种信息，无法自动分配：工序 ",
)
AUTO_ASSIGN_INVALID_HOURS_PREFIX = "工时不合法：工序 "
AUTO_ASSIGN_RESOURCE_ERROR_CODES = {
    "auto_assign_inputs_missing",
    "auto_assign_resource_pool_incomplete",
    "auto_assign_no_resource_combination",
}
SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES = {*AUTO_ASSIGN_RESOURCE_ERROR_CODES, "invalid_internal_work_hours"}
SGS_OPERATION_SEQUENCE_RE = re.compile(r"^工序顺序 (?P<seq>[0-9]{1,9})$")


def is_auto_assign_resource_error(message: Any) -> bool:
    text = str(message or "").strip()
    if any(text.startswith(prefix) for prefix in AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES):
        return True
    if _is_legacy_auto_assign_invalid_hours_error(text):
        return True
    return _is_sgs_auto_assign_resource_error(text)


def first_auto_assign_resource_error(messages: Optional[List[str]]) -> str:
    for item in list(messages or []):
        text = str(item or "").strip()
        if is_auto_assign_resource_error(text):
            return text
    return ""


def public_auto_assign_resource_error_message(message: Any) -> str:
    text = str(message or "").strip()
    public_message = legacy_public_error_message(text)
    if not public_message:
        return ""
    if not is_auto_assign_resource_error(text):
        return ""
    return public_message


def first_public_auto_assign_resource_error(messages: Optional[List[str]]) -> str:
    for item in list(messages or []):
        public_message = public_auto_assign_resource_error_message(item)
        if public_message:
            return public_message
    return ""


def auto_assign_failed_op_ids_from_errors(*, errors: Any, operations: List[Any]) -> Set[int]:
    id_index = _operation_id_index(operations)
    out: Set[int] = set()
    for raw_error in list(errors or []):
        op_id = _auto_assign_error_op_id(raw_error, id_index)
        if op_id:
            out.add(op_id)
    return out


def _operation_id_index(operations: List[Any]) -> Dict[str, Dict[Any, List[int]]]:
    ids_by_code: Dict[str, List[int]] = {}
    ids_by_batch_and_code: Dict[Tuple[str, str], List[int]] = {}
    ids_by_batch_and_seq: Dict[Tuple[str, int], List[int]] = {}
    for op in list(operations or []):
        op_code = str(getattr(op, "op_code", "") or "").strip()
        batch_id = str(getattr(op, "batch_id", "") or "").strip()
        try:
            op_id = int(getattr(op, "id", 0) or 0)
        except Exception:
            continue
        if op_id <= 0:
            continue
        if op_code:
            ids_by_code.setdefault(op_code, []).append(op_id)
            if batch_id:
                ids_by_batch_and_code.setdefault((batch_id, op_code), []).append(op_id)
        seq = _positive_int(getattr(op, "seq", None))
        if batch_id and seq > 0:
            ids_by_batch_and_seq.setdefault((batch_id, seq), []).append(op_id)
    return {
        "by_code": ids_by_code,
        "by_batch_and_code": ids_by_batch_and_code,
        "by_batch_and_seq": ids_by_batch_and_seq,
    }


def _auto_assign_error_op_id(message: Any, id_index: Dict[str, Dict[Any, List[int]]]) -> Optional[int]:
    batch_id, op_text = _auto_assign_error_identity(message)
    if not op_text:
        return None
    seq = _operation_sequence(op_text)
    if batch_id:
        if seq > 0:
            return _single_op_id(list(id_index["by_batch_and_seq"].get((batch_id, seq)) or []))
        by_batch_and_code = id_index["by_batch_and_code"]
        for (op_batch_id, op_code), op_ids in _longest_batch_op_codes(by_batch_and_code):
            if op_batch_id == batch_id and _tail_belongs_to_op_code(op_text, op_code):
                return _single_op_id(op_ids)
        return None
    for op_code, op_ids in _longest_op_codes(id_index["by_code"]):
        if _tail_belongs_to_op_code(op_text, op_code):
            return _single_op_id(op_ids)
    return None


def _positive_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except Exception:
        return 0
    return number if number > 0 else 0


def _single_op_id(op_ids: List[int]) -> Optional[int]:
    unique_ids = sorted({int(op_id) for op_id in list(op_ids or []) if int(op_id or 0) > 0})
    return unique_ids[0] if len(unique_ids) == 1 else None


def _auto_assign_error_identity(message: Any) -> Tuple[str, str]:
    text = str(message or "").strip()
    batch_id, op_code = _sgs_auto_assign_error_identity(text)
    if batch_id or op_code:
        return batch_id, op_code
    for prefix in AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES:
        if text.startswith(prefix):
            return "", text[len(prefix) :].strip()
    invalid_hours_tail = _legacy_auto_assign_invalid_hours_tail(text)
    if invalid_hours_tail:
        return "", invalid_hours_tail
    return "", ""


def _is_legacy_auto_assign_invalid_hours_error(text: str) -> bool:
    return bool(_legacy_auto_assign_invalid_hours_tail(text) and legacy_public_error_message(text) == text)


def _legacy_auto_assign_invalid_hours_tail(text: str) -> str:
    if not text.startswith(AUTO_ASSIGN_INVALID_HOURS_PREFIX):
        return ""
    tail = text[len(AUTO_ASSIGN_INVALID_HOURS_PREFIX) :].strip()
    if not tail or "\n" in tail or "\r" in tail:
        return ""
    return tail


def _is_sgs_auto_assign_resource_error(text: str) -> bool:
    if not text.startswith("批次 "):
        return False
    return infer_legacy_public_code(text) in SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES


def _sgs_auto_assign_error_identity(text: str) -> Tuple[str, str]:
    marker = " 的"
    if not _is_sgs_auto_assign_resource_error(text) or marker not in text:
        return "", ""
    batch_id = text[len("批次 ") :].split(marker, 1)[0].strip()
    operation_text = text.split(marker, 1)[1].split("（", 1)[0].strip()
    return batch_id, _normalize_sgs_operation_text(operation_text)


def _normalize_sgs_operation_text(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("工序顺序 "):
        return value
    if value.startswith("工序 "):
        return value[len("工序 ") :].strip()
    return value


def _operation_sequence(text: str) -> int:
    match = SGS_OPERATION_SEQUENCE_RE.fullmatch(str(text or "").strip())
    return _positive_int(match.group("seq")) if match else 0


def _longest_batch_op_codes(ids_by_batch_and_code: Dict[Tuple[str, str], List[int]]) -> List[Tuple[Tuple[str, str], List[int]]]:
    return sorted(ids_by_batch_and_code.items(), key=lambda item: len(item[0][1]), reverse=True)


def _longest_op_codes(ids_by_code: Dict[str, List[int]]) -> List[Tuple[str, List[int]]]:
    return sorted(ids_by_code.items(), key=lambda item: len(item[0]), reverse=True)


def _tail_belongs_to_op_code(tail: str, op_code: str) -> bool:
    if tail == op_code or tail.startswith(f"{op_code}。"):
        return True
    return False
