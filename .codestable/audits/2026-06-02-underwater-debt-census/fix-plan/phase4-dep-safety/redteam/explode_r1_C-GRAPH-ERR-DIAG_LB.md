# 逐簇爆炸对抗 · C-GRAPH-ERR-DIAG · 主透镜【承重误删】· 第 1 轮

> 角色：承重误删对抗 skeptic（只读不改）。默认怀疑：任何「看着像该统一/DRY/对齐」落在承重不对称上即标红。
> 回盘日期 2026-06-05，所有 file:line 经独立 rg 回盘，不信旧值。
> 成员债 9：R02 R06 R25 R27 R52 LB08 R46 R14 R24
> 主透镜 Q1 + 六质问点全过。

---

## 回盘核对总表（本轮独立 rg，全部命中，零漂移）

| 债 | 关键符号 | dossier 标 | 本轮 rg 实测 | 漂移 |
|---|---|---|---|---|
| R02 | build_first_wave_ready_nodes 壳 | dispatch_context.py:461 | schedule_graph_dispatch_context.py:461 | 0 |
| R02 | 兄弟壳 build_graph_resource_matching_projection（承重） | :478 | :478，report.py:180 唯一生产消费 ✅ | 0 |
| R06 | dispatch 空包 | 0 字节 | 0 字节 ✅ | 0 |
| R27 | calendar/batch/gantt 空包 | 0 字节 | 全 0 字节 ✅ | 0 |
| R06/R27 | SP05 存在性元组 | :310 七元组 | :310 `("config","run","summary","batch","dispatch","gantt","calendar")` ✅ | 0 |
| R06/R27 | SP05 delayed 循环 | :315-316 | :315 四元组 + :316 _assert_init_has_no_imports ✅ | 0 |
| R06/R27 | 共享函数禁区 | :173 def，:409 web 复用 | :173 def，:409 web 域调用 ✅ | 0 |
| R52 | get_ready_operation_ids impl | ready_queue.py:103 | :103，__all__:138，ReadyQueueContractError:10 ✅ | 0 |
| R25 | service 垫片 | 11 行 :9/:11 | 11 行，:9 import / :11 __all__ ✅ | 0 |
| R52 | 迁移目标 | test_sgs_graph_ready.py 不存在 | NOT EXIST ✅ | 0 |
| LB08 | LEGACY_PUBLIC_PATTERNS | :62 | :62 ✅ | 0 |
| LB08 | _LEGACY_CODE_PREFIXES/make_public_error/legacy_msg/infer | :94/:175/:218/:284 | :94/:175/:218/:284 ✅ | 0 |
| R46 | _safe_identifier（models 死别名） | :163 | :163，零调用方 ✅ | 0 |
| R46 | 同名陷阱 v4_sanitizers | :37/:121/:122 | :37 def + :121/:122 活调用 ✅ | 0 |
| R14 | diagnose_plan_overdue/batch/_resolve_strict_plan | :42/:114/:134 | :42/:114/:134，活门 :56 ✅ | 0 |
| R14 | resolve_plan fallback vs resolve_existing_plan raise | :136/:157 | :105 fallback_to_adopted:136；:141 raise:157/163 ✅ | 0 |
| R24 | core 死副本 | 82 行四 def | :12/:25/:46/:73，__all__:77 ✅ | 0 |
| R24 | web 孪生护栏（禁区） | helpers:101/127/144 | NonFiniteDiagnosticNumber:101/safe_int:127/safe_float:144 ✅ | 0 |
| R24 | networkx roadmap 调和点 | items.yaml:435/480/481 | :435 primary_path + :480 ruff + :481 pyright ✅ | 0 |
| R14 | roadmap 调和点 | roadmap.md:485/492，items.yaml:83 | :485/:492，:83 ✅ | 0 |

**承重符号回盘全部坐实，无误删入口被悄悄打开。9 债的计划修法逐条审。**

---

## 主透镜 Q1 逐债判决（承重误删：统一/DRY/对齐落在承重不对称上即红）

### LB08 — 🟡 黄（承重，条件可做：注释先落 + 文案产出点更正）
- **承重事实坐实**：`scheduler_public_errors.py:62 LEGACY_PUBLIC_PATTERNS` 是 legacy 中文串→code 反解桥，与 `make_public_error:175`（结构化带 code 产出）**两代并存**，是产出↔解析桥**非双栈等价**。计划修法严格「补注释 + 绑已存在契约 `regression_scheduler_user_visible_messages.py:678`」，**无删/统一/透传**——符合铁律 3，不踩 Q1。
- **黄的条件（必须满足才放行）**：
  1. **注释逐字文案产出点指向错位（owner_pending=true 真因）**：planned 草稿指 `auto_assign_resource_errors.py`，但该文件是**消费/反解方**；真产出点本轮独立确认为 `core/algorithms/greedy/internal_operation.py:119/148/150/154` + `dispatch/resource_validation.py:86`。注释若逐字贴会把维护者指向错误文件→护栏失效→未来改文案不同步正则→**静默降级通用文案 + code 丢失（P4 红区）**。owner 须更正指向后再贴。
  2. **注释必须先于 R46 删行落地（或同提交先于）**：钉死承重边界后 R46 才能在保护下删 :162-164。
- **若违反（灾难链）**：跳过注释直接让某人后续「统一两代错误体制、把 legacy 正则桥删了走 make_public_error」→ legacy 中文串 fullmatch 全失配→ `legacy_public_error_message` 静默返回通用文案「排产执行遇到问题…」+ `infer_legacy_public_code` 返回空 code→用户可见错误丢失归类与具体工序→**静默失真**（呈现层，medium）。这正是承重不可轻删的根据，故必须先把「文案与正则同生共死」钉成显式护栏。

### R52 — 🔴 红（删全量版会连环炸：测试连坐蒸发 + parity 异类异常被抹平）
- **owner_pending=true，方向 A（删 impl+垫片）一旦走而前置不全 = 必炸**，灾难链：
  - **链 1（测试连坐蒸发）**：裸删 impl → R25 垫片 :9 import 立即 ImportError → `test_ready_queue.py:16` 经垫片 import 整文件 collection error → **三条唯一 LIVE ValidationError 契约（:302 不能同时是固定 / :326 rejects_unknown_link_scope / :361 固定·已完成冲突，本轮 rg 全部坐实）一次性蒸发**。注意：这三条契约本体 import 自 `sgs_graph`（:7）直接、断言 LIVE 行为，但它们与 `get_ready_operation_ids`(:16) 同文件，垫片一断 → 整模块红 → LIVE 覆盖陪葬。**这是「删的是死全量版，炸的是活 LIVE 覆盖」的承重不对称误删。**
  - **链 2（parity 异类异常被抹平）**：本轮独立验证 parity 反例成立——全量版 `ready_queue.py:16-100` 全程 `raise ReadyQueueContractError`(ValueError 子类)；LIVE `sgs_graph.py:22-66` 全程 `raise ValidationError(field="graph_ready_context")`，**异常类不同**。若 parity 测试图省事断言「同类型」→ 假绿掩盖差异 → 后续有人「对齐异常类、把 LIVE 也改 ReadyQueueContractError」→ 下游 `ValidationError(field=...)` 的 web 错误呈现链断裂。parity **只能断言「均拒绝」**。
  - **链 3（None 分支不可 cross-check）**：`sgs_graph.py:38-39 graph_ready_context is None → return None`（不 raise）；全量版无 None 入口。两路这一分支**不可互证**，差分 oracle 删后须两路分别写，否则漏覆盖。
- **前置（红转绿的唯一路径，缺一即红）**：① owner 先裁方向 A/B；② 走 A 须先迁 ~23 LIVE 测试 + 三 ValidationError 契约到**新建** `test_sgs_graph_ready.py`（确认不存在）；③ 6 处差分 oracle（:275/278/281/284/296）改 LIVE 字面量期望；④ 同提交退 `lazy_runtime:27`+`metrics_topology:140` 模块名枚举；⑤ R25 同提交。**绝不裸删整 test_ready_queue.py。**

### R25 — 🟡 黄（owner_pending=false 但命运绑 R52，须同提交 + 序对）
- 纯删 11 行垫片 + 退两枚举 + roadmap 备忘，承重 false、零生产消费（本轮 rg 证实仅 4 命中：impl 定义×2 + 垫片×2），不踩 Q1。
- **黄的条件**：① 必须与 R52 同提交（impl 一删垫片 import 红，反之先删垫片而 test 未迁则 :16 红）；② 删垫片前先迁/改 `test_ready_queue.py:16`、退 `lazy_runtime:27`/`metrics_topology:140`，**序错则 loud fail**（非静默，安全但破测试）；③ roadmap 备忘措辞勿误指 service 目录（取代者 sgs_graph 在算法层）。R25 实为 R52 决策门的果，R52 不裁 R25 不动。

### R46 — 🟡 黄（死别名直删，但同文件三承重 + 同名陷阱）
- 删 `:162-164` 死别名 `_safe_identifier`，本轮 rg 证实 models 版零调用方、不在 __all__、无动态引用 → 自身爆炸半径 0。
- **黄的条件（三锁定杜绝误删承重）**：
  1. **同名陷阱**：`v4_sanitizers.py:37 _safe_identifier` 是 infrastructure 层独立函数，被 :121/:122 **活调用**做 SQL 标识符 sanitize。误删 → v4 迁移 NameError/崩。删除范围必须文件+行号双锁 `scheduler_public_errors.py:162-164`。
  2. **承重禁区零重叠**：LB08 正则桥 :62/:94/:218/:284 + make_public_error:175 + public_safe_identifier:142 + _positive_int:167(R09 跨簇) + __all__:340 全部神圣，与 :162-164 物理分离。
  3. **行号位移**：LB08 注释先落使 :162-164 下移 N 行 → R46 落地时**必须按符号名重新 grep，不可照搬旧值**。
- 不踩 Q1（直删死别名非统一承重），但若手滑越界删 public_safe_identifier(:142，8 处生产消费) 即承重误删→ batch_id/op_code 渲染全崩。

### R14 — 🔴 红（删死门会静默丢「无静默回退」灵魂线 + 撞 LB01 承重）
- owner_pending=true。**死门 prod-unwired 零调用本身不炸，但删除动作牵动灵魂线覆盖**，本轮 parity 反例独立坐实：
  - **承重不对称铁证**：死门 `_resolve_strict_plan:134` 非 scenario 走 `resolve_existing_plan:141` → 角色明细缺失 `raise ValueError("所选方案没有可查看的明细"):157/163`（**无回退**）。活门 `diagnose_resolved_plan_overdue:56` 经 `_resolve_plan`→`resolve_plan_view`→非 scenario 走 `resolve_plan:105` → 角色缺失 `status="fallback_to_adopted":136`（**静默回退 adopted，不 raise**）。两门**非逐分支等价**。
  - **灾难链**：把候选灵魂线 `:328 reads_candidate_rows_without_fallback`（断言 :348 `pytest.raises ValueError 所选方案没有可查看的明细`，本轮 rg 坐实）裸平移到活门 diagnose 入口 → 解析阶段 fallback_to_adopted 不 raise → 断言失败 → 为「修复」改测试 → **「非 scenario 缺角色应 raise（无静默回退）」的灵魂线覆盖被悄悄丢掉**（静默债，踩 Q4）。
  - **撞 LB01 承重（跨簇硬边）**：`_resolve_strict_plan` 同符号在 R14 主文件 :49/:134，LB01（他簇承重）门控此符号。LB01 放行前 :134-139 按潜在禁区对待，R14 删除让位。
- **前置（红转绿）**：① LB01 承重裁断先行；② owner 裁 :328 候选灵魂线迁哪个活路径（候选语义仅 `resolve_existing_plan` 保 raise，须钉到 query 层）；③ scenario 灵魂线 :358（断言 :381 模拟方案明细不存在）两门同源可平移；④ 改 roadmap.md:485-498 + items.yaml:83；⑤ **删死门不得顺手当作修复 resolve_plan 静默回退隐患**（铁律 4）。

### R24 — 🔴 红（路 B 把活路径改指零消费 core = 灵魂线退化静默吞错）
- owner_pending=true，ISOLATED。**路 A（删 core 死副本）影响有限；但路 B（立 core 为收口点）= 承重误删的镜像陷阱**：
  - **parity 反例坐实**：core 死副本四 def 纯 dict 拼装、零 except（`schedule_diagnostic_contract.py:12/25/46/73`）；web 孪生独占灵魂线护栏 `NonFiniteDiagnosticNumber:101`/`safe_int:127`/`safe_float:144`（本轮 rg 坐实）。NaN/Inf/bool 三场景：core 静默透传 vs web loud raise → **非等价**。
  - **灾难链（路 B）**：owner 误判「DRY、让活 web 路径改指 core 合同」→ web build_item/build_section 改指零消费 core → **丢非有限数字护栏退化为静默渲染坏值（踩 P4/Q4）**。这是「收口到一个零消费副本 = 新建收口点违铁律 5」的典型。路 B 必须护栏先下沉 core + 补三反例 parity + 另立 P5，否则禁走。
- **路 A 前置**：① 先调和 networkx roadmap（本轮坐实 items.yaml:435 primary_path + :480 ruff + :481 pyright 三处列 core 文件 + web helpers 同命令）——只摘 core 文件名保留 web helpers 路径，否则裸删致 PR-9 exit_check 引用死文件门禁报错；② 删 core 整文件；③ 测试逐条剪：删 :9-13 core import + :19/:63/:74 三纯 core 用例 + **混合用例 :82 仅删首行 :83 `assert empty_diagnostic_sections()==[]`** 保留 :84+ web 断言；**绝不反删 web 孪生**。

### R02 — 🟢 绿（直删死壳，承重禁区已圈定）
- 本轮坐实：壳 :461 生产零消费；兄弟壳 build_graph_resource_matching_projection:478 被 report.py:180 唯一消费（承重禁区，不连删）；灵魂守卫 GraphInputContractError 在 resource_matching_context.py:28-45（删壳碰不到）。
- 内部两步序：① 先拆 `test_graph_dispatch_context.py:10-15` 四符号 import 块——**仅** :11 build_first_wave_ready_nodes 单拎改指 resource_matching_context（真 __all__ home），:12/:13/:14 三符号留原 dispatch_context import（本轮坐实 :12/:13/:14 在原块，:13 真定义在 dispatch_context.py:396、:14 在 :41）；② 后删壳 :461-475。**严禁整块换路径**（后三符号在 resource_matching_context 不存在→ImportError）。所有失败均 loud ImportError，无静默。绿。

### R06 + R27 — 🟢 绿（四空包同提交直删，禁区已圈定）
- 本轮坐实：四空包全 0 字节；SP05 :310 七元组 / :315-316 delayed 循环；共享函数 `_assert_init_has_no_imports:173` 被 :409 web 域复用（删 :315-316 调用块时**保留 :173 定义**，否则 :409 NameError）。
- 唯一安全顺序「四包同一原子提交」：一次性把 :310 改 `("config","run","summary")`、删 :315-316 整块，同删 dispatch/calendar/batch/gantt 四目录。**逐增量摘会产生中间态致第二次 old_string 失配**。config/run/summary 真包不摘。绿（所有失败 loud AssertionError/NameError，无静默）。

---

## 六质问点小结

- **Q1 承重误删**：LB08🟡（注释禁区咬合，文案产出点待更正）；R52🔴（删全量版连坐 LIVE 测试 + parity 异类异常须断「均拒绝」）；R14🔴（删死门丢「无静默回退」+ 撞 LB01）；R24🔴（路 B 改指零消费 core 丢护栏）；R46🟡（同名陷阱 + 同文件三承重禁区）；R02/R06/R27/R25 不踩。
- **Q2 分层导入环**：全 9 债纯删/插注释/退测试/改 yaml，0 新增 import，不击穿 0 违规。绿。
- **Q3 迁移耦合**：本簇无一与 schema CHECK/v18·v19 DB CHECK 耦合（R27 §12 已澄清「V22」是批次代号非 DB 迁移，无 schema 改动）。绿。
- **Q4 灵魂线热路径**：R14（候选灵魂线 fallback 吞）、R24（路 B 护栏退化）、LB08（文案不同步正则静默降级）三处是 P4 红区，均已在红/黄判决覆盖；**禁新增兜底/静默回退**。
- **Q5 收口行为等价**：R52 parity 反例（异类异常 + None 分支不可 cross-check）、R14 parity 反例（fallback vs raise）、R24 parity 反例（透传 vs raise）全部独立坐实，**不可抹平**。
- **Q6 测试迁移序**：R52（先迁 23 测试 + 3 契约到新文件再删 impl+垫片）、R25（test 先就绪再删垫片）、R02（先拆 import 再删壳）、R06/R27（四包同提交）——序错=测试红/复活兜底，均已锁定。

---

## 漏项（本轮新发现，没被簇计划完全覆盖的爆点 / 缺失前置）

1. **【中·别名 grep 纪律漏标】R24 networkx roadmap 调和**：本轮 rg 发现 items.yaml 的 :435/:480/:481 同时以 **别名 `core/services/scheduler/analysis/ln.py`** 形态出现（workflow 别名替换把 `schedule_diagnostic_contract` 显示为 `ln`）。簇计划只说「按 `schedule_diagnostic_contract` 名摘」，若执行者只 grep 原名会**漏掉别名行**导致只改一半。前置应补：R24 调和须同查 `schedule_diagnostic_contract` 与 `ln.py` 两种形态（呼应 _layer2_residual.md D2「别名 grep 纪律」，本簇 R24 未显式继承此纪律）。
2. **【低·R25 灾难链表述偏差，不改修法】**：R25 dossier §8 把 `metrics_topology:140` 漏摘说成「ModuleNotFoundError 红」，其对抗核验已自纠为「悬空残留不红」（该测试对 forbidden 列表不做 import_module）。影响：删垫片漏摘 metrics_topology 是**静默残留非 loud fail**——比 lazy_runtime:27（loud 红）更隐蔽，review 须显式核两处都摘。计划摘项动作正确，仅风险等级表述偏差。
3. **【低·R14 web 路由行号微漂】**：dossier 记 reports_page_support.py:230，对抗核验实测 :239。不影响消费关系，但 R14 落地「人确认无树外调用」一步须按符号重定位活门消费者，勿照搬 :230。
4. **【提示·R09 跨簇软位移】R46 删 :162-164 使 _positive_int 从 :167 上移**：R09（他簇）后续动 `:167` 须按符号 grep 重定位；且 :167 clamp-to-0(`int`) ≠ R09 收口点 None 语义（`Optional[int]`），勿误并。本簇 R46 不主动触 :167，登记供 R09 owner 警惕。

无新增承重误删入口被本轮放过。R52/R14/R24 三红的共性：**删/改的对象是死的，但承重/灵魂线覆盖活在邻接的测试或孪生里，序错或抹平 parity 即静默失效。**
