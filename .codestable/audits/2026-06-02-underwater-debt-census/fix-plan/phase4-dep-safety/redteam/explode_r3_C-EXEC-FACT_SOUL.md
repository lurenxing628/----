# 逐簇爆炸对抗 r3 · C-EXEC-FACT · 主透镜【灵魂线热路径+收口等价】

> 簇 C-EXEC-FACT | 成员债 LB01 R13 R15 R17 R18 R19 R20 | 第3轮 skeptic 只读不改
> 回盘日 2026-06-05 / HEAD c2aa7501 / 全部 file:line 经本轮 rg 复盘(不信旧值)
> 主透镜聚焦: R15 provider P4 残留(空值vs坏值)、R17↔LB01 同 _build_event_payload 最危边、R19 sorted 指纹、R18/R13 stub 组解耦
> 默认怀疑:多维度存疑即红;不放过「测试绿但护栏已破」的静默失效

---

## 0) 本轮 rg 回盘核验台账(权威实测,逐条坐实)

| 核验对象 | 实测 file:line | 结论 |
|---|---|---|
| R15 provider `_parse_execution_time` | execution_fact_provider.py:85 def / :87 `if not text: return None`(空值) / :95 `return None`(坏值循环失败后) | **空值→None、坏值→None 双静默**,坐实唯一残留 P4 |
| R15 收口符号 `parse_operation_event_time` | operation_execution_event.py:75 def / :80 空值`raise ValueError("event_time is required")` / :86 坏值`raise ValueError(...must be valid...)` | **空值→raise、坏值→raise**;与 provider 双重不等价 |
| R15 provider 调用点 | execution_fact_provider.py:52/53(填 actual_start/end_time 进 ExecutionFact) | 直喂 duration/重排 |
| LB01 写死消毒 | feedback_service.py:471 `SOURCE_SCHEDULE` / :472 `ROLE_ADOPTED` / :473 `scenario_id=None` | 承重三写死健在 |
| LB01 硬拒 | feedback_service.py:367 def / :369-372 四条件 / :374 `raise _conflict("not_current_official_plan")` | 承重护栏健在 |
| R17 死import(service) | feedback_service.py:12 `EXECUTION_EVENT_EXCEPTION,` | 死import在,body零用 |
| R17↔LB01 同函数体 | `_build_event_payload` def :455;:471-473 写死 + :475 `_REPORTED_STATUS_BY_ACTION[action]` **同属一函数体** | **最危边坐实** |
| R17 support 推导式死键项 | feedback_support.py:11 import + :74-84 推导式,:80 活键`REPORT_EXCEPTION` / :81 死键项`EXECUTION_EVENT_EXCEPTION` | 删:81 保:80 |
| R19 三处排序差异 | snapshot.py:28 def/:40 `return sorted(out)`;provider.py:70 def/:82 `return out`;repo.py:67 def `return out` | snapshot排序,provider/repo不排序 |
| R19 指纹依赖排序 | snapshot.py:78 `ids=positive_op_ids(...)`;:87-90 payload按 ids 顺序拼接;:91 sha256 | **指纹强依赖 sorted** |
| R19 导入边 | snapshot.py:7 `import ...execution_fact_provider`;provider rg snapshot **0命中** | snapshot→provider 单向,反向收口即环 |
| R18 stub 组 | repo.py:354/356/399/401/403/405 全 `raise _unscoped_execution_read_error()`;:82 定义返回`ValueError("...完整计划身份...")` | 6格契约护栏,非死码 |
| R18 契约测试 | foundation.py:352 `rejects_unscoped` / :366-367 对 list_latest_exception 断言 raise match="完整计划身份" | 拒绝护栏断言,非续命 |
| R13 死字段 | provider.py:23-24 定义 / :56-57 赋值(`None if latest is None else int(...)`) | 生产侧0消费 |
| R13 测试读活 | reschedule:196 `==1`;scope_read_contract:108 `is None`/:190-191 dict两键/:220-221 构造kwarg | **被5处测试读活** |
| R13 生产侧消费 | `rg .last_event_schedule_(version\|id) core/ web/ data/` → **0命中** | 生产0消费坐实 |
| R09 收口点存在 | operation_execution_scope.py:9 `parse_positive_execution_int` / :36 `validate_current_official_execution_scope` | 收口到已存在点合规,不新建 |
| R20 web 消费方 | context.py:11 `from ...operation_execution_labels import execution_action_label`;routes.py **0命中** | 假边坐实,真消费在 context.py |

---

## 1) LB01 — 🟢绿(承重,仅补注释,零结构动作)

**判定理由**: load_bearing=true,修法严格锁定「仅补两处中文注释 + 认账已存在契约」,零删除/零透传/零统一。本轮六维全过:
- Q1承重误删: 无。修法不碰 :368-374/:381-382/:471-473 任一逻辑,仅上方加注释。注释锚在符号上方,随符号移动不丢。
- Q2分层环: 无。零新增 import。
- Q3迁移耦合: 写死 :471-473 与 schema.sql:190-192 三 CHECK + scope.py validate 三 raise 是纵深三道闸,改码不改迁移无探针炸风险(本债不改码)。
- Q4灵魂线热路径: 写死消毒是 coerce-to-safe(silent-but-safe),不是吞错;它本就是灵魂线护栏本体,补注释强化而非削弱。
- Q5收口等价: 本债不收口。§7 三路 parity 反例已证「拒(硬拒/validate=loud raise) vs 消毒(写死=coerce-to-safe)」逐分支不等价、必须并存——主动驳斥「repo 已 validate 故写死冗余可删」最危险诱惑。
- Q6测试迁移序: 纯注释零迁测;仅需把 registry 过时测试函数名(`test_write_post_rejects_candidate_preview...`/`test_report_exception_rejects...` 盘上不存在)更正为真名(:285/:310)。

**唯一隐患(非红,执行纪律)**: LB01 是门控边——它的注释**必须先落**,R17/R20 才能动同文件。若执行序倒置(R17 先删 :12),:471 行号上移、LB01 注释锚点偏移,虽因注释锚在符号上方不致丢,但裸奔期改承重违 PHASE0 §10.1。**前置: LB01 注释先于 R17/R20。**

---

## 2) R17 — 🟡黄(条件: LB01 注释先落 + 删 :81 非 :80 + 绝不重构 _build_event_payload)

**判定理由**: 最危险的边(LB01↔R17 同 `_build_event_payload` 函数体)。死键/死import病理 P6 成立、删除行为等价,但三个条件任一破即炸,故黄不绿。

**灾难链 A(误删活键→静默拒真实报异常)**:
改 R17 时把 support.py:**80** `EXECUTION_ACTION_REPORT_EXCEPTION`(活键)当死键删,而非删 :**81** `EXECUTION_EVENT_EXCEPTION`(死键项)→ `_REPORTED_STATUS_BY_ACTION` 失去 `"report_exception"` 活键 → feedback_service.py:269 成员校验对真实「报异常」操作走 :269 `raise ValidationError` → **用户报异常被静默拒**(归一后 action 永是 report_exception,该键消失即所有报异常落 ValidationError)。
**前置/禁区**: 删 support.py:81(推导式输入元组里的 `EXECUTION_EVENT_EXCEPTION` 项),**保 :80**;删后 :11 import 孤立一并删。

**灾难链 B(顺手重构 _build_event_payload→打穿 LB01 写死)**:
R17 触及的 :475 `_REPORTED_STATUS_BY_ACTION[action]` 与 LB01 写死 :471-473 **同属 :455 起 `_build_event_payload` 函数体**(本轮坐实)。若 R17 借「清理死键」之名顺手重排/简化该函数体 → 误碰 :471-473 写死消毒 → scenario/candidate 上下文现场事件落库 → execution_fact_provider:40 纯按 op_id 读无过滤 → schedule_execution_guardrails:213 把预览态喂重排护栏 → **坏数据静默进排产决策**。
**前置/禁区**: R17 在 service 文件**只删 :12 一行 import**,绝不碰 :471-473/:367-374/:381-382;LB01 注释先落门控本债。

**灾难链 C(误删常量定义)**:
`EXECUTION_EVENT_EXCEPTION` 在 6 文件真活(event.py:14 定义 + labels/data_contract/state_builder/viewmodel/event 活点)。若误删 event.py:14 常量定义而非 feedback 两文件局部 import → 状态机/数据契约/viewmodel 全线 ImportError/KeyError。
**禁区**: 只删 feedback 两文件的局部 import(service:12 + support:11)+ 推导式项(support:81),绝不碰 event.py:14。

---

## 3) R15 — 🔴红(provider P4 残留:直接收口=空值与坏值双重静默放宽,炸执行事实读取链)

**判定理由(主透镜核心爆点)**: owner_pending=true 待裁,但本轮主透镜要求区分「空值→None vs 坏值→raise」。本轮 rg 逐字坐实 provider:85 与收口符号:75 **双重不等价**(空值: None vs raise;坏值: None vs raise),naive 收口会在两个方向同时静默放宽,且热路径在执行事实进口侧。多维存疑→红。

**灾难链(坏值方向,P4 期望但须分支隔离)**:
若把 provider `_parse_execution_time` 整体收口到 `parse_operation_event_time`(坏→raise),**且未先用 parity 钉死空值分支**:
- 空值方向(必炸): provider:52/53 喂的 actual_start/end_time 在「任务未开始/未结束」时合法为空 → 收口符号:80 `if not text: raise` → 现场事实读取直接抛 → 整个重排/甘特读不出执行事实。若上层有宽 except 吞掉 → **执行事实全空而无报错** → 排程按空数据重排 → 错误排产(静默)。
- 坏值方向(可用性放大): 坏时间从「静默 None」变 raise,而 :52/53 下游(duration 计算)未必接 except → 单条坏数据使整次 facts 查询抛错 → **可用性事故**。

**反向灾难链(若有人把 support 的 raise 误改成 None 求一致)**:
support.py:228 的 required raise 改 None → `_validate_event_time_sequence`(service:400/403/416)拿 None 比序列 → **时间序列校验形同虚设** → 乱序事件放行入库 → 状态机错乱(静默)。

**修正建议(前置/禁区,严格灵魂线)**:
1. **前置**: owner 裁断三分叉(跟随既成事实收口到 parse_operation_event_time vs 回迁 strict_parse;provider 坏值 raise vs 可观测降级标记)**之前 provider 残债不进任何执行批次**。
2. **必须先补 parity 测试钉死三处本就不同的 required/optional 矩阵**(provider 空→必须仍 None;support 空/坏→必须 raise + 保「反馈时间格式不正确」文案;state_builder 空→None/坏→raise),否则收口无护栏 P5 必复发。
3. **禁区(灵魂线,任何修法不得越)**: provider:87 `if not text: return None` 是合法 optional,**严禁误判 required**(把正常缺时间炸成假错);support:228 raise **严禁改 None**;**严禁给 provider 加更深 return None/except 吞错**——修向只能是 loud raise(空值分支保 None)或可观测降级标记。
4. provider 收口若选 raise,**空值分支必须显式保 None**(不能整体 delegate),即 `if not text: return None` 留在 provider,仅坏值走收口符号或转可观测降级。

---

## 4) R19 — 🔴红(canonical 必须 sorted;一刀切统一为不排序版=快照指纹静默漂移,且三函数零符号级测试无护栏)

**判定理由(主透镜:收口等价+事实承重)**: owner_pending=true。三处逻辑全等,唯一差异=末行排序。snapshot:40 `return sorted(out)` 是**事实承重行**(指纹稳定性唯一来源,本轮坐实 :78→:87-91 payload 按 ids 顺序拼 sha256)。三函数 rg tests/ **0 符号级测试**(无护栏)。收口若误统一成不排序 canonical → 指纹静默漂移,无测试拦截。多维存疑(无测试+导入环+分层双阻断+事实承重)→红。

**灾难链(最严重,静默)**:
若收口时把 canonical 实现统一成 provider/repo 的「不排序」版,或让 snapshot 走不排序路径 → `build_execution_snapshot` 对同一输入产出不同 sha256 revision → 快照/重订指纹漂移 → 下游 4 处(persistence_guard:9 / publish:34 / scenario:16 / guardrails:17)的快照比对、变更检测**静默失真** → 误判「无变化」或「有变化」→ 排产护栏决策基于错指纹。**三函数零符号级测试 = 无任何单测立即报警**。

**次级爆点(导入环/越层,响,可拦但仍是前置)**:
- 阻断A(环): snapshot.py:7 已 import provider;若让 provider 反向 import snapshot.positive_op_ids → service 内成环,运行时 ImportError。
- 阻断B(越层): repo 在 data 层,positive_op_ids 在 core/services;repo 收 service = data→service 越层违 test_architecture_fitness。

**修正建议(前置/禁区)**:
1. **前置**: owner 裁 repo 落点(下沉 core/models canonical vs repo 保私有版补注释);裁断前**保守解 = provider 同层收口 + repo 保留私有版补「我是故意的:repo 顺序无关」注释**,零越层零环。
2. **canonical 实现强制 `sorted`**——snapshot:40 视为事实承重行,改它须补「指纹稳定性依赖排序」注释 + parity。
3. **必须先补 positive_op_ids 黄金用例**(空/None/含0负数/含非int/重复→锁 [1,2,3] 排序)再动代码。
4. provider missing[0](:145)顺序变会改 loud raise 文案——parity 须显式断言文案变更或 owner 接受(此为可见非静默,非红主因)。
5. **禁区**: 绝不让 provider 反向 import snapshot(环);绝不让 repo import service(越层);canonical 绝不丢 sorted。

---

## 5) R18 — 🟡黄(条件: 不直删/不退断言;补 :399-405 整组护栏注释;与 R13 repo 部分解耦)

**判定理由**: registry 「直删+退测试+摘 import」前提已被 scope 重构全面推翻。:401 是 6 格 stub 护栏之一(:354/356/399/401/403/405),非死码。改注释类零行为影响→黄(条件守住即安全),但若执行者照旧 registry 直删→炸。

**灾难链(若照旧 registry 直删)**:
删 :401 → `repo.list_latest_exception_events_by_op_ids([10])` 从受控 `ValueError("...完整计划身份...")` 退化为裸 `AttributeError` → 击穿「拒绝非 scoped 读」契约 + foundation.py:367 `pytest.raises(match="完整计划身份")` 红。**更危险变体(违灵魂线,严禁)**: 若有人把 stub 改 `return {}` 兜底 → 非 scoped 读**静默返回空 dict** → 调用方误以为「无异常事件」而非「你不该这样读」→ 典型静默回退坑。

**修正建议(前置/禁区)**:
1. **前置**: owner F 门确认「降级为注释护栏」(registry title/pathology/planned_fix 三处 stale,前提已被推翻)。
2. **修法 = 补 :399-405 整组「我是故意的」中文护栏注释**(钉「故意保留 loud-raise,拒非 scoped 读,删除退化 AttributeError,禁改静默」)。
3. **禁区**: 不直删任一 stub;不退 foundation:367 断言;不删 `EXECUTION_EVENT_EXCEPTION` import(已零命中,无对象;但 `OperationExecutionEvent` 被 :401 返回注解占用不可删);绝不改 `return {}` 静默。
4. **R13↔R18 解耦**(本轮坐实): R13 是 provider 死字段,不碰 repo;R18 独立处置 :399-405。registry 旧「R13 连带删 repo:254 + 与 R18 同原子」基于旧假设作废。R18 与 R13(repo相邻:399)若都走补注释路线则**共用一条覆盖 :399-405 整组的注释,合批、天然不撞**。

---

## 6) R13 — 🟡黄(条件: owner 二次确认字段无未来消费;先迁5处测试再删;不碰 repo;不削弱 :110/:113 raise)

**判定理由**: 「死」定性已被重构推翻——生产侧 0 消费(本轮 rg 0 命中坐实),但被 5 处测试读活(reschedule:196 `==1`、scope_read_contract:108/190-191/220-221,本轮逐行坐实)。owner_pending=false 但建议升级二次确认。直删会破契约测试(响,非静默),故非红;但若误碰 repo raise 或顺手删则有静默风险→黄。

**灾难链(误判「死」连带删 `_latest_events_by_scope`:163-170 而未来有人想读 last_event 信号)**:
last_event_* 编码「该 op 有无执行事件」信号(latest is None 时为 None,scope.schedule_version 恒有值)。误判全死连带删 → **信号永久消失且无报错**(P6 类静默退化)。当前生产 0 消费故直删安全,但须 owner 拍「无未来消费」。

**次级爆点(漏退测试,响非静默)**:
漏退 scope_read_contract:220-221 构造 kwarg → `ExecutionFact(...)` 传已删字段 → TypeError 即时炸(响);漏退 :190-191 dict 快照键 → KeyError/断言失败(响)。

**最危险静默变体(若顺手删 repo:399 改回查询)**:
若 R13 越界把 repo:399 `list_latest_events_by_op_ids` 从 raise 改回真实查询 → **复活 R18 要消灭的越身份读取**,静默破坏「按计划身份读取」契约。

**修正建议(前置/顺序/禁区)**:
1. **前置**: owner 二次确认字段无未来消费后再选路A(直删)/路B(保留+「我是故意的」注释)。
2. **迁移序(Q6)**: 先改 scope_read_contract(契约源头 :108/:190-191/:220-221)→ 再改 reschedule:196 → 生产代码删字段最后(测试先表达新契约,红→绿自证)。**registry 误写「退 foundation:172」是错的**(:172 与本债无关,真实是 :365 属 R18,不退)。
3. **禁区**: R13 不碰 repo(:399/:401 属 R18);不削弱 provider:110/:113 的 `raise ValueError("...完整计划身份...")`(软禁区,loud raise 不得改静默/兜底)。
4. **同文件串行**: R13 删字段收缩文件→ R19(:70)→ R15(:85),或同原子提交,避免后改桶照旧行号改错位置。

---

## 7) R20 — 🟢绿(条件已明确: LB01 先落 + 与 R17 协调行号;字节级等价无静默路径)

**判定理由**: P3 纯转发垫片,删后 5 处改直连 model。严格字节级等价(`from X import Y` 同一对象),无 None vs raise 边界,无静默炸路径(漏改即 ImportError loud,CI 拦)。六维全过:
- Q1承重: 毗邻 LB01(347-356/451-453)但物理隔离(:52 vs 347-453),只改 :52 import 块。
- Q2分层环: 改向 services/web/tests → core.models 合法下行,减一次 service→service 横向转发,0越层0环。
- Q3迁移: 无。
- Q4灵魂线: loud-degrade(`状态未识别`:83/`处理状态未识别`:117)由 model 实现,删垫片无法削弱。
- Q5等价: 严格超集 15⊂17,多出集=∅,无分支差异。
- Q6测试序: 2 测试 import 改写须与生产同 PR;门禁 :128 摘 + 指南 :151 删配套(漏则文档门禁红,记账失败非安全失守)。

**唯一隐患(已是 🟢 的执行纪律)**: registry planned_fix 误写 routes.py,真实是 context.py:11(本轮坐实 routes.py 零命中)。**前置: LB01 注释先落 + R17 删 :12 后重新 rg `from .operation_execution_labels import` 真实行号,不照抄 :52 快照。**

---

## 8) 漏项 — 本轮新发现没被计划覆盖的爆点/缺失前置

1. **【R15 收口的「半收口」陷阱·主透镜新发现】**: dossier 倾向「provider 跟随既成事实收口到 parse_operation_event_time」,但该符号是「整体 delegate」——空值与坏值都 raise。若执行者图省事整行 `return parse_operation_event_time(text)`,**空值分支(合法 optional)会一并被吞进 raise**。计划虽点了「区分空值vs坏值」,但**没明写「provider 收口必须是分支级而非整体 delegate」**——即 `if not text: return None` 必须**留在 provider 本地**,仅坏值路径走收口符号。这是「测试绿但护栏破」的高发点:若 parity 测试只测坏值不测空值,空值 raise 会漏网。**缺失前置: parity 矩阵必须含空值分支断言。**

2. **【R15↔R19 同文件紧邻撞行,跨 owner_pending 协调真空】**: 两者都 owner_pending=true 待裁,provider:70(R19)与 :85(R15)仅隔 ~15 行,且都改 provider 函数区。计划分别说了「R15 先于 R19」,但**两者都卡 owner 裁断**——若 owner 分两次裁(先裁 R19 后裁 R15 或反之),先落地一方会漂移另一方行号,而 dossier 的 Edit old_string 锚点失效。**缺失前置: R15/R19 的 owner 裁断宜同批给出,或明确「先裁先动者落地后,后动者必重新 rg 回盘再写 Edit」。**

3. **【R13 路A删字段会动 ExecutionFact dataclass 字段顺序,潜在波及 R19 同 dataclass?】**: R13 删 :23-24 两字段改 ExecutionFact 结构。本轮核 R19 不读 last_event_*(snapshot 指纹不含),无直接耦合;但 ExecutionFact 是 R13/R15(填字段)/R19(消费 op_id)三债共享 dataclass,**计划未显式声明「R13 改 dataclass 字段集时,R15 的 :52/53 赋值行、R19 的消费点须同 dataclass 版本对账」**。当前安全(R15/R19 不碰被删字段),但若 R13 路A与 R15 收口同批,dataclass 同时增删字段+改赋值,须一次性对账 kwargs 完整性,否则 TypeError。**前置: 三债若同批改 provider,以 ExecutionFact 最终字段表为单一对账锚。**

4. **【R17 删 support:81 后 R15 support 处行号上移,但 R15 support 已落地】**: R17 删 support.py:81 推导式项使其后行号上移 1 行,R15 的 support `_parse_feedback_datetime`:225 会上移。dossier 说 R15 support 已落地(in_progress),但**若 R17 与 R15 收尾不同批**,R17 删行后 R15 若还需补 parity 测试锚 :225,行号已漂。**前置: R17 动 support 前确认 R15 support 处 parity 已锁,或 R17 后 R15 重新 rg :225。**

5. **【R18/R13 共用注释合批 vs R19 repo 串行的三方文件锁】**: operation_execution_event_repo.py 上同时有 R18(:399-405 补注释)、R13关心的相邻(:399)、R19(:67 私有版待裁)。R18+R13 走合批补注释(:399-405 整组一条注释),R19 在 :67 独立——三相距 330+ 行物理不重叠,但**计划未给「同一 repo 文件三债的提交序」硬约束**,若 R19 owner 裁定下沉/删 :67 与 R18 注释同批,merge 漂移风险在。**前置: repo 文件三债以「R18+R13注释合批 → R19 独立串行 rebase」为序。**
