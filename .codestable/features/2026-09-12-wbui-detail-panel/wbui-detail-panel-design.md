---
doc_type: feature-design
feature: 2026-09-12-wbui-detail-panel
status: approved
summary: 共享详情面板与焦点恢复
tags:
- workbench
- ui
- accessibility
roadmap: workbench-ui-refinement
roadmap_item: wbui-detail-panel
created: '2026-09-12'
---

# 共享详情面板与焦点恢复

用户于2026-09-12授权按审查意见并行实施整个路线图。合同以路线图 implementation-20260912.md 的修订为准。

## 范围

WorkbenchDetailPanel 输出非模态 aside region，含标题、副标题、动作和详情内容；不改变领域详情契约。

## 已批准的实现合同

消费者外容器 wb-detail-layout 实现桌面内容与右侧详情两列，低于1280宽时改一列。打开/切换detailKey聚焦标题，窄屏滚动到详情；Esc关闭后回到触发元素，若另有模态框则不抢焦点。triggerRef可显式提供原触发元素。自动首条概览可显式autoFocus=false；用户点击和准确定位恢复默认true，避免未经操作移走首屏。

保持离线、Chromium109、Win7目标环境；不调整领域API、业务规则或数据。依赖清单由主线程统一登记，不在子任务构建或提交static。

## 验证

新增源代码编译与真实Chromium109控件探针覆盖核心交互，并回归受影响资源编辑器。所有证据标明源哈希；总门禁和整个工作台基线由主线程集成后执行，当前并行dirty工作区不宣称clean proof。
