---
doc_type: feature-design
feature: 2026-09-12-wbui-header-controls
status: approved
date: 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-header-controls
summary: 顶栏显示本机实例标签、动作语义主题按钮和帮助链接
tags:
- workbench
- ui
created: '2026-09-12'
---

顶栏显示本机实例标签、动作语义主题按钮和帮助链接。帮助 `help_url` 复用现有 `/scheduler/config/manual`，不新增手册路由或复制渲染逻辑；有草稿时先确认再离开。排产历史等已由 navigation context 明确标记的子页同步更新标题。

结构保持壳统一管理全局控件，新增专属 CSS 文件承载布局，禁止向 JSX 增加 style。主题偏好及手册下载、返回上下文沿用既有服务合同。共享 GuardHost 挂在随 view 重建的容器外，待守卫模块集成后锁定导航取消不丢草稿。

验收检查两种主题动作名称、实例文本、只读手册可达和历史子页标题。菜单/顶栏会影响全站截图与旧主题选择器，最终证据按实际 build_id 重新绑定。
