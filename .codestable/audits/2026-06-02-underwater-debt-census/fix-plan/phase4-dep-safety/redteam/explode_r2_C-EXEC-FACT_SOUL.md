# C-EXEC-FACT 爆炸对抗 r2（主透镜:灵魂线热路径+收口等价）

> 簇 C-EXEC-FACT | 成员 LB01 R13 R15 R17 R18 R19 R20 | 第2轮 skeptic 只读不改
> 回盘 HEAD c2aa7501 / 2026-06-05；行号经本轮 rg 独立回盘（不信旧值）
> 主攻 Q4/Q5/Q6：P4改raise落热路径 / 收口逐分支等价 / 测试迁移序错复活兜底

---

## 逐债判定

### 🔴 R15（provider:85 P4 残留改 raise → 直穿 ExecutionFact 构造热路径，可用性放大）

**判定红。** 这是本簇唯一灵魂线真爆点，主透镜核心命中。

**当前真实证据：**
- `execution_fact_provider.py:85` `_parse_execution_time`：`if not text: return None`(:88 空值→None) + 三 fmt strptime 全失败→`return None`(:95 坏值→None 静默)。
- **坏值生产可达（关键）**：`core/models/operation_execution_state.py:15-16` `actual_start_time: Optional[str]` 是**已落库字符串**，由 `state_builder.py:242 _first_event_time` 从事件取。历史脏库/事件时间畸形 → provider 拿到非法格式字符串 → 坏值分支生产可达，非理论。
- **热路径无 try/except 兜底（致命）**：`_parse_execution_time` 被 `_fact_from_state:52/53` **内联进 `ExecutionFact(...)` 构造的 kwarg**；`_fact_from_state` 被 `facts_by_scope:120`、`facts_by_op_id_for_scopes:129+`、`facts_by_op_id_for_plan_rows:150+` 调用，**调用链全程无 try/except**（:76/:93 的 except 在解析函数体内部，非调用点）。

**灾难链（坏值改裸 raise）：** 历史脏 actual_start_time 字符串 → `_parse_execution_time` raise ValueError → 直穿 `_fact_from_state` ExecutionFact 构造 → `facts_by_scope` 无兜底 → 整个现场执行事实读取炸 → 甘特/重排/dashboard 读不出 facts（**正常用户读历史计划 500**）。这正是「P4 改 loud raise 落扫历史/legacy 热路径=可用性放大」。

**禁区铁律命中：** 灵魂线不新增兜底；但 P4 在此热路径**不得裸 raise**。修正建议（前置，按铁律）：
1. **空值→None 必须保**（:88，合法 optional「任务未开始无 actual time」，误判 required=制造假错）。
2. 坏值分支收口形态二选一，**owner 裁（owner_pending=true，不替拍）**：(a) 跟随既成事实收口到 `parse_operation_event_time`(event.py:75) 坏→raise，**但须在 provider 调用点包「可观测降级标记+记日志」而非裸 raise 穿透热路径**；(b) 保 None 但加 loud 日志/计数器（可观测降级），不更深静默。
3. **先补 §7 三处 required/optional parity 测试再动**（tests/ 当前全缺），否则未来重构一刀切复发 P5。

---

### 🔴 R17（删 support:81 推导式项 → 误碰 LB01 同函数体写死 / 误删活键）

**判定红（高危边，非红在病理而在毗邻爆面）。** LB01↔R17 同 `_build_event_payload`，本簇最危险边坐实。

**证据：** R17 删点 = service:12 死 import + support:11 import + support:81 推导式元组项 `EXECUTION_EVENT_EXCEPTION,`。LB01 写死 :471-473（`source_table=SOURCE_SCHEDULE/effective_plan_role=ROLE_ADOPTED/scenario_id=None`）+ :475 `_REPORTED_STATUS_BY_ACTION[action]` **与 R17 触及的 reported_status 同属 `_build_event_payload`**。

**双爆面：**
1. **撞写死**：R17 若「顺手清理/重构」`_build_event_payload` → 打穿 LB01 消毒层 → scenario/candidate 现场事件落库污染重排护栏（数据完整性事故，静默）。
2. **误删活键**：support:80 `EXECUTION_ACTION_REPORT_EXCEPTION`（活键）vs :81 `EXECUTION_EVENT_EXCEPTION`（死键），**必须删 :81 而非 :80**。删错 :80 → "report_exception" 键消失 → `_normalize_action` 成员校验把真实报异常误判非法 → 用户报异常被静默拒。

**修正（前置/顺序，强制）：** LB01 两处注释先落（门控 service 文件）→ R17 才动 → 删点限 :12/:11/:81 三行净删，**绝不碰 :368-374 硬拒、:471-473 写死、:80 活键**。R17 删 :81 后 :225（R15 support）/:52（R20）/:471（LB01）行号上移，后改桶**重 rg 回盘**不照抄快照。

---

### 🟡 R13（死字段 :23-24 被 3 测试读活 → 删序错=测试红/破契约）

**条件可做：** owner 二次确认「字段无未来消费」+ 先迁测试后删码。

**证据：** 死字段定义 :23-24、赋值 :56-57；生产侧 `rg .last_event_schedule_(version|id) core/ web/ data/` = **0 命中**（生产零消费坐实）。但 **3 测试读活**：`reschedule_execution_facts.py:196` 直读 `== 1`、`scope_read_contract.py:108`(`is None`)/:190-191(dict 两键)/:220-221(构造 kwarg)。

**灾难链（序错）：** 先删码后退测试 → :220-221 `ExecutionFact(last_event_schedule_version=None...)` 传已删字段 → **TypeError 测试红**（响，可拦）；:196 `==1` 无字段可读 → 红。非静默，但序错即红。

**条件：** (1) owner 裁路 A 直删 vs 路 B 保留补注释；(2) 走 A 须**先改 3 测试（scope_read_contract 契约源头→reschedule 消费）后删码**（红→绿自证）；(3) R13 **不碰 repo:399**（属 R18，registry 强耦合已解除）；(4) 同文件序 R13→R19→R15 或同批，删字段(-2~-13行)使下方 R19:70/R15:85 上移须重 rg。(5) 软禁区 :110/:113 raise 不得削弱。

---

### 🟡 R19（provider/repo→snapshot 收口 → 破指纹 sorted / 越层 / 导入环）

**条件可做：** owner 裁落点 + 保 sorted + 不越层不成环。

**证据：** 三函数体逻辑全等，唯一差异末行：snapshot:40 `return sorted(out)` vs provider:82/repo:79 `return out`。**snapshot sorted 是事实承重**：`build_execution_snapshot:78` 调 `positive_op_ids` 得 ids → :91 sha256 进指纹 → :94 `op_ids=ids` 落 payload。

**灾难链（统一错）：** 若误把 canonical 统一成不排序或让 snapshot 走不排序 → sha256 revision 对同输入产不同值 → 下游 4 处 guard/publish/scenario 快照比对**静默失真**（无测试拦截，test_consumers 空）。越层（repo→service data→service）/导入环（provider→snapshot→provider，snapshot.py:7 已 import provider）则是**响**爆（CI 拦）。

**条件：** (1) owner 裁 repo 落点（core/models 下沉 vs 保私有补注释）；(2) canonical **强制 sorted**+「我是故意的:指纹依赖排序」注释+parity；(3) provider 收 sorted 版 → missing[0](:147 raise 文案)首 op_id 可能变（[3]→[1]），须 parity 断言或 owner 接受文案变；(4) **与 R01/R46 共享 `__all__`:118-123 串行对账**；(5) 不让 repo/provider 反向 import snapshot。

---

### 🟢 LB01（承重,仅补注释）

**安全（绿）。** 修法纯补两处「我是故意的」中文注释（:368 上方 + :471 上方）+认账已存在契约，零删/零透传/零统一/零加形参。禁区 :368-374/:381-382/:471-473 本体零改。门控 service 全部删改（注释先落→R17→R20）。注：registry 三处证据漂移（A git态MM/B repo已 validate 强校验/C 测试重命名）dossier 已主动标注，**不改变承重仅注释终态**。无可炸点。

### 🟢 R18（stub:401 补护栏注释）

**安全（绿）。** :399-405 共 6 格 `raise _unscoped_execution_read_error()` 契约护栏；修法仅补一条注释覆盖整组，零行为变。生产零调用、parity 测试 :367 已存在。禁区:**严禁直删**（退化 AttributeError 击穿契约）、**严禁改 return {}** 静默。与 R13关心:399 共注释合批天然不撞。R18↔R13 强耦合已解除（R13 不入 repo）。

### 🟢 R20（删 service 垫片→直连 model）

**安全（绿）。** 垫片 35 行纯转发，5 处 import 改连 `core.models.operation_execution_labels`（6 处已直连为主流）。字节级等价，漏改即 ImportError（响）。loud-degrade 标签由 model 保全。R08/R09/R12 假边删除。禁区:只改 :52 import 块，绝不碰 LB01 :347-356/:451-453。前置:LB01 注释先落+与 R17 协调行号（R17 删 :12 后 :52 上移须重 rg）。

---

## 漏项（本轮新发现，计划未充分覆盖）

1. **R15 调用点无兜底是真爆点，dossier §4 仅说「provider 包 try/except 转可观测降级」但未点明 `_fact_from_state` 是内联 kwarg 构造、`facts_by_scope` 链全程裸奔**——裸 raise 会穿透整个 ExecutionFact 构造，不是「下游可能没接 except」而是「下游确定没接」。owner 裁时须明确：收口点即便选 raise 版，provider 侧**必须**包降级层，否则坏值改 raise = 历史计划读取直接 500。这是 P4 在本簇最硬的「可用性放大」，应列为 owner 裁断的**硬约束**而非可选项。

2. **R15 空值分支 None 与坏值分支 None 当前共用一个 return**（:88 与 :95 都是 None）——收口时若只盯坏值改 raise 而代码上两者同函数，极易连空值一起改，制造假错（任务未开始炸）。前置须**先拆分空值/坏值两分支**再分别处置，dossier 提了「区分」但未强调当前是同函数体内两个独立 return 易误连改。

3. **R13/R18 共测试 :352 `test_..._rejects_unscoped_op_reads`** 一个函数内 :365（R13关心 list_latest_events）+:367（R18 list_latest_exception）同一 `pytest.raises` 序列——若 R13 走路 A 误顺手删 repo:399，会同时破 :365 断言且与 :367 相邻，**两债测试耦合在同一测试函数**，比 dossier 描述的「相邻行」更紧（同测试体），R13 碰 repo 的连带爆面应升级标注。
