"""Batch request shapes and signed previews, using common contexts and receipts."""

import re
from datetime import datetime
from types import MappingProxyType
from typing import Dict, Union

from core.errors import ValidationError
from core.models.workbench_batch_query import SCOPE_FIELDS, batch_scope
from core.models.workbench_command import SHAPE_REJECTED, WorkbenchCommandRejected
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .read_context import fact_value
from .request_json import BodyTexts, single_value_arguments

PREVIEW_SCOPE = "workbench-batch-preview-v1"
BODY = BodyTexts(transport="提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。",
                 malformed="提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。",
                 incomplete=SHAPE_REJECTED)
STALE = "本页数据已过期，还没有保存。请点「刷新资料」后重新填写。"


def read_scope():
    arguments = single_value_arguments(SCOPE_FIELDS, message="筛选条件有重复或不支持的项，列表没有变化。请刷新页面后重新选择。")
    for key in ("page", "size"):
        if key in arguments and re.fullmatch(r"[1-9][0-9]{0,6}", arguments[key]) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码或每页条数填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
    values: Dict[str, Union[str, int]] = {key: int(value) if key in ("page", "size") else value
                                          for key, value in arguments.items()}
    return batch_scope(values)


def save_preview(action, ref, payload, fingerprint, *, with_expiry=False):
    token, expiry = issue_public_token_with_expiry(
        PREVIEW_SCOPE, MappingProxyType({"action": action, "ref": ref, "input": payload, "fingerprint": fingerprint}),
        key=(action, ref, fact_value(payload)), group=fact_value(fingerprint), ttl_seconds=900)
    return (token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")) if with_expiry else token


# 预检编号失效或对不上时：按动作说清没做成什么，并点名页面上真正用来重做这一步的按钮。
_RETRY = {
    "split_confirm": ("预检结果", "还没有保存", "重新点「预检可开工数量」"),
    "sync_confirm": ("预检结果", "还没有保存", "重新点「预检工序更新」"),
    # 批量修改、复制所选、删除所选和单个批次的删除（列表「删除」/详情「删除批次」）共用这一个确认动作；编号失效后分不出是哪一种。
    "bulk_confirm": ("预检结果", "还没有保存", "按原来的操作重新点「预览变更」「复制所选」「删除所选」，或列表里该批次的「删除」、批次详情的「删除批次」"),
    # 导入预检结果出来后「开始预检」会收起，要先点「更换文件」才会再出现。
    "import_confirm": ("预检结果", "文件还没有导入", "点「更换文件」后重新点「开始预检」"),
    "export": ("导出范围", "没有开始下载", "重新点「下载批次清单」"),
}
_BULK_RETRY = {"update": "重新点「预览变更」", "copy": "重新点「复制所选」", "delete": "重新点「删除所选」，或列表里该批次的「删除」、批次详情的「删除批次」"}


def retry_hint(action, payload=None):
    """重做这一步要点的按钮；批量操作读得出原动作时只点名那一个按钮。"""
    bulk = payload.get("action") if action == "bulk_confirm" and isinstance(payload, dict) else None
    return (_BULK_RETRY.get(bulk) if isinstance(bulk, str) else None) or _RETRY[action][2]


def retry_message(action, reason, payload=None):
    return reason + "，" + _RETRY[action][1] + "。请" + retry_hint(action, payload) + "。"


def load_preview(token, action, ref):
    noun = _RETRY[action][0]
    expired = retry_message(action, noun + "已过期，系统没有自动重做")
    try:
        binding = resolve_public_token(PREVIEW_SCOPE, token, message=expired, field="preview_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("stale_write", expired) from exc
    if binding["action"] != action or binding["ref"] != ref:
        raise WorkbenchCommandRejected("stale_write", retry_message(action, noun + "和当前批次操作对不上"))
    return binding
