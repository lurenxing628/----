---
doc_type: audit-index
audit: 2026-05-21-networkx-full-browser-stress
scope: APS 全系统浏览器重度压测、NetworkX/关键链结果核对、前端问题记录
created: 2026-05-21
status: open
total_findings: 7
---

# NetworkX 全系统浏览器重度压测记录

## 结论

本轮使用临时库和临时服务做压测，没有直接写仓库业务库。浏览器保持可见，至少完成了 11 次真实页面手工新增/提交操作，并补充了批量表单、Excel 上传检查、排产、结果页、报表和系统管理链路。

已确认 7 个问题，并已追加子代理并行根因追踪。最需要优先修的是甘特图短任务条无法正常拖拽、分析页计算模式显示成“快速模式”、资源排班日期参数不生效、报表超期查询漏版本批次范围、缺资源报错只显示内部编号。

补充：甘特图短任务问题已在 2026-05-21 追加 4 个子代理并行追根因。交叉结论是：v15 这两条工序后端排程时间正常，API 合同也带了真实 `duration_minutes`；问题出在前端把任务交给本地 Frappe Gantt 后，Frappe 在 Day 视图用“整小时向下取整 + 38px/天”计算条宽，导致 36 分钟、51 分 36 秒这类任务被画成 0px，长文字只是标签，不是可拖拽条。详见 [finding-05-gantt-short-task-zero-width.md](finding-05-gantt-short-task-zero-width.md)。

补充：2026-05-21 又追加 7 个子代理，把全部 7 个问题逐项追到调用链、关键变量和最小修复点。子代理均已关闭；浏览器和服务进程未关闭。

## 临时环境

- 服务地址：`http://127.0.0.1:61661/`
- 临时库：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/aps.db`
- 日志目录：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/logs`
- 备份目录：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/backups`
- 浏览器证据：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts`
- 浏览器辅助页服务：`http://127.0.0.1:61662/`

## 压测数据规模

只读 SQL 复核结果：

| 类型 | 数量 |
|---|---:|
| 工种 | 10 |
| 供应商 | 3 |
| 班组 | 3 |
| 人员 | 7 |
| 设备 | 8 |
| 人机关联 | 17 |
| 零件路线 | 6 |
| 路线工序 | 19 |
| 物料 | 4 |
| 批次 | 130 |
| 批次工序 | 621 |
| 批次物料需求 | 6 |
| 工作日历 | 3 |
| 个人日历 | 3 |
| 设备停机 | 5 |
| 排产历史版本 | 15 |

说明：工种数量包含后补的 Excel 链路压测工种 `XLS-QA-CUT`。

## 真实页面手工操作

至少 11 次真实 APS 页面表单操作已完成：

1. 工种页新增 `MAN-TURN / 手点数车`。
2. 工种页新增 `MAN-OUT / 手点外协`。
3. 供应商页新增 `SMAN-OUT / 手点外协供应商`。
4. 班组页新增 `TMAN-A / 手点A班`。
5. 人员页新增 `OPMAN-A / 手点员工A`。
6. 设备页新增 `MCMAN-T1 / 手点数车设备1`。
7. 设备详情页新增 `MCMAN-T1 -> OPMAN-A` 人机关联。
8. 设备详情页新增 `MCMAN-T1` 停机。
9. 物料页新增 `MAT-MAN-1 / 手点钢料`。
10. 零件路线页新增 `PMAN-1 / 手点双工序件`。
11. 批次页新增 `BMAN-1` 并生成 2 道工序。

## Excel 链路

已对“工种配置”跑通一条真实 Excel 链路：

- 打开 `/process/excel/op-types`。
- 触发模板下载入口 `/process/excel/op-types/template`。
- 上传临时 Excel：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/excel-optypes-qa.xlsx`。
- 检查结果页显示新增行后，点击“确认写入系统”。
- 触发导出入口 `/process/excel/op-types/export`。
- 只读 SQL 复核新增了 `XLS-QA-CUT / Excel链路压测切割`。
- 操作日志记录了模板导出、导入预览、确认导入、导出。

## 排产版本和关键链

| 版本 | 类型 | 数据规模 | 关键结果 |
|---|---|---:|---|
| v1 | 模拟 | 36 批 / 116 工序 | 图分析可用，采用原算法 |
| v3 | 模拟 | 1 批 / 2 工序 | report 模式可见 |
| v4 | 正式 | 36 批 / 116 工序 | 正式排产成功 |
| v5 | 模拟 | 36 批 / 116 工序 | 90 秒上限，8 个候选全部算完，采用原算法 |
| v8 | 模拟 | 9 批 / 24 工序 | 关键链方案胜出 |
| v9 | 模拟 | 80 批 / 480 工序 | 90 秒上限，8 个候选全部算完，采用原算法 |
| v10 | 模拟 | 80 批 / 480 工序 | 1 秒上限触发，完成 1 个候选、跳过 7 个候选 |
| v12 | 模拟 | 80 批 / 480 工序 | 90 秒上限，实际约 29.7 秒，8 个候选全部算完 |
| v13-v15 | 模拟 | 9 批 / 24 工序 | 连续 3 次关键链方案胜出 |

关于“90 秒没有用满”：本轮验证到上限是“最多允许算多久”，不是“必须算满多久”。v10 把上限降到 1 秒后，系统确实只完成了原算法并跳过 7 个候选；v9/v12 把上限改回 90 秒后，候选全部完成，因此不会继续空跑到 90 秒。

## 页面覆盖

- 首页、导航、主题/密度、帮助入口。
- 工艺管理：工种、供应商、零件路线、路线解析、工时维护、Excel 批量维护入口。
- 人员设备：人员、班组、设备、人机关联、个人日历入口、设备停机、Excel 批量维护入口。
- 物料管理：物料、批次物料需求、齐套相关提示。
- 排产链路：批次新增、生成工序、批次详情补资源、模拟排产、正式排产、失败边界。
- NetworkX/关键链：off/report/on、候选方案对比、自动择优、PR-8 资源匹配报告。
- 结果页：设备甘特图、人员甘特图、周计划、资源排班、优化分析、报表、历史。
- 系统管理：备份、操作日志、排产历史、界面模式入口。

## 已确认问题

| # | 严重程度 | 类型 | 标题 | 文件 |
|---|---|---|---|---|
| 1 | 明显影响使用 | 配置/启动信息错误 | 运行端口文件写成 5000，但实际服务在 61661 | [finding-01-runtime-port-file-mismatch.md](finding-01-runtime-port-file-mismatch.md) |
| 2 | 明显影响使用 | 文案难懂 | 缺资源报错只给内部工序编号，不告诉调度员是哪一批哪道工序 | [finding-02-missing-resource-message-op-id-only.md](finding-02-missing-resource-message-op-id-only.md) |
| 3 | 明显影响使用 | 页面展示错误 | 深度优化已开启，但分析页显示“计算模式：快速模式” | [finding-03-analysis-mode-display-mismatch.md](finding-03-analysis-mode-display-mismatch.md) |
| 4 | 轻微但建议修 | 文案难懂 | 分析页直接使用 `ready` 英文术语，调度员不容易理解 | [finding-04-analysis-ready-wording.md](finding-04-analysis-ready-wording.md) |
| 5 | 明显影响使用 | 前端交互/排版 | 甘特图短任务真实条宽为 0 或极窄，文字看得到但不能正常拖拽 | [finding-05-gantt-short-task-zero-width.md](finding-05-gantt-short-task-zero-width.md) |
| 6 | 明显影响使用 | 数据筛选/交互错误 | 资源排班页面忽略 `start_date/end_date` 查询参数 | [finding-06-resource-dispatch-date-query-ignored.md](finding-06-resource-dispatch-date-query-ignored.md) |
| 7 | 明显影响使用 | 数据口径不一致 | 报表中心超期查询从全量批次起步，漏了版本批次范围 | [finding-07-report-overdue-version-scope-inconsistent.md](finding-07-report-overdue-version-scope-inconsistent.md) |

## 根因追踪状态

| # | 根因结论 |
|---|---|
| 1 | 开发重载子进程复用父进程 61661 socket，却重新 `pick_port()` 并把 5000 写进运行契约。 |
| 2 | SGS 评分阶段抛缺资源异常时只用了 `meta["op_id"]`，没有把已存在的批次、工序、工种和缺失字段写进 `details.user_message`。 |
| 3 | 候选比较内部把候选 `algo_mode` 改成 `greedy`，摘要同时保留 `config_snapshot.algo_mode=improve`；分析页误读 `algo.mode`。 |
| 4 | 分析页 viewmodel 把算法内部 `ready` 术语直接拼进前台文案，模板只是展示。 |
| 5 | Frappe Gantt 在 Day 视图按整小时向下取整算宽度，短工序真实可拖条宽为 0 或极窄。 |
| 6 | 资源排班入口虽读到 `start_date/end_date`，但默认 `period_preset=week`，没有进入自定义日期范围。 |
| 7 | 超期报表 SQL 从全量 `Batches` 起步，只过滤排程行版本，未限制到该版本或候选方案涉及的批次。 |

## 暂未执行或不建议执行的项

- 恢复备份没有实际点击执行。原因：用户要求保留当前浏览器和临时服务现场继续批注，恢复会覆盖当前临时库，影响批注环境。
- 没有做源码修复，也没有提交代码。本轮任务是浏览器压测和问题记录。
- 没有跑仓库质量门禁。本轮没有改业务源码，主要验证方式是浏览器操作、只读 SQL、截图和操作日志。

## 关键证据文件

- 分析页截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/analysis-v15-visible.png`
- 甘特图截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/gantt-current-after-user-comment.png`
- 资源排班截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/resource-dispatch-machine-v15-query-ignored.png`
- 报表中心截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/reports-latest-v15-overdue-mismatch.png`
- Excel 预览截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/excel-optypes-preview-xlsqa.png`
- 备份页截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/system-backup-after-create.png`
