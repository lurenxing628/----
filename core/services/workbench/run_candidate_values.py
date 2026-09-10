"""Strict stored-value parsing and small public projections."""

import json
import math
from typing import Any, NoReturn, Type

from core.models.workbench_run_candidate import reject


def corrupt() -> NoReturn:
    reject("candidate_artifact_invalid", "候选持久结果缺失或不一致，请核对运行台账；未返回替代结果。", 500)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate stored JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite stored JSON value")


def stored_json(value, expected: Type[Any] = dict) -> Any:
    if type(value) is not str:
        corrupt()
    try:
        data = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, RecursionError):
        corrupt()
    if type(data) is not expected:
        corrupt()
    return data


def gap(field, code="not_recorded"):
    messages = {"not_recorded": "生成时未记录该字段。", "invalid_stored_value": "生成时字段格式无效。",
                "blob_metadata": "生成时该字段为字节型数据，未猜测解码。",
                "source_missing": "生成时源记录缺失，未套用当前同编号实体。",
                "undefined_metric": "生成时指标未定义，不能把占位值当作测量结果。"}
    return {"field": field, "code": code, "message": messages[code]}


def text(value, field, gaps):
    if type(value) is str and value and "\x00" not in value:
        return value
    code = "not_recorded" if value is None or value == "" else "invalid_stored_value"
    if isinstance(value, dict) and "sqlite_blob_base64" in value:
        code = "blob_metadata"
    gaps.append(gap(field, code))
    return None


def number(value, field, gaps, *, integer=False):
    if type(value) in ((int,) if integer else (int, float)) and value >= 0:
        try:
            if math.isfinite(value):
                return str(value) if type(value) is int and value > (1 << 53) - 1 else value
        except OverflowError:
            pass
    gaps.append(gap(field, "not_recorded" if value is None else "invalid_stored_value"))
    return None


def bounded_size(size, limit):
    if type(size) is not int or size < 0:
        corrupt()
    if size > limit:
        reject("candidate_capacity_exceeded", "候选或生成时历史快照超过读取容量，未截断或退回当前数据。", 413)
