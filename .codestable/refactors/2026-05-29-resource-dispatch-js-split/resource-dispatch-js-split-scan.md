---
doc_type: refactor-scan
refactor: 2026-05-29-resource-dispatch-js-split
status: user-reviewed
scope: static/js/resource_dispatch.js + templates/scheduler/resource_dispatch.html script 引入 + 相关前端合约测试
summary: 发现 2 条定点重构项，均来自 resource-dispatch-execution-page-extraction 的对抗评审结论
---

# resource-dispatch-js-split scan

## 总览

- 扫描范围：`static/js/resource_dispatch.js`、`templates/scheduler/resource_dispatch.html` 的 `<script>` 引入、硬编码读取 `resource_dispatch.js` 的前端合约测试。
- 发现 2 条优化点：结构 2 / 性能 0 / 可读性 0。
- 按风险：中 1 / 高 1。
- 建议先做：#R2（先改测试读取口径，给后续拆文件提供行为等价保护）。
- 建议后做：#R1（真正拆 JS，风险集中在加载顺序、共享状态和查询参数）。
- 前置检查 7 条：
  1. 问题类型是结构性维护负担，不改变业务行为，适合走 refactor。
  2. 目标模块有测试覆盖，至少包括 `regression_resource_dispatch_site_records_frontend_contract.py`、`regression_table_layout_readability_contract.py`、`regression_scheduler_ui_range_feedback_contract.py`、`regression_scheduler_resource_dispatch_invalid_query_cleanup.py`、`regression_frontend_ui_language_polish.py`。
  3. 用户可见行为边界清楚：资源排班页 URL、导航、DOM 主体、API、schema 都不变。
  4. 回滚边界清楚：应以单个 refactor 提交回滚，不承诺"删新增文件即可回滚"。
  5. 外部兼容边界清楚：本轮只动静态 JS 和模板 script 引入，不新增 Python 路由，不触发 Win7 hidden-import 变更。
  6. 范围未超过 CodeStable 大拆分阈值：目标单文件约 1398 行，未超过 3000 行，但涉及启动顺序和共享状态，必须走标准 refactor，不走 fastforward。
  7. 验收边界清楚：自动化测试通过后，还需要资源排班页人工点一圈确认查询、tab、现场记录、导入入口仍在原页。
- 用户选择：本轮用户已明确要求"按照你的意见改"，因此两条均按 ✓ 进入 design；未勾选的拆页面、主导航、甘特图跳转不进入本 refactor。

## 条目

### #R1 把 resource_dispatch.js 拆成 shared/core/execution/boot ✓

- **位置**：`static/js/resource_dispatch.js:1-1398`，`templates/scheduler/resource_dispatch.html:427`
- **分类**：结构
- **现状**：`resource_dispatch.js` 是单 IIFE，工具函数、排班查询/渲染、现场记录、实际情况导入、启动逻辑都在一个文件里；同一个 `state` 同时装 `data` 和 `execution`，`currentQueryString()` 被排班和执行两域共用。
- **问题**：单文件 1398 行 / 62KB；`pageEl` 在 `static/js/resource_dispatch.js:298` 读取并于 `:299` 早退，`state` 在 `:301` 定义，`currentQueryString()` 在 `:1294` 定义并被 `:874/:983/:1318/:1324` 跨域调用，`loadData()` 在 `:1347` 定义并于 `:1380` 级联 `loadExecutionData()`、失败时于 `:1389` 清空执行卡，`submitActualImport()` 在 `:1066-1067` 同时刷新执行卡和排班表。后续改现场记录时必须理解整页启动和排班渲染，开发维护负担高。
- **建议**：拆为 `resource_dispatch_shared.js`、`resource_dispatch_core.js`、`resource_execution.js`、`resource_dispatch_boot.js`；使用明确命名空间 `window.__APS_RESOURCE_DISPATCH__` 承接共享工具、共享状态和注册函数；排班页仍同时引入四个文件，DOM、URL、导航和用户操作不变。
- **建议映射的方法**：M-L3-07（Single Responsibility Split 职责分离）
- **风险**：高（不是纯文本搬移，必须保持 shared → core → execution → boot 的加载顺序，并保持 `loadData()` 级联刷新执行卡、导入成功双刷新等现有行为）
- **验证**：AI 自证（跑资源排班/现场记录前端合约测试；grep 不出现新 `/scheduler/resource-execution` 路由；浏览器或等价静态检查确认 script 顺序）
- **范围**：约 4 个 JS 文件 / 1 个模板 script 区 / 约 1398 行迁移

### #R2 把前端合约测试从单文件读取改成脚本束读取 ✓

- **位置**：`tests/operation_execution_feedback_test_support.py:13`，`tests/regression_resource_dispatch_site_records_frontend_contract.py:24`，`tests/regression_table_layout_readability_contract.py:51`，`tests/regression_scheduler_ui_range_feedback_contract.py:28`，`tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py:28`，`tests/regression_frontend_ui_language_polish.py:732`
- **分类**：结构
- **现状**：多个测试把 `static/js/resource_dispatch.js` 当作唯一事实源，部分测试逐字断言 `bindExecutionActionClicks`、`postExecutionAction`、`submitActualImport` 等函数名在这个单文件里。
- **问题**：只要执行逻辑搬到 `resource_execution.js`，这些测试即使用户行为没变也会失败；旧 design/checklist 的"全部既有测试未修改即通过"已被代码事实证伪。#R2 是 #R1 的前置依赖，不能把测试适配放到最后补救。
- **建议**：先建立测试侧的资源排班脚本束读取 helper，按页面实际加载顺序读取 `shared/core/execution/boot`；在拆分前 helper 可兼容现有单文件，拆分后测试断言改为针对脚本束整体或明确目标子文件。`regression_table_layout_readability_contract.py` 的 `namedResourceInfo` 断言不能继续依赖 `[namedResourceInfo, renderFlags]` 这段跨文件区间，也不能降级成全文 `in`；应逐个提取日历资源展示链路的相关函数体后继续断言语义。
- **建议映射的方法**：M-L1-04（Characterization Test 刻画测试）
- **风险**：中（测试改错会掩盖真实行为变化，因此要先保证拆分前 helper 读取现有单文件时测试仍通过）
- **验证**：AI 自证（先跑改造后的前端合约测试，确认拆分前仍通过；拆分后再跑同一组测试）
- **范围**：约 6 个测试文件 / 小范围 helper 改造
