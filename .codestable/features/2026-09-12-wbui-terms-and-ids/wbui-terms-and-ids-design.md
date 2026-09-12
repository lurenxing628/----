---
doc_type: feature-design
feature: 2026-09-12-wbui-terms-and-ids
status: approved
summary: 用统一术语和折叠编号呈现保留业务说明及完整查证入口。
tags: [workbench, terminology, ui]
roadmap: workbench-ui-refinement
roadmap_item: wbui-terms-and-ids
---

# 统一术语和内部编号

## 0. 术语与依据

用户已批准路线图默认词表：预计超期批次、超期时长、总拖期、利用率、候选方案、正式计划、试调以及 actions 中的新增/保存/确认/取消/清除/导入/导出/下载。相同字段含义采用相同词，不按字符串同名合并不同业务概念。

## 1. 目标与范围

新增 `WorkbenchTerms.js` 和 `WorkbenchReferences.jsx`。内部引用、请求键和技术错误可折叠查证，不在业务正文显示。复杂度为共享前端呈现组件；不更改 API、请求身份、业务批次编号或原错误对象，各工作区由其 owner 接入。

## 2. 接口、流程与挂载点

现有正文多处直接输出 `*_ref`、`request_key` 与错误码。变更为：

- `window.WorkbenchTerms` 为冻结的默认词表，字段与路线图一致。
- `window.WorkbenchReference({value, entries, label='编号'})`：`entries` 为标签到原值的映射，`value` 为单个编号；输出默认关闭的 `details.wb-ref`，保留完整编号可选择复制。空输入不显示空折叠框。
- `window.WorkbenchError({error, fallback, fields=[], excludePaths=[]})`：普通业务说明保持可见；包含技术码、HTTP 状态、JSON、异常类或长内部引用的原始消息进入编号折叠框，正文提供可行动的 fallback。字段错误按 path 排除并按 message 去重；错误 code/status/request 等已知诊断一并保留。

流程：业务说明和错误对象 → 呈现分类 → 用户说明正文 + 默认关闭的完整编号查证入口。以 React 文本节点渲染，不插入 HTML，不修改错误对象。

例如 `<code>{row.run_ref}</code>` 改为 `<window.WorkbenchReference entries={{'运行编号': row.run_ref}}/>`；批次号 `B20260912` 仍为正常业务文本。构建顺序在 ResourceControls 和各消费者之前。

## 3. 验收契约

- 默认 DOM 文本将长引用和技术码限制在 `details.wb-ref` 后代；展开后原值完整保留。
- 用户业务错误不消失，字段级错误不重复；被遮蔽的技术消息保留查证入口。
- 不改变原始 error 或 API 写入标识；词表冻结。
- 独立组件合同通过；各域 G6 与统一浏览器证据由主线程合并，不能用独立测试冒充全工作区通过。

## 4. 文档与验证边界

此 feature 独占共享词表、编号组件、独立测试和本目录文件，不批量改其他代理持有的业务 JSX。详细消费者迁移清单随 acceptance 记录。
