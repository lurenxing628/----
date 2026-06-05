from __future__ import annotations

from typing import Dict

_REPORT_LIMITATIONS = {
    "overdue": (
        "这张表能回答哪些批次晚了。",
        "它不能单独证明唯一原因；需要结合延期说明、甘特排班和现场事实继续看。",
    ),
    "utilization": (
        "这张表能回答设备和人员在当前范围内有多忙。",
        "它不能证明资源一定造成延期；需要回资源派工或甘特确认排班细节。",
    ),
    "execution_review": (
        "这张表能回答正式计划和现场实际是否一致。",
        "它不复盘模拟预览，也不在这里写现场记录。",
    ),
    "downtime": (
        "这张表能回答设备级停机时长和排程重叠情况。",
        "当前不能证明具体影响了哪一道任务；任务级影响需要单独查看明细。",
    ),
}


def build_report_limitations(report_key: str) -> Dict[str, str]:
    answer, limitation = _REPORT_LIMITATIONS.get(
        report_key,
        ("这张报表用于继续追踪排产风险。", "它不能替代对应业务页面的明细核查。"),
    )
    return {"answer_text": answer, "limitation_text": limitation}
