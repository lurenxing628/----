"""Bounded process payloads keep each action's label in the shared strict JSON texts and byte limit."""

from .request_json import BodyTexts, command_body, read_json_body


def _texts(label, incomplete):
    return BodyTexts(transport=label + "没有执行：提交的内容格式不正确，也不能在网址上附加条件。请刷新页面后重新提交。",
                     malformed=label + "没有执行：提交的内容格式不正确。请刷新页面后重新提交。",
                     incomplete=incomplete,
                     duplicate=label + "没有执行：提交的内容有重复项。请刷新页面后重新提交。")


def _limit(label, maximum):
    return maximum, label + "没有执行：一次提交的内容太多，系统没有截断处理。请缩小范围后重新提交。"


def read_process_json(label, maximum):
    return read_json_body(_texts(label, label + "没有执行：提交的内容不完整。请刷新页面后重新提交。"),
                          limit=_limit(label, maximum))


def process_command_body(label, maximum, *, incomplete, stale):
    """A process command envelope under the label's transport texts and byte limit; ``incomplete`` names a wrong envelope."""
    return command_body(_texts(label, incomplete), stale=stale, limit=_limit(label, maximum))
