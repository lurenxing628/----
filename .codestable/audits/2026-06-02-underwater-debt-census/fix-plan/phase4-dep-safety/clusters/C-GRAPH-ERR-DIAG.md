# 簇 C-GRAPH-ERR-DIAG · 原子簇重建

> 只读不改、只产计划。行号均经 2026-06-05 rg 回盘，不信旧值。
> 成员债 9：R02 R06 R25 R27 R52 LB08 R46 R14 R24
> 主要文件：schedule_graph_dispatch_context.py / ready_queue.py(两层) / scheduler_dispatch 空包 __init__.py / scheduler_public_errors.py / schedule_delay_diagnosis_service.py / schedule_diagnostic_contract.py

---

## A. 原子子簇拆分（必须同批/同提交 vs 可独立）

本簇 9 债横跨 5 个物理收口点，**不是一个原子团**，而是 **5 个互不撞行号的独立原子子簇** + 2 个跨簇决策门。逐个拆：

### 子簇 A1 — R02（独立单债，可任意时点最先落）
- **成员**：R02。
- **2026-06-08 B 执行终态**：已 fixed。测试 import 已拆分到真实实现，dispatch_context 的 `build_first_wave_ready_nodes` 转发壳已删除；兄弟壳与 `GraphInputContractError` 守卫未动。
- **原子原因**：无。R02 主文件 `schedule_graph_dispatch_context.py:461-475`（test-only re-export 壳），生产零消费，与本簇任何成员**不同物理文件、不同收口点**。registry 标的 `R02↔R25 same_file` 是假边（见 C 节）。
- **已完成的内部顺序（历史执行记录，勿重复处理）**：
  1. 已先拆 `tests/scheduler_graph/test_graph_dispatch_context.py:10-15` 的 4 符号 import 块——**只**把 `build_first_wave_ready_nodes`(:11) 单拎改指 `schedule_graph_resource_matching_context`(真 `__all__` home :132)；`build_graph_resource_matching_projection`(:12,兄弟活壳)/`build_predecessor_successor_maps`(:13,:396 真定义)/`graph_score_weights`(:14,:41 真定义) 三符号**留在原 dispatch_context import**。严禁整块换路径（后三符号在 resource_matching_context 不存在 → ImportError）。
  2. 已后删壳 :461-475（连 476-477 收尾空行）。
- **禁区**：兄弟壳 `build_graph_resource_matching_projection`(:478，report.py:180 唯一生产消费=事实承重)不可连删；`schedule_graph_resource_matching_context.py:28-45` 灵魂守卫 `GraphInputContractError` 不可碰（删的是 dispatch 层壳，守卫在 resource 层 impl）。

### 子簇 A2 — R06 + R27 + gantt 空包（**强制同一提交**）
- **成员**：R06(dispatch 空包)、R27(calendar+batch 空包)、gantt 空包(无独立 id，V22 同批带走)。
- **原子原因**：**同收口点同两行**。三方都改 `tests/gate_meta/test_sp05_path_topology_contract.py` 的**同一 :310 存在性循环行**（`for package_name in ("config","run","summary","batch","dispatch","gantt","calendar")`）和**同一 :315 delayed 循环行**（`for delayed_package in ("batch","dispatch","gantt","calendar")`）。逐增量摘会产生中间态（七元组→六元组→…），第二次提交按过时行内容 old_string 匹配会失配/误删。空包目录本身是不同目录的不同 `__init__.py`、互不撞行号，但 SP05 两行是物理同改点。
- **内部顺序**：**无先后，只有「四包同提交」单一安全顺序**——一次性把 :310 改成 `("config","run","summary")`、:315-316 整块删除，同提交删 dispatch/calendar/batch/gantt 四目录。
- **禁区行（删块时绝不越界）**：`:173 def _assert_init_has_no_imports`（:409 web 空域循环仍调用，连定义删→NameError）；:310 元组里 `config/run/summary`（真业务包）只保留不摘；:318 起 lingering/strong-compat 断言不碰。

### 子簇 A3 — R52 + R25（**同提交**；R52 决策门先行）
- **成员**：R52(算法层 `core/algorithms/greedy/dispatch/ready_queue.py:103` impl body)、R25(service 层 `core/services/scheduler/graph/ready_queue.py` 11 行垫片 shell)。
- **原子原因**：**同符号 `get_ready_operation_ids` 的 shell+body**。impl 一删，垫片 :9 import 立即 ImportError；二者必须同一提交。两文件物理隔离（algorithm 层 vs service 层），不撞行号、无 dict 键位移。
- **内部顺序**：
  1. **R52 决策门先裁**（R52 owner_pending=true）：方向 A(删 impl+垫片) vs 方向 B(保留作 incremental-vs-fullscan 差分 oracle 加「我是故意的」注释)。R25 命运由 R52 决定。
  2. 若走方向 A：**先迁约 23 个 LIVE-only sgs_graph 测试 + 三条唯一 ValidationError 契约**（test_ready_queue.py :302/:326/:361）到新建 `tests/scheduler_graph/test_sgs_graph_ready.py`（当前不存在），并把 6 处差分 oracle(:275/278/281/284/296)改成对 LIVE 路径字面量期望；6 处迁完后再删 impl+垫片。**绝不裸删整 test_ready_queue.py**（裸删 = LIVE sgs_graph 行为覆盖一次性蒸发）。
  3. 同提交退两处模块名枚举：`regression_scheduler_graph_lazy_runtime_contract.py:27`、`test_metrics_topology.py:140`。
- **parity 反例（删前必证，不可抹平）**：全量版坏 op_id raise `ReadyQueueContractError`，LIVE 版 raise `ValidationError(field=graph_ready_context)`——**异常类不同**，parity 须断言「均拒绝」而非「同类型」；None 输入 LIVE `_prepare_graph_ready_state` `return None` 不 raise，全量版无 None 入口，**该分支不可 cross-check，须两路分别写**。
- **路径钉死**：取代者 sgs_graph 在**算法层** `core/algorithms/greedy/dispatch/`，非 service 目录（纠 registry phase1_blast 误标）。roadmap 备忘措辞勿误指 service。

### 子簇 A4 — LB08 + R46（**承重先于动同文件**；LB08 注释先落）
- **成员**：LB08(承重 true，legacy 正则反解桥，`scheduler_public_errors.py:62` 上方插注释 + 绑契约)、R46(死别名直删 `:162-164`)。
- **原子原因**：**同物理文件 `core/models/scheduler_public_errors.py`，且 LB08 注释钉死承重边界后 R46 才能在保护下删**。两段物理分离（:61/:62 插入点 vs :162-164 删除段），不撞 dict 键，但**双向行号位移**：LB08 插 N 行使 :162-164 下移；R46 删 3 行使 :175/:218/:284/:340 上移——互不抵消但都让对方绝对行号失效。
- **内部顺序**：**LB08 注释先落（或同提交先于 R46 删行）**。LB08 owner_pending=true（注释逐字文案的产出点指向待裁：planned_fix 草稿指 `auto_assign_resource_errors.py` 错位，真产出点是 `core/algorithms/greedy/internal_operation.py:119/148/150/154` + `dispatch/resource_validation.py:86`）。R46 落地后行号 +N，**务必按符号名重新 grep 定位 :162-164，不可照搬旧值**。
- **承重禁区行（R46 删时神圣）**：`LEGACY_PUBLIC_PATTERNS:62`、`_LEGACY_CODE_PREFIXES:94`、`public_safe_identifier:142`(活,8 处消费)、`make_public_error:175`、`legacy_public_error_message:218`、`infer_legacy_public_code:284`、`_positive_int:167`(R09 同文件,跨簇)、`__all__:340-`(LEGACY 导出 :342/:345/:346)。R46 删段 :162-164 与全部禁区零重叠。
- **同名陷阱**：`v4_sanitizers.py:37 _safe_identifier`(独立函数,:121/:122 活调用)绝不能误删。

### 子簇 A5 — R14（独立单债，owner 裁迁移目标 + 跨簇 LB01 让位）
- **成员**：R14（延期诊断死三件套 prod-unwired，`schedule_delay_diagnosis_service.py:42/:114/:134`）。
- **原子原因**：无同文件兄弟（主文件独占，same_file_siblings=[]）。但**非裸删**——owner_pending=true，删前三步前置 + 跨簇 LB01 同符号让位（见 B 节）。
- **内部顺序（前置三步，全完成方可删 :42-54+:114-139）**：① 迁灵魂线测试（:358 scenario 可平移；:328 候选**不可**平移到活门 diagnose 入口——活门非 scenario 走 `resolve_plan` 静默 fallback_to_adopted 不 raise，owner 须裁把「无静默回退」断言改钉 `resolve_existing_plan` 层）；② 改 roadmap：`aps-three-gap-directions-roadmap.md:485-498` 签名块 + `items.yaml:83` exit_check → diagnose_resolved_plan_overdue；③ 人确认无树外调用。**删死门不得顺手当作修复 resolve_plan 静默回退隐患**（铁律 4）。

### 子簇 A6 — R24（独立单债，owner 裁删 vs 重构 + 跨簇 networkx roadmap 先调和）
- **成员**：R24（`schedule_diagnostic_contract.py` 82 行零消费孪生副本，ISOLATED）。
- **原子原因**：无（same_file_siblings=[]、interference_edges=[]）。owner_pending=true：路 A(删 core 死副本) vs 路 B(立 core 为收口点=新建收口点，违铁律 5，须另立 P5)。
- **内部顺序（路 A）**：① **先调和 PR-9 networkx roadmap**（`networkx-...-items.yaml:435 primary_paths` 移 core 文件、:480 ruff/:481 pyright 命令**只摘 core 文件名**保留 web helpers 路径、加 note）；② 删 core 整文件；③ 测试**逐条剪不删整文件**：删 :9-13 core import、删 :19/:63/:74 三纯 core 用例、**混合用例 :82 仅删首行 :83 `assert empty_diagnostic_sections()==[]`** 保留 :84+ web 断言。
- **禁区（绝不碰 web 孪生）**：`scheduler_analysis_diagnostic_helpers.py` 灵魂线护栏 `NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144` + raise 行 + `build_item:41`/`build_section:62`（活渲染唯一护栏）。

## B. 跨簇边（本簇成员指向【其他簇】债）

| 本簇债 | 指向他簇债 | 关系类型 | 顺序 |
|---|---|---|---|
| **R52** | **R50**(@sgs.py 同文件) | 同文件非同符号弱边 | R52 不动 sgs.py（impl 在 ready_queue.py），无真撞；仅簇内共现登记，**无硬序**。 |
| **R46** | **R09**(@scheduler_public_errors.py `_positive_int:167`) | 同文件、行号协调（修A失效B=否，仅位移） | R09 前置 F3 门（收口点 `parse_positive_execution_int` 已存在，见 C 节降级）落地远晚于 R46。**R46 先删 → R09 后续动 :167 时按符号 grep 重定位**。clamp-to-0(:172) ≠ None-语义 sink，R09 owner 勿误并。 |
| **R46** | **R01 / R19**(@`__all__` 同符号块) | 同 `__all__` 块同居，非同行编辑 | R46 删段 :162-164 **不触 `__all__`**（`_safe_identifier` 本就不在表内）→ 与 R01/R19 编辑物理不重叠，**顺序不敏感、可任意先后**。 |
| **LB08** | **R04 / R09**(@auto_assign_resource_errors.py / scheduler_public_errors.py) | 同文件非同符号 | LB08 纯插注释不删，禁区不重叠；R04/R09 各自动各自段。**无硬序**。 |
| **R14** | **LB01**(@schedule_delay_diagnosis_service.py `_resolve_strict_plan` 同符号) | **承重先于动同文件 + 修A可能违B禁区** | **最硬跨簇前置**：R14 删 `_resolve_strict_plan:134-139` 前，LB01(承重)若禁区覆盖该符号则 R14 删除违 LB01 禁区。**R14 删除必须让位/晚于 LB01 承重裁断**。 |
| **R14** | **LB02 / LB05 / R61**(@report_engine.py) | 同文件非同符号（迁测试触碰邻域） | R14 迁灵魂线到活门时触碰 report_engine.py 邻域，LB02/LB05 若锁某段须避让；R61 低-中文件级共改。**非承重直撞，避让即可**。 |
| **R24** | **R14**(共享「先动 roadmap 再删」范式) | 范式相同、roadmap 文件不同（R24=networkx / R14=aps-three-gap） | 无文件级硬边，**可并行**。 |

> 簇内无跨子簇硬边：A1–A6 五个原子子簇彼此**不同物理文件、不同收口点**，可并行调度（各自满足内部顺序/前置即可）。

## C. 相对旧 146 边的变化（删/新/降）

### 删除（误标假边，corrections B 节 + dossier 回盘双证）
- **删 R02↔R25 `same_file`**：registry interference_edge 标 `{R02,R25,same_file:true,@schedule_graph_dispatch_context.py}` **误**。回盘：R25 primary_file = `core/services/scheduler/graph/ready_queue.py`，R02 = `schedule_graph_dispatch_context.py`，**不同文件**。downstream「删 dispatch→matching 模块边」实为函数内懒 import(:468)非模块级边。→ 该边删除，R02 与 R25 仅同簇 C01 弱共现，调度互不争行号。

### 新增（registry 未登记、本轮回盘补的真协同点）
- **新 R06+R27+gantt「同 SP05 两行」原子边**：registry 把 R06/R27 标 `same_file_siblings`（basename `__init__.py` 撞名）+ ISOLATED，**漏标真碰撞点**——三方实改 `tests/gate_meta/test_sp05_path_topology_contract.py` 同 :310/:315 两行。本簇据 dossier §5/§6 升为「四包必须同一原子提交」硬边（gantt 无独立 id 由二者带走）。
- **新 R24 测试 :82/:83 单行剪除点**：registry phase1_blast 只说「移 :10-13 core import + 3 个 core-only 用例」，**漏标**混合用例 :82 首行 :83 `empty_diagnostic_sections()` 须单行剪除（corrections A 节 R24 已锚定）。

### 降级
- **R46→R09 由「同文件硬边」降为「软位移协调」**：二者无调用关系(fix_invalidation=none)，R09 收口点 `parse_positive_execution_int` **已存在**(corrections A 节 R09)，前提「批准新建 parse_optional_positive_int」作废；R46 与 R09 仅行号位移协调，非硬阻塞。
- **R14→LB01 维持承重硬边**（不降）：同符号 `_resolve_strict_plan`，R14 让位 LB01。

### 本簇 fixed 影响（E 节详）
- **2026-06-08 B 执行后补登：R02 已 fixed。** 其余 R06/R25/R27/R46 owner_pending=false 仍按计划给终态；R52/LB08/R14/R24 owner_pending=true 待裁。LB03/LB06/R07/R16/R56/R57 已 fixed，均不在本簇，仍不门控本簇任何结构动作。

## D. 承重前置（LB/N1/N2/R03/R58 门控的结构动作 + 禁区行）

本簇唯一**簇内**承重点 = **LB08**（load_bearing=true）；唯一**跨簇**承重门 = **LB01**（他簇，门控 R14）。N1/N2/R03/R58 不在本簇。

### LB08（簇内承重，门控 A4 子簇 R46）
- **必须先落的承重动作**：在 `scheduler_public_errors.py:62` 上方(:61 空行)插「我是故意的」护栏注释（钉死三件事：①正则把已渲染中文串反解回 code，与 make_public_error 结构化产出并存；②文案与正则同生共死，改文案不同步正则=静默降级通用文案+code 丢失；③终态让老路径走 make_public_error 端到端带 code 后才删正则）+ 绑**已存在**契约 `tests/schedule/route_view/test_scheduler_user_visible_messages.py:678`(+:695/:721/:743/:758)。**绝不删/统一/透传正则桥**。
- **门控的结构动作**：R46 删 :162-164——LB08 注释先落，钉死承重边界后 R46 才删。
- **禁区行（动同文件 R46 时绝不碰）**：`:62 LEGACY_PUBLIC_PATTERNS`、`:94 _LEGACY_CODE_PREFIXES`、`:142 public_safe_identifier`、`:175 make_public_error`、`:218 legacy_public_error_message`、`:284 infer_legacy_public_code`、`:340- __all__`(LEGACY 导出 :342/:345/:346)。
- **owner_pending=true**：注释逐字文案产出点指向待裁（产出真点 = greedy/internal_operation.py + dispatch/resource_validation.py，非 auto_assign）。

### LB01（跨簇承重，门控 A5 子簇 R14）
- R14 删 `_resolve_strict_plan`(schedule_delay_diagnosis_service.py:134-139)前，**LB01 承重裁断必须先行**；在 LB01 放行前，:134-139 按「潜在禁区行」对待，R14 删除让位。

### 灵魂线（loud raise / 可观测）禁区——本簇删除动作绝不削弱：
- **R02 / A1**：`schedule_graph_resource_matching_context.py:28-45 GraphInputContractError` raise（:33/:43）。
- **R52 / A3**：`ready_queue.py ReadyQueueContractError` 抛错链 + LIVE `sgs_graph.py ValidationError`；方向 A 删全量版前须证 LIVE 校验不弱于全量版（dossier §7：LIVE 等价或更严，仅异常类不同）。
- **R14 / A5**：:328 候选「无静默回退」灵魂线不可被 fallback_to_adopted 吃掉（owner 须重钉 `resolve_existing_plan` 层）；删死门**不得**顺手修 `resolve_plan` 静默回退隐患。
- **R24 / A6**：web 孪生 `NonFiniteDiagnosticNumber` loud raise 护栏绝不碰；路 B 把活路径改指零消费 core 会退化为静默吞错（踩 P4），故路 B 须另立 P5、护栏先下沉。

### 分层 0 违规确认
全 9 债均为「纯删 / 插注释 / 退测试 / 改 yaml」，**不新增任何 import**，0 AST 越层、0 导入环。R25/R52 删 service→algorithm 边只减不增。

## E. fixed 成员残留动作（认账注释）

**本簇 9 成员中 R02 已于 2026-06-08 B 执行 fixed。** corrections E 节旧 fixed 态 = LB03/LB06/R07/R16/R56/R57，全部在他簇，**不门控本簇任何结构动作**。R02 只是 test-only 壳清理，不产生固定前置门；其余成员仍按上文顺序和 owner 裁决执行。

唯一与「认账」相关的是 LB08 本身要**新增**承重认账注释（D 节），但那是本簇待落的承重前置，非「fixed 前置已完成的残留动作」。

---

## 返回摘要

簇 C-GRAPH-ERR-DIAG | 原子子簇：6 个 — A1(R02 已 fixed)/A2(R06+R27+gantt 同提交)/A3(R52+R25 同提交,R52 决策门先)/A4(LB08→R46 承重先)/A5(R14 独立,LB01 让位)/A6(R24 独立) | 关键内部顺序：R02 已完成（历史步骤：先拆测试 import 再删壳，勿重复处理）；R06/R27/gantt 四包一次性同提交改 SP05 :310/删 :315-316；R52 先裁 A/B→先迁 23 测试+3 契约到新文件→再删 impl+R25 垫片；LB08 注释先落再 R46 删 :162-164；R14 三步前置(迁灵魂线/改 roadmap/确认)后删；R24 先调和 networkx roadmap 再删 core+测试单行剪 :83 | 跨簇边：R14→LB01(承重先,同符号 _resolve_strict_plan,硬)；R46→R09(_positive_int:167 软位移)/R01/R19(__all__ 块不撞)；R14→LB02/LB05/R61(report_engine 避让)；R24‖R14(roadmap 范式同可并行)；R52→R50(sgs.py 弱) | 边变化：删 R02↔R25(假 same_file)；新 R06+R27+gantt 同 SP05 两行原子边、R24 测试 :83 单行剪；降 R46↔R09 为软位移(R09 收口点已存在) | 承重前置：LB08 注释+绑 regression 契约先于 R46 删行(禁区 :62/:94/:142/:175/:218/:284/:340)；跨簇 LB01 裁断先于 R14 删 :134-139；灵魂线 raise(GraphInputContractError/ReadyQueueContractError/NonFiniteDiagnosticNumber/:328 无回退)全程不削弱；分层 0 违规
