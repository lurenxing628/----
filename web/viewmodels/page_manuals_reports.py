from __future__ import annotations

from typing import Any, Dict

from .page_manuals_common import _card, _section, _topic

REPORTS_TOPICS: Dict[str, Dict[str, Any]] = {
    "reports_index": _topic(
        title="报表中心",
        summary="报表中心是各种分析报表的导航页，适合先判断要看超期、利用率还是停机影响。",
        full_manual_anchor="#9-报表中心",
        help_card=_card(
            "先在这里选好要看哪类报表",
            "看交期风险去超期清单，看资源负荷去利用率报表。",
            "看停机影响去停机影响统计。",
            "如果多个报表数据都异常，优先回版本和资源数据核对源头。",
        ),
        sections=[
            _section("怎么从这里选报表", "{{reports_filter_basics}}"),
            _section(
                "常见入口分工",
                "\n".join(
                    [
                        "- 看交期风险：先去超期清单。",
                        "- 看资源负荷和利用率：去资源负荷与利用率。",
                        "- 看停机造成的结果偏差：去停机影响统计。",
                    ]
                ),
            ),
            _section(
                "使用建议",
                "\n".join(
                    [
                        "- 先在这里明确问题类型，再进入具体报表页，效率更高。",
                        "- 如果多个报表数据都异常，优先回到版本、日历和资源数据核对事实源。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["reports_overdue", "reports_utilization", "reports_downtime"],
    ),
    "reports_overdue": _topic(
        title="超期清单",
        summary="超期清单用于定位哪些批次、哪些工序存在交期风险，是排产结果复盘最常看的报表之一。",
        full_manual_anchor="#9-1超期清单",
        help_card=_card(
            "超期清单先看哪些批次超了、超多久",
            "先看批次级超期情况，再看具体卡在哪道工序。",
            "页面和 Excel 列顺序一致：先超期(天)，再超期(小时)。",
            "如果超期集中在少数资源，去甘特图或资源排班中心定位瓶颈。",
            "策略问题回高级设置调方案，资源问题回设备、人员或日历页修正。",
        ),
        sections=[
            _section("先怎么筛", "{{reports_filter_basics}}"),
            _section(
                "看这张表最先看什么",
                "\n".join(
                    [
                        "- 先看哪些批次超期、超期多久，再看具体卡在哪道工序。",
                        "- 若超期集中在少数资源，后续应去甘特图或资源排班中心定位瓶颈。",
                    ]
                ),
            ),
            _section(
                "如何处理发现的问题",
                "\n".join(
                    [
                        "- 如果是策略问题，回高级设置调整方案后重算版本。",
                        "- 如果是资源或日历问题，回设备、人员、工作日历或停机计划页修正事实源。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["reports_index", "scheduler_batches_manage", "scheduler_gantt"],
    ),
    "reports_utilization": _topic(
        title="资源负荷与利用率",
        summary="这张报表用于判断资源是否过载、闲置或分布不均，是调优产能平衡的重要依据。",
        full_manual_anchor="#9-2资源负荷与利用率",
        help_card=_card(
            "利用率看的是资源忙不忙、分布均不均",
            "页面和 Excel 都按百分比显示，表头统一为“利用率(%)”。",
            "利用率异常高的设备或人员可能是瓶颈。",
            "长期空闲的资源可能说明路由或派工方式有问题。",
            "先去资源排班中心看矩阵，再回甘特图定位具体冲突。",
        ),
        sections=[
            _section("先怎么筛", "{{reports_filter_basics}}"),
            _section(
                "最值得先看的指标",
                "\n".join(
                    [
                        "- 哪些设备或人员利用率异常高。",
                        "- 利用率按百分比看：0.75 会显示为 75，超过 100 表示排程负荷超过可用工时。",
                        "- 哪些资源长期空闲，是否说明路由、技能或派工方式有问题。",
                    ]
                ),
            ),
            _section(
                "报表异常时怎么回查",
                "\n".join(
                    [
                        "- 先去资源排班中心看矩阵和任务分布。",
                        "- 再回甘特图定位具体时间段冲突，必要时回高级设置调派工方式或策略。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["reports_index", "scheduler_dispatch", "scheduler_analysis"],
    ),
    "reports_downtime": _topic(
        title="停机影响统计",
        summary="停机影响统计用于评估设备停机对交期、任务分布和版本结果造成的影响。",
        full_manual_anchor="#9-3停机影响统计",
        help_card=_card(
            "停机影响看的是某次停机到底波及了多少任务",
            "先看某段停机窗口影响了哪些批次和任务。",
            "确认关键设备停机是否是超期的主要原因。",
            "停机事实录错了先回设备管理和停机计划页修正。",
        ),
        sections=[
            _section("先怎么筛", "{{reports_filter_basics}}"),
            _section(
                "这张表适合回答什么问题",
                "\n".join(
                    [
                        "- 某段停机窗口到底影响了哪些任务、哪些批次。",
                        "- 是不是某台关键设备的停机导致超期扩散。",
                    ]
                ),
            ),
            _section(
                "发现问题后怎么回到业务页",
                "\n".join(
                    [
                        "- 先回设备管理和停机计划确认停机事实是否录对。",
                        "- 再回超期清单或甘特图验证停机影响是否真的是主要瓶颈。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["reports_index", "equipment_management", "reports_overdue"],
    ),
}
