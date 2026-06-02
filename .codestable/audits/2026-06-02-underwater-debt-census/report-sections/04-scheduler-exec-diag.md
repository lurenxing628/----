## 04 · 分区【scheduler-exec-diag】执行事实与诊断

> 覆盖 `operation_execution_*` / `execution_fact_provider` / `execution_snapshot` / `schedule_delay_diagnosis_*` / `operation_execution_feedback_service`(9 文件)。

> **分区健康一句话**:**地基扎实,残渣集中在边角**。承重骨架很硬——`OperationExecutionEvents` 有 schema 级 CHECK + NOT NULL + 唯一索引契约(`migration_operation_execution_contract` 还带坏值探针)、写入幂等 + 乐观锁(state_revision)、dashboard 读现场事实失败会把错误抛到页面(符合"不自欺"灵魂)。问题集中在两类:(1) 一层"被 DB 不变量架空的死防御"(reported_status 兜底表、死键),都因 schema 约束永不触发;(2) 一组 specced-but-prod-unwired 的公开 API(延期诊断三件套)只剩契约测试 + roadmap 续命。**唯一危险的是写侧 adopted-only 护栏(P2)缺注释**(详见 §90 LB-A3)。无 P1 假冒计算值,无活跃 P4 静默吞错。

> 本分区 9 条:1 条承重护栏(P2,已在 §90 详述)、2 条 P3 半截迁移、2 条 P5 私有实现、4 条 P6 死面包屑。

---

### 4.1 【P2 · high · load_bearing=TRUE】⚠️承重护栏:现场反馈写侧 adopted-only 硬拒 + 写死消毒,无注释保护

**位置**:`core/services/scheduler/operation_execution_feedback_service.py:347-356`(硬拒)+ `:451-453`(写死消毒)

> **本条是承重护栏,完整论述见 §90 LB-A3**(execution_review「只复盘正式采用方案」纵深防御 4 处之一——写侧那一处)。此处只记要点。

- **守的不变量**:现场反馈只能写在当前正式采用方案上,禁止预览/scenario 冒充正式现场记录。
- **不对称实锤**:对照延期诊断**读**服务 `_resolve_strict_plan`(`schedule_delay_diagnosis_service.py:137-138`)是 `resolve_plan_view` 接受 scenario_key 的——**读可带 scenario,写禁带 scenario**,这是刻意的读写不对称。三重护栏:路由 `_identity_allows_query_membership_check` + 此处校验 + schema CHECK(`source_table='schedule'`/`effective_plan_role='adopted'`/`scenario_id is null`)。
- **删了会炸什么**:把 `_build_event_payload` 三个写死常量改成透传 context、或删 `:347-356` 拒绝分支,现场反馈可被写到候选方案/scenario 预览上,污染"正式采用方案"的现场执行事实;下游重排护栏(`schedule_execution_guardrails` 读 `ExecutionFact`)会把预览态当真实现场,坏数据进排产决策。
- **复核结论**:✅ 证据仍准(`:347-356,451-453` 当前 HEAD `b08162cd` 已复核,行号一致;grep 注释仍零命中)。
- **🔧 该补注释**:见 §90 LB-A3 逐字文案。

---

### 4.2 【P6 · medium】ExecutionFact 两死字段,拖着一次每调必跑的无用 DB 查询

**位置**:`core/services/scheduler/execution_fact_provider.py:20-21`(字段定义)`,42-43`(赋值)`,96`(死查询)

**引用链**
- 字段 `last_event_schedule_version`/`last_event_schedule_id` 定义 `:20-21`、赋值 `:42-43`(来自 `latest.schedule_version/schedule_id`)。
- grep 全仓(core/web/data/tests)除定义/赋值外**零命中**——连测试都不读。
- 赋值来源链:`list_by_op_ids:96` 调 `event_repo.list_latest_events_by_op_ids(ids)`;而 `_fact_from_state` 里 `latest` 参数**仅**用于这两个死字段(`:42-43`),`ExecutionFact` 其余字段全部来自 `state`(`aggregate_states_by_op_ids`)。
- `list_latest_events_by_op_ids`(repo:254)的生产唯一调用方就是 `:96`。
- 真实消费方(schedule_execution_guardrails/persistence_guard/gantt_tasks/dashboard_workbench/gantt_adjustment_publish_service)只读 actual_status/actual_start_time/actual_end_time/actual_machine_id/actual_operator_id/op_id/state_revision。

**为何算债**:两字段被算出来后永无人读;唯一存在意义是触发 `list_latest_events_by_op_ids` 这次额外全事件查询(每次 `list_by_op_ids` 都跑)。死面包屑 + 被它吊住的死查询。

**爆炸半径**:删两字段 + 不再调 `list_latest_events_by_op_ids`(其本身也仅 `:96` 调用,连带死),零生产消费方受影响。误判风险低——已 grep 实证连测试都不读。

**处置**:删字段 + 连带删 `list_latest_events_by_op_ids`。属真债清理册第二档(#14)。

**复核结论**:⚠️ 涉及 report/gantt 上游消费方,b08162cd 改过 gantt_tasks,动手前重新 grep 两字段确认仍零读取。

---

### 4.3 【P3 · medium】延期诊断公开 API 三件套 prod-unwired

**位置**:`core/services/scheduler/schedule_delay_diagnosis_service.py:42-54,114-139`(`diagnose_plan_overdue`/`diagnose_batch`/`_resolve_strict_plan`)

**引用链**
- 生产入口 `report_engine.py:200,213` 都只调 `diagnose_resolved_plan_overdue`(传入已解析好的 resolution)。
- grep 全 web/core/data:`diagnose_plan_overdue` 生产零调用(仅本文件 `:122` 被 `diagnose_batch` 调),`diagnose_batch` 生产零调用,`_resolve_strict_plan`(`:134`)唯一调用方是 `diagnose_plan_overdue`(`:49`)。
- 即:三者构成一个**生产不可达的自洽子图**。
- 续命来源:`tests/regression_scheduler_delay_diagnosis_contract.py:262/332/349/362/382` + **roadmap `aps-three-gap-directions`(当前分支)`roadmap.md:492`** 把 `diagnose_batch` 列为公开 API 签名、`items.yaml:83` exit_checks 引用两者。
- git:二者生于 `f5f2f1ea`(第2阶段诊断核心服务),`diagnose_resolved_plan_overdue` 后在 `a0cfa3e7` 加入并成为实际生产门。

**为何算债**:specced-and-built 的公开 API,但 UI/report 层改走 `diagnose_resolved_plan_overdue`(自解析 resolution),把带 plan_role/scenario 自解析的 `diagnose_plan_overdue`/`diagnose_batch` 晾在一边。是迁移到 resolved 入口后没收尾的旧入口,**还是有意保留供未来/外部调用的契约 API——需裁决**。

**爆炸半径**:若当残渣删,会破坏 contract 测试多个用例,并与 `aps-three-gap-directions` roadmap 文档化的公开 API 契约冲突。**删前必须先确认 roadmap 是否仍把它当对外契约**——属真债清理册第六档(需先协调)。

**复核结论**:⚠️ **当前分支就是 `aps-three-gap-directions`**——这组 API 是本分支 roadmap 的在途契约,**现阶段不应删**,标"在途"而非"残渣"。

---

### 4.4 【P5 · medium】datetime 解析私造 3 份,绕过 strict_parse 收口点且语义漂移

**位置**:`execution_fact_provider.py:66` / `operation_execution_feedback_support.py:226` / `data/repositories/operation_execution_state_builder.py:42`

**引用链**
- 已知收口点 `core/shared/strict_parse` 提供 `parse_required_datetime(:113)`/`parse_optional_datetime(:127)`,内部正是 `str.strip().replace('/','-').replace('T',' ').replace('：',':')` + 对 `('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M','%Y-%m-%d')` 循环 strptime。
- 分区内三处各自重写同一套:`_parse_execution_time`(provider:66-76,失败 **return None**)、`_parse_feedback_datetime`(support:226-233,失败 **raise** `_invalid_field_value`)、`_parse_time`(state_builder:42-55,先 fromisoformat 再循环,失败 **return None**)。
- grep 实证三者均未 import strict_parse。

**为何算债**:同一"解析现场时间字符串"职责有统一收口点,却私造三遍**并已语义漂移**:写校验链(`_parse_feedback_datetime`)对坏时间抛错(符合不自欺),而 provider/state_builder 两份对坏时间静默返回 None。同一概念三套口径,其中两套的静默 None 与灵魂原则相左(虽因上游约束当前不易触发)。

**爆炸半径**:改为统一调 strict_parse 需逐处对齐错误语义——provider/state_builder 当前靠 None 表达"无时间"是合法语义,不能简单换成抛错版;收口时若不分清 required vs optional 会把"正常缺时间"误判成错误。中等改造面。属真债清理册第四档(#33,语义需逐处对齐)。

**复核结论**:✅ 证据仍准(provider/support/state_builder 未被 b08162cd 改动)。

---

### 4.5 【P5 · low】positive-op-id 过滤:provider/repo 各私造一份且漂移(公开排序/私有不排序)

**位置**:`execution_snapshot.py:27`(public)vs `execution_fact_provider.py:51` vs `operation_execution_event_repo.py:63`

**引用链**
- `snapshot.positive_op_ids`(`:27`)是 public 且进 `__all__`(`:70`),逻辑 = int 化 + 去重 + **`return sorted(out)`**。
- `provider._positive_op_ids`(`:51`)同逻辑但 **`return out`(不排序)**;`repo._positive_ids`(`:63`)同逻辑也不排序。
- grep 实证 provider/repo 未 import `snapshot.positive_op_ids`,各用私有版。

**为何算债**:已有导出的公共 `positive_op_ids`,另两处不复用而私造,且**语义漂移**(是否排序)。漂移可能引入隐蔽 bug:依赖顺序的下游(如 `execution_snapshot` 的 sha256 指纹按 ids 顺序拼接)必须用排序版,而 provider/repo 的不排序版若被误用于指纹会得到不同 digest。

**爆炸半径**:收口为单一实现时必须保留"排序"语义给 snapshot(指纹稳定性依赖它);provider/list_by_op_ids 当前按入参顺序产 facts——强行换排序版会改变 facts 返回顺序,需确认无下游依赖原顺序。低-中。属真债清理册第四档(#34)。

**复核结论**:✅ 证据仍准。

---

### 4.6 【P6 · low】reported_status 兜底映射表 + or 右支,被 schema 不变量架空永不触发

**位置**:`data/repositories/operation_execution_state_builder.py:33-39`(表)`,76-79`(or 右支)

**引用链**
- `_current_status:77` = `last_event.reported_status or _REPORTED_STATUS_BY_EVENT_TYPE.get(last_event.event_type, EXECUTION_STATUS_NOT_STARTED)`。
- 追 `reported_status` 来源:`OperationExecutionEvent.from_row`(`operation_execution_event.py:95`)`reported_status=str(get(row,'reported_status') or '')`,行来自 DB。
- `migration_operation_execution_contract.py` 把 reported_status 列入 `_OPERATION_EXECUTION_REQUIRED_NOT_NULL_COLUMNS`(`:172`)且 CHECK `reported_status in ('processing','paused','exception','completed')`(`:140`),坏值探针 `:264` 实证拒绝 'finished'。
- 故每条持久化事件 reported_status 恒为四非空合法值之一 → `or` 右支**永不求值** → 整张 `_REPORTED_STATUS_BY_EVENT_TYPE` 死。

**为何算债**:一张看着在用、实则被 DB CHECK + NOT NULL 完全架空的兜底映射 + 一条不可达 or 分支。死面包屑——制造"状态映射有两处真值来源"的假象(真值来源只有写入侧 `_REPORTED_STATUS_BY_ACTION`)。

**爆炸半径**:删表 + `:77` 简化为直接用 reported_status,仅当未来有人绕过 repo 直接构造无 reported_status 的事件才会暴露(但那条路径同样被 schema 拒)。极低。属真债清理册第二档(#21)。

**复核结论**:✅ 证据仍准。

---

### 4.7 【P6 · low】`_REPORTED_STATUS_BY_ACTION` 的 EXCEPTION 死键 + 死导入

**位置**:`operation_execution_feedback_support.py:64` + `operation_execution_feedback_service.py:12,455`

**引用链**
- `_REPORTED_STATUS_BY_ACTION`(support:59-66)同含 `EXECUTION_EVENT_EXCEPTION('exception')` 与 `EXECUTION_ACTION_REPORT_EXCEPTION('report_exception')` 两键。
- 但 `_normalize_action`(service:247-248)= `event_type_to_action(action_to_event_type(text))`,经验证(`labels.py:91-102`)无论输入 'exception' 还是 'report_exception' 恒归一为 'report_exception';`:249` 成员校验与 `:455` 索引用的都是归一后 action,故 'exception' 键**永不被命中**。
- `EXECUTION_EVENT_EXCEPTION` 导入 `service.py:12`,grep body 内零使用(`:278` 用的是 PAUSE+REPORT_EXCEPTION)。

**为何算债**:写后永不读的字典键 + 导入后永不用的符号。死面包屑,让映射表看起来比实际多覆盖一个分支。

**爆炸半径**:删 'exception' 键 + 死导入,零行为影响(已证不可达)。极低。属真债清理册第二档(#22)。

**复核结论**:✅ 证据仍准。

---

### 4.8 【P6 · low】`list_latest_exception_events_by_op_ids` 生产零调用,仅测试续命

**位置**:`data/repositories/operation_execution_event_repo.py:260-265`

**引用链**:方法定义 `:260`。grep 全 web/core/data 除定义外**零命中**;唯一引用 `tests/regression_operation_execution_event_foundation.py:173`。最新异常态的真实生产来源是 `state_builder._latest_exception`(`:91`) + `OperationExecutionState.latest_exception_*` 字段,不经此方法。

**为何算债**:公开 repo 方法被造出但生产无人调,仅靠基础回归测试续命。死代码(已 grep 实证)。

**爆炸半径**:删除需同步删 `regression_operation_execution_event_foundation.py:173` 一行断言。低。属真债清理册第二档(#15)。

**复核结论**:✅ 证据仍准。

---

### 4.9 【P3 · low】service 层 `operation_execution_labels.py` 是 model 同名模块的纯转出垫片

**位置**:`core/services/scheduler/operation_execution_labels.py:1-36`

**引用链**
- 全文件 35 行:从 `core.models.operation_execution_labels` import 15 个符号,`__all__` 再原样导出同 15 个,**无任何新定义/封装/适配**。
- 导入方:`feedback_service.py:48`、`feedback_support.py:26`、`routes:16`、两个测试。
- 对照同分区 `gantt_tasks.py`、`state_builder.py`、`scheduler_resource_dispatch_execution.py` 全部**直接** `from core.models.operation_execution_labels import ...`——绕过此垫片。
- git:生于 `5e1617ec`(第8项执行事件基础)。

**为何算债**:一层不做任何事的 re-export 垫片;且"是否走垫片"在分区内不一致(一半直连 model、一半经垫片),说明它不是被贯彻的服务边界门面,而是半截留下的转发层。

**爆炸半径**:删垫片改 5 个导入方直连 model,行为零影响;但若团队有意以"service 不直接 import model 标签"为约定则会破坏该约定(然而现状已大量直连,约定并未贯彻)。需裁决是收编为统一门面还是删除。低。属真债清理册第三档(#27)。

**复核结论**:✅ 证据仍准。

---

### 本分区小结

| 条 | 病理 | 位置 | 性质 | 复核 |
|---|---|---|---|---|
| 4.1 | P2(LB) | feedback_service.py:347-356,451-453 | 承重护栏(见§90) | ✅ 注释仍缺 |
| 4.2 | P6 | execution_fact_provider.py:20-21,96 | 死字段+死查询 | ⚠️ 重 grep |
| 4.3 | P3 | schedule_delay_diagnosis_service.py:42-54 | **本分支 roadmap 在途契约,勿删** | ⚠️ 在途 |
| 4.4 | P5 | provider/support/state_builder datetime ×3 | 私造+语义漂移 | ✅ |
| 4.5 | P5 | positive_op_ids ×3 | 私造+排序漂移 | ✅ |
| 4.6 | P6 | state_builder.py:33-39,76-79 | schema 架空的死防御 | ✅ |
| 4.7 | P6 | feedback_support.py:64 + service.py:12 | 死键+死导入 | ✅ |
| 4.8 | P6 | event_repo.py:260-265 | 测试续命死方法 | ✅ |
| 4.9 | P3 | operation_execution_labels.py:1-36 | 纯转出垫片 | ✅ |

**要点**:本分区地基由 schema CHECK + 乐观锁 + 启动期 contract probe 三重锁死,大量"死防御"恰恰是因为 DB 不变量太硬而被架空——这是健康的过度防御,不是坏味道。唯一需要人工动作的是 4.1 补注释(§90)和 4.3 确认在途状态。
