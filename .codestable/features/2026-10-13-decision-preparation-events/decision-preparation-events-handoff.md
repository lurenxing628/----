---
doc_type: feature-handoff
feature: decision-preparation-events
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第4阶段需求账及切换的实际职责、文件范围、隔离实例和复核入口
tags: [aps, workbench, operation-effort, changeovers]
---

# 第4阶段交接

**第4阶段实施和主对话独立验收通过。** 共同需求、准备／加工明细、实际工种事件、旧同义消费者、原始导出及真实浏览器核对均完成；日常461 passed／20 skipped及其后布局增量验证通过。主对话未新增返修项，已派发第5阶段，第6—8阶段等待。

主对话独立证据位于`evidence/decision-stage-acceptance/stage-04/`，结论记录在母任务维护的[阶段验收](../../roadmap/scheduling-decision-workbench/stage-acceptance.md#第-4-阶段主对话独立验收)。独立复算31道账／310字段、4候选准备14.5h／加工45.55h、3次实际工种切换、712数值格／32空值格及正式来源和实际往返均通过。

工作目录`/Users/lurenxing/GitHub/----`，继续第0—3阶段累计未提交源码；本清单按第4阶段职责列出路径，README原有并发新增保留。设计、执行和验收分别见本目录另外三份文件。

## 1. 实际职责与合同

- 共同公式同时供实际排槽与运行账：准备＋加工＝实际标准需求。分件自身量1，共同工序按批量只计一次；外协周期／合并组单列。
- 完成事务一次保存永久工序需求账，候选按真实安排判归属。原需求目标及标准小时、本次AJ执行目标／余量分别表达；正式before来自每道最后采用的原需求，同时展示本次AJ数量。
- 保留、执行、完成和未构造按保存事实表达；旧runtime及原正式标准缺项保持缺项。AJ `complete`与旧实际完工`completed`分别读取。
- 工种计数、事件与原生插入惩罚共用真实ID规则；完整设备序列建立前驱后按next_start裁窗，点事件／首道／同ID为0。显式未知ID作为屏障，legacy缺字段沿自己的原输入读取。
- 两新页签、工序与甘特详情、稳定筛选分页、两侧定位返回及双格式消费同一账；目录52项／v4，原算法保存统计独立。资源内部投影继续`available_occupancy_v1`。
- 准备为整次受理，事件为共同左闭右开窗。XLSX完整9表／逐日11表，准备86列、事件33列、工序109唯一列。scope、永久身份、数值和缺项与页面一致。

## 2. 第4阶段文件范围

### 共同调度源头、类型身份和评价

```text
core/algorithm_contracts/operation_effort.py
core/algorithm_contracts/changeover_events.py
core/algorithm_contracts/types.py
core/algorithm_runtime/operation_effort.py
core/algorithm_runtime/internal_slot.py
core/algorithm_runtime/resource_quality.py
core/algorithm_runtime/runtime_state.py
core/algorithm_runtime/run_state.py
core/algorithms/evaluation.py
core/algorithms/greedy/internal_operation.py
core/algorithms/greedy/dispatch/sgs_reuse.py
core/models/enums.py
core/services/scheduler/run/operation_effort.py
core/services/scheduler/run/schedule_input_collector.py
core/services/scheduler/run/schedule_execution_guardrails.py
core/services/scheduler/run/freeze_window_seed_rows.py
core/services/scheduler/run/schedule_seed_contracts.py
```

`ScheduleResult.op_type_id`追加在末尾保持位置参数；原生评分依赖加入真实ID，公开名称提示字典保留自己的原语义。排槽数值和错误边界沿共同公式保持。

### 保存、决策与旧同义读取

```text
core/services/workbench/facts/operation_effort_evidence.py
core/services/workbench/facts/preparation_projection.py
core/services/workbench/facts/changeovers.py
core/services/workbench/facts/candidate_effort.py
core/services/workbench/facts/candidate_facts.py
core/services/workbench/facts/candidate_tasks.py
core/services/workbench/facts/decision_baseline.py
core/services/workbench/facts/decision_baseline_source.py
core/services/workbench/run/input_effort.py
core/services/workbench/run/input.py
core/services/workbench/run/candidates.py
core/services/workbench/run/candidate_metrics.py
core/services/workbench/run/candidate_comparison.py
core/services/workbench/run/decision.py
core/services/workbench/run/decision_source.py
core/services/workbench/run/decision_metrics.py
core/services/workbench/run/decision_reference.py
core/services/workbench/run/decision_impact.py
core/services/workbench/run/decision_workspace.py
core/services/workbench/run/decision_export.py
core/services/workbench/run/decision_preparation.py
core/services/workbench/run/decision_changeovers.py
core/services/workbench/run/decision_preparation_queries.py
core/services/workbench/run/decision_preparation_export.py
data/repositories/workbench_run_result_repo.py
web/routes/workbench/run_decision.py
web/routes/workbench/navigation_boot.py
```

查询保存的需求分解与原标准有独立字段，原source缺项继续缺项；正式完整视角的未选工序详情按其原来源按需读取。原算法字段保持保存来源，实际事件由新字段表达。

### 试调与旧界面

```text
core/services/workbench/facts/trial_policy.py
core/services/workbench/facts/trial_scenario_archive.py
core/services/workbench/trial/arrangements.py
core/services/workbench/trial/effort.py
core/services/workbench/trial/preparation.py
core/services/workbench/trial/base.py
core/services/workbench/trial/calendar.py
core/services/workbench/trial/projection.py
core/services/workbench/trial/service.py
core/services/workbench/trial/validation.py
frontend/workbench/app/TrialContract.js
frontend/workbench/app/TrialControls.jsx
frontend/workbench/app/TrialDetails.jsx
frontend/workbench/app/TrialResults.jsx
frontend/workbench/app/TrialExport.js
frontend/workbench/app/TrialViewState.js
frontend/workbench/app/TrialAdoptionHistoryState.js
frontend/workbench/app/RunCandidateAnalysis.jsx
frontend/workbench/app/DashboardCandidatePanels.jsx
```

试调实际新槽使用共同公式保存，原样／执行／完成保留原需求；几何相等、重置及metadata分别处理。保存场景完整需求账包含未排／暂缓源项，实际工种来源区分原来源与真实新槽输入。两类旧CSV与任务／结果详情消费共同投影。

### 新前端、构建、测试与验证

```text
frontend/workbench/app/WorkbenchTerms.js
frontend/workbench/app/EffortProjectionContract.js
frontend/workbench/app/RunOperationEffort.jsx
frontend/workbench/app/RunDecisionPreparation.jsx
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunDecisionDetails.jsx
frontend/workbench/app/RunCandidateAPI.js
frontend/workbench/app/RunCandidateModel.js
frontend/workbench/app/RunCandidateControls.jsx
frontend/workbench/app/RunCandidateGantt.jsx
frontend/workbench/app/RunCandidateWorkspace.jsx
frontend/workbench/app/styles/34-run.css
scripts/workbench/build-order.json
static/workbench/app/main.js
static/workbench/app/workbench.css
tests/algorithm/test_operation_effort.py
tests/schedule/service/test_operation_effort_input.py
tests/workbench/test_changeover_projection.py
tests/workbench/test_trial_effort_projection.py
tests/workbench/test_run_decision_preparation_api.py
tests/workbench/test_run_decision_api.py
tests/workbench/test_run_decision_metrics.py
tests/workbench/test_run_decision_impact_api.py
tests/workbench/test_run_decision_resource_api.py
tests/workbench/test_scheduler_execution_ledger_guards.py
tests/workbench/test_ui_refinement_node_contracts.py
tests/workbench/decision_comparison_contract.cjs
tests/workbench/decision_preparation_contract.cjs
tests/workbench/decision_resource_contract.cjs
tests/workbench/fixtures/decision_preparation_workspace.json
tests/workbench-terms-and-ids.cjs
tools/test_registry_data.py
scripts/verify_decision_workbench.py
```

新增行为进入既有必跑注册表，日常127目标实际执行。三处真实跨层合同修正：工序runtime用compact、资源外层目录v4与内部投影分别校验、候选严格任务形状接纳可选永久工种字段；最新shipped组件已读实际DTO。最后布局增量把常用候选行重复理由收进原生依据，准备汇总改8行对照；状态、小计、缺项、差值及完整理由保留，原详细工序表和全部指标矩阵沿用完整展示。

### 项目材料

```text
.codestable/features/2026-10-13-decision-preparation-events/decision-preparation-events-design.md
.codestable/features/2026-10-13-decision-preparation-events/decision-preparation-events-checklist.yaml
.codestable/features/2026-10-13-decision-preparation-events/decision-preparation-events-acceptance.md
.codestable/features/2026-10-13-decision-preparation-events/decision-preparation-events-handoff.md
.codestable/requirements/candidate-comparison-business-view.md
.codestable/architecture/service-scheduler.md
.codestable/architecture/workbench-shell.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-roadmap.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-items.yaml
static/docs/scheduler_manual.md
开发文档/系统速查表.md
```

## 3. 隔离实例及真实范围

数据库`/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`，身份文件`/private/tmp/aps-decision-workbench-20261013/instance.json`。最终只读实例为`http://127.0.0.1:50306`／PID62818；正常关闭63879后用相同数据库冷启动，未新增排产或采用。

新增运行`85c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb`：10批、31工序，含全部正式15、完整件别6、外协及待料1；4候选各30实际安排，收据31项账。截止沿原案例10月30日参数，查看窗10月13日至17日；工序准备14.5h／加工45.55h，实际切换3次。冻结DC05首道原时段机人及零时点保持，普通未排另用真实SQLite/API及旧ordinary_partial归档验证。

候选：

```text
70fc4f40b5b80f94d993e67329264f6e1b7bd3c329e2c2b1
fdb594cff65c41c044d0e6561682284b1b11b0ebcedab6cc
fa50a4b6ec7faffcda7482dd67fe54841b0daa73a1e86ee3
695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626
```

本阶段最初两个受理失败分别为`piece_scope_incomplete`与`official_scope_not_covered`，完整原记录保留；最终31scope先核正式／件别覆盖和容量再受理成功。原7运行／34候选和所有旧资料逐tuple保存、配置恢复；当前46批／90工序／10运行／38候选／613任务，正式v1／15行保持。预览实例本阶段完成后仅只读核对。

直接查看入口（4条实际GET、保存导航及对应API均通过）：

- [候选对比／准备需求](http://127.0.0.1:50306/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%2285c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb%22%2C%22candidate_ref%22%3A%22695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22comparison_tab%22%3A%22preparation%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22resource_view%22%3A%22selected_batches%22%2C%22reference_candidate_ref%22%3A%2270fc4f40b5b80f94d993e67329264f6e1b7bd3c329e2c2b1%22%7D%7D)，明细总数31。
- [候选对比／工种切换](http://127.0.0.1:50306/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%2285c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb%22%2C%22candidate_ref%22%3A%22695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22comparison_tab%22%3A%22changeovers%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22resource_view%22%3A%22selected_batches%22%2C%22reference_candidate_ref%22%3A%2270fc4f40b5b80f94d993e67329264f6e1b7bd3c329e2c2b1%22%7D%7D)，明细总数6。
- [正式基准／准备需求](http://127.0.0.1:50306/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%2285c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb%22%2C%22candidate_ref%22%3A%22695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22comparison_tab%22%3A%22preparation%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D)，明细总数31。
- [正式基准／工种切换（完整候选视角）](http://127.0.0.1:50306/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%2285c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb%22%2C%22candidate_ref%22%3A%22695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22comparison_tab%22%3A%22changeovers%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22resource_view%22%3A%22full_candidate%22%7D%7D)，明细总数3。

## 4. 验证与证据入口

- Python3.8.10日常：461 passed／20 skipped，127目标，70.44s；Ruff全通过。日常后仅布局增量，2项既有Node契约和Chrome109本地10文件构建再次通过；源头及数据保持，相关既有结果复用。质量证据`evidence/decision-preparation-events/quality/`。
- 共同源头8项、切换5项、新API5项、试调5项等新增契约和相关既有回归通过；同一有效结果按范围复用。实际反馈用例证明开工保护及完工worker保持实际时间与0.75h原需求。
- 独立需求／事件读取核930字段、两侧6事件、零时点、件别实际量、外协周期、窄窗前驱／右端排除及31／42工序稳定20／50分页。
- 原始5案例7文件899行、42,897格／11,347数字与202个JSON安排核对通过，9表和筛选范围一致。新增的唯一单人员逐日XLSX为11表／293行，包含31道准备需求与两侧6事件；原4案例／6文件按相同有效源码复用，各自实例已在合并报告分开记录。
- C3测试中的v1来自真实worker／采用，manual部分v2是旧档fixture，证明最后来源缺项和当前AJ数量分开；其B1实际冻结、B2实际新排。Trial原10件／7h、本次20件及完工0余量有真实保存证明。
- [最终浏览器](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/browser/verification.json)：准备所选／正式、切换基准前序／所选后序4次真实往返，永久工序和原上下文一致；正式详情绑定只读v1，窗口前驱自动扩展定位窗并恢复原窄窗。两页1392／1920深浅8张最终图、原生依据Enter／Space通过，主字体13px；1392末候选行底部904.31px、行高67.38px，准备8指标汇总高326px。准备汇总／逐道表原生125／150%缩放时保留局部横向滚动、定位按钮可见，页面缩放已恢复100%。实际浏览器155，构建目标109。
- 详细结果、修正前证据和范围见[实施验收](decision-preparation-events-acceptance.md)及[原始证据索引](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/evidence-index.json)。索引保留19张有效截图、2张修正前布局、两次失败受理及最终成功记录；原始根`evidence/decision-preparation-events/aps-decision-workbench-20261013/`。

## 5. 交回状态

第4阶段为done／implementation_acceptance=passed／parent_acceptance=passed；第5阶段已派发，第6—8阶段planned。当前为累计dirty工作区和本阶段日常及增量证明；最终HEAD、Win7实机及clean-worktree证明沿第8阶段完成。
