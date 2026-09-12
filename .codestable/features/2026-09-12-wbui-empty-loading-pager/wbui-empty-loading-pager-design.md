---
doc_type: feature-design
feature: 2026-09-12-wbui-empty-loading-pager
status: approved
summary: 统一列表状态和分页呈现
tags: [workbench, ui, accessibility]
roadmap: workbench-ui-refinement
roadmap_item: wbui-empty-loading-pager
---

# 统一列表状态和分页呈现

用户于2026-09-12授权按审查意见并行实施整个路线图。合同以路线图 implementation-20260912.md 的修订为准。

## 范围

WorkbenchListControls.EmptyState 与 Pager 提供共享样式和读屏语义；WorkbenchControls 同步附上这两个组件供既有调用方式使用。

## 已批准的实现合同

sizes 必须由领域消费者显式传入，不修改后端枚举。page 接受数字或现有 {number,pages,total,size}；cursor 模式只显示读取顺序和前后动作，不补造总数/总页。可选 showPageSelect 保留既有跳页入口；filtered/error 状态必须给恢复动作。

保持离线、Chromium109、Win7目标环境；不调整领域API、业务规则或数据。依赖清单由主线程统一登记，不在子任务构建或提交static。

## 验证

新增源代码编译与真实Chromium109控件探针覆盖核心交互，并回归受影响资源编辑器。所有证据标明源哈希；总门禁和整个工作台基线由主线程集成后执行，当前并行dirty工作区不宣称clean proof。
