## 08 · core-algorithms（排产算法核心 `core/algorithms/`）

**分区健康一句话**：这是全项目水下语义债最干净的分区之一——在最危险的 P1（写死常量假冒计算值）、P2（无注释承重不对称）、P4（静默兜底死角）、P5（第 N 套私有身份构造）四类上**零命中**；实际债务全部集中在 P6/P3 一层"新路径胜出、旧路径未清"的迁移尾巴，来自三次算法层重构（`c8a5a49c` 日期解析收敛、`e02cb914` 配置读取内联、`84812566` 图就绪队列增量化），共 6 条，**无一条 load_bearing、无一条违背灵魂暗线**，清理风险低且 blast 主要落在同步测试文件而非生产。

> **复核总结（回到 2026-06-02 当前代码逐条 grep/Read 实证）**：6 条全部 ✅ 证据仍准，主位置 `file:line` 全部精确命中，0 条行号已变、0 条疑似已修复。下文每条末尾给出复核细节。

---

### 为什么本分区没有 P1/P2/P4/P5（审计留痕，便于后续 owner 复核）

这几类是本次普查最在意的承重类病理，本分区**确认无命中**，但相关"看着像债其实有注释自证"的点值得显式登记，避免后续 agent 重复误报：

- **P2 候选（承重护栏）已自带注释，故不计债**：
  - `core/algorithms/dispatch_rules.py:71-72` — `build_dispatch_key` 内 `_safe_positive` 的 `proc_hours<=0` 不兜底极小值，注释明写"否则 ATC 会出现极端值（错误地把不可估算候选排到最前）"+"过滤非有限值（NaN/Inf）避免 -0.0/inf 传播"。这是**有意的承重护栏且已写明意图**，符合标准，不补注释。
  - `core/algorithms/dispatch_rules.py:83-85` — `p<=0` 回退 `avg_proc_hours` 再回退 `1.0`，是显式分级降级而非假身份。
- **P1 候选**：分区内 `1.0` / `2.0`（ATC 的 `k`）/ 排序哨兵均为带语义的算法常量或被 `ctx.increment(...fallback_count)` 计数的可见降级，非"写死假冒计算结果"。
- **P4**：分区内 17 处 `except` 全部 strict 即抛 / 追加可见 `errors` / best-effort 遥测，无一静默吞错。`ready_queue.py:99-100` 的 `except (TypeError, ValueError)` 直接 `raise ReadyQueueContractError(...) from exc`，是灵魂暗线"宁可暴露错误"的正面样本。
- **P5**：string→enum 已统一收口到 `_require_choice + Enum()` 严格路径（见债 4），无第 N 套私有身份构造。

---

### 债 1 · P3 — `config_adapter.py` 整模块迁移残渣：配置读取门面已被内联取代，生产零引用

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣 · **low** · load_bearing = **false**
- **位置**：`core/algorithms/greedy/config_adapter.py` 全文件 28 行
  - `:10` `CriticalConfigReadResult`（frozen dataclass，含 `value/missing/error` 三字段）
  - `:16` `read_schedule_config_value(config, key)`
  - `:26` `read_critical_schedule_config(config, key)`（仅转调 `:16`）
- **引用链**：
  - `config_adapter.py:16,26` 定义 → 全仓 `grep "read_critical_schedule_config\|read_schedule_config_value"` 生产 **0 引用**（命中仅为 `config_adapter.py` 自身 `:16/:26/:27` 三行）。
  - 唯一外部提及：`tests/regression_sp06_no_duplicate_defs.py:15` 在"禁止重复定义"扫描的路径白名单里列了该文件名（不是调用，是把它纳入静态检查范围）。
  - `git log -S 'read_critical_schedule_config('`：最后调用点在 `e02cb914` 被删除（diff 删 `from .config_adapter import ...` + `read_result = read_critical_schedule_config(config, key, default)`），改由 `core/algorithms/greedy/schedule_params.py` 的 `_snapshot_attr` 内联读取并直接抛 `ValidationError`。
- **为何算债**：排产配置校验链路重构（`fd4b6a9c` 引入 → `e02cb914` 拆除）留下的半截迁移。新路径（直接 `getattr` 快照 + 缺字段即抛）已**全面取代**旧的 `CriticalConfigReadResult`（把异常包进 `.error` 字段返回）。旧门面整模块悬空，且其"把错误塞进结果对象"的风格与新路径"缺字段即抛"**语义相反**——若被误用会绕过快照校验，等于在配置入口重新引入一处可被忽略的错误通道。
- **爆炸半径**：删除整模块仅需同步 `tests/regression_sp06_no_duplicate_defs.py:15` 的路径白名单；无生产调用点，无运行期影响。
- **处置建议 + 收口点**：整文件删除，收口到**已胜出的统一点** `core/algorithms/greedy/schedule_params.py` 的 `_snapshot_attr`（缺字段即抛 `ValidationError`）。同步从 `tests/regression_sp06_no_duplicate_defs.py:15` 白名单移除该路径。
- **复核结论**：✅ 证据仍准。文件仍为 28 行，三个定义在 `:10/:16/:26` 精确命中；生产 grep 仍 0 引用；测试白名单引用仍在 `:15`。

---

### 债 2 · P6 — 5 处死模块别名 `_due_exclusive` / `_parse_due_date` 散落 3 文件，定义后从不被读

- **病理标签 / 严重度 / 承重**：P6 死面包屑 · **low** · load_bearing = **false**
- **位置（5 行）**：
  - `core/algorithms/dispatch_rules.py:25` — `_due_exclusive = due_exclusive`
  - `core/algorithms/evaluation.py:40` — `_parse_due_date = parse_date`
  - `core/algorithms/evaluation.py:41` — `_due_exclusive = due_exclusive`
  - `core/algorithms/ortools_bottleneck.py:24` — `_parse_due_date = parse_date`
  - `core/algorithms/ortools_bottleneck.py:25` — `_due_exclusive = due_exclusive`
- **引用链（逐文件实证别名 0 读取、调用点全走裸名）**：
  - `dispatch_rules.py`：别名 `_due_exclusive`（`:25`）同文件 grep 仅 1 次（定义行）；真正调用在 `:67` 用裸名 `due_exclusive(inp.due_date)`，源自 `:9` `from .greedy.date_parsers import due_exclusive`。
  - `evaluation.py`：别名 `_parse_due_date`/`_due_exclusive`（`:40-41`）0 读取；真正调用 `:36` 裸 `parse_date(s)`、`:257` 裸 `due_exclusive(due_date_value)`，源自 `:9` 共享导入。⚠️注意区分：`:26` 的 `_parse_due_date_state(...)`（`:230` 被调用）是**另一个函数**，不是本条的别名。
  - `ortools_bottleneck.py`：别名（`:24-25`）0 读取；真正调用 `:138` 裸 `parse_date(...)`、`:140` 裸 `due_exclusive(due_d)`，源自 `:19` 共享导入。
  - `git blame`：5 行全部来自 `c8a5a49c`（2026-04-09「日期解析收敛」）。
- **为何算债**：日期解析收口重构时，模块从本地实现切到共享 `core/algorithms/greedy/date_parsers`，留下一层私有别名做"兼容垫片"；但**同一次提交里**调用点已直接改用裸名导入，垫片**从出生就没人用**。三文件同病，是同一次机械改造的残渣。
- **爆炸半径**：5 行纯删除，无任何引用，零运行期影响。
- **处置建议 + 收口点**：5 行直接删除。共享日期解析的唯一收口点已是 `core/algorithms/greedy/date_parsers`（`due_exclusive`/`parse_date`），三文件均已 import 裸名，无需任何替换。
- **复核结论**：✅ 证据仍准。5 行别名定义在 `:25 / :40 / :41 / :24 / :25` 精确命中；各文件裸名调用点（`dispatch_rules:67`、`evaluation:36/257`、`ortools_bottleneck:138/140`）全部仍在，别名读取数仍为 0。

---

### 债 3 · P6 — `mean_positive` 死函数：生产用内联均值，该助手仅靠测试续命

- **病理标签 / 严重度 / 承重**：P6 死代码（第二套实现胜出、第一套悬空）· **low** · load_bearing = **false**
- **位置**：`core/algorithms/dispatch_rules.py:112` `mean_positive(values: Dict[str, float]) -> float`
- **引用链**：
  - `dispatch_rules.py:112` 定义 → 全仓 `grep mean_positive` 生产 **0 引用**；唯一消费者是 `tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py:20/62`（import + 断言"忽略 Inf/非正值"）。
  - 本应消费它的真实生产路径（SGS 算 `avg_proc_hours`）在 `core/algorithms/greedy/dispatch/sgs.py:150` `_average_proc_hours` 内**自己内联**了等价逻辑：`:168-169` `if samples: return sum(samples) / float(len(samples))`，`:170` `ctx.increment("dispatch_key_avg_proc_hours_fallback_count")` 计数降级——从不调 `mean_positive`。
  - `git log -S`：自 `38719ab1` 引入后再无生产调用。
- **为何算债**：为"仅统计严格正值的均值"写的公共助手，但真正算 `avg_proc_hours` 的生产路径自己内联了等价逻辑，**绕过了这个本应是收口点的助手**。属"第二套实现胜出、第一套悬空"的死残渣，仅靠一个回归测试维持存在。
- **爆炸半径**：删除需同步删 `tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py` 中针对 `mean_positive` 的 import 与断言（`:20/:61-63`）；无生产影响。
- **处置建议 + 收口点**：二选一并由 owner 拍板——
  1. （推荐）删除 `mean_positive` + 同步删测试断言；"正值均值"的事实收口点保持在 `sgs.py:150 _average_proc_hours`。
  2. 若想保留一个公共"正值均值"助手，则反向收口：让 `_average_proc_hours` **改调** `mean_positive`，消除两份等价逻辑——但这会改动生产热路径，需谨慎。
- **复核结论**：✅ 证据仍准。主位置 `dispatch_rules.py:112` 精确命中；生产 grep 仍 0 引用，仅测试消费。内联实现确认在 `sgs.py`（全路径 `core/algorithms/greedy/dispatch/sgs.py`）`:150` 定义、`:168-169` 取均值、`:170` 计降级——与证据一致（证据写 `:168`，实际 `if samples:` 在 `:168`、`return` 在 `:169`，同一块，无实质偏差）。

---

### 债 4 · P3 — `parse_dispatch_rule` / `parse_strategy`：被严格收口取代的宽容解析器，生产零引用且语义与灵魂相悖

> **本分区最需要注意的一条（severity = medium）。** 危险面不在"它存在"，而在"它被复活"——一旦有人误把它当规范解析器复用，等于把已铲除的 P4 静默兜底重新引回派工/排序参数入口。

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣（宽容解析器对抗灵魂暗线）· **medium** · load_bearing = **false**
- **位置**：
  - `core/algorithms/dispatch_rules.py:28` `parse_dispatch_rule(value, default=DispatchRule.SLACK)`，非法分支 `:34-35` `except ValueError: return default`
  - `core/algorithms/sort_strategies.py:161` `parse_strategy(value, default=SortStrategy.PRIORITY_FIRST)`，空值分支 `:169-170` `return default`、非法分支 `:172-173` `except Exception: return default`
- **引用链**：
  - 两函数定义 → 全仓 `grep` 生产（`core/` 非测试、`web/`、`data/`）**0 引用**；且 `core/algorithms/__init__.py:17` 的 `__all__` 也**不导出**它们（实测 `__all__` 仅 `SortStrategy/StrategyFactory/BatchForSort/GreedyScheduler/ScheduleResult/ScheduleSummary`）。
  - 消费者仅为测试：`tests/regression_dispatch_rule_case_insensitive.py:18-25`、`tests/regression_sort_strategy_case_insensitive.py:18-25`。
  - 生产 string→enum 走**严格路径**：
    - `core/algorithms/greedy/schedule_params.py:277` `return SortStrategy(strategy_key)`、`:346` `return DispatchRule(rule_key)`，二者前置 `_require_choice(...)`（`:71` 定义：空值/非法值即抛 `ValidationError`，调用点在 `:272/:341`）。
    - `core/services/scheduler/run/optimizer_config.py:166` `strategy_enum = SortStrategy(require_choice(snapshot.sort_strategy, field="sort_strategy", valid_values=valid_strategies))`。
- **为何算债**：这是 choice 字段校验收口的迁移残渣——早期宽容解析器（非法→静默回退默认枚举）被严格收口（`_require_choice + Enum()` 非法即抛）**全面取代**，但宽容版未清除，仅测试续命。隐患在于其"坏值静默兜底成默认值"的策略**正是灵魂暗线『坏数据不准静默兜底』明令禁止的**；一旦有人误以为它是规范解析器而复用，等于把已铲除的 P4 静默兜底重新引回派工/排序参数入口。
- **爆炸半径**：代码本身生产零 blast；清除需同步处理约 5-9 个 import 它们的测试文件（直接命中 2 个 `*_case_insensitive` 回归，连带其他引用枚举的测试需扫一遍）。**真正危险面在"复活"而非"存在"。**
- **处置建议 + 收口点**：删除两函数，统一收口到严格路径——string→enum 一律走 `schedule_params._require_choice + Enum()`（`:272/277`、`:341/346`）与 `optimizer_config.require_choice + SortStrategy(...)`（`:166`）。若团队确需保留"大小写/空白容错"，应把容错**前移到 `_require_choice` 内部**（先 `.strip().lower()` 再校验合法集合、非法仍抛），而非保留一个独立的"非法→默认"宽容函数。同步删除 `tests/regression_dispatch_rule_case_insensitive.py` 与 `tests/regression_sort_strategy_case_insensitive.py`（或将其大小写容错断言迁移到严格路径上）。
- **复核结论**：✅ 证据仍准。`parse_dispatch_rule` 在 `dispatch_rules.py:28`、`except ValueError` 在 `:34`；`parse_strategy` 在 `sort_strategies.py:161`、`except Exception: return default` 在 `:172-173`——精确命中。`__all__` 不导出实测确认。严格路径锚点 `schedule_params.py:71/272/277/341/346`、`optimizer_config.py:166` 全部精确命中。

---

### 债 5 · P3 — `ready_queue.get_ready_operation_ids` 全量扫描版：生产已换增量前沿，经 service 再导出垫片仅供测试

> **本分区唯一 `needs_adversarial = true` 的条目——需 owner 拍板：是有意保留的差分测试 oracle，还是遗忘的迁移残渣。**

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣（含一层 service 垫片）· **medium** · load_bearing = **false**
- **位置**：
  - 全量实现：`core/algorithms/greedy/dispatch/ready_queue.py:103` `get_ready_operation_ids(*, schedulable_op_ids, completed_or_fixed_op_ids, blocked_op_ids, predecessor_op_ids_by_op_id, sort_key_by_op_id)`（`:128-135` 全量遍历 schedulable 集合判前驱子集）
  - 再导出垫片：`core/services/scheduler/graph/ready_queue.py`（纯 re-export，文件头注释自陈 *"Compatibility export for graph ready queue helpers."*，`:9` 从算法包 import、`:11` `__all__` 转出）
- **引用链**：
  - `ready_queue.py:103` 定义 → 生产 **0 直接调用**；唯一入口是 `core/services/scheduler/graph/ready_queue.py` 垫片。
  - 垫片消费者仅测试：`tests/scheduler_graph/test_ready_queue.py:16` import + `:31/:80/:193/:210/:221/:239` 调用；`tests/scheduler_graph/test_metrics_topology.py:140` 以字符串 `"core.services.scheduler.graph.ready_queue"` 引用（monkeypatch/mock 目标）。
  - `git show 84812566`（2026-05-19「优化图调度 ready 队列」）diff：删 `from .ready_queue import get_ready_operation_ids` + `ready_op_ids = get_ready_operation_ids(...)`，改为 `core/algorithms/greedy/dispatch/sgs_graph.py` 内联 `_initialize_graph_ready_frontier`（`:226`，在 `:85` 被调用）+ `_mark_graph_operation_completed`（`:305`，`sgs.py:386` 调用）增量维护（Kahn 入度递减）。生产 SGS 走 `sgs_graph._collect_candidates`（`:244`，`sgs.py:203` 调用），不再触及全量版。
  - 差分 oracle 用途确凿：`tests/scheduler_graph/test_ready_queue.py:79` `_full_scan_ready_ids(graph_state)` 直接调 `get_ready_operation_ids`，`:68` `_incremental_ready_ids(...)` 为增量版，`:270` `test_incremental_ready_queue_matches_full_scan_for_branch_join` 等多条断言 `_incremental_ready_ids(...) == _full_scan_ready_ids(...)`——**全量版被当作增量版的差分基准**。
- **为何算债**：同一"就绪集合计算"概念现存**两套实现**：生产用 `sgs_graph` 增量前沿（Kahn 入度递减），全量扫描版 `get_ready_operation_ids` 退居 `core/services/scheduler/graph/ready_queue.py` 再导出垫片后**只被测试引用**。它被 `test_ready_queue.py:270` 系列当作差分测试 oracle——所以**不是纯死残渣**，但"生产包里维护一份仅供测试当基准的旧实现 + 一层仅供测试的 service 垫片"是否值得保留，需 owner 判定（意图保留的差分 oracle vs 遗忘的迁移残渣）。
- **爆炸半径**：删除会移除 incremental-vs-fullscan 差分测试覆盖 + 一层 service 垫片；若保留则应**显式标注其 oracle 用途**。生产路径不受影响。
- **处置建议 + owner 决策（二选一，需拍板）**：
  1. **判定为"有意的差分 oracle"** → 保留，但在 `ready_queue.py:103` 函数 docstring 补一行用途声明（见下方文案），并把 `core/services/scheduler/graph/ready_queue.py` 垫片的"compatibility export"注释改写为"test-only differential oracle export"，消除"看起来像生产兼容层"的误导。这样未来 agent 不会再把它当残渣重报，也不会误当生产入口复用。
  2. **判定为"遗忘的残渣"** → 删除全量版 + service 垫片，把差分断言改为"增量版对已知拓扑的固定期望值"（测试里已有 `== [1]`、`== [2,3]` 等硬编码期望，可独立成立，不必依赖全量版当 oracle）。
  - 无论哪条，收口方向都是：**生产唯一就绪集合实现 = `sgs_graph` 增量前沿**（`:226/:244/:305`），全量版要么显式降格为 test oracle、要么删除，不得再以"compatibility export"的模糊身份停留在 `core/services` 层。
- **复核结论**：✅ 证据仍准。`ready_queue.py:103` 定义、`:138 __all__` 精确命中；service 垫片注释 *"Compatibility export..."* 实测确认；生产 0 直接调用、消费者为 `test_ready_queue.py` + `test_metrics_topology.py:140`（字符串 mock）实测确认；增量前沿 `sgs_graph.py:226/244/305` 与差分 oracle `test_ready_queue.py:79/270` 全部精确命中。

---

### 债 6 · P6 — `batch_order.dispatch_batch_order` 内 `_ = scheduled_count` 死空操作面包屑

- **病理标签 / 严重度 / 承重**：P6 误导性死代码 · **low** · load_bearing = **false**
- **位置**：`core/algorithms/greedy/dispatch/batch_order.py:74` `_ = scheduled_count`
- **引用链**：
  - 形参 `scheduled_count: int = 0` 在 `:39` → 已在 `:58` 传入 `_coerce_state(... scheduled_count=scheduled_count ...)` 用于构造 `ScheduleRunState`。
  - `core/algorithms/greedy/run_state.py:55` `initial_scheduled_count = max(int(scheduled_count or 0) - len(results or []), 0)`、`:75` `return int(self.initial_scheduled_count or 0) + len(self.results)`（`scheduled_count` property）。
  - `:74` `_ = scheduled_count` 把参数赋给丢弃名再"消费"一次；`:75` `return run_state.scheduled_count, run_state.failed_count` 用的是 `run_state` 的 property，与 `:74` 那行无关。
- **为何算债**：重构成 `ScheduleRunState` 后，`scheduled_count` 的真正消费已移入 `_coerce_state`（`:58`），`:74` 这行 `_ = scheduled_count` 是为压制"未使用参数"告警留下的空操作面包屑——但实际参数**早已在 `:58` 被用**，该行属误导性死代码（读者会误以为参数尚未被消费）。
- **爆炸半径**：1 行删除，无行为影响。
- **处置建议 + 收口点**：删除 `:74` 该行。参数 `scheduled_count` 的唯一消费收口点已是 `:58 _coerce_state → run_state.py:55`，无需任何替换；删除后不会触发"未使用参数"告警（参数在 `:58` 已被引用）。
- **复核结论**：✅ 证据仍准。`:74 _ = scheduled_count` 精确命中；`:39` 形参、`:58` 传入 `_coerce_state`、`:75` 用 property 返回均确认；`run_state.py:55` `initial_scheduled_count` 计算精确命中。

---

### 本分区处置优先级速览

| # | 病理 | 位置（主） | 严重度 | 承重 | 对抗 | 处置 | 收口点 |
|---|------|-----------|--------|------|------|------|--------|
| 1 | P3 | `greedy/config_adapter.py`（整模块 28 行） | low | 否 | 否 | 删模块 + 同步测试白名单 | `schedule_params._snapshot_attr` |
| 2 | P6 | `dispatch_rules.py:25` / `evaluation.py:40-41` / `ortools_bottleneck.py:24-25` | low | 否 | 否 | 删 5 行别名 | `greedy/date_parsers` 裸名 |
| 3 | P6 | `dispatch_rules.py:112 mean_positive` | low | 否 | 否 | 删函数 + 同步测试 | `sgs.py:150 _average_proc_hours` |
| 4 | P3 | `dispatch_rules.py:28` / `sort_strategies.py:161` | **medium** | 否 | 否 | 删宽容解析器，容错前移进严格路径 | `_require_choice + Enum()` |
| 5 | P3 | `greedy/dispatch/ready_queue.py:103` + service 垫片 | **medium** | 否 | **是** | owner 拍板：标注 oracle 用途 **或** 删除 | `sgs_graph` 增量前沿 `:226/:244/:305` |
| 6 | P6 | `greedy/dispatch/batch_order.py:74` | low | 否 | 否 | 删 1 行 | `_coerce_state → run_state.py:55` |

**一句话总评**：核心算法层地基干净——6 条债全是三次重构的"旧路径未清"尾巴，无承重、无灵魂违背；只有债 4（宽容解析器复活风险）和债 5（全量就绪队列的 oracle vs 残渣定性）需 owner 一次拍板，其余 4 条可直接清扫。
