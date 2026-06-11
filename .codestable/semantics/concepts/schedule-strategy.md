# 概念身份证 · schedule_strategy（排产策略）

- status: current
- owner_area: scheduler_result_view
- canonical module: 配置合法值 `core/services/scheduler/config/config_field_spec.py`（sort_strategy spec）；展示词表 `web/viewmodels/scheduler_history_summary.py::_STRATEGY_LABELS`
- 立证 feature: fusion-label-single-source（2026-06-12）

## 规范定义（两层）

**合法配置值**（用户可选，与 config_field_spec choices 对账相等）：

| 值 | 中文标签 |
|---|---|
| priority_first | 优先级优先 |
| due_date_first | 交期优先 |
| weighted | 综合优先级和交期 |
| fifo | 先进先出 |

**历史展示兼容值**（历史行实存，非用户可选配置）：

| 值 | 中文标签 | 来历 |
|---|---|---|
| manual | 手动排产 | 仅甘特调整发布写入（gantt_adjustment_publish_service） |
| improve | 优化排产 | algo_mode 值混入 strategy 的历史遗留 |
| greedy | 快速排产 | 同上；瘦身归 cs-refactor（需老库考古） |

合法值 ∪ 兼容值 = `_STRATEGY_LABELS` 7 键（registry 对账规则，刻意不做三方硬相等——greedy 在测试夹具与历史行真实在用）。

## 行为合同

- 模板一律消费 decorate 行级标签（`strategy_label`），不查词表。
- 未知值展示走 `strategy_display_label`（「历史记录异常」不伪装）；strict 场景 `strict_strategy_display_label` raise。

## 禁止含义

- ❌ improve/greedy 是 algo_mode，不是 sort_strategy 合法配置值——不得加进 config choices。
- ❌ 在模板内联 strategy_zh 中文字典（回潮守卫同 result_status）。

## 守卫指针

- registry 对账：`.codestable/semantics/tools/check_concept_registry.py`（合法值=config choices；合法∪兼容=标签键集）
- 标签快照：`.codestable/semantics/tests/__snapshots__/strategy_labels.json`
- 回潮守卫（required）：`tests/web_pages/test_label_single_source_contract.py`
