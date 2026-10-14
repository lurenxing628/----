# 第8阶段概览性能定向施工指令

日期：2026-10-14。主对话负责方案与复核，原实施对话负责实现。界面按`operator-experience-instructions.md`继续，后端本节按独立文件owner实施。

## 事实与本轮目标

主对话已直接读取完整HTTP证据。受控只读存档每候选20,000道安排，402资源×100日，共40,200资源日；真实接口4／6／8候选概览为16.08／20.57／24.68秒，响应约7.93／10.62／13.31MB。典型15道工序的概览为46／38／41毫秒。边界读取超过原2秒目标，A的性能验收仍待通过。

主对话对现有`controlled-normalized.sqlite`亲自执行一次4候选只读服务级cProfile：`query_only=1`、`total_changes=0`，22.02秒包含profile开销，不用于替代HTTP时延。主要调用为：

| 调用 | 次数与累计耗时 | 结论 |
| --- | --- | --- |
| `DecisionResources.prepare_overview/_ensure_windows` | 11.37秒 | 优先处理资源汇总内部重复工作。 |
| `ResourceTaskIndex.window` | 2,010次，8.34秒 | 4候选加一份重复候选基准，均扫描402资源。 |
| `_ResourceMeasurement.cell` | 203,010次，3.84秒 | 为整窗峰值和警报生成完整每日DTO及工序计数。 |
| `parse_local_datetime` | 3,172,422次，2.72秒 | 同一归档日历边界在各层重复解析。 |
| `operation_comparisons` | 4次，1.85秒 | 概览构造完整前后安排，只取变化数量。 |

证据：`evidence/decision-stage-acceptance/stage-08/performance-overview4-profile.json`；完整HTTP原件在`evidence/decision-integration-acceptance/2026-10-14/performance/normalized/http/performance.json`。本次profile未显示原内容判等为主要热点；保持当前去hash职责。

本轮先实现下列三项内部收敛，保持当前公开DTO、指标值、完整窗口、分页和导出协议。概览重复ID集合的体积问题已记录，后续是否调整合同由主对话根据这轮结果决定。

## 1. 共同日历只规范化一次，摘要只计算需要的量

修改职责：`facts/resource_projection.py`的`_ResourceMeasurement`与`ResourceTaskIndex`，以及`run/decision_resources.py`的`DecisionResources._ensure_windows`。复用`ArchivedCalendar.iter_resources`现有逐资源产出，保持40,000日分块和整窗覆盖。

1. 每次迭代到一个资源后，将该资源日历的日边界、可排区间、已知日覆盖规范化一次，内部保留datetime／区间索引及原日历状态；同一请求内的各候选测量共用它。公共JSON仍保持现有字符串和字段。规范化入口放共同资源投影层，正式计划／试调沿同一转换路径；不在各消费者另写解析器。
2. `_days_in`使用已规范化边界筛选和裁剪；只为公开时段输出生成字符串。取消同一日期在筛选、初始化、逐日汇总中反复`instant/isoformat/dict(day)`的来回转换。
3. 将`cell`内部“原始区间数值与状态／警报计算”和“公共DTO组装”分清职责。日／时／班次明细继续经过同一数值和状态函数；`window`逐日累计峰值、高负荷、超载、冲突、零容量及未知状态时直接使用必要数值，避免为每个日格生成几十个字段和完整issues。
4. 概览逐日摘要不读取每日工序数量，不调用`ResourceIntervals.counts/overlapping`来构建区间树。它所需的“该日是否可能有工作”用已有安排跨度交集是否大于0和真实未知工作状态判断；区间索引在正式详情需要任务／独立工序计数时才建立。整窗公开的task_count／operation_count仍按原真实集合给值；部分窗口明细仍给正确计数。
5. 高负荷时段记录只在达到阈值时构造；过载／冲突仅需计数的地方直接累计，不先造数组再取长度。已存在的公开`high_pressure_periods`仍完整提供。保留部分日历时的已知小计、未知传播、班内重叠和正常跨休息语义；日、周、整窗继续共用规则。

内部复用严格限于本请求的实际资源／范围／日历。资源迭代完成后不额外长期保存全体资源日DTO；不增加持久缓存、摘要、重试或框架。

## 2. 同一候选作为基准时，只计算一份

修改职责：`DecisionSource`提供共同私有计算身份；`DecisionResources`、`DecisionPreparation`、`DecisionChangeovers`采用它。已有`DecisionCompletion.delivery`的候选基准别名行为为当前一致参考。

- `comparison_mode == candidates`且存在`reference_ref`时，私有key `reference`映射到该实际候选ref。正式计划基准继续使用其独立来源，缺基准状态也独立保留。
- 资源tasks／index／window_rows／summary／group、准备groups／rows／summary、切换projection／metrics在进入请求内缓存前统一key。准备／切换各方法使用一个入口，避免每个方法追加一份特殊缓存。
- `prepare_overview`按实际唯一候选遍历。当前4候选样本中的2,010个资源窗口应减少为1,608个；6／8候选同理减少一份重复基准。
- API仍显示固定对照的公开身份、名称和定位；before与after的引用含义保持。公开组装需要加侧别字段时创建外层DTO，避免修改共享的内部统计对象而污染另一侧。

## 3. 工序变化使用同一规则，概览直接累计

修改职责：`decision_impact.py`的`operation_comparisons/_operation_delta`与`decision_metrics.py:operation_changes`。

- 提取共同的逐工序比较迭代入口，旧`operation_comparisons`从该入口收集字典供明细使用；概览`operation_changes`边迭代边累计，不再`dict -> values -> list`保留整份20,000行前后安排。
- 将同一对照的工序分组在请求内准备一次供各候选使用。单段安排可直接作为只读比较输入；多段、资料缺项、零时长和未排状态继续走现有共同规则。只有明细DTO需要时才复制展示用安排字段。
- “已确认变化／变化待确认／设备变化／设备待确认”四项累计条件沿用现有含义。公开全部指标和实际变化明细继续相同，保留缺料与其他未排区别。

## 4. 验证与交接

- 实现前后复用同一受控库和既有归档，不新造大样例、不重新排产／采用。概览、资源日明细、试调／正式资源及工序变化的现有有效用例按影响复用；只补确有覆盖缺口的独立边界。
- 先完成共同单元验证与同一4候选概览的一次HTTP计时，读取完整响应体，比较原数据值、覆盖、未知、差值及身份；此阶段不重复全矩阵。
- 对比原同候选作为基准与正式基准、真实休息／未知日历／跨夜／重叠、原精确窗口、单段／多段／未排行为。关注实际工作是否减少、RSS是否下降；服务profile计时与HTTP时延分别报告。
- 4候选结果提交主对话。达到目标且数据保持后，再完成必要6／8候选边界与一组受影响原件核对。若仍未达到，交具体耗时分布与剩余瓶颈，由主对话确定下一步；UI和其他已明确实施继续。
- 主对话按实际代码与性能决定是否通过。2秒目标、20,000安排、完整40,200资源日和Win7最终环境边界保持原定义。

## 5. 第一轮复核与第二轮施工（2026-10-14）

第一轮同库单请求实测11.1868秒，原16.0802秒；响应仍7,931,315字节，采样最大RSS947,126,272字节。主对话亲自读取两个完整响应，严格比较161,192个节点，键、类型、数组次序和值零差异，仅排除原约定的三个请求元数据。第一轮内部收敛有效，整体2秒目标继续保留。

主对话再执行一次同库只读profile：15.65秒包含测量开销，query_only=1、total_changes=0。资源窗口从2,010减至1,608，资源预计算从11.37降至5.89秒；剩余日历展开2.29秒、候选完整任务投影2.57秒、准备1.55秒、正式覆盖触发执行重建1.47秒、工序变化1.10秒、切换1.09秒。工序共同标签仍生成80,000次，日期解析仍1,164,022次。后续按以下位置收敛，公开DTO、业务值、全窗口和历史原件继续保持。

### 5.1 同一归档工序的基础展示事实只生成一次

`facts/candidate_tasks.py:operation_labels/_task_dto`与`GenerationFacts`共同处理。批次、零件、序号、数量、交期、执行展示事实只依赖同一GenerationFacts和operation_ref；在该facts实例内按真实operation_ref保存基础结果。`operation_labels`仍保持现有公共入口和返回形状。

- 每个任务继续执行`_check_task_payload`、payload.op_id与永久工序绑定、时间／source／locked及真实点事件检查；缓存命中不跳过这些任务级职责。
- 每次返回新的外层dict、独立data_gaps列表及其中的gap对象；`_task_dto`追加资源缺项、正式基准追加来源说明、unplanned追加状态，均不污染其他任务和候选。只读基础字段按实际消费保持共享。
- 同候选保存trace里的实际工种覆盖继续在任务层完成，不能让共同模板工种覆盖实际工种。当前80,000次基础标签组装应收敛到该归档20,000个永久工序。

### 5.2 同一任务的已核实时间在请求内贯穿使用

`tasks_projection`内部已完成时间解析和点事件核验；把这一次得到的(start,end)保存在与公开rows并列的私有投影结果中，键使用该候选的真实row_ref。公共`tasks_projection`继续返回原rows，DecisionSource接收共同内部投影及区间；不向公开任务dict添加私有字段，不修改JSON时间字符串。

在`DecisionSource`按实际候选身份持有区间；同候选reference复用该份。资源集合／`ResourceTaskIndex`、`DecisionChangeovers`的序列和计数、`decision_impact`时间变化使用该已解析区间，避免每层再次解析ISO字符串。其他正式／试调来源保留同一`task_interval`的现有规则，并在本来源请求内准备一次可复用区间。多段安排、interval_comparable=false、未知和零时点仍按原规则处理；几何复用只限同一来源和真实row_ref。不要建立全局任务注册表、持久缓存或摘要key。

### 5.3 正式覆盖成员与执行事实重建分开

`DecisionResources.coverage(details=False)`只需要正式状态、永久工序集合及差集，现在却为此调用整个`source.official`，甚至“无正式计划”也先重建20,000道执行事实。将归档正式身份／成员读取从完整任务与执行投影中分出一个共同入口。

- 在`candidate_baseline.py`抽出具体基础类`ArchivedAdmissionPlan`：读取facts、ScheduleHistory、Schedule、WorkbenchPlanSourceRefs／TaskRefs，执行现有`_check_baseline`、版本／plan_ref／行原文与绑定检查。`AdmissionBaseline`继承它，随后继续执行原settings、selected和完整`_execution`职责；不删除原执行验证，也不增加“跳过校验”开关。
- `decision_baseline.py`的新成员读取入口复用这份基础、`_last_official_rows`、`_official_sources`和`_bindings`。真实正式集合是“每道工序最后一次正式版本”的全部段，包含旧版本中仍有效的工序；禁止只取capture.baseline.rows或最新版本。无正式版本在完成对应归档一致性检查后返回absent和空集合。
- `DecisionSource`在请求内保留此成员结果，`coverage(details=False)`使用它；正式比较、安排详情、采用及其他需要执行事实的入口继续使用原完整读取。已有完整正式投影时由它派生同一成员结果，避免第二份成员计算。
- `coverage(details=True)`仍给原缺失安排明细，全部永久来源错误继续按原规则报错。覆盖集合、状态及数量应与原完整投影逐字段一致。

### 5.4 日历直接复用已生效的共同结果

`ArchivedCalendar._policy_day`只在事实已足够证明“当前日和可能跨夜的前一日均无个人覆盖，人员未分配班表，OperatorCalendar及WorkbenchOperatorProfiles表确实存在”时，复用该请求已有的全厂日历投影；仍使用原全厂／默认规则。若这些事实缺失、存在个人／班表覆盖或投影不可用，沿原人员解析路径给出对应缺项。保留人员basis与实际provenance，不合并不同人员规则，不另写班次算法。

`plan_calendar_windows.apply_resource`在完成原资源状态及传入停机记录检查后，若裁剪后的停机区间为空，直接复用base窗口和已算容量。active资源的值原样保留；inactive／maintain仍给空窗口及零容量；两项downtime值为真实0。非空停机继续原减区间规则。该处理去掉每个正常资源日无实际变化的字符串转换、区间复制和六种容量重算。共享窗口只读，资源状态不回写base。

### 5.5 这轮验证边界

先复用现有候选投影、正式基准／覆盖、CPU等价、真实班表及资源用例，重点保持payload错绑、各候选独立gaps、实际工种、旧版本保留工序／多段、个人覆盖／夜班／缺表／停机／停用、未知及点事件。仅补确认的独立行为缺口；不为缓存内部调用次数建立一组新测试。

实现后仍先读取同一4候选完整HTTP一次，比较同一全部161,192节点并记录耗时／RSS。这轮不展开6／8或重复导出矩阵。公开重复ID集合的精简暂不实施：历史按真实资源成员判断范围，API、页面、采用和导出仍有消费者；若将来调整，必须由主对话另给一致的合同改法。界面和Windows接线可独立完成并交付验收。

主对话证据：`performance-overview4-repair01-profile.json`、`performance-repair01-response-comparison.json`，均在`evidence/decision-stage-acceptance/stage-08/`。原HTTP材料在第8 performance/repair-01目录。

## 6. 第二轮复核与首屏职责收敛

第二轮同库4候选完整HTTP为7.3206秒、7,931,315字节，原161,192节点逐项保持；比原16.0802秒减少54.5%，2秒目标仍未达到。主对话只读profile10.0575秒含测量开销：source初始化2.707秒、资源3.800秒、准备1.264秒、工序变化0.793秒、切换0.724秒。再用原共同函数仅读取全部候选交付与保存推荐依据，服务级2.4255秒，其中source2.1889秒；这次不含真实当前取舍，因此只用于判断成本，不能作为首屏验收通过。

主方案§9已经规定首屏聚合、详情按页签；A02同时要求首屏明确收益与代价。最终边界定为：**全部候选的真实交期／完成性＋保存推荐与当前固定基准这一对的真实取舍**。完整候选指标矩阵按需。保留完整原接口、历史和导出契约，目标不改写为骨架出现时间。

### 6.1 共同任务校验先于展示，首屏不强制构造全部富任务

位置：`facts/candidate_tasks.py`、`DecisionSource`、`decision_delivery.py`。当前`DecisionSource.__init__:50`为了scope.resource_refs立即调用cohort→tasks，为全部候选构造80,000条含批次／工序／执行／资源展示的DTO；核心计数和交付只消费身份、时间与点事件。

- 从`tasks_projection_with_intervals`提取共同的已保存任务校验循环。继续执行_expected_task_rows、payload完整字段／重复op、永久operation_ref与payload绑定、source／locked／时间、真实零时点证据。将当前由operation_labels顺带执行的`facts.operation(ref,payload,...)`绑定检查留在事实层；展示gaps和工种覆盖仍由原展示入口负责。校验后得到原行及真实row_ref→已解析区间；不建立新的对象族或公开任务类型。
- `DecisionSource`按实际候选身份请求内保存这份已验证安排。scope的全候选资源成员直接由已验证payload的machine/operator ID映射归档永久ref取得，资源标签每个实际资源补一次；仍走现有共同资源成员规则，保留external、已核实point、缺资源身份和resource_view所选批次的现有语义。正式基准沿原完整来源。共同集合仍是全部候选＋基准，禁止缩为推荐一对。
- 候选核心计数使用原行的operation_ref；交付把已验证原安排转换为共同`project_delivery_batch`需要的schedule字段，沿现有完整批次链、deferred、incomplete和point规则。不要另写拖期或完成性算法。已解析时间复用，不重新逐行parse。
- 富任务展示继续用原_task_dto／operation_labels，按需要的候选生成，并复用已验证区间和校验结果。已有公共tasks_projection、甘特、工序明细形状保持。一个候选生成富任务后，后续事实消费者可从该已验证结果读取，释放不再需要的重复原行／轻量外层；不要在请求中长期叠加raw、轻量、富DTO三套完整任务。

### 6.2 新增明确的首屏读取，旧完整概览保持

位置：`run/decision.py`、`decision_recommendation.py`、`DecisionResources`、`web/routes/workbench/run_decision.py`。

- 增加`GET /api/workbench/v1/scheduling/runs/<run_ref>/decision/summary`及对应`read_run_decision_summary`，查询参数和权限沿原概览。原`/decision`继续返回全部候选完整指标，历史与导出继续原路径；本轮不连带重构历史查询或导出组织。
- 提取共同候选核心组装，两个入口复用原_candidate／candidate_metrics、实际delivery、保存selection_basis。summary保留run、scope、capture_ref、catalog_complete、全部metric_definitions、全部候选身份／状态／能力／角色／source，以及候选的原核心coverage、核心metrics；不为未计算的资源／准备／切换／工序变化填null或unknown。summary不提供completion_groups或完整候选矩阵；它有单独明确的前端校验。
- summary内部仅补齐“保存的推荐候选＋当前固定基准”需要的重指标、覆盖和差值，复用原共同函数及recommendation计算完整的推荐对象。推荐等于候选基准时按真实私有key只算一次；正式基准保持完整来源。未完成候选、无推荐或缺基准仍按原业务状态。候选卡公开metrics只保留核心集合，推荐计算所需的重值留在独立内部结果，不能因先后enrich污染卡片合同。
- summary同时保留原resource_cohort；baseline保留原身份／label／state及核心metrics／coverage，候选核心deltas与三项difference_summary均按原共同比较规则从核心值产生。不要把用于推荐内部计算的完整baseline覆盖回公开核心字段；正式基准从现有official_reference_metrics选取同一核心集合，真实缺算法值按原来源状态。
- 资源增加按明确keys一起准备窗口的入口，完整概览传全部keys，summary传推荐和reference唯一keys；一次日历遍历供这一组复用。禁止summary调用prepare_overview再删除输出。准备、切换、工序变化亦只对这两个实际来源计算；“当前查看”仅用于自身交期三项difference_summary及后续页签，不因切当前查看重做其他候选完整矩阵。
- 首屏`recommendation`保留原固定理由、主要收益／代价、完整差值、完成覆盖、剩余需求与明细入口；数值继续基于真实当前基准和窗口。不要把存档算法changeover_count当真实type_changeover_count，不删A02的资源或切换代价，不把等待计算当业务unknown。
- scope与state沿原完整身份：run／selected／reference／range／resource_view／批次工序和共同资源集合。快照kind仍为`run-decision`；source.state原样，summary令牌可直接用于原导出。不得省略scope成员、另造hash、设立持久缓存或后台预取。原最大响应边界继续在各自实际响应上检查。

### 6.3 页面使用首屏结果，完整指标只在需要时读取

位置：`RunDecisionAPI.js`、原adapter挂载链、`RunDecisionComparison.jsx`及其完整指标／数据来源消费者。

- adapter增加decisionSummary，Workspace初始read改用summary；原decision继续作为完整读取。两种校验抽共同的身份／范围／核心候选／推荐规则，完整validator继续要求原全部字段，summary validator只要求自身明确字段，不允许给旧validator加“缺就跳过”。
- 现`recommendation()`校验末尾的completion_groups两段拆成仅完整概览调用的独立检查；推荐自身的身份、完整all_differences、收益／代价、scope和drill继续共同验证。`tradeoff`的metric_version直接对照共同metric_definitions中该指标的metric_version，避免为校验一个已在目录中声明的版本而强制读取每个候选重指标。完整矩阵的逐指标值与delta检查仍保留在完整validator。
- 推荐主区域和“推荐详情”使用summary内的原真实recommendation；交期、资源、准备／切换、过程和工序安排页签继续使用已有独立详情接口。共同当前候选、固定基准、推荐身份和采用预检职责保持；采用候选目录及显示名称仍来自summary真实catalog。
- “全部指标”才请求原完整decision。关闭的“数据来源”不挂载要求完整candidate指标的CandidateFacts；其中若确实消费重指标，展开时再启用同一个完整read。这两个入口在同一Workspace复用一份请求结果，不各发一次。其余轻量来源文字和永久编号可以直接使用summary。不要后台自动预取完整概览，后端现为单读取槽，预取会阻塞用户下一步。
- 完整read用现有useQuery、AbortController和请求身份隔离；身份包括run、当前候选、比较模式／基准、完整时间与resource_view及refresh revision。查询变化后旧完整结果立即失效。只在启用的入口显示“正在读取全部方案指标”，保留既有取消／刷新动作，失败在该区域给实际错误，候选与其他已读结果继续可用。取消按目前客户端停止读取的能力表达，不能声称同步后端已经终止计算。
- differences的三项交期变化取summary真实difference_summary。当前“安排一致／差值待确认”依赖完整changed_operation_count，改由批次明细返回`summary.operation_changes`（含原changed_operation_count及machine_change_count metric形状）。`batch_impacts`已遍历source.operation_comparisons；将decision_metrics.operation_changes中的累计封成共同函数，批次明细复用已经得到的全范围comparison values计算，保持selected_available/reference_available及未知边界；不再次组装20k行、不从筛选页或batch page计数推全范围。前端两项提示只在这个明细结果到达后判断，缺指标不当0；相同候选仍由永久身份判断。导出继续直接使用summary快照，不先为获取令牌再读完整概览。
- 保留当前排版、推荐区收益代价、正常加载文案和已有返回上下文；这轮只改读取职责与明确依赖，避免再排版一轮。

### 6.4 必要验证与交接

复用现有候选投影／归档绑定／点事件、交付、推荐、资源、snapshot与导出用例；在已有API用例内覆盖summary与完整结果的核心值／推荐／scope逐项相同及summary令牌导出。前端沿既有契约用例证明独立校验、关闭完整入口不请求、切候选不会回填旧完整结果。只补真实新读取边界，不新增排列组合矩阵。

同一现有4候选边界库先各读取一次新summary和旧完整概览：summary记录完整HTTP耗时与RSS，逐字段比较旧概览对应的scope、核心候选、推荐和三项变化；旧完整概览仍与原161,192节点比较。再实际打开页面确认候选、主要收益代价和默认交期结果出现，单独记录首屏与后续明细时延。首屏2秒目标仍按真实内容计，结果未达时直接交具体结果，不自行追加新架构／缓存或重复大矩阵。完成这次职责收敛后，由主对话结合实际收益判断后续动作；其他UI、清理和门禁准备继续。

本段源头证据：主对话`performance-overview4-repair02-profile.json`、`performance-first-content-cost.json`。实验均query_only=1、total_changes=0；未修改产品、接口、归档或数据库。

### 6.5 首屏与按需完整指标共用同一读取快照

冻结代码的`RunDecisionComparison.jsx:210-214`按首屏scope生成fullQuery，尚未传首屏的snapshot_ref。排产等待／运行中先显示summary，随后候选写入或运行结束，再打开完整指标时，旧卡片可与新候选矩阵混在同页；单纯run／candidate查询身份无法排除这种同一run的事实变化。现有`test_run_decision_api.py`已包含pending→worker完成的真实过程，属于现有合法使用状态。

fullQuery必须同时带`result.meta.snapshot_ref`。两接口已使用同一`run-decision` scope/state，直接复用`bind_read_snapshot`和已有前端bindSnapshot验证；不增加另一套版本号、签名或比较器。来源变化／令牌过期时，完整指标区域显示现有snapshot_stale错误，保留带原刷新时间的首屏结果，等待用户刷新。

“刷新全部方案指标”改为调用Workspace现有整体reload（其resetDetailPages已解除fullPaused），先取得新summary，再按新snapshot_ref读当前开启的完整区域；不要仅fullRead.reload重试旧令牌，不自动重试。原顶部刷新沿同一路径。正常未变化的summary→full应返回同一token。

验证复用已有pending API用例：保存pending summary token，在该用例原有worker完成后以旧token读full，确认snapshot_stale；刷新取得新summary后full共用新token。前端既有按需读取用例核对fullQuery带当前token，点击完整区域刷新走共同reload。只补这项真实跨读取一致性缺口；此次前端接线不要求重跑已完成的后端耗时请求。

### 6.6 第三轮结果与剩余边界取证

同库实际summary为3.6246秒／1,500,277字节／采样最大RSS846,954,496字节；full为7.1560秒／7,931,315字节。主对话独立比较summary声明字段32,643节点、full全部161,192节点，均零差异。2秒目标仍未达到。主对话对新summary路径的一次只读profile为4.8697秒（含测量开销）：初始化1.946秒、推荐一对的重计算2.440秒，其中资源1.579秒；80,009次存档JSON读取累计0.954秒。当前示例推荐等于候选对照，已经只计算一个实际重来源。

本轮已完成有明确职责收益的内部复用及首屏／完整读取分离。下一步先完成必要边界事实，再判断性能收口，不自动追加缓存、持久派生表、并行请求、新依赖或更多微调轮次：

- 在原`controlled-normalized.sqlite`复用既有6候选和8候选归档，各仅读一次新summary完整HTTP。这两项新接口边界尚未执行，是本轮需要补齐的事实；不重读4、不重跑6／8完整概览或导出矩阵。
- 分别与原6／8完整概览中的声明核心、推荐、scope和三项变化逐字段核对，记录耗时、完整body与采样RSS；同原资源窗口和推荐／基准身份，不换小窗口或减少候选。
- 4／6／8新首屏结果分列，2秒目标继续如实记录通过或未达。前端6.5快照接线和历史CSS修复可独立收口；现有真实首屏／按需完整读取／取消／导出路径完成后交主对话。前述只改前端的两处不使已完成的后端时延证据失效。
- 这两次边界测量结束且相关源码最终冻结后，可完成原约定的完整dirty门禁；前端构建及门禁各自报告真实结果。性能目标、Win7实机和代码门禁分别核销，不用门禁通过替代性能／目标机结果。

独立原件`performance-repair03-response-comparison.json`与`performance-summary4-repair03-profile.json`；本次profile query_only=1、total_changes=0，无新fixture或业务写入。


## 7. 用户决定：性能交由C收口，A／B先推进

2026-10-14，主对话完成当前源码、原profile和实际归档结构核对后，用户明确选择“性能留到 C 收口，先推进 A/B（建议）”。本稿第1—6节已完成的有效优化与证据保留；A阶段不再追加性能微调。4／6／8首屏3.6246／4.6823／5.2835秒继续记为未达2秒，2秒目标及全部旧候选／完整窗口范围保持，C的U0承接读取结构设计并在最终交付按实测收口。

原4候选run的80,000条任务JSON各解析一次，receipt原文32,029,852字节、artifact每份约3.38MB；results保存元数据而非另一份安排，validated_payload.schedule_rows已不存在。共同资源成员使用生成器，推荐富任务只构造一份。进一步资源转换／无工作日计算的有限余量不构成达标证明。主对话证据`evidence/decision-stage-acceptance/stage-08/performance-c-handoff.json`保留当前源与只读库事实；不新增缓存框架、重复矩阵或未经设计的输入旁路。
