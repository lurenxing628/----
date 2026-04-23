# 2026-04-16 SP05/SP06 follow-up 修复留痕

## 本次修复关闭的问题

- 修复 `apply_preset()` 对语义等价 legacy preset 的误判：active preset 现在按 canonical snapshot 对 canonical snapshot 判等，不再因为大小写、字符串数值、规范化后的等价值误切 `custom`。
- 修复 `optimize_schedule()` 的 fake strict-mode：`dict/object cfg` 在 `strict_mode=True` 下会按原始输入严格校验，不再先走宽松归一化吞错。
- 修复 objective score/UI schema 多份手写映射：算法评分、summary 的 `comparison_metric/best_score_schema`、analysis VM 的 legacy fallback 统一改为同一 objective spec 来源。
- 修复 summary 主链的本地 cfg fallback：`schedule_summary_assembly`、`schedule_summary_degradation`、`schedule_summary_freeze` 不再定义 `_cfg_value`、`_cfg_yes_no_flag`、`_cfg_freeze_window_state` 这类本地读配置 helper，统一走 snapshot。
- 顺手收掉 `schedule_params.py` 中 weighted `strategy_params` 的 partial 自动补 `0.4/0.5` 行为，改为显式失败。

## 明确保留的有益改动

- `safe_next_url` / facade 单核心实现继续保留。
- `active_preset_reason` 当前状态同步机制继续保留；本次只修误判来源，不回退状态展示链。
- `scheduler_config` 页面 metadata 统一来源继续保留。

## 本次采用的契约口径

- `optimize_schedule()` 当前版本继续兼容 `dict/object/ScheduleConfigSnapshot` 输入。
- `strict_mode=True` 的语义明确为“按原始输入严格验证”。
- `ScheduleConfigSnapshot` 仍是内部首选输入形态，但这次不做公开 API 的破坏性收紧。

## 暂不处理但已留痕的事项

- 若后续要把 `optimize_schedule()` 彻底收紧为 `ScheduleConfigSnapshot` only，需要单独做契约变更。
- 当前未继续扩大页面 metadata 的覆盖范围；本次仅清理无害 compat 残留，不新增第二事实源。
