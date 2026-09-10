---
title: 原型移植的验证与交付证据评估
status: draft
created: 2026-09-09
scope: verification-and-release-only
implementation_authorized: false
---

# 结论与范围

- **现有测试可复用，但不足以支持“所有原型功能已接后端、已压测、逐页手输点击和目视通过、可以下线旧页”的结论。** 主分母采用已完成的206个能力族ID清单，逐ID补充真实数据库持久化浏览器测试、手输/目视证据，并完成大规模业务混合负载、Win7实机验收和完整回滚演练。
- 当前仓库已有大量 staged、unstaged、untracked 内容，包括测试、运行时、打包与原型文件。本报告描述的是 **2026-09-09 本地工作区源码快照**，不是最终 HEAD 的 clean proof；已有测试文件存在不等于本轮跑过。
- 本轮仅阅读 AGENTS、attention、system-overview、项目 cs-explore 及相关源码，做解释器/模块可发现性检查；未运行 pytest、JS 测试、压测、应用、浏览器、构建、备份或清理，未打开业务数据库，未安装依赖。仅写本文件，不设计全局路由架构，不实施移植或旧页下线。
- 本报告里的规模、时延预算是**建议验收目标，未经实测**。没有读取用户库统计，因此不能声称代表用户真实规模。路由及页面取舍由主代理冻结清单，本报告只规定如何证明其完整、正确、可用及可回退。
- 最新任务分工：Chrome/Edge109官方支持边界与隔离Chromium109真实内核验证由主代理负责，本报告不重复下载或运行浏览器。**已收到并只读核查Mac Chromium109的60状态与1510维护导航断言结果；主代理另报甘特1186checks/72states/56screens通过。浏览器/CSS专题结论转交[Win7评估稿](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/win7-runtime-assessment.md)，本子任务不再重复调查；Win7实机字体/DPI/GPU/IME和冻结交付另按9.3-9.6验收。** 若目标承载失败，按用户要求保留原方案外观复刻，不以改布局、减少功能或提高目标系统版本消除失败。

# 1. 已核查的测试基础与证据边界

下列引用以当前工作区源码行号为准；后续合并后需重新定位。E 编号供矩阵引用。

| 证据 | 已读源码与确切结论 | 能证明 / 不能证明 |
|---|---|---|
| E01 pytest 入口 | [pyproject.toml:5](/Users/lurenxing/GitHub/----/pyproject.toml:5)、[conftest.py:34](/Users/lurenxing/GitHub/----/tests/conftest.py:34)：默认只收集 `tests` 下 Python 用例；`required` 来自 registry，`serial`、`perf` 来自分片分类，债务节点标 strict xfail。coverage 为 core/web/data 的分支覆盖且按需启用，见 pyproject:14。 | Python 默认收集不包括所有 `.cjs`、原型测试目录，也不自动执行 `_scripts_e2e/run_*.py`；总 pytest 通过数不是 UI 功能覆盖率。xfail/skip 与 passed 分开计数。 |
| E02 共享隔离 fixture | [conftest.py:79](/Users/lurenxing/GitHub/----/tests/conftest.py:79)、[conftest.py:155](/Users/lurenxing/GitHub/----/tests/conftest.py:155)：逐例还原 env/退出备份全局；`db_path` 在 tmp_path 建完整 schema；`db_env` 在导入 app 前设置数据库、日志、备份、模板目录；`app_client` 延迟导入。 | fixture 使用者的建库基础可复用；autouse 的 env 还原不是全局路径重定向，更不能保护测试收集期间的模块顶层代码。 |
| E03 工厂副作用 | [app.py:50](/Users/lurenxing/GitHub/----/app.py:50)、[factory.py:73](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:73)、[factory.py:322](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:322)、[factory.py:403](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:403)：import app 即 create_app；工厂创建目录/模板、ensure_schema、插件加载；普通请求运行维护检查。 | 不能先 import app 再覆盖 config，也不能以“只 GET 页面”推断无写入。 |
| E04 数据根与自动任务 | [launcher_paths.py:88](/Users/lurenxing/GitHub/----/web/bootstrap/launcher_paths.py:88)、[system_config_service.py:150](/Users/lurenxing/GitHub/----/core/services/system/system_config_service.py:150)、[system_maintenance_service.py:102](/Users/lurenxing/GitHub/----/core/services/system/system_maintenance_service.py:102)、[security.py:12](/Users/lurenxing/GitHub/----/web/bootstrap/security.py:12)：未冻结默认数据根为源码根；冻结后可选注册表共享根；三个自动任务默认 no，但已存 yes 不会因 development 自动关闭；SECRET_KEY 缺失可落日志目录。 | 必须隔离所有目录和设置，不能只改 DB。现有旧库配置不能当“默认关闭”处理。 |
| E05 全量测试的额外写点 | [test_startup_host_portfile.py:188](/Users/lurenxing/GitHub/----/tests/app_runtime/test_startup_host_portfile.py:188)：尽管 test_db 在临时目录，210-215 行仍访问并清理 `repo_root/logs` 运行时镜像，随后启动 app 子进程；[test_win7_launcher_runtime_paths.py:148](/Users/lurenxing/GitHub/----/tests/app_runtime/test_win7_launcher_runtime_paths.py:148) 锁定源码态镜像行为。 | **全量门禁不能在当前用户工作目录盲跑。** 必须独立 checkout/测试机，不能把“临时库”误当整个执行链无副作用。 |
| E06 完整质量门禁 | [quality_gate_shared.py:735](/Users/lurenxing/GitHub/----/tools/quality_gate_shared.py:735)：ruff、导入环、全量 collect、YAML、py38 扫描、quickref、anti-regression、pyright、架构、债务账本、启动回归、3 分片 full-test-debt 及 required 对账；[run_quality_gate.py:3095](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:3095)：默认要求 clean，但 3116-3137 行写 manifest/清理证据先于 3142 行 dirty 拒绝。 | 门禁不是只读命令；即使因 dirty 失败也可能动既有证据。`--allow-dirty-worktree` 成功结尾为 `passed_but_unbound` 且返回 2，见 3210-3216 行。 |
| E07 日常门禁 | [run_daily_quality_gate.py:708](/Users/lurenxing/GitHub/----/scripts/run_daily_quality_gate.py:708)、[full_test_debt_shards.py:72](/Users/lurenxing/GitHub/----/tools/full_test_debt_shards.py:72)：daily 明示非 clean proof，重性能/浏览器类标 perf。 | 快速反馈不能替代完整门禁、浏览器操作和性能验收。 |
| E08 现有真实浏览器几何冒烟 | [test_ui_browser_geometry_smoke.py:25](/Users/lurenxing/GitHub/----/tests/app_runtime/test_ui_browser_geometry_smoke.py:25)、[ui_geometry_browser_support.py:42](/Users/lurenxing/GitHub/----/tests/app_runtime/ui_geometry_browser_support.py:42)、[ui_geometry_probe.mjs:285](/Users/lurenxing/GitHub/----/tests/ui_geometry_probe.mjs:285)：临时真实工厂、一个主要批次/工序，含坏历史 JSON；CDP 导航到 [20 条路径](/Users/lurenxing/GitHub/----/tests/app_runtime/ui_geometry_contract_data.py:7)，宽 1024/768、高 900，断言 HTTP、外壳、DOM、溢出、对比度等。 | 是现代 Chrome 渲染探针，不是全部按钮操作、键盘逐字输入、数据库写入或人工目视；`CI` 非空时整条浏览器测试直接 skip，`APS_BROWSER_SMOKE_REQUIRED=1` 不能越过这个 decorator。 |
| E09 临时 HTTP 生命周期 | [ui_geometry_browser_support.py:214](/Users/lurenxing/GitHub/----/tests/app_runtime/ui_geometry_browser_support.py:214)：`make_server("127.0.0.1", 0, app)`，finally shutdown/join/server_close；[factory.py:180](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:180) 产品服务器显式 `threaded=True`。 | 现有几何服务是自收口的短时测试服务，且并发方式不同；不能拿其耗时声称产品并发性能。 |
| E10 截图工具 | [capture_ui_baseline.py:33](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/capture_ui_baseline.py:33)、[ui_baseline_capture.mjs:32](/Users/lurenxing/GitHub/----/tests/ui_baseline_capture.mjs:32)：短时服务/Chrome，固定截图路径集合及双主题，写 checkout 的 output/ui_baseline；40 张图为该清单的截图，不是全部功能。 | 工具检查截图完整性，不替人看图；截图脚本直接改 data-theme，不证明真实主题开关；手跑采集不在 gate/registry。 |
| E11 原型 JSDOM | [workbench-batches-style.cjs:20](/Users/lurenxing/GitHub/----/tests/workbench-batches-style.cjs:20)：JSDOM/Babel/React，禁止 fetch；64-75 行直接 value setter/dispatchEvent/伪 File；90 行五批次；139-156 行明确验证演示导入响应且保持原五行。 | DOM 组件合同，不是物理布局、文件选择对话框、真实 Excel 导入或数据库持久化。不能把断言“共126行”写成导入126条成功。 |
| E12 原型 Playwright 工作流 | [workbench-workflow-browser.cjs:9](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/tests/workbench-workflow-browser.cjs:9)：headless Chrome，真实 locator click、fill，采用状态查 localStorage；56-79 行是14视图×2桌面尺寸×2主题的56张图。 | 已有真浏览器动作，但不等于后端链路；fill 非逐键输入；截图不等于已目视；其中试调独立页也不能只算一次跳转即全功能覆盖。 |
| E13 原型 Playwright 批次 | [batch-workbench-browser.cjs:24](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/tests/batch-workbench-browser.cjs:24)：五条 seed，34-35 行缺样式时注入，51-68 行 fill，108 行明确断言 reload 恢复原型初始数量。 | 生产验收应断言 reload/新会话仍保存；不得临时 addStyleTag 修补待交付页后声称成品通过。390px 的 sharedOverflow 在此是记录项，不是全局阻断断言。 |
| E14 小范围真实键盘/像素测试 | [field-gantt-focus-boundaries.cjs:16](/Users/lurenxing/GitHub/----/tests/field-gantt-focus-boundaries.cjs:16)：阻断网络、setContent、三任务 fixture，局部 native Tab/click 及像素裁切，104 行起多宽度主题。 | 有局部键盘/像素证据机制，但没有后端和全页功能；部分 focus/class 由 evaluate 注入，不能通算为键盘可达性。 |
| E15 原型离线资源检查 | [workbench-offline-assets.cjs:11](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/tests/workbench-offline-assets.cjs:11)：React18.3.1/Babel7.29.0固定SHA384、许可证、本地入口/CSS资源存在性、JS解析。 | 可复用原型供应物完整性；Node vm解析不证明Chrome109支持，不证明这些资源已收入产品包。 |
| E16 全站离线静态扫描 | [test_frontend_offline_static_assets.py:16](/Users/lurenxing/GitHub/----/tests/app_runtime/test_frontend_offline_static_assets.py:16)、[同文件:59](/Users/lurenxing/GitHub/----/tests/app_runtime/test_frontend_offline_static_assets.py:59)：扫描 templates/static/docs 的外链script/link/media/CSS url/import及CDN，UTF-8严格读取。 | 不包含整个“前端设计”树；正则静态扫描不能穷尽运行时拼接 fetch URL，仍需断公网的网络记录。 |
| E17 浏览器压测造数器 | [run_browser_extreme_stress_case.py:400](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_browser_extreme_stress_case.py:400)、[同文件:490](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_browser_extreme_stress_case.py:490)：真实文件SQLite/schema，批次/工序/外协/日历/停机/隐藏失败批次，写 manifest；默认32品种×2-4批×9工序，再加12失败批次各4工序，即624-1200工序。 | **只造数，不启动浏览器、不跑排产、不测性能。** 不生成完整正式/候选/试调历史及报工事实。`--force` 会删 aps.db 与 templates_excel（70-79、524-528行），禁用于复验模板。 |
| E18 造数局限 | [run_synthetic_case.py:114](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_synthetic_case.py:114)、[同文件:552](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_synthetic_case.py:552)：底座固定18台机器、21人、3供应商；可变品种/批次/工序；内存库真实ScheduleService simulate=True。E17:414、此文件:633取当天次日。 | 放大 parts 不等于放大资源/报工/历史规模；同 seed 跨日期不保证同数据，须归档 start_dt/输入库hash；内存算法性能不等于文件SQLite+HTTP+浏览器。 |
| E19 复杂Excel E2E | [run_complex_excel_cases_e2e.py:228](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_complex_excel_cases_e2e.py:228)、[同文件:394](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_complex_excel_cases_e2e.py:394)、[同文件:964](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_complex_excel_cases_e2e.py:964)、[同文件:1163](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_complex_excel_cases_e2e.py:1163)：6类案例、逐例临时库，真实Excel预览/确认/排产/导出；核查行数、时间、资源冲突、停机、merged外协一致性。 | 有价值的复杂业务回归，不是浏览器。自建测试工厂不含正式维护/插件全部语义；sanity还不是独立完整排产oracle，所有前置约束/技能/实际执行一致性需另核查。 |
| E20 真实库回放风险 | [run_real_db_replay_e2e.py:289](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/run_real_db_replay_e2e.py:289)：固定读取repo/db/aps.db，copy2到证据目录，没有输入库参数，随后在副本排产。 | 本轮禁运行。`APS_DB_PATH`不能改变其源；源码未见在线SQLite一致性快照步骤，不能把copy2直接当活库一致性备份证明。 |
| E21 算法基准分层 | [test_graph_performance.py:29](/Users/lurenxing/GitHub/----/tests/scheduler_graph/test_graph_performance.py:29)：2000节点/1900边图分析，平均2500ms、最大5000ms，诊断20KB/投影30KB；5000单链中位1500ms。 [optimizer_quality_matrix_cases.py:18](/Users/lurenxing/GitHub/----/tests/_support/optimizer_quality_matrix_cases.py:18)：4×2=8及12×4=48工序，两场景×四目标。 | 前者是图子系统上限；后者是真实SGS/CalendarService质量对照，但不是“大规模”。[optimizer_quality_matrix.py:149](/Users/lurenxing/GitHub/----/tests/_support/optimizer_quality_matrix.py:149)明确计时不含造数/审计，更不含HTTP/渲染。 |
| E22 大资源池名字不等于整机压测 | [benchmark_sgs_large_resource_pool.py:37](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py:37)、[同文件:166](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py:166)：日历stub、30×10候选对、单工序场景与1000+种子碎片场景，报告估算器调用和耗时。 | 用于算法热点定位，不代表多页面大库负载。medium gate仅选FJSP mk01、SMTWT、此脚本，见[medium_gate.py:33](/Users/lurenxing/GitHub/----/tests/_scripts_e2e/benchmark_optimizer_medium_gate.py:33)。 |
| E23 后端坏数据/冲突回归 | [test_excel_import_hardening.py:466](/Users/lurenxing/GitHub/----/tests/excel_data_io/test_excel_import_hardening.py:466)证明重复名称确认拒绝且原行不变；521行上传超限；543行日期规范化后重复；[test_material_finite_quantity_contract.py:73](/Users/lurenxing/GitHub/----/tests/material/test_material_finite_quantity_contract.py:73)、169行锁非有限值拒写/坏数据只读不修复。 | 应保留并把错误沿新页面呈现；这些断言本身不证明新页面会保留用户输入或正确显示错误。 |
| E24 计划/现场写入保护 | [test_operation_execution_state_revision.py:263](/Users/lurenxing/GitHub/----/tests/operation_execution/test_operation_execution_state_revision.py:263)：旧revision/非正式计划不能写事件；[test_gantt_adjustment_publish_execution_revision.py:190](/Users/lurenxing/GitHub/----/tests/gantt/test_gantt_adjustment_publish_execution_revision.py:190)：草稿不改正式表，现场变化后发布拒绝且正式表/发布状态/成功日志不变。 | 可作为迁移不破坏业务的强oracle，但须加真实前端的双页冲突、失败回显、重试路径。 |
| E25 导出真实边界 | [report_engine.py:58](/Users/lurenxing/GitHub/----/core/services/report/report_engine.py:58)：≤2000行direct，≤20000行stream，再大reject_need_async；[test_report_export_large_scope_rejects_need_async.py:40](/Users/lurenxing/GitHub/----/tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py:40)用阈值2/4及5行stub验证拒绝早于诊断。 | 不能以此宣称20000真实行性能已测。>20000预期可正确拒绝，不擅自新增异步架构，也不显示“下载成功”。 |
| E26 冻结包与资源锚点 | [build_win7_onedir.bat:15](/Users/lurenxing/GitHub/----/build_win7_onedir.bat:15)锁Python3.8 x64/PyInstaller4.10，66-71/93-97行收templates/static等；[test_frozen_bundle_contract.py:136](/Users/lurenxing/GitHub/----/tests/gate_meta/test_frozen_bundle_contract.py:136)对账动态模块/hidden-import/锚点；[test_win7_networkx_package_contract.py:14](/Users/lurenxing/GitHub/----/tests/gate_meta/test_win7_networkx_package_contract.py:14)查本地wheel/离线安装声明。 | 测试是收包规则合同，不是实机冻结exe成功；构建脚本含依赖安装和构建目录操作，本轮禁运行。 |
| E27 包验收已有缺口 | [validate_dist_exe.py:40](/Users/lurenxing/GitHub/----/validate_dist_exe.py:40)：静态锚点仅style.css/common.js；246行起清运行时文件、启动exe、访问6页及2静态资源，检查非空；[test_validate_dist_static_payload.py:30](/Users/lurenxing/GitHub/----/tests/app_runtime/test_validate_dist_static_payload.py:30)覆盖缺失/空文件/布局及调用合同。 | 不验新增全套静态资源hash/MIME/内容；脚本未自行隔离DB，且固定从exe目录logs读契约，不能向已安装正式目录直接执行。 |
| E28 静态缓存 | [test_static_versioning.py:23](/Users/lurenxing/GitHub/----/tests/web_pages/test_static_versioning.py:23)、71行：缺文件降级告警，mtime变化刷新版本。 | 不证明新旧包缓存切换或回滚后所有浏览器资源一致；应比较资产hash及实际请求结果，不能仅页面200。 |
| E29 恢复两阶段 | [test_restore_integrity_check_contract.py:70](/Users/lurenxing/GitHub/----/tests/migration_db/test_restore_integrity_check_contract.py:70)、108行：坏库拒绝，正常copy返回copied_pending_verify；[system_backup.py:331](/Users/lurenxing/GitHub/----/web/routes/system_backup.py:331)再走run_backup_restore/ensure_schema。 | 复制成功不等于结构和业务恢复验收通过；该小测试的Demo表检查不能替代全计划/报工恢复对账。 |

## 1.1 本机工具检查结果

- 实际执行 `.venv/bin/python -B -c` 的标准库元数据查询：Python **3.8.10**；pytest、pytest_cov、xdist、flask、openpyxl、networkx、ruff、pyright、radon 可通过 `find_spec` 找到。只证明可发现，不证明 import/版本组合/门禁运行成功。
- 实际执行 `node -e` 查询：Node **v24.15.0**；从当前默认解析环境找 `playwright`、`@playwright/test`、`jsdom`、`@babel/standalone`、`pngjs` 的 package.json 均为 `MODULE_NOT_FOUND`。不能推广为本机任何位置都没装，但现成 `node <cjs>` 在此环境不具备这些依赖。
- 未发现原型目录的 package.json/lockfile/Playwright config；不要给出不存在的 `npm test` / `npx playwright test` 作为统一入口。已有测试是独立Node脚本，工具链版本和入口登记需要补齐；不在本轮安装。
- 初始工具探测时本子任务未核查浏览器；随后收到主代理的Mac Chromium109实测结果，见9.3。Win7虚拟机/物理机、冻结exe及目标机CPU/内存/磁盘仍未验证可用，不得宣称已跑Win7实机兼容验收。

# 2. 安全执行边界与启动方式

## 2.1 本轮禁止与未来先决条件

1. 当前只允许本文件落盘，因此连 `pytest --collect-only`、质量门禁、造数器、截图器也未执行：它们可能产生缓存、临时库、日志、模板、应用启动或证据文件。
2. 后续实施获准后，先建立**专用可丢弃源码checkout和独立测试根**；全量/破坏性测试优先在不挂载用户业务目录的测试机/VM。env只能重定向配置，不是文件系统隔离。checkout含最终待测代码和必要离线资源，但不把用户db/backups/logs复制进去，不共享原logs镜像。
3. 源码快照必须如实涵盖获准纳入的dirty/untracked文件；单独 `git archive HEAD` 不包含它们。这里不自动快照、提交或清理。最终clean proof另外绑定已提交最终HEAD。
4. 每次运行在新目录里创建数据；全部路径取realpath，拒绝symlink/指向用户目录的hardlink、已有DB及复用的pytest basetemp。`--basetemp`会重用/清空目标，必须逐次唯一。下载目录、浏览器profile、TMPDIR、模板、日志、运行时锁和产物也独立。
5. 在任何产品导入前设置 `APS_SHARED_DATA_ROOT`、`APS_DB_PATH`、`APS_LOG_DIR`、`APS_BACKUP_DIR`、`APS_EXCEL_TEMPLATE_DIR`、`APS_ENV`、`SECRET_KEY`。单纯 `TESTING=True` 不是产品已实现的“禁止维护”开关。
6. 普通功能/性能fixture要求 `SystemConfig` 的 `auto_backup_enabled`、`auto_backup_cleanup_enabled`、`auto_log_cleanup_enabled` 均明确为no；只能在造数阶段对**测试库**设置。另建维护专用fixture才启用它们。退出备份同样受配置影响。禁止为跑测试修改用户的开关/备份/计划。
7. 输入默认纯合成文件库。真实历史兼容测试只能使用用户另行授权提供的一致、脱敏、只读基准副本，再复制为运行副本；不运行E20去读取活动用户库。需要获取原库快照属于另一个授权动作，本报告不执行。
8. 运行前后保存测试输入/源码/配置清单、业务表逻辑摘要和测试根文件manifest；验收结束只停止本次PID/线程/浏览器context。失败保留测试库与证据，不做全局pkill、删除共享profile、清用户缓存或备份。

## 2.2 现有可复用的短时服务方式

- Python浏览器回归已具备E08/E09路径：tmp_path造数、真实工厂、`127.0.0.1:0`分配端口、finally关闭。不占用用户已有端口，也不需要启动长期开发服务。浏览器验证接口身份、实际DB路径均应在放行写操作前核对，不能仅凭端口返回200认作目标实例。
- 未来逐页手工验收需要**有期限的专用运行器**：复用真实工厂，绑定loopback随机端口、显式`threaded=True`，打印仅测试实例的URL与已校验DB路径，设置总时限及finally关闭。现有几何helper可作基础，但没有“全页人工会话+压测+到期回收”的现成CLI，本轮不虚构该命令已存在。
- 运行器必须在启动前校验全部数据根，在开始输入前核对服务实例与fixture标识，超时后停止并等待正在写入的请求收口。强制终止只用于单独的崩溃恢复用例，使用新测试库。
- `python app.py`/Windows启动bat涉及入口锁、镜像日志、Chrome profile，不作为当前checkout的便利验收入口。冻结包启动另在独立安装测试机验证，不能以绕开launcher的工厂测试替代。

## 2.3 后续执行环境模板（现在不执行）

以下是POSIX测试环境准备模板。`QA_CHECKOUT`必须先由主代理确认是独立待测checkout，`QA_PY`是已具备依赖的3.8解释器绝对路径；缺失即停止，不自动安装。此模板不负责建立checkout，也不代表操作系统级隔离已经存在。

```bash
set -eu
: "${QA_CHECKOUT:?请设置独立待测checkout绝对路径}"
: "${QA_PY:?请设置已核验Python3.8解释器绝对路径}"
export QA_CHECKOUT QA_PY
cd "$QA_CHECKOUT"
export QA_ROOT="$(mktemp -d /tmp/aps-wb-qa.XXXXXX)"
export APS_SHARED_DATA_ROOT="$QA_ROOT/shared"
export APS_DB_PATH="$QA_ROOT/shared/db/aps.db"
export APS_LOG_DIR="$QA_ROOT/shared/logs"
export APS_BACKUP_DIR="$QA_ROOT/shared/backups"
export APS_EXCEL_TEMPLATE_DIR="$QA_ROOT/shared/templates_excel"
export APS_ENV=development
export SECRET_KEY=aps-isolated-verification-key-not-for-deployment
export PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$QA_CHECKOUT"
export TMPDIR="$QA_ROOT/tmp" TEMP="$QA_ROOT/tmp" TMP="$QA_ROOT/tmp"
mkdir -p "$TMPDIR" "$QA_ROOT/evidence"
"$QA_PY" -B -c 'import os; from pathlib import Path; q=Path(os.environ["QA_CHECKOUT"]).resolve(); original=Path("/Users/lurenxing/GitHub/----").resolve(); assert q != original and original not in q.parents and q not in original.parents; r=Path(os.environ["QA_ROOT"]).resolve(); names=("APS_SHARED_DATA_ROOT","APS_DB_PATH","APS_LOG_DIR","APS_BACKUP_DIR","APS_EXCEL_TEMPLATE_DIR","TMPDIR"); assert all(os.path.commonpath([str(r),str(Path(os.environ[n]).resolve())]) == str(r) for n in names); print("QA paths checked; not an OS sandbox")'
```

需把 `QA_CHECKOUT` / `QA_PY`作为export变量提供给模板；继承的 `CI`、`PYTEST_ADDOPTS`、`APS_CHROME_*`、`WERKZEUG_RUN_MAIN`等先检查再设置，不继承指向生产实例的profile/端口。检查命令不能代替测试账户/VM的访问限制。

# 3. 覆盖率口径与逐页功能矩阵

## 3.1 采用已完成的206个能力族ID

- 主分母唯一引用[prototype-capability-inventory.md:424](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md:424)的**206个稳定能力族ID**，入口为14个index view（含delay）加独立trial。清单已完成，不再另按本报告P01-P24或脚本加载文件数建立竞争分母；206不是206条API，也不是206个单独动作已通过。
- 当前`process`实际挂载`ProcessNative -> APSPlanAInit`，见[能力清单:46](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md:46)。`BaseDataScreen`的chain/flat及其旧Base*编辑器仅加载定义、未挂载，不能据此追加两种结构、旧子tab或旧编辑器功能。[清单排除项:445](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md:445)另列30个旧设计备选/比较/备份HTML，均非当前主线，不要求为未纳入主线先做“退役审批”。
- 沿用`WBP-*` ID，为其实际字段/子动作增加测试后缀和`page_id/action_id`映射，记录原型位置、新页面位置、请求合同、影响表、正常/失败/取消/空态、自动化用例、K输入证据、V目视证据、数据前后摘要。已列入清单的STUB/OFF不因占位/禁用免做；潜在/未达入口（例如DETAIL-008）依清单标记和主代理决定处理，不强行虚构可见入口。
- 每项状态只能是`not_run / passed / failed / blocked / approved_retired / not_applicable_with_reason`。能力族与子动作覆盖分开计数，缺K/V/后端证据不得passed；不重排原206个ID。清单之外的新增需求须明确批准后单列，不以“验收需要”为由自动增功能。
- 以下P矩阵是**验证视角和场景模板，不是当前原型能力事实源**。每个动作先映射206清单，**仅在当前样板实际提供时**才作为移植验收项；有控件但未实现的行为按清单标记补接后端。未提供的旧选项另做“旧生产页能力减当前可达能力”的差集，逐项说明保留/暂不移植及理由，经主代理确认后处理，不能默认追加；未挂载Base*或30个旧设计HTML本身也不等于旧生产页差集。

## 3.2 全页面/功能矩阵

所有**已映射206清单或另获批准旧页差集**的动作均执行：真实HTTP/持久化断言(B)、浏览器键盘与点击(K)、目标浏览器目视(V)。下表广项仅在现有样板实际提供时适用，不是24类功能一律新增。只读动作需证明业务事实无变化；预期审计日志另设允许变化表白名单。

| ID / 页面范围 | 必须逐个操作的功能 | 数据与失败验收 | 现有基础 / 需补证据 |
|---|---|---|---|
| P01 全局外壳 | 每项导航、当前页标记、深浅色、前进后退、刷新、直接访问、从详情返回、所有返回链接、帮助/用户说明 | 版本/方案/筛选上下文不串；浏览器存储坏值/不可用不造假；输入未保存的离开行为符合合同 | E08/E12；补真实后端、所有入口K/V及交付URL检查 |
| P02 值班台 | 每张风险卡/待办、全部筛选、详情下钻、回到值班台 | 卡片数量/范围/时间与真实查询一致；零风险、未知、读取失败三者区分；历史/候选不能冒充当前正式 | E08/E24；补真实混合数据和逐卡K/V |
| P03 当前基础资料外壳 | 仅按WBP-PROC与关联SH/DETAIL：ProcessNative产能链节点及当前8类子页、下一步批次管理、实际提供的定位/返回/编辑保护 | 节点切换与真实实体/阶段一致；不把固定计数当后端数据；未提供的保护另按清单接入合同，不猜现状 | 能力清单PROC；BaseDataScreen两种结构和旧tab不在本行范围 |
| P04 工艺/零件模板 | 查询/排序/分页、新增/编辑/复制/删除、路线解析、工序增删改排序、自制外协切换、工时、外协组、应用到批次、模板/导入/导出 | 引用保护、顺序/环/重复编号、merged/separate、缺资源、部分错误整批回滚；未选批次不变 | E19/E23；补所有控件与刷新后DB对账 |
| P05 自制/外协工种 | 两类查询和详情、增改删、归属/默认工时、引用保护、Excel全部步骤 | 重复编号/名称、归属不符、0/负/非有限工时、被使用工种不能误删 | E23；补新页真请求/键盘错误保持 |
| P06 供应商 | 查询详情、增改删、状态、外协工种/周期、Excel | 已引用删除/停用、错误周期、空值和0的区分、名称特殊字符 | E19部分；补B/K/V |
| P07 物料主数据 | 搜索筛选分页、增改删、库存/单位、模板导入导出 | 非有限/负数/极大值、重复编号、坏库存读不自动清洗、库存变动刷新保持 | E23；补文件库规模及新页回显 |
| P08 物料/齐套验证视角 | 当前清单提供的齐套显示/定位按对应ID验；批次物料需求增改删等未提供旧选项仅为旧生产页差集待核对项，不默认新增页面或控件 | 当前显示事实与排产readiness一致；若差集获准保留需求编辑，再验数量/引用/事务及库存不误改 | E19/E23是后端回归基础，不证明旧BaseMaterial编辑器当前可达 |
| P09 设备/设备组 | 列表详情、增改删、工种/状态、组成员、两套Excel、停机/保养增改删 | 人机资格一致、被引用拒删、停机重叠/跨日/相接端点、取消不写 | E19；补真实数据库及浏览器编辑 |
| P10 人员/技能/班组 | 人员增改删、状态、多技能矩阵、主操、组成员、各Excel、人员日历 | 人机不匹配、唯一/重复关系、停用资源、跨午夜/短班/请假覆盖全局日历 | E19；补键盘矩阵/日期/持久化 |
| P11 工作日历 | 日期定位、单日/批量修改、节假日、班次/效率、允许急件、模板导入导出 | 无工作日、零产能、倒置时间、跨午夜、边界日期、重复日期、坏值失败明确 | E19/E23；补大跨度和目标浏览器日期输入 |
| P12 批次管理 | 搜索排序列筛选分页、全选/跨页选择、展开工序、详情增改删复制、资源工时编辑、批改预览/确认/取消、Excel | 作用域精确、未选不变、预览不写、确认后刷新/新会话保持；过期预览拒绝、重复提交只生效一次 | E11/E13目前为原型；E23后端局部；需端到端重写对应断言 |
| P13 执行排产/参数 | 选批次、齐套/严格模式、资源补齐、所有高级开关/目标/权重/预算/冻结、开始及界面存在的取消/重试动作 | 不完整批次拒绝/跳过需可解释；真实运行状态与历史一致；失败不假成功；所有按钮都要接实际能力 | E19/E21/E24；补排产进行中的UI/请求并发 |
| P14 方案选择/分析 | 各候选详情/指标、比较、采用前确认/取消、采用、切版本、进入甘特/延期/试调/周计划 | 同一fixture的指标不串方案；旧revision拒绝；采用仅一次且原子；候选查看/导出不改正式 | E24；补真实候选库与K/V |
| P15 当前方案试调独立页 | 仅按WBP-TRIAL-001..012及PLAN：设备/批次视图、基线/仅变更/搜索、展开收起、任务/交付批次选择、resource/start编辑与保存试调/取消、约束诊断、采用/放弃、记录、CSV及返回；重置样板按清单待决策，不映射生产重置 | 草稿不改正式；固定/已执行守卫、冲突草稿可编辑但禁止采用/导出、失败保留输入；设备配套人员不能沿用样例硬映射 | [能力清单:223](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md:223)为事实源；不追加任务拖动、人员视图、撤销/重做或未提供的缩放/模拟按钮 |
| P16 计划甘特 | 设备/人员/批次视图、筛选清除、缩放/适应/滚动、条目/tooltip/详情、关键链定位、导出、跳转报工或试调 | 端点/跨日/外协、短条、超长名称、高密度、无数据/加载失败/只读上下文；导出范围与屏幕相同 | E08/E14局部；补真实上千/万条及实际资源命中 |
| P17 延期说明下钻 | 所有来源入口、范围、批次切换、原因/时间线展开、回链、导出（若交付） | 原因来自当前选定方案与数据，缺证据不得给确定归因；不可把数据缺口算0 | E19的sanity并不覆盖归因；需独立oracle和K/V |
| P18 现场记录 | 搜索/过滤/选择、开始/暂停/恢复/异常/完成、数量工时录入、补报/修改/撤销、原因、历史、Excel导入导出 | 计划量/本次数/累计量/剩余量分别对账；幂等、旧revision、两页冲突、部分记录、实际资源变化；审计完整 | E24；补新页面全部写流程和重启后保持 |
| P19 现场实际甘特 | 实际/计划/剩余条、分组、时间窗、展开折叠、筛选、键盘选择、实际记录详情、链路、跳转/导出 | 无结束时间、不完整报工、多段相接/重叠、实际资源不同于计划；实际条不可被计划覆盖 | E14仅三fixture；需真实报工历史+K/V |
| P20 执行复盘 | 主题/日期/资源/状态筛选、偏差口径、图表、排序分页、详情、回到现场/甘特、导出 | 缺工时/未完成/数量不齐全不当0，排除错误计划身份，跨页和导出一致 | E24只覆盖部分边界；补汇总oracle |
| P21 报表中心/周计划 | 每类报表、字段选择、日期/方案/资源筛选、图表、工序/记录/人员/设备表、详情与所有Excel/CSV下载 | 2000/2001/20000/20001真实行；空报表；字段、数量、单位、计划版本、文件内容/文件名/MIME一致；拒绝不得下载伪xlsx | E25/E19；补真实大文件/完整筛选空间 |
| P22 工时定额校准 | 筛选/排序、样本详情、建议、单项/批量采纳、取消、进入模板维护 | 必须真实样本与统计定义；样本不足/异常值/0定额；采纳精确写所选模板并留痕，不改历史事实 | [CalibScreen.jsx:13](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/CalibScreen.jsx:13)是固定样本；不能仅保留演示“已采纳” |
| P23 主数据总览 | 数据域切换、检查状态、搜索/筛选/排序/分页、关系/缺项详情、逐项定位、导出 | 未读取≠空≠合格，定位实体一致；只读扫描不顺带修改主数据 | [MasterDataOverview.jsx:25](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/MasterDataOverview.jsx:25)；需真实后端检查和全入口K/V |
| P24 系统管理/历史 | 总览检查、日志各集/筛选/详情/导出、诊断包、历史版本详情；备份创建/下载/恢复/删除、维护策略、交付的插件开关 | E29恢复须完整校验；失败/回滚失败分别展示；取消零写；正式诊断包无凭证；破坏性动作只在专用fixture | [SystemManagementScreen.jsx:125](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/SystemManagementScreen.jsx:125)仍有未接入的禁用动作；不得计成功；补完整恢复演练 |

共同状态至少包括：loading、正常、空结果、错误、输入非法、保存中、保存失败、取消、冲突、已停用/已删除对象、只读历史。页面不存在的动作标不适用并给主代理确认的合同依据，不增加不存在的产品能力。

# 4. “手输点击+目视”的证据分级

| 级别 | 允许方法 | 证据结论 |
|---|---|---|
| D 组件/数据设置 | JSDOM setter、DOM `.click()`、dispatchEvent、evaluate直接调用业务函数或改state/localStorage | 只能作为组件/模型测试、造数或测量；不能计手工验收 |
| A 浏览器便捷自动化 | Playwright `fill/check/selectOption/setInputFiles`，请求client/route.fulfill辅助 | 浏览器集成证据；fill不是逐键输入，setInputFiles不是系统文件选择对话框。后端成功路径不得mock响应 |
| K 浏览器真实输入路径 | 浏览器可见控件locator.click（不force）、键盘逐键`pressSequentially`/`keyboard.type`、Tab/Shift+Tab/Enter/Escape/Backspace，mouse down/move/up拖动 | 确认命中/遮挡/焦点/输入事件路径；是自动化输入，不冒充人拿物理键盘的事实 |
| H 人工/桌面原生输入 | 操作者在目标机逐字录入、使用中文IME组合输入、点击日期控件与系统文件选择器、拖动、保存 | 用户若要求严格人工“手输”，需逐动作H签名；K不能自动替代。代理桌面type也必须记为代理输入，未测IME不声称通过 |
| V 目视 | 对每个操作后的截图/可见页面实际查看并记判定人、时间、图号、问题坐标 | 生成PNG/几何断言≠目视；必须查看正常、弹窗、错误、完成态，不只首页 |

执行规则：

1. 每个 `action_id`从浏览器入口进入，点击实际控件，焦点确认后逐字输入，提交/取消；屏幕不能通过evaluate改值/调用handler来完成。可以用evaluate**只读测量**几何、表格或性能，须与动作区分。
2. ASCII数值/日期需测逐键编辑、选中替换、清空、退格、中间插入、Tab移焦及Enter提交；中文名称/备注另测目标机IME的compositionstart/update/end和取消组合，不能用keyboard.type中文字符串替代IME验收。
3. 对206清单实际提供的每种下拉、日期/时间、复选框、文件选择器、tooltip、拖动/缩放、焦点回归走真实可见交互；方法清单不代表每页都有这些控件，也不要求新造它们。保留遮挡失败，禁止force click、自动注入CSS或消除弹窗后冒称原始页面通过。
4. 导入：先真实下载模板，核验文件，再用原生文件选择器选测试文件；预览/取消/确认分别截图，对账输入有效行/错误行/写入行。自动化setInputFiles另行计A，不计H。
5. 保存：请求响应、业务表变化、审计记录、刷新后值、新浏览器context或应用重启后的值形成同一证据链；“toast成功”不是持久化证明。失败时业务表不变，允许失败审计，但不能有成功审计。
6. 最小V环境建议：Win7 Chrome109，1366×768（侧栏+弹窗空间风险），1920×1080，系统DPI100%/125%，浏览器100%/125%，深浅两主题；自动化沿用1024×900、768×900探针，并补390×844窄屏检查。移动端是否正式支持由主代理冻结，不影响桌面小窗不遮挡的要求。
7. 每次证据记录 `input_method=D/A/K/H`、`visual_checked_by`；每功能至少B+K+V，严格手工项另有H。失败重试保留首次失败与修复后重跑记录，不只保留最后成功截图。

官方输入语义见第9节O2；类型区别也由E11-E14本地源码直接印证。

# 5. 复杂场景、坏数据与事务矩阵

以下对每个受影响页面实际提供的提交、取消、重新进入等动作验收；不采用“所有坏数据只在一个表单测一遍”的缩减方法。仅后端已有但原型没有UI的行为保留为后端回归/旧页差集，不为测试新造按钮。允许对**失败注入**用mock；正常和压力链必须真实服务、SQL、序列化与浏览器。

| ID | 数据/步骤 | 必须通过的断言与停止条件 |
|---|---|---|
| X01 闭环主线 | 工种/资源/技能/日历→工艺/外协→物料齐套→批次→运行→比较→试调→采用→派工/多次报工→复盘/报表 | 各阶段实体/版本/数量/资源/时间一致；输入库、每阶段DB逻辑摘要、API与下载逐一对齐；不可仅给最终截图 |
| X02 计划身份 | 同时存在正式、候选、试调、旧历史，各页反复切换/前进后退/刷新 | 读范围相同；非正式不能报工；预览/取消不改正式；采用旧快照拒绝；不把内部身份词直接泄漏成业务文案（E24） |
| X03 排产约束 | 稀疏资格、瓶颈共享人员、跨日/短班/假期/效率、密集停机、冻结窗口插单、merged/separate外协 | 独立检查时间有效、前置依赖、技能、设备/人员时间占用不重叠、停机/日历避让、外协组、冻结/实际事实保留；失败计数+原因与完整工序分母一致 |
| X04 现场连续性 | 部分批次已开工/暂停/完成但不在本轮排产选择；修改真实资源；多个报工段；数量逐步达标 | 未选事实与占用不丢失；实际起止/资源/事件不可被新计划覆盖；未完工不得算完成，剩余工时不凭空取0 |
| X05 幂等/并发 | 同一表单双击、两tab同revision保存、同幂等键重试/不同payload、预览后他页修改再确认 | 一个合法提交仅一次业务效果；冲突返回明确原因并保留输入；所有计划/报工关联表同事务；不可多出成功历史 |
| X06 导入组合 | 空/全错/混合错、重复ID和规范化重复日期、错表头/工作表、已有对象引用、预览token过期、刷新后重发 | 每行位置/原因明确；预览零业务写；确认只按批准语义写；整批拒绝/部分接受必须与合同一致，不能自动猜测兼容 |
| X07 输入边界 | 空/空白/0/负/小数/超大整数/1e309/NaN/Infinity/bool，闰日/2月30日/日期倒置/边界年 | 服务和路由拒绝一致；无静默截断、转换失败当0、库存脏读自动清洗；文字超长/中文/单双引号正常可见（E23） |
| X08 文件边界 | 真实xlsx：压缩文件坏头/截断/不是xlsx、空表、16MiB附近（按实际config核对）、重复上传，公式样字符串、合法中文文件名 | 超限明确413；文件本体与multipart上限区分；导出ZIP可读、行列/类型/公式样文本转义正确；错误响应不命名成成功xlsx |
| X09 坏历史/数据缺口 | 旧摘要无字段、坏JSON、坏库存数、悬空引用/停用资源、未知枚举、缺实际结束/工时/资源 | 页面unknown/empty/error区分；错误可追溯；加载页无自动“修复”；只在独立坏库注入，FK关闭注入行为不进入正常造数 |
| X10 失败恢复 | HTTP 400/409/413/500/503（按实际合同）、请求断开/超时、SQLite写锁、磁盘满/只读、保存中断 | 错误/重试/取消可操作；成功反馈严格跟提交；失败后新连接检查无半写；写后响应丢失可安全查结果/幂等重试 |
| X11 长会话 | 切页/筛选/弹窗/详情200轮，1写+多读，数据增量/刷新/浏览器重开 | 不重复绑定、串选择、漏刷新、累积连接或内存；长会话产生的每次写均可查；无假空态/自动清掉草稿 |
| X12 时间与导出 | 起止相接、跨午夜/月/年、闰日、时区、历史version及资源过滤；2000/2001/20000/20001真实导出行 | 各页/CSV/XLSX同一日期包含规则与单位；大范围正确stream/拒绝；E25缩阈值stub不能抵实际性能 |
| X13 备份/恢复 | 仅维护fixture：好备份、坏文件、旧schema、恢复后校验失败、回滚成功、回滚失败、备份失败后清理 | 恢复前副本存在且可用；copied_pending_verify不能显示完成；失败/回滚失败保留原始证据；不顺带删除唯一好备份 |
| X14 离线/资源故障 | 断外网保loopback、冷cache；单个新JS/CSS/字体/图标丢失或坏hash、混装前后版本 | 不依赖CDN或远程请求；关键缺件阻断交付，非关键降级必须被显式批准；无“页200但不可操作” |

独立oracle要求：SQL/只读校验器按照定义重算而非直接比较同一个viewmodel输出；完整扫描所有任务及报工关联，抽样只用于人工肉眼核对，不能替代数据完整性断言。E19 sanity可复用，但还需补前置依赖、技能、人员日历、实际执行与业务数量检查。

# 6. 真正的规模与性能方案

## 6.1 建议的数据档位

**不是用户现网统计。** L1以已有2000节点基准为起点，L2/L3是5倍/25倍工序的探索性容量档；上线前须用经授权的脱敏统计对齐实际品种、资源、历史保留年限及常用过滤范围。数量是实际写入完整schema的行数，不是JS数组长度或把几行数据mock成巨大count。

| 档位 | 建议实际数据 | 使用目标与现有生成能力 |
|---|---|---|
| L0 完整性样本 | 20批×5工序=100；至少10机器/15人、内外协、齐套三态、3个历史版本、50条报工 | 全功能H/K/V逐项、精准oracle。小样本仅做功能，不叫压测 |
| L1 常规基准 | 100品种×2批×10=2000工序；30机器/60人、90天；10版本、约2万排程历史行，5000报工事件、2万操作日志 | 端到端性能起始档。E17可造2000主工序+48隐藏失败工序；资源/历史/报工必须另补完整fixture |
| L2 重载 | 250品种×4批×10=10000工序；100机器/200人；365天；30版本、约30万历史排程行，5万报工事件、10万日志 | 日常最大工作集与积累历史混合；页面/查询/导出/采用/报工同库运行。不能只测内存排产 |
| L3 容量/失效边界 | 1000品种×5批×10=50000工序；300机器/600人；多年度存储，查询仍按实际合法日期范围；100版本、最多约500万历史排程行，50万报工事件、100万日志 | 探索容量上限与可控拒绝，不预先承诺该规模全功能SLA。分批增长，先测磁盘/内存；超产品请求限制应明确拒绝，不强行放开上限 |

需补充的生成器合同（尚未实现）：

- 固定seed与绝对start_dt，保留完整file DB或逻辑输入、schema版本、资源分布、业务状态计数、文件大小/hash；每档至少3个seed，参数相同不重复使用已修改库。
- 正常集含不同工序长度、共享瓶颈、至少若干无备选资源、内外协混合、短班/跨午夜/请假/停机；数量/周期按业务可行范围生成。建议初始分布内制约80%、外协约20%、10%未齐套/部分齐套、10%已开始/部分完成，均是待业务确认假设。
- 历史版本/正式/候选/试调/报工通过真实服务生成合法关联；复杂业务造数时间单独记录，不从最终端到端动作计时中偷走实际工作。大规模storage fixture可批量插入，但需独立完整性/身份校验，不能为速度绕开生产查询或保存路径。
- 基础压力与负向case分开。E17隐藏批次单独标记，不把预期失败算系统错误，也不删除它们来美化统计。
- E17放大命令仍只有18机器/21人；大量积压可能超过可排日历。不得将“50k工序全失败很快”记为高吞吐。基准必须有足够日历/资源形成有效排程，超容量档另验正确失败。
- SQLite文件模式、journal_mode、page_size、外键开关、数据库/索引/连接设置均记录，使用产品连接行为（[database.py:76](/Users/lurenxing/GitHub/----/core/infrastructure/database.py:76)）。不为出好分临时开WAL/换内存库/改索引而不进入交付版本。

## 6.2 负载与计量

| 层级 | 负载与步骤 | 度量 / 不可替代关系 |
|---|---|---|
| 算法/服务 | 保留E21/E22基准；另对L1/L2完整排产与草稿/采用计时，单worker，真实CalendarService/SGS、真实wall clock | 总耗时、baseline/优化/持久化分段、候选数、失败/完成数、目标质量、最大资源占用；不把优化time_budget当整个请求上限 |
| 文件SQLite+HTTP | 独立实例：1个操作者、2个tab典型；并发1/2/4梯度，8仅短突发；1写+2读、排产中查看、导出中保存、双击提交 | 请求首字节/完整响应p50/p95/p99/max、错误分类、SQL耗时/次数、锁等待、CPU/RSS、FD/线程/连接、DB/WAL/临时磁盘增长 |
| 真浏览器 | L1/L2执行列表分页/排序/过滤、甘特2000/10000任务范围、详情、批改、报工、导出；UI输入走K，不能用page.evaluate直接触发业务 | 输入到反馈、响应到内容稳定、长任务/帧间隔、实际渲染条数/DOM节点、可见区域命中/遮挡、下载完成时间；HTTP快不等于UI快 |
| 长稳 | L1先30分钟，再L2建议2小时；循环写入/筛选/跨页/详情，带相同计划的重复读和增量数据 | 事件/计划零丢失，内存/连接无持续增长，失败可恢复；受控时限/子进程回收。不是网络多用户压力项目 |

- 每个环境记录Win7补丁/CPU型号与频率/核心数/内存/磁盘类型及空余、Python/SQLite/浏览器版本/包hash。主目标假设Win7 x64、2-4核、4-8GiB、机械盘或普通SSD，两类磁盘须分报；本机现代Mac结果不能换算承诺目标机时间。
- 冷启动至少5次只报中位/最大；热动作预热5次后每动作至少100个有效样本报p95；p99至少1000样本，否则标样本不足。长排产至少每seed3次（共9次）报每次/中位/最大，不伪称可靠p99。不得混合不同页面/不同规模分位数。
- 顺序对比旧页与新页，使用同机器、同输入库、同参数、同浏览器、同缓存冷热条件；测性能时不要并行跑pytest/造数/其他CPU重任务。业务正确性失败样本保留，不从延迟统计消失。
- `Server-Timing`已有[factory.py:469](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:469)接口，可辅助分段；after_request耗时不等于流式body传输和浏览器完成时间，另采完整下载/渲染计时。

## 6.3 建议初始预算（需基线校准后签字）

| 指标 | L1建议 | L2建议 | 依据/限制 |
|---|---|---|---|
| 本地输入/筛选/弹窗反馈 | p95≤100ms；单次无≥1s主线程冻结 | 同左；数据重算另显示真实pending | 用户连续操作的工程目标，非既有SLA |
| 简单列表/详情HTTP（热） | p95≤1s，p99≤2s | p95≤2s，p99≤4s | 待同机baseline验证；原型本地数组不算baseline |
| 复杂首屏/报表/甘特内容可用 | p95≤3s | p95≤8s | 包含HTTP+渲染；E21图分析已有avg2.5s/max5s仅是子系统边界，不能直接推出本预算已满足 |
| 单行保存到确认可见 | p95≤1.5s，无重复写 | p95≤3s，无重复写 | 仅小事务；大型导入/采用分开统计 |
| 真实Excel输入/导出 | 2000行≤20s | 20000行≤60s | 暂定完整文件完成上限；按报表是否支持stream区分；20001行允许明确拒绝，不擅自改变E25合同 |
| greedy完整排产 | 最大≤30s | 最大≤120s | 探索目标，不是源码已有保证；需包含收集/基线/存储。improve额外配置预算单列，逐阶段检查预算遵守 |
| 内存稳定性 | 假设4GiB目标机：测试实例与浏览器合计峰值先以≤1.5GiB评估 | 先以≤2GiB评估 | 需验证OS与其它必需进程余量；两小时稳定阶段RSS较热稳起点增长≤10%，且无连续上升趋势；不是普适阈值 |
| 相对退化 | 同负载p95相对旧实现≤1.20倍且绝对预算达标 | 同左 | 20%是建议警戒线，需排除测量噪声；旧实现不支持的新功能只看绝对预算和稳定性 |

硬停止：数据错/丢/串版本、重复写、无响应且无法恢复、内存持续增长、进程崩溃、长时锁死、正常路径外链/资源404、错误被包装成功，一次可复现即阻断。预算连续两次超限或任一已签硬上限超限也阻断；先记录归因，不现场调高阈值放行。L3未作为交付容量承诺时仅报告边界，不用其失败替代L1/L2验收。

# 7. 实际命令目录与待补执行器

**下列命令均未在本轮执行。** 仅允许在第2节环境条件落实、未来实施/验收授权后运行。`QA_ROOT`每次会话唯一；同一C编号复跑也换新basetemp/输出目录。命令里`tests/...`相对路径均相对于显式设置的`QA_CHECKOUT`，不是让用户在当前工作区执行。

| ID | 源码支持的命令 | 产物/边界 |
|---|---|---|
| C01 定向后端 | `"$QA_PY" -B -m pytest -p no:cacheprovider --basetemp="$QA_ROOT/pytest-C01" --junitxml="$QA_ROOT/evidence/C01.xml" -q tests/excel_data_io/test_excel_import_hardening.py tests/material/test_material_finite_quantity_contract.py tests/operation_execution/test_operation_execution_state_revision.py tests/gantt/test_gantt_adjustment_publish_execution_revision.py tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py` | E23-E25真实用例；只证明所列合同，不能宣称全页已接入 |
| C02 离线与打包合同 | `"$QA_PY" -B -m pytest -p no:cacheprovider --basetemp="$QA_ROOT/pytest-C02" --junitxml="$QA_ROOT/evidence/C02.xml" -q tests/app_runtime/test_frontend_offline_static_assets.py tests/app_runtime/test_validate_dist_static_payload.py tests/gate_meta/test_frozen_bundle_contract.py tests/gate_meta/test_win7_networkx_package_contract.py tests/web_pages/test_static_versioning.py` | 包规则/源资产检查，不构建exe、不证明目标机启动 |
| C03 真实浏览器几何 | `APS_BROWSER_SMOKE_REQUIRED=1 "$QA_PY" -B -m pytest -p no:cacheprovider --basetemp="$QA_ROOT/pytest-C03" --junitxml="$QA_ROOT/evidence/C03.xml" -q tests/app_runtime/test_ui_browser_geometry_smoke.py` | 自动短时服务/Chrome；需显式正确APS_CHROME_PATH及Node fetch/WebSocket；CI存在会skip，必须检查实际节点passed，不能通过删CI变量伪造CI证据 |
| C04 旧页截图底座 | `"$QA_PY" -B tests/_scripts_e2e/capture_ui_baseline.py` | checkout/output/ui_baseline下20路径双主题；短时服务；后续仍需真目视与动作态截图 |
| C05 复杂业务E2E | `"$QA_PY" -B -m tests._scripts_e2e.run_complex_excel_cases_e2e --out "$QA_ROOT/evidence/complex" --cases Case01,Case02,Case03,Case04,Case05,Case06 --repeat 3 --seed 1000` | 6类×3轮，输入xlsx/输出/逐case result与总报告；repeat会改变seed；是test_client，不是浏览器 |
| C06 L1造数起点 | `"$QA_PY" -B tests/_scripts_e2e/run_browser_extreme_stress_case.py --workdir "$QA_ROOT/L1" --seed 20260909 --parts 100 --batches-min 2 --batches-max 2 --ops-per-part 10 --calendar-days 365` | 2000主工序+48失败边界；不加--force；只造库/manifest，不跑服务/性能，资源仍固定，需补历史报工与资源档位 |
| C07 L2瓶颈探索起点 | `"$QA_PY" -B tests/_scripts_e2e/run_browser_extreme_stress_case.py --workdir "$QA_ROOT/L2" --seed 20260909 --parts 250 --batches-min 4 --batches-max 4 --ops-per-part 10 --calendar-days 365` | 10000主工序+48；仅固定小资源的瓶颈fixture，不是已满足第6节完整L2 |
| C08 内存排产对照 | `"$QA_PY" -B tests/_scripts_e2e/run_synthetic_case.py --parts 100 --batches-min 2 --batches-max 2 --ops-per-part 10 --calendar-days 365 --seed 7 --mode both --objective min_tardiness --time-budget 20 --export-gantt-dir "$QA_ROOT/evidence/synthetic"` | 真ScheduleService内存模拟；无HTTP/浏览器及目标磁盘证据 |
| C09 图子系统性能 | `"$QA_PY" -B -m pytest -p no:cacheprovider --basetemp="$QA_ROOT/pytest-C09" -q tests/scheduler_graph/test_graph_performance.py` | E21；其中还校验repo/evidence/scheduler_graph/performance_2000_nodes.txt，隔离checkout缺已有证据应如实失败，不引用旧日志当本轮通过 |
| C10 优化质量矩阵 | `"$QA_PY" -B tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py run --workers 1 --time-budget-seconds 10 --output "$QA_ROOT/evidence/matrix.json"` | 实际48/8工序×目标；输出允许repo外路径；只用run/compare，不用update-baseline给退化背书（E21） |
| C11 专项基准 | `"$QA_PY" -B tests/_scripts_e2e/benchmark_optimizer_medium_gate.py --run --workers 1` | E22的3个命令、输出在测试checkout/evidence；不含全站性能；离线benchmark数据缺失需先报告，不自动下载 |
| C12 完整门禁 | `"$QA_PY" -B scripts/run_quality_gate.py --require-clean-worktree --no-long-gate-cache --long-gate-force-rerun-all` | 在已提交最终HEAD的独立干净checkout执行；会写/整理证据并启动测试实例。保留manifest、collect、required清单、command receipts、stdout/stderr、环境/源码绑定。不是当前目录的只读检查 |
| C13 恢复失败护栏 | `"$QA_PY" -B -m pytest -p no:cacheprovider --basetemp="$QA_ROOT/pytest-C13" --junitxml="$QA_ROOT/evidence/C13.xml" -q tests/migration_db/test_restore_integrity_check_contract.py tests/migration_db/test_migration_restore_integrity.py` | **会备份/恢复/清理测试临时文件**，仅未来维护fixture授权后；本轮禁执行；还需全业务恢复演练 |
| C14 原型离线/组件 | `node 前端设计/ui_kits/workbench/tests/workbench-offline-assets.cjs`；`node tests/workbench-batches-style.cjs` | 当前缺Node依赖，不能立即运行；后续只用已配置、版本锁定工具链，不能npx触发临时安装。此类仅证明原型 |
| C15 原型浏览器 | `node 前端设计/ui_kits/workbench/tests/batch-workbench-browser.cjs`；`node tests/field-gantt-focus-boundaries.cjs` | 前者默认file页；后者setContent无需服务；会启动/关闭浏览器并落截图。当前工具链缺失；不是移植后成品验收脚本 |
| C16 冻结exe | `python validate_dist_exe.py "C:\APS-QA\case-unique\app\排产系统.exe"` | 仅独立Windows测试机的全新解包副本；先设独立APS_*，且APS_LOG_DIR必须对齐该副本app\logs以满足脚本现有读取方式。绝不对正式安装目录运行；额外核对runtime DB确为测试路径，补全部资产/功能检查 |

新流程至少还缺：

- `action_id`驱动的**真实后端浏览器功能suite**及独立K/H/V签收记录，不能直接把C15 URL替换成生产首页就认为支持新流程。
- 具备规模/资源/版本/报工事件参数、绝对日期、合法关联和manifest的完整file DB fixture扩展；真实坏文件/坏库案例库。
- 有时限、可核对实例/DB、可收口的人工验收服务运行器；使用产品等价并发的混合HTTP/browser负载驱动与延迟/内存采集。
- 全资产递归清单、打包payload/hash/HTTP/MIME检查及旧页下线清单执行器。
- 升级/代码回退/旧schema恢复/失败再回滚的**完整业务**演练。以上是后续实施项，不存在的脚本不写成“现有命令”。

# 8. 旧页备份、下线及回滚验收

旧页归档是代码/资产交付物保存，不等于业务数据库备份。只在主代理获准实施后执行，按以下顺序形成证据；本轮不做任何备份。

| 阶段 | 需要保留的证据与操作验收 | 停止线 |
|---|---|---|
| R01 下线前归档 | 主代理冻结旧页/模板/JS/CSS/本地字体图标/说明/入口映射；保存实际旧运行payload、源码状态、每文件hash、依赖和构建信息；归档放离线非公开目录，证明可重新解包。已有未提交内容不能遗漏 | 没有实际可读取的归档及hash核对，不能下线；只有Git commit名不够 |
| R02 数据保留 | 在授权的合成旧版本库上记录schema、正式/候选/草稿计划、历史、报工、主数据、配置与日志清单；升级后按字段/数量/外键/业务意义对账 | 差异不在获准迁移白名单，立刻停止；不借UI移植清历史/改计划 |
| R03 新版放行 | 206能力族及其实际子动作逐项有结论，另获批准的旧页差集有处置；P/X适用项通过、L1/L2预算签字、C12最终HEAD门禁、Win7冻结包离线验收 | 范围内动作仍演示数据/假保存/未接后端/缺手输或目视，不能宣称全功能完成；不以P矩阵广项追加原型没有的旧功能 |
| R04 旧页下线 | 根据主代理的明确入口处置表逐个验证侧栏、旧书签、直接URL、帮助链接、下载/旧静态入口；预期是重定向或明确退役响应，由主代理决定；记录每项请求与屏幕结果 | 仍可从未登记入口进入可写旧页，或下线漏功能，无证据即停止；本报告不选择路由架构 |
| R05 仅代码回退 | 专用测试库：新版成功写入一组测试数据→停测试实例→换回归档旧代码/资产→冷缓存及保留旧浏览器缓存各测一次→重新查询/使用新写入数据 | 若schema未变，回退不得顺手恢复旧DB丢掉新写入；旧代码不能读新版数据则不承诺代码回退 |
| R06 schema相关回退 | 若确实有schema变化，由主代理另外提供可验证迁移与回退策略。分别记录旧schema副本、升级结果、反向恢复过程及恢复后的所有业务摘要 | 禁止把旧DB盖回去当无损回滚；需要丢弃升级后写入时须另行明确批准，并清楚报告RPO |
| R07 故障演练 | 损坏/截断备份、目标库busy、空间不足、恢复后schema失败、回滚文件坏/回滚失败；保持故障前/故障后库与审计、重启重连后核查 | copied_pending_verify不算完成；自动回滚失败不得给成功页面/继续写数据；保留证据等待人工处置 |
| R08 交付留档 | 安装包/解包树hash、全部资源清单及许可、运行环境、测试清单/结果、所有下载文件校验、目视签名、已下线清单、恢复步骤/实际用时 | 不能用开发截图/旧HEAD测试或源文件存在替代安装后实际payload；归档未验证不能删除旧运行资产 |

回退预算建议：**代码回退RPO=0（不换DB），RTO先以15分钟为演练目标**；这是待目标机实测假设。涉及备份恢复时RPO等于选定快照之后的变更窗口，不能沿用RPO=0。RTO从决定回退到旧版关键流程恢复可用计时，不只算文件拷贝。

# 9. Win7、离线浏览器和静态资产交付

## 9.1 已有目标与官方核对

- 本地打包合同锁Win7 x64/Python3.8/PyInstaller4.10（E26）；[aps_win7_chrome.iss:1](/Users/lurenxing/GitHub/----/installer/aps_win7_chrome.iss:1)声明Chrome109运行时版本109.0.5414.120。该声明不证明目标机实际安装的exe版本和hash。
- O1 Google官方支持表：Chrome109为Windows7最后支持版本，109于2023-01-10发布。因此“在本机最新Chrome通过”不能代替Chrome109，不能为迁移默认提高目标浏览器。
- O2 Playwright官方明确：fill聚焦并触发input；pressSequentially逐字符产生键盘事件；正常click执行可见/稳定/未遮挡等检查，dispatchEvent是程序化点击。由此采用第4节分级，不把fill包装成手输。
- O3 Playwright当前官方安装页列现代宿主要求，没有Windows7。测试控制器应留在受支持的开发/测试机；Win7目标机另做真实Chrome109有界验收。不能宣称当前Playwright在Win7有官方支持，也不能假定任意版本Playwright控制Chrome109都兼容，必须先小范围核验实际组合。
- O4 Chrome官方文档说明Chrome112引入统一的新Headless实现。本仓库E08/E10固定`--headless=new`；**现有探针不能不经验证直接作为Chrome109证据**。本轮未运行109，不对该参数在109的具体表现下“必定成功/必定失败”的结论；目标机有头验收单列。

官方来源（2026-09-09读取；web工具未返回可读内容后，经网页抓取读取下列官方正文；未引用社区二手兼容性结论）：

- O1 `https://support.google.com/chrome/a/answer/7100626?hl=en`
- O2 `https://playwright.dev/docs/input`
- O3 `https://playwright.dev/docs/intro`
- O4 `https://developer.chrome.com/docs/chromium/headless`

## 9.2 静态资产必须增加的验收面

1. 保留E15/E16/E26/E27已有测试，新增页面使用的每一个运行时依赖都进入可追溯清单：入口JS/CSS、拆分chunk、图片/图标/字体、导入导出依赖、说明、许可证。原型资源位于“前端设计”，E26收包规则当前只收产品目录，不能假设自动带入。
2. 同一最终HEAD对比源构建输出、包内文件、安装后文件、HTTP返回内容的hash/长度/MIME；E27只有两个非空锚点，不足以证明新增全套payload一致。
3. 对最终构建JS做Chrome109语法与API使用核查，对CSS/字体/图标用109实际渲染。Node语法检查、React/Babel文件hash、py38扫描各管不同层，不能互相替代。
4. 断外网但保留loopback，清空**测试profile**缓存后走全部功能，记录所有请求；不能以Playwright整context offline使本地后端也失联后宣称离线业务不可用。正常路径外链为0、关键资产失败为0。
5. 每个资源损坏/缺失用例只改解包测试副本，证明门禁或明确可见错误能拦住；不能自动回退CDN、偷偷注入测试资源或保留旧cache掩盖漏包。
6. 最终Win7机器不要求Python/Node/npm运行时；验收脚本可由测试机执行，但交付应用必须在无开发工具的干净目标环境启动并完成关键业务。构建依赖升级另审，主线约束不改变。

## 9.3 与主代理109内核验证的交接及判断界限

| 证据层 | 所需材料 | 可以下的结论 / 不可以下的结论 |
|---|---|---|
| 浏览器官方支持 | 主代理核验的浏览器产品名、版本线、操作系统/架构、官方来源及日期 | Chrome/Edge各自的支持终点与产品选择；不把两者的109结论直接写成“世界上任何Win7浏览器最高都是109” |
| 隔离Chromium109 | 可执行文件来源/hash、完整版本/revision、宿主OS/架构、headless/headed、启动flags、原型文件hash、成功与失败的page/action | 该内核/宿主/原型快照实际运行结果；不能推成Chrome品牌包、Edge品牌包或Win7设备上的字体/驱动/IME已经通过 |
| Win7 x64目标机 | 本节W01-W10及L1/L2、B/K/H/V结果；实际打包浏览器exe版本/hash | 该硬件/系统/浏览器组合可交付；没有实机就明确“缺Win7实机证据”，不得用现代Mac/Linux性能换算 |
| 最终安装包 | 同一最终HEAD，干净安装与保留数据升级，安装后payload/快捷方式/数据根，正常用户操作 | 实際交付物可用；开发目录或解包版成功不等于安装器流程成功 |

### 已接收的Mac109实测证据

本子任务只解析已提供JSON、核对结果计数/环境/错误集合、计算证据文件hash并列出既有截图文件，没有重新运行浏览器，也没有逐图目视。

| 证据 | 核查结果 | 结论限制 |
|---|---|---|
| [runtime-probe.json](/tmp/aps-chromium109-assessment/runtime-probe.json:1) | `environment=darwin/arm64`，`version=109.0.5414.46`；15入口×2主题×2宽度=60，60项pass=true；errors=[]、requests=[]；state包括独立trial；主代理给出的视口为1920×1080/1392×924 | Mac109原型入口/所列状态通过，不是Win7或后端持久化。JSON的loadMs仅单状态加载样本，不能作L1/L2大库或目标机p95预算证明 |
| [maintenance/measurements.json](/tmp/aps-chromium109-assessment/maintenance/measurements.json:1) | 1510项全部pass=true；errors/requests/downloads为空；1920/1392/390×light/dark×current/sample | 脚本只检验系统维护导航，且明确断言正式维护动作仍不可用，见[system-maintenance-navigation.cjs:26](/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/tests/system-maintenance-navigation.cjs:26)。requests跟踪在初始加载完成后才开启（120-125行），不能当作完整首屏资源网络审计 |
| [workflow截图目录](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-1iNiul) | 56个文件，全部为PNG。主代理回报强制109运行原workbench-workflow-browser.cjs得247checks/56screens通过 | 本子任务已核对文件数量，247checks及强制指定内核的执行归属采用主代理报告；目录没有stdout/receipt，未独立重跑、未逐图看图，不把截图数转换成逐页H/V签收 |
| 主代理补充的field-gantt-surfaces-browser.cjs结果 | 强制109执行PASS：1186checks、72states、56screens；结论及证据索引交由上述Win7评估稿统一归档 | 此项为主代理报告，本子任务按收束要求未再读原始文件、未重跑或目视；仍仅为Mac109原型甘特覆盖，不是Win7/真实业务/性能证明 |

证据内容指纹：

- runtime-probe.json SHA256：`8dfb5276b63518dd6ba312abe0f1d406e45f010157e3a375436ab67a6cb9e6ad`。
- maintenance/measurements.json SHA256：`0a6d6f25aeccd7876f7ecb09b5a82157852eb1d90ebb54e389da973929442c3c`。
- 主代理提供下载来源标识：官方Playwright v1.29.2、revision1041、mac-arm64 Chromium109.0.5414.46。本子任务不重复下载/核查获取链。该版本与本地Windows运行时安装脚本声明109.0.5414.120不是同一完整版本，最终Windows包仍需自己的payload/版本绑定。

现有JSON同时记录了`CSS.supports(color-mix(...))=false`、`text-wrap:pretty=false`等能力信号（[runtime-probe.json:16](/tmp/aps-chromium109-assessment/runtime-probe.json:16)）。这不否定已通过的入口和动作，但**pass=true不等于逐像素同外观**。具体受影响样式、fallback与视觉差异以主代理Win7评估稿为专题入口；本报告不重复CSS实验，不仅凭能力探针宣称“所有外观完全一致”或“必须整套重做”。

收尾一致性核对已读最新版[Win7评估稿](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/drafts/win7-runtime-assessment.md)：当前未发现迫使放弃既有布局/配色/交互的兼容阻塞，建议有条件保留样板；部分残留不兼容CSS已被后置样式覆盖或当前无匹配节点，不能冒充当前页面故障。正式交付仍需兼容资产处理、真实后端、Win7实机及性能验收；本子任务未重跑其中实验。

正式归档时把这批临时目录结果与主代理的执行命令、强制109设置、浏览器/源码hash关联，避免系统临时目录回收后只剩数字。补证据归档不要求重复已完成实验；后续有实质代码变化再定向补测。失败需保留最小复现、console/网络记录、截图与实际flags，而非只报总断言数。

验收决策：

1. 109全功能/视觉通过，只解除“该内核承载”阻断，继续后端、Win7实机与打包门禁，不能直接宣布全量移植通过。
2. 仅部分CSS/API/事件行为失败，先定位具体能力和受影响action；不得把一处失败扩大为“整个原型不能复刻”。复刻候选用同一视觉/功能清单验证，保留相同布局、尺寸、色彩、信息密度、表格/甘特含义及完整动作。
3. 如果原型载体在目标内核不可用，按用户要求以兼容实现复刻同外观；“使用同一技术栈/同一DOM”不是目标，但“关键图形换样、删掉交互、无法保存”不能算兼容。实现方案归主代理，本报告不选前端框架或路由架构。
4. 复刻基线取获批准原型快照与相同fixture。原型不能在Win7运行时，用其已验证宿主的截图/几何规范作为设计参照，再用Win7实际字体建立可解释容差；不能先修改原型来让差异自动消失。跨OS抗锯齿差异单独标注，文字裁切、缺字、遮挡、错误时间比例不属于可忽略差异。

## 9.4 Win7实机专项矩阵

本轮没有实机，全部为`not_run`。W01-W10是P/X矩阵的环境补充，不是用10项代替逐页全功能。

| ID | 实际目标机操作与样本 | 留证与停止线 |
|---|---|---|
| W01 环境身份 | 记录Win7版本/build/SP/补丁、x64 OS及实际浏览器进程架构、CPU/内存/磁盘、显示器原生分辨率、浏览器完整版本和exe hash、UI语言、时区；本地控制台与RDP/VM分开标 | 环境manifest缺字段则证据范围相应缺失；UA字符串或模拟viewport不能证明Win7/实际架构；未实际测试不得承诺Win7所有硬件 |
| W02 字体载荷与字形 | 核对系统字体与包内字体清单/hash、HTTP字体响应；检查中文设备/人员/长图号、数字0/1/8/9、小数/负号/单位、中文标点、混合中英文；400/500/600/700、代码等宽、表格等宽数字分别目视 | 保存选中元素的实际Rendered Fonts（工具可提供时）、样本文字宽高、字体请求和屏幕截图。computed font-family/document.fonts.ready只作辅助，不能单独证明实际使用字体或粗体效果；缺字、数字错位、关键文字裁切阻断 |
| W03 字体冷启动/退化 | 测试profile冷缓存首开、字体加载前后、字体正常/临时缺失/加载失败（仅解包测试副本），逐页长标签和错误提示 | 原型[typography.css:14](/Users/lurenxing/GitHub/----/前端设计/tokens/typography.css:14)只有400的url字体且font-display:swap，24行另有系统栈；不得只按注释推断“系统字体一定先用”。首屏跳动导致误点、按钮尺寸改变、关键字体丢失后仍假通过均阻断 |
| W04 DPI与窗口尺寸 | 至少两物理分辨率1366×768/1920×1080，系统DPI100%/125%，浏览器zoom100%/125%；按OS要求重新登录后复核设置；目标用户存在150%时加测；窗口最大化/缩小/恢复、滚动条同时出现 | 记录物理分辨率、系统DPI、browser zoom、devicePixelRatio、inner/outer尺寸、截图像素尺寸；不得把Playwright deviceScaleFactor等同系统DPI。全部弹窗/确认/错误/分页按钮可见可点，甘特坐标命中不漂移 |
| W05 GPU默认渲染 | 在实际目标机以交付launcher的真实flags启动，不先加disable-gpu；记录chrome://gpu的实际图形状态/驱动信息及本地或RDP会话；深浅色/高密度甘特滚动缩放拖动、遮挡/恢复窗口、连续切页 | E08/E10探针加了disable-gpu（[ui_geometry_probe.mjs:16](/Users/lurenxing/GitHub/----/tests/ui_geometry_probe.mjs:16)），只能证明该探针路径，不覆盖目标默认GPU。黑块/闪烁/时间条消失/命中偏离或GPU进程反复失败阻断 |
| W06 软件渲染/受限设备 | 与W05同库/页面/分辨率做单独GPU受限或软件渲染诊断，明确记录实际生效状态；如目标仅有VM/RDP则按其实际交付范围报告 | 不把“加参数后看起来正常”算默认交付通过；若需要发布固定flags，须主代理明确纳入交付并重跑功能/性能。VM虚拟显卡成绩不能承诺物理旧显卡表现 |
| W07 中文输入法 | 用户目标机实际安装的IME名称/版本；英文直接输入与中文拼音选字、连续组合、空格选词、Enter选字、Esc取消、组合中点保存/切页、全半角切换、中文标点、撤销、退格，覆盖搜索和持久化字段 | 原生录屏/输入步骤/提交请求次数/最终存储值，配只读事件采样可记录composition序列。组合未结束误提交、吞字、重复输入/重复保存、选字触发表单提交均阻断；React vendor中存在composition代码不等于应用IME验收 |
| W08 原生控件与文件 | 日期/时间控件、select键盘选择、焦点环/tooltip、Windows文件对话框输入中文路径、取消/选择/重新选择、下载中文xlsx/csv、重复同名文件、打开真实下载 | 默认应用窗口和普通浏览器窗口按实际交付形态测试；setInputFiles/DOM伪File不能计原生选择器验收；Windows文件名编码、实际内容和DB写入一致 |
| W09 启动/权限/路径 | 独立测试机干净安装后普通用户启动（安装提权与日常运行分别记录）；中文用户名/含空格路径；无Python/Node/npm/网络；重复启动同库与独立测试库；退出/再开 | 快捷方式确实选到预期浏览器/同一app，runtime contract与测试DB一致、默认数据根可写；没有从开发目录偷读资源。安装器定义见9.5，不在现用工作机试装 |
| W10 性能与长稳 | 第6节L1/L2原始数据在该实机重跑，带真实字体、目标DPI、交付GPU模式、原生输入；排产/大导出时仍能查看状态、等待/取消语义真实；做冷启动/热稳/长稳 | 分别记录CPU、应用/浏览器各PID私有内存与系统可用内存、磁盘/锁等待、UI长任务及错误；不以简单累加多进程WorkingSet冒充精确物理占用。超预算/持续增长/无响应按第6节阻断 |

字体附加证据：原型本地存在[MicrosoftYaHei-Regular.ttf](/Users/lurenxing/GitHub/----/前端设计/fonts/MicrosoftYaHei-Regular.ttf)，本轮未审计字体来源或再分发授权。供应物需补字体来源/许可记录；**文件存在或注释写“uploaded brand file”不是授权证据**。这只是交付材料门禁，不对授权是否合法作未经核实的法律结论；也不擅自删除或替换字体。现有等待[document.fonts.ready](/Users/lurenxing/GitHub/----/tests/ui_geometry_probe_page_eval.mjs:15)不检查每一字形实际字体，需补W02/W03。

## 9.5 安装器不能靠“另选目录”实现隔离

- [aps_win7.iss:9](/Users/lurenxing/GitHub/----/installer/aps_win7.iss:9)固定共享根`{commonappdata}\APS\shared-data`；17行固定AppId；62-70行写HKLM配置且有受条件控制的共享数据卸载删除。
- [TryStopKnownApsRuntime:625](/Users/lurenxing/GitHub/----/installer/aps_win7.iss:625)会处理共享根、旧数据根、已登记应用目录；650行的清理流程还有这些目录的删除调用。此处不判断何种UI选择触发它，只确认“改安装目录”不是隔离证明。
- **安装/升级/卸载/全清流程必须在独立Win7 VM或专用测试机，且不存在用户真实APS实例和数据。** 不在用户实际工作机靠`APS_DB_PATH`或`/DIR`隔离安装器；新建Windows账户也不能独自隔离HKLM及ProgramData共享状态。
- 主程序和浏览器运行时安装包分开核验：包hash→安装后exe/静态/字体hash→快捷方式launcher→实际启动浏览器版本→应用实例/DB→P/X/W测试。浏览器仅由主代理负责获取，不在本报告工作内重复下载。
- C16是解包exe的验收器，且需要测试侧Python。它不能替代“未安装Python的Win7普通用户从快捷方式操作”的另一份证据；安装器自己的共享路径也不会因C16的env配置自动改变。
- 卸载默认保留数据、明确选择清数据、取消卸载、旧版本升级和升级失败回退分别在不同测试快照中演练。每次先保存**测试**库和目录清单，恢复后对账，不能操作或触发用户备份。

## 9.6 实机证据采集命令与性能可比性

下列为目标Win7测试机上可选的**只读元数据命令**，本轮未执行，也不启动浏览器、不安装依赖。先检查工具存在；WMI不可用需保留错误，不自动重启服务/安装组件。已有[verify_installer_wmic_availability.bat:17](/Users/lurenxing/GitHub/----/tests/verify_installer_wmic_availability.bat:17)可用于测试机的可用性诊断，不等于整个安装/启动通过。

```bat
ver
where wmic
wmic os get Caption,Version,BuildNumber,OSArchitecture /value
wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /value
wmic computersystem get TotalPhysicalMemory /value
wmic path Win32_VideoController get Name,DriverVersion /value
reg query "HKCU\Control Panel\Desktop" /v LogPixels
reg query "HKCU\Control Panel\Desktop" /v FontSmoothing
reg query "HKCU\Keyboard Layout\Preload"
```

- `LogPixels`缺项不推断DPI100%；记录实际系统设置和页面测量。注册表输入法登记不能证明当前启用哪个IME，另记实际选中输入法与版本。GPU驱动名称不能替代浏览器真实图形功能状态。
- 浏览器启动和截图仍由已授权、隔离、有期限会话执行；将chrome://version中的实际完整版本/命令行、chrome://gpu状态与包hash关联。若命令行带敏感字段，报告只保留所需非敏感flags，不保存令牌。
- 优先使用目标机已有任务管理器/性能监视器，按本次运行PID记录应用和浏览器进程树。磁盘型号/空余量、采样间隔、计数器单位、CPU多核口径、RSS/PrivateBytes/WorkingSet区别写清；某项工具不具备就标缺失，不填0。
- 限制对比变量：原型内核验证、移植后源码态、冻结exe、安装后快捷方式四组分报；旧/新UI性能只在相同后端与相同fixture上比较。JS数组示例不能作为后端时延基线；本机Babel原型首次编译也不能冒充生产后端耗时。
- GPU模式、IME是否组合中、DPI、字体冷热、RDP/本地会话和机械盘/SSD不能混进同一统计桶。带录像/DevTools性能采样与不带采样分开测，记录采样开销；缺Win7数据时第6节预算仅为待验证目标。
- 当前结论是：**Mac109原型60状态与所列工作流有实测通过证据，不能再说只有静态推断；浏览器/CSS109具体结论由主代理Win7评估稿承接，Win7整机、迁移后真实业务和最终包验收仍无本子任务的通过证明。** 不因为尚缺Win7证据就推断原型必然不可用，也不以现代宿主成功先行下线旧页。

# 10. 最终交付证据包和总停止线

建议未来每次验收保存一个不可混写的run目录，包含：

- `manifest`：run_id、开始/结束时间与时区、HEAD/dirty状态/文件hash、环境、fixture/schema/hash/行数、实际服务实例/测试DB、工具版本、命令、退出码、时限、已停止的PID。
- `coverage`：冻结的page/action全集、计划身份/场景维度、pytest/node/browser用例映射、D/A/K/H分类、V签名；passed/failed/blocked/skip/xfail/退役分别计数。
- `backend`：原始JUnit、每条关键请求/响应摘要、独立SQL/oracle、事务前后逻辑摘要、错误/审计；不混入用户库或密钥。
- `browser`：每步骤截图和已查看记录、视频/trace（若所选工具支持）、console/pageerror/失败请求、目标命中/焦点/输入方法、实际下载及内容校验。不要因截图数量大就省略逐图查看。
- `performance`：原始每次样本、冷/热、规模/资源分布、并发、分位数算法、CPU/RSS/磁盘/长任务、超限样本、同机baseline与对比；保留错误请求，不只出汇总绿灯。
- `release`：旧版归档清单、下线入口对账、最终包及安装后payload、Chrome109/Win7证据、完整恢复演练与实际RPO/RTO。

**任一条件成立即不得批准旧页下线/正式交付：**

1. 数据路径或实例身份无法确认隔离，可能访问/清理用户db、计划、备份、日志、profile。
2. 未按既有206能力族清单完成验收映射/处置，范围内功能无后端、成功依靠mock/本地示例/注入CSS，或者刷新后业务数据丢失；清单外旧选项不得默默加入或冒称已覆盖。
3. 任一业务正确性、幂等、事务、计划身份、坏数据不清洗、回滚保护合同失败。
4. 只有自动fill/DOM调用、只有PNG、没有逐功能K/H（按用户要求）和实际V记录。
5. 用8/48工序、单任务大资源池或单页几何fixture声称高复杂压测完成；没写实际行数、资源数、历史和报工规模。
6. 预算未获确认/未在目标环境验证，正常负载超签字预算、长期无响应、内存/连接持续增长。
7. Chrome109/Win7离线及冻结payload证据缺失，外部资源或漏包仍存在；缺依赖或CI skip被当passed。
8. 没有已验证旧版归档/完整恢复演练，或者回退会丢新版数据但没有明确批准。
9. 最终代码与测试代码不一致、门禁依赖旧证据、工作区dirty却宣称clean proof；已有dirty工作区的局部诊断可保留，但不能替代最终放行。

**本子任务状态：评估草稿完成并收束，未实施移植或执行验收。** 已接收主代理Mac109原型兼容性实测，区分了本子任务只读核查与主代理报告；不能据此给迁移后的页面业务、大规模压测或Win7交付填passed。浏览器专题已交叉引用，不再扩展调查。

交接摘要：

- 已完成：引用并对齐已完成的206能力族主清单（不另造分母）；29组现有测试/门禁源码证据；数据库/目录/实例隔离方案；24类条件化验证视角；D/A/K/H/V证据分级；14类复杂/坏数据矩阵；L0-L3实际规模与条件化预算；16项现有命令；8阶段备份下线/回滚门禁；10项Win7实机专项及安装器隔离边界；最新版Win7专题结论交叉核对。
- 仍缺：206能力族的实际字段/子动作到新页、后端和验收证据的实施后映射（能力清单本身已完成）、旧生产页差集逐项处置、移植后真实后端浏览器全功能及手输/目视签收、完整大文件库fixture与混合负载实测、Win7物理环境字体/DPI/GPU/IME证据、冻结安装payload全资产校验、全业务无损回退演练和最终HEAD clean gate。
- 本轮只改本文件；未提交；保留原有工作区改动；不把主代理报告的原型通过数当成本子任务运行或迁移交付验收通过。
