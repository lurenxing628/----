---
doc_type: feature-design
feature: 2026-04-28-plugin-enabled-source-contract
status: approved
summary: 收口插件开关来源合同，让默认关闭、来源汇总、错误公开文案和系统页可见信息被测试锁住。
tags: [startup, plugin, ui-contract, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: plugin-enabled-source-contract
---

# plugin enabled source contract 设计

## 0. 承接边界

本任务只处理 M7-B：`web/bootstrap/plugins.py:_apply_enabled_sources` 复杂度和插件来源可见性。

明确不做：

- 不改变 `PluginManager.load_from_base_dir()` 的默认开关语义。
- 不把 P1-24 当成 open bug；本轮只复核没有 open 的 plugin fallback。
- 不新增数据库失败、配置读取失败或插件加载失败的兜底分支。
- 不处理 launcher、runtime stop 或 P1-25。

## 1. 对外合同

- 真实可选插件 `pandas_excel_backend` 和 `ortools_probe` 在无配置时默认关闭。
- 默认关闭时不注册 pandas 或 OR-Tools 能力，Excel 默认仍走 openpyxl。
- `enabled_source` 先看显式配置来源，再看插件行自带来源，最后才用本轮默认来源。
- 有配置和默认来源混用时，整体 `config_source` 为 `mixed`。
- 系统页能看到插件留痕状态和能力冲突信息。

## 2. 实现策略

1. 补真实插件默认关闭测试和 `_apply_enabled_sources` 来源汇总测试。
2. 将 `_apply_enabled_sources` 拆成来源判定、公开状态行整理、整体来源汇总三个小函数。
3. 系统页模板展示 `telemetry_persisted` 和 `conflicted_capabilities`。
4. 跑 plugin bootstrap 回归和架构复杂度检查。

## 3. 验收契约

- P1-23 复杂度登记关闭。
- P1-24 只复核，不能写成修复 open fallback。
- 默认关闭、来源汇总、错误脱敏、冲突信息、留痕状态均有测试或模板守护。
