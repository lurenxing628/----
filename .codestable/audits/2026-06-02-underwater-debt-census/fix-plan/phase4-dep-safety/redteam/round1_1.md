# 红队 Round1 · Agent#1 · 攻击角度=漏边

> 只读不改任何 .py。行号全部 rg 实盘回 HEAD c2aa7501，不信旧值。默认怀疑，挑刺不背书。
> 攻击面：漏边 / 两债同物理文件却无边 / 同收口符号无顺序敏感标 / 新债 N1N2 漏边 / 已修债(LB06/R56/R57)残留边清干净没。
> 范围：只报真问题，不凑数。每条带 file:line 或簇证据 + 修正建议。

## 结论
发现 **6 个真问题**（4 个硬漏边/漏副本 + 2 个标注精度缺口），无凑数项。
最重的是 **P1（R09 收口家与 LB01「最终底」承重同住一文件却无边）** 和 **P2（R09 收编面被严重低估：synthesis 只认 2 旧副本，实盘 Optional-family 还有第 3 份未收口副本 + service.py A 副本是 4 调用点不是 1）**。

---

## 逐条发现

### P1【硬漏边 · 同物理文件承重】R09 收口家 operation_execution_scope.py 同住一个 LB01「配套最终底」禁区，全图零边
**证据**：
- R09 的收口点 `parse_positive_execution_int` 实盘在 `core/models/operation_execution_scope.py:9`（rg 命中 :9 def / :11,:17,:20,:27 raise / :102 __all__）。
- **同一文件 :36** 是 `validate_current_official_execution_scope`（:44/:47/:50 三 raise），而 EXEC-FACT 簇 §D「承重前置」白纸黑字把它列为 **LB01 的「配套最终底（簇外但相关，禁删其 raise）：operation_execution_scope.py validate_current_official_execution_scope 三 raise」**。
- 即：R09 收编动作要往 `:9 parse_positive_execution_int` 收拢/对 parity，而它和一条 LB01 承重最终底坐在**同一个 461-byte 小文件**里（:9 vs :36，相距 27 行，:77-79 调用点把两者夹在一起）。
**问题**：synthesis §2.1/§3 既没把这条「R09 收口家 ↔ LB01 最终底 同文件」列入跨簇边，也没把 `operation_execution_scope.py` 列入 §3 重灾区（19 文件清单里没有它）。R09 收编时若顺手「整理」该文件（删空行/调 import/移函数）会漂移 :36-50 承重 raise 的锚点；EXEC-FACT §D 只说「禁删其 raise」但没把这条同文件邻接回连到 R09/G22。
**修正建议**：补一条 **R09(G22) → LB01 最终底(operation_execution_scope.py:36-50)** 的「同文件承重毗邻」软边（S，按符号非行号定位，R09 收编时禁碰 :36-50），并把 `operation_execution_scope.py` 补进 §3 重灾区清单（承重点 +1，实际是 6 承重文件不是 5）。

### P2【硬漏副本 · 同收口符号族被低估】R09「2 旧内联副本」口径与实盘不符：Optional-family 至少 3 份未收口，且 service A 副本是 4 个调用点不是 1
**证据**（rg 全仓 `_positive_int` def 分类）：
- corrections A + synthesis G22/§5.1 一致声称「剩 2 个 baseline 旧内联副本未收编」＝ viewmodel:33 + service.py:24。
- 实盘 `-> Optional[int]`（宽松归 None/可 `or 0`）的 inline 副本有 **至少 3 份未收口**：
  - `web/viewmodels/scheduler_resource_dispatch_execution.py:33`（B 副本，已认）
  - `core/services/scheduler/resource_dispatch_execution_service.py:24`（A 副本，已认）
  - **`core/services/scheduler/run/schedule_persistence_errors.py:13`**（**未认**：`def _positive_int(value)->Optional[int]`，**不** import/wrap `parse_positive_execution_int`，调用点 :24/:56(`or 0`)/:77——与 A/B 同范式的第 3 份裸内联）。
- 另外 **service.py 的 A 副本不是「:24 一处」**：`_positive_int` 在该文件有 **4 个消费点** :169 / :180 / :181（外加 def:24），且 :189 `_context_is_current_official` 是依赖判定的活护栏。synthesis G22/PARSE §0 只写「service.py:24」，会让收编者以为改 def 一处即可，漏掉 3 个调用点的 parity（5.9→5 vs 5.9→None 的语义放宽点正是在调用点 `==int(...)` 比较处，:180-181）。
**问题**：R09 收编面的「分两路 parity」结论建立在「2 副本」基数上；若实际是 3 份 Optional 副本（且 service 副本 4 调用点），收编/parity 漏一份 = 同符号语义半截漂移（部分 5.9→None 部分 5.9→5），正是失忆债复发。
**修正建议**：① 由 dossier owner 复核 `schedule_persistence_errors.py:13` 究竟是 R09 同族第 3 副本还是独立 run/ 包解析器——若同族，G22 收编面 2→3 份、parity 分路口径要扩；若独立，须在 registry 标注「同符号 `_positive_int` 但非 R09 范围」防后续误并。② PARSE §0 把 A 副本由「service.py:24」改为「service.py:24 def + 169/180/181 三调用点」，明确 parity 钉的是调用点比较语义。

### P3【硬漏边 · 新债 N1 与 R09 C 路同住一文件，零边】N1 的「我是故意的」注释落点 = R09 C 路收口副本所在文件，synthesis 只连 N1↔R08/R54/R58，漏 N1↔R09
**证据**：
- N1 在 `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:129-130`（`_identity_allows_query_membership_check` / `can_write_feedback`，rg 命中）。
- **同一文件 :28-30** 正是 corrections A 说的「C 路已收口」副本：`def _positive_int(value)->Optional[int]: parsed=parse_positive_execution_int(value,"execution_context")`（:28 def / :30 wrap 收口点），调用点 :96/:97/:107/:271/:272。
- 即：R09 的「C 路严格 5.9→None」parity **基线就锚在 N1 的本体文件里**。R09 收编 A/B 要对照的「C 路严格语义」实证 = context.py:28-30；而 N1 补注释/绑 parity 也在同文件 :129-130。
**问题**：synthesis E26 写「N1 → G22(R08) / G04(R54/R58)」，把 N1 连到 R08（同 viewmodel 死分支）、R54/R58（同护栏概念），却**没连 N1 ↔ R09**——尽管 R09 的 C 路 parity 实证就在 N1 文件里。两件事同期改同文件（N1 注释 :129-130 + 若 R09 决定「C 路一并复核」要读 :28-30），存在行号互漂 + 概念同源（can_write_feedback 与 _positive_int 都服务于同一查询成员闸）的真毗邻。
**修正建议**：补 **N1 ↔ R09(C 路 context.py:28-30)** 同文件毗邻边（S，行号联动，谁后做谁重 rg），并在 G22 的 parity 分路里明确「C 路严格语义的实证锚点 = context.py:28-30，与 N1 注释同文件，收编 A/B 前先在此文件钉死 C 路 parity」。

### P4【硬漏边 · 新债 N2 物理文件被多债共载，N2 仅连 G04/G22 邻接，漏与 event 文件实际改动方的边】
**证据**：
- N2 在 `core/models/operation_execution_event.py:156-163`（`_event_id_for_revision` 末位 `return 0`，rg 命中 :156 def / :161 `if index<total` / :163 return 0 / :179 另一 return 0 / :205 previous_event_id=0 / :246 调用点）。
- 该文件**被多处生产消费**（rg import 命中）：`feedback_service.py`（LB01/R17/R20 宿主）、`operation_execution_feedback_actions.py`、`gantt_adjustment_publish_service.py`、`scheduler_resource_dispatch_execution.py`（R08/R09 B 副本宿主）、`operation_execution_event_data_contract.py` 等。
**问题**：synthesis E27 把 N2 标为「↔ G04 / G22 邻接」「本簇不触发结构动作」。但 N2 的 `return 0` sentinel 进 `previous_event_id`（:205/:218/:246）下游 revision 拼接，而 **R08/R09 的 B 副本宿主文件 import 了 operation_execution_event**（viewmodel:行首 import 命中）。N2 与 G22（R08/R09）不只是「邻接」，是**下游数据契约同源**（event id 拼接链）。更要紧：synthesis 没标 N2 与 LB01 宿主 feedback_service.py 的关系——feedback_service 也 import operation_execution_event，N2 的 sentinel 语义若被「顺手统一」会穿透写侧消毒层。
**修正建议**：把 E27 由「N2↔G04/G22 邻接（不触发结构动作）」升精为：标注 N2 的下游消费面（previous_event_id 拼接链：:205/:218/:246），并补一条 **N2 → LB01 宿主(feedback_service.py) / G22(viewmodel) 的「event-id 契约同源」弱边**，提醒「禁删 `if index<total: raise` 之外，也禁动 :179/:205 的 0 初值语义」。当前只钉了 :161 的 raise，漏了 :179/:205 两个同语义 sentinel 点。

### P5【标注精度 · 已修债 R56/R57/LB06 残留边「清干净」结论可信，但有一处反向风险未钉】
**证据**：
- 三处 fixed 残留边（R42↔R56/R57、R42↔LB06）在 NAV-PLANID §C/§D + EXEC-REVIEW §C 均已退化为「禁区行约束」，逐条核对：R56=navigation_context.py:79（rg 待复核行号）、LB06=reports_page_support.py execution-review 强制分支、R57=已收敛无残留。删边动作本身**干净**，没有发现残留活边漏删。
**问题**（这是反向风险，非漏边）：corrections D + 三簇 §E 反复强调「LB03/LB06 勿粘 §90 LB-B4 反向 fail-OPEN 文案——现盘已 fail-CLOSED」。这说明**历史上确实出现过把 fail-CLOSED 误描述成 fail-OPEN 的污染**（与 memory「审计自污染」一致）。synthesis §5.3 只在文字里提了一句「勿粘反向文案」，**没有在 §3 禁区表或 §2.1 边表里给 R42/R66 的认账注释动作设一条「文案方向校验」硬门**。R42 删 plan_id 时若顺手补 R56/LB06 认账注释，极易粘错方向（把现盘 fail-CLOSED 写成 fail-OPEN），而这正好是承重护栏方向反转——比漏边更危险。
**修正建议**：在 §3 重灾区把 `navigation_context.py:79`(R56) / `reports_page_support.py`(LB06) 的禁区行旁补一条**显式方向断言**：「认账注释必须写 fail-CLOSED（plan_role 非法→强制 ROLE_ADOPTED / execution-review→强制 adopted+scenario=None），严禁粘 §90 LB-B4 的 fail-OPEN 旧文案」，并把它从「文字提醒」升为禁区表一行（与 P0 同级，因方向反转=承重击穿）。

### P6【标注精度 · R09 禁区 STRICT-family 副本与 Optional-family 收口候选未在边表显式区分，误删风险只在簇内文字】
**证据**（rg 全仓 `def _positive_int` 分类）：
- **STRICT-raise family**（`-> int`，坏值直接 raise，是 R09 **禁区**「别误删当重复」）：`operation_execution_feedback_support.py:161`、`scheduler_public_errors.py:167`、`run/auto_assign_resource_errors.py:114`、收口点 `operation_execution_scope.py:9` 本身。
- **Optional-None family**（`-> Optional[int]`，R09 收口/收编候选）：viewmodel:33、service:24、context.py:28(C 路已收口)、`operation_execution_scope_read.py:21`(已收口 C 族)、`schedule_persistence_errors.py:13`(见 P2 未认)。
**问题**：PARSE §B/§D 把 feedback_support:161 / public_errors:167 列为「R09 禁区毗邻」是对的，但 synthesis 主档 §2.1 边表和 §3 重灾区**没有把「同名 `_positive_int` 跨两个语义 family（raise vs None）」这个最高误删风险显性化**。收编者全仓 grep `def _positive_int` 会一次撞到 7+ 处同名异义函数，synthesis 没给一张「哪几份是 raise 禁碰 / 哪几份是 None 待收 / 哪几份已收口」的对照表，纯靠各簇分散文字，极易误删 STRICT 版当「重复副本」——这恰是灵魂线（坏值 raise）被静默削弱的入口。
**修正建议**：在 §3 或新增小节给 R09 配一张 **`_positive_int` 同符号 family 对照表**（STRICT-raise 禁区 4 处 vs Optional-None 收口候选/已收口 5 处），标顺序敏感=「同名异义，收编只动 Optional family，STRICT family 一字不碰」。这是同收口符号但语义分叉、却未标顺序敏感的典型漏标。

---

## 自证（rg 实盘锚点，2026-06-05 / HEAD c2aa7501）
- operation_execution_scope.py: `:9 parse_positive_execution_int` + `:36 validate_current_official_execution_scope`(:44/47/50 raise) 同文件 → P1
- _positive_int defs 分类：viewmodel:33 / service:24(+169/180/181 调用) / context.py:28(C路) / scope_read.py:21(已收口) / schedule_persistence_errors.py:13(未认) / feedback_support.py:161(STRICT) / public_errors.py:167(STRICT) / auto_assign_resource_errors.py:114(STRICT) → P2/P6
- N1 context.py:129-130 与 C 路 _positive_int:28-30 同文件 → P3
- N2 event.py:156-163，多生产消费(feedback_service/viewmodel/actions/gantt_adjustment import 命中)，:179/:205 同语义 0 sentinel → P4
- R20 viewmodel 导入的是 `core.models.operation_execution_labels`(:10) ≠ R20 删的 `core.services.scheduler.operation_execution_labels` → 确认 synthesis D07/D08 删 R20↔R08/R09 假边**正确**，无误删（此项核对通过，非问题）
