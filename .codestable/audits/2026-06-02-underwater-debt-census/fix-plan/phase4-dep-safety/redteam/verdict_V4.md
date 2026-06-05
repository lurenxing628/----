# Verdict V4 — 测试迁移/壳性质/monkeypatch 三争议裁定

> 裁定 agent，只读不改任何 .py。行号全部 rg 回盘（2026-06-05），不信旧值。
> 权威路径以 _layer2_residual.md 表为准。owner_pending 只标不给终态修法/不分配批次。
> 三争议：⑦R52 测试迁移清单重盘 · ②degradation 真实现 vs 壳 · ⑪R29 monkeypatch 指错文件修正

---

## 争议 ⑦：R52 测试迁移清单重盘（GRAPH-ERR-DIAG / B09 / owner_pending=true）

**【裁定】** 爆点对、dossier 错且方向倒置：`tests/scheduler_graph/test_ready_queue.py` 实测 **31 个 test 函数**（非 dossier 的「~23 LIVE」）；按 helper 重新分桶——**23 个走全量版 `_ready()`→`get_ready_operation_ids`（R52 待删 impl，删 impl 即全断），8 个走 LIVE `_prepare_graph_ready_state/_incremental`（sgs_graph）**。dossier 把「~23」安给 LIVE 是把多数桶贴反了标签：真正 LIVE-only 仅 8 个，要随删的全量版用例是 23 个（含 15 个 ReadyQueueContractError 合同），这 23 个 dossier 迁移方案根本没排归属。

**【证据】file:line**（rg + AST 回盘，31 个逐函数判桶）：
- 文件实测 **374 行 / 31 个 `def test_`**（`rg -c "^def test_"` = 31）。迁移目标 `tests/scheduler_graph/test_sgs_graph_ready.py` **确不存在**（`ls` NOT EXIST），与 dossier §2 一致。
- **桶 A — 全量版（FULLSCAN，经 `_ready()`:23→`get_ready_operation_ids`:31，删 R52 impl 即 ImportError/全断）= 23 个**：
  - 8 个正向行为：`:89/:95/:101/:107/:117/:128/:135/:146`（linear/fork/join/fixed/blocked，全调 `_ready()`）。
  - 15 个 **ReadyQueueContractError 合同**：`:156/:163/:168/:174/:179/:186/:191/:203/:208/:219/:230/:248/:253/:258/:263`（每条 `pytest.raises(ReadyQueueContractError, match=...)`，异常类是 RQErr ≠ LIVE 的 ValidationError）。
- **桶 B — LIVE sgs_graph（经 `_prepare_graph_ready_state`:65 / `_incremental_ready_ids`:68）= 8 个**：`:270/:287/:299/:311/:326/:340/:352/:365`。其中 **4 个是唯一 ValidationError 契约**：`:299`(不能同时是固定)、`:311`(大于等于 1)、`:326`(rejects_unknown_link_scope)、`:352`(固定/已完成工序冲突)——这 4 条是删全量版后唯一 LIVE 行为护栏，**必须存活**。
- **桶 C — 跨双路差分 oracle（同时调 `_incremental==_full_scan`）= 2 个**：`:270`(branch_join, `:275/:278/:281/:284` 字面量 `[1]/[2,3]/[3]/[4]`)、`:287`(fixed_predecessor, `:296`=`[2]`)。这 2 个**两路都用**，删全量版后 `_full_scan_ready_ids`:79 失效，须改写为仅对 LIVE 路径的字面量期望。
- import 头：`:7` `from ...sgs_graph import`（LIVE 批）、`:15` `from core.infrastructure.errors import ValidationError`、`:16` `from core.services.scheduler.graph.ready_queue import ReadyQueueContractError, get_ready_operation_ids`（经 R25 垫片→全量版）。

**最终迁移清单**（方向 A=收/删 才触发；owner 未裁前不动）：
1. **新建** `tests/scheduler_graph/test_sgs_graph_ready.py`。
2. **8 个 LIVE 用例（`:270/:287/:299/:311/:326/:340/:352/:365`）整体迁入**新文件——含 4 条 ValidationError 契约（`:299/:311/:326/:352`），保唯一 LIVE 覆盖。
3. **2 个差分 oracle（`:270/:287`）迁后改写**：删 `== _full_scan_ready_ids(...)` 段，断言收敛为对 LIVE 增量路径的字面量期望（`[1]/[2,3]/[3]/[4]`、`[2]`），失去 cross-check 可接受。
4. **23 个全量版用例（8 正向 + 15 RQErr 合同）归属 = owner 裁断门**：
   - **选项 A1（随 impl 同删，接受丢 ReadyQueueContractError 合同覆盖）**——前提须先逐分支证 LIVE 的 ValidationError 路径**语义已等价或更严**（不能用「均拒绝」一句带过；§7 已列反例：传图对象两路都 raise 但异常类不同，None 输入 LIVE `:38 return None` 不 raise 而全量版无 None 入口，这两个分支不可 cross-check）。
   - **选项 A2（把 15 个 RQErr 合同改写为对 LIVE ValidationError 的等价断言后迁入新文件）**——保住「坏输入被拒」覆盖，但断言须改异常类型且逐条核 match 文案，工作量大。
   - **建议**：8 正向行为用例随删（LIVE 8 个已覆盖等价正向场景）；15 个 RQErr 合同走 A2 选保留为 LIVE 契约（拒绝路径覆盖珍贵，不宜裸丢）。**【待 owner 裁 A1 vs A2】**
5. 删 R25 垫片时同步改模块路径字符串断言：`tests/regression_scheduler_graph_lazy_runtime_contract.py:27`、`tests/scheduler_graph/test_metrics_topology.py:140`（loud fail，非静默）。

**【对批次计划的影响】**
- **dossier §11 测试迁移清单须回写**：把「~23 个 LIVE-only sgs_graph 用例迁出」更正为「8 个 LIVE 用例迁出 + 23 个全量版用例（含 15 RQErr 合同）随删/改写归属待 owner 裁」。照旧 dossier 文字会误迁错桶。
- **owner 裁断门扩项**：原 owner_pending 只裁「方向 A 收 vs 方向 B 保留 oracle」；现须**增裁子门**：方向 A 选定后，23 个全量版用例中 15 个 RQErr 合同走 A1（随删丢合同）还是 A2（改写为 LIVE 等价断言保留）。
- **顺序/禁区不变**：R52→R25 co_change 同提交；impl `ReadyQueueContractError` 抛错链 loud raise（P3 非 P4）不改；lb=false 无禁区。本债仍**不进任何批次**直至 owner 裁断（铁律 7）。

---

## 争议 ②：degradation 真实现 vs 壳 自相矛盾拍定（COMPAT-DISPATCH，影响 R33/R26）

**【裁定】** 两方都对了一半，真相是「**活桥接壳**」：`core/services/common/degradation.py` 是 **17 行 / 385 字节的纯 re-export 壳**（`:3 from core.shared.degradation import (...)`，零 def/class）——r2-SOUL「17 行纯 re-export 壳」**字面正确**；真承重实现在 **`core/shared/degradation.py`（148 行 / 4618 字节，DegradationEvent/DegradationCollector + 2 函数）**。但这个壳**不是死壳**，有 **~13 个活生产消费者**经它 import——r1-LB/LAYER「20+ 生产直连真承重」是**把『经壳的活引用数』错记成『壳本身是实现』**，并把 385 字节误当作实现体量（385B 恰恰是壳的大小）。R33 dossier 对抗核验「不是壳是真实现 385B」**判错方向**：385B 文件就是壳，实现在 shared。

**【证据】file:line**：
- `core/services/common/degradation.py` 实测 **17 行 / 385 字节，def+class=0**，全文仅 `:3-9` 一条 `from core.shared.degradation import (STABLE_DEGRADATION_CODES, DegradationCollector, DegradationEvent, degradation_event_to_dict, degradation_events_to_dicts)` + `:11-17 __all__`。**纯 re-export 壳，铁证。**
- `core/shared/degradation.py` 实测 **148 行 / 4618 字节**，`:40 class DegradationEvent`、`:49 class DegradationCollector`、`:136 def degradation_event_to_dict`、`:147 def degradation_events_to_dicts`。**真实现在此。**
- **经壳的活生产消费者 ~13 处**（`from core.services.common.degradation import ...`）：`resource_sheet_builder.py:8`、`route_sheet_builder.py:7`、`template_builder.py:9`、`template_validation.py:5`、`schedule_summary_degradation.py:7`、`build_outcome.py:6`、`resource_dispatch_support.py:6`、`web/bootstrap/plugins.py:11`、`gantt_service_support.py:5`、`_sched_display_utils.py:6`、`resource_dispatch_rows.py:7`、`gantt_tasks.py:10`、`gantt_week_plan.py:6`、`gantt_service.py:6`。另有一批直连 `core.shared.degradation`（schedule_params:9、external_groups:8、config/* 等），不经壳。

**对 R33/R26 批次的影响裁断**：
- **R33 结论完全不变，但其 dossier §178 措辞须再纠**：R33 对抗核验把 degradation 改称「反例（真承重实现，非壳）」——**仍不准**。正确表述应为「**反例：活桥接 re-export 壳（壳在 services/common，实现在 core.shared，~13 活生产消费者经它进），与三死壳同处 common/ 但性质相反——它是『被生产经它进』的活兼容层，绝不能当死兼容壳删**」。`tests/regression_config_service_component_contract.py:15` 的 degradation 元组条目**死保不变**（删元组只动 `:14/:16/:19`，死保 `:15`）。
- **执行者认知反转点已堵**：dispute 提的「据『真实现 vs 壳』判断是否可删的认知会反转」——本裁定钉死：**无论叫壳还是实现，degradation 都不可删**（删壳→13 活消费者 loud ImportError；shared 实现更不能碰）。结论方向唯一。
- **R26 不受影响**：R26 是 scheduler/ 顶层 5 shim，与 common/degradation 无文件重叠；其字段 8 排除 `degradation` 出生产扫描口径正确（degradation 经的是 common/ 壳不是 scheduler 顶层 shim）。
- **爆炸半径修正**：_layer3 §128「两 facade 均无活生产消费者只有 3 测试 import」是讲 R30/R33 的 compat_parse/value_policies 壳——**不含 degradation 壳**；degradation 壳恰相反是 ~13 活消费者，不可混入「无活消费者」那批。

---

## 争议 ⑪：R29 monkeypatch 指错文件修正（COMPAT-DISPATCH / B05 / owner_pending=true）

**【裁定】** dossier/Layer1 指错文件，爆点 §11 对：R29 薄壳化前置的真 monkeypatch 续命点是 **`tests/regression_number_utils_facade_delegates_strict_parse.py` 的 `:45-48`**（把 number_utils 的 4 个 parse 函数替换为 fake 以验证「门面确实转调」）；dossier A4/Layer1 指的 **`regression_ortools_warmstart_failure_contract.py:136` 与 number_utils 毫无关系**——该处 `:136 test_ortools_nonfinite_hours_is_visible` monkeypatch 的是 **ortools/cp_model**（`sys.modules` 注 fake ortools），全文件零 number_utils 引用。照误指改 warmstart 会以为前置满足、实则真续命点没动。

**【证据】file:line**：
- 真文件 `tests/regression_number_utils_facade_delegates_strict_parse.py`（3978 字节）：`:19 from core.services.common import number_utils`；`:23-26` 存原函数（parse_required_float/optional_float/required_int/optional_int）；**`:45-48` 四行 rebind**（`number_utils.parse_required_float = fake_required_float` … `:48`）；`:57-60` restore；`:67` 断言 `number_utils 未转调 strict_parse 门面：{calls!r}`。这是「门面 delegation 身份测试」的本体。
- 误指文件 `regression_ortools_warmstart_failure_contract.py`（7621 字节）：`:136 def test_ortools_nonfinite_hours_is_visible(monkeypatch)`；该测试经 `_install_fake_cp_model`（`:53`）`monkeypatch.setitem(sys.modules, "ortools..." )`（`:81-84`）注 fake ortools。`rg number_utils` 在该文件 **0 命中**。**与 number_utils/R29 无关，铁证误指。**
- R29 本体 `core/services/common/number_utils.py`（44 行）= delegation-facade：`:5 from core.shared.strict_parse import (...)`，定义 `parse_finite_float`（:14/:19/:23 三 overload）、`parse_finite_int`（:31/:36/:40），转调 strict_parse。**真实现在 `core.shared.strict_parse`，本文件是全量委托门面。**
- R29 活生产消费者 = **2 处**（与 _layer3 §55 一致）：`core/services/common/excel_validators.py:26`、`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py:8`（后者只用 parse_finite_float）。**非死壳，薄壳化须同改这 2 处。**

**【对批次计划的影响】**
- **R29 dossier A4 / _layer1 续命点字段须回写**：`regression_ortools_warmstart_failure_contract.py:136` → 改为 `regression_number_utils_facade_delegates_strict_parse.py:45-48`。
- **薄壳化前置动作锚点重定**：R29 走 B（薄壳化）的前置 =「先把 `regression_number_utils_facade_delegates_strict_parse.py` 重写为身份测试（断 `number_utils.parse_finite_* is core.shared.strict_parse.*`，去掉 `:45-48` 的 fake-rebind delegation 探针）」。锚点必须落在这个文件，不是 warmstart。
- **owner 门不变**：R29 误标已被 _layer1_corrections:48 降为 **planned(owner-pending)**（number_utils 仍全量 delegation-facade、4 兄弟全薄壳、半截迁移不对称客观在场）。**owner 未裁前不给终态修法、不进批次**；本裁定只修「续命点指向」这一事实错，不替 owner 拍薄壳化方向。
- **KEEP 路径**：若 owner 裁 KEEP（不薄壳化），则仅补「我是故意的：number_utils 是 strict_parse 的兼容门面，2 活消费者经它进」注释，不动测试——此路无 monkeypatch 改写需求，续命点修正仅用于「将来若走薄壳化别指错文件」。

---

## 对批次计划的影响汇总

| 争议 | 一句话裁定 | 须改前置/顺序/禁区/owner 门 |
|---|---|---|
| ⑦ R52 测试归属 | dossier「~23 LIVE」方向倒置：实测 31 用例=**23 全量版（含 15 RQErr 合同）随删/改写 + 8 LIVE（含 4 ValErr 契约）迁出 + 2 差分 oracle 改写** | 回写 dossier §11 迁移清单；owner 裁断门**增子门**：15 个 RQErr 合同走 A1（随删丢合同）还是 A2（改写为 LIVE 等价断言保留），建议 A2；不进批次直至裁断 |
| ② degradation 性质 | `services/common/degradation.py`=**17 行 385B 纯 re-export 壳**，实现在 `core.shared.degradation`(148 行)，但壳有 **~13 活生产消费者**=「**活桥接壳**」绝不可删 | R33 dossier §178 措辞再纠为「活桥接 re-export 壳」；`config_contract:15` degradation 元组死保；删元组只动 `:14/:16/:19`；degradation 不可混入 §128「无活消费者 facade」批 |
| ⑪ R29 续命点 | dossier 指的 `warmstart:136`（monkeypatch ortools）与 number_utils 无关；**真点=`regression_number_utils_facade_delegates_strict_parse.py:45-48`** | 回写 dossier A4/_layer1 续命点字段；薄壳化前置锚点重定到该文件（重写为身份测试）；2 活消费者(excel_validators:26 / scheduler_excel_calendar_rows:8)须同改；owner 门不变 |

**三条共性**：均为「文档侧指向/分类错」而非「分析结论错」——R52 迁移方向、degradation 死保、R29 薄壳化的**结论都不撼**，错的是执行者据以动手的锚点/桶标签，照旧文字执行会迁错桶 / 误判 degradation 可删 / 改错 monkeypatch 文件。三处全须在 Layer4 出可执行批次前回写。R52 与 R29 仍 owner_pending（不进批次）；degradation 是禁区（R33 做时只需保证不连带删）。
