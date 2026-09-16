# 关联资料维护后父表单反复报版本过期

## 只读现场核验

- 5003 服务 PID `91706`，启动时间 `2026-09-15 20:49:56`，本任务未重启。
- 只读连接 `file:.../aps-manual-resources-20260915-494scls2/db/aps.db?mode=ro`，并设置 `PRAGMA query_only=ON`。
- 实际人员编号为 `QA-20260509-OP01`，不是简写 `OP01`；其 `WorkbenchOperatorProfiles.shift_profile_id` 仍为 `MANUAL-SHIFT-0915`。
- 班次名称已成功变成 `手动验收两日班-更新`，班次实体引用 `88cc9defcbd07405bd952e0c979acde9749f57204c33ee9e`，修订 5。最后一条班次更名回执为 `5a3104224d4f49978760ecd275edd8b1`，时间 `2026-09-15T14:25:40.393Z`。
- 用户提供的结果编号 `3d9cc676128143cfa8d28f3be454a775` 没有匹配 `WorkbenchCommandReceipts.receipt_ref`；未将该错误结果编号冒充成功写入回执。已有绑定与更名成功事实来自上述原表和回执。

## 根因

1. 父表单的“刷新最新资料”只把读取结果放到 `contextReview`，没有更新实际保存用的 `writeContext`；必须另外点击“已核对，继续编辑”才更新版本。与此同时，保存按钮仍可点击，因此再次提交的还是旧版本。
2. 从父表单完成班次/设备组维护后，回调只刷新关联选项，未刷新父表单保存版本。目录更名属于父表单相关事实的变化，旧版本随后被后端正确拒绝。

修改前当前源码中同样存在这两条路径，没有“已有修复尚未被 5003 加载”的证据。不是后端错误接受/生成版本，也不是班次实体引用因更名被替换。

定位前检查了指定文件的已有修改；使用 `symbol_locator` 查找 `update_resource` 无同名函数后，以 `rg` 定位组件和回调，并通过 `snapshot` 定位到 `WorkbenchResourceStateService.snapshot`。后端 `resource_states.py` 的相关班次事实与 `write_context.py` 的版本比较保持原样。

## 修改范围

- `frontend/workbench/app/ResourceWorkspace.jsx`：读取最新资料成功后直接更新当前保存版本；重置之前明确拒绝的命令状态；通过现有 `acceptedEntity` 和 `rebaseDraft` 保留用户改过的字段，更新未修改字段。
- `frontend/workbench/app/ResourceForms.jsx`：移除父表单单纯用于接受新版本的“已核对，继续编辑”步骤。继续展示数据库中当前已保存的字段及关联，并明确说明用户修改已保留、未修改字段已更新。
- 班次或设备组由本表单自行维护成功后，统一刷新选项和父表单版本；未确认的维护结果不进入该成功分支。
- 没有改 `ResourceCatalog` 自身编辑器的其他流程，没有改后端 `stale_write` 检查，没有自动重发失败保存请求。

## 定向验证

1. 新 `test_resource_context_refresh.py::test_parent_refresh_and_own_catalog_commit_preserve_draft`：**1 passed in 2.13s**，Chromium `109.0.5414.46`，3 个当前组件流程，44 个源码哈希全部吻合：
   - 连续刷新两次可直接保存，姓名草稿与班次“未选”保留，未修改的状态跟随最新资料；展示服务器当前名称，取消额外接受步骤。
   - 从人员编辑进入真实班次目录组件，更名完成并返回后自动刷新父表单，草稿保留，直接保存成功，班次引用不变。
   - 刷新之后再发生并发修改，模拟版本检查仍拒绝；再次刷新保留草稿，保存成功。
2. 新增到既有 `test_resource_api.py::test_catalog_rename_requires_current_parent_context_and_preserves_unrelated_facts`：真实临时 SQLite/Flask **1 项通过**。班次更名后的旧父版本返回 HTTP 409；刷新后再并发更名仍返回 `stale_write`；连续读取两次最新版本后，姓名修改及明确解绑可保存。测试库计划表、计划历史、人员设备关系、技能和班次逐日规则保持原值。
3. 既有 `resource_forms_probe.cjs` 调整相应刷新用例后，Chromium 109 **84 项通过、32 张截图**；21 个参与源码哈希全部吻合，页面/控制台错误与外部请求均为空。

新专项初次失败是探针把真实“编辑班次档”模态写成“编辑班次”，修正该定位名称后通过；未为此更改产品行为。真实 API 专项已在该次通过，无重复运行。

## 证据

- 新专项：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-resource-context-refresh-pumgfwwr/resource-context-refresh.json`；SHA-256 `25c6b7d031e7d611dbdda55c3c0937bbd8acc9e9a26df8696407ec48a80ff0e4`。该浏览器探针为当前组件加带版本检查的模拟适配器，真实后端并发规则由上述 API 用例验证，二者不冒充手动现场测试。
- 既有组件：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-resource-forms-context-final-z622w50u/forms-result.json`；SHA-256 `309af69abcfd9a2e18c48c714b9a553c1b5393ecf43c16af85958a834c7c918f`。
- 最终 `ResourceWorkspace.jsx` SHA-256：`229dd49f91e180f351bd500ca140bc3cd0a9f45bd570a8838dda365e655c6b3b`。
- 最终 `ResourceForms.jsx` SHA-256：`a26561c7a84097daa2b5422b92dc93f648cfcf37884ec56f520d60cee9cc77b7`。

## 交接与边界

- 新增 `test_resource_context_refresh.py`、`resource_context_refresh_probe.cjs` 已交主代理统一登记到资源组；修改了既有 `test_resource_api.py` 和 `resource_forms_probe.cjs`。
- 未构建共享资产，未操作手动验收的 Chrome/IAB，未写入 5003 或其他手动业务数据库，未重启服务。需由主代理集中构建后在真实模态流程回验。
- 用户禁止的全门禁、`run_quality_gate.py` 任何模式及整仓测试均未执行。保留工作区其他修改，不构成 clean-worktree proof。
