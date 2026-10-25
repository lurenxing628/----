"""Bounded process payloads keep each action's label in the shared strict JSON texts."""

from .request_json import read_json_body


def read_process_json(label, maximum):
    return read_json_body(
        transport=label + "没有执行：提交的内容格式不正确，也不能在网址上附加条件。请刷新页面后重新提交。",
        malformed=label + "没有执行：提交的内容格式不正确。请刷新页面后重新提交。",
        incomplete=label + "没有执行：提交的内容不完整。请刷新页面后重新提交。",
        duplicate=label + "没有执行：提交的内容有重复项。请刷新页面后重新提交。",
        limit=(maximum, label + "没有执行：一次提交的内容太多，系统没有截断处理。请缩小范围后重新提交。"),
    )
