# 批次、基础资料、日历和外协域实施记录

## 设计与边界

- 按 `implementation-20260912.md` 的批准修订实施；保留原有 API、命令、原子批量策略、未知值、旧资料和请求待核实边界。
- 批次列表与资源表采用有高度预算的内部滚动框。表头相对滚动框 `top:0`，批次号/资源编号及操作列固定；不依赖整页滚动吸顶。
- 表单消费共享 `ResourceControls.Field`、`WorkbenchGuards`；本域不另建确认框。新增批次按既有三个必填合同，一次报告批次号、图号、数量全部错误；编辑旧记录仅验证并提交改动字段。
- 分页呈现统一到共享 `Pager`，各消费者显式声明原可接受页大小，保留原数字跳页；资源关联固定每页 5 项，没有放大领域 API。
- 日期、工时、数值与内部编号消费共享格式/编号模块。原型文件不修改，域样式迁入 `31-batches-resources.css` 与 `32-calendar-outsourcing.css`。
- 产能链保持原有数据输入→自制/外协链→日历结构及原 1280 竖排断点；仅解除强制 `height:100%`/零 `flex-basis` 导致的溢出和卡片重叠。

## 已实施

- [x] BatchTable 与 ResourceTables 表头/关键列/操作列固定，表内高度预算，caption/scope，筛选按钮聚焦/激活时显示。
- [x] BatchDetail、批次导入/批量确认表格与资源预检表格补 caption/scope 和内部滚动；预检/关联列表复用 EmptyState/Pager。
- [x] 批次基础/工序表单共用 Field，聚焦首个错误，字段消息不在总错误中重复；新增批次三必填聚合错误，保存 payload 保持原格式。
- [x] 批次基础、工序补充和批量编辑登记独立草稿 owner；取消、Esc/遮罩、SPA导航由公共守卫同一接口处理，pending 仍沿原请求保护。
- [x] 资源表格、日历、目录、物料导入/预览、外协的空态、分页、编号、格式与域内样式接线。
- [x] 批次“清除全部筛选”同时清搜索词及显示输入，避免空结果恢复按钮只清部分条件。
- [x] 日历/外协/目录具体实施由真实子代理 `calendar_outsource` 并行完成，保持结构化字段错误边界，不猜测错误字符串对应字段。

## 已完成的局部验证

- `python3 -m tools.symbol_locator whereis BatchWorkspace`：未找到 JS 符号，随后用 `rg` 核对定义/消费方；没有冒充 Python 索引已覆盖前端。
- Node 编译本域 38 个 JS/JSX 源文件：38 输出，目标 Chrome 109。
- `node tests/workbench/batch_ui_contract.cjs`：10 个命令/字段边界通过；证明新建聚合错误、零/小数/非法数量拒绝、旧未知字段不因编辑备注被补写。
- `pytest -q tests/workbench/test_batch_widgets.py tests/workbench/test_batch_transport.py tests/workbench/test_batch_dashboard_return_context.py`：3 passed in 17.46s。组件测试使用 Chromium `109.0.5414.46`，1366×768/1280×720 × 浅/深色，共 40 场，通过表内吸顶/固定列、必填错误和焦点、取消保留草稿、确认放弃、创建/工序/stale/批量/待核实/导入导出既有行为；JS 与新 CSS 均记录源 SHA-256。
- 首轮组件报告保存在 `/tmp/aps-wbui-implementation-20260912/batch-widgets/`；最终 pytest 产物路径由其 `BATCH_WIDGET_ARTIFACTS` 输出给出。组件 fixture 按工作台内容预算保留 289px 外壳空间，并不冒充整页真实服务截图。
- `git diff --check`：本域已检查文件无 whitespace 错误。
- 最终独立 Node 源码回归：`batch_widgets_probe.cjs /tmp/aps-wbui-implementation-20260912/batch-widgets-final`，40 场通过；`resource_table_header_probe.cjs /tmp/aps-wbui-implementation-20260912/resource-table-headers-final`，64 场/28 张截图通过，`errors=[]`、`external=[]`，源 SHA-256 核对一致。资源表头保留 2000 列值完整读取、分页/搜索/全选范围、异步取消、stale/失败不改筛选、列宽拖拽及键盘、窄列与模态交互断言。
- 资源表头异步测试将“固定等待 140ms 再检查 loading”改为受控 Promise 释放，保证待完成期间真实检查禁用状态，避免高并发时先完成请求造成时间竞争误报。
- `test_process_readiness_browser.py`：1 passed；`test_resource_readiness.py::test_rail_chromium109_two_sizes_two_themes` 扩展为 1920/1392/1366/1280 × 双主题，共 8 场通过，检查卡片实际边界、两两不重叠、文字局部溢出及点击导航。基于初次统一构建 `02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4` 加当前 Rail/Workspace 源码替换，仍须跟随最终构建复验。
- 测试期间曾遇原调度优化并发文件中间态 `optimizer_multi_start_dedup.py:19` 导入 `native_multi_start_calendar_snapshot` 失败；本域没有修改相关核心文件。另有两轮表头行为全部跑完但因并发源码变化被哈希守卫拒绝，已重跑取得上面的最终一致结果，不将被拒绝的轮次记通过。
- 调度优化中间态恢复后，`pytest -q tests/workbench/test_batch_transport.py tests/workbench/test_batch_dashboard_return_context.py`：3 passed in 1.12s，新增的字段/payload 合同已挂入原有 `test_batch_transport.py`，不会只留为人工 Node 测试。
- 日历/外协/目录独立受控组件探针 9 项通过（`/tmp/aps-wbui-calendar-outsourcing-20260912/result.json`），包含精度保留、真实字段聚焦、无结构错误不猜字段、取消留草稿/单次确认、明确分页档位与横纵滚动 sticky。
- 子代理最终回归：目录 76 项通过并核对当前源码哈希；日历 4 变体通过并核对当前源码哈希、`protected_unchanged=true`；真实外协 pytest 2 passed in 45.75s，覆盖 4 场景、17 项边界、4 次浏览器重启、源 CSS 哈希及数据库保留。
  - 目录证据：`/tmp/aps-wbui-catalog-existing-20260912/catalog-result.json`。
  - 日历证据：`/tmp/aps-wbui-calendar-existing-20260912/calendar-result.json`、`source-hashes.json`。
  - 外协证据：`/tmp/aps-wbui-outsourcing-existing-20260912/outsourcing-ui.json`、`outsourcing-server.json`。

## 待主线程统一收口

- [x] 初次主构建后的 ResourceRail/readiness 几何已完成；15 视图最终当前源码截图及 build_id 绑定仍由主线程完成。
- [x] 资源表头完整行为回归完成。
- [x] 日历/外协/目录子代理最终报告补充。
- [ ] 最终质量门禁与迁移证据交接。工作区保留原有大量未提交/已暂存内容，本记录不是 clean-worktree proof。

本域未执行 `git add`、commit、push、数据库迁移或产品写入；既有数据行为由受控 adapter/隔离 fixture 验证。
