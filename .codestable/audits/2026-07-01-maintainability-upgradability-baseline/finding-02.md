---
doc_type: audit-finding
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
finding_id: "maintainability-02"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 02：排产核心仍是巨型模块

## 速答

`core/services/scheduler/` 是项目最大模块，虽然已经切出 `run/summary/config/graph/analysis`，但根目录仍平铺大量业务文件，且保留旧路径垫片。后续继续加功能时，很容易继续往大模块里塞。

## 关键证据

- `.codestable/architecture/service-scheduler.md:21-23` — 文档记录 `core/services/scheduler/` 约 43628 行 / 206 个 Python 文件，且仍有 79 个业务文件直接平铺在根目录。
- `.codestable/architecture/service-scheduler.md:48-66` — 模块一半按流程分包，一半按业务对象平铺，心智模型较重。
- `core/services/scheduler/__init__.py:18-57` — 对外 13 个 Service 入口集中在根门面，其中多数真实实现仍在根目录业务文件。
- `.codestable/architecture/service-scheduler.md:123-127` — 文档记录 `run_shim` 旧路径垫片和多个跨族枢纽文件。
- `.codestable/architecture/service-scheduler.md:170-174` — 文档明确记录旧垫片造成双入口，以及 `config_snapshot` 已经成为隐性公共契约。

## 影响

大白话讲：不是说它不能跑，而是以后每次要改排产，很难一眼判断“该改哪一层”。这会带来几个成本：

- 新功能容易继续堆到根目录。
- 同一能力可能从新旧两个入口进入。
- 分包时先要还垫片和公共契约债。
- 代码评审时很难只看一个小范围就放心。

## 修复方向

先做分包路线图，再分阶段治理：

- 第一阶段：明确新代码只能走 `scheduler.run.*` 还是根门面。
- 第二阶段：把 `config_snapshot` 这类事实公共契约移到更中立的位置。
- 第三阶段：按业务族拆根目录，例如 `gantt`、`resource_dispatch`、`plan_core`、`execution_fact`。

## 建议动作

走 `cs-refactor` 或 `cs-roadmap`。如果只拆一小块，走 `cs-refactor`；如果要治理整个排产模块，走 `cs-roadmap` 更合适。
