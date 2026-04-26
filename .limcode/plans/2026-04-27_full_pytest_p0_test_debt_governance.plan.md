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

**目标**
- 在 main-style 污染消除、required/proof 自身测试通过之后，重新生成可导入债务的正式基线。

**文件**
- 新建：`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`
- 使用 / 验证：`tools/collect_full_test_debt.py`

- [ ] **步骤 1：生成正式基线**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/collect_full_test_debt.py \
  --baseline-kind after_main_style_isolation \
  --write-baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md \
  -- tests -q --tb=short -ra -p no:cacheprovider
```

预期：
- 基线包含机器可读 JSON 结构块。
- 基线标注 `baseline_kind = "after_main_style_isolation"`。
- required/proof nodeid 不在 `candidate_test_debt` 中。
- 如果剩余失败数为 0，后续 `test_debt.entries` 为空，`max_registered_xfail=0`。

### 任务 5：把测试债务并入现有治理台账

**目标**
- 不另起第二套债务事实源；nodeid 级测试债务进入 `开发文档/技术债务治理台账.md` 的受控 JSON。

**文件**
- 修改：`开发文档/技术债务治理台账.md`
- 修改：`tools/quality_gate_ledger.py`
- 修改：`scripts/sync_debt_ledger.py`
- 新建：`tools/test_debt_registry.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`

- [ ] **步骤 1：写 ledger schema 合同测试**

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

`mode` 只允许 `xfail`、`fixed`。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

预期：因为 ledger 还没有 `test_debt` schema 而失败。

- [ ] **步骤 3：扩展 ledger schema**

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

- [ ] **步骤 4：增加导入命令**

在 `scripts/sync_debt_ledger.py` 增加：

```bash
python scripts/sync_debt_ledger.py import-test-debt-baseline --baseline audit/2026-04/20260427_full_pytest_p0_debt_baseline.md
```

该命令只做一件事：读取基线里的机器可读 JSON 结构块，把 `candidate_test_debt` nodeid 转成 `test_debt.entries` 初始登记。`required_or_quality_gate_self_failure` 和 `main_style_isolation_candidate` 不允许导入。命令不得解析 Markdown 普通文字。

导入前必须为每个 `candidate_test_debt` 填好 `domain`、`root.module`、`root.function`、`owner`、`exit_condition`。不允许写 `untriaged` 占位，因为用户要求 P0 全部核对，不接受只登记不归因。

如果实现这一步必须新增条件分支，执行者先停下来向用户说明原因。

- [ ] **步骤 5：重新运行 ledger 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sync_debt_ledger.py tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
```

预期：通过。

### 任务 6：给 pytest 接入 debt-aware xfail

**目标**
- 已登记债务显示为 xfail；未登记的新失败仍然失败。

**文件**
- 修改：`tests/conftest.py`
- 修改：`tools/test_debt_registry.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`

- [ ] **步骤 1：写 collection 合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加：

```python
def test_registered_test_debt_marks_exact_nodeid_xfail_and_rejects_missing_nodeid(tmp_path):
    ...
```

断言：
- 只按精确 nodeid 匹配。
- 普通定向 pytest 只给本次实际收集到的登记 nodeid 加 xfail，不检查未收集到的全量登记 nodeid。
- 登记文件解析失败时，pytest collection 失败。
- `mode=fixed` 不会加 xfail。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

预期：因为 `tests/conftest.py` 还没有 debt-aware hook 而失败。

- [ ] **步骤 3：接入 pytest hook**

在 `tests/conftest.py` 增加 `pytest_collection_modifyitems`，行为为：
- 加载 `tools/test_debt_registry.py` 的登记。
- 计算 collected nodeid 集合。
- 只处理当前 collected nodeid 中存在的登记项。
- `mode=xfail` 时给 item 加 `pytest.mark.xfail(reason="TEST-DEBT-xxx: ...", strict=True)`。
- `mode=fixed` 时不加 marker。

不得按文件前缀、目录、正则模糊匹配。不得在这里校验“登记 nodeid 是否全部被 collect 到”；这个全量一致性检查只放在 `tools/check_full_test_debt.py`。

- [ ] **步骤 4：重新运行 collection 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --collect-only -q tests -p no:cacheprovider
```

预期：通过，收集数量稳定。

### 任务 7：质量门禁 runner 真正按 shared command plan 执行

**目标**
- 先修正 `scripts/run_quality_gate.py` 的固定索引执行方式，避免新增命令插入 shared plan 后被跳过。

**文件**
- 修改：`scripts/run_quality_gate.py`
- 修改：`tests/test_run_quality_gate.py`

- [ ] **步骤 1：写命令顺序合同测试**

在 `tests/test_run_quality_gate.py` 增加断言：
- runner 执行的 display 顺序等于 `build_quality_gate_command_plan()`。
- ruff version / pyright version 的解析仍然发生。
- command receipt 数量等于 shared command plan 数量。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

预期：因为当前 runner 手写前三个命令并跑 `command_plan[3:]` 而失败。

- [ ] **步骤 3：改造 runner**

让 `scripts/run_quality_gate.py` 以 shared command plan 为唯一命令源。需要对特定 display 绑定结果解析器：
- `python -m pytest --collect-only -q tests`：构建 collection proof。
- `python -m ruff --version`：解析 ruff version。
- `python -m pyright --version`：解析 pyright version。
- 其他命令只要求 returncode 为 0。

这一步必然需要 display 到解析器的映射或等价表驱动结构。实现前必须向用户说明新增条件分支或映射的必要性；不得写“命令不存在就跳过”的兜底。

- [ ] **步骤 4：重新运行命令顺序合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

预期：通过。

### 任务 8：质量门禁接入 full-test-debt proof

**目标**
- CI 仍然只跑统一门禁入口，但门禁能证明没有未登记全量失败。

**文件**
- 新建：`tools/check_full_test_debt.py`
- 修改：`tools/quality_gate_shared.py`
- 修改：`tools/quality_gate_support.py`
- 修改：`scripts/run_quality_gate.py`
- 修改：`tests/test_run_quality_gate.py`
- 修改：`tests/test_run_full_selftest_report_metadata.py`

- [ ] **步骤 1：写 proof 合同测试**

在 `tests/test_run_quality_gate.py` 增加断言：
- command plan 包含 `python tools/check_full_test_debt.py`。
- 该命令来自 `build_quality_gate_command_plan()`。
- `scripts/run_quality_gate.py` 不手写第二套 full-test-debt 命令。
- 新脚本在 `QUALITY_GATE_SOURCE_FILES` 里。
- 新脚本在 `QUALITY_GATE_TOOL_PATHS` 里接受 pyright 检查。
- `tools/collect_full_test_debt.py`、`tools/test_debt_registry.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py` 也进入 `QUALITY_GATE_SOURCE_FILES`，因为它们共同决定 full-test-debt proof 语义。

在 `tests/test_run_full_selftest_report_metadata.py` 增加断言：
- command replay 会重新跑 `tools/check_full_test_debt.py`。
- 缺少该 command receipt 时，quality gate binding 失败。
- receipt hash 被篡改时，quality gate binding 失败。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py --tb=short -p no:cacheprovider
```

预期：因为 command plan 未接入 full-test-debt proof 而失败。

- [ ] **步骤 3：实现 `tools/check_full_test_debt.py`**

行为：
- 调用 `tools/collect_full_test_debt.py`，执行 `pytest tests -q --tb=short -ra`。
- 读取结构化 JSON。
- 校验 collected nodeid 不为空。
- 校验登记 nodeid 都被 collect 到。
- 校验未登记失败数为 0。
- 校验 `mode=xfail` 数量不超过 `test_debt.ratchet.max_registered_xfail`。
- 校验 `mode=fixed` 不再出现在 xfail marker 中。
- 校验 required/proof 测试不在 `mode=xfail` 中。
- 校验采集结果包含 xfail/xpass 相关字段，例如 `wasxfail` 或等价 reason 字段，能区分登记债务 xfail、普通 skip 和 XPASS。
- stdout 输出稳定 JSON summary，供 quality gate receipt 记录 hash。

第一版不新增 `quality_gate_manifest.json` 顶层自由字段。证明通过 command receipt、commands hash、source hash 和 replay 表达。这样不会制造第二套 manifest 字段解释口径。

- [ ] **步骤 4：接入 shared command plan**

在 `tools/quality_gate_shared.py::build_quality_gate_command_plan()` 增加：

```text
python tools/check_full_test_debt.py
```

放置位置：`python -m pytest --collect-only -q tests` 之后，`python -m ruff --version` 之前。

同步：
- `QUALITY_GATE_TOOL_PATHS`
- `QUALITY_GATE_SOURCE_FILES`
- `tools/quality_gate_support.py` 导出项

不得修改 `.github/workflows/quality.yml`。

- [ ] **步骤 5：重新运行 proof 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py --tb=short -p no:cacheprovider
```

预期：通过。

### 任务 9：收敛 required/startup/full-debt 三套入口

**目标**
- 让 required tests、startup regressions、full test debt 都从同一个测试 registry 模块派生，避免以后再分裂。

**文件**
- 新建或扩展：`tools/test_debt_registry.py`
- 修改：`tools/quality_gate_shared.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`
- 测试：`tests/test_run_quality_gate.py`

- [ ] **步骤 1：写 registry 一致性测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加：

```python
def test_quality_gate_required_startup_and_full_debt_share_registry():
    ...
```

断言：
- required tests 没有重复。
- startup regressions 没有重复。
- full debt nodeids 没有重复。
- required tests 不允许出现在 `mode=xfail` 的 test debt 中。
- 所有路径都存在并被 git 跟踪。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

预期：因为 registry 还没有统一出口而失败。

- [ ] **步骤 3：收敛 registry 出口**

`tools/test_debt_registry.py` 提供：
- `iter_required_tests()`
- `iter_startup_regressions()`
- `load_test_debt_registry()`
- `hash_test_debt_registry()`

`tools/quality_gate_shared.py` 使用这些出口生成 command plan，不再在多个文件手工维护测试清单。

不得同时保留旧路径和新路径。

- [ ] **步骤 4：重新运行 registry 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

预期：通过。

### 任务 10：建立只减不增的 ratchet

**目标**
- 从 P0 完成后开始，已登记 xfail 数只能减少，不能增加。

**文件**
- 修改：`tools/test_debt_registry.py`
- 修改：`tools/check_full_test_debt.py`
- 修改：`scripts/sync_debt_ledger.py`
- 测试：`tests/test_full_test_debt_registry_contract.py`

- [ ] **步骤 1：写 ratchet 合同测试**

在 `tests/test_full_test_debt_registry_contract.py` 增加：

```python
def test_test_debt_ratchet_rejects_growth_and_fixed_entries():
    ...
```

断言：
- `entries` 中 `mode=xfail` 数量大于 `ratchet.max_registered_xfail` 时失败。
- 删除一个 xfail entry 后，必须降低 `max_registered_xfail`。
- `mode=fixed` 条目不能长期留在 registry 中。

- [ ] **步骤 2：确认测试先失败**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
```

预期：因为 ratchet 还没有校验而失败。

- [ ] **步骤 3：实现 ratchet**

在 `tools/test_debt_registry.py` 和 `tools/check_full_test_debt.py` 中执行 ratchet 校验。发现增长直接报错。

在 `scripts/sync_debt_ledger.py` 中增加命令：

```bash
python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id TEST-DEBT-001
```

该命令只做两件事：
- 把对应 entry 标成 `fixed`。
- 把 `ratchet.max_registered_xfail` 下调 1。

`ratchet.max_registered_xfail` 初始值必须由导入后的 `mode=xfail` 数量生成，不能手写 36 或 41。

- [ ] **步骤 4：重新运行 ratchet 合同**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_full_test_debt_registry_contract.py --tb=short -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
```

预期：通过。

### 任务 11：文档同步

**目标**
- 让 README 和开发文档不再暗示“collect-only 等于 full pytest 已执行”。

**文件**
- 修改：`README.md`
- 修改：`开发文档/README.md`

- [ ] **步骤 1：更新根 README**

修改 `README.md` 的质量门禁说明：
- 本地入口仍是 `python scripts/run_quality_gate.py`。
- CI 入口是 `python scripts/run_quality_gate.py --require-clean-worktree`。
- 门禁包含 full-test-debt proof，但 proof 的意思是“没有未登记 full pytest 失败”，不是“历史债务已全部修完”。

- [ ] **步骤 2：更新开发文档 README**

修改 `开发文档/README.md`：
- 增加 `test_debt` 登记规则。
- 增加 main-style 回归统一子进程执行规则。
- 明确新增 main-style 回归继续优先放 `tests/regression/`。
- 明确 `pytest tests` 的全量结果通过 `tools/check_full_test_debt.py` 纳入门禁。

- [ ] **步骤 3：运行文档相关验证**

运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py --tb=short -p no:cacheprovider
```

预期：通过。

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
