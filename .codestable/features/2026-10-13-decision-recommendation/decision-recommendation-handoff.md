---
doc_type: feature-handoff
feature: decision-recommendation
status: done
implementation_acceptance: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第5阶段固定推荐与取舍的职责、实际文件、隔离实例及独立复核入口
tags: [aps, workbench, recommendation, completion, tradeoff]
---

# 第5阶段交接

第5阶段第一轮返修已完成，P2-05-01、P2-05-02和P3-05-03均通过实施验证。当前`done / implementation_acceptance=passed / parent_acceptance=passed`，主对话独立复验通过，第6阶段已派发，第7—8阶段等待派发。固定选择、52项差值、SHA清理及原文件有效证据继续复用；修复与原失败记录见 [repair-01](decision-recommendation-repair-01-fix-note.md)。

返修前第5阶段实施验收通过，用户追加的无用SHA与临时编号清理已完成。固定推荐、三轴完成性、共同完成集合、主要3+3与全部差值、并列／复用、真实支撑和同源导出已通过当时业务、浏览器、原文件和日常核验。

## 1. 职责及事实链

```text
选择器/健康计算器原始事实
  → 完成事务映射永久候选ref并保存
  → 请求内共同完成集合、交付/准备/资源及差值
  → 固定selection_basis与recommendation.current_comparison
  → 主页面/值班台/分行导出
  → 当前采用preview及原事务复验
```

保存推荐、raw最优、健康原方案固定；第三查看与当前基准独立。推荐当前取舍按保存推荐减当前基准，候选表／明细按各候选减当前基准。共同完成交付与整次受理未知分别保持范围。三类推荐为“推荐方案／本次可排范围推荐／算法选中的部分结果”。

聚合支撑进入固定推荐的既有批次、资源、准备或切换明细。具体工序／事件使用真实安排drill进入甘特；推荐移除了原安排时，工序支撑进入该比较基准的原安排。未知／未安排／多段覆盖保持各自事实，支撑样例仅使用统计中的已知变化。甘特恢复支撑页，支撑页再恢复原比较。内部上下文包含原第三候选、查看基准、范围、页签、筛选、分页与快照；URL仍沿既有导航白名单。

## 2. 本阶段文件范围

### 源头与共同领域

```text
core/services/scheduler/run/schedule_candidate_selection.py
core/services/scheduler/run/schedule_candidate_health.py
data/repositories/workbench_run_result_repo.py
core/services/workbench/facts/completion_scope.py
core/services/workbench/facts/common_completed_delivery.py
core/services/workbench/run/decision_delivery.py
tests/candidate/test_scheduler_selection_evidence.py
tests/workbench/test_completion_scope.py
```

### 推荐、当前取舍及导出

```text
core/services/workbench/run/decision.py
core/services/workbench/run/decision_source.py
core/services/workbench/run/decision_metrics.py
core/services/workbench/run/decision_reference.py
core/services/workbench/run/decision_completion.py
core/services/workbench/run/decision_completion_queries.py
core/services/workbench/run/decision_preparation_queries.py
core/services/workbench/run/decision_preparation_export.py
core/services/workbench/run/decision_selection.py
core/services/workbench/run/decision_selection_explanation.py
core/services/workbench/run/decision_recommendation.py
core/services/workbench/run/decision_tradeoffs.py
core/services/workbench/run/decision_recommendation_export.py
core/services/workbench/run/decision_export.py
core/services/workbench/run/candidate_comparison.py
core/services/workbench/run/candidate_tradeoffs.py
web/routes/workbench/run_decision.py
tests/workbench/test_run_decision_recommendation.py
tests/workbench/test_run_decision_api.py
tests/workbench/test_run_decision_metrics.py
tests/workbench/test_run_decision_impact_api.py
tests/workbench/test_run_decision_resource_api.py
tests/workbench/test_run_decision_preparation_api.py
tests/workbench/test_run_decision_completion_api.py
```

`decision_metrics.candidate_metrics`复用同一候选的交付投影；旧候选对照从共同取舍纯投影读取。全部导出的三张新增表和推荐分区共用相同事实。新推荐测试登记到已有必跑组，既有API测试更新实际合同与12／14表名单。

### 页面、旧实际消费者与构建

```text
frontend/workbench/app/RecommendationContract.js
frontend/workbench/app/RunDecisionRecommendation.jsx
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunDecisionCompletion.jsx
frontend/workbench/app/RunDecisionPreparation.jsx
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/styles/34-run.css
frontend/workbench/app/DashboardCandidateComparisonAPI.js
frontend/workbench/app/DashboardCandidatePanels.jsx
frontend/workbench/app/TrialWorkspace.jsx
frontend/workbench/app/TrialAdoptionControls.jsx
scripts/workbench/build-order.json
static/workbench/app/main.js
static/workbench/app/workbench.css
tests/workbench/decision_comparison_contract.cjs
tests/workbench/decision_preparation_contract.cjs
tests/workbench/decision_resource_contract.cjs
tests/workbench/notice_ownership_contract.cjs
tests/workbench/test_legacy_resource_projection.py
tools/test_registry_data.py
scripts/verify_decision_workbench.py
```

`RunCandidateWorkspace.jsx`本阶段未修改，沿用已完成的甘特返回。新增复用行展开消费原source四字段及双方保存引用；原始浮点展示格式化为6位且title保留原值，JSON／导出原数值保持。

Chrome109交付payload为10项：`app/main.js`、`app/theme.js`、`app/workbench.css`、`prototype/assets/logo-mark.svg`、`prototype/fonts/MicrosoftYaHei-Regular.ttf`、`prototype/ui_kits/workbench/assets/lucide-LICENSE`、React／ReactDOM两个min.js及两个LICENSE；均相对`static/workbench/`。`asset-manifest.json`为独立索引记录，结构／路径沿用。

### 项目材料

```text
.codestable/features/2026-10-13-decision-recommendation/decision-recommendation-design.md
.codestable/features/2026-10-13-decision-recommendation/decision-recommendation-checklist.yaml
.codestable/features/2026-10-13-decision-recommendation/decision-recommendation-acceptance.md
.codestable/features/2026-10-13-decision-recommendation/decision-recommendation-handoff.md
.codestable/features/2026-10-13-decision-recommendation/decision-recommendation-repair-01-fix-note.md
.codestable/requirements/candidate-comparison-business-view.md
.codestable/architecture/service-scheduler.md
.codestable/architecture/workbench-shell.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-roadmap.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-items.yaml
static/docs/scheduler_manual.md
开发文档/系统速查表.md
```

原始证据在`evidence/decision-recommendation/`；源HEAD为`0df8fc48`，工作区含第0—5阶段累计改动及README原并发10行。本轮无提交、推送或发布；母`stage-acceptance.md`由主对话维护。

## 3. 隔离实例及实际案例

数据库`/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`，身份文件`/private/tmp/aps-decision-workbench-20261013/instance.json`。返修当前只读预览`http://127.0.0.1:65050`／PID41829；同库正常冷启动一次，清理阶段58804／PID77096正常退出。旧业务截图、导出和冷读记录按当时身份保留；[最终实例](../../../evidence/decision-recommendation/repair-01/runtime-final.json)核对实际数据库、PID及最终main.js版本1791871190，直接链接见文末。

真实balanced运行`454f75ffaa01ad531eceaa8454f14b7d139677015b36c0f3`：11批／32工序，4候选各31安排、待料暂缓1道；推荐graph1、raw最优与健康原方案均为baseline。主目标算法切换3对3；超期2→3、拖期增加17.24h／约6.0574%，四项实际检查通过，健康3分。主目标并列4个、完整评分最优1个；源证据和当时阈值保留。

```text
推荐 graph1: 11c2be4c3a18ee08c7964c8de61601bc2e236cdf8f806a1e
raw/健康 baseline: fb57f70b77acb5beb87c53e62f1277fe306f76d9fd25fe64
graph2: 148ac438fbc8284dd264db62f2cf560797aa76fb52b4e875
graph3: 552b2a3f4a985dffd85577fc0141e3b69753f2978540674c
```

只新增DN-BALANCED-01一批／一道独立工序及一次worker运行，生成参数恢复34行。原资料保留，当前47批／91工序／11运行／42候选／737任务；正式v1／15条安排保持。旧4／6／8候选、全部分、暂缓和混合交期案例按原记录读取，采用只进行预检。

## 4. 原第5阶段及SHA清理证据

- [实施验收](decision-recommendation-acceptance.md)按C01—08记录接口、行为、实际场景和边界；[执行清单](decision-recommendation-checklist.yaml)记录本阶段状态。
- [日常原日志](../../../evidence/decision-recommendation/quality/daily-final.log)：Python3.8.10，130目标，476 passed／20 skipped，76.15s，Ruff全通过。日常后的界面和支撑修正单列相关增量验证。
- [界面增量](../../../evidence/decision-recommendation/quality/frontend-incremental.json)：Nodecomparison、10文件Chrome109构建、2项离线资产检查通过；复用行和17.24展示补验后并入浏览器记录。
- [真实三类DTO合同](../../../evidence/decision-recommendation/quality/aps-p5-ui-contract-result.json)：实际归档暂缓、全部分及真实API完整夹具均严格解码和渲染通过，每类52项差值。完整类来源为真实SQLite/API测试库，另两类为隔离预览库；未为此新增现场运行。
- [固定依据](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/fixed-basis-verification.json)、[原收据](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/balanced-run/original-receipt.json)、[保全证明](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/balanced-run/retention-verification.json)。
- [原接口速查253项对账](../../../evidence/decision-recommendation/quality/quickref_vs_routes.md)：原文档／实现各253项，双向缺项0。返修新增完成集合GET后，各254项、双向缺项0，见[当前对账](../../../evidence/decision-recommendation/repair-01/quickref-vs-routes.md)。

- [浏览器核验](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/browser/verification.json)：四首屏、原生125／150%、键盘、五类真实支撑、两条嵌套甘特完整返回、6／8候选策略来源与采用预检通过。有效图片20张；旧问题及3张未就绪／截图偏移图片单列保留。
- [原始导出核验](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/exports/export-verification.json)：7文件、2315业务行、137525单元格通过；最后完整导出按受理正式基准模式核对12表、771行。
- [完整证据索引](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/evidence-index.json)：30份原记录、20张有效图片、7份原始导出，均已检查文件存在。

用户追加的全仓无用SHA及编号清理已完成：读取状态绑定原范围及来源，缓存用已有查询／业务值，物料行使用同源排序序号，master／表格／系统临时键用精确业务身份或实际文件位置，打包取消SHA sidecar。实际删除、70路径范围、保留用途及所有原日志见[清理摘要](../../../evidence/sha256-cleanup/summary.json)。永久记录、持久回放、真实文件核对及长期排程内容缓存沿用已有职责。
- [支撑后端增量](../../../evidence/decision-recommendation/quality/backend-support-incremental.log)：项目Python3.8.10／NetworkX3.1复验9项通过；保留误用宿主NetworkX3.6.1的原失败，来源标注及取样修正均已覆盖。
- [支撑前端增量](../../../evidence/decision-recommendation/quality/frontend-support-incremental.json)：实际冷读DTO严格解码和渲染、基准侧标签及返回合同、Chrome109构建和2项离线检查通过。

## 5. 第一轮返修证据与交回状态

P2-05-01已以真实默认主因、可见当前基准关系和13px／3+3完成最终八组合首屏验证；P2-05-02已提供各候选完整集合及精确剩余筛选，第三查看／基准／成员／类别／分页和展开条件完整往返通过；P3-05-03已修正graph2／graph3实际映射。原生缩放、分页UI、最后数据保全与交接身份核对均通过，返修实施验收passed，主对话独立复验passed，第6阶段in_progress，第7—8阶段planned。最终HEAD、clean-worktree、Win7实机及整体边界性能沿第8阶段完成。

- [返修记录](decision-recommendation-repair-01-fix-note.md)、[当前日常](../../../evidence/decision-recommendation/repair-01/daily-final.json)：Python3.8.10、134目标、487 passed／20 skipped、77.06s，Ruff通过。日常后的局部UI仅做相关增量，[最终Node及10项Chrome109构建](../../../evidence/decision-recommendation/repair-01/build-tradeoff-correction.json)、[两项离线资产](../../../evidence/decision-recommendation/repair-01/assets-final.log)通过。
- [完整集合真实GET](../../../evidence/decision-recommendation/repair-01/api-readback.json)及[主代理原始复核](../../../evidence/decision-recommendation/repair-01/root-api-inspection.json)：普通部分结果四anchor完整列出A/B互补集合，保存推荐仅DD-P-A一道普通未排；21批按20+1／50取全，原数据、snapshot与as_of相等。
- [最终八组合](../../../evidence/decision-recommendation/repair-01/layout-final.json)、[原坐标及像素复核](../../../evidence/decision-recommendation/repair-01/root-layout-inspection.json)：balanced／三项代价各在1392×924、1920×1080浅深主题保持四完整候选，13px主因与可见基准关系、3+3和当前操作完整。
- [成员集合](../../../evidence/decision-recommendation/repair-01/browser/four-candidate-completion-lists.json)、[类别切换](../../../evidence/decision-recommendation/repair-01/browser/completion-categories.json)、[精确剩余与甘特完整返回](../../../evidence/decision-recommendation/repair-01/browser/recommended-remaining-roundtrip.json)保留实际页面及上下文证据。
- [21批页面分页](../../../evidence/decision-recommendation/repair-01/browser/mixed-completion-paging.json)、[合法待料及未知空类别](../../../evidence/decision-recommendation/repair-01/browser/legal-deferred-unknown.json)、[Chrome原生125／150%](../../../evidence/decision-recommendation/repair-01/browser/native-zoom-final.json)均通过；原生缩放下主因、基准关系、集合控件与正文保持13px，类别读取同推荐成员，表内水平滚动及零alerts，最终恢复100%。
- [最终返修验证索引](../../../evidence/decision-recommendation/repair-01/verification-final.json)、[最终业务保全](../../../evidence/decision-recommendation/repair-01/final-retention-verification.json)：9表完整行集和列均与修复前相等，47批／91工序／11运行／42候选／737任务、正式v1／15行和34参数保持，读取total_changes=0。本轮新增排产、业务样例、采用和重复导出均为0。

此前SHA清理的有效结果继续保留：

- [质量摘要](../../../evidence/decision-recommendation/quality/quality-summary.json)保留阶段记录；[清理后日常](../../../evidence/sha256-cleanup/daily-repaired.log)：Python3.8.10、133目标、484 passed／20 skipped、77.52s，Ruff通过，同次执行覆盖实际交付包legacy wrapper。
- [清理后本地构建](../../../evidence/sha256-cleanup/build-incremental.json)：10 payload、Chrome109。前一构建与两个过时测试夹具的初轮失败保留；实际恢复行为修正后重建，清理最终日常退出0。
- [清理后冷读](../../../evidence/sha256-cleanup/cold-read-final.json)：四案例同scope复用原token／as_of／数据、跨scope各409；正式辅助入口v1／available及原固定选择保持；新键实际筛选、37主数据问题、10日志通过。当时9张业务表、34参数及正式v1／15行逐行相等，读取连接total_changes=0。
- [返修当前链接身份](../../../evidence/decision-recommendation/repair-01/current-links.json)核对四案例及三项代价的原保存身份；[原直接链接身份](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/readonly-link-identities.json)保留清理时记录。正式辅助沿已验证上下文指向当前同库实例；以下链接均只读。

| 实际只读入口 | 链接 |
| --- | --- |
| balanced：第三查看／另一关键链基准 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22454f75ffaa01ad531eceaa8454f14b7d139677015b36c0f3%22%2C%22candidate_ref%22%3A%22552b2a3f4a985dffd85577fc0141e3b69753f2978540674c%22%2C%22reference_candidate_ref%22%3A%22148ac438fbc8284dd264db62f2cf560797aa76fb52b4e875%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |
| 混合交期与算法取舍 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22e8e31a32e1062ad45f1c7bbd70c2edee894e59cee96e4530%22%2C%22candidate_ref%22%3A%22663f80877d6780b8f20b06968b0075e649258abd4eb6f9e8%22%2C%22reference_candidate_ref%22%3A%22abd00b49636f8e98440ca8b9dc9bba1b765f217a15d3599d%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-21T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |
| 普通部分结果／空共同完成集合 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%228178403fae7fab31de6c7199067c244ebf31453e8f888bc9%22%2C%22candidate_ref%22%3A%22dc7f93962daf94673c1d00841329bd2e81edee577ff6d7d6%22%2C%22reference_candidate_ref%22%3A%22c8498743844a26286e97fa6bbc6472304465de3732c98267%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-14T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |
| 合法待料暂缓 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%224ba269dd2f90b7559237633a6f95c181bdb4e961b8fc3915%22%2C%22candidate_ref%22%3A%2245e2a434083523571ee3d0dd1a316939c892e023a5c4ca5c%22%2C%22reference_candidate_ref%22%3A%225ada1e845e70e810332de8ae7d8a420fa8010c8003ad4e88%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-16T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |
| balanced：受理正式基准 v1 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22454f75ffaa01ad531eceaa8454f14b7d139677015b36c0f3%22%2C%22candidate_ref%22%3A%22552b2a3f4a985dffd85577fc0141e3b69753f2978540674c%22%2C%22comparison_mode%22%3A%22admission_official%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |
| 三项代价：一天窗口／第三查看 | [打开页面](http://127.0.0.1:65050/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%2285c1b9b12f46a4ca6fa0cb88d6ffab94b858cab54f338ddb%22%2C%22candidate_ref%22%3A%22695ccfbbf5bfa9439522a0d1bd33df6e47b552a225092626%22%2C%22reference_candidate_ref%22%3A%22fdb594cff65c41c044d0e6561682284b1b11b0ebcedab6cc%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-14T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D) |

主对话独立复验已通过：在65050实例实测四完整候选、真实主因／可视基准／13px／3+3、四成员互补全集、21批同快照分页和精确剩余往返；原始证据在`evidence/decision-stage-acceptance/stage-05-repair-01/`。母`stage-acceptance.md`由主对话维护，本记录仅同步其通过结论。
