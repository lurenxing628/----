# 逐簇爆炸对抗 · C-GRAPH-ERR-DIAG · LAYER 透镜 · r1

> skeptic 第1轮，只读不改。主透镜：分层导入环 + 迁移耦合（Q2/Q3）。默认怀疑。
> 行号经 2026-06-05 rg 回盘。成员债 9：R02 R06 R25 R27 R52 LB08 R46 R14 R24。

---

## 逐债判定

### R02 — 🟢 绿（安全）
- test-only re-export 壳 `schedule_graph_dispatch_context.py:461-475`，生产零消费（rg 实证仅测试 3 处）。
- Q2 分层：删的是 :468 **函数体内懒 import**，模块级 `resource→dispatch` 单向边不变；三文件同层 `run/`，0 越层 0 新环。绿。
- 最坏路径全是响亮 ImportError（先拆测试 import 再删壳即可），无静默。禁区：兄弟壳 `build_graph_resource_matching_projection:478`（report.py:180 承重）、灵魂守卫 `GraphInputContractError`（resource_matching_context.py:33/:43）不碰。

### R06 + R27 + gantt 空包 — 🟡 黄（条件：四包必须同一原子提交）
- 三方共改 **同一** SP05:310 元组 + :315-316 delayed 循环。逐增量摘 → 中间态七元组→…，第二次 old_string 失配/误删。
- Q3 迁移耦合：**非 DB 迁移**——"V22" 是批次代号，`migrations/v22.py` 不存在，零 schema 改动（已回盘证实）。无 DB CHECK 探针风险。
- 条件：(a) 一次性把 :310 改 `("config","run","summary")`、整删 :315-316，同提交删 dispatch/calendar/batch/gantt 四目录；(b) 禁删 `_assert_init_has_no_imports:173`（:409 web 域仍调，连删→NameError）；(c) 禁摘 config/run/summary 真包。满足即绿。

### R52 + R25 — 🔴 红（裸删/序错会炸；R52 决策门未裁）
- **灾难链**：直删算法层 impl `ready_queue.py:103` + R25 service 垫片 → `test_ready_queue.py:16` 经垫片 import 立即 ImportError → 整文件 ~23 个 LIVE sgs_graph 用例（同文件 :7 直 import sgs_graph）+ 三条唯一 ValidationError 契约（:299/:326/:361）一次性蒸发 → LIVE 图排产校验覆盖静默归零，下次回归绿但护栏已破。
- Q2 分层：删 service→algorithm 边只减不增，0 新环（绿）。**红点在测试迁移序 + parity，非分层**。
- 条件（红转绿）：① owner 先裁方向 A/B（owner_pending=true）；② 走 A 须先新建 `tests/scheduler_graph/test_sgs_graph_ready.py`（实测不存在）迁 23 测试 + 3 契约 + 6 处差分 oracle(:275/278/281/284/296) 改 LIVE 字面量期望，再删 impl+垫片，R25/R52 同提交；③ parity 反例不可抹平：坏 op_id 全量版 raise `ReadyQueueContractError`(:32) vs LIVE raise `ValidationError(field=graph_ready_context)`(:26)——异常类不同，须断"均拒绝"非"同类型"；None 输入 LIVE `_prepare_graph_ready_state:38 return None` 不 raise，全量版无 None 入口，该分支两路分别写。④ 同步退 lazy_runtime:27 / metrics_topology:140 模块名枚举。

### LB08 + R46 — 🟡 黄（条件：LB08 注释先落 + R46 按符号重定位 + 同名陷阱）
- LB08 承重 true：正则桥把已渲染中文串反解回 code，与 make_public_error 并存。**只补"我是故意的"注释 + 绑已存在契约 regression_scheduler_user_visible_messages.py:678**，绝不删/统一/透传（删→legacy 串 fullmatch 失配→静默降级通用文案+code 丢失，P4 红区）。
- R46 死别名直删 `:163-164`（`_safe_identifier` 死壳）。**同名陷阱已实证**：`v4_sanitizers.py:37 _safe_identifier` 是独立活函数（:121/:122 活调用），绝不能误删。
- Q2 分层：纯 leaf model 仅 import re+typing，注释/删行 0 新 import 0 环（绿）。
- 条件：① LB08 注释先落钉死承重边界，R46 才删；② LB08 插 N 行使 :163-164 下移、R46 删 3 行使 :175/:218/:284/:340 上移——R46 落地后**务必按符号 grep 重定位不照搬旧值**；③ 注释逐字文案产出点待裁（真产出点 internal_operation.py:119/148/150 + resource_validation.py，**非** auto_assign，已回盘）。禁区 :62/:94/:142/:175/:218/:284/:340 零重叠。

### R14 — 🔴 红（裸删/迁错落 fallback 静默吞错；LB01 让位未裁）
- 死三件套 `diagnose_plan_overdue:42 / diagnose_batch:114 / _resolve_strict_plan:134` 确 prod-unwired（report_engine 仅调活门 `diagnose_resolved_plan_overdue:56`，已实证）。
- **灾难链**：裸删或把 `:328` 候选灵魂线断言（期望 raise `所选方案没有可查看的明细`）平移到活门 diagnose 入口 → 活门非 scenario 走 `resolve_plan`(schedule_plan_query_service.py:127-139) **fallback_to_adopted 静默不 raise** → "候选角色无静默回退"灵魂线覆盖被悄悄吃掉 → 测试绿但 P4 护栏破（铁律4 违例）。
- Q2 分层：纯删 0 新 import 0 环（绿）。红点在灵魂线迁移序 + 跨簇 LB01。
- 条件：① 跨簇 **LB01 承重裁断先行**（同符号 `_resolve_strict_plan`，R14 删 :134-139 让位/晚于 LB01）；② owner 裁 :328 候选灵魂线改钉 `resolve_existing_plan` 层（保严格语义脱离 diagnose 入口），:358 scenario 灵魂线两门同源可平移；③ 改 roadmap.md:485-498 + items.yaml:83 → diagnose_resolved_plan_overdue；④ **删死门不得顺手修 resolve_plan 静默回退隐患**（fix_invalidation，铁律4）。先迁后删。

### R24 — 🟡 黄（条件：路 A 不反删 web 孪生 + 先调和 networkx roadmap + 路径漂移纠正）
- core 死副本 `analysis/schedule_diagnostic_contract.py`（82 行）生产零消费；web 孪生 `scheduler_analysis_diagnostic_helpers.py` 独占灵魂线护栏 `NonFiniteDiagnosticNumber:101/safe_int:127/safe_float:144`（loud raise）承载全部活渲染。
- **路 B 即灾难**：把活 web 路径改指零消费 core 合同 = 丢非有限数字护栏退化静默吞错（NaN/Inf/bool 原样塞 dict，P4）+ 违"收口到已存在点"铁律5，须另立 P5、护栏先下沉。本债**只走路 A 删 core**。
- Q2 分层：core 叶子仅 import __future__/typing，0 出入边，删除 0 越层 0 环（绿）。
- 条件：① 先调和 PR-9 networkx-...-items.yaml:435/:480/:481（**只摘 core 文件名**保留 web helpers 路径，否则 exit_check 引用死文件门禁报错）；② 测试逐条剪不删整文件——删 :9-13 core import + :19/:63/:74 纯 core 用例，**混合用例 :82 仅删首行 :83 `empty_diagnostic_sections()`** 保留 :84+ web 断言；③ 禁碰 web 孪生护栏行。

---

## 漏项（本轮新发现，计划未覆盖/缺前置）

1. **【路径漂移·中】R24 簇头第 5 行 + dossier 标题路径不一致**：cluster 头 `主要文件` 列 `schedule_diagnostic_contract.py` **无 `analysis/`**，真实路径是 `core/services/scheduler/analysis/schedule_diagnostic_contract.py`（dossier 字段1已纠、find 实证）。Layer4 出批次命令时若照簇头裸名做 `rm`/exit_check 会找不到文件。须以 `analysis/` 全路径钉死。

2. **【序错·中】test_ready_queue.py 是 R25 与 R52 的共同唯一爆点，但 import 双源易漏**：该文件 :16 经 **R25 service 垫片** import `get_ready_operation_ids`，同时 :7 直接 import sgs_graph LIVE 批——删 R25 垫片单独就会让 :16 红（即便 R52 暂不删 impl）。计划把 R25「删垫片」与 R52「删 impl」标同提交是对的，但须强调：**:16 这一行删垫片前必须改指算法层 `core.algorithms.greedy.dispatch.ready_queue` 或随 R52 整体迁走**，否则即便方向 B（保留 impl 作 oracle）也会因删垫片炸 :16。

3. **【契约行号·低】R52 三契约行号回盘微漂**：dossier/计划记 `:302`（不能同时是固定），实测 `test_graph_ready_state_rejects_schedulable_fixed_overlap` 在 **:299**（:302 是其 `pytest.raises` 行）；另 `:311 rejects_non_positive_fixed_op_id`（match "大于等于 1"）是计划未列的**第四条** LIVE ValidationError 契约。迁移时按符号名而非旧行号抓，且勿漏 :311。

4. **【无】Q3 DB 迁移耦合本簇全空**：本簇 9 债无一触 schema/v18·v19 DB CHECK；"V22" 是批次代号非迁移脚本。adopted-only v19 CHECK 与本簇零耦合，无启动探针炸点。主透镜的"迁移耦合"维度在本簇判绿。
