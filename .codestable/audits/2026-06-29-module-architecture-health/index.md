---
doc_type: audit
slug: module-architecture-health
scope: scheduler 之外的全仓模块架构合理性体检——algorithms / 基础层(models+infrastructure+shared)/ 业务服务族 / common+plugins+data / web 三层;聚焦职责划分、依赖方向、结构债
summary: 历史模块体检 + 2026-07-13 依赖事实校正；A2/A3 已解除，基础层和算法主链改为单向依赖，A4-A6 与 tests 圈仍待治理
status: open
created: 2026-06-29
last_reviewed: 2026-07-13
verified_by: 2026-06-29 五路历史体检 + 2026-07-10 首次工具复扫 + 2026-07-11 确定性证据重建 + 2026-07-12 A1/A2 治理 + 2026-07-13 A3 双 scope/调用图核对
tags: [architecture, module-health, dependency-direction, responsibility, audit]
---

# 模块架构体检（scheduler 之外，含 2026-07-13 校正）

## 2026-07-13 当前依赖事实校正

- 下方主体保留 2026-06-29 的历史人工判断；与本节冲突时，以本节和双 v2 基线为准。
- A2 已通过两个最小归位点解除：零依赖错误合同在 `core.errors`，migration outcome/SQLite helper 在 `core.infrastructure.migration_common`。当前基础方向为 `migrations → infrastructure → models → shared → core.errors`。
- A3 已通过两个 sibling leaves 解除：纯日期/排序/派工/类型合同在 `core.algorithm_contracts`，共享统计/自动派工合同/时隙/run-state/dispatch context 在 `core.algorithm_runtime`；当前算法方向为 `algorithms → greedy → dispatch → runtime/contracts`，runtime 只单向依赖 contracts。旧路径保持同对象兼容，根 `GreedyScheduler` 与 dispatch/algo-stats 真实 patch 模块状态不变。
- A4 当前生产目录 SCC 仍为 `. ⇄ web/bootstrap ⇄ web/routes ⇄ web/routes/domains/scheduler`；A5 plugins/common 与 A6 report/exporters 也仍在。纯显式 hard 文件 SCC 仍为 0，不能把目录圈直接叫文件死循环。
- 父包 `__init__.py` 初始化链仍形成 9 个 hard 文件加载 SCC；migration 圈保持 5/11，A3 相关 algorithms 圈已从 21/94 严格缩为 8/24。父包感知/纯显式 runtime 文件 SCC 为 13/4。
- 正式质量门禁继续包含生产与含测试两条独立 v2 基线。A3 终态为 production 779 模块 / 3 SCC、with-tests 1475 模块 / 4 SCC，unresolved 仍为 6/44；A4/A5/A6/tests 记录不变。
- 当前调用图为 7337 callable / 25798 edges / 10171 confident / 15627 ambiguous / typed 0；7329 个旧 callable 全映射，新增仅 8 个 context adapter callable，旧边差异全部落入批准白名单。
- A4-A6 与 tests 辅助代码圈仍待治理。A2 clean closure 继续绑定 `d6d41e1a`；A3 当前已有 19/19 dirty-worktree 门禁在内的未提交工作区机械证据（manifest=`passed_but_unbound`），commit/clean-HEAD proof 尚未授权。

> 性质:**发现清单**,不代表已治理。治理(改代码)归 roadmap / refactor。
> 配套:循环依赖细节见 [[2026-06-28-circular-imports]];scheduler 模块见 [[service-scheduler]]。本报告补各模块"职责划分 / 依赖方向 / 结构债"的全景视角,并给出 A2–A6 环的**模块视角根因**。

## 0. 一句话结论

scheduler 之外的模块**分层底盘整体健康**——算法层是真"纯计算"、基础层是真"叶子"、data 访问层收口很干净、web viewmodel 纪律零违规、服务间无环(门禁已锁)。发现的问题集中在 **3 类**:① 底层/公共包混进了本该归业务模块的"飞地"文件;② web 的 `domains/` 目录化是半成品(空壳)+ Excel 路由未归域;③ 一批近/超门禁大文件。**循环依赖 A2–A6 的根因已逐个定位到具体的"误放工具/契约文件",治本都是低风险的下沉/上移**,且全部不阻断运行。

## 1. 方法与口径

- 5 个 OPUS 子代理并行,各审一个模块单元,结论带 `file:line`;主代理对关键数字(行数、空壳字节、直连唯一性、飞地消费方)独立核实。
- 范围:`core/algorithms` / 基础层(`core/models`+`core/infrastructure`+`core/shared`)/ 业务服务族(`report`/`process`/`personnel`/`equipment`/`material`/`system`)/ `core/services/common`+`core/plugins`+`data/repositories` / web 三层(`routes`/`viewmodels`/`bootstrap`)。
- scheduler 已单独有架构文档,本次不重复。

## 2. 健康面(先讲对的——这是主体)

| 维度 | 结论 | 证据 |
|---|---|---|
| 算法层纯计算 | ✅ `core.algorithms`、`core.algorithm_contracts`、`core.algorithm_runtime` 零 `core.services`/`data`/`web` 依赖、零 I/O；日历/配置靠**注入**，dispatch 经最小上下文合同调用 | `core/algorithms/greedy/scheduler.py` 注入构造；两个 sibling leaf AST 边界测试锁定禁止反向依赖 |
| 基础层真叶子 | ✅ models/infrastructure/shared **不反依赖任何上层**(services/web/data/algorithms) | 反向依赖核查为空 |
| data 收口 | ✅ web **业务路由 0 处**直连 data;repositories 之间零横向、对 service 零反向 | 全 web 仅 `web/bootstrap/plugins.py:13` 一处直连(装配期,见 §3.5) |
| viewmodel 纪律 | ✅ `web/viewmodels` 对 `core.services`/`flask`/`data`/`routes` 的 import **零违规** | 仅 2 处注释提及,属纪律声明非依赖 |
| 服务间无环 | ✅ 顶层包粒度依赖无环,且有门禁锁 | `tests/gate_meta/test_architecture_fitness.py:209-214` `known_cycles=空` |

## 3. 发现清单(按类)

### 3.1 飞地 / 误放——底层或公共包混进业务逻辑(最该先收的一类)

| 文件 | 现状 | 应归 / 治本 | 严重度 |
|---|---|---|---|
| `core/services/common/overdue_calculations.py:113` | 排产逾期分桶计算,消费方全是排产/报表域(`scheduler/plan_overdue_markers.py:10`、`schedule_delay_diagnosis_service.py:16`、`report/calculations.py:7` 等 4 处),与 common 内部零 import | 搬去 scheduler | 🔴 |
| `core/services/common/excel_validators.py:27` | 反依赖 `data.repositories`(common→data 倒挂)+ 只校验"批次/人员日历"两张具体表 | 拆回各业务模块 | 🟡 |
| `core/infrastructure/errors.py:8` | 零依赖纯异常契约,被 **176 处**依赖,逻辑上"比 shared 还底",却寄居 infrastructure(而 infrastructure 又借 models 做契约校验)→ 造成 **A2 环** | 下沉为独立零依赖底层模块(如 `core/errors`),仅改 import 路径无逻辑风险 | 🟡 |
| `core/algorithms/greedy/date_parsers.py` | 49 行纯 stdlib 日期工具放在 `greedy/` 子包,却被 4 个顶层文件反依赖(`dispatch_rules.py:8`/`evaluation.py:9`/`ordering.py:9`/`ortools_bottleneck.py:19`)→ 造成 **A3 环** | 上移到 `core/algorithms/` 顶层 | 🟡 |
| `core/services/report/report_number_parsing.py` | 包内纯叶子,被子包 `exporters/xlsx.py:14` 回借 → 造成 **A6 环** | 下沉为无回边叶子(或移 common) | 🟢 |

**共性**:都是"公共工具/契约放在了一个会反向依赖业务的包里",造成包级环或叶子不纯。治本统一是"**下沉/上移成无反向依赖的叶子**"。

### 3.2 循环依赖 A2–A6 的模块视角根因(呼应 [[2026-06-28-circular-imports]])

| 环 | 模块视角根因 | 性质 | 关键证据 |
|---|---|---|---|
| **A2** infra⇄migrations⇄models⇄shared | `errors.py` 寄居 infra(§3.1);另 `infra↔migrations` 硬加载期其实**单向**,反向的 `migrations→infra.logging` 已做成**函数内延迟 import** 规避成环 | 物理分包债,非逻辑错误 | `migrations/common.py:92` 延迟 import;`operation_execution_event_data_contract.py:6-7`→models |
| **A3** algorithms⇄greedy⇄dispatch | `date_parsers` 放错层(§3.1) | 真债低危,运行期不爆 | 见 §3.1 |
| **A4** web/routes⇄domains/scheduler | 顶层与排产域**互借共享辅助**:顶层借 `domains.scheduler.scheduler_plan_context_token`(脱敏 token),域借顶层 `excel_utils`/`navigation_utils` 等;借出双方都是叶子、互不相交 | **目录粒度伪环**(`hard_file_cycles:0`),不阻断 | `reports_export_support.py:11`↔`scheduler_excel_calendar.py:16` |
| **A5** plugins⇄common | 插件框架借 common 纯工具、common 后端工厂借 plugins 能力发现机制,互供能力 | by-design 浅**活**边(web 13+ 处经 `get_excel_backend()` 在用) | `plugins/manager.py:11`↔`common/excel_backend_factory.py:6` |
| **A6** report⇄exporters | `report_number_parsing` 被回借(§3.1) | 局部、可正常加载 | `exporters/xlsx.py:14` |

**历史判断（2026-07-10 校正）**:A2–A6 的 file:line 已定位，但 A2 涉及错误合同和旧迁移语义，不能笼统称全部低风险。当前双 scope 门禁已正式接入；它阻断新 SCC、同成员新增边和新增未解析动态加载，不再只是成员级“可挂”检查。

### 3.3 web `domains/` 目录化半成品(web 最大结构债)

| 现象 | 证据 | 严重度 |
|---|---|---|
| `domains/{system,equipment,personnel,process}/__init__.py` **全 0 字节空壳**,真实路由仍在顶层;只有 `domains/scheduler/`(36 文件、132B `__init__`)走通 | 主代理实测 4 个文件均 0 字节 | 🔴 |
| 13 个 `*excel*.py` = **4476 行,占 routes 顶层 45%**,逻辑已带域前缀却散在顶层未归域 | `equipment_excel_machines.py:468`、`process_excel_part_operation_hours.py:463` 等 | 🔴 |

**影响**:两套子域组织法(顶层前缀聚合 vs domains 目录)并存,空壳目录误导后来者以为 domains 是统一规范。

### 3.4 近 / 超门禁大文件(门禁线 500 行;全仓散布)

- **已超 500**(应在门禁豁免台账中、治理时核销):`core/services/report/report_engine.py` **578**(子代理称已在治理台账)、`core/infrastructure/backup.py` **577**(维护窗口锁 + 备份管理两职责混居,`:44-320` 锁 vs `:322-577` BackupManager;是否已豁免**待核实**)。
- **近门禁(477–498,趁实质改动按职责薄抽)**:`scheduler_analysis_candidate_helpers.py:498`、`web/bootstrap/factory.py:497`、`common/excel_templates.py:496`、`models/schedule_config_runtime_coercion.py:496`、`scheduler_resource_dispatch.py:490`、`operator_machine_service.py:486`、`execution_review.py:485`、`data/repositories/schedule_plan_query_repo.py:485`、`launcher_stop.py:480`、`unit_excel/template_builder.py:478`、`part_service.py:477`、`algorithms/greedy/scheduler.py:472`、`launcher_contracts.py:465`、`algorithms/greedy/schedule_params.py:465` 等。

**共性**:多为职责单一但信息密集,非失控;近门禁的留待下次实质改动时顺势按职责微拆。

### 3.5 个别越界(轻)

| 现象 | 证据 | 严重度 |
|---|---|---|
| web→data 唯一越层直连:读插件 enabled 开关 | `web/bootstrap/plugins.py:13`(用点 `:159/:177`);**有现成等价门面** `SystemConfigService`,同文件夹 `factory.py:108` 已走门面——plugins.py 是不一致异类,可零摩擦收口 | 🟡 |
| dashboard 上帝 route:摘要可信度/降级判定塞进 route | `web/routes/dashboard.py:72-285` | 🟡 |
| route 穿透 service 摸仓储(孤例) | `web/routes/domains/scheduler/scheduler_batches.py:346` `batch_svc.batch_repo.get(...)` | 🟢 |
| common 命名误导:`excel_audit.py`(实为导入审计日志)、`build_outcome`/`degradation` 真身在 `core.shared` 更宜下沉 | `common/excel_audit.py:39` 等 | 🟢 |

> 注:`web/bootstrap/plugins.py:13` 两个子代理判断略有分歧——"公共+插件+仓储"组视其为"可接受的启动期装配",web 组视其为"应收口的越层"。主代理裁决:它确是全 web 唯一的 data 直连,且有等价门面、同目录已有走门面的先例,故按"🟡 可顺手收口的分层不一致"定性。

## 4. 严重度与治理优先级(保守口径)

- 🔴 **结构性**:web `domains/` 半成品 + Excel 路由未归域(web 最大结构债,§3.3);`overdue_calculations.py` 排产逻辑飞地(§3.1)。
- 🟡 **中**:循环依赖根因下沉(A2 `errors` / A3 `date_parsers`,各单点低风险但 errors 影响面 176 处);超门禁 `backup.py`(§3.4);web→data 收口(§3.5)。
- 🟢 **轻**:A5/A6 浅环;近门禁文件;个别越界。

## 5. 治理建议(待办,按节奏;本报告不改代码)

- **可合并成几个小重构**:(a)"叶子下沉"批次——`errors` 下沉断 A2、`date_parsers` 上移断 A3、`report_number_parsing` 下沉断 A6、`overdue_calculations` 归 scheduler,这些都是低风险移动 + 改 import 路径,适合一并走 cs-refactor;(b)web `domains/` 收口——把 13 个 Excel 路由按域归进 `domains/{...}`,填实空壳;(c)`web/bootstrap/plugins.py` 改走 `SystemConfigService` 门面。
- **门禁（已落地）**：生产与含测试两条 `scan_import_cycles --fail-on-new-cycle --quiet-when-clean` 已进入正式共享计划；基线分别为 `.codestable/checkup/import_cycles_production_baseline.json` 与 `import_cycles_with_tests_baseline.json`。
- 与并行进行的其它改动(optimizer 等)错峰,避免同区域冲突。

## 6. 复核工具

- 环:`python3 -m tools.scan_import_cycles`(`--json` 机器可读 / `--fail-on-new-cycle` 门禁)。
- 影响面:`python3 -m tools.symbol_locator whereis|callers|callees <符号>`。
- 行数/空壳:`wc -l` / `wc -c`。
