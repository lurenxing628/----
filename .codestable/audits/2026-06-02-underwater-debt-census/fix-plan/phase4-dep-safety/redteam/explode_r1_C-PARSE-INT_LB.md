# 逐簇爆炸对抗 r1 · C-PARSE-INT · 主透镜【承重误删/fail-open】

> skeptic 第1轮，只读不改，默认怀疑。主透镜 Q1：任何「看着像该统一/该 DRY/该对齐」落在承重不对称上即红。
> 全部行号 2026-06-05 rg 回盘，不信 dossier/registry 旧值。STRICT 4 处一字不碰已逐处确认。

## 0) 承重禁区行回盘（STRICT 写入闸，R09 一字不碰，全部命中）

| 禁区符号 | 真实 file:line | 契约 |
|---|---|---|
| `parse_positive_execution_int` | core/models/operation_execution_scope.py:9 | bool/非digit/<=0 一律 `raise ValueError`（:10/:16/:20） |
| `_positive_int(value, field)` | core/services/scheduler/operation_execution_feedback_support.py:161 | →raise（STRICT 写入闸） |
| `_required_positive_int` | data/repositories/operation_execution_event_repo.py:100 | →raise |
| `_positive_int(value)` | core/models/scheduler_public_errors.py:167 | →raise（LEGACY 正则桥邻） |
| `_positive_int(value)` | core/services/scheduler/run/auto_assign_resource_errors.py:114 | →raise（R04 哨兵 B 邻 LB08） |

收口家族 Optional 副本（收编面）：C 路 context.py:28 **已委托** scope.py:9（严格）；A 路 service.py:24、B 路 viewmodel:33 **未收编**（裸 `int(value)` 宽松）。

---

## 逐债判定

### 🔴 R09 — 收编静默放宽（本簇最危爆点，主透镜直接命中）
**判定红。owner_pending=true，本就不该进批次；强行收编即静默 fail-open。**

证据（回盘逐字坐实）：
- C 路 `context.py:28`：`parse_positive_execution_int(value,"execution_context")` except `ValueError→None` → `5.9→None`、`3.0→None`、`True→None`（scope.py:10 显式 reject bool、:16 `text.isdigit()` 拒小数点）。
- A 路 `service.py:24` / B 路 `viewmodel:33`：裸 `int(value)` except `(TypeError,ValueError)→None`，`>0` 保留 → `5.9→5`、`3.0→3`、`True→1`。
- `parse_optional_positive_int` 全仓 rg = **0**（新建前提作废，收口点 scope.py:9 已存在）。

**灾难链（改 X→静默→坏数据流到 Y）**：把 A/B 当「字节同体」直接收口到 scope.py:9 严格点 → A/B 由宽松变严格不是问题，**反向才是**：若按「字节对齐 A/B」新建宽松 sink 再把 **C 一并收口** → C 的 `5.9→None` 退化成 `5.9→5` → context.py:96/:97/:271/:272 的 `_positive_int(row.get("op_id")) == int(op_id)` 行比对中，用户输入 `request.args.get("schedule_id")="5.9"`（:258 用户字符串入口）被当 op_id=5 → `_row_matches_feedback_target` 误命中相邻行 → **现场记录静默写到错的任务上，无报错**。low 债踩成数据错配。

**修正建议**：①owner 未裁前 R09 整体不进批次（铁律：owner_pending 只标不给终态）。②收编只动 A/B 两 Optional 副本、收口到 **已存在** scope.py:9，C 路保持不动。③先补两路 parity：`test_parity_AB`(A/B vs sink 零漂移) + `test_parity_C_float_bool`(钉 5.9/3.0/True 在 C 收口前后是否变化)。④禁区行 5 处 STRICT 一字不碰；禁复用 R04 的 `parse_finite_int`(raise 契约相反)。

### 🔴 R04 — F1 默认值 + 6 处 except 异常逃逸（双爆点）
**判定红（强条件爆点，漏一处即炸）。**

证据：
- F1 `reject_integer_float` 全仓 rg = **0**（未落地）。`parse_required_int`(strict_parse.py:81) 被 **core/algorithms 大量调用**：sgs_graph.py:13/:28/:155-157/:169/:175、ordering.py:117/:118、auto_assign.py:395、sgs.py:143/:144、sgs_scoring.py:224/:225。
- 6 处 except 全是 `except (TypeError, ValueError)`：:73/:150/:199/:309/:325/:373（逐处回盘命中）。
- `class ValidationError(AppError)`(errors.py:97)，`class AppError(Exception)`(:63) → **ValidationError 非 ValueError 子类**。

**灾难链 1（F1 默认 True）**：F1 给 `_parse_finite_int` 加 `reject_integer_float` 若默认 **True** → sgs_graph/ordering/sgs 等现有调用方的 `3.0`/`id=3.0` 由接受变 raise → **排程内核静默回归**（配置/调度跑挂）。**必须默认 False**。
**灾难链 2（except 逃逸）**：A `_strict_positive_int` 收口后改抛 ValidationError，**漏改任一处 except (TypeError,ValueError)** → 脏 op_id 由「静默 continue/字段化」变「ValidationError 一路上抛」→ 经 `count_actionable_schedule_rows`(R01 兄弟链) 整个排程统计/持久化 abort。low 踩 P0。

**修正建议**：F1 必默认 False + 自带 parity(True→3.0 raise / False→3.0 接受) 先绿；6 处 except 同 PR 加 `ValidationError`，不可拆；A 收口与 R01 同 PR（R01 先删缩收口面 6→5，R04 按删后新行号 rg 重定位）；auto_assign_resource_errors.py 哨兵 B 只补注释，禁碰 LB08 文案/正则桥(:126+ `AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES`/`_auto_assign_error_identity`)。

### 🔴 R08 — 死分支删除依赖同源不变式，误删参数=门禁塌缩
**判定红（owner_pending=true，且 (T,F) 不可达依赖隐式不变式，无守卫即脆）。**

证据：
- 死常量 :25、死分支① :227-228、死分支② :367-368 原样在；活路径 :234 `fill_enabled = bool(can_write and feedback_write_enabled and ...)`。
- 同源不变式 service.py:127 `bool(plan_role_fields.get("can_write_feedback"))` ≡ :130 `bool(plan_role_fields.get("can_write_feedback"))` **同 key 同 bool()**；context.py:229/:237/:246 三处硬传 `feedback_write_enabled=True` → (T,F) 不可达。
- 二层护城河确认：build_execution_payload:372 `"guardrail_text": "" if can_write else disabled_reason` → can_write=True 时恒空。

**灾难链**：候选A 删死分支须**保留 `feedback_write_enabled` 参数**（仍被 :234 消费）。若以「DRY/参数没用了」名义连参数删 → :234 门禁判定塌成只看 can_write → 已完工/非可填态也亮「填写实际」按钮 → **静默放开误填现场记录**。另：(T,F) 不可达依赖 service:127≡:130 同源，无测试守卫时未来有人拆开同源 → 死分支变可达 → 删除引入回归。

**修正建议**：owner 先裁「是否未来总开关预埋」(commit 65870e47 lane)；先在 `tests/resource_dispatch/test_resource_dispatch_workbench_lane_contract.py` 钉 `can_write_feedback==feedback_write_enabled` 不变式守卫，再删；候选A 保参数只删分支+常量；R08(B01)先于 R09(B05) 同文件串行(:367 锚)；等本文件在途 task_key 重构 diff 落定再动（行号已漂 +1~+6）。

### 🟡 R59 — F1 互锁，裸收口撞续命测试（条件可做）
**判定黄：F1 落地前只能停「注释+parity」临时态，F1 后可独立收口。**

证据：续命测试 `regression_web_silent_fallback_contract.py:241('1.5')/:244('-1')/:247('1.0')/:250(1.0)` 全 `pytest.raises(ValidationError, match="导出行数")`（回盘命中）；私有正则 `_INT_TEXT_PATTERN`(:9 `^[+-]?\d+$`) 现态拒 `'1.0'`(:68 fullmatch 不含小数点)。

**条件**：F1 前裸收口 → `parse_required_int('1.0')` 接受 1（strict_parse:56 `1e-9` 容差）→ 撞 :247/:250 → **CI 红（显性，非静默，良性炸法）**。故必须 F1 先落 + `reject_integer_float=True`，并保留 blank 短路(:63 `return int(blank_default)`，strict_parse 对 blank 是 raise)。禁顺手改兄弟 `parse_report_int`(:36，别 field 语义，接受 '2000.0' 是有意的)。独立文件、不撞行号，F1 后可独立提交。

### 🟢 R28 — 完全独立叶子，收口改 raise 方向（安全）
**判定绿。**

证据：2026-06-08 已 fixed。`_safe_float` @staticmethod batch_service.py:56(@:55)，当前函数体 :57 已为 `parse_finite_float(..., allow_none=True)`；2 消费点 batch_template_ops.py:172 / batch_copy.py:72 不变；收口点 `parse_finite_float`(number_utils.py:14/:19/:23 已存在 overload)。上游模型层已 `ext_days=parse_optional_float(...)`：part_operation.py:75 / batch_operation.py:92 → 流入 `_safe_float` 恒为 None 或合法 float。收口走 services→shared 合法方向，未改 number_utils 一行。

**执行结果**（非红）：已使用 `allow_none=True`（ext_days 合法可空）；fitness 白名单 test_architecture_fitness.py:77 经 `pytest -k test_no_new_local_parse_helpers` 实测保留；未越界动两消费点 `setup_hours/unit_hours = float(... or 0.0)` 工时兜底。同名异符号 process_bp.py `_safe_float(value,field)`(R41 raise版)未误碰。

### 🟢 R01 — 死簇纯删，零生产消费（安全）
**判定绿。**

证据：`_iter:67`→`count:90/:91`→`has:94/:95` 自封闭死环，`__all__:414-415`；inbound 全零（外部边=0）。纯删不新增 import，0 分层违规。所有误删以 ImportError/SyntaxError/SP05 红 **响亮暴露**，无静默业务损坏路径。

**纪律**：自下而上删避免自伤行号；同删孤儿 `typing:5 Iterator`(仅 :67 用)；只删 run import :16-17 保 :13-15(ValidatedSchedulePayload/Row/build_ 生产路径)；与 R04 同 PR(R01 先删)；SP05 改时 rg 重定位模块键当前行(:53-56)。

---

## 漏项（本轮新发现，计划未覆盖 / 缺前置）

1. **R09 用户输入路径放宽风险被低估**：context.py:258 `request.args.get("schedule_id")` 是**用户字符串入口**（非可信 DB 行），C 路严格 `5.9→None` 是当前安全护栏。簇文档把 R09 收编面笼统记「C 已收口」，但**未把「C 路守的是用户输入路径」单列为收编 C 时的额外回归面**——`regression_resource_dispatch_*` 4 个契约测试是否覆盖「畸形 schedule_id 用户输入→不误命中行」需 owner 收编 C 前显式确认（当前 dossier 字段11 只列测试名未断言覆盖此分支）。

2. **R04 F1 与 R59 F1 是否同一形参/同一默认值缺一致性守卫**：F1 被 R04+R59 共用，但二者 parity 各自写。若 R04 落 F1 默认 False、R59 收口传 `reject_integer_float=True`，而**未在 F1 自身加「默认 False 不破坏 algorithms 调用方」的回归门**（sgs_graph 8 处），则 R04/R59 各自 parity 绿但 algorithms 静默回归无人接——簇文档把 F1 默认 False 写进 D-4 门控，但**未指定 F1 自带「algorithms 调用方 3.0 仍接受」的专项回归测试**作为 F1 落地放行门，仅靠 R04/R59 的 parity 兜不住 algorithms 面。建议 F1 落地 PR 自带对 sgs_graph/ordering 的 smoke。

3. **R08 在途 diff 未落定 = 行号漂移叠加风险未进 DAG**：本文件当前工作区有未提交 task_key/state_key 重构（build_task_card 大改），死分支绝对行号已漂 +1~+6。簇文档 A4 串行只锁了 R08→R09 顺序，**未把「F-worktree-settle」(等在途 feature 落定)列为 A4 进批次的硬前置门**——若在途 diff 与 R08 删行同窗口落地会撞。建议补为 A4 前置门。
