---
doc_type: roadmap
slug: aps-architecture-consolidation
status: active
created: 2026-11-09
last_reviewed: 2026-11-12
summary: 保留离线模块化单体，穿透收敛排产/试调/采用、工作台事实作用域、前端显式模块与受控DTO边界、宿主单入口及门禁单一描述，零存储格式变更一次性切换交付
tags: [architecture, maintainability, scheduler, workbench, offline, one-shot-migration]
related_requirements: [workbench-production-workflows, candidate-comparison-business-view]
related_architecture: [ARCHITECTURE, service-scheduler, workbench-shell, ui-gantt]
---

# APS 全局架构收敛设计与一次性迁移方案

## 1. 设计结论与阅读顺序

推荐目标是**职责明确的离线模块化单体**：保留 Python 3.8、Flask、SQLite、React 和本地静态交付；业务用例拥有事务和裁决，事实层按明确作用域单向提供完整关系闭包事实，排产/试调/采用核心消费统一的准备结果与安排验证结果，前端通过显式 ESM 模块依赖组织并剥离对本机受控 DTO 的重复自检，宿主收口为唯一生产入口，治理工具只维护一份检查定义。

本次定稿融合了全仓源码穿透推导与双模型多轮核查：不仅解决排产输入九元位置元组、前端业务 `window.*` 全局变量和门禁字符串分类，还从源头一并根除以下结构性病灶：
- **排产与试调域**：预检与受理重复准备及 `preflight_result.py:76` 原地 `pop` 删字段隐式耦合、试调采用同事务双跑验证器与普通/分件复制粘贴安排验证、日历服务跨层转发与带连接快照子类。
- **工作台数据与宿主域**：业务域 `self._snapshot` 临时属性偷渡（`try/finally` 动态塞属性）与 `_RawProcessFacts(dict)` 字典伪装仓储偷跑 SQL、命令回执路由分散及校准采用 404 特判、宿主 `app_new_ui.py` / `ui_mode` 双入口分裂与 `app.py:52` 模块导入期重副作用。
- **前端工作台域**：25 个 `Contract/API` 模块对本机受控 DTO 的数千行重复算术/字段表/排序重验（及 `PlanContract.js:209` 在校验器内混做数据展开）、生产代码反向依赖 `prototype/` 死组件库及 `ReportEvidence.jsx:45` 挂载后 `useLayoutEffect` 扫 DOM 补属性。
- **质量门禁工具域**：`quality_gate_shared.py:1312` 0 生产调用死代码孤岛引发的反向导入、单步门禁双跑两次 `pyright` 子进程，以及硬编码历史 commit `d4589d77` 的临时扫描器。

**用户已明确：无需照顾过去的兼容问题，迁移一次性全部完成。** 所有生产调用者、测试、构建、规则与文档在一个交付单元内完成切换；不交付旧新双轨、兼容重导出空壳、旧协议适配或半迁移状态。经源码与 Schema（`CURRENT_SCHEMA_VERSION=45`，`migration_state.py:55`）穿透核实，**本次架构重构对持久存储格式保持 100% 零变更**，无需离线数据库格式转换器。文中的工作包是依赖顺序与并行开发分工，不是分批上线。

本文状态为 `active`：总体路线图与四份专题设计已定稿冻结，作为实施的唯一架构依据；当前 `A0`（`ownership-contracts`）、`A1`（`scheduler-use-case`）、`A2`（`data-command-boundaries`）、`A3`（`frontend-modules`）与 `A4`（`tooling-definition`）已完成（`completed`），最终合流工作包 `A5`（`integrated-cutover`）保持 `in-progress`（macOS Python 3.8.10 下 `scripts/run_daily_quality_gate.py` 通过 `1095 passed, 20 skipped` 且宿主工具测试 `tools/host_tests` 全部通过；`scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache` 第 1～14 步全部通过——全集收集 `1404` 项：`1368 passed`、`36 skipped`、`0 failed`、`0 active xfail`，退役历史债务 `5` 项，其中 `36` 项平台/环境跳过含必跑回归中的 `20` 个 Windows/PowerShell 节点即 `test_launcher_startup.py` `15` 个与 `test_runtime_server_binding.py` `5` 个，另有非必跑 `test_sample_switch.py` `15` 个 `pwsh` 节点与 `test_portable_delivery.py` `1` 个 Windows 7-Zip 节点，故第 15 步 `required_regressions` 在 macOS 上按设计因该 `20` 个必跑跳过节点返回 `1`；隔离临时库现场浏览器验收通过——通过 `aps-start-and-rerun-route` `rerun --db-path /private/tmp/.../demo.db` 在 `127.0.0.1:58766` 完成预检、排产与正式采用 `v1` 19 道任务，实测甘特图、正式 `Table` 原生 `<caption>`/`<th scope="col">`/列宽拖拽 `+30.12px`、`/workbench/trial` 及 100% 本地静态资源，`0` 控制台/页面/网络错误；剩余待办仅限 Win7 x64 目标机实跑 Windows 专属测试节点与 Chrome 109 验收，以及正式 git commit 后执行 `--require-clean-worktree --long-gate-cache --no-resume` 生成最终 clean-worktree proof）。

| 阅读对象 | 文档 | 内容 |
|---|---|---|
| 项目负责人、整体实施者 | 本文 | 架构裁决、全域职责、依赖、工作包、切换与验收 |
| 排产核心实施者 | [调度专题](scheduler-design.md) | `PreparedBusinessInput`、统一安排约束验证、单一无连接 `CalendarEngine`、求解与消费者迁移 |
| 业务和运行时实施者 | [数据与运行时专题](data-and-runtime-design.md) | 轻量指纹与按需事实闭包、7 条命令回执统一、宿主单入口与零存储格式变更切换 |
| 前端实施者 | [前端专题](frontend-design.md) | 显式 ESM 模块、`esbuild` + `vm.Context` 测试沙箱、拔除 `prototype/`、剥离受控 DTO 重复重验与展开归位 |
| 工具维护者 | [治理工具专题](tooling-design.md) | `GateCheckSpec` 单一定义、删 0 调用孤岛与重复 `pyright`、退役临时扫描器与规则同步 |
| 调度实施进度 | [工作包清单](aps-architecture-consolidation-items.yaml) | `A0`、`A1`、`A2`、`A3`、`A4` 已完成（`completed`），`A5` 保持 `in-progress`（macOS Python 3.8.10 下 `scripts/run_daily_quality_gate.py` `1095 passed, 20 skipped` 与 `tools/host_tests` 全过；`scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache` 第 1～14 步全过，全集 `1404` 项为 `1368 passed`、`36 skipped`、`0 failed`、`0 active xfail`、退役历史债务 `5` 项，第 15 步 `required_regressions` 因必跑回归中 `20` 个 Windows/PowerShell 跳过节点——`test_launcher_startup.py` `15` 个与 `test_runtime_server_binding.py` `5` 个、另含非必跑 `test_sample_switch.py` `15` 个 `pwsh` 与 `test_portable_delivery.py` `1` 个 Windows 7-Zip 节点共 `36` 项跳过——在 macOS 按设计返回 `1`；`aps-start-and-rerun-route` 隔离临时库 `127.0.0.1:58766` 预检/排产/正式采用 `v1` 19 道任务与现场浏览器验收 `0` 错误通过；剩余待办仅限 Win7 x64 目标机实跑 Windows 专属测试节点与 Chrome 109 验收，及正式 git commit 后执行 `--require-clean-worktree --long-gate-cache --no-resume` 生成最终 clean-worktree proof），含修正后依赖顺序与退出条件 |

总文决定范围、依赖和切换规则；专题拥有该领域的具体接口与逐文件迁移表。实施中调整专题细节时，必须同步其全部生产与测试消费者，严禁另建同名第二版本或兼容垫片绕开。

## 2. 设计基点与证据

### 2.1 当前基点

- 核对日期：2026-11-09；Git HEAD：`7ff4fc47f`，当前工作树含 500+ 项既有改动，**本设计依据当前工作树源码核实，实施前必须先对当前工作树建立可恢复 Git 快照**。
- 已完成全仓相关源码、Schema 定义、测试夹具与治理脚本的穿透核对；本轮定稿只修改路线图文档，未运行排产或改动代码。
- 既有测试用于锁定验收入口与迁移范围；产品函数修改前按项目约定使用 `python3 -m tools.symbol_locator` 核查全部引用。
- 规划文档位于 `.codestable/roadmap/aps-architecture-consolidation/`；`.git/info/exclude` 已收窄放行受控治理路径（含 `.codestable/roadmap/aps-architecture-consolidation/`、`.codestable/architecture/`、`.codestable/checkup/`、`.limcode/{rules,skills}/`），仅忽略运行期草稿与大体积历史证据。

### 2.2 支撑设计的当前事实

| 当前事实 | 维护影响 | 设计动作 | 当前源码证据 |
|---|---|---|---|
| worker 领取、隔离计算、保存复核分别有真实责任 | 缩成一个大事务会扩大锁持有范围并混淆状态 | 保留三段生命周期边界 | [worker.py:65](../../../core/services/workbench/run/worker.py#L65)、[worker.py:111](../../../core/services/workbench/run/worker.py#L111) |
| 预检与受理各自准备输入，且靠九元位置元组与原地 `pop` 删字段交接 | 预检与受理重复计算，采用携带求解空占位，内部评估字段靠原地篡改剥离 | 收口为 `PreparedBusinessInput`，分离预检公开投影与内部评估行，受理仅增量补齐未选工序投影 | [input.py:53](../../../core/services/workbench/run/input.py#L53)、[input_runtime.py:197](../../../core/services/workbench/run/input_runtime.py#L197)、[preflight_result.py:76](../../../core/services/workbench/run/preflight_result.py#L76) |
| 候选发布、普通/分件采用、试调保存/采用分散重复安排验证，试调采用同事务跑两遍验证器 | 约束口径分散在多处，同事务重复校验，且留有 `schedule_orchestrator.py` 等薄包装壳 | 收口为统一的安排约束验证函数与结果结构，退役重复守卫与两处 8 行采用持久化转发壳 | [compute.py:73](../../../core/services/workbench/run/compute.py#L73)、[schedule_orchestrator.py:21](../../../core/services/scheduler/run/schedule_orchestrator.py#L21) |
| 日历同时存在 `CalendarEngine`、`CalendarService` 转发壳与带连接快照子类 | 空表 `()` 与未提供 `None` 语义混淆，跨夜分段散落，快照额外挂 `connection_snapshot_metadata` | 收口为单一无连接 `CalendarEngine(CalendarInputs)`，按日惰性解析并注册 checkpoint 证书 | [production_capture.py:88](../../../core/services/workbench/facts/production_capture.py#L88)、[candidate_facts.py:121](../../../core/services/workbench/facts/candidate_facts.py#L121) |
| 工作台业务域用 `self._snapshot` 偷渡状态、`_RawProcessFacts(dict)` 偷跑 SQL，`batch` 无消费预取全库快照 | 实例状态跨调用脆弱，字典夹带仓储引用，列表/单行读取白跑重型组装 | 先验轻量修订指纹 → 按用途取完整关系闭包 → 显式事实作用域传参，删临时属性与字典伪仓储 | [架构规则:29](../../../.limcode/rules/architecture-invariants.mdc#L29)、[实际仓储:31](../../../data/repositories/workbench_run_repo.py#L31) |
| 前端通过 `window.*` 连接、反向依赖 `prototype/`，且 25 个 `Contract/API` 对受控 DTO 重复重验数千行 | 人工维护脚本顺序，校验器混做数据展开并阻塞主线程，`Table` 缺属性靠 `useLayoutEffect` 扫 DOM 补丁 | 全量 ESM + `esbuild`（含 `vm.Context` 测试沙箱），拔除 `prototype/`，剥离受控 DTO 重复自检并将展开归位 Model | [RunDecisionComparison.jsx:3](../../../frontend/workbench/app/RunDecisionComparison.jsx#L3)、[build.py:63](../../../scripts/workbench/build.py#L63)、[compile.cjs:33](../../../scripts/workbench/compile.cjs#L33) |
| 门禁命令定义后靠字符串分类，存在 `quality_gate_shared.py:1312` 0 调用孤岛与单步双跑 `pyright` | 新增或修改检查需改多处分类器，公共模块反向依赖 runner，门禁耗时翻倍 | 单一 `GateCheckSpec` 直出三方消费，删 0 调用孤岛与第二次 `pyright`，退役 `d4589d77` 临时扫描器 | [命令计划:706](../../../tools/quality_gate_shared.py#L706)、[分类器:91](../../../tools/long_gate_manifest.py#L91) |

## 3. 目标、硬约束和范围

### 3.1 成功目标

1. 一条业务规则有唯一明确的拥有者；下游直接消费上游已产出的具名结论，不在同作用域内重查、重算、重验或靠原地删改字典配合。
2. 一次业务动作（预检、受理、计算、候选发布、试调保存、正式采用、命令回执查询）的输入来源、事务边界、验证结果与失败路径可从单一用例入口顺畅读完。
3. 跨阶段交接使用职责明确的不可变/受控结构，消除九元位置元组、`self._snapshot` 动态属性偷渡、`_RawProcessFacts(dict)` 伪仓储与求解空占位。
4. 前端模块依赖与门禁检查定义均由代码静态直接表达，彻底消除 `window.*` 业务导出、人工脚本加载清单、`prototype/` 生产依赖、受控 DTO 重复算术/排序自检及门禁字符串逆向分类。
5. 当前业务能力完整迁入目标结构，旧实现、薄转发壳与历史临时扫描脚本一次性彻底删除；生产系统只运行单一入口、单一协议。

### 3.2 产品约束

- Win7 x64、Python 3.8、离线单机；目标机不安装 Python、Node 或开发工具。
- Chrome 109 与本地静态资源随包交付保持；宿主构建与测试使用固定版本 `esbuild` 与 Node `vm.Context`，绝不进入离线产品包。
- SQLite 继续作为业务事实和持久回执的唯一存储；运行锁、维护排他、写事务和恢复日志保留现有真实责任。
- 工序约束、数量、分件、零工时、跨夜日历、效率、已开工保护、外协接续、候选排序和正式采用业务语义 100% 保持，架构收敛不夹带算法策略或业务口径变更。
- 日期时间保留本地工厂时间与现有精度；精确量全程用 `int` / `Decimal` / `Fraction`，不绕道 `float` 或把合法 `0` 篡改为 `epsilon`，不用 UI 展示浮点回流计算。

### 3.3 范围裁决

| 范围 | 本设计裁决 |
|---|---|
| 整体部署形态 | 单一离线模块化单体；彻底退役 `app_new_ui.py`、`start_new_ui.bat` 与 `ui_mode` 分支，保留 `app.py` 唯一生产宿主入口 |
| 数据库/后端框架/UI框架 | 保留 Python 3.8 + Flask + SQLite + React 底座；不引入 ORM、DI 容器、通用任务引擎或 Schema 代码生成框架 |
| 内部 Python 接口、目录、前端模块 | 按真实职责完整重构，一次性迁移全部生产与测试调用者，不留兼容重导出或双轨开关 |
| HTTP / 命令回执 DTO | 前后端在 `A2` 工作包内同步切换到统一的 7 条命令回执查询协议；普通 CRUD 保持 key-only |
| **持久存储与本机状态格式** | **零存储格式变更**：SQLite 表结构（`CURRENT_SCHEMA_VERSION=45`）、候选/试调归档 JSON、持久读模型、外部维护日志及浏览器 `pending` 存储编码保持 100% 不变；**无需任何离线数据库格式转换器或离线 `reconcile_frozen_intent` 对账脚本** |
| 历史业务事实与未决命令 | 原地 100% 保全现有数据库中的全部候选、正式计划、报工、审计与 `WorkbenchCommandReceipts` 原记录；切换前后未决命令直接由现有启动恢复与在线回执查询接口按原 `request_key` 处理 |
| 新业务能力 | 联动试调、新交期口径、新排产策略等另属功能路线图，不混入本次架构收敛 |

### 3.4 为什么选择这一结构

| 选择 | 收益与代价 | 裁决 |
|---|---|---|
| 仅做零散防御语句清理 | 无法消除九元元组、预检/受理重复准备、`self._snapshot` 偷渡、前端数千行 DTO 重验和门禁双跑 | 不采用；本次从源头重构共同机制 |
| 全仓推翻目录命名或拆分为多服务/多文件碎片 | 制造海量无效路径搬迁与薄转发层，违背认知一致性 | 不采用；后端保持清晰主目录，门禁保留 `quality_gate_shared.py` 公共底座（不拆 4 个碎片新文件） |
| 预设离线数据库格式转换器与离线未决意图对账器 | 经核实 Schema 与持久 JSON 格式零变化，回执查询包装仅在读取出口生成、不改写底层表记录；预设转换器纯属无消费死机制 | **彻底删除**离线数据转换器与离线对账工具设计 |
| 保留技术底座，穿透收敛核心阶段合同、事实作用域、ESM 模块化与单一门禁描述 | 直接消除重复准备、重复验证、隐式全局状态与主线程重验阻塞，且零存储迁移风险 | **采用** |

## 4. 目标架构

### 4.1 系统图

```mermaid
flowchart TB
  UI["React 工作台：页面状态、交互与 Model 展开"] --> API["前端领域 API + 共同传输与命令结算会话"]
  API --> HTTP["Flask 路由：HTTP 准入、通用命令路由与响应信封"]
  HTTP --> UC["业务用例：轻量指纹核验、事务裁决与命令回执"]
  UC --> FACT["显式事实作用域：按用途取完整关系闭包"]
  UC --> SQL["明确查询与写入仓储"]
  FACT --> SQL
  SQL --> DB[("SQLite (Schema v45 零变更)")]
  UC --> PREP["PreparedBusinessInput + 统一安排约束验证"]
  PREP --> SOLVE["求解准备与共享优化 (CalendarEngine 纯内存)"]
  SOLVE --> ALG["排程算法与动态占用"]
  ALG --> RESULT["计算结果与候选发布"]
  RESULT --> UC
  HOST["单一宿主入口 (app.py)：无副作用导入、锁与启动恢复"] --> UC
  HOST --> DB
  TOOLS["宿主构建 (esbuild) 与单一 GateCheckSpec 门禁"] -.构建与 vm.Context 沙箱验证.-> UI
  TOOLS -.门禁验证.-> UC
```

图中结果箭头表达数据返回，编译依赖方向严格从上层编排指向下层职责模块，彻底消除公共库反向 import 上层 runner 或生产前端反向引用 `prototype/`。

### 4.2 目录设计：保留可理解的骨架，修正内部责任

```text
web/
  routes/workbench/             HTTP 准入、抽取自 materials.py 的通用命令路由与响应注册
  bootstrap/                    单一宿主生命周期、运行锁、恢复与服务装配（无 import 副作用）
core/
  models/                       跨领域数据结构与外部输入准入合同；无数据库访问
  services/workbench/
    run/                        预检/受理共享 PreparedBusinessInput、共同安排约束验证、直接计算编排、候选发布与采用
    trial/ execution/ plan/     试调、执行事实、正式计划用例（共用 workbench/run 统一安排约束验证）
    process/ batch/ resource/ material/ outsourcing/
    calibration/ report/ dashboard/ history/ system/ master/
    facts/                      跨领域只读事实作用域、按用途关系闭包加载与纯投影叶子
  services/scheduler/           求解输入准备（SolverInput / SolverResources）、共享优化搜索与无连接 CalendarEngine
  algorithms/                   实际排程策略
  algorithm_contracts/          算法间共享的输入输出合同
  algorithm_runtime/            单次解码的占用、计数和运行态
  infrastructure/               SQLite 事务/连接、Schema (v45)、文件和系统边界
  shared/                       跨领域无关的值语义、时间分段纯函数与解析
data/repositories/              SQL 访问、原始记录与明确批量查询
frontend/workbench/app/
  shell/ shared/                应用外壳、唯一 vendor 边界、正式基础组件（含完整 Table）及请求/命令会话
  *.{js,jsx}                    run/trial/plan/field 等领域 ESM 页面、Model（含甘特展开）与精简 Contract/API
  styles/                       样式入口、tokens、控件与领域样式
scripts/workbench/              固定版本 esbuild 构建入口、Node vm.Context 测试打包辅助与离线资产发布
tools/                          quality_gate_shared.py（含 GateCheckSpec）、执行器、证据缓存与 repo_identity
tests/                          按业务责任和真实接口验证（彻底移除对 prototype/ 与死代码的依赖）
```

### 4.3 模块边界规则

- **HTTP 与输入准入边界**：外部 HTTP 请求和文件导入在入口合同处完成唯一一次结构与值域准入；进入内部后全部作为受控结构消费，严禁下游用 `.get()`、宽泛 `except` 或 `Reflect.ownKeys` 重复自检。
- **用例与事实作用域边界**：读取用例进门先验轻量修订指纹（`snapshot_token`），再按实际用途加载完整关系闭包事实，通过显式事实作用域对象单向传给领域方法；彻底禁止往 `self._snapshot` 临时塞属性或往字典里塞仓储引用（`_RawProcessFacts`）。
- **排产准备与安排验证边界**：`PreparedBusinessInput` 一次性完成业务事实准备并同时服务预检与受理；候选发布、普通/分件正式采用、试调保存与试调采用共用同一套安排约束验证逻辑。
- **前端边界**：生产代码 100% 走 ESM `import/export`，彻底拔除 `prototype/` 依赖与业务 `window.*`；前端 `Contract` 只验响应信封、身份/快照绑定与真正可变或需持久化的边界，本机受控 DTO 的紧凑引用展开归位到领域 `Model`。
- **宿主与工具边界**：`import app` 保持零文件/数据库/线程副作用；门禁检查的分类、缓存与 proof 统一消费 `GateCheckSpec` 字段，公共底座不反向导入上层脚本。

## 5. 业务域责任与读写边界

| 领域 | 写入/裁决归属 | 主要事实消费者 | 本轮收敛方向 |
|---|---|---|---|
| 工艺与模板 | 工艺维护、路线确认、模板血缘 | 批次生成、排产输入、校准 | 删除 `_RawProcessFacts(dict)` 偷跑 SQL 与 `self._snapshot` 偷渡；文件预览与正式提交共用已解析结构；`capabilities/blocked_reasons` 收口到领域层 |
| 批次与分件 | 数量、拆分、状态、工序实例 | 排产、物料、现场、交付 | `batch` 列表/选择/导出跳过无消费的全库 `workflow_snapshot`，单批次详情与工艺同步按目标零件及外协组闭包加载；分件图保持完整前驱与范围闭包 |
| 资源与工作日历 | 设备、人员、资格、时段、停机 | 求解、采用、负荷、甘特 | 收口为单一无连接 `CalendarEngine(CalendarInputs)`，区分缺表 `None` 与空表 `()`，按日惰性解析并共享跨夜尾巴分段纯函数 |
| 物料与齐套 | 到料、分配、分阶段齐套规则 | 预检、排产、交付、看板 | 保留整批/按序差异；从 `materials.py` 抽离通用命令路由 helper 供全域共用 |
| 外协 | 外协记录、接续与反馈 | 排产、执行、看板 | 外协接续规则一处维护；单条与批量导入共享准入 |
| 排产运行 | 预检、受理、计算编排、候选发布 | 决策、历史、采用 | 预检与受理共用 `PreparedBusinessInput`（分离公开投影与内部评估行，受理仅增量补齐未选工序投影）；退役 `schedule_orchestrator.py` |
| 正式计划与试调 | 正式采用、试调保存、试调采用 | 现场、对比、报表、历史 | 普通/分件采用、候选发布、试调保存/采用共用统一安排约束验证结果；消除试调采用同事务双跑验证器与两处 8 行采用持久化转发壳 |
| 报工执行 | 实际数量、时间、撤销、剩余量 | 排产保护、实际甘特、校准 | 执行台账为唯一权威；已开工保护在 `PreparedBusinessInput` 源头一次生成 |
| 校准 | 样本、测算、确认采用、定额血缘 | 工艺、历史 | 校准采用回执查询并入统一数据库命令回执协议，删除校准采用 404 特判；精确量不经显示浮点回流 |
| 报表/看板/决策/历史 | 只读投影和导出 | 用户 | 显式事实作用域单向供数；前端正式 `Table` 原生支持列宽拖拽与 `caption/scope`，删除 `ReportEvidence.jsx:45` 扫 DOM 补丁 |
| 系统维护与宿主 | 启动、备份、恢复、配置、生命周期 | 所有业务用例 | 退役 `app_new_ui.py`、`start_new_ui.bat` 与 `ui_mode`；删除 `app.py:52` import 副作用；修复 `wufenchang_demo/builder.py:33` |

## 6. 状态、契约和生命周期

### 6.1 每类状态只有一个权威来源

| 状态 | 权威与生命周期 | 消费规则 |
|---|---|---|
| 当前生产资料、执行事实、正式安排 | SQLite 当前事实（Schema v45）；受事务和修订指纹约束 | 进门先验轻量修订指纹；同事务内通过显式事实作用域对象共享按需关系闭包 |
| 已受理输入、候选与历史证据 | 保存时的归档 JSON、安排与持久读模型（格式零变更） | 直接消费保存事实，不用当前资料悄悄重算历史归档 |
| `PreparedBusinessInput` | 单次预检/受理或受理后复用作用域 | 完整持有 `algo_ops`、执行保护、`SeedPreparation`（含 `to_schedule` 与人员资格准入）、`piece_scope` + `predecessors`、`dispositions`、`latest_plan_rows`、`operation_efforts` |
| 统一安排约束验证结果 | 候选发布、正式采用、试调保存/采用单次验证 | 同事务验证一次即产出结构化验证结论，直接交给持久化写入，不再二次重跑 |
| `CalendarEngine(CalendarInputs)` | 纯内存日历实例（按快照/输入构建） | 按日惰性解析，注册 checkpoint 证书，无数据库连接依赖 |
| 命令最终结果与回执查询 | `WorkbenchCommandReceipts` 原表记录 + 读取出口统一信封 | 5 类数据库命令回执链路共用 `WorkbenchCommandService` 解析原语（包装仅在读取出口生成，不写回改表）；排产受理保持 `{found, run, resolution, data_context_ref}`；系统维护保持数据库回执或外部维护日志协议；浏览器本机存储失败不推翻服务端已确认终态 |
| 前端请求、命令结算与页面状态 | 共享传输/命令会话 + React 组件状态 + 领域 Model | `bindResponse` 校验请求身份与快照绑定；`PlanGanttModel` 负责紧凑引用展开；Contract 不再重跑分页算术、全量 diff 与 SQL 排序重验 |
| 门禁检查描述与证据缓存 | `GateCheckSpec` + `FingerprintFileSnapshot`（评估阶段单次缓存） | runner、cache、proof 共同消费同一 `GateCheckSpec` 实例，不再按命令显示字符串分类 |

### 6.2 解析、校验与错误

外部输入在负责边界完成唯一一次结构和业务准入；内部受控结构直接按契约访问。

| 错误类别 | 处理责任 | 面向调用者的含义 |
|---|---|---|
| 外部输入格式或值域无效 | 后端输入合同 / 前端表单 `input` 校验 | 拒绝本次请求，返回具体字段或明确业务原因 |
| 轻量修订指纹与当前事实冲突 | 用例进门快速指纹核验 / 写事务前置守卫 | 立即返回 `409 snapshot_stale`（不在重型组装之后才判旧），不产生部分写入 |
| 已提交但响应未到达 | 前端统一命令结算会话 + 后端 7 条统一回执查询接口 | 结果未决；按原 `request_key` 与 `RunDataContext` 查询，不生成新键重做，不因校准未找到抛 404 特例 |
| 存储/进程/文件异常 | 基础设施边界及用例终结逻辑 | 保持失败、回滚或持久恢复状态，日志可精确定位 |
| 内部受控契约破坏 | 实现所属模块 | 直接暴露异常，严禁补默认值、`.get()` 兜底或静默吞错 |

### 6.3 具体接口归属

| 交接 | 目标责任 | 详细接口来源 |
|---|---|---|
| 当前事实 → `PreparedBusinessInput` | 预检与受理共享的一次业务准备（分离公开投影与内部评估行，受理仅增量补齐未选工序投影） | [调度专题](scheduler-design.md) |
| 候选/试调/采用安排 → 统一安排约束验证结果 | 统一验证普通/分件安排约束并直接供候选发布、正式采用、试调保存/采用消费 | [调度专题](scheduler-design.md) |
| `CalendarInputs` → `CalendarEngine` | 单一无连接日历引擎（区分 `None` 与 `()`、按日惰性解析、checkpoint 证书、跨夜尾巴分段纯函数） | [调度专题](scheduler-design.md) |
| 轻量指纹 → 显式事实作用域（按用途关系闭包） | 各业务域只读/写用例的统一取数与供数边界 | [数据与运行时专题](data-and-runtime-design.md) |
| 7 条命令提交与回执查询 → 统一回执信封 | 抽离通用命令路由 + `WorkbenchCommandService` 解析原语 + 前端统一回执结算会话 | [数据与运行时专题](data-and-runtime-design.md)、[前端专题](frontend-design.md) |
| ESM 源码 → `esbuild` 生产产物 / `vm.Context` 沙箱 bundle | 生产离线 bundle 与 Node 契约测试统一构建管道 | [前端专题](frontend-design.md) |
| `GateCheckSpec` → runner / cache / proof | 门禁定义、执行、缓存与完成证明 | [治理工具专题](tooling-design.md) |

## 7. 各系统的目标设计

### 7.1 排产、试调与日历：两份核心结果与单一无连接日历引擎

1. **`PreparedBusinessInput` 统一预检与受理准备**：
   - 完整持有 `algo_ops`、执行保护、`SeedPreparation`（含 `to_schedule` 与人员资格准入）、`piece_scope` + `predecessors`、`dispositions`、`latest_plan_rows`、`operation_efforts`，彻底废除九元位置元组与求解空占位。
   - 从源头分离预检公开 DTO 投影与内部评估行，彻底删除 `preflight_result.py:76` 对返回字典原地 `pop("_internal_...")` 的破坏性操作；受理复用同一准备核心，仅在需要时增量补齐上版正式计划未选工序投影。
2. **统一的安排约束验证结果**：
   - 将散落在候选发布、普通批次正式采用、分件正式采用、试调保存与试调采用中的安排约束验证收口为单一验证入口与结构化结果。
   - 消除试调采用同一写事务内连跑两遍验证器的冗余；退役 `schedule_execution_persistence_guard.py`、`schedule_orchestrator.py` 以及普通/分件采用中两处 8 行持久化转发壳。
3. **单一无连接 `CalendarEngine(CalendarInputs)`**：
   - 严格区分缺表 `None`（未提供）与空表 `()`（显式为空），按日惰性解析日历时段，显式注册 checkpoint 证书，提取共享的跨夜尾巴分段纯函数。
   - 彻底退役 `CalendarService` 计算转发壳、带连接的日历快照子类以及 `connection_snapshot_metadata` 幽灵元数据。详见[调度专题](scheduler-design.md)。

### 7.2 前端：ESM 显式模块化、拔除 `prototype/` 与剥离受控 DTO 重复自检

1. **全量 ESM 与统一 `esbuild` 构建/测试管道**：
   - 全部生产前端模块改为显式 `import/export`，彻底删除业务 `window.*` 全局导出与 `build.py` / `compile.cjs` 人工脚本顺序表。
   - 宿主使用固定版本 `esbuild` 同时服务生产 IIFE 离线打包与 Node `vm.Context` 测试沙箱打包（支持按测试注入 React/模块替身），目标机只消费编译产物。
2. **彻底拔除 `prototype/` 生产依赖并补齐正式 `Table`**：
   - `frontend/workbench/prototype/`、`static/workbench/prototype/` 与 `scripts/workbench/import_prototype.py` 已 100% 物理清退归零（存活样式/字体/图标迁入 `frontend/workbench/app/{styles,assets}/`）；正式 `app/shared/ui/Table.jsx` 完整保留列宽拖拽交互，并原生渲染无障碍 `caption` 与表头 `scope`，从而彻底删除 `ReportEvidence.jsx:45` 挂载后用 `useLayoutEffect` 遍历 DOM 补属性的补丁。
3. **剥离对本机受控 DTO 的数千行重复自检与职责错位**：
   - 从 25 个 `Contract/API` 模块中剥离对本机 Python 后端受控 DTO 的 `Reflect.ownKeys` 键数白名单、分页公式重算（`totalPages` 等）、主线程 2 万行全量 diff 重验与 SQL 排序顺序重验。
   - 将 `PlanContract.js:209` 在校验器内混做的甘特图紧凑引用展开归位到 `PlanGanttModel`。
   - 严格保留真实边界保护：HTTP 响应信封校验、`bindResponse` 请求身份与快照绑定、外部表单 `input` 校验、浏览器 `localStorage` 的 `validIntent` 解析及真实局部降级语义；统一底层命令结算与资源订阅会话。详见[前端专题](frontend-design.md)。

### 7.3 工作台数据与命令回执：显式事实作用域、统一回执协议与零存储变更

1. **轻量修订指纹 → 按用途完整关系闭包 → 显式事实作用域**：
   - 各业务域统一遵循“进门先验轻量修订指纹 → 按实际用途加载完整关系闭包（如 `batch` 列表/选择/普通导出直接跳过无消费的全库 `workflow_snapshot`，单批次详情与工艺同步按目标零件及外协组闭包加载）→ 通过显式事实作用域对象单向传参”。
   - 彻底删除各业务服务上的 `self._snapshot` 临时属性偷渡（`try/finally` 置空）与 `_RawProcessFacts(dict)` 在字典里夹带仓储偷跑 SQL 的反模式；将实体 `capabilities/blocked_reasons` 判定收口到领域层。
2. **7 条命令/任务回执查询收口与协议边界**：
   - 从 `materials.py` 抽离通用命令路由模块；5 类数据库命令回执链路（普通、候选采用、试调采用、校准采用、试调编辑）共用 `WorkbenchCommandService` 解析原语与 `{state: "recorded" | "not_observed", receipt, may_be_in_flight, resolution}` 响应信封，删除校准采用回执查询的 404 特判，保留各领域路由身份与 `RunDataContext`，普通 CRUD 保持 key-only；排产任务受理查询保持 `{found, run, resolution, data_context_ref}`，文件级系统维护保持外部 `SystemMaintenanceJournal` 查询协议。
3. **持久存储格式 100% 零变更**：
   - 经核实 Schema（`CURRENT_SCHEMA_VERSION=45`，`migration_state.py:55`）与所有持久归档/读模型/回执表结构均无需改动；统一回执信封仅在读取出口组装，不改写 `WorkbenchCommandReceipts` 存量记录。因此**不设任何离线数据库格式转换器或离线 `reconcile_frozen_intent` 对账工具**。详见[数据与运行时专题](data-and-runtime-design.md)。

### 7.4 门禁工具：保留 `quality_gate_shared.py`、单一 `GateCheckSpec` 与清理死代码

1. **保留 `quality_gate_shared.py` 公共底座，单一 `GateCheckSpec` 消除字符串分类**：
   - 不拆分 4 个碎片新文件；在 `quality_gate_shared.py` 中以 `GateCheckSpec` 统一声明检查身份、命令、作用域、缓存策略与长门禁归属，直接消除 `long_gate_manifest.py:91` 与 `run_quality_gate.py:1028` 两处靠命令字符串逆向分类的脆弱逻辑。
2. **删除 0 调用 manifest/replay 死代码闭包与单步重复 `pyright`**：
   - 按符号调用闭包删除 `quality_gate_shared.py` 中 0 生产调用的 manifest/replay 验证死代码孤岛（`:529-551`、`:579-673`、`:986-999`、`:1068-1095`、`:1126-1457`，完整保留 `:1460-1502` 活函数底座与 `run_quality_gate.py:458` 实际使用的回执/resume 原语），彻底消除公共底座对上层 `run_quality_gate` 的反向导入；将仓库身份纯函数下沉为 `repo_identity`。
   - 删除 `run_quality_gate.py:955-987` 及 `:994` 在同一门禁步骤内紧挨着重跑第二次的重复 `pyright` 子进程（保留 `:940` 的配置一致性检查）；保持 `FingerprintFileSnapshot` 在单次缓存评估阶段的作用域内复用。
3. **退役历史临时扫描器**：
   - 将当前完整生产文件集的 required scope 覆盖检查直接并入 `test_registry` 常规检查，彻底退役 `scan_anti_regression_gate.py`、`scan_aps_three_gap_py38_scope.py` 及硬编码历史 commit `d4589d77` 的专向扫描。详见[治理工具专题](tooling-design.md)。

### 7.5 宿主启动、恢复和交付：彻底单入口化与零导入副作用

1. **彻底退役 `app_new_ui.py`、`start_new_ui.bat` 与 `ui_mode`**：
   - 移除 `app_new_ui.py`、`start_new_ui.bat` 以及散落在 `/system/health`、`launcher_contracts.py`、`validate_dist_exe.py:262` 中的 `ui_mode` 双入口字段与分支；源码与冻结包统一由唯一生产入口 `app.py` 启动。
2. **消除 `app.py:52` 模块导入副作用并修复维护工具引用**：
   - 将应用装配、目录准备、数据库检查与后台线程启动严格收口到显式启动入口函数中，确保 `import app` 零副作用；同步修复 `tools/wufenchang_demo/builder.py:33` 的失效导入。
3. **Win7 离线交付与原生平台验证**：
   - 恢复流程协调文件替换与数据库身份；离线交付包不携带 `esbuild` / Node 等宿主构建依赖；20 个待目标平台实跑的 Windows 专属监听测试节点纳入 `A5` 最终交付必过验收。[现行风险登记](../../../开发文档/技术债务治理台账.md#L1920)。

## 8. 一次性迁移的实施顺序

### 8.1 一个交付单元内的工作包（已修正依赖顺序）

> **实施前置硬约束**：当前工作树包含 500+ 项既有修改，动手实施任何工作包前，**必须先对当前工作树建立可恢复的 Git 快照（stash/branch/tag 备份）**，严禁裸跑 `git checkout` 或丢弃既有修复。

| ID / slug | 内容与退出条件 | 依赖 |
|---|---|---|
| `A0` / `ownership-contracts` | 冻结全域职责、目标接口签名、零存储变更边界与逐文件消费者清单；对齐 `.limcode/rules/` 修订草案 | 无 |
| `A1` / `scheduler-use-case` | **(`minimal_loop: true`)** 落地 `PreparedBusinessInput`（分离预检公开投影与内部评估行，删除 `preflight_result.py:76` 删字段，受理仅增量补齐未选工序投影）、统一安排约束验证结果（消除试调采用同事务双跑验证器，退役 `schedule_execution_persistence_guard.py`、`schedule_orchestrator.py` 及两处 8 行采用持久化转发壳）、单一无连接 `CalendarEngine(CalendarInputs)`；同步完成宿主单入口化（退役 `app_new_ui.py`、`start_new_ui.bat`、`ui_mode`，消除 `app.py:52` import 副作用，修复 `wufenchang_demo/builder.py:33`）；通过最小开发闭环验证 | `A0` |
| `A3` / `frontend-modules` | **（保持现有 HTTP 协议不变，先于 `A2` 完成）** 全生产前端改为显式 ESM 模块，落地宿主固定版本 `esbuild` 生产打包与 Node `vm.Context` 测试沙箱；彻底拔除 `prototype/` 生产依赖（正式 `Table` 保留列宽拖拽并原生支持 `caption/scope`，删除 `ReportEvidence.jsx:45` 扫 DOM 补丁）；剥离 25 个 `Contract/API` 对本机受控 DTO 的重复算术/字段表/排序重验，将 `PlanContract.js:209` 紧凑引用展开归位 `PlanGanttModel`；统一前端底层命令结算与订阅会话 | `A0` |
| `A2` / `data-command-boundaries` | **（在 `A1`、`A3` 基础上同包切换前后端回执协议与后端事实作用域）** 完成工作台各业务域“先验轻量修订指纹 → 按用途取完整关系闭包（`batch` 列表/选择/导出跳过无消费 `workflow_snapshot`，详情与工艺同步按目标零件及外协组闭包加载）→ 显式事实作用域单向供数”，删除 `self._snapshot` 临时属性偷渡与 `_RawProcessFacts(dict)`，领域层收口 `capabilities/blocked_reasons`；从 `materials.py` 抽离通用命令路由，**同包同步切换后端 7 条命令回执查询链路、全部前端回执消费者、错误回执地址 `expect` 与契约测试 fixture**（删除校准采用 404 特判，保留领域路由身份、`RunDataContext`、排产受理与外部维护日志契约，底层持久存储零变更） | `A0`、`A1`、`A3` |
| `A4` / `tooling-definition` | 保留 `quality_gate_shared.py` 公共底座，落地单一 `GateCheckSpec` 消除两处字符串分类；按调用闭包删除 `quality_gate_shared.py` 中 0 生产调用的 manifest/replay 死代码孤岛（`:529-551`、`:579-673`、`:986-999`、`:1068-1095`、`:1126-1457`，保留 `:1460-1502` 活底座与回执/resume 原语）消除反向导入，下沉 `repo_identity`；删除 `run_quality_gate.py:955-987` 及 `:994` 第二次重复 `pyright` 子进程；将完整生产文件集 required scope 检查并入 `test_registry`，退役 `scan_anti_regression_gate.py`、`scan_aps_three_gap_py38_scope.py` 及 `d4589d77` 硬编码 | `A0` |
| `A5` / `integrated-cutover` | 全工作树合流，同步更新 `.limcode/rules/`、架构与开发文档；使用 `A4` 新门禁执行完整门禁、实际浏览器主流程验证与 Win7 原生平台验收；一次性停写切换激活整套新程序与静态资产 | `A1`、`A2`、`A3`、`A4` |

**为什么 `A3` 先于 `A2`、`A2` 依赖 `A0, A1, A3`**：
`A3` 在保持现有 HTTP 传输协议不变的前提下，先把前端重构为清晰的 ESM 模块、完成 `esbuild` + `vm.Context` 测试底座并收口前端统一命令结算会话；随后 `A2` 只需在单一集中的前后端命令边界上，同包原子切换后端 7 条回执路由与前端回执消费者、错误回执 `expect` 及测试夹具，避免前后端工作包循环等待或半途协议分裂。`A1` 标为 `minimal_loop: true`，仅作为内部开发闭环验证，所有工作包合流通过 `A5` 后一次性交付。

### 8.2 每个工作包的旧路径退出要求

1. 迁移清单同时覆盖生产调用、测试夹具、字符串引用、构建/打包脚本、规则文档和门禁登记。
2. 实现目标契约后一次性迁移全部消费者，当场删除被替代的旧模块、薄包装壳、死分支与只为旧实现续命的测试支撑（严禁搬家兜底或留重导出空壳）。
3. 保留验证真实业务语义的断言，更新依赖旧私有结构或旧脚本拼接方式的测试，严禁通过放宽断言或吞异常制造假通过。
4. 在源码与构建产物中通过 `rg` 与 `tools.symbol_locator` 核实旧符号、旧路径（如 `prototype/`、`app_new_ui`、`ui_mode`、`schedule_orchestrator`、`d4589d77`）引用清零。
5. 对应文档与实际代码同步后完成工作包，全部工作包在 `A5` 合流通过完整门禁后统一交付。

## 9. 零存储变更下的程序统一切换

### 9.1 开发快照与演练准备

- **第一步先建快照**：在当前含 500+ 项既有改动的工作树上创建可恢复 Git 快照，确保任何时候均可完整还原。
- **零数据库格式转换**：由于 SQLite Schema（v45）、候选/试调归档 JSON、持久读模型、`WorkbenchCommandReceipts` 原表记录及本机 `localStorage` 未决意图编码均保持 100% 不变，切换过程**不需要运行任何离线数据库转换脚本或离线未决意图对账工具**。
- 在当前业务库副本上直接演练新程序的启动恢复、未决命令在线回执查询、排产/试调/采用全流程及静态资源加载。

### 9.2 正式切换顺序

1. 确认 `A1`～`A4` 全部合流，完整门禁、实际浏览器与 Win7 目标平台验收通过，安排一次简短停写窗口。
2. 停止接收新命令；等待正在计算的排产运行或进行中的维护恢复正常终结（或由现有停止屏障安全收尾）。
3. 关闭旧进程并确认运行锁释放，保存当前数据库文件与配置目录的完整可恢复备份副本。
4. 部署目标程序与 `esbuild` 生成的离线静态资产（移除 `app_new_ui.py` 与 `start_new_ui.bat`），从唯一生产入口 `app.py` 启动服务，由现有启动恢复机制自动完成运行态自检。
5. 浏览器刷新加载新静态资产：可丢弃的只读查询缓存直接清空；若浏览器 `localStorage` 中仍存有切换前已发出但尚未收到响应的 `pending` 命令，前端统一命令结算会话直接按原 `request_key` 与 `RunDataContext` 调用在线回执查询接口获取统一回执信封并完成终态结算，严禁粗暴清空 `localStorage` 抹掉未决意图。
6. 完成核心读取、命令提交与回执查询冒烟核验后，正式开放业务写入。

### 9.3 回滚责任

- **开放新写入前**：若启动或冒烟检查发现异常，直接停机并切回备份的程序与数据库副本。
- **开放新写入后**：虽底层 Schema 与存储格式零变更，但一旦产生新业务写入，严禁直接用旧数据库备份覆盖回滚以免丢失新生产的报工、计划或回执记录；优先前向修复，确需切回旧程序版本前须先停写并核对新增记录的完整性。

## 10. 验收：验证真实行为和维护收益

### 10.1 行为覆盖矩阵

| 面向风险 | 必须证明的行为 | 现有入口示例 |
|---|---|---|
| 排产、预检与日历 | `PreparedBusinessInput` 预检/受理共享且无原地删字段；普通/分件/零工时/执行保护/人员资格 seed；`CalendarEngine` 空表 `()` 与 `None` 区分、跨夜分段与 checkpoint 证书 | `tests/candidate/test_shared_optimizer.py`、`test_shared_schedule_archive.py`、`tests/workbench/test_piece_chain_end_to_end.py` |
| 统一安排验证与采用原子性 | 候选发布、普通/分件采用、试调保存/采用共用安排验证；试调采用同事务只验一次；事实变更拒绝、重复键幂等、失败完整回滚 | `tests/workbench/test_run_candidate_adoption_atomic.py`、`test_trial_adoption_atomic.py` |
| 显式事实作用域与命令回执 | 进门先验轻量指纹、`batch` 跳过无消费 `workflow_snapshot`、无 `self._snapshot` 偷渡与 `_RawProcessFacts`；7 条命令统一回执信封（含校准采用未命中正常返回未找到状态而非 404 特判） | `tests/workbench/test_stored_snapshot_validation.py`、`test_dashboard_read_reuse.py`、`test_run_decision_process_api.py`、`test_execution_ledger_commands.py` |
| 前端 ESM、正式 `Table` 与受控 DTO 边界 | `esbuild` + `vm.Context` 沙箱测试通过；0 `prototype/` 引用；正式 `Table` 列宽拖拽与原生 `caption/scope`；`PlanGanttModel` 紧凑引用展开；剥离重复算术/排序自检后真实边界守卫完好 | `tests/workbench/test_ui_refinement_node_contracts.py` 与实际浏览器验证 |
| 门禁单一描述与性能 | `GateCheckSpec` 驱动 runner/cache/proof；`quality_gate_shared.py` 无反向导入；单步门禁 `pyright` 只跑一次；`test_registry` 覆盖完整生产文件集 required scope | `tools/host_tests/test_quality_gate_shared.py`、`test_gate_runner_and_hooks_content.py`、`test_long_gate_content.py` |
| 宿主单入口与 Win7 运行 | `import app` 零副作用；`app_new_ui.py`/`ui_mode` 彻底清零；离线冷启动、端口预绑定、双开拦截、停止重启、恢复与锁 | `tests/app_runtime/test_launcher_startup.py`、`test_runtime_server_binding.py` 及 Win7 目标机实测 |

### 10.2 执行层次

各工作包执行直接关联测试与适用日常检查；`A5` 全工作树合流后使用 `A4` 完成的门禁工具执行项目完整门禁，按[质量治理入口](../../../开发文档/README.md)收集真实 clean proof。

实际浏览器覆盖新前端主业务流程、甘特交互、正式 `Table` 列宽拖拽与打印/导出行为；Node `vm.Context` 契约测试不能代替真实浏览器渲染。20 个 Windows 专属节点必须在目标平台实跑通过，不得借缓存或跳过核销。

### 10.3 架构收益验收

| 实施前的维护负担 | 完成后可直接核验的变化 |
|---|---|
| 预检/受理重复准备、九元元组交接、`preflight_result.py:76` 原地 `pop` 删字段 | 统一为 `PreparedBusinessInput`，公开投影与内部评估行源头分离，受理仅增量补齐未选工序投影 |
| 候选发布、普通/分件采用、试调保存/采用各写一套验证，试调采用同事务双跑验证器 | 收口为单一安排约束验证函数与结果，退役 `schedule_execution_persistence_guard.py`、`schedule_orchestrator.py` 及两处 8 行采用持久化转发壳 |
| 业务域 `self._snapshot` 临时属性偷渡、`_RawProcessFacts(dict)` 偷跑 SQL、`batch` 白取全库快照 | 统一为“轻量指纹 → 按用途完整关系闭包 → 显式事实作用域传参”，临时属性与字典伪仓储清零 |
| 前端 `window.*` 导出、反向依赖 `prototype/`、25 个 `Contract/API` 数千行重复算术/排序重验 | 100% ESM + `esbuild`，`frontend/workbench/prototype/`、`static/workbench/prototype/` 与 `scripts/workbench/import_prototype.py` 已 100% 物理清退归零（存活样式/字体/图标迁入 `frontend/workbench/app/{styles,assets}/`），正式 `Table` 原生支持拖拽与无障碍属性，受控 DTO 重复自检剥离且甘特展开归位 `PlanGanttModel` |
| `app_new_ui.py` / `ui_mode` 双入口分裂，`app.py:52` import 触发重副作用 | 唯一生产入口 `app.py`，`import app` 零副作用，`ui_mode` 全面退役 |
| 门禁靠字符串分类、`quality_gate_shared.py:1312` 0 调用孤岛反向导入、单步双跑 `pyright`、硬编码 `d4589d77` | 单一 `GateCheckSpec`，0 调用孤岛与第二次 `pyright` 删除，临时扫描器退役并由 `test_registry` 接管完整生产文件集 |

## 11. 未来功能怎样进入这个架构

| 未来变化 | 首要拥有者 | 合理影响范围 |
|---|---|---|
| 增加由保存事实计算的展示指标 | 对应只读投影与前端领域 Model | 后端投影、公开 DTO、前端领域 Model/组件；无需在前端 `Contract` 再写一套算术/排序重验 |
| 修改日历效率或跨夜时段解释 | `CalendarEngine` 与共享跨夜分段纯函数 | 所有求解、验证与展示消费者自动复用同一结论 |
| 新增排产策略或试调联动能力 | `scheduler` 求解策略与 `workbench/run` 统一安排约束验证 | 求解策略直接消费 `SolverInput / SolverResources`，工作台安排验证直接消费 `PreparedBusinessInput` 与统一安排验证结果，不再新建准备或持久化转发链 |
| 新增或修改工作台写命令 | 领域写用例 + 通用命令路由 + `WorkbenchCommandService` | 自动接入 7 条统一回执查询信封与前端命令结算会话，无需单写回执路由和前端轮询状态机 |
| 新增门禁检查 | `quality_gate_shared.py` 中的 `GateCheckSpec` | 声明一次规格，runner、cache、proof 自动消费，无需修改分类器分支 |

## 12. 与旧规划、规则的关系及实施前置准备

### 12.1 明确承接与改变

| 既有资料 | 本次关系 |
|---|---|
| [地基边界治理](../foundation-boundary-governance/foundation-boundary-governance-roadmap.md) | 承接 SQL/业务分离与单向依赖；本次进一步清退 `_RawProcessFacts(dict)`、`self._snapshot` 偷渡与前端/工具遗留边界问题 |
| [工作台簇层次](../foundation-boundary-governance/workbench-cluster-layering.md) | 保留领域簇与 `facts/` 共享叶子职责；明确按用途取完整关系闭包，禁止把业务编排塞入 `facts/` |
| [单次准备设计](../../refactors/2026-10-15-single-pass-workflow/single-pass-workflow-refactor-design.md) | 保留一次事实捕获与固定准备复用，并将其彻底推进为预检/受理共享的 `PreparedBusinessInput` 与统一安排验证结果 |
| [试调扩展规划](../trial-scenario-planning/trial-scenario-planning-roadmap.md) | 保留独立功能路线；本次消除试调采用同事务双跑验证器并统一安排验证底座，为后续试调扩展提供干净接缝 |
| 当前 `.limcode/rules/` 与架构文档 | 在 `A0` 冻结修订草案，在 `A5` 代码合流后按真实责任同步更新，废除要求所有模型/仓储套僵化模板及保留 `ui_mode` 的过时条款 |

### 12.2 实施启动前的明确准备项

1. **建立工作树可恢复快照**：在动手修改任何代码前，先对当前含 500+ 项既有改动的工作树建立可恢复 Git 快照。
2. **锁定宿主 `esbuild` 版本与沙箱基线**：在 `A3` 启动时固定宿主 `esbuild` 二进制版本，跑通生产离线 bundle 与 Node `vm.Context` 测试沙箱注入。
3. **准备 Win7 目标平台测试环境**：在 `A5` 合流前就绪 Win7 目标机/虚拟机环境，完成 20 个 Windows 专属节点与 Chrome 109 实测。

## 13. 文档定稿状态

本路线图及四份专题（[调度专题](scheduler-design.md)、[数据与运行时专题](data-and-runtime-design.md)、[前端专题](frontend-design.md)、[治理工具专题](tooling-design.md)）、[工作包清单](aps-architecture-consolidation-items.yaml)已完成全仓源码穿透核查与双模型多轮定稿收敛。路线图状态已更新为 `active`；当前 `A0`、`A1`、`A2`、`A3`、`A4` 已完成（`completed`），`A5` 保持 `in-progress`（macOS Python 3.8.10 下 `scripts/run_daily_quality_gate.py` 通过 `1095 passed, 20 skipped` 且宿主工具测试 `tools/host_tests` 全部通过；`scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache` 第 1～14 步全部通过——全集收集 `1404` 项：`1368 passed`、`36 skipped`、`0 failed`、`0 active xfail`，退役历史债务 `5` 项，其中 `36` 项平台/环境跳过含必跑回归中的 `20` 个 Windows/PowerShell 节点即 `test_launcher_startup.py` `15` 个与 `test_runtime_server_binding.py` `5` 个，另有非必跑 `test_sample_switch.py` `15` 个 `pwsh` 节点与 `test_portable_delivery.py` `1` 个 Windows 7-Zip 节点，故第 15 步 `required_regressions` 在 macOS 上按设计因该 `20` 个必跑跳过节点返回 `1`；隔离临时库现场浏览器验收通过——通过 `aps-start-and-rerun-route` `rerun --db-path /private/tmp/.../demo.db` 在 `127.0.0.1:58766` 完成预检、排产与正式采用 `v1` 19 道任务，实测甘特图、正式 `Table` 原生 `<caption>`/`<th scope="col">`/列宽拖拽 `+30.12px`、`/workbench/trial` 及 100% 本地静态资源，`0` 控制台/页面/网络错误；剩余待办仅限 Win7 x64 目标机实跑 Windows 专属测试节点与 Chrome 109 验收，以及正式 git commit 后执行 `--require-clean-worktree --long-gate-cache --no-resume` 生成最终 clean-worktree proof），依赖顺序已修正为 `A0 -> {A1, A3, A4} -> A2 (依赖 A0, A1, A3) -> A5`，并明确了 100% 零持久存储格式变更裁决。
