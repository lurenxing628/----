# 逐簇爆炸对抗 r2 · C-GRAPH-ERR-DIAG · SOUL 主透镜

> skeptic r2，只读不改。主透镜=灵魂线热路径+收口等价（Q4/Q5/Q6 为重）。行号经 2026-06-05 独立 rg 回盘，不信旧值、不盲信 r1。
> 默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。
> r1 判定已读；本轮独立复跑全部关键反例，r1 结论**整体成立**，并补 4 处新爆点（见漏项）。

## 判定总览（与 r1 对账：维持）

| 债 | r1 | r2 | 一句话 |
|---|---|---|---|
| R52 | 🔴 | 🔴 | 裸删 impl → test_ready_queue.py 31 用例 + 4 ValidationError 契约一次性蒸发；异常类不等价、None 分支不可 cross-check |
| R25 | 🟡 | 🟡 | 与 R52 同提交且晚于测试迁移；先删垫片 → :16 import + `_full_scan_ready_ids:79` 双红 |
| R14 | 🟡 | 🟡 | 候选灵魂线 :328 不可平移活门（resolve_plan:136 fallback_to_adopted 吞 raise）；LB01 同符号承重先裁 |
| R24 | 🟡 | 🟡 | 路 B 把活路径改指零消费 core → 丢 NonFiniteDiagnosticNumber 护栏=静默吞坏值（P4，违铁律 5） |
| LB08 | 🟡 | 🟡 | 承重正则反解桥；注释产出点 = internal_operation.py:119/148/150/152/154 + resource_validation.py:86（**非 auto_assign**） |
| R06 | 🟡 | 🟡 | 四包+SP05 两行原子提交，否则 SP05 红或漏删 `_assert_init_has_no_imports` 守卫静默劣化 |
| R27 | 🟡 | 🟡 | 同 R06 |
| R46 | 🟡 | 🟡 | 同名陷阱 v4_sanitizers.py:37 `_safe_identifier` 活引用，按符号名跨文件删=v4 迁移 SQL 标识符无清洗 |
| R02 | 🟢 | 🟢 | 死壳直删，先拆测试 import :11 再删壳；最坏响亮 ImportError |

---

## 🔴 R52 — 唯一硬红（独立复证，证据强化）

**实盘回盘（2026-06-05，未照抄）：**
- impl `core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids`；`__all__:138`；`ReadyQueueContractError(ValueError):10`；全文 **19 处 raise ReadyQueueContractError**（:16/20/22/28/30/32/36/41/44/49/54/66/69/83/86/91/94/96/100）。
- `rg get_ready_operation_ids core/ web/ data/` 仅 4 命中=impl 定义 + R25 垫片 :9/:11，**生产零业务调用**。
- LIVE `sgs_graph.py`：`raise ValidationError(...,field="graph_ready_context")` 实测 :22/24/26/30/41/48/56/66/106/112/115/121/125/128/132/134…**异常类 ValidationError ≠ ReadyQueueContractError**。
- `_prepare_graph_ready_state:33` 对 `graph_ready_context is None` → `:39 return None`（**不 raise**）；全量版无 None 入口。

**灾难链（裸删 impl）→** 删 :103 impl → R25 垫片 :9 import 立即 ImportError →
**新爆点（r1 未点透）**：`test_ready_queue.py:16` 经垫片 import `get_ready_operation_ids`，且 **`_full_scan_ready_ids:79` 函数体直接 `return get_ready_operation_ids(...)`**（实测 :80-86）→ impl 一删，不仅 import 红，**6 处差分 oracle（:275/278/281/284/296）调用的 `_full_scan_ready_ids` helper 也炸**，必须先删 :79 helper 并把 oracle 改字面量期望 →
整文件 **31 个 def_test 蒸发**（`rg -c def test_`=31，r1 已纠 dossier「~23」低估，r2 复证 31）→ 其中 **4 条唯一 LIVE ValidationError 契约消失**：:302（不能同时是固定）/:314（大于等于 1）/:336（rejects_unknown_link_scope）/:361（固定/已完成工序冲突）→ **LIVE sgs_graph 行为覆盖一次性清零**。

**收口等价反例（Q5，删前必证不可抹平）：**
1. 坏 op_id：全量 raise ReadyQueueContractError，LIVE raise ValidationError → parity **只能断言「均拒绝」，禁断言同类型**。
2. None 输入：LIVE `:39 return None` 不 raise，全量无 None 入口 → **两路必须分别写，禁差分 oracle 一行 cross-check**。
3. oracle 删 full_scan 后 `_full_scan_ready_ids` 消失 → 6 处断言必先改字面量期望（`[1]/[2,3]/[3]/[4]/[2]`）+ **同删 :79 helper**（r1 漏项2 已点，r2 复证 helper 体确实调 impl）。

**修正（缺一即红）**：owner 先裁 A/B（owner_pending=true）→ 方向 A 先新建 `tests/scheduler_graph/test_sgs_graph_ready.py`（实测 NOT EXIST），按 **31 用例全量分流**（LIVE→新文件、full_scan 差分→改字面量 + 删 :79 helper、4 ValidationError 契约迁出）→ 再删 impl+R25 垫片（同提交）→ 同提交退 `regression_scheduler_graph_lazy_runtime_contract.py:27` + `test_metrics_topology.py:140` 两处模块路径字符串断言（loud fail）。**禁区**：ReadyQueueContractError 抛错链 loud raise（P3 非 P4），保留不改不加兜底。

---

## 🟡 条件可做（5 条，独立复证）

### R25（条件：与 R52 同提交 + 晚于测试迁移）
垫片 11 行纯转发（实测全文，`:9` import + `:11 __all__`），lb=false。先删垫片而 R52 未迁测试 → :16 import + `_full_scan_ready_ids:79` 双红（loud，安全失败中间态）。命运由 R52 决策门定（因 R52→果 R25）。同提交退两处模块路径断言。物理隔离（algorithm vs service），不撞行号。

### R14（条件：LB01 承重先裁 + owner 裁 :328 迁移目标）
死门三件套 `:42/:114/:134` 生产零引用（实测）。**parity 反例独立复证成立**：
- 死门非 scenario → `_resolve_strict_plan:139 resolve_existing_plan` → 缺角色/明细 **loud raise**（schedule_plan_query_service.py:152「所选方案不存在」/:157/:163「所选方案没有可查看的明细」）。
- 活门非 scenario → `resolve_plan:105` → 缺角色 **静默 fallback_to_adopted**（:136 status、不 raise）。

**灾难链**：把 :328 候选灵魂线（test:349 `pytest.raises 所选方案没有可查看的明细`）平移活门 `diagnose_resolved_plan_overdue` → 解析被 fallback 吃 → 断言失败 + 「无静默回退」语义被悄悄丢=失忆债。**修正**：:358 scenario 灵魂线两门同源可平移；:328 候选须 owner 裁改钉 `resolve_existing_plan` 层。删前三步前置（迁灵魂线/改 roadmap.md:485-498+items.yaml:83/确认无树外调用）。**铁律 4**：删死门不得顺手修 resolve_plan:136 静默回退。跨簇 LB01 同符号 `_resolve_strict_plan` 承重裁断必须先行，R14 删 :134-139 让位。

### R24（条件：先调和 networkx roadmap + 不走路 B）
core 死副本 `core/services/scheduler/analysis/schedule_diagnostic_contract.py`（`empty_diagnostic_sections:73` 等 5 符号）生产零消费（实测 `rg core/ web/ data/` 零命中，唯一引用 = test）。**路 B = 🔴级隐患**：core 对 NaN/Inf/bool 静默透传；web 孪生 `web/viewmodels/scheduler_analysis_diagnostic_helpers.py` `safe_int:127`/`safe_float:144` loud raise `NonFiniteDiagnosticNumber:101`（raise :106/131/139/141/148/152/154）。路 B 把活路径改指零消费 core = **丢护栏退化为静默吞坏值（P4）+ 立零消费 core 为收口点违铁律 5，须另立 P5**。
**修正（路 A）**：① 先改 `networkx-...items.yaml:435 primary_paths` 移 core + :480/:481 ruff/pyright **只摘 core 文件名**保留 web helpers 路径 + 加 note；② 删 core 整文件；③ 测试逐条剪 `tests/scheduler_analysis/test_scheduler_analysis_diagnostic_contract.py`：删 core import（:9-13 块，含 `empty_diagnostic_sections:13`）+ 纯 core 用例，**混合用例 :83 `assert empty_diagnostic_sections() == []` 单行剪除**（实测 :83 字面就是此串、非别名，r1/簇文件锚点准）保留 web 断言。
**禁区**：web 孪生护栏 `NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144`/`build_item:41`/`build_section:62` 绝不反删。

### LB08（条件：承重只补注释 + 产出点已实证待裁）
承重 true，legacy 正则反解桥 `LEGACY_PUBLIC_PATTERNS:62`。修法仅补注释+绑契约，绝不删/统一/透传。**误碰灾难链**：删正则桥 → `legacy_public_error_message:218` 对 legacy 中文串 fullmatch 失配 → 静默降级通用文案 + code 丢失（P4）。
**owner_pending#1 实证**：planned 草稿指 `auto_assign_resource_errors`（消费/反解方）错位；**真产出点 = `core/algorithms/greedy/internal_operation.py:119/148/150/152/154` + `core/algorithms/greedy/dispatch/resource_validation.py:86`**（实测产 raw 中文串「无法排产/无法自动分配/工时不合法/缺少自动派工所需工种信息」）。
**前置**：LB08 注释先落钉死承重边界 → R46 才在保护下删。绑已存在契约 `tests/schedule/route_view/test_scheduler_user_visible_messages.py:678 test_legacy_error_with_sensitive_tail_is_generic`（+ :694/:721 build_public_error_records）。禁区 :62/:94/:142/:167(R09)/:175/:218/:284/:340。

### R06 + R27（条件：四包+gantt 同一原子提交）
四空包 `core/services/scheduler/{batch,dispatch,gantt,calendar}/__init__.py` 实测均 **0 字节**、生产零引用（"imports" 全是 `n`/`ln`-aliased 异物 false positive）。碰撞点 = 同一 SP05 测试 **:310 七元组循环 + :315/:316 四元组 delayed 循环**（实测命中）。**灾难链**：逐增量摘 → 中间态过时 old_string 失配/误删；或删目录漏改 SP05 → `is_dir()` 红（loud）；或漏删某包却整删 :315-316 → 失 `_assert_init_has_no_imports:173` 守卫=未来塞 import 不被发现（静默劣化）。
**修正**：四包一次性把 :310 改 `("config","run","summary")`、删 :315-316 整块。**禁区**：`_assert_init_has_no_imports:173`（:409 web 域仍调用，删块只删调用、保留 :173，否则 NameError）；:310 内 config/run/summary 真包只留不摘；:638 另一 `("config","run","summary")` 循环（strong-compat 段）不碰。

### R46（条件：LB08 注释先落 + 三锁定避同名陷阱）
死别名 `scheduler_public_errors.py:163 _safe_identifier`（体 :164 `return public_safe_identifier(...)`）生产/测试零引用。**同名陷阱实证坐实**：`core/infrastructure/migrations/v4_sanitizers.py:37 _safe_identifier`（`-> Optional[str]`，被 `n()`-aliased 调用活引用）是独立函数 → 按符号名跨文件删=v4 迁移 SQL 标识符无清洗、迁移崩。
**修正**：文件+行号+符号三锁定删 `scheduler_public_errors.py:163-165`（连尾空行）。LB08 插注释后行号 +N，**按符号重新 grep 不照搬旧值**。禁区 :62/:94/:142/:167(R09)/:175/:218/:284/:340。删段不触 `__all__`（_safe_identifier 不在表），与 R01/R19 物理不重叠、顺序不敏感。

---

## 🟢 安全（1 条）

### R02 — 死壳直删
test-only re-export 壳 `build_first_wave_ready_nodes`（schedule_graph_dispatch_context.py:461）生产零消费。**顺序**：先拆 `test_graph_dispatch_context.py:10-14` 4 符号 import 块（实测 :11/:12/:13/:14）——**只**把 :11 单符号改指 resource_matching_context（真 __all__ home），后三符号留原路径，否则 ImportError → 再删壳 :461-475。最坏响亮 ImportError 无静默炸。**禁区**：兄弟壳 `build_graph_resource_matching_projection`（report.py:180 唯一生产消费=事实承重）不连删；resource_matching_context.py:28-45 `GraphInputContractError` 灵魂守卫不碰。lb=false，分层 0 违规。

---

## 漏项（r2 新发现，计划/r1 未充分覆盖）

1. **R52 的 `_full_scan_ready_ids:79` helper 是隐性二次爆点**：r1 漏项2 只点「6 oracle 改字面量 + 删 :79 helper」，但未强调 **helper 体本身 `return get_ready_operation_ids(...)`**——执行者若只改 import、漏改 helper，删 impl 后 helper 调用 NameError，且若先删 helper 漏改 oracle 则 6 断言 NameError。迁移指引须显式写「删 :79 helper 与改 6 oracle 是同一原子动作，二者顺序锁死」。
2. **SP05 存在第二处 `("config","run","summary")` @ :638（strong-compat 段）**：簇文件/r1 只点 :310/:315，未登记 :638。执行者 grep `config","run","summary"` 会命中两处，若误改 :638 = 破坏 strong-compat 断言（loud 红，非静默，但拖批）。须显式标「只改 :310，:638 不碰」。
3. **R24 测试 import 块跨文件别名混淆风险**：`rg empty_diagnostic_sections tests/` 在另一文件出现 `n,`/`ln (` 别名形态（Layer2 D2 已警 `build_workbench_plan_context` 别名纪律），但 `regression_scheduler_analysis_diagnostic_contract.py:83` 本文件是**字面 `empty_diagnostic_sections()`非别名**（实测 :13 直 import、:83 直调）——簇文件 :83 锚点准，但执行者跨文件 co-change grep 时须按文件区分，勿被别名文件干扰误判锚点漂移。
4. **R14/R24 双门 owner_pending 排批风险**：R14=LB01 承重裁 + :328 迁移目标裁（双门）；R24=路 A/B 裁 + networkx roadmap 调和（双门）。二者任一久拖即卡 B11/B-D 收尾。计划须显式标两债为「双门 owner_pending」，勿误当单门叶子排进 Batch-A 死叶子。
5. **LB08 注释逐字文案若贴 planned 草稿=指错文件**：草稿指 auto_assign，真产出点在算法层两文件（实证）。注释落地前 owner 须按实证产出点改写文案，否则承重认账注释指向消费方而非产出方 = 反而埋新失忆债。
