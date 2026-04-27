# Full pytest P0 测试债务治理实施 plan

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：把全量 `pytest tests` 暴露出来的历史失败，治理成“可复跑、可登记、可阻断新增失败、可逐步清零”的工程闭环。

**总体做法**：先冻结当前全量测试事实，再把测试债务接入唯一治理台账和 pytest 收集链，最后把质量门禁改成阻断“新失败”和“证明不完整”，而不是把已知历史债务包装成通过。P0 期间不修排产、Excel、Gantt、启动器、插件或共享层业务语义；只治理测试入口、登记表、runner 和质量门禁证明链。

**涉及技术 / 模块**：`tests/conftest.py`、`tests/main_style_regression_runner.py`、`tools/test_debt_registry.py`、`tools/collect_full_test_debt.py`、`tools/check_full_test_debt.py`、`tools/quality_gate_shared.py`、`tools/quality_gate_ledger.py`、`tools/quality_gate_support.py`、`scripts/run_quality_gate.py`、`scripts/sync_debt_ledger.py`、`开发文档/技术债务治理台账.md`、`tests/test_run_quality_gate.py`、`tests/test_run_full_selftest_report_metadata.py`、`tests/test_full_test_debt_registry_contract.py`。

**影响域声明**：本轮不涉及 `schema.sql`、数据库 migration、Excel 模板、Route、页面模板或用户可见业务文案。`开发文档/技术债务治理台账.md` 的受控 JSON 最终只能由 `scripts/sync_debt_ledger.py` 新命令写入；不得手改结构块。

---

## 0. 已核对事实

### 当前全量测试不是 41 个失败

任务 1 细化前，本轮在当前工作区实际执行：

```bash
.venv/bin/python -m pytest tests -q -ra --tb=short
```

结果是：

```text
36 failed, 539 passed in 55.69s
```

任务 1 执行后，新增的 3 条采集器合同测试已纳入全量收集并在污染链后保持通过；新采集器生成的 raw baseline 当前结果是：

```text
exitstatus=1
collected_count=578
36 failed, 542 passed
classification_counts={
  "required_or_quality_gate_self_failure": 27,
  "main_style_isolation_candidate": 4,
  "candidate_test_debt": 5
}
```

所以后续实现仍不能把“36 个失败”写死成业务真债务，也不能沿用“41 个失败”的旧说法；数字只能来自当次采集器输出，再由基线驱动登记。

当前失败 nodeid 如下：

```text
tests/regression_skill_rank_mapping.py::regression_skill_rank_mapping
tests/regression_startup_host_portfile.py::regression_startup_host_portfile
tests/regression_startup_host_portfile_new_ui.py::regression_startup_host_portfile_new_ui
tests/test_excel_normalizers_contract.py::test_regression_excel_normalizers_mixed_case_script_smoke
tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error
tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error
tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors
tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error
tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_accepts_clean_proof_manifest
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_manifest_replay_rechecks_clean_worktree
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_command_replay_failure
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_replay_disabled_is_structural_only
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_replay_rejects_forged_non_collect_receipt_output
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_reports_failed_manifest_reason
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_hash_mismatch
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_missing_command_receipt_file
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collection_proof
tests/test_run_full_selftest_report_metadata.py::test_quality_gate_binding_status_rejects_fabricated_collect_receipt
tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks
tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree
tests/test_run_quality_gate.py::test_guard_collect_only_keeps_analysis_and_history_in_default_collect
tests/test_run_quality_gate.py::test_main_allow_dirty_worktree_marks_manifest_unbound
tests/test_run_quality_gate.py::test_main_writes_running_then_passed_manifest
tests/test_run_quality_gate.py::test_main_updates_manifest_to_failed_on_command_error
tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_by_default
tests/test_run_quality_gate.py::test_main_rejects_dirty_worktree_when_require_clean_worktree
tests/test_run_quality_gate.py::test_main_dirty_worktree_message_names_untracked_source
tests/test_run_quality_gate.py::test_main_fails_when_tracked_status_changes_during_gate
tests/test_sp05_path_topology_contract.py::test_sp05_route_wrapper_imports_force_fully_registered_scheduler_entrypoint
tests/test_sp05_path_topology_contract.py::test_sp05_behavior_compat_route_wrapper_imports_force_fully_registered_scheduler_entrypoint
tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_domain_package_import_stays_passive
tests/test_sp05_path_topology_contract.py::test_sp05_scheduler_leaf_imports_do_not_pull_registrar_side_effects
```

这些失败里有两条很关键的公共信号：

- `regression_startup_host_portfile*.py` 失败后，后面大量测试都报 `subprocess.Popen` 上缺 `__enter__`。这说明 main-style 回归在同一 pytest 进程里执行，确实可能污染后续测试状态。P0-5 的隔离不是锦上添花，而是公共根因修复。
- 失败清单里包含 `tests/test_run_quality_gate.py` 和 `tests/test_run_full_selftest_report_metadata.py`，而这些文件属于质量门禁自身的 required/proof 测试。它们不能登记成 xfail 债务，必须先作为 P0 工具链自身问题处理。

### 当前 pytest 收集链

- `tests/conftest.py` 用 `_is_main_style_regression(path)` 判断 `regression_*.py + main() + 没有 test_`。
- `RegressionMainFile.collect()` 只生成一个 item，nodeid 形态是 `tests/regression_x.py::regression_x`。
- `RegressionMainItem.runtest()` 当前在同一进程动态 import 并调用 `main()`，只恢复 `os.environ`、`cwd`、`sys.path` 和临时模块名，不会恢复业务模块缓存、全局 monkeypatch、单例和已导入模块状态。

### 当前质量门禁口径

- CI 只跑 `.github/workflows/quality.yml` 里的 `python scripts/run_quality_gate.py --require-clean-worktree`。
- `tools/quality_gate_shared.py::build_quality_gate_command_plan()` 第一个命令是 `python -m pytest --collect-only -q tests`。
- 真正执行的测试是架构适应度、required/guard 清单、startup 回归清单和速查表检查，不是完整 `python -m pytest tests`。
- `QUALITY_GATE_PROOF_SCOPE` 当前声明的是 `required_registry_bound_to_clean_worktree`，同时明确 `does_not_claim = risk_coverage_complete`。

### 当前治理台账口径

- `开发文档/技术债务治理台账.md` 是质量门禁机器可读事实源。
- `scripts/sync_debt_ledger.py` 是台账唯一写入口。
- 当前台账 schema 只覆盖 `oversize_allowlist`、`complexity_allowlist`、`silent_fallback`、`accepted_risks`，还没有 nodeid 级测试债务。

---

## 1. 本次 P0 的硬边界

### 必须做

- 冻结当前全量 pytest 基线，不写死失败数量。
- 给每个已登记失败建立 nodeid、失败类别、根因入口、owner、退出条件。
- 让 pytest 收集阶段能识别已登记债务。
- 让 main-style 回归默认隔离执行，避免污染后续测试。
- 先修复 required/quality-gate 自身失败，再决定剩余失败是否登记成债务。
- 先完成 main-style 子进程隔离，再生成隔离后对比基线；隔离前的 36 只能当 raw baseline，不得直接入账。正式可导入债务基线必须等 required/proof 自身测试普通通过后，由任务 4 生成。
- 让质量门禁证明“没有未登记全量失败”，并能被 receipt/hash/replay 复验。
- 建立 ratchet，让已登记债务只能减少，不能增加。

### 明确不做

- 不修排产、Excel、Gantt、配置页、分析页、启动器、插件的业务语义。
- 不把 `pytest tests` 直接塞进 CI 变成红灯。
- 不新增外部依赖。
- 不新增第二套 CI workflow 命令。
- 不把 `core/shared` 纳入新的架构扫描范围。
- 不扩大路由直接装配门禁范围。
- 不把 `evidence/TestDebt/` 作为长期事实源。

### 无新增兜底停线

实施时必须先跑下面的 diff 扫描。凡是计划修改文件里出现新增 `if`、`elif`、`else`、`try`、`except`、`fallback`、`兜底`、`回退`、`getattr`、`hasattr`，执行者必须停下来向用户说明为什么必须加；用户确认前不能继续。

```bash
git diff -U0 -- \
  tests/conftest.py \
  tests/main_style_regression_runner.py \
  tools/test_debt_registry.py \
  tools/collect_full_test_debt.py \
  tools/check_full_test_debt.py \
  tools/quality_gate_shared.py \
  tools/quality_gate_ledger.py \
  tools/quality_gate_support.py \
  scripts/run_quality_gate.py \
  scripts/sync_debt_ledger.py \
  | rg '^\+.*\b(if|elif|else|try|except|getattr|hasattr)\b|^\+.*(fallback|兜底|回退|or \[\]|or \{\})'
```

这个约束的意思很直接：本轮不靠特殊判断、旧路径兼容、收集不到就跳过、证明不完整也继续跑来解决问题。需要判断错误时，必须是显式失败合同，不能是隐藏兜底。

这条不是说 runner、CLI、schema 校验永远不可能写条件判断；这些入口天然要判断返回码、退出码和字段是否合法。它的执行规则是：任何新增条件或异常处理都必须先单独解释“为什么不用它就无法表达显式失败合同”，并得到用户确认。未经确认，不得实现。

---

## 2. 文件结构与职责

### 新建文件

- `tools/collect_full_test_debt.py`：运行 full pytest，并通过 pytest hook 产出结构化 JSON；不解析终端文本。
- `tools/check_full_test_debt.py`：读取 full pytest 结构化结果和测试债务登记，判断是否存在未登记失败、登记缺失、超过 ratchet 上限。
- `tools/test_debt_registry.py`：读取 `开发文档/技术债务治理台账.md` 里的 `test_debt` 结构块字段，并提供校验 API。
- `tests/main_style_regression_runner.py`：main-style 回归子进程 runner，只负责 import 目标脚本、调用 `main()`、把返回值/SystemExit 映射为进程退出码。文件名不得以 `regression_` 开头，避免被 `tests/conftest.py` 的 main-style collector 收进测试集。
- `tests/test_full_test_debt_registry_contract.py`：测试债务登记合同测试。
- `tests/test_regression_main_isolation_contract.py`：main-style 子进程隔离合同测试。
- `audit/2026-04/20260427_full_pytest_p0_baseline.md`：人工可读基线摘要，记录当次失败数量、命令、解释器、失败 nodeid、失败类别。

### 修改文件

- `开发文档/技术债务治理台账.md`：扩展受控 JSON，新增 `test_debt` 区域。
- `tools/quality_gate_ledger.py`：扩展台账默认值、校验、排序、渲染，支持 `test_debt`。
- `scripts/sync_debt_ledger.py`：增加导入 full pytest baseline 和更新 test debt 人工字段的命令。
- `tools/quality_gate_shared.py`：把 full-test-debt 检查脚本纳入统一命令计划、source proof 和工具类型检查。
- `tools/quality_gate_support.py`：保持纯导入门面，只导出新 registry/check helper；不得增加条件导入。
- `scripts/run_quality_gate.py`：继续按 shared command plan 执行，不写第二套命令；如果 shared plan 接入后脚本本体无需变化，不得为了“计划里写了修改”强行制造 diff。
- `tests/conftest.py`：给 main-style 回归接入子进程 runner；给当前收集到的已登记测试债务加 xfail marker。不得在普通 collection hook 里检查“登记 nodeid 是否全部被收集”，否则定向测试会被全量台账拖死。
- `tests/test_run_quality_gate.py`：更新命令顺序、manifest/receipt 断言。
- `tests/test_run_full_selftest_report_metadata.py`：更新 quality gate command replay 和 proof 断言。
- `README.md`：说明本地入口和 CI `--require-clean-worktree` 的关系，避免误解。
- `开发文档/README.md`：同步测试债务、main-style 隔离、全量测试登记规则。

### 必须不修改

- `core/shared/**`
- `core/services/scheduler/**`
- `web/bootstrap/launcher.py`
- `web/bootstrap/plugins.py`
- `web/routes/**`
- `.github/workflows/quality.yml`
- `requirements-dev.txt`

如果实现过程中发现必须修改上面文件，停下来说明原因并等待用户确认。

---

## 3. 实施任务

### 任务 1：冻结当前 raw full pytest 基线（已细化并执行）

**目标**
- 让“隔离前当前到底失败多少条、分别是哪几条、哪些明显来自污染链”变成可复跑的 raw 事实，而不是口头数字。这个 raw baseline 只用于排查和对比，不允许直接导入债务台账。
- 本任务只解决“可靠记录现场”，不修 main-style 隔离、不登记测试债、不改 `开发文档/技术债务治理台账.md`。

**根因核实**
- 当前 main-style 回归由 `tests/conftest.py` 在同一 pytest 进程里 import 后直接调用 `main()`，只恢复 `os.environ`、`cwd`、`sys.path` 和临时模块名。
- 已确认 `subprocess.Popen` 污染的直接来源是 `tests/regression_start_and_rerun_route_resolution.py` 把 runner 模块里的 `subprocess.Popen` 赋值为 `_fake_popen`；由于 runner 导入的是标准库 `subprocess`，后续测试会继续拿到假的 `Popen`。
- `tests/regression_startup_host_portfile.py` 与 `tests/regression_startup_host_portfile_new_ui.py` 本身只是调用 `subprocess.Popen(...)`，不是赋值污染源；它们是后续首先踩到 `_DummyProc` 的测试。
- `required_or_quality_gate_self_failure` 不允许硬编码 3 个文件，必须动态来自 `tools.quality_gate_shared.iter_quality_gate_required_tests()`。

**文件**
- 新建：`tools/collect_full_test_debt.py`
- 新建：`audit/2026-04/20260427_full_pytest_p0_raw_baseline.md`
- 新建：`tests/test_full_test_debt_registry_contract.py`
- 本任务不新建：`tools/test_debt_registry.py`
- 本任务不新建：`tests/main_style_regression_runner.py`

**采集器合同**
- 命令形态固定为：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py \
  --baseline-kind raw_before_isolation \
  --write-baseline audit/2026-04/20260427_full_pytest_p0_raw_baseline.md \
  -- tests -q --tb=short -ra -p no:cacheprovider
```

- stdout 必须是纯 JSON，pytest 进度、失败摘要、warning 和 logging 内部噪声不得混进 stdout。
- 命令退出码必须透传 pytest：当前 raw 失败现场应返回 `1`，不能把失败包装成成功。
- baseline Markdown 必须使用机器块标记：先写 `<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->`，中间放一个 `json` 代码块，最后写 `<!-- APS-FULL-PYTEST-BASELINE:END -->`。

- JSON 字段固定包含：`schema_version`、`baseline_kind`、`importable`、`generated_at`、`head_sha`、`python_executable`、`python_version`、`pytest_version`、`pytest_args`、`exitstatus`、`collected_nodeids`、`collection_errors`、`reports`、`summary`、`classifications`。
- `reports` 每条固定包含：`nodeid`、`when`、`outcome`、`duration`、`longrepr`；`when` 必须保留 `setup`、`call`、`teardown`。
- `baseline_kind` 必须是 `raw_before_isolation`，`importable` 必须是 `false`。

- [x] **步骤 1：写采集器合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 中构造临时 pytest 项目，覆盖：
- 普通通过。
- 普通失败。
- 参数化 nodeid，要求保留 `[...]`。
- setup 阶段失败。
- teardown 阶段失败。
- collection error。
- main-style `tests/regression_x.py::regression_x`。
- stdout 纯 JSON。
- `proc.returncode == payload["exitstatus"]`。
- baseline Markdown 机器块可被 JSON 解析。

- [x] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

实际结果：

```text
3 failed
失败原因：tools/collect_full_test_debt.py 尚不存在，stdout 不是 JSON。
```

- [x] **步骤 3：写采集器**

实现 `tools/collect_full_test_debt.py`：
- 使用 pytest hook 对象采集结果，不解析 `-q -ra --tb=short` 终端文本。
- 采集 `pytest_collection_modifyitems`、`pytest_runtest_logreport`、`pytest_collectreport`、`pytest_sessionfinish`。
- 默认把 JSON 写到 stdout；显式传 `--write-baseline` 时写 baseline Markdown。
- 不写 `evidence/TestDebt/`，避免质量门禁时产生新的 tracked evidence。
- 分类规则：
  - required/proof：动态匹配 `iter_quality_gate_required_tests()`。
  - main-style 隔离候选：main-style nodeid，或失败文本包含 `_DummyProc`、`AttributeError: __enter__`、`subprocess.py` + `Popen`。
  - 其余失败进入 `candidate_test_debt`，但仍不可导入。

- [x] **步骤 4：重新运行合同测试**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_start_and_rerun_route_resolution.py tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
```

实际结果：

```text
3 passed in 0.52s
4 passed in 0.59s
py_compile 通过
ruff check 通过
pyright 0 errors, 0 warnings
治理台账校验通过，schema_version=1，silent_fallback_count=159
```

说明：第二条命令把已确认的 Popen 污染源放在新合同测试前面，证明新合同测试不会再因为同进程污染变成 raw baseline 里的新增假失败。

- [x] **步骤 5：生成当前 raw baseline**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py \
  --baseline-kind raw_before_isolation \
  --write-baseline audit/2026-04/20260427_full_pytest_p0_raw_baseline.md \
  -- tests -q --tb=short -ra -p no:cacheprovider \
  > /tmp/full_pytest_p0_raw.json \
  2> /tmp/full_pytest_p0_raw.stderr
```

实际结果：

```text
exitstatus=1
stderr_bytes=0
collected_count=578
failed_nodeid_count=36
call:failed=36
call:passed=542
collection_error_count=0
```

分类结果：

```text
required_or_quality_gate_self_failure=27
main_style_isolation_candidate=4
candidate_test_debt=5
```

生成文件：

```text
audit/2026-04/20260427_full_pytest_p0_raw_baseline.md
```

该文件明确写入：
- `baseline_kind = "raw_before_isolation"`
- `importable = false`
- `exitstatus = 1`
- 机器可读 JSON 结构块

后续任务不得把这份 raw baseline 作为 `import-test-debt-baseline` 输入；任务 2 完成 main-style 隔离后，只生成隔离后的对比基线，仍然 `importable=false`，只用于任务 3 承接。正式可导入债务基线必须等任务 3 处理完 required/proof 自身失败后，在任务 4 生成。

### 任务 2：先完成 main-style 子进程隔离

**任务 1 已完成，可直接承接的工作**
- 已新增 `tools/collect_full_test_debt.py`，可以继续用它生成隔离前后 full pytest 的结构化对比。
- 已新增 `tests/test_full_test_debt_registry_contract.py`，并验证它即使排在污染源 `tests/regression_start_and_rerun_route_resolution.py` 后面也不会被 `subprocess.Popen` 污染带倒。
- 已生成 raw baseline：`audit/2026-04/20260427_full_pytest_p0_raw_baseline.md`。
- 当前 raw baseline 明确是 `baseline_kind = "raw_before_isolation"`、`importable = false`，不得导入台账。
- 当前 raw baseline 结果：`collected_count=578`，`failed_nodeid_count=36`，其中 `required_or_quality_gate_self_failure=27`、`main_style_isolation_candidate=4`、`candidate_test_debt=5`。
- 已确认污染链根因入口：`tests/regression_start_and_rerun_route_resolution.py` 把 runner 模块里的 `subprocess.Popen` 赋值为 `_fake_popen`；由于 runner 引用标准库 `subprocess`，污染会传给后续测试。
- `tests/regression_startup_host_portfile.py` 与 `tests/regression_startup_host_portfile_new_ui.py` 不是赋值污染源，只是隔离前首先踩到 `_DummyProc` 的后续测试。
- 本任务完成后必须用同一个采集器重新生成隔离后的对比 baseline，不能复用任务 1 的 raw baseline；该对比 baseline 不允许导入台账，正式 baseline 留给任务 4。

**根因核实与对抗审查结论**
- 已用 5 个只读 subagent 做根因核实和对抗审查，结论一致：任务 2 的方向正确，根因不是 required/proof 测试本身坏了，而是 main-style 回归在同一个 pytest 进程内 import 后直接调用 `main()`，把测试进程里的标准库模块状态污染了。
- `tests/conftest.py::RegressionMainItem.runtest()` 当前同进程执行 main-style 回归，只恢复 `cwd`、`os.environ`、`sys.path` 和临时模块名，不会恢复标准库模块对象、业务模块缓存、单例或 monkeypatch。
- `tests/regression_start_and_rerun_route_resolution.py` 的 `_fake_popen` 是当前已确认的直接污染源；`tests/regression_startup_host_portfile.py` 与 `tests/regression_startup_host_portfile_new_ui.py` 只是后续首先踩到污染的测试，不是赋值污染源。
- `tests/test_full_test_debt_registry_contract.py` 排在污染源后仍能通过，只能证明该合同测试自己保存了原始 `subprocess.Popen` 并用它启动子进程，不能证明普通后续测试不会被污染。
- 对抗审查要求收紧 baseline 口径：任务 2 只能产出隔离后对比基线，`importable=false`；如果隔离后 `regression_*.py` 仍有普通断言失败，不能再仅凭文件名把它排除出候选债务，只有仍带 `_DummyProc`、`AttributeError: __enter__`、`subprocess.py` + `Popen` 等污染签名的失败才继续归为隔离问题。

**目标**
- 解决 main-style 回归污染同一 pytest 进程的问题，避免把污染制造出来的假失败登记为测试债务。

**文件**
- 修改：`tests/conftest.py`
- 修改：`tools/collect_full_test_debt.py`
- 修改：`tests/test_full_test_debt_registry_contract.py`
- 新建：`tests/main_style_regression_runner.py`
- 测试：`tests/test_regression_main_isolation_contract.py`
- 新建：`audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md`

- [ ] **步骤 1：写隔离合同测试**

在 `tests/test_regression_main_isolation_contract.py` 写临时 pytest 项目，并让临时项目的 `tests/conftest.py` 桥接真实的 `tests/conftest.py`，不得复制一份假的 collector。覆盖：
- `pytest --collect-only -q` 收集到的 nodeid 仍是 `tests/regression_x.py::regression_x`。
- `main()` 返回 `0` 时 pytest 通过。
- `main()` 返回 `None` 或 `bool` 时沿用旧语义：不当作失败。
- `main()` 返回非 0 时 pytest 失败。
- `main()` 抛 `SystemExit(0)` 时 pytest 通过。
- `main()` 抛 `SystemExit(2)` 时 pytest 失败。
- 子进程运行时 `cwd` 固定为仓库根，并且 runner 能从仓库根 import `core/`。
- 失败信息必须包含 `returncode`、目标脚本路径、`cwd`、stdout、stderr。
- regression 脚本修改 `subprocess.Popen` 后，不影响后续普通 pytest 用例。
- runner 文件自身不会被 `pytest --collect-only -q tests` 收集成 `regression_main_runner` 之类的 main-style item。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_regression_main_isolation_contract.py --tb=short -p no:cacheprovider
```

预期：至少污染检查失败，因为当前 `RegressionMainItem.runtest()` 是同进程执行；runner 文件存在性检查也会失败，因为 `tests/main_style_regression_runner.py` 尚不存在。

- [ ] **步骤 3：实现 runner**

`tests/main_style_regression_runner.py` 只负责：
- 接收一个脚本路径参数。
- 把仓库根加入 `sys.path`，保证 regression 脚本在子进程里仍能 import `core/`、`data/`、`web/`。
- 动态 import 目标脚本。
- 调用 `main()`。
- 把返回非 0 int 或非 0 `SystemExit` 转成进程非 0；`return None`、非 int、`bool`、`0` 继续按旧语义视为成功。
- 原样输出 stdout/stderr。
- 普通异常不吞掉，用 Python traceback 和非 0 退出暴露。

不得保留 in-process 执行路径。main-style 回归只有一种执行方式：子进程。

这一步必然需要处理返回码和 `SystemExit`。在实现前，执行者必须向用户说明新增条件分支的必要性：这些分支不是兜底，而是把 main-style 脚本的退出合同显式转换成 pytest 结果；未经确认不得写代码。

- [ ] **步骤 4：改造 `RegressionMainItem.runtest()`**

在 `tests/conftest.py` 中让 `RegressionMainItem.runtest()` 调用：

```bash
sys.executable <绝对路径 tests/main_style_regression_runner.py> <绝对路径 regression 脚本>
```

要求：
- pytest nodeid 不变。
- cwd 是仓库根。
- 子进程退出非 0 时，pytest item 失败。
- 子进程 stdout/stderr、退出码、cwd、脚本路径进入 pytest 失败信息。
- 子进程启动失败、runner 缺失、目标脚本导入失败时，直接失败，不允许回退到旧的同进程 import + `main()`。

- [ ] **步骤 5：扩展隔离后采集口径**

修改 `tools/collect_full_test_debt.py`：
- `--baseline-kind` 允许 `after_main_style_isolation`。
- `after_main_style_isolation` 的输出仍然 `importable=false`。
- `raw_before_isolation` 下，main-style nodeid 可以归入 `main_style_isolation_candidate`。
- `after_main_style_isolation` 下，不能只因为文件名是 `regression_*.py` 就归入 `main_style_isolation_candidate`；只有 longrepr 仍带 `_DummyProc`、`AttributeError: __enter__`、`subprocess.py` + `Popen` 污染签名时，才归入 `main_style_isolation_candidate`。

在 `tests/test_full_test_debt_registry_contract.py` 增加采集器合同：
- `after_main_style_isolation` 能被 CLI 接受。
- 隔离后的普通 `regression_*.py` 失败进入 `candidate_test_debt`。
- 带污染签名的失败仍进入 `main_style_isolation_candidate`。

- [ ] **步骤 6：重新运行隔离合同、污染源窄验证、全量两遍和隔离后对比基线**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_regression_main_isolation_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_start_and_rerun_route_resolution.py tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tests/conftest.py tests/main_style_regression_runner.py tests/test_regression_main_isolation_contract.py tools/collect_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/conftest.py tests/main_style_regression_runner.py tests/test_regression_main_isolation_contract.py tools/collect_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tests/conftest.py tests/main_style_regression_runner.py tests/test_regression_main_isolation_contract.py tools/collect_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q -ra --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q -ra --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py \
  --baseline-kind after_main_style_isolation \
  --write-baseline audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md \
  -- tests -q --tb=short -ra -p no:cacheprovider
```

预期：
- 隔离合同通过。
- 采集器合同通过。
- 污染源放在 quality gate 单测前面时，不再把后者打成 `AttributeError: __enter__`。
- 两次 full pytest 的结果一致。
- 不再出现 `subprocess.Popen` 被前序测试污染导致的 `__enter__` 批量失败。
- 生成 `audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md`，并明确 `baseline_kind=after_main_style_isolation`、`importable=false`。

**任务 2 执行结果（任务 3 承接用）**
- 状态：已完成。任务 2 已把 main-style 回归从同一 pytest 进程内执行改成子进程执行，并生成隔离后对比基线。
- 实际改动范围：修改 `tests/conftest.py`、`tools/collect_full_test_debt.py`、`tests/test_full_test_debt_registry_contract.py`；新建 `tests/main_style_regression_runner.py`、`tests/test_regression_main_isolation_contract.py`、`audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md`。未修改 `tests/test_run_quality_gate.py`、`tests/test_run_full_selftest_report_metadata.py`、`tools/quality_gate_shared.py`、`scripts/run_quality_gate.py`。
- 隔离合同结果：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_regression_main_isolation_contract.py tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider` 最终复跑结果为 `8 passed in 2.57s`。
- 污染源前置验证：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_start_and_rerun_route_resolution.py tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks --tb=short -p no:cacheprovider` 结果为 `2 passed in 0.12s`，说明污染源前置后不再打倒后续 quality gate 单测。
- 定向静态验证：`py_compile` 通过；`ruff check` 通过；`pyright` 为 `0 errors, 0 warnings, 0 informations`。
- 两次 full pytest 结果：第一遍 `5 failed, 578 passed in 96.80s`；第二遍 `5 failed, 578 passed in 99.80s`。两次失败 nodeid 一致，未再出现 `_DummyProc`、`AttributeError: __enter__`、`subprocess.Popen` 污染链批量失败。
- 隔离后采集器结果：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation --write-baseline audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md -- tests -q --tb=short -ra -p no:cacheprovider` 退出码为 `1`（透传剩余 5 个 pytest 失败），`stderr_bytes=0`，`collected_count=583`，`failed_nodeid_count=5`，`classification_counts={"required_or_quality_gate_self_failure": 0, "main_style_isolation_candidate": 0, "candidate_test_debt": 5}`。
- required/proof 移交清单：无 required/proof 失败移交给任务 3；raw baseline 中的 27 个 required/proof 失败已随 main-style 隔离消失。任务 3 仍需保留“required/proof 禁入 candidate_test_debt 候选债务”的 collector 合同；`mode=xfail` 登记拒绝留给任务 5/6/8。
- candidate_test_debt 移交清单：`tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors`、`tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error`、`tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error`、`tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error`、`tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows`。
- baseline 处置：`audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md` 已生成，明确 `baseline_kind=after_main_style_isolation`、`importable=false`。该文件只作为任务 3/任务 4 的交接证据，不得直接导入台账。
- 是否触发停线：未触发任务 2 停线；没有修改 quality gate / required / proof 文件，没有修改业务层，没有修改 workflow，没有新增外部依赖。

### 任务 3：确认 required/proof 已恢复，并阻止它们进入候选债务

**任务 2 承接说明**
- 任务 2 已完成 main-style 子进程隔离：`tests/conftest.py` 不再同进程 import 并调用 main-style 回归，而是用 `tests/main_style_regression_runner.py` 在子进程里执行；`tools/collect_full_test_debt.py` 已支持 `after_main_style_isolation` 对比基线，并修正隔离后的分类规则。
- 任务 2 的实际验证结果是：隔离合同和采集器合同 `8 passed`，污染源前置 quality gate 单测 `2 passed`，两次 full pytest 都稳定为 `5 failed, 578 passed`，隔离后对比基线显示 required/proof 失败数为 0、main-style 污染候选为 0、候选测试债务为 5。
- 本任务只接收任务 2 回填的隔离后对比结果。任务 1 的 raw baseline 只能作为历史对照，不能作为债务导入依据。
- raw baseline 里的 27 条 required/proof 失败已随任务 2 的 main-style 子进程隔离消失；本任务不再默认修改 required/proof 测试文件。
- 本任务只补 collector 层防回退：required/proof 失败不得进入 `candidate_test_debt`，只能进入 `required_or_quality_gate_self_failure`。
- 真正的 `mode=xfail` 登记拒绝、台账 schema、pytest xfail hook、full-test-debt proof 接入，全部留给任务 5、任务 6、任务 8；本任务不得提前实现。
- 只有 required/proof 普通通过，并且 collector 合同确认 required/proof 不进入候选债务后，任务 4 才能重新生成正式基线。

**目标**
- 确认质量门禁自己的 required/proof 测试已经普通通过。
- 增加一条现状锁定测试，防止后续把 required/proof 失败误采集成可导入的候选测试债务。

**文件**
- 修改：`tests/test_full_test_debt_registry_contract.py`
- 修改：`.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`
- 验证：`tests/test_run_quality_gate.py`
- 验证：`tests/test_run_full_selftest_report_metadata.py`
- 验证：`tests/test_sp05_path_topology_contract.py`
- 测试：`tests/test_run_quality_gate.py`
- 测试：`tests/test_run_full_selftest_report_metadata.py`
- 测试：`tests/test_sp05_path_topology_contract.py`

- [ ] **步骤 1：写 required/proof 禁入候选债务防回退测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加：

```python
def test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt():
    ...
```

断言：
- 临时项目里写一个 required/proof 路径失败，优先使用 `QUALITY_GATE_SELFTEST_PATH` 对应的 `tests/test_run_quality_gate.py`。
- 同时写一个普通失败测试。
- collector 使用 `--baseline-kind after_main_style_isolation` 运行。
- required/proof nodeid 只进入 `required_or_quality_gate_self_failure`。
- required/proof nodeid 不进入 `candidate_test_debt`。
- 普通失败仍进入 `candidate_test_debt`。
- payload 的 `importable` 仍为 `false`。

说明：这是一条现状锁定测试，很可能一开始就通过；如果通过，不得为了制造 diff 去改 `tools/collect_full_test_debt.py`。

- [ ] **步骤 2：运行 collector 合同测试**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_full_test_debt_registry_contract.py \
  --tb=short -p no:cacheprovider
```

预期：
- 通过。
- 如果失败，且失败原因是 required/proof 进入了 `candidate_test_debt`，才允许最小修改 `tools/collect_full_test_debt.py`。
- 不允许在本任务中新建 `tools/test_debt_registry.py`、`tools/check_full_test_debt.py`，不允许改 `tools/quality_gate_ledger.py`、`scripts/sync_debt_ledger.py`，不允许接 pytest xfail hook。

- [ ] **步骤 3：跑 required/proof 定向证明**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_run_quality_gate.py \
  tests/test_run_full_selftest_report_metadata.py \
  tests/test_sp05_path_topology_contract.py \
  --tb=short -p no:cacheprovider
```

预期：
- 通过。
- 如果失败，立即停线；只允许查测试工具链自身夹具或 helper，不允许登记债务，不允许改业务层。

- [ ] **步骤 4：运行静态快检**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile \
  tests/test_full_test_debt_registry_contract.py \
  tools/collect_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check \
  tests/test_full_test_debt_registry_contract.py \
  tools/collect_full_test_debt.py
```

预期：通过。若本任务被迫修改 `tools/collect_full_test_debt.py`，再补跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright \
  tests/test_full_test_debt_registry_contract.py \
  tools/collect_full_test_debt.py
```

- [ ] **步骤 5：审查与回填**

要求：
- 先调用只读子代理做需求符合性审查，确认没有提前实现任务 5/6/8，也没有修改三份 required/proof 测试文件。
- 再调用只读子代理做测试与文档回填质量审查。
- 审查不过先修复，再重新审查。
- 审查通过后，在本任务下补写执行结果；同时在任务 4 头部补写任务 3 交接说明。

**任务 3 执行结果（任务 4 承接用）**
- 状态：已完成。任务 3 只补了 collector 层 required/proof 禁入候选债务的现状锁定测试，并回填计划；未修改 `tests/test_run_quality_gate.py`、`tests/test_run_full_selftest_report_metadata.py`、`tests/test_sp05_path_topology_contract.py`。
- 根因结论：raw baseline 里的 27 条 required/proof 失败不是这些测试自身坏了，而是任务 2 已确认的 main-style 同进程污染带出的假失败。隔离后基线中 `required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`、`candidate_test_debt=5`。
- 禁入结果：新增 `test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt`，确认 `QUALITY_GATE_SELFTEST_PATH` 对应的 required/proof 失败只进入 `required_or_quality_gate_self_failure`，不进入 `candidate_test_debt`，普通失败仍进入 `candidate_test_debt`，payload 仍为 `importable=false`。
- 验证结果：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider` 结果为 `5 passed in 0.89s`；`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py tests/test_sp05_path_topology_contract.py --tb=short -p no:cacheprovider` 结果为 `51 passed in 6.79s`；`py_compile` 通过；`ruff check` 通过。
- 审查结果：需求符合性审查先发现任务 2 交接里残留旧的 `xfail` 口径，已改为 `candidate_test_debt` 候选债务；代码质量审查建议补充 `baseline_kind` 和 `main_style_isolation_candidate` 断言，已纳入测试。
- 停线状态：未触发。未新建正式 baseline，未导入台账，未提前实现任务 5/6/8，未修改业务层或 workflow。

### 任务 4：生成隔离后的正式 full pytest 债务基线

**任务 3 交接说明**
- raw baseline 只作历史对照，不能作为正式导入输入。
- `audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md` 只作任务 2/3 交接证据，不能直接导入台账；该文件的 `head_sha` 不是任务 4 执行时的新 HEAD。
- 任务 3 已确认 required/proof 当前普通通过；后续不得把 `QUALITY_GATE_REQUIRED_TESTS` 覆盖的 nodeid 导入 `candidate_test_debt` 候选债务或登记为 `mode=xfail`。
- 任务 4 必须重新生成正式基线，并显式校验 `required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`。
- 只读复验当前 HEAD 时，full pytest 采集仍为 5 个候选债务，且 `required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`、`head_sha` 对上当前提交；该结果只作为任务 4 细化依据，正式结果以后续新基线为准。
- 5 个调查 / 对抗审查 subagent 的结论一致：当前采集器只有“隔离后对比基线”，没有“正式可导入基线”的机器合同；因此任务 4 不能只重跑旧命令。

**目标**
- 在 main-style 污染消除、required/proof 自身测试通过之后，补齐“可导入债务正式基线”的机器合同，并重新生成当前 HEAD 下的正式 full pytest 债务基线。
- 正式基线必须诚实记录 full pytest 原始退出码仍为 1，同时用 `importable=true` 表示“剩余失败已经全部归入候选测试债务，可交给任务 5 导入台账”。

**文件**
- 修改：`tools/collect_full_test_debt.py`
- 修改：`tests/test_full_test_debt_registry_contract.py`
- 新建：`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`
- 修改：`.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`

- [x] **步骤 1：写正式可导入基线合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加测试，覆盖：
- 新参数 `--importable-debt-baseline` 能生成 `importable=true` 的正式 baseline。
- 普通 `--baseline-kind after_main_style_isolation` 仍保持 `importable=false`，并继续写“不能导入”的说明。
- `--importable-debt-baseline` 只能和 `--baseline-kind after_main_style_isolation`、`--write-baseline` 一起使用。
- required/proof 分类、main-style 污染分类、collection error 任一非 0 时，命令退出 `2`，且不写正式 baseline。
- 正式 baseline 的机器块可解析，`summary` 和 `classifications` 与 stdout payload 一致。

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

预期：先失败，原因是采集器还没有 `--importable-debt-baseline`。

- [x] **步骤 2：实现正式可导入基线合同**

修改 `tools/collect_full_test_debt.py`：
- 新增 `--importable-debt-baseline` 参数。
- 该参数必须同时满足 `--baseline-kind after_main_style_isolation` 与 `--write-baseline`，否则直接退出 `2`。
- 带该参数时，payload 写 `importable=true`，Markdown 标题为 `Full pytest P0 debt baseline`，说明写明“可作为任务 5 导入测试债务台账的正式输入”。
- 不带该参数时，现有 `after_main_style_isolation` 行为不变，继续 `importable=false`，继续标明“不允许导入债务台账”。
- 带该参数时，如果 `required_or_quality_gate_self_failure`、`main_style_isolation_candidate` 或 `collection_error_count` 任一非 0，命令退出 `2`，不写正式 baseline。
- 带该参数且只剩已分类候选债务时，命令返回 `0`；payload 里的 `exitstatus` 仍保留 pytest 原始退出码。

- [x] **步骤 3：重新运行合同测试与静态验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/collect_full_test_debt.py tests/test_full_test_debt_registry_contract.py
```

预期：全部通过。

- [x] **步骤 4：生成正式基线**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py \
  --baseline-kind after_main_style_isolation \
  --importable-debt-baseline \
  --write-baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md \
  -- tests -q --tb=short -ra -p no:cacheprovider
```

预期：
- 命令退出码为 `0`。
- 基线包含机器可读 JSON 结构块。
- 基线标注 `baseline_kind = "after_main_style_isolation"`。
- 基线标注 `importable = true`。
- payload 中的 `exitstatus = 1`，表示 full pytest 仍有已知历史失败。
- `head_sha` 等于当前 `git rev-parse HEAD`。
- required/proof nodeid 不在 `candidate_test_debt` 中。
- `required_or_quality_gate_self_failure=0`。
- `main_style_isolation_candidate=0`。
- `collection_error_count=0`。
- `candidate_test_debt=5`，且 nodeid 精确等于任务 2/3 移交的 5 条。
- 如果剩余失败数为 0，后续 `test_debt.entries` 为空，`max_registered_xfail=0`。

- [x] **步骤 5：写入 5 条候选债务归因摘要**

正式基线生成后，在本任务执行结果里写清以下 5 条候选债务，任务 5 导入时不得写 `untriaged` 占位：

| nodeid | domain | style | root.module | root.function | owner | exit_condition |
|---|---|---|---|---|---|---|
| `tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error` | `personnel.operator_machine` | `stale_patch_target` | `core.services.personnel.operator_machine_normalizers` | `normalize_skill_level_optional` | `personnel.operator_machine` | 更新测试 patch 目标或改成公开入口验证，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。 |
| `tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error` | `personnel.operator_machine` | `stale_patch_target` | `core.services.personnel.operator_machine_normalizers` | `normalize_skill_level_stored` | `personnel.operator_machine` | 更新测试 patch 目标或改成公开入口验证，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。 |
| `tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors` | `personnel.operator_machine` | `stale_patch_target` | `core.services.personnel.operator_machine_service` | `list_by_operator` | `personnel.operator_machine` | 更新读侧异常传播测试的 patch 目标，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。 |
| `tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error` | `personnel.operator_machine` | `return_contract_drift` | `core.services.personnel.operator_machine_service` | `_resolve_write_values` | `personnel.operator_machine` | 按当前“返回旧值和错误消息、调用方跳过写入”的合同更新测试，或先改实现再同步测试；该 nodeid 定向 pytest 普通通过后，从正式 full pytest 债务基线移除。 |
| `tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows` | `personnel.operator_machine` | `readside_normalization_contract_drift` | `core.services.personnel.operator_machine_query_service` | `OperatorMachineQueryService._normalize_row` | `personnel.operator_machine` | 更新测试，明确断言归一化后的 `skill_level/is_primary` 以及 `dirty_fields/dirty_reasons`；该 nodeid 定向 pytest 普通通过后，从正式 full pytest 债务基线移除。 |

共同归因：`debt_family=operator_machine_normalization_contract_drift`。后续登记和 xfail 必须按精确 nodeid 拆 5 条，不能只登记 family。

- [x] **步骤 6：审查、回填与任务 5 承接**

要求：
- 调用只读 subagent 做需求符合性审查，确认没有提前实现任务 5/6/8，没有修改台账 schema、pytest xfail、quality gate proof 或 workflow。
- 调用只读 subagent 做代码质量审查，确认正式基线合同没有破坏 raw / after-isolation 旧口径。
- 审查不过先修复，再重新审查。
- 审查通过后，在本任务下补写执行结果；同时在任务 5 头部写清任务 4 生成了什么、5 条候选债务分别是什么、任务 5 只能接正式 baseline。

**任务 4 执行结果（任务 5 承接用）**
- 状态：已完成。任务 4 已补上正式可导入 full pytest 债务基线的机器合同，生成当前 HEAD 下的新正式 baseline，并把 5 条候选债务的归因写清楚。
- 实际改动范围：修改 `tools/collect_full_test_debt.py`、`tests/test_full_test_debt_registry_contract.py`、`.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`；新建 `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`。未修改 `开发文档/技术债务治理台账.md`、`tools/quality_gate_ledger.py`、`scripts/sync_debt_ledger.py`、`tests/conftest.py`、`tools/quality_gate_shared.py`、`.github/workflows/quality.yml`。
- 合同结果：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider` 最终结果为 `9 passed in 1.61s`。其中新增合同确认：普通 `after_main_style_isolation` 仍 `importable=false`；只有 `--importable-debt-baseline` 才会产出 `importable=true`；required/proof、main-style 污染、collection error 任一存在时，正式 baseline 直接拒绝写入；pytest 参数错误等非预期退出码也会拒绝写入正式 baseline。
- 静态验证：`py_compile` 通过；`ruff check` 通过；`pyright` 为 `0 errors, 0 warnings, 0 informations`。
- 正式 baseline：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation --importable-debt-baseline --write-baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md -- tests -q --tb=short -ra -p no:cacheprovider` 退出码为 `0`；payload 中 `exitstatus=1`，表示 full pytest 仍有已知历史失败。
- 正式 baseline 机器块校验：`head_sha=ee96b3248a2bdf8abf48a5c5eba8d152379c8fdf`，与当前 `git rev-parse HEAD` 一致；`baseline_kind=after_main_style_isolation`；`importable=true`；`collected_count=588`；`failed_nodeid_count=5`；`classification_counts={"candidate_test_debt": 5, "main_style_isolation_candidate": 0, "required_or_quality_gate_self_failure": 0}`；`collection_error_count=0`。
- 5 条候选债务：`tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors`、`tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error`、`tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error`、`tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error`、`tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows`。
- 归因结论：5 条都属于 `personnel.operator_machine`，共同 `debt_family=operator_machine_normalization_contract_drift`，但任务 5 必须按精确 nodeid 拆成 5 条登记；其中 3 条是 `stale_patch_target`，1 条是 `return_contract_drift`，1 条是 `readside_normalization_contract_drift`。
- 任务 5 接口：只能读取 `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 的机器块；不得读取旧的 `audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md`；不得给任何条目写 `untriaged` 占位；不得把 required/proof 测试登记为 xfail。
- 审查与返修：需求符合性审查通过。代码质量审查发现正式模式会把 pytest 参数错误误判成可导入 baseline，已补 `pytest_exitstatus` 禁入合同并复跑通过。
- 停线状态：未触发 required/proof 禁入、main-style 污染、collection error、workflow 修改或业务层修改。新增条件分支都属于本任务已说明的“正式 baseline 参数校验 / 禁入分类与 pytest 异常退出显式失败合同”。

**任务 6 后深审返修记录（2026-04-27）**
- 多路只读 deep review 确认：上面的正式 baseline 不能再作为“可按自身 `head_sha` 复跑”的证明使用。它记录的 `head_sha=ee96b3248a2bdf8abf48a5c5eba8d152379c8fdf` 不包含 `--importable-debt-baseline` 参数；该参数在后续提交才出现。
- 根因不是候选 nodeid 本身错了，而是正式 baseline 当时使用了未提交的 collector 能力生成，payload 只记录 `git rev-parse HEAD`，没有记录生成前工作区是否干净。
- 本次返修不改写历史结论，只把旧 baseline 标记为 provenance 不足：它可以解释当时任务 4/5 如何推进，不能再作为可复跑正式输入。
- 本次返修代码必须把 baseline schema 升到新版本，记录 `collector_argv`、`git_status_short_before=[]`、`worktree_clean_before=true`，并要求 `--importable-debt-baseline` 在生成前工作区干净、生成后只允许目标 baseline 文件变脏。
- 本次返修必须先提交代码/测试/计划留痕，再从该干净提交重新生成 `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`；否则会重复制造“文件内容来自未提交代码，但 `head_sha` 指向旧提交”的断链。

### 任务 5：把测试债务并入现有治理台账

**任务 4 承接说明**
- 下面几条记录的是任务 5 执行当时读取过的历史导入种子，不代表当前 HEAD 下 `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 仍可导入。
- 任务 4 当时生成过正式可导入 baseline：`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`。
- 那份历史 baseline 当时 `importable=true`，`required_or_quality_gate_self_failure=0`，`main_style_isolation_candidate=0`，`candidate_test_debt=5`，`collection_error_count=0`。
- 当前 HEAD 下同名文件已经是 0 候选的 full pytest 当前证明，只能证明“现在没有未登记 full pytest 失败”，不能作为任务 5 导入种子；机器合同必须拒绝 `candidate_test_debt=[]` 的导入。
- 任务 5 当时只能从历史正式 baseline 的机器块读取候选债务；不得直接导入 `audit/2026-04/20260427_full_pytest_p0_after_isolation_baseline.md`，因为那份文件是 `importable=false` 的任务 2/3 交接证据。
- 5 条候选债务都属于 `personnel.operator_machine`，可共享 `debt_family=operator_machine_normalization_contract_drift`，但必须按精确 nodeid 分 5 条登记。
- 任务 5 导入前必须填好 `domain`、`style`、`root.module`、`root.function`、`owner`、`exit_condition`；不允许写 `untriaged` 占位。
- 执行前已在当前 HEAD `19f743fca9fb145723e1353b4e812c3d24bd7be4` 下复跑 dry-run 采集：`collected_count=588`、`failed_nodeid_count=5`、`candidate_test_debt=5`、`required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`、`collection_error_count=0`，5 条 nodeid 与正式 baseline 一致。
- 正式 baseline 机器块里的 `head_sha=ee96b3248a2bdf8abf48a5c5eba8d152379c8fdf` 不作为任务 5 的硬拒绝条件；原因是 baseline 文件提交后当前 HEAD 必然变化。任务 5 执行结果必须同时记录 `baseline_head_sha` 和 `verified_head_sha`，并记录候选集合一致性。
- 返修修正：上一条是任务 5 执行当时的承接解释；任务 6 后深审确认，这份旧 baseline 的核心问题不是“提交后 HEAD 漂移”，而是 `baseline_head_sha` 本身不可复跑。后续任务必须改读返修后重新生成的新 baseline，旧 baseline 只保留历史留痕。

**根因核实与对抗审查采纳**
- 已调用多路只读调查 subagent 核实 5 条候选债务：
  - 3 条 `stale_patch_target` 属实：测试还在 patch 已不存在的 `core.services.personnel.operator_machine_normalizers.normalize_skill_level`，当前真实入口是 `normalize_skill_level_optional`、`normalize_skill_level_stored` 或 `list_by_operator` 链路。
  - 1 条 `return_contract_drift` 属实：`_resolve_write_values()` 当前遇到校验错误时返回旧值和错误消息，测试仍期待 `None`。
  - 1 条 `readside_normalization_contract_drift` 属实：查询服务当前会返回 `dirty_fields/dirty_reasons`，旧测试仍按只有普通字段做精确相等。
- 已调用多路只读对抗审查 subagent 复核本计划，采纳以下修正：
  - 计划必须先回填到原文档，再执行。
  - `reason` 与 `last_verified_at` 必须进入 schema、测试和导入字段。
  - `sort_ledger()`、`save_ledger()`、`finalize_ledger_update()`、`refresh-auto-fields` 必须有“不丢 test_debt”的红灯测试。
  - `tools/test_debt_registry.py` 不能成为第二事实源；正式登记只能来自 `开发文档/技术债务治理台账.md` 的受控 JSON。
  - 不扩大 `accepted_risks` 去引用 `debt_id`，这件事留给未来单独设计。
  - schema1 到 schema2 的迁移只能通过 `import-test-debt-baseline` 受控入口完成；普通 `load_ledger()`、`check`、`refresh` 不自动补空 `test_debt`。

**目标**
- 不另起第二套债务事实源；nodeid 级测试债务进入 `开发文档/技术债务治理台账.md` 的受控 JSON。
- 本任务只登记和治理，不修 5 条失败测试本身，不让 pytest 自动 xfail，不接 quality gate full-test-debt proof。

**文件**
- 修改：`开发文档/技术债务治理台账.md`
- 修改：`tools/quality_gate_shared.py`
- 修改：`tools/quality_gate_ledger.py`
- 修改：`tools/quality_gate_support.py`
- 修改：`scripts/sync_debt_ledger.py`
- 新建：`tools/test_debt_registry.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`
- 测试：`tests/test_sync_debt_ledger.py`

**禁止越界**
- 不修改 `tests/conftest.py`，不接 debt-aware xfail。
- 不新建 `tools/check_full_test_debt.py`，不接 full-test-debt proof。
- 不修改 `.github/workflows/quality.yml`。
- 不修改业务层文件，包括 `core/services/personnel/**`。
- 不扩大 `accepted_risks` 去引用 `debt_id`。

- [x] **步骤 1：写 ledger schema 合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加：

```python
def test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition(tmp_path):
    ...
```

断言每个 test debt entry 必须有：
- `debt_id`
- `nodeid`
- `mode`
- `reason`
- `domain`
- `style`
- `root.module`
- `root.function`
- `owner`
- `exit_condition`
- `last_verified_at`
- `debt_family`

`mode` 只允许 `xfail`、`fixed`。

继续增加这些红灯测试：
- 缺 `test_debt` 的 schema2 ledger 必须失败，不能自动补空对象。
- `nodeid` 重复必须失败。
- `debt_id` 重复必须失败。
- `ratchet.max_registered_xfail` 小于 0 必须失败。
- 任意人工字段为空、`root.module/root.function` 缺失或写 `untriaged` 必须失败。
- `active_xfail_nodeids()` 只返回 `mode=xfail` 的精确 nodeid；`mode=fixed` 不得返回。
- registry 必须从传入的 ledger / 台账结构读取正式登记，不得从 P0 seed 常量读取正式登记。

- [x] **步骤 2：写 ledger 保留合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 或 `tests/test_sync_debt_ledger.py` 增加：
- `sort_ledger()` 保留 `test_debt.ratchet` 和 `test_debt.entries`，并按 nodeid / debt_id 稳定排序。
- `save_ledger()` 写出的 Markdown 当前快照包含测试债务数量，机器块包含完整 `test_debt`。
- `finalize_ledger_update()` 不会在语义未变时刷新 `updated_at`，也不会丢 `test_debt`。
- `refresh-auto-fields` 只刷新超长文件 / 复杂度 / 静默回退自动字段，必须原样保留 `test_debt`。
- 缺 `test_debt` 的普通 `load_ledger()` / `check` / `refresh-auto-fields` 必须失败；schema1 旧台账只能交给导入命令的受控 legacy 读取路径。

- [x] **步骤 3：写导入命令合同测试**

在 `tests/test_sync_debt_ledger.py` 增加：
- `import-test-debt-baseline --baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 能把正式 baseline 的 5 条 `candidate_test_debt` 导入 `test_debt.entries`，并把 `ratchet.max_registered_xfail` 写成导入条数。
- 成功摘要必须包含导入数量、nodeid 列表、`baseline_head_sha`、`verified_head_sha`、`ratchet.max_registered_xfail`、`updated_at`。
- 导入命令只能读取 `APS-FULL-PYTEST-BASELINE` 机器块，不解析 Markdown 普通文字。
- 拒绝 `baseline_kind=raw_before_isolation`。
- 拒绝 `importable=false`。
- 拒绝 `required_or_quality_gate_self_failure` 非 0。
- 拒绝 `main_style_isolation_candidate` 非 0。
- 拒绝 `collection_error_count` 非 0。
- 拒绝 pytest 异常退出码。
- 拒绝候选 nodeid 不等于任务 4 已核实的 5 条。
- 拒绝缺任意 seed metadata、字段为空、`untriaged`、重复 nodeid、重复 debt_id。
- baseline 机器块的 `head_sha` 与当前 HEAD 不一致时，不直接拒绝；必须依赖当前 dry-run 复验候选集合一致，并在执行结果中写清双 SHA。

- [x] **步骤 4：确认红灯测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sync_debt_ledger.py --tb=short -p no:cacheprovider
```

预期：因为 ledger 还没有 `test_debt` schema、registry helper 和 `import-test-debt-baseline` 命令而失败。

- [x] **步骤 5：扩展 ledger schema**

在 `tools/quality_gate_shared.py` 中：
- `LEDGER_SCHEMA_VERSION` 从 1 升到 2。
- 新增 `TEST_DEBT_MODE_VALUES = {"xfail", "fixed"}`。

在 `tools/quality_gate_ledger.py` 增加 `test_debt`：

```json
{
  "test_debt": {
    "ratchet": {
      "max_registered_xfail": "<由 candidate_test_debt 数量生成，不能手写当前数字>"
    },
    "entries": []
  }
}
```

要求：
- `LEDGER_SCHEMA_VERSION` 从 1 升到 2，避免旧结构和新结构共用同一个版本号。
- 缺 `test_debt` 直接报错，不自动补空对象。
- `nodeid` 重复直接报错。
- `debt_id` 重复直接报错。
- `mode=fixed` 的条目不得继续被 pytest xfail 使用。
- `ratchet.max_registered_xfail` 小于 0 直接报错。
- `render_ledger_markdown()` 的“当前快照”新增测试债务登记数量。
- `collect_main_entry_ids()` 本任务不纳入 `debt_id`，避免扩大 `accepted_risks` 引用范围。

- [x] **步骤 6：新增 test debt registry helper**

新建 `tools/test_debt_registry.py`，职责限定为：
- 读取 baseline 机器块。
- 保存任务 5 导入所需的 5 条 P0 seed metadata。
- 根据 baseline candidate nodeid 构建完整 `test_debt.entries`。
- 校验 test debt entry 字段完整性。
- 从传入 ledger / 当前台账读取正式登记。
- 提供 `active_xfail_nodeids(ledger)`，只返回 `mode=xfail` 的精确 nodeid，供任务 6 使用。

硬边界：
- seed metadata 只能用于导入，不能作为正式登记事实源。
- 不在本文件里读取或修改 `tests/conftest.py`。
- 不做 full pytest proof。

- [x] **步骤 7：增加导入命令**

在 `scripts/sync_debt_ledger.py` 增加：

```bash
python scripts/sync_debt_ledger.py import-test-debt-baseline --baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md
```

该命令只做一件事：读取基线里的机器可读 JSON 结构块，把 `candidate_test_debt` nodeid 转成 `test_debt.entries` 初始登记。`required_or_quality_gate_self_failure` 和 `main_style_isolation_candidate` 不允许导入。命令不得解析 Markdown 普通文字。

导入前必须为每个 `candidate_test_debt` 填好 `domain`、`root.module`、`root.function`、`owner`、`exit_condition`。不允许写 `untriaged` 占位，因为用户要求 P0 全部核对，不接受只登记不归因。

导入命令是唯一允许 schema1 -> schema2 的受控迁移入口：
- 先读取旧台账机器块。
- 先用 legacy 校验确认旧台账仍有 `schema_version=1`、`identity_strategy`、`updated_at`、`oversize_allowlist`、`complexity_allowlist`、`silent_fallback`、`accepted_risks`，并且这些结构字段类型正确。
- 再生成完整 schema2 ledger，添加 `test_debt`，保存回 `开发文档/技术债务治理台账.md`。
- 普通 `load_ledger()`、`check`、`refresh` 不得自动迁移旧结构。

本步骤新增条件分支属于显式失败合同：用于拒绝错误 baseline、拒绝旧台账损坏、拒绝候选集合不一致、拒绝字段缺失；不得写“读不到就跳过 / 收集失败也继续”的兜底。

- [x] **步骤 8：导入测试债务并验证任务 5 边界**

先在当前 HEAD 下 dry-run 复验正式 baseline 仍可承接：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation -- tests -q --tb=short -ra -p no:cacheprovider
```

预期：返回码为 1，stdout JSON 中 `candidate_test_debt=5`、`required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`、`collection_error_count=0`，5 条 nodeid 与正式 baseline 完全一致。

执行导入：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py import-test-debt-baseline --baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md
```

预期：
- `开发文档/技术债务治理台账.md` schema 变成 2。
- `test_debt.ratchet.max_registered_xfail=5`。
- `test_debt.entries` 有 5 条 `mode=xfail` 登记。
- 每条登记都有完整 `reason`、`root`、`owner`、`exit_condition`、`last_verified_at`、`debt_family`。
- 未修改 `tests/conftest.py`，5 条失败还没有变成 xfail。

- [x] **步骤 9：重新运行 ledger 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
```

预期：通过。

- [x] **步骤 10：确认没有提前做任务 6 / 8**

运行 5 条候选 nodeid 定向 pytest：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error \
  tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error \
  tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors \
  tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error \
  tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows \
  --tb=short -p no:cacheprovider
```

预期：仍然 5 failed；这证明任务 5 没有改业务、没修测试、没接 pytest xfail。

检查未越界：

```bash
git diff --name-only
```

预期：不包含 `tests/conftest.py`、`tools/check_full_test_debt.py`、`.github/workflows/quality.yml`、`core/services/personnel/**`。

- [x] **步骤 11：审查、回填与任务 6 承接**

要求：
- 调用只读 subagent 做需求符合性审查，确认任务 5 已按 plan 完成，没有提前做任务 6/8，没有改业务层。
- 调用只读 subagent 做代码质量审查，重点确认 `test_debt` 不会被 `sort_ledger` / `save_ledger` / `refresh-auto-fields` 丢掉，`tools/test_debt_registry.py` 没变成第二事实源。
- 调用只读 subagent 做整体验收审查，确认验证命令、文档回填和台账机器块一致。
- 审查不过先修复，再重新审查。
- 审查通过后，在任务 5 下补写执行结果；同时在任务 6 头部写清任务 5 已完成什么、剩余什么、任务 6 只能接 pytest collection xfail。

- [x] **步骤 12：任务 5 收尾检查与提交准备**

运行：

```bash
ruff check tools/quality_gate_shared.py tools/quality_gate_ledger.py tools/quality_gate_support.py tools/test_debt_registry.py scripts/sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py
pyright
git diff --check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .limcode/skills/aps-post-change-check/scripts/post_change_check.py
git status --short --branch
```

预期：
- lint、pyright、diff check 通过。
- post-change-check 没有本任务新增阻断项；如果有警告，按证据处理或写入执行结果。
- 根据最终 `git status` 把整个工作区按真实改动分组合适提交；不能只提交当前会话以为改过的文件。

**任务 5 执行结果**
- 实际改动：
  - `开发文档/技术债务治理台账.md` 已升级到 `schema_version=2`，新增 `test_debt.ratchet.max_registered_xfail=5`，新增 5 条 `mode=xfail` 测试债务登记。
  - `tools/quality_gate_shared.py` 新增测试债务模式常量，并顺手拆小本次触碰到的质量门禁校验函数，避免改后检查复杂度超线。
  - `tools/quality_gate_ledger.py` 新增 `test_debt` schema 校验、稳定排序、Markdown 快照数量、保存保留逻辑；普通 `load_ledger()` / `check` / `refresh-auto-fields` 不会静默给旧结构补空 `test_debt`。
  - `tools/test_debt_registry.py` 只负责 baseline 机器块读取、导入 seed、正式台账读取和 `active_xfail_nodeids(ledger)`；正式事实源仍是 `开发文档/技术债务治理台账.md`。
  - `scripts/sync_debt_ledger.py` 新增 `import-test-debt-baseline --baseline ...`，导入前会复验当前 full pytest 候选集合仍与正式 baseline 一致；已有 `test_debt.entries` 时拒绝覆盖。
  - `tests/test_full_test_debt_registry_contract.py` 与 `tests/test_sync_debt_ledger.py` 已补 schema、保留、导入、防覆盖、禁入分类和 seed 字段校验。
- 导入摘要：
  - baseline 文件：`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`
  - `baseline_head_sha=ee96b3248a2bdf8abf48a5c5eba8d152379c8fdf`
  - `verified_head_sha=19f743fca9fb145723e1353b4e812c3d24bd7be4`
  - 台账 `updated_at=2026-04-27T08:56:24+08:00`
  - 导入数量：5；`max_registered_xfail=5`
  - 5 条 nodeid 与任务 4 正式 baseline 完全一致，且每条都有 `debt_id/nodeid/mode/reason/domain/style/root.module/root.function/owner/exit_condition/last_verified_at/debt_family`。
- 当前 full pytest dry-run 复验：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY' ... collect_current_test_debt_payload() ... PY`
  - 结果：`exitstatus=1`，`collected_count=610`，`failed_nodeid_count=5`，`candidate_test_debt=5`，`required_or_quality_gate_self_failure=0`，`main_style_isolation_candidate=0`，`collection_error_count=0`。
  - 当前收集数量从任务 4 的 588 变为 610，是因为任务 5 自身新增了测试；候选失败集合仍是原 5 条，没有新增测试债务。
- 验证命令与结果：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider`：`42 passed`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`schema_version=2`，`test_debt_count=5`。
  - 5 条候选 nodeid 定向 pytest：仍为 `5 failed`，证明任务 5 没有提前修业务、没有提前改测试、没有提前接 pytest xfail。
  - `ruff check tools/quality_gate_shared.py tools/quality_gate_ledger.py tools/quality_gate_support.py tools/test_debt_registry.py scripts/sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py`：通过。
  - `pyright scripts/sync_debt_ledger.py tools/quality_gate_shared.py tools/quality_gate_ledger.py tools/quality_gate_support.py tools/test_debt_registry.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py`：通过。
  - 全仓 `pyright`：仍有仓库既有 `238 errors, 6 warnings`，主要在旧测试和旧导入合同，不是任务 5 新增文件引入；本任务用“改动文件 pyright 通过 + 记录全仓既有失败”收口。
  - `git diff --check`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .limcode/skills/aps-post-change-check/scripts/post_change_check.py`：通过。
- 子代理审查结论与处理：
  - 需求符合性审查指出导入命令必须复验当前候选集合、保留测试要补齐；已修复并新增测试。
  - 代码质量审查指出 schema v2 上重跑导入会覆盖已有正式 `test_debt`，且禁入列表不能只看统计数；已改为已有登记拒绝覆盖，并同时检查实际列表和统计数。
  - 代码质量复审指出 candidate 列表里混入空 nodeid 时不能被静默过滤；已改为保留原始列表参与比对，空 nodeid 会受控拒绝，并新增回归测试。
  - 整体验收审查指出任务 5 执行结果与任务 6 承接未回填、改后检查复杂度失败；已回填，并拆小复杂度超线函数后复验通过。
- 停线情况：
  - 未修改 `tests/conftest.py`。
  - 未新建 `tools/check_full_test_debt.py`。
  - 未修改 `.github/workflows/quality.yml`。
  - 未修改 `core/services/personnel/**`。
  - 未扩大 `accepted_risks` 去引用 `debt_id`。

### 任务 6：给 pytest 接入 debt-aware xfail（已细化并执行）

**任务 5 承接说明**
- 任务 5 已完成台账 schema v2 和 5 条 `mode=xfail` 登记；正式事实源是 `开发文档/技术债务治理台账.md` 的 `test_debt.entries`。
- 任务 5 只登记，不改变 pytest 行为；执行任务 6 前，5 条候选 nodeid 定向 pytest 仍是 `5 failed`，还没有显示为 xfail。
- 任务 6 只能接 `tests/conftest.py` 的 pytest collection hook 和 `tools/test_debt_registry.py` 的台账读取能力；不得改业务层，不得接 full-test-debt proof，不得把未登记的新失败吞掉。
- 任务 6 需要继续遵守精确 nodeid 匹配：`mode=xfail` 才加 xfail，`mode=fixed` 不加；未收集到的登记 nodeid 不在 collection hook 里做全量失败检查。
- 任务 6 对抗审查补充要求：不能只返回 nodeid 集合，还必须让 pytest marker reason 稳定包含 `debt_id` 和 `reason`，否则后续任务 8 很难证明“为什么这条失败被允许显示为 xfail”。

**目标**
- 已登记债务显示为 xfail；未登记的新失败仍然失败。

**文件**
- 修改：`tests/conftest.py`
- 修改：`tools/test_debt_registry.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`

- [x] **步骤 1：写 collection 合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加合同测试，实际覆盖：
- 已登记失败用例显示为 xfailed，pytest 退出码为 0。
- 已登记用例如果真实通过，会因为 `strict=True` 变成 XPASS(strict) 失败。
- 参数化 nodeid 必须完整匹配，例如 `test_param[bad]` 不能误伤 `test_param[good]`。
- fixture 参数化 nodeid 也必须完整匹配。
- `mode=fixed` 不会进入 active xfail 映射。
- 未登记的新失败仍然失败。
- 登记项本次没被收集到不会失败，定向 pytest 不会被全量台账拖死。
- registry/台账读取失败会让 pytest collection 失败。
- xfail reason 稳定包含 `debt_id`，后续任务 8 可继续读取 reason 做 proof。

```python
def test_pytest_collection_marks_registered_exact_nodeids_xfail(tmp_path):
    ...
```

- [x] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

实际红灯：
- `ImportError: cannot import name 'active_xfail_entries_by_nodeid'`
- `AttributeError: module '_repo_tests_conftest_under_test' has no attribute 'pytest_collection_modifyitems'`
- 结果为 `6 failed, 15 passed`，失败原因正好指向缺 registry helper 和缺 pytest collection hook，不是测试本身写坏。

- [x] **步骤 3：接入 pytest hook**

实际实现：
- `tools/test_debt_registry.py` 新增 `active_xfail_entries_by_nodeid(ledger=None)`。
- 不传 ledger 时，函数通过现有 `load_ledger(required=True)` 读取正式治理台账并校验；传入 ledger 时只用于测试和调用方显式验证。
- 该函数返回 `nodeid -> entry` 映射，只包含 `mode=xfail`，因此 marker 能拿到 `debt_id` 和 `reason`。
- `active_xfail_nodeids(ledger)` 继续保留，改为基于 `active_xfail_entries_by_nodeid(ledger)` 返回 nodeid 集合。
- `tests/conftest.py` 增加 `pytest_collection_modifyitems(items)`，只按当前收集到的 `item.nodeid` 精确匹配，命中后加 `pytest.mark.xfail(reason="<debt_id>: <reason>", strict=True)`。
- 台账读取、字段校验或结构解析失败不会被吞掉，会让 pytest collection 直接失败。

不得按文件前缀、目录、正则模糊匹配。不得在这里校验“登记 nodeid 是否全部被 collect 到”；这个全量一致性检查只放在 `tools/check_full_test_debt.py`。

- [x] **步骤 4：重新运行 collection 合同与任务 6 验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --collect-only -q tests -p no:cacheprovider
```

实际结果：
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider`：`21 passed`。
- 5 条正式登记 nodeid 定向 pytest：`5 xfailed`，已从任务 5 的普通失败变成已登记 xfail。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --collect-only -q tests -p no:cacheprovider`：`615 tests collected`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`schema_version=2`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/conftest.py tools/test_debt_registry.py tests/test_full_test_debt_registry_contract.py`：通过。
- `pyright tests/conftest.py tools/test_debt_registry.py tests/test_full_test_debt_registry_contract.py`：`0 errors, 0 warnings, 0 informations`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tests/conftest.py tools/test_debt_registry.py tests/test_full_test_debt_registry_contract.py`：通过。
- `git diff --check`：通过。

**任务 6 执行结果**
- 实际改动：
  - `tools/test_debt_registry.py` 新增 `active_xfail_entries_by_nodeid()`，让 pytest 能从正式治理台账拿到 `nodeid/debt_id/reason`，同时只返回 `mode=xfail` 的登记。
  - `tests/conftest.py` 新增 debt-aware collection hook，只对当前本次收集到、且 nodeid 精确命中的测试加 `strict=True` xfail；未登记测试保持原样失败。
  - `tests/test_full_test_debt_registry_contract.py` 增加完整合同测试，覆盖参数化精确匹配、fixture 参数化精确匹配、未登记失败、未收集登记项、XPASS(strict)、registry 失败和 reason 包含 `debt_id`。
- 行为变化：
  - 任务 5 登记的 5 条 nodeid 现在显示为 `5 xfailed`。
  - 如果未来某条登记项真的修好但仍留在台账里，会变成 XPASS(strict) 失败，提醒执行者从台账移除或改成 `mode=fixed`。
  - 未登记的新失败不会被 hook 吞掉，仍然是普通失败。
  - collection hook 不做“台账所有 nodeid 必须被本次 collect 到”的全量检查，定向 pytest 不会被全量台账拖死。
- 子代理审查结论：
  - 需求符合性审查通过：diff 只包含 `tests/conftest.py`、`tests/test_full_test_debt_registry_contract.py`、`tools/test_debt_registry.py`，没有提前修改 `tools/collect_full_test_debt.py`、`tools/check_full_test_debt.py`、`.github/workflows/quality.yml` 或业务层。
  - 代码质量与对抗审查通过：确认没有吞未登记失败，reason 稳定包含 `debt_id/reason`，台账读取失败会显式失败，测试确实加载真实 repo `tests/conftest.py` hook，而不是复制一份 hook 逻辑。
- 停线情况：
  - 未修改业务层。
  - 未接 full-test-debt proof。
  - 未修改 quality workflow。
  - 未新建 `tools/check_full_test_debt.py`。
  - 未修改 `tools/collect_full_test_debt.py`。

### 任务 7：质量门禁 runner 真正按 shared command plan 执行

**任务 6 后审查返修与任务 7 边界**
- 本轮 review finding 重新编号并固定归属：
  - Finding 1：`scripts/run_quality_gate.py` 手写执行 collect、ruff version、pyright version，再从 `command_plan[3:]` 开始跑，新增命令插到 collect 后会被跳过。归属任务 7。
  - Finding 2：`QUALITY_GATE_SOURCE_FILES` 还没覆盖 full-test-debt 语义链路。归属任务 8，本轮不抢跑。
  - Finding 3：`P0_TEST_DEBT_SEED_METADATA` 仍参与决定可导入 nodeid。归属任务 7 前置返修。
  - Finding 4：台账手写可把 required/proof 测试登记成 active xfail。归属任务 7 前置返修。
  - Finding 5：dirty-before 拒绝路径会留下旧 baseline。归属任务 7 前置返修。
- 当前工作区开始前已有 `evidence/DeepReview/reference_trace.md` 脏改动；它不属于任务 7 代码改动，不得混入任务 7 功能提交。
- 用户新增约束：本轮不得新增 fallback、兜底或静默回退。新增判断只允许是“坏输入必须失败”的显式合同检查，并且要能被测试证明。

**已完成的前置返修（Finding 3/4/5）**
- [x] `tools/test_debt_registry.py` 已把“baseline 机器合同是否可信”和“seed metadata 如何生成登记条目”拆开：`validate_importable_baseline()` 不再要求 `candidate_test_debt` 等于 `P0_TEST_DEBT_SEED_METADATA` 的 key 集合；0 候选 current proof baseline 可以加载。
- [x] `build_test_debt_entries()` 仍在真正生成台账登记项时要求 seed metadata 存在；未知候选会显式报错“缺少测试债务登记元数据”，不会变成 KeyError，也不会静默跳过。
- [x] `tools/quality_gate_shared.py` 新增 required/proof nodeid 共享匹配 helper；`tools/collect_full_test_debt.py` 和 `tools/quality_gate_ledger.py` 共用同一判断口径，避免 collector 与台账校验分裂。
- [x] `tools/quality_gate_ledger.py` 已禁止 `mode=xfail` 的 active 测试债务登记 required/proof 测试；`mode=fixed` 作为历史记录仍允许保留。
- [x] `tools/collect_full_test_debt.py` 的 dirty-before 两个提前拒绝路径已经先删除旧 `--write-baseline` 目标文件，再返回失败，和后续禁入分类、写后漂移路径一致。

**已完成的 runner 修复（Finding 1）**
- [x] `tests/test_run_quality_gate.py::test_main_executes_every_shared_command_when_plan_inserts_preflight` 先用 monkeypatch 把 `python tools/check_full_test_debt.py` 作为哨兵命令插到 collect 和 ruff version 中间；旧 runner 会漏跑哨兵并重复 pyright version，测试先红。
- [x] `scripts/run_quality_gate.py` 已删除手写前三条命令和 `command_plan[3:]`，改成 `_run_quality_gate_command_plan()` 单次遍历 shared command plan。每条命令只执行一次、写一次 receipt、进入 manifest 一次。
- [x] collect、ruff version、pyright version 通过显式 handler 解析结果；其他命令只检查 returncode。这是命令验收表，不是“命令不存在就跳过”的兜底。
- [x] 对抗审查发现“必需证明命令被删除也会通过”的风险后，已补 `tests/test_run_quality_gate.py::test_main_fails_when_required_command_proof_is_missing`。现在 collect / ruff version / pyright version 任一缺失，runner 都会显式失败，并把 manifest 写成 `failed`。
- [x] 本轮没有新增 `tools/check_full_test_debt.py`，没有把 `python tools/check_full_test_debt.py` 接入真实 command plan，没有修改 `.github/workflows/quality.yml`，没有提前实现 Finding 2。

**验证结果**
- 红灯确认：
  - `test_collect_full_test_debt_importable_requires_clean_worktree` 先失败于旧 baseline 未删除。
  - `test_test_debt_registry_rejects_required_tests_as_active_xfail` 先失败于 required/proof active xfail 未拒绝。
  - `test_importable_baseline_contract_accepts_zero_candidate_current_proof` 先失败于 seed key 集合仍决定候选集合。
  - `test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid` 先失败于旧 seed 集合错误消息。
  - `test_main_executes_every_shared_command_when_plan_inserts_preflight` 先失败于哨兵命令被跳过、pyright version 被重复执行。
  - `test_main_fails_when_required_command_proof_is_missing` 先失败于缺 collect / ruff version / pyright version 时 runner 仍通过。
- 绿灯验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_run_quality_gate.py --tb=short -p no:cacheprovider`：`87 passed`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tools/test_debt_registry.py tools/quality_gate_ledger.py tools/collect_full_test_debt.py tools/quality_gate_shared.py tools/quality_gate_support.py scripts/run_quality_gate.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_run_quality_gate.py`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/test_debt_registry.py tools/quality_gate_ledger.py tools/collect_full_test_debt.py tools/quality_gate_shared.py tools/quality_gate_support.py scripts/run_quality_gate.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_run_quality_gate.py`：`All checks passed!`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/test_debt_registry.py tools/quality_gate_ledger.py tools/collect_full_test_debt.py tools/quality_gate_shared.py tools/quality_gate_support.py scripts/run_quality_gate.py`：`0 errors, 0 warnings, 0 informations`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`test_debt_count=5`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation -- tests -q --tb=short -ra -p no:cacheprovider`：通过，输出 `candidate_test_debt=0`、`required_or_quality_gate_self_failure=0`、`main_style_isolation_candidate=0`、`collection_error_count=0`、`failed_nodeid_count=0`、`collected_count=634`。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .limcode/skills/aps-post-change-check/scripts/post_change_check.py`：最终 `PASS - 可以提交`。
  - `git diff --check`：通过。
- 新增条件扫描：
  - 测试里的 `if display == ...` 只用于 fake 命令输出。
  - `tools/quality_gate_ledger.py` 新增 `if quality_gate_required_test_nodeid_matches(nodeid)` 是 active xfail 禁入合同。
  - `tools/test_debt_registry.py` 新增 `if schema_version != ...`、`if baseline_kind != ...`、`if importable is not ...`、`if worktree_clean_before is not True`、`if git_status_short_before != []`、`if "--importable-debt-baseline" not in collector_argv` 都是 baseline 机器合同失败检查。
  - 未新增 fallback、兜底、静默回退逻辑。

**子代理审查结果**
- 需求符合性审查：PASS。确认 Finding 1/3/4/5 已闭环；Finding 2 未抢跑；`python tools/check_full_test_debt.py` 只作为测试哨兵出现。
- 测试与根因审查：PASS。确认测试覆盖哨兵插入、0 候选 proof、未知候选缺 seed、required/proof active xfail、相似前缀不误杀、dirty-before 删除旧 baseline。
- 风险与提交边界审查：第一轮 BLOCKED，指出缺 collect / ruff version / pyright version 时 runner 会静默通过。已补显式必需证明检查和反向测试。
- 返修复审：PASS。确认缺任一必需证明命令会失败并写 failed manifest；新增检查是显式合同失败，不是 fallback/兜底；Finding 2 仍未抢跑。
- 当前仍需在最终提交点后的干净 worktree 上运行 `scripts/run_quality_gate.py --require-clean-worktree`，最终 clean gate 结果以提交后记录为准。

### 任务 8：质量门禁接入 full-test-debt proof

**Finding 2 留痕：source proof 未覆盖测试债务链路**
- 深审确认：`QUALITY_GATE_SOURCE_FILES` 当前还没有绑定 `tools/collect_full_test_debt.py`、`tools/test_debt_registry.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py`，因此当前 source proof 不能声明已经覆盖 full-test-debt 语义。
- 本缺口属于任务 8 的正式工作，不属于任务 7 前置返修或 runner 修复范围。任务 8 落地时必须一次性接入 command plan、source proof、tool pyright 和 replay receipt；不能只把文件名塞进 source 列表。
- 任务 7 已完成 runner 改造：runner 现在按 shared command plan 单次遍历执行，每条命令只执行一次、写一次 receipt、进入 manifest 一次；新增命令插到 collect 后、ruff version 前也不会被跳过。
- 任务 7 还补了必需证明缺失检查：collect / ruff version / pyright version 任一缺失都会失败并写 failed manifest。任务 8 如果新增 `python tools/check_full_test_debt.py`，不需要再改 runner 才能保证它被执行。
- 任务 8 仍必须自己证明 full-test-debt 的 source proof、receipt、replay、checker 输出合同；任务 7 没有新增 `tools/check_full_test_debt.py`，也没有把 full-test-debt proof 提前接入真实 command plan。

**任务 8 细化边界**
- 本任务只闭环 Finding 2：command plan、source proof、tool pyright、receipt/replay、checker 输出合同。
- 本任务不做任务 9：不统一 required/startup/full-debt registry 出口，不重排测试 registry，不新增三套入口的共同抽象。
- 本任务默认不改 `.github/workflows/quality.yml`，也默认不改 `scripts/run_quality_gate.py`；只有红灯证明 runner 仍有缺口时才允许触碰 runner。
- 本任务允许新增的判断只限显式失败合同：JSON 坏、字段缺、登记缺、XPASS、ratchet 超限、required/proof 混入等必须直接失败，不允许空列表兜底、文本猜测、seed metadata 第二事实源或静默回退。

**目标**
- CI 仍然只跑统一门禁入口，但门禁能证明没有未登记全量失败。

**文件**
- 新建：`tools/check_full_test_debt.py`
- 新建：`tests/test_check_full_test_debt.py`
- 修改：`tools/collect_full_test_debt.py`
- 修改：`tools/quality_gate_shared.py`
- 修改：`tests/test_run_quality_gate.py`
- 修改：`tests/test_run_full_selftest_report_metadata.py`
- 修改：`tests/test_full_test_debt_registry_contract.py`
- 修改：`.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`

- [x] **步骤 0：边界锁定**

执行时已确认：
- `tools/check_full_test_debt.py` 尚不存在。
- `build_quality_gate_command_plan()` 尚未包含 `python tools/check_full_test_debt.py`。
- `QUALITY_GATE_SOURCE_FILES` 尚未包含 collector / registry / pytest hook / main-style runner / 台账文件。
- 现有 collector report 尚未结构化记录 xfail reason / strict XPASS。
- 现有 runner 已经按 shared command plan 单次遍历，任务 8 不再重写 runner。

- [x] **步骤 1：写红灯合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加 collector 合同：
- `test_collect_full_test_debt_records_structured_xfail_reason`：登记债务 xfail 的 report 必须有结构化 `xfail_marker_reason`、`xfail_marker_strict`、`wasxfail_reason`。
- `test_collect_full_test_debt_records_strict_xpass_without_text_guessing`：strict XPASS 必须用结构化字段识别。
- `test_collect_full_test_debt_keeps_plain_skip_separate_from_debt_xfail`：普通 skip 不得被当成债务 xfail。

新建 `tests/test_check_full_test_debt.py`，覆盖：
- 通过场景：active xfail 都被 collect 到，reason 对齐，候选失败为 0。
- 未登记失败：`candidate_test_debt` 非空必须失败。
- 登记 nodeid 未收集：必须失败。
- xfail reason 和台账不一致：必须失败。
- active xfail 的 marker reason 和台账不一致：必须失败。
- active xfail 的 marker strict 不是 `true`：必须失败。
- collector `exitstatus` 不是 0：必须失败。
- strict XPASS：必须失败。
- `mode=fixed` 仍出现 xfail marker：必须失败。
- ratchet 超限：必须失败。
- collector stdout 不是 JSON：必须失败。
- required/proof 混入 active xfail：必须失败。

在 `tests/test_run_quality_gate.py` 增加断言：
- command plan 包含 `python tools/check_full_test_debt.py`。
- 该命令来自 `build_quality_gate_command_plan()`，位置在 collect-only 之后、ruff version 之前。
- 现有“插入命令不会被跳过”的哨兵测试不得再使用真实 `python tools/check_full_test_debt.py`，避免和任务 8 真命令重复。
- `scripts/run_quality_gate.py` 不手写第二套 full-test-debt 命令。
- 新脚本在 `QUALITY_GATE_SOURCE_FILES` 里。
- 新脚本在 `QUALITY_GATE_TOOL_PATHS` 里接受 pyright 检查。
- `tools/collect_full_test_debt.py`、`tools/test_debt_registry.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py`、`开发文档/技术债务治理台账.md` 也进入 `QUALITY_GATE_SOURCE_FILES`，因为它们共同决定 full-test-debt proof 语义。

在 `tests/test_run_full_selftest_report_metadata.py` 增加断言：
- command replay 会重新跑 `tools/check_full_test_debt.py`。
- 缺少该 command receipt 时，quality gate binding 失败。
- receipt hash 被篡改时，quality gate binding 失败。

- [x] **步骤 2：确认红灯**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_check_full_test_debt.py tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py --tb=short -p no:cacheprovider
```

结果：首轮红灯为 `17 failed, 67 passed`。失败原因正是 collector 尚无结构化 xfail 字段、checker 尚不存在、command plan 未接入 full-test-debt proof。对抗审查后又补了两条红灯：非 strict 的 active xfail 未被拒绝、`exitstatus=1` 且分类为空未被拒绝；两条都已先失败再修复。

- [x] **步骤 3：增强 collector 结构化 xfail**

修改 `tools/collect_full_test_debt.py`：
- report 行新增结构化字段：`xfail_marker_reason`、`xfail_marker_strict`、`wasxfail_reason`、`strict_xpass`。
- 这些字段来自 pytest item marker 和 makereport 结果，不解析 `-rx`、终端文本或 `longrepr`。
- 普通 skip 的 `xfail_marker_reason`、`wasxfail_reason` 必须为空。
- 保持 baseline `schema_version=2`；这是 report 行加字段，不改变 baseline 顶层机器合同。

- [x] **步骤 4：实现 `tools/check_full_test_debt.py`**

行为：
- 读取正式台账，不读 `P0_TEST_DEBT_SEED_METADATA`，不读 audit baseline。
- 调用 `tools/collect_full_test_debt.py`，执行 `pytest tests -q --tb=short -ra -p no:cacheprovider`。
- 读取结构化 JSON。
- 校验 collected nodeid 不为空。
- 校验 `collection_errors` 为空。
- 校验 `required_or_quality_gate_self_failure`、`main_style_isolation_candidate`、`candidate_test_debt` 全部为空。
- 校验 active xfail 登记 nodeid 都被 full suite collect 到。
- 校验 `mode=xfail` 数量不超过 `test_debt.ratchet.max_registered_xfail`。
- 校验每个 active xfail 的 marker reason、marker strict、`wasxfail_reason` 都符合台账：reason 必须等于 `debt_id: reason`，strict 必须为 `true`。
- 校验 collector `exitstatus` 必须为 0，避免 pytest 已失败但结构化分类没反映出来时被误放行。
- 校验 `mode=fixed` 不再出现在 xfail marker 中。
- 校验 required/proof 测试不在 `mode=xfail` 中。
- 校验 strict XPASS 不存在。
- stdout 输出稳定 JSON summary，供 quality gate receipt 记录 hash；summary 不含时间、duration、临时路径或原始 longrepr。
- checker 不写 baseline、不写 evidence、不刷新台账。

第一版不新增 `quality_gate_manifest.json` 顶层自由字段。证明通过 command receipt、commands hash、source hash 和 replay 表达。这样不会制造第二套 manifest 字段解释口径。

- [x] **步骤 5：接入 shared command plan / source proof / tool pyright**

在 `tools/quality_gate_shared.py::build_quality_gate_command_plan()` 增加：

```text
python tools/check_full_test_debt.py
```

放置位置：`python -m pytest --collect-only -q tests` 之后，`python -m ruff --version` 之前。

同步：
- `QUALITY_GATE_TOOL_PATHS` 增加 checker、collector、test debt registry、`tests/conftest.py`、`tests/main_style_regression_runner.py`。
- `QUALITY_GATE_SOURCE_FILES` 增加 checker、collector、test debt registry、`tests/conftest.py`、`tests/main_style_regression_runner.py`、`开发文档/技术债务治理台账.md`。
- 如仅修改既有列表，不为了制造 diff 改 `tools/quality_gate_support.py`。

不得修改 `.github/workflows/quality.yml`。

- [x] **步骤 6：绿灯验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_check_full_test_debt.py tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile tools/check_full_test_debt.py tools/collect_full_test_debt.py tools/test_debt_registry.py tools/quality_gate_shared.py tests/conftest.py tests/main_style_regression_runner.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/check_full_test_debt.py tools/collect_full_test_debt.py tools/test_debt_registry.py tools/quality_gate_shared.py tests/conftest.py tests/main_style_regression_runner.py tests/test_check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/check_full_test_debt.py tools/collect_full_test_debt.py tools/test_debt_registry.py tests/conftest.py tests/main_style_regression_runner.py
git diff --check
```

结果：通过。任务八相关四组测试最终为 `86 passed`；`tools/check_full_test_debt.py` 实跑通过，稳定 summary 显示 `active_xfail_count=5`、`collected_count=656`、`collection_error_count=0`、`fixed_count=0`、`max_registered_xfail=5`、`unexpected_failure_count=0`。

- [x] **步骤 7：subagent 对抗审查**

实现后调用至少 3 个只读 subagent：
- 一路查 Finding 2 是否真正闭环，且没抢任务 9。
- 一路查 checker/collector 是否没有 fallback、没有文本猜测、没有 seed 第二事实源。
- 一路查 command plan、source proof、tool pyright、receipt/replay、clean gate 证明是否可信。

结果：已调用 3 路只读 subagent。一路确认 Finding 2 主体闭环且未抢任务 9，同时指出 `exitstatus=1` 未强制失败；一路指出 active xfail 未强制 `strict=True`；一路确认 command plan、source proof、tool pyright、receipt/replay 链路可信，同时提醒必须提交后再跑 clean gate。两个代码缺口均已补红灯、修复并复跑任务八测试。

- [x] **步骤 8：结果回填与提交**

任务 8 完成后回填本节尾部：
- 红灯测试名和旧代码失败原因。
- checker 输出合同和实际 summary 字段。
- source proof / tool pyright / receipt / replay 接入结果。
- subagent 审查结论。
- clean gate 的 HEAD、worktree 路径和结果。
- 明确写：任务 9 只做 registry 收敛，不再重复 runner/proof 工作。

**任务 8 执行结果回填**
- 红灯测试：`test_collect_full_test_debt_records_structured_xfail_reason`、`test_collect_full_test_debt_records_strict_xpass_without_text_guessing`、`test_collect_full_test_debt_keeps_plain_skip_separate_from_debt_xfail`、`tests/test_check_full_test_debt.py` 的 checker 合同测试、`test_full_test_debt_proof_is_in_shared_quality_gate_plan`、`test_quality_gate_binding_status_replays_full_test_debt_proof_command`、缺 receipt 和篡改 receipt 的 replay 测试。旧代码失败原因是：collector 没有 xfail 机器字段、checker 文件不存在、shared command plan/source proof/tool proof 没有 full-test-debt 证明、receipt/replay 没有该命令。
- collector 已用 pytest marker 和 makereport 结果记录 `xfail_marker_reason`、`xfail_marker_strict`、`wasxfail_reason`、`strict_xpass`。普通 skip 不会被当作债务 xfail，strict XPASS 不靠终端文本或 `longrepr` 猜。
- checker 读取正式台账，不读 seed metadata，不读 audit baseline，不写 baseline/evidence/台账。它只解析 collector JSON，并对 JSON 坏、字段缺、收集为空、收集错误、未登记失败、required/proof 失败、main-style 候选、登记 nodeid 未收集、reason 不一致、marker strict 非 true、`mode=fixed` 仍 xfail、strict XPASS、ratchet 超限、required/proof active xfail、`exitstatus != 0` 直接失败。
- checker 稳定输出字段：`schema_version`、`status`、`active_xfail_count`、`active_xfail_entries`、`collected_count`、`collection_error_count`、`fixed_count`、`max_registered_xfail`、`unexpected_failure_count`。实跑结果为 `active_xfail_count=5`、`collected_count=656`、`collection_error_count=0`、`fixed_count=0`、`max_registered_xfail=5`、`unexpected_failure_count=0`。
- shared command plan 已在 collect-only 后、ruff version 前插入 `python tools/check_full_test_debt.py`，该命令 `capture_output=True`、`output_policy=exact`。`QUALITY_GATE_TOOL_PATHS` 和 `QUALITY_GATE_SOURCE_FILES` 已覆盖 checker、collector、test debt registry、pytest hook、main-style runner；`QUALITY_GATE_SOURCE_FILES` 额外覆盖 `开发文档/技术债务治理台账.md`。
- receipt/replay 已覆盖 full-test-debt proof：replay 会重跑 `python tools/check_full_test_debt.py`，缺该 receipt 会失败，receipt hash 被篡改会失败。
- 验证结果：任务八四组测试 `86 passed`；`tools/check_full_test_debt.py` 通过；`py_compile`、`ruff check`、`pyright`、`git diff --check`、`scripts/sync_debt_ledger.py check`、`aps-post-change-check` 均通过。
- 对抗审查结论：3 路只读审查已完成，发现的两个真实缺口是 active xfail 未强制 strict、`exitstatus=1` 未强制失败；均已修复并新增测试。其余审查确认未解析终端文本、未使用 seed metadata 作为第二事实源、未抢任务 9、未修改 runner、未修改 GitHub Actions。
- clean gate：最终 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree` 必须在本轮本地提交完成后的干净 worktree 上运行；结果和最终 HEAD 以提交后记录为准。
- 明确未实施任务 9：本轮没有统一 required/startup/full-debt registry 出口，任务 9 只做 registry 收敛，不再重复 runner/proof 工作。

### 任务 9：收敛 required/startup/full-debt 三套入口

**任务 8 承接说明**
- 任务 8 已完成后，`python tools/check_full_test_debt.py` 已进入 shared command plan、source proof、tool pyright、receipt/replay，质量门禁已经能证明当前 full pytest 没有未登记失败。
- 任务 9 只处理 required/startup/full-debt 三套入口从统一 registry 派生，不重复 runner 改造、full-test-debt proof 接入、receipt/replay 绑定，也不改 GitHub Actions。
- 执行前复核到的当前事实是：required tests 为 70 条，startup regressions 为 14 条，正式台账里的 active xfail 为 5 条；`tools/check_full_test_debt.py` 通过，summary 为 `active_xfail_count=5`、`collected_count=656`、`collection_error_count=0`、`fixed_count=0`、`max_registered_xfail=5`。

**根因核实**
- required/startup 清单原来手写在 `tools/quality_gate_shared.py`，full-debt 的正式事实源在 `开发文档/技术债务治理台账.md` 并由 `tools/test_debt_registry.py` 读取；三套入口虽然当前能跑通，但没有统一出口。
- 任务 8 已经把 full-test-debt proof 接进门禁，任务 9 的风险不是“没跑 proof”，而是以后维护 required/startup/full-debt 时容易各改各的。
- `tools/test_debt_registry.py` 会读取 `tools/quality_gate_shared.py` 和 `tools/quality_gate_ledger.py`；如果让 `quality_gate_shared.py` 反过来顶层导入 `test_debt_registry.py`，会有循环导入风险。所以本任务新增一个更薄的 `tools/test_registry.py` 作为 required/startup 清单事实源。

**目标**
- required tests、startup regressions、full test debt 对外由同一组 registry 出口提供，后续新增或删除测试时不再分散维护。
- 保持现有门禁命令顺序和 proof 语义不变：collect-only 后仍先跑 `python tools/check_full_test_debt.py`，required pytest 仍在 `scripts/sync_debt_ledger.py check` 前，startup pytest 仍在台账检查后。

**文件**
- 新建：`tools/test_registry.py`
- 扩展：`tools/test_debt_registry.py`
- 修改：`tools/quality_gate_shared.py`
- 修改：`tools/quality_gate_support.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`
- 测试：`tests/test_run_quality_gate.py`

**禁止越界**
- 不修改 `.github/workflows/quality.yml`。
- 不修改 `tools/check_full_test_debt.py` 的 proof 语义，不重做 collector 分类，不重接 receipt/replay。
- 不修 5 条 operator-machine/query 旧测试债务，不把任何 `mode=xfail` 转成 `fixed`，不下调 `test_debt.ratchet.max_registered_xfail`。
- 不把 `P0_TEST_DEBT_SEED_METADATA`、audit baseline 或 collector stdout 变成 active xfail 的第二事实源；正式事实源仍是 `开发文档/技术债务治理台账.md`。
- 不把重型 full-suite 检查塞进 `tests/conftest.py` 的 collection hook；局部 pytest 仍只做精确 nodeid xfail 标记。

- [x] **步骤 1：写 registry 一致性红灯测试**

已在 `tests/test_full_test_debt_registry_contract.py` 增加 `test_quality_gate_required_startup_and_full_debt_share_registry()`，断言：
- `tools.test_debt_registry` 必须暴露 `iter_required_tests()`、`iter_startup_regressions()`、`load_test_debt_registry()`、`hash_test_debt_registry()`。
- required tests、startup regressions、active xfail nodeids 都没有重复。
- required tests 与 startup regressions 不互相混入；required tests 不允许出现在 active xfail 中。
- required/startup 路径必须存在，并且已经被 git 跟踪。
- registry hash 同一份输入多次计算稳定一致。

已在 `tests/test_run_quality_gate.py` 扩展门禁行为锁，断言：
- `scripts.run_quality_gate.REQUIRED_TEST_ARGS`、`STARTUP_REGRESSION_ARGS`、`tools.quality_gate_shared.iter_quality_gate_required_tests()` 和 registry 出口完全一致。
- required/startup pytest 命令的 display/args 来自 registry，且现有命令顺序不变。
- `tools/test_registry.py` 进入 `QUALITY_GATE_TOOL_PATHS` 和 `QUALITY_GATE_SOURCE_FILES`，避免 source proof 漏掉新的事实源。

- [x] **步骤 2：确认红灯测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

结果：`2 failed, 50 passed`。两条失败都来自缺少统一出口：
- `ImportError: cannot import name 'hash_test_debt_registry' from 'tools.test_debt_registry'`
- `ImportError: cannot import name 'iter_required_tests' from 'tools.test_debt_registry'`

- [x] **步骤 3：收敛 registry 出口**

实际实现：
- `tools/test_registry.py` 成为 required/startup 清单唯一维护点，提供规范化、去重、required nodeid 匹配、路径状态检查和稳定 hash。
- `tools/quality_gate_shared.py` 保留 `QUALITY_GATE_REQUIRED_TESTS`、`QUALITY_GATE_STARTUP_REGRESSION_ARGS` 等旧公开名字，但这些名字只作为 `tools/test_registry.py` 的兼容别名，不再重复手写清单。
- `tools/test_debt_registry.py` 新增 `iter_required_tests()`、`iter_startup_regressions()`、`load_test_debt_registry()`、`hash_test_debt_registry()`；其中 full-debt 仍通过 `registered_test_debt_entries()` 从正式台账读取。
- `tools/quality_gate_support.py` 同步导出新增 registry 出口，方便旧入口继续使用统一来源。

- [x] **步骤 4：重新运行 registry 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

结果：`52 passed`。

- [x] **步骤 5：任务 9 完整验收与审查**

已运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py tests/test_check_full_test_debt.py tests/test_run_full_selftest_report_metadata.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/test_registry.py tools/test_debt_registry.py tools/quality_gate_shared.py tools/quality_gate_support.py tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/test_registry.py tools/test_debt_registry.py tools/quality_gate_shared.py
git diff --check
```

结果：
- 任务 9 与任务 8 防回退测试组合：`87 passed`。
- `tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`collected_count=657`、`collection_error_count=0`、`fixed_count=0`、`max_registered_xfail=5`、`unexpected_failure_count=0`。
- `scripts/sync_debt_ledger.py check`：通过，`schema_version=2`、`test_debt_count=5`。
- `ruff check`：通过。
- `pyright tools/test_registry.py tools/test_debt_registry.py tools/quality_gate_shared.py`：`0 errors, 0 warnings, 0 informations`。
- `git diff --check`：通过。

只读 subagent 审查结果：
- 入口边界审查：通过。确认 `tools/test_registry.py` 只导入标准库，没有循环导入风险；required/startup 清单已集中到 `test_registry`；full-debt 仍只读正式台账；没有抢任务 10，也没有改业务测试债务。
- proof 链路审查：通过。确认 command plan 顺序保持不变，`tools/test_registry.py` 已进入 `QUALITY_GATE_TOOL_PATHS` 和 `QUALITY_GATE_SOURCE_FILES`，receipt/replay/source proof 没有放松。审查指出 `tools/test_registry.py` 仍是未跟踪文件，已作为提交边界要求纳入第一笔提交。
- 文档与提交边界审查：要求把任务 10 头部改成完成态承接，并且不要把无关的 `codestable/compound/2026-04-27-explore-repo-garbage-files.md` 混入本任务提交。本轮按该建议处理。

- [x] **步骤 6：任务 9 收尾回填与提交**

本步骤已完成。任务 9 执行结果已回填，任务 10 头部已改为完成态承接。

提交边界：
- 第一笔：测试入口 registry 收敛代码和测试，提交 `6167f6a`。
- 第二笔：本计划文件回填，提交 `3e07366`。
- 工作区里另有一份无关的 CodeStable 探索记录 `codestable/compound/2026-04-27-explore-repo-garbage-files.md`。它不属于任务 9 入口收敛，所以没有混入前两笔；为了满足整棵工作区干净和最终 clean gate，已单独提交为 `f65b5dd`。

提交后、工作区干净时，已运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果：通过，最后输出 `质量门禁通过`。门禁命令中 `python tools/check_full_test_debt.py` 再次确认 `active_xfail_count=5`、`collected_count=657`、`collection_error_count=0`、`fixed_count=0`、`max_registered_xfail=5`。

### 任务 10：建立只减不增的 ratchet

**任务 9 承接说明**
- 任务 9 已把 required/startup/full-debt 三套入口收敛到统一 registry。任务 10 不再重新整理入口清单，只在统一 registry 和正式台账上继续处理“只减不增”和 fixed 流程。
- required/startup 清单事实源是 `tools/test_registry.py`；兼容旧入口的 `QUALITY_GATE_REQUIRED_TESTS`、`QUALITY_GATE_STARTUP_REGRESSION_ARGS` 仍由 `tools/quality_gate_shared.py` 导出，但只作为 `tools/test_registry.py` 的别名。
- full-debt 正式事实源仍是 `开发文档/技术债务治理台账.md`。任务 10 预计依赖 `tools.test_debt_registry.load_test_debt_registry()`、`iter_required_tests()`、`iter_startup_regressions()` 和 `python tools/check_full_test_debt.py`。
- 当前正式台账仍是 `mode=xfail` 5 条，`test_debt.ratchet.max_registered_xfail=5`；任务 9 没有把任何条目改成 `fixed`，也没有下调 ratchet。
- 任务 9 的聚焦验证已通过：`87 passed`、`tools/check_full_test_debt.py` 通过、`scripts/sync_debt_ledger.py check` 通过、`ruff` 通过、改动文件 `pyright` 通过、`git diff --check` 通过。
- 任务 9 提交后已在干净工作区补跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`，结果通过，最后输出 `质量门禁通过`。

**任务 10 已完成结果**
- 任务 10 已把“只减不增”从口头规则变成台账和门禁都会检查的硬规则：正式台账里的 active xfail 数必须等于 `test_debt.ratchet.max_registered_xfail`，不能多登记，也不能留下宽松余量。
- 已新增 `python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id ...`。以后某条测试债务真的修好后，先用这个命令把对应条目标成 `fixed`，命令会更新时间并按剩余 active xfail 数重算 ratchet。
- `fixed` 条目会保留在 `test_debt.entries` 里作为关闭痕迹，但它不再属于 active xfail，也不会被 pytest 自动标成 xfail。`tools/check_full_test_debt.py` 会要求 fixed nodeid 被收集到、普通通过，并且没有任何 xfail 标记痕迹，包括空 reason 的 xfail 标记。
- 本任务没有修那 5 条业务测试，没有修改正式台账、README、开发文档 README、GitHub Actions 或 baseline 报告。当前正式台账仍是 5 条 active xfail，`fixed_count=0`，`max_registered_xfail=5`。
- 对抗复审发现一个真实缺口：fixed proof 原来只看 xfail reason，可能漏掉空 reason 的 xfail 标记。已通过 `xfail_marker_present` 显式字段修复，并补测试确认空 reason xfail 也会被抓住。

**目标**
- 从 P0 完成后开始，已登记 active xfail 数只能减少，不能增加；修掉一条后，ratchet 必须同步下降。

**文件**
- 修改：`tools/quality_gate_ledger.py`
- 修改：`tools/test_debt_registry.py`
- 修改：`tools/collect_full_test_debt.py`
- 修改：`tools/check_full_test_debt.py`
- 修改：`scripts/sync_debt_ledger.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`
- 测试：`tests/test_check_full_test_debt.py`
- 测试：`tests/test_sync_debt_ledger.py`

- [x] **步骤 1：写 ratchet / fixed 红灯测试**

已补测试覆盖：

- `tests/test_full_test_debt_registry_contract.py`：active xfail 数小于或大于 `max_registered_xfail` 都必须失败；空 reason 的 xfail 标记也会被 collector 记录成 `xfail_marker_present=true`。
- `tests/test_check_full_test_debt.py`：fixed 条目必须被 collect 到、必须普通 passed、不能继续带 xfail marker / wasxfail / XPASS 痕迹；active xfail 数和 ratchet 不一致必须失败。
- `tests/test_sync_debt_ledger.py`：`mark-test-debt-fixed` 成功路径、未知 debt_id、重复 debt_id、已经 fixed、ratchet 失真时失败且不保存。

- [x] **步骤 2：确认测试先失败**

运行任务 10 相关测试后先得到红灯：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_check_full_test_debt.py tests/test_sync_debt_ledger.py --tb=short -p no:cacheprovider
```

结果：`8 failed, 81 passed`。失败集中在：
- ratchet 只有“不能超过上限”，还没要求精确等于 active xfail 数。
- fixed 条目没有要求普通通过。
- `mark-test-debt-fixed` 命令不存在。

- [x] **步骤 3：实现 ratchet / fixed 闭环**

实际实现：
- `tools/quality_gate_ledger.py`：正式台账校验改成 `active_xfail_count == max_registered_xfail`，不允许留增长空位。
- `tools/test_debt_registry.py`：新增 `mark_test_debt_fixed()`，按唯一 debt_id 找到 active xfail，改成 fixed，更新 `last_verified_at`，并按剩余 active xfail 数重算 ratchet。
- `scripts/sync_debt_ledger.py`：新增 `mark-test-debt-fixed --debt-id ...` 命令；命令只读当前正式台账，不读 baseline，不碰 seed metadata；失败时不保存。
- `tools/collect_full_test_debt.py`：报告新增 `xfail_marker_present`，避免空 reason 的 xfail 标记被误判成无 xfail。
- `tools/check_full_test_debt.py`：fixed proof 要求 fixed nodeid 被 collect 到、有普通 passed 报告、没有 xfail marker、没有 wasxfail、没有 strict XPASS。

新增命令形态：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id <debt-id>
```

成功后摘要会包含 `debt_id`、`nodeid`、`previous_max_registered_xfail`、`next_max_registered_xfail`、`active_xfail_count`、`fixed_count`、`updated_at`。

- [x] **步骤 4：重新运行 ratchet 合同和门禁证明**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_check_full_test_debt.py tests/test_sync_debt_ledger.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/quality_gate_ledger.py tools/test_debt_registry.py tools/check_full_test_debt.py tools/collect_full_test_debt.py scripts/sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py tests/test_check_full_test_debt.py tests/test_sync_debt_ledger.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/quality_gate_ledger.py tools/test_debt_registry.py tools/check_full_test_debt.py tools/collect_full_test_debt.py scripts/sync_debt_ledger.py
git diff --check
```

结果：
- 任务 10 相关测试：`91 passed`。
- `tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`fixed_count=0`、`max_registered_xfail=5`、`collected_count=668`、`collection_error_count=0`、`unexpected_failure_count=0`。
- `scripts/sync_debt_ledger.py check`：通过，`schema_version=2`、`test_debt_count=5`。
- `ruff check`：通过。
- `pyright`：`0 errors, 0 warnings, 0 informations`。
- `git diff --check`：通过。

- [x] **步骤 5：子代理复审、修复审查问题并最终 clean gate**

子代理复审结果：
- 测试覆盖复审：通过。确认成功、未知 id、重复 id、已 fixed、ratchet 失真不保存、active 少于/多于 max 失败、fixed 未收集/未普通通过/仍带 xfail 痕迹失败都已覆盖。
- 提交边界复审：通过。确认没有混入 README、开发文档 README、`.github/workflows`、正式台账或 baseline 报告。
- 实现复审：先发现 fixed proof 对空 reason xfail 标记不够硬；已补 `xfail_marker_present` 并复审通过。

代码和测试提交后，在干净工作区运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果：通过，最后输出 `质量门禁通过`。门禁里的 `python tools/check_full_test_debt.py` 再次确认 `active_xfail_count=5`、`fixed_count=0`、`max_registered_xfail=5`、`collected_count=668`。

### 任务 11：文档同步

**任务 10 承接说明**
- 任务 10 已建立 full-test-debt 的只减不增规则：正式台账里的 active xfail 数必须等于 `test_debt.ratchet.max_registered_xfail`，不能多登记，也不能保留宽松余量。
- 已新增 `python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id ...`。后续修掉某条测试债务时，应先用该命令把条目标成 fixed，并同步下调 ratchet。
- fixed 条目不是“口头说修好了”即可通过，`tools/check_full_test_debt.py` 会要求它被 collect 到、有普通 passed 报告，并且没有任何 xfail 标记痕迹。
- 当前正式台账仍是 5 条 active xfail，`fixed_count=0`，`max_registered_xfail=5`；任务 10 没有修改正式台账，也没有修改 README、开发文档 README、workflow 或 baseline 报告。
- 任务 11 只做文档同步，不再改 ratchet 代码，不再改台账机器块，不修 5 条业务测试。文档要说清楚：full-test-debt proof 证明“没有未登记的 full pytest 失败，并且已登记债务只减不增”，不是证明历史债务已经全部修完。

**目标**
- 让 README 和开发文档不再暗示“collect-only 等于 full pytest 已执行”。

**文件**
- 修改：`README.md`
- 修改：`开发文档/README.md`
- 回填：`.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`

**本任务不改**
- 不改代码、测试、workflow、baseline 报告。
- 不改 `开发文档/技术债务治理台账.md` 的受控机器结构块。
- 不把 5 条已登记测试债务改成 fixed，也不下调 `test_debt.ratchet.max_registered_xfail`。

**停线边界**
- 如果文档同步必须改代码、workflow、baseline 或台账机器结构块，先停下来重新确认范围。
- 如果 `tools/check_full_test_debt.py` 或 `scripts/sync_debt_ledger.py check` 失败，先判断是当前文档改动造成，还是已有门禁事实变化；不能把失败包装成“仅文档问题”继续提交。
- 任务 11 后面没有任务 12，因此不硬造下一个任务头部；执行完成后在任务 11 末尾和 `## 4. 分层验证命令` 前写入 P0 收口说明。

- [x] **步骤 1：更新根 README**

修改 `README.md` 的质量门禁说明：
- 本地入口仍是 `python scripts/run_quality_gate.py`。
- CI 入口是 `python scripts/run_quality_gate.py --require-clean-worktree`。
- 门禁包含 full-test-debt proof，但 proof 的意思是“没有未登记 full pytest 失败”，不是“历史债务已全部修完”。
- `collect-only` 只列出测试，不执行 full pytest；`tests/regression` 是专项回归；`pytest tests` 才是直接执行全量测试。

执行结果：
- `README.md` 已补充干净工作区 / 托管入口 `python scripts/run_quality_gate.py --require-clean-worktree`。
- 已写清 `collect-only` 只列测试，不等于执行 full pytest。
- 已写清 full-test-debt proof 证明“没有未登记的 full pytest 失败，已登记债务被台账管住并只能减少”，不是证明 5 条历史测试债务已经修完。

- [x] **步骤 2：更新开发文档 README**

修改 `开发文档/README.md`：
- 增加 `test_debt` 登记规则。
- 增加 main-style 回归统一子进程执行规则。
- 明确新增 main-style 回归继续优先放 `tests/regression/`。
- 明确 `pytest tests` 的全量结果通过 `tools/check_full_test_debt.py` 纳入门禁。
- 明确测试债务修好后用 `python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id ...` 标成 fixed，不手删台账条目。
- 明确 `test_debt.ratchet.max_registered_xfail` 等于当前 active xfail 数，修掉一条后要同步下降。

执行结果：
- `开发文档/README.md` 已补充 `python tools/check_full_test_debt.py` 在门禁固定顺序中的位置。
- 已把“三类治理数据”改成当前真实口径：治理台账当前包含超长文件、高复杂度、静默回退、测试债务和接受风险。
- 已写清测试债务修好后走 `mark-test-debt-fixed`，并写清 active xfail 数必须等于 `test_debt.ratchet.max_registered_xfail`。
- 已写清 main-style 回归继续优先放 `tests/regression/`，由子进程执行；辅助 runner 不要命名成 `regression_*.py`。

- [x] **步骤 3：运行文档旧口径扫描**

运行：

```bash
rg -n "三类治理数据|collect-only|full pytest|check_full_test_debt|mark-test-debt-fixed|只减不增|未登记" README.md 开发文档/README.md
```

预期：只保留新口径解释，不再出现“collect-only 等于 full pytest 已执行”或“三类治理数据”的旧口径。

结果：通过。扫描命中均为新口径解释，未再出现“三类治理数据”，也未出现“collect-only 等于 full pytest 已执行”的旧说法。

- [x] **步骤 4：运行文档和门禁相关验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
git diff --check
```

预期：通过。

结果：
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py`：通过，输出 `OK`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py --tb=short -p no:cacheprovider`：通过，`24 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`fixed_count=0`、`max_registered_xfail=5`、`collected_count=668`、`collection_error_count=0`、`unexpected_failure_count=0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`schema_version=2`、`test_debt_count=5`。
- `git diff --check`：通过。

- [x] **步骤 5：子代理复审、修复问题并提交后跑 clean gate**

复审要求：
- 文档复审：确认文案没有把 full-test-debt proof 写成“历史债务已修完”。
- 边界复审：确认没有改代码、workflow、baseline、台账机器结构块，并确认本计划已回填。

提交后运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

预期：通过，最后输出 `质量门禁通过`。

复审结果：
- 文档复审通过：确认文案没有把 full-test-debt proof 写成“历史测试债务已修完”，`collect-only`、full pytest 执行和 `tools/check_full_test_debt.py` 的关系表达清楚。
- 边界复审通过：当前未提交改动仅限 `README.md`、`开发文档/README.md` 和本计划文件；没有改代码、测试、workflow、baseline、`开发文档/技术债务治理台账.md`，也没有硬造任务 12。
- 复审未提出需要修复的问题。

说明：提交后 clean gate 必须在干净工作区运行。本计划先记录提交前全部文档改动、验证和复审结果；最终提交后的 clean gate 结果在本轮交付说明中回报，避免为了记录“提交后验证结果”再次制造新的文档改动。

**P0 收口说明**
- 任务 11 已完成入口文档同步：根 README 和开发文档 README 都已写清 `collect-only` 只列测试，不等于执行 full pytest；full-test-debt proof 由 `python tools/check_full_test_debt.py` 完成，证明当前没有未登记的 full pytest 失败，且已登记测试债务受台账和只减不增规则约束。
- 文档已写清当前 5 条 full pytest 测试债务仍是 active xfail，`fixed_count=0`，`max_registered_xfail=5`；本任务没有把它们伪装成已修完，也没有改成 fixed。
- 文档已写清测试债务修好后的关闭动作：通过 `python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id ...` 标成 fixed，并随剩余 active xfail 数同步下调 ratchet。
- 文档已写清 main-style 回归继续优先放 `tests/regression/`，由子进程隔离执行，辅助 runner 不要命名成 `regression_*.py`。
- 本任务没有修改代码、测试、workflow、baseline 报告，也没有修改 `开发文档/技术债务治理台账.md` 的受控机器结构块。
- 提交前验证已通过：文档旧口径扫描、速查表一致性检查、`tests/test_run_quality_gate.py`、`tools/check_full_test_debt.py`、`scripts/sync_debt_ledger.py check`、`git diff --check`。
- 提交前只读复审已通过：文档含义无问题，改动边界无问题，原计划已回填执行结果。

**二次 deep review 返修记录（2026-04-27）**
- 当前返修来自 5 路初审和 3 路对抗复审后的 Review findings，重点修 4 个点：full pytest 债务 proof 只看 call 阶段会漏掉 setup / `xfail(run=False)`，CodeStable YAML fallback 读不懂多行列表，目录校验把 markdown 必填字段误套到 checklist.yaml，旧 baseline 不能继续作为当前证明。
- full pytest 债务合同已补硬：采集报告新增 `xfail_marker_run`；检查器用所有阶段报告查未登记 xfail 和 active xfail，用 call 阶段普通 passed 判断 fixed；已补测试覆盖未登记 `xfail(run=False)`、已登记 setup xfail、fixed 债务仍在 setup xfail 这三条边界。
- CodeStable 工具合同已补硬：无 PyYAML 时 fallback 支持常见 block list；坏 block list 和非独立 `---` 分隔符直接失败；目录模式下 `--require doc_type --require status` 只检查 markdown frontmatter，不再套到 checklist.yaml。
- 证据文档收口：`codestable/issues/2026-04-27-review-contract-hardening/review-contract-hardening-fix-note.md` 已修正测试数量；`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 的旧内容必须按历史快照看待，当前证明以后续干净工作区重新生成的 baseline 和 clean gate 为准。
- 本轮已复跑：`tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_regression_main_isolation_contract.py` 为 `154 passed`；`tests/test_codestable_tools_contract.py` 为 `10 passed`；`tools/check_full_test_debt.py` 为 `active_xfail_count=5`、`fixed_count=0`、`max_registered_xfail=5`、`collected_count=690`、`collection_error_count=0`；`scripts/sync_debt_ledger.py check` 通过。

---

## 4. 分层验证命令

### 每个任务后都跑

```bash
git status --short
git diff --check
git diff -U0 -- \
  tests/conftest.py \
  tests/main_style_regression_runner.py \
  tools/test_debt_registry.py \
  tools/collect_full_test_debt.py \
  tools/check_full_test_debt.py \
  tools/quality_gate_shared.py \
  tools/quality_gate_ledger.py \
  tools/quality_gate_support.py \
  scripts/run_quality_gate.py \
  scripts/sync_debt_ledger.py \
  | rg '^\+.*\b(if|elif|else|try|except|getattr|hasattr)\b|^\+.*(fallback|兜底|回退|or \[\]|or \{\})'
```

`rg` 有输出时停线，不继续实现。

### P0 定向验证

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --collect-only -q tests -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_full_test_debt_registry_contract.py \
  tests/test_regression_main_isolation_contract.py \
  tests/test_run_quality_gate.py \
  tests/test_run_full_selftest_report_metadata.py \
  --tb=short -p no:cacheprovider
```

### 共享层和主链普通测试

这些测试不代表修改业务，只用来证明 P0 治理没有带坏共享层、排产入口、启动器和插件。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/regression_config_service_component_contract.py \
  tests/regression_value_policies_matrix_contract.py \
  tests/regression_strict_parse_blank_required.py \
  tests/regression_field_parse_contract.py \
  tests/regression_schedule_input_builder_safe_float_parse.py \
  tests/regression_schedule_orchestrator_contract.py \
  tests/regression_schedule_service_facade_delegation.py \
  --tb=short -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/regression_runtime_probe_resolution.py \
  tests/test_win7_launcher_runtime_paths.py \
  tests/regression_runtime_contract_launcher.py \
  tests/regression_plugin_bootstrap_config_failure_visible.py \
  tests/regression_plugin_bootstrap_injects_config_reader.py \
  tests/regression_plugin_bootstrap_telemetry_failure_visible.py \
  --tb=short -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_architecture_fitness.py \
  tests/regression_request_services_contract.py \
  tests/regression_request_services_lazy_construction.py \
  tests/regression_request_services_failure_propagation.py \
  tests/regression_route_version_normalizers_contract.py \
  tests/regression_reports_page_version_default_latest.py \
  tests/regression_reports_export_version_default_latest.py \
  tests/regression_system_history_route_contract.py \
  --tb=short -p no:cacheprovider
```

### full pytest 验证

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q -ra --tb=short -p no:cacheprovider
```

预期：
- 没有未登记失败。
- 已登记债务显示为 xfail。
- 没有 XPASS。
- 两次连续运行结果一致。

### 最终质量门禁

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

预期：
- 质量门禁通过。
- worktree 运行前后干净。
- command receipt 中能看到 `python tools/check_full_test_debt.py`。
- replay 仍然绑定。

---

## 5. 停线条件

出现以下任一情况，停止实现并回报用户：

- 当前 full pytest 失败数量和基线不一致，且无法用已登记债务解释。
- 发现 required/proof 测试需要登记为 xfail。
- 需要修改 `core/shared/**`、`core/services/scheduler/**`、`web/bootstrap/launcher.py`、`web/bootstrap/plugins.py`、`web/routes/**`。
- 需要新增外部依赖。
- 需要修改 `.github/workflows/quality.yml`。
- 需要新增 `if`、`elif`、`else`、`try`、`except`、`fallback`、`兜底`、`回退`、`getattr`、`hasattr`。
- `tools/check_full_test_debt.py` 运行后产生 tracked 文件变更。
- `run_quality_gate.py --require-clean-worktree` 只能通过关闭 replay、允许 dirty worktree 或扩大 ignored evidence 才能通过。

---

## 6. 子代理核对结论采纳

- 采纳 pytest 收集链核对：main-style nodeid 不能变，债务 xfail 必须精确 nodeid 匹配；普通定向 pytest 不做全量登记缺失检查，登记缺失只由 `tools/check_full_test_debt.py` 在 full-suite 场景失败。
- 采纳质量门禁核对：full-test-debt proof 必须进入 shared command plan 和 receipt/replay 体系，不能只写在 workflow 或自由文本里。
- 采纳台账核对：不新建第二套长期债务事实源，扩展现有 `开发文档/技术债务治理台账.md`。
- 采纳共享层联动核对：P0 不碰业务层，只跑普通测试证明没有带坏。
- 采纳采集方式核对：不用解析 `pytest -q -ra --tb=short` 文本，不引入 `pytest-json-report`，使用 pytest hook 结构化采集。
- 采纳文档/CI 核对：不改 CI workflow，不新增依赖，同步 README 和开发文档入口。
- 采纳对抗审查修正：required/proof 自身失败不能登记为 xfail；导入时不允许 `untriaged` 占位；`ratchet.max_registered_xfail` 由实际候选债务数量生成；新增条件分支必须先向用户解释并确认。

---

## 7. 交付标准

P0 完成时必须同时满足：

- 当前 full pytest 失败债务有登记、有 owner、有 root、有退出条件。
- required/proof 自身测试全部普通通过，不在 xfail 债务里。
- `tools/check_full_test_debt.py` 阻断未登记失败。
- main-style 回归子进程隔离，连续两次 full pytest 结果一致。
- `scripts/run_quality_gate.py --require-clean-worktree` 通过。
- `git status --short` 干净。
- diff 扫描没有新增未经用户确认的条件分支或兜底字样。
- README 和开发文档说明不再把 collect-only 误写成全量执行。
