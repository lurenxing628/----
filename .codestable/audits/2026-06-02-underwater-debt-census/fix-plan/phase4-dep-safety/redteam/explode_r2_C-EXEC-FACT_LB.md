# 逐簇爆炸对抗 r2 — C-EXEC-FACT — 主透镜【承重误删】

> skeptic 第2轮 / 只读不改 / 默认怀疑 / HEAD c2aa7501 / 回盘日 2026-06-05
> 主透镜:承重误删(Q1)为重。5套 guard 漏拷一键=fail-open;A族给 execution_review 加形参=预览冒充正式。
> 全部行号经本轮独立 rg 回盘(不信旧值)。

## 0. 回盘证据锚(本轮 rg 实测,逐点坐实)

| 锚点 | 实测 file:line | 性质 |
|---|---|---|
| LB01 硬拒四条件 | feedback_service.py:369-372 → raise :374 | 承重禁区 |
| LB01 第二硬门 | feedback_service.py:381-382 can_write_feedback | 承重禁区 |
| LB01 写死消毒 | feedback_service.py:471(SOURCE_SCHEDULE)/472(ROLE_ADOPTED)/473(None) | 承重禁区 |
| LB01 reported_status | feedback_service.py:475 `_REPORTED_STATUS_BY_ACTION[action]` | R17 触及行紧贴禁区 |
| R17 死import service | feedback_service.py:12 EXECUTION_EVENT_EXCEPTION | 删 |
| R17 死键 support | feedback_support.py:11(import)/:81(推导式项) | 删 |
| R20 labels import service | feedback_service.py:52 `from .operation_execution_labels import (` | 改 |
| R15 provider 残留 | execution_fact_provider.py:85-95(空:87→None / 坏:95→None 双静默) | P4 残留 |
| R15 support raise | feedback_support.py:225-230 raise(灵魂线禁区) | 守 |
| R19 snapshot sorted | execution_snapshot.py:40 `return sorted(out)` → :78/:91 sha256 | 事实承重 |
| R19 provider 不排序 | execution_fact_provider.py:82 `return out` → :145 missing[0] loud raise | 收口面 |
| R19 repo 不排序 | operation_execution_event_repo.py:79 `return out` → :408 SQL IN | 顺序无关 |
| R13 死字段 | execution_fact_provider.py:23-24 定义 / :56-57 赋值 | 生产0消费,3测试读活 |
| R13 latest 链 | _fact_from_state latest 形参 :42 / _latest_events_by_scope :163-170 | 删字段连带 |
| R18 stub 组 | repo.py:354/356/399/401/403/405 全 raise _unscoped_execution_read_error() | 契约护栏 |
| 最终底 | schema.sql:190-192 三CHECK + :284 candidate_rows另表 + scope.py:44/47/50 三raise | 不可删 |

---

## 1. 逐成员判定

### LB01 — 🟢 绿(承重,仅补注释,门控先落)

**判定 绿**:修法是纯补两处中文注释(贴 :367 上方 + :471 上方),零删除/零透传/零统一/零加形参。owner_pending=false。本轮 rg 坐实禁区行本体零改:硬拒 :369-372→:374、第二硬门 :381-382、写死 :471-473、reported_status :475 全部健在。

**承重不对称已显性绑死(主透镜过关)**:LB01 的全部价值就是把「拒 vs 消毒 vs validate」三道闸的不对称钉成「我是故意的」。本轮独立验证三路 parity 反例全部成立——schema.sql:284 另有 `CHECK(source_table IN ('schedule','candidate_rows'))` 的第二张表(实测命中),故「删写死 + 误写另表 → candidate_rows 不被拒 → 脏数据静默落库」这条灾难链坐实;scope.py:44/47/50 三 loud raise 与 service 写死(silent-but-safe coerce)不等价,两者必须并存。

**绿的前提(硬约束,违反即转红)**:
1. 注释必须锚在符号上方(随符号移动),不锚绝对行号——R17 删 :12 会让 :369/:471 上移 1 行。
2. LB01 注释**必须先落,门控整个 service 文件**(R17 删 :12 / R20 改 :52 都在此文件)。承重裸奔期严禁动同文件结构。
3. 文案禁出现「repo 已 validate 故写死冗余」式措辞——这是最危险诱惑的入口,会诱导后人删写死。

**唯一灰区(不影响绿,记账给 owner)**:文件当前 git 态为 `MM`,他桶 OperationExecutionScope 改动已在工作区;LB01 注释落地前须先确认基线三套 regression 绿,且 registry 记的测试函数名已漂(实际拒绝测试 = `test_actual_post_without_query_rejects_body_plan_identity`),执行清单按盘上真名认账。

### R17 — 🟡 黄(最危险的边 LB01↔R17,同 `_build_event_payload`,有条件可做)

**判定 黄(非红)**:R17 修法是纯删死代码(service:12 死import + support:81 推导式项 + support:11 孤立import),病理 P6 死键不可达本轮已复证(`_normalize_action` 经 `event_type_to_action` 把 "exception"→"report_exception",死键 :81 产物永不命中 :475/:269)。非承重、非收口、不新增兜底。**但因物理同居 LB01 写死消毒层(:471-473)与 reported_status(:475)同属 `_build_event_payload`,定为黄、附强条件。**

**为何不红(主透镜:这不是承重误删)**:R17 删的是 import 行(:12)与推导式输入元组项(:81),**绝不触碰** :471-475 任何一行。删 :81 影响的是 `_REPORTED_STATUS_BY_ACTION` 这张映射表的键空间,与 LB01 写死的 `_build_event_payload` 返回 dict 字面键值**是两个 dict、不共享键空间**(本轮确认 :471-473 是 payload 字面键,:74-84 是模块级映射表)——无 dict 键位移耦合。

**黄的强条件(缺一即转红,灾难链)**:
1. **LB01 注释必须先落**:R17 早于 LB01 动 service 文件 = 承重裸奔期改同文件,违 PHASE0 §10.1。
2. **绝对禁删活键 :80**:删错 :80 `EXECUTION_ACTION_REPORT_EXCEPTION`(而非死键 :81)→ "report_exception" 键消失 → :269 成员校验把真实「报异常」操作误判非法 → 用户报异常被 ValidationError 静默拒(可用性事故)。本轮 rg 确认 :80 是活键、:81 是死键,删点必须精确到 :81。
3. **绝对禁删常量定义**:`EXECUTION_EVENT_EXCEPTION` 在 6 文件真活(state_builder/event/viewmodel/labels/data_contract/event_foundation 本轮 rg 坐实);R17 只删 feedback 两文件局部 import,误删 event.py:14 常量定义 → 全线 ImportError。
4. **行号重 rg**:R17 删 :12 后,R20 的 :52、LB01 的 :369/:471 全上移 1 行,后续债不照抄快照行号。

### R15 — 🔴 红(provider:85-95 P4 残留,直接收口=静默放宽必炸执行事实读取)

**判定 红**:R15 provider 处是本簇唯一残留真 P4(本轮 rg 复证函数体 :85-95 未动:空值 :87→None、坏值循环失败 :95→None **双静默**)。owner_pending=true。**红的核心:任何「把三处私造解析统一收口」的 DRY 动作落在 required/optional 不对称上,即制造静默事故。**

**灾难链 A(空值误判 required)**:provider 的 `if not text: return None`(:87)是合法 optional——现场「任务还没开始/没结束」即 actual_start/end 为空是正常态。若收口到 `parse_operation_event_time`(空→`raise ValueError("event_time is required")`,本轮已读其语义),则正常空时间被炸成 raise → `execution_fact_provider.py` 的 :52/53(`actual_start_time`/`actual_end_time` 填充)抛错 → `facts_by_scope` 读不出执行事实 → 若上游有宽 except 吞掉 = **执行事实全空、无报错** → 排程按空数据重排 = 错误排产(静默,数据完整性)。

**灾难链 B(坏值仍 None)**:provider 坏值 :95 现 return None,是 P4 该消灭的静默吞坏值;但若收口方向选错、把 support 的 raise(:228)一并「对齐」成 None → `_validate_event_time_sequence`(service:400/403/416,本轮经 dossier 链确认在 service)拿 None 比时间序列 → 校验形同虚设 → 乱序事件入库 → 状态机错乱。

**红的边界(给 owner 的强约束,而非否定收口本身)**:
- **禁区铁律**:support:228 raise 必保(required);provider:87 / state_builder:39 的 `if not text: return None` 必保(optional),禁误判 required。三处 required/optional **本就不同**,禁一刀切。
- provider 坏值收口方向只能二选一:loud raise(须先确认 :52/53 下游接得住,owner 裁)或「可观测降级标记 + 记日志」,**严禁更深的 return None**。
- **前置**:R15 是 SCC-EXEC-FACT 最前置,必须先于 R13/R17/R19 动这3文件(先改语义后删死物,防撞行号 + 防删物误伤 raise);且 parity 测试(钉死三处 required/optional 矩阵)须先 merge,否则收口无护栏 P5 必复发。
- owner 未裁前不进批次。

### R19 — 🔴 红(repo→service 越层 + 指纹事实承重 sorted,naive 全收口双击穿)

**判定 红**:三处 positive-id 过滤(snapshot:28-40 / provider:70-82 / repo:67-79)逻辑全等,**唯一差异=末行排序**(本轮 rg 坐实:snapshot :40 `return sorted(out)`、provider :82 `return out`、repo :79 `return out`)。owner_pending=true。**红的核心:naive「三处全收口到 snapshot.positive_op_ids」被分层 + 导入环双重击穿,且 sorted 是事实承重不可丢。**

**灾难链 A(指纹漂移,最严重静默)**:snapshot :40 sorted → :78 `ids=positive_op_ids(op_ids)` → :91 `sha256(payload)` 当快照 revision。本轮确认指纹**强依赖排序**。若把 canonical 统一成「不排序」或让 snapshot 走不排序路径 → 同一输入产出不同 sha256 → 下游4处(persistence_guard/gantt_adjustment_publish/scenario_service/execution_guardrails)快照比对**静默失真**,且三函数零符号级测试(本轮 `rg tests/` 0命中),无单测拦截。⇒ canonical 实现**强制保 sorted**,等同承重待遇,改它须补「我是故意的:指纹稳定性依赖排序」注释。

**灾难链 B(越层 + 导入环,响,但仍须拦)**:本轮 rg 坐实——snapshot:7 已 `import execution_fact_provider`(单向边),provider 零反向 import;若让 provider 反向 import snapshot 收口 = service↔service 成环。repo 在 data 层、`positive_op_ids` 在 core/services;repo 收 service = data→service 越层(repo import 头本轮确认仅 core.models + base_repo + aggregation,无 service)。两者强行收口会炸 test_architecture_fitness(响,可拦,但属红队必标的破护栏路径)。

**红的边界(保守解,owner 裁落点前不进批次)**:
- provider `_positive_op_ids` 同 service 层,技术可收口到 snapshot,但 provider 不排序、收到排序版会让 :145 `missing[0]` 的首个 op_id 值变 → :147 loud raise **对外文案变**(从 `[3]`→`[1]`),须 parity 断言显式钉或 owner 接受。
- repo 因分层**不能收 service**:保守解=保留 repo 私有版 + 补「我是故意的:repo 层独立去重、刻意不依赖 service 排序、顺序无关(:408 SQL IN)」注释 + parity;下沉 core/models 触 red line #3,须 owner 裁。
- R19 改 `__all__`(snapshot:118-123,本轮确认块内仅4项含 `positive_op_ids`)与 R01/R46 跨簇同符号边高顺序敏感,须串行对账最终导出表。
- 两共享文件:provider 处须与 R15(:66,紧邻 :70)/R13(:56-57)同批或串行;repo 处与 R18(:399-405)串行。R19 排批次最晚(Batch-14)。

### R13 — 🟡 黄(死字段被3测试读活,直删须先退测试 + owner二次确认,禁碰 repo raise)

**判定 黄**:本轮 rg 坐实生产侧 `\.last_event_schedule_(version|id)` **0命中**(死字段真死);但被 **3测试读活**——reschedule:196 `==1`、scope_read_contract:108 `is None`/:190-191 dict两键/:220-221 构造kwarg两参。owner_pending=false,但「死」定性已被重构读活推翻,**升级 owner 二次确认删/留**。非红(直删可解耦、无承重误删),但因测试契约 + latest 连带链定为黄。

**为何不红(主透镜)**:R13 是直删类、不收口、不新增 import,本轮确认 0越层 0导入环。死字段与 scope.schedule_version 在 latest 存在时数值恒等(scope 由 event 同名字段派生),仅 None 分支携带「有无事件」信号,而该信号生产侧 0 消费 → 直删本体安全。

**黄的强条件(序错即测试红或复活护栏)**:
1. **测试迁移序**:先改 scope_read_contract(契约源头 :108/:190-191/:220-221)→ 再改 reschedule:196 → 生产删字段最后(红→绿自证)。漏退 :220-221 kwarg → `ExecutionFact(...)` TypeError;漏退 :190-191 dict键 → snapshot 比对 KeyError(均响,可接受但须覆盖)。
2. **禁碰 repo :399**:R13↔R18 强耦合**已解除**(本轮确认 repo:399 `list_latest_events_by_op_ids` 已是 stub raise,生产0调,属 R18 范畴)。R13 若顺手删 :399 → foundation:365 期望 raise 变 AttributeError;**更危险**:若把 :399 从 raise 改回真实查询 = 复活 R18 要消灭的越身份读取,静默破坏「按完整计划身份读取」契约。R13 完全不碰 repo。
3. **latest 连带孤儿 import 精确**:删字段后 :42 latest 形参 + :163-170 `_latest_events_by_scope` 成孤儿可清(省一次 list_events_by_scopes 往返,真性能收益);连带 `operation_execution_scope_from_event`(:8,本轮确认仅 :169 用)成孤儿可删,但 `OperationExecutionEvent`(:7)在 :166/:169 类型注解仍用、`EXECUTION_STATUS_NOT_STARTED`(:7)在 :47 仍用,**不可删**。
4. 软禁区:provider:110/:113 与 repo:399/401 的 loud raise(「按完整计划身份读取」灵魂线)R13 不得削弱成静默。

### R18 — 🟢 绿(stub 是契约护栏,修法仅补注释,registry 直删已被推翻)

**判定 绿**:本轮 rg 坐实 repo:401 `list_latest_exception_events_by_op_ids` 已是单行 stub `raise _unscoped_execution_read_error()`(:82-83 返回 `ValueError("现场执行事件必须按完整计划身份读取...")`),与 :354/356/399/403/405 共6格构成「拒绝非 scoped 读」契约面。生产0消费(本轮 rg 仅 :401定义 + 测试:367)。修法=补「我是故意的」护栏注释,零删除/零改静默。owner_pending=false。

**registry 直删修法已击穿契约(主透镜:这正是「看着像死码该删」的陷阱)**:
- planned_fix「直删 + 退 :367 + 摘 EXECUTION_EVENT_EXCEPTION import」全失真:本轮确认 `rg EXECUTION_EVENT_EXCEPTION repo.py` **零命中**(无对象可摘);`OperationExecutionEvent` 被 :401 返回注解占用不可删。
- 直删后 `repo.list_latest_exception_events_by_op_ids([10])` 从受控 ValueError 退化为 `AttributeError`(裸异常、无中文业务语义)= 「受控 raise vs 失控 AttributeError」的 None-vs-raise 变体反例。
- 若有人把 stub 改 `return {}` 兜底 → 非 scoped 读静默返回空 dict,调用方误以为「无异常事件」而非「不该这样读」= 典型 fail-open,**严禁**。

**绿的前提**:
1. 契约测试 :352 `test_..._rejects_unscoped_op_reads` 对6格逐一 `pytest.raises(match="完整计划身份")`(本轮坐实 :360-371,其中 :365=R13关心、:367=R18),补注释零影响、测试续绿。
2. R18 与 R13 共用同一条注释覆盖 :399-405 整组,合批、天然不撞行号。
3. owner F门确认「降级为注释护栏」后再落(registry title/pathology/planned_fix 三处 stale)。

### R20 — 🟡 黄(纯删垫片字节级等价,但毗邻 LB01 + 与 R17 撞行号,假边×3 已除)

**判定 黄**:R20 删 service 层 labels 垫片(:1-35)+ 5 处 import 改直连 core.models,本轮确认字节级等价(`from X import Y` 同一对象)、漏改即 ImportError(loud,非静默)、无 P4/无收口/不触灵魂线。本应近绿,**因毗邻 LB01 承重宿主文件 + 与 R17 同文件撞行号定为黄**。

**假边×3 本轮全部证伪(主透镜:假边不该牵连承重)**:
- R20↔R12(gantt_tasks):本轮 rg 坐实 `gantt_tasks.py:8 from core.models.operation_execution_labels`,**直连不经垫片**,删垫片不碰它。假。
- R20↔R08/R09(..._execution.py):本轮 rg 确认 labels import 在 `scheduler_resource_dispatch_execution_context.py:11`,**非** `..._execution.py`(后者零命中)。假。registry planned_fix 误写 routes.py,真实是 context.py:11。

**黄的强条件**:
1. **LB01 注释先落,门控同文件**:R20 改 service:52,与 LB01 :347-356(审计 raw dict 承重字段)/:369-374/:471-473 同居。禁碰这些禁区行(本轮坐实 :369-372 硬拒、:471-473 写死健在);:52 import 块与 347-473 物理隔离,只改 import 不越界。
2. **与 R17 串行 + 重 rg**:R17 删 :12 死import → :52 上移1行,R20 动手前重新 rg `from .operation_execution_labels import` 真实行,不照抄 :52 快照。
3. 门禁三同步:删文件须同摘 docs_quality_gate:128 元组项 + 删指南条目,否则文档门禁红(记账失败非安全失守)。


## 2. 六质问点汇总(主透镜为重)

| Q | 质问 | 本簇裁决 |
|---|---|---|
| Q1 承重误删 | 统一/DRY 名义抹承重不对称→fail-open? | **R15/R19 红**:R15「三处解析统一」抹 required/optional 不对称→静默炸执行事实;R19「三处过滤统一」抹 sorted 事实承重→指纹漂移 + repo 越层。LB01/R18 绿(主动驳斥「repo已validate故写死冗余」「stub是死码」两大诱惑)。 |
| Q2 分层导入环 | 收口造跨层/导入环? | **R19 命中双阻断**:provider反向import snapshot=service内环;repo收service=data→service越层。本轮 rg 坐实 snapshot:7→provider 单向边、repo import 头无 service。R13/R17/R18/R20 净删/注释,0越层0环。 |
| Q3 迁移耦合 | 与 schema/v18·v19 CHECK 耦合? | LB01 配套最终底 schema.sql:190-192 三CHECK + scope:44/47/50 三raise,本轮坐实;LB01 仅注释不改码,不撼 CHECK,启动探针不炸。adopted-only 已下沉。 |
| Q4 灵魂线热路径 | P4 改 raise 落热路径放大可用性? | **R15 命中**:provider:85 坏值若改 raise 落 facts_by_scope 热路径,空值误判 required 会炸执行事实读取。修向须区分空值→None(保) vs 坏值→loud/可观测,禁更深 return None。 |
| Q5 收口行为等价 | 收口点与副本逐分支等价? | **R15 不等价**(空 None-vs-raise、坏 None-vs-raise 双跃迁);**R19 不等价**(顺序:snapshot sorted vs provider/repo 插入序,影响指纹 + missing[0] 文案)。两者均须 parity 钉死差异。 |
| Q6 测试迁移序 | 删/改前先迁哪些测试? | **R13 序敏感**:先 scope_read_contract(:108/190-191/220-221)→ reschedule:196 → 生产删字段。**R17**:删 :81 死键前确认 :80 活键不动、6文件常量不碰。**R20**:2测试 import 同 PR 改 + 门禁三同步。R18 契约测试 :367 是资产不退。 |

**主透镜专项结论(5套guard漏拷一键 / A族加形参)**:
- 本簇**无** execution_review 加形参动作(A族 LB02/LB05/LB06 在他簇 execution_review.py 读侧,本簇仅 LB01 写侧)。本簇写侧 adopted-only 纵深=路由→service:369-374硬拒→:381 can_write_feedback→:471-473写死→repo scope validate→schema CHECK,**多道闸逐分支不等价、不可合并**。R15/R19 的红正是「漏拷一键即 fail-open」在解析/过滤层的同构:解析层漏拷 = 把 required 当 optional(或反之)静默放宽;过滤层漏拷 = 把 sorted 丢掉静默漂指纹。


## 3. 本轮新发现漏项

本轮新发现、计划未充分覆盖的爆点与缺失前置:

1. **【R13 测试入口反例,序敏感被低估】** reschedule:196 走的是 `facts_by_op_id_for_scopes` → :118 `latest_events = self._latest_events_by_scope(normalized)` → :123 喂 `_fact_from_state` 的 latest。本轮坐实 `list_events_by_scopes` 在 provider **仅 :168 一处用**(即 `_latest_events_by_scope` 内)。⇒ R13 删字段若连带删 latest 链,**reschedule:196 的整个数据通路被抽掉**,不是单纯「删个断言」——测试须改的是「字段取值来源」而非仅「字段名」。dossier 说的「省一次往返」成立,但代价是该测试的 latest 语义整体消失,owner 二次确认时须把这点摊给 owner(否则可能误以为只是删两个 None 断言)。

2. **【R15 收口去向 vs provider import 头缺口】** 本轮确认 provider import 头(:1-11)**无** `parse_operation_event_time` 也无 strict_parse(自造)。若 owner 裁定收口到 `parse_operation_event_time`(core.models.operation_execution_event,本轮坐实 :75 + :71 `_event_time_text` 归一化与 provider:88 字节同)→ 须**新增一行 import**;虽合法下行(已 import 同模块 EXECUTION_STATUS_NOT_STARTED/OperationExecutionEvent :7),但属新增,执行清单须列出,别当「零 import 改动」。

3. **【R32 假边二次坐实,可顺带消解但须协调】** R15 provider:88 的 `.replace("/","-").replace("T"," ").replace("：",":")` 与收口点 `_event_time_text`(:72)字节同;R15 收口到 parse_operation_event_time 会**顺带删掉 provider 这处 replace 链**,即 R32(若指向此处归一化)被 R15 消解。R32=backup os.replace 是异物假边(corrections B 已断);但 R15 先于 R32 的协调须记,避免 R32 收口时 provider 处已被删造成 old_string 失配。

4. **【最危险边的隐性第三方:_REPORTED_STATUS_BY_ACTION 跨文件全名共享】** 本轮排查别名陷阱:support 定义全名 :74、service 全名 import :32 + 用 :269/:475,**无别名 `n` 转译**(早期 grep 的 `n` 命中系 import 块换行误匹配,非别名)。R17 删 :81 推导式项 → 该表少一个 "exception" 键 → service:269 成员校验 + :475 取值读侧逻辑不变(action 永非 "exception")。删点定位无别名漂移风险。**此点是确认而非新爆点,但 D2 提到的「别名 import 漏改」纪律在本簇不适用,执行者勿误套。**

5. **【缺失前置:R15/R19 双 owner_pending 卡住整条 SCC 串行链】** R15 是 SCC 最前置(须先于 R13/R17/R19 动3文件),R19 排最晚(Batch-14);两者都 owner_pending=true。⇒ **owner 未裁 R15 收口去向 + R19 repo 落点前,本簇 R13/R17/R20 的「先 R15 后删死物」串行序无法启动**——R17/R20 虽自身可早做(只需 LB01 注释先落),但若严守「R15 先于同文件兄弟」铁律,R17(动 support :81,与 R15 :225 同文件)会被 R15 owner 裁断阻塞。**前置缺口**:需 owner 先对 R15 至少给出「provider 坏值方向 + 三处不统一」的最小裁断,解锁 support 文件的删死物动作,否则整簇卡在两个 pending 上。建议 Layer4 把「R15 最小裁断」作为本簇解锁的唯一硬前置单列。

6. **【schema:284 第二张表是 LB01 反例的活证,但无人守它】** 本轮坐实 schema.sql:284 `CHECK(source_table IN ('schedule','candidate_rows'))` 另一张表确在——这是 LB01「删写死且误写另表则 candidate_rows 不被拒」灾难链的物理依据。但**本簇无任何债守护「事件不会被误写到 :284 那张表」**,该防线完全靠 LB01 写死 + service 路由。属簇外承重底,Layer4 须确认 :284 表的写入路径不被本簇任何改动触及(本簇未触,但记账留痕)。
