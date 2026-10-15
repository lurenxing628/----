---
doc_type: refactor-design
refactor: 2026-10-15-single-pass-workflow
status: approved
created: 2026-10-15
baseline: 8096bdbbf3c04ef17ec24fa2cd19bfc71fa678b8
scope: APS 搜索解码、事务事实、工作台读写、token、输出编码、显示模型和启动维护的重复工作收敛
summary: 退役旧入口，以现有操作、会话和来源对象拥有一次准备结果，下游直接消费；完整覆盖72项审计及复核新增发现
implementation_status: complete
validation_status: platform_deferred
reviewed: 2026-10-15
review_status: independent_review_revisions_incorporated
---

# 一次准备，直接消费：重复工作与结构收敛方案

## 1. 结论与选择

推荐按七条共同路径完成结构调整，最后集中验收。目标是减少系统必须理解的入口、事实副本和处理阶段。72 个审计编号用来追踪覆盖，不作为 72 个独立补丁实施。

1. **退役旧生产入口和无消费者产物。** 当前工作台只保留一条输入准备、计算、保存路径。仍有效的函数、工具和历史读取迁到实际职责，随后删除旧服务装配和旁路。
2. **一次操作拥有一份事实。** 沿用 ProductionFactsCapture、PreflightFacts、CandidateRunInput、BatchFacts、DecisionSource；同一事务已读事实和已算索引直接传下去。
3. **一次搜索拥有固定准备，候选只表达变化。** 沿用 NativeSchedulePreparation、SharedDecodeSession、RepairParentPreparation、SharedScheduleArchive；去掉反复传入固定数据再检查是否相同的接口。
4. **token 保存内存绑定值。** 原登记表直接持有绑定对象及共享事实值，删除 binding 的 JSON 编码/解析。逐行 token 持对象引用，不建立第二个快照登记表。
5. **领域规则只做一次，写入与输出消费结果。** 日历、资源、工艺、报工使用共同规范化和写入实现；持久化文本、响应字节各在真实出口产生一次并直接使用。
6. **界面分为准备、布局、绘制。** 数据变化才重新准备，搜索筛选并更新可见成员的轻量汇总，宽度只改变几何，滚动只处理可见区。退出旧的一次性布局入口。
7. **启动、维护和 SQL 各自归口。** 启动 journal 捕获一次，普通请求只检查内存运行状态及开库前一次维护窗；SQL 消费已解析区间或一次区间判定，索引只服务实际保留的查询。

这比三种替代路线更直接：

| 路线 | 结果 | 本方案取舍 |
|---|---|---|
| 在各下游增加缓存、校验开关和特殊分支 | 仍保留多条准备路径，调用者还要决定是否可信、何时失效 | 由真实拥有者交接结果，删除下游重复入口 |
| 新建通用 Prepared/UnitOfWork/快照证书层 | 引入一套跨领域协议，现有职责仍在其下重复 | 扩展已有对象的实际职责，使用领域模型、具名参数和普通不可变值 |
| 每次重算内容证明共享数据没变 | 保留重复遍历，又产生更多证明字段 | 接口只允许候选表达变化，固定输入由创建会话的一方拥有 |

用户已授权在独立实施对话完成 P1–P8，代码、调用方、测试接线和当前架构说明已同步。第 2–9 节保留方案批准时的问题与目标，并纳入后续批准的职责调整；实际实现及验证结果见同目录 single-pass-workflow-apply-notes.md。首轮全量的 841 通过，以及后续 899 项的 860 通过/3 失败、902 项的 866 通过，均保留为相应源码状态的历史结果。

后续 IAB 发现的完整来源/展示范围冲突、微秒投影、日志 UTC/本地时间及 Dashboard 图准备和设备事实重复读取均已完成共同职责修复。三个工作区在既有 useMemo 内各建一次图，三个 model 只准备显示事实；Actual 关键链与完整路线直接消费该索引，后端同一 capture 的设备事实直接交给计划读取。20k 范围恢复、范围外点事件、保留资源、独立文件和维护闭环、stage 前序放行、非空不重排时段、公共日历恢复默认、空白模板下载及维护结果双编号手填查询均已完成真实 IAB 验收。资源压力卡按现有设计进入交期风险下的共同影响分析，完整时间线、资源表、首尾定位、缩放及停机分析均已回验；原失败证据保留，具体修法和原始证据见[实施记录末节](single-pass-workflow-apply-notes.md)。

最终冻结状态的完整门禁收集 **903 项：867 通过、0 失败、36 跳过、0 收集错误**；第 1–16 步全部通过。第 17 步因 15 个必需 Windows/PowerShell 启动器节点在当前平台 setup 跳过而失败，正式 manifest 保持 `failed`，平台验收延期。实施已完成，验证状态为 `platform_deferred`；该次 dirty 工作区诊断运行前后内容相等、`tracked_drift_detected=false`，执行时 HEAD 为基线，未形成 clean-worktree proof。本轮按后续明确授权形成本地提交；用户原 README 增补 10 行、删除 0 行保留在工作区，推送暂缓。

最终 IAB 原 171 条功能/风险索引为 **124 项选定实测、13 项共同入口复用、34 项风险未选**；另 5 个独立文件入口和 2 份空白模板下载实测完成，独立 UI 待验为 0，6 个确认产品问题均已修复回验关闭。257 个实际产物（192 截图、31 下载、34 只读支持）全部关联，未选组合保留原分类。原始分类和证据入口为 `output/iab/single-pass-20261015/coverage.json` 与 `coverage.md`。

## 2. 依据、现状和一次性的含义

基线为上述已推送提交。来源是[原审计](../../audits/2026-10-15-redundant-work-scan/index.md)、当前代码、两轮已完成复核，以及本轮四个不继承对话上下文的独立设计代理。方案写完后，另启四个不继承对话上下文的代理审查架构、token/输出、前端/基础设施和全量覆盖；修订见第 12 节。原审计保留历史原文，实施范围以本文为准。

已经完成的主体包括 A11、B10、C15；B7 的单次建图已经完成，但旧多候选缓存仍保存无用途副本，本轮直接删除。B2/B5/B9/B13/C4/C13/C14/C24/G3/G4 的部分路径也已完成。具体剩余范围见第 11 节。已有 791 通过、0 失败及真实页面/性能材料用于基线，不能当作未来改动后的通过结果。Windows/Win7 现场项沿用既有延期安排。

**一次不是整个进程只做一次，而是同一份事实、同一个职责作用域只做一次。**

| 作用域 | 现有拥有者 | 交给下游的内容 | 下一次重新取得事实的时机 |
|---|---|---|---|
| 一次数据库读快照或写命令准备 | ProductionFactsCapture / PreflightFacts / BatchFacts | 所需原始行、业务投影、关联索引、执行事实、配置 | 新请求、新事务，或本次操作真正写入相关事实后 |
| 一次排产搜索 | NativeSchedulePreparation / SharedDecodeSession | 固定工序、批次、种子、资源基础、拓扑、日历及按需断点固定部分 | 新搜索 |
| 一个搜索父代 | RepairParentPreparation | 父代继承资源、顺序、邻域和结果索引 | 真正切换父代 |
| 一次候选请求 | 会话现有请求/解码结果 | 已解析参数、最终优先级、批序、资源变化、warnings/计数 | 候选决策变化 |
| 一个保存来源的本次读取 | GenerationFacts / DecisionSource / PlanReadContext / ledger 读上下文 | 解码表、成员、任务、已解析区间、真实正式计划身份 | 换来源或结束本次读取 |
| 一次领域变更 | 现有领域服务及命令 guard | 规范化模型、已检查的变更及所需当前行 | 下一个命令，或确认时发现预览事实已经变化 |
| 一份输出 | 现有仓储 codec / web 响应构造 | 实际落库文本或实际发送字节 | 输出内容变化 |
| 一份界面数据 | 现有工作区/model | 时间、名称、索引、marks、冲突及搜索文本 | 收到新数据或改变真正影响准备的显示模式 |

预检到受理、采用预览到确认、worker 计算副本到最终写事务、导入预览到确认，比较的是不同时间的事实；这些入口继续各自取得当时事实。它们内部再调用多个函数时，全部共享本次已经取得的结果。

同一命令的锁外/锁内回执查找处理重发竞争；数据库触发器新生成的引用需要真实取得。保留这些具体用途，删除“读回来证明刚才写对了”“重建一次证明刚才规范化稳定”等自证动作。

## 3. P1：先退出旧入口，让公共编排器只计算

### 3.1 旧排产与配置装配

当前工作台在 core/services/workbench/run/compute.py 的唯一生产调用使用 simulate=True、allocate_version=False、persist_schedule_fn=None。它已经拥有输入与保存，旧 ScheduleService.run_schedule 又保留一整套采集/版本/保存分支。

实施顺序：

1. 把仍由 CandidateRunInput 继承的 ScheduleRunInput 移入现有输入契约位置；调用方直接引用该 DTO。
2. schedule_orchestrator 直接导入现有 schedule_payload_contract 和真正使用的计算函数，解除经 schedule_persistence 重导出的依赖。
3. 工作台调用方使用现有 ScheduleRepositoryBundle、当前 capture 和所需纯函数，退出仅为取得这些成员而实例化 ScheduleService 的路径。
4. 将公共 orchestrator 收成纯候选计算：输入准备结果，输出选中 payload、候选和摘要对象。版本分配及正式保存继续由工作台现有采用事务负责。
5. 删除旧 run_schedule/_run_schedule_impl、旧 collector 采集部分、旧 persistence 写入链、simulate/allocate_version/persist 回调分支。独立 GreedyScheduler 原始输入 API 保留，进入 P3 的共同解码核心。
6. 删除 result_summary_json 字段和为旧保存链生成它的序列化；当前 result_summary_obj 及真正被展示/持久化的摘要继续保留。摘要规范化在入口一次完成，内部辅助函数直接使用。

配置同样按真实消费拆开：启动仅使用注册字段默认值和当前来源状态初始化；排产继续 build_schedule_config_snapshot；日历只取得本次所需假期效率；错误提示直接用字段说明函数。迁完后删除 ConfigService 的旧页面保存、预设编辑、validator/write 子服务装配。已有旧配置和历史预设数据保持可读，不为删除 Python 服务额外改表。

有效工具 tools/wufenchang_demo/builder.py 的配置步骤迁为使用现有字段规范和仓储一次写入 ScheduleConfig。SystemConfig 中的工作台偏好是另一种事实，不拿它替代。旧 networkx phase0 基线采集 PoC 随旧执行链退出，历史 evidence 原件保留；有效业务测试迁到当前工作台或共同计算入口。

### 3.2 旧甘特、报表和独立死代码

| 退出对象 | 先完成的迁移/保留内容 |
|---|---|
| resource_dispatch 旧服务目录 | 62 天报表规则归 report/date_range_limits；移除旧懒导出及仅验证旧入口的测试 |
| 旧 GanttService 与 desktop/gantt PoC | 桌面 PoC 一并退役；保留工作台实际使用的 critical_chain、task_labels；旧书签范围解析归现有计划模块 |
| 旧 ExecutionReviewMixin、ScheduleDelayDiagnosisService 包装、无人调用的 ReportEngine 导出方法 | 当前报表事实、利用率/停机计算和独立 XLSX exporter 继续使用；直接消费上游已解析计划 |
| preview_import_links/apply_import_links、人员日历专用 Excel validator、excel_audit | 删除专用辅助；保留活跃人机增改方法和批次 Excel validator |
| locked_seed_range、图 payload 中随后被覆盖的 algo_stats、ProcessOpTypeCreate 无人消费的 list 回读 | 直接删字段/调用，使用已有 seed_result_count、decoded.algo_stats 和必要 detail |

input_admitted 保留：当前 preview/accept 实际使用它阻止同一检查结果重复受理。历史候选、正式计划、试调和归档读取继续服务已有数据；旧 URL 跳转沿现有 legacy_page_contract 保留。退役不增加兼容 facade 或另一套 wrapper。

**退出信号：**当前工具和产品调用方全部迁完；旧入口和装配实际删除；编排器只计算，保存只有现有工作台事务路径。函数移到新职责后同步导入、构建顺序、测试登记和现有说明。

## 4. P2：一次事务捕获，全部消费者使用同一事实

### 4.1 排产、采用和 worker

沿现有链收拢：ProductionFactsCapture → PreflightFacts → CandidateRunInput。捕获对象由入口创建，事实比较函数只比较它和原归档，内部 prepare 必须消费它。

- 采用的 check_admission_current 当前捕获后丢弃，后续 prepare 重取；改成由采用入口持有 capture，当前事实比较、输入准备和候选约束复核都使用它。
- worker 的计算快照中，_check_facts 与 compute_candidate_run 共用一次 capture。最终 _persist 在正式库写事务中仍取得自己的当前事实一次。
- 受理链已有 PreparedPreflight 复用，保持现状，删除已经没有真实调用需求的重复准备分支。
- 一次派生 latest 计划行、执行投影、预约、配置、停机、技能、人机授权和外协上下文，放进现有准备对象。latest 投影保留同工序同版本重复行的原拒绝语义。
- validate_execution_guard_before_persist 的纯约束部分只消费当前 prepared；跨事务的旧包装随 P1 退出。不给函数增加 facts_current/skip_validation 之类豁免开关。
- 完工下游按批次和合并外协组建立一次索引。外协组来自 prepared.algo_ops 的真实扩展字段；原 BatchOperation 不含这些字段，不直接在原模型上猜组身份。
- 停机、资格、授权直接使用 capture 中已有行。资格按实际消费人员/工种准备，保留人机授权、固定资源、历史报工沿用原实际资源的语义；不提前校验无关人员。
- 候选共同输入只解析一次 operation source；选中 payload 已有复用，继续使用。

### 4.2 批次、报工、工艺与来源读取

- BatchFacts 的四张计划表改为按 op_id 的引用计数，group_protected 与 plan_reference_count 使用同一结果；旧事件/PlanSourceRefs 只在旧执行账本分支取。避免无关新排产使整本批次指纹变化。
- ledger 本次读取持有正式计划身份、任务映射及已读依赖。报工准备收齐本批实际需要的上游/下游/同组工序，一次分块加载；preview 和直接 command guard 都进入同一准备作用域。
- GenerationFacts 已解码表供 AdmissionBaseline、日历、采用来源共同消费，删除同表反复恢复。当前 DDL columns/LRU 与 CandidateStore 正文累计上限成果保留。
- 试调来源 resolver 按 scenario_ref 持有一次已保存场景及来源准备，metadata、点事件与 read_adoption_operation_facts 直接消费它。移除 _operation_metadata 独立解析 facts_text、下游再次 load_saved_scenario/GenerationFacts 的路径。有原 run capture 时，原资源资料与建草稿时的 assigned_resources 分别保留；没有 capture 时，同一 admission facts 共用一份 _TrialResourceFacts。
- AdmissionBaseline 的读取保留必需表/列、工序引用集合与唯一性、任务归属这些实际解码和关联规则；将 project_execution 的历史公式重演、disposition 的重复全文比对归落档/采用边界。构造器只建立实际消费索引，不再重演历史计算；RunBaselineAPI 的 source_verification 同步表达保存边界事实。
- DecisionSource 继续使用保存的 summary/memberships/arrangements；C14 剩余的 operations_by_batch、批次反查及 admission 集合在落档 builder 的 facts 上一次派生，两个 delivery 公式直接用。
- 工艺路线的 facts/detail/choices/parser 与实际变更由同次准备持有。预览只是变更的展示；确认在写锁内准备当前变更并执行，不再调用整页 preview 后丢结果。批次 sync 退出完整 BatchProjection 和空 warnings 的展示依赖。
- 批次资格统一消费已有技能、人机授权和供应商能力。供应商能力同时包含 Suppliers.op_type_id 与 WorkbenchSupplierOpTypes；保留 legacy 工作流原放行语义。
- 报表使用上游已解析的真实 plan resolution，资源映射全集一次生成再取子集；CSV 静态 scope/来源/说明移出逐行循环。
- 现有 SchemaContractMemo/SchemaStructure 由本次连接/读作用域共享，不在各仓储重新全扫 sqlite_master。各业务自己的拒绝/降级判断继续消费同一结构事实。
- CalendarEngine 每日期生成一次公共 policy，人员层只叠加个人日历/班表；保留个人优先级和原错误归属。

**退出信号：**同一操作中的实际事实只捕获一次；已拥有的原行、身份、解析结果和索引不再从下游数据库补取。所有受影响调用者迁到这些已有对象，没有平行“轻量 facts”体系。

### 4.3 IAB 回验后的计划读取边界

2026-10-15，合法 20k 候选已真实采用为正式计划，原整源 10000 条资格检查却使目录不可选、Plan/Actual 缩窗仍被拒绝。原对话批准把完整来源、展示范围和真实输出的职责收拢如下；这是本轮明确的读取合同调整。

- PlanReadContext 按永久来源持有一次完整 raw 安排行；detail 从这份安排行补齐所需工序、批次、供应商及资源名称，关联键去重后分块读取，退出第二次安排查询。同一上下文继续持有已解析区间、任务身份和按需投影，下一请求重新取得当时事实。
- catalog、selected、baseline、delivery 和 calendar 退出对完整安排源的 10000 条资格、SQL 截断及其旁路，目录自身分页保留。采用基线与交付统计消费完整来源，任务与采用链身份校验保留；`context=None` 的独立采用/历史入口仍直接读取一次所需事实。
- 公开 Plan workspace 先应用用户时间范围，再检查本次返回安排最多 10000 条。完整来源超过该值仍可列入目录并选择；范围内任务符合条数后，最终信封继续受原出口字节限制。相关实现为 `plan/read_context.py`、`plan/point_query.py`、`plan/queries.py` 及三个 `workbench_plan_*_repo.py`。
- Actual 先从同一 context 按原时间重叠、计划完工日期和批次筛出安排，再交 ledger 投影。资源筛选保留“计划资源、实际报工资源、已记录剩余安排资源”的并集，必须在 ledger 后执行。完整关键链直接消费该 context 的完整安排、任务投影和区间，退出重建 execution_workspace。
- Actual 范围切换后仍保留已选 resource_ref/resource_type；当前资源选项目录无该项时显示“已选资源（当前范围无记录）”，再次应用继续提交同一资源，不改查全部资源。

| 真实职责 | 当前边界 |
|---|---|
| 完整计划来源与采用基线、交付、关系图 | 本次一次完整捕获，不按可见窗口截断，不再以整源 10000 条决定可查看资格 |
| 公开 Plan workspace | 应用范围后最多 10000 条安排；最终输出 8 MiB |
| Candidate / Actual 实际输出 | 各自最终 32 MiB；容量错误后保留手动范围恢复入口 |
| 试调、执行账本 | 试调仍检查完整基础来源最多 10000 条；ledger 仍最多 10000 工序、50000 事实行；Actual 最多 50000 条报工 |

完整图固定采用 `nodes[].predecessor_operation_refs` 表达原始工艺前驱，包含未安排前驱；退出重复的公开 `edges` 与 `process_order.items`，`process_order` 只保留 state/basis/issues。完整 nodes、critical_task_refs 和 critical_edges 保留，范围只改变展示任务，后端不裁剪关系或关键链来凑字节上限。字节仍只在真实出口编码一次。

## 5. P3：搜索只传变化，结果只保留一份

这一包按三个连续实施段完成，最终全部进入同一个目标结构；“内部单份结果”列入本次方案，不留为另一项长期补丁。

### 5.1 固定输入与原生解码

- NativeSchedulePreparation 拥有本次固定工序/索引、规范化批次、种子、停机、资源基础、拓扑和按需断点固定编码。
- SharedDecodeSession 的请求只接收真正变化的批序、派工规则、图启用状态、最终优先级、资源覆盖/偏好及允许变化的参数。scheduler、expected_operations、整份固定图等不再每次传入再核对。
- GreedyScheduler 的原始输入入口准备一次后调用同一个内部解码；共享搜索直接把本次已解析参数、批序、优先级交给核心。warnings 与 param_fallbacks 同时交接，删除“再解析一遍补计数”。
- 拓扑准备一次，移除候选侧平行 topology_cache 及内部逐解码 matches 热路径。接口退出静态图参数后，也退出“比较原字典和原字典证明未变”的动作。使用现有已准备拓扑对象，不新增冻结框架或版本字段。
- 原始输入和注入解码器只在创建准备对象/会话时完成实际所需适配；内部原生解码直接消费 OpForScheduleAlgo 和已有准备。热路径退出反射、关键字重试、MRO/访问器/类描述符重复认证。独立 GreedyScheduler 原始入口仍适配 proof_oracle 等真实 SimpleNamespace 输入；OptimizerRuntime.scheduler_factory 和测试替身在会话创建时选定适配，不增加 trusted 标志或证书。
- DecodeRequest 删除会话固定图和基础资源池大字段。LocalSearchState 直接持当前池，资源邻域只表达真实 pair_rank 变化；不再为无修改用途 shallow copy，也不添加哈希缓存。
- 当前共享搜索只调用一次 graph_prepare，runner 直接使用 prepare_schedule_graph_for_dispatch。删除 make_cached_graph_preparation_fn、贯穿的 core_cache 参数、命中/保存分支和仅为缓存服务的 copy_graph_ready_context/deepcopy；正常建图、健康/ready/资源投影与评分继续生成一次。B7 不再保留这套已失去用途的多候选缓存。

### 5.2 父代、资格、工时和断点

- repair 与 IG 共用 RepairParentPreparation。IG 的父代对象只保留 IG 独有顺序，退出第二套继承覆盖/图关系/结果映射准备。
- 父代已通过共同资格计算，内部生成的合法覆盖直接消费；外部原始决策入口执行一次准入。真实新增资源组合由同一资格规则处理。
- 静态可用机人配对、技能集合和 pair_rank 规范值由解码/会话准备持有；score cache、剪枝、ResourceDemand、probe 和正式放置共同使用。动态负载、换型和排槽照常实时计算。
- 已有 total_hours_by_op_id 直接供 probe 与正式估时使用。非 SGS 和无缓存错误输入沿一次真实消费入口处理，保留错误/统计时点。
- 种子只规范化一次，有正 op_id 时不建全表回填索引。下游只应用结果与资源占用；按件批次副本与首次 ready 的 earliest 共用，运行中变化的计数仍来自当前 state。
- 断点固定内容准备一次，请求只补动态部分。独立调用继续其一次完整签名；正式续排仍比较不同输入/参考断点所需内容。保留现有不一致、unsupported 和前缀合同，不新增证书。
- PoolEntry 在构造时持规范决策顺序；删除重复排序。固定记录类在准备/会话入口完成适配，候选解码和每轮派工直接消费；SGS 分组使用上游排序。原生 DTO 首条退出的旧兼容 reuse 路径随入口清理，避免保留不在产品热路径上的缓存与认证循环。

### 5.3 档案、过程与所有权

- 删除 SharedScheduleArchive.origins、_record_origin 及其线性查重/拷贝。完整多来源历史由已有 events 表达，来源增加即事件增加；无需新增 origins() 诊断入口。
- 保留一次实际用于最终 CandidatePlan 发布的 evidence_origin；repair_decision 等真实公开字段由选中证据提供。事件已有的 entry_id/request_id/evidence_event_ids 负责串联，不在每处存一份 N 项决策副本。
- 安排身份在 SharedDecodeSession 的真实解码出口产生，先于 profile pool、repair 指纹和 report。新解码只计算一次现有 content key，已登记结果复用 entry_id；已验证的新内容由现有档案接管，scope/目标评价同时准备，证据升级沿 evidence_revision 处理。报告消费身份与标量、追加事件，退出“先算报告指纹，报告再驱动档案登记”的反向依赖。
- 未验证 checkpoint trial 先以这次 content key 查询现有身份；命中则复用，未命中由现有编号器分配临时 entry_id，随后释放临时 key。它不进入 _identities/_StoredSchedule/best/verified seen。当前 trial 只与已验证父代和 seen 比较，remember_fingerprint=False，不需要为未知 trial 之间维持永久身份。结果沿现有 IG pending_outputs 保留到实际续排/完整验证完成；request_id 串联试算和验证，事件只存编号/标量。保留 decode_output_contents 对 warnings/errors 等真实续排输出的比较；安排编号本身不意味着 payload 已入档。这样无需长期保存“试算次数 × 工序数”的身份键，也不增加第二登记表。
- **安排身份统一由档案拥有，目标评价保留真实差异。** 报告的内部 key 收成“entry_id + objective + 完成性摘要 + 已有 metric/score 标量”，不再扫描/排序 results，也不保留第二份结果身份投影。当前两套 key 字段不同，不能只把整个报告 key 换成 entry_id；本方案明确统一的是固定输入会话内的安排身份，目标评价和完成性差异仍参与比较。op_code/op_type_name 等标签来自该会话固定输入，不作为另一套结果判等来源。新报告各计数仍表达原请求/正式结果/目标评价含义，历史报告原值保持；独立测试迁到真实会话边界，记录正常业务场景的原计数对照。若实际产品输入能在会话中改变这些标签，应在输入拥有者解决，而不恢复逐层指纹。
- 搜索内部使用现有 DecodedEvaluation/候选小视图引用档案结果，不再每次命中、每目标 sync 都物化一份 results/metrics。目标 score、请求 warnings、阶段来源留在该视图；档案原摘要不被改写。真正要修改的资源覆盖只复制被改工序，最终公开发布只物化一次。
- 将目前“任意修改内部候选副本”的测试约定迁为“阶段只修改自身决策和视图，档案不受影响”；保留真实外部返回值的独立所有权。无需只读代理、写屏障、全树 immutable 转换或额外自证。
- 请求数、真实解码数、复用、未验证试排、内容候选及最好结果改善仍各有原含义，预算继续按真实解码成本计。A11 的 scopes 表直接沿用。

**退出信号：**阶段只表达决策；固定输入、父代和结果各有唯一拥有者；五类解码入口、report、sync、发布全部迁完；旧 origins、大静态请求 key、重复参数/资格准备和无用途候选副本退出。

## 6. P4：token 是内存引用，快照只保存需要比较的值

### 6.1 直接保存绑定，复用原登记表

现有 public_token_registry 只存在于 current_app.extensions，没有落盘或跨进程传输。JSON 并非这个边界的要求。

- 原登记表 value 直接接受不可变绑定值。写绑定保存 subject_ref、actions 元组、共享 snapshot；读绑定保存 scope、as_of、必要 facts。现有字符串 ID 调用方继续存字符串。
- 已有 content_text 指纹直接共享同一个字符串；原始 dict 在事实拥有者处规范一次。保留 bool/int/REAL、BLOB、日期及转义字典的现有内容语义，不再写一套递归相等算法。
- 同一签发批次先在现有 by_value 反向索引中定位共享事实值一次，随后按 subject/actions/scope 等小键复用 token，避免每行重新比较同一大字符串。这是原登记表反向索引的分组，不另登记 snapshot token；逐行绑定仍直接持事实引用。保留 namespace、有效期、半 TTL 改签、旧 token 到期、LRU 和线程锁；旧 token 清理沿原 _drop_token 完成，空索引分组随之移除。共享内容由 Python 引用自然持有，不加第二套存储、引用计数或 TTL 同步。
- 删除 content_text(binding)、json.loads/unpacked(binding)、内存协议 version/source 标签及其格式自检。subject/action/scope 与用户实际提交是否匹配仍在实际准入处检查。
- 同一时点的读消费只 resolve 一次；直接从同一 binding 取得 as_of，服务完成后使用同一值比较必要事实。看板、报表、校准、外协和 facets 迁到同一流程。报工文件等锁外准备后等待写锁的入口，保留写锁内 O(1) token 存活/到期检查；这里时间已经变化，直接对象绑定使它无需重新解码或准备正文。
- resource_action_context 与 material_actions_previews 的预览/导出对象、准备好的文件 source 也由原 token 登记表直接持有。使用既有规范 document 值承担幂等定位，不再把它嵌入 context_key 再包 binding JSON；删除旁路 store、整表到期清理和 TTL 同步。所有资源、工艺、日历、物料、报工文件及导出调用者同批迁移，沿用原 token 的有效期和内容身份语义。

### 6.2 收窄事实与清理无消费者凭证

- 批次读、逐行写和创建 token 共享 P2 的紧凑批次事实。报工每工序的所有 task/report token 共享一次规范快照，删除 route 的第二次 plain_plan_facts。
- 预检响应使用已有 input_ref；删除无人消费的额外读快照。排产写绑定只关联 input_ref、normalized_input、data_context_ref；受理 resolver 已经比较当前事实，写绑定不再保存/比较同一整库 fingerprint。
- 排产状态和请求查询退出 DTO token 登记。保留前端需要的 meta 形状，以现有响应引用表达本次返回。
- 历史目录/锚点使用永久来源编号、运行状态、回执身份、source_issue 和现有 identity clock；删除整份 source_state、deepcopy 和全文头/摘要指纹。沿用原时钟，不新建版本体系。
- 现场甘特 state 不含派生 critical_chain。无 target 算实际展示的全局链，有 target 只算 target 链；本请求共享全计划事实和已有 plan_revision。
- 资料总览统一 scope token：列表每次查询、详情、定位、导出返回该次最新数据，响应给本次 as_of。scope token 不再绑定 28 张表全文。列表分页随本次当前数据读取，与“详情/导出最新”使用同一规则。
- MasterOverview 下载去掉旧列表 count 入参及旧零条数禁用；直接使用响应头中本次实际条数。详情仍保持自身分页/计数一致；token 和 scope 对应关系保留。此处属于第 9 节明确的公开读行为变化。

**退出信号：**同一事实只有一份规范值；N 行签发只构造 N 个小绑定；同一个 token 每请求不再解析两次；普通读不登记无人消费的整份 DTO。

## 7. P5：规范化产出直接写入，编码产出直接交付

### 7.1 领域写入和回执

沿用 WorkbenchCommandService 的 guard → mutate → receipt 结构。领域服务把输入与当前行准备成实际变更，公开单条入口、批量、导入都进入同一个 apply。准备结果使用现有领域模型/具名结果，不添加 trusted/validated 证书。

- 批量入口在写锁中一次取齐当前行、身份及关系，形成整批变更，再执行写入；删除每行重新走公开单条“读取→校验→写后读”的流程。人机主操关系按真实变更同步，保留最后写主操的规则。
- 工时确认直接使用 revise_current；路线新建一次写完整初始字段和解析结果，去掉 create 后为了同一数据连续 update。
- 仓储只返回实际消费者需要的结果：rowcount/已有业务键就直接返回；确需数据库默认值、新 ID、触发器永久 ref 时做一次定向读取。上游不以 old_revision+1 或另取 clock 伪造数据库结果。
- CommandRepository.insert 返回实际 outcome 编码或一次 JSON 往返结果；命令直接构造本次回执，删除 INSERT 后 GET 和再次序列化自检。重放继续读取原回执。输入准入和存档编码可在原共同函数内一次完成，保留现有类型集合，禁止把两种语义直接互换。
- worker 最终窄 status 回读只有在 claim/finish 已交出实际 started_at、finished_at、receipt_ref 后才删除；直接复用 public_job_head。写入者返回实际值，避免上层再取时间。

### 7.2 日历与报工

- CalendarAdmin 的共同规范化函数返回 WorkCalendar/OperatorCalendar。UI 补丁、文件导入、独立入口都使用它；repo 直接写模型字段。分钟稳定性、输入工时与班次冲突在这次构造中明确判断，删除 _check_proposed 的再次 build 和 upsert/repo 的后续重建。
- 补丁“未改字段保持”检查仍属于本次变更准备一次。preview 自指纹删除；confirm 的 TTL、实际日期集合和锁内当前日历比较保留。
- 写后不逐日 snapshot 自证。更新/删除使用已有 ref；需要返回新建 ref 的入口在整批写完后一次分块取得。文件导入没有 ref 消费时不补读。
- 默认效率/默认时段由本次操作持有，真正使用时取一次；下一命令重新取得配置。
- 报工事件入口规范化单条一次、按 scope 分组验序列一次，聚合器只归约。仓储读取、新增、legacy、预检和迁移实际调用方一起迁移，不在 reducer 增加 already_validated 开关。
- 文件 source 接管解码后私有行，parsed 保留消费副本；报工模拟只复制会追加的 reports 容器，旧报告行及 operations/plan/legacy 共用。真正更正的新行独立建立。

### 7.3 响应与保存编码

**推荐统一公开响应为最终 UTF-8 JSON 信封：一次严格编码、量实际字节、直接发送这些字节。** 扩展现有 web/api_responses，不新建响应框架。保持端点上限数值，使用 canonical_json 的紧凑 UTF-8 和 allow_nan=False。由 HTTP 出口承担的量尺从 service 删除；jsonify → get_json → canonical_json 往返退出。

这是明确的计量口径收敛：旧端点混用 data、canonical envelope 和 ASCII HTTP bytes，本来并不相等。方案采用一个最终发送口径；相对原 ASCII 门槛，中文响应可能容纳更多内容，相对只量 data 的门槛则加入信封开销。第 9 节将它列为可见边界调整，不写成逐字等价。

- 内部 ledger、搜索/采用准备和导出中无人发送的投影不量 HTTP 大小。行数和真实写入文档限制仍在相应入口承担。
- actual workspace、related-chain、CSV 各自的实际产物出口接全，随后删共同服务里重复量整份工作区的动作；CSV 不为导出预演另一份 JSON。
- 删除内部 execution_workspace 的 8 MiB JSON 预演上限；field 等内部消费者沿真实出口计量，Actual 和 chain 直接消费第 4.3 节的同次 context。公开 plan/field 工作区沿各自真实端点上限计最终字节，Plan 8 MiB、Candidate/Actual 32 MiB 与 related-chain/CSV 各自真实输出边界保留。这会使“内部计划 JSON 超过 8 MiB、实际目标输出仍在上限内”的请求可成功，列入第 9 节的明确行为调整；原测试迁为验证真实输出上限，不继续锁定内部预演。
- 看板 analysis 超限后产生不含 analysis 的新响应，可以编码这个不同结果；原降级含义保留。看板比较最终使用 8 MiB/query_too_large，退出没有独立消费者的内层 32 MiB/candidate_capacity_exceeded。
- 场景保存由现有 trial codec 返回 header 文本、各 task 文本及完整逻辑 snapshot 字节数，编码结果直接交仓储。逻辑大小按 metadata、逻辑 tasks 数组、任务正文及实际字段/分隔符合成；物理 header 的 format/snapshot 包装与 task_row_refs 数组不属于逻辑 snapshot，不能与任务列长度直接相加。保存与读取共用此定义，物理列各自上限继续独立承担。
- 场景读取从已读的规范片段计完整逻辑文档大小，承接现有 64 MiB 总量后删除 dump(result)。旧非规范文本或 legacy 双份内容沿其实际格式做一次必要解码/计量，不给全部新场景再次编码。当前 byte_limit=None 及 header/bodies 分别限制不覆盖这一职责，迁移时一并收拢到 codec 的共同入口。
- 新场景 tasks 由 stored[ref] 直接组装，删除整份自比较；row_ref 关系在组装时处理一次。legacy 两份独立内容的比较留在旧格式入口。
- 新建草稿直接使用同次 live，调用链不再执行“归档与当前比较”再识别两者是自己。已有草稿/采用的跨请求比较保留；原文计量与 schema_compat 比较投影分别在其真实用途只处理一次。

**退出信号：**每个业务规则只有一个实现，每份落库文本和发送字节有实际消费者；所有下游自证、无人消费的 references/snapshot、无效 JSON 预演实际删除。

## 8. P6/P7：显示生命周期、启动维护与 SQL 收口

### 8.1 P6 显示与请求

工作区持有 prepare(data, semantic_mode)；它生成时间、名称、搜索串、资源成员索引、稳定分轨、冲突成员、任务索引、marks 及每成员计数。query/late/onlySelected 先筛选已准备成员，布局从可见成员生成组汇总；collapsed 决定当前行、top、locations/reportLocations/graphLocations 和键盘可达顺序。width 只改变几何；mode 真正改变资源分组/基线含义时，只重建受它影响的部分。时间解析和每成员分轨复用，筛选后的实际汇总与折叠位置继续随 view 变化。

- PlanWorkspace 的匹配数、PlanGantt、详情与 Dashboard 使用同一准备结果；迁掉唯一 G.layout 消费者后删除旧一次性布局入口。
- PlanWorkspace、RunCandidateWorkspace、ActualGanttWorkspace 在各自既有 useMemo 中持有显示准备并各建一次 GanttGraph 索引；三个 model 只准备任务事实，甘特、详情与 GanttRouteList 直接消费同一索引。Actual 的计划关键链也接收同一 index，使用 index.nodes，保留实际需要的可见集合与关键链入边准备；退出每次 render 从原始 graph.nodes 重建完整 Map 的路径。路线组件内第二次 create、甘特组件补建分支和 PlanProcessOrder 均退出。已安排任务的关系边由完整节点及原始前驱在本地建立，未安排前驱继续显示缺项事实。
- 范围外路线节点使用已持有的原始 start/end，一次请求目标范围 workspace；已在本次任务集内的节点直接定位。点事件的排他结束时间按原微秒文本精确加 1 微秒，跨秒、跨年和闰日进位保留规范时间表示，不经过毫秒截断。
- 投影保留真实微秒窗口的正容量和停机小时值：共同日历先累计秒再换小时，Plan 占用复用现有 `precision=None`，归档总量直接累加日值，退出各自 round6。`ResourceUtilizationMetrics` 的默认报表显示精度仍沿原约定，前端合同继续校验真实容量与比例的一致性。
- 可见项由父层选一次，密集判断、DOM/Canvas 绘制与命中共用；hover 提示独立更新。
- 共同 canvas hook 挂载一次 observer/打印/主题监听，回调使用当前 paint；尺寸真正变动才设置缓冲区。内容、视口或选择改变只请求一次绘制。保留 DPR、主题、打印和点事件语义。
- Actual marks 在 model 准备一次，Rows/Canvas/命中/连线共同读取；报工次数、已知工时、缺工时及旧记录数按当前可见成员汇总，连线读取当前布局位置。冲突详情使用资源索引。
- 热力图直接消费后端 heatmap.buckets；前端只建立 group_key 索引、桶的展示值与对应键盘顺序，删除逐桶 filter/indexOf，不重新造桶。presentation 随 mode/definitions 的真实变化更新。
- WorkbenchFormat 的有限格式选项复用 Intl.NumberFormat；hours 走同一个内部格式化实现，保留 exact、空值、负零和文案。
- 列筛选采用现有搜索按钮和 Enter 提交：input 只改本地草稿，提交才改变 request；沿用现有过期响应隔离。无需新 debounce/请求缓存层。甘特本地搜索继续即时过滤。
- ReportDetail 只读取和校验 detail + 必要 plan/meta，退出完整列表统计/图表生成。保留筛选范围外 404。
- 新工种只读必要 detail；经办人提示挂载读一次，保存后使用实际写入结果更新。同一文档写入不依赖 storage 事件。

### 8.2 P7 启动、维护与数据库

- 启动协调者捕获 journal 一次，runtime/restore host 消费同一 records。维护接受和退出备份属于下一操作，再取得当时记录。
- 普通 WSGI 准入只读内存停止状态；维护窗唯一检查留在 factory._open_db 开库前。真正展示 restore-host 时再算 operations_available。退出释放锁、维护恢复继续使用它们已有的所有权检查。
- 不把提前检查的维护观察值塞入 environ 再复用；自动维护线程可能在两层之间进入，现有开库边界已经是更直接的位置。
- 当前版本普通启动只查结构；迁移完成、外部恢复执行完整数据合同及缺历史头检查。恢复实际接线包括 core/services/system/backup_restore.py 的 _verify_restored_database，调用明确的完整合同入口；不能沿普通 ensure_schema 分支只验结构。已有 schema42 库通过下一次迁移进入该检查，随后采用不再做全历史反连接。检查使用 DISTINCT version 的共同实现。
- 完整事件数据合同按序列顺序读一遍同时验值/序列，写探针只在真实迁移/恢复边界运行。
- 备份/恢复保留入口路径类型、独占创建、实际 integrity_check、最终目标槽位、恢复后合同和失败回滚；删除维护期间复制过程的反复身份自证。
- 完整 canonical SQL 的代码常量结果在定义侧准备一次；live 结构仍由当前作用域读取。日志用一次已有安全打开表达 missing/empty/error，删除外层 stat 探测。
- SQL 时间处理先让实际调用者消费现有 PlanReadContext 的 parsed intervals。对仍须在 SQL 过滤的路径，将反复展开的 valid/overlap 表达式改成一次区间判定函数：每行起止各解析一次，参数由查询入口预规范化，坏时间仍返回给原上层显示。纯跨度/按批统计若仍有实际消费者，用同一解析规则的窄 SQLite 聚合一次完成；随着旧 reader 退出而消失的聚合不再实现。
- 不使用本机已实证无效的 AS MATERIALIZED 作为次数保证；不为时间过滤增设持久化影子时间列、全局解析缓存或第二套日期语义。沿已有连接 UDF 注册入口接入，保留 TRIM/CAST、微秒、点事件和空值含义。

索引在旧 reader 迁移后统一进入下一迁移版本（基线为 42，当前预期下一版 43）：新增 BatchMaterials(batch_id)、BatchOperations(supplier_id)、PartOperations(supplier_id) 三个单列索引，整数主键的 rowid 顺序已经足够。

| 原建议删除的索引 | 本方案动作 |
|---|---|
| idx_schedule_candidate_selection_version | 删除；现有 UNIQUE 足以承担实际筛选 |
| idx_operation_execution_events_schedule | 删除；真实完整 scope 使用 schedule_id/op_id 索引 |
| idx_operator_machine_operator、idx_schedule_candidate_version | 随无产品消费者的旧 reader 退出后删除；有效工具调用先迁完。若该 reader 被保留，则保留其排序索引 |
| idx_part_operations_part、idx_batch_operations_batch、idx_schedule_history_version、idx_schedule_candidate_rows_version_candidate | 保留真实 ORDER BY id 排序用途；不为删除索引改变版本头选择语义或引入额外排序 |

F2 的 action 复合索引已存在，保留；无用探针移到真实旧库缺表分支。新迁移同时同步 schema.sql、版本注册、结构合同和现有数据库说明；不改已发布的 v41/v42，不迁移或删除历史业务正文。

同次迁移扩展现有 core/services/workbench/facts/schema_compat.py 的 project_facts：将下一版本纳入已声明表示兼容范围，并归一此次明确增删的性能索引 DDL。当前只接纳 v39–v42，直接升级会让历史候选/试调仅因版本或索引差异被判 snapshot_stale。比较投影只处理本次已声明且定义匹配的索引，真实业务行与未声明结构变化仍参与原比较；原归档原文保持。复用现有 v41 读模型迁移的事实兼容用例扩展至本次版本，不加第二兼容层。

## 9. 11 项裁决和明确的公开行为调整

原裁决的减重目标全部纳入，当前代码事实及更简单实现优先于旧文档中的具体步骤。

| 裁决 | 本方案落点 |
|---|---|
| 1 批次只读所需事实 | P2 聚合引用、旧账本按需读取；P4 共享紧凑事实值 |
| 2 每个出口量一次 | P5 统一最终 UTF-8 信封与实际保存边界；删除内部 execution_workspace 预演，覆盖全部入口 |
| 3 普通请求不验启动锁 | P7 内存停止状态 + 现有开库处一次维护检查；不增建写入口验证层 |
| 4 归档读取不重演公式 | P2/P5 保留实际解码/关联规则，落档/采用承担公式和内容确认；RunBaselineAPI 的 source_verification 同步表达保存边界事实 |
| 5 缺历史头移出采用 | P7 下一迁移与恢复完成处一次检查；日常采用复用现有原子写入保证 |
| 6 重启只查结构 | P7 明确正常启动与外部数据进入边界 |
| 7 共享拓扑不再匹配 | P3 固定输入从候选接口退出，直接消费现有准备结果 |
| 8 日历写后不逐日回读 | P5 一次构造模型、一次落库，仅按实际回执补新 ref |
| 9 总览详情/定位/导出最新 | P4 列表同样采用 scope 绑定的当前读取，前端不再依赖旧 count |
| 10 档案身份与甘特链 | P4 现有永久引用/clock/revision 绑定，去掉全文与派生链 |
| 11 内部投影不量 HTTP 大小 | P5 输出层负责实际产物；内部准备不序列化预演 |

方案中明确包含以下公开调整：资料总览统一当前读取、列筛选改为 Enter/已有按钮提交、报表详情改窄 DTO、响应按最终 UTF-8 字节计量、删除内部 execution_workspace 的 8 MiB 预演门槛，以及看板超大比较统一最终错误码。实现时后端和全部前端消费者同批迁移，保留页面已有功能。旧保存数据不重写；旧配置/接口实现退出与旧数据读取分开处理。

IAB 后追加批准第 4.3 节的完整计划来源读取与范围准入分工，以及第 8.1 节的统一完整图协议：整源 20k 计划可以选择并按窗口读取，公开 Plan 10000 条范围及原输出字节上限保留；Actual 在 ledger 前应用完工日、批次和重叠范围，资源并集仍在 ledger 后筛选。试调完整基础来源及账本自身上限保持。FieldFiles 在保存完成后隐藏旧“尚未写入”的预检句，继续由原 Feedback 显示真实保存结果。

原审计另列的 8 个细节也采用明确口径，随所属步骤迁移：

| 原来源 | 本方案处理 |
|---|---|
| S04-05 停机失败粒度 | 当前 partial_fail 仍会中止排产，没有成功降级。P2 保留 input_runtime 的 invalid_downtime_state/invalid_downtime_interval 及原中文说明；整次捕获失败沿 preflight 的 storage_failure 或 worker 的 failed/diagnostic 表达。删除新运行中逐设备查询的 partial 分类/计数，已有历史诊断照常可读。 |
| S07-02 历史目录坏回执 | 当前目录按小头读取、目标回执按需解析已经完成，沿用现状；详情读取坏回执在真实消费处报告，不恢复全目录预扫。 |
| S08-09 外协页外超大项 | P5 采用实际响应与写入文档边界；不在本次输出中的项不再只因内部 JSON 超过 8 MiB 阻断当前页。读取行数限制及该项被真正读取/写入时的边界保留。这是明确的拒绝时机调整。 |
| S09-06 新零件 revision | P5 初始字段一次 INSERT，revision 从触发器/默认值实际取得；当前常见路线导入从创建后的 3 变为 1。file_route_preview/file_route 只比较捕获值相等，创建回执及公开零件 DTO 不展示该数，未找到依赖固定增量的真实消费者。删除两次多余 UPDATE，不人为补增；永久 ref 与后续真实 UPDATE 递增保留。 |
| S11-09 导出预演与时间字段 | P5 最终发送内容编码一次并直接发送，动态字段在本次投影时确定；删除对另一份内部 workspace 的预演，实际输出上限保留。 |
| S06-02 / S06R-02 参数与默认起点 | P3 解析结果连同 warnings/param_fallbacks 直接交解码；共享搜索缺省 start_dt 只取会话起点，独立原始入口使用自身本次起点。 |
| S06R-08 解码中改记录类 | P3 退出内部对固定类的反复认证；测试替身在会话创建边界注入，保留真实原始输入适配，不维护解码中修改类定义的专用合同。 |
| S13R-01 origins 测试 | P3 全来源历史直接检查已有 events，发布来源检查 evidence_origin；删除 entry().origins 断言，不另建诊断接口。 |

上表的外协拒绝时机、新零件 revision 和旧停机查询失败诊断随结构调整明确变化；已有错误传播、实际业务失败与并发身份比较继续由原职责承担。

## 10. 依赖、交付和有效验证

| 步骤 | 前置 | 完成后实际少掉的工作 |
|---|---|---|
| P1 旧入口收口 | 当前基线 | 第二条输入/持久化链、旧配置装配、无人消费产物 |
| P2 操作事实归口 | P1 的共享输入/仓储职责迁移 | 同事务重复捕获、点查、重复关联和计划解析 |
| P3 搜索准备与档案 | P1；资源准备与 P2 对齐后推进 | 固定大 key、重复参数/拓扑/资格、origins 和候选副本 |
| P4 内存绑定 | P2 紧凑事实形状 | token JSON、N 份指纹包装、双解析、无人消费快照 |
| P5 单次规范化/写入/编码 | P1/P2；token 消费与 P4 同批 | 下游重验、写后自证、重复编码/导出预演 |
| P6 显示与请求 | P1；公开 DTO 与 P4/P5 同批 | 每按键重准备、每帧建 observer、详情整页运算 |
| P7 启动维护与 SQL | P1/P2 的实际保留查询确定 | journal/锁/事件重复检查、每行重复时间解析、无用索引 |
| P8 集成与文档 | P1–P7 | 清理所有临时迁移分支、旧参数/导出/测试接线，记录真实结果 |

P3 与 P4 可由不同负责人推进，P6 的纯模型/绘制部分可并行；共享文件由一个负责人接续。正式实施如使用子代理，按用户要求新建不继承对话上下文的代理，提供已定稿接口和明确文件职责。

验证按职责组集中复用现有用例：

- 搜索：shared optimizer/archive、repair real decode、checkpoint、process evidence；确认固定准备次数、实际解码/复用统计、种子/DAG/停机/点事件、证据升级和最终来源字段。
- 事务与写入：run jobs atomic、采用、批次/资源/工艺/日历/报工现有事务用例；确认写锁内当前事实、回滚/重放、真实生成 ref/时间、分钟语义和事件序列。给真实缺口补少量调用计数，不给72条各造一份测试。
- token/输出：现有读写 scope、幂等签发/expiry/LRU、首发与重放、CSV/JSON、试调保存读取用例；确认共享对象无需 JSON 往返，写 token 不依赖读 token 存活，等待写锁期间到期仍被拒绝；大小边界使用已选最终字节口径，试调逻辑大小排除物理包装。
- 界面：复用 Node 契约和实际页面，覆盖搜索提交、可见成员汇总/折叠定位、滚动/hover、缩放、点事件、键盘、主题/打印、最新导出条数和报表详情。旧 opt-in 浏览器脚本已退役，使用当前宿主真实浏览器，不把 collect/skip 当通过。
- 启动与 Schema：新库/升级/恢复、维护503、备份回滚；确认普通启动不扫描事件数据，迁移/恢复执行数据合同；本次纯索引升级前后旧业务事实保持相等，真实业务修改仍可识别；对实际保留 SQL 做 EXPLAIN 与时间解析调用计数。

设计阶段已完成文档 frontmatter/YAML、链接、编号覆盖和正文/清单一致性检查。授权实施后按影响运行产品验证，最终整合使用项目现行完整门禁；实际命令、结果及平台延期记录在实施记录。只在最终 HEAD、干净工作区与要求证据齐全时声明 clean proof。

性能只针对实际改动路径做可比测量，复用已有独立 858/20k 副本及未变结果，不重跑整套历史 benchmark。优先证明少读、少准备、少编码、少绘制，再测一个代表流程的真实耗时；达到行为与目标后结束。

回退以每条完整职责迁移的提交为边界。当前版本升级失败沿现有备份/事务机制恢复，不新建旁路；不通过长期保留两套实现解决回退。代码完成时同步当前架构、接口/数据库说明和测试登记，本文只记录目标态。

## 11. 全部72项覆盖与复核新增发现

### 11.1 原编号映射

| 编号 | 当前处理 | 落点 |
|---|---|---|
| A1 | 删除 archive.origins；事件拥有多来源，发布保留选中证据 | P3 |
| A2 | 固定断点输入一次准备，请求只补变化 | P3 |
| A3 | 会话拓扑一次准备、最终key一次规范化 | P3 |
| A4 | 静态资格共同准备，动态派工照常 | P2/P3 |
| A5 | repair/IG 共用父代准备，退出全量继承覆盖复验 | P3 |
| A6 | 参数/批序/警告一次解析与交接 | P3 |
| A7 | 直接使用已有 total_hours_by_op_id | P3 |
| A8 | 删除固定大key与无修改浅拷贝 | P3 |
| A9 | 档案一次拥有安排/评价身份，report不再扫结果 | P3 |
| A10 | 删除 locked_seed_range 全部生产写入 | P1/P3 |
| A11 | 已解决，沿用 scopes 表与 scope_ref | 沿用 |
| A12 | 统计直传、父代key、种子、原生入口、类认证、批序、按件输入一并收口 | P3 |
| B1 | capture 派生 latest 一次，所有消费者复用 | P2 |
| B2 | 补采用/worker共享capture；受理已完成部分沿用 | P2 |
| B3 | 同事务约束复核直接消费 prepared 执行事实 | P2 |
| B4 | 预约/种子使用已读计划、工序、人机事实 | P2 |
| B5 | 已有选中payload沿用；共同source映射准备一次 | P2 |
| B6 | 停机从已读事实分组，不逐机重查 | P2 |
| B7 | 单次建图已完成；删除已无命中用途的多候选缓存及深拷贝 | P3 |
| B8 | 资格/授权统一事实与判断 | P2/P5 |
| B9 | 预检已完成；试调及独立配置读取一次 | P1/P2 |
| B10 | 已解决，PreparedRunResult 文本直接落库 | 沿用 |
| B11 | 缺历史头检查移到新迁移/恢复 | P7 |
| B12 | 摘要入口规范化一次，旧result_summary_json随旧链退出 | P1/P5 |
| B13 | 普通状态已轻量；写入者交实际值后删窄回读，保留恢复COUNT(t.row_ref) | P5 |
| B14 | 下游/同组一次索引，直接传algo_ops组身份 | P2 |
| B15 | 一次完整建图准备同工种资源，含piece逐工序入口 | P2/P3 |
| C1 | 批次计划引用聚合、旧账本按需 | P2 |
| C2 | N个token共享一份内存事实值 | P4 |
| C3 | 已解析区间复用；必要SQL一次区间判定/聚合 | P7 |
| C4 | 大回执读取已解决；目录state改紧凑身份 | P4 |
| C5 | ledger本次计划/依赖一次读取，覆盖直接命令guard | P2 |
| C6 | 响应/独立产物出口各一次编码计量 | P5 |
| C7 | binding直接存值，规范事实只比较一次 | P4 |
| C8 | 同时点消费resolve一次；锁内保留真实到期检查 | P4 |
| C9 | 删额外预检、确认整库及轮询DTO登记 | P4 |
| C10 | scope绑定的最新读取，前后端导出计数一起迁 | P4/P6 |
| C11 | 每工序一次规范快照，报工/任务token共享 | P2/P4 |
| C12 | GenerationFacts提供共同解码表，删重复小头/体积编码 | P2 |
| C13 | 预扫已解决；任务准入产出IDs供completion直接用 | P2 |
| C14 | 普通读取已解决；落档builder静态分组一次 | P2 |
| C15 | 已解决，兄弟资源来自保存summary | 沿用 |
| C16 | 读归档退出历史公式验算，迁移实际source_verification消费者 | P2/P5 |
| C17 | trial来源一次读取/解码；删自比较；codec一次编码并负责逻辑文档上限 | P2/P5 |
| C18 | 历史锚点改永久身份/现有时钟，删全文deepcopy | P4 |
| C19 | 按实际target算链一次，复用全计划事实 | P2/P4 |
| C20 | 计划resolution、资源映射和CSV静态元数据复用 | P2/P5 |
| C21 | 公共日期policy一次，人员只叠加覆盖 | P2/P5 |
| C22 | facts/detail/choices/route变更同次共享 | P2/P5 |
| C23 | 变更准备替代整页preview，资格使用共同来源 | P2/P5 |
| C24 | 班次cell已解决；外协只量实际输出/写入边界 | P5 |
| C25 | 本次连接共享已有SchemaStructure/Memo | P2 |
| C26 | 一次安全打开返回missing/empty/error | P7 |
| D1 | 单条/批量同一领域变更与apply，删除重读/连续重复写 | P5 |
| D2 | 人机关联一次确认事实，一次应用主操变更 | P5 |
| D3 | 导出只取输出列，删references和丢弃snapshot；导入一次取齐 | P2/P5 |
| D4 | 日历一次规范化、批量写、按需取得新ref | P5 |
| D5 | 回执insert返回实际编码，删GET及二次编码 | P5 |
| D6 | 单事件规范化、序列检查、聚合各一次 | P5 |
| D7 | source接管私有解码行，parsed保留消费副本 | P5 |
| D8 | 外协guard结构检查一次，报工只复制变更容器 | P5 |
| E1 | 普通启动结构、迁移/恢复数据合同 | P7 |
| E2 | 内存运行状态、开库前一次维护检查 | P7 |
| E3 | journal由启动协调者捕获一次 | P7 |
| E4 | 完整常量DDL规范化复用，删复制过程身份自证 | P7 |
| F2 | action索引已存在；旧库探针按需 | P7 |
| F3 | 三个有实际消费者的单列查询索引 | P7 |
| F4 | 删除两项、两项随旧reader退出；保留四项生产排序用途 | P1/P7 |
| G1 | 共同绘制生命周期、可见项一次选取、hover独立 | P6 |
| G2 | 固定时间/marks/冲突索引一次准备，可见汇总/位置随view变化，热图消费现有桶 | P6 |
| G3 | 双结果校验已解决；输入准入归口、详情窄DTO、显式提交筛选 | P4/P6 |
| G4 | identity已解决；删除新工种list，存储挂载读/保存更新 | P1/P6 |

### 11.2 已纳入的新问题与更直接解法

| 编号 | 复核发现 | 纳入方式 |
|---|---|---|
| N1 | token只有进程内存，却把binding反复JSON化，预览/导出还保留旁路store | P4直接值登记并删除旁路store与TTL同步 |
| N2 | worker同一计算副本_check_facts与prepare重复capture | P2与采用共用同一修法 |
| N3 | 导出references与物料snapshot没有消费者 | P5直接删，不批量化保留无用工作 |
| N4 | 日历稳定检查是第二次build，repo还会from_row | P5一次模型构造贯穿所有入口 |
| N5 | 工作台只消费纯计算，旧orchestrator仍带版本/持久化分支 | P1退旧链后删除分支及result_summary_json |
| N6 | IG与repair各建父代；报告与档案各扫结果；复用还反复物化 | P3统一父代与结果拥有者，包含内部单份结果迁移 |
| N7 | scope最新读取与前端旧count/零条禁用冲突 | P4/P6使用实际导出count及scope状态 |
| N8 | 现有AS MATERIALIZED在SQLite3.35.5未达到一次解析 | P7使用直接区间函数/实际保留聚合，不新增影子列 |
| N9 | 旧索引前缀覆盖遗漏rowid排序 | P7保留真实排序用途；不为删索引改业务选择 |
| N10 | 已落档执行事实读时重演、新格式场景自比较没有新增产物 | P2/P5移除重复计算，沿用写入/迁移事实；可变旧历史仍绑定现有clock |
| N11 | 供应商能力还有Suppliers.op_type_id，原始工序没有外协组扩展字段 | P2使用共同资格来源及prepared.algo_ops真实字段 |
| N12 | 写token引用读token会改变寿命，重新拼worker状态会漏真实时间/ref | P4直接对象引用；P5由写入者返回实际值 |
| N13 | 新索引版本未接入现有schema_compat会使旧事实仅因版本/DDL变化而失配 | P7同次扩展明确版本与索引表示兼容，原文及业务变化保留 |
| N14 | graph_prepare已每搜索一次，旧core_cache仍为不存在的第二次准备存深拷贝 | P3删除缓存factory/参数/命中保存分支，直接准备一次 |

以上各项均进入同一执行清单。后续实施发现同职责的新重复，优先扩展共同入口并删除重复调用；只有真正增加业务范围或改变这里已定的公开行为时，才另行明确取舍。

## 12. 独立复审结果与修订

完整初稿完成后，四个全新代理分别审查整体架构、token/输出、前端/基础设施、72 项与 11 项裁决覆盖。它们只拿方案和设计时的代码，没有继承设计对话。主代理逐项回到代码复核后，将下列修正写入正文、映射和执行清单；其中 Schema 兼容为主代理并行核查补充。下表保留设计阶段的证据位置，当前实施状态以文首和实施记录为准。

| 核查结果与证据 | 已采用的修正 |
|---|---|
| 报告/父代池先用指纹、档案后登记；未验证 trial 没有档案身份：[stages.py:71](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/stages.py:71)、[search_report.py:133](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/search_report.py:133) | P3 在共同解码出口先取得身份；未命中未验证 trial 只持临时编号，退出长期身份键/payload 保存，保留既有验证准入 |
| 固定 DTO 在每候选仍重复认证：[sgs_score_cache.py:90](/Users/lurenxing/GitHub/----/core/algorithms/greedy/dispatch/sgs_score_cache.py:90) | P3 适配提升到准备/会话，内部直接消费；独立原始入口继续支持真实 proof_oracle 输入 |
| 单次建图仍保存多候选缓存副本：[schedule_candidate_runner.py:44](/Users/lurenxing/GitHub/----/core/services/scheduler/run/schedule_candidate_runner.py:44)、[schedule_graph_cached_projection.py:86](/Users/lurenxing/GitHub/----/core/services/scheduler/run/schedule_graph_cached_projection.py:86) | P3 整段删除 factory、core_cache 与缓存专用复制；B7 从“沿用”改为清理残留 |
| C17 来源元数据先解析，资源来源随后再次准备：[decision_baseline_source.py:141](/Users/lurenxing/GitHub/----/core/services/workbench/facts/decision_baseline_source.py:141)、[adoption_baseline_sources.py:187](/Users/lurenxing/GitHub/----/core/services/workbench/facts/adoption_baseline_sources.py:187) | P2 resolver 持有一次场景与来源准备，保留原来源/当前分配资源的差别 |
| 等待写锁期间 preview 可能真实到期：[execution_files.py:87](/Users/lurenxing/GitHub/----/web/routes/workbench/execution_files.py:87) | P4 同时点读消费复用；写锁内保留 O(1) 存活/到期检查 |
| 预览/导出还维护正文包装和独立 TTL store：[resource_action_context.py:64](/Users/lurenxing/GitHub/----/web/routes/workbench/resource_action_context.py:64)、[material_actions_previews.py:43](/Users/lurenxing/GitHub/----/web/routes/workbench/material_actions_previews.py:43) | P4 一并迁入原 token 登记表，删除两份旁路存储 |
| execution_workspace 仅为内部产物，却预演完整 JSON：[queries.py:230](/Users/lurenxing/GitHub/----/core/services/workbench/plan/queries.py:230) | P5 删除内部 8 MiB 门槛，实际输出各量一次；公开边界变化列入第 9 节 |
| task_row_refs 属物理归档包装，逻辑 snapshot 恢复为 tasks：[workbench_trial_scenario_archive.py:10](/Users/lurenxing/GitHub/----/core/models/workbench_trial_scenario_archive.py:10) | P5 分开逻辑总量与物理列上限；codec 按实际逻辑片段计量 |
| Actual 甘特先筛选再汇总，折叠决定位置：[ActualGanttModel.js:76](/Users/lurenxing/GitHub/----/frontend/workbench/app/ActualGanttModel.js:76)；热图桶已有后端来源：[decision_resources.py:515](/Users/lurenxing/GitHub/----/core/services/workbench/run/decision_resources.py:515) | P6 固定准备与动态可见汇总/布局分开；前端只索引已有热图桶 |
| 恢复当前经 ensure_schema；事实兼容只接纳 v39–v42：[backup_restore.py:71](/Users/lurenxing/GitHub/----/core/services/system/backup_restore.py:71)、[schema_compat.py:145](/Users/lurenxing/GitHub/----/core/services/workbench/facts/schema_compat.py:145) | P7 恢复显式执行完整合同；下一索引迁移接入现有兼容投影，防止旧事实仅因结构表示失配 |

复审确定采用现有职责交接结果，必要验证按第 10 节及 V1–V8 集中执行。后续实施与原对话复核的结果记录在实施记录和执行清单。
