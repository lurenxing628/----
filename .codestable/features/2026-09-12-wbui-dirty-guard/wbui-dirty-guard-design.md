---
doc_type: feature-design
feature: 2026-09-12-wbui-dirty-guard
status: approved
summary: 对导航、历史切换和编辑器关闭统一保护未保存内容，保留待核实请求
tags: [workbench, frontend, reliability]
roadmap: workbench-ui-refinement
roadmap_item: wbui-dirty-guard
---

# 草稿离开保护

批准依据：`../../roadmap/workbench-ui-refinement/implementation-20260912.md` 第 3 条；用户已授权并行实施。

- `WorkbenchGuards` 按 owner 登记纯前端草稿与已有命令锁定；不存储表单、业务事实或请求。
- `useDirtyGuard({owner?, dirty, message, locked?})` 返回稳定 owner；`register` 返回注销函数；`hasDirty({owner?,excludeOwners?})` 包含锁定；`confirmLeave` 同参数返回 Promise<boolean>。
- 全页导航检查全部 owner，弹窗或取消只检查对应 owner。确认框展示全部受影响草稿。锁定请求只能留在当前页面。未改动无需确认。一个确认未结束时后来的请求返回 false，不能批准多个动作。
- `WorkbenchGuardHost.jsx` 在页面切换重建范围外挂载，并 portal 到 body；核心 `WorkbenchGuards.js` 不依赖 `ResourceControls`，保持构建依赖无环。确认框通过 `ResourceControls.Modal guardBypass` 免递归。Modal 确认后向 onClose 传 `{guardConfirmed:true,guardOwner}`，footer 回调可识别同 owner 已批准，避免双确认。
- `leaveExternal(navigate)` 确认全部 owner 后只放行本次外部离开；许可消费一次或下一个任务自动失效，登记变化立即撤销；不清空草稿注册，不屏蔽之后的 beforeunload。
- shell navigate 和 popstate 由导航 owner 实施：历史先回到旧条目保持组件、URL 与草稿，再确认并重放；取消保持原状态。所有外部离开通过 beforeunload 提醒（浏览器原生能力无法强制阻止用户关闭）。
- Process 保留现有多阶段草稿、文件导入丢弃确认和请求核实保护；Trial 仅将未提交的工序编辑和新建/命名表单列为脏内容，已持久保存的试调草稿不误报。

验证：共享守卫干净/多 owner/作用域/待核实/取消/确认/并发/外部离开；真实 React Modal 的取消、Esc、确认不递归与焦点；现有 Process/Trial 受影响合同；导航集成由导航 owner 验证。基线构建和总门禁由主线程补齐，不把模拟适配器或 dirty 工作区结果称为 clean proof。
