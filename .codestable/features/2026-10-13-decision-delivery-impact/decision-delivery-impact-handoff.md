---
doc_type: feature-handoff
feature: decision-delivery-impact
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第 2 阶段完整实现交付与工序影响，保留隔离实例供主对话独立复核
tags: [aps, workbench, delivery, candidate-comparison]
---

# 第 2 阶段交接

**本阶段完整实现与实施验收通过。** 共同交付、正式归档对照、逐批/工序明细、筛选分页、甘特定位返回与导出均已完成。主对话独立验收已通过，两项P3关闭；第3阶段已派发，第4—8阶段保持planned。

工作目录：`/Users/lurenxing/GitHub/----`。下列项目路径相对此目录。本阶段在第 0/1 阶段未提交实现上继续；`开发文档/README.md` 的原有并发改动保持原样。

## 1. 实际交付

- 统一交期、全链完成性、三轴覆盖与成对交付差值，迁移候选、正式计划、值班台、试调及对应导出和前端枚举。
- `candidates / admission_official` 共同比较模式。正式基准取受理前每道工序最后正式安排，只读取归档绑定的不可变来源，保留多段、待料、零工时和原资源身份；当前资料修改保持历史结果。显式历史版本入口保留原版本范围。
- 批次交付与工序变化页签、全范围批次/资源目录、变化类型筛选、稳定排序和 20/50 分页；全范围汇总与行筛选分开表达。
- 双方批次/工序甘特定位，正式基准只读；返回恢复模式、候选、基准、原时间窗、页签、指标视图和列表条件/页码/快照。
- CSV/XLSX 单明细和完整五表比较，导出全部筛选结果；普通文本原样、null 空格、XLSX 数字保持数值类型。当前页签筛选与其他分区共同范围明确表达。
- 工序需求展示保存工艺的标准工时；执行保护与方案保存锁定标记分别表达。共同资源班表和实际准备需求分解沿后续第 3/4 阶段建设。

## 2. 第 2 阶段实际文件范围

下列文件经分工交接核对，包含第 2 阶段实际改动；同名第 1 阶段新文件本阶段继续修改。第 0/1 阶段独有的 `schedule_candidate_selection.py`、`candidate_facts.py`、`decision_selection.py`、`workbench_run_result_repo.py`、`run_candidates.py` 和 `test_ui_refinement_node_contracts.py` 沿前阶段清单保留。

### 共同交付与旧读取入口

```text
core/models/enums.py
core/models/workbench_run_analysis.py
core/services/workbench/plan/delivery_projection.py
core/services/workbench/plan/delivery_completeness.py
core/services/workbench/plan/delivery.py
core/services/workbench/plan/delivery_repository.py
core/services/workbench/plan/workspace_dto.py
core/services/workbench/plan/official_persistence.py
core/services/workbench/run/candidate_delivery.py
core/services/workbench/run/candidate_comparison.py
core/services/workbench/run/candidate_analysis.py
core/services/workbench/run/candidate_baseline.py
core/services/workbench/dashboard/projection.py
core/services/workbench/dashboard/service.py
core/services/workbench/dashboard/analysis_projection.py
core/services/workbench/trial/base.py
core/services/workbench/trial/projection.py
core/services/workbench/trial/service.py
data/repositories/workbench_plan_delivery_repo.py
```

### 归档、共同决策与 Web

```text
core/services/workbench/facts/decision_baseline.py
core/services/workbench/facts/decision_baseline_source.py
core/services/workbench/run/decision.py
core/services/workbench/run/decision_source.py
core/services/workbench/run/decision_delivery.py
core/services/workbench/run/decision_metrics.py
core/services/workbench/run/decision_reference.py
core/services/workbench/run/decision_impact.py
core/services/workbench/run/decision_queries.py
core/services/workbench/run/decision_workspace.py
core/services/workbench/run/decision_export.py
web/routes/workbench/run_decision.py
web/routes/workbench/navigation_boot.py
web/routes/workbench/read_context.py
```

### 前端与编译产物

```text
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunDecisionDetails.jsx
frontend/workbench/app/RunCandidateControls.jsx
frontend/workbench/app/RunCandidateWorkspace.jsx
frontend/workbench/app/RunCandidateModel.js
frontend/workbench/app/RunCandidateGantt.jsx
frontend/workbench/app/SchedulingWorkspace.jsx
frontend/workbench/app/RunCandidateAPI.js
frontend/workbench/app/RunCandidateAnalysisAPI.js
frontend/workbench/app/RunCandidateAnalysis.jsx
frontend/workbench/app/PlanContract.js
frontend/workbench/app/PlanDetailsUI.jsx
frontend/workbench/app/DashboardContract.js
frontend/workbench/app/DashboardCandidateComparisonAPI.js
frontend/workbench/app/DashboardCandidatePanels.jsx
frontend/workbench/app/DashboardPanels.jsx
frontend/workbench/app/DashboardEvidence.jsx
frontend/workbench/app/DashboardAnalysisPanels.jsx
frontend/workbench/app/TrialContract.js
frontend/workbench/app/TrialControls.jsx
frontend/workbench/app/TrialResults.jsx
frontend/workbench/app/TrialExport.js
frontend/workbench/app/WorkbenchTerms.js
frontend/workbench/app/styles/34-run.css
scripts/workbench/build-order.json
static/workbench/app/main.js
static/workbench/app/workbench.css
```

构建同步写 `static/workbench/asset-manifest.json`，当前字段保持已有清单。产品资源均本地随包交付，target=chrome109。

### 回归、验证工具与文档

```text
tests/workbench/test_delivery_projection.py
tests/workbench/test_delivery_trial_projection.py
tests/workbench/test_candidate_comparison_baseline.py
tests/workbench/test_decision_baseline.py
tests/workbench/test_run_decision_impact_api.py
tests/workbench/test_run_decision_metrics.py
tests/workbench/test_run_decision_api.py
tests/workbench/test_run_candidate_api.py
tests/workbench/decision_comparison_contract.cjs
tests/gantt/test_gantt_adapter_contract.py
tests/gantt/fixtures/admission_official_detail.json
tests/workbench-terms-and-ids.cjs
tests/workbench/analysis_ui_contract.cjs
tests/workbench/plan_transport_probe.cjs
tests/workbench/notice_ownership_contract.cjs
tools/test_registry_data.py
scripts/verify_decision_workbench.py
static/docs/scheduler_manual.md
开发文档/系统速查表.md
.codestable/architecture/service-scheduler.md
.codestable/architecture/workbench-shell.md
.codestable/requirements/candidate-comparison-business-view.md
.codestable/features/2026-10-13-decision-delivery-impact/
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-items.yaml
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-roadmap.md
```

第 1 阶段 feature 仅补主对话独立通过回执和接续状态，保留原验证与实例记录。母任务 `stage-acceptance.md`、独立审查报告和 `evidence/decision-stage-acceptance/` 由主对话维护。

## 3. 已执行验证

- 最终 `.venv/bin/python scripts/run_daily_quality_gate.py`：Ruff 全通过，116 个必跑目标，**400 passed / 20 skipped，62.68s**。正式详情返修前的历史结果为 399 passed / 20 skipped，62.34s；新增实际响应渲染回归随修复后的日常门禁通过。
- `node tests/workbench/decision_comparison_contract.cjs`：最终通过；shared UI Node 14 项、相关甘特 5 项既有有效验证复用，另补一项实际正式 Detail 渲染回归通过。`python3 scripts/workbench/build.py`：最终 10 files、target=chrome109，通过。
- 正式来源、共同交付/试调、不同完成集合、部分新版、范围受限、未知时间/点证据、恢复资源、分页筛选、导出类型和导航身份都有相关回归；日常门禁覆盖登记的新增 Python 文件。
- 12 份真实 HTTP DTO、142 条明细的实际前端组件验证通过。旧入口另核对真实无正式基准/部分 v2、明确/未指定/非法交期、正式整批待料和旧试调保存响应；错误基准身份正确拒绝，通知契约 38 项通过。
- `.venv/bin/python tests/gate_meta/check_quickref_vs_routes.py`：OK；初次交付 feature 4 份及路线图 2 份 YAML/frontmatter 全通过，`git diff --check` 退出0。交接清单86个路径条目均存在，本地证据链接均有效。
- 真实场景使用 `scripts/verify_decision_workbench.py delivery-fixtures --instance /private/tmp/aps-decision-workbench-20261013/instance.json`，按 `--scenario ordinary_partial legal_stage` 和确认后的 `--scenario mixed_due` 分步生成；`delivery-verify --instance ...` 实际退出0。原始导出由同脚本 `delivery-export-verify` 逐字段核对；浏览器走现有 Playwright CLI `aps-decision-repair` 会话。最终查询/导出/正式回跳复用既有运行。

## 4. 当前实例与场景

当前服务 **http://127.0.0.1:60154**，PID **37323**。实例身份文件 `/private/tmp/aps-decision-workbench-20261013/instance.json`，数据库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`。`runtime-current.json` 保存当前端口/PID/数据库及运行记录。

| 场景 | run_ref | 所选 candidate_ref | 候选 reference_ref |
| --- | --- | --- | --- |
| 混合交期、21 批/42 工序 | e8e31a32e1062ad45f1c7bbd70c2edee894e59cee96e4530 | 663f80877d6780b8f20b06968b0075e649258abd4eb6f9e8 | b5d6dedeac38efde8294bd6ed060bf90e9dec10b13ae60dc |
| 普通部分、2 批/3 工序 | 8178403fae7fab31de6c7199067c244ebf31453e8f888bc9 | dc7f93962daf94673c1d00841329bd2e81edee577ff6d7d6 | c8498743844a26286e97fa6bbc6472304465de3732c98267 |
| 合法待料、1 批/2 工序 | 4ba269dd2f90b7559237633a6f95c181bdb4e961b8fc3915 | 45e2a434083523571ee3d0dd1a316939c892e023a5c4ca5c | 2e40b7f47064097d719e213ecc3e2d738f20703cce659304 |

新增真实输入合计 24 批/47 工序；混合交期为 18 个指定、1 个未指定、2 个 null。非法非空日期的现有预检会拒绝，证据单列，历史非法值由投影测试核对。当前共有 30 批/62 工序、6 个运行/30 候选；旧 4/6/8 候选运行与第 1 版正式采用保存，正式 Schedule 仍 15 行、History 仍 1 版。本阶段没有再次采用方案，生成参数恢复原配置。

原 4 候选运行：`e4f3ff6fa4234ce6cc85473517303b81ff4405ce59509246`；6 候选：`579e93d3ca41c34b4ed1eae76d520093f88ce523928b3473`；8 候选：`aa2e2610e4b1fb8e0a04b131c4c153f1c101036e7f1c9e6e`。正式 1 版 plan_ref：`0d7a9dad1ccd4513a883c1f2173b7de53affc7fad74bf901`。

## 5. 原始证据与复核

证据目录为 [evidence/decision-delivery-impact/aps-decision-workbench-20261013/](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/)。

- [真实场景清单](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/delivery-fixtures.json) 与 [早期生成/查询结果](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/delivery-verification.json) 记录生成时 58521/PID28424；这些历史记录原样保留。
- [当前实例](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/runtime-current.json) 与 [最终导航拒绝核对](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/final-navigation-probe.json) 绑定 60154/PID37323。
- [最终只读查询](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/final-query-verification.json) 在当前实例逐字段核对三个真实场景，结果与已验证归档相同；复用原运行和采用。
- 三个场景子目录内有真实运行、候选、总览、批次/工序整表与分页、资源筛选和双方工作区原始 JSON；`mixed_due/verification/current-fields-archive-check.json` 为当前资料修改后的归档回看。
- [最终浏览器核对](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/browser-verification.json) 汇总五次真实往返与四个有效主题尺寸截图。所选/候选基准的批次与工序往返均保持9项上下文；正式往返另核对原15行列表、时间窗、正确工序/v1身份、自动扩窗、只读能力和无采用按钮。正式详情12项执行字段正确显示，最终console 0 errors / 0 warnings。
- 有效桌面截图：[1392浅色批次](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/mixed-batches-light-1392x924.png)、[1392深色批次](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/mixed-batches-dark-1392x924.png)、[1920浅色工序](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/mixed-operations-light-1920x1080.png)、[1920深色工序](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/mixed-operations-dark-1920x1080.png)。主字13px/小字12px，表格沿现有区域滚动。
- [正式定位与完整返回上下文](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/formal-reference-return-context.json) 保存最后一次实际复验；其他四次往返、布局和导出证明复用。浏览器通道为 Playwright CLI / Chromium Headless 154；离线编译 target 仍为 Chrome109。
- [最终导出核对](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/export-verification.json) 绑定当前实例：11 个场景、18 份 raw CSV/XLSX、743 业务行；批次 38 列/工序 49 列共 14568 格逐值相同，3320 个数字格，身份顺序和同筛选全页一致。完整五表核对当前页签筛选与其他分区范围，并覆盖正式模式。root 标准读取原始 21 行批次文件确认“交付影响验收零件”原文、空字段和原生数字。
- 原始文件可直接复核：[批次 CSV](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/mixed-batches/decision-batches.csv)、[批次 XLSX](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/mixed-batches/decision-batches.xlsx)、[工序 CSV](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/mixed-operations/decision-operations.csv)、[工序 XLSX](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/mixed-operations/decision-operations.xlsx)、[正式完整五表](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/exports/all-formal-filter/decision-all.xlsx)。
- 正式详情的实际布尔格式异常已在共同 `RunCandidateModel` 路径修正：完整性、时间与完成依据按字段语义显示，null 使用具体原因或保存时缺项文案。实际 12 字段完整响应作为单一 fixture 保存在 `tests/gantt/fixtures/admission_official_detail.json`，实际 Detail 渲染回归通过；失败响应、console 与截图仍保留在 browser 目录。
- [修复后正式甘特详情](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/browser/formal-reference-detail-success-dark-1920x1080.png) 已实际目视，v1只读标记、目标工序和12字段同屏清楚可见。该图补入最终浏览器汇总，修复前失败图仅作历史记录。

### 当前直接复核入口

链接同时使用顶层 `view=analysis` 与 `nav.view=analysis`，按现有导航合同进入对应页面。

- [混合交期批次明细](http://127.0.0.1:60154/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22e8e31a32e1062ad45f1c7bbd70c2edee894e59cee96e4530%22%2C%22candidate_ref%22%3A%22663f80877d6780b8f20b06968b0075e649258abd4eb6f9e8%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22reference_candidate_ref%22%3A%22b5d6dedeac38efde8294bd6ed060bf90e9dec10b13ae60dc%22%2C%22comparison_tab%22%3A%22batches%22%7D%7D)
- [普通漏排批次明细](http://127.0.0.1:60154/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%228178403fae7fab31de6c7199067c244ebf31453e8f888bc9%22%2C%22candidate_ref%22%3A%22dc7f93962daf94673c1d00841329bd2e81edee577ff6d7d6%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22reference_candidate_ref%22%3A%22c8498743844a26286e97fa6bbc6472304465de3732c98267%22%2C%22comparison_tab%22%3A%22batches%22%7D%7D)
- [合法待料工序明细](http://127.0.0.1:60154/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%224ba269dd2f90b7559237633a6f95c181bdb4e961b8fc3915%22%2C%22candidate_ref%22%3A%2245e2a434083523571ee3d0dd1a316939c892e023a5c4ca5c%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22reference_candidate_ref%22%3A%222e40b7f47064097d719e213ecc3e2d738f20703cce659304%22%2C%22comparison_tab%22%3A%22operations%22%7D%7D)
- [受理时正式计划工序对照](http://127.0.0.1:60154/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22579e93d3ca41c34b4ed1eae76d520093f88ce523928b3473%22%2C%22candidate_ref%22%3A%225ca8eb405054988e9ba5c4ea83905e57716c1781b9fd6d84%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22comparison_tab%22%3A%22operations%22%7D%7D)

## 6. 状态与接续

第2阶段status=done、implementation_acceptance=passed、parent_acceptance=passed；第3阶段已派发，第4—8阶段保持planned，按主对话逐阶段复核和派发。源码、静态产物和材料未提交、推送或发布。后续主对话可以复用当前隔离实例读取与复核。

## 7. 主对话复核修正

- 预览链接：本节4个直接复核入口原来只包含 `nav.view=analysis`；已全部补齐顶层 `view=analysis`。同批 feature/roadmap/原始证据、说明和验证脚本的同类URL已核对。实际从本文件打开混合交期链接，身份、比较模式和批次页签准确，第一页20行/共21批与API一致，无定位错误。证据见 [链接核对](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/link-repair-01/link-verification.json) 与 [实际打开截图](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/link-repair-01/current-handoff-mixed-batches-dark-1920x1080.png)。
- 正式主时间行标签：主对话发现归档页主行仍显示“新安排”；共同 `laneLabel(row, reference)` 已消费明确 `data.reference`，正式主行显示“正式归档”，可见标签、行title与canvas可访问名称一致；普通候选及原重叠/零工时语义保留。现有实际响应组件核对两种身份1 passed，Chrome109构建10 files通过。真实DC-04/工序1、正式v1定位与只读身份正确，两条主行及可访问名称均显示正式归档；证据见 [标签核对](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/link-repair-01/formal-row-label-verification.json) 与 [当前正式页截图](../../../evidence/decision-delivery-impact/aps-decision-workbench-20261013/link-repair-01/formal-row-label-success-dark-1920x1080.png)。
- 本轮复用主体实现的400项日常门禁和导出/归档证明，增量验证对应预览链接与正式标签；主对话独立阶段结论仍待执行。

## 主对话独立验收回执

2026-10-13 主对话确认第2阶段正式通过，两项P3关闭。直接从当前handoff抽取4条URL并实际打开正式对照，15行正常加载，DC-04定位、两条主行可见文案/title/canvas可访问名称均为“正式归档”，无alert；其余交付/归档/API/导出/分页往返证据沿首轮主审复用。独立证据在 `evidence/decision-stage-acceptance/stage-02/repair-01/` 的 `formal-lane-verification.json` 和 `formal-lane-label-1920.jpg`。母stage-acceptance由主对话维护；第3阶段已派发，第4—8阶段等待。本文件前文保留各次交付当时状态。
