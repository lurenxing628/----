# 逐簇爆炸对抗 r1 · C-GRAPH-ERR-DIAG · SOUL 主透镜

> skeptic r1，只读不改。主透镜=灵魂线热路径+收口等价（Q4/Q5/Q6 为重）。行号经 2026-06-05 rg 回盘，不信旧值。
> 默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。

## 判定总览

| 债 | 判定 | 一句话 |
|---|---|---|
| R52 | 🔴 | 裸删全量版 impl → test_ready_queue.py 整文件 31 用例（含 4 条 LIVE ValidationError 契约）一次性蒸发 |
| R25 | 🟡 | 必与 R52 同提交且晚于测试迁移；单独先删垫片 → :16 import 红 |
| R14 | 🟡 | 候选灵魂线 :328 不可平移到活门（fallback_to_adopted 吞 raise）；LB01 承重先裁 |
| R24 | 🟡 | 路 B 把活路径改指零消费 core → 丢 NonFiniteDiagnosticNumber 护栏=静默吞坏值（P4） |
| LB08 | 🟡 | 承重正则桥；注释产出点指向待裁（真产出在算法层非 auto_assign） |
| R06 | 🟡 | 四包必须同提交；漏删 _assert_init_has_no_imports 调用块边界 → :409 NameError |
| R27 | 🟡 | 同 R06：四包+SP05 两行原子提交，否则 SP05 红或野生残渣 |
| R46 | 🟡 | 同名陷阱 v4_sanitizers._safe_identifier 有活引用，误删=迁移 SQL 标识符崩 |
| R02 | 🟢 | 死壳直删，先拆测试 import 再删壳；最坏响亮 ImportError |

---

## 🔴 R52 — 唯一硬红：灵魂线覆盖一次性蒸发 + 收口异常类不等价

**灾难链（裸删 impl）→** 删 `core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids` impl
→ R25 垫片 `core/services/scheduler/graph/ready_queue.py:9` import 立即 ImportError
→ `tests/scheduler_graph/test_ready_queue.py:16`（经垫片 import）整模块收集失败
→ **整文件 31 个 def_test 一次性蒸发**（rg 实测 `rg -c "def test_"`=31，dossier 称 ~23 LIVE-only 是子集近似；裸删带走全部 31）
→ 其中 **4 条唯一 LIVE ValidationError 契约**（:299/302 `不能同时是固定`、:311/314 `大于等于 1`、:326/336 `rejects_unknown_link_scope`、:352/361 `固定/已完成工序冲突`）随之消失
→ **LIVE sgs_graph 行为覆盖静默清零**，测试不会变红（连收集都失败=红，但若有人改 conftest 跳过则静默）。

**收口等价反例（Q5，删前必证不可抹平）：**
- 全量版 raise `ReadyQueueContractError`（ValueError 子类，:16/20/22/…，实测 19 处 raise）；LIVE 版 raise `ValidationError(field="graph_ready_context")`（sgs_graph.py:22/24/26/…，实测 27 处 raise）。**异常类不同** → parity 须断言「均拒绝」，禁断言同类型。
- **None 输入分支不可 cross-check**：LIVE `_prepare_graph_ready_state` 对 None `return None` 不 raise；全量版无 None 入口。**两路必须分别写**，不可用差分 oracle 一行覆盖。
- 6 处差分 oracle（:275/278/281/284/296）当前 `_incremental == _full_scan == 字面量`，删全量版后 `_full_scan` 消失 → 必须先改成对 LIVE 路径字面量期望，否则 NameError。

**修正（前置+顺序，缺一即红）：**
1. owner 先裁方向 A（删）vs B（保留作差分 oracle + "我是故意的"注释）——owner_pending=true。
2. 方向 A：**先**新建 `tests/scheduler_graph/test_sgs_graph_ready.py`（实测 NOT EXIST），迁出 4 条 ValidationError 契约 + LIVE-only 用例 + 6 处差分 oracle 改字面量期望 → **再**删 impl+R25 垫片（同提交）。
3. 同提交退 `regression_scheduler_graph_lazy_runtime_contract.py:27` + `test_metrics_topology.py:140` 两处模块路径字符串断言（loud fail，非静默）。
4. 路径钉死：取代者 sgs_graph 在**算法层** `core/algorithms/greedy/dispatch/`，非 service。
**禁区**：ReadyQueueContractError 抛错链是 loud raise（P3 非 P4），保留即可，不改 raise、不加兜底。

---

## 🟡 条件可做（5 条）

### R25（条件：与 R52 同提交 + 晚于测试迁移）
service 垫片 11 行纯转发，本身无承重（lb=false，无标记）。但 `test_ready_queue.py:16` 经它 import；**先删垫片而 R52 未迁测试 → :16 ImportError**（loud，安全失败但中间态红）。命运由 R52 决策门定（R52=因 R25=果）。同提交退两处模块路径断言。不撞行号（algorithm 层 vs service 层物理隔离）。R25 owner_pending=false 但执行受 R52 决策门门控。

### R14（条件：LB01 承重先裁 + owner 裁 :328 迁移目标）
死门三件套生产零引用（rg 实测 core/web/data 死门符号 0 命中），删本身无生产风险。**但两处灵魂线热路径不等价（Q4/Q5 实证）：**
- 死门非 scenario 走 `resolve_existing_plan`（schedule_plan_query_service.py:141）→ 缺角色/明细 **loud raise**（`所选方案不存在`/`所选方案没有可查看的明细`）。
- 活门非 scenario 走 `resolve_plan`（:105）→ 缺角色 **静默 fallback_to_adopted**（:136 `status="fallback_to_adopted"`），**不 raise**。
**灾难链**：把 :328 候选灵魂线（test:348 `pytest.raises 所选方案没有可查看的明细`）直接平移到活门 `diagnose_resolved_plan_overdue` → 解析阶段被 fallback 吃掉 → 断言失败且「无静默回退」语义覆盖被悄悄丢掉=失忆债。
**修正**：:358 scenario 灵魂线（两门同源）可平移；:328 候选须 owner 裁断改钉 `resolve_existing_plan` 层，**不可**平移到活门 diagnose 入口。删前三步前置（迁灵魂线/改 roadmap.md:485-498+items.yaml:83/确认无树外调用）。
**铁律 4**：删死门**不得**顺手修 `resolve_plan:136` 静默回退隐患（那是独立债）。跨簇 LB01（同符号 `_resolve_strict_plan:134`）承重裁断必须先行，R14 删 :134 让位。

### R24（条件：先调和 networkx roadmap + 不走路 B）
core 死副本 82 行生产零消费（rg 实测 core/web/data 零命中，唯一外部 import 是 tests）。**路 A（删 core）影响有限**。**路 B（把活 web 路径改指 core 合同）= 🔴级隐患**：core 对 NaN/Inf/bool 是「静默透传」（`value: value`），web 孪生 `safe_int/safe_float` 是 **loud raise NonFiniteDiagnosticNumber**（helpers:101/127/144，raise :131/139/141/148/152/154）；路 B 把活路径改指零消费 core = **丢护栏退化为静默吞坏值，踩 P4**，且把零消费 core 立为收口点违铁律 5，须另立 P5。
**修正（路 A）**：① 先改 `networkx-...items.yaml:435 primary_paths` 移 core + :480 ruff/:481 pyright **只摘 core 文件名**（保留同命令 web helpers 路径，否则 PR-9 exit_check 引用死文件门禁报错）+ 加 note；② 删 core 整文件；③ 测试**逐条剪**：删 :9-13 core import + :19/:63/:74 三纯 core 用例，**混合用例 :82 仅删首行 :83** 保留 :84+ web 断言。
**禁区**：web 孪生护栏 `NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144`/`build_item:41`/`build_section:62` 绝不反删。

### LB08（条件：承重只补注释 + 注释产出点待裁）
承重 true，legacy 正则反解桥。修法**仅补注释+绑契约**，绝不删/统一/透传。**灾难链（若误碰）**：删正则桥 → `legacy_public_error_message` 对 legacy 中文串 fullmatch 全失配 → 静默降级通用文案 + code 丢失（P4 静默回退）。
**owner_pending#1（实证）**：planned 注释草稿指向 `auto_assign_resource_errors` 是**消费/反解方**；真产出点是算法层 `internal_operation.py:119/148/150/154` + `dispatch/resource_validation.py:86`（rg 实证）。注释逐字贴入会指错文件。
**前置**：LB08 注释先落（钉死承重边界）→ R46 才在保护下删。绑已存在契约 `regression_scheduler_user_visible_messages.py:678`(+695/721/743/758)。禁区 :62/:94/:142/:175/:218/:284/:340。

### R06 + R27（条件：四包+gantt 同一原子提交）
四空包 0 字节、生产零引用。**碰撞点是同一 SP05 测试同两行**（:310 七元组 / :315 四元组循环）。**灾难链**：逐增量摘 → 中间态（七元组→六元组），第二次按过时行 old_string 匹配失配/误删；或删目录漏改 SP05 → `package_dir.is_dir()` 红（loud）；或漏删某包却整删 :315-316 循环 → 该空包失 `_assert_init_has_no_imports` 守卫=未来塞 import 不被发现（静默劣化）。
**修正**：R06(dispatch)+R27(calendar/batch)+gantt 一次性把 :310 改 `("config","run","summary")`、删 :315-316 整块。**禁区**：`_assert_init_has_no_imports` 定义 :173（:409 web 域仍调用，删块只删 :315-316 调用、保留 :173，否则 NameError）；:310 内 config/run/summary 真包只留不摘。

### R46（条件：LB08 注释先落 + 三锁定避同名陷阱）
死别名 `_safe_identifier`（:163）生产/测试零引用。**同名陷阱（实证）**：`v4_sanitizers.py:37 _safe_identifier` 是独立函数（Optional[str]，:121/:122 活引用），误删 → v4 迁移 SQL 标识符无清洗、迁移崩。
**修正**：文件+行号+符号三锁定删 `scheduler_public_errors.py:162-164`。LB08 插注释后行号 +N，**按符号重新 grep 不照搬 :162-164**。禁区 :62/:94/:142/:167(R09)/:175/:218/:284/:340。R46 删段不触 `__all__`（_safe_identifier 不在表内），与 R01/R19 物理不重叠、顺序不敏感。

---

## 🟢 安全（1 条）

### R02 — 死壳直删
test-only re-export 壳 `build_first_wave_ready_nodes`（schedule_graph_dispatch_context.py:461）生产零消费（rg 实证），真 impl 在 resource_matching_context.py:48 挂 __all__。**顺序**：先拆 `test_graph_dispatch_context.py:10-15` 4 符号 import 块（**只**把 :11 单符号改指 resource_matching_context，后三符号 :12/:13/:14 留原路径，否则 ImportError）→ 再删壳 :461-475。最坏响亮 ImportError 无静默炸。**禁区**：兄弟壳 `build_graph_resource_matching_projection:478`（report.py:180 唯一生产消费=事实承重）不连删；resource_matching_context.py:28-45 `GraphInputContractError` 灵魂守卫不碰。lb=false，分层 0 违规。

---

## 漏项（本轮新发现，计划未覆盖/前置缺失）

1. **R52 测试规模 dossier 低估**：dossier/簇文件称「~23 LIVE 测试」，rg 实测 `test_ready_queue.py` 共 **31 个 def_test**。裸删带走全部 31（含 4 条 ValidationError 契约 + 12+ ReadyQueueContractError 契约用例 + 6 差分 oracle），非 23。迁移清单须按 31 全量盘点，否则漏迁的契约用例随删消失=静默丢覆盖。计划「迁 23」措辞须更正为「全文件 31 用例分流：LIVE→新文件，全量版差分→改字面量期望」。
2. **R52 异常类不等价已被簇文件登记但 None 分支双路要求易被执行者忽略**：差分 oracle 思维惯性会诱导执行者继续写 `incremental==full_scan`，而 full_scan 已删。须显式在迁移指引里写「6 处 oracle 改为对 LIVE 字面量直断，删 `_full_scan_ready_ids` helper（:79）」——簇文件未点名 helper :79 须同删。
3. **R24 路 B 的 P4 风险是全簇最隐蔽的静默爆点**：若 owner 误选路 B，测试可能仍绿（core 合同被新接入时 NaN 透传不报错），但生产 analysis.html 渲染坏值=静默失真。建议在 owner 裁断材料里**默认推路 A**，路 B 强制前置「护栏先下沉 core + 补 NaN/Inf/bool 三 parity 反例」，否则不放行。
4. **R14 的 :328 迁移目标若 owner 久拖，R14 会卡死整个 B11 收尾**：LB01 承重裁断 + owner 裁 :328 是双重门，二者任一不决则 R14 不可删。计划应显式标 R14 为「双门 owner_pending」，避免排批时误当单门叶子。
