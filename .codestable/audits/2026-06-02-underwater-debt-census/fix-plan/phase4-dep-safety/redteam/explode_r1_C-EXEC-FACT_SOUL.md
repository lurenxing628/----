# 逐簇爆炸对抗 r1 · C-EXEC-FACT · 主透镜 SOUL（灵魂线热路径 + 收口等价）

> skeptic 第 1 轮 / 只读不改 / HEAD c2aa7501 / 2026-06-05 全部行号经本轮 rg 回盘（不信旧值）
> 主透镜：Q4 灵魂线热路径 + Q5 收口逐分支等价（兼过 Q1/Q2/Q3/Q6）
> 成员债：LB01 R13 R15 R17 R18 R19 R20
> 默认怀疑：多数维度存疑即标红；不放过「测试绿但护栏已破」的静默失效。

---

## 本轮 rg 回盘真值表（权威，覆盖 dossier 旧值）

| 锚点 | 回盘 file:line | 实测内容 |
|---|---|---|
| R17 死 import（service） | `operation_execution_feedback_service.py:12` | `EXECUTION_EVENT_EXCEPTION,` |
| LB01 硬拒分支 | `feedback_service.py:369-371`，raise `:374` | 三条件 `!=ROLE_ADOPTED/!=SOURCE_SCHEDULE` |
| LB01 写死消毒 | `feedback_service.py:471-473` | `SOURCE_SCHEDULE / ROLE_ADOPTED / None` |
| `_build_event_payload` 函数体 | `feedback_service.py:455`def，`:475` reported_status | **R17(:475) 与 LB01(:471-473) 同一函数体** |
| R15 provider 解析 | `execution_fact_provider.py:85`def，空→None `:87-88`，坏→None `:95` | 双静默残留 P4 |
| R15 收口符号 | `operation_execution_event.py:75`，空→raise `:80`，坏→raise `:86` | **空值也 raise（与 provider 空→None 不等价）** |
| R15 support raise | `feedback_support.py:225`def，raise `:229` | 收口已落地，loud |
| R13 死字段 | `execution_fact_provider.py:23-24`定义/`:56-57`赋值 | 生产侧 `rg .last_event_schedule_*` 全仓 0 命中 |
| R13 测试读活 | reschedule:196 `==1`；scope_read_contract :108/:190/:191/:220/:221 | 5 处直读/构造 kwarg |
| R19 三处末行 | snapshot `:40 return sorted(out)`；provider `:82 return out`；repo `:79 return out` | 仅末行排序差异 |
| R19 指纹链 | snapshot `:78 ids=positive_op_ids` → `:91 sha256` | sorted 事实承重 |
| R19 provider missing | provider `:147 raise ...missing[0]` | 顺序影响 loud raise 文案 |
| R17 推导式死键 | `feedback_support.py:81 EXECUTION_EVENT_EXCEPTION`，活键 `:80` | 删 :81 保 :80 |
| R20 labels import | service`:52` / support`:24` / context`:11` | 三处经垫片，web 是 context（非 routes） |

---

## 逐债判定

### LB01 — 🟡 黄（承重门控前置必须先落，否则裸奔期 R17/R20 动同文件 = 静默击穿）
- **证据**：硬拒 `feedback_service.py:369-374` + 写死消毒 `:471-473` 本体零注释（`sed '466,473p'|grep '#'` 零命中，债真实）。文件当前 `MM` 态但禁区行本体零改（diff 仅 import 段 + `__all__` list→tuple）。
- **为何黄不绿**：LB01 自身修法（仅补两处「我是故意的」中文注释）零风险，但它是**整个 service 文件删改的门控前置**。在注释落地前若 R17 先删 :12 / R20 先改 :52，承重边裸奔。
- **灾难链（Q1 误删诱惑）**：后续若有人以「repo:241 已 `validate_current_official_execution_scope` 强校验，写死冗余」名义删 :471-473 → ① 删写死改透传：合法 adopted 请求边界值触发 repo/schema raise → AppError(DB_INTEGRITY) → **正常操作变 500（可用性事故）**；② 删写死且 repo validate 同期被「统一」掉：scenario/candidate 上下文现场事件静默落库 → `execution_fact_provider:40 _fact_from_state` 纯按 op_id 读无过滤 → `schedule_execution_guardrails:213` 把预览态当真实现场喂重排护栏 → **坏数据进排产决策，无 raise 无日志（数据完整性事故）**。
- **修正建议（前置/禁区）**：① 注释必须先落且锚定在符号上方（随行号移动不丢）；② 禁区行 :369-374 / :381-382 / :471-473 任何债不得改逻辑只可上方加注释；③ 注释口径与 LB02/LB05/LB06 读侧统一「只能挂在正式采用方案上」；④ 三路 parity（硬拒 raise vs 写死 coerce-to-safe vs repo validate raise）逐分支不等价，注释须主动驳斥「写死冗余可删」。

### R17 — 🔴 红（同 `_build_event_payload` 函数体，"顺手清理"即打穿 LB01 写死消毒）
- **证据**：R17 触及 reported_status `:475` 与 LB01 写死 `:471-473` 同属 `_build_event_payload`（:455 def）；死键项在 support `:81`，活键 `:80`。
- **灾难链（最危险边）**：R17 名义是删死 import（service:12）+ 删推导式死键项（support:81）。爆点 1：若执行者在删 :12 时「顺手重构/清理」`_build_event_payload`，或误判 :471-473 为可与 context 透传的冗余 → 直接静默削弱写死消毒 → 同 LB01 灾难链②（scenario/candidate 现场事件落库污染重排护栏）。爆点 2（Q6 误删活键）：若把 support `:80 EXECUTION_ACTION_REPORT_EXCEPTION` 当死键删（而非 :81）→ `"report_exception"` 活键消失 → `_normalize_action` 成员校验把真实「报异常」操作误判非法 → 用户报异常被静默拒（ValidationError）。
- **为何红**：物理上与承重写死同函数体，是计划明示的「最危险的边」；删错对象（:80 vs :81）或顺手清理都落在灵魂线热路径。
- **修正建议（顺序/禁区）**：① 硬前置 LB01 注释先落（PHASE0 §10.1，承重裸奔期严禁动）；② 只删 service:12 + support:81 + support:11 孤立 import 三行，**绝不碰** :369-374/:381-382/:471-475；③ 删 :81 一行使其后行号上移，R15(:225)/R20(:24/:52) 动手前须重 rg 回盘真实行；④ 三处一次原子提交，避免「表已删键但 import 仍在」悬挂。

### R15 — 🔴 红（provider 残留 P4：空值 vs 坏值不区分，直接收口=静默放大可用性事故）
- **证据**：provider `:87-88` 空→None（合法 optional：actual_start/end 任务没开始就为空）、`:95` 坏→None（静默吞坏值，唯一残留 P4）。收口符号 `parse_operation_event_time:75`：空→raise `:80`、坏→raise `:86`——**空值也 raise**。owner_pending=true。
- **灾难链（Q5 收口逐分支不等价 + Q4 改 raise 落热路径）**：若把 provider 直接收口到 `parse_operation_event_time` 一刀切 raise：① **空值分支**：合法「任务未开始」actual_start=空 → 改 raise → `:52/:53` 填 ExecutionFact 时炸 → 经 `facts_by_op_id_for_scopes`/`facts_by_op_id_for_plan_rows` 整个执行事实读取链抛错 → 若上层有宽 except 吞掉则**执行事实全空、排程按空数据重排（静默错误排程）**；若无 except 则甘特/重排读不出执行事实（可用性事故）。这是 P4 改 loud raise 落在「扫历史/读现场」热路径被放大的典型。② 反向（坏值仍保 None）：脏时间字符串静默变 None 喂 duration 计算 → 算出错误现场耗时进重排。
- **为何红**：dossier 自己标 owner_pending，且 §7 反例表证「空/坏 None→raise 是双重语义跃迁绝非平移」；主透镜 Q5 点名 R15 区分空值 vs 坏值，本轮坐实收口点对空值也 raise，直接收口必炸合法空态。
- **修正建议（禁区/前置）**：① owner 先裁（owner_pending=true，裁断前不进批次）；② **空→None 必须保留**（禁把合法 optional 误判 required，制造假错）；③ 坏值分支改向只能是「loud raise（确认 :52/:53 下游接得住）」或「可观测降级标记 + 记日志」，**禁更深 return None**（灵魂线）；④ 收口前先补三处 required/optional parity 测试（tests/ 当前完全缺），钉死「三处语义本就不同、禁一刀切统一」；⑤ R15 是 SCC 串行链最前置，须先于 R13/R17/R19 动这几个文件。

### R13 — 🔴 红（死字段被 5 处测试读活，无脑直删破契约；连带删 latest 链=信号永久静默消失）
- **证据**：生产侧 `rg .last_event_schedule_*` 全仓 0 命中（生产零消费坐实）；但测试读活 5 处——reschedule:196 `==1`、scope_read_contract :108(`is None`)/:190-191(dict 快照两键)/:220-221(构造 kwarg)。owner_pending=false（但「死」定性已被重构推翻）。
- **灾难链（Q6 测试迁移序错 + Q4 静默退化）**：① 若按 registry 旧 planned「无脑直删字段」而漏退 :220-221 构造 kwarg → `ExecutionFact(...)` 传已删字段 → TypeError 炸测试（响亮，可接受）；② 漏退 :190-191 dict 快照键 → KeyError/断言失败（响亮）；③ **真静默爆点**：误判「死」而连带删 `_latest_events_by_scope:163` + :118 调用（dossier 自标的「真实性能收益点」），但若未来有人想读「该 op 有无执行事件」信号 → 该信号（None 分支携带「无事件」语义）永久消失且无报错（P6 类静默退化）；④ 跨债：若 R13「顺手」碰 repo:397 区的 `list_latest_events_by_op_ids` raise stub 改回真实查询 → **复活越身份读取，静默破坏「按完整计划身份读取」契约**。
- **为何红**：「死」定性被 5 测试推翻，直删非无脑安全；连带删 latest 链是静默信号消失；R13↔R18 已解耦但 R13 仍可能误伸进 repo。多维存疑。
- **修正建议（前置/顺序/禁区）**：① 升级 owner 二次确认「字段确无未来消费」后再选路 A（直删）/ 路 B（保留+「我是故意的」注释）；② 测试迁移序：先改 scope_read_contract（契约源头）→ 再 reschedule → 生产删字段最后（红→绿自证）；③ **R13 不碰 repo**（:397 raise stub 属 R18 范畴，软禁区 provider:110/:113 + repo stub raise 不得改静默）；④ 同文件串行：R15 先（收口语义）→ R19 → R13 最后（删字段缩文件），或同一原子提交。

### R19 — 🟡 黄（条件：canonical 强制 sorted + provider missing 顺序 parity + repo 不越层；naive 三处全收口被双重阻断）
- **证据**：snapshot `:40 return sorted(out)` → `:78 ids` → `:91 sha256`（指纹强依赖排序，事实承重）；provider `:82 return out` 不排序、`:147 raise ...missing[0]` 顺序敏感；repo `:79 return out`（`_batch_ids_by_op_ids` SQL IN 顺序无关）。owner_pending=true。snapshot:7 已 import provider（反向收口成环）；repo 在 data 层（收 service 越层）。
- **灾难链（Q2 导入环 + 指纹静默漂移）**：① 若误把 canonical 统一成不排序、或让 snapshot 走不排序路径 → `build_execution_snapshot` sha256 对同输入产不同值 → 下游 4 处（persistence_guard/gantt_adjustment_publish/scenario/guardrails）快照比对、变更检测**静默失真，无测试拦截**（三函数零符号级测试，§8/§11 坐实 `rg tests/` 0 命中）；② 若强行让 provider 反向 import snapshot 收口 → service↔service 导入环（响，ImportError 可拦）；③ 若让 repo 收 service 层 → data→service 越层（响，test_architecture_fitness 可拦）；④ provider missing[0] 顺序变 → loud raise 文案里首个 op_id 变（轻、可见，非静默）。
- **为何黄**：本债 low + 三处逻辑全等，可做；但条件硬——canonical 必须 sorted（等同承重待遇）、收口形态须绕开环+越层双阻断、收口前必补 parity（当前零守卫）。多数维度可控但前置缺一即静默炸指纹。
- **修正建议（前置/禁区）**：① owner 裁 repo 落点（core/models canonical 归位 vs 保私有版补「我是故意的：顺序无关」注释）；② canonical 实现强制 `return sorted(out)` + 补「指纹稳定性依赖排序」注释（事实承重行 :40 等同承重待遇）；③ 收口前先补 `positive_op_ids` 黄金用例 parity（钉指纹排序）+ provider missing[0] 文案断言；④ provider(:82)/repo(:79) 改动须分别与 R15/R13(provider 文件)、R18(repo 文件) 串行避撞行号；⑤ 与 R01/R46 共享 `execution_snapshot.py:118-123 __all__` 块高顺序敏感，须串行对账最终导出表。

### R18 — 🟢 绿（前提已被 scope 重构推翻，终态=补「我是故意的」护栏注释，parity 已存在，零行为改动）
- **证据**：`operation_execution_event_repo.py:401` 已是单行 stub `raise _unscoped_execution_read_error()`，是 6 格拒绝非 scoped 读契约护栏之一（:354/:356/:397区/:401/:403/:405）；`EXECUTION_EVENT_EXCEPTION` 在本文件 0 命中（planned_fix 第 3 步无对象）；foundation:367 `pytest.raises(ValueError, match="完整计划身份")` 是契约断言（非续命）。生产零调（callgraph 零入边 + rg 仅定义+测试）。
- **为何绿**：终态修法是补注释（覆盖 :397-405 整组），不改行为/签名/import，foundation 测试继续绿。唯一风险是**误按 registry 旧 planned 直删**（会退化为 AttributeError 击穿契约）——但那是旧 planned 失真，dossier 已主动标红驳斥。
- **修正建议**：① 不直删、不退测试、不清 import（`OperationExecutionEvent` 被返回注解占用不可删）；② 与 R13(repo 相邻 stub) 共用同一条护栏注释合批，天然不撞；③ Phase2 owner F 门点头「降级为注释护栏」后再落注释。

### R20 — 🟡 黄（条件：LB01 注释先落 + 与 R17 协调行号；本体删垫片严格等价无静默路径）
- **证据**：垫片 35 行纯转发；5 处经垫片消费方 service:52 / support:24 / context:11 / 2 测试，回盘全坐实；web 真实是 context.py:11（非 registry planned 误写的 routes.py，rg routes 零命中）。R08/R09/R12 同文件干扰边经核全假（R20 不碰 ..._execution.py / gantt_tasks）。
- **为何黄不绿**：本体改 import（service/web/tests → core.models）严格等价（`from X import Y` 同一对象，删垫片改直连零行为差异），漏改即 ImportError（loud 可拦），无静默路径。但黄因两条件：① 改 service:52 须等 LB01 注释先落（同文件承重门控，Phase1 边 LB01→R20）；② R17 删 :12 上方 import 会上移 :52，须与 R17 串行/同批且动手前重 rg 回盘真实行号（禁照抄 :52 快照）。
- **灾难链（Q1 误碰承重）**：唯一真灾难链是改 :52 时误碰同文件 LB01 禁区（:369-374 硬拒 / :471-473 写死）→ 静默削弱承重。但 :52 与禁区物理隔离（相距 300+ 行），遵禁区即不触发。
- **修正建议（前置/禁区）**：① LB01 注释先落；② 与 R17 协调行号，后做方重 rg；③ 只改 :52 起 import 块为绝对 model 路径、保持 7 符号清单不变，绝不碰 347-356/451-453/369-374/471-473；④ 删文件同批摘门禁 docs_quality_gate:128 + 指南 :151（缺一文档门禁红）；⑤ 测试 import 改写与生产同 PR。

---

## Q1-Q6 六质问点小结（本簇）
- **Q1 承重误删**：LB01 写死 :471-473 / 硬拒 :369-374 是最大诱饵（「repo 已 validate 故冗余」），三路 parity 证逐分支不等价、必须并存。R20/R17 同文件须设禁区。
- **Q2 分层/导入环**：R19 naive 全收口被双重阻断（snapshot↔provider 环 + repo→service 越层）；其余债零新增 import，0 违规。
- **Q3 迁移耦合**：本簇写死 :471-473 与 schema.sql:190-192 三 CHECK + scope.py validate 三 raise 是配套最终底，禁删其 raise；R20 删文件须同步文档门禁记账。
- **Q4 灵魂线热路径**：R15 provider 坏值改 raise 落「读现场/扫历史」热路径，须区分空→None（保）vs 坏→loud；禁新增兜底/更深 return None。
- **Q5 收口等价**：R15 空值→None vs 收口点空值→raise 不等价（坐实）；R19 三处仅末行 sorted 差异、canonical 必 sorted。
- **Q6 测试迁移序**：R13 删字段前先迁 scope_read_contract→reschedule（5 处读活），漏退 :220-221 即 TypeError；R17 删 :81（非 :80 活键）。

---

## 漏项（本轮新发现，计划未充分覆盖）
1. **R15 provider「可观测降级标记」选项缺落点设计**：dossier 给「loud raise」或「可观测降级标记」两路，但坏值若选降级标记，ExecutionFact 无承载字段、下游 duration 计算如何识别降级未定义 —— owner 裁前需补该字段/契约设计，否则收口仍可能静默。
2. **R13 路 A 删字段会留 scope_read_contract:190-191 dict 快照模板孤键**：若只删 dataclass 字段与 :220-221 kwarg 而漏改 :190-191 的 dict 模板（它是独立 dict literal 非 dataclass 投影），快照比对处 KeyError —— 计划「先改契约源头」须显式列入这两行（dossier §11 提及但未单列为强制项）。
3. **R19 指纹零符号级测试 = 收口护栏盲区**：三函数 `rg tests/` 0 命中，snapshot sha256 漂移无单测拦截。计划要求「先补 parity 再动代码」，但未把「指纹回归基线测试必须先 merge」列为 F 门硬阻塞 —— 建议升级为收口前置 F-fingerprint 门。
4. **R17 原子提交跨度被低估**：R17 三处（service:12 + support:81 + support:11）与 R20（service:52 + support:24 + context:11）在 support 文件高度交错，两债同改 support 的 import 块 :11/:24 区，计划标「串行」但未明确二者是否须同一原子提交以避 import 块二次漂移 —— 建议 R17+R20 在 support 文件上合批。
