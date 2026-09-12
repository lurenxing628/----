---
doc_type: feature-design
feature: 2026-09-12-wbui-view-tabs-merge
status: approved
date: 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-view-tabs-merge
summary: 在保留15个视图身份及上下文的前提下合并计划和报表入口，通过页签与统一历史守卫切换。
tags: [workbench, ui]
---

菜单将计划三视图归入选择排产方案、报表与复盘归入报表中心，壳提供 3 项和 2 项页签。15 个 view ID 与旧 URL 保持原身份，别名仅决定菜单高亮，不重写 URL 或解析后的 navigation.view。

视图状态继续使用既有每页 history 保存机制。明确导航上下文优先于恢复值，前进/后退保持原计划、筛选、滚动与页签；页签切换不改领域请求合同。所有 SPA 退出先经过共享草稿守卫，同文档历史导航取消时恢复原历史条目后显示确认，拒绝保持旧页面及草稿挂载。

结构：壳统一管理顶级页签，工作区内部的主题页签仍归各自模块。浏览器历史守卫属于 WorkbenchNavigation，表单草稿登记及确认弹窗属于 WorkbenchGuards。测试覆盖旧 URL、带显式上下文的别名、页签高亮与历史拒绝/允许分支；主线程完成最终构建和真实页面几何验收。
