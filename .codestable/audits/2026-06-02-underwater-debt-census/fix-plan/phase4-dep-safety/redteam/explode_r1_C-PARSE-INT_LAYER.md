# 逐簇爆炸对抗 r1 · C-PARSE-INT · 主透镜【分层导入环+迁移耦合】

> skeptic 第1轮，只读不改，默认怀疑。行号 2026-06-05 rg 回盘实证。
> 成员债 R01 / R04 / R09 / R28 / R59 / R08。
> 主透镜聚焦：LB04 越层环（本簇不在两端，下方核对）；R19 repo→service（本簇不在）；facade 删/收口与 v18·v19 DB CHECK 耦合（本簇不在）。
> 实测结论：**本簇 6 成员零跨层违规、零导入环、零迁移(DB CHECK)耦合**——主透镜在本簇空打；真爆点在 Q1/Q5/Q6（承重静默放宽 + 收口非等价 + 测试序）。

## 0) 主透镜专项核对（Q2 分层 / Q3 迁移）——本簇全绿

| 透镜 | 核对 | 结论 |
|---|---|---|
| Q2 越层 core.models→core.services | R09 sink `parse_positive_execution_int` 在 `core/models/operation_execution_scope.py:9`，该文件 import 仅 `dataclasses/typing/core.models.schedule_plan_role:6`，**零回指 services/web** | A 副本(core.services)/B 副本(web)收口到它=`services→models`/`web→models` 下行合法，**无环** |
| Q2 越层 repo→service | R04 收口点 `core/shared/strict_parse.py`（仅 import `core.infrastructure.errors`+stdlib）；R28 收口点 `core/shared/number_utils.py`（scheduler 本地 `number_utils.py:6` 已 re-export）；R59 收口点同 strict_parse | 全是 `services/report→shared` 下行，**0 越层 0 环** |
| Q3 迁移/DB CHECK 耦合 | 本簇全是「内存数值解析助手收口/删死码」，**不碰 schema / v18·v19 CHECK / effective_plan_role / source_table** | **零迁移耦合**，改码不触发启动探针 |

主透镜的越层环/facade/DB CHECK 三爆点在本簇**不存在**——本簇非 LB04/R19/facade 所在。守门正常。

## 1) 逐债判定

### 🔴 R09（B05/P5/owner_pending=true）— 收编静默放宽，按计划「直接收口 A/B」会写脏 op_id/错配现场记录
**灾难链（已 rg 实证）**：sink `parse_positive_execution_int`(scope.py:9) 是 **STRICT**——`:10 isinstance bool→raise`、`:16 text.isdigit()` 对 `'5.9'`/`'3.0'` raise、float 入参非 int 非 digit-str→raise；C 副本(context.py:28)已 wrap 它 catch ValueError→None，故 C 对 `5.9→None`/`True→None`。
而 **A 副本(service.py:24) 与 B 副本(viewmodel:33) 实测逐字节同体 = `int(value)`** → `5.9→5`、`3.0→3`、`True→1`（已读两 body 确认）。
→ 若按「字节对齐 A/B 的 sink」收 A/B：A/B 零漂移✓；但若反过来把 A/B 收到现 STRICT sink，则 A/B 对 float/bool 由「截断接受」变 None=**静默收紧**；若新建一个「对齐 A/B 的宽松 sink」再让 C 也指它，则 C 由 None 放宽成截断/1=**静默放宽**，`5.9` 当 op_id=5 喂 `_row_matches_feedback_target`(context.py:96/97/271/272)→误命中相邻行→**现场记录静默写到错任务上，无报错**。
→ **两路 parity 不可合并**：C 严格 vs A/B 宽松是真契约差异（已实证 sink 体）。
**修正**：(1) owner_pending=true，**本轮只标不给终态**；(2) 收编只动 Optional 副本，STRICT 4 处（scope:9 / public_errors:167 / auto_assign:114 / feedback_support:161，已逐一 rg 命中 `-> int` loud raise）一字不碰；(3) 必先写两路 parity（test_parity_AB 零漂移 + test_parity_C_float_bool 钉 5.9/3.0/True 分歧），owner 裁「保 C 严格 None」还是「放宽到 A/B 截断」后才能定 sink；(4) `parse_optional_positive_int` 全仓=0 实证，**新建前提作废**，禁新建（铁律5：收口点已存在）；(5) 强串行排 B01(R07/R08)之后重 rg 回盘行号。

### 🔴 R04（B05/P5）— ValidationError 逃逸 6 处 except，漏一处=low 踩 P0 整链崩
**灾难链（已 rg 实证）**：`_strict_positive_int`(payload_contract:50) `:51` 显式拒 None/bool/float→raise **ValueError**；6 调用点 `:72/:149/:198/:308/:324/:372`，对应 6 except 全是 `(TypeError, ValueError)`（`:73/:150/:199/:309/:325/:373` 逐一命中）。`ValidationError(AppError)`(errors.py:97)**非 ValueError 子类**（AppError(Exception):63）。
→ 收口 A 委托 `parse_required_int`(strict_parse:81，抛 ValidationError) 后**漏改任一 except** = 脏 op_id 由「静默 skip」变「ValidationError 一路上抛」，经 `count_actionable_schedule_rows` 链使本应正常的排程持久化整体 abort。
**修正**：(1) 6 except 同 PR 加捕 `ValidationError`（payload_contract:7 已 import，零新增 import）；(2) **F1 前置且必默认 False**——实证 `reject_integer_float` 全仓=0 未落地，且 `parse_required_int` 被 core/algorithms 大量调用（sgs_graph.py:13/28/155/156、auto_assign.py:395、ordering.py:117/118 均命中），默认 True 会把它们的 `3.0` 由接受变 raise=排程/配置静默回归；(3) F1 自带 parity（True→3.0 raise / False→3.0 接受）先绿；(4) 哨兵 B(auto_assign:114→0)/C(persistence_errors:13→None)是错误处理路径降级，**只补注释+parity 钉 →0/→None，严禁改 raise**（灵魂线）。

### 🟡 R59（B05/P5）— 不等 F1 裸收口必撞续命测试（显性红，非静默；可控）
**条件**：实证续命测试 `regression_web_silent_fallback_contract.py:241/244/247/250` 要求 `'1.5'/'-1'/'1.0'/1.0` 全 raise；私有正则 `_INT_TEXT_PATTERN=^[+-]?\d+$`(:9) 对 `.` 不匹配故 `'1.0'`/`1.0` raise。现 `parse_required_int` 接受 `'1.0'/1.0→1`（:50 float()+ :56 1e-9 容差）。
→ F1 前裸收口 = `'1.0'`/`1.0` 由 raise 变 1，直撞 :247/:250 = **CI 显性红（良性，会被拦）**。更危险：误删续命测试或漏传 reject_integer_float=True → 导出阈值静默接受 float 污染。
**条件放行**：F1 落地+默认 False 后，收口委托 `reject_integer_float=True`；删 `_parse_plain_report_int`(:54-70)/`_INT_TEXT_PATTERN`(:9) 时**必保留 blank 短路**（现 :62-63 blank→blank_default(0)，strict_parse 对 blank raise，漏迁=空值导出由降级0变报错中断）。F1 前只能停「注释+parity」临时态。owner_pending=false 可给终态但执行须等 F1。

### 🟡 R28（B05/P4）— fitness 白名单按「名」命中，方案 b 留名则白名单不能退（退=CI 红）
**条件**：实证 `LOCAL_PARSE_HELPER_NAMES` 含字符串 `"_safe_float"`(:64)，白名单 `:77`=`batch_service.py:_safe_float`。若走推荐方案 b（保 `_safe_float` 名、体改 `return parse_finite_float(...)`），探测器按**名**命中则白名单条目须**保留**而非退；走方案 a（删函数）才退。盲目退条目 → `:254 stale_entries` 红。
→ 其余安全：收口点 `parse_finite_float`(number_utils:14/23)已存在、scheduler 本地:6 已 re-export，**不改 number_utils 一行**；services→shared 下行合法 0 越层；上游 ext_days 已 `parse_optional_float` 严格校验（batch_operation:92/part_operation:75）故 except 分支近不可达、爆炸半径极小。
**条件放行**：动手第一步先跑 `pytest -k allowlist` 定退/留；必 `allow_none=True`（否则空 ext_days 正常批次炸）；禁越界动消费点 `setup/unit_hours=float(...or 0.0)` 工时兜底。

### 🟡 R08（B01/P6/owner_pending=true）— 删死分支须保 feedback_write_enabled 参数，误删参=填写按钮门禁塌缩静默放开误填
**条件**：实证死分支①`:227-228`、死分支②`:367-368`、死常量`:25` 活体在；(T,F) 不可达依赖 service `:127≡:130`（同 key `can_write_feedback` 同 bool()，实证）。但参数被活路径 `:234 fill_enabled=bool(can_write and feedback_write_enabled and ...)` 真消费。
→ 候选A 删死分支删常量**必须保留参数**；误把参数一起删 → :234 门禁塌成只看 can_write → 已完工状态也亮「填写实际」按钮 → **静默放开误填现场记录**（最大爆点）。
**条件放行**：owner_pending=true **本轮只标不给终态**——owner 须裁 `feedback_write_enabled` 是否「现场记录保护总开关」预埋（commit 65870e47 lane）；删前先在测试钉 `:127≡:130` 同源不变式（把 (T,F) 不可达从偶然变契约）；R08(B01)→R09(B05)同文件串行；**本文件当前工作区有未提交 build_task_card 重构 diff（`git status` M）抬移行号，须等在途改动落定再动**。

### 🟢 R01（B14/P6）— 纯删死码，0 生产消费、0 新增 import、误删均响亮（ImportError/SyntaxError/SP05红）
死簇 `_iter:67-87`/`count:90`/`has:94` 闭合自环零外部边（callgraph 实证）；删后须同删孤儿 `from typing import Iterator`(:5)、SP05 断言 `:54-55`、两层 re-export。无静默业务损坏路径。唯一操作风险=与 R04 同文件强行号互撞→**R01 先删（消 :72，R04 收口面 6→5）再 R04 按删后新行号 rg 重定位**，同 PR 原子提交。分层：纯删不新增 import，0 违规自动满足。

## 2) 漏项（本轮新发现，计划未充分覆盖的爆点/缺失前置）

1. **【中】R04 哨兵 C 文件名漂移**：R04 dossier/cluster 写哨兵 C 在 `schedule_persistence_errors.py:13`，但 R09 收编面权威表(_layer2_residual)把 `schedule_persistence_errors.py:13 _positive_int int(value or 0)` 列为 **R09 的「第 3 份未收编 Optional 副本」owner 复核项**。即同一行 `:13` 被 R04（当哨兵 C 补注释）与 R09（当待收编副本）**双重认领**——若 R04 先补「禁收口」注释、R09 后又想收编同一处，语义冲突。**前置缺失**：owner 须先裁 `schedule_persistence_errors.py:13` 归 R04（→None 哨兵注释钉死）还是 R09（收编入 sink），不能两路同时动。
2. **【低】F1 改 `_parse_finite_int` 是 parse_required_int 与 parse_required_float 共用内核**：cluster 只点了 parse_required_int 调用方回归，但 `_parse_finite_int`(:46) 仅服务 int 路；parse_required_float 走 `:67 parse_required_float` 独立路（已 rg）。F1 只动 int 路不波及 float 路——此点 cluster 未显式澄清，建议 F1 parity 同时断言「float 路不受 reject_integer_float 影响」防误改面扩大。
3. **【低】R08 在途 diff 与 R09 调用点读取交织**：R08 dossier 已记本文件 build_task_card 重构 diff 未提交；但 R09 的 B 副本调用点 `:257/:258/:353` 正落在被重构的 build_task_card 区——R09 重盘行号时须确认在途 diff 是否已动 `:257/:258`（实测 build_task_card def 现 :256，调用点须落定后重 rg），否则 R09 照本档行号迁=踩在途 diff 漂移。前置：R08+R09 都须等同一在途 feature 落定。
