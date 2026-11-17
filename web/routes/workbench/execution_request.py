"""Field (execution) request shapes shared by the report and report-file routes: the read body and the report command."""

from .request_json import BodyTexts, command_body, read_json_body, rejecter

_UNREADABLE = "提交的内容格式不正确，报工还没有保存。请刷新页面后重新填写。"
_COMMAND = BodyTexts(transport=_UNREADABLE, malformed=_UNREADABLE,
                     incomplete="提交的内容不完整或有多余项，报工还没有保存。请刷新页面后重新填写。")
_READ_REJECTED = "现场记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。"
_READ = BodyTexts(transport=_READ_REJECTED, malformed=_READ_REJECTED, incomplete=_READ_REJECTED)


def field_read():
    """A field read's scope, paging and locator travel in the POST body: a batch list can be longer than a request
    line allows. Its keys and values are admitted by ``field_workspace_scope``."""
    return read_json_body(_READ)


def field_command():
    """A report command: the command envelope whose input is an object."""
    body = command_body(_COMMAND, stale="本页数据已过期，报工还没有保存。请点「刷新资料」后重新填写。")
    if type(body["input"]) is not dict:
        rejecter(_COMMAND.incomplete)()
    return body
