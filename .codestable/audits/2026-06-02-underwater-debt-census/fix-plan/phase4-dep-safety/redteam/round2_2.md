# 红队第2轮 · 2号 复检报告（只读不改）

> 输入：_interference_rebuilt.md（含红队第1轮修订小节）。回盘 HEAD c2aa7501（实测一致）。行号全部 rg/sed 实盘回盘，不信文档旧值。
> 复检维度：1)第1轮采纳修订是否真改对 2)有无新引入不一致 3)拓扑是否仍无环 4)承重前置/facade晚于收敛/parity先于收敛是否仍守 5)第1轮漏掉的硬伤。
> 铁律：只读不改任何 .py；承重只补注释/绑契约 parity 不删/统一/透传；灵魂线不新增兜底；P5 收口到已存在点；分层 0 违规；owner_pending 只标不给终态。

## A. 第1轮采纳 11 项修订逐条复检（全部 rg 实盘回盘）

| 红队条 | 文档断言 | 实盘回盘 | 判定 |
|---|---|---|---|
| **R1-P1** | scope.py:9 收口点 + :36 validate(三 raise :44/47/50) 同住 3499B 小文件，:77-79 调用点夹两者 | `parse_positive_execution_int`:9（raise :11/:17/:20），`validate_current_official_execution_scope`:36（raise :44/:47/:50），`wc -c`=**3499**，:77-79 三行调 parse_positive_execution_int（schedule_version/schedule_id/op_id） | **真改对** 逐字命中 |
| **R1-P2** | schedule_persistence_errors.py:13 第3份裸 `-> Optional[int]`（`int(value or 0)` 不 wrap 收口点），调用点 :24/:56/:77 | `_positive_int`:13 `-> Optional[int]`，:15 `int(value or 0)`（确实未 wrap parse_positive_execution_int），调用点 :24/:56（`or 0`）/:77 全中 | **真改对**。owner 复核标注（同族 vs 独立 run/解析器）合理保留 |
| **R1-P3** | N1(:129-130) 与 C 路收口副本(:28-30 wrap 收口点) 同住 context.py，C 路调用点 :96/97/107/258/271/272 | 同文件：`_positive_int`:28（:30 调 parse_positive_execution_int=wrap 收口点），`_identity_allows_query_membership_check`:129/:130 `return bool(identity.get("can_write_feedback"))`；调用点 :96/:97/:107/:258/:271/:272 **逐个命中** | **真改对** |
| **R1-P4** | event.py 除 :161 raise/:163 return 0 外，:179 return 0 + :205 previous_event_id=0 同 sentinel；多处 import | `_event_id_for_revision`:156，`if index < total:`:161→`raise`:162，`return 0`:163；`_suggest_reschedule_field` :179 `return 0`（:182 有 raise 守 0/1）；`previous_event_id = 0`:205，下游 :218/:246 拼接；importer 实测 feedback_service/viewmodel/actions/gantt_adjustment_publish_service 等≥8 处 | **真改对**。E27「禁删 :161/:162」中 :161=if、:162=raise，表述准确 |
| **R1-P5** | navigation_context.py:79 fail-CLOSED（非法 role→ROLE_ADOPTED） | `web/navigation_context.py:79` = `plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`，:7 import VALID_PLAN_ROLES、:23 ROLE_ADOPTED="adopted"，确为 **fail-CLOSED** | **真改对**。方向硬门成立 |
| **R1-P6** | `def _positive_int`/`parse_positive_execution_int` STRICT(-> int raise) 4 处 vs Optional(-> None) 5 处 | STRICT 4：scope.py:9 / public_errors:167 / feedback_support:161 / auto_assign:114（全 `-> int`）；Optional 5：dispatch_execution:33 / service:24 / context:28 / scope_read:21 / **persistence:13**（全 `-> Optional[int]`） | **真改对** 9 处全命中，family 分类零误 |
| **R2-P1** | R54 五套手维面跨 5 文件，G04 物理只锁 1 套 | L2 nav_publish `_PLAN_GUARD_FIELD_NAMES`:12 / L4 dashboard:8 / L3 resource_dispatch `_copy_plan_guard_fields`:64 / L1 reports:36 / L5 gantt_task_detail `_PLAN_GUARD_FIELD_ALIASES`:8 **五套全在位** | **真改对** |
| **R2-P2** | 3 种字段基数：L2/L4=16键、L3=15缺plan_role_status、L1=12缺三阻断态+别名源键 | **逐字数**：L2=16、L4=16(与L2逐字相同)、L3=15(loop 元组无 plan_role_status，:267 的 plan_role_status 属 internal_filters 不在元组)、L1=12(mappings 无 plan_role_status+无 plan_identity_error/blocking_error/blocking_scope，且用别名源键 requested_role/selected_role/is_official/is_preview)、L5=别名元组(含 plan_role_status:11) | **真改对** 三基数+别名源键全部逐字坐实 |
| **R2-P3** | L3 guard 调用唯一 :109，:95 是 collar 调用 | resource_dispatch.py：`_copy_plan_guard_fields` def:64、唯一 guard 调用 :109、:267 是 internal_filters 噪声非元组成员 | **真改对** |
| **R2-P4** | R54 5 套 = 3 viewmodels + 2 routes，非「都在 routes」 | dashboard/reports/gantt_task_detail 在 `web/viewmodels/`，nav_publish/resource_dispatch 在 `web/routes/domains/scheduler/` | **真改对** |
| **R2-P5** | analysis_links.py:24 调 collar 未传 plan_id，对 R42 删形参安全 | `scheduler_analysis_links.py` 内 `_plan_role_links` 调 `build_workbench_plan_context(version=,plan_role=,date_from=,date_to=,query_date=,period_preset=,...)` **确无 plan_id=**，对删形参安全 | **真改对**（见 D2 一处叫法瑕疵） |
| **R3-发现1 (A14)** | A14 标 R31→R33 与 E05 R33→R31 自相矛盾，改 R33→R31 | 壳 `core/services/common/value_policies.py`:3 `from core.shared.value_policies import (...)`，依赖方向=壳 import 源；故须先删壳 import(R33) 后删源(R31)。改后 A14=R33→R31 与 E05 一致 | **真改对** 方向修正成立 |
| **R3-发现2 (E06/A15)** | R30/R31 同 shared 侧删彼此无序，真前置=壳 R33 先停 import；改 R33→{R30,R31} | 实盘壳单 import 块 :3-19：READ_FILTER_ONLY=:6 / VALUE_DATE=:7 / VALUE_DATETIME=:8（即「:6-8 三常量」）、WRITE_INTERNAL_ONLY=:11；源 WRITE_INTERNAL_ONLY=:9。R30(删源三常量)/R31(删源:9) 对等无序，硬前置确为壳 R33 步1 | **真改对** |

**A 节小结：第1轮采纳的 11 条修订 + 2 条精度修订（A14/A15）逐条 rg 回盘，全部真改对，无一处行号/语义漂移。承重(R09 收口点/N1/N2/LB01 最终底)的「补注释+绑契约/parity、禁删禁统一」处置全部守住；灵魂线 raise 锚点（scope:11/17/20/44/47/50、event:162/182）实盘在位未削弱。**

## B. 新引入不一致 / 内部矛盾扫描（针对第1轮改动面）

- **E27 行号自洽**：E27 文末「:161/:162」与 §5.2 N2 行「:161 raise」措辞略不同——实盘 if=:161、raise=:162，E27 的「:161/:162」更准，§5.2 单写「:161 raise」是把 if 行当 raise 行的**口径简化**，不构成矛盾（同指一处 `if index<total: raise`），属可接受的概述。**非硬伤**。
- **A14/E05 方向一致性**：修订后 A14(§4.2)=R33→R31、E05(§2.1)=R33→R31、E06/A15=R33→{R30,R31}，三处方向**已自洽**，原「R31→R33 vs R33→R31」自相矛盾已消除。复算无新矛盾。
- **承重文件计数一致性**：§3 表末「19→24」「5→6」、§返回摘要「重灾区 19→24、承重 5→6」、§5.5「6 承重文件」三处计数一致。operation_execution_scope.py 新登为第 6 承重文件，与 §3.1 family 表 STRICT 本体一致。**自洽**。
- **边数一致性**：§4.1「27→29」、§4.3「+17+2=19 / 跨簇 29 条(H13/S14/P2)」、§返回摘要「跨簇 29 条(H13/S14/P2)」三处一致；H 边「方向修正不增减条数=仍 13」三处一致。**自洽**。
- **R54 delegate 面计数**：§1 G04「五套」、§3「5 套」、§5.1「+1=5 套（原 3/4→5）」一致。**自洽**。

**B 节小结：第1轮改动未引入新的数字打架 / 方向自相矛盾 / 计数漂移。原有的唯一一处方向自相矛盾（A14↔E05）已被 R3-发现1 修平。**

## C. 拓扑无环 + 三大承重约束复检

- **无环复核**：第1轮新增 2 条边 E28(R09↔LB01 最终底,同文件)、E29(N1↔R09 C 路,同文件) 实盘均为**同文件承重毗邻**关系，文档定性为 **S 软边（按符号定位+重 rg，非删除依赖）**，零入 H 环；方向修正 A14/E06/A15 只纠既有 H 边指向不增边。对 13 条 H 边重做心算 DFS：source 层(GF1/LB01/LB02/LB05/LB08/LB07/LB03/R05-step1/R22-parity) 零入边；汇点 {G19,G20,G01,G17,G26,G23,G39,G07,G15} 无一回指 source。**仍无环，DAG 成立，环成员=空。** 与文档 §2.3 结论一致。
- **承重前置守住**：ROOT 层全为「承重注释+parity/默认值门」纯增量零结构（GF1 默认 False、LB01/02/05/07/08/03 注释、R05-step1、R22-parity），门控其下游删改。E28/E29 把 R09 收编与 LB01 最终底/N1 钉在「同文件按符号定位、禁碰 :36-50 raise」——**承重让位先于动手**守住。
- **facade 晚于收敛守住**：E07/E08/E09（R26→{R29,R33,R52}）+ E05/E06/A14/A15（R33 壳 import 先停 → R30/R31 源删）方向实盘坐实（壳 import 源），G18(R26) 仍排 Batch-D 最晚。**守住。**
- **parity 先于收敛守住**：E12(R22 24键 exact parity 先 → 收敛 build_plan_identity)、GF1(reject_integer_float 默认 False+parity 先 → R04/R59 收口)、G33a(R05 步1扩collar+步2 五条parity 先 → 步3 收敛)、G15a(LB07 注释+扩spec_sync parity 先 → R47/R71)。R54 三基数(16/15/12)分组 parity「禁向 16 键看齐/禁补 plan_role_status」红线建在实测三基数图上。**守住。**

## D. 第1轮漏掉的硬伤（本轮新发现）

> 以下为第1轮三份红队 + 第1轮裁定均未捕获、本轮 rg 实测发现的问题。按危险度排序。

**D1〔中·路径前缀错误，4 处，会误导按路径定位的下游工具/agent〕** §3 重灾区表 4 个物理文件路径前缀写错（函数级行号锚点正确，但带错前缀的整路径在仓里不存在）：
| §3 文档路径（错） | 实盘真路径 |
|---|---|
| `core/services/scheduler/scheduler_navigation_publish.py`（行195 R58/R54/R44 行） | `web/routes/domains/scheduler/scheduler_navigation_publish.py` |
| `core/models/schedule_payload_contract.py`（行198 R01/R04 行） | `core/services/scheduler/run/schedule_payload_contract.py` |
| `core/data/repositories/schedule_repo.py`（行199 R34/R35 行） | `data/repositories/schedule_repo.py`（无 core/ 前缀） |
| `core/data/repositories/part_repo.py`（行204 R38/R39 行） | `data/repositories/part_repo.py`（无 core/ 前缀） |
说明：这 4 行是 §3 表的**既有行（非第1轮新增）**，第1轮补登的 5 个新文件路径（operation_execution_scope.py + R54 缺席四文件）实测路径**全部正确**。故属第1轮「该顺手核但漏核」的存量瑕疵。危险度中：函数符号名+行号准确，按符号 grep 仍可定位；但若下游照搬路径打开文件会 No such file。**建议正文修 4 处前缀（纯文档侧，不撼批次/拓扑/承重结论）。**

**D2〔低·符号叫法不一致，不影响安全〕** collar 真符号是 `def build_workbench_plan_context`（workbench_links:187），多数调用方以别名 `n` import（`from ... import ... n`），仅 navigation_context/analysis_links 用全名。§1 G01/E03 以全名「build_workbench_plan_context co-change」描述同符号 co-change——语义正确（同一符号），但「co-change MUST 同批」落地时按符号 grep 须同时覆盖别名 `n(` 调用点，否则 grep 全名会漏掉 dashboard/reports/gantt_task_detail/navigation_links 的 `n(` 调用。**建议在 §3 workbench_links 行补一句「collar 别名 `n`，grep co-change 须同查 `build_workbench_plan_context` 与 `n(`」。** 非硬伤，但漏了会导致 R42 删形参时漏改别名调用方（不过这些调用方都不传 plan_id，TypeError 风险低）。

**D3〔低·锚点行号小漂，存量非第1轮引入〕** §3 行198 R01「__all__:414-415」实盘 `__all__` 在 `core/services/scheduler/run/schedule_payload_contract.py`:**410-417**（块内列 count_actionable_schedule_rows/has_actionable_schedule_rows 等，非 :414-415 两行）。R01 删 __all__ 项时按符号删即可，行号小漂不致命。存量瑕疵，**建议顺手订正为 :410-417 块**。

**说明：GF1「strict_parse:46 经:81 透传」经核为正确**——`strict_parse` 指模块 `core/shared/strict_parse.py`（`core/services/common/strict_parse.py` 是其薄壳 re-export）；实盘 `_parse_finite_int`:46（现 `float()`→`int()` 带 1e-9 容差，故 3.0 今被接受）+ `parse_required_int`:81 透传。reject_integer_float 全仓不存在=符合「非债/待加新参」定性。**默认 False 理由（默认 True 炸现有 parse_required_int 调用方）成立。非硬伤。**

## 签收结论

**仍有问题（均为文档侧瑕疵，不撼批次/拓扑/承重/灵魂线结论；无 P0/P1 级硬伤）：**

1. 〔中〕§3 重灾区表 4 处物理文件路径前缀错（D1）：navigation_publish 应在 `web/routes/domains/scheduler/`、schedule_payload_contract 应在 `core/services/scheduler/run/`、schedule_repo/part_repo 应去掉 `core/` 前缀。函数符号+行号正确，仅整路径在仓里不存在。建议修 4 行前缀。
2. 〔低〕collar 符号别名 `n` 未在 co-change grep 纪律里点明（D2），R42 删形参按全名 grep 会漏别名调用方。建议补一句。
3. 〔低〕R01 `__all__` 锚点 :414-415 实为 :410-417 块（D3），存量小漂，按符号删不致命。

**核心结论：第1轮采纳的 11 项修订 + A14/A15 方向精修，逐条 rg 回盘 HEAD c2aa7501 全部真改对，行号/语义零漂移；承重(R09 收口点已存在/N1/N2/LB01 最终底/LB02/05/07/08/03)「只补注释+绑契约 parity、禁删禁统一禁透传」全程守住；灵魂线 raise 锚点实盘在位未削弱；R54 三基数(16/15/12)+别名源键逐字坐实；P5 收口到已存在点(scope.py:9)未新建模块；分层 0 违规；owner_pending 只标不给终态。拓扑仍无环（E28/E29 均 S 软边，A14/E06/A15 只纠方向不增边，环成员=空）。承重前置/facade晚于收敛/parity先于收敛三道约束全部仍守。** 上述 3 条为纯文档侧路径/叫法/行号瑕疵，修订后即可签收 PASS。

签收：**仍有问题（D1 中 / D2 低 / D3 低，均文档侧，无承重/拓扑/灵魂线级硬伤）。**
