---
doc_type: architecture
slug: workbench-shell
scope: 工作台离线外壳、领域服务、受管运行及恢复边界
summary: 工作台拥有事务与持久结果，内存绑定和真实出口共享准备，显示模型分准备、布局、绘制
status: current
created: 2026-09-09
last_reviewed: 2026-10-15
updated: 2026-10-15
tags: [workbench, flask, offline, win7]
depends_on: [ARCHITECTURE]
implements: [workbench-foundation-read-loop, workbench-production-workflows]
---

# 工作台宿主与领域边界

## 当前边界

`/workbench` 和 `/workbench/trial` 支持15个视图，侧栏12项；计划甘特/交付风险及报表/复盘通过页内页签组织，旧URL和精确上下文仍保留。主数据、工艺、批次、候选生成和采用、正式计划、试调、执行台账、实际甘特、复盘报表、工时校准、值班台和系统维护均通过真实领域服务接线。本文记录 2026-10-15 当前工作区已落地职责；本轮整合验收见[单次准备执行记录](../refactors/2026-10-15-single-pass-workflow/single-pass-workflow-refactor-design.md)，Win7 打包、真机和发布状态由既有路线图维护。

## 职责

- `web/bootstrap/factory.py` 注册 `web.routes.workbench`，在开库前检查一次实际维护窗口。普通请求消费 runtime 的内存运行状态；static/health 走轻量路径。真正到期的自动维护才进入原维护 owner 与 journal 准入，失败沿原503或存储错误传播；请求关闭和恢复继续由既有生命周期协调。
- `web/routes/workbench/assets.py` 校验本地 manifest 和引用文件；资源不完整时宿主明确503。`pages.py` 提供启动信息和只读 JSON 协议，不执行 SQL。
- `core/services/system/workbench_overview.py` 使用已提供的连接及路径进行只读投影；不补配置、不读日志正文、不校验备份、不生成备份。失败、未知和0分开。
- `frontend/workbench/app/` 负责呈现、正式主题键 `aps_theme`、请求时限/取消、响应校验及样例隔离；不计算或保存正式业务事实。
- `frontend/workbench/prototype/` 是原型依赖的可追溯副本，不是开发时依赖的忽略目录。原始 `前端设计/` 不被构建改写。
- `scripts/workbench/build.py` 在开发机将固定 React18、原有共享控件和 live 源预编译，发布到 `static/workbench/`。目标Chrome109不需要 Node、Babel现场编译或外网。

## 服务包结构（2026-09-20 起）

- `core/services/workbench/` 按业务簇分子包，根只留跨簇协调件 `commands.py`（命令事务框架）与 `messages.py`（共享文案）。簇：`facts/`（只读事实与叶子助手）、`plan/`、`execution/`、`run/`、`trial/`、`report/`、`dashboard/`、`process/`、`resource/`、`material/`、`batch/`、`calibration/`、`outsourcing/`、`system/`、`master/`。
- 簇之间只允许单向依赖：结果侧 `facts ← plan ← execution ← run ← trial ← report ← dashboard`，主数据侧 `facts ← process ← resource`，`batch`、`calibration` 在其上，其余只依赖 `facts`。完整方向表、五对历史双向依赖的解法与模块分配表见 `.codestable/roadmap/foundation-boundary-governance/workbench-cluster-layering.md`；当前依赖核对沿开发文档的质量治理入口执行。
- 子包 `__init__.py` 只有 docstring，没有转发导入或懒导出；搬模块用 `tools/move_modules.py` 一次改完所有调用方。

## 请求与恢复

HTML -> 提前应用主题 -> manifest本地脚本/样式 -> React宿主 -> 同源领域API -> 校验实际消费字段 -> 展示数据。读请求有时限，卸载或切换工作区取消旧读取。错误显示重试，不静默读取样例。主题偏好与业务状态分开。

系统概况的 `snapshot_ref` 标识本次只读响应；各领域读快照继续按其真实事实和 scope 绑定。资料总览的列表、详情、定位与导出统一读取该 scope 下的当前资料，响应回传本次 `as_of` 和实际导出条数；过期或 scope 不符沿原 `snapshot_stale` 表达。永久实体引用、短期上下文和页面偏好各有独立职责。

## 2026-10-15 单次准备的当前实现

- **事务与计算**：工作台拥有受理、worker、保存和正式采用。`ScheduleService` 当前只负责批次工序编辑；候选计算经 `compute_candidate_run` → `orchestrate_schedule_run` → `run_candidate_comparison`，计算阶段使用明确版本上下文。旧运行、collector 生产采集和持久化链已经退役。
- **共享事实**：`ProductionFactsCapture` 拥有一次事务快照的原始表、最新正式安排索引与资源执行事实；`PreflightFacts`、`CandidateRunInput`、`BatchFacts`、`GenerationFacts` 和 `DecisionSource` 消费已取得内容。worker 同一次副本核对与输入准备共用 capture，写锁内的新事实仍在实际采用或完成事务取得。
- **搜索与档案**：`NativeSchedulePreparation` 和 `SharedDecodeSession` 拥有固定工序、参数适配、资源、拓扑与断点准备，请求表达真实变化。真实解码出口取得安排编号，阶段和目标同步使用档案小视图；未验证 trial 未命中时只保留临时编号。报告消费编号及评价标量，完整来源在 events，最终发布物化结果与选中证据。
- **内存 token**：`web/public_token_registry.py` 直接保留 `ReadBinding`、`WriteBinding` 和预览/文件对象；共同规范事实按组共享，小键服务签发复用。binding 不再做 JSON 编码后解析，逐行 token 不再各包一份大事实。读写绑定直接引用各自所需值，写入口寿命由自身 expiry 决定；等待写锁后的实际到期检查和锁内当前事实比较继续执行。
- **规范化、写入和输出**：日历、资源、工艺及报工的原始输入在共同领域入口规范化，写入者返回实际 ref、revision 和时间供响应使用。命令回执首发与重放消费实际保存文本。JSON 最终信封在 `web/api_responses.py:json_response` 编码 UTF-8 并直接发送该字节；独立文件在自己的真实输出边界编码。内部投影按实际消费者加工，HTTP 大小限制位于真实响应出口。
- **显示和查询**：计划与实际甘特把固定事实准备、可见成员/布局与绘制分开；Canvas 生命周期归 `GanttPresentation.useCanvasPaint`，搜索只更新筛选与轻量汇总，宽度只改变几何，滚动只选择可见区。列筛选由 Enter 或已有按钮提交；资源热图直接消费后端已有桶。报表工序详情使用 `plan + detail` 的窄 DTO，前端同步按详情合同读取。
- **启动和维护**：启动协调器在开库前捕获 journal，后续 owner 消费同一捕获；普通请求读取内存停止状态并在开库前检查维护窗口。当前 Schema43 在 v41/v42 保存读模型上调整实际查询索引；普通启动检查结构，新库、升级与恢复执行完整数据合同，v39—v43 明确表示差异由现有 `schema_compat.py` 处理。

## 共同事实与存储

- 排产事实新鲜度排除只写审计 `OperationLogs` 和仅驱动维护间隔的 `SystemJobState` 内容及其自增序列；真实 Schema 和业务输入仍参与核验。访问驱动自动备份不使排产候选保存误报输入变化。
- 新候选以 `WorkbenchRunCandidateTasks` 为安排正文权威，artifact 标记 `candidate_tasks_v1`，只保存引擎独有追溯和验证结论；写前核对引擎与验证安排一致。旧完整 artifact 保持原数据和读取合同，永久身份、范围、顺序与零工时依据继续验证。
- 新保存试调的 `snapshot_json` 只保存元数据与有序永久行引用，任务正文来自 `WorkbenchTrialScenarioRows`。完整命令回执承担精确 replay；读取解析保存内容及永久引用，落档、采用和迁移承担实际内容确认，旧摘要、历史编码和记录保留原值。
- 排产配置字段、Snapshot、转换和权重公式由 `core/models/schedule_config_runtime*` 统一维护；服务层只补页面元数据、错误标签与旧方案缺省策略。可变配置输入仍在算法边界验证；同次候选参数覆盖和默认保留窗口共用原始配置读取。
- 原生优化器在会话创建时准备固定拓扑和实际输入适配，decode 只重建动态进度并消费请求优先级；独立原始算法入口继续适配真实原始输入。
- 普通维护状态使用运行 owner 的内存状态；启动、文件维护接受、真正到期自动维护及明确历史读取在实际边界取得 journal 记录。正常结果跟踪使用原 request key 精确读取，手工 job_ref 查询独立保留。
- 页面 context 与 scroll 由共同导航 owner 保存；普通 read 生命周期和已核实 Blob 的 DOM 保存进入已有共享机制。领域响应、业务归属、跨 tab 和写前/写后核验各自保留，卸载会取消请求及等待队列。

## 界面共享层

- 应用样式集中在`frontend/workbench/app/styles/`，由`build-order.json`显式登记，按基础令牌、布局、共享控件和工作区域顺序进入资产清单。原型依赖先加载，应用层负责当前界面；静态样式不再由工作区组件反复插入。视口预算、表内双向滚动、吸顶表头与固定关键/操作列共同保证长表可用。`WorkbenchScrollShadows`在壳层挂载一次，按实际遮挡给表格框打`data-overflow-left/right`，固定列只在遮住其他列时显示滚动阴影；表头`word-break: keep-all`不在中文词内折行。顶栏是唯一可见页面标题，工作区重复的`h2`以`wb-page-title`视觉隐藏、副标题以`wb-page-context`作上下文行；工作区根统一`padding: 0`，灰底加白卡，KPI 条统一四格，甘特滚动框按行数自适应到上限。间距字面量按`--space-1..6`接线，行高有`--wb-line-*`三档，圆角统一`--wb-radius-control`。
- `WorkbenchFormat`区分工厂本地日期文本与带时区的实际时刻；空值和非法值分开处理，显示层不另加业务取值范围。`number/percent/hours`接受`{ digits, trim }`：trim 保留录入精度（最多 digits 位），录入类工时、报工累计与候选对比指标用它而不是 1 位摘要；-0 归零显示。报工时间经`FieldContract.date`保留秒。`WorkbenchTerms`统一界面术语，`WorkbenchReferences`把完整引用与诊断收纳到可展开区域，保留原始内容；值班台来源只折叠诊断码、`*_ref/*_key`与完整十六进制引用，`business_code`、`kind`等业务字段保持可见。
- `ResourceControls`和`WorkbenchControls/WorkbenchListControls`提供字段错误、空态、分页、弹窗与详情。`Button`的禁用原因分`inline`与`tooltip`两种呈现，表格操作列和工具栏用 tooltip（title 加视觉隐藏说明），表单与页面级主动作保持 inline；`Issues`把相同消息合并为一行并标注条数。分页档位由领域消费者明确给出，游标模式不虚构总数。详情按业务条目更换内容并管理焦点；只读自动预览可显式保持原焦点。密度由`WorkbenchDensity`共享订阅和保存，切换行距时保持字号和数据不变，保存失败明确显示。
- `WorkbenchGuards`按owner和作用域登记未保存输入及待核实命令；`WorkbenchGuardHost`通过共享Modal呈现确认，避免核心守卫反向依赖UI。导航、同文档前进后退和编辑器关闭都查询同一守卫，拒绝时保留URL、页面和输入；确认框不再次拦截自己，待核实业务请求不被当成可放弃草稿。`locked`只来自待核实命令，目录弹窗或重读资料等UI忙碌态不得传入；确认等待期间受保护条目全部保存或卸载时，守卫自动放行并关闭空确认框。
- `PlanSelectionModel`只在没有明确或恢复上下文时选取唯一可读的当前正式计划。选中计划或候选后目录可收起并重新展开；从候选目录切换对象后归还展开入口焦点，外部进入不抢焦点。`ActualGanttWindow`仅计算显示窗口和命中区域，按时间中心与可见时长恢复刷新/跨宽度视窗，保留原`axis_span/as_of`、点工序和真实持续时长。
- `FieldDraftModel/FieldEditorFields`仅为新建报工生成可清除的建议，并限制“上一条”的来源与复制字段。保存继续必须经过成功回执、重新读取和新的可写上下文；补齐、更正、保留草稿和未知结果继续沿原事务恢复链。任务详情位于列表滚动框之外，避免编辑器被表格高度预算裁切。

界面验证沿`../reference/tools.md`的opt-in浏览器通道取得实际渲染和交互证据；相关Node合同进入普通pytest。日常、局部浏览器和最终HEAD门禁分别记录，命令与证据边界统一见`../../开发文档/README.md`“质量治理入口”。

## 已接后端

- v20增加`WorkbenchEntityRefs`、`WorkbenchCommandReceipts`及资源生命周期触发器。引用跨进程稳定；更新保留、删除重建或REPLACE产生新实例。复合内部键采用百分号/分隔符转义，覆盖NUL及UTF-8/UTF-16，不改业务字段。物料批次引用查找有独立索引。
- `WorkbenchCommandService`拥有最外层SQLite事务，先查询已提交回执，再校验短期编辑上下文、执行领域动作和落不可变回执。回执不保存短期token；不确定结果可按`request_key`查证。此服务不用于文件恢复或异步排产受理。
- `web/routes/workbench/materials.py`开放真实物料列表/详情、新增/修改/删除和命令回执API。领域动作复用`MaterialService`，保留省略字段及`BatchMaterials`事实；NULL库存不显示成零，未配置阈值不声称低库存。
- v21显式资源表不替代旧授权/班组，也不回填猜测值。资源领域服务复用旧增删改保护，`resources.py`暴露有限类型的公开实体/永久引用和短期上下文；统计过滤发生在分页前。坏资料仅影响相应指标并明确问题，真实存储故障仍拒绝读取。
- `OperatorQualificationService`同时供资源统计、可选资源池与固定人员校验使用；`operator_shift_calendar.py`由CalendarService调用，个人日期覆盖优先，全局休息与许可仍约束班次。旧完成/冻结事实不参与新资格校验而被误改写。
- 物料`material_actions*`负责服务器预览登记、短引用与真实文件下载，确认仍使用原子SQLite命令。文件导出只读；批删及增量导入整批回滚。只把2000行限制用于导入。
- `calendars.py`月读和单日/范围维护只修改全局WorkCalendar。公开投影区分编辑字段、原存储字段和实际生效工作窗，不泄露内部revision/history；原始预览留服务器。DATE在仓储统一ISO字符串，不截断datetime或做UTC转换。
- `ResourceLive`挂载真实adapter与各独立向导。`resource-api.js`验证同源、协议与提交状态；`resource-session.js`在会话存储保留待核实请求键，不持久化生产输入/短期令牌。未确认提交时不自动换请求重试。
- 非物料`resource_actions/resource_file_exports`按白名单类型开放预检、三字段确认、CSV/XLSX模板和下载。服务器保留完整原预览/字节，公开令牌仅短引用；导入限2000行，完整导出与显式批删不沿用该行数限制。scope固定自制/外协类别，未展示旧字段只读回传，不开放新写入口。
- `WorkbenchResourceFileRepository`为导入冲突核对提供所需引用，将真实SQLite DATE对象规范为ISO日期，保留datetime原义；个人日历/旧授权继续参与删除约束和预检后的过时保护。导出读取当前范围内实际输出列，覆盖完整筛选结果。
- `ResourceRail`消费真实资源统计与本周日历只读投影。标准工时未配置不填样例值，显式/服务默认/无许可/坏资料分开。工种文件待核实状态独立保留category，跨资源命名空间不混用。
- 计划查询已通过`core/services/workbench/`的公开领域层与`web/routes/workbench/`接到目录、分析和甘特UI。内部计划目录/页仍只负责内部数据，不直接序列化内部行号；公开计划和任务引用跨进程稳定，快照与范围另外核对。

## 当前业务与宿主

- 资源、工艺三步确认、批次三种文件导入、复制及批量操作已接领域服务。预览与原子命令保留旧授权、隐藏字段及已有业务事实，不因新UI未展示而清空。
- 排产由`web/bootstrap/workbench_run_runtime.py`及`workbench_run_lifecycle.py`管理实际worker、持久受理、候选、运行锁与停止等待。候选选择只读，正式采用必须明确确认并核对执行快照和版本。
- 空排产配置在应用启动时由`web/bootstrap/schedule_config.py`原子建立默认字段、内置方案和来源记录；已有缺项或坏值不自动补齐。预检和候选计算继续读取严格快照，不在请求或只读计算里初始化配置。
- 试调持久草稿与正式采用分离；共享与分件工序保留原引用、单件前置关系、计划应做量和整批量。合法零时长是计划点，不占资源，也不自动成为实际完工。
- 分次报工与更正走追加台账，旧事件保留原义，未知数量和工时不补零。实际甘特、复盘、报表及工时校准消费同一已核实事实，交付风险不把缺工序或局部完工当作完整批次完成。
- 值班处理状态与业务风险分开。系统备份下载只解析已登记公开引用，文件存在不等于可恢复；`workbench_system_restore*.py`与`workbench_request_lifecycle*.py`负责排空连接、停止worker、恢复状态及冷启动核对，恢复不走普通行命令。

## 历史专题与验收记录

以下保留各次专题交付时的业务说明和证据范围。当前输入、token、输出、显示和 Schema 职责以本文前面的现状章节及对应代码为准。

### 2026-09-28 工艺与外协一致性

- `process.groups_confirm`复用阶段预检与回执协议，按永久工序/组引用增量新增、调整、拆分和解除外协段。合并段周期只解释一次，旧逐序周期保留但不参与合并段的生效投影；整段换供应商保持组身份。页面共用能力选择器，并在已确认保存、详情刷新失败时开放父页面恢复入口，保留未存工时草稿。
- v33 的 `BatchExternalContexts`保存各批次工序的外协规则；新建、实例复制、分件、明确模板更新分别捕获或复制来源，不在排产时回查当前模板。旧库只记录升级时可核实资料并标记来源。批次逐序维护不能拆开合并段改派供应商，预检和输入构建独立核对冻结组与实际成员；历史候选试调仅使用该候选自己的归档事实。

### 2026-09-15 手动整改实现

- `ResourceControls.jsx`统一本地 `trash-2`、展开/收起与搜索图标，`20-controls.css`统一按钮图文和筛选对齐，`21-table-frame.css`提供单层表格框及编辑列分隔。所有可达删除动作使用垃圾桶和可见文字。可达管理样例的三项共享组件移至 `SystemSampleControls.jsx`，由 build-order 放在资源控件之后、SystemLive 之前，冻结原型不改。
- 工艺归属保存继续走 `stagePreview` 与 `process.source_confirm`；明确保存时提交全部有效工序的确认内容，实际解除外协组关系仍单独列出影响。`ProcessHoursEditor.jsx`拆分自制/外协表，`process_zero_hours.py`在事务内按内容绑定的确认记录决定是否要求零值确认，工时文件读写复用相同规则。既有批次不随模板修改自动变化。
- `batch_template_validation.py`提供必要资料完整性结果，详情与更新预览共用；`batch_template_preview.py`生成逐工序前后变化及设备/人员指定清除列表。更新确认重新检查模板与批次快照并原子替换。旧 `strict_mode: false` 返回 `template_validation_required`，不再允许宽松复制缺项资料；旧模板缺少确认记录与资料实际缺项分开判断。
- `run_data_context.py`由数据库 scope 与数据库外已成功恢复的 journal 集合生成 `data_context_ref`，普通重启及备份创建/删除不改变它。预览、受理和查询绑定同一数据上下文；查找先核对当前任务和回执，再捕获一次 journal 供 resolution 和 data_context_ref 共用。旧 pending 沿原 journal 与受保护备份定位原请求，核对登记文件身份并只读查询实际任务/回执；原来源缺失保持未核实。v2 pending保存最小身份和数据上下文，旧64hex上下文仍可查询；未知查询满60秒暂停自动查询，保留同号重查，真实计算继续查询，不自动重新受理。
- `OperatorMachinePermissions.jsx`在人员详情维护既有设备资格集合，后端复用 `OperatorMachineService` 与原资格检查，无新授权表；界面以预览/确认保存全量关系，保留未展示的旧字段，不从工种技能推导全部设备权限。
- v32 在同一可回滚迁移中安装两项追加扩展：`WorkbenchOutsourcingSourceConfirmations`与`WorkbenchProductionReportVoids`，共2表10触发器。只安装空结构，旧来源空值、旧出生事件、报工修订和回执不改写。`migration_state.py`严格校验两项结构，缺表/错误触发器不能以空数据继续读取；原 v25/v30 安装器及冻结历史 schema 保持原合同。
- `core/services/workbench/outsourcing/source.py`（`resolve_source_binding`，仓储 `workbench_outsourcing_source_repo.py` 只读事实）按出生记录、首次登记确认、当前完整关系解析来源；已有证据与当前实例冲突仍拒绝。`source_resolution`用于说明与快照，不改变稳定的 `source.identity`。普通外协登记事务同时追加外协单、成员、事实、来源确认和回执；首次登记后来源解析方式变化不会使更正误认成新对象。
- `production_report_void.py`负责撤销预览及事务重查，`FieldVoidEditor.jsx`沿普通命令回执恢复链确认。中立的 `ExecutionLedgerReader`只把有效报工放进 `reports`，`voided_reports`保留完整历史用于审计；现场、实际甘特、风险、复盘、报表和校准共用该事实集合。候选基线从受理归档内的撤销表重投影，不用当前库事实污染历史基线。
- `resource_utilization_metrics.py`以 `available_occupancy_v1`共用区间运算，`utilization_calendars.py`读取逐资源日历和停机。班表内占用取并集与可用区间交集，分母不乘效率；累计负荷、重叠与班表外占用另列。已有严格计划 DTO 的历史 `occupied_hours`仍是自然跨度并集，显示层使用 `available_occupied_hours/inside_available_hours`；报表、值班台和计划占用读取同一内核。已有资源占用率入口仍为 planned，未新增独立 actual 占用率页面。
- `TrialCatalog`以实际 candidate/plan来源初始化，`preview_create`投影原 `admission.source.identity`为只读 `base_identity`。草稿验证仅报告真实约束，正式采用仍由独立预检授权；UI/对比CSV只过滤已识别的历史能力说明码，原始JSON与保存历史不重写。`report_exports.py`区分行级“数据缺口”和全局“统计说明与待补资料”，下载结果显示实际文件名和范围。
- 采用完整性检查复用`preflight_checks.stored_date`处理正式SQLite连接的DATE对象和规范文本，保留齐套日与其他约束。`jobs_facts.run_facts_unchanged`比较当前与归档完整事实；旧归档按自身DDL及共同`non_input_row`解释。v39/v40仅投影已知技术变化，未知结构及实际业务变化继续识别。日志、维护时钟、排产自身账本、试调草稿、看板处置及相关非输入回执按同一排除规则处理。新入场归档保留完整原文，摘要列写NULL；Worker计算前／保存前和采用检查共用，旧归档保持原样。SQLite仓储读取原存储类型，DATE转换器不改变事实表示。
- `AdmissionBaseline._execution`从完整入场归档Schedule恢复截至基准版本曾有正式安排的工序，与所选工序合成捕获执行集合；投影必须完全相等，归档报工、当前任务身份和数值继续逐项核验。历史大范围按既有执行投影单块上限恢复后核对完整集合，AJ和worker上限保持。最新版本对照行不混入旧版本工序，也不读取当前库补历史。
- 校准样本明确区分没有逐次报工与已有报工字段缺失；无报工的派生缺口合并，独立的来源/历史异常检查保留。导出说明反映已接入的预检采用入口；采用仍要求当前模板版本至少5条合格样本；v39 起采用记录可追加，人工保存、Excel/CSV 导入和校准采用共用 `ProcessTemplateHours.revise` 修订当前模板，旧批次与历史计划不反写。旧永久锁表和单模板一次采用约束已退役。
- 文件导出清单中已声明的参考列不进入导入写DTO：物料创建时间和资源原始只读资料在预检`reference_fields`中明确列示，批次兼容原八列模板和包含状态的九列清单，状态只供参考。未知列、公式、必要字段、文件指纹、并发和原子确认仍按原合同检查；导入文件不能恢复人员原设备权限或覆盖系统时间。
- `FieldWorkspace.done`保存后同时更新当前`task_ref/operation_ref`，没有任务时一起清除；原计划、搜索和日期范围保留。任务切换不复用入口工序引用，后端继续拒绝真正错配；已成功保存后的读取失败不自动重复提交。
- `ResourceWorkspace`读取父表单最新资料后同时更新保存上下文，借既有`acceptedEntity/rebaseDraft`保留用户已改字段、更新未改字段。从父表单自己完成班次/设备组维护后统一刷新选项及父版本，不再额外要求“已核对”；未知维护结果和后续并发变化仍不自动放行或重提。

#### 独立功能补验中的接续修复

- `trial_execution_anchors.py`在新草稿创建与验证时复用`build_execution_guardrails_from_projections`：已完工工序固定为真实起止和资源，已支持的开工工序固定实际开工/资源并沿用原计划时长推算预计结束。`original.execution_anchor`保留依据，`original.arrangement`仍保存原计划对比；公开DTO校验固定安排一致且不可编辑。旧保存场景不重写，旧计划时段与真实固定冲突时返回`scenario_execution_anchor_outdated`。齐套、前后序及最终采用保护不放宽，预计结束不充当可信实际释放。
- `TrialAdoptionBlocked`复制实际阻止采用的问题并统一为blocker级别，保留其code、消息与任务引用；草稿warning和原保存快照不变，避免采用预检把真实业务原因误判为响应损坏。
- `system_log_snapshots.py`在进程内保存已脱敏、不可变的读取窗口。日志翻页/CSV/ZIP沿原token和范围读取相同内容，主动刷新才读新日志；15分钟、最多32份/64MiB，过期/淘汰/重启/恢复数据代次变化均要求刷新。原完整日志、慢请求写入、公共快照设施及备份写操作不变，不用浏览器回传内容拼导出。
- `PlanDetailsUI`任务详情/计划负荷及`TrialResults`资源表统一使用班表内占用分子，完整安排与班表外占用另列，保留后端旧跨度字段兼容语义；`TrialContract`拒绝缺失班表内分子的响应。`material_actions_context`只对公开预览副本转换UTC创建时间，私有快照与库内UTC不动。
- `master_overview_process`按实际路线/归属/工时阶段给出下一步指引，零值说明只用于真实未确认0。现场直接子弹窗在`35-field.css`设置一致高度预算、固定头尾及可滚动正文，长文件预检不再将确认按钮推出矮屏；不改文件与事务协议。

以上描述源码职责与合同；本轮程序专项、真实UI结果、迁移保留证据及未覆盖动作分别记录在[执行盘点](../roadmap/workbench-manual-remediation/execution-20260915/implementation-and-coverage.md)，不作为整系统手动通过声明。

### 页面状态与故障

- `templates/workbench/index.html`先给可读启动状态，并由独立watchdog显示资源错误或启动超时，不依赖末尾主脚本自己报告缺失。
- `WorkbenchBoundary.jsx`隔离工作区渲染错误，保留侧栏和同对象重试。启动信息或核心资源损坏时提供重新加载入口，不渲染虚假业务页面。
- `WorkbenchNavigation.js`维护精确页面context、辅助历史状态及滚动位置；显式规范URL不被另一对象的旧history覆盖，无效定位不静默扩大为全部范围。
- `WorkbenchPageContext.jsx`让各领域显式登记已验证的只读选择和筛选，不保存写表单、不重放请求；待核实写入仍由原命令恢复协议负责。各域接入与实际回返验收仍在收口。
- `WorkbenchCaption.jsx`只消费领域DTO的真实方案身份、版本和范围。页面切换或卸载清除旧信息，无所选方案不显示样例。主题焦点返回同步不改业务状态。

### 统一交互控件

- `templates/workbench/index.html`以`body.aps-workbench`限定工作台样式和事件范围，不影响旧入口。`main.jsx`常驻挂载公共样式、下拉/日期浮层及数字微调器，后续工作区复用同一套控件。
- `WorkbenchControlStyles.jsx`沿用原主题变量和本地Lucide图标，统一按钮、输入、单选、勾选、滑块、文件选择、分页、展开状态和键盘焦点。工具区32px，编辑字段36px，控件4px圆角；导航、日历格和甘特条保留各自语义与尺寸。
- `WorkbenchControls.jsx`和`WorkbenchSelectMenu.jsx`替代原生下拉菜单、日期/月份/时间弹层；浮层限制在视口内，长选项换行并内部滚动。弹窗内使用局部portal，Esc只关当前浮层，随后恢复原控件焦点；日期支持鼠标、方向键及手输。
- `WorkbenchControlBridge.js`通过原生属性setter及input/change事件更新原React控件，不替换输入节点，不改变保存命令。`WorkbenchNumberControls.jsx`用受控portal添加微调按钮，保留min/max/step、空值和无效输入，处理卸载、重绘与禁用。
- `WorkbenchDatePickerModel.js`使用工厂本地日期字符串和浏览器原生约束校验，不以UTC转换日期，不猜测未填的时间。保留原value attribute作为step基点；时间增减按钮与其他数字微调器一致。
- 所有资源本地交付，不新增目标运行时或依赖。编译使用Chrome109支持的对象展开，避免多个独立脚本生成同名Babel全局辅助函数。系统的文件打开/保存窗口继续由操作系统负责，页面内触发按钮及状态提示使用工作台样式。

### 验证边界

2026-09-12界面质量层补充：

- `navigation_metadata.py`提供导航分组/视图别名，`pages.py`下发`nav_groups/view_aliases/help_url`。菜单显示集合与15视图可达集合分别验证；帮助复用现有只读手册路由，壳层通过`WorkbenchNavigation.helpUrl`附加`src=当前视图URL`，手册页据此渲染返回链接。计划中心页签条由`WorkbenchNavigation.historyView`判定，在排产历史上下文中隐藏；报表/复盘页签切换（`preferSaved`）整体恢复目标页签自己保存的上下文（范围、主题、分页、选中、滚动），只有首次进入才沿用当前范围与返回来源；两个页签各自保留范围是验收锁定的既有设计。
- `app/styles/`按令牌、外壳、控件与领域样式显式排序发布。原型导入保留原文快照并直接核对内容，资产索引登记来源／输入／发布路径及字节数。JSX不再通过runtime style块改变层叠顺序。
- `WorkbenchGuards`管理按owner登记的未保存内容和命令锁定；`WorkbenchGuardHost`单独负责共享Modal呈现，避免classic-script依赖环。导航、历史前进后退、编辑器关闭与外部离开遵守同一退出决定，拒绝时保留URL/页面/草稿。
- `WorkbenchListControls`区分页码与游标分页，档位由既有领域API决定；`WorkbenchDetailPanel`统一用户主动打开后的焦点与返回，自动预览不夺走首屏。共享Field负责字段说明与首错聚焦，错误编号保留在可展开的诊断区域。
- `WorkbenchFormat`区分工厂本地文本和带时区时刻，超大整数字符串单独无损分组；`WorkbenchTerms`统一同义业务术语。格式层不新增领域取值约束，不把未知补零。
- `WorkbenchDensity`只保存本机显示偏好。计划默认选择不覆盖明确来源，实际甘特显示窗口与服务器数据范围分离；报工继续操作只在原回执确认并取得新写入上下文后启动。
- 独立工作台截图／几何／交互按opt-in浏览器入口运行；每份证据记录实际源码、构建和实例身份，发生变化时核对实际影响并补相应验证。

前期专项测试及双尺寸双主题浏览器证据继续保留，不能将旧局部通过重记为最终快照通过。2026-09-16接续时G3/G4/G5/G7与G1放弃已闭环，正向试调采用和最新主实例激活继续收口，具体状态见执行盘点。270587be…的355输入hash及导航92/92只属于22:41冻结阶段，后续已有新修复与b71675b…页面回验，不再把旧构建称为当前最终证明。历史5000同资源工序、四个完整候选的正式隔离测量为122.728285375秒，只绑定当时冻结快照，不自动覆盖最终HEAD。

完整门禁的仓库入口仍为`scripts/run_quality_gate.py`，这是工具事实，不是本轮执行授权。2026-09-15用户明确禁止全门禁，本轮不调用该入口任何模式、不运行整仓测试，仅执行相关专项、构建与手动浏览器验证；未提交工作区不声称clean-worktree proof。历史迁移路线的归档、旧UI退役状态见`../roadmap/workbench-prototype-migration/round2-progress-20260910.md`及同目录`legacy-retirement/`；本轮最新覆盖见上述执行盘点。Win7打包、真机与最终发布仍排除。代码归档不是业务数据库备份，代码回退与新数据保全分别核对，不用旧库覆盖新增事实，未应用的决定不作为已实现能力。

### 2026-09-21 界面全量审查修复

- “管理样例”下线：`SystemSampleControls.jsx` 删除并从 build-order 移出，`SystemLive.jsx` 只读本机数据，`SystemMaintenanceAPI.pageContext` 只接受 `source: "current"`；恢复状态标签以 `SystemRestoreStatus.labels` 为唯一来源，后端 `workbench_system_restore_view.py` 与之逐字对齐并由测试锁住。
- 共享控件：`ResourceControls.jsx` 的 Modal 在打开时记住启动器按钮，关闭后按“启动器 → 父弹窗启动器 → 最近可聚焦容器（`#wb-view-panel[tabindex=-1]`）”恢复焦点（vm 合同 `tests/workbench/modal_focus_restore_contract.cjs`）；带 tooltip 原因的 Button 改用 `aria-disabled="true"` 保持可聚焦并拦截点击。
- 壳层：`main.jsx` 最前面加 `.wb-skip-link` 跳到主内容；帮助链接带 `page=<view id>`，`page_manuals_registry.py` 以视图 id 为键；`theme.js`/`WorkbenchDensity.js` 值未变不通知；滚动记忆 200 ms 尾沿节流并在 `pagehide` 一次性写入。
- 样式 token：主按钮走 `--wb-primary-button-bg/-text/-hover-bg`（深色映射 `--ui-primary-hover` 底 + `--ui-bg` 字）；深色弹窗遮罩靠 `--wb-modal-backdrop-dim`（`backdrop-filter`）；深色表头底色统一 `--ui-surface-muted`；固定操作列阴影 `--wb-scroll-shadow-right/-left`；产能链收起态由 `section.rail[data-collapsed]` 驱动。
- 文案：`tools/ui_copy_glossary.json` 新增停用词“证据”，`scan.backend` 扩到 `core/services/execution` 及会经 `domain_failure`/`WorkbenchCommandRejected` 原样上屏的领域服务文件；`WorkbenchTerms.js` 新增 `refresh_latest`、`accept_latest`、`personal_calendar`、`plan_version`、`download_started`、`data_as_of`、`run_statuses`、`candidate_statuses` 等共享叫法。

### 2026-10-13 同次候选方案比较

- `RunCandidateWorkspace` 的 `analysis` 候选入口挂载 `RunDecisionComparison.Workspace`；首屏一次读取全部候选紧凑总览，按推荐、收益代价、当前选择动作和候选行表组织页面。默认常用指标，完整指标矩阵按需展开；运行搜索覆盖显示一次，算法角色归入选择依据。比较方式可选同次候选或受理时正式计划，采用记录按需展开。
- `RunDecisionAPI` 统一 envelope 和响应身份核对；指标单位、精度、改善方向和范围从服务目录消费，差值由服务计算。失败、跳过和待料暂缓显示保存原因与三轴覆盖。
- 所选候选、查看基准与甘特窗口进入现有 `WorkbenchPageContext`；甘特回跳恢复完整比较上下文。显式 URL 支持候选、运行、查看基准及成对时间窗，沿现有导航入口校验。
- 采用继续接 `renderAdoption` 的原预检/正式事务入口；CSV/XLSX 总览绑定同一比较快照。离线 JavaScript/CSS 由现有 build-order 编译，浅深主题使用工作台 token。
- 第 0、1 阶段交付与界面证据见 `../features/2026-10-13-decision-comparison-loop/`，后续能力按整体路线图推进。

### 2026-10-13 交付与工序影响

- `RunDecisionDetails.Pane` 在候选行表后按“总览 / 批次交付 / 工序变化”页签组织明细。批次显示双方全链完成状态、交期状态、完工与拖期差、改善/恶化及未排工序；工序按永久身份配对，保留多段安排、设备人员、执行、保护与保存的锁定标记。工时需求标注保存工艺标准依据，准备需求的实际排槽分解沿第 4 阶段建设。
- 明细查询使用所选候选、比较模式、基准和共同时间窗；全范围汇总与行筛选分别表达。批次/资源目录覆盖整个比较范围，分页前筛选和稳定排序，默认 20 行、可选 50 行，未知值排末，同值按永久引用排序。
- `RunDecisionAPI` 核对范围、基准身份、筛选、分页与快照。CSV 导出当前一个分区；XLSX 可导出完整比较，当前页签使用该页签筛选，其他分区使用共同范围，页码不限制导出。普通文本原样、null 留空、XLSX 数值保持数值类型。
- 批次/工序行可定位所选方案或比较基准甘特。正式归档通过 `decision/reference-workspace` 读取原安排，保持只读；候选甘特沿原工作区加载。缺时间任务保留在表格和详情，图中仅绘制有效时间。定位窗可覆盖目标安排，返回时恢复原时间窗、所选方案、模式、基准、页签、指标视图及列表条件/页码/快照。
- 新导航沿现有 `WorkbenchPageContext`，显式 URL 校验工序引用、比较页签和指标视图；正式只读上下文必须带运行、所选候选和正式计划身份，同次候选基准仅用于候选模式。旧候选分析、值班台、正式计划与试调前端消费共同交期、完成性和风险枚举。
- 第 2 阶段实施与独立验收已通过，记录见 `../features/2026-10-13-decision-delivery-impact/`。第 3 阶段已派发，第 4—8 阶段等待母任务继续派发。

### 2026-10-13 设备人员资源影响

- 方案对比沿紧凑候选行表增加资源页签，设备／人员共用一张资源影响表和逐日热力图。共同时间窗与 `resource_view` 随总览和明细请求传递；本次选批贡献／完整候选安排均标明正式覆盖缺口、未排和待料范围。
- 资源影响展示双方容量、班表内占用、独立工序需求、班外、重叠、占用率和逐日峰值。整窗容量加权汇总保留固定资源集合；Top10压力和增长可展开全部。筛选排序与20/50分页、热力图日期页分别控制显示，整窗摘要保持完整。
- 单资源逐日展示实际任务和冲突区间；资源／日期／冲突均能定位实际候选或正式归档甘特。甘特按永久资源身份过滤，正式完整视角读取全部归档安排；返回恢复原窗口、视角、类别、资源、筛选排序、列表／日格页和焦点。
- `navigation_boot.py` 接受资源页签、视角、类别和永久资源引用并逐项校验；当前页签内部查询与热力图焦点使用现有 `WorkbenchPageContext` 保存。所有直接URL继续带匹配的顶层view与nav.view。
- 资源／单资源逐日CSV和XLSX由同一服务输出全部筛选记录，完整比较包含资源影响；逐日入口追加该资源完整日期。资源覆盖及逐日冲突为原生数量，XLSX另附“覆盖工序”完整逐条身份、逐日“资源冲突”区间及实际成员；常用标记和来源独立表达。旧候选分析、值班台和试调按共同字段呈现容量、需求、占用及未知原因。
- 本阶段实施与独立验收状态见 `../features/2026-10-13-decision-resource-impact/`；产品继续使用本地静态资源及Chrome109构建目标。

### 2026-10-13 准备需求与工种切换

- `RunDecisionPreparation.Pane` 沿同一比较屏幕提供准备需求、工种切换两个页签。`EffortProjectionContract` 与 `RunOperationEffort` 校验并呈现共同需求账：准备、加工、排槽标准需求、原需求目标、本次执行目标／剩余量及来源；归档工序标准独立展开。历史缺账、已保存但未构造和保存缺项分别说明。
- 准备汇总覆盖整次受理，区分实际新排、普通未排、合法暂缓和保留／执行／完成；切换汇总按共同窗口及资源视角。两页支持设备、各自业务条件、稳定排序和20／50分页，完整汇总和筛选目录保持原范围。
- 准备工序行可定位所选或候选／正式基准；事件行可定位同侧前序、后序。钻取消费保存的永久工序及真实安排行身份，返回恢复共同模式、窗口、视角、候选／基准和两页各自条件、排序及页码。URL白名单接受两个页签，内部查询沿现有保存上下文。
- 总览目录为52项，新增准备／加工8项和实际工种切换2项；准备范围变化使用中性差值，算法保存切换保持独立标签。CSV及XLSX同scope输出准备需求和事件双方原始值，页码只控制屏幕；旧候选、值班台和试调需求／切换读取复用共同投影。
- 第4阶段设计、验证与交接见 `../features/2026-10-13-decision-preparation-events/`。产品静态资产继续由原build-order本地构建，目标Chrome109。

### 2026-10-13 推荐、当前取舍与采用预检

- `RunDecisionRecommendation` 从后端消费三类推荐结论、完成性主因、固定选择解释和当前3+3主要取舍，原生展开保存规则、全部差值、完成集合及真实剩余需求。前端仅格式化数值、单位和状态，理由由共同服务生成。
- 当前查看候选与保存推荐分别显示。切换第三候选／基准后，保存推荐及raw最优／健康基准保留原身份，当前取舍按新基准读取。部分结果显示具体未排、合法暂缓和未知；搜索失败／跳过单列。
- 完成组按各成员独立候选身份读取完整批次分页清单，复用共同完成集合及剩余需求事实；概览保留有界样例。准备明细的 `work_scope=remaining` 与现有筛选取交集，分页、导出和返回上下文共用该条件。组内共同完成集合相同的候选仍分别读取其剩余需求。
- 聚合支撑按钮按保存推荐进入批次、资源、准备或切换页签，具体工序／事件沿真实钻取直接定位甘特；推荐移除安排时定位基准侧原安排，支撑仅采样实际已知变化。内部 `return_recommendation_context` 保存原比较的候选、基准、窗口、视角、页签、指标视图和各列表查询；现有 `return_decision_context` 将其带入甘特并完整回跳。二者使用既有SPA历史状态，显式URL合同沿用原白名单。
- 推荐、排产完整性与当前采用预检各有独立展示。采用仍由原入口读取当前preview并在事务中复验；试调保存后先进行采用预检，通过后再确认。值班台收益／代价接同一差值投影，保留其明确候选、选批和窗口。
- 推荐CSV/XLSX增加推荐说明、完成集合和剩余需求分行表，保存与页面一致的固定推荐、当前查看／基准、范围、版本、数值与缺项。第5阶段实施和独立验收状态在 `../features/2026-10-13-decision-recommendation/`；本节交接时第5阶段已通过独立复验，第6阶段已派发，第7—8阶段等待派发。

### 2026-10-13 优化过程阅读

- `RunDecisionComparison` 在候选表后挂默认折叠过程区，候选依据可打开指定过程成员；展开时 `RunDecisionProcess.Pane` 才读取，当前查看、比较基准与保存推荐继续保持各自身份。
- 外层列全部候选的真实计算来源、profile、配置／实际派工规则、候选自身／来源求解耗时、状态、停止原因和保存最终值。复用来源使用永久引用，已开始预算中断、未开始和失败各有实际覆盖说明。
- `RunDecisionProcessChart` 用本地SVG显示累计求解耗时与主业务目标、单位；同来源、完成性、目标范围及真实评价集合的已核验相邻点才能连线。搜索阶段变化保留连续的同集合过程，未排齐批次成员变化则断线；旧记录已保存`all_batches`且未排齐批次数为0时，共同投影确定空排除集合并保留连续性；部分旧记录缺评价成员时按离散点显示并说明缺项。无严格改善时固定展示全过程，改善聚焦按钮显示“无改善记录”并禁用。缺耗时点保留键盘详情；全部缺耗时的旧档明确使用已保存事件顺序。图形与分页数值表消费相同保存点，完整score仅用于详情。
- 记录表、圆点详情与键盘播报共用评价范围名称，完整性标注评价内应排／完整及评价外结果；完整批次子集的已知0直接显示，未知目标保持缺项。候选元数据中的最终值标为算法保存统计。
- 过程查询叶保存独立成员、attempts/progress、排序、20/50页容量、页码及snapshot。现有 `APSResourceSession` 处理刷新、取消与重试，原 `return_decision_context` 恢复第三查看候选、基准、窗口和过程叶。代表尝试只读取已保存结果，最终候选可进入原甘特。
- CSV分行及XLSX候选计算／进步事件／搜索阶段／代表尝试与屏幕共用读取协议，保留原数、单位、null和覆盖。原离线build-order与Chrome109目标编译两个过程组件，样式限定过程区。材料见 `../features/2026-10-13-decision-optimization-process/`。

### 2026-10-13 计划相关页面的共同信息层级

- 比较、候选／正式甘特、交付风险、资源负荷／班表及同义试调、值班台保留同一事实的一个默认展示位置。身份、范围、安排数量与操作各自归位；编号、读取时间、生成来源、精确边界、评分和数学说明按需展开，正常0值不扩成长句。
- 比较页统一安排现有导航和操作工具组，移除隐藏标题留下的空容器。范围复用`WorkbenchFormat.compactRange`与`compactDateTime`：默认分钟显示，同年缩短日期、跨年保留年份；原查询秒、小数、区间开闭和末端零工时边界保存在原值和详情，打开关闭编辑保持原范围。
- 甘特保留实际`as_of`时刻线并标为“本次刷新时间”，悬停显示分钟；读取日期零点不再另画。甘特详情操作位于图表工具区，原安排对照开启时显示对应图例，未选工序提示归入详情空态。
- 工序已排齐、预计完工、未安排和因缺料暂未安排表达保存安排；现场完工沿执行记录。缺料与其他未安排可以出现在同一批次，汇总按实际非零项说明。推荐主因使用当时目标、真实指标和并列／健康决定项，搜索过程的接受与正式采用分别命名。
- 班表突出可排总时长与时段，普通／急件效率分别折算标准工时并按需显示。资源工序起止合计、班次内实际占用、重叠区间长度、重叠重复计时和班表外占用继续消费各自字段，UI调整不改变计算。

### 2026-10-13 读取与临时编号计算清理

- 进程内读令牌直接绑定规范范围和实际来源状态，保留原`as_of`。正式采用来源状态由共同resolver明确给出可用性与缺项；原来源后补恢复、历史新增、运行非终态进度和查询范围改变仍使旧读取状态失效。
- 缓存键复用查询值、原audit或已留存文档。SGS输入及日历证据用原结构比较，物料行由共同排序序号生成。缓存与临时展示键沿实际业务身份生成；真实归档、命令回放、外部下载与文件更换核对各自承担原职责。
- 本地构建索引只登记来源、路径及字节；便携交付使用ZIP完整性和实际离线启动检查。全仓扫描、具体删除及保留用途记录在`../../evidence/sha256-cleanup/`。

### 2026-10-14 第二版原型正式接入

- 完成及已产出候选的部分结果由 `SchedulingWorkspace` 直接进入原 `RunCandidateWorkspace`／方案比较工作台；等待、计算中、失败及中断读取同一 Job 记录。批次业务名称、工序数量与目标来自接收时归档，接收／开始／结束时间保留保存精度，旧秒级记录明确其精度。
- 全部候选卡保留当前查看、固定对照与保存推荐三个身份。交期页默认列当前超期、缺料及其他未安排批次；差异页依据永久工序的时间、资源、供应商、来源和安排状态变化筛选。`selected_batch_ref` 在候选切换及两类甘特返回时保持，单一全宽详情分别显示当前工序链或真实前后差异。三项差异摘要读取服务端值，零变化中性、未知保留缺项。
- 候选名称、身份、指标和操作各有稳定区域，公共 `C.Button` 的外层 `.wb-button-host` 参与伸展；同排指标与footer对齐。整体未知但已有已知成员时，卡片明确显示保存的已知小计和集中待确认提示；完整覆盖与原主因保留在既有保存依据。窄屏页签按自然按钮宽换行，差异摘要以110px最小列宽换行，沿用系统字体与控件。
- 资源页共用 `heatmap.buckets`／`items[].cells` 表达小时、真实可排班段、天和周；跨夜班段计入起始日一次，次日仅显示延续入口。阈值及高负荷筛选使用返回的有效窗口，小时分页把实际显示时段写入 `filters.display_start/end`，列表、格子贡献工序和导出保持同源；全窗口指标单列。日期／时间和下拉继续走 `WorkbenchControlBridge`，原工厂本地时间及微秒保留。
- 计算过程进入独立页签，图形主线读取完整 `progress`，尝试散点读取完整 `attempts`，表格页码仅裁剪记录表。阶梯使用真实累计耗时；完整事件流为实线，采样缺口明确标注并吸附真实保存点，旧缺耗时记录继续按真实事件顺序显示。准备、切换、指标、采用预检及原始明细入口延续。
- 资源共同读模型为 `decision-resource-v4`：班表内冲突与保留安排跨度分开，跨度跨非工作时间不推断实际加工。正式计划资源主表和冲突详情读取权威班表内重叠时段；旧缺项显示未记录。页面和原生导出分别标注资源版本及原共同指标版本。
- 本轮实现、实际页面、原生文件和保全证据在 `../features/2026-10-13-decision-optimization-process/` 与 `../../evidence/prototype-integration/2026-10-14/`，实施验收与主对话验收分别记录。

### 2026-10-14 历史走势与同条件对照

- `RunHistoryWorkspace.TopicTabs` 在既有“排产记录”入口组织“运行记录 / 历史走势”，默认保留运行查找。`DecisionHistoryWorkspace.Session` 持有时间线、业务／同条件模式、日期、指标、基准、资源窗、筛选排序、条目／条件分页和选中项；查询消费只读服务，前端负责显示与阅读上下文。
- `DecisionHistoryChart.Chart` 与历史数值表读取同一当前页，图按发生时间排列，支持点选、方向键与Home／End。曲线消费每项指标的已知状态、单位、版本、范围和服务给出的连接标记；缺数值或时间保留可选择的条目，原数和具体原因进入详情。列表20／50分页与显示图页保持一致。
- `DecisionHistoryDetails.Details` 一处呈现四类发生身份、保存结果、具体来源、优化目标、生产条件八类逐字段行和算法实验配置。逐字段保留保存状态、原值和出处；同条件结论及逐指标成立依据由共同服务提供。资源详情分别列所选和基准的实际窗口、永久资源集合、占用分子与可排容量分母；缺省各来源起点固定7天与共同绝对窗口独立于时间线日期。
- `DecisionHistoryWorkspace.open` 将同一`return_decision_history_context`带入原运行、原候选分析、原试调或正式甘特。`RunDecisionComparison`与`RunCandidateWorkspace`沿现有甘特返回链透传，`SchedulingWorkspace.HistoryReturn`与`TrialWorkspace`提供“返回历史走势”；`navigation_boot._decision_history_state`按共同query校验URL内选中、基准与图指标。返回恢复原时间线、模式、基准、指标、日期、资源窗、排序筛选、分页、选择及快照。
- 历史导出弹窗选择条目、生产条件、算法配置或XLSX全部分区。条目文件覆盖筛选全集，条件与配置对应选中条目及明确基准；页码只控制屏幕，下载仍走既有取消、错误和原生文件通道。三个历史组件及`36-decision-history.css`登记在离线build-order中；完整历史说明同步`page_manuals_scheduler_outputs.py`与系统手册第6.3节。共同帮助按历史主题分别打开analysis与run章节，并附返回视图；缓存模块由宿主正常加载。
- 零匹配沿共同空态提供清除日期与状态筛选入口，保留时间线、指标、基准和资源窗；越页恢复第1页继续原快照。三组页签使用系统主题选中色与键盘焦点。条目、基准选择、图和详情统一消费目录`label`，运行序号从完整未筛选目录确定，发生时间保留独立字段。
- 代码入口：`frontend/workbench/app/RunHistoryWorkspace.jsx:TopicTabs`、`DecisionHistoryWorkspace.jsx:Session/Export`、`DecisionHistoryChart.jsx:Chart`、`DecisionHistoryDetails.jsx:Details`、`SchedulingWorkspace.jsx:HistoryReturn`、`web/routes/workbench/navigation_boot.py:_decision_history_state`。设计依据：[历史走势与同条件对照](../features/2026-10-14-decision-history-trends/decision-history-trends-design.md)；本节更新实现职责，阶段验收材料保持独立。

### 2026-10-15 统一优化与保存结果读取

- 新运行使用一次共同预算/解码/档案，发布1—3份实际业务代表；保存推荐、当前查看与比较基准仍各自持有身份。各目标winner可指向同一代表，部分结果依已知完成集合表达，目标搜索机会与安排完整性分别读取。旧4/6/8候选、weight/health/selection及复用/失败/跳过继续读取原保存值。
- Schema42包含v41的三类不可变`decision-read-v1`保存读模型，以及v42原生business_objective候选与四目标role。受理与完成事务构造读模型，查询保持只读，缺行/损坏/未知版本明确失败；历史升级沿显式迁移，不在首次浏览中补写。
- 资源首开或父scope刷新调用一次`decision/resource-workspace`，同一快照/source返回完整summary与resources；资源错误保留已成功summary并沿原资源错误/重试入口表达。无可查看完成候选时resource_result为null。普通summary/resources/resource-days接口及各自token保持，资源分页/筛选/刷新只读资源；切页签或隐藏重开复用现有成功状态。
- 服务保留201等实际资源集合、完整候选范围和全窗统计，显示页仅决定完整cell/钻取投影；请求内日历、measurement和前缀统计共用。当前可见20×7与完整100日统计分别负责显示和计算；关闭的详细汇总保持保存内容，首屏以真实可见容量、占用、资源总数和热图判定。
- 过程页与导出沿保存字段显示“跳过执行次数”和“不同计算请求”；同一排法请求可多次尝试，跳过按次数记录。总运行耗时与首次发现时刻分开，保留原64/40等实际存档值和旧缺项。操作帮助同步同一口径。
- 当前共同runtime和真实阶段会话承担执行，固定图档、旧选择/health重算与旧独立缓存退出结果生成；内部图profile、SGS评分交接及decode checkpoint证书保持。配置退役四字段保留历史值，新页面只提交有效字段，旧客户端明确刷新。离线资产继续由原build-order构建，目标Chrome109。
- 实施与主验收分别见[统一优化feature](../features/2026-10-13-unified-scheduling-optimization/unified-scheduling-optimization-design.md)和`../../evidence/unified-scheduling-optimization/2026-10-14/`。U5质量/性能绑定其原冻结状态，U6整合与最终实页结果另存；Windows延期。
