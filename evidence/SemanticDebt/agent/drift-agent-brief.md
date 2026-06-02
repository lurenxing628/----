# Semantic Drift Agent Brief — b08162cd 现状基线

> drift-analyzer 2.51.1 · 669 文件 / 5918 函数 · grade C · 1606 findings
> AI 归因比 5.3%，检出 AI 工具: ['agents', 'claude']

## 项目硬边界(Agent 判断时不可违背)
- Win7 x64 / Python 3.8 / 离线交付 / 不污染运行时依赖
- 用户可见位置禁露 plan_role/scenario_id/source_table/candidate_id(ARCHITECTURE.md:65)
- 灵魂线：坏数据不准静默兜底，宁可暴露错误也不自欺
- 已知收口点(判 P5 用)：core/models/schedule_plan_role.py、normalize_schedule_resource_filter、build_workbench_plan_context、core/shared/strict_parse

## ⚠️ 工具口径校准(读 drift 结果前必看)
- **drift 的 AVS『Architecture Violation』≠ 本项目审计的『分层违规』**。drift 的 AVS 实为 *Unstable dependency*(Martin 不稳定度耦合指标)，全是 `A.py -> B.py 不稳定依赖`，**不是**有向越层。本项目 AST 全量分层违规仍是 **0**。154 条 AVS 不要当成 154 处越层。
- **drift 的 MDS『Exact duplicates』里有真护栏**。例：`normalization_matrix._merge_aliases` ↔ `boolean_normalize`(下方 A∩B 第 1 条)正是审计 §90 **LB-B1 承重双实现**——drift 叫你『删重复』，但删它会撞分层红线。**这正是为什么 drift 结果必须过 Agent 语义法医，不能直接修。**

## findings 分布
| 维度 | 计数 |
|---|---|
| severity=medium | 700 |
| severity=high | 448 |
| severity=low | 258 |
| severity=critical | 175 |
| severity=info | 25 |

信号 top: PHR=397, EDS=291, DCA=221, MAZ=175, AVS=154, CXS=119, PFS=63, TVS=59, MDS=28, COD=24, NBV=22, SMS=15

## A∩B 交叉核验(drift 是否独立命中审计的承重文件)
> drift 命中 = 第二信源。命中≠该删；多数承重点 drift 只看到表层 smell(PHR/DCA/EDS)，护栏意图它读不出来——还得靠 concept-registry + Agent。

| 审计承重文件 | drift 命中信号 | 备注 |
|---|---|---|
| `core/services/report/execution_review.py` | {'PHR': 1, 'DCA': 1, 'TVS': 1} | 只看到 PHR/DCA/TVS 表层，**读不出 only-adopted 护栏意图** |
| `web/navigation_context.py` | {'PHR': 1} | 只 1 条 PHR，**护栏靠字面量匹配它测不出**(印证 N3 最脆弱) |
| `core/services/scheduler/operation_execution_feedback_service.py` | {'PHR': 1, 'AVS': 1, 'DCA': 1} |  |
| `core/shared/boolean_normalize.py` | {'EDS': 1} |  |
| `core/services/common/normalization_matrix.py` | {'MDS': 1, 'AVS': 2, 'EDS': 2} | **MDS 命中 = 强互证 LB-B1**；但『删重复』是引爆动作 |
| `core/services/scheduler/schedule_plan_identity_builder.py` | {'EDS': 1} |  |
| `web/viewmodels/scheduler_reports_workbench.py` | {'PHR': 1, 'DCA': 1} |  |
| `web/viewmodels/scheduler_workbench_links.py` | {'EDS': 3, 'AVS': 1, 'PHR': 1, 'DCA': 1} |  |
| `core/services/scheduler/gantt_service_support.py` | {'PHR': 1} |  |

## 待 Agent 分类的高价值 findings(MDS/PFS 真近似重复，按分降序 top 15)
> 每条 Agent 须判：consistent / pure_refactor_debt / naming_debt / stale_doc / semantic_drift / insufficient_evidence

- [PFS/high] `core/infrastructure:1`  — error_handling: 22 variants in core/infrastructure/
  - related: core/infrastructure/backup.py, core/infrastructure/backup.py, core/infrastructure/backup.py
- [PFS/high] `core/services/process:1`  — return_pattern: 7 variants in core/services/process/
  - related: core/services/process/deletion_validator.py, core/services/process/deletion_validator.py, core/services/process/deletion_validator.py
- [PFS/high] `core/services/scheduler:1`  — return_pattern: 12 variants in core/services/scheduler/
  - related: core/services/scheduler/_sched_display_utils.py, core/services/scheduler/batch_service.py, core/services/scheduler/execution_fact_provider.py
- [PFS/high] `core/services/scheduler:1`  — error_handling: 12 variants in core/services/scheduler/
  - related: core/services/scheduler/_sched_display_utils.py, core/services/scheduler/execution_fact_provider.py, core/services/scheduler/execution_fact_provider.py
- [PFS/high] `core/services/scheduler/run:1`  — return_pattern: 11 variants in core/services/scheduler/run/
  - related: core/services/scheduler/run/auto_assign_resource_errors.py, core/services/scheduler/run/freeze_window.py, core/services/scheduler/run/freeze_window.py
- [PFS/high] `data/repositories:1`  — return_pattern: 8 variants in data/repositories/
  - related: data/repositories/base_repo.py, data/repositories/batch_repo.py, data/repositories/operation_execution_event_repo.py
- [PFS/high] `tools:1`  — return_pattern: 10 variants in tools/
  - related: tools/architecture_scan_cache.py, tools/git_hook_cache.py, tools/long_gate_cache.py
- [PFS/high] `tools:1`  — error_handling: 22 variants in tools/
  - related: tools/architecture_scan_cache.py, tools/long_gate_fingerprint.py, tools/long_gate_full_test_debt.py
- [PFS/high] `web/routes:1`  — return_pattern: 7 variants in web/routes/
  - related: web/routes/dashboard.py, web/routes/equipment_excel_machines.py, web/routes/equipment_excel_machines.py
- [PFS/high] `web/routes:1`  — api_endpoint: 36 variants in web/routes/
  - related: web/routes/dashboard.py, web/routes/equipment_downtimes.py, web/routes/equipment_pages.py
- [PFS/high] `web/routes/domains/scheduler:1`  — return_pattern: 8 variants in web/routes/domains/scheduler/
  - related: web/routes/domains/scheduler/scheduler_analysis_read.py, web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py, web/routes/domains/scheduler/scheduler_batches.py
- [PFS/high] `web/routes/domains/scheduler:1`  — api_endpoint: 21 variants in web/routes/domains/scheduler/
  - related: web/routes/domains/scheduler/scheduler_batches.py, web/routes/domains/scheduler/scheduler_batches.py, web/routes/domains/scheduler/scheduler_batches.py
- [PFS/high] `web/viewmodels:1`  — return_pattern: 10 variants in web/viewmodels/
  - related: web/viewmodels/dashboard_workbench.py, web/viewmodels/scheduler_analysis_diagnostic_helpers.py, web/viewmodels/scheduler_analysis_diagnostic_helpers.py
- [PFS/high] `web:1`  — error_handling: 9 variants in web/
  - related: web/error_boundary.py, web/error_boundary.py, web/error_boundary.py
- [PFS/high] `core/algorithms/greedy:1`  — return_pattern: 8 variants in core/algorithms/greedy/
  - related: core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/auto_assign.py
