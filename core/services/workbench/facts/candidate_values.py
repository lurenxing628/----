"""Strict stored-value parsing and small public projections."""

from typing import Any, NoReturn, Type

from core.models.workbench_run_candidate import reject
from core.shared.strict_json import load_strict_json
from core.shared.strict_parse import is_exact_non_negative_number


def corrupt() -> NoReturn:
    reject("candidate_artifact_invalid", "这次排产保存的结果缺失或不一致，请到「排产记录」核对；仍有问题请联系维护人员。", 500)


def stored_json(value, expected: Type[Any] = dict) -> Any:
    # Stored documents are TEXT; a BLOB is as corrupt as unreadable JSON.
    if type(value) is not str:
        corrupt()
    return load_strict_json(value, on_malformed=corrupt, expected=expected)


def gap(field, code="not_recorded"):
    texts = {"not_recorded": "排产时没有记下这一项。", "invalid_stored_value": "排产时记下的这一项格式不对。",
             "blob_metadata": "排产时这一项的记录格式无法显示，请联系维护人员核对。",
             "source_missing": "排产时的原始记录已不存在。",
             "undefined_metric": "排产时未计算此指标。"}
    return {"field": field, "code": code, "message": texts[code]}


def text(value, field, gaps):
    if type(value) is str and value and "\x00" not in value:
        return value
    code = "not_recorded" if value is None or value == "" else "invalid_stored_value"
    if isinstance(value, dict) and "sqlite_blob_base64" in value:
        code = "blob_metadata"
    gaps.append(gap(field, code))
    return None


def number(value, field, gaps, *, integer=False):
    if (type(value) is int or not integer) and is_exact_non_negative_number(value):
        return str(value) if type(value) is int and value > (1 << 53) - 1 else value
    gaps.append(gap(field, "not_recorded" if value is None else "invalid_stored_value"))
    return None


def bounded_size(size, limit):
    if type(size) is not int or size < 0:
        corrupt()
    if size > limit:
        reject("candidate_capacity_exceeded", "这次排产的记录超过单次读取上限，请缩小查询范围后重试。", 413)
