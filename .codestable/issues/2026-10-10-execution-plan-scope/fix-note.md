# 大计划现场范围读取被无关计划投影拒绝

状态：宿主回归通过；Win7 实机复验由本次完整验收继续执行。

100 批次、5000 工序真实排产并采用第二个正式版本后，即使现场甘特和报工页只请求 4 小时范围，两者仍先读取完整计划 workspace。完整 workspace 包含现场页面不使用的基线对比、占用、交付和工序顺序投影，组合超过计划读取的 8 MiB 边界。因此时间筛选、现场账本和详情令牌还没处理，就返回 413。

`WorkbenchPlanQueryService.execution_workspace` 复用原有选计划、来源容量、身份、采用时数量、完整范围任务、资源和指纹路径，仅跳过不使用的展示投影；实际甘特仍生成所选时间范围的真实日历。任务读取仍检查原 10000 条和 8 MiB 边界，账本和实际甘特的现有边界均未改变。原完整计划 workspace 的投影契约和 413 行为保持。

两个现场服务把请求时间范围传到正常计划查询；计划设备、实际设备、历史报工设备和剩余安排设备的筛选仍沿用账本事实。现场关键链另读完整任务事实保留范围外前驱，继续明确 `scope=full_plan`，并把完整链事实绑定到快照。报工仍只给返回页或详情签发写令牌；分页、文件导出、模板和确认仍绑定原范围和事实。

宿主证据保存在忽略目录 `output/win7-complex-20261010/`：

- `derived-scope-http-red.json`：修复前运行中的真实后端，第二正式版本的范围 actual-gantt、execution/tasks 均 413；第一版为 200 正对照。
- `derived-scope-green.json`：独立 query-only 连接、无写 SQL；第二版范围实际甘特完整 42 任务，327233 B、5.109 秒；范围报工完整 42 任务、2.313 秒；完整报工 5000 任务、3.031 秒。原完整计划 workspace 仍 413。
- `derived-scope-full-actual-green.json`：两版完整实际甘特均 5000 个唯一任务和工序，账本比较身份逐一对应，完整关键链可用且依据 5000 个计划任务。canonical 响应约 9.89 MB，满足原实际甘特 32 MiB 边界，耗时 3.579 / 4.312 秒。普通计划 workspace 的 8 MiB 边界不能替代实际甘特自身边界。
- `derived-scope-test-red.txt`：在隔离测试进程恢复原消费者完整 workspace 调用，目标回归真实返回 413 而失败。

定向和关联回归：`test_execution_plan_read_scope.py`、`test_field_workspace_api.py`、`test_point_downstream_api.py`、`test_piece_downstream_api.py`、`test_plan_query_api.py`，共 12 passed（36.85 秒）；Ruff 通过。新回归包含无关投影超限、完整关键链范围外前驱、前驱变更使旧链和导出快照失效、报工续页和实际写令牌、写后旧文件快照拒绝，以及必要任务本身超 8 MiB 仍拒绝。
