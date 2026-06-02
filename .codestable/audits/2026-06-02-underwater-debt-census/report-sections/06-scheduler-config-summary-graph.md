## 06. 分区【scheduler-config-summary-graph】配置/汇总/图分析

**分区健康一句话**：有残渣但非重灾区——`config/` 与 `summary/` 两个子系统是"坏数据不准静默兜底"灵魂原则的范本（except 一律 re-raise `ValidationError`、解析失败一律 append warning + 记 degradation event + 打 `summary_count_parse_failed` 标记）；全部 5 条债集中在三处迁移/抽象残渣上：① SP05 半截包拆分留下的 5 个顶层 shim + 4 个空 delayed 包，② 排产分析诊断块的 core 合同被 web 本地副本架空，③ 图 ready 队列旧抽象被 `sgs_graph.py` 取代后只剩测试续命。**无 P1 写死假冒计算值，无未注释的 P2 隐藏护栏，本分区 5 条债 `load_bearing` 全部为 false**——这点很关键：所有"看起来像护栏"的 shim/兼容面，对抗验证一致裁定其删除后果只是"响亮的 ImportError"，不破任何安全不变量，系统在有无它们时都是 fail-loud 的。

> **承重护栏说明**：本分区没有 `load_bearing=true` 的安全护栏条目，因此没有"我是故意的（安全不变量）"注释需要补。但下文 F3/F4 涉及的 **SP05 冻结兼容面是有意的治理决定**（不是安全护栏，是迁移协调护栏）——它们缺的不是安全注释，而是"我是被 SP05 有意冻结的、删除需走三步迁移"的治理注释。文案见各条处置建议。

---

### F1 · 排产分析诊断块的 core 合同 `schedule_diagnostic_contract.py` 是 web 侧 LIVE 构造器的零生产消费孪生副本

- **病理标签**：P3（半截迁移残渣 / 第 N 套私有实现） · **严重度**：medium · **load_bearing**：false
- **位置**：`core/services/scheduler/analysis/schedule_diagnostic_contract.py`（整文件，约 1-82 行）
  - 三个构造器当前行号：`build_diagnostic_link`→**第 12 行**、`build_diagnostic_item`→**第 25 行**、`build_diagnostic_section`→**第 46 行**（普查证据记的是 :13/:24/:45，已轻微下移）
- **引用链**：
  - **定义点**：`schedule_diagnostic_contract.py:12/25/46` 三个 builder，产出 dict 键 `key/label/value/level/message/details/links`（item）与 `key/title/status/status_label/summary/items/links/degraded/degradation_events/empty_reason`（section）。
  - **唯一引用**：`tests/regression_scheduler_analysis_diagnostic_contract.py:10` `from core.services.scheduler.analysis.schedule_diagnostic_contract import …`。**生产 importer = 0**（全仓 grep `schedule_diagnostic_contract` 仅此一条 test 命中；grep `scheduler.analysis` 另两条命中是 `page_manuals_registry.py:40` / `regression_page_manual_registry.py:505` 的字符串 key `"scheduler.analysis_page"`，与本模块无关）。
  - **LIVE 孪生（实际渲染路径）**：`web/viewmodels/scheduler_analysis_diagnostic_helpers.py:41 build_item` / `:62 build_section`，逐键同形状；被 `web/viewmodels/scheduler_analysis_diagnostics.py:13-37` import 后在 `:54 build_section()` / `:68 build_item()` / `:98 build_section()` 实际拼装，再经 `scheduler_analysis_vm.py`→`analysis.html` 渲染。`_delay_impact.py` / `_health.py` 也同走该 web helper。
  - **git 错位证据**：core 合同单提交 `45c222a0`（"refactor: 增加排产分析诊断块合同"，2026-05-21），此后从未改动；web helper 晚 2 天落地（`ed695e79`，2026-05-23）且获追加修复（`184121ff`）。页面落地时没 import core 合同，而是在 web 层另写了一份本地副本，把 core 合同晾了 12 天。
- **为何算债**：同一职责（诊断 section/item 构造契约）存在两套实现——core 版语义完整但零生产消费，web 版是实际渲染用的活路径。core 合同被绕过，沦为只靠 1 个测试续命的悬空副本。更关键的反证：**真正的灵魂暗线护栏全在 web 侧，core 版一条都没有**——`NonFiniteDiagnosticNumber`（`helpers.py:101`）、`safe_int`（`:127`）、`safe_float`（`:142`）拒非有限数、status 缺失返回 `unknown` 不猜 `ok`，core 合同只有 `str(x or "")` 强转，无任何安全逻辑。所以 core 不是"规范源"，是被架空的废稿。
- **爆炸半径**：误删 core 合同→只破 `regression_scheduler_analysis_diagnostic_contract` 1 个测试（其 :21-82 三个 core-only 用例自证空转），**零生产页面、零安全不变量受影响**（web twin 原封不动）。反向风险：若有人误判方向去删 web twin，会摧毁活渲染路径 + 非有限数护栏——**绝不能删 web 侧**。
- **处置建议 + 收口点**：收口到 **web 侧 `scheduler_analysis_diagnostic_helpers.py`（活路径）**，而非 core。动手前先调和过时的 PR-9 roadmap，不要盲删：
  1. 在 `networkx-scheduler-graph-introduction-items.yaml` 的 `scheduler-graph-analysis-diagnostic-sections` 项里，把 `schedule_diagnostic_contract.py` 从 `primary_paths`（约 :435）及 ruff/pyright `exit_checks`（约 :480-481）移除，标注"该收口已被 web 路径取代"；
  2. 删 core 文件，并清理 `tests/regression_scheduler_analysis_diagnostic_contract.py:10-14` 的 core import 与 :21-82 三个 core-only 用例（web 键集断言 :229-240 是硬编码字面量、与 core 解耦，保留不动）；
  3. 若团队仍坚持让 core 成为规范收口点（走 PR-9 本意），则必须**整体重构**：把 web helper 的 `build_item/build_section` 改指向 core，并把灵魂暗线护栏（`NonFiniteDiagnosticNumber`/`safe_int`/`safe_float`/status 不猜）一并下沉到 core，再连同测试一次性迁移——绝不能单点删改任一侧。
- **复核结论**：⚠️ **行号已变（builder 定义 :13/:24/:45 → :12/:25/:46，下移约 1 行）**，其余证据全部仍准：唯一 test importer、生产 0 引用、web twin 形状/护栏分布、git 时间错位均与普查一致。对抗裁决 `real_debt`（已被精炼，附前置条件）维持。

---

### F2 · `graph/ready_queue.py` 兼容导出 + 底层 `get_ready_operation_ids` 是被 `sgs_graph.py` 取代的未接线并行实现

- **病理标签**：P3（半截迁移残渣 / 死代码） · **严重度**：medium · **load_bearing**：false
- **位置**：`core/services/scheduler/graph/ready_queue.py:1-12`（整文件，**当前精确 1-12 行**）
- **引用链**：
  - **shim 本体**：`ready_queue.py:9` `from core.algorithms.greedy.dispatch.ready_queue import ReadyQueueContractError, get_ready_operation_ids`，文件 docstring 自述意图"so SGS does not import the scheduler service layer"（当 SGS 的 ready 桥）。
  - **底层实现**：`core/algorithms/greedy/dispatch/ready_queue.py:103 def get_ready_operation_ids`。
  - **`get_ready_operation_ids(` 全仓调用点**：仅 `tests/scheduler_graph/test_ready_queue.py` 的 **6 处**（:31/:80/:193/:210/:221/:239，import 在 :16），**生产 0 调用**。
  - **shim 被谁 import**：仅 `tests/regression_scheduler_graph_lazy_runtime_contract.py:27` 与 `tests/scheduler_graph/test_metrics_topology.py:140`——二者只把模块名字符串放进枚举数组断言"若存在则必须保持懒加载/不反向 import"，**并不调用其函数**（注意：上面 grep 里大量 `effective_mode == "graph_ready_queue"` / `"sgs_without_graph_ready_queue"` 是结果摘要里的字符串枚举值，与本 shim 模块无关，勿混淆）。
  - **LIVE 的 SGS ready 排序实际路径**：`core/algorithms/greedy/dispatch/sgs.py:16 from .sgs_graph import (… :23 _prepare_graph_ready_state …)`，在 `sgs.py:201` 调用；定义在 `sgs_graph.py:33 def _prepare_graph_ready_state`。`run/schedule_graph_dispatch_context.py` 只 import `graph.input_adapter/scoring`，从不碰 `ready_queue` shim。全程不经 `get_ready_operation_ids`。
- **为何算债**：PR-5（roadmap 标 done"让 ready 队列参与 SGS 候选"）留下的早期抽象——`get_ready_operation_ids` 这套带完整契约校验的纯函数 + `graph/ready_queue.py` 桥，最终被 PR-6 下沉到 `sgs_graph.py:33 _prepare_graph_ready_state` 取代，自己沦为只有测试调用的死路径。lazy-runtime 合同只是顺带枚举它（"若存在则必须懒"），并不证明它活。
- **爆炸半径**：误删 `graph/ready_queue.py`→破 `regression_scheduler_graph_lazy_runtime_contract`、`test_metrics_topology` 两个 test 的模块枚举断言 + `test_ready_queue.py` 整组（其 import 会失败），**不影响任何排产产出**（SGS 不调它）。安全语义不退化：`sgs_graph.py:22-66` 的 `ValidationError(field="graph_ready_context")` 校验套件（缺集合/非 op_id 集合/误传图对象/重复 op_id/与待排工序不一致）已等价或更严于死函数抛的 `ReadyQueueContractError`，灵魂暗线"坏数据不静默兜底"不退化。
- **处置建议 + 收口点**：收口到 **`sgs_graph.py` 的 `_prepare_graph_ready_state`（活校验）**。同一改动内三处测试耦合必须一起处理，否则破测试模块枚举/导入：
  1. 删 `tests/scheduler_graph/test_ready_queue.py`（否则其 import 失败）；
  2. 从 `regression_scheduler_graph_lazy_runtime_contract.py:27` 与 `test_metrics_topology.py:140` 的模块名数组里摘掉 `"core.services.scheduler.graph.ready_queue"`；
  3. 在 PR-5 决定/roadmap 备忘里补一句"ready_queue helper 已被 `sgs_graph._prepare_graph_ready_state` 取代、连同 service 层兼容 shim 一并下线"，避免历史失忆。
  - 删前确认 `sgs_graph.py:20-160` 校验已覆盖原 helper 的合同点（坏 op_id / 前后置 / 排序 key / 图对象误传）——**经本次核对已等价或更严，无需迁移逻辑**。
- **复核结论**：✅ **证据仍准**。文件 1-12 行精确不变；`get_ready_operation_ids` 唯一调用方仍是 `test_ready_queue.py`（6 处）；两个 lazy/topology 合同的枚举断言行号（:27 / :140）精确不变；`sgs.py:16/:23/:201` 活路径与 `sgs_graph.py:33` 定义、`ValidationError(field="graph_ready_context")` 全部对上。对抗裁决 `real_debt`（附前置条件）维持。

---

### F3 · 顶层 5 个 config/summary shim：生产已迁走、被 SP05 钉死为冻结兼容面

- **病理标签**：P3（半截迁移残渣，地基体检"主病=半截迁移"的尾巴） · **严重度**：low · **load_bearing**：false（**但属 SP05 有意冻结的治理面**）
- **位置**：`core/services/scheduler/config_service.py:1-5`（+ `config_snapshot.py` / `config_validator.py` / `schedule_summary.py:1-29` / `schedule_summary_types.py:1-25`）
- **引用链**：
  - **shim 本体**：5 个文件各 5-29 行，纯 `from .config.X` / `.summary.X` 转出 + `__all__`，**0 逻辑行**（本次逐字确认：无 fallback / 无校验 / 无版本闸）。
  - **生产 importer（排除 tests）= 但发现 2 个 LIVE 非测试消费者**（普查 pass1 误记为"0 生产"，对抗已修正）：
    - `tools/capture_networkx_phase0_baseline.py:17` `from core.services.scheduler.config_service import ConfigService`（也是 `rev_deps.json` 里 config_service shim 的唯一 rev_dep）；
    - `audit/2026-03/20260316_schedule_audit_probes.py:87` `from core.services.scheduler.schedule_summary import build_overdue_items`。
    - 二者均为 SP05 扫描根（core/web）**之外**的离线运维/诊断脚本——正是"离线脚本踩旧路径"的承重顾虑所在。
  - **真正的生产代码全部走深路径**：`web/error_boundary.py:104` / `scheduler_config_display_state.py:5`→`.config`；`scheduler_config.py:11` / `personnel_calendar_pages.py:7`→经 `scheduler/__init__.py __getattr__` 映射 `ConfigService`→`.config.config_service`；`schedule_service.py:259`→`.config.config_service`。**无生产代码走顶层 shim**。
  - **测试 importer = 71 处**（普查 pass1 记的是 53，现已增长到 71，方向不变：仍是"只有测试 + 2 个离线工具在用旧路径"）。
  - **钉死点（SP05 治理合同）**：`tests/test_sp05_path_topology_contract.py:20-31 SERVICE_BEHAVIOR_COMPAT_SYMBOLS` 把这 5 个列为"behavior-compat 别名"（:21 config_service→config.config_service，:29/:30 schedule_summary(_types)→summary.X）；`:328-340` 断言旧模块 `__all__ == expected` 且 `getattr(old,sym) is getattr(new,sym)`（共享身份→无双类 isinstance 隐患）；`:438 assert old_module is not new_module`（"behavior-compatible, not a patch alias"）；`PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS`（:135）禁止 core/web 生产代码 import 它们；`:648/:655` 期望 `config_service.py` 被文档标注为"兼容薄门面"。
- **为何算债**：`config→config/`、`summary→summary/` 包拆分留下的兼容尾巴——生产已全量迁到深路径，旧顶层路径只作冻结兼容面保留。属典型迁移残渣，只是被 SP05 锁住不会悄悄烂。**注意纠偏**：它不是"纯自指测试续命"，确有 2 个离线工具仍踩旧路径，所以直接 `rm` 会破真实工具。
- **爆炸半径**：误删任一 shim→破 `test_sp05_path_topology_contract` + 71 个测试 import + 上述 2 个离线工具。**但失败模式是响亮的 ImportError，不破任何安全不变量**（无预览冒充正式/旧版本冒充现行/坏数据静默吞没/跨层违规）→ **确认非承重安全护栏**。
- **处置建议 + 收口点**：收口到 **深路径 `.config.config_service` / `.summary.schedule_summary`（迁移终点）**。这是一次需协调的迁移、不是自由删除：
  1. 先把 2 个非测试消费者迁到深路径——`tools/capture_networkx_phase0_baseline.py:17` 与 `audit/2026-03/20260316_schedule_audit_probes.py:87` 改为 `.config.config_service` / `.summary.schedule_summary`；
  2. 重指 71 处测试 import 到深路径；
  3. 从 `test_sp05_path_topology_contract.py` 的 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS`/`PUBLIC_SYMBOLS`（:20-82）删这 5 条，并改文档树断言（:648-658 期望"兼容薄门面"标注）；三步做完再删 shim。
  - **该补的"我是有意冻结的"治理注释文案**（贴在每个 shim 顶部，替代裸 import）：
    > `# [SP05 冻结兼容面] 本模块是 config/→config.config_service 包拆分迁移留下的薄门面，由 tests/test_sp05_path_topology_contract.py 钉死。生产代码一律走深路径 .config.config_service；保留此别名仅为兼容尚未迁移的离线脚本（tools/、audit/）与 71 处历史测试。删除前必须先迁这两类消费者并改 SP05 合同——不是自由删除。`
- **复核结论**：⚠️ **行号/计数已变**：测试 importer **53 → 71**（增长，但结论方向不变）；SP05 文档断言行 642-658 → **648/655**（轻微下移）。其余证据全部仍准：5 个 shim 逐字确认纯转出 0 逻辑；2 个离线消费者 `tools/…:17` 与 `audit/…:87` 行号精确不变；SP05 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS` 在 :20-31、`PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS` 在 :135 精确对上。对抗裁决 `depends`（可收但证据需纠偏，附三步前置）维持。

---

### F4 · 空 delayed 包 `calendar/` 与 `batch/`（及 `dispatch/`、`gantt/`）：SP05 强制存在却始终未填充

- **病理标签**：P3（搁置的迁移脚手架） · **严重度**：low · **load_bearing**：false（**属 SP05 有意冻结的空占位**）
- **位置**：`core/services/scheduler/calendar/__init__.py`（**0 字节**）+ `core/services/scheduler/batch/__init__.py`（**0 字节**，普查记为 1 字节，现为 0——更空了）；连带 `dispatch/__init__.py`、`gantt/__init__.py` 同为 0 字节空壳。四目录内**除空 `__init__.py` 外无任何模块**。
- **引用链**：
  - grep 全树：`scheduler.(calendar|batch|dispatch|gantt)` 作为包的生产引用 = 0；`from . import calendar/batch` = 0；importlib 动态字符串引用 = 0——**零运行时消费者**。
  - 干扰项排除：`core/models/__init__.py:11/14 from .batch/.calendar` 是 `core.models` 同名包，非本包；`resource_dispatch_range.py:3 import calendar` 经运行时确认解析到 Python 标准库 `calendar.py`，非本空包，且无 `from .` 相对导入遮蔽标准库的陷阱；`tests/test_greedy_refactor_contracts.py:81 assert "scheduler.calendar" not in text` 是反向断言（禁止 dispatch 算法耦合它），不是依赖。
  - **钉死点**：`tests/test_sp05_path_topology_contract.py:310` 七包存在性元组 `for package_name in ("config", "run", "summary", "batch", "dispatch", "gantt", "calendar")`（断言目录 + `__init__.py` 存在），`:315-316` `for delayed_package in ("batch", "dispatch", "gantt", "calendar")` 循环调 `_assert_init_has_no_imports`（四个 delayed 包 `__init__` 必须无 import）。普查记为 :311-316，实际存在性元组在 :310、无 import 循环在 :315-316，相差约 1 行。
  - **对照**：`config/run/summary` 已填满迁移完成；`batch/calendar/dispatch/gantt` 只搭了空壳。真实日历/批次逻辑仍在顶层 `calendar_engine.py` / `batch_service.py` 等（18+ 活跃 importer，如 `regression_calendar_invalid_shift_window_contract.py:10`、`regression_batch_template_autobuild_same_tx.py:26`）。
- **为何算债**：包拆分计划只完成 `config/run/summary` 三块，`batch/calendar/dispatch/gantt` 预建空包目录就停下，顶层文件从未下沉。SP05 把空壳钉死保证它不被误删也不被误填，但空包本身是搁置的迁移脚手架——且 SP05 对这四包的 pin 是自指的（包只为过测试而存在，测试只为护包而存在），真正护迁移正确性的 strong-alias/behavior-compat 断言只覆盖 `config/run/summary`（:321-340），从不涉及这四个空包。
- **爆炸半径**：误删空包目录→只破 SP05 `:310` 存在断言 + `:315-316` 无 import 循环。**纯目录拓扑，不触碰任何安全不变量**（无预览冒充正式/旧版本冒充现行/坏数据静默吞没/跨层违规）。
- **处置建议 + 收口点**：收口到 **SP05 合同本身**（删空壳 + 同步删断言）。同一提交里两件事一起做、缺一不可：
  1. 删 4 个空占位目录 `core/services/scheduler/{batch,calendar,dispatch,gantt}/`；
  2. 同步改 `tests/test_sp05_path_topology_contract.py`——把 `batch/dispatch/gantt/calendar` 从 :310 存在性元组和 :315 delayed-package 无导入循环里移除，否则该测试失败。
  - 已实证无需额外动作：无 importlib 动态引用、无 `from . import calendar/batch` 相对导入遮蔽标准库、`.limcode/plans/…/05_后续结构债治理与文档同步.plan.md:226,230-233` 明确把批次逻辑保留为顶层文件、**无 active roadmap 把它们当待下沉预留位**。若日后真要分包，届时重建包目录即可，不必现在留空壳。
  - **若选择保留**，该补的治理注释（写进空 `__init__.py`）：
    > `# [SP05 空占位] 此包为 config/run/summary 包拆分的预留位，至今未下沉任何模块。真实 batch/calendar 逻辑仍在顶层 batch_service.py / calendar_engine.py。由 test_sp05_path_topology_contract.py:310/315 钉死"存在且无 import"。删除须同步删该测试断言；无 active roadmap 计划填充本包。`
- **复核结论**：✅ **证据仍准**（一处更"利好"：`batch/__init__.py` 普查记 1 字节、现为 0 字节，更空）。四目录均空、零运行时引用、标准库 `calendar` 非本包均确认；SP05 存在性元组在 :310、无 import 循环在 :315-316（普查 :311-316 范围内，存在性元组实际 :310，偏 1 行）。对抗裁决 `real_debt`（附"删空壳 + 删断言"双动作前置）维持。

---

### F5 · `batch_service._safe_float` 重造浮点解析并静默吞错，绕过 `parse_finite_float`

- **病理标签**：P4（静默兜底死角）+ P5（第 N 套私有浮点解析） · **严重度**：low · **load_bearing**：false
- **位置**：`core/services/scheduler/batch_service.py:56-65`（`@staticmethod` 在 :55，`def _safe_float` 在 :56，函数体 :57-65，**当前精确对上**）
- **引用链**：
  - **本体**：`_safe_float(value)`——`value` 为 `None`/空串 `return None`，否则 `try: float(value) except Exception: return None`——**坏值悄悄变 `None`，不抛不记**。
  - **绕过的收口点**：`core/shared/number_utils.py:23 parse_finite_float`（会 `raise ValidationError` 并校验有限性）。
  - **消费点**：`batch_template_ops.py:172 "ext_days": svc._safe_float(tmpl.ext_days)`、`batch_copy.py:72 "ext_days": svc._safe_float(op.ext_days)`（均精确对上）。
  - **上游已严格校验**：`core/models/batch_operation.py:92 ext_days=parse_optional_float(ext_days, field="ext_days")`、`core/models/part_operation.py:75` 同理——即模型加载时 `ext_days` 已是合法 `float`/`None`，`_safe_float` 看到的几乎不可能是坏值。
  - **已被显式承认**：`tests/test_architecture_fitness.py:77 "core/services/scheduler/batch_service.py:_safe_float"` 在 `LOCAL_PARSE_HELPER_ALLOWLIST`（:75）中（且 :64 也列了 `_safe_float` 名）。
- **为何算债**：同一概念（浮点解析）的私有第 N 套实现 + 静默兜底死角——理论上若 `ext_days` 是坏值会被悄悄吞成 `None` 而非暴露，违背"宁可暴露错误也不自欺"原则。但因上游模型已严格 `parse_optional_float`，实际是冗余防御；且已被 fitness 注册表显式 allowlist 承认，不是失控的私有实现。这是本分区唯一一条 P4，严重度最低。
- **爆炸半径**：极小。替换为 `parse_finite_float` 仅在 `ext_days` 真为坏值时改变行为（从静默 `None` → 抛 `ValidationError`，反而更符合灵魂原则）；但因上游已校验，几乎触发不到。
- **处置建议 + 收口点**：收口到 **`core/shared/number_utils.py:parse_finite_float`（项目统一有限性浮点解析）**。但需先核对模板/复制路径是否真要拒绝坏 `ext_days`（确认语义后再动），改完同步移除 `tests/test_architecture_fitness.py:77` 的 allowlist 条目，否则 fitness 测试会报 stale entry（:254 `stale_entries` 检查）。低优先级，可与其它 P5 私有解析收口一起批量处理。
- **复核结论**：✅ **证据仍准**。`_safe_float` 体 :56-65、两处消费点（`batch_template_ops.py:172` / `batch_copy.py:72`）、两处上游严格解析（`batch_operation.py:92` / `part_operation.py:75`）、收口点 `number_utils.py:23`、allowlist `test_architecture_fitness.py:77` 全部精确对上。该条普查未要求对抗验证（`needs_adversarial=false`），无对抗裁决。

---

### 本分区复核小结

| 编号 | 病理 | 严重度 | load_bearing | 复核结论 |
|---|---|---|---|---|
| F1 | P3 诊断合同孪生副本 | medium | false | ⚠️ 行号已变（builder :13/:24/:45→:12/:25/:46） |
| F2 | P3 ready_queue 旧抽象 | medium | false | ✅ 证据仍准（1-12 行精确） |
| F3 | P3 5 个顶层 shim | low | false | ⚠️ 计数/行号已变（测试 53→71，SP05 :642-658→:648/655） |
| F4 | P3 4 个空 delayed 包 | low | false | ✅ 证据仍准（batch 1→0 字节，更空） |
| F5 | P4 `_safe_float` 静默吞错 | low | false | ✅ 证据仍准（:56-65 精确） |

**一句话总评**：5 条债全部复核为真且 `load_bearing` 全为 false——config/summary 子系统本体干净（fail-loud 范本），债集中在 SP05 半截包拆分的兼容尾巴（5 shim + 4 空包）、诊断合同被 web 副本架空、ready 队列旧抽象被 sgs_graph 取代三处迁移/抽象残渣；所有"看起来像护栏"的 shim 经核实删除后果只是响亮 ImportError，无一是安全护栏，但 SP05 冻结是有意治理决定，处置须走"先迁消费者→再改合同→后删壳"的协调路径而非自由删除。
