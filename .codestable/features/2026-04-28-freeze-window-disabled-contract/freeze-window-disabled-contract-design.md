---
doc_type: feature-design
feature: 2026-04-28-freeze-window-disabled-contract
status: approved
summary: 固定冻结窗口 disabled/degraded 状态合同，并补齐 review 后页面展示和 CodeStable 承接记录。
tags: [scheduler, freeze-window, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: freeze-window-disabled-contract
---

# 冻结窗口状态合同设计补录

## 0. 补录说明

本设计是 M2 执行后的补录承接，不伪装成当时完整重走了一遍 feature 流程。M2 已通过提交 `8c23c94` 完成冻结窗口状态合同实现，并通过 `d941a1b` 回填 roadmap/items；本补录用于补齐 CodeStable feature 追踪链。

## 1. 决策与约束

- 本次只处理冻结窗口状态合同、分析页展示和 M2 文档承接。
- `enabled` 保持配置开关兼容值，不把 degraded 伪装成 enabled。
- `degraded` 由 `freeze_state` / `degraded` 表达，页面展示也以状态为主事实。
- 不新增 fallback、兜底、静默吞错，不写入 `input_fallback` 或 `config_fallback`。
- P1-14 复杂度仍未关闭，P1-15 只写状态合同测试补证；本次不减少 full-test-debt。

## 2. 名词与展示合同

- `freeze_state="disabled"`：正常未启用冻结窗口，页面显示“冻结窗口：未启用”。
- `freeze_state="degraded"`：冻结窗口状态异常，页面必须显示“当前状态：已降级”，即使 `enabled="no"`。
- `freeze_disabled_reason`：仅说明普通 disabled 的安全原因；配置降级不通过它公开给页面。

## 3. 验收契约

- 配置关闭、天数为 0、无上一版本、无可 seed、上一版本无行要能区分 disabled 原因。
- `freeze_window_enabled` / `freeze_window_days` 配置读取降级必须是 degraded，strict 模式继续 fail closed。
- Summary 只在真正 disabled 时透传 `freeze_disabled_reason`。
- 分析页不能把 `enabled=no + freeze_state=degraded` 显示成普通未启用。
- CodeStable roadmap item 必须能追到本 feature 目录、验收记录和 source-map 结论。

## 4. 明确不做

- 不降低 `build_freeze_window_seed` 复杂度，不刷新台账移除 P1-14。
- 不关闭任何 active full-test-debt。
- 不修改停机区间、资源池、落库、runtime/plugin 或质量门禁工具。
