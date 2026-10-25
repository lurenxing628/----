---
doc_type: architecture
slug: service-scheduler
scope: 当前工作台排产计算、事务事实、搜索会话、结果档案与正式采用职责
summary: 工作台拥有受理和持久化，scheduler 只编排计算；事实、固定准备和已解码结果在各自作用域内共享
status: current
created: 2026-06-28
last_reviewed: 2026-10-15
updated: 2026-10-15
tags: [scheduler, core, service, 排产, architecture]
depends_on: []
implements: []
---

# 排产调度模块架构现状

本文以 2026-10-15 当前工作区已落地代码为准。单次准备重构的整合检查、性能材料和平台延期状态由[方案及执行记录](../refactors/2026-10-15-single-pass-workflow/single-pass-workflow-refactor-design.md)统一维护；文末专题段落保留各次交付时的历史口径。

## 1. 入口与职责

工作台的 `core/services/workbench/run/` 拥有排产预检、持久受理、worker、候选保存和正式采用。`core/services/scheduler/run/` 消费准备好的输入，执行算法、校验结果并生成摘要。正式版本在采用事务中分配，计算阶段使用明确的版本上下文。

`core/services/scheduler/__init__.py` 不再装配或再导出服务。实际消费者从各职责文件深路径导入；当前保留以下真实服务职责：

| 服务 | 当前职责 |
|---|---|
| `CalendarService` | 工作日历及资源班次查询 |
| `OperationExecutionFeedbackService` | 现场执行反馈与事件写入 |
| `ScheduleService` | 批次工序查询和内制、外协字段编辑 |

批次主数据位于 `core/services/batch/`。原 `ScheduleService.run_schedule/_run_schedule_impl`、输入 collector 的生产采集链和 `schedule_persistence.py` 已退役；`schedule_input_contracts.py` 保留共同输入合同，输入领域校验、资源事实和实际错误类型仍由当前消费者使用。排产配置通过 `core/models/schedule_config_runtime*` 的共同字段、Snapshot 和解析规则进入计算；旧配置服务装配及页面保存入口已经退出。

## 2. 当前分层

| 位置 | 所有者职责 |
|---|---|
| `workbench/run/` | 预检、输入准备、worker、保存、查询与采用 |
| `scheduler/run/` | 纯计算编排、共同优化、图准备、产出校验 |
| `scheduler/run/optimizer/` | 共享预算、解码会话、结果档案与各阶段的小视图 |
| `scheduler/run/optimizer/graph/` | Profile、Repair、IG 以及父代和真实续排决策 |
| `scheduler/summary/`、`scheduler/contracts/` | 当前摘要组装及公开投影合同 |
| `scheduler/graph/` | 可选工序图分析，按实际功能延迟加载 NetworkX |
| `scheduler/calendar/`、`scheduler/execution/` | 日历与执行事实叶子 |
| `core/algorithms/`、`core/algorithm_runtime/`、`core/algorithm_contracts/` | 算法、动态运行态与中立输入合同 |

主要方向为工作台领域服务 → scheduler 计算 → algorithms/runtime/contracts；算法和事实叶子保持各自职责。具体目录依赖约束继续由现有分层检查维护，本文不沿用旧文件数或历史 SCC 数字描述当前规模。

## 3. 一次排产的数据流

1. 工作台受理在事务内捕获输入、执行事实与当时正式计划，保存持久任务及来源。
2. `WorkbenchRunWorker` 在私有计算副本中创建 `ProductionFactsCapture`；事实复核和 `compute_candidate_run` 共用这一份捕获。
3. `PreflightFacts` 消费已捕获的表、最新安排索引、执行与资源事实，`prepare_candidate_run_input` 生成 `CandidateRunInput`。组合入口在同一只读快照内直接计算；独立 `compute_prepared_candidate_run` 对跨时点输入继续核对当前事实。
4. `orchestrate_schedule_run` 调用 `run_candidate_comparison`，执行一次 `optimize_shared_schedule`；选中结果、校验 payload 和对象摘要沿同一计算链交接。
5. worker 的结果准备构造实际保存文本和读模型；完成事务重新取得当时事实，再保存候选与终态。保存推荐、当前查看和比较基准各有自己的身份。
6. 正式采用由 `candidate_adoption*` 或试调采用入口在写事务中核对来源、当前执行事实、资源约束与版本，并原子写入正式计划和回执。

`ProductionFactsCapture` 的作用域是一份事务快照，`latest_plan_rows` 等派生索引也归它拥有。`PreflightFacts`、`BatchFacts`、`GenerationFacts`、`DecisionSource` 分别复用本次操作已取得的行、永久引用、解码表和共同来源；新请求、新事务或真实写入后的事实由对应入口重新取得。

## 4. 一次搜索的固定准备与结果所有权

- `NativeSchedulePreparation` 归本次搜索所有，准备固定工序、批次、种子、停机、基础资源、图拓扑和断点固定编码。`GreedyScheduler.schedule` 的独立原始输入入口准备一次；共享会话直接调用共同准备后的核心。
- `SharedDecodeSession` 在创建时选定实际解码器及输入适配，请求只表达批序、派工规则、图开关和优先级、资源覆盖或偏好、允许变化的参数。已解析参数连同 warnings、param_fallbacks 直接交解码，缺省起点使用会话起点。
- 静态资格和资源组合共同准备，动态占用、换型、需求退休和排槽仍随搜索运行态实时计算。`RepairParentPreparation` 供 repair 与 IG 共用；内部合法覆盖只复制被修改的工序。
- 图准备和图特征各在实际搜索作用域内生成一次。旧多候选 `core_cache`、缓存 factory、候选侧重复拓扑匹配和缓存专用深拷贝已经删除。
- `SharedScheduleArchive.register_decode` 在真实解码出口取得安排身份，计算一次内容 key 并接管已验证 payload；已登记安排复用 `entry_id`，完成性证据升级仍沿原 revision 处理。
- 未验证 checkpoint trial 只查询已有安排身份；未命中时从同一编号器取得临时编号，随后释放 key，不进入档案、best 或已验证 seen。trial 的实际结果由原 IG 待验证路径短暂持有，正式采用前继续完整验证。
- 内部阶段、请求命中和目标同步使用 `archive.view`，共享档案的 results、metrics 和原摘要；目标 score、请求 warnings 和阶段决策属于各自的小视图。`materialize` 只在最终 `CandidatePlan` 发布出口赋予外部结果独立所有权。
- 报告只比较 `entry_id + objective + 完成性摘要 + metric/score`，保留同安排不同评价的真实差异。旧结果扫描和另一份结果身份投影已经退出。
- 多来源由已有 events 保存；`origins`、`_record_origin` 和报告反向驱动内容登记的旧入口已删除。档案只持选中 `evidence_origin`，事件通过 entry/request/event 编号串联，最终发布时复制选中证据。

`OptimizerRuntime` 保留 scheduler_factory、clock、rng_factory、run_ortools_warmstart 四项实际依赖。共同预算记录真实解码成本、复用、跳过和目标机会。MultiStart、LocalSearch、GRASP/IG 与图 Profile/Repair/IG 继续执行真实算法；普通 SGS、分件 DAG、合法点工序、种子和完整验证各自保留原业务语义。

## 5. 保存结果与真实出口

新运行发布 1—3 份实际业务代表，各目标 winner 可以指向同一永久候选；部分结果按真实完成集合表达。`WorkbenchRunCandidateTasks` 拥有安排正文，`GenerationFacts` 提供共同解码表；`decision-read-v1` 在受理、完成事务和明确迁移中构建，查询直接消费保存投影。旧 balanced/health/权重、复用、失败和跳过记录按其保存版本解释。

摘要对象在计算内交接，持久化文本在实际保存边界生成并直接落库。Web 的 `json_response` 对最终信封编码 UTF-8，并发送同一份字节；大小限制也针对实际产物。内部 `execution_workspace` 的 HTTP 大小预演已删除。归档读取消费保存证据，公式与内容确认由原落档、采用和迁移边界负责。

当前 Schema 为 43：v41/v42 的保存读模型和原生业务目标候选继续保留，v43 只调整实际查询所需索引。`schema_compat.py` 接纳明确的 v39—v43 表示差异，业务行和未声明结构变化继续参与事实比较。普通启动检查结构；新库、升级、恢复等数据进入边界执行完整数据合同。

## 6. 相关入口与历史演进

- [工作台外壳](workbench-shell.md)、[甘特显示模型](ui-gantt.md)记录宿主、token、输出和前端职责。
- [单次准备方案](../refactors/2026-10-15-single-pass-workflow/single-pass-workflow-refactor-design.md)及同目录执行记录维护本轮范围和验收状态。
- 2026-06-28 的 43886 行、219 个文件、79 个根目录文件属于当时普查。2026-07 A1/A3 拆除循环依赖，2026-09-20 将 gantt/resource_dispatch/calendar 分包、batch 迁出、旧 analysis 与转发垫片退役；上述规模和引用计数保留为历史事实。
- 2026-09 的多候选外层预算、原生内容认证、图缓存与旧 `ScheduleService` 运行链属于本轮重构前结构，已由当前单会话与工作台拥有者接替。历史验收材料保留各自源码和环境范围。

## 历史专题记录（2026-10-13—2026-10-14）

以下保留这些专题交付时的业务口径和证据入口；当前接线、Schema、固定准备与结果所有权以本文前五节为准。

### 2026-10-13 同次候选决策入口

- `schedule_candidate_selection.py` 保存选择规则版本、实际 balanced 容差与所选分数；`WorkbenchRunResultRepository.prepare_run_result` 在分配永久候选引用后，将推荐、原始分数最佳候选和算法健康基准一次映射到运行收据。同次查看基准由查询选择，两组身份分别负责计算解释与当前差值。
- `core/services/workbench/run/decision.py` 在一个 SQLite 只读快照中读取运行、候选全集、归档和任务；`GenerationFacts` 共同解析 JSON、Schema 与永久身份。查询消费归档事实，当前业务资料修改由正式采用预检处理。
- `decision_metrics.py` 统一总览指标目录及覆盖/差值入口。应排、搜索与全链交付分别核对，待料暂缓单列。资源指标使用第 3 阶段共同班表口径；保存算法统计保留独立来源与范围。
- `decision_selection.py` 从保存收据给出固定选择依据，旧收据用原候选键映射为永久引用。`decision_export.py` 将同一查询结果与目录写为 CSV/XLSX；总览快照直接保存范围和身份字段。
- 实施与实际验证记录：`../features/2026-10-13-decision-comparison-loop/`。本节只更新相关链路，前文历史规模和算法治理记录保留各自时间口径。

### 2026-10-13 共同交付投影与决策影响

- `plan/delivery_projection.py` 为共同批次投影、汇总与成对差值入口。搜索覆盖、可排工序覆盖与全链交付独立；合法待料后道为 `deferred`，普通漏排为 `incomplete`，缺事实为 `unknown`。`due_state` 区分合法交期、`9999-12-31` 未指定和缺失/非法交期。完整且合法交期才有已知拖期；全未指定为 `not_applicable`，拖期为 null。已知小计与未知覆盖同时返回，保留微秒时间精度。
- `due_eligible_count`、`excluded_due_count`、`invalid_due_count` 分别计指定、未指定和无效交期，合计全部批次；`due_evaluation_count` 为指定加无效，等于已知加未知数量。工艺完成状态与交期风险分别表达。候选、正式计划、值班台、试调、候选分析及导出均提供自己的保存事实并消费共同规则；算法保存的原分数与采用事务保持原职责。
- `DecisionSource` 在一个只读 SQLite 快照中持有归档、候选及任务。正式基准由 `facts/decision_baseline.py` 从受理归档选择每道工序在受理版本及以前的最后正式安排，保留多段任务与来源绑定。`decision_baseline_source.py` 只解析归档绑定的不可变候选/试调来源，恢复零工时实际工作、合法待料和原资源身份；缺项按具体来源表达。当前 Schedule、设备、人员和工艺修改不参与冻结比较。原受理归档保持原样，显式历史版本 API 继续使用其指定版本范围。
- `candidate_comparison.py` 与 `candidate_analysis.py` 的当前正式比较使用同一共同基准；缺正式基准时其完成性和差值保持未知。`decision_reference.py` 按本次选批和工序限制正式比较范围，双方实际工作集合一致时才比较跨度/切换；交付收益另按共同完成批次计算，并单列全范围未知覆盖。
- `decision_impact.py` 投影逐批和逐工序变化、资源变化、保存工艺的标准工时依据与甘特钻取身份；`decision_queries.py` 共用筛选、稳定排序和 20/50 分页。明细快照绑定共同范围、基准和筛选，翻页不改变快照。`decision_workspace.py` 提供正式基准只读甘特；`decision_export.py` 复用同一投影输出总览、批次、工序和完整比较。当前指标目录版本为 `decision-preparation-v4`。
- 第 2 阶段实施、真实边界运行、浏览器与导出证据见 `../features/2026-10-13-decision-delivery-impact/`。主对话独立验收已通过；实际准备需求分解见下面第4阶段共同需求入口。

### 2026-10-13 共同资源投影与资源影响

- `facts/archived_calendar.py` 将保存的全局日历、停机、个人日历、轮班、资源状态、Schema 版本和永久身份适配为逐自然日容量，复用领域日历规则。运行与试调保存全表，默认规则和例外均从自己的保存事实解释；当前资料不回填历史。未知日独立保留，休息、禁排或停机扣尽为真实 0；夜班包含前日尾段。
- `resource_intervals.py` 按永久资源和工序建立索引；`resource_projection.py` 复用 `ResourceUtilizationMetrics` 计算班表内区间并集占用、独立工序合并后的累计需求、班外占用、重叠、日峰及冲突身份。点事件无资源占用。`resource_summary.py` 按固定资源集合汇总，容量加权占用率和 CV 纳入正容量空闲 0；均值为零时 CV 不适用。缺安排与已知空安排区分，独立容量事实保留。
- `DecisionSource` 的 `resource_view=selected_batches|full_candidate` 决定本次选批贡献或候选完整安排；共同资源集合为同次全部候选与基准所涉永久资源并集。窗口为工厂本地左闭右开，默认起日00:00至截止日次日00:00，所有候选共享。正式工序覆盖由 `official_scope_coverage.py` 与采用预检共用；候选缺少的正式安排、普通未排和合法待料分别展示。
- `decision_resources.py` 一次构建各候选和基准索引、完整整窗汇总，资源表／热力图／单资源逐日按显示范围生成。资源行支持20/50分页，热力图支持7/14/31天；40k资源日作为分块计算预算，整窗保留全部事实。快照绑定视角、窗口、固定集合和业务筛选，显示页码不改变事实身份。
- `decision_resource_export.py` 与比较屏幕复用同一资源服务，输出资源及逐日 CSV/XLSX。全比较增加资源影响表，逐日入口可追加单资源逐日表；资源行覆盖使用原生数量，XLSX“覆盖工序”逐侧／分类／工序保存完整永久身份，避免Excel单格长度造成截断。逐日冲突数量为原生整数，“资源冲突”按区间和实际成员保留工序、行及批次身份。数字保持原生类型、null为空，百分数按单位转换。既有候选、值班台和试调同义资源读者使用共同规则；`facts/current_resource_calendar.py` 只适配已读的本事务日历、Schema和身份，明确 `current_transaction_snapshot` 来源。保存候选／试调使用 `archived_resource_calendar` 来源。
- 本阶段设计、实施验收及原始验证入口见 `../features/2026-10-13-decision-resource-impact/`，主对话独立验收状态分别记录。

### 2026-10-13 共同工序需求与工种切换

- `algorithm_runtime/operation_effort.py` 的 `internal_requirement_parts` 是实际排槽及需求账的共同标准公式；`OperationEffort` 保存准备、加工、总需求、实际量依据、准备状态与种子角色。`piece_input.operation_batch` 决定分件自身量或共同批量，外协周期／合并组独立于内制标准小时。
- `scheduler/run/operation_effort.py` 在真实执行保护、冻结与种子分离后构造需求账。新排使用真正排槽量，保留种子从其最后正式采用来源读取原分解；原需求目标保持原值，本次AJ目标及剩余量独立记录。执行中、完成和旧档缺项各有状态，现行安排和执行保护继续生效。
- `run/input_effort.py` 验证原需求与永久工序对应；`WorkbenchRunResultRepository` 在完成事务中一次保存带永久引用的收据需求账，所有同次候选根据自身实际安排判定归属。试调新排槽也保存共同分解，原样／执行／完成安排保留来源；正式比较按每道工序最后采用的不可变候选或试调读取。
- `facts/operation_effort_evidence.py`、`preparation_projection.py` 区分保存runtime与归档工序标准。`DecisionPreparation` 的待执行、新排、普通未排和合法暂缓汇总覆盖整次受理，保留／执行／完成另列；新排范围不同的差值保持中性，缺小时返回缺项和已知小计。查询、工序／甘特详情和导出消费相同账。
- `algorithm_contracts/changeover_events.py` 按真实工种ID生成事件及计数；首道、同工种和零时点为0，缺身份保留缺项，重叠附冲突。设备完整序列先建立前驱，再按后序开始落入左闭右开窗口筛选。新排结果、执行／冻结种子和原生插入惩罚透传同一工种ID；原算法保存计数单列来源。
- `DecisionChangeovers` 提供双方保存事件、永久工序／安排行引用及甘特钻取。目录为 `decision-preparation-v4`，新增8项准备／加工和2项实际切换指标；资源共同计量继续使用 `available_occupancy_v1`。第4阶段证据和独立验收状态见 `../features/2026-10-13-decision-preparation-events/`。

### 2026-10-13 选择解释与推荐取舍

- 原选择器和健康计分处分别保存 `candidate-selection-evidence-v1`、`candidate-health-evidence-v1`。实际目标完整score、目标／全score并列、baseline／sequence裁决、balanced四项实际检查及真正覆盖标记、健康原数和原阈值在原完成事务中映射为永久候选引用。选择规则版本保持 `candidate-selection-v1`，原求解和健康结果沿用。
- `facts/completion_scope.py` 统一精确完成、普通未完整、合法暂缓和未知批次集合，分别保留实际剩余工序、原runtime需求／归档标准／本次AJ目标。`facts/common_completed_delivery.py` 是共同完成批次交集的交付差值入口，复用原交付算术；整次受理未知摘要继续保留。
- `DecisionCompletion` 在请求内缓存归档交付、完成集合与剩余需求，候选按 exact 完成批次集合分组。概览返回数量、最多3个样例支撑及完整明细入口，完整身份和工序需求用于同一请求的分行导出。
- `decision_completion_queries` 按独立候选anchor读取完整受理批次并分页筛选完成／未完整／普通缺排／待料／未知；当前查看和基准继续保留原scope。每批剩余需求复用同一共同事实，准备明细及导出以 `work_scope=remaining` 筛选真实未安排工序，组内各候选保留独立剩余需求。
- `decision_selection_explanation.py` 解释保存的实际规则和缺项；`decision_tradeoffs.py` 从共同目录、差值生成稳定业务文案及3+3主要条目。推荐使用固定候选，当前比较使用用户基准，当前查看身份单列；部分交付收益标注 `common_completed_batches`，减少未安排需求保持中性。
- 推荐读模型使用 `decision-recommendation-v1`，共同52项指标目录仍为 `decision-preparation-v4`。既有v1推荐字段保持兼容，新解释和当前取舍各有独立字段；页面、旧实际比较入口和CSV/XLSX复用同源投影。推荐、完成性和当前采用预检分层，采用继续走原preview及事务内复验。
- 本阶段实施、浏览器、原始导出与独立验收状态在 `../features/2026-10-13-decision-recommendation/`；本节交接时第5阶段已通过独立复验，第6阶段已派发，第7—8阶段等待派发。

### 2026-10-13 候选优化过程

- `optimizer/process_evidence.py` 接入共同 `OptimizationSearchReportState` 的实际评估、接受、拒绝与阶段入口；评估、接受、当前解接受、严格改善、未核验试验、解码调用各有真实口径。原 `search_report` 语义延续，新严格改善按同完成子集的完整评分判断，旧含同分的最好解更新独立表达。
- 完成后按真实总耗时等宽分桶保留桶末当前最好结果，并固定保留首次有效、首次应排完整和最终结果；重合标记合并，每候选最多200点。运行期只保留有效变化的小事件，最终采样同时记录原事件数、保留数、桶宽及首尾覆盖；原代表尝试排名与12条保留规则延续。
- `Outcome`、`CandidatePlan` 将 `optimization-process-v1` 随原artifact完成事务保存，repository把复用来源映射到永久候选引用。未开始的搜索投入为已知0；失败或已开始预算中断的过程计数保持未知，`budget_skipped` 与 `not_started` 分别表达。
- `facts/candidate_process.py` 纯读保存的过程、真实公开profile、评分、阶段、完成性和代表尝试。复用自身投入与来源求解分开；旧档按实际保存离散点读取，缺完整首末、时点和接受情况保留null。过程读取沿 `decision_process.py` 的独立 `process_candidate_ref`，共享scope/snapshot、20/50分页与稳定排序，资源查看窗保持比较上下文。
- 每点与代表尝试保留实际 `objective_scope`，完成性描述对应算法评价范围；完整批次子集的已知0保留，显式未知目标的主值和目标评分分量为null，首项失败工序数保持原位置。保存最终统计保持原算法口径。
- 2026-10-14 母验收返修：已核验且完成性已知的保存点增加`evaluation_scope.incomplete_batch_ids`，独立于搜索阶段、访问次数及计数；完整集合保存`[]`；旧`all_batches`且未排齐批次数为0的事实同样确定空集合，部分覆盖缺身份时公开为`null`。共同投影和CSV/XLSX进步事件沿同一保存字段读取，前端以真实集合判定连续性。
- 代表尝试在真实接受结果确定后保存来源、profile、累计耗时、对应评价序号、接受和严格改善。`attempt_decision_evidence` 冻结当时比较对象的目标、评价范围、评分与业务指标，只有同一评价范围且资料齐全时提供差值；原12条保留排名继续承担代表选择，行间名次不承担时间先后。首次无比较对象、未核验试解、不同范围和旧缺项各自保留真实状态。GraphReady生成、修复、IG及原多起点／局部搜索共用该保存职责。
- 过程读模型 `decision-process-v1` 与共同52项目录版本独立。GET、页面和四grain导出消费同一投影，当前页只限制屏幕；完整导出保留全部过程成员，普通16表、逐日18表。设计与验收材料见 `../features/2026-10-13-decision-optimization-process/`。

### 2026-10-14 整页决策工作台共同投影

- `decision_source.operation_change` 作为真实工序差异共同入口；批次完工相同仍可有工序变化，缺料／未安排状态及缺项沿原归档读取。`decision_queries` 的 `delivery_filter` 与 `selected_batch_ref` 支持当前风险筛选和过滤外选中项；`difference_summary` 复用三个完整受理范围指标的既有差值及覆盖判据。
- 资源 `decision-resource-v4` 在同一保存班表与区间上按小时、真实可排班段、天、周汇总；周比例为占用合计除容量合计，单列日峰及高负荷时段。小时筛选窗口由当前实际桶范围确定并随公开 filters 传给导出，完整比较窗保持原 scope。零容量判断区分已知休息、班表缺项和未保存实际工作片段；保留跨度跨休息不生成实际加工证据。
- 正式资源投影的 `available_overlap_hours`、`has_overlap` 和 `conflict_segments` 为归档可排窗口内不同永久工序的重叠；自然跨度与原 `segments` 留作安排详情。三道工序同时重叠一小时仍是一小时冲突区间，重复计时继续使用其独立指标。
- `decision_process` 的完整 `attempts` 与分页 items、CSV／XLSX 共用同一保存尝试投影，求解记录、计数、采样和优化器行为保持原职责。Job `scope_summary` 读取不可变接收归档中的业务批次、工序数及保存目标；终态失败原因复用历史共同投影。新增写入保留真实时钟微秒，既有保存时间原样读取。

### 2026-10-14 历史事件、保存来源与同条件指标

- `core/models/workbench_decision_history.py` 统一`decision-history-v1`的查询、条目身份和快照范围。`web/routes/workbench/decision_history.py`注册历史读取与CSV/XLSX导出两个GET入口，沿已有只读预算、响应及快照绑定协议；历史页和文件各消费同一服务。
- `history/export.py`的文件格式2独立于历史查询版本：CSV/XLSX共用指标值、范围引用、指标覆盖引用三类长表行，引用按条目编号、指标键和字段关联，逐成员保留原顺序、集合数量及null/空数组差异。主分区记录数随共同生成器实际消费累计，含引用和占位行；XLSX说明附表不计入响应记录数。单元格字符与工作表行数校验保持原职责，导出不再把整组永久编号合并成任意长文本格。
- `history/catalog.py:read_history_catalog`只组织四类事件：运行、候选正式采用、试调正式采用、旧正式版本。运行以保存推荐为默认结果，缺推荐保留缺项；采用以真实回执和采用来源为准。同run多次采用分别保留事件，运行仍计一次；已有现代采用回执覆盖的旧版本只保留采用事件，原历史行和出处继续存在。发生时间保留原工厂本地、UTC回执和旧保存时间的各自依据。展示序号按完整未筛选运行目录的发生时间及永久引用确定；查询、分页、选择和导出共同读取此标签，永久事件身份继续沿原引用。
- `history/reading.py:HistoryReader`在调用方的只读快照内恢复并核对原run／candidate／scenario，按来源缓存归档、候选和决策投影；多个采用事件共用恢复结果，事件身份和结果身份独立。`history/conditions_source.py:ConditionSource`将运行接收归档、试调原草稿／保存场景、旧摘要适配为带保存位置的事实，保留真实空集合及缺表／列／来源的差异。
- `history/conditions.py:compare_history_conditions`按永久实体和实际字段比较八类事实：排产范围、批次交期与数量、工序标准需求、物料与外协、有效日历与停机、资源与人员资格、报工与正式原安排、不重排窗口与成员。结果为相同、变化或未知，双方保留是否保存、原值、具体出处；归档保存时间和编号标明出处，目录统计计数独立显示，真实成员及生产字段（含实际报工时段）承担一致性判断。算法参数独立为实验维度，优化目标另行判断；旧缺项、已知0、False、合法null和明确空集合保持各自含义。
- `history/metrics.py:project_history_metrics`复用共同交付、资源、需求、切换及决策投影，算法保存统计和旧摘要保留自己的版本、范围与来源。资源缺省窗口由`history/metric_window.py:history_window`从保存来源的排产起点起固定7天，可统一调整窗口天数或指定所有来源共用的绝对窗口；缺起点或起点读不出为窗口未知。实际起止、资源成员、占用分子和容量分母随条目返回。`history/metric_gate.py:gate_history_metric`依次核对生产条件、目标、指标充分性、单位／版本、范围、真实覆盖成员和资源窗／容量分母，成立时才提供同条件改善。
- `history/queries.py`统一排序、20／50分页、过滤外选中条目及明确基准。`projection.py`生成当前页走势、范围变化标记、连接判断与成对结论；未知或口径不一致保留断点和观测原数。查询及导出共享请求内来源缓存与条件对照，分页不另建事实来源。`export.py:read_history_export/write_history_export`读取筛选全集与完整成对字段，CSV输出一个分区，XLSX追加指标口径、比较范围和数据缺项；批次总量同时保留数值、已知小计、真实覆盖成员、单位、版本和保存出处，数量缺项进入同一缺项表；原数、空值、类型和出处随文件保留。
- 设计依据：[历史走势与同条件对照](../features/2026-10-14-decision-history-trends/decision-history-trends-design.md)。本节记录新增只读职责，求解、接收、保存归档、试调及正式采用继续沿原事务入口。
