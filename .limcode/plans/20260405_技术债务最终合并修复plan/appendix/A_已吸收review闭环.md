# 附录 A：已吸收 review 闭环

> 本附录完整承接原总 plan 中“本 plan 已吸收并修正的问题”长清单，用于证明拆分过程中没有丢失细节。执行时请回到对应子 plan 查看如何落地；本附录不单独替代步骤、完成判定或验证命令。

## 一、已吸收并修正的问题（1~95）

1. 已把 `A5`、`A7`、`B3`、`B4`、`C3`、`C6`、`E6` 拉回主 plan，不再外置。
2. 已修正 `web/routes/scheduler.py` 与 `web/routes/scheduler/` 这类同名路径冲突风险。
3. 已修正算法路径误写为 `core/algorithms/greedy/types.py`、`greedy/evaluation.py`、`greedy/dispatch_rules.py` 的问题，统一使用真实路径。
4. 已移除未声明依赖的 `--timeout=120` 验证方式。
5. 已明确禁止引入 `ExcelImportController` 与 `window.__APS_PAGES__` 这类新一层总抽象。
6. 已修正 `ScheduleService` 仓储数量从错误的“12 个”改为真实的“10 个内部创建实例”，并修正构造器事实描述。
7. 已修正任务 5 契约边界的文件归属：`_get_snapshot_with_strict_mode` 归属 `schedule_service.py`、`_build_algo_operations_outcome` 和 `_build_freeze_window_seed_with_meta` 归属 `run/schedule_input_contracts.py`、模板 / 外部组查找边界归属 `run/schedule_template_lookup.py`；`schedule_input_collector.py` 与 `schedule_input_builder.py` 只作为消费者。
8. 已修正任务 10 的 `check_quickref_vs_routes.py` 验证命令从空转的 `pytest` 入口改为 `python` 直接执行。
9. 已修正任务 9 迁移后任务 10 仍引用旧测试路径的问题，统一使用迁移后新路径。
10. 已在任务 1 前移 `开发文档/README.md` 与 `audit/README.md` 最小入口版，解决前后依赖倒置。
11. 已修正任务 3 路由根层保留清单，补入 `web/routes/team_view_helpers.py` 这一共享辅助文件。
12. 已修正任务 3 调度服务根层保留清单，补入 `repository_bundle.py`（由任务 2 创建），并显式声明“任务 2 必须先于任务 3 完成”。
13. 已修正任务 5 中 `collect_schedule_run_input` 的参数计数为 16，并把 `ScheduleRunInput` 字段计数修正为 27。
14. 已把 `run/schedule_template_lookup.py::lookup_template_group_context_for_op` 的结构化退化边界纳入任务 5 的边界清单，并补入对应回归测试迁移要求。
15. 已把 `web/bootstrap/static_versioning.py` 中 `_mtime_version()` 的静默异常纳入任务 8 治理范围，并明确 `ui_v2_static.static` / `web_new_test/static/` 也必须纳入版本化清单。
16. 已修正任务 3、任务 5 的描述偏差：根层路由门面当前已是薄壳，`_run_schedule_impl(...)` 保持现有清晰主线，只收口兼容桥与阶段边界。
17. 已把任务 1 的文件职责、完成判定与批次 0 / 任务 10 入口链显式补入 `开发文档/README.md` 与 `audit/README.md`，防止入口链未闭合即误判完成。
18. 已把 `web/bootstrap/` 门禁改为“分批白名单 + 清零节奏”治理方式，并要求把 `factory.py:_open_db`、`static_versioning.py` 等现存例外逐项登记到治理台账和统一门禁。
19. 已把任务 2 的直接装配统计改为“执行前精确搜索并写入台账”，不再使用约数作为退出判定，并把 `scheduler_config.py` 的 6 处直接装配纳入第二批治理范围。
20. 已为任务 3 补入跨包导入策略：迁入 `web/routes/domains/**` 的文件统一改用根层共享工具绝对导入，并新增 `web/routes/navigation_utils.py` 承接 `_safe_next_url`，消除 `scheduler` 域跨用 `system_utils.py` 的断裂点。
21. 已统一任务 5 / 任务 6 之间 `if best is None` 的归属：任务 5 先移除兼容函数依赖并改成可观测显式失败路径，任务 6 只在可证明不可达时删除该分支。
22. 已把 `persist_schedule()` 的口径统一为“`svc` + 21 个关键字参数”，并纳入任务 5 的显式精简范围，要求改为接收稳定的上下文 / 结果对象边界。
23. 已细化任务 4 对 `schedule_optimizer.py` 中 `_cfg_value()`、`_norm_text()` 的替换方案，明确受影响键和调用点必须统一走注册表 / 规范化门面。
24. 已把 `web/ui_mode.py` 纳入任务 8 治理范围，覆盖 `ui_v2_static` 注册、V2 模板叠加环境、失败回退路径与渲染期 `url_for` 注入。
25. 已把静态资源版本化的初始化顺序、构建时机、质量门禁接入、清单缺失的可观测降级策略与 Win7 / Python 3.8 兼容约束补成硬条件。
26. 已统一“任务 3 完成后只再引用迁移后路径”的口径，并补入根层兼容入口清单；任务 4、任务 5、任务 7、任务 8 的后续步骤统一改写为 `core/services/scheduler/<子包>/**` 与 `web/routes/domains/**` 新路径。
27. 已在任务 1 前移 `tests/regression/` 最小目录与嵌套门禁配置，并要求先实测 `tests/*` 与 `tests/**/*.py` 的语义差异，再显式固化可覆盖子目录的写法与最小 `pytest` 采集边界，避免任务 8 先落 `tests/regression/**` 时破坏统一门禁。
28. 已在任务 3 显式补入 `scheduler.py -> scheduler_pages.py -> 8 个 scheduler 子模块` 的导入聚合链，避免迁移后丢失路由注册。
29. 已把 `gantt_critical_chain.py` 的 5 处 `except Exception` 全部纳入任务 7 治理，不再只处理 `_load_rows()` 一处。
30. 已把任务 4 中 `schedule_optimizer.py` 的 `_cfg_value` / `_norm_text` 替换方案具体化，区分直接读取点、数值 helper 传入点与统一文本规范化门面。
31. 已在任务 7、任务 8、任务 9 的新建目录步骤里显式补入 `__init__.py`，覆盖 `data/queries/`、`core/infrastructure/data_repairs/`、`web/pageflows/` 与前置的 `tests/regression/`。
32. 已把任务 3 中 `pyproject.toml` 的 `per-file-ignores` 迁移写成明确步骤，要求先移除全局 `F401` 忽略，再同步覆盖根层门面与迁移后的聚合文件。
33. 已把任务 5 中 `_schedule_with_optional_strict_mode` 的收口范围补齐到 `schedule_optimizer_steps.py` 内部 `_run_ortools_warmstart()` 与 `_run_multi_start()` 两处同文件调用。
34. 已把 `ScheduleService._run_schedule_impl(...)` 返回值构建块中的 `orchestration.summary` 防御性 `getattr(...)` 一并纳入任务 5 收口范围，并要求以提交前实测命中数为准全部清理。
35. 已把 `factory.py:_perf_headers` 的 2 处异常吞没，以及 `web/ui_mode.py` 中“异常后 `pass` / 返回空值”的现存路径，一并纳入门禁与治理台账范围；静默回退门禁不再只识别 `pass / ...`。
36. 已把 `number_utils.py` 从任务 3 的 `config/` 子包落位清单中移回 `core/services/scheduler/` 根层共享工具，避免跨子包反向依赖。
37. 已把任务 3 后必须同步修正的路径敏感测试 / 门禁清单显式写入任务 3，覆盖 `tests/test_architecture_fitness.py`、`tests/regression_safe_next_url_hardening.py`、`tests/test_source_merge_mode_constants.py` 及依赖源码路径的支撑脚本。
38. 已把 `schedule_orchestrator.py` 中 `_normalize_optimizer_outcome()` 纳入任务 5 主链兼容桥收口范围，不再只处理 `_merge_summary_warnings`。
39. 已把 `tests/regression_schedule_input_builder_template_missing_surfaces_event.py` 补入任务 5 的实施前确认与验证命令，作为删除模板查找旧回退后的必跑护栏。
40. 已在任务 1 中补入 `ruff` 版本锁定要求，并明确本地 / 托管环境都必须落在同一版本区间。
41. 已把 `factory.py:_open_db` 中“请求起始时间设置失败回退为 `None`”与“请求路径解析失败后 `pass`”两处无日志静默回退单独写入任务 1 台账与门禁要求。
42. 已把 `g.services` 的挂载时序明确为“维护任务之后”，并写清维护任务继续直接构造 `SystemMaintenanceService`，不依赖请求级服务容器。
43. 已把任务 2 与任务 4 围绕 `ConfigService` 的交叉边界写清：任务 2 只改取用方式，任务 4 才改内部规则源。
44. 已把 `CalendarService` / `ConfigService` 延迟导入命运、`BatchForSort` 与日期解析共同前移、`_norm_text()` 无闭包依赖可直接提取等执行断层显式写回对应任务。
45. 已核实 `web/bootstrap/` 静默回退治理范围不止 `factory.py`、`static_versioning.py` 与 `web/ui_mode.py`；任务 1 现补为“请求装配层 / 启动入口层 / 运行时探测层 / 插件装载层”四类清单，并把 `plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py` 与 `factory.py:_close_db` 纳入台账与首批治理边界。
46. 已核实本地 `ruff` 提交钩子存在版本漂移风险；任务 1 现要求 `.pre-commit-config.yaml` 与统一门禁共用 `python -m ruff` 调用，并由 `scripts/run_quality_gate.py` 先校验版本区间。
47. 已核实治理台账必须提供稳定机器可读结构；任务 1 现要求在 `开发文档/技术债务治理台账.md` 中维护受控 `json` 代码块，架构门禁与专项门禁只解析该结构块。
48. 已核实批次 1 不应前置全量目录迁移；任务 3 现改为“目录骨架 + `config/run/summary` 与 scheduler 域热点先迁”，其余物理迁移分别并入任务 7、任务 8 的行为改造批次。
49. 已修正任务 7 中 `gantt_critical_chain.py` 5 处异常落点描述，统一使用“工艺前驱边判定 / 资源前驱边判定”而非“机器链路 / 操作员链路”。
50. 已核实任务 4 不仅要清理 `schedule_optimizer.py` 的 `_cfg_value()` / `_norm_text()`，还必须同步清理 `schedule_optimizer_steps.py` 内 `_run_ortools_warmstart()` 与 `_run_multi_start()` 的本地 `_cfg_value()` 闭包。
51. 已核实任务 2 的直接装配统计还需显式覆盖 `Repository(g.db, ...)` 形态；验证命令与治理台账统计口径现统一扩展为 `Service` / `Repository` 两类构造，并以正则搜索消除歧义。
52. 已核实任务 5 必须给出 `ScheduleRunInput` 27 字段的完整归属规则，并显式声明 `OptimizationOutcome.metrics -> ScheduleOrchestrationOutcome.best_metrics` 的单行映射。
53. 已核实任务 8 必须固定 `asset_manifest.json` 的版本语义；现统一要求 manifest 与运行时降级路径都使用与 `static_versioning.py` 一致的 `mtime` 版本口径。
54. 已核实静默回退门禁不能只覆盖 `None / "" / False / continue`；任务 1、任务 7、任务 8 现一并覆盖 `[] / {} / 0 / ()` 等空集合或空值回退。
55. 已核实根层门面导入写法需要明确；任务 3 现显式写明 `web/routes/scheduler.py` 等根层门面改用 `from .domains.scheduler import scheduler_pages as _pages` 等包内导入，并要求 `web/routes/domains/__init__.py` 作为空包标记先行创建。
56. 已核实 `pyproject.toml` 的 `F401` 去重策略、`tests/**/*.py` 递归门禁、`excel_demo.py` 根层保留、`GreedyScheduler.schedule(...)` 的“300 多行”描述与 `radon` 依赖补齐等项已被现有步骤覆盖或属于接受风险，不再另起新任务。
57. 已根据 `web/bootstrap/factory.py:_maintenance_gate_response()` 与 `web/bootstrap/paths.py:runtime_base_dir()` 的真实调用链，补齐任务 1 的启动链治理清单、完成判定与验证范围。
58. 已把 `web/ui_mode.py:_read_ui_mode_from_db()` 中直接 `SystemConfigService(conn, ...)` 装配显式纳入任务 2 收口范围，并要求在请求级服务容器落地后优先改为复用 `g.services` 取用。
59. 已把任务 1 的静默回退门禁范围显式补齐到 `web/ui_mode.py` 单文件入口，避免 `tests/test_architecture_fitness.py` 只按目录扫描时漏掉高密度静默回退点。
60. 已把任务 3 的 `F401` 收口顺序改成“先 `python -m ruff check --select F401` 评估影响清单，再移除全局忽略并逐文件收紧”，避免一次性放大全仓报错面。
61. 已把 `core/services/scheduler/summary/schedule_summary_freeze.py` 的摘要侧配置读取纳入任务 4，要求冻结窗口配置与摘要展示复用同一注册表 / 读取门面。
62. 已把 `core/services/scheduler/gantt/gantt_service.py` 中 `_critical_chain_cache_key()`、`_get_critical_chain()` 的静默回退白名单清零归属补入任务 7。
63. 已把 `scheduler_excel_calendar.py`、`process_excel_part_operation_hours.py` 的现成专项回归补入任务 8 验收，并要求 `scheduler_analysis.py` 只做最小边界收口，不按 `system_logs.py` 的重构重量处理。
64. 已把 `tests/regression_frontend_common_interactions.py` 与 `tests/test_ui_mode.py` 纳入任务 9 的首批迁移与共享路径辅助范围，避免界面契约测试滞留根层。
65. 已把任务 10 的速查表校验扩展为“接口一致性 + 关键文件 / 目录路径存在性”双重验证，避免文档路径漂移漏检。
66. 已根据当前引用链核实 `CalendarService` / `ConfigService` 不构成循环依赖，任务 5 改为直接上移到模块顶层导入，不再留开放决策。
67. 已根据 `tests/test_architecture_fitness.py:CORE_DIRS` 的当前实装，明确任务 1 必须先把 `web/bootstrap/` 接入 `CORE_DIRS` 或等价专项扫描入口，再登记白名单与治理台账；不得只补台账不补扫描范围。
68. 已把 `web/bootstrap/factory.py:_is_exit_backup_enabled` 与 `_run_exit_backup` 补入任务 1 的 `web/bootstrap/` 台账清单，并要求把它们明确归类为“已有日志的可观测回退”或继续清零对象。
69. 已把任务 1 的 `web/bootstrap/` 门禁补充为“样本命中验证”要求，必须用 `factory.py:_open_db`、`_close_db`、`_perf_headers` 的现存异常点实测扫描与白名单计数确实生效。
70. 已把任务 2 中 `web/ui_mode.py:_read_ui_mode_from_db()` 的容器改造补齐为“维护窗口短路 / 无 `g.services` 时返回 `missing=True`”，禁止直接无守卫访问 `g.services.system_config_service`。
71. 已把任务 5 的内部执行顺序写死为 `步骤 3 → 步骤 3.5 → 步骤 4 → 步骤 5 → 步骤 6 → 步骤 7`，禁止跨步并行导致现状稳定调用面与旧兼容桥并存。
72. 已把任务 6 中 `_parse_date()` 的非严格模式替代策略写成显式要求：解析失败只能进入结构化退化 / 确定性告警路径，不得静默 `return None`。
73. 已把任务 6 中 `_parse_datetime()` 的迁移要求收紧为复用 `python-dateutil`，禁止把手工多格式循环解析原样搬到新边界层。
74. 已把任务 1 的启动链专项回归显式补入验证集合，覆盖 `runtime_probe`、启动契约 / 运行路径、插件装配可观测性与停机链路四类护栏，不再只以统一门禁入口笼统代替。
75. 已修正任务 3 中非 scheduler 域根层门面的切换时序：批次 1 只切 `web/routes/scheduler.py`；`process.py`、`personnel.py`、`equipment.py`、`system.py` 保持旧导入直到任务 8 对应物理迁移完成，禁止空子包先接管。
76. 已把 `web/routes/domains/scheduler/scheduler_config.py` 与 `templates/scheduler/config.html` 纳入任务 4 单一事实源范围，并要求页面选项、标签、提示语统一由字段注册表或统一字段元数据门面生成。
77. 已为任务 8 补入 DOM 协议直接门禁：`page_boot.js` 接入、`data-page` 产出、旧全局命名空间停止扩张，并要求旧协议残余页面形成“已迁 / 未迁”清单。
78. 已把任务 4 结构门禁补齐为同时检查 `schedule_optimizer_steps.py` 中 `_cfg_value` 的定义与调用全部清零。
79. 已把任务 7 的白名单计数口径改成“以任务 1 扩展扫描器后的实测值为准”，不沿用旧扫描范围下 `gantt_service.py` 的历史计数。
80. 已把任务 3 的中间态导入路径保障写入根层兼容导出规则，要求 `gantt_*`、`batch_*`、`dispatch_*`、`calendar_*` 未迁组先建立稳定导出路径，再允许后续任务引用迁移后口径。
81. 已把任务 2 的直接装配基线搜索扩展为同时覆盖 `Service / Repository(g.db, ...)` 与 `Service / Repository(conn, ...)` 等间接传参形态。
82. 已明确任务 5 中稳定调用面的字段单向映射规则，以 `ScheduleRunInput`、`ScheduleOrchestrationOutcome`、`SummaryBuildContext` 为准，禁止执行链同时暴露原始字段与规范化字段两套可消费事实源。
83. 已将 `_parse_date()` 非严格模式静默吐值明确定性为 BUG 修复，并要求补充“无效交期类型触发可观测告警”的专项回归。
84. 已把任务 5 验证命令补强为显式断言 `OptimizationOutcome.metrics -> ScheduleOrchestrationOutcome.best_metrics` 映射已落地。
85. 已补充算法层 `runtime_checkable` 只允许用于边界检查、禁止进入热路径循环的约束。
86. 已根据 `ScheduleService` 当前引用链核实，任务 2 改为保留公开构造边界 `ScheduleService(conn, logger=None, op_logger=None)` 的稳定兼容，并把 `svc.<repo>` 平铺仓储属性定性为本轮正式代理面，而不是执行期临时兼容桥。
87. 已根据 `web/bootstrap/` 现状把任务 1 的计数方式改为“执行时全量扫描 + 机器可读落账”；当前文本级 `except Exception` 命中约 104 处，其中 `launcher.py` 50 处、`factory.py` 14 处、`plugins.py` 12 处、`entrypoint.py` 12 处、`runtime_probe.py` 6 处、`security.py` 6 处、`static_versioning.py` 3 处、`paths.py` 1 处，不再按“约 20 处代表点”估算工作量。
88. 已把 `factory.py:_open_db`、`_close_db`、`_perf_headers` 从“样本点”升级为任务 1 必须显式处置的执行对象：每条异常分支都必须在本批清零、改成可观测降级，或绑定唯一后续批次，不再允许只登记样本不定归属。
89. 已把任务 4 的“单一事实源”补齐到 `schedule_optimizer.py:_cfg_choices()`、`ConfigService.VALID_*` / `get_available_strategies()` 投影链、`cfg_snapshot is None` 静默默认运行路径，以及 `config_presets.py` 中活动预设基线比对异常回退。
90. 已把排产主链中 `_normalized_status_text` 的 3 套实现、`_raise_schedule_empty_result` 的 2 处定义、重复的 `_TERMINAL_OPERATION_STATUSES` / `_FAIL_FAST_BATCH_STATUSES` 纳入任务 5 共用语义收口，不再留第二套状态事实源。
91. 已把 `schedule_summary.py:_append_summary_warning` 的静默 `return False`、`ScheduleService._run_schedule_impl(...)` 中对已是 `set` 字段的重复 `set()` 包装、以及稳定调用面收口后 `_aps_schedule_input_cache` 的生命周期归属，一并写入任务 5 的明确步骤与完成判定。
92. 已把 `calendar_engine.py:_parse_shift_start()` 的 `08:00` 静默回退纳入任务 7 的时间解析治理范围。
93. 已把 `gantt_critical_chain.py:_parse_dt()` 与 `core/services/scheduler/_sched_display_utils.py:parse_dt()` 的重复实现并轨纳入任务 7，避免同类时间解析失败模式只修一处。
94. 已把任务 7、任务 8 的后续物理迁移补齐为“同批同步更新 `tests/test_architecture_fitness.py` / `tests/architecture/test_architecture_fitness.py` 路径敏感白名单与断言”的横向固定动作。
95. 已把两份新增 review 的 open finding 与第四轮低等级遗漏全部写入任务步骤、完成判定与覆盖矩阵，不再只停留在审查结论文本。

## 二、使用方式

1. 需要核对“某条 review 结论是否已经被吸收”时，先查本附录。
2. 需要知道“吸收之后具体在哪个子 plan 落地”，再回到附录 B 或对应子 plan。
3. 若后续实施发现新增细节，应补到对应子 plan 或附录，而不是再把长清单写回索引版主 plan。
