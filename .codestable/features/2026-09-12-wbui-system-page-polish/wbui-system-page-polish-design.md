---
doc_type: feature-design
slug: wbui-system-page-polish
feature: 2026-09-12-wbui-system-page-polish
status: approved
created: 2026-09-12
summary: 系统自检折叠、显示格式和恢复维护页的保守呈现收口。
tags: [workbench, system, ui]
roadmap: workbench-ui-refinement
roadmap_item: wbui-system-page-polish
---

# 系统管理呈现收口

依据已批准 implementation-20260912.md 实施。页面环境自检默认折叠，导出按钮使用“导出诊断文件”；checkedAt 明确使用 instant 转本机时区，服务 DTO 的 factory_local 使用 dateTime。系统列表接共享 Pager（仅 10/25/50）、EmptyState、技术编号折叠与可见禁用原因，表格补 caption/scope。只将静态系统样式迁至 styles/37-system.css。

恢复页区分“无法读取维护状态”和已证实暂停；原请求、错误码及指纹可在 details 内核对。增加返回工作台链接，仍由现有维护守卫决定能否开放业务界面。保留 pending 标记、原请求查询、禁用业务读写、只读维护导出及整个软件重启语义；不改维护 API、数据库或恢复流程。

验收包括源文件编译、describe 状态合同、真实冷启动只读页面/维护记录测试、隔离系统组件交互测试。最终 static 构建及统一浏览器几何/门禁由主线程绑定 build_id，本分支不构建或提交主工作区。
