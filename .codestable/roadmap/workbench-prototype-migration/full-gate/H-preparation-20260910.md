# H 准备核查与有限债务分诊

- 日期：2026-09-10。
- 状态：首跑准备已交接；完整 quality gate 未运行，尚无 clean-worktree proof。
- 本轮仅修改 `full-gate/` 内三份准备材料。没有产品、tests、registry、Git index/commit、基线、阈值或全局配置写入；没有运行生产库、旧预览或新浏览器/编译重任务。
- 主线负责分批本地提交与最终 HEAD；H 等隔离工作区和重任务窗口后执行。当前不因其它域中途增删文件做全局登记，严格等冻结 handoff。

## 结论与首跑条件

| 项目 | 已有真实结果 | 本次处置 |
| --- | --- | --- |
| tools Pyright | 62 files，0 errors / 0 warnings，2.027 秒，exit 0 | 工具显式范围可用，不是产品/全部 tests 类型证明 |
| tools Ruff | 对同样 62 个配置路径 `--no-cache`，`All checks passed!`，exit 0 | 不自动 fix；不代表完整默认 Ruff 通过 |
| 工具范围一致性 | `pyrightconfig.tools.json.include == QUALITY_GATE_TOOL_PATHS` 为 true | 未扩大/缩小范围；62 个源 SHA-256 已保存 |
| command plan | 19 步，SHA-256 `a9ef9378c8dc982a3f7e83a0122937ff193d3c80ed59bce36145789762cff35e` | 见 `H-command-plan-20260910.md`，不能用单独 Pyright/pytest 代替 |
| 既有登记 | 582 required / 33 required groups；85 supplemental / 15 supplemental groups；missing/duplicates/unknown 均为空，无跨类重叠 | 这是既有登记的结构核验，不保证新增验收文件已经登记，也不保证 tests 都执行过 |
| Git tracked | 核查时 required 308、supplemental 85 未跟踪 | 待 Main 随所属代码提交；不是永久不可解决。旧 staged 冻结测试已在 index，不更动 |
| 新增验收登记 | 实时曾发现 `test_final_planning_browser.py` 待登记；Main 通知还将增加 `final_foundation*` | 属于过程中待冻结事项，当前不改 registry，不把临时文件状态写成最终缺陷 |
| 产品 15 warnings | 历史报告均为两处懒导出 `reportUnsupportedDunderAll`，目标类/函数当前均存在 | 不按 15 个产品 bug 计数；保留诊断，非通过放宽配置来消音 |
| 默认 2011 errors | 上轮无 `-p`、含 tests 的额外 Pyright 结果，记录称 errors 全在 tests | 不属于 `pyrightconfig.gate.json` 产品范围，不升级为本次完整门禁阻断；该额外检查仍是失败，不能改写成通过 |
| 依赖债务 | 上轮生产 1 dir SCC / 8 file SCC / 5 unresolved；含 tests 为 43 unresolved | 按下文同根因有限分诊，不无限清债，不改冻结 baseline |

已执行静态检查的完整命令、结果、62 个当前源哈希、19 步原始 plan、登记哈希、43 个历史动态位置及对应当前源哈希在 `H-readonly-evidence-20260910.json`。哈希采样发生在工具检查之后，不包装成执行前后锁定源码的证明。历史日志未重新运行，当前源哈希也不会追溯绑定旧运行。

## 实际命令与环境

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache \
  PYRIGHT_PYTHON_CACHE_DIR=/tmp/aps-task-h-01a08b02/pyright-cache \
  XDG_CACHE_HOME=/tmp/aps-task-h-01a08b02/cache \
  .venv/bin/python -B -m pyright -p pyrightconfig.tools.json --outputjson

env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache \
  .venv/bin/python -B -c 'import json,subprocess,sys; paths=json.load(open("pyrightconfig.tools.json"))["include"]; print("tool_scope_paths="+str(len(paths)),flush=True); result=subprocess.run([sys.executable,"-m","ruff","check","--no-cache"]+paths); sys.exit(result.returncode)'
```

- Python 实测 3.8.10；工具版本 Pyright 1.1.406，Ruff 包元数据 0.15.11。没有调用坏 shebang。
- Node 实际可执行文件 `/Users/lurenxing/.local/node-v24.15.0-darwin-arm64/bin/node`，版本 v24.15.0；设 `NODE_PATH=/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules` 后 `require.resolve("playwright")` 成功。本轮仅解析模块，没有启动浏览器。
- Chromium 109 既有硬编码路径存在；尚未在本轮启动/测版本，不能据此算浏览器测试通过。
- `piece_main_build.cjs:11`、`scripts/workbench/compile.cjs:25` 读取仓库固定 `frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js`，文件 3,137,752 bytes，SHA-256 `2623a9e22809915ce789b4461154e277ddce520d5a4320c14d44332a5d0dcea0`。环境初查 `esbuild` 和 `@babel/core` 均 `MODULE_NOT_FOUND`/exit 1，但它们不在实际构建合同内，不作为阻断，不安装依赖来满足错误前提。
- 两次目录/文件定位尝试命中不存在的旧名称后已按现有路径重读，没有把缺失的辅助文件当产品失败；没有因定位失败停止现场核查。

## 15 条产品 Warning

历史源：`output/workbench-migration/verification/round1-20260910/pyright-product-frozen.json`，1161 files / 0 errors / 15 warnings。以下为历史报告逐条映射与当前源码核对，不称本轮重新运行的产品 Pyright。

| # | warning 位置 | 实际目标定义 |
| --- | --- | --- |
| 1 | `core/services/scheduler/__init__.py:44` BatchService | `core/services/scheduler/batch_service.py:17` |
| 2 | 同文件 :45 CalendarService | `core/services/scheduler/calendar_service.py:15` |
| 3 | 同文件 :46 ConfigService | `core/services/scheduler/config/config_service.py:80` |
| 4 | 同文件 :47 GanttAdjustmentDraftService | `core/services/scheduler/gantt_adjustment_draft_service.py:74` |
| 5 | 同文件 :48 GanttAdjustmentScenarioService | `core/services/scheduler/gantt_adjustment_scenario_service.py:44` |
| 6 | 同文件 :49 GanttAdjustmentPublishService | `core/services/scheduler/gantt_adjustment_publish_service.py:58` |
| 7 | 同文件 :50 GanttAdjustmentValidationService | `core/services/scheduler/gantt_adjustment_validation_service.py:50` |
| 8 | 同文件 :51 GanttService | `core/services/scheduler/gantt_service.py:44` |
| 9 | 同文件 :52 OperationExecutionFeedbackService | `core/services/scheduler/operation_execution_feedback_service.py:63` |
| 10 | 同文件 :53 ResourceDispatchActualRecordService | `core/services/scheduler/resource_dispatch_actual_record_service.py:53` |
| 11 | 同文件 :54 ResourceDispatchExecutionService | `core/services/scheduler/resource_dispatch_execution_service.py:44` |
| 12 | 同文件 :55 ResourceDispatchService | `core/services/scheduler/resource_dispatch_service.py:41` |
| 13 | 同文件 :56 ScheduleService | `core/services/scheduler/schedule_service.py:46` |
| 14 | `core/services/scheduler/schedule_orchestrator.py:6` ScheduleOrchestrationOutcome | `core/services/scheduler/run/schedule_orchestrator.py:35` |
| 15 | 同文件 :6 orchestrate_schedule_run | `core/services/scheduler/run/schedule_orchestrator.py:281` |

- 同根因：前 13 条由 `_EXPORTS` + 模块 `__getattr__` 提供对象（`scheduler/__init__.py:18,35`），后 2 条由旧模块兼容转口 `__getattr__` 返回目标（`schedule_orchestrator.py:8,11`）。`__all__` 存在静态名字但没有显式静态导入声明。不是丢了 15 个实现。
- 实际风险：静态工具无法验证公开导出类型；如果以后映射名字/目标漂移，失败延后到访问导出时才暴露。当前只读核对没有找到目标缺失证据，没有本轮运行时失败证据；这不等于所有导入次序已验证。
- 本轮保留理由：门禁 Pyright 命令未使用 `--warnings`，不要求 warnings 归零。懒导入是既有兼容与初始化行为，不能为了消警改成 eager 导入或改 ignore。现有 `test_sp05_path_topology_contract.py:255` 明确守护旧/新模块同对象，`test_schedule_orchestrator_contract.py:73` 使用旧导出路径。
- 有限具体修法（产品改动归 Main）：仿照已存在的 `core/services/scheduler/config/__init__.py:6`，在 `TYPE_CHECKING` 内声明这些真实目标，保留运行时懒导出和旧对象身份；新增/复用精确导出、未知名抛 AttributeError、fresh-process import-order 合同，再跑产品 Pyright 和导入扫描。当前没有证据要求在首跑前扩大为调度器重构。

## 历史依赖分诊

### 计数口径

`1dir/8file/43dynamic` 是上轮扫描的混合简写，不是两个冻结 baseline 文件本身的当前条数：

| 来源 | directory SCC | file SCC | dynamic 未解析 |
| --- | --- | --- | --- |
| 上轮 `imports-product-after.json` | 1 | 8 | 5 |
| 上轮 `imports-with-tests-verified.json` | 1 | 8 | 43（生产 5 + tests 38） |
| 冻结 `import_cycles_production_baseline.json` | 3 | 9 | 6 |
| 冻结 `import_cycles_with_tests_baseline.json` | 4 | 9 | 44 |

冻结基线允许消圈/删边/SCC 缩小；不允许新增成员、圈内边或带行号的动态位置。见 `tools/import_cycle_baseline.py:227,235,246`。两份 baseline 本轮仅读取、取哈希，不刷新。正式新 HEAD 的“无新增”仍须重新扫描，旧日志不能冒充新运行。

### 1 个目录环

上轮成员为根目录 `.`、`web/bootstrap`、`web/routes`。边包含 `app_new_ui.py:5 -> web.bootstrap.entrypoint`、`web/bootstrap/factory.py:16 -> config`、factory 注册各 blueprint、`web/routes/system_runtime_logs.py:18 -> config`。这是目录聚合关系，不自动等同具体文件加载闭环。

- 风险：根配置、启动装配与路由的职责耦合，改装配顺序可能影响启动/路由加载。
- 保留理由：没有单凭目录环证明当前启动失败；Main 正在处理入口/旧 UI 退役，H 不额外迁移模块。
- 若此次入口退役实际复现失败：将共享配置契约下移独立叶模块，factory 注入路由所需配置，不让 route 反向拉起 app；保留原路由注册/响应合同与启动锁前置断言。

### 8 个文件环

上轮 `explicit_hard_file_cycles=[]`；8 个 hard SCC 来自包含 Python 父包初始化边的完整图，不能当成 8 个确定 ImportError。扫描器刻意同时保留两种图，见 `tools/scan_import_cycles.py:275-327`。这也不意味着完整图可删除或基线可放宽。

| SCC 范围 | 真实风险与本轮保留理由 | 影响交付时的定向处理 |
| --- | --- | --- |
| `core.models` 及 26 个子模块 | `core/models/__init__.py:11` 起集中再导出；包初始化顺序敏感，当前无显式 hard SCC。不得为消图破坏模型公开导出 | 仅把造成回读的共享类型放叶模块，或做保持对象身份的懒导出；加 fresh-process 模型导入次序测试 |
| `core.services.report`、exporters、计算/执行复盘等 | `report/__init__.py:12` 导出 ReportEngine，`exporters/__init__.py:3` 导出 xlsx；报告入口容易连带加载。当前不是导出失败证明 | 若报表/台账启动失败，拆只读 DTO/计算叶依赖，保留 Excel/CSV 数据与错误合同 |
| `core.algorithms`、greedy、dispatch/sgs、run_context | 顶层 `core/algorithms/__init__.py:13` 导出 GreedyScheduler，greedy 再导出 scheduler；初始化闭合来自父包图。无证据要求为图改排产算法 | 仅将公共 contract 常量/类型归独立叶模块，不改策略评分、5000 阈值或算法基线 |
| `core.infrastructure.migrations`、v4/v16/v18/v19 | `migrations/__init__.py:7` 起版本登记与版本间真实复用。迁移链最忌盲目删旧依赖 | 复现时提取纯升级 helper，保持版本登记、原 DDL、备份/事务/逐项数据保留测试；不改迁移顺序 |
| `core.services.personnel`、operator_machine helper/service | `personnel/__init__.py:11` 公开导出与内部 helper 的父包边；属于既有人机能力边界 | 发生实际导入/归一化故障才将纯 normalizer 下移，保留异常传播和现有 test-debt 台账，不吞错 |
| `core.services.system`、maintenance、system_maintenance_service | `system/__init__.py:14` 公开导出维护服务，服务加载 maintenance 子包；无本轮启动失败证据 | 若维护/恢复入口复现，拆生命周期协议到叶模块；不把日志、恢复不确定态改成成功 |
| `core.plugins`、manager | `core/plugins/__init__.py:10` 再导出 manager，父包回边；不是插件代码本身执行通过证明 | 保留动态插件入口，必要时减少包级 eager 导出；逐项验证配置注入与错误状态 |
| `desktop.gantt`、pyqt_poc | `desktop/gantt/__init__.py:10` 保留旧可选 PoC 出口；不是当前离线 Web 工作台或 Win7 发布通过条件 | 不为旧 PoC 把 PyQt 加进运行包；仅在当前产品仍真实调用且失败时交 Main 处理 |

### 43 个动态位置

机器证据逐条保存原 file/line/context/expression，不删分母。按同根因分为：

| 同根因 | 数量 | 风险、保留理由与本次处理 |
| --- | --- | --- |
| 产品插件文件装载 | 1 | `core/plugins/manager.py:176` 从实际插件文件构建 spec；本来就是动态装载，未知静态目标应保留。真正风险是插件缺失/载入失败；看插件状态/既有异常合同，不把任意文件静态猜成固定模块 |
| 产品按名字懒导出 | 3 | scheduler/config/repositories 的 `__getattr__`，当前目标来自固定映射但扫描器不推断分支/名字到值。保留懒加载；发生导出失败按前节定向修，不加“动态都安全”的豁免 |
| 产品路由清单装配 | 1 | `scheduler_route_registrar.py:31` 拼接相对模块名；仅全部导入完成才设 `_REGISTERED=True`。退役时需保留正确的注册集合与可见入口验收，不改扫描器猜路由来消债 |
| 历史 stress/benchmark/Gantt 脚本装载 | 17 | stress 1、optimizer harness 1、Gantt 15；大多用 spec 从复用脚本取帮助函数。静态无法解析不代表没有运行覆盖，亦不能从旧 passed 推断新 UI 通过；必要的合同更新随真实功能归属，不删除旧断言 |
| tests 的启动/导入/路由行为探针 | 8 | app_runtime 4、schedule 3、web health 1；按参数选模块用于环境刷新/异常可见性。保留真正动态测试，发生陈旧 patch 目标才按现有运行合同修夹具 |
| tools/meta 动态加载与旧新路径身份探针 | 13 | gate_meta 五个单点 + SP05 八个 old_name/new_name 位置；是工具脚本/兼容对象测试，不是 13 个产品动态入口。保留逐项检查；只有能静态证明的真实常量或源路径才允许扫描器后续解析，不刷新 baseline |
| 总计 | 43 | 产品 5，tests 38；所有项均保留在机器清单 |

## 冻结后的 Registry 工作

- Main 的 foundation 补漏涉及 `main.jsx`、`theme.js`、导航模块（最新通知为 `navigation.js`，此前方案曾提 `WorkbenchNavigation.js`）、`build-order.json` 与 `tests/workbench/final_foundation*`。以 Main 冻结清单确认最终实际路径/哈希/命令/适用环境，再登记；全站测试必须是真当前 build，不复用旧 compiled payload。
- D 的 `test_final_planning_browser.py:67` 是四个尺寸/主题组合的真实编译、输入/点击与新进程保留，截图仍要 Main 单独 V 审视。冻结后合适 owner 是现有 supplemental `workbench_browser`，不是 backend required，也不是假定 opt-in（当前文件没有 opt-in skip）。
- Foundation 若含纯合同与真实浏览器两个测试文件，分别按其真实行为分为 required/backend 或 supplemental/browser；只辅助 build/server/oracle 的文件进 dependency/input scopes，不能拿 helper 冒充必跑 test target。
- 浏览器 `_BROWSER_SCOPES` 当前已覆盖 `frontend/workbench/**/*`、`scripts/workbench/**/*`、`tests/workbench/*.py/*.cjs/*.mjs/*.jsx`，见 `tools/test_registry_groups_workbench.py:701`。仍需逐一锁定 target owner、实际 helper/fixture 依赖、必要环境变量与缓存失效，不能只加文件名就宣称登记完整。
- 后续 meta 验证至少覆盖现有 registry/round1/cache-environment 合同及新 target 的一主归属、无重复、无未知、存在真实 test 定义、源/构建/fixture 变动命中 owner。等冻结后再做小范围 registry/meta 修改与对应测试，不用扫描过程中浮动的总数去改断言。

## 未完成与保留

- full gate 要等 Main 的最终 HEAD、隔离工作区和执行窗口。未跑 full pytest、架构、全默认 Ruff、产品 Pyright、全量新导入扫描，也未做本轮 B/K/V/P 或性能测量。
- 当前门禁 full-test-debt 默认会发现 supplemental，但专题 opt-in 仍可能 skip；required verifier 在 macOS 不接受任意 skipped/xfail（仅已有白名单允许指定 node 在 nt 跳过），见 `tools/verify_required_regressions_from_full_test_debt.py:215`。不能称 gate 通过就全动作验收通过。
- 唯一原 staged 冻结测试与 staged patch 在本轮两次只读采样均保留原哈希；H 从未 Git 写。Main 后续按授权提交的变动不属于 H 更动，不能再要求 index 永远停在旧值。
- 原大量 dirty 未回退、清理、覆盖；两个源码备份未操作，共享调用图未写入，未清缓存或停止旧预览。手工产物均用 `apply_patch`。
- 不包含 Win7 打包、真机和最终发布，不改 planning206、旧原型 passed 或历史验收记录。

## 提交窗口回读

- 当前已观察到 Main 提交 `c00972784ccc129957f650836dd2a423792f7049`，原 index 为空。H 将机器清单的 62 个工具源逐一重新取 SHA-256，与之前采样相比 changed 列表为空；无需把提交钩子的短暂 stash 误判为产品问题。
- 只读 `git show c0097278:tests/gate_meta/test_frozen_bundle_contract.py` 后计算 SHA-256，与原工作区文件和原冻结值完全相同，均为 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。原暂存文件现已随 Main 的授权提交入库；H 无 Git 写。
- Main 报告的 `/tmp/aps-workbench-r2-gate-PFwbOz/checkout` 冻结测试 6 passed / 0.67 秒，未由 H 重跑，不升级为 full gate 或最终 HEAD 证明。遵守暂不在早期 HEAD 全跑的指令。
