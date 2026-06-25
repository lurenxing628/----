---
doc_type: issue-fix
issue: 2026-06-24-core-algorithm-deep-review-fixes
status: fixed
path: standard
fix_date: 2026-06-25
tags:
  - scheduler-core
  - deep-review
  - failure-semantics
  - plan-identity
  - quality-gate
---

# Core Algorithm Deep Review 修复记录

## 背景

本轮修复承接 `.codestable/audits/2026-06-24-core-algorithm-deep-review/verification-reconciliation.md`
核实后的 12 条问题。目标不是在页面上补提示，而是把排产核心、候选选择、计划身份、摘要留痕和门禁登记按根因收口。

## 修复范围

- `partial` 版本不再被当作可执行计划：派工、现场记录写入、计划和现场实际复盘都只认成功生成明细的正式方案；历史成功正式方案仍可只读复盘。
- 停机数据加载失败改为 `ValidationError` 阻断，不再用空停机表继续排产。
- 自制工序 setup/unit 工时和冻结后可排工序校验收紧，非法工时、未知齐套开关都 fail-loud。
- 候选试算继承当前 `algo_mode`，候选 runner 不再把 improve 模式压成 greedy；balanced 覆盖选择增加“当前主目标不能变差”护栏。
- `ScheduleSummary` 对 `success` 和计数字段做严格类型校验，不再让字符串、bool 计数或负数混入。
- 图分析因环降级时写入公开降级事件、原因和前端标签。
- 模拟排产与正式持久化边界收紧：模拟入口不分配版本、不持久化；底层持久化接口拒绝 `allocate_version=False` 还传持久化回调。
- 调度失败、跳过、图依赖阻断统一生成结构化 `failure_details`，摘要公开错误、`error_count`、`failure_detail_count` 和 OperationLogs 计数保持一致。
- `SchedulePlanResolution`、工作台链接、复盘共享判断统一解析 `yes/no/true/false/1/0`，避免字符串 `"no"` 被当成真。
- required tests、scheduler 分组、docs 质量门禁清单同步登记本轮新增回归。

## 对抗复审追加修复

- 核心服务 `ExecutionReviewMixin.execution_review()` 下沉复盘身份检查，直接调用服务也不能读取 `partial/failed/preview/simulation/摘要失败/缺明细` 方案。
- `error_count` 改为按公开错误文案计数，同时保留 `raw_error_count` 表示原始 `summary.errors` 数量，避免“明明有公开错误但计数为 0”。
- 拆分超 500 行测试文件：`scheduler_workbench_links` 合同拆成 4 个主题测试，资源派工 partial deep-review 用例拆到独立文件。
- `scheduler_workbench_links.py` 标签映射拆入 `scheduler_workbench_link_labels.py`，主文件回到 500 行以内。
- 恢复 `schedule_persistence.py` 的旧公开转出口 `ValidatedSchedulePayload`、`ValidatedScheduleRow`、`build_validated_schedule_payload`，并用 `__all__` 固定。
- 清理当前改动 Python 文件的 ruff `F401/I001` 问题，完整文件集包含未跟踪新测试文件。
- `can_read_execution_review` 下沉到 `core.models.execution_review_identity`，后端服务和前端 viewmodel 共享低层合同，避免 viewmodel 反向导入 service。
- `reports_page_support.py` 拆出 `reports_execution_review_page.py`，原文件从 550 行降到 397 行，并通过债务账本自动刷新移除该 oversize 条目。
- 复盘入口拆成两种语义：默认工作台/首页/顶部导航只允许当前正式可执行方案；资源派工历史行显式走只读复盘入口，按后端读侧合同允许历史成功正式方案，继续阻断 partial/缺明细/预览/模拟/对比。
- `test_reports_workbench_navigation_contract.py` 拆出 `test_reports_workbench_navigation_publish_contract.py`，原文件降到 500 行以内；新文件同步进入 required tests 和 scheduler 分组。
- 去掉 `QUALITY_GATE_GUARD_TESTS` 里的重复注册，保持 required 注册表不重不漏。

## 主要改动文件

- 核心算法与调度状态：`core/algorithms/types.py`、`core/algorithms/greedy/run_state.py`、`core/algorithms/greedy/dispatch/batch_order.py`、`core/algorithms/greedy/dispatch/sgs.py`、`core/algorithms/greedy/dispatch/sgs_graph.py`、`core/algorithms/greedy/scheduler.py`
- 输入、候选、持久化：`core/services/scheduler/resource_pool_builder.py`、`core/services/scheduler/run/schedule_input_builder.py`、`core/services/scheduler/run/schedule_input_collector.py`、`core/services/scheduler/run/schedule_input_runtime_support.py`、`core/services/scheduler/run/schedule_candidate_*`、`core/services/scheduler/run/schedule_persistence.py`、`core/services/scheduler/run/schedule_orchestrator.py`
- 计划身份与复盘：`core/models/schedule_plan_role.py`、`core/models/schedule_plan_resolution.py`、`core/models/execution_review_identity.py`、`core/services/report/execution_review.py`、`core/services/report/execution_review_identity.py`、`web/routes/reports_execution_review_page.py`、`web/viewmodels/scheduler_workbench_links.py`、`web/viewmodels/scheduler_workbench_link_labels.py`
- 摘要与公开错误：`core/models/scheduler_public_errors.py`、`core/models/scheduler_degradation_messages.py`、`core/services/scheduler/summary/schedule_summary_assembly.py`、`core/services/scheduler/summary/summary_visible_degradation.py`、`core/services/scheduler/run/schedule_operation_log_details.py`
- 测试和门禁：`tests/algorithm/test_schedule_summary_contract.py`、`tests/schedule/summary/test_schedule_summary_deep_review_degradations.py`、`tests/schedule/summary/test_scheduler_summary_public_projection_deep_review.py`、`tests/resource_dispatch/test_scheduler_dispatch_plan_identity_deep_review_contract.py`、拆分后的 `tests/schedule/route_view/test_scheduler_workbench_link_*_contract.py`、`tests/web_pages/test_reports_workbench_navigation_publish_contract.py`、`tools/test_registry_data.py`、`tools/test_registry_groups_scheduler.py`

## 已完成验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest ... -q --tb=short -ra -p no:cacheprovider`：最终 200 个定向回归通过。
- `git diff --check && git diff --cached --check`：通过。
- 当前改动 Python 文件 ruff：`{ git diff --name-only --diff-filter=ACMRTUXB HEAD -- '*.py'; git ls-files --others --exclude-standard -- '*.py'; } | sort -u | xargs -n 40 ... ruff check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/models/execution_review_identity.py core/services/report/execution_review_identity.py web/viewmodels/scheduler_workbench_links.py web/routes/reports_execution_review_page.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`：17/17 步全部通过；因工作区 dirty，manifest 状态为 `passed_but_unbound`，不能作为 clean-worktree proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.symbol_locator callers build_workbench_link` / `callers can_read_execution_review` / `callees _execution_review_link`：确认资源派工只读复盘入口与默认工作台入口分流，`can_read_execution_review` 仅被后端服务、复盘页挡板和只读复盘判断调用。

## Subagent 对抗复审

- 初始逐项复核确认 12 条代码事实均需修复或收紧。
- 定向复核关闭了 `yes/no` 布尔投影、复盘读写边界、`error_count` 计数、服务层 partial 直调、文件行数、ruff/import 等 blocker。
- 最终定向复审（资源派工只读复盘、registry 去重、ruff import、历史方案默认导航禁用）结果 PASS。
- 最终盲审 A（web/registry/ledger/tests）结果 PASS。
- 最终盲审 B（core/scheduler/report 算法链）结果 PASS。
- 所有已报 blocker 均已复现、修复并由定向或盲审确认关闭。

## 遗留边界

- 当前工作区不是 clean，且包含审计报告、callgraph 和历史材料改动；本记录只能证明当前 dirty workspace 下的修复与验证结果，不能称为 clean-worktree proof。
- 仓库中仍有少数历史测试文件超过 500 行，但它们在本轮之前已经超限；本轮新增越线文件已拆分。

## 第二轮：对修复本身的深度 review 复修（2026-06-25）

对第一轮修复又做了多 Sub agent 分域深审 + 主线独立核验，确认并按根因复修了 1 个 HIGH 和 3 个 MEDIUM；另有 1 个 MEDIUM 复核后判为 by-design 不改，1 个既有限制如实标注。

### HIGH：失败公开错误“双发”——删掉三处 errors.append

- 根因：`record_missing_batch`(`run_state.py`)、`record_dispatch_exception`(`run_state.py`)、图阻塞 `_record_graph_blocked_operations`(`sgs_graph.py`)在写结构化 `failure_details` 的同时，还往 `state.errors` 塞原始中文串。这三句原始串不匹配任何 `LEGACY_PUBLIC_PATTERNS`，在 `build_public_error_records` 里回落成 `generic_scheduler_error`（“排产执行遇到问题，请联系管理员查看日志。”），与结构化的具体文案并列形成双发，并让单道失败的 `error_count` 虚增为 2。那条 generic 文案恰恰是第一轮 fail-loud 改造想消灭的低信号话术。
- 修复：删除三处 `errors.append`，失败文案统一由结构化 `failure_details` + `_structured_failure_message` 单点渲染；连带清理 `sgs_graph._graph_op_label`（变为死代码）。`internal_operation.py`/`external_groups.py` 里匹配 legacy 模式的具体错误串（缺资源、工时不合法、外协周期等）保持不动，它们各自只产一条具体公开错误，非双发。
- 回归：`tests/algorithm/test_dispatch_blocking_consistency.py` 新增 `test_dispatch_failures_record_structured_details_without_raw_error_duplication`，钉死三类失败只写结构化明细、`state.errors == []`；同步修正 `test_batch_order_bid_unboundlocal.py`、`test_scheduler_graph_on_mode_contract.py` 改为断言 `failure_details`。

### MEDIUM：删除无消费端的死字段（raw_error_count、原始 failure_details 列表）

- 根因：`schedule_summary_assembly` 把 `raw_error_count` 与原始 `failure_details` 列表序列化进 `result_summary` 落库，但全仓无任何生产消费端读取它们（`dispatch_error_summary` 只消费 `failure_detail_count` 与 `public_error_details`；size guard 大列表时本就丢弃 failure_details）。`raw_error_count` 声称的“防止公开错误丢失”无任何代码兑现。
- 修复：移除 `result_summary` 中的 `failure_details` 原始列表与 `raw_error_count`，保留被消费的 `failure_detail_count`；同步删 `summary_size_guard_fields` 对 `raw_error_count` 的透传与三处测试断言/输入。失败对外展示统一走 `public_error_details`。

### MEDIUM：enforce_ready 解析单源化

- 根因：`schedule_input_collector._resolve_enforce_ready_effective` 手搓窄别名集 `_YES_VALUES/_NO_VALUES`，与项目唯一低层别名源 `normalize_yes_no_wide` 分叉，`"是"/"否"/"y"/"n"` 会被误判未知而拒绝（与 `boolean_normalize.py` “勿单边维护别名集”的告诫冲突）。
- 修复：改用 `normalize_yes_no_wide(text, unknown_policy="raise")` 单源解析，未知值仍 fail-loud（捕 `ValueError` 重包成 `ValidationError`），空串显式拒绝；删掉手搓常量。

### MEDIUM：persist_schedule 的 simulate 层次语义——加澄清 docstring（不改名）

- 复核结论：底层 `persist_schedule` 是 `__all__` 导出的契约级入口，被 8+ 合同测试与 conformance 报告直接调用；其 `simulate` 形参在持久化层语义本就正确（=写模拟版本），与服务层“不落库”语义永不交叉（服务层 simulate 时根本不调它）。级联改名会波及 8+ 处测试且零行为收益。
- 处理：仅补一段 docstring 说明两套 simulate 的层次差异，消除“语义陷阱”误读；不做改名。

### MEDIUM（复核后判为 by-design，不改）：dispatch_error_summary 的 count 与 codes

- 子代理曾报“count 与 codes 自相矛盾”。独立下钻发现：`count`=真实失败总数（去重/采样前的 `failure_detail_count`），`codes`=去重/采样后展示样本的归类，二者度量不同对象。该口径被 `test_dispatch_error_summary_keeps_total_count_when_error_details_are_sampled`（断言 count=12000、codes={...:10}）明确钉死，属有意设计而非缺陷。强行令 `count==sum(codes)` 反会破坏“采样后仍保留真实总数”的契约。故不改，仅在此记录结论。

### 既有限制：improve 候选单候选超时（如实标注，待产品决策）

- 候选试算继承 `algo_mode` 后未注入更短的 `time_budget_seconds`，候选 runner 的 deadline 仅在每个候选 spec 开始前检查、无法打断“正在跑的单个候选”。故 improve 模式下单个候选最坏可跑满 `base_cfg.time_budget`，总耗时最坏会超出 `run_time_budget_seconds` 约一个候选预算量（后续候选会被 deadline 标记 skipped，不会无限超时）。此为既有架构限制，非本批引入。是否给候选注入按候选数均摊的 per-candidate 预算，属性能/质量取舍，留待产品拍板。

### 待产品拍板项（修复完一并上报，未擅改）

- 零总工时内部工序一律拒绝（算法层允许 ==0，输入层收紧到 >0，口径不一致且可能误杀占位/瞬时工序）。
- 单台设备停机区间读取失败即阻断整次排产（鲁棒性偏脆）。
- 报表“计划和现场实际”页内历史方案的行级只读链接被一并禁用（read-only flag 未随报表上下文传播）。
- improve 候选 per-candidate 预算是否注入（见上）。

### 第二轮验证

- 定向回归：`tests/algorithm/ tests/schedule/ tests/candidate/ tests/scheduler_graph/ tests/resource_dispatch/ tests/operation_execution/` 全绿（1640 passed）。
- 改动文件 `py_compile` + `ruff check` 通过。
- `scripts/run_quality_gate.py --allow-dirty-worktree`：17/17 步全通过；因工作区 dirty，manifest 为 `passed_but_unbound`，不作 clean-worktree proof。
- Codex 对抗复审（新开线程、自包含 prompt）：5 处修复零阻塞，无正确性 bug / 回归 / 静默回退；唯一“疑似”是它把第一轮对 `schedule_persistence.py` 的改动也算进来，本轮对该文件实为 docstring-only，非阻塞。
- 关键事实（`failed_count`/`failed_ops` 不变、`raw_error_count`/原始 `failure_details` 无生产消费端、enforce_ready 解析等价且未知值仍 fail-loud）由主线独立读码核实。

### 产品拍板结果与落地（2026-06-25）

四个待拍板项的处理：

1. **零工时口径 → 选 A（放行 0，与全系统一致）。** 上下游全链路核实：标准工时表 `update_internal_hours`、Excel 导入、模型默认值、建批模板/复制带出、手工编辑（注释明写“空视为 0”）、排产 build 层 `_internal_work_hour`、算法层 `validate_internal_hours` —— **全程允许总工时为 0、缺失自动补 0，只拦负数/非数字**。唯独第一轮新加的 runtime `total_hours <= 0` 把合法的 0 判非法、且整批硬报错，与全系统口径打架、比算法层还严，且没对准原审计“坏工时被悄悄当 0”的靶子（那个真问题已由 `_internal_work_hour` 拒空/非数字解决）。
   - 落地：`schedule_input_runtime_support._ensure_internal_runtime_hours` 把 `total_hours <= 0` 改为 `total_hours < 0`，与算法层 `internal_slot.validate_internal_hours` 的 `< 0` 口径对齐；孤儿批次、有限数解析、数量>0 等护栏全部保留。测试 `rejects_zero_internal_runtime_hours` 改为 `allows_zero_internal_runtime_hours` + `still_rejects_negative_total`。
2. **停机读取失败 → 保持现状（fail-loud），并按建议把报错分清“全挂/个别挂”。** 落地：`resource_pool_builder` 的 load/extend 个别失败路径,按“失败设备是否覆盖全部被查设备”分流——全挂用“全部设备…”文案 + reason `downtime_load_failed`/`downtime_extend_failed`，个别挂用“部分设备…”文案 + 新 reason `downtime_load_partial_failed`/`downtime_extend_partial_failed`。修正了此前“2 台全失败却报‘部分设备(2 台)’”的误导。infra setup 失败仍走原全挂 reason。
   - **连带修复（Codex 对抗发现）：** 停机失败文案此前根本到不了用户面前——`field="downtime"` 不在 `web/routes/domains/scheduler/scheduler_user_messages.py` 的 `_DIRECT_SCHEDULER_VALIDATION_FIELDS` 白名单里，消息里的机器编号（如 `MC_BAD`，带下划线）命中 `error_boundary._INTERNAL_KEY_RE` 被泛化成“参数填写不正确，请检查后重试。”。这是第一轮加停机 fail-loud 时漏登记白名单的遗留 bug，本轮②把它暴露并修复（把 `downtime` 加入白名单 + 回归用例 `test_scheduler_downtime_failure_message_with_machine_samples_reaches_user`）。修好后“全挂/个别挂”分流对用户才真正可见。
3. **报表历史方案只读链接 → 停手不做。** 前端将整体重做，本轮不动。
4. **improve 候选超时 → 不卡时间，维持现状。** 追求排产质量，不注入 per-candidate 预算；既有特性已在上文“既有限制”如实记档。

### 第二轮 + 拍板落地验证

- 定向回归：零工时 + 停机分流相关 20 项全绿；大范围（algorithm/schedule/candidate/scheduler_graph/resource_dispatch/operation_execution）1641 passed；web 路由（route_view/web_pages）809 passed。
- 改动文件 `py_compile` + `ruff check` 通过；新 reason code 无白名单需登记。
- `scripts/run_quality_gate.py --allow-dirty-worktree`：17/17 步全通过（dirty → `passed_but_unbound`）。
- Codex 对抗复审循环到零阻塞：第 1 轮发现“停机失败文案被泛化”BLOCKER（已修，见上）；第 2 轮复审白名单安全性 + ①②回归，判定零阻塞、可合入。白名单安全性由主线独立读码复核（`field="downtime"` 仅两个受控抛出点，原始异常只进日志不进 message）。

## 第三轮：对修复本身再做 5 域对抗深审 + 后台深读，按发现复修（2026-06-25）

对前两轮修复又派 5 个 Sub agent 分域对抗深审（算法失败语义 / 输入校验 / 候选与持久化 / 摘要公开错误 / 计划身份与复盘），用四透镜（全局最优 / 过度防御 / 过度兜底矫枉过正 / 静默回退）核。结论：方向正确、主体扎实，确认并按根因复修了 1 个 MEDIUM + 3 处可维护性收口；3 个“知道一下”项由后台 agent 深读上下游后判定无需改（其一仅补注释）。

### MEDIUM：`_ensure_internal_runtime_hours` 的 `quantity <= 0` 收过头，与刚拍的“放行 0”自相矛盾

- 根因：第二轮新增的 runtime 守卫一边按拍板把 `total_hours <= 0` 放宽成 `< 0`（注释明写“总工时 0 合法”），一边在 `_batch_quantity_for_work_hours` 里手搓 `quantity <= 0` 硬拦整批。算法层真相源 `internal_slot.validate_internal_hours` 经 `_coerce_legacy_hours_value` 把 `quantity=0/None/缺失` 一律按 `0.0` 放行（总量=setup）。故 `quantity=0` 的脏数据（`Batch.quantity` 默认 0、`from_row` 对 NULL 回落 0、DB 无 CHECK）会把算法层本可成功排出的整次排产 abort——比算法层更严，且违背拍板①。
- 修复：删掉手搓的 `_batch_quantity_for_work_hours` 与逐项 setup/unit 解析，`_ensure_internal_runtime_hours` 直接复用算法层 `validate_internal_hours` 作单一真相源（捕 `ValueError` 重包成 `field="work_hours"`、`reason=invalid_internal_work_hours` 的 `ValidationError`，保留 op_id/batch_id/op_code 明细）；`batch is None` 的存在性检查保留。一举消除“口径分叉 + 重复维护面”。
- 回归：`test_schedule_input_collector_legacy_compat.py` 新增 `test_ensure_internal_runtime_hours_allows_zero_quantity`（quantity=0 两形态：总量 0 与仅 setup 均放行），保留 total=0 放行与负数拒绝两例。

### 收口①：可执行/可复盘的 `{success}` 口径散落 4 处 → 单一共享常量

- 根因：`schedule_plan_identity_builder.py`、`reports_plan_template_fields.py`、`core/models/execution_review_identity.py` 各定义一份 `{success}`，外加 `scheduler_resource_dispatch.py` 内联 `!= "success"`。四处现一致，但“partial 是否可执行”这类策略下次一改极易漏改一处造成入口间漂移。
- 修复：在 `core/models/schedule_plan_role.py` 立 `COMPLETED_RESULT_STATUSES = frozenset({"success"})` 单一真相源（含文档注释说明 executable 与 reviewable 在 result_status 维度共用此口径、差异由各自其他谓词处理），4 处全部 import 该常量；删除 3 处本地常量定义 + 改写 1 处内联比较。

### 收口②：删除零差异的误导别名 `_identity_yes_bool`

- `schedule_plan_role.py` 的 `_identity_yes_bool` 函数体就是 `return _identity_bool(...)`，命名暗示“仅 yes 才真”的更严语义但实际不存在。删别名，2 处调用点（detail_saved / is_simulation_plan）改回 `_identity_bool`，行为不变。

### 收口③：停机 abort 路径的自相矛盾用户文案

- 根因（后台 agent 深读发现，比“过时注释”更严重）：停机读取失败现已 fail-loud abort，但 `_raise_downtime_*` 复用了 summary 降级常量/suffix（`DOWNTIME_LOAD_FAILED_MESSAGE`“…先不使用停机约束”、suffix“这些设备本次先不使用停机约束 / 可能未覆盖停机约束”），拼上 abort 尾句后给用户看到的是“先不使用停机约束……本次没有生成新排程”——前半句继续排、后半句没排，自相矛盾。且该矛盾被 `test_scheduler_user_visible_messages.py:255-256` 锁死。
- 修复（不污染 summary 语义）：新增 abort 专用中性常量 `DOWNTIME_LOAD_ABORTED_MESSAGE`/`DOWNTIME_EXTEND_ABORTED_MESSAGE`（“停机区间加载/扩展失败。”），abort 路径（infra 全挂 + partial 个别挂 + 逐台日志 + meta/warnings + 抛出 message）全程改用事实文案、suffix 改“无法读取这些设备的停机记录”；summary 降级路径仍用原“先不使用”常量（`downtime_avoid_degraded` 等“继续排”语义不变）。同步更新 `test_resource_pool_builder_contract.py`（2 个 expected_error + load/extend 全挂 meta 断言改 ABORTED 常量）与 `test_scheduler_user_visible_messages.py`（用户可见消息断言）。

### 后台深读判定“无需改”的 3 项

- **error_count 口径迁移（安全）**：去重后公开文案数（含结构化失败注入）的新语义无下游破坏；success 推断有 `error_count` 与 `public_error_details` 双护栏；`raw_error_count` 删除彻底（仅 evidence 取证基线快照有残留，非门禁消费端）；新语义已被 `test_schedule_summary_deep_review_degradations.py` 钉死，无需补测试。
- **失败双通道 + degraded_success 不对称（by-design）**：错误明细区与降级提示区双显是有意的两种语义；`dispatch_failure_details` 分支不抬 `degraded_success` 是正确的——`dispatch_failure_count>0` 蕴含 `failed_count>0` 蕴含 `completion≠success`，二者代码层面互斥，补那行只会引入死逻辑。仅在该分支补一行解释性注释防后人误“修”。
- **停机“单台失败即 abort 整次”脆性**：产品已拍板维持 fail-loud，后台 agent 评估的“仅阻断受影响设备”更稳健形态属建议级、改动面大，不在本轮做。

### 第三轮验证

- 改动文件 `ruff check` + `py_compile` 全通过；`git diff --check` 通过；删除符号（`_identity_yes_bool`/`_EXECUTABLE_RESULT_STATUSES`/`_REVIEWABLE_RESULT_STATUSES`/`_batch_quantity_for_work_hours`）全仓 0 残留。
- 定向回归：`tests/algorithm tests/candidate tests/scheduler_graph` 768 passed；`tests/schedule tests/resource_dispatch tests/operation_execution tests/web_pages tests/algorithm/test_resource_pool_builder_contract.py tests/algorithm/test_dict_cfg_contract.py` 1378 passed。
- 遗留：完整门禁（`run_quality_gate.py`）与 Codex 终轮对抗复审尚未在本轮跑，合入前应补。
