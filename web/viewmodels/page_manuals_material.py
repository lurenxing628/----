from __future__ import annotations

from typing import Any, Dict

from .page_manuals_common import _card, _section, _topic

MATERIAL_TOPICS: Dict[str, Dict[str, Any]] = {
    "material_master": _topic(
        title="物料主数据",
        summary="物料主数据用于维护物料清单和库存基础信息，是后续批次齐套判定的前提。",
        full_manual_anchor="#物料主数据",
        help_card=_card(
            "物料主数据和齐套是两步事",
            "先建物料主数据，再去“批次物料需求”维护齐套。",
            "库存数量填数值；状态和备注可后续补。",
            "只有挂了物料需求行的批次，系统才会自动接管齐套状态。",
        ),
        sections=[
            _section("这个页面主要做什么", "{{list_page_basics}}"),
            _section(
                "为什么先维护这里",
                "\n".join(
                    [
                        "- 物料主数据是批次物料需求页的前置条件。",
                        "- 没有物料主数据，后续齐套判定无法正确挂接到具体物料。",
                    ]
                ),
            ),
            _section(
                "容易误解的地方",
                "\n".join(
                    [
                        "- 这里维护的是物料本身，不是批次的齐套状态。",
                        "- 只有批次真正挂了物料需求，系统才会自动计算和回写齐套结果。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["material_batch", "scheduler_batches", "excel_batches"],
    ),
    "material_batch": _topic(
        title="批次物料需求（齐套判定）",
        summary="这里维护批次对应的物料需求，并由系统回写齐套状态和齐套日期。",
        full_manual_anchor="#批次物料需求齐套判定",
        help_card=_card(
            "齐套判定页这样用最稳",
            "先选批次，再新增物料需求；系统会自动回写齐套状态和齐套日期。",
            "如果批次没有任何物料需求行，系统不会覆盖你手工填写的齐套状态。",
            "物料必须先在“物料主数据”里存在。",
        ),
        sections=[
            _section(
                "这个页面主要做什么",
                "\n".join(
                    [
                        "- 给批次挂接具体物料需求。",
                        "- 根据需求与库存情况，辅助判断批次是否齐套、何时齐套。",
                    ]
                ),
            ),
            _section(
                "维护顺序建议",
                "\n".join(
                    [
                        "- 先建物料主数据，再回来给批次挂需求。",
                        "- 批次需求维护完后，再去执行排产页验证齐套约束是否生效。",
                    ]
                ),
            ),
            _section(
                "为什么系统有时不回写齐套状态",
                "\n".join(
                    [
                        "- 如果该批次根本没有需求行，系统不会强行覆盖你手工填的齐套状态。",
                        "- 若想让系统自动接管，必须保证物料需求行完整且引用的是已存在物料。",
                    ]
                ),
            ),
        ],
        related_manual_ids=["material_master", "scheduler_batches", "excel_batches"],
    ),
}
