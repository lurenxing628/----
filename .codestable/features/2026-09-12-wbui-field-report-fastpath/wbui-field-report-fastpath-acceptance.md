---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-field-report-fastpath
status: "completed-with-validation-limit"
summary: "报工建议、复制与保存继续路径及回执和新上下文边界实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- ui
- execution
roadmap: workbench-ui-refinement
roadmap_item: wbui-field-report-fastpath
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

## 1. 接口契约核对

- `FieldDraftModel.js:8` 的上一条只从同任务、同工序且具有有效实际结束的当前报工取值；新建才生成可见建议，补齐、更正、legacy、retained 均保留原始未知。
- `FieldContract.js:62` 的输入仍只接受业务字段白名单，清空时间仍写 `null`，零值仍为 `0`；新增本地字段错误与后台既有时间顺序、有效工时跨度规则一致。
- `FieldDraftModel.js:29` 复制不带报工、任务、工序、版本、请求键或旧 `write_context`，保留当前用户自行填写的声明人。
- 领域 API、后端分页档位、台账规则和存储结构未改。现场分页仍是 10/20/50/100。

## 2. 行为与决策核对

`FieldEditor.jsx` 在终态 `committed/unchanged` 后请求自动重读；`FieldWorkspace.jsx:59` 清除已保存草稿、刷新当前明确任务；`FieldDetail.jsx` 等新详情成功，才交 `FieldDraftModel.continuation` 检查身份、新 token、create 能力和未完工状态。pending 不重置原命令；重读失败、旧 token、不可写及任务变化不打开下一张。

当前任务与其他临时保留草稿分别注册 Guard scope；取消当前任务只丢当前草稿，导航/前进后退/外部离开由主外壳统一查全部 scope。表单关闭只使用 guard 确认，未绕过 pending 锁。

截图复核发现把 FieldDetail 留在任务表 tbody 会令编辑器受列表高度预算裁切。最终已将详情移到表格与分页之后，打开编辑器自动滚入视口；未更改对象选择、请求身份或报工数据流。

## 3. 验收场景核对

- `node tests/workbench/test_field_fastpath.cjs`：8 组合同通过，11 个 Field 脚本以 Chrome 109 目标编译通过。
- `.venv/bin/python -m pytest tests/workbench/test_field_workspace_api.py tests/workbench/test_field_files_api.py tests/workbench/test_field_files_codec.py -q`：26 passed in 29.76s。
- `tests/workbench/field_fastpath_browser.cjs`：Chrome 109.0.5414.46、独立临时 Flask/SQLite，7 场景通过：建议清空保持台账 null；补齐无新默认且聚焦错误；保存继续取得不同 token/request_key；多任务缓存和明确取消；双尺寸双主题滚动/caption/scope；pending 不新写；确认后重读失败及旧 token 不开新草稿。
- 最新证据：`/tmp/aps-wbui-field-fastpath-20260912-12/field-fastpath.json`。同目录 4 张尺寸主题截图、`field-editor-suggestions.png` 和 `field-editor-validation.png` 已人工查看。
- 源码由组件探针独立编译，JSON 保存各脚本与 CSS 的 SHA-256。沿用的静态基础构建为 `02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`；这不是最终整站 UI 构建的通过证据。
- 早期 8–10 轮重试在并行优化器文件替换窗口出现导入缺项，未启动服务器；源文件恢复后第 11/12 轮通过。未修改优化器来绕过错误。

## 4. 术语一致性

日期与工时接 WorkbenchFormat；显示未知统一为“未知”，补齐动作说明仍保留“待补”的业务含义。候选、试调引用 WorkbenchTerms。报工内部引用移到历史的 WorkbenchReference 折叠块。三个表均有 caption 与列 scope；输入、清空、复制、分页均有明确名称。

## 5. 架构归并

仅新增 FieldDraftModel、FieldEditorFields 和域 CSS；主线程负责统一前端架构文档，建议登记“任务详情不受列表滚动框约束、报工下一张草稿受回执和新上下文双条件保护”。本子任务不并发改中央架构。

## 6. Requirement 回写

需求属于已批准 UI 路线图，领域报工能力未扩展。主线程汇总前端便捷路径与无损边界后统一回写，避免分工同时编辑中央需求。

## 7. Roadmap 回写

子任务 steps 已 done；独立合同、组件和浏览器 checks 已 passed。统一主构建、全站几何和质量门禁仍由主线程验收，`unified-browser` 保持 pending，本文件不提前把整个条目记 done。

## 8. Attention 候选盘点

无新增项目通用长期规则需要写入；现有“dirty worktree 不等于 clean proof”继续适用。

## 9. 遗留

- 工作区已有他任务的暂存与未暂存修改；本项未 git add/commit，未运行主目录 static build。
- 最终统一截图、主构建 build_id 绑定、整仓门禁和 Win7 发布证明未由本子任务完成；Win7 发布仍属迁移路线图。
- 旧 `field_workspace_probe.cjs` 中编辑器保存步骤已改为等待自动重读；整份旧历史 probe 未全量重跑。新独立 probe 为本轮报工行为证据。
