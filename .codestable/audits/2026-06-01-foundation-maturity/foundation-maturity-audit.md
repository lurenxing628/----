---
doc_type: audit
slug: foundation-maturity
scope: APS 项目地基成熟度第一轮体检 + 第二轮函数级深钻的专题划分依据
summary: 7 个并行审计 Agent 对 core/web/data/文档/门禁的可维护性体检结论，结论是"地基比预期牢，主病是迁移做了一半"，并据此切出第二轮深钻专题
status: current
created: 2026-06-01
last_reviewed: 2026-06-01
tags: [aps, codestable, audit, maintainability, foundation, refactor-seed]
depends_on: [ARCHITECTURE]
implements: []
---

# APS 项目地基成熟度体检（第一轮）

> 体检日期：2026-06-01
> 方法：7 个并行审计 Agent，分区互斥，统一要求 `file:line` 证据 + 严重度分级 + 1-5 地基评分；关键结论由主控交叉验证
> 目的：为"把项目做成可持续迭代的优秀项目"建立**地基基准**，并切出第二轮**函数级深钻**的专题
> 重要定性：本轮是**广度扫描**，刻意覆盖全项目找出主旋律。它**不是**最终整改方案——治本要靠第二轮按本文专题钻到函数级（见 §6）

---

## 0. 阅读这份文档的人

- **维护者（你）**：看 §1 总体结论、§2 主旋律、§5 优先级，建立全局判断。
- **第二轮深钻 Agent**：看 §6 专题清单——每个专题给了入口文件、已知线索、要钻到的粒度和输出契约。不要重复第一轮的广度扫描，要往函数级钻。

---

## 1. 总体结论：地基比预期牢，主病是"迁移做了一半"

**先给安心的结论**：这个项目的地基比典型 LLM 长期项目健康得多。支撑这一判断的硬指标（均经独立验证，非文档自述）：

- **分层红线真实成立**：
  - `core/algorithms/` grep `core.services` 完全为空——算法层零反向依赖 service（架构文档这条声明属实）。
  - 57 个 viewmodel 零个 import `data.repositories`、零裸 SQL、零 import service。
  - 98 个 route 零个直连 repository。
  - 33 个 repo 全部注入连接、不自开连接、默认不 commit（事务交给 `TransactionManager`）。
  - 裸 SQL 仅出现在 `data/repositories/`、`core/infrastructure/`（logging/migration）三处合理位置；service 层零裸 SQL。
- **没有脏债务标记乱飞**：全 core/web/data 仅 3 个 TODO/FIXME；98 处"临时/暂时"几乎全是面向用户的中文文案（"暂时算不出来"），不是代码凑合标记。
- **文件命名成族群**：`batch_*`/`gantt_*`/`resource_dispatch_*`/`schedule_*`/`config_*` 命名体系化，不是 `_v2`/`_tmp` 垃圾命名。
- **测试没被静默关闭**：全仓仅 1 处 `mark.skip`、7 处 `xfail`，债务台账 ratchet 设 `max_registered_xfail: 0`。

**真正的病根，一句话：迁移做了一半。** 几乎每个分区的高/中严重度问题，本质都是"重构开了头没收尾"——新结构建好了，旧结构靠测试养着不死，于是同一概念出现两套实现、三种 shim、四个空目录。这是 LLM 增量建设的典型签名：每次都新建一条干净的路，但很少回头拆旧路。

### 各分区评分

| 分区 | 评分 | 一句话 |
|---|---|---|
| 排产算法主链（scheduler/run + 顶层 schedule_*） | **4/5** | 骨架与依赖注入是全系统标杆，命名漂移在累积 |
| core 地基层（models/algorithms/infra/shared） | **4/5** | 分层过硬，两处局部债（备份双实现、配置校验放错层） |
| 持久层 + 报表层（data/repositories + report） | **4/5** | 最成熟的区，扣分在 ScheduleRepository 死代码 |
| 派工/甘特/执行/诊断（scheduler 其余） | **3/5** | 设计用心但被过度平铺 + helper 复制 + 半截重组拖累 |
| web 展示层（routes/viewmodels/bootstrap） | **3/5** | 分层扎实但三处重构都只做了一半 |
| 文档时效性 | **3/5** | 两层断裂：`.codestable` 出奇地准，`开发文档/` 严重滞后 |
| 质量门禁与测试 | **2/5** | 唯一拉响警报的区：脚手架已重过它保护的对象 |

---

## 2. 跨分区主旋律（SPEC 应锁定的根因）

把 7 份报告叠起来看，4 个模式在多个分区**独立复现**。治本要治这 4 条，而不是逐个 issue 打地鼠。

### 主旋律 1：shim 垫片泛滥，且生产零引用、仅测试在养
- 排产层：顶层 `schedule_optimizer.py` 等用 3 种不同写法转发到 `run/`（`__getattr__`+import_module / `sys.modules[__name__]=_impl` / 直接 from import）
- 派工层：12 个 config/schedule 顶层 shim，2 种机制并存
- web 层：9 个顶层 scheduler 路由 shim + 3 种写法（`_scheduler_compat.py` 支撑）
- **已验证**：`core.services.scheduler.schedule_optimizer` 在 core/web 生产代码引用为 0；这些 shim 唯一消费者是测试（旧导入路径）。
- **含义**：测试把旧导入路径钉死了，导致 shim 永远删不掉 → **测试在阻止重构收尾**。这是主旋律 1 和门禁臃肿（分区 7）的交汇点。

### 主旋律 2：同一概念两套并行实现，旧的靠测试续命
- `ScheduleRepository`（旧明细查询）vs `SchedulePlanQueryRepository`（新统一入口）——旧的 `list_dispatch_rows_with_resource_context`/`list_overlapping_with_details`/`list_between` 生产零调用，仅测试引用。
- `persist_schedule`（独立分支）vs `persist_schedule_run_with_candidates`（生产实际走的）——前者全仓仅 ~5 测试调用，且被 `as persist_schedule` 误导性改名。
- `backup.py` vs `migration_backup.py`——两套 DB 文件锁重试，零代码复用，机制不同（在线 backup API vs 文件 replace，字符串匹配 vs winerror 判定）。
- **危险点**：改一处忘改另一处不报错，两条路径**静默分叉**。

### 主旋律 3：琐碎 helper 复制粘贴 + 同名函数静默漂移
- `_text(value): return str(value or "").strip()` 在派工区复制 **15 份**、web viewmodel 区复制 **9 份**，4 种名字（`_text`/`text`/`_clean_text`/`_text_or_none`）。
- op_id 取值逻辑被重写 ~5 个不同名私有函数（`_op_id`/`_algo_op_id`/`_seed_op_id`/`_op_id_set`/`positive_op_ids`）。
- **最危险的一条（P0 候选）**：`gantt_tasks.py:171/179/193` 与 `gantt_critical_chain.py:34/42/48` 有**同名但行为不同**的标签函数（`_detail_part_label`/`_detail_operation_label`/`_public_task_label`）——空值一个返回 `"-"` 一个返回 `""`，一个带 `piece_id` 兜底一个没有。同一道工序在甘特条 vs 关键链 tooltip 里可能显示成不同名字，改一处不报错。

### 主旋律 4：命名漂移让"名字"不再传达信息
- 同一个"最优解三元组"在 4 个 dataclass 里三套命名：`OptimizationOutcome`(metrics/best_score/best_order) / `CandidatePlan`(score/metrics/best_order) / `ScheduleOrchestrationOutcome`(best_metrics/best_score/best_order)，靠 `_normalize_optimizer_outcome`/`_normalize_candidate_plan` 两个逐字段映射函数桥接——错配（如 score 映到 best_order）静默串数据不报错。
- 下划线"私有"函数被跨文件 import（`_run_multi_start`/`_run_ortools_warmstart`），公有函数被改名成私有（`schedule_with_optional_strict_mode` → `_schedule_with_optional_strict_mode`）。
- viewmodel 类后缀混用：ViewModel / State / PanelState / ViewResult；文件后缀 `_vm`/`_page`/`_presenter`/`_display`/裸名 漂移。

---

## 3. 分区详细发现（带证据）

### 3.1 排产算法主链 — 4/5
- **[高] 最优解三元组三套命名靠映射桥接**：见主旋律 4。证据 `run/schedule_optimizer.py:41-43`、`run/schedule_candidate_runner.py:39,45,51`、`run/schedule_orchestrator.py:42-44,67-69,78,100`。
- **[高] 两条持久化入口近似重复，生产只走其一**：`schedule_service.py:23`（`persist_schedule_run_with_candidates as persist_schedule`）vs `run/schedule_persistence.py:322`（独立 `persist_schedule`，生产零调用）。
- **[中] "已完工下游不能早于实际完工"规则两文件各实现一遍**：`run/schedule_input_runtime_support.py:243` vs `run/schedule_execution_persistence_guard.py:168`，同 ErrorCode 同 reason，遍历逻辑平行拷贝。
- **[中] op-id 取值重写 ~5 个不同名私有函数**：见主旋律 3。
- **[中] 顶层 re-export shim 三种写法**：见主旋律 1。**澄清：不存在双 orchestrator**——顶层 `schedule_orchestrator.py` 只是 shim，真身在 `run/schedule_orchestrator.py:275`，无职责重叠。
- **[低] 过度拆分**：`run/optimizer_runtime.py` 仅 14 行、`run/freeze_window_prefixes.py` 仅 29 行、`schedule_graph_report.py:9-44` 用 12 条 `import X as _X` 仅为加下划线前缀。
- **做得好**：编排层依赖注入干净可测（`orchestrate_schedule_run` 注入 optimize/summary/persist/before_version_allocate 4 个 fn）；输入收口为单一 `ScheduleRunInput` 数据契约；strict_mode 兼容垫片用 `inspect.signature` 探测且不支持时显式抛错而非静默吞。

### 3.2 派工/甘特/执行/诊断 — 3/5
- **[高] gantt_tasks vs gantt_critical_chain 同名标签函数行为漂移**：见主旋律 3（P0 候选）。
- **[中] resource_dispatch_actual_* 五文件命名相互混淆**：`actual_records.py`（复数，实为共享 dataclass+helper，无"records"管理逻辑）vs `actual_record_service.py`（单数+service，真编排器）；配合 actual_import/actual_import_validation/actual_excel，靠单复数+后缀区分职责，全缺模块 docstring。
- **[中] 琐碎 `_text` helper 全区复制 15 份**：见主旋律 3。
- **[中] 顶层 shim 泛滥且两种机制，测试钉死旧扁平路径**：35 处扁平路径命中全在 tests/。
- **[低] 四个空子目录是半截重组残骸**：`scheduler/{gantt,dispatch,calendar,batch}/__init__.py` 全空，但平铺文件 `gantt_*.py`(13)/`resource_dispatch_*.py`(14) 都在外层——目录树误导。
- **做得好**：关键链双文件实为干净分层（`gantt_critical_chain.py` 纯计算引擎，`_provider.py` 带 LRU 缓存+分发+线程锁），非职责重叠；诊断子系统三层（service/clues/utils）职责不混；config 顶层非双轨（顶层只是转发壳，真实现全在 `config/` 子包）；全区零 TODO/FIXME/HACK。

### 3.3 core 地基层 — 4/5
- **[中] backup.py vs migration_backup.py 双实现**：见主旋律 2。`backup.py:354` `_copy_db_file`（在线 backup API + 字符串匹配重试）vs `migration_backup.py:38` `restore_db_file_from_backup`（copy2+replace + winerror 重试 + sidecar 清理），零复用。
- **[中] schedule_config_runtime_* 家族放错层**：6 文件 994 行（`core/models/schedule_config_runtime_coercion.py:1` 499 行等），做的是配置校验+降级引擎（import ValidationError/DegradationCollector），却挂在 models 下；models 其余 46 文件中 32 个是纯 dataclass。**注意这是"结构化但放错层"的债，不是拼凑债**——它被刻意拆成单一职责文件，分解质量好，问题纯在分层归属与 `runtime`/`coercion` 命名含糊。
- **[低] database_bootstrap.py 命名邻接误导**：实为 schema DDL 补齐（`bootstrap_missing_tables_from_schema`），与两个 backup 文件同目录易被误联想成备份。
- **[低] 算法层非纯计算**：`ortools_bottleneck.py:22`/`ordering.py:6` 依赖 infra 的 logging/errors（向下依赖合规，但拖了"纯函数可独立测试"的理想）。
- **做得好**：算法层零反向依赖（已验证）；models 层整体纯净（无 sqlite3/cursor/execute）；algorithms 内部内聚清晰（value_domains 显式标 EXTERNAL/INTERNAL/MERGED 域，greedy/ 子包按 run_state/external_groups/internal_operation 拆）。

### 3.4 持久层 + 报表层 — 4/5
- **[中] ScheduleRepository vs SchedulePlanQueryRepository 两套并行，前者明细查询生产已死**：见主旋律 2。
- **[中] scope 过滤分支两 repo 逐字符重复**：`schedule_repo.py:137-153` 与 `schedule_plan_query_repo.py:457-473`，operator/machine/team where 子句完全一致。
- **[中] 资源筛选归一化三处近似重复**：`schedule_plan_query_repo.py:62` 与 `schedule_plan_query_service.py:29` 同名函数**一字不差**（repo 和它的 service 各存一份），report 层 `report_context_filters.py:12` 第三份是扩展版；报错文案已开始不一致。
- **[中] operation_execution_state_builder.py 放在 repositories 却零 SQL**：277 行纯领域聚合（事件流→状态推导、暂停时长累加、label 映射），放在 data/repositories 违反"repo 只管数据访问"约定。
- **[低] schema 死表 OperatorSkill**：`schema.sql:111-121`（注释"预留"），全仓零引用。
- **[低] schema 版本双真相**：`schema.sql:23` 写死 version=0，`migration_state.py:9` `CURRENT_SCHEMA_VERSION=17`，靠运行时探测兜底。
- **[低] OperationExecutionEventRepo 双名别名**：33 repo 里唯一同时叫 `...Repo` 和 `...Repository`。
- **做得好**：连接管理高度统一（`sqlite3.connect` 只在 `database.py:67`）；SQL 收敛承诺真实成立；report 层不与 scheduler 重复造查询（`report_engine.py:68` 直接复用 `SchedulePlanQueryService`）；`schedule_detail_query.py` SQL 片段化构造是合理去重。

### 3.5 web 展示层 — 3/5
> **重要校准**：本分区部分发现需结合前端在途状态判读，见 §4。
- **[高] 路由注册三套并存，domains/ 分层迁移只做了 1/5**：`domains/scheduler/`（28 文件已分层）vs 顶层散落 personnel/equipment/process/system；`domains/{system,equipment,personnel,process}/__init__.py` 全 0 字节空占位。注册范式 3 种（side-effect import / 蓝图子类 register / 直接 bp 调用）。
- **[高] 9 个顶层 scheduler 路由 shim + 3 种写法**：见主旋律 1。
- **[中] service 获取方式按模块新旧分裂**：scheduler domain 15 文件全用 `g.services.xxx`；personnel/equipment/process 19 文件全部 `Service(g.db,...)` 现场 new；同一 service 两条获取路径，registry 请求级缓存对老路由失效。
- **[中] 两套"UI 模式"概念名实混淆**：启动级 `ui_mode`(default/new_ui，落 APP_UI_MODE) vs 请求级 `get_ui_mode()`(v1/v2)，两者完全解耦；`app_new_ui.py` 与 `app.py` 唯一差别是一行日志和测试探针。
- **[中] v2 设为默认但仅 7/67 模板有 v2 版本，60 页静默回退**：`render_bridge.py:129-144` 对找不到 v2 的页返回 `base_fallback`。**见 §4：这条很可能是搁置的旧路，不在前端 roadmap 范围**。
- **[低] `web/ui_mode.py` 门面 re-export 19 个私有符号无人消费**；viewmodel `_text` 复制 9 份 + 类名后缀漂移。
- **做得好**：viewmodel 层职责边界干净（零碰 repo/SQL/service）；route 不绕过 service 直连 repo；`g.services` registry 设计本身合理。

### 3.6 文档时效性 — 3/5
**两层断裂，关键不在分数而在"信哪一层"**：
- **可信层**（受门禁约束 / `last_reviewed: 2026-06-01`）：`.codestable/architecture/ARCHITECTURE.md`（抽查 24 个路径全部存在，架构边界断言成立）；`开发文档/系统速查表.md`（受 `tests/check_quickref_vs_routes.py` 门禁强约束，正确列出全部 8+ JSON 端点）；`README.md`。
- **滞后层**（不受门禁约束的 `开发文档/` 自由文本）：
  - **[高]** `开发文档/面板与接口清单.md:29` 称"只有两个 JSON API"，实际 8+（漏掉整个执行反馈+甘特模拟子系统）。
  - **[高]** Frappe Gantt 版本：`系统速查表.md:20/702/703` + `ADR/0004` 三处写"0.6.1"，实际 vendor 文件是 v1.x（有 popup_html/readonly API）。
  - **[中]** `面板与接口清单.md:31` 把 blueprint 前缀标为"来自 app.py"（实际在 `factory.py:444-454`），引用已拆分的 `resource_dispatch.js`。
  - **[中]** `ADR/0009-web-排产异步执行模型` 停在"待决策（占位）"，但 `run/` 已有 40+ 文件成熟编排子系统；时间框架早已跨越，决策从未落档。

### 3.7 质量门禁与测试 — 2/5（唯一警报区）
- **[高] 门禁脚手架自指复杂度失控**：`scripts/*.py + tools/*.py` 实测 23102 行；`grep 'from tools|import tools' core/ web/` = **0 命中**（删掉整个 tools/ 业务系统照常运行）；tests/ 中 **651/2797**（23.3%）`def test_` 在 import tools.* 的文件里（测门禁自己）。
- **[高] run_quality_gate.py 3401 行 / 137 顶层函数 / 仅 3 类**：纯过程式巨石，单函数 `_run_quality_gate_command_plan` 跨 360 行；17 个门禁模块全部 0 docstring。
- **[中] 债务台账是最勤更新的文件**：`开发文档/技术债务治理台账.md` 104KB/2196 行，**60 次提交**（比门禁引擎本身还多）；条目 silent_fallback **100** 条全 open。
- **[中] regression_*.py(440) / test_*.py(116) 双命名 = 两套执行模型**：233 个 regression 带 `main()`（子进程脚本），又被 pytest 收集，双重身份。
- **[中] "1 bug=1 文件"测试线性膨胀 + 脆性快照断言**：281/440(64%) regression 文件 ≤2 个 test；389 处断言匹配 CSS/HTML 快照（改 class 名就红）。
- **[中] 三套 pyright 配置，tests/(594 文件)豁免门禁类型检查**：门禁只跑 gate.json(不含 tests，exclude scripts/tools) + tools.json(白名单 7 个 test 文件)。
- **[低] 永久门禁计划硬编码 git SHA**：`quality_gate_shared.py:804` `--base-ref d4589d77`。
- **做得好**：测试没被静默关闭（仅 1 skip/7 xfail）；门禁有真实价值内核（ruff/pyright/全量收集/必跑回归/架构适应度）；**项目已自我诊断**——`.codestable/refactors/2026-06-01-test-gate-cleanup/` 用 12 个 SubAgent 精读 597 测试产出裁决（KEEP 362/DROP 32/DROP_WITH_TOOL 18/MERGE 105），结论与本审计高度一致，但**尚未执行**。

---

## 4. 关键校准：区分"在途"与"搁置"的半截路

第一轮发现里有大量"迁移做了一半"，但**不是所有半截都是债**。必须区分：

### 4.1 计划内在途（不要当债务去"修复"）
- **前端工作台 roadmap**（`.codestable/roadmap/aps-frontend-workbench/`）：13 条子 feature，**1-7 已 done，8-13 planned**（与"7/13"吻合）。这是**横向功能编排**（把已有页面组织成工作台），不是模板重写。`domains/scheduler/` 的分层、`g.services` registry 都是这条线推进中新建的"好的一半"。
- 含义：web 层"scheduler 走新模式、其他模块走老模式"的分裂，部分是**因为前端线优先改了 scheduler 相关页面**，老模块还没轮到——属正常推进节奏。

### 4.2 真正搁置的旧路（这些才是 SPEC 要清的债）
- **v1/v2 UI 模式覆盖层**（`web_new_test/templates`，7/67 覆盖，60 页静默回退）：roadmap 第 397 行明确"当前首页仍是经典模板，现代界面覆盖层如参与需单独确认"——说明这是一条**比前端 roadmap 更早、已搁置**的路，与在途工作无关。**需用户确认：这条路是继续走、还是正式废弃回收？**
- **顶层 shim 群 + 空 domains 目录**：是 scheduler 域分层完成后没回收的尾巴。
- **两套并行实现**（ScheduleRepository、persist_schedule、backup 双实现）：与前端线无关，是更底层的历史遗留。

---

## 5. 优先级行动候选（待逐条拍板）

> 仅为候选清单。每条的具体函数级方案由第二轮深钻产出。

**P0 — 静默正确性隐患**
1. gantt_tasks / gantt_critical_chain 同名标签函数行为漂移 → 抽单一共享 label 函数。

**P1 — 阻碍重构收尾的结构债**
2. 制定"shim 退役"计划：先把测试旧导入路径批量改到新路径，再删 shim（同时缓解门禁臃肿）。
3. 清理 4 个空占位目录（`scheduler/{gantt,dispatch,calendar,batch}/`）+ 4 个空 `domains/` 子目录。
4. 删除/合并死代码：ScheduleRepository 旧明细查询、persist_schedule 独立分支。
5. 用户决策：v1/v2 UI 模式覆盖层继续走还是废弃回收。

**P2 — 一致性收口**
6. 抽公共 util 落点，消灭 `_text`/op_id helper 的二十余份复制。
7. 统一"最优解三元组"字段命名，删桥接映射函数。
8. `schedule_config_runtime_*` 从 core/models 移到配置服务层。
9. `operation_execution_state_builder.py` 从 data/repositories 移到领域/服务层。

**P3 — 门禁/测试减负（最重，你今天已在做）**
10. 执行已存在未落地的 `2026-06-01-test-gate-cleanup`（DROP 32 + MERGE 105）。
11. run_quality_gate.py（3401 行）按职责拆分。
12. 评估 long_gate_* 自指脚手架（2.3 万行）是否过度。

**P4 — 文档**
13. 修或作废 `开发文档/面板与接口清单.md`（漏整个执行反馈子系统）、Frappe Gantt 版本号（0.6.1→实际 v1.x）两条硬错误。

---

## 6. 第二轮：函数级深钻专题（给后续 Agent 的分工）

第一轮是广度扫描。**治本要靠这一轮**——每个专题派 1 个 Agent，钻到**每个函数**，产出可直接执行的整改清单（哪个函数、改成什么、影响哪些调用方、哪些测试要跟着改）。专题边界互斥，可并行。

### 专题 A：shim 退役全景图
- 入口：所有顶层 shim（scheduler 顶层 schedule_*/config_*、web/routes/scheduler_*、`_scheduler_compat.py`）。
- 钻到：逐个 shim 列出 (转发目标, 转发写法, 生产引用数, 测试引用清单)。产出"先改哪些测试导入、再删哪些 shim"的精确顺序。
- 输出：一张 shim 退役执行表 + 受影响测试文件清单。

### 专题 B：两套并行实现的死代码确权
- 入口：ScheduleRepository vs SchedulePlanQueryRepository、persist_schedule 双入口、backup vs migration_backup。
- 钻到：逐方法确认生产调用方（grep 全仓，排除 tests/），标记"可删/需合并/保留"，给合并后的目标签名。
- 输出：死代码删除清单（含每个方法的调用方证据）+ 合并方案。

### 专题 C：helper 去重与公共 util 落点设计
- 入口：`_text`(24 份)、op_id 解析族(~5 种)、`_positive_int`、`_append_row` 等。
- 钻到：列出每一份的精确位置和细微差异（有的 strip 有的不 strip），设计一个公共 util 模块的 API，确认合并不改变任何现有行为。
- 输出：公共 util 模块设计 + 逐处替换清单（标注行为差异处需人工确认）。

### 专题 D：命名统一（最优解三元组 + 私有/公有约定）
- 入口：4 个 optimizer/candidate/orchestrator dataclass、跨文件 import 的下划线函数。
- 钻到：设计统一字段命名表，列出每个 dataclass 和每个映射函数的改动，确认无字段错配风险。
- 输出：命名统一方案 + 桥接函数删除清单。

### 专题 E：分层归属修正
- 入口：`schedule_config_runtime_*`（在 models）、`operation_execution_state_builder.py`（在 repositories）。
- 钻到：确认这两块的所有调用方和 import，设计搬迁后的目标位置和 import 更新。
- 输出：搬迁方案 + import 影响清单。

### 专题 F：门禁/测试减负的可执行方案
- 入口：`test-gate-cleanup` 已有裁决清单、run_quality_gate.py、long_gate_* 家族、债务台账。
- 钻到：把已有 DROP/MERGE 裁决落成具体删除/合并命令；评估 run_quality_gate.py 按职责拆成哪几个模块；债务台账 100 条 silent_fallback 分类（哪些真该修、哪些可接受）。
- 输出：门禁减负执行方案（与正在进行的 test-gate-cleanup 对齐，不冲突）。

### 专题 G：甘特双路径标签一致性（P0，可独立先做）
- 入口：gantt_tasks.py、gantt_critical_chain.py、gantt_popup.js/gantt_render.js 对应后端。
- 钻到：逐字段对比两套标签函数的行为差异，确认正确行为，设计统一 label 函数。
- 输出：统一方案 + 回归测试要点（确保甘特条与关键链 tooltip 显示一致）。

### 第二轮 Agent 统一输出契约
每个专题 Agent 必须产出：
1. **逐函数清单**：`文件:行号` + 现状 + 目标 + 风险（行为是否会变）。
2. **调用方/测试影响**：哪些生产代码、哪些测试会受影响。
3. **执行顺序**：先做什么后做什么，哪些可并行。
4. **与在途前端 roadmap 的冲突检查**：是否触碰 §4.1 的在途文件。

---

## 7. 变更日志
- 2026-06-01：第一轮地基体检，7 个并行 Agent 广度扫描，建立基准 + 切出第二轮 7 个深钻专题。
