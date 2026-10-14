---
doc_type: feature-acceptance
feature: decision-comparison-loop
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第 0、1 阶段及两项 P2 返修已通过主对话独立复验
tags: [aps, workbench, candidate-comparison]
---

# 第 0、1 阶段验收

**第 0、1 阶段及 P2-01 / P2-02 返修已通过主对话独立复验。** 同次比较、基准切换、甘特回跳和既有引擎/采用验证继续复用。母任务的逐阶段审查与验收由主对话维护；本文件保存本阶段实现和实际验证。第 2 阶段已派发，其记录见 `features/2026-10-13-decision-delivery-impact/`；第 3—8 阶段等待逐段派发。

| 主对话发现 | 原因与返修动作 | 当前状态 |
| --- | --- | --- |
| P2-01 决策主区密度 | 大卡片重复覆盖、搜索、角色和指标；改候选行表、常用/全部指标与首屏当前动作，搜索在范围栏显示一次。 | repaired；1392×924 四行表底端 901.63px，甘特/采用底端 515.19px；4/6/8 候选双桌面尺寸实测通过。 |
| P2-02 报表文本与空值 | 复用导入/回写转义造成普通文本带撇号、空值带 \\N；新总览按报表语义直接写文本和空值，读取端直接核对。 | repaired；CSV 名称“原算法”、空值空字符串；XLSX 名称原文、空单元格，数字保持数值类型。 |

先前导出数值/身份验证通过；该轮读取使用导入解码辅助函数，报表普通文本和正常空值的原样性在首轮主验收中发现缺口。本轮以标准 CSV/XLSX 读取结果直接核对。

返修原始证据在 `evidence/decision-comparison-loop/aps-decision-workbench-20261013/repair-01/`：`repair-verification.json`、`layout-verification.json`、`raw-report-verification.json`、`gantt-return-context.json` 和同目录截图、原始 CSV/XLSX。1392×924 与 1920×1080 均核对真实 4/6/8 候选；浅深主题核对 4 候选。全部 18 项矩阵可访问，进入甘特再返回后，所选候选、基准、时间窗和全部指标视图相同。主文字 13px、既有小字 12px 保持。

准确文件清单、实际命令、可复用隔离实例、引用和原型/截图交付见 [阶段交接材料](decision-comparison-loop-handoff.md)。

## 1. 接口契约核对

- `GET /api/workbench/v1/scheduling/runs/<run_ref>/decision` 一次返回全部候选、共同归档身份、18 项指标目录、覆盖、查看基准、数值差值与固定选择依据。
- `/decision/export?format=csv|xlsx&section=overview&snapshot_ref=...` 消费相同投影。XLSX 为“方案总览 / 指标口径 / 比较范围”；CSV 为同一长表。百分比按百分数单位输出数字，XLSX 数字列保持数字类型。
- 引用属于同一运行且已产出安排；时间成对且有序。比较快照用现有身份字段及直接范围核对；旧接口延续原协议。
- 新比较查询与下载的测试把 `read_context.input_fingerprint` 设为报错仍通过，实际证明这条链路使用字段状态。
- 快照状态直接保存既有指标目录版本，指标口径版本变化时旧快照按字段比较识别。

## 2. 行为与决策核对

- 读取入口为 `decision.py`，共享归档由 `GenerationFacts` 解析一次；移除重复 SHA256 计算，继续核对归档结构及永久引用。
- 指标、覆盖与差值统一在 `decision_metrics.py`；用户查看基准与 `decision_selection.py` 的推荐 / raw_score_best / health_reference 分开。
- 保存时在同一运行完成事务中将算法键映射为永久引用。balanced 保存实际容差，score_only 的容差为 null 并明确显示策略未启用交期容差；旧收据按原键适配读取。
- `RunCandidateWorkspace` 的 analysis 分支挂载 `RunDecisionComparison`；甘特保持独立查看，回跳恢复所选候选、第三候选基准和窗口。原 `renderAdoption` 负责预检及采用。
- 挂载点 grep 核对：`register_run_candidate_routes` 注册 decision；前端 build-order 在 Workspace 前加载 decision API/UI；导出调用同一查询服务。拔除对应挂载点会使该能力消失，旧候选甘特和正式计划入口仍有各自职责。
- 页面采用原型的推荐→收益代价→当前动作→候选常用行表顺序，全部 18 项指标在同区展开；业务指标从生成资料移至主区。当前资源统计标明算法保存口径。
- 实际已排工序集合不同且双方应排范围仍有缺口时，跨度与切换差值标记覆盖不同；少排工作带来的短跨度从推荐收益中移出。完整候选继续正常比较。

## 3. 验收场景与实际证据

| 场景 | 结果 | 实际证据 |
| --- | --- | --- |
| C01 全部候选、任选基准、差值 | passed | 真实 4 候选；API 基准/差值用例，失败与预算跳过用例；原算法跨度 145.47h，重点候选 78.25h。 |
| C02 固定选择依据 | passed | 第三候选作查看基准后 selection_basis 保持相同；原算法失败要求选基准，balanced/score_only 容差保存分别核对。 |
| C03 三轴覆盖与待料 | passed | 搜索预算跳过保持已产出候选应排完成；stage 暂缓单列，业务交付仍部分；交付身份集合不同的差值有明确状态。真实单日 8h 班表中 5h / 6h 两工序分别漏排，已排工作不同的短跨度不给收益。 |
| C04 归档与导出 | passed | 既有引用/范围/快照用例复用。返修 72 行 CSV/XLSX 直接核对 15 个字段：名称、身份、范围、单位、空值、数值、小计、基准值和差值；XLSX 288 个数字格保持数值类型。定点用例包含公式文本、48 位数字编号、普通撇号和字面 \\N。 |
| C05 浏览器闭环 | passed | 初轮比较→第三基准→候选2→甘特→回跳→UI 正式采用→正式计划证据复用；返修补齐 4/6/8 候选双桌面尺寸、浅深主题、全部指标与甘特回跳。 |
| C06 验证与离线 | passed | Python 3.8.10；Node 比较契约和 chrome109 离线构建；日常门禁及下述增量验证。 |

真实实例：`/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`，6 批 / 15 工序；运行 `e4f3ff6fa4234ce6cc85473517303b81ff4405ce59509246`。UI 采用候选 `a4183073694ddf7705e6baf6114d3b7e5aa27aa713d37cdb`，查看基准 `93c029d9ebe40c231ae840adf473ddc330736b9d7e8ab516`。正式 v1 引用 `0d7a9dad1ccd4513a883c1f2173b7de53affc7fad74bf901`；15 道工序的永久身份、数量、起止、设备/人员/供应商及采用来源与该候选一致。

初轮原始证据：`evidence/decision-comparison-loop/aps-decision-workbench-20261013/verification.json`、同目录 decision JSON、CSV/XLSX、正式 workspace、实例身份及 `screenshots/`。初轮 `final-code-refresh.json` 记录当时服务 PID 21880。返修沿用同一库与原引用启动当时服务 `http://127.0.0.1:50387`、PID 43541；`repair-01/repair-verification.json` 保留当时身份和预览，原运行、归档和正式 v1 保留。当前接续实例见第 2 阶段 handoff。

实际验证：

- 既有候选 API、部分/stage 采用、持久化、采用来源复用回归：23 passed。
- 新 API 5 个场景、纯指标关键场景及 Node 比较契约通过；新增用例已进入 required 登记。
- `.venv/bin/python scripts/run_daily_quality_gate.py`：全仓 Ruff 通过，111 个 required 目标单进程执行，361 passed / 20 skipped（56.57s）。跳过项受 Windows 等平台条件约束。
- 门禁后 score_only 容差修正：两种选择策略与既有持久化验证 4 passed；前端对应文字的 Node 契约和离线构建通过。其余有效验证复用。
- 最后跨度/切换覆盖修正与指标目录版本进入快照：指标关键场景 7 项 + API 5 项共 12 passed（2.17s），相关 Ruff 通过；复用未受影响的整体检查。
- 用户说明书同步后，离线资产冒烟 3 passed；路线图/feature YAML、接口速查表对账和 diff 检查通过。

上述为初轮实施与增量验证记录。两项返修仅执行相关验证：

- `node tests/workbench/decision_comparison_contract.cjs`：通过；补充行表、默认常用/全部切换、搜索覆盖单处显示，并保留既有交互断言。
- `python3 scripts/workbench/build.py`：离线 chrome109 构建通过。
- `.venv/bin/python -m pytest tests/workbench/test_run_decision_api.py::test_overview_exports_require_the_screen_reference_snapshot -q`：1 passed（0.61s）。
- `.venv/bin/python -m ruff check core/services/workbench/run/decision_export.py tests/workbench/test_run_decision_api.py scripts/verify_decision_workbench.py`：All checks passed。
- 浏览器布局、全部指标/甘特回跳和标准 CSV/XLSX 读取通过，具体结果见返修证据与交接材料。原有引擎、正式采用和未受影响的日常门禁结果复用。

## 4. 术语一致性

搜索覆盖、应排工序覆盖、业务交付覆盖分别表达；待料暂缓与普通漏排分开。基准使用“查看基准”“计算时的目标最优 / 健康比较原方案”“受理时正式计划”三个清楚来源。调整按永久工序身份逐字段比较；算法加权拖期标明算法评价批次集合。

## 5. 架构归并

已实际更新 `architecture/service-scheduler.md` 与 `architecture/workbench-shell.md` 的 2026-10-13 相关入口；`开发文档/系统速查表.md` 登记服务、前端和两条 HTTP 接口。旧架构规模及历史记录保留原时间口径。

## 6. Requirement 回写

`candidate-comparison-business-view.md` 扩展为同次全部候选、任选查看基准和真实采用闭环，保留历史变更日志；VISION 将这项能力归入当前有效。`static/docs/scheduler_manual.md` 同步当前候选比较与采用步骤。

## 7. Roadmap 回写

初轮实施已回写 `decision-comparison-loop` 完成状态，两项返修已通过主对话独立复验。主对话负责阶段验收与母路线图状态；第 2 阶段已派发，第 3—8 阶段保持 planned。旧 `review.md` 保留当时方案审查记录。

## 8. Attention 候选盘点

本轮无新增长期宿主约定，沿用现有 Python 3.8 产品 / 宿主维护工具边界。

## 9. 遗留与交付边界

- 第 2—8 项继续建设逐批影响、共同班表资源、准备需求、完整推荐解释、优化过程、历史趋势及整体集成；本次交付 18 项总览和最小真实决策闭环。
- Win7 真机、边界性能和最终完整门禁按后续验收阶段验证。本轮使用 Mac / Python 3.8.10、离线 Chromium 构建与真实浏览器。
- 本轮源码、静态编译产物和记录保持未提交；提交、推送、发布按明确授权执行。`开发文档/README.md` 的既有并发改动保留原样。
- 本地 `.codestable` 新规划/feature 记录按当前 `.git/info/exclude` 规则留存；实际源码与工作台编译产物在工作区可审阅。

## 10. 主对话独立复验回执

2026-10-13 主对话确认两项 P2 关闭。实际检查 1392×924 浅深四候选、1920×1080 八候选及第八行选择；四行表底约 902px，操作区底约 525px，字号 13px / 12px。全部 18 指标→更换基准/选择→甘特→返回保留完整上下文；独立 csv / openpyxl 直接读取 72 行与 288 个核心数值格通过。主复验证据在 `evidence/decision-stage-acceptance/stage-01/repair-01/`，其正式验收记录由主对话维护。
