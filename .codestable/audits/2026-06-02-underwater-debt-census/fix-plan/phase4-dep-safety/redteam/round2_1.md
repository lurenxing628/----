# 红队第2轮复检 · agent 1（只读不改 · 默认怀疑）

> 输入：_interference_rebuilt.md（含红队第1轮修订）。回盘 HEAD c2aa7501ca2dc5ccfd2e64006094f584e2c1089b（实测一致）。
> 任务：复检第1轮采纳的 11 项修订是否真改对了；有无新引入不一致；拓扑是否仍无环；承重前置/facade 晚于收敛/parity 先于收敛是否仍守；有无第1轮漏掉的硬伤。
> 全部行号 2026-06-05 在 HEAD 实盘 rg 复核，不信旧值。只读，未改任何 .py。
> 铁律遵守自检：只读 ✓；承重(R09/N1/N2/LB01/LB02/LB05/LB07/LB08/LB03/R05)未删/未统一/未透传 ✓；灵魂线未新增兜底 ✓；P5 收口到已存在点 ✓；分层未引入违规 ✓；owner_pending 未给终态 ✓。

---

## 一、第1轮 11 项采纳修订逐项复检（rg 实盘）

| 红队条 | 复检结论 | 实盘证据 |
|---|---|---|
| **R1-P1** E28 scope.py | **改对** | operation_execution_scope.py = 3499B ✓；`parse_positive_execution_int`:9（raise :11/:17/:20）✓；`validate_current_official_execution_scope`:36（三 raise :44/:47/:50）✓；调用点 :77/:78/:79 ✓。E28「同文件承重毗邻 S 边、禁碰 :36-50、按符号定位」成立 |
| **R1-P2** 第3副本 + A 副本调用点 | **改对** | `schedule_persistence_errors.py:13` 确为 `-> Optional[int]`，body `int(value or 0)`（:15），不 wrap 收口点 ✓，调用点 :24/:56/:77 ✓。service A 副本 `resource_dispatch_execution_service.py:24` def + 调用点 :169/:180/:181 ✓，放宽点 :180-181 `== int(...)` 比较 ✓。「2 已认 + 1 待 owner 认」口径成立 |
| **R1-P3** E29 N1↔C 路 | **改对** | context.py `_positive_int`:28-30 wrap `parse_positive_execution_int`（:30）✓；C 路调用点 :96/:97/:107/:258/:271/:272 **逐个命中** ✓；N1 `_identity_allows_query_membership_check`:129-130（`can_write_feedback`）✓。E29「N1 与 C 路同住 context.py」成立 |
| **R1-P4** E27 event.py sentinel | **改对** | `_event_id_for_revision`:156，`if index < total:`:161 / `raise`:162 / `return 0`:163 ✓；`_suggest_reschedule_field`:177 `return 0`:179 ✓；`previous_event_id = 0`:205 + 下游 :218/:246 ✓。importers 实盘命中 feedback_service / scheduler_resource_dispatch_execution(viewmodel) / operation_execution_feedback_actions / gantt_adjustment_publish_service 四者 ✓。**唯一名义瑕疵**：doc 称 `__suggest_reschedule`，真符号 `_suggest_reschedule_field`（行号对、名字差一前缀，不影响承重结论） |
| **R1-P5** §3.2 fail-CLOSED 方向硬门 | **改对（一处文件归属偏移，见硬伤②）** | navigation_context.py:79 `plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED` = fail-CLOSED ✓。LB06 行：doc 标 `reports_page_support.py`，实盘该文件（真路径 web/routes/reports_page_support.py，无 fail-closed 逻辑本体）只是消费方；fail-CLOSED 强制 adopted+scenario=None 的本体在 `reports_execution_review_context.py` / `reports_request_support.py:require_execution_review_ln_plan() -> Tuple[str, None]`。**方向结论无误，宿主文件标错** |
| **R1-P6** §3.1 _positive_int family | **改对** | 全仓 `def _positive_int`/`parse_positive_execution_int` rg：STRICT(`-> int`) 恰 4 处（scope:9 / public_errors:167 / auto_assign:114 / feedback_support:161）✓；Optional(`-> Optional[int]`) 恰 5 处（context:28 / dispatch_execution viewmodel:33 / scope_read:21 / service:24 / persistence_errors:13）✓。`-> None`(event_data_contract:48)、`_positive_int_set`/`_positive_int_text` 正确排除。4/5 计数与签名性质全对 |
| **R2-P1** R54 五套跨文件 | **改对（路径前缀错，见硬伤①）** | 五套 def 全部实盘命中：L2 nav_publish `_PLAN_GUARD_FIELD_NAMES`:12 / L4 dashboard:8 / L3 resource_dispatch `_copy_plan_guard_fields`:64 / L1 reports_workbench:36 / L5 gantt_task_detail `_PLAN_GUARD_FIELD_ALIASES`:8 ✓ |
| **R2-P2** 三基数 16/15/12 + 别名源键 | **改对** | 逐字数键：L2=16 / L4=16（逐字≡L2）/ L3=15（**缺 plan_role_status**）/ L1=12（**缺 plan_role_status + 三阻断态 plan_identity_error/blocking_error/blocking_scope，且用别名源键 requested_role/selected_role/is_official/is_preview**）✓。三基数定性完全坐实 |
| **R2-P3** L3 调用点 :109 | **改对** | resource_dispatch `_copy_plan_guard_fields` def:64 / 调用唯一 :109（在 `_workbench_context`）✓；:95 是 collar `build_workbench_plan_context` 调用（非 guard 调用）✓ |
| **R2-P4** layer 归属 | **改对（与硬伤①自相矛盾）** | L2 nav_publish、L3 resource_dispatch 实在 `web/routes/domains/scheduler/`（2 routes）；L1 reports/L4 dashboard/L5 gantt_task_detail 在 `web/viewmodels/`（3 viewmodels）✓。**但 §3 行 195 把 L2 标进 `core/services/scheduler/`，与本条结论打架** |
| **R2-P5** E03 collar 第6调用方 | **改对** | collar def `scheduler_workbench_links.py:187`，形参 `plan_id: Any = None`:191（keyword-only）✓。生产调用方实盘 7 处：navigation_context:57/:76、dashboard_workbench_context:119、resource_dispatch:95、gantt_task_detail:78、reports_workbench:77、navigation_links:40、**analysis_links.py:24**。analysis_links:24 实盘 **未传 plan_id**（kwargs 仅 version/plan_role/date_from/date_to/query_date/period_preset/batch_id/resource_type/resource_id）✓，删形参对它安全成立 |

**R3-发现1/2（facade 删序方向）复检：改对。**
- 壳 `core/services/common/value_policies.py:3` `from core.shared.value_policies import (...)`，:6 READ_FILTER_ONLY / :7 VALUE_DATE / :8 VALUE_DATETIME / :11 WRITE_INTERNAL_ONLY ✓；__all__ :21（含 :29 WRITE_INTERNAL_ONLY）✓。
- 源 `core/shared/value_policies.py`：WRITE_INTERNAL_ONLY:9（R31 删）✓、READ_FILTER_ONLY:12 / VALUE_DATE:16 / VALUE_DATETIME:17（R30 删的三常量）✓，FieldPolicy:23/_FIELD_POLICIES:43 ✓。
- 依赖方向 = 壳 import 源 ⇒ **必须先停壳 import（R33 步1）再删源定义（R30/R31）**，否则 facade:11 残 import loud ImportError。A14 改 `R33→R31`、E06/A15 改 `R33→{R30,R31}` **方向正确且与 E05/G23 内部序自洽**。全文档已无任何残留 `R31→R33`/`R30→R31`/`R30→R33` 反向标注（rg 确认）。**E06 内 R30 三常量行号标 :12/:16/:17 与实盘逐字吻合**。

**小结：11 项采纳修订 + R3-发现1/2，全部经实盘核对成立。无一改错方向、无一漏验、无一行号凭空。**

---

## 二、本轮新发现硬伤（第1轮漏掉，且部分与第1轮修订自相矛盾）

### 硬伤①（**中-高**，与 R2-P4 自相矛盾）：§3 重灾区表 4 行 file 路径前缀错（basename 对、目录错）

实盘 `find` + 逐个 `-f` 存在性核对，§3/§1/§2 引用的 4 个物理文件**目录前缀全错**（行内行号/符号锚点经核**全对**，仅路径头错）：

| doc 标注路径（不存在） | 真实路径 | 出现处 |
|---|---|---|
| `core/services/scheduler/scheduler_navigation_publish.py` | `web/routes/domains/scheduler/scheduler_navigation_publish.py` | §3 行195、§1 G04 行19（含「navigation_publish.py」泛指） |
| `core/models/schedule_payload_contract.py` | `core/services/scheduler/run/schedule_payload_contract.py` | §3 行198、§1 G19 行34 |
| `core/data/repositories/schedule_repo.py` | `data/repositories/schedule_repo.py`（无 `core/`） | §3 行199、§1 G30 行46 |
| `core/data/repositories/part_repo.py` | `data/repositories/part_repo.py`（无 `core/`） | §3 行204、§1 G31 行47 |

补：`core/data/repositories/` 整个目录不存在（实盘只有 `data/repositories/`），故 §1 同桶的 batch_operation_repo（G35）、operator_machine_repo（G36）若也带 `core/` 前缀同病（未在 §3 表逐列，需 owner 顺手核）。

- **nav_publish 这一条最严重**：它**直接和第1轮 R2-P4 的 layer 修订打架**——§3 行218（R2-P1/P4 新写）明说 nav_publish 属「2 routes/domains/scheduler」，而 §3 行195（旧表未随 R2-P4 同步）仍把它压在 `core/services/scheduler/`。第1轮修了 prose 没回写 §3 表行 → 同一文件在同一份文档里两个目录，下游若按 §3 行195 路径 rg 会 IO error（我已复现：`No such file or directory`）。
- schedule_payload_contract / schedule_repo / part_repo 三条是**纯历史前缀债**，第1轮未触碰也未发现。
- **危害分级**：不撼拓扑、不撼承重结论、不撼批次序（行号/符号全对，按 basename+符号仍能定位）；但「按符号非行号定位」铁律要求收编者先 rg 命中文件——错路径会让确定性脚本/下游 agent rg 直接落空。属**可执行性硬伤**，非分析硬伤。建议 Layer4 出可执行批次前统一回写真实路径。

### 硬伤②（**低**）：§3.2 LB06 宿主文件归属偏移

§3.2 把 LB06 fail-CLOSED（execution-review 强制 adopted + scenario=None）挂在 `reports_page_support.py`。实盘该文件（`web/routes/reports_page_support.py`）只是消费页，fail-CLOSED 强制逻辑本体在 `reports_execution_review_context.py`（`blocked_execution_review_plan_resolution`/`execution_review_context_overrides`）+ `reports_request_support.py`（`require_execution_review_ln_plan() -> Tuple[str, None]` = 返回 adopted+None）。**方向硬门结论（fail-CLOSED、禁粘 §90 反向 fail-OPEN）完全正确**，仅认账注释要落到正确宿主文件，否则注释钉错地方=承重护栏注释悬空。

### 观察③（**非硬伤，登记**）：若干 pre-round-1 锚点松动（不在第2轮 mandate，仅提示 Layer4）

- §3 行192 `_resource_pair_payload:417`：实盘 def 在 :406，:417 是其 body `return {...}` 行（仍在该函数内，非误指）。
- §3 行191 LB01 内层行 `:369-371/:381/:471-473/:347-356`：实盘 `_build_event_payload` def 在 :455（doc 标 :455-494 函数体锚点**对**），但所列内层 raise/消毒行号与当前盘的 raise 分布（:405/:418/:440-453 等）对不齐——疑似引自略早修订。函数体级承重结论（LB01↔R17 同 `_build_event_payload`）成立，**内层裸行号需 Layer4 重 rg**。
- §4.2 L05 行335 R58「真放行走:469」：真实 nav_publish 仅 182 行，:469 不在该文件——该 fail-open 锚点指向另一生产路径文件（pre-round-1 松锚，非环、非承重）。

以上三条均属**第1轮范围之外的存量松锚**，不影响第1轮修订正确性，登记供 Layer4 收口。

---

## 三、拓扑/承重/facade/parity 不变式复核

- **拓扑仍无环**：13 条 H 边方向逐条核——`GF1→{G19,G20}`、`G04(R54)→G01(R42)`（同符号 rebase）、`G23(R33)→G17{R30,R31}`（方向修正后自洽）、`G18(R26)→{G26,G23,G39}`、`G41(R14)→G07(LB01)`、`G27(R22)→LB03`、E12/E13 承重让位——无任一汇点回指其源。第1轮新增 E28/E29 实盘均为**同文件承重毗邻 S 软边**（按符号定位、重 rg 纪律，非删除依赖），零入环。A14/E06/A15 只纠**既有 H 边方向**不增减条数。**环成员=空，DAG 成立。**
- **承重前置守住**：ROOT 层 GF1（reject_integer_float 默认 False，锚 strict_parse `_parse_finite_int`:46→`parse_required_int`:81，实盘存在且 :56 已拒分数 float、默认 False 不破存量调用方=结论成立）+ LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity 全在 source 层零入边。承重 6 文件实盘全在（含 R1-P1 新登 operation_execution_scope.py），其内 raise/sentinel 均「只补注释/绑契约」无删动作。
- **facade 晚于收敛守住**：G18(R26) 仍最晚（E07/E08/E09 硬前置 G26/G23/G39 三桶收敛），R29 复活 facade 删序前置成立。
- **parity 先于收敛守住**：G27 R22 24 键 exact parity 先落（ROOT G27p）→ 再收敛；R54 三基数（16/15/12）分组钉 parity、禁向 16 键看齐（补 plan_role_status=统一改行为违承重红线）——实盘三基数坐实，红线成立。
- **owner_pending 只标不给终态**：G09/G10/G13/G15/G18/G22/G26/G27/G29/G30/G33/G34/G39/G40/G41/G42 + §3.1 persistence_errors:13 第3副本，全为「只标不给终态」，未见任一被擅自定 KEEP/删。

---

## 四、结论

**仍有问题（非 PASS）——但均为可执行性瑕疵，不撼分析正确性。**

逐条：
1. **§3 重灾区表 4 行 file 路径前缀错**（nav_publish→应为 web/routes/domains/scheduler/；schedule_payload_contract→应为 core/services/scheduler/run/；schedule_repo/part_repo→应去掉 `core/` 前缀，`core/data/repositories/` 不存在）。其中 nav_publish 一条**与第1轮 R2-P4 layer 修订自相矛盾**（行218 说 routes，行195 说 core/services），属第1轮改 prose 漏回写 §3 表。行号/符号锚点全对，仅路径头错——但违「按符号 rg 命中文件」可执行前提，下游脚本会 rg 落空。**建议 Layer4 出批次前统一回写真实路径。**
2. **§3.2 LB06 fail-CLOSED 宿主文件归属偏移**（标 reports_page_support.py，本体实在 reports_execution_review_context.py / reports_request_support.py）。方向硬门结论正确，认账注释落点须改对，否则承重注释悬空。低危。
3. **存量松锚 3 处**（_resource_pair_payload:417 vs def:406；LB01 内层裸行号；L05 R58 :469 跨文件）——非第1轮范围，登记供 Layer4 重 rg。

**第1轮 11 项采纳修订本身：全部实盘核对成立，方向/计数/行号无一改错（仅 R1-P4 符号名差一前缀、R1-P5 宿主文件偏移两处文字瑕疵，不影响承重结论）。拓扑仍无环，承重前置/facade 晚于收敛/parity 先于收敛三不变式全部守住。** 上述硬伤均为第1轮**未引入但也未发现**的存量路径债（含一处第1轮自身 prose↔表行未同步），不影响 Layer2 分析层结论，影响 Layer4 可执行批次的 rg 命中——须在出可执行 patch 前修正路径，否则确定性脚本按 §3 路径回盘会落空。

**签收：仍有问题（逐条见上，1=中高/可执行性，2=低，3=登记项）。分析层（拓扑/承重/边）PASS，可执行性层须修 4 处路径前缀 + 1 处宿主归属后方可放行 Layer4。**
