## 分区 01 · scheduler-run（排产主链 `core/services/scheduler/run/`）

**分区健康一句话**：这是经「静默回退治理」(e2e4bf7c) 与 `p1-scheduler-debt-cleanup` 整条 roadmap（PR-1~PR-8 全 done）双重打磨过的成熟主链——输入收集层全程 fail-fast、冻结窗口/落库护栏在每个数据缺口处 `raise` 或经 `DegradationCollector` 显式上报、`strict_mode` 一律抛错，灵魂原则（坏数据不静默兜底）落实得很彻底，**未发现活的 P1/P3/P4**；残渣集中在 3 条 P6 死面包屑 + 1 条边界 P5，无重灾区。

> 复核方法：本分区 4 条 finding 已逐条回到**当前代码**（含本批 git modified/added 文件）用 grep + Read 复核。结论：**4 条全部「证据仍准」**，cited file:line 与当前代码逐字对齐；仅 F4 的"全仓 dup 计数"因 6/01 后新增「资源派工执行车道」(commit 65870e47) 由 6 处涨到 7 处，但**本分区内的 2 处定位与全部承重论证不受影响**。

---

### F1 · `count_actionable_schedule_rows` / `has_actionable_schedule_rows` 是拆分重构后遗留的死函数，靠两层 re-export + 拓扑测试续命

- **病理标签**：P6（死代码 / 死面包屑）｜**严重度**：medium｜**load_bearing**：false（纯死代码，删除不移除任何不变量）
- **复核结论**：✅ **证据仍准**。`count_actionable_schedule_rows` 现仍在 `schedule_payload_contract.py:90`、`has_actionable_schedule_rows` 在 `:94`（内部调 `:95`），与原证据逐字一致。

**位置**
- 定义：`core/services/scheduler/run/schedule_payload_contract.py:90`（`count_actionable_schedule_rows`）、`:94`（`has_actionable_schedule_rows`，函数体 `:95` 调前者）
- 唯一私有依赖：`_iter_actionable_results`（`schedule_payload_contract.py:67`，静默跳过无 `op_id`/坏时间的结果行，只计数不报错）

**引用链（当前实测）**
- `run/schedule_persistence.py:16-17` 把两符号 import 进来（位于 `:12-18` 的 `from .schedule_payload_contract import (...)` 块，与 `build_validated_schedule_payload` 并列）。
- `scheduler/schedule_persistence.py:3` 二次 import 并 `:5` 列入 `__all__ = ["count_actionable_schedule_rows", "has_actionable_schedule_rows", "persist_schedule"]`。
- `schedule_payload_contract.py:414-415` 自身 `__all__` 也导出二者。
- **全仓 grep 实证**：除 `has()` 内部调用 `count()`（`:95`）外，`core/`、`web/`、`data/` 无任何 `has_actionable_schedule_rows(` / `count_actionable_schedule_rows(` 调用点；唯一外部引用是 `tests/test_sp05_path_topology_contract.py:54-55`，断言二者作为 `core.services.scheduler.schedule_persistence` 的公开符号存在（该断言块当前在 `:53-58`，含 `persist_schedule`）。
- **git 考古（pass1 已验，本次不复跑）**：`git -S` 证明历史生产调用点 `has_actionable_schedule_rows_fn=...` 在 `78879ec1`（schedule_service 600 行拆为输入收集 + 编排 + 薄门面）时被删除，函数本体留下未清。

**为何算债**
本应判断"是否有可落库排程行"的计数/布尔函数，在 schedule_service 拆分后，生产侧已改走 `build_validated_schedule_payload` → `_validate_persist_inputs`（`run/schedule_persistence.py:201`：`if not validated_schedule_payload.schedule_rows: raise_no_actionable_schedule_error(...)`）做严格落库闸门——这套老 count/has 函数因此**失去所有生产消费方**。两层 re-export 链 + 两处 `__all__` + 拓扑契约测试共同营造"仍在用"的假象，`_iter_actionable_results` 的静默跳过逻辑也随之沦为零生产价值的孤儿。

**爆炸半径**
纯死代码。删除清单：`count_actionable_schedule_rows` + `has_actionable_schedule_rows` + `_iter_actionable_results` + `run/schedule_persistence.py:16-17` 与 `scheduler/schedule_persistence.py:3,5` 两处 re-export/`__all__` + `payload_contract.py:414-415` 两条 `__all__`，并**必须同步删** `tests/test_sp05_path_topology_contract.py:54-55` 的断言（否则该拓扑契约测试会红——这正是它当前在做的事）。无生产路径受影响，误判风险极低（已 grep 实证 + git 考古双确认）。

**处置建议 + 收口点**
直接收（medium）。收口到生产唯一在用的落库闸门 `run/schedule_persistence.py:201` 的 `_validate_persist_inputs`——"有无可落库行"的判断已由它独占，老 count/has 无须保留为公开 seam。删除时一并把拓扑契约测试 `test_sp05_path_topology_contract.py` 中 `schedule_persistence` 的导出清单收缩为只剩 `persist_schedule`。

---

### F2 · `schedule_graph_dispatch_context.build_first_wave_ready_nodes` 是 test-only re-export 包装器（兄弟包装器是活的，唯独它没有生产调用方）

- **病理标签**：P6（冗余转发层 / 死面包屑）｜**严重度**：low｜**load_bearing**：false
- **对抗验证结论**：`_adv_verdict = real_debt`，`_adv_refuted = true`（怀疑者已裁断为真债，可删，但**带前置条件**）
- **复核结论**：✅ **证据仍准**。包装器现仍在 `schedule_graph_dispatch_context.py:461-475`，函数体 `:468` 懒 import 真 impl；真 impl 在 `resource_matching_context.py:48`、本地调用方 `:115`、`__all__` home `:131-134`，全部与原证据逐字对齐。

**位置**
- 包装器：`core/services/scheduler/run/schedule_graph_dispatch_context.py:461-475`（函数体 `:468` `from .schedule_graph_resource_matching_context import build_first_wave_ready_nodes as _impl`，`:470-475` 纯 `return _impl(...)` 转发）
- 真实现：`core/services/scheduler/run/schedule_graph_resource_matching_context.py:48`

**引用链（当前实测）**
- 真 impl 的**唯一生产调用方**在 `resource_matching_context.py:115`（裸名 `build_first_wave_ready_nodes(...)`，绑定到本模块 `:48` 的 local def，**完全不经过** dispatch_context 包装器）。
- 生产消费 dispatch_context 的只有兄弟包装器：`schedule_graph_report.py:19` `import build_graph_resource_matching_projection as _build_graph_resource_matching_projection`，`:180` 调用（确活跃）。
- **全仓 grep `build_first_wave_ready_nodes`**：除上述 2 个模块 + 包装器自身外，唯一外部导入方是 `tests/scheduler_graph/test_graph_dispatch_context.py:11`（import 块 `:10-14`，`:55`/`:66` 调用）。无任何 `core/web/data` 生产代码从 dispatch_context 导入它。
- `dispatch_context` 全文**无 `__all__`**（已 grep 确认），包装器不属于任何已声明门面契约；`run/__init__.py` 为空（1 行），无包级转出。

**为何算债**
同文件两个并排的 re-export 包装器（`build_first_wave_ready_nodes` 与 `build_graph_resource_matching_projection`）给人"对称公开 seam"的印象，但**只有后者有生产调用方**（`report.py:180`），前者纯粹被测试导入，造成"在用"假象。真逻辑在 `resource_matching_context`，该包装器是冗余转发层；其懒 import（`:468`）仅为规避 `matching→dispatch` 的模块级环，删它只会移除 `dispatch→matching` 这条边，改善而非破坏 import 图。

**爆炸半径**
极小。删除需同步改 `tests/scheduler_graph/test_graph_dispatch_context.py:11` 的 import（改为直接从 `schedule_graph_resource_matching_context` 导入，`:55`/`:66` 调用不变）。生产路径（`resource_matching_context:115` 本地调用 + `report.py:180` 走兄弟包装器）不受影响。`regression_scheduler_candidate_py38_contract.py` 仅做 banned-import/py38 语法检查、未 pin 公开导出面，删包装器不破契约测试。

**处置建议 + 收口点**
按对抗裁决的**前置条件顺序**收（low）：先把 `tests/scheduler_graph/test_graph_dispatch_context.py:11` 的 import 从 `schedule_graph_dispatch_context` 改为从 `schedule_graph_resource_matching_context`（其真实 `__all__` home，`:131-134`）导入 `build_first_wave_ready_nodes`，再删 `dispatch_context.py:461-475` 转发包装器；删后跑 `scheduler_graph` 测试套件 + `regression_scheduler_candidate_py38_contract` 自证。收口点 = `resource_matching_context.py` 的 `__all__`（`:131-134`，本就是真 home）。

> ⚠️ **承重旁注（不可顺手删）**：兄弟包装器 `build_graph_resource_matching_projection`（`dispatch_context.py:478`）是**真承重**——`report.py:180` 经 dispatch_context 消费它，删除会断生产路径。本条只动 `build_first_wave_ready_nodes` 一个，两包装器互不耦合（`report.py` 从不 import 前者）。

---

### F3 · 候选"失败"态全套机制（`CANDIDATE_STATUS_FAILED` / `_failed_plan` / `failed_candidate_count` / `baseline_missing_or_failed`）在生产中不可达，一路铺到死 UI 分支

- **病理标签**：P6（为不可达状态铺设的下游死管道）｜**严重度**：low｜**load_bearing**：false（**但内含一处承重窄 except，见下方醒目护栏区**）
- **needs_adversarial**：true（待怀疑者裁断：是"为持久化 schema 枚举保留的防御性契约面"还是"不可达状态的死脚手架"）
- **复核结论**：✅ **证据仍准**。唯一 catch 点仍在 `schedule_candidate_runner.py:216`，`_failed_plan` 在 `:470`（产出 `status=CANDIDATE_STATUS_FAILED` `:476`），`failed_count`/`baseline_missing_or_failed` 计算在 `:241`/`:247`，下游 viewmodel 分支全部命中——逐条对齐。

**位置**
- 失败态触发链：`CandidateTrialFailure` 类（`schedule_candidate_runner.py:28`，`class CandidateTrialFailure(RuntimeError)`）→ **唯一 catch 点** `:216`（`except CandidateTrialFailure as exc: return _failed_plan(...)`）→ `_failed_plan`（`:470-483`，产出 `status=CANDIDATE_STATUS_FAILED`，常量定义 `:24`）

**引用链（当前实测）**
- **生产侧零 raise**：`grep raise CandidateTrialFailure` 全仓只命中 `tests/regression_scheduler_candidate_runner_contract.py:470,576`，生产代码无任何 `raise CandidateTrialFailure`。
- **不可达推理（当前代码逐行验证）**：
  - baseline spec 在 `schedule_candidate_specs.py:61-63` 恒为 `sequence=0` / `candidate_key="baseline"` / `kind=CANDIDATE_KIND_BASELINE` 的首跑；
  - `runner.py:172` 的时间预算闸 `if now() >= deadline:` 在**首个 spec** 时（`deadline = started + budget`，`budget > 0`）不成立，故 baseline **永不被 skip**；
  - 加上 `CANDIDATE_STATUS_FAILED` 不可达 → `_baseline_missing_or_failed`（`:263-267`，baseline 必 `COMPLETED` 时返 False）生产**恒 False**、`failed_count`（`:241` `_count_candidates(..., CANDIDATE_STATUS_FAILED)`）生产**恒 0**。
- **死下游管道**：`failed_count`/`baseline_missing_or_failed` 流入 `schedule_candidate_summary.py:135,140`（公开摘要字段）→ 多个 viewmodel 的展示分支：
  - `web/viewmodels/dashboard_workbench.py:207`：`if comparison.get("baseline_missing_or_failed"):` → 追加"原算法代表方案没有完整结果"（生产永不触发）
  - `web/viewmodels/scheduler_analysis_candidate_helpers.py:324`（`failed_count = int(comparison.get("failed_candidate_count") or 0)`）、`:329`（`if bool(comparison.get("baseline_missing_or_failed")):`）→ 两条 `_warning_message` 分支（生产永不触发）
  - `web/viewmodels/scheduler_analysis_candidates.py:194,206,230,242,260,265` 透传同名字段
- **附带死枚举**：`ScheduleCandidate.status` 持久化枚举里的 `'not_run'`（`core/infrastructure/migrations/v10.py:14` 的 `CHECK(status IN ('completed','failed','skipped','not_run'))`）在整个 `run/` 零产出点（生产只产 completed/skipped，failed 仅测试可造，not_run 无人写）。

**为何算债**
这是一组"为不可达状态铺设的下游管道"：生产中候选要么 `completed`、要么 `skipped`（时间预算，可达）、要么真异常直接 propagate（`b81f8b3f` 收窄 except 后的正确行为）；`FAILED` 这一态**只有测试能造**。`failed_candidate_count` / `baseline_missing_or_failed` 一路传到 viewmodel 的 `if` 分支，这些 UI 分支生产永不触发，构成跨 service→viewmodel→template 的死脚手架。

**爆炸半径**
中等。若清理下游计数 + UI 分支，将牵动**已落库的 `ScheduleCandidate.status` 枚举契约**（`v10.py:14` 的 `completed/failed/skipped/not_run`）+ 两个 viewmodel（`dashboard_workbench`、`scheduler_analysis_candidate_helpers`）+ 候选公开摘要字段（`schedule_candidate_summary.py`），并涉及一批 contract 测试（`regression_scheduler_candidate_runner_contract` / `_summary_contract` / `_display_contract` / `_analysis_links_contract` / `dashboard_workbench_contract` 均断言这些字段）。

**处置建议 + 收口点**
**标 needs_adversarial，倾向低优先登记、暂不动**。这套字段是否该保留取决于一个判断：`failed`/`not_run` 是不是"为持久化 schema 防御性保留的契约面"——若 DB 已落 `v10` migration 的 4 值 CHECK 约束，贸然删 service 侧产出会让 schema 与代码失配。建议处置：(1) 维持枚举与字段不动；(2) 在 `_failed_plan`（`:470`）与 `_baseline_missing_or_failed`（`:263`）上各补一行"我是故意的"注释，标注"生产不可达、为持久化 schema 枚举 + 测试可造态保留"，把"看起来在用其实是契约面"的真相显式化；(3) 待 schema 决策明确后再统一收口到 `schedule_candidate_summary` 的公开摘要契约。

> 🛑🛑 **承重护栏（绝对不可动）—— 本条内嵌的真护栏：`schedule_candidate_runner.py:216` 的窄 except**
>
> 相邻的 `except CandidateTrialFailure as exc:`（`:216`）是 `b81f8b3f`「移除未知异常转 failed candidate 的宽泛捕获，只保留明确的 `CandidateTrialFailure`」**刻意收窄**的成果，是防止已被治理掉的"静默吞错"复活的承重护栏。**绝不能以"统一/简化"名义改回 `except Exception`**——那等于重新引入违背灵魂暗线（坏数据不静默兜底）的高危回归。测试 `regression_scheduler_candidate_runner_contract.py:473` 注释已明确："只有显式 `CandidateTrialFailure` 是候选级失败；`ValidationError`/`RuntimeError`/`TypeError` 必须继续向上抛。"
>
> **该补的"我是故意的"注释文案（建议加在 `:216` 上方）**：
> ```python
> # [承重·勿改宽] 仅捕获显式 CandidateTrialFailure，是 b81f8b3f 对"未知异常吞成 failed candidate"
> # 静默兜底的定点治理。ValidationError/RuntimeError/TypeError 必须继续向上 propagate——
> # 改成 except Exception 会复活已被删除的静默吞错，违背"坏数据宁可暴露错误也不自欺"。
> # 契约由 regression_scheduler_candidate_runner_contract.py:473 守护。
> ```

---

### F4 · 三套私有正整数强制器与统一收口点 `parse_finite_int` 并存（契约各异：raise / →0 / →None）

- **病理标签**：P5（第 N 套私有实现）｜**严重度**：low
- **load_bearing 字段**：false → **但对抗裁决推翻为 `_adv_verdict = load_bearing`（`_adv_refuted = false`）**：三套契约是按上下文刻意分化的，**不可裸合并**。本条因此**以承重论处**。
- **复核结论**：✅ **证据仍准**。三个强制器现仍在 `payload_contract.py:50` / `auto_assign_resource_errors.py:114` / `schedule_persistence_errors.py:13`，6 个 `_strict_positive_int` 调用点的 `except (TypeError, ValueError)` 全部对齐；收口点 `parse_finite_int` 仍在 `number_utils.py:39` 且仍无 `min_value` 形参。唯一漂移:`_positive_int` 全仓计数因新增资源派工车道由 6→7(live grep 实证,见下)，**本分区内 2 处不受影响**。

**位置（三套并存）**
1. `core/services/scheduler/run/schedule_payload_contract.py:50` —— `_strict_positive_int`：`None`/`bool`/`float`/`<=0` **全 raise `ValueError`**，是 `_iter_actionable_results` 与 `_build_validated_schedule_row` 的 `op_id` 落库闸门。
2. `core/services/scheduler/run/auto_assign_resource_errors.py:114` —— `_positive_int`：`except → 0`（错误消息解析路径上的 fall-through sentinel，配合 `:85-86` 的 `if batch_id and seq > 0`）。
3. `core/services/scheduler/run/schedule_persistence_errors.py:13` —— `_positive_int`：`except → None`（装配 `raise_no_actionable_schedule_error` 时的 id-dropping sentinel）。

**统一收口点**：`core/shared/number_utils.py:39` `parse_finite_int(value, *, field, allow_none)`——`allow_none` 重载恰好覆盖"返回 None"（`:41` 转 `parse_optional_int`）与"raise"（`:42` 转 `parse_required_int`）两种语义。同分区的 `optimizer_config.py:75,83` 则**正确**走 `core.shared.strict_parse`（`parse_required_float`/`parse_required_int`）。

**引用链 / 为何算债**
已有覆盖"可空/必需"两态的 `parse_finite_int` 收口点，本分区仍各处私造正整数强制器，三者语义已**漂移**（异常 vs 0 vs None），且 `_strict_positive_int` 抛**裸 `ValueError`** 而非 field 化的 `ValidationError`，属同一概念（正整数强制）的第 N 套私有实现，绕过收口点。
- `_positive_int` 当前**全仓 7 处**(本轮 `grep -rn 'def _positive_int' core/ web/` live 实证,排除 2 个 `_positive_int_set`;原 finding 写"6 处",65870e47 新增 `resource_dispatch_execution_service.py:23` 与 `scheduler_resource_dispatch_execution.py:32` 两处导致 +1。注:此前引的 `2026-06-01-foundation-maturity/codemap/dup_symbols.json` 出处文件在本仓不存在,已改为 live grep 证据)；**本分区内仍恰为 2 处**：`auto_assign_resource_errors.py:114` 与 `schedule_persistence_errors.py:13`，与原定位一致。

> 🛑 **承重裁决（对抗已确权为 load_bearing，绝对不可裸合并）**
>
> 怀疑者复核后**未能推翻**这三套的分化是刻意的，反而坐实了它——三者契约按上下文（**落库闸门 / 解析不可信错误文本 / 装配错误响应**）刻意分化，裸合并会破坏不变量：
>
> 1. **收口点表达力不足**：`parse_finite_int`（`number_utils.py:39`）**没有 `min_value` 形参**，根本表达不出 `op_id` 的契约（`>0` 且**非 float**）。底层 `strict_parse._parse_finite_int`（`strict_parse.py:46-58`）**接受整值 float**（`3.0→3`，`abs(parsed-int)<=1e-9`，`:56`），且 `parse_required_int` 默认 `min_value=None`——**严格弱于** `_strict_positive_int`（后者 `isinstance(value,float)` 一律 raise、`<=0` 一律 raise）。
> 2. **异常类型不兼容会击穿 6 个 except**：`core/infrastructure/errors.py:63,97` —— `class ValidationError(AppError)`、`class AppError(Exception)`，`ValidationError` **不是** `ValueError`/`TypeError` 子类。`_strict_positive_int` 的 6 个调用点全部 `except (TypeError, ValueError)`（`payload_contract.py:73,150,199,309,325,373`）——若换成抛 `ValidationError` 的收口点，异常会**逃逸所有 6 个本地 except**，把 `count`/`has_actionable_schedule_rows` 从"容错跳过脏行"变成"崩溃"。该 raise 是**内部 sentinel 而非真 abort**。
> 3. **数据腐蚀风险**：`payload_contract.py:33-47` `to_repo_rows` 对 DB write 做 `int(row.op_id)`（op_id 是 linkage / lock_status 键），下游无 bool/float 再守卫；Python 中 `isinstance(True,int)` 与 `3.0 in {3}` 均为 True，故 `True→1` / `3.0→3` 会**静默腐蚀 op↔row 映射**。`_strict_positive_int` 对 bool/float 的拒绝是这道腐蚀的唯一闸门。
> 4. **错误路径上的容错 sentinel 不可改抛错**：`auto_assign_resource_errors.py:85-86,114-119` 的 `→0` 与 `schedule_persistence_errors.py:13-18` 的 `→None` 都在**错误处理/错误消息解析**路径上——让它们抛错会**用二次异常掩盖真正的诊断**，违背暗线"坏数据不准静默兜底**但也不自欺**"。

**爆炸半径**
统一到 `parse_finite_int` 的 naive 替换会把"容错点"变成"抛错点"、把"落库闸门"放水接受 float——高危。属边界 P5，承重不对称已被对抗确权。

**处置建议 + 收口点（带前置条件，缺一不可）**
**不可裸合并；按债登记、低优先**。若日后确要收口到 `parse_finite_int`，必须满足全部前置条件：
1. **先扩展收口点**：给 `parse_finite_int`（`number_utils.py:39`）增加 `min_value` 形参，并加"拒绝任何 float（含整值 3.0）"的严格模式——否则收口点表达不出 `op_id` 的 `>0 且非 float` 契约。
2. **保契约迁移每个调用点**：`_strict_positive_int` 的 raise 必须仍能被原地 except 捕获（要么把 6 处 `except` 改成捕获 `ValidationError`，要么保留 `ValueError` 语义），否则 `count`/`has_actionable_schedule_rows` 会从"跳过脏行"变成"抛错"。
3. **不得把 `auto_assign(→0)` 与 `schedule_persistence_errors(→None)` 改成抛错**——它们在错误处理路径上，抛错会用二次异常掩盖真正诊断。

**该补的"我是故意的"注释文案**（分别加在三个强制器上方，把刻意分化显式化）：
- `payload_contract.py:50`（`_strict_positive_int`）：
  ```python
  # [承重·勿合并到 parse_finite_int] op_id 落库闸门：拒 bool/float/<=0。
  # 抛裸 ValueError 是"内部 sentinel"——6 个调用点(:73/:150/:199/:309/:325/:373)
  # 用 except (TypeError, ValueError) 接住转"跳过脏行"。收口点 parse_finite_int 抛的是
  # ValidationError(非 ValueError 子类)且无 min_value/拒 float 能力,裸替换会击穿这些 except
  # 并放水让 True->1 / 3.0->3 腐蚀 op<->row 映射(见 to_repo_rows int(op_id))。
  ```
- `auto_assign_resource_errors.py:114`（`_positive_int → 0`）：
  ```python
  # [承重·勿改抛错] 错误消息解析路径上的 fall-through sentinel(配合 :86 if batch_id and seq>0)。
  # 这是"解析不可信错误文本"语境,容错归 0 是刻意的;改成抛错会用二次异常掩盖真正诊断。
  ```
- `schedule_persistence_errors.py:13`（`_positive_int → None`）：
  ```python
  # [承重·勿改抛错] 装配 raise_no_actionable_schedule_error 时的 id-dropping sentinel。
  # 在"组装错误响应"路径上让坏 id 安静消失,改成抛错会用二次异常掩盖主错误(违背暗线)。
  ```

---

### 本分区债务索引（速查）

| 编号 | 病理 | 严重度 | load_bearing | 复核 | 一句话处置 |
|------|------|--------|--------------|------|-----------|
| F1 | P6 死函数 | medium | false | ✅ 证据仍准 | 直接收，连带删 `test_sp05` 断言，收口到 `_validate_persist_inputs(:201)` |
| F2 | P6 冗余转发 | low | false（对抗判 real_debt 可删） | ✅ 证据仍准 | 先改测试 import 再删包装器，收口到 `resource_matching_context.__all__` |
| F3 | P6 不可达下游脚手架 | low | false（内嵌承重窄 except :216） | ✅ 证据仍准 | needs_adversarial，倾向留 + 补注释；**窄 except 绝不可改宽** |
| F4 | P5 第 N 套正整数强制器 | low | **对抗推翻为 load_bearing** | ✅ 证据仍准（全仓计数 6→7） | 不可裸合并，按债登记 + 补三条注释；收口需先给 `parse_finite_int` 加 `min_value`/拒 float |
