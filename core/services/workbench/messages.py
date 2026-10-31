"""工作台面向用户的提示模板与统一用词。

词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md。
前端对应 frontend/workbench/app/WorkbenchTerms.js，两边句式保持一致：
结果未知这一族提示只从这里取，各服务不再自己写。
"""
import re
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


# 资源导出与物料导出共用同一条规则：认得出的存储时刻才换算。
_STORED_TIME_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")


def local_created_at(value):
    """数据库按 UTC 写入的创建/更新时间；资源与物料的导出、物料导入预检的"原值"都换算为工厂本地时间。

    这些时间只是导出带出的参考列，导入不看。认不出的旧写法（只有日期、斜杠日期、空串等）原样写出，
    不猜着换算，也不因为这一格让整份资料导不出来、导入预检报错。
    """
    if type(value) is not str or _STORED_TIME_TEXT.match(value) is None:
        return value
    try:
        return stored_utc_text(value)
    except (ValueError, OverflowError):
        # 形似时刻却不是真实日期（例如 2026-02-30 08:00），或换算后越过 9999 年（9999-12-31 16:00 以后），同样原样写出
        return value
