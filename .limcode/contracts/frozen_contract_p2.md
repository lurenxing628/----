# FrozenContract（core P2 清理期）

- **parse_strategy(value)**：大小写/空白容错（`str(value).strip().lower()`）；非法/空值回退 default。
- **schedule_optimizer.sort_strategy**：统一走 `parse_strategy()`；multi-start keys 以 `strategy_enum.value` 为准，避免大小写导致策略被静默跳过/重复。
- **priority 常量**：`dispatch_rules / evaluation / sort_strategies` 必须共用同一套 `PRIORITY_*` 与 `normalize_priority()`，避免权重/顺序/分数漂移。
- **metrics 边界语义**：`ScheduleMetrics` 允许新增字段但必须向后兼容；`util_defined=False` 表示 internal horizon=0（util_avg 仅为占位 0.0）。
- **可观测性**：OR-Tools warm-start 失败不阻断主流程，但必须能在日志中定位根因（优先 `exc_info=True`；不支持时回退拼接 traceback）。
- **无 DB schema 变更**：本轮不得改动 `schema.sql` 结构。

