---
doc_type: feature-acceptance
slug: wb-analysis-reports
status: partial-delivery
created: 2026-09-09
agent: K
---

# K 本域交接

## 结论

已交付当前正式计划的真实复盘/五专题读 DTO、同范围 CSV/XLSX、四种目录报表、两个可操作工作区及局部验证。不是全站接线或整个 wb-analysis-reports 最终完成：入口/build 由主代理接合，逐次报工领域投影未到位，因此累计数量、剩余数量、有效加工工时和业务报工号仍明确未知/不可用。

此次未修改 ReportEngine、calculations、execution_review、overdue、scheduler 算法、plan 模块、schema、resource-api/session、main.jsx、构建清单、全局 __init__。没有访问生产数据库、外联、build、commit 或启动其他代理。全部本轮源码是新增未跟踪文件，保留原有并行脏改。

## 主代理接合

1. 在共享入口注册 `from .reports import register_report_routes` 和 `register_report_routes(bp)`；它会同时注册目录路由。K 没有改现有注册文件。
2. 既有 `APSWorkbenchUI`、`APSResourceAPI`、`APSResourceContract`、`ResourceControls` 加载后，按以下顺序加入现有构建/加载表：

```text
ReportAPI.js
ReportControls.jsx
ReportTable.jsx
ReportDetail.jsx
ReviewChartViews.jsx
ReviewCharts.jsx
ReportCatalog.jsx
ReportWorkspace.jsx
ReviewWorkspace.jsx
```

3. reports/review 真实分支分别挂 `window.ReportWorkspace` / `window.ReviewWorkspace`。参数：`onNav(view, context)`、`initialContext`；可选 `onOpenOperation(operation_ref, scope_and_snapshot)`。未提供工序外部导航时该入口带原因禁用，内嵌真实工序详情可用，不猜 task/batch 对象。
4. 保留原型现有 `report-workbench.css`、`execution-review.css`、`execution-analysis-shared.css`；本轮没有新底色、全局 CSS 或新外部依赖，也不依赖样例执行分析模型。图表展示层使用既有 aw-* 样式。
5. `initialContext` 的 scope、topic、snapshot_ref、table、selected、chartsOpen、catalogOpen、scroll、returnTo 用于往返恢复。跨页不得将 demo/current、candidate 或旧字段名悄悄改成 production；不支持的范围字段明确拒绝。

## 路由与响应

| GET 地址 | 用途 |
| --- | --- |
| `/api/workbench/v1/analytics` | 五专题与复盘共用读取 |
| `/api/workbench/v1/analytics/operations/<operation_ref>` | 当前 Scope 内工序及其旧事件详情 |
| `/api/workbench/v1/analytics/export` | 同一 Scope 全筛选 CSV/XLSX，不是当前页 |
| `/api/workbench/v1/reports/<kind>` | kind=overdue/utilization/downtime/official-review |
| `/api/workbench/v1/reports/<kind>/export` | 目录同范围导出；official-review 为现有 Excel |

analytics 参数：source=production、plan_ref（省略仅选择当前版本，绝不退旧）、plan_finish_date_from/to、batch_ref、resource_type=machine/operator、resource_ref（可明确 unassigned）、query、focus、topic、page、size=10/20/50、sort、direction、snapshot_ref。导出需 format=csv/xlsx 和 snapshot_ref；详情与第 2 页起必须带 snapshot_ref。as_of 由服务端快照确定，不允许客户端任意指定。

focus=all/unreported/unclosed/late_open/finish_late/complete/data_gaps。topic=delivery/records/machines/people/quality；sort 以 `core/services/workbench/report_queries.py:SORTS` 为准。

成功响应沿用 `ok/schema_version/data/meta/warnings`；meta 含 source=production、time_basis=factory_local、as_of、snapshot_ref、request_ref。data 包含 plan、scope、topic、provenance、rows、columns、summary、page、charts、resources、choices、capabilities、data_gaps、exports；工序详情另有 detail。目录响应按其真实字段返回 rows/columns/summary/page/provenance/data_gaps，不冒充实际工时。

下载响应：真实 CSV 或 XLSX MIME、Content-Disposition 文件名，以及 `X-Workbench-Snapshot`、`X-Workbench-As-Of`、`X-Workbench-Row-Count`。CSV 每行保留数据时点、快照、Scope、来源和缺口；XLSX 的范围说明页与表格同快照。空范围明确 empty_export；超既有导出限额 export_too_large，不截断或假称已启动后台任务。

目录的 utilization/downtime 独立使用 window_date_from/to（缺省显示正式计划窗口），按计划时段交集；overdue 是全部计划批次及其风险。不接受把 analytics 的计划完工日期参数直接挪用；official-review 则沿用 analytics 的工序 cohort 与快照。

## 事实与能力边界

- 正式读取仍经现有计划查询身份、ReportEngine.execution_review 和 ExecutionReviewMixin；拒绝 candidate、scenario、历史非当前和 latest failed/partial，不用其他方案冒充实际。
- operation_ref/task_ref/batch_ref/resource_ref 只读已有永久身份；缺失即失败，GET 不补建。普通 DTO 不含 op_id/schedule_id/candidate_id/scenario_id/source_table/revision 等内部定位字段。
- 旧事件没有独立公开报工引用；rows 中 projection_index 只是只读显示行序，不是数据库 ID 或业务报工号。report_ref/report_no 为 null，记录来源明确 legacy_event/现场事件。
- 旧合法 finish 保持整道完成；仅有 start 不算完成。事件登记 quantity_done 不跨事件累加，跨度不填有效工时。未来完成时间标 invalid，不计已确认完工；旧 Excel 同样不将其标成已确认。
- 完工日期选中的工序，其所有关联事件一起进入统计；资源筛选匹配计划或已发生的实际资源。到期工序完成率分母不是批次；延后 10 分钟整仍按时，10 分钟 1 秒为晚完。
- unknown 不当 0；partial 并非最终能力验收通过。待领域逐次报工上线后，需要继续接 report_ref、可核对累计数量/剩余量、有效工时、修订链和对应真实图表，不把旧事件包装成这些能力。

## 已执行验证

运行环境：macOS；仓库 `.venv/bin/python` 实测为 **Python 3.8.10**。目标浏览器为实装 **Chromium 109.0.5414.46**。没有 Win7 真机或最终冻结包证明。

```text
.venv/bin/python -m pytest tests/workbench/test_report_read.py tests/workbench/test_report_export.py tests/workbench/test_report_boundaries.py tests/scheduler_analysis/test_plan_vs_actual_review.py tests/operation_execution/test_execution_review_identity_guard.py tests/scheduler_analysis/test_report_export_size_mode_selection.py tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py -q -x
73 passed in 14.49s
```

其中 50 项为本域新增测试，23 项为现有领域回归。覆盖真实 SQLite、query_only、iterdump 前后相同、稳定引用与重启、当前正式保护、计划完工日与时段交集区分、实际资源关联、无反馈、合法完工、未来事实、十分钟边界、Scope/事实/时间快照、分页与全量导出、CSV/XLSX payload、空范围/容量拒绝、公式文字和 Python 3.8 语法。

本轮新增 Python 文件 Ruff 检查全部通过。`tests/workbench/report_api_probe.cjs` 通过，确认沿已有 transport.query、仅 GET、未知范围/候选响应/缺数值失败、无新增写 namespace。

浏览器证据明确为 **mock 交互**：先用临时真实 SQLite 抓取 DTO 和导出字节，再由专用 mock HTTP 服务驱动组件；不是已完成全站真实后端浏览器接入的证明。新 JSX 仅在测试进程内用仓库固定 Babel 转译，没有发布构建资产。

四组：1920x1080、1392x924，各 light/dark。包含页签键盘切换、分页、筛选、详情、全 23 行下载（当前页 10 行）、过期快照失败/重读、目录切换、复盘导航与图表。24 张截图；无页面异常、无外部请求；额外验证页面不横向溢出、控件可见且边界有效、根工作区背景保持透明。故意注入的 snapshot_stale 为预期失败用例。

产物：`/tmp/workbench-report-k-visual/report-ui-result.json`、同目录 24 张 PNG 与 4 份 CSV。最终代表截图已目视核对：1392-dark-reports.png、1392-light-catalog.png、1392-light-detail.png、1920-dark-charts.png。

## 剩余验证

- 主代理完成入口/加载接合后，仍需在隔离全站实例做真实 API + 浏览器端到端读回，尤其检查全局导航对 context/returnTo 的传递。
- 当前目录明显 dirty 且多人并行，不运行会刷新共享产物的全量质量流程；没有最终 HEAD / clean-worktree proof。此次只有明确列出的局部验证，没有提交。
- 主代理继续执行总体路线图的完整领域能力、复杂容量、Win7 真机和最终发布门禁；本批不缩小该分母。
