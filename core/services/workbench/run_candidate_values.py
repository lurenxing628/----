"""Strict stored-value parsing and small public projections."""

import json
import math
from typing import Any, NoReturn, Type

from core.models.workbench_run_candidate import reject


def corrupt() -> NoReturn:
    reject("candidate_artifact_invalid", "这次排产存下来的结果缺失或对不上，页面没有显示替代内容。请到「排产记录」核对。", 500)


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
    texts = {"not_recorded": "排产时没有记下这一项。", "invalid_stored_value": "排产时记下的这一项格式不对。",
             "blob_metadata": "排产时这一项存的是二进制内容，系统不猜着解读。",
             "source_missing": "排产时的原始记录已经没有了，系统不会拿当前同编号的资料顶替。",
             "undefined_metric": "排产时这个指标没有算出来，占位数字不能当成真实结果。"}
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
        reject("candidate_capacity_exceeded", "这次排产的记录太多，一次读不完，页面没有显示，也没有换成当前数据。请缩小查询范围后重试。", 413)
