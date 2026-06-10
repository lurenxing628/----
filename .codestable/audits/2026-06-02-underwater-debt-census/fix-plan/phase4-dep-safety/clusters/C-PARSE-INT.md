# C-PARSE-INT 原子簇分析（只读不改）

> **2026-06-08 B 执行补登：G19(R01+R04) 已 fixed。** 执行顺序为 R01 先删 `_iter/count/has` 死链并退 SP05，R04 后收口 `_strict_positive_int` 到 `parse_required_int(..., reject_integer_float=True)`，剩余 5 处调用点均捕获 `ValidationError`；B/C 哨兵只补注释与 parity，行为保持 `→0` / `→None`。
> **GF1 状态：已落地。** `core/shared/strict_parse.py` 已有 `reject_integer_float`，默认 `False`，并有 `tests/models_domain/test_strict_parse_blank_required.py` 钉默认兼容与严格拒绝两路。G20(R59) 已在该前置满足后完成单簇自证。
> **2026-06-08 B 执行补登：G20(R59) 已 fixed。** `parse_report_nonnegative_int` 已保留 blank 短路并收口到 `parse_required_int(..., min_value=0, reject_integer_float=True)`；私有正则 `_INT_TEXT_PATTERN`、`_parse_plain_report_int` 和孤儿 `import re` 已删除；测试已补 blank default 与兄弟 `parse_report_int("2000.0")` 不误改守卫。

> 簇 id: C-PARSE-INT（C01 的手工原子子簇）
> 成员债: R01 / R04 / R09 / R28 / R59 / R08
> 主要文件: schedule_payload_contract.py / strict_parse.py / report_number_parsing.py / batch_service.py / resource_dispatch_execution_service.py / scheduler_resource_dispatch_execution.py / operation_execution_scope.py
> 全部行号 2026-06-05 当前工作区 rg 回盘，不信 dossier/registry 旧值。

## 0) 成员定位回盘（live code 实证）

| 债 | 桶/病理/承重/owner_pending | 主文件 | 关键行号（rg 回盘 2026-06-05） |
|---|---|---|---|
| R01 | B14 / P6 死码 / false / false | schedule_payload_contract.py | `_iter_actionable_results:67`(body 67-87)、`count:90`、`has:94-95`、`__all__:414-415`、`typing import Iterator:5`（删死簇后孤儿，须同删） |
| R04 | B05 / P5 收口 / false / false | schedule_payload_contract.py（+strict_parse.py 收口点） | `_strict_positive_int:50`，6 调用点 `:72/:149/:198/:308/:324/:372`（:72 在 R01 删区内！）；6 处 except `(TypeError,ValueError)` 须同步加 `ValidationError` |
| R59 | B05 / P5 漂移 / false / false / **2026-06-08 已 fixed** | report_number_parsing.py（+strict_parse 收口点） | 已删除 `_INT_TEXT_PATTERN` / `_parse_plain_report_int`；`parse_report_nonnegative_int:51` 已委派 `parse_required_int(..., reject_integer_float=True)`；续命测试在 `tests/web_pages/test_web_silent_fallback_contract.py` |
| R28 | B05 / P4 静默吞错 / false / false / **2026-06-08 已 fixed** | batch_service.py（+number_utils 收口点） | `_safe_float:56`(@staticmethod :55，body :57 已薄包装到 `parse_finite_float(..., allow_none=True)`)，消费点 batch_template_ops.py:172 / batch_copy.py:72；fitness 白名单 test_architecture_fitness.py:77 实测保留 |
| R09 | B05 / P5 收口 / false / **owner_pending true** | resource_dispatch_execution_service.py:24 + scheduler_resource_dispatch_execution.py:33（2 旧副本） | 收口点 `parse_positive_execution_int` **已存在** operation_execution_scope.py:9；`parse_optional_positive_int` 全仓=0（新建前提作废）；C 路 context.py:28 已收口 |
| R08 | B01 / P6 死码 / false / **owner_pending true** | scheduler_resource_dispatch_execution.py | 死常量 `_FEEDBACK_DISABLED_REASON:25`、死分支① `:227-228`、死分支② `:367-368`；活路径 `:234`；消费者 context.py:229/237/246（**非** routes.py，registry 误标） |

**F1（共享前置，非债，是 R04+R59 共用的 strict_parse 改造）**：2026-06-08 已落地，`reject_integer_float` 已加在 `core/shared/strict_parse.py` 并经 `parse_required_int` 透传，**默认 False**。默认兼容与严格拒绝两路已由 `tests/models_domain/test_strict_parse_blank_required.py` 覆盖；G20(R59) 已跑自身受影响测试并 fixed。

**收口点全部已存在，本簇零新建模块**：R04/R59→`parse_required_int(strict_parse:81)`；R28→`parse_finite_float(number_utils:14/23)`；R09→`parse_positive_execution_int(operation_execution_scope:9)`（corrections A 已确认，不新建 parse_optional_positive_int）。

## A) 原子子簇（必须同批 vs 可独立）

本簇拆成 **4 个原子子簇**（A1/A2/A3/A4）+ **1 个共享前置门 F1**（不是子簇，是 A1/A2 共用的 strict_parse 改造，须最先落且默认 False）。

### A1 = {R01, R04}　原子原因：同物理文件 schedule_payload_contract.py + 行号互撞 + 删除面∩收口面交集
- **同文件**：R01 删 `_iter:67-87`/`count:90-91`/`has:94-95`/`__all__:414-415`；R04 收口 `_strict_positive_int:50` 函数体 + 改 6 处 except。
- **交集（关键）**：R04 的调用点 `:72` 正落在 R01 要删的 `_iter` body(67-87) 内。R01 删 _iter 后 R04 收口面 6→5 点；R01 删约 29 行 → R04 :149 以下行号上移 ~29 行。
- **内部顺序：R01 先删 → R04 后收口**。理由：R01 先删缩小 R04 收口面（消掉 :72），R04 再按删后新行号 rg 重定位剩余 5 点。反序则 R04 在 :72 的改动白做 + R04 改 except 后 R01 死链判定踩漂移语义。**必须同 PR 原子提交**（强行号互撞，无法跨 PR 安全串行）。
- **R04 自带不可拆子动作**：F1 前置（见下）+ 6 处 except 同步加 `ValidationError`（漏一处 → 脏 op_id 由「静默跳过」变「ValidationError 一路上抛」炸排程统计/持久化，low 踩 P0）。

### A2 = {R59}（依赖 F1，独立文件，2026-06-08 已 fixed）
- R59 已改 report_number_parsing.py（`same_file_siblings=[]`、`interference_edges=[]`，独立文件）。
- **与 R04 共享 F1 产物**（`reject_integer_float`）：F1 已先落地并保持默认 `False`；R59 已在 G20 中显式传 `reject_integer_float=True`，所以 `'1.0'`/`1.0` 仍按导出行数字段语义 raise。
- **执行终态**：删除私有正则与私有解析函数，保留 blank→`blank_default` 短路，非 blank 收口到 `parse_required_int(..., min_value=0, reject_integer_float=True)`；未改 `parse_report_int`、`parse_report_float`、`__all__`。

### A3 = {R28}（完全独立叶子，2026-06-08 已 fixed）　原子原因：无
- batch_service.py 孤儿债（`same_file_siblings=[]`），已收口到既有 `parse_finite_float`，**未改 number_utils.py 任何一行**。
- 与 R04/R09/R59 是 co-change 组但 registry 明示「无代码耦合」，不共用被改符号，**不依赖 F1**（走 parse_finite_float 自己的 raise，与 reject_integer_float 无关）。
- 已执行方案 b：保留 `_safe_float` 名，函数体为 `return parse_finite_float(value, field="ext_days", allow_none=True)`。`pytest -k test_no_new_local_parse_helpers` 已证明 fitness 白名单 test_architecture_fitness.py:77 必须保留。后续不要重复删除白名单或改消费点。

### A4 = {R08, R09}　原子原因：同物理文件 viewmodel scheduler_resource_dispatch_execution.py，须串行避免行号互撞
- **同文件**：R08 改 `:25/:227-228/:367-368`（文件中下部）；R09 改 B 副本 def `:33` + 调用点 `:257/:258/:353`。物理区段不重叠，但同文件删行会位移彼此锚点。
- **内部顺序：R08 先（Batch-3/B01）→ R09 后（Batch-6/B05）串行**。R08 删约 7 行（:25 常量 + :227-228 + :367-368），R09 的 def:33 在删点之上不受影响、调用点 :257/:258/:353 均在 :367 之上；反序（R09 先收口）会让 R08 的 :367-368 锚漂移更大。
- **两者都 owner_pending=true**：R08 待裁「feedback_write_enabled 是否未来总开关预埋」；R09 待裁「sink 落点 + C 路是否一并收口 + float/bool 契约取舍」。**owner 未裁前 A4 整体不进执行批次、只标不给终态**。
- **R09 是跨子簇的：B 副本(viewmodel:33)属 A4，A 副本(service.py:24)属 A1 邻域文件**。R09 两副本须分两路 parity（见 C 节 corrections A）：C 路严格 float/bool→None（5.9→None），A/B 旧内联宽松（5.9→5）；A/B 直接收口会静默放宽，须先补 parity + owner 裁语义。

### 独立性总结
- **A1（R01+R04）原子内核**：必须同 PR。
- **A3（R28）**：完全独立叶子，已 fixed，后续只做残留核查。
- **F1 门**：A1 的 R04 + A2 的 R59 共用，最先落、默认 False。
- **A2（R59）**：F1 后独立，2026-06-08 已 fixed。
- **A4（R08+R09）**：同文件串行 R08→R09，**双 owner_pending 阻塞**，R09 还跨 A1/A4。

## B) 跨簇边（本簇成员指向其他簇债的依赖）

| 本簇债 | → 外簇债 | 关系类型 | 说明 |
|---|---|---|---|
| R04 | → LB08（auto_assign_resource_errors.py 文案/正则桥承重） | 承重先于动同文件 / 禁区毗邻 | R04 在该文件只动哨兵 B `_positive_int:114`（补注释）；LB08 禁区=一切错误文案常量/`AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES`/`_auto_assign_error_identity`（约 :126+）。R04 注释修法天然不碰，但**须确认 LB08 认账注释先落或同批**。 |
| R09 | → R07（service.py，已 fixed） | 承重/结构先于收口（前置） | R07 在 service.py:24 邻域改 raise（corrections E：已 fixed，用 ValidationError 偏离需 owner 认账）。R07 已落 → R09 收 A 副本(service.py:24)须在 R07 稳定行号上重盘。**已是前置完成态**。 |
| R09 | → R20（operation_execution_labels.py） | **假边，删** | registry 标 R20 same_file:scheduler_resource_dispatch_execution.py，但 R20 primary=operation_execution_labels.py（context.py:11），不碰本文件。corrections B 明列 R20↔{R08,R09,R12} 三边全假。 |
| R09 | → R15/R17（operation_execution_feedback_support.py STRICT `_positive_int:161`→raise） | 禁区毗邻（非依赖） | R15/R17 在另一文件的 STRICT 写入闸，是 R09 禁区（严禁误删当重复）。无收口竞争，仅「别碰」。 |
| R09 | → R46/LB08（scheduler_public_errors.py） | 禁区毗邻 | STRICT `_positive_int:167`→raise 写入闸，R09 禁碰。 |
| R28 | → R04/R29/R33（number_utils.py 同住） | 软约束（无代码耦合，已 fixed） | 三债住 R28 收口目标模块 number_utils.py，但 R28 只**调用** parse_finite_float 不改其一行。R28 已落地；仅当未来 R04/R29/R33 改 parse_finite_float 签名/边界语义才需要复核 R28 相关测试。 |
| R01 | → R26/R43（test_sp05_path_topology_contract.py） | **假边/弱边，降级** | corrections B：R26↔R43 是 scheduler_config.py basename 假碰撞；R01 改 SP05 的 schedule_persistence 模块键块(:53-56)，R26/R43 改别的模块键条目，同文件不同区。R01 改 SP05 时须 rg 重定位模块键当前行（别照 :54-55）。 |
| R01 | → R19/R46（sym:__all__） | **弱标签，非边** | 不同文件各自的 __all__，非同一列表，无行号互撞，无顺序敏感。 |

**净跨簇硬依赖**：仅 **R04→LB08 禁区毗邻**（认账注释协调）、**R09→R07 前置（已完成）**。其余皆假边/弱边/软约束。

## C) 相对旧 146 边的变化（逐条：删/新/降）

### 删除（假边 / 已修前置）
1. **删 R20↔R09**（及 R20↔R08）：corrections B 假边。R20 primary=operation_execution_labels.py，不在 viewmodel/service。registry same_file 标记误标作废。
2. **删 R20↔R08**：同上（R08 dossier 字段5 也独立纠出 R20 边作废，回盘 R20 在 context.py:11）。
3. **降级/弱化 R01↔R26、R01↔R43**：corrections B 指 R26↔R43 为 scheduler_config.py basename 假碰撞；对 R01 而言只是 SP05 同文件不同区的弱「同文件」标签，不构成顺序硬边 → 降为「R01 改 SP05 时 rg 重定位」纪律，非阻塞边。
4. **弱化 R01↔R19、R01↔R46（sym:__all__）**：不同文件各自 __all__，非真行号互撞 → 从「同符号边」降为「弱标签」，不入 DAG。

### 新增（dossier/corrections 回盘补出，旧 146 未显式建）
5. **新增 F1 共享门：R04 ⇄ R59**（经 `reject_integer_float`）。旧图把 R04/R59 列 co-change 组但未显式建「F1 互锁」边。本簇确认：R59 收口**强依赖** R04 的 F1 先落（否则撞续命测试 :247/:250）。这是真硬边（收口前置）。
6. **新增 R09 双副本分裂边**：corrections A 把 R09「唯一批准新建 parse_optional_positive_int」前提作废（收口点 parse_positive_execution_int 已存在）→ R09 内部从「3 副本同体收口」变「C 路已收口 + A/B 2 旧副本待收编，且须分两路 parity（A/B 宽松 vs C 严格）」。这改变了 R09 的原子结构（A 副本归 A1 邻域、B 副本归 A4）。
7. **新增/确认 R04→6 处 except 同步改边**（异常类型逃逸灾难链）：ValidationError 非 ValueError 子类，6 处 except 须同 PR 加捕 ValidationError，不可拆。

### 降级（硬→软）
8. **R28↔{R04,R29,R33}（number_utils.py same_file）降为软约束且 R28 已 fixed**：R28 只调用不改 parse_finite_float，无代码耦合（registry 明示）。从同文件硬边降为「仅当他债改 parse_finite_float 签名才敏感」的条件软边。
9. **R09→R07 降为「前置已完成」**：corrections E 标 R07 已 fixed（偏离用 ValidationError 待认账）。该边从「待做前置」降为「已满足，剩认账」。

### 本簇不涉及的 corrections B 假边（仅记录，本簇成员不在两端，无需处理）
R02↔R25、R45↔{LB07,R33,R51}、R32↔R15、LB04↔{LB07,R33}、config_snapshot R26↔R71、R13↔R18 解耦、R05→R34 降级——均不含本簇 6 成员，本簇不动。

## D) 承重前置（簇内 LB/N1/N2/R03/R58 承重点门控的结构动作 + 禁区行）

本簇 6 成员 **自身全部 load_bearing=false**，无簇内承重债主体。承重门控来自**毗邻/同源**承重点，须先落注释/parity 才放行结构动作：

1. **LB08（外簇承重，毗邻 R04）**：auto_assign_resource_errors.py 的「中文文案↔正则桥同生共死」。
   - **门控**：R04 在该文件改哨兵 B `_positive_int:114`（补「我是故意的」注释 + parity 钉 →0 契约）前，须确认 LB08 认账注释已落或同批。
   - **禁区行**：`auto_assign_resource_errors.py` 内一切错误文案常量/前缀/`AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES`/`_auto_assign_error_identity`（约 :126+）——R04 一行不许动。

2. **N1（新承重，corrections C，毗邻 R08/R09 所在执行车道）**：`scheduler_resource_dispatch_execution_context.py:129-130` `_identity_allows_query_membership_check` 单字段 `can_write_feedback` 收敛，零注释=失忆债，load_bearing 倾向 true。
   - **门控**：动 R08（同执行车道、依赖 can_write_feedback≡feedback_write_enabled 同源不变式）前，N1 须先补「我是故意的」注释（钉 can_write_feedback⇒adopted-only 来源链）+绑 parity。R08 删死分支的安全性**依赖 service:127≡:130 同源**，须先在测试钉该不变式守卫（把 (T,F) 不可达从偶然变契约）。
   - **禁区行**：`_can_write_feedback:89-110`、`_is_official_plan:70-84`、本闸 `:129-130`——禁放宽成 or、禁加 preview 旁路。

3. **N2（新承重，corrections C）**：`operation_execution_event.py:156-163` `_event_id_for_revision` 末位 `return 0` sentinel。
   - **与本簇关系弱**（本簇不直接动该文件），但 R09 收口涉及 operation_execution_scope.py 同域，须知 N2 禁区：禁删 `if index<total: raise`、补注释（末位无后继故允许 0）。本簇不触发 N2 结构动作。

4. **F1 默认值（准承重，R04+R59 共用）**：`reject_integer_float` 改 `_parse_finite_int`（被 parse_required_int 共用，core/algorithms 大量调用方）。
   - **门控禁区**：**必须默认 False**。默认 True = 把所有现有 parse_required_int 调用方（sgs_graph.py 8 处等）的 `3.0` 由接受变 raise → 配置/排程静默回归。F1 自带 parity（reject_integer_float=True→3.0 raise；=False→3.0 接受）须先绿，再放行 R04/R59 收口。

5. **R03/R58**：不在本簇成员内，本簇无相关门控。

**门控结论**：A1 的 R04 须等 LB08 认账协调 + F1 默认 False parity 绿；A4 的 R08 须等 N1 注释 + service:127≡:130 同源守卫先落 + owner 裁。无簇内 LB 主体需「先注释才删」。

## E) fixed 成员作为前置已完成 — 残留动作（认账注释）

本簇 6 成员里 **R28 已 fixed**（2026-06-08 Batch-A/G21），**R01/R04 已 fixed**（2026-06-08 Batch-B/G19），**R59 已 fixed**（2026-06-08 Batch-B/G20）；**R09/R08 亦已 fixed**（✅ 2026-06-10 终态校正：原「仍 planned+owner_pending」已过期——registry 现盘 R08/R09 均 `fixed`，R09 逐字节复制助手收口到 `parse_positive_execution_int`、R08 休眠开关死分支生产不可达且全树零残留）。其他 fixed 态来自**毗邻前置**（corrections E：LB03/LB06/R07/R16/R56/R57 已结构性消除）：

1. **R07（已 fixed，A4/A1 邻域前置）**：resource_dispatch_execution_service.py 改 raise 已完成，但**偏离**——用 `ValidationError(field=schedule_id)` 而非计划的 `AppError/ErrorCode.NOT_FOUND`，与写门禁 feedback_service.py:385 跨文件错误类不对称，且缺 schedule=None→raise 专项回归。
   - **残留动作**：owner 须**认账**此偏离 + 裁是否统一错误类（改则补 AppError/ErrorCode 导入）。
   - **对本簇影响**：R09 收 A 副本(service.py:24) 须在 R07 稳定后的行号上重盘（回盘 service.py:24 def 仍在，R07 改的是别处兜底点，A 副本未被 R07 触碰）。

2. **R16/R56/R57（已 fixed，非本簇直接邻）**：corrections D：R56 走高风险结构路线删 `_is_execution_review_request` 本体（违铁律3），owner 须认账 + 确认契约测试同提交入账。与本簇无直接耦合，仅作 DAG 前置已完成态记录。

3. **R28（本簇 fixed 成员）**：`_safe_float` 已保名收口到 `parse_finite_float(..., allow_none=True)`；旧静默吞错分支已删除；fitness 白名单保留已由 `test_no_new_local_parse_helpers` 证明。后续残留动作只有避免重复施工。

4. **R29（corrections E：误标 → planned owner-pending）**：number_utils.py 仍全量 delegation-facade、4 兄弟全薄壳，半截迁移不对称客观在场。与 R28 同住 number_utils.py，但 R28 只调用 parse_finite_float 不改文件，**R29 不阻塞 R28**（软约束，见 C-8）。

**残留动作清单**：仅 R07 偏离需 owner 认账（错误类不对称 + 缺回归）；其余 fixed 前置已硬完成，无本簇阻塞。

## 返回摘要

簇 C-PARSE-INT | 原子子簇 4 个：A1{R01+R04 同文件强行号互撞，2026-06-08 已fixed}、A2{R59 依赖F1独立文件，2026-06-08 已fixed}、A3{R28 完全独立叶子，已fixed}、A4{R08+R09 同viewmodel串行+双owner_pending}；F1（reject_integer_float）已落地且默认False。
关键内部顺序：A1 已完成（R01先删→R04后收口，剩5点均接ValidationError）；A2 已完成（R59 保留 blank 短路后收口到 GF1 strict 模式）；A4 R08先(B01)R09后(B05)串行(:367-368锚)；R09 A/B两副本须分两路parity(C严格5.9→None vs A/B宽松5.9→5)。
跨簇边：R04→LB08禁区毗邻已在 G19 中绕开；R09→R07前置已完成(认账偏离)、R28→number_utils软约束。
边变化：删 R20↔{R08,R09}假边、R01↔{R19,R46}__all__弱标签；R04⇄R59 的 F1 互锁现只剩 GF1→R59；R09双副本分裂边仍待执行；降 R28↔{R04,R29,R33}硬→软、R09→R07待做→已完成、R01↔{R26,R43}降为rg重定位纪律。
承重前置：F1默认False+parity已绿并已门控 R59 收口；N1注释+service:127≡:130同源守卫门控R08删死分支；LB08文案/正则桥禁区(:126+)已在R04哨兵注释中绕开；本簇自身零LB主体。
