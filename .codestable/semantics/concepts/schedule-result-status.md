# 概念身份证 · schedule_result_status（排产结果状态）

- status: current
- owner_area: scheduler_result_view
- canonical module: `web/viewmodels/scheduler_summary_result_state.py`
- 立证 feature: fusion-label-single-source（2026-06-12）

## 规范定义

| 值 | 中文标签 | 来源 |
|---|---|---|
| success | 成功 | ScheduleResultStatus 枚举 |
| partial | 部分成功 | 同上 |
| failed | 失败 | 同上 |
| simulated | 模拟排产 | 同上（甘特模拟预览） |
| （unknown） | 有问题，需检查 | 非合法值的诚实降级标签，不是可写入值 |

输入别名（读取归一，不进展示字典）：`ok→success`、`fail→failed`（老现场库兼容，`resolve_result_status`）。

## 行为合同

- 模板一律消费 decorate 行级标签（`result_status_label`/`version_option_label`），不查词表；
  全部版本下拉/摘要行数据先过 `decorate_history_version_options`。
- simulated 行展示复合标签「模拟排产 / {outcome}」（`result_status_display_label`）。
- 未知值（含已删除的 ok2 残值）→「有问题，需检查」——诚实降级而非静默错标成功。
- analysis_overview / guardrail_messages 的 status 字典从 `result_status_display_labels()` 派生，禁手写。

## 禁止含义

- ❌ 在模板内联 status_zh 中文字典（回潮守卫 `tests/web_pages/test_label_single_source_contract.py`）。
- ❌ `ok2` 不是合法值——写入方零证据（git log -S 零命中 + 枚举仅 4 值），2026-06-12 全删；重新引入即漂移。
- ❌ 把输入别名 ok/fail 当平行展示键写进任何字典。

## 守卫指针

- registry 对账：`.codestable/semantics/tools/check_concept_registry.py`（枚举值集/标签/别名表三对账）
- 标签快照：`.codestable/semantics/tests/__snapshots__/result_status_labels.json`
- 回潮守卫（required）：`tests/web_pages/test_label_single_source_contract.py`
