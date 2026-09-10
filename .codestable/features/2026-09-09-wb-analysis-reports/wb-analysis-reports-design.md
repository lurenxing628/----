---
doc_type: feature-design
slug: wb-analysis-reports
status: implementing
created: 2026-09-09
authorization: approved-parent-roadmap
---

# 执行复盘与报表中心

- 在总体批准范围内分块交付，保持当前原型底色、连续分区和控件密度。不改领域算法、schema、计划模块、共享 transport/session 或入口/build。
- 第一块：当前正式计划保护、真实 ReportEngine/ExecutionReview 事实、公开 DTO、五专题同一计划完工日 cohort、分页排序、完整范围 CSV/XLSX。
- 旧事件只能作为只读行投影；没有独立公开事件引用或业务报工号时不编造。数量不跨事件猜测累计；有效加工工时和逐次记录完整性在现有领域缺失时为 null，并明确 partial。
- 稳定 operation_ref / task_ref / batch_ref / resource_ref 仅读既有永久身份。当前正式计划无效或引用缺失即拒绝，不 GET 补引用，不退到旧版或候选。
- snapshot_ref 绑定规范化 Scope、真实事实指纹、工厂本地 as_of；摘要/图表/表/详情/导出同快照。分页和排序不改变 cohort；更改事实或筛选时旧快照 409。
- API：GET `/api/workbench/v1/analytics`、`/analytics/export`；参数 source、plan_ref、plan_finish_date_from/to、batch_ref、resource_type/ref、query、focus、topic、page、size、sort、direction、snapshot_ref；export 还需 format=csv/xlsx，必须携带 snapshot_ref。
- 目录四报表单独明确日期含义，不将计划完工日直接冒充利用率/停机时间窗口；复用既有领域计算和文件渲染器。
- 主代理接合：注册 `register_report_routes(bp)`；加载新增 Report*.js/jsx、Review*.jsx 并将 reports/review 真实分支连接到导出的工作区。具体载入顺序与导出地址在验收记录更新。

## 验证边界

真实隔离 SQLite、候选/历史拒绝、缺身份、零写、快照失效、完整导出字节/范围、未知值与十分钟边界；mock 浏览器真实控件交互与 1920x1080 / 1392x924 浅深截图。当前 dirty 工作区只提供定点证明，不 build、不提交、不启动其他代理、不碰生产数据。
