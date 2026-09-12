---
doc_type: feature-design
feature: 2026-09-12-wbui-table-density-noise
roadmap: workbench-ui-refinement
roadmap_item: wbui-table-density-noise
status: approved
summary: 表格共享舒适与紧凑密度，保留未知语义并减少重复信息
tags: [workbench, ui, density]
---

用户已批准路线图及2026-09-12审查修订。现状是各表行距和系统页compact状态独立维护；变化为`WorkbenchDensity`统一`aps_density`偏好与`html[data-density]`，共享CSS只调整单元格内边距，不改变字号、业务数据、列范围和分页。

顶栏提供全局切换；系统原密度入口同步同一状态。读取/写入偏好失败明确提示，已生效的当前会话密度不伪称已持久保存。未知存储值回到舒适并显式报错。跨窗口storage事件同步。

报表只有整个当前范围没有现场数据时使用统一横幅，部分缺失仍按行保留未知与可追查说明；现场记录移除重复统计，不移除业务状态。页面owner分别实施，公共模块不读取领域数据。

挂载点：显式构建清单、main/System密度入口、00-tokens与20-controls表格规则。删除模块和这些挂载点即可恢复原呈现；不涉及持久业务事实。结构健康度：密度职责独立，新模块仅处理偏好，不向theme或业务模块塞无关状态。

验收：舒适/紧凑来回切换只改变行距；刷新保留；两入口同步；无效值和存储失败可见；密度变化后操作列可点击；部分未知不能被全局横幅误判为全无。
