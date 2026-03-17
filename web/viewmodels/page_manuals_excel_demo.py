from __future__ import annotations

from typing import Any, Dict

from .page_manuals_common import _card, _section, _topic

EXCEL_DEMO_TOPICS: Dict[str, Dict[str, Any]] = {
    "excel_demo": _topic(
        title="Excel 演示页",
        summary="这是练习导入流程的安全入口，适合先熟悉预览、导入结果和错误定位方式。",
        full_manual_anchor="#excel演示页",
        help_card=_card(
            "先用这个页面熟悉导入流程",
            '这是练流程的演示页，使用的是"人员基本信息"模板。经典界面需直接访问 /excel-demo/，现代界面可从导航进入。',
            '这里的导入也会写入真实人员数据，不是沙盘数据；页面会把当前库里的人员列出来，方便观察"新增/更新/无变化/跳过/错误"。',
            "先下载模板，表头不要改，文件只支持 .xlsx，大小不超过 16MB；只要有 1 行错误，整份文件都不会导入。",
            "正式业务规则以“人员基本信息（Excel）”页面和说明书第 1.5.5 节为准。",
        ),
        sections=[
            _section(
                "这个页面适合什么时候用",
                "\n".join(
                    [
                        "- 第一次接触系统时，先在这里熟悉导入闭环，而不是直接去正式业务页。",
                        "- 适合验证模板、预览、错误提示和导入结果的阅读方式。",
                        "- 不适合当成沙盘环境，因为这里导入的仍然是真实数据。",
                    ]
                ),
            ),
            _section("通用导入流程", "{{excel_common_flow}}\n\n{{excel_import_modes}}\n\n{{excel_common_errors}}"),
            _section(
                "怎么看导入结果",
                "\n".join(
                    [
                        "- 先看汇总：新增、更新、无变化、跳过、错误各有多少行。",
                        "- 再看明细：错误通常会直接指出哪一列、哪一行不满足规则。",
                        "- 想核对最终结果时，观察页面下方的现存人员列表，确认导入后数据是否符合预期。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["excel_personnel", "excel_personnel_link", "excel_personnel_calendar"],
    ),
}
