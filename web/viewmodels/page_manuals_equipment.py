from __future__ import annotations

from typing import Any, Dict

from .page_manuals_common import _card, _section, _topic

EQUIPMENT_TOPICS: Dict[str, Dict[str, Any]] = {
    "equipment_management": _topic(
        title="设备管理",
        summary="这里管理所有设备的状态、工种、班组和停机计划，设备信息不对，排产结果就不对。",
        full_manual_anchor="#5-3设备管理",
        help_card=_card(
            "设备信息决定排产能用哪些资源",
            "设备状态和停机计划都会直接影响排产结果。",
            "删除或停用设备前，先确认有没有被排产和人员关联引用。",
            "批量停机计划在子导航里，设置后会在甘特图上直接反映。",
        ),
        sections=[
            _section("进入前准备", "{{list_page_basics}}"),
            _section(
                "这个页面主要做什么",
                "\n".join(
                    [
                        "- 查看当前设备清单及其状态、工种、班组信息。",
                        "- 进入详情页维护单台设备属性，或进入批量停机计划设置停机窗口。",
                        "- 从这里进入设备信息导入和设备人员关联维护页。",
                    ]
                ),
            ),
            _section(
                "容易忽略的影响",
                "\n".join(
                    [
                        "- 设备状态和停机计划都会直接影响排产结果与资源利用率。",
                        "- 删除或停用设备前，先确认是否仍被历史版本、人员关联或工艺模板引用。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["equipment_downtime_batch", "excel_equipment", "excel_equipment_link", "scheduler_gantt"],
    ),
    "equipment_detail": _topic(
        title="设备详情",
        summary="这里查看和维护单台设备的状态、工种、班组和关联人员，信息错了，派工和甘特图都会跟着偏。",
        full_manual_anchor="#5-3设备管理",
        help_card=_card(
            "先看这台设备现在能不能用",
            "优先确认设备状态、工种和班组是不是对的。",
            "再看关联人员和主操设置，避免人机关系配错。",
            "如果只是临时停机，优先去停机计划，不要直接把设备改停用。",
        ),
        sections=[
            _section(
                "这个页面主要做什么",
                "\n".join(
                    [
                        "- 维护单台设备的详细资料，而不是整张设备列表。",
                        "- 查看并维护关联人员、停机记录和状态变化。",
                        "- 作为设备侧排错入口，确认这台设备为什么没被排上或为什么排错了。",
                    ]
                ),
            ),
            _section(
                "最值得先检查的 4 项",
                "\n".join(
                    [
                        "- 状态是不是可用、维修还是停用。",
                        "- 工种和班组是不是挂对，避免任务被派到不该派的设备上。",
                        "- 关联人员是否完整，技能等级和主操设置是否合理。",
                        "- 最近有没有停机计划，尤其是当前版本涉及的时间段。",
                    ]
                ),
            ),
            _section(
                "什么时候别在这里直接改",
                "\n".join(
                    [
                        "- 只是临时停机时，优先走停机计划，不要把状态直接改成停用。",
                        "- 很多设备一起改时，优先回 Excel 页批量维护。",
                        "- 发现排产异常时，先看是不是工种、关联人员或停机计划导致，再决定改哪个字段。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["equipment_management", "equipment_downtime_batch", "excel_equipment_link", "scheduler_gantt"],
    ),
    "equipment_downtime_batch": _topic(
        title="批量停机计划",
        summary="这里按设备、类别或全体设备批量维护停机窗口，停机会直接改写资源可用性和排产结果。",
        full_manual_anchor="#批量停机计划",
        help_card=_card(
            "批量停机前先想清楚影响范围",
            "先选对范围，再确认开始结束时间，避免一键影响太多设备。",
            "时间段有重叠时，系统会跳过冲突设备，不会强行覆盖。",
            "建完后建议马上去甘特图或停机影响报表复核效果。",
        ),
        sections=[
            _section(
                "这个页面适合什么时候用",
                "\n".join(
                    [
                        "- 同一批设备要一起停机检修时。",
                        "- 按设备类别统一安排停机窗口时。",
                        "- 想快速把维护计划反映到排产结果，而不是一台台手填时。",
                    ]
                ),
            ),
            _section(
                "创建前先确认什么",
                "\n".join(
                    [
                        "- 先确认范围：是单台、某个类别，还是全部设备。",
                        "- 停机时间不要和已有停机窗口重叠，否则部分设备会被跳过。",
                        "- 如果只是个别设备临时调整，优先回设备详情单独维护，更不容易误伤。",
                    ]
                ),
            ),
            _section(
                "建完后怎么验证",
                "\n".join(
                    [
                        "- 去甘特图看停机时段内任务是否避让开了。",
                        "- 去停机影响统计看这次停机到底影响了哪些任务和批次。",
                        "- 如果现场实际恢复时间有变，要及时回来修，不然版本分析会一直偏。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["equipment_management", "equipment_detail", "scheduler_gantt", "reports_downtime"],
    ),
    "excel_equipment": _topic(
        title="设备信息（Excel）",
        summary="用 Excel 批量维护设备主数据，重点控制设备编号、状态、工种和班组。",
        full_manual_anchor="#1-56设备信息",
        help_card=_card(
            "设备信息——填写速查",
            "列：设备编号、设备名称、工种、班组、状态。",
            "其中设备编号、设备名称、状态必填；工种、班组选填。",
            "工种填工种ID或工种名称，必须在“工种配置”里存在；留空则不设工种。",
            "状态可填：可用 / 停用 / 维修 / active / inactive / maintain / 维护 / 保养；状态不能为空，不是“不填默认可用”。",
            "班组填班组编号或名称，必须系统里已存在；留空则不分组。",
            "设备编号会被停机计划、人员关联和排产结果引用，导入后保持稳定。",
            "替换模式下如有排产数据引用了设备，系统会拒绝，改用覆盖即可。",
        ),
        sections=[
            _section("导入前准备", "{{excel_common_flow}}\n\n{{excel_import_modes}}"),
            _section(
                "关键列怎么填",
                "\n".join(
                    [
                        "- `设备编号`：主键字段，必须唯一且保持稳定。",
                        "- `设备名称`：展示字段，建议和现场标识一致。",
                        "- `工种`：可填工种 ID 或名称，必须先在工种配置中存在。",
                        "- `班组`：可填编号或名称，但必须先有班组主数据。",
                        "- `状态`：必填，支持可用/停用/维修及对应英文别名。",
                    ]
                ),
            ),
            _section("错误与联动", "{{excel_common_errors}}"),
            _section(
                "替换模式为什么风险高",
                "\n".join(
                    [
                        "- 设备经常被停机计划、人员关联和排产记录引用，贸然替换容易打断后续数据链路。",
                        "- 系统通常会阻止存在引用关系的高风险替换，日常维护优先用覆盖。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["equipment_management", "excel_equipment_link", "excel_op_types"],
    ),
    "excel_equipment_link": _topic(
        title="设备人员关联（Excel）",
        summary="批量维护设备与人员的关联关系，业务含义与人员设备关联一致，适合从设备视角维护。",
        full_manual_anchor="#1-57人员设备关联",
        help_card=_card(
            "设备人员关联——填写速查",
            "列：设备编号(必填)、工号(必填)、技能等级、主操设备。",
            "设备编号和工号必须是系统里已存在的，否则报错。",
            "技能等级可填：初级 / 普通 / 熟练 / beginner / normal / expert（也兼容专家、高级、新手等别名），不填默认普通。",
            "主操设备填 是/否 或 yes/no 或 主操/非主操；同一人只能有 1 台主操设备，多了会报错。",
            "和人员侧导入的区别主要是列顺序：这里是“设备编号在前、工号在后”。",
            "导入前先确认设备和人员都已创建。",
        ),
        sections=[
            _section("导入前准备", "{{excel_common_flow}}\n\n{{excel_import_modes}}"),
            _section(
                "关键列怎么填",
                "\n".join(
                    [
                        "- `设备编号` 和 `工号` 都必填，且必须存在。",
                        "- `技能等级` 和 `主操设备` 的业务规则与人员侧导入完全一致。",
                        "- 适合在设备主管按设备视角维护关联时使用。",
                    ]
                ),
            ),
            _section(
                "什么时候选设备侧，什么时候选人员侧",
                "\n".join(
                    [
                        "- 业务上二者等价，只是录入视角不同。",
                        "- 一个周期内建议固定只用一侧维护，避免双方同时更新造成理解偏差。",
                    ]
                ),
            ),
            _section("错误与联动", "{{excel_common_errors}}"),
        ],
        related_manual_ids=["excel_equipment", "excel_personnel", "equipment_management"],
    ),
}
