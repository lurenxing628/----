---
doc_type: design
status: approved
created: 2026-09-09
scope: cross-module-contracts-only
implementation_authorized: true
---

# Workbench 跨模块合同草案

本文已随总体方案获用户确认，定义各实施包共同遵守的协议，不宣称所有拟建API/数据结构已经存在。领域内部算法与表实现由对应feature设计；现有可复用入口/字段以两份后端评估的源码证据为准。D01-D08见主方案。

## 1. 外壳与离线资产

- 拟建入口`GET /workbench?view=<view>`和`GET /workbench/trial`，最终`GET /`使用新工作台。允许view固定为现有14项，未知值给明确页面错误，不把未找到的方案换成latest。
- 工作区资产随现有Flask本地服务交付，路径隔离为`static/workbench/`；不把旧base.css/ui_contract.css无选择叠加到样板。现有SVG图标、字体策略和主题token按基线处理，无CDN、远程字体或目标机Node进程。
- 构建`asset-manifest.json`包含相对路径、sha256、字节数、MIME、依赖、许可证来源和Chrome109目标。若采用D01，使用已有JSX编译能力在开发/打包端生成生产JS，不在交付HTML保留`text/babel`或Babel standalone。
- 样板`aps_kit_theme`与产品`aps_theme`共用主题适配器：产品正式键`aps_theme`优先，缺失时才读原型键，再读合法cookie/默认；保存同时更新正式键和兼容键，只改偏好不改计划。此优先级已在首项联调中修正，避免旧页后来切换主题仍被原型残留值覆盖；有22条回归断言。存储不可用明确反馈，不吞掉保存失败。
- 路由上下文：`{view, entity_ref?, plan_ref?, baseline_ref?, scope?, return_to?}`。URL仅可序列化合法view、业务ID和公开引用；`return_to`只允许站内已登记目标，不带任意URL或深层递归。搜索/页码/折叠/滚动属于页面偏好，不当作生产事实。
- 展示层接口统一为`load(context, signal) -> Promise<WorkspaceData>`、`command(action, input) -> Promise<CommandResult>`、`navigate(target)`。不同页面不得继续从固定全局样例对象读正式数据。失败不得回退到seed并显示连接成功。

## 2. HTTP与状态

拟建JSON前缀`/api/workbench/v1`，继续同一本机Flask实例和领域服务，不建立另一个后端。旧表单端点保持原合同直到退役；新前端不得通过旧HTML/flash字符串解析业务结果。

```text
QuerySuccess<T> = {
  ok: true, schema_version: 1, data: T,
  meta: {request_ref, source: "production"|"demo", as_of, time_basis:"factory_local", snapshot_ref},
  warnings: [{code, message, entity_ref?}]
}
Failure = {
  ok: false,
  error: {code, message, fields:[{path,message}], entity_ref?, retryable, request_ref},
  committed: false|true|"unknown"
}
CommandInput<T> = {request_key, write_token, input:T}
CommandResult<T> = {ok:true, result:"committed"|"unchanged"|"partial", data:T,
  receipt_ref, replayed:boolean, warnings:[]}
Accepted = {ok:true, result:"accepted", job_ref, status_target, replayed:boolean}
```

- 请求/校验错误400；对象不存在404；旧快照/重复请求内容冲突/业务状态冲突409；业务字段约束422；维护中503；未预期错误500。HTTP成功不等于完整业务成功，批量部分结果必须逐项列明，不能只返回总数。
- 公共错误码至少`invalid_input/entity_not_found/stale_write/snapshot_stale/plan_not_writable/constraint_conflict/request_key_conflict/maintenance_active/storage_failure`；页面显示中文message/字段定位，不把内部异常、英文代码或裸ID贴给普通用户。
- `committed=unknown`时提供按`request_key`查询结果，前端显示“结果待核实”，不自动重做写入。已提交主事务后日志/下载失败与主事务失败分别报告。
- 演示source不接受生产`write_token`。服务器独立验证上下文，不能仅依赖按钮disabled或客户端source字段。
- Accepted只说明持久受理，不是完成回执；页面保持进行中，直到查询到终态。普通SQLite写事务、异步运行与文件恢复的回执边界分别执行第3节规则，不能通用地声称全部动作是一次DB事务。

## 3. 身份、并发与幂等

```text
EntityRef = opaque stable reference
PlanIdentity = {
  plan_ref, version:int|null, kind:"official"|"candidate"|"draft"|"scenario",
  is_current_official:boolean, display_name, source_run_ref?, baseline_ref?,
  completeness:"complete"|"partial"|"invalid"|"unknown",
  capabilities:{view, edit_draft, adopt, report_actual}, blocked_reasons:[]
}
WriteContext = {write_token, expires_at, capabilities, blocked_reasons}
```

- `plan_ref/task_ref/report_ref/draft_ref`等是稳定公开引用，不能是裸`op_id/schedule_id/candidate_id/scenario_id`或把它们拼成可逆字符串。实体映射由持久层管理，重启不换对象；引用不是登录/授权凭证。
- `operation_ref`在执行领域指一个有独立生命周期的批次工序/分件实例，跨计划版本不变；同批次同序号被显式重建时也不能复用旧实例引用。`task_ref`指某个plan_ref里的该工序排程安排，严格绑定版本/候选身份；跨日显示分段使用segment_ref，不新增执行工序。异步作业使用job_ref，不与执行实例混用。
- 新报工保存`operation_ref + recorded_against_task_ref + recorded_against_plan_ref`；后两项是录入时依据且永不随新采用版本改写。采用新版本后，由服务端通过operation_ref关联真实历史事实到新的current_task_ref，不能按批次号/序号猜关联。历史查询的原计划基线继续由原plan_ref/task_ref提供，不能被当前安排替代。
- 现有进程内`plan_context_token`有过期/重启失效特点，不用它充当新永久实体主键。兼容旧token时通过原解析器核对后再转新引用，失效明确提示。
- `write_token`为短期服务端上下文，绑定实体、当前内部revision、计划/执行快照、允许动作及范围；内部revision不直接暴露到普通页面/导出/URL。重启后旧令牌失效，用户刷新复核输入后重新提交，不静默换令牌覆盖。
- `request_key`是单次意图幂等键。同键同规范化载荷返回同receipt；同键异载荷409。普通SQLite业务写入的令牌/最新事实校验、业务变更和持久化receipt在同一事务；单靠浏览器禁用按钮不足。允许逐项提交的批量动作，每项也有稳定结果，批次回执准确列partial，不能宣称全批原子。
- 异步排产分两次短事务：受理事务创建唯一run_ref、规范化输入和受理回执，成功后才能交给worker；计算期间不持写事务；候选结果、结果回执和run终态在结果提交事务一同写入。重启按request_key/run_ref核对结果：已提交则恢复终态，确未提交且没有活动执行者才标interrupted，绝不因浏览器断开或轮询超时重跑。
- 文件恢复/删除与SQLite不可组成同一原子事务，采用独立维护作业和持久文件journal。journal位于受保护的维护日志目录，不在被替换的数据库内，不被普通操作日志清理；包含job_ref、请求摘要、目标/保护副本指纹、阶段和结果，不存敏感凭证。恢复前先持久记录意图和保护副本，恢复后校验，再记录终态。
- 维护状态至少区分accepted/checking/protecting/restoring/verifying/succeeded/failed/rolling_back/rolled_back/rollback_failed/recovery_required。启动在任何普通写库/自动迁移/自动维护前核对未终结journal；证据不能确定完成或回滚时保持维护态，保全文件，不重复执行。配置保存仍属普通DB事务；备份恢复不借DB回执缺失认定未执行。
- 同一业务对象竞争写入串行校验；预览不持长写锁。批量输入必须精确列出对象引用，隐藏选中项也在确认范围中；不能将“全选当前筛选”偷偷变成全库操作。
- 接入新事实或主数据时，读取旧界面未展示字段并保留。省略字段表示“不修改”，显式null必须符合该字段可空合同，不能按表单默认值覆盖存量。

## 4. 统一时间、范围和分页

```text
Scope = {
  source:"production"|"demo", plan_ref?, baseline_ref?,
  plan_finish_date_from?, plan_finish_date_to?,
  range_start?, range_end?, resource_type?:"machine"|"operator"|"batch",
  resource_ref?, batch_ids?:string[], query?:string, focus?:string,
  as_of?, snapshot_ref?
}
Page = {number:int>=1, size:int, total:int, pages:int, sort:[{field,direction:"asc"|"desc"}]}
```

- 工厂时间为`YYYY-MM-DDTHH:mm:ss`本地墙钟值，不加Z冒充UTC；所有服务使用统一工厂时间策略，浏览器轴换算与显示使用同一策略。日期`YYYY-MM-DD`合法范围由服务验证，实际记录不得晚于服务确认的当前时点。
- 日期型交期保持后端`due_exclusive`语义；页面若显示具体时分，必须标明来自哪种截止定义，不能把原“某日内完成”变成该日00:00超期。
- 报表/复盘按样板“计划完工日期”选择工序；资源条件匹配计划或实际资源所关联的工序，选中的工序全部有效报工参与统计。工序集合与报工行集合分开计数。
- 10分钟偏差边界按样板统一处理：提前或延后不超过10分钟为按时，超过才属晚；到期未确认不等于未生产。不要把此阈值暗中用于批次交期或排产优化。
- `snapshot_ref`绑定规范化筛选、业务数据版本和as_of；表、指标、图、详情、导出来自同一读取快照。已过期数据返回snapshot_stale，要求显式刷新，不在分页或下载时静默换范围。
- 列表/详情的数量是全过滤范围的真实计数；过滤/排序在分页前完成。导出为同范围全量或明确选中集合，不只导出DOM可见行。现有产品上限仍适用，超限必须明确拒绝或使用已批准的文件任务，不静默截断。
- 甘特轴范围来自真实计划/日历，不能固定两个日班；折叠仅可折叠确无工作区间，夜班/跨夜工序必须可见。条宽等于时间占用，选中/hover不扩大hitbox，冻结列和轴滚动同步。

## 5. 主数据、工艺、批次与文件

共享只读形状：`Entity{ref,business_code,label,status,fields,relationships,issues,write_context}`；关系以真实两端引用表达，不从中文chip或DOM文本反推。实体种类白名单为part/op_type/machine/operator/supplier/material/calendar/batch，字段合同引用运营后端评估第3至5节；不提供任意表名/字段写接口。

| 拟建操作 | 输入关键字段 | 输出/约束 |
| --- | --- | --- |
| `GET /entities/<kind>`、`GET /entities/<kind>/<ref>` | filter、Page或公开ref | 类型化实体/关系/问题；无数据、未读取、读取失败分别表达 |
| `POST /entities/<kind>/create`、`POST .../<ref>/update` | CommandInput +该类白名单字段 | 真实实体及新write_context；保持不展示字段；引用保护沿用领域服务 |
| `POST /entities/<kind>/bulk-preview` | action、明确refs、patch | preview_ref、每项前后值/影响/不可执行原因；不写业务表 |
| `POST /entities/<kind>/bulk-confirm` | preview_ref、request_key、write_token | 重新核对预览版本/范围；返回逐项结果与实际事务政策 |
| `POST /process/<part_ref>/route-preview` | 原路线、规范化seq/op_type_ref/source列表 | 识别/未知项/工序顺序/分组影响；不改正式模板 |
| `POST /process/<part_ref>/stage-confirm` | stage:route/source/hours、preview_ref、stage fields、CommandInput | 原子保存该阶段与确认人/时间/依据；后阶段可用性来自服务端，不只切前端stage |
| `POST /batches/<ref>/sync-template-preview`、`.../confirm` | template_ref、write_token、严格缺项策略、request_key | 不覆盖已发生执行事实；预览与确认间模板/批次变化409 |
| `POST /imports/<kind>/preview` | multipart file、mode、scope | preview_ref、文件hash、模板版本、统计、逐行错误、commit_policy |
| `POST /imports/<kind>/confirm` | preview_ref、write_token、request_key | 重新核对文件/模式/引用/事实；全部或逐项事务政策须与页面承诺一致 |
| `GET /exports/<kind>`、`GET /templates/<kind>` | snapshot_ref、格式、明确选中refs（如适用） | 正确MIME/文件名/完整字节；附带一致范围的业务标识和时间 |

字段单位：quantity为有限非负整数（创建批次必须正整数），hours为有限非负数，周期days为领域规则允许的正值，库存数量和单位分开；0与尚未填写用值/unknown状态区分。实体ID沿现有业务唯一性规则，不自动改码规避重复。

显式新增关系不替代旧授权：人员工种登记不自动授权全部设备；供应商多工种不复制供应商编号；班次档与个人日期例外的优先级必须由日历服务统一实现。旧inactive原因未知时保留原值，不能导入后全部认定为请假。

批次样板三种导入模式全部保留：新增、覆盖/更新、替换；真实名称/影响依表单显示核对。替换模式必须展示删除集合并保护已执行/引用数据。所有导入预检结果必须注明是否有允许的审计写入，不能误称文件预检绝对无任何写点。

## 6. 执行事实与分次报工

```text
ProductionReport = {
  report_ref, report_no, operation_ref, recorded_against_task_ref, recorded_against_plan_ref,
  source:"manual"|"excel",
  actual_start:null|local_time, actual_end:null|local_time,
  completed_quantity:null|int, effective_processing_hours:null|number,
  actual_machine_ref:null|EntityRef, actual_operator_ref:null|EntityRef,
  remark, recorded_at, correction_history:[], write_context
}
ExecutionProjection = {
  operation_ref, current_task_ref, comparison_task_ref, plan_identity,
  target_quantity, target_basis:"batch"|"piece",
  known_completed_quantity, quantity_complete:boolean, unknown_record_count,
  records_complete:boolean, first_actual_start?, confirmed_finish?,
  execution_state:"unreported"|"started"|"partial"|"paused"|"exception"|"complete",
  completion_basis:null|"complete_reports"|"legacy_finish_event",
  data_quality:"complete"|"incomplete"|"legacy_incomplete"|"invalid",
  reports:[], legacy_facts:[], remaining_quantity:null|int, remaining_plan:null|PlannedInterval,
  data_gaps:[], write_context
}
```

- 拟建`GET /execution/tasks`、`GET /execution/tasks/<task_ref>`、`POST /execution/tasks/<task_ref>/reports`、`POST /execution/reports/<report_ref>/supplement`、`POST .../correct`；写入均为CommandInput。更正必须有reason和原值引用，旧版本不可直接覆盖。
- 任务目标量由批次工序/分件实例权威确定，不一律用Batches.quantity。未填qty/hours是null不是0。有效加工小时不能由计划时长或实际跨度填补；开始/结束齐全时校验小时不超跨度。
- 部分报工的actual_end只结束这次记录，不终结整道工序。由新逐次记录推定整道完成，需要累计数量达目标、没有超报、所有必要记录字段齐全，由服务端事务内重算。已有合法旧完工事件是独立完成证据，不受新增完整性字段缺失影响。
- 同一工序可有多次记录及实际资源变更，关系合法性由服务校验；不把每次记录翻译成旧事件状态机的finish。新增逐次事实和旧事件在唯一执行投影中整合，排产/重排保护、实际甘特、报表和校准必须消费同一投影。
- 旧事件保持原始内容、身份和顺序，单列legacy_facts，不伪造ProductionReport或加工小时。旧工序可同时execution_state=complete、completion_basis=legacy_finish_event、data_quality=legacy_incomplete；仍阻止重排，不能因数量/工时未知变成partial。未知剩余量为null，不能自动作零或重新排产。
- 旧已知数量和新补充数据须按来源关联去重，不重复累计。对旧事实补齐要有明确legacy_fact_ref及新的审计记录，保留原事件；无法无歧义关联时拒绝推断。旧完成证据与数量发生矛盾时保留已完成事实并标invalid/需复核，不静默用较新表格数值覆盖完成证据。
- 更正可能改变完成状态，但不能撤销已有下游生产或已采用安排的事实；若会破坏执行约束，拒绝并列冲突，要求先处理影响，不静默重开整道工序。前后值、原因、操作者、时点和幂等receipt一并持久化。
- 报工模板仍为样板逐次十列合同，5000行上限保留；重复导入不累计，未知字段可补齐，已知事实冲突拒绝，更正走明确动作。报工导出XLSX与旧任务反馈模板不是同一种文件。

## 7. 排产、候选、试调与采用

```text
PreflightInput = {batch_ids, start_date, end_date, ready_check:boolean,
  missing_resource_policy:"auto_assign"|"exclude", completed_policy:"preserve_actuals"}
PreflightResult = {input_ref, included_batches, excluded_batches:[{batch_id,reason}],
  eligible_tasks, auto_assign_required, skipped_tasks, blockers, warnings,
  effective_config, effective_start, calendar_check:"not_evaluated"|"checked", write_context}
RunResult = {run_ref, state:"queued"|"running"|"complete"|"partial"|"failed"|"interrupted",
  stage, progress:null, plans:PlanIdentity[], result_persisted:boolean,
  error?, started_at?, finished_at?}
TaskProjection = {task_ref,operation_ref,plan_ref,batch_id,process_label,source,machine_ref,operator_ref,
  start,end,locked,predecessor_refs,edit_context,issues:[]}
Validation = {status:"valid"|"warning"|"blocked",can_adopt:boolean,
  issues:[{code,message,severity,task_ref?,related_task_ref?}]}
```

| 拟建操作 | 合同 |
| --- | --- |
| `POST /scheduling/preflight` | PreflightInput -> PreflightResult；真实只读业务检查，不调用正式run生成版本；自动排除前序时必须连同受影响后序解释，不产生断链可排结果 |
| `POST /scheduling/runs` | input_ref、write_token、request_key -> 202+RunResult；单机受控worker、沿用运行锁，无云队列。阶段来自实际执行，不造百分比；不增加样板没有的取消动作 |
| `GET /scheduling/runs/<run_ref>` | 持久化任务状态/结果；重启将确未提交的运行标interrupted，已提交候选集合不能误报失败再次生成 |
| `GET /plans`、`GET /plans/<plan_ref>/workspace` | 同一Scope返回方案选择项、身份、基线、任务、批次、日历/产能、风险/变更；候选明细缺失不能从摘要重造甘特 |
| `POST /plans/<plan_ref>/adopt` | write_token、request_key、confirm、reason、declared_operator -> 新official plan_ref/version及receipt；实际应用操作者由本机服务记录，声明人单列，不伪装认证身份 |
| `POST /trial/drafts`、`GET /trial/drafts/<draft_ref>` | 基础plan_ref与当前事实快照 -> 可重启恢复的editing草稿和任务投影 |
| `POST /trial/drafts/<draft_ref>/change` | task_ref、目标设备/人员、目标开工、write_token、request_key；保持工时不变由服务端算end，一次原子保存资源+时间并返回Validation和新投影 |
| `POST /trial/drafts/<draft_ref>/save` | 名称、write_token、request_key -> scenario_ref、preview target、Validation；与新official版本不同 |
| `POST /trial/drafts/<draft_ref>/discard` | 明确草稿引用与确认 -> 草稿状态变化；不删正式计划、场景历史或采用记录 |

- 候选生成与正式发布分离。旧run的自动正式持久化行为不得偷偷改变给旧调用方；新工作台使用明确candidate-set生命周期。正式采用在同一事务核对基础计划仍当前、执行事实未漂移、资源/日历/前后序/锁定全部合法，再写完整计划、版本及审计。
- 现有代表三方案继续使用真实角色/明细；不能把“原算法代表”错当上次正式基线，不能将样板三组名字直接硬映射成并不存在的引擎策略。基线默认运行开始时的当前正式方案；无基线明确显示无可比数据。
- 保存冲突草稿可以保持可编辑，但can_adopt=false；不得因HTTP成功就画“约束已通过”。设备匹配不自动假设某个默认人员，固定工序与真实已开始/完成事实受服务端保护。
- 新正式版本号由数据库事务分配，不用localStorage的v+1。幂等采用只能生效一次；旧当前正式在新版本完整提交之前不消失。
- 风险分类统一为on_time/overdue/incomplete/unscheduled/invalid_data/unavailable；未排完或坏交期不能算按时。换型/成本指标无真实计算时为null并显示原因，不能保留固定样板数字。

## 8. 报表、校准、处置和维护

### 8.1 分析

拟建`GET /analytics`及`GET /analytics/export`，输入Scope+topic(delivery/records/machines/people/quality)。返回同一cohort的操作行/逐次行/资源汇总、summary、charts、data_gaps、Page、snapshot_ref。未知有效工时不混作0，整道完成率分母为已到期的计划工序，不标成批次交付率；已报工时不标成设备利用率或人员效率。

目录四报表拟建`GET /reports/<kind>`和`.../export`，kind=overdue/utilization/downtime/official-review；包装已核查ReportEngine/执行复盘服务，保留正式身份和现有导出上限。统一Scope在语义不等价时显式转换/拒绝，不能把“计划完工日”参数直接当旧利用率窗口。

### 8.2 校准

拟建`GET /calibration`、`GET /calibration/<suggestion_ref>`、`POST .../adopt`及`.../export`。建议包含template_operation_ref、旧定额、建议值、sample_count、sample_refs、筛选/剔除原因、method_version、generated_at和write_context。

D05建议口径：同模板工序修订、已完整完工且qty>0的近20个有效样本，至少5个；每个样本=有效加工小时合计/完成数量，排除有已知异常/暂停污染、工时或数量未知、无法确认加工口径的样本，不从备注关键词推断。中位数作为建议；旧定额为0/未知时不给无穷偏差率。数据不足保持不可采纳，不以示例补样本。

采用必须复核样本与旧定额未变化，原子更新模板定额、来源/人/时/原因和锁定标记；只影响后续模板使用。普通工时导入跳过锁定项并报告数量/原因，不能覆盖后再补标记。既有批次、历史计划、历史实际不随之改写。全部边界需D05确认后才实施。

### 8.3 值班台与主数据总览

拟建`GET /dashboard`、`POST /dashboard/items/<item_ref>/transition`。处置输入完整保留样板字段：target_status（原status）、owner、deadline、action、remark、completed_at（原completedAt）、completion_evidence（原completionEvidence）、evidence_reference_text（原evidenceRef）以及CommandInput；关联真实附件/对象时另用evidence_ref，不把用户填写的凭据文字当成已核验文件引用。状态为new/following/awaiting_verification/closed，中文保持待分析/跟进中/待验证/已关闭，服务给出allowed_transitions。

remark为本次核实备注，保存必填；非new状态还必须有owner/deadline/action。关闭必须有不晚于服务当前时点的completed_at、具体完成结果和可核对凭据，不能只填“已处理/已完成”；填写凭据不等于系统已核验凭据存在。已closed记录只读，普通更新拒绝；重开只能由独立reopen动作并填reason，追加前后状态历史，转following，清空本轮完成字段但永久保留原关闭时间/结果/凭据。无变化不追加重复历史。关闭处置不能删除风险来源或抹掉未齐套/晚交事实。

`POST /outsourcing/receipts`保存真实发出/回厂与对象引用，不能改供应商默认周期冒充实际回厂；值班台回填统一调用报工领域服务。`GET /master-overview`直接从原始实体/关系生成八域检查和维护目标，不解析DOM。规则失败/域未读取/无数据分别显示，导航保存后重新读取。

### 8.4 系统维护

拟建`GET /system/overview`、`GET /system/backups`、`GET /system/logs`、`GET /system/config`，查询业务只读，不以读配置顺便修正旧异常值；页面JS自检不代表DB或备份健康。自动维护仍沿现有“请求触发检查”，不虚构定时执行承诺。

备份创建/恢复/单删、诊断包、配置保存以分离CommandInput动作包装现有BackupManager/维护服务。恢复/删除需同样式的确认窗与目标摘要；配置先读取真实快照再编辑/检查/保存，留空不得覆盖未展示字段。恢复锁、恢复前保护副本、完整性检查、失败回滚及错误留痕不可绕过。

备份记录明确区分file_exists/verification_state/last_run_result，未检查不标通过；日志的操作记录和运行文件分别标来源，统一筛选不改变两者可写性。任何新API不得接收任意本机文件路径来代替服务签发的backup_ref/file_ref。

## 9. 验收证据合同

`CapabilityEvidence{capability_id,action_id,source_fingerprint,fixture_ref,environment,backend_result,
browser_input_method,interaction_trace,visual_images,visual_review_result,persistence_result,
failure_cases,artifact_checks,reviewer,checked_at,status}`。

status只能为not_run/passed/failed/blocked/approved_retired/not_applicable_with_reason；本轮全部迁移动作未执行。分母含实际可达样板入口，潜在未达项单列决定，不因旧UI无接口或当前disabled而删。

完成必须具备：全动作B/K/V/P适用证据、复杂真实业务、已校准容量目标、正式源代码备份/恢复、旧UI已退役的最终包、Win7真机及完整门禁。所有自动化与人工证据绑定最终源/包hash。基线测试通过只证明基线，不传递为新包通过。
