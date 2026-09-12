---
doc_type: feature-design
feature: 2026-09-12-wbui-nav-boot-groups
status: approved
date: 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-nav-boot-groups
summary: 导航元数据由原型常量转到呈现层启动信息
tags:
- workbench
- ui
created: '2026-09-12'
---

导航元数据由原型常量转到呈现层启动信息。值班台置顶，资料入口同组，生产壳读取 `nav_groups` 和 `view_aliases`；支持的 15 个视图与 12 个可见菜单项分开，不删除领域查询入口。

启动信息校验拒绝重复菜单、未知视图、缺失别名、无效图标和标签漂移。测试独立锁定支持视图及核心菜单，另验证真实菜单与 boot 顺序一致。无数据库读写、无新增运行时依赖。

结构：导航元数据从 pages 拆入独立 Python 呈现模块，页面函数只装配 boot。前端导航仍由 WorkbenchNavigation 管上下文和浏览器历史，壳负责呈现。移除本功能时移除 boot 元数据及对应壳消费者即可，领域服务不变。

验收须绑定最终源码/build_id，菜单改动覆盖所有视图，旧迁移截图不可自动复用。使用已批准的 implementation-20260912.md 合同；路由与共享守卫并行集成后再完成实际浏览器验收。
