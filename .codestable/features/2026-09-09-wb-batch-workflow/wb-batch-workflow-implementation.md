---
doc_type: implementation
feature: wb-batch-workflow
status: integration-pending
created: 2026-09-09
summary: J交付真实批次API及9个独立前端文件，主线可立即挂载，最终页面验收未冒充完成
tags: [workbench, batch, sqlite]
---

# 可立即接入

后端 `web/routes/workbench/batches.py:register_batch_routes(bp)`。
该函数内部已调用文件接口注册，不能再次单独注册 `register_batch_file_routes`。
共享回执查询继续由既有 `workbench.command_receipt` 提供。本模块不自行挂全局Blueprint。

前置加载 React、foundation（含 APSFieldReports.iconNodes 和本地 Lucide 许可）、
resource-contract.js、resource-api.js、resource-session.js、ResourceControls.jsx、
ResourceTables.jsx、ResourceForms.jsx。随后按顺序加载 app 下9文件：

1. BatchContract.js
2. BatchAPI.js
3. BatchControls.jsx
4. BatchForms.jsx
5. BatchOperationEditor.jsx
6. BatchDetail.jsx
7. BatchTable.jsx
8. BatchFiles.jsx
9. BatchWorkspace.jsx

入口 `window.BatchWorkspace`，adapter 必须为稳定实例 `window.APSBatchAPI.create()`。
Props：`adapter`、`onCommitted(receipt)`、`disabled=false`、`initialContext`、`onNav(view)`。
`initialContext={entity_ref?,focus?:"gaps"|"unready",batchIds?:string[]}` 仅初始化读取，
同页新定位通过显式key重挂载。`onNav` 当前发出 `"run"`。

# 已交付范围

- WBP-BATCH-001..006：真实字段、搜索、状态/齐套和列值筛选、三态排序、分页、列宽、当前页/全筛选选择、隐藏选中计数、工序概况及新增。
- 007..009：明确refs的批量修改/复制/删除预览确认；整批原子提交。复制新建永久工序引用，不复制原计划/执行/物料需求事实。
- 010..012：首工作表XLSX，overwrite/append/replace三模式，真实模板及清单下载；导出界面明确区分选中集合与筛选全量。
- 013..017：四区详情、基础信息白名单编辑、模板同步、严格开关、工序资源/工时/外协周期、缺项提示和原外协组只读信息。
- 齐套显示/日期保留原业务字段；已有BatchMaterials作为真实到料需求只读展示。没有新增原型不存在的需求增删编辑器，不拿库存数值冒充到料。

# HTTP 与 Pending 合同

所有地址固定在 `/api/workbench/v1/entities/batch` 下：

- GET 集合、`/<ref>`、`/choices`、`/template`、`/export?export_ref=...`。
- POST `/query`、`/facets`、`/selection` 为只读查询；分页快照绑定完整筛选（页号除外）。
- POST `/create`、`/<ref>/update`、`/<ref>/delete`、`/<ref>/operation_update`。
- POST `/bulk-preview`、`/bulk-confirm`、`/<ref>/sync-preview`、`/<ref>/sync-confirm`。
- POST `/import-preview`（multipart）、`/import-confirm`、`/export-preview`。

JSON写入统一 `{request_key,write_token,input}`；preview-confirm input 为 `{preview_ref}`。
普通新增 input 为 `{business_code,part_ref,fields}`；fields完整八字段中的六个可变字段，
即quantity/due_date/priority/ready_status/ready_date/remark。更新只传 `{fields:{被编辑字段}}`。
工序更新 input 为 `{operation_ref,fields}`，URL和pending ref仍是批次ref。

N已接入 namespace `batches`，kind `batch`，category严格undefined：
create/ref=null；update/delete/operation_update/sync_confirm/ref=48hex；
bulk_confirm/import_confirm/ref=32位opaque preview_ref。
请求键复用resource-48hex；未把batch加入通用resources kind。BatchAPI仅包装base.query/preview/execute/download。

# 保留边界

- 不改既有scheduler、BatchService、schema/migrations、workflow/plan、main/build或route __init__；普通CRUD调用BatchService。
- 模板刷新使用已有managed ready闸门，但显式复制raw模板值：旧batch_template_ops和BatchOperation.from_row存在null转0路径，本模块不调用该有损复制投影。
- 合并外协组仍禁止逐道修改周期，沿既有operation_edit_service约束；整组周期与组关系不在本页编辑。
- 正式、候选、试调和执行引用以及已有非pending工序状态，阻止删除/重建/改数量；物料需求阻止批次删除和replace。
- 普通修改保留未展示字段；新导入批次固定不自动生成工序，已有批次空单元格不覆盖。这些规则在预览页面显式显示。
- 本接口单次文件及全选上限5000行、上传10MB、展开64MB；超过明确拒绝，不截断。该容量为本实现保护值，不宣称旧批次导入原有相同上限。
- 当前guard指纹保守覆盖整套批次依赖事实；无关资源变动也可能要求刷新。GET/preview不自动补身份、模板、工时或周期。

# 验证

最终组合命令：
`.venv/bin/python -m pytest -q -s tests/workbench/test_batch_commands.py tests/workbench/test_batch_actions.py tests/workbench/test_batch_files.py tests/workbench/test_batch_transport.py tests/workbench/test_batch_widgets.py tests/workbench/test_process_batch_gate.py tests/workbench/test_commands.py tests/workbench/test_write_context.py tests/workbench/test_resource_transport.py`

结果 **90 passed in 14.68s**。包含真实临时SQLite所有表保留、原子回执、重启读回、stale、动作权限、部分完成、null/0、三个文件模式、公式与坏文件拒绝及下载字节核验。

Chrome109组件mock：1440x1000和390x844，light/dark，共32交互组、40截图；当前源文件sha256随报告保存，外部请求与浏览器错误均为空。
原pytest轮转目录已不存在，测试输出改为独立临时目录后重新运行组件测试，结果1 passed in 12.50s；9个UI文件未变。
现存产物：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-batch-widgets-c0g7bizq/batch-result.json`。
已目视复核其中桌面深色文件预览和窄屏深色工序编辑；列表/预览的宽表在自身区域横向滚动。
文件弹窗的浏览器下载是明确mock，真实XLSX字节由独立SQLite/codec测试验证，不能混称端到端真实文件验收。

Ruff scoped check通过；20个Python文件通过`tools/scan_py38plus_syntax.py --fail-on-hit`，无3.8.10之后语法/注解发现。

# 留给主线

本轮未启动生产库、未全局构建、未提交、未spawn。整个工作区已有大量其他代理改动，不提供clean-worktree proof。
未运行整仓quality gate：本轮限制不build，且主线正在并行整合；仅报告上述dirty工作区局部证据。
主线仍须实际挂载、跨页上下文联调、真实浏览器写入/刷新/重启、复杂批量规模和最终Win7包验收。
特别是后续排产预检须把raw null工时视为缺项，不能通过旧BatchOperation.from_row的默认值误认成显式零工时。
