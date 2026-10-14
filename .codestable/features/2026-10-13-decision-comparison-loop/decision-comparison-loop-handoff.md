---
doc_type: feature-handoff
feature: decision-comparison-loop
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第 0、1 阶段及两项返修通过主对话复验，保留实现与原始证据交接
tags: [aps, workbench, candidate-comparison]
---

# 第 0、1 阶段交接

**第 0、1 阶段及 P2-01 决策密度 / P2-02 导出文本与空值返修已通过主对话复验。** 本轮修改覆盖这两项及相关 UI、导出验证；既有引擎回归与采用事务结果复用。主对话维护母任务的阶段结论；第 2 阶段已派发，记录见 `features/2026-10-13-decision-delivery-impact/`，第 3—8 阶段等待逐段派发。本材料保留第 0、1 阶段交付当时的实例与验证；本轮未提交、推送或发布。

工作目录：`/Users/lurenxing/GitHub/----`。下面的项目路径均相对于该绝对目录。

## 1. 本阶段实际交付

- 同次全部候选的共同归档读取、18 项指标目录、覆盖、任选查看基准及差值。
- 保存推荐、raw_score_best 与 health_reference 的永久引用及当时选择策略、评分顺序和实际容差；score_only 明确未启用交期容差。
- 推荐→收益代价→当前动作→候选常用行表的工作台布局，全部 18 项在同区展开；失败/预算跳过原因、待料暂缓与三轴覆盖。
- 同候选甘特钻取与返回上下文、现有正式采用入口、同快照 CSV/XLSX 总览。
- 归档入口移除重复 SHA256 计算，新比较快照按运行/候选身份、范围及既有指标版本核对。保留 SQLite 事务和实际引用/结构校验。
- 实际已排工作不同且仍有应排缺口时，跨度与切换差值显示覆盖不同；少排工作带来的短跨度移出推荐收益。

## 2. 准确改动文件

### 后端与 Web

```text
core/services/scheduler/run/schedule_candidate_selection.py
core/services/workbench/facts/candidate_facts.py
core/services/workbench/run/decision.py
core/services/workbench/run/decision_metrics.py
core/services/workbench/run/decision_selection.py
core/services/workbench/run/decision_export.py
data/repositories/workbench_run_result_repo.py
web/routes/workbench/run_decision.py
web/routes/workbench/run_candidates.py
web/routes/workbench/read_context.py
web/routes/workbench/navigation_boot.py
```

### 前端、离线构建与验证入口

```text
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunCandidateControls.jsx
frontend/workbench/app/RunCandidateWorkspace.jsx
frontend/workbench/app/styles/34-run.css
scripts/workbench/build-order.json
static/workbench/app/main.js
static/workbench/app/workbench.css
scripts/verify_decision_workbench.py
tests/workbench/decision_comparison_contract.cjs
tests/workbench/test_ui_refinement_node_contracts.py
tests/workbench/test_run_decision_api.py
tests/workbench/test_run_decision_metrics.py
tools/test_registry_data.py
```

### 文档与阶段材料

```text
static/docs/scheduler_manual.md
开发文档/系统速查表.md
.codestable/architecture/service-scheduler.md
.codestable/architecture/workbench-shell.md
.codestable/requirements/candidate-comparison-business-view.md
.codestable/requirements/VISION.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-roadmap.md
.codestable/roadmap/scheduling-decision-workbench/scheduling-decision-workbench-items.yaml
.codestable/features/2026-10-13-decision-comparison-loop/decision-comparison-loop-design.md
.codestable/features/2026-10-13-decision-comparison-loop/decision-comparison-loop-checklist.yaml
.codestable/features/2026-10-13-decision-comparison-loop/decision-comparison-loop-acceptance.md
.codestable/features/2026-10-13-decision-comparison-loop/decision-comparison-loop-handoff.md
```

`开发文档/README.md` 的既有并发增补完整保留，未纳入本轮修改清单。原型文件只作参考。`review.md` 保留规划审查时记录。本地 `.codestable` 新文件沿用 `.git/info/exclude` 留存规则；联调临时契约另在 `/tmp/aps-decision-contract.md`。上表是第 0、1 阶段累计范围；本轮返修范围单列于第 8 节。

## 3. 初轮实际执行命令与结果

命令均从上述工作目录执行。产品验证环境为 Python 3.8.10，前端构建目标为 chrome109。本节保留初轮历史证据；本轮返修相关验证见第 8 节。

| 实际命令 | 结果与范围 |
| --- | --- |
| `.venv/bin/python scripts/run_daily_quality_gate.py` | 全仓 Ruff 通过；111 个 required 目标单进程执行，361 passed / 20 平台条件 skipped，56.57s。 |
| `.venv/bin/python -m pytest tests/workbench/test_run_candidate_api.py tests/workbench/test_run_candidate_partial_adoption.py tests/candidate/test_scheduler_candidate_persistence_contract.py tests/workbench/test_adoption_source_read_reuse.py -q` | 既有候选、partial/stage 采用、持久化与来源复用，23 passed，6.33s。 |
| `.venv/bin/python -m pytest tests/workbench/test_run_decision_metrics.py::test_failed_algorithm_baseline_requires_explicit_viewing_reference tests/candidate/test_scheduler_candidate_persistence_contract.py -q` | score_only / balanced 容差与既有持久化增量，4 passed，0.91s。 |
| `.venv/bin/python -m pytest tests/workbench/test_run_decision_metrics.py tests/workbench/test_run_decision_api.py -q` | 最终指标 7 项及 API 5 项，12 passed，2.17s；包含真实不同漏排工序的跨度/切换差值。 |
| `node tests/workbench/decision_comparison_contract.cjs` | 全部候选、固定推荐、独立基准、响应身份、甘特返回与采用候选身份通过。 |
| `node tests/workbench/runtime_reuse_contract.cjs` | 既有导航/前进后退/身份复用契约通过。 |
| `python3 scripts/workbench/build.py` | status=built，files=10，target=chrome109。 |
| `.venv/bin/python -m pytest tests/app_runtime/test_frontend_offline_static_assets.py -q` | 说明书同步后离线资产冒烟，3 passed，0.55s。 |
| `.venv/bin/python tests/gate_meta/check_quickref_vs_routes.py` | 接口速查表对账 OK。 |
| `.venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-10-13-decision-comparison-loop --yaml-only` | feature frontmatter / checklist YAML 通过；交接文件新增后同目录复核。 |
| `.venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/roadmap/scheduling-decision-workbench --yaml-only` | 三份规划材料通过。 |
| `git diff --check` | 通过。 |

后端最终 Ruff 实际命令：

```bash
.venv/bin/python -m ruff check core/services/workbench/run/decision.py core/services/workbench/run/decision_metrics.py core/services/workbench/run/decision_selection.py core/services/scheduler/run/schedule_candidate_selection.py data/repositories/workbench_run_result_repo.py core/services/workbench/facts/candidate_facts.py
.venv/bin/python -m ruff check core/services/scheduler/run/schedule_candidate_selection.py tests/workbench/test_run_decision_metrics.py
.venv/bin/python -m ruff check core/services/workbench/run/decision.py core/services/workbench/run/decision_metrics.py tests/workbench/test_run_decision_metrics.py
```

三条均为 All checks passed。Web / 导出、宿主脚本与测试也已通过对应 Ruff，日常门禁包含全仓检查。门禁后只针对 score_only、最后工序覆盖修正及说明书变化执行相应增量验证。早期 XLSX 测试使用 `write_only` 工作簿 `max_row` 读取方式导致一次失败；改为实际遍历行数后，最终 12 项结果通过。

## 4. 可复用的真实隔离实例

- 第 1 阶段返修时地址：`http://127.0.0.1:50387`，PID `43541`；当时复核 `/system/health` 返回 status=ok 且 PID 一致。接续的当前实例见第 2 阶段 handoff。
- 数据库绝对路径：`/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`。
- 实例身份文件：`/private/tmp/aps-decision-workbench-20261013/instance.json`。
- 运行合同：`/private/tmp/aps-decision-workbench-20261013/logs/aps_runtime.json`。
- 原始证据目录：`/Users/lurenxing/GitHub/----/evidence/decision-comparison-loop/aps-decision-workbench-20261013`。
- 当时完整预览 URL 在 `repair-01/repair-verification.json` 的 `preview_url`，打开原四候选、候选2和候选3基准。`verification.json` 与 `final-code-refresh.json` 保留初轮端口的历史预览和窗口证据。

服务关闭后，复用原库与原引用启动：

```bash
.venv/bin/python scripts/verify_decision_workbench.py serve --instance /private/tmp/aps-decision-workbench-20261013/instance.json
```

该命令加载同一实例，采用新空闲端口，并更新实例文件中的 URL/PID；既有运行和正式采用结果保留。新建一份独立隔离实例时用 `serve --root <专用目录>`，会生成 6 批 / 15 工序并真实排产。

复核既有 UI 采用结果的实际命令：

```bash
.venv/bin/python scripts/verify_decision_workbench.py verify --instance /private/tmp/aps-decision-workbench-20261013/instance.json --selected-candidate-ref a4183073694ddf7705e6baf6114d3b7e5aa27aa713d37cdb --reference-candidate-ref 93c029d9ebe40c231ae840adf473ddc330736b9d7e8ab516 --official-plan-ref 0d7a9dad1ccd4513a883c1f2173b7de53affc7fad74bf901
```

初轮结果 passed：数值、身份和范围核对通过；正式 15 工序的身份、数量、时间、设备/人员/供应商及采用来源与所选候选相同。初轮导出核对使用导入解码辅助函数，普通文本与空值原样性由主对话发现缺口。本轮已删除该解码依赖，按标准读取直接复核，结果见第 8 节。原正式字段证据继续复用。

## 5. 验收引用

| 对象 | 永久引用 |
| --- | --- |
| 运行 | `e4f3ff6fa4234ce6cc85473517303b81ff4405ce59509246` |
| 原算法 / 计算时推荐 | `22d183723a495f3e1f261d78f28996d1c1edf49f4d802289` |
| 重点工序优先 1/3，UI 实际采用 | `a4183073694ddf7705e6baf6114d3b7e5aa27aa713d37cdb` |
| 重点工序优先 2/3，UI 查看基准 | `93c029d9ebe40c231ae840adf473ddc330736b9d7e8ab516` |
| 重点工序优先 3/3 | `b276d807e7073730b329798df279e2fd06d6de5b12f2e877` |
| UI 采用后的正式 v1 | `0d7a9dad1ccd4513a883c1f2173b7de53affc7fad74bf901` |

实际浏览器完成比较→切第三候选基准→查看候选2→甘特→返回保持身份/窗口→正式采用→正式计划。控制台 0 errors / 0 warnings。

## 6. 原型对照与截图

| 原型依据 | 本阶段采用的内容 |
| --- | --- |
| `docs/aps_frontend_workbench_mockup.html:2138` 的 comparison 区域 | 推荐结论→收益和代价→方案摘要→详细比较。 |
| `frontend/workbench/prototype/ui_kits/workbench/AnalysisScreen.jsx` | 比较页面组织与采用 / 甘特入口。 |
| 同目录 `PlanShared.jsx` | 查看方案、比较上下文与返回入口。 |
| 同目录 `trial-sample-views.js` 的 comparison / timeline / impact | 候选对照及钻取交互。 |
| 同目录 `plan-workbench.css` | 当前工作台密度、颜色、间距、摘要与响应式排版；浅深主题沿用现有 token。 |
| Git `d2a40813` 的早期批次/资源影响原型 | 完整产品的后续目标，按第 2—8 阶段继续建设。 |

原型示例数字由真实候选事实替换。截图均保存在绝对目录：

`/Users/lurenxing/GitHub/----/evidence/decision-comparison-loop/aps-decision-workbench-20261013/screenshots/`

```text
decision-overview-light.png
decision-overview-dark.png
decision-metric-scope-light.png
decision-gantt-return-light.png
decision-adopted-dark.png
decision-official-plan-dark.png
```

同名原始截图在 `/Users/lurenxing/GitHub/----/output/playwright/`。浅深首屏与新增指标口径使用最终接口；甘特回跳和 UI 采用保留当次实际操作证据。

## 7. 后续阶段门槛与验证范围

当前共同资源摘要标为算法保存口径；共同班表、准备需求账、完整批次/资源影响、过程与历史趋势按第 2—8 项继续。Win7 真机、边界性能和最终完整门禁列入后续验收。本阶段按 Mac / Python 3.8.10 与离线 Chromium 构建验证，源码和编译产物保持未提交状态。

主对话阶段验收已通过，第 2 阶段按其明确派发推进。

## 8. 首轮返修交回复验

### 8.1 P2-01：首屏比较与选择

候选卡片改为常用指标行表；每行保留应排完成性、普通漏排、待料暂缓、完整交付、超期、拖期、跨度、切换和调整。搜索覆盖仅在范围栏显示一次，算法技术角色归入当时选择依据。当前选择、甘特与采用置于表前；全部指标开关展开同区 18 项矩阵。主文字 13px、既有小字 12px 保持。

| 实际扫描 | 结果 |
| --- | --- |
| 真实 4 候选，1392×924 | 表格底端 901.63px；第四个基准按钮底端 894.06px；甘特/采用按钮底端 515.19px，首屏可见。 |
| 真实 4 候选，1920×1080 | 表格底端 901.63px；甘特/采用底端 515.19px，首屏可见。 |
| 真实 6/8 候选，两个桌面尺寸 | 六行/八行准确呈现，超出首屏部分沿现有表格滚动；选择最后候选 5/5、7/7 后，当前动作仍在 494.63px。 |
| 浅深主题、全部指标与回跳 | 四候选双桌面浅深截图已保存；全部矩阵为 18 项加表头，甘特返回后所选候选、查看基准、时间窗及 metric_view=all 相同。 |

6/8 候选是同一隔离实例通过真实 HTTP 排产生成的 UI 规模夹具，运行分别为 `579e93d3ca41c34b4ed1eae76d520093f88ce523928b3473`、`aa2e2610e4b1fb8e0a04b131c4c153f1c101036e7f1c9e6e`；生成后权重候选数恢复为 3。原四候选运行、归档和正式 v1 保留。

### 8.2 P2-02：报表直接读取

决策总览脱离导入/回写转义，普通文本原样、空值留空。CSV 对实际公式前缀和数字文本编号做针对性保护；XLSX 字符串以文本格保存，数字以数字格保存。标准读取无需剥除前缀或解码 `\\N`。

- CSV 与 XLSX 各 72 行；候选名称直接读取为“原算法”“重点工序优先方案 1/3”等原文。
- “原算法 / 应排工序”行缺项说明直接读取为 CSV 空字符串、XLSX 空单元格。
- `_check_export_rows` 以候选编号和指标名称定位，逐行核对 15 个身份、名称、范围、单位、空值及核心数值字段；XLSX 288 个核心数值格保持数字类型。数值、小计、基准值和差值按指标单位比较。
- 既有 HTTP 导出用例补充公式文本、48 位数字编号、普通撇号和字面 `\\N`，直接检查原始读取值。

### 8.3 本轮修改与验证

本轮代码及对应编译产物：

```text
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/styles/34-run.css
static/workbench/app/main.js
static/workbench/app/workbench.css
tests/workbench/decision_comparison_contract.cjs
core/services/workbench/run/decision_export.py
tests/workbench/test_run_decision_api.py
scripts/verify_decision_workbench.py
```

同步 `static/docs/scheduler_manual.md`、`.codestable/architecture/workbench-shell.md` 及本 feature 的 design、checklist、acceptance、handoff。母任务的阶段验收材料由主对话维护。

| 实际命令 / 操作 | 结果 |
| --- | --- |
| `node tests/workbench/decision_comparison_contract.cjs` | 通过；保留交互契约，增加行表、常用/全部和搜索单处显示检查。 |
| `python3 scripts/workbench/build.py` | chrome109 离线构建通过。 |
| `.venv/bin/python -m pytest tests/workbench/test_run_decision_api.py::test_overview_exports_require_the_screen_reference_snapshot -q` | 1 passed，0.61s。 |
| `.venv/bin/python -m ruff check core/services/workbench/run/decision_export.py tests/workbench/test_run_decision_api.py scripts/verify_decision_workbench.py` | All checks passed。 |
| 实际浏览器布局扫描、基准切换、全部指标→甘特→返回 | 通过；原始测量和上下文 JSON 已保存。 |
| 实际 HTTP CSV/XLSX 下载、标准库 csv / openpyxl 直接读取 | 通过；名称、空值、15 个字段和核心数字类型证据已保存。 |

既有引擎回归、正式采用和未受影响的日常门禁结果复用。本轮进行 UI 规模夹具生成和相关界面/导出验证。

### 8.4 第 1 阶段返修时复验入口

当前证据绝对目录：`/Users/lurenxing/GitHub/----/evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/`。

[第 1 阶段历史预览 URL](http://127.0.0.1:50387/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22e4f3ff6fa4234ce6cc85473517303b81ff4405ce59509246%22%2C%22candidate_ref%22%3A%22a4183073694ddf7705e6baf6114d3b7e5aa27aa713d37cdb%22%2C%22reference_candidate_ref%22%3A%2293c029d9ebe40c231ae840adf473ddc330736b9d7e8ab516%22%2C%22comparison_mode%22%3A%22candidates%22%7D%7D)。第 2 阶段沿用同一库与原运行，当前复核入口见 [第 2 阶段交接](../2026-10-13-decision-delivery-impact/decision-delivery-impact-handoff.md)。

- [返修身份、结论与完整预览 URL](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/repair-verification.json)
- [布局实测](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/layout-verification.json)、[全部指标甘特回跳](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/gantt-return-context.json)
- [原始报表核对](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/raw-report-verification.json)、[CSV](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/decision-overview-raw.csv)、[XLSX](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/decision-overview-raw.xlsx)
- [1392×924 浅色四候选首屏](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/4-candidates-common-light-1392x924.png)、[真实 6/8 候选身份](../../../evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/candidate-count-fixtures.json)

`layout-verification.json` 的 `screenshots` 仅列当前有效截图，早期全部指标截图单列于 `interim_screenshots`。原主对话 `evidence/decision-stage-acceptance/stage-01/` 材料保留原样。

2026-10-13 主对话确认 P2-01 / P2-02 关闭；其独立复验证据位于 `evidence/decision-stage-acceptance/stage-01/repair-01/`，阶段正式验收记录由主对话维护。
