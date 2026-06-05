# 逐簇爆炸对抗 r2 · C-GRAPH-ERR-DIAG · 主透镜【承重误删】

> 只读不改，行号经 2026-06-05 rg 回盘。主攻 Q1 承重误删 / Q5 收口等价 / Q6 测试迁移序。
> 默认怀疑：多数维度存疑即红。本轮独立回盘，不信旧值。

---

## 回盘已确认（与 cluster/dossier 一致的承重点，绑定不删）

- R52/R25 同符号 `get_ready_operation_ids`：impl `ready_queue.py:103`、`ReadyQueueContractError:10`、`__all__:138`；service 垫片 `core/services/scheduler/graph/ready_queue.py:9 import` 全准。生产零业务调用证实。
- sgs_graph parity 反例成立：`_prepare_graph_ready_state:33` 对 `None` 输入 `:38-39 return None` **不 raise**；全量版 raise `ReadyQueueContractError`，LIVE raise `ValidationError(field=graph_ready_context)`（:22/:24/:26…）——**异常类不同**，不可断言同类型。
- LB08 承重点全准：`LEGACY_PUBLIC_PATTERNS:62`/`_LEGACY_CODE_PREFIXES:94`/`public_safe_identifier:142`/`make_public_error:175`/`legacy_public_error_message:218`/`infer_legacy_public_code:284`；注释插入点 `:61` 空行确认。
- R46 删除段 `:162`(注释)+`:163`(def)+`:164`(body) 准；与 `_positive_int:167` 仅隔 2 空行，与禁区零重叠。
- R14 死门 `:42/:114/:134`、活门 `:56` 准；`resolve_plan:105` 含 `fallback_to_adopted:136` 不 raise，`resolve_existing_plan:141` 严格 raise——fallback 吃 raise 成立。
- R24 web 孪生护栏 `NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144`+raise 行全在 web，core 零护栏；roadmap `:435/:480/:481` 三处引用确认。
- R02 壳 `:461`/兄弟壳 `:478` 准；R06/R27 SP05 `:310` 七元组、`:315` 四元组、`_assert_init_has_no_imports:173` 被 `:316`+`:409` 双调用全准。

---

## 逐债判定

### 🔴 R52 + R25（方向 A 删全量版）— 测试迁移清单严重失真，序错即丢合同覆盖
**dossier 把 test_ready_queue.py 笼统说成"~23 个 LIVE-only sgs_graph 测试"，实测失真。**
回盘：整文件共 **31 个用例**，helper `_ready()`（:23-37）**直接调全量版 `get_ready_operation_ids`**。`:89-263` 约 **18 个用例**（含全部 `test_*_reports_contract_error`:156/163/168/174/186/191/263、`test_graph_like_object_is_not_accepted:230`、`test_bool_sort_key:258` 等合同断言）走 `_ready()`→**全量版**，断言的是**全量版自己的 `ReadyQueueContractError`**，**不是** sgs_graph 的 `ValidationError`。
**灾难链**：方向 A 删 impl → 这 18 个走 `_ready()` 的合同用例随之死 → 它们覆盖的 `ReadyQueueContractError` 合同（异常类 ≠ LIVE 的 ValidationError）一次性蒸发 → dossier 的迁移方案"23 LIVE 用例 + 3 契约 + 6 oracle 改字面量"**根本没安排这 18 个全量版合同用例的归属** → 要么静默丢 ReadyQueueContractError 合同覆盖，要么硬迁到 sgs_graph 文件却发现 LIVE 不抛该异常类、断言必红。
**叠加漂移**：dossier 钉的三契约行 `:302/:326/:361` 实测偏移——`:299`(schedulable_fixed_overlap)/`:311`(non_positive_fixed)/`:326`(unknown_link_scope)/`:352`(fixed_successor_conflict)。照搬旧行号迁移会错配。
**修正建议（前置/禁区）**：① owner 决策门先裁 A/B 前，必须按 `_ready` vs `_graph_state/_incremental` 两类 helper **重新分桶 31 个用例**（哪些断全量版 ReadyQueueContractError、哪些断 LIVE ValidationError），不可用"23 LIVE-only"旧口径。② 全量版合同用例（断 ReadyQueueContractError 那批）须 owner 显式裁定：是随全量版删（接受丢该异常类合同），还是 LIVE 的 ValidationError 已等价覆盖（须逐分支证 parity，非"均拒绝"一句带过）。③ 迁移前按符号名 rg 重定位三契约行，禁照搬 :302/:326/:361。④ 同提交退 `lazy_runtime:27`+`metrics_topology:140` 模块名断言。

### 🟡 R24（路 A 删 core）— 条件：roadmap `:481 pyright` 同样要摘 core，且禁反删 web 孪生
承重灵魂线全在 web 孪生（`NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144`+raise），core 零护栏。**条件**：① 先调和 roadmap，`:480 ruff`/`:481 pyright` **两条命令都含 core 文件名**，须只摘 core、保留 web helpers 路径（dossier 已覆盖，执行勿只摘 :480 漏 :481）；② 绝不反删 web 孪生（反删=活诊断页 analysis.html 炸+丢非有限数字护栏=静默坏值/500）；③ 测试 `:82` 混合用例仅剪首行 `:83`，保留 :84+ web 断言。满足即绿。owner_pending 走路 B（立 core 为收口点）则踩 P4、违铁律 5，须另立 P5+护栏先下沉。

### 🟡 R14（删死门）— 条件：LB01 让位 + :328 候选灵魂线不可平移到活门
`resolve_plan:105`→`fallback_to_adopted:136` 不 raise，`resolve_existing_plan:141` 严格 raise，二者**非 scenario 分支不等价**。**条件**：① 跨簇 LB01（同符号 `_resolve_strict_plan:134`）承重裁断先行，未放行前 :134-139 按禁区对待，R14 让位；② `:328 reads_candidate_rows_without_fallback` 灵魂线**不可**平移到活门 diagnose 入口（会被 fallback 吃掉静默丢"无静默回退"覆盖），owner 须重钉 `resolve_existing_plan` 层；③ 删死门**不得**顺手修 resolve_plan 静默回退隐患（铁律 4）；④ 改 roadmap:485-498+items.yaml:83。满足即绿。

### 🟡 LB08 → R46（同文件承重先于删行）— 条件：LB08 注释先落 + R46 按符号重定位
**条件**：① LB08 注释先落（或同提交先于 R46），钉死正则桥承重边界；② LB08 插 N 行后 R46 的 :162-164 下移，**必须按符号名重新 grep 定位，禁照搬旧值**；③ R46 删段与禁区（:62/:94/:142/:175/:218/:284/:340）零重叠，同名陷阱 `v4_sanitizers.py:37 _safe_identifier`（2 处活调用）绝不误删；④ LB08 owner_pending：注释文案产出点指 `greedy/internal_operation.py:119/148/150/154`+`dispatch/resource_validation.py:86`，非 auto_assign，owner 裁。LB08 纯插注释零运行时改动安全；R46 直删死别名安全。满足顺序即绿。

### 🟡 R06 + R27 + gantt（四空包同提交）— 条件：唯一安全顺序=一次性原子提交
**条件**：① 四包必须同一提交：一次性把 `:310` 改成 `("config","run","summary")`、`:315-316` 整块删、同删 dispatch/calendar/batch/gantt 四目录。逐增量摘产生中间态，第二次按过时行 old_string 匹配会失配/误删。② 删 `:315-316` 块**只删调用语句、保留 `_assert_init_has_no_imports:173` 定义**（:409 web 域仍调用，连定义删=NameError）；③ `:310` 里 `config/run/summary` 真包只留不摘。满足即绿。

### 🟢 R02（独立单债）
壳 `:461` 直删 + 测试 import 拆分（`build_first_wave_ready_nodes:11` 单拎改指 resource_matching_context，后三符号留原 dispatch import），生产零消费、最坏响亮 ImportError 无静默炸。先拆 import 再删壳。禁连删兄弟壳 `:478`（report.py:180 承重）。安全。

---

## 漏项（本轮新发现，未被计划覆盖）

1. **【高】R52 迁移清单失真**：dossier"~23 LIVE-only 测试"口径错——实测 31 用例中约 18 个走 `_ready()`→全量版、断 `ReadyQueueContractError`（异常类 ≠ LIVE ValidationError）。计划未安排这 18 个全量版合同用例的归属，删 impl 即静默丢该异常类合同覆盖。前置缺失：owner 决策门前须按 helper 重新分桶 31 用例，非沿用旧口径。
2. **【中】R52 三契约行号漂移**：dossier 钉 :302/:326/:361，实测 :299/:311/:326/:352。照搬旧行迁移错配。须按符号 rg 重定位。
3. **【低】R02 灵魂守卫定位漂移**：cluster D 节/R02 dossier 说 `GraphInputContractError` 在 `schedule_graph_resource_matching_context.py:28-45` 本地定义，实测守卫 raise 在该文件但 `GraphInputContractError` **import 自 `core.services.scheduler.graph.input_adapter`**（:31/:41）。不影响 R02 安全结论（删壳碰不到守卫），但禁区行的真 home 是 input_adapter，记账修正。
4. **【低】R24 roadmap 双命令**：`:481 pyright` 与 `:480 ruff` 都含 core 文件名，执行勿只摘 :480。
