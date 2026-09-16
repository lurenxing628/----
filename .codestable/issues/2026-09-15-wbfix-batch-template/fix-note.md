---
doc_type: issue
slug: wbfix-batch-template
status: implemented
created: 2026-09-15
last_reviewed: 2026-09-15
tags: [workbench, batch, template, manual-remediation]
related_roadmap: workbench-manual-remediation
---

# 批次详情与模板更新整改

对应用户批注 14–18，以及全部删除统一垃圾桶的补充要求。仅修改批次专属界面和更新合同，没有操作真实数据库、执行全局前端构建或提交 Git。

## 实施结果

- 详情标题和返回/删除按钮分区，长编号自动换行；删除显示 `trash-2` 和“删除批次”，批量删除确认也显示垃圾桶和“确认删除”。共用垃圾桶来自共用控件条目。
- 图号、数量、批次状态和工序进度采用标签/值网格；基础信息单独成组，备注整行完整显示。计划/报工保护原因独立成行，操作列不再反复挤入长说明。
- 模板区改为“从工艺模板更新工序”，显示来源图号、名称、有效工序数及具体缺项；不再显示“存量模板”或严格模式开关。
- 更新输入使用 `{}`；旧 `strict_mode: true` 兼容，旧 `false` 明确返回 `template_validation_required`。所有更新统一检查工序号、归属、工种、自制工时、适用外协周期和供应商。空值保留为空，合法 0 不改写。
- 详情和更新预览共用 `template_status` 完整性结果。旧模板仍可按实际完整资料使用；已经进入新确认流程的模板继续遵守原工作流状态，不伪造旧确认记录。
- 预览新增 `completeness_checked`、`changes`、`change_counts`、`cleared_resources`：逐工序展示新增/删除/修改及前后内容，列出实际将清掉的设备和人员指定。自制工时与外协周期按适用归属显示。
- 确认仍在原命令事务中检查快照并重验，原子替换工序；已有计划、报工或执行状态的批次继续禁止重建。详情现在为删除、替换、工序编辑分别提供真实禁用原因。

## 源码范围

- `frontend/workbench/app/BatchDetail.jsx`、`BatchForms.jsx`、`BatchContract.js`。
- `BatchWorkspace.jsx` 仅修改本条的 `onSync` 请求签名；该文件其他改动由共用控件条目处理。
- `frontend/workbench/app/styles/31-batches-resources.css` 仅新增 `.batch-workspace` 作用域规则；资源区并行改动属于人员设备条目。
- `core/services/workbench/batch_operations.py`、`batch_template_validation.py`、`batch_queries.py`，新增 `batch_template_preview.py`。
- `web/routes/workbench/batches.py` 的批次能力及禁用原因投影。
- 对应批次动作、模板更新、边界、组件测试；现有 batch ledger 和 template lineage 测试的更新请求改用新合同。

## 验证

2026-09-15，全部在临时 SQLite 或显式组件 mock 中完成：

1. 批次 actions、commands、execution ledger guards/boundaries/atomic/projection、files、round1 boundaries、transport、process batch gate，连同新增模板更新测试：143 passed。之后新增三条缺项入口测试，最终 actions + template updates：15 passed。
2. 模板来源 writes/integrity/calibration 联动与新增模板更新：41 passed。此集合与上面的测试有重叠，不能相加宣称唯一用例总数。
3. 最新故障注入在删除旧工序并成功写入第一道新工序后，让第二道复制抛错；批次工序、引用、来源事实及数据库状态全部回滚，15 passed 中包含此验证。
4. Chrome 109 显式组件 mock 覆盖 1392×924、1366×768、1280×720 浅深主题，共 66 场景和 66 截图；包括长编号/长备注、禁止更新、模板缺项、取消和确认、查询/写入草稿保留。共用控件和资源样式冻结后，最终重跑 `tests/workbench/test_batch_widgets.py`：1 passed in 51.83s，66 场景和 66 截图全部通过，浏览器无脚本错误/外部请求，全部参与源码的当前 SHA-256 与编译快照一致。最终证据在 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-batch-widgets-urkyl2n0/batch-result.json`；已目视核对长字段/受保护批次和更新预览截图。早一轮曾因并行修改导致末尾源哈希不一致，未把那次作为当前快照通过证明。
5. `git diff --check` 对本条修改路径通过。未运行全局 build 或全项目质量门禁。用户随后明确禁止本轮运行全门禁；整合后仅执行相关专项及真实业务手动验收，不调用 `run_quality_gate.py` 的任何模式，也不运行整仓测试。

## 验收边界

本工作区原有大量未提交改动；本条结论是实际工作快照的局部验证，不是 clean-worktree proof。后续整合验收需在隔离测试实例中手动验证工艺修改→批次更新预览→取消/确认→刷新回读，以及主任务的全页面、高压排产和数据库恢复流程。
