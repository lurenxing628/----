---
doc_type: decision
category: convention
date: 2026-09-20
slug: tests-at-seams
status: active
area: tests
tags: [tests, repositories, services, contracts, quality-gate]
---

## 背景

工作台 493 个测试文件对应 233 个模块，大部分测试从路由或服务入口一路打到 SQLite，同一条 SQL 被几十个测试间接覆盖，却没有一个测试直接锁住它的合同。SQL 排水把 SQL 收进 `data/repositories` 之后，接缝第一次清晰起来：仓储返回事实，服务做裁决，路由做投影。这条政策规定新测试往哪一层写。它是长期做法，不是一次性 feature。

## 决定

1. **仓储合同用真 SQLite 锁。** 每个新增或改动的仓储方法都要有一条直接调用它的测试：建最小表、灌几行、断言返回的事实（`None` / 列表 / `limit+1` 行 / 布尔 / `schema_issues`）。测试文件按簇命名 `tests/<area>/test_sql_drain_<簇>_repositories.py`，登记进门禁分组。
2. **服务裁决用仓储的事实边界测。** 错误码、HTTP 状态、文案在服务层策略模块里断言；要制造"仓储返回了某种事实"时优先打桩仓储方法，而不是伪造整张表。
3. **路由只测投影与错误映射。** 路由测试断言载荷形状与失败响应，不重复覆盖服务层已锁的裁决。
4. **端到端测试只留每个业务链一条。** 新功能允许一条从路由到 SQLite 的链路测试作为冒烟，其余用例落到上面三层；不再为每个分支各写一条端到端。
5. **改一处只改一层的测试。** 改 SQL → 改仓储合同测试；改裁决 → 改服务测试；改载荷 → 改路由测试。若一处改动迫使三层测试同时改，先怀疑接缝放错了位置。
6. **登记与门禁。** 新测试文件必须 `git add` 并登记到 `tools/test_registry_groups_*.py` 对应分组的 `target_paths`；合同类测试还要进 `tools/test_registry_data.py` 的 `QUALITY_GATE_GUARD_TESTS`。

## 理由

- 接缝测试失败时能直接指出是哪一层坏了；端到端测试失败只能告诉你"链路坏了"。
- SQLite 是真实依赖且极快，仓储合同没有理由用假库。
- 仓储只返回事实之后，服务层测试可以用极小的桩表达"仓储看到了什么"，不再需要搭整套 fixture。

## 考虑过的替代方案

- **继续以端到端为主**：改一条 SQL 要跑几十个测试才知道结果，且 2026-06 的测试冗余审计已指出结构重复才是主要冗余。
- **用 mock 替代 SQLite 测仓储**：mock 只能证明"调用了 execute"，证明不了 SQL 正确。

## 后果

- 已落地的例子：`tests/workbench/test_sql_drain_{run,plan_trial,master_report}_repositories.py`、`tests/schedule/service/test_sql_drain_scheduler_repositories.py`。
- 历史端到端测试不强制迁移；改到哪一层时顺手把该层的合同补上即可。

## 相关文档

- `.codestable/roadmap/foundation-boundary-governance/foundation-boundary-governance-roadmap.md` §C、§5 观察项
- `.codestable/compound/2026-09-20-decision-ratchet-gate-lifecycle.md`
- `.codestable/audits/2026-06-30-test-suite-redundancy/`
