---
doc_type: feature-design
feature: 2026-09-12-wbui-field-validation
status: approved
summary: 共享字段校验与禁用原因
tags:
- workbench
- ui
- accessibility
roadmap: workbench-ui-refinement
roadmap_item: wbui-field-validation
created: '2026-09-12'
---

# 共享字段校验与禁用原因

用户于2026-09-12授权按审查意见并行实施整个路线图。合同以路线图 implementation-20260912.md 的修订为准。

## 范围

ResourceControls.Field、focusFirstInvalid 与 ErrorBox 显式字段路径排除；ResourceForms 消费共享 Field，错误渲染后聚焦首个可见无效字段。保留原控件 id、aria-describedby、aria-required。Choice 的关系字段统一标注。Button 默认 reasonDisplay=inline 展示并关联禁用原因；显式title模式只用于同处已有可见说明的调用。

## 已批准的实现合同

字段错误通过 APSResourceContract.fieldErrors 的 error.fields/error.error.fields 提取；input. 路径前缀归一。Field 已展示路径必须显式传 ErrorBox/Feedback.excludePaths，未知路径保留在摘要。ResourceForms 编辑草稿使用 WorkbenchGuards owner，三个关闭入口和取消按钮均确认；locked 仍先阻断。

保持离线、Chromium109、Win7目标环境；不调整领域API、业务规则或数据。依赖清单由主线程统一登记，不在子任务构建或提交static。

## 验证

新增源代码编译与真实Chromium109控件探针覆盖核心交互，并回归受影响资源编辑器。所有证据标明源哈希；总门禁和整个工作台基线由主线程集成后执行，当前并行dirty工作区不宣称clean proof。
