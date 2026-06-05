---
doc_type: decision
date: 2026-06-05
slug: r24-diagnostic-contract-keep
title: 保留 core 诊断契约 schedule_diagnostic_contract.py（不删，架构受限的预留件）
status: decided
owner: lurenxing
source: 80 条水下债依赖分析 R24 dossier（docs/_panorama_data/phase4_dep_safety/dossiers/R24.md）
---

# 决策：保留 core 层诊断契约 `schedule_diagnostic_contract.py`（R24）

## 一句话结论

`core/services/scheduler/analysis/schedule_diagnostic_contract.py`（82 行）**保留不删**。它不是冗余的重复实现，而是一份**因架构规矩暂时落不了地的预留契约层**。删它容易（零生产消费），但 owner 决定留作"诊断回归 core 统一契约层"这一未来架构方向的地基。

## 这块原本打算干嘛

- 当初重构（分支 `codex/scheduler-analysis-entry-refactor`）在 **core 层**建了这份"诊断合同"，意图是做成排产分析页诊断摘要的**统一数据契约层**：`build_diagnostic_link / build_diagnostic_item / build_diagnostic_section / empty_diagnostic_sections`（纯 dict 拼装）。
- networkx 路线图 **PR-9「排产分析页诊断摘要第一版」**（slug: `scheduler-graph-analysis-diagnostic-sections`，状态 `planned` 未开工）计划基于它做四块诊断：**排产体检 / 资源卡点 / 延期风险 / 影响解释**，把它列入 `primary_paths`（:435）与 ruff/pyright `exit_checks`（:480/:481）。

## 为什么它现在零消费（被架空）

- PR-9 设计自带一条**架构铁律**（其 notes 原文）：诊断 builder 要拆成**纯 viewmodel 小文件**，**"避免 viewmodel 反向 import service 层"**。
- 而这份契约在 **core(service) 层**。web 的 viewmodel 若 import 它 = viewmodel 反向依赖 service，**违反架构门禁**。
- 于是实际落地时，web 的 viewmodel **自己实现了一份孪生** `web/viewmodels/scheduler_analysis_diagnostic_helpers.py`，承载全部活渲染，且**比 core 那份更完善**——带 `NonFiniteDiagnosticNumber / safe_int / safe_float` 的"坏数字 loud raise"护栏。
- 结果：core 这份契约**从未真正接上**，全仓生产零消费（仅 1 个测试 import 它）。

## 决策理由（为什么留而不删）

- owner 判断：保留为"**诊断回归 core 统一契约层**"这一**未来可能的架构方向**留地基。若将来决定让诊断走 core 契约（而非 web viewmodel 各写一套），可直接捡起这份。
- 留着的成本极低（82 行、零消费、不在任何活链路上）。

## 防误删 / 防误用警示（关键 —— 给未来的人）

1. **别把它当"重复实现/P5"删掉**：它是架构受限的**预留件**，不是冗余。审计 / 语义雷达再扫到"诊断 dict 拼装有两份"时，先读本记录，**不要当重复副本清理**。
2. **绝不能反向让活路径改指它**：core 这份对非有限数字是**"静默透传坏值"**，web 孪生是**"loud raise 拦住"**。若让 web 活路径改用 core 契约，会**丢掉坏数字护栏、退化为静默吞错（踩 P4 灵魂线）**。真要走 core 路线，**必须先把护栏下沉到 core 并补 NaN/Inf/bool 三反例 parity**。
3. core 文件本身无 except / 无回退，删除不触灵魂线；**真护栏在 web 孪生**（禁区行：helpers.py `NonFiniteDiagnosticNumber:101` / `safe_int:127` / `safe_float:144` + 各 raise 行）。

## 配套动作（owner 2026-06-05 裁定）

- 在 core 文件顶部补一行"**我是故意保留**"注释：说明它是诊断统一契约层的预留件，因"viewmodel 不得反向 import service 层"的架构门禁暂未接入，活渲染由 web 孪生承载。
- PR-9 networkx 路线图对它的引用（primary_paths/exit_checks）**保留不动**（因为文件留着，检查命令不会指向死文件）。
- 本记录作为事实档案沉淀，供未来检索。

## 重新启用条件

当且仅当 owner 决定**改架构方向**、让排产诊断回归"core 统一契约层"（需配套：解决 viewmodel↔service 分层约束、把坏数字护栏下沉到 core、补 NaN/Inf/bool parity）。否则它将一直是零消费预留件，**保持现状即可**。

## 证据锚点（2026-06-05 回盘）

- core 文件：`core/services/scheduler/analysis/schedule_diagnostic_contract.py`（82 行；def `:12/:25/:46/:73`；`__all__ :77-82`）
- web 活孪生：`web/viewmodels/scheduler_analysis_diagnostic_helpers.py`（`build_item:41` / `build_section:62`；护栏 `NonFiniteDiagnosticNumber:101` / `safe_int:127` / `safe_float:144`）
- 路线图：`.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml`（PR-9 `primary_paths:435`，`exit_checks` ruff`:480` / pyright`:481`）
- 唯一测试：`tests/regression_scheduler_analysis_diagnostic_contract.py`
- 生产消费：`rg` 全仓零命中（除文件自身 + 1 测试）
