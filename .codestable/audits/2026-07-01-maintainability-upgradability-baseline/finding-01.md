---
doc_type: audit-finding
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
finding_id: "arch-drift-01"
nature: arch-drift
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 01：硬加载期目录环仍在

## 速答

项目已有分层治理，但核心目录仍存在硬加载期循环依赖。现在能运行，不代表升级安全；后续一旦移动公共函数或新增顶层 import，就可能踩到半初始化模块错误。

## 关键证据

- `.codestable/architecture/service-scheduler.md:155-162` — 文档明确记录 `run` 与 `summary` 两个子包互相顶层 import，并把它归为 `scheduler 根 ⇄ run ⇄ summary ⇄ config` 四方硬加载期目录环。
- `core/services/scheduler/run/schedule_orchestrator.py:7` — `run` 顶层导入 `summary.schedule_summary_types.SummaryBuildContext`。
- `core/services/scheduler/summary/schedule_summary_assembly.py:8-11` — `summary` 顶层反向导入 `config.config_snapshot` 和多个 `run` 内部工具函数。
- `python3 -m tools.scan_import_cycles --json` — 本次输出 `hard_dir_cycles` 共 6 组，包含 `core/services/scheduler`、`core/services/scheduler/config`、`core/services/scheduler/run`、`core/services/scheduler/summary`，也包含 `core/infrastructure`、`core/infrastructure/migrations`、`core/models`、`core/shared`。

## 影响

这类问题平时不一定爆炸，但会让升级和拆包变贵：

- 想移动摘要工具时，要担心执行链导入顺序。
- 想拆配置快照时，要同时考虑 run、summary、config 三边。
- 新人或后续代理一旦把函数内导入上提，可能引入启动期错误。

## 修复方向

先不要大搬家。建议先抽出纯契约/纯工具层，例如 `scheduler/common_contracts` 或 `scheduler/result_contracts`，把 `summary` 反借 `run` 的纯函数逐步搬出循环边。

## 建议动作

走 `cs-refactor`。这是行为不变的结构治理，不应该在本审计里直接改。
