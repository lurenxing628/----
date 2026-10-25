"""工作台面向用户的提示模板与统一用词。

词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md。
前端对应 frontend/workbench/app/WorkbenchTerms.js，两边句式保持一致：
结果未知这一族提示只从这里取，各服务不再自己写。
"""
from datetime import datetime, timedelta, timezone

BEIJING = timezone(timedelta(hours=8))

STALE = "数据已更新，请刷新后重试。刚才的选择已保留。"
UNAVAILABLE = "此功能尚未开通。"
FAILURE = "操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。"


def pending(action: str) -> str:
    return f"上次{action}的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。"


def unknown(action: str) -> str:
    return f"{action}结果不确定，可能已经生效。请刷新后核对，不要重复提交。"


def stored_utc_text(value: str) -> str:
    """把数据库 DEFAULT CURRENT_TIMESTAMP 写入的无时区 UTC 时刻换算成北京时间文本。

    SQLite 的 CURRENT_TIMESTAMP 是 UTC，形如 2026-09-13 00:30:00；也接受 ISO 的 T 分隔和小数秒。
    格式不对直接抛 ValueError，不静默给出错误时间。
    """
    text = value.strip().replace("T", " ")
    if len(text) >= 19:
        point = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    else:
        point = datetime.strptime(text, "%Y-%m-%d %H:%M")
    local = point.replace(tzinfo=timezone.utc).astimezone(BEIJING)
    return local.strftime("%Y-%m-%d %H:%M:%S")
