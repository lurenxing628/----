---
doc_type: refactor-design
refactor: 2026-05-29-resource-dispatch-js-split
status: approved
scope: 只拆资源排班页前端 JS 文件，不拆页面、不新增路由、不改变用户可见行为
summary: 将 resource_dispatch.js 按 shared/core/execution/boot 拆分，并同步适配前端合约测试读取口径
---

# resource-dispatch-js-split refactor design

> 当前状态：approved。用户已确认按本方案拆分；实现完成后已补资源排班页浏览器点验。

## 1. 本次范围

- 从 scan 勾选：#R2 测试读取口径适配、#R1 JS 职责拆分。
- 明确不做：
  - 不新增 `/scheduler/resource-execution`。
  - 不新增 `scheduler_resource_execution.py`。
  - 不新增排产主导航"现场记录"入口。
  - 不摘除资源排班页现有现场记录 UI。
  - 不把模板拆成 include 切片；本轮只允许改 `<script>` 引入顺序。
  - 不做甘特图改跳转。
  - 不改执行 API、`OperationExecutionEvents` schema、`can_write_feedback` 语义。
- 旧入口策略：
  - `templates/scheduler/resource_dispatch.html` 最终移除 `static/js/resource_dispatch.js` 的主入口引用。
  - 模板只按顺序引入 `resource_dispatch_shared.js`、`resource_dispatch_core.js`、`resource_execution.js`、`resource_dispatch_boot.js`。
  - 这 4 个新业务脚本必须和旧 `resource_dispatch.js` 一样放在 `{% if has_history %}` 块外无条件加载；只有 `frappe-gantt.min.js` 与 `gantt_popup_fit.js` 留在 `has_history` 条件块内。
  - 这 4 个新业务脚本继续使用 `defer`，禁止改成 `async`，避免脚本执行顺序不稳定。
  - 旧 `resource_dispatch.js` 若保留，只能作为未被模板引用的兼容壳或历史迁移文件，不再承载主启动逻辑。
- 总风险档位：中高。用户行为目标是不变，但跨文件启动顺序、共享状态、测试读取口径都必须小步验证。

## 2. 前置依赖

- 已有测试覆盖和需要适配的读取点：
  - `tests/operation_execution_feedback_test_support.py:13` 的 `RESOURCE_DISPATCH_JS` 常量。
  - `tests/regression_resource_dispatch_site_records_frontend_contract.py:4,24,56`。
  - `tests/regression_table_layout_readability_contract.py:51,92,118`。
  - `tests/regression_scheduler_ui_range_feedback_contract.py:28`。
  - `tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py:28`。
  - `tests/regression_frontend_ui_language_polish.py:732`。
- 需要先改测试支持函数：把"读单个 `resource_dispatch.js`"改成"读资源排班页脚本束"，否则拆文件后测试会把结构变化误判成行为变化。
- 测试适配不能削弱保护：
  - 脚本束读取顺序必须等于模板 script 顺序。
  - `regression_table_layout_readability_contract.py:118` 不能继续依赖 `[namedResourceInfo, renderFlags]` 这段跨文件区间，也不能降级成全文搜索；应逐个提取 `namedResourceInfo`、`resourceInfoHtml`、`calendarTaskHtml` 函数体后继续断言 `完整身份：` 不在日历资源展示链路里。
- Win7 打包前置结论：本轮只新增/调整 `static/js/*.js`，`build_win7_onedir.bat` 已通过 `--add-data "static;static"` 带上静态资源；不新增 Python 路由模块，因此不需要补 `--hidden-import`。
- 若未来另起拆页 feature，需要同时补 `web/routes/domains/scheduler/scheduler_route_registrar.py:5` 的 `_ROUTE_MODULES` 和 `build_win7_onedir.bat` 的 `--hidden-import`。

## 3. 跨文件契约

- 统一命名空间：使用 `window.__APS_RESOURCE_DISPATCH__`，不使用短名 `window.RD`。
- shared 负责：
  - 初始化命名空间。
  - 读取 `pageEl = $("rdPage")`，并在读取 `pageEl.getAttribute(...)` 之前先判空；如果没有页面根节点，只设置安全的空状态，boot 直接退出。
  - 初始化共享 `state` 与 `state.cfg`。
  - 提供共享工具：`escapeHtml`、`trim`、`text`、`show`、`$`、`badge`、`parseJson`、`resourceInfo`、`resourceDisplayHtml`、`resourceCell`、`namedResourceInfo`、`resourceInfoHtml`、`fullTextCell`、`latestExceptionSummary` 等。
- core 至少导出：
  - `loadData`。
  - `currentQueryString`。
  - `bindFieldToggles`、`bindTabs`。
  - 排班查询、汇总、明细、日历、甘特、班组表渲染所需函数。
- execution 至少导出：
  - `loadExecutionData`。
  - `renderExecutionCards`。
  - `bindExecutionActionClicks`。
  - `bindActualImportButtons`。
  - 现场记录任务卡、单条填写、查看记录、实际情况 Excel 导入相关函数。
- 跨域互调必须在调用时从 `window.__APS_RESOURCE_DISPATCH__` 读取最新引用，禁止在文件加载时捕获另一个子文件的函数引用。
- 需要逐点改写的跨文件调用至少包括：`executionEventsUrl()` 调用 `currentQueryString()`、`actualImportUrl()` 调用 `currentQueryString()`、`executionRequestUrl()` 调用 `currentQueryString()`、`loadData()` 调用 `loadExecutionData()`、`loadData()` 失败分支调用 `renderExecutionCards(null)`、`submitActualImport()` 调用 `loadExecutionData()` 和 `loadData()`、`buildDetailRowsHtml()` / `ganttPopup()` 调用 `latestExceptionSummary()`。
- `currentQueryString()` 语义必须保持：先使用 `window.location.search`；只有为空时才从 `state.cfg.filters` 重建，并保留 `scope_type/operator_id/machine_id/team_id/team_axis/period_preset/query_date/start_date/end_date/version/plan_role/scenario_id`。
- 启动顺序必须保持旧末尾顺序：`bindFieldToggles()`、`bindTabs()`、`bindExecutionActionClicks()`、`bindActualImportButtons()`，最后只调用一次 `loadData()`。
- `loadData()` 成功后仍调用 `loadExecutionData()`；失败分支仍调用 `renderExecutionCards(null)`。
- `loadExecutionData()` 自身行为必须保持：无历史、不可查询或无执行 URL 时仍 `renderExecutionCards(null)` 并返回；请求失败时仍设置 `state.execution = null`，并渲染带 `disabled_reason` 的空任务卡。
- `submitActualImport()` 成功后仍保持 `loadExecutionData()` + `loadData()` 双刷新。
- 模板脚本顺序：`frappe-gantt.min.js`、`gantt_popup_fit.js` 保留在 `{% if has_history %}` 内；随后在条件块外以 `defer` 顺序加载 `resource_dispatch_shared.js`、`resource_dispatch_core.js`、`resource_execution.js`、`resource_dispatch_boot.js`。

## 4. 执行顺序

### 步骤 1：先改测试读取口径

- 引用方法：M-L1-04 Characterization Test 刻画测试
- 具体操作：
  - 在 `tests/operation_execution_feedback_test_support.py` 或就近测试 helper 中提供资源排班脚本束读取函数。
  - 拆分前 helper 仍读取现有 `static/js/resource_dispatch.js`，保证测试语义不变。
  - 将直接 `_read("static/js/resource_dispatch.js")` 或 `RESOURCE_DISPATCH_JS.read_text(...)` 的测试迁到 helper 或脚本束读取口径。
  - 对日历资源展示链路的 `完整身份：` 断言使用逐函数体提取，不再用 `[namedResourceInfo, renderFlags]` 跨文件区间，也不把断言降级为全文搜索。
- 退出信号：
  - 拆分前运行相关前端合约测试仍通过。
  - 测试里不再把"执行函数必须存在于 `resource_dispatch.js` 单文件"当作行为契约。
- 验证责任：AI 自证
- 回滚：git revert 本步骤测试改动。

### 步骤 2：建立 shared 命名空间和 boot 启动边界

- 引用方法：M-L3-07 Single Responsibility Split 职责分离
- 具体操作：
  - 新增 `static/js/resource_dispatch_shared.js`，初始化 `window.__APS_RESOURCE_DISPATCH__`。
  - 共享工具、共享状态、`pageEl` 早退守卫、注册入口都挂在这个命名空间下。
  - 新增 `static/js/resource_dispatch_boot.js`，只负责在所有子文件加载后绑定事件并启动首轮加载。
  - 模板移除旧 `resource_dispatch.js` 主入口引用，按 §3 的顺序引入 4 个新文件。
  - 4 个新业务脚本必须放在 `{% if has_history %}` 外，继续使用 `defer`，禁止 `async`。
- 退出信号：
  - `templates/scheduler/resource_dispatch.html` 的脚本顺序明确为 shared -> core -> execution -> boot，且排在 gantt 依赖之后。
  - no_history 页面仍加载 shared/core/execution/boot，视角和区间下拉联动不丢。
  - boot 之前不触发 `loadData()` 或 `loadExecutionData()`。
  - 无 `rdPage` 时 boot 安静退出，不让 shared/core/execution 因页面根节点缺失报错。
- 验证责任：AI 自证
- 回滚：删除新增 JS，模板恢复单脚本引用。

### 步骤 3：拆出 execution 子域

- 引用方法：M-L3-07 Single Responsibility Split 职责分离
- 具体操作：
  - 新增 `static/js/resource_execution.js`。
  - 搬迁现场记录任务卡、单条填写、查看记录、实际情况 Excel 导入相关函数。
  - execution 通过命名空间调用 core 的 `currentQueryString()` 和 `loadData()`，core 通过命名空间调用 execution 的 `loadExecutionData()` 与 `renderExecutionCards()`。
  - 保持现有行为：导入成功后仍执行 `loadExecutionData()` + `loadData()` 双刷新；排班 `loadData()` 成功后仍级联刷新执行卡，失败后仍清空执行卡。
  - 保持 `loadExecutionData()` 的无 URL / 不可查询早退和请求失败提示分支。
- 退出信号：
  - 现场记录相关前端合约测试通过。
  - grep 确认没有新增 `/scheduler/resource-execution` 或新的执行 API。
- 验证责任：AI 自证
- 回滚：恢复原 `resource_dispatch.js` 与脚本引用。

### 步骤 4：拆出 core 子域并收束原文件

- 引用方法：M-L3-07 Single Responsibility Split 职责分离
- 具体操作：
  - 将排班查询、汇总、任务明细、日历、甘特、班组表逻辑放入 `resource_dispatch_core.js`。
  - 原 `resource_dispatch.js` 不再作为主入口；若保留，必须只是兼容壳或彻底移除模板引用。
  - `currentQueryString()`、`state.cfg.filters` 等跨域共享点只保留一份，避免 core/execution 各算一遍 URL。
- 退出信号：
  - 排班页 URL/UI/交互不变。
  - `currentQueryString()` 语义不变：仍优先使用 `window.location.search`，空时再从 `state.cfg.filters` 重建参数。
- 验证责任：AI 自证
- 回滚：恢复原单文件。

### 步骤 5：回归验证和范围守护

- 引用方法：M-L1-04 Characterization Test 刻画测试
- 具体操作：
  - 跑聚焦测试：
    - `.venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py`
    - `.venv/bin/python -m pytest tests/regression_table_layout_readability_contract.py`
    - `.venv/bin/python -m pytest tests/regression_scheduler_ui_range_feedback_contract.py`
    - `.venv/bin/python -m pytest tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`
    - `.venv/bin/python -m pytest tests/regression_frontend_ui_language_polish.py`
  - grep 范围守护：
    - 不出现新的 `/scheduler/resource-execution`。
    - 不新增 `scheduler_resource_execution.py`。
    - 不改 `build_win7_onedir.bat` 的 hidden-import。
    - 不改 `OperationExecutionEvents` schema。
  - 打开资源排班页做人工目视：查询、tab、现场记录任务卡、实际情况导入入口仍在原页。
- 退出信号：
  - 聚焦测试通过。
  - 范围守护 grep 通过。
  - 资源排班页人工点一圈确认后，才允许收尾或继续下一阶段。
- 验证责任：AI 自证；最终页面目视为 HUMAN（需要用户确认时停下）
- 回滚：git revert 本 refactor 单提交。

## 5. 风险与看点

- 高风险：启动顺序。旧单文件所有函数定义完才 `loadData()`；拆分后必须由 boot 统一启动。
- 高风险：双向依赖。`loadData()` 会刷新执行卡，执行导入成功又会刷新排班表；拆分后必须通过命名空间晚绑定，不能在加载时互相捕获函数。
- 高风险：`currentQueryString()`。它不是普通工具函数，历史 `version`、`plan_role`、`scenario_id` 都会进入排班/执行/导入链路；拆错会改变请求。
- 中风险：测试口径。测试应证明用户行为不变，不应继续证明"某函数必须在某个物理 JS 文件里"。
- 中风险：命名空间。使用 `window.__APS_RESOURCE_DISPATCH__`，不用 `window.RD`。
- 不触发风险：Win7 hidden-import。只拆静态 JS 不新增 Python 路由模块，因此不需要修改 `build_win7_onedir.bat`。
