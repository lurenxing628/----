# 逐簇爆炸对抗 r2 · C-PARSE-INT · 主透镜【承重误删】

> skeptic 第2轮，只读不改。默认怀疑：这一簇按计划改下去会不会连环炸？
> 全部 file:line 为 2026-06-05 当前工作区 rg/sed 回盘实证，不信 dossier/registry/residual 旧值。
> 成员债：R01 / R04 / R09 / R28 / R59 / R08。本簇 6 成员自身 load_bearing 全 false，承重门控来自毗邻/同源。

---

## 0) 回盘实证总账（本轮独立重跑，全部坐实）

| 锚点 | 回盘命中 | 与计划口径 |
|---|---|---|
| R09 收口点 `parse_positive_execution_int` | `operation_execution_scope.py:9`，`:10 isinstance bool→raise`、`:16 not isdigit→raise`、`:20 raise` | 严格 loud raise，准 |
| R09 A 副本 | `resource_dispatch_execution_service.py:24` body `int(value)`，调用 :169/:180/:181 | 宽松 `5.9→5`/`True→1`，准 |
| R09 B 副本 | `web/viewmodels/scheduler_resource_dispatch_execution.py:33` body `int(value)`，调用 :257/:258/:353 | 宽松，准 |
| R09 C 路（已收口） | `..._execution_context.py:28` wrap `parse_positive_execution_int`(:30) + `except ValueError→None`(:31-32) | 严格 `5.9→None`/`True→None`，准 |
| 新建 sink `parse_optional_positive_int` | 全仓 grep=**0** | 未建，准 |
| F1 `reject_integer_float` | 全仓 grep=**0** | 未落地，准 |
| strict_parse 收口点 | `_parse_finite_int:46`（无 reject 形参）、`:56 1e-9` 容差接受 3.0、`parse_required_int:81` | F1 缺位坐实 |
| R04 主符号 | `schedule_payload_contract.py:50`，`:51` 显式拒 float/bool；6 调用点 :72/:149/:198/:308/:324/:372，except 全 `(TypeError,ValueError)` | 准 |
| ValidationError 继承 | `errors.py:63 AppError(Exception)` / `:97 ValidationError(AppError)` | 非 ValueError 子类，逃逸坐实 |
| R59 续命测试 | `regression_web_silent_fallback_contract.py:247('1.0')/:250(1.0)` 全 `raises(ValidationError, match="导出行数")` | 准 |
| R59 私有正则 | `report_number_parsing.py:9 _INT_TEXT_PATTERN`、`:54 _parse_plain_report_int`、`:73 nonnegative`、`:36 parse_report_int`(禁动) | 准 |
| R08 同源不变式 | `service.py:127 ≡ :130`（同 key 同 bool）、:139 默认 True、:214 _empty(F,F) | (T,F) 不可达坐实 |
| R08 死分支 | viewmodel `:25 常量`、`:227-228 死①`、`:367-368 死②`、`:234 活路径 can_write and feedback_write_enabled` | 准 |
| R08 真消费点 | `..._context.py:229/:237/:246` 硬传 True；`..._routes.py` grep=**0** | registry 误标 routes 坐实 |
| R28 静默吞错 | `batch_service.py:55-64` `except Exception: return None`（:63-64） | 准 |
| R28 上游护栏 | `batch_operation.py:92` / `part_operation.py:75` `parse_optional_float(ext_days)` | 爆炸半径极小坐实 |
| R28 fitness 守卫 | `test_architecture_fitness.py:64 NAMES`、`:77 ALLOWLIST`、`:254 stale_entries` 断言 | 准 |
| R28 越界禁区 | `batch_template_ops.py:170-171` / `batch_copy.py:70-71` `float(... or 0.0)` 工时兜底 | 准 |
| R01 死链 | `schedule_payload_contract.py:67/:90/:94/:414-415` 闭环；外部消费 grep=**0**；`Iterator:5` 孤儿 | 准 |

---

## Q1 承重误删（主透镜）逐成员裁定

### 🔴 R09 — 红（最危：A/B 直接收编 = 静默放宽 + persistence:13 跨计划矛盾指令）

**灾难链 1（静默放宽，本轮独立复现）**：A/B 副本是 `int(value)`（`5.9→5`、`True→1`），C 收口点 `parse_positive_execution_int` 对 bool/非 isdigit 文本 loud raise（`5.9→None`、`'5.9'→None`、`True→None`）。改 X = 把 A/B "按字节同体直接换收口点" → C 经用户输入路径（context.py:107/:258 取 `payload`/`request.args.get`）当前把 `5.9`/`True` 拒为 None（安全），若把 A/B 收口到与 C 同一收口点而 sink 取 C 的严格语义 → A/B 由"垃圾正整数 `5.9` 截断成 5 参与行比对"变 None，**或**反之把 C 拉宽到 A/B 截断语义 → `5.9→5` 进 `_row_matches_feedback_target`(context:96/:271) 误命中相邻行 → **现场记录静默写到错的任务上，无报错**。承重不对称（A/B 宽松 vs C 严格）被"看着该 DRY"的统一动作抹平 = fail-open 放行垃圾正整数。**主透镜命中**。

**灾难链 2（误用 raise 版替本助手，整页崩）**：若执行者把 A/B 收口到 `parse_finite_int`（R04 sink，raise 契约）或直接 `parse_positive_execution_int`（raise）而不保留"坏值→None 跳过坏行"语义 → 遍历可信 DB 行/任务卡渲染遇任何非正值由"跳过"变"抛异常" → service:169 `_op_ids` / viewmodel:353 任务列表 / build_task_card 整页崩。

**灾难链 3（本轮新发现，跨 R04/R09 矛盾指令）**：`schedule_persistence_errors.py:13 _positive_int`（→None 哨兵）被 **R04 dossier 字段4c 钉死"错误处理路径降级哨兵，禁止收口到会 raise 的 parse_required_int，仅补注释"**；但 `_layer2_residual.md` 第37行把同一个 `persistence_errors.py:13` 列为"R09 第3份未收编 Optional 副本，owner 复核收编"。**两份计划对同一承重哨兵给出相反指令**。若 R09 执行者按 residual 把 persistence:13 收编进 `parse_positive_execution_int`（raise 链）→ 在持久化错误归一路径抛二次异常掩盖主诊断 = 违 R04 灵魂线 + fail-loud 反噬错误路径。

**修正/前置**：(a) owner 先裁 C 的 float/bool 契约取哪条（保 C 严格 / 放宽到 A/B），据此调 sink；(b) **persistence:13 归 R04 注释禁区，不归 R09 收编面**——R09 收编面仅 A(service:24)+B(viewmodel:33) 两份，residual 第37行"第3份未收编"须撤销或显式标"= R04 哨兵C，禁收口"；(c) 强串行 R07(已 fixed)→R08(B01)→R09(B05) 之后重 grep 行号再迁；(d) 收口前先写两路 parity（A/B 零漂移 + C float/bool 分歧）；(e) STRICT 收口点本体 `scope:9` 一字不碰。owner_pending=true，**只标不给终态**。

### 🟡 R04 — 黄（6 处 except 漏一处 = ValidationError 一路上抛炸排程；F1 默认必 False）

**条件可做，但三道闸全绿才放行**：
1. **异常逃逸链（坐实）**：ValidationError 非 ValueError 子类（errors.py:63/:97）。A 收口改抛 ValidationError 而漏改 6 处 except 任一 → 脏 op_id 由"静默跳过/字段化"变"ValidationError 一路上抛"。经 `count_actionable_schedule_rows:90→_iter:67→A` → 排程统计崩；经 `has_:94`（R01 兄弟）→ 本应正常的持久化整体 abort。low 踩 P0。6 处 except 须**同 PR 全改**，不可拆。
2. **F1 默认值（主透镜·准承重）**：`reject_integer_float` 加在 `_parse_finite_int:46`，**必须默认 False**。默认 True = 把所有现有 `parse_required_int` 调用方（sgs_graph 等 core/algorithms）的 `3.0` 由接受变 raise → 配置/排程静默回归。这正是"看着该对齐签名"落在承重不对称上的红线。F1 parity（True→3.0 raise / False→3.0 接受）先绿。
3. **哨兵 B/C 仅注释禁改 raise（灵魂线）**：`auto_assign:114`（→0）、`persistence:13`（→None）在错误处理路径，改 raise = 抛二次异常掩盖主诊断。仅补"我是故意的"注释 + parity 钉边界，**不参与 A 收口**。
4. **LB08 毗邻**：R04 在 auto_assign 只动哨兵 B（数值序号解析）补注释，禁碰 `AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES`/`_auto_assign_error_identity`(约:126+) 文案/正则桥；须确认 LB08 认账注释先落或同批。

### 🟡 R59 — 黄（不等 F1 裸收口撞 '1.0'/1.0 raise 续命测试；blank 短路必迁）

**条件**：F1 未落地前裸收口 → `parse_required_int` 接受 `'1.0'`/`1.0`→1，直撞 `:247/:250 raises(ValidationError)` → **CI 显性红（非静默，良性炸法）**。F1 落地后 `reject_integer_float=True` 才兑现 raise。隐性静默炸点：删 `_parse_plain_report_int:54`/`_INT_TEXT_PATTERN:9` 时**漏迁 blank 短路**（现 :62-63 blank→blank_default(0)，strict_parse 对 blank raise）→ 导出行数空值由"降级到 0"变"报错中断 web 导出"。禁动兄弟 `parse_report_int:36`（接受 '2000.0' 是别 field 有意语义）。F1 前停"注释+parity"临时态。

### 🟡 R08 — 黄（owner_pending；误删参数 = 填写按钮门禁塌缩静默放开误填）

**条件**：(T,F) 不可达**依赖 service:127≡:130 同源**这一不变式（坐实），删死分支前须先在测试钉该不变式（把偶然变契约，对应 corrections C 的 N1 承重）。候选A 删 `:25/:227-228/:367-368` 但**必须保留 `feedback_write_enabled` 参数**——它仍被活路径 `:234 can_write and feedback_write_enabled` 消费。误把参数一起删 → `build_available_actions:232` 门禁塌成只看 can_write → 已完工/非可填状态亮按钮 → **静默放开误填现场记录**（主透镜·承重不对称误删）。owner 须先裁"是否未来总开关预埋"。owner_pending=true，**只标不给终态**。须等本文件在途 task_key 重构落定再动（行号会再漂）。

### 🟢 R28 — 绿（完全独立叶子，方向 P4 正向，爆炸半径极小）

收口到已存在 `parse_finite_float`（scheduler/number_utils:6 已 re-export），**不改 number_utils 一行**。上游护栏 `batch_operation:92`/`part_operation:75` 已 `parse_optional_float`，`_safe_float` except 几乎不可达 = 冗余防御，收口后生产零变化。必守：`allow_none=True`（否则炸所有空 ext_days）、不越界动 `setup/unit_hours float(... or 0.0)`(:170-171/:70-71)、同步退/留 fitness 白名单 :77（先跑 `pytest -k allowlist` 据实定）。承重误删风险无。

### 🟢 R01 — 绿（纯删死码，零外部消费双证，所有误删响亮暴露）

死链 `:67/:90/:94` 闭环，外部消费 grep=0，无静默业务损坏路径——漏删/误删均以 ImportError/SyntaxError/SP05 红 响亮暴露。非承重文件无禁区行。须同删 `Iterator:5` 孤儿 import（坐实仅 :67 用）。唯一真爆点：误删 run import 块 :13-15（ValidatedSchedulePayload/Row/build_）→ 生产 ImportError，严守"只删 :16-17"。与 R04 同文件强行号互撞 → 同 PR、R01 先删缩 R04 收口面 6→5、R04 按删后新行号重 grep。

---

## Q2 分层导入环：🟢 全绿
R09 sink 落 core/shared 或沿用 core.models.scope（已 import，web→core.models 合法）；R04/R59 收口点 strict_parse 在 core/shared（已 import，零新增边）；R28 services→shared 合法。无 core.models→core.services / core.algorithms→core.services / repo→service 越层，无导入环。0 AST 违规。

## Q3 迁移耦合：🟢 不触发
本簇纯码层数字解析收口/删死码，不动 schema CHECK / v18·v19 DB CHECK / adopted-only 下沉。无改码不改迁移=启动探针炸风险。

## Q4 灵魂线热路径：🟡 见 R04/R09/R28
R04 A 收口走 loud raise（正向），但 6 处 except 漏改 = 热路径（排程统计/持久化）可用性放大（已计 R04 黄）。R28 改 raise 是 P4 正向修（静默吞错→loud），上游护栏托底不放大。R09/R01/R08 不新增兜底；R08 删死分支须保参数防门禁塌缩。无新增静默回退/吞错。

## Q5 收口行为等价：🔴 R09 不等价（核心反例）
C 路严格 `5.9→None`/`True→None` vs A/B 宽松 `5.9→5`/`True→1`（独立复现坐实）。直接收口静默放宽/收紧，须先 parity 钉死 + owner 裁。R04 A 旧 ValueError vs 新 ValidationError"行为等价类型变"（须同改 except）。R59 `'1.0'` 旧 raise vs 裸收口接受 1（F1 兜）。R28 垃圾/NaN/inf/bool 旧静默 vs 新 raise = 有意方向变更（非回归）。

## Q6 测试迁移序：🟡 强序约束
R04 先写 A/B/C parity → 改 except → 收口；R59 先 parity 钉 '1.0' raise + blank 短路 → F1 后收口；R08 先钉 :127≡:130 不变式守卫 → 删死分支；R01 删函数 + 删 SP05:54-55 断言**必须同提交**（中间提交必红）；R09 先两路 parity → R07/R08(B01) 后重 grep → 迁 A/B。R28 先跑 `-k allowlist` 定白名单退留。序错=测试红或复活兜底。

---

## 返回摘要

簇内裁定：R09🔴 / R04🟡 / R59🟡 / R08🟡 / R28🟢 / R01🟢。承重误删主风险集中在 R09（A/B 静默放宽 + 误用 raise 版整页崩 + persistence:13 跨计划矛盾指令）与 R08（误删 feedback_write_enabled 参数门禁塌缩）。F1 默认必 False 为 R04/R59 共用准承重红线。

**本轮新发现（计划未覆盖）：**
1. **R04↔R09 对 `schedule_persistence_errors.py:13 _positive_int` 给矛盾指令**：R04 dossier 列其为"禁收口的错误路径降级哨兵（仅注释）"，但 _layer2_residual.md:37 列其为"R09 第3份未收编 Optional 副本（owner 复核收编）"。须裁定归属——按 R04 口径它是禁区，按 residual 口径收编它会违 R04 灵魂线在错误路径抛二次异常。建议归 R04 禁区、撤 residual"第3份"标记。
2. **residual"STRICT 4 处 `-> int` loud raise 一字不碰"口径部分失真**：回盘 `auto_assign:114` 与 `scheduler_public_errors:167` 签名虽 `-> int`，body 实为 `except Exception: return 0`（→0 哨兵，非 loud raise）；只有 `feedback_support:161`(带 field) 与 `scope:9` 是真 loud raise。被 `-> int` 签名误导分类。不构成 R09 误删风险（R09 本就不碰这两文件），但"STRICT 标签"作为收编依据失真，须更正为"2 真 loud raise + 2 →0 哨兵"。
