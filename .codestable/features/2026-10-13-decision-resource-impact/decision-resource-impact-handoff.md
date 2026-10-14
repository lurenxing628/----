---
doc_type: feature-handoff
feature: decision-resource-impact
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第3阶段资源影响的实现、实际证据、文件范围与主对话复核入口
tags: [aps, workbench, resource, candidate-comparison]
---

# 第3阶段交接

**第3阶段实施和主对话独立验收通过。** 共同资源日历和计量、设备／人员表、逐日热力图、压力、冲突、两视角、甘特往返及旧消费者均已接入，日常检查、真实浏览器和原始导出核对通过。无新增返修项；第4阶段已派发，第5—8阶段等待。

工作目录 `/Users/lurenxing/GitHub/----`。本阶段继续第0—2阶段未提交实现；下面清单只列第3阶段实际路径。`开发文档/README.md` 原有并发改动保留。

## 1. 实际职责与合同

- 所有候选与基准使用同一工厂本地左闭右开窗口，默认受理起日00:00至截止日次日00:00；固定永久资源并集保留正容量空闲0。
- 本次选批贡献与完整候选压力分别表达。候选自己的安排、完整正式工序覆盖、普通未排和合法待料单列；正式覆盖与采用预检共享集合规则。
- 保存的全局日历、停机、个人日历、轮班、Schema和永久身份由共同工厂适配。已知休息／禁排／停机扣尽为0；缺事实为unknown。当前值班台适配自己的已读事务事实，来源明确。
- 班内占用为区间并集；独立工序先合并片段再累计需求；班外、重复负荷及实际重叠时长分别保存。日峰和高压力覆盖完整窗口，零容量有任务保留true／null／false。
- 汇总按容量加权，CV纳入正容量空闲资源。已知日子窗参与已知比率；CV使用完整整窗资源，均值为0时不适用。
- 总览42项指标保留24项共同资源指标和原算法统计各自来源。资源／日期分页只改变显示；单资源逐日只测量目标资源两侧。
- 资源、日格、工序及冲突定位实际侧甘特，资源过滤生效；正式完整视角读取归档全部安排。返回恢复原窗口、视角、类别、资源、筛选排序、资源／日格页和焦点。
- CSV与XLSX同服务同scope，数字原生、null空。资源覆盖与逐日冲突使用数量列；XLSX“覆盖工序”和“资源冲突”逐条保存完整永久身份，避免单格长度截断。

## 2. 第3阶段文件范围

### 共同事实、旧消费者与采用覆盖

```text
core/services/workbench/facts/archived_calendar.py
core/services/workbench/facts/current_resource_calendar.py
core/services/workbench/facts/resource_intervals.py
core/services/workbench/facts/resource_projection.py
core/services/workbench/facts/resource_summary.py
core/services/workbench/facts/resource_pressure.py
core/services/workbench/facts/official_scope_coverage.py
core/services/workbench/run/candidate_adoption_validation.py
core/services/workbench/run/candidate_metrics.py
core/services/workbench/run/candidate_comparison.py
core/services/workbench/run/candidates.py
core/services/workbench/trial/calendar.py
core/services/workbench/trial/capacity.py
core/services/workbench/trial/projection.py
core/services/workbench/trial/service.py
core/services/workbench/dashboard/analysis_projection.py
```

旧daily `occupied_hours`保留墙钟并集，`inside_available_hours`对应共同班内占用；旧`overlap_hours`保留实际并发时段。试调`arranged_hours`保留独立工序累计跨度，`occupied_hours`保留墙钟并集，`available_occupied_hours`为共同班内占用；`segments`复用共同扫线。新`window_metrics`为`available_occupancy_v1`，`resource_common`为`decision-resource-v3`；当前来源为`current_transaction_snapshot`，保存来源为`archived_resource_calendar`。

### 共同决策、Web与导出

```text
core/services/workbench/run/decision_resources.py
core/services/workbench/run/decision_resource_export.py
core/services/workbench/run/decision_source.py
core/services/workbench/run/decision.py
core/services/workbench/run/decision_metrics.py
core/services/workbench/run/decision_queries.py
core/services/workbench/run/decision_workspace.py
core/services/workbench/run/decision_impact.py
core/services/workbench/run/decision_export.py
web/routes/workbench/run_decision.py
web/routes/workbench/navigation_boot.py
```

`web/routes/workbench/read_context.py`沿用前阶段scope和身份绑定，本阶段未增加第二套快照机制。显式URL须保持顶层view与nav.view一致。

### 前端与本地资产

```text
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunDecisionDetails.jsx
frontend/workbench/app/RunDecisionResources.jsx
frontend/workbench/app/RunDecisionResourceHeatmap.jsx
frontend/workbench/app/RunCandidateControls.jsx
frontend/workbench/app/RunCandidateGantt.jsx
frontend/workbench/app/RunCandidateModel.js
frontend/workbench/app/RunCandidateWorkspace.jsx
frontend/workbench/app/ResourceProjectionContract.js
frontend/workbench/app/WorkbenchTerms.js
frontend/workbench/app/DashboardAnalysisAPI.js
frontend/workbench/app/DashboardCandidateComparisonAPI.js
frontend/workbench/app/DashboardPanels.jsx
frontend/workbench/app/DashboardCandidatePanels.jsx
frontend/workbench/app/TrialContract.js
frontend/workbench/app/TrialResults.jsx
frontend/workbench/app/styles/34-run.css
scripts/workbench/build-order.json
static/workbench/app/main.js
static/workbench/app/workbench.css
```

构建10文件，target=chrome109，所有资源本地随包交付。`SchedulingWorkspace.jsx`与正式详情fixture属于第2阶段，本阶段保留原实现。

### 回归、验证工具与文档

```text
tests/workbench/test_archived_calendar.py
tests/workbench/test_resource_projection.py
tests/workbench/test_resource_summary.py
tests/workbench/test_official_scope_coverage.py
tests/workbench/test_legacy_resource_projection.py
tests/workbench/test_run_decision_resource_api.py
tests/workbench/test_run_decision_api.py
tests/workbench/test_run_decision_metrics.py
tests/workbench/test_run_decision_impact_api.py
tests/workbench/decision_comparison_contract.cjs
tests/workbench/decision_resource_contract.cjs
tests/workbench/dashboard_list_probe.cjs
tests/workbench/notice_ownership_contract.cjs
tests/workbench-terms-and-ids.cjs
tests/workbench/test_ui_refinement_node_contracts.py
tests/gantt/test_gantt_adapter_contract.py
tools/test_registry_data.py
scripts/verify_decision_workbench.py
static/docs/scheduler_manual.md
开发文档/系统速查表.md
.codestable/architecture/service-scheduler.md
.codestable/architecture/workbench-shell.md
.codestable/requirements/candidate-comparison-business-view.md
.codestable/features/2026-10-13-decision-resource-impact/
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-items.yaml
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-roadmap.md
```

第2阶段feature只同步主对话通过及接续状态，原始验证保留。母任务`stage-acceptance.md`与`evidence/decision-stage-acceptance/`由主对话维护。

## 3. 实例、场景与复核材料

固定数据库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`，身份文件 `/private/tmp/aps-decision-workbench-20261013/instance.json`。本阶段只生成一个资源运行：`c93b6734772b1478796c48b48ce6eaf1a304497934ed678a`。4个实际候选各11道安排、11台机器、2名人员；原6个运行／30候选、旧资源与日期、defaults、正式v1和15行正式安排逐行保留。生成配置恢复。

当前共41批、73工序、7运行、34候选、493候选安排、11机器、7人员。最终服务为 `http://127.0.0.1:56030`、PID56365，同库正式v1／15行保持。三次实际资源甘特往返、浅深主题与1920／1392布局、100／125／150%原生缩放、热图键盘、缺基准及零容量呈现通过。最终导出5个受影响案例、7文件、894业务行、16,239核对格、7,105数字格通过。本阶段只生成上述一个资源运行；已有运行和采用结果复用。

证据根目录 [evidence/decision-resource-impact/](../../../evidence/decision-resource-impact/)；真实实例子目录 [aps-decision-workbench-20261013/](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/)。

- [唯一实际生成与保全清单](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-fixture.json)
- [实际资源与独立区间核对](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-verification.json)
- [8组真实HTTP与已构建React核对](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-ui-render.json)
- [真实15条缺失正式安排标签](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-coverage-label-render.json)
- [零容量三项比率的实际呈现](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-zero-capacity-label-render.json)
- [最终浏览器往返、主题、缩放与键盘](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/browser/verification.json)、[最终1392浅色](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/browser/resources-latest-light-1392.png)、[最终1392深色横滚](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/browser/resources-latest-dark-1392-scrolled.png)
- [最终导出回读](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/exports/coverage-cell-repair-01/export-verification.json)、[当前实例](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/runtime-current.json)、[同库资源数学复用证明](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/final-runtime-reuse.json)
- [最终日常检查](../../../evidence/decision-resource-impact/quality/daily-final.log)、[四条交付链接核对](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/link-verification.json)、[完整证据索引](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/evidence-index.json)
- [20k任务核心性能脚本](../../../evidence/decision-resource-impact/performance/measure_resource_core.py)、[产品Python3.8边界结果](../../../evidence/decision-resource-impact/performance/resource_core_20k_4_6_8.json)、[宿主Python3.14优化前](../../../evidence/decision-resource-impact/performance/resource_core_20k_4_6_8_before_window_optimization.json)、[宿主Python3.14优化后](../../../evidence/decision-resource-impact/performance/resource_core_20k_4_6_8_host_python314.json)
- [Excel单格静默截断的实际复现](../../../evidence/decision-resource-impact/performance/xlsx-coverage-cell-boundary-before.json)

## 4. 验证状态与边界

7项共同日历、14项资源内核、8项旧消费者新增真实SQLite、原旧路径回归和6项资源API均已通过；2个决策Node合同、2项甘特合同及Chrome109构建通过。最终日常 **437 passed／20 skipped，67.38s，122必跑目标，Ruff全通过**。首轮Ruff脚本文字格式和旧notice fixture失败已修正并保留before日志；38个notice检查与对应pytest通过。最后UI/CSS增量由相关Node、构建与真实浏览器复验，计算和导出保持冻结。

20k任务／对象、4／6／8候选加1基准、402资源×100日=40,200资源日／对象，全部跨块汇总通过。最终产品Python3.8.10／macOS测量：索引加整窗汇总1.745／2.451／3.179秒，含生成输入1.922／2.703／3.500秒，8候选进程累计峰值333,725,696B。原宿主Python3.14的优化前后结果另存，不与产品运行时耗时混用。

实际典型4／6／8候选HTTP于55291/PID48832各测一次，总览17.6／24.8／27.7ms、单资源逐日13.8／16.7／17.6ms、CSV20.4／22.1／24.5ms、XLSX60.7／43.0／33.2ms，服务采样峰值105,856KiB。[性能记录](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/performance/performance.json)保留当时端口、请求与分段采样；最终56030导出已单独原始回读。Win7实机达标留最终整体验收。

源码、资产和材料尚未提交、推送或发布；当前工作区包含前阶段和并发改动，实施检查覆盖本阶段及适用日常目标。最终HEAD及clean-worktree证明沿整体收口执行。主对话独立阶段验收已通过，无新增返修；第4阶段已派发，第5—8阶段保持planned。完整9节核对及独立回执见 [实施验收](decision-resource-impact-acceptance.md)。

## 5. 当前直接复核入口

顶层`view=analysis`与`nav.view=analysis`匹配；均按永久运行／候选和资源视角进入当前实例。

- [11台设备与共同容量](http://127.0.0.1:56030/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22c93b6734772b1478796c48b48ce6eaf1a304497934ed678a%22%2C%22candidate_ref%22%3A%225e67e328c3e05d9a2ce18d348b0c90ec1f86c84d610291e6%22%2C%22comparison_tab%22%3A%22resources%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22reference_candidate_ref%22%3A%22432624ce37d1c494139bbb2bf97d8d7d34e3402a47fdae91%22%2C%22resource_view%22%3A%22selected_batches%22%2C%22resource_kind%22%3A%22machine%22%7D%7D)
- [人员完整候选与正式基准](http://127.0.0.1:56030/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22c93b6734772b1478796c48b48ce6eaf1a304497934ed678a%22%2C%22candidate_ref%22%3A%225e67e328c3e05d9a2ce18d348b0c90ec1f86c84d610291e6%22%2C%22comparison_tab%22%3A%22resources%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22resource_view%22%3A%22full_candidate%22%2C%22resource_kind%22%3A%22operator%22%7D%7D)
- [旧6候选正式归档资源对照](http://127.0.0.1:56030/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22579e93d3ca41c34b4ed1eae76d520093f88ce523928b3473%22%2C%22candidate_ref%22%3A%225ca8eb405054988e9ba5c4ea83905e57716c1781b9fd6d84%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22comparison_tab%22%3A%22resources%22%2C%22resource_view%22%3A%22full_candidate%22%2C%22resource_kind%22%3A%22machine%22%7D%7D)
- [旧4候选正式基准缺失](http://127.0.0.1:56030/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22e4f3ff6fa4234ce6cc85473517303b81ff4405ce59509246%22%2C%22candidate_ref%22%3A%22a4183073694ddf7705e6baf6114d3b7e5aa27aa713d37cdb%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22comparison_tab%22%3A%22resources%22%2C%22resource_view%22%3A%22selected_batches%22%2C%22resource_kind%22%3A%22machine%22%7D%7D)
