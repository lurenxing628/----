"""工作台面向用户的提示模板与统一用词。

词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md。
前端对应 frontend/workbench/app/WorkbenchTerms.js，两边句式保持一致：
结果未知这一族提示只从这里取，各服务不再自己写。
"""
from datetime import datetime, timedelta, timezone

HOURS_UNIT = "小时"
BEIJING = timezone(timedelta(hours=8))

STALE = "数据已更新，请刷新后重试。刚才的选择已保留。"
UNAVAILABLE = "此功能尚未开通。"
FAILURE = "操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。"

_ENDINGS = ("。", "！", "？", "；")


def sentence(text: str) -> str:
    """补齐句号，让拼接出来的提示读起来是完整的句子。"""
    text = text.strip()
    return text if text.endswith(_ENDINGS) else text + "。"


def pending(action: str) -> str:
    return f"上次{action}的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。"


def rejected(action: str, reason: str) -> str:
    return f"上次{action}没有生效：{sentence(reason)}填写内容已保留，改好后重新提交。"


def done(action: str, next_step: str = "") -> str:
    return f"{action}已完成。{sentence(next_step) if next_step else ''}"


def unknown(action: str) -> str:
    return f"{action}结果不确定，可能已经生效。请刷新后核对，不要重复提交。"


def beijing_text(value: str, seconds: bool = True) -> str:
    """把带时区的 ISO 时刻换算成北京时间文本，供导出与提示使用。

    输入形如 2026-09-13T00:30:00Z 或 2026-09-13T08:30:00+08:00。
    缺时区或格式不对直接抛 ValueError，不静默给出错误时间。
    """
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    point = datetime.fromisoformat(text)
    if point.tzinfo is None:
        raise ValueError(f"时刻缺少时区，无法换算成北京时间：{value}")
    local = point.astimezone(BEIJING)
    return local.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")


def stored_utc_text(value: str, seconds: bool = True) -> str:
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
    return local.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")
