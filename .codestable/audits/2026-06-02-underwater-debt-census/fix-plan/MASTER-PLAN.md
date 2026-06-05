# APS 水下语义债 · 修复总计划（MASTER-PLAN）

> 本文件是 80 条水下债（72 真债 R01-R72 + 8 承重护栏 LB01-LB08）的**有序修复总计划**。
> 由 Phase 0（脚本确定性真相源）→ Phase 1（8 组 grep 爆炸半径 + 全局矩阵）→ Phase 2（19 单元逐桶细计划）→ Phase 3（全局对账 + 对抗核查）四阶段产出。
> **本轮只出计划，未改任何生产代码。** 逐债细计划见 `B01..B17.md`；逐债爆炸半径见 `phase1/_phase1_blast.json`；逐债修法见 `phase2/units/*.json`。

## 0. 复核基线与铁律（执行前必读）

- **复核基线 = 提交 `b08162cd`**；HEAD `c2aa7501` 只动 `.codestable/`+`evidence/`，提交态生产代码 ≡ `b08162cd`。
- **真实行号漂移在 16 个工作树未提交生产文件里**（见 `phase0/PHASE0-TRUTH.md` §0）。每条 `file:line` 落地前必须 Read/grep 回盘复核。
- **五条红线**：① 坏数据不准静默兜底（P4 改 raise/补可观测，严禁加兜底）；② 承重护栏只补注释+绑契约测试，严禁删/统一/透传；③ P5 收口到已存在点，唯一新建例外=R09；④ 0 分层违规，删 facade 前先迁测试；⑤ drift 工具标定。

## 1. 对抗核查裁定（Phase 3 独立第二双眼睛）

**VERDICT = `可发布`**

| 退出自检项 | 结果 | 证据摘要 |
|---|---|---|
| 1. 80条全覆盖(72真债+8承重,每条恰好一个家) | **partial** | 脚本枚举_phase2_index.json=80键,R1-R72无缺口,LB01-08齐全;批次映射后80/80全覆盖无遗漏。但R31双重落家:R30/R31决议明文『R31完整落在Batch-7不再留尾巴到Batch-14』,而execution_order的Batch-7列R31-shared、Batch-14又 |
| 2. 8承重零删除(LB01-08+R56/R58全是补注释+绑测试) | **pass** | 逐条核fix:LB01/02/05/06零删除零统一零透传补注释;LB03=已fail-closed治理仅确认入账+git add守卫+:141注释;LB04注释+契约;LB07红线2补注释+扩parity;LB08只补注释严禁删正则桥;R56补注释+绑rename守卫;R58默认只补注释。无删/统一/透传混入。R58 |
| 3. P4无兜底(LB03/R07/R12/R28/R32/R40/R69全raise或补可观测) | **pass** | R07改loud raise AppError(NOT_FOUND)+补导入;R12补dropped_count可观测保留:84过滤(盘上证:84=if not st or not et or not(st<et):continue);R28收口parse_finite_float垃圾raise;R32 except→ |
| 4. 无新建模块(除R09外) | **pass** | 扫全部fix仅R09的F3新建parse_optional_positive_int(唯一批准),盘上grep证不预存在=前提成立。其余收口点全盘上EXISTS:gantt_critical_chain.py/summary_count_parse.py/schedule_input_contracts.py/oper |
| 5. 排序无环(B01先落/B13晚于收敛/承重前置) | **pass** | 对depends_on做DFS环检测=NONE无环。所有16批可达Batch-1(承重先落);Batch-14祖先含Batch-6/7/10=facade晚于B05/B06/B09收敛;Batch-13(R34)祖先含Batch-8(R05)=承重前置;Batch-12(B11)祖先含Batch-7(B06 R15)= |
| 6. 打架已解(Phase1的16条纠偏都定调) | **pass** | 逐条比对:#1#2 R11≡R63合并、#3 R29授权CSV盘上ls复证不存在、#4 R47双栈对称(盘上证service:68同声明)、#5 R44方向反(盘上证core更严)、#6 R54第4套dashboard_workbench:19-24(盘上证)、#7 LB06 off-by-one、#8 R26两离线消 |
| 7. 灵魂线(有无以统一名义抹掉承重不对称) | **pass** | 无一条以统一名义抹不对称:LB02/05明文勿为统一四报表签名加形参保:141不对称;R44收口core但盘上证core更严(handles None)=增强非抹平;R47双栈对称删死参but LB07保双栈;R71默认仅parity锁定不物理收敛owner-gated;R23复用model._normalize_ro |

**must_fix（已在本文件消解）**：
- R31单一落家口径不一致(低severity非阻塞):cross_bucket_conflicts的R30/R31决议明文『R31 shared源侧value_policies.py:9折叠进Batch-7的R30同文件编辑,不再留尾巴到Batch-14』,但execution_order的Batch-14仍把R31-cleanup列为成员。盘上已证R30与R31-shared确同改core/shared/value_policies.py(:9 WRITE_INTERNAL

> R31 双重落家已消歧：R31 完整并入 Batch-7（与 R30 同改 `value_policies.py`），Batch-14 不再含 R31。

## 2. 有序执行批次（16 批，解决全部排序冲突）

> 依赖关系构成 DAG（已验无环）。Batch-1 是全局地基（承重注释+契约/parity 安全网），所有后续批依赖它。Batch-14（B13 facade 删除）全局最晚。

### Batch-1 承重注释+契约/parity安全网(全局ROOT·纯增量零结构)
- **债**：LB01, LB02, LB05, LB06, LB07, LB08, LB03, LB04, R56, R58, R03, R22-parity, R68-parity
- **依赖前置批**：（无，可立即起）
- **为何这批可一起做**：全部=补『我是故意的』中文注释+绑/新建契约测试,跨多个不同文件互不改同一行段,可一次铺齐。这是B02/B05/B11/B13触碰execution_review/navigation_publish/feedback_service/reports_page_support/navigation_context这些高频承重文件前的唯一安全网,不先钉=后续全在『护栏裸奔期』被顺手打穿。含5个子动作:①LB03抢时间窗(守卫测试untracked,立即git add四治理文件+regression_scheduler_plan_identity_summary_guardrail.py,防并行git clean删);②LB01/LB02/LB05/LB06共享盲区=新增GET /reports/execution-review?plan_role=非adopted&scenario_id=X 服务端拒绝/回退adopted请求级负向回归(一次补齐三条precondition);③LB07扩regression_scheduler_config_spec_sync_contract.py覆盖R71三helper行为parity;④LB04新建boolean_normalize↔matrix等价契约;⑤R22 parity(全VALID_PLAN_ROLES断default_plan_resolution_dict['plan_identity']==build_plan_identity(source_table='schedule').to_dict())、R68 parity(两路_meta_bool_state对同一meta含parse_failed位一致)。R03/R58/LB08注释同入此批。
- **验收**：现有契约全绿(regression_reports_workbench_navigation_contract/scheduler_workbench_link_guardrails/plan_vs_actual_review/operation_execution_feedback_routes:336/exception_feedback:485/event_foundation:272/user_visible_messages);新增execution-review请求级负向回归通过;LB07 spec-sync三helper parity绿;LB04等价契约绿;R22/R68 parity绿;守卫测试已git跟踪;git diff仅注释+测试、零生产逻辑改动。

### Batch-2 B01 guard字段收口(N1唯一真相源·单债独立成批)
- **债**：R54
- **依赖前置批**：Batch-1
- **为何这批可一起做**：把plan-guard字段收口进【已存在】build_workbench_plan_context(scheduler_workbench_links.py:183-251),内部从单一来源plan_role_filter_fields(schedule_result_view_context.py:277)产出全集guard字段,让【4套】手维列表(含报告漏列、盘上坐实的第4套dashboard_workbench.py:19-24)统一delegate。这是R42/R60(删plan_id形参)与R44(navigation_publish)的签名地基,必须独立先落、原子完成SCC-NAV 5-6文件。dashboard那套的plan_identity_error保留dashboard本地来源单独merge(非guard字段)。
- **验收**：4个guard契约绿(navigation_contract guard-fields 11键/resource_dispatch site_records blocked_fields/link_guardrails下游逐键/dashboard_workbench);4套手维列表全delegate到收口点,grep确认无残留独立key列表;is_comparison/is_superseded_by_newer_version仍齐全(fail-closed不退化)。

### Batch-3 B01 plan_id整链下线+死码清理(SCC-NAV结构)
- **债**：R42, R60, R62, R66, R07, R08, R57
- **依赖前置批**：Batch-1, Batch-2
- **为何这批可一起做**：全部rebase在Batch-2的build_workbench_plan_context新签名上。R42+R60合并为单次plan_id下线(共享link_query:118/154,只删一边=半截残渣);R62压扁execution_review三档死分支(绝不碰:112/123/153/166-167 ROLE_ADOPTED硬钉);R66纯删死_context_summary(按完整签名定位,勿误删workbench_links:254 LIVE同名);R07改loud raise(补AppError/ErrorCode导入);R08删死开关分支(保feedback_write_enabled参数);R57双路径默认补注释(保:80-82强制adopted)。此批还稳定resource_dispatch_execution_service.py/scheduler_resource_dispatch_execution.py两文件供Batch-6的R09迁_positive_int。
- **验收**：navigation_contract:109/122/126三plan_id断言同步退(保back_to:123/127);roadmap制度化3处(items.yaml:289+acceptance.md:52+checklist.yaml:82)同步删;execution_review模板:131-136死副行+xlsx:410-415死回退退;R07新增NOT_FOUND raise回归;R57 flow-contract:385 home_query['plan_role']==['baseline_best']透传断言绿;SP05拓扑绿;navigation_context.py:80-82 forced-adopted未被碰。

### Batch-4 B02 plan_role取参+方案身份收口
- **债**：R21, R22, R23, R44, R72
- **依赖前置批**：Batch-1, Batch-2, Batch-3
- **为何这批可一起做**：方案身份收口族。R23最先(独立零风险,query_service复用model._normalize_role,绝不动resolve_plan双段语义);R22委托build_plan_identity+to_dict(parity已在Batch-1,内层委托最小止血);R21删3个真死shim但【保留】default_plan_resolution_dict wrapper(R22遗留文案precondition依赖)+保留range系LIVE函数;R44照搬gantt_plan_query:46 re-export范式收口到core selected_plan_role(Phase1#5纠偏:core更严格,收口只增强);R72提到web/scheduler_utils.py(读flask request,绝不下沉core)。必须在B01改完navigation_publish之后。
- **验收**：schedule_result_view_context parity绿(全VALID_PLAN_ROLES);gantt_plan_query遗留文案wrapper『未知的排产方案角色:bad』保留且test绿;navigation_contract publish_*绿;candidate_plan_query/plan_identity_evidence绿;_PLAN_GUARD_FIELD_NAMES/_plan_guard_fields闸门路径未被碰。

### Batch-5 B03 config双栈+adapter+B04 enum收口
- **债**：R45, R48, R71, R47, R41
- **依赖前置批**：Batch-1
- **为何这批可一起做**：不同文件群,内部冲突自由。R45+R48锁为单次整文件删config_adapter.py(27行,非两条债)+同提交退sp06:15 NO_CFG_GET_TARGETS路径;R71受LB07 parity前置,owner裁决物理收敛(service反向import model三helper下行)vs仅parity锁定;R47双栈对称删raw_value死参数(model coercion:88+155/210与service config_field_coercion:68+158/207,两栈必须对称同删,Phase1#4纠偏);R41枚举收口到enum_normalizers(6符号)+把test_enum_display_consistency:59/61钉死的静默改loud暴露断言(受owner语义裁断门控)。绝不碰coercion:470承重置零/:152-153 loud raise。
- **验收**：sp06 NO_CFG_GET_TARGETS退config_adapter路径同提交;spec-sync扩展parity绿、py38 contract绿、projection_sync绿;coercion:470/:152-153承重未被碰;test_enum_display_consistency坏ready/operator改为loud暴露断言绿(符合灵魂线)。

### Batch-6 B05正整数/解析收口+R01死链(parse-int互锁)
- **债**：R04, R09, R28, R59, R01, R29-KEEP
- **依赖前置批**：Batch-1, Batch-3
- **为何这批可一起做**：桶内地基F最先(纯增量):F1给strict_parse.parse_required_int/optional_int+底层_parse_finite_int加reject_integer_float严格模式(min_value已有);F3新建core/shared parse_optional_positive_int(R09专用,垃圾/非正→None,字节对齐现3副本,严禁复用R04的parse_finite_int因契约相反)。然后:R04收口_strict_positive_int(委托扩展后strict_parse+本地ValidationError→ValueError适配保6个except,两哨兵永不动);R59委派parse_required_int(reject_integer_float=True,保:44-47 blank短路)——必须等F1否则撞自身'1.0' raise测试;R09迁3处字节同体(须在Batch-3稳定两文件后);R28收口parse_finite_float(allow_none=True,垃圾raise);R01删count/has死簇+SP05:54-55(同schedule_payload_contract.py与R04不同区域)。R29=KEEP不写代码(授权CSV盘上不存在,见owner裁断)。
- **验收**：web_silent_fallback:67/70绿('1.0'/1.0仍raise);persistence_reject_empty绿;resource_dispatch四契约绿;test_architecture_fitness:77 R28白名单同步退;SP05:54-55 R01两符号断言退;parse_optional_positive_int(垃圾→None)与parse_finite_int(垃圾raise)契约相反未混用。

### Batch-7 B06 datetime收口+dispatch死码+compat半截
- **债**：R15, R49, R51, R50, R33, R30, R31-shared
- **依赖前置批**：Batch-1, Batch-6
- **为何这批可一起做**：dispatch_rules.py三债(R49:25死别名/R51:28宽容解析器/R50:112 mean_positive)必须同批删避免行号互撞(盘上证三行号);R50从B05迁入此批(纠正Phase1 Batch-6债清单与Batch-7推理的内部矛盾);R51删解析器须连退regression_dispatch_rule/sort_strategy_case_insensitive.py(它们钉死灵魂线禁止的兜底,严禁保留续命)。R15逐处收口datetime(provider:66/state_builder:42的None版vs support:226的raise版分清,严禁一刀切),作为SCC-EXEC-FACT串行链最前置(先于Batch-12/Batch-14动同3文件)。R33步骤1迁测试import到core.shared→R30删shared date实现(硬顺序);R31 shared源侧:9 WRITE_INTERNAL_ONLY折叠进R30同文件value_policies.py编辑(补Phase0§3漏记的R30↔R31同文件边),common侧随R33删整facade吞并。
- **验收**：feedback_support:226 raise语义保留;dispatch_rule/sort_strategy_case_insensitive测试随解析器退(不续命);value_policies_matrix start/end断言退;compat_parse degradation date用例退;config_service_component_contract:411 parse_compat_date身份断言随R30删(保:408-409 strict_parse活兄弟);exec-fact三文件与B11/B13无行号冲突。

### Batch-8 B07资源筛选collar(team-extend先行)
- **债**：R05, R67
- **依赖前置批**：Batch-1
- **为何这批可一起做**：R05分3原子小步严格串行:步1给ScheduleResourceFilter/normalize_schedule_resource_filter扩team双join谓词接口+放开『类型有/id空=全量』语义→步2补team≠全量+空id可查负向回归(纯增量钉反例)→步3收口点验证绿后才收敛repo:451-463与schedule_repo:141-153字面量。R05是Batch-13 R34的前置(软约束:R34实为纯删死方法,被删method零生产引用、活孪生自带team过滤,故R05→R34的『收敛column_name丢team』原措辞对纯删失效,但保留批次先后零成本)。R67抽REPORT_RESOURCE_FILTER_ARG_KEYS单一常量到report_context_filters.py,纳入盘上发现的第4处(scheduler_navigation_links.py:22-27,superset解包改造不整元组替换,R54-style漏列教训)。
- **验收**：新增回归:scope_type=team只返回该team、空id全量视图可查;schedule_plan_query_repo:461-463 team双join与空id全量分支保留;report_context_filters collar别名优先级契约绿;invalid_query_cleanup:341直调_normalize_scope_type绿。

### Batch-9 B08关键链甘特(SCC-GANTT:统一→加键)
- **债**：R11≡R63, R12, R55, R10
- **依赖前置批**：Batch-1
- **为何这批可一起做**：R11≡R63是同一债(Phase1#1#2纠偏:两份_normalize_critical_chain_result逐字复制,support:32-51/provider:104-128),合并为单个work item先抽单份到gantt_critical_chain.py公共落点(绝不简化为return raw);再R12加dropped_count/critical_chain_partial(保留:84过滤,DegradationCollector范式)、R55加scope=filtered/full(调用点显式置值非静默推断),二者新键同穿三道白名单(support:32-51/provider:104-128/contract:19-40)。R10(桶B14)删gantt_service.py:60-62死方法,与R55(:375)同gantt_service.py跨桶同批(纠正:R10批次=Batch-9非Batch-14)。自成簇不阻塞他桶。
- **验收**：gantt_contract_snapshot subset检查绿(加键不破);critical_chain_unavailable降级契约绿;新dropped_count/scope键端到端不被归一层剥离(穿三白名单验证);:84过滤未裸删;gantt_service.py R10删除+week_plan stub:59退。

### Batch-10 B09图死版+空包(V22打包簇)
- **债**：R02, R25≡R52, R06, R27
- **依赖前置批**：Batch-1
- **为何这批可一起做**：R02删test-only re-export包装器(关键:test_graph_dispatch_context.py:10-15四符号import块须拆分,只迁build_first_wave_ready_nodes,另三符号留dispatch_context);R25(service垫片)+R52(算法impl)同提交删,但必须先迁test_ready_queue.py约23个LIVE sgs_graph测试+三条ValidationError契约到sgs_graph自有测试文件(绝对排除裸删整test文件)+摘lazy_runtime:27/metrics_topology:140枚举名;R06(桶B09 dispatch/__init__)+R27(桶B14 calendar+batch)+gantt空包经V22强制4空包同提交删+改SP05:310元组/:315-316 delayed循环块(R27跨桶批次=Batch-10非Batch-14)。
- **验收**：SP05 path topology绿(:310元组/:315 delayed循环摘4包);graph测试绿(test_graph_dispatch_context import改home);test_ready_queue LIVE覆盖迁移后绿、lazy_runtime/metrics_topology枚举摘名;R52删前确认sgs_graph ValidationError已逐条覆盖原合同点(灵魂线底线)。

### Batch-11 B10错误体制死别名
- **债**：R46
- **依赖前置批**：Batch-1
- **为何这批可一起做**：LB08承重注释已在Batch-1。R46删scheduler_public_errors.py:162-164三行死别名_safe_identifier,纯叶子弱耦合,严格不碰LEGACY正则桥/make_public_error/活的public_safe_identifier(:142,8处生产消费)。Batch-1后任意时点可落。
- **验收**：user_visible_messages全套绿;LEGACY_PUBLIC_PATTERNS:62/_LEGACY_CODE_PREFIXES:94/legacy_public_error_message:218/infer_legacy_public_code:284未被碰;删除范围严格:162-164三行,保PEP8两空行间距。

### Batch-12 B11执行诊断死码(SCC-EXEC-FACT串行)
- **债**：R17, R13≡R18, R16, R14, R24
- **依赖前置批**：Batch-1, Batch-7
- **为何这批可一起做**：R17先做(纯3行删,依赖且仅依赖Batch-1 LB01注释已落,清掉feedback_service死导入缩短承重文件打开窗口,绝不碰:347-354/451-453);R13+R18同一原子提交(event_repo相邻方法:254/:260+foundation相邻断言:172/173,R13删后:254成死码连带删,各清孤儿import);R16删state_builder死表:33-39+清5个EXECUTION_STATUS_*孤儿import(简化:77后严禁加or默认兜底);R14/R24放最后(先迁灵魂线测试+认账roadmap再删):R14迁:328候选断言到resolve_existing_plan直断言(非改指生产门LENIENT会静默弱化)+改aps-three-gap roadmap;R24调和networkx PR-9 roadmap(items.yaml:435/480-481)再删core,铁律绝不反删web孪生(独占NonFiniteDiagnosticNumber护栏)。exec-fact三文件已被Batch-7 R15先动,本批rebase。
- **验收**：delay_diagnosis灵魂线:328/:358迁resolver层后绿;analysis_diagnostic core-only用例退、web孪生护栏保留;event_foundation:172/173相邻断言退;feedback_service:347-354/451-453未被碰;roadmap aps-three-gap+networkx items.yaml同步修订。

### Batch-13 B12 repo死方法(按文件聚批)
- **债**：R36, R37, R38, R39, R34, R35
- **依赖前置批**：Batch-1, Batch-8
- **为何这批可一起做**：风险升序+同文件聚批:R36(batch_operation_repo)/R37(operator_machine_repo,紧盯活近亲list_links_with_operator_info:92勿误删)纯死隔离叶子先清;R38三处list_as_dicts结构同形非字面同体(Phase1#10纠偏,三处各自直删勿抽helper)+R39同part_repo.py子批;R34三死方法(:36/:114/:128)+R35(:61夹其间)同schedule_repo.py子批同提交(避免行号二次漂移),R34退4件套+benchmark repoint+清R34的失效monkeypatch(Phase1#9)。软排在Batch-8 R05之后(零成本,因R34实为纯删,R05→R34硬依赖对纯删失效)。
- **验收**：facade_delegation退:31/:36/:38-41三死方法断言、保:33/:37活方法;detail_queries用例退;gantt_critical_chain_unavailable:59无效monkeypatch删;benchmark_fjsp:503 repoint;全删后grep确认零生产引用。

### Batch-14 B13 facade残渣(全局最晚)
- **债**：R43, R20, R26, R19
- **依赖前置批**：Batch-1, Batch-6, Batch-7, Batch-10, Batch-12
- **为何这批可一起做**：§10.2 facade删除晚于B05/B06/B09收敛。R43最独立(仅需认账roadmap:522延期+迁15个test-only import到domains叶子路径+改SP05三ROUTE_*区块);R20删labels垫片须在Batch-1 LB01注释后改feedback_service:48 import(与Batch-12 R17同文件协调,绝不碰承重段);R26删config/summary 5 shim(先迁2离线脚本capture_networkx_phase0_baseline:17+20260316_audit_probes:87+71测试import+SP05:21-82/642-658,前置=B05/B06/B09收敛闸门);R19受循环导入+分层红线双重阻断,owner裁收口落点(推荐下沉core/models/operation_execution_event.py,保sorted指纹),须Batch-7 R15/Batch-12 R13·R18在两共享文件先动。R31 shared源侧若未在Batch-7折叠则此批收尾。 【消歧·采纳Phase3核查must_fix】R31已完整折叠进Batch-7(与R30同改value_policies.py),本批不再含R31,避免据本批成员二次派工撞R30行号。
- **验收**：SP05冻结面同步(strong/behavior compat列退);71测试import repoint+2离线脚本迁移;lazy_runtime绿;R19 provider收口保sorted指纹、repo不引入越层(test_architecture_fitness绿);R43 wrapper_import_order_contract整文件退+ROUTE_COMPAT/BEHAVIOR/REAL_ROUTE_FILES改;config_snapshot.py跨桶边(R26↔R71)标误报、不串行化。

### Batch-15 B15逐字两份收口
- **债**：R70, R68, R69
- **依赖前置批**：Batch-1
- **为何这批可一起做**：R70先(零前置纯死副本直删schedule_service.py:46-50,Phase1#11坐实非twin,不删input_collector:79 live份,不删:7 ValidationError import因:217仍用);R68等Batch-1 parity后收口到summary_count_parse.py(灵魂线:严禁压扁(bool,bool)二元组、严禁丢parse_failed位);R69收口单点+护栏内坏seq改loud(严禁静默归0,owner裁收口家schedule_input_contracts vs新建op_keys+异常类型AppError vs ValueError)。三条不同文件可并行。
- **验收**：R68两路used_default对同一meta含parse_failed一致(parity绿);R69收口后坏seq不再静默归0(护栏loud/可观测);R70 facade_delegation不依赖该符号故直删死副本不红;history_not_created/empty_reschedulable_rejected绿。

### Batch-16 B16 P4灵魂线+B17死叶子(独立并行)
- **债**：R32, R40, R53, R61, R64, R65
- **依赖前置批**：Batch-1
- **为何这批可一起做**：全部独立隔离文件、无关键路径门控。R32 backup.py:335 integrity except→raise(对齐:340 else,无法校验=不可信备份绝不os.replace,+顺手system_backup:107-113 flash清晰错误);R40 material_repo:70-72删except吞咽让float()抛原生ValueError(灵魂线,owner裁错误分类);R53只删batch_order.py:74一行(勿误删sgs.py:127同形非本债);R61删filter_plan_rows死簇(:160-187盘上修正行号)+两负向测试重定向到normalize_report_resource_filter(保filter_downtime孪生:190-293);R64删:66-67;R65原子三件套(删def:74-78+:160化简为plain_url+删:4/:6孤儿import,否则NameError)。R64+R65同文件原子提交。
- **验收**：restore_success_condition mock不触达校验块故R32改raise不红;R40 numeric_parse_hybrid model护栏未碰;report_context_filters downtime孪生:28/39/51/59保留、plan份退;scheduler_navigation_links build绿(:160化简无NameError);R53 batch_order行为契约绿。

## 3. 跨桶打架定调（Phase 1 的 16 条回代码纠偏 + Phase 2/3 新增，共 20 条）

| 涉及债 | 冲突 | 定调 |
|---|---|---|
| R11, R63 | Phase0§9把R11/R63列为B08两个独立桶成员,各自投工。 | 采纳Phase1#1#2纠偏:R11≡R63是同一条债的两条记录(两份_normalize_critical_chain_result逐字复制),Phase3 master plan合并为单个work item一次抽单份helper同时消除,排期工具绝不当两条派工撞改同两文件。R11『未提交(A)』记述过时,以R63『已提交P5』为准。 |
| R54 | 报告location只点名3套plan-guard手维列表,投工范围按3套算。 | 采纳Phase1#6纠偏+盘上复证:存在第4套dashboard_workbench.py:19-24(12键,含plan_role_status/can_write_feedback/plan_identity_error)。R54收口范围必须纳入第4套,漏则fail-OPEN旧正式版本冒充现行采用方案;但dashboard的plan_identity_error是本地错误标记(dashboard.py:121设)非guard字段,delegate后保留本地来源单独merg |
| R29 | 报告引以为据的权威裁定L3_verdicts.csv:174=KEEP/high,经ls复核整目录盘上不存在,仅REPORT.md自引用。 | 采纳Phase1#3纠偏:R29授权链断裂,Phase3独立重裁=KEEP现状不写代码(薄壳化零生产收益+击穿绿facade测试+裁断需项目记忆),上交owner拍板『有意delegation-facade vs半截迁移残渣』。绝不照搬不存在的CSV,也不单方推翻。 |
| R47, R71 | 报告why_debt称『服务侧孪生没有raw_value参数』,按单边删处理。 | 采纳Phase1#4纠偏+盘上复证:service config_field_coercion.py:68同样声明raw_value、调用点:158/207同样传入,是双栈对称死参数。R47必须两栈对称同删(model:88+155/210与service:68+158/207),只删model侧会加大R71/LB07要消除的逐字分叉。 |
| R44 | 报告称web版selected_plan_role多加or ROLE_ADOPTED兜底,担心统一会改变缺selected_role时角色。 | 采纳Phase1#5纠偏+盘上逐字复核:core schedule_result_view_context.selected_plan_role(:201-202)更严格(还处理plan_resolution=None),两版同ROLE_ADOPTED常量。报告方向反了,收口到core只保持或增强行为。 |
| LB06 | 报告称写死adopted『污染复盘行数据』且location写:366/:368。 | 采纳Phase1#7纠偏:行数据因core不收参恒adopted,真正承重=显示标签身份+nav-context泄漏+默认日期窗;真实盘上行号:367/:369(报告转录off-by-one)。R42删:86时按符号定位不照搬裸行号。 |
| R26 | 普查证据称config/summary facade『0生产消费』,可直接rm。 | 采纳Phase1#8纠偏:有2个离线非测试消费者(tools/capture_networkx_phase0_baseline.py:17+audit/2026-03/20260316_schedule_audit_probes.py:87)。删shim前必须先迁这2脚本否则ImportError。 |
| R34, R05 | Phase1 DAG把R05→R34设为硬依赖,理由『R34收敛column_name若先于R05扩team会丢谓词』。 | 盘上复证(本轮):R34实为纯删死方法——被删的schedule_repo.list_dispatch_rows_with_resource_context零生产引用(仅def站点),活孪生schedule_plan_query_repo.list_dispatch_rows:430自带team过滤。原措辞对纯删失效。降级为软约束:保留Batch-8(R05)先于Batch-13(R34)的批次先后(零成本),但不再是『收敛丢谓词』式硬阻塞。 |
| R38 | codemap dup_bodies标三处list_as_dicts(op_type:73/operator:85/part:71)为『同体逐字』。 | 采纳Phase1#10纠偏:三处SQL不同(OpTypes/Operators/Parts各异),实为结构同形非字面同体。三处各自直删(各按grep证零引用),绝不为消重抽公共helper(=造零消费活模块违收口点规则);记账上是三次独立删除。 |
| R70 | 报告框R70为『逐字两份均loud raise』的twin需收口。 | 采纳Phase1#11纠偏:schedule_service.py:46那份本文件零调用+不在__all__+非facade委托面=死副本,只有input_collector:79是live。纯删死副本即闭合,无需收口到上游helper(twin框架不成立);误删live份=灾难。 |
| R69 | 报告why_debt写裸『except:return 0』。 | 采纳Phase1#12纠偏:实为typed『except (TypeError,ValueError):return 0』。但坏seq仍静默归0踩P4气味,收口到护栏文件单点时须改loud(严禁静默归0,否则:149漏拦后继工序排到已完工序前)。 |
| R50 | Phase1§4 Batch-6债清单含R50(桶B05),但Batch-7推理文本又写『R50已在B05』『dispatch_rules.py R49/R50/R51同批』——内部自相矛盾;且报告reference_chain写sgs.py:150。 | 盘上复证dispatch_rules.py三债共居(R49:25/R51:28/R50:112)+真路径core/algorithms/greedy/dispatch/sgs.py:150(顶层路径不存在,Phase1#13)。定调:R50批次=Batch-7(随dispatch_rules.py三债同批避免行号互撞),从Batch-6移出。R50无F依赖,迁批零成本。 |
| LB03 | 旧报告+§90 LB-B4起草文案判P4『改loud raise』,且LB-B4描述fail-OPEN容忍语义。 | 采纳Phase1#14纠偏:工作树已超前治理为fail-closed标记(_parsed_summary_flag_is_true(fail_closed=True):141)+可观测字段result_summary_parse_failed。LB03仅需确认四文件入账+git add untracked守卫测试+:141认账fail-closed注释。严禁按旧报告改loud raise(latest_executable_official_version全量扫历史会触发可用 |
| R12 | 报告把:84丢坏时间行当活跃P4灵魂线缺口需补可观测。 | 采纳Phase1#16纠偏:scenario写入经gantt_adjustment_projection:143/164校验st<et,Schedule/候选NOT NULL+引擎写入,:84分支近死。仍按灵魂线合规补dropped_count/critical_chain_partial留痕(低投入),但owner确认投入量级——不为不可达路径过度投工。 |
| R03, R52, R55, LB08 | Phase0§6明示这4条needs_adversarial=True但verdict数组未收录独立结论(标题未精确匹配),无现成对抗结论可依赖。 | 各桶owner额外谨慎复核当下债vs在途中间态:R55(呈现失真只补scope标记不可裸砍过滤)、R52(差分oracle保留vs收,绝对排除裸删test_ready_queue)、R03(narrow-except只补注释绝不改except Exception)、LB08(只补注释绝不删正则桥)。均不依赖现成verdict,落地走最保守方向。 |
| R30, R31 | Phase0§3跨桶同文件边表只记value_policies.py的R31↔R33,漏了R30(B06)。 | 盘上复证core/shared/value_policies.py同时含R31的WRITE_INTERNAL_ONLY(:9)与R30的VALUE_DATE/VALUE_DATETIME/READ_FILTER_ONLY(:12-17)+due_date策略(:180+)。补这条漏记边:R31 shared源侧:9删除折叠进Batch-7 R30的同文件value_policies.py编辑(R31 common侧已随R33同批),从而R31完整落在Batch-7,不再留尾巴 |
| R26, R71 | Phase0§2/§3把config_snapshot.py列为R26(B13)↔R71(B03)跨桶同文件边,要求串行化。 | 盘上复证是basename假碰撞:存在两个不同物理文件——core/services/scheduler/config_snapshot.py(R26顶层shim)与core/services/scheduler/config/config_snapshot.py(R71深实现,经schedule_config_runtime_read.py:68关联后者)。Phase3标此§3边为误报,R26与R71不动同一物理文件,绝不无谓串行化(R26→Batch-14,R71→Bat |
| R01, R10, R27, R03 | 四条债桶=B14,直觉上应同在『Batch-14』,易被排期工具误聚。 | 定调:B14无内部硬依赖,落地批次由跨桶同文件邻居决定,与桶标签解耦——R01→Batch-6(随R04同schedule_payload_contract.py)、R10→Batch-9(随R55同gantt_service.py)、R27→Batch-10(随R06 V22同提交)、R03承重注释→Batch-1/下游脚手架→DEFER。Batch-14实际只含B13五债,不含任何B14债。 |
| R67 | 报告/pack只点名3处资源别名清单,漏列第4处。 | 盘上发现疑似第4处scheduler_navigation_links.py:22-27(R54-style漏列同型):16键passthrough superset元组里嵌同样6个资源别名键。R67收口纳入第4处,但须superset解包改造(不可整元组替换,否则压扁丢plan_id/scenario_id/日期)。owner确认纳入。 |
| R72, R44 | Phase1跨债边写『R72/R44宜同收口到scheduler_utils.py一个公共helper』,但R44的verdict要求selected_plan_role收口到core。 | 分层裁断:二者本质不同落点——R72的_get_plan_role_arg读flask request.args属请求层、core无孪生、下沉core破AST分层红线→收口web/scheduler_utils.py;R44的selected_plan_role读plan_resolution dict、core有canonical孪生→收口core re-export。绝不硬塞同一落点(否则给selected_plan_role造web第二落点=新P5)。N1真正消解=各回 |

## 4. 前置门清单（18 条「先做 X 才能做 Y」）

| 前置门 | 阻塞 | 属于批次 |
|---|---|---|
| F1: 给core/shared/strict_parse.parse_required_int/parse_optional_int及底层_parse_finite_int加reject_integer_float严格模式(min_value已有),拒'1.0'/3.0整值float。纯增量。 | R04, R59 | Batch-6(桶内最先,先于R04/R59收口) |
| F3: 在core/shared新建唯一批准的新收口点parse_optional_positive_int(垃圾/非正→None,字节对齐现3副本契约,严禁复用R04的parse_finite_int因契约相反)。盘上已确认该符号不预先存在。 | R09 | Batch-6(先于R09迁3处字节同体) |
| LB07 parity: 扩regression_scheduler_config_spec_sync_contract.py覆盖model↔service两栈三helper(_float_matches_choice/_normalize_valid_texts/_coerce_degradation_event)行为等价断言+两栈snapshot类定义上 | R71, R47 | Batch-1(先于Batch-5任何物理收敛) |
| R22 parity: 对全VALID_PLAN_ROLES断言default_plan_resolution_dict(role)['plan_identity']键集+取值==build_plan_identity(source_table='schedule').to_dict();测试文件头钉注释『删除=放任失忆债复发』。 | R22 | Batch-1(先于Batch-4 R22收口) |
| R68 parity: 断言两份_meta_bool_state对同一(meta,key,default)矩阵输出完全一致【含parse_failed位】。 | R68 | Batch-1(先于Batch-15 R68收口) |
| LB04等价契约: 新建绑死boolean_normalize.normalize_yes_no_wide↔normalization_matrix.normalize_yes_no_wide_value两套语义等价的回归(同wide别名集/是否短路/None→default/空串→NO/四分支),+:33 def上方钉分层承重注释。 | R41 | Batch-1(LB04属安全网范式,R41在Batch-5后落) |
| execution-review请求级负向回归: 新增GET /reports/execution-review?plan_role=非adopted&scenario_id=X服务端拒绝/回退adopted,一次补齐LB02/LB05/LB06三条precondition(service级断硬钉adopted+页路由级断标签/nav/默认日期窗仍adopt | R62, R42, R57 | Batch-1(先于Batch-3结构动作) |
| R54 guard真相源: build_workbench_plan_context承载guard字段、4套手维列表(含第4套dashboard_workbench)统一delegate到plan_role_filter_fields全集。 | R42, R60, R44 | Batch-2(先于Batch-3 plan_id下线rebase签名+Batch-4 R44动navigation_publish) |
| R05收口点扩容: 给ScheduleResourceFilter/normalize_schedule_resource_filter扩team双join谓词接口(产出sql_fragment+params)+放开『类型有/id空=全量』语义+补team≠全量/空id可查负向回归。 | R34 | Batch-8(软先于Batch-13 R34,因R34实为纯删故降级软约束) |
| R33步骤1: 把regression_compat_parse_emits_degradation:18/regression_value_policies_matrix:18两测试import从core.services.common迁到core.shared承重点。 | R30 | Batch-7(R33步1先于R30删core.shared date实现) |
| R11≡R63统一: 抽单份_normalize_critical_chain_result到gantt_critical_chain.py公共落点,support/provider两路改调它(逐字保留归一行为,绝不return raw)。 | R12, R55 | Batch-9(先于R12/R55在单helper上加键穿三白名单) |
| R25/R52测试迁移: 把test_ready_queue.py约23个LIVE sgs_graph测试+三条唯一ValidationError契约迁到sgs_graph自有测试文件,6处差分oracle断言转直接期望值;绝对排除裸删整test文件。 | R25, R52 | Batch-10(删impl+shim前) |
| R02 import拆块: test_graph_dispatch_context.py:10-15四符号import块拆分,只迁build_first_wave_ready_nodes,build_predecessor_successor_maps/graph_score_weights留dispatch_context(整块挪会ImportError) | R02 | Batch-10(删包装器前) |
| R14灵魂线测试迁移: 把regression_scheduler_delay_diagnosis_contract:328候选无静默回退断言迁到resolve_existing_plan直断言(非改指生产门LENIENT会静默弱化)+改aps-three-gap roadmap items.yaml。 | R14 | Batch-12(删死三件套前;owner裁断迁移目标) |
| R24 roadmap调和: 改networkx PR-9 items.yaml(:435 primary_path移除+:480/:481 exit_checks摘core文件名保web helpers)再删core schedule_diagnostic_contract,铁律绝不反删web孪生。 | R24 | Batch-12(删core前) |
| R43 roadmap认账+import迁移: 认账或修订p1-scheduler-debt-cleanup-roadmap.md:522延期决定(抢跑需owner批准)+迁15个test-only import到domains叶子路径+改SP05三ROUTE_*区块。 | R43 | Batch-14(删9 wrapper前) |
| R26三桶收敛闸门+迁移: 等B05(R29)/B06(R33)/B09(R52)收敛完成(判定信号=对应batch验收全绿且老顶层路径无测试依赖)+迁2离线脚本+71测试import+改SP05:21-82/642-658。 | R26 | Batch-14(全局最晚,§10.2) |
| LB01承重注释先落: feedback_service.py:451消毒层+:348硬拒分支钉『故意忽略context、勿透传』注释,确立护栏可见。 | R17, R20 | Batch-1(先于Batch-12 R17删:12 import+Batch-14 R20改:48 import,二者同文件) |

## 5. 承重护栏先落专章（整个计划的地基）

承重护栏先落是整个计划的地基,原因是脊梁结论:B01承重文件(execution_review/navigation_publish/feedback_service/reports_page_support/navigation_context)恰恰是B02(R44)、B05(R07/R08/R09)、B11(R17/R20)、B13(R20/R19)都要反复触碰的高频文件。如果不先把『哪段是承重、绝不可碰』用注释+契约钉死,这些后续批次就在『护栏裸奔期』作业,一次手滑就把纵深防御打穿成fail-open(旧正式版本/候选/模拟方案冒充现行采用方案放行写入与派工)。故Batch-1全部=纯增量(注释+契约/parity测试),零生产逻辑改动,是后续所有收敛/删除的安全网。统一红线口径:8条LB+R56/R58/R03一律只能①补『我是故意的』中文注释(§90已起草文案,LB03/LB08两条文案需owner更正后用)+②绑/认账契约测试,严禁删/合并/统一/透传参数;LB04唯一合法消重=上层matrix反向delegate到下层boolean_normalize(services→shared下行),绝不能删shared改指services(立刻造core.models→core.services越层+导入环,破AST 0违规)。逐条门控关系:【LB01】feedback_service.py:347-354硬拒+:451-453写死消毒——门控R17(B11删:12死导入同函数_build_event_payload,PHASE0§3最危险的边)与R20(B13改:48 import),二者删import时绝不碰这两段。【LB02≡LB05】execution_review.py:141故意不对称签名(不收plan_role/scenario_id)+:112/123/153/166-167硬钉ROLE_ADOPTED——门控R62(同文件清三档死分支绝不碰硬钉、更不给:141加形参),一次注释满足两finding。【LB06】reports_page_support.py:367/369(off-by-one纠偏)+navigation_context.py:80-82 forced-adopted——门控R42(删:86 plan_id绝不碰:80-82)、R56、R57(双路径收敛必须保留:80-82强制adopted)。【LB03】plan_identity_builder已超前治理为fail-closed,仅需确认四文件入账+立即git add untracked守卫测试(时间窗最紧,防并行git clean删)+:141认账注释;STALE警示:严禁按旧报告/§90 LB-B4改loud raise(会引爆latest_executable_official_version全链可用性放大事故)。【LB07】config双栈ScheduleConfigSnapshot(model栈为源,分层强制的双实现)——门控R71/R47(parity先于收敛,扩spec-sync三helper等价断言+两栈注释先落,否则锁步守卫缺位静默漂移踩灵魂线)。【LB08】scheduler_public_errors.py LEGACY正则桥:62/94/218/284+make_public_error:175——门控R46(删:162-164死别名严格不碰正则桥),注释钉『文案与正则同生共死』(文案产出点指向需owner更正为greedy三文件)。【R56】navigation_context.py:42-47靠endpoint/path字面量匹配钉execution_review强制adopted,零注释最脆弱——门控R57及co-located R42,真正rename守卫=regression_plan_vs_actual_review:350-359必须绑牢。【R58】navigation_publish.py:86 context.update覆盖builder已gate的can_write_feedback——门控R44(同文件),默认只补注释,结构剔除(可选)在Batch-4与R44/R54协调。【R03】runner.py:216 narrow-except(防b81f8b3f删掉的静默吞错复活)——不在§90预起草名单但Phase1判为verdict-confirmed承重,只补注释绝不改except Exception。【R05】verdict=load_bearing,schedule_plan_query_repo:461-463 team双join+空id全量是column_name单列表达不了的承重第三轴,塌缩=班组静默失效/整页500——门控R34,必须先扩收口点再谈收敛。【N1=R54】high+load_bearing,虽在Batch-2(不在Batch-1注释网),但它确立build_workbench_plan_context为全站唯一guard真相源,是R42/R60/R44的签名地基,4套手维列表(含漏列第4套)delegate的前提。

## 6. 需 Owner 拍板的决策（19 条）

1. R29重新裁断(授权链断裂):报告据以判KEEP/high的.codestable/refactors/2026-06-01-test-gate-cleanup/整目录盘上不存在。本agent独立重裁倾向KEEP+补显性『刻意delegation-facade』注释(薄壳化零生产收益+击穿绿测试+裁断需项目记忆);但『common/number_utils是有意双份还是4/5半截迁移漏改残渣』需有项目记忆的owner拍板:KEEP还是走协调式收敛(须先重写facade测试为身份测试)。
2. R55设计意图(无独立verdict):filtered关键链补scope标记的呈现修法二选一——(a)仅补后端scope=filtered/full+前端标注『筛选视图』(推荐,PHASE0§7 mandated方向),还是(b)filtered时关键链/makespan直接置unavailable(reason='filtered_view')更诚实但改变既有显示。建议(a)。
3. R03下游FAILED脚手架(无独立verdict):failed_candidate_count/baseline_missing_or_failed一路传到dashboard_workbench:231+candidate_helpers:324-329恒-0/恒-False分支——是『为持久化schema enum(v10.py:14 CHECK)保留的防御契约面』(留着+补不可达注释)还是『纯不可达死脚手架』(连枚举面收敛)?倾向保留枚举面(DB CHECK是硬底,删CANDIDATE_STATUS_FAILED破往返),但viewmodel恒-False分支补observability注释vs完全不动需拍板。此项DEFER不分配批次。
4. R43 roadmap抢跑:p1-scheduler-debt-cleanup-roadmap.md:522明示『先保留旧wrapper避免冲击启动链』的延期决定。现在删=抢跑该决定(流程非安全问题),须owner把该行改为『已收口』或显式批准提前;否则R43标记『计划已备、执行待roadmap放行』。
5. R54收口点形态:build_workbench_plan_context(web/viewmodels层)接收guard字段的入参形态——加显式guard入参vs接plan_resolution dict整体?且确认web→core调用plan_role_filter_fields(core/services层)方向不撞分层红线(应合法,web最上层)。+第4套dashboard的plan_identity_error保留dashboard本地来源单独merge(确认不算收口不彻底)。
6. R71物理收敛方向:R71三helper是LB07(load_bearing)双栈锁步配料表,红线2规定load_bearing只补注释+契约。R71自身load_bearing=false但related=LB07。是否真物理收敛(service import model删副本,需跨模块import私有helper代码味)?建议鉴于helper trivial+双栈分层强制,最稳=仅扩parity锁三helper等价不做物理收敛,R71降级为『守卫补齐』。owner在Batch-1后/Batch-5前拍板:物理收敛vs仅parity锁定。
7. R72 vs R44收口落点分层裁断:不应硬塞同一落点(Phase1跨债边字面误导)——R72的_get_plan_role_arg读flask request属请求层、下沉core破分层→收口web/scheduler_utils.py;R44的selected_plan_role有core canonical孪生→收口core re-export。owner确认采纳此分层裁断,否则按字面同塞scheduler_utils给selected_plan_role造web第二落点=新P5。
8. R22委托深度:内层委托build_plan_identity+外层保留并加parity守卫(最小止血,已发生的漂移result_summary_parse_failed/reason就在内层)vs内外全量委托SchedulePlanResolution.to_dict(彻底但no_history场景须构造完整Resolution,回归面大)。倾向最小止血优先。
9. R41语义裁断4项:①operator inactive『停用/休假』→『停用』(收口方向)还是反向对齐canonical(连带改导出personnel_excel_operators:347);②ready未知/None正确呈现口径(『未知』or原值暴露,test:59/61改loud暴露而非删了重钉静默);③_source_zh外协/EXTERNAL大写归一(收口source_type_label治误判自制);④day_type空串保留''→'-'(不收空串分支)vs接受''→'工作日'。+范围外二符号batch_status_zh/_merge_mode_zh在enum_normalizers无对应label,新建=红线3禁止,默认划出R41范围除非owner批准受控例外。
10. R15坏值语义升级+能力缺口:①坏时间收口到parse_optional_datetime直接raise(最简,blast称上游约束不易触发)vs改DegradationCollector可观测降级标记(read侧不中断留痕)?决定R15是纯P5还是带P4式降级;②state_builder:42 _parse_time先调datetime.fromisoformat,而strict_parse收口点不含fromisoformat,带微秒/时区ISO串收口后从可解析变抛错——(a)把fromisoformat纳入strict_parse集中化(改公共收口点需评估其它消费方)vs(b)确认event_time所有写入方都经3-fmt strptime校验从而fromisoformat分支安全可丢。未裁定前R15的state_builder部分不动手。
11. R52差分oracle去留(无独立verdict):方向A收(删全量版get_ready_operation_ids+R25垫片,但必须先迁约23个LIVE sgs_graph测试+三条ValidationError契约到sgs_graph自有测试)vs方向B保(留作incremental-vs-fullscan差分oracle+显式注释+roadmap备忘)。绝对排除pack字面的『裸删test_ready_queue.py整文件』(混着唯一LIVE行为契约)。+确认R52全量版非PR-11预留接口。
12. R19收口落点(双重阻断):naive三处全收口execution_snapshot.positive_op_ids被循环导入(snapshot:7已import provider)+分层红线(repo data层→snapshot service层越层)阻断。推荐下沉【已存在的core/models/operation_execution_event.py】(repo已import、无环、向已存在模块加函数非新建模块)——owner确认:(1)是否接受不算违红线3新建模块;(2)vs core/shared(当前无data→core.shared先例);(3)vs降级为仅补parity+原地三处都改sorted消漂移保留三份。务必保sorted给execution_snapshot指纹。
13. R69收口家+loud形态:收口家schedule_input_contracts.py(runtime_support已依赖,persistence_guard新增import无环)vs新建极小run/op_keys.py(语义最干净触红线3谨慎区);loud-raise异常类型AppError(ErrorCode.SCHEDULE_CONFLICT,与_execution_guard_conflict风格一致能flash)vs ValueError(更轻,鉴于model边界已loud coerce该路径近不可达)。
14. R08现场记录保护总开关:roadmap owner(commit 65870e47 resource dispatch execution lane)确认近期是否计划上线真正的『现场记录保护总开关』配置?无规划→方案A删死分支+死文案(保feedback_write_enabled参数);有规划→保留并转注释钉『为未来总开关预留』。
15. R34 benchmark repoint API:precondition写get_plan_time_span_for_resolution(version,ROLE_ADOPTED)但该方法keyword-only位置传会TypeError。建议改用SchedulePlanQueryService.get_plan_time_span(version,ROLE_ADOPTED)。owner确认benchmark是否接受引入SchedulePlanQueryService依赖(当前只import ScheduleRepository),还是就地保留最小version-only span(若保留则get_version_time_span不能全删=债残留)。倾向repoint彻底删。
16. R40 raise错误分类:默认推荐删:70-72 except让float()抛原生ValueError(最省、无import、不引data→core分层耦合)vs repo层抛具名领域错误(如ValidationError,会让data层import core错误体系)。确认仓库是否已有『data层可抛core错误』既定约定。无论选哪种红线=去掉静默val=原值不加新兜底。
17. R32回滚消费侧integrity复检:_copy_db_file/migration_backup restore盖活库前零完整性复检——是否本轮纳入?这是行为变更(紧急回滚路径加校验可能阻断emergency rollback)且必须loud(校验不过喂回_auto_rollback的RestoreResult(ok=False)绝不静默跳过)。建议作为独立follow-up债不混入R32核心except→raise。
18. LB03/LB08承重注释文案授权:①LB03需owner确认采用改写的fail-closed文案、废弃§90 LB-B4 fail-OPEN STALE逐字(否则照搬与现治理矛盾);②LB08需owner裁断逐字贴守红线vs把第二行更正为『改任何排产引擎(greedy/internal_operation·external_groups·dispatch/resource_validation)发出的错误文案』(倾向更正,因承重注释价值=给改文案的人指对地方,auto_assign_resource_errors只持有前缀常量不发完整模板)。
19. LB03四治理文件入账边界:守卫测试当前untracked+四治理文件git-modified未提交。owner确认本Batch-1即把『治理(四文件)+守卫测试』作为既成事实git add入账(认账而非改逻辑)还是归属另一在途提交、本计划仅补:141注释——避免与并行工作撞车或漏add致裸奔。

## 7. 总纲

纲领:以『承重护栏先钉(Batch-1纯增量注释+契约/parity安全网)→guard唯一真相源收口(Batch-2 R54含漏列第4套)→SCC簇按文件原子串行收敛→facade全局最晚删(Batch-14)』为脊梁,把80条债的17桶/19单元重排成16个可独立验收的有序批次。关键风险与定调:①B01必须最先落,否则后续B02/B05/B11/B13在护栏裸奔期打穿纵深防御(fail-open冒充采用方案);②抓到的跨桶打架已最终定调——R11≡R63合并单work item、R54是4套非3套、R29授权CSV盘上不存在须重裁、R47双栈对称非单边、R44防御方向报告写反、R34实为纯删使R05→R34降为软约束、R50迁Batch-7随dispatch_rules.py三债、R30↔R31补漏记同文件边并入Batch-7、config_snapshot.py是basename假碰撞不串行化、B14四债按邻居散入Batch-6/9/10而非Batch-14;③6个强连通簇(SCC-NAV/SCC-GANTT/SCC-EXEC-FACT/SCC-CONFIG-DUAL/parse-int互锁/compat-facade)靠批次先后天然串行;④最危险失效模式=R54漏第4套、R05未先扩team轴、LB03误按旧报告改loud raise、R59不等F1、R51保留case_insensitive测试续命兜底、R69收口沿用静默归0;⑤约23项需owner拍板(R29/R55/R03下游/R43抢跑/R71收敛方向/R19落点/R72-R44分层/R41四裁断/R15能力缺口/R52 oracle等),其中R03下游脚手架DEFER不分配批次。全程只读+只产计划,零生产代码改动。