# ISOLATE_PERF 隔离方案（P5.3，机制下钻 — 非合并）

> 目标：把 8 个性能 / 重 E2E 文件从「每次 push 的 daily gate 路径」剔除，迁到独立 CI job / 手动入口，
> **不制造死 marker、不碰 full gate 红线**。本 spec 只读分析，不改任何文件。

铁律对照：本任务不涉及断言合并，无「断言条数对账」；保真口径＝隔离前后 full gate 全量覆盖与 required 覆盖**完全不变**，
仅改变「push 路径是否跑 perf」。

---

## 0. 现状机制(已读源码核实)

| 机制 | 事实 | 出处(file:line) |
|---|---|---|
| full gate 全量集 | `FORMAL_FULL_TEST_PYTEST_ARGS = ["tests","-q","--tb=short","-ra","-p","no:cacheprovider"]` —— **跑整个 tests 目录，无任何 `-m` markexpr deselect** | tools/quality_gate_shared.py:96 |
| full gate 分片 | `collect_full_test_debt.py` sharded 模式先 `--collect-only` 全量 nodeid，再 `split_nodeids`→`classify_nodeid` 分 serial/parallel；**分片只看文件名/nodeid 模式，完全不看 marker** | tools/collect_full_test_debt.py:636-647 / tools/full_test_debt_shards.py:46-57 |
| daily gate impact 集 | 按 `tools.test_registry` 的 required regression groups 的 `target_paths`/scope 选；非全量；分两步 `-m "not serial"`(parallel) + `-m "serial"` | scripts/run_daily_quality_gate.py:519-541,364-412 |
| daily gate collect 自检 | 无条件 `pytest --collect-only tests -q`，只统计 collected_count，不按 marker 过滤 | scripts/run_daily_quality_gate.py:568-569 |
| serial/required 自动打标 | conftest `pytest_collection_modifyitems` 按 `classify_nodeid`==serial 打 `serial`、按 registry 打 `required`（单一真相源） | tests/conftest.py:33-46 |
| marker 登记 | pyproject `[tool.pytest.ini_options].markers` 仅登记 `required` / `serial`；**无 `strict-markers`、无 `addopts`** | pyproject.toml:6-11 |
| required 覆盖核销 | verifier 从 full gate payload 核销「required 全收集+全通过+组覆盖完整」，required_paths 来自 registry groups | tools/verify_required_regressions_from_full_test_debt.py:1-5,150-163 |

**两条决定性推论**：
1. **加 `perf` marker 对 full gate 完全惰性、零误伤**。full gate 不带 `-m` deselect → 照样收集并跑 perf 文件；sharding 只按文件名/nodeid 分流不看 marker → perf marker 不影响分片归属。full gate 红线安全。
2. **`-m "not perf"` 即便无任何用例打 perf 也不报错**（pytest marker 表达式对未匹配 marker 返回空集，非错误）。再叠加「pyproject 无 strict-markers」→ 不会因未登记 marker 而 collect 报错。**死 marker 风险天然不成立**。唯一干净度要求：要用 `perf` 就把它登记进 pyproject markers 段（消除 `PytestUnknownMarkWarning`）。

---

## A. 5 个未收集脚本(main-style 脚本，exit-5 不被 pytest 收集)：当前如何被调用？删/标记会断什么？

`python_files=["test_*.py","*_test.py","regression_*.py"]`。这 5 个文件名都不匹配 → pytest 永不收集 → **本就不在 daily/full 任何 pytest 路径内**。逐个核实全仓引用：

### A1. `tests/run_complex_excel_cases_e2e.py` (1909 行) —— **强 load-bearing，禁删**
- 被 `tests/regression_request_service_test_factory_invariant.py:17` 顶层 `import run_complex_excel_cases_e2e as complex_mod`，并在 :77 调 `complex_mod.create_test_app(...)`（该 regression 是被收集的 required-风格测试）。
- 被 `tools/quality_gate_shared.py:218`（`REQUEST_SERVICE_SCAN_SCOPE_PATTERNS`）+ :252（`REQUEST_SERVICE_TARGET_SYMBOLS` 登记 `["create_test_app","_open_db"]`）作为**门禁扫描契约目标**。
- 被 `tests/regression_quality_gate_scan_contract.py:615` 断言：`assert "_open_db" in shared_mod.REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_complex_excel_cases_e2e.py"]`。
- **断点**：删文件 → `regression_request_service_test_factory_invariant.py` 收集期 ImportError（红）；契约扫描找不到目标文件/符号（红）；scan_contract 断言失败（红）。
- **动作**：**保持原样，零改动**。它已不在 push 路径（exit-5）。若未来要删须同步退掉上述 3 处契约+1 处 import，超出本 P5.3 范围。

### A2. `tests/smoke_e2e_excel_to_schedule.py` (773 行) —— 仅手动跑 + 文档引用
- 代码引用：**全仓 0 处** `import`/契约。仅 .codestable 审计文档（R40/B16 dossier、_CROSS_IMPACT_TRUTH.md:73 标记 ISOLATE_PERF）与 audit/ 历史 runbook 提到手动命令 `python tests/smoke_e2e_excel_to_schedule.py`（写 `evidence/FullE2E/excel_to_schedule_report.md`）。
- **断点**：无代码断点。删则丢失全链路 happy-path 手动 smoke 能力（_CROSS_IMPACT_TRUTH.md:73 明确「应隔离非删」）。
- **动作**：保留为手动/CI-perf 入口；不收集、不进 push，**本就已隔离，无需改动**。

### A3. `tests/benchmark_sgs_large_resource_pool.py` (269 行) —— 仅手动 benchmark
- 代码引用：0 处 import/契约。仅 perf-cache refactor 笔记里的手动命令 `.venv/bin/python tests/benchmark_sgs_large_resource_pool.py`（写 benchmark report）。
- **动作**：保留手动入口，无需改动。

### A4. `tests/benchmark_fjsp.py` (702 行) —— 仅手动 benchmark；有一处 R34 计划性 repoint(未落地)
- 代码引用：0 处运行期 import。`.codestable` R34 dossier 记录 `benchmark_fjsp.py:503` 调 `ScheduleRepository.get_version_time_span` 需 repoint —— 那是**另一条债(R34/P4)的计划，不在本 ISOLATE_PERF 范围**，且尚未落地（dossier 自述「仍未 repoint」）。本 spec 不动 :503。
- **动作**：保留手动入口，无需改动。提醒：R34 落地时会改 :503，与本隔离正交。

### A5. `tests/run_synthetic_case.py` (697 行) —— 仅手动 CLI
- 代码引用：0 处 import/契约。仅 audit/2026-03 的 deep_review / perf_profile 历史手动命令。
- **动作**：保留手动入口，无需改动。

**A 小结**：5 个 main-style 脚本里 **4 个(A2-A5) 已天然在 push 路径之外，零动作**；唯一需特别保护的是 A1（load-bearing，禁删禁动）。本批 ISOLATE_PERF 对这 5 个文件**不需要任何代码改动** —— 它们的「隔离」是既成事实。真正要做的隔离动作只针对 B 节的 3 个被收集文件。

---

## B. 3 个被收集文件：最优雅的「出 push 路径」强制点

### 被收集文件清单与归属核实

| 文件(行数) | pytest 收集 | classify_nodeid 当前归属 | 在 registry/required/startup? | 其它代码引用 |
|---|---|---|---|---|
| `tests/scheduler_graph/test_graph_performance.py` (417) | 5 tests, parallel | parallel | **否**(grep tools/scripts/conftest/pyproject/.github 全 0) | 无 |
| `tests/regression_scheduler_candidate_performance_guard.py` (236) | 4 tests, parallel | parallel | **否**(全 0) | 无 |
| `tests/regression_ui_browser_geometry_smoke.py` (124) | 2 tests, **serial**(真浏览器 ~19s 最慢) | serial(命中 full_test_debt_shards.py:11-12 SERIAL_FILE_PATTERNS 首条精确名) | **否**(不在 registry；test_registry_data.py:233 命中的是另一文件 `test_ui_browser_geometry_env.py`) | full_test_debt_shards.py:12(serial 清单)、report_full_test_debt_durations.py:41(报告特判) |

三者都**不在任何 registry required group / startup regression** → daily gate 的 impact 集**理论上不会主动选中它们**（除非将来某 group 的 target_paths/scope glob 覆盖到这些路径，或 scope-unknown 兜底全跑）。但它们**会被 daily gate 的 `pytest --collect-only tests` 收集计数**，且**会被 full gate 全量跑**。

### 最优雅强制点 = conftest 自动打 `perf` marker（与 serial/required 同机制单一真相源）

不在 8 个文件里逐个手写 `pytestmark = pytest.mark.perf`（散点、易漏、与现有 serial/required 自动打标范式不一致）。改在 `tests/conftest.py:33` 的 `pytest_collection_modifyitems` 增一段：维护一个 **PERF 文件清单**（最稳是复用一个 `tools` 侧单一真相源，类比 `full_test_debt_shards.SERIAL_FILE_PATTERNS`），对匹配用例 `item.add_marker(pytest.mark.perf)`。

- **daily gate 强制点**：scripts/run_daily_quality_gate.py:_commands。
  - 现状两步：`-m "not serial"`（parallel）与 `-m "serial"`。
  - 改为：parallel 步 `-m "not serial and not perf"`，serial 步 `-m "serial and not perf"`，**再新增一步 `-m perf`(单独、可选、默认不在 push 跑)**。
  - 类比依据：P4 已在此处加 serial 分流，daily gate **非红线**（脚本头自述「fast daily gate only, not final clean proof」run_daily_quality_gate.py:622-623）→ 加 `not perf` deselect 是安全的同范式扩展。
  - 注意 `allow_no_tests=True` 已对 parallel/serial 两步开启（exit-5 容忍合法空集，:533/:540）→ 叠加 `not perf` 后某步为空仍合法通过。
  - **真实「出 push」语义**：daily gate 当前对 impact 集本就极少命中这 3 文件；真正每次 push 必跑的是 FOCUSED_PYTEST_NODEIDS（3 个固定冒烟，run_daily_quality_gate.py:33-37，不含任何 perf）。所以 daily 侧加 `not perf` 是**防御性兜底**(防 scope-unknown 全跑或未来 group glob 误纳)，主要价值在 collect 计数与语义清晰，不是当前热点。

- **full gate 强制点**：**不需要也不应改**。full gate 跑 `tests` 全量无 markexpr → perf 文件继续被 full gate 收集+跑（覆盖不丢，required 核销不受影响）。perf marker 在 full gate 惰性存在。

- **独立 CI perf job**：在 `.github/workflows/quality.yml` 新增一个独立 job（或现有 job 加一步），跑：
  - `pytest -m perf tests`（收集到的 3 个文件 11 个 test）
  - + 5 个 main-style 脚本的显式手动命令（A2/A3/A5 的 `python tests/xxx.py ...`；A4 benchmark_fjsp 同理）。
  - 该 perf job 设 `continue-on-error` 或独立 timeout，不阻塞 quality-gate job 的 push 合并门禁。

### full gate sharding 是否会被 perf 标记误伤？—— **不会**

- `split_nodeids`/`classify_nodeid`（full_test_debt_shards.py:46-80）分流键是**文件路径 + nodeid 文本模式**，从不读 pytest marker。加 perf marker 后这 3 文件的 serial/parallel 归属**完全不变**：
  - test_graph_performance / candidate_performance_guard → 仍 parallel（不匹配任何 SERIAL_FILE_PATTERNS/NODEID_PATTERNS）。
  - regression_ui_browser_geometry_smoke → 仍 serial（命中 SERIAL_FILE_PATTERNS:11-12 精确名，**不可动这条**，动了会让真浏览器测试错进并行分片）。
- 结论：perf marker 与 full gate sharding 正交，零误伤。

---

## C. 每文件明确建议动作 + 真实强制点

| # | 文件 | 收集态 | 建议动作 | 真实强制点(避免死 marker) |
|---|---|---|---|---|
| 1 | tests/scheduler_graph/test_graph_performance.py | 收集,5,parallel | 打 `perf` marker(经 conftest 清单) | conftest 自动打标 + daily `-m "not ... and not perf"` deselect；full gate 不变照跑 |
| 2 | tests/regression_scheduler_candidate_performance_guard.py | 收集,4,parallel | 打 `perf` marker | 同上 |
| 3 | tests/regression_ui_browser_geometry_smoke.py | 收集,2,**serial** | 打 `perf` marker，**保留 serial 归属不动** | conftest 同时保留 serial 自动打标(shards.py:12 不改) + 加 perf；daily serial 步用 `-m "serial and not perf"` 把它踢出 push；CI perf job 用 `-m perf` 单独串行跑 |
| 4 | tests/run_complex_excel_cases_e2e.py | 未收集(exit-5) | **零动作，禁删** | 已不在 push 路径；3 处契约+1 import load-bearing(见 A1) |
| 5 | tests/smoke_e2e_excel_to_schedule.py | 未收集 | 零代码改动；登记进 CI perf job 手动命令 | 文件名不匹配 python_files → 永不收集，已隔离 |
| 6 | tests/benchmark_sgs_large_resource_pool.py | 未收集 | 同 5 | 已隔离 |
| 7 | tests/benchmark_fjsp.py | 未收集 | 同 5；:503 的 R34 repoint 归 P4 另办 | 已隔离 |
| 8 | tests/run_synthetic_case.py | 未收集 | 同 5 | 已隔离 |

### 落地改动面(供 P5.3 实现批用)
1. **pyproject.toml:8 markers 段**：新增 `"perf: 性能/重E2E用例,出push路径,走独立CI job;人用入口 pytest -m perf"`（消除 unknown-mark 警告；非强制但应做）。
2. **新增 PERF 单一真相源**：建议在 `tools/full_test_debt_shards.py` 旁加 `PERF_FILE_PATTERNS`（或新模块），列入文件 #1/#2/#3 三条路径，供 conftest 复用——与 SERIAL_FILE_PATTERNS 同范式。
3. **tests/conftest.py:33-46**：在 `pytest_collection_modifyitems` 内补 `if <匹配 PERF 清单>: item.add_marker(pytest.mark.perf)`。
4. **scripts/run_daily_quality_gate.py:_commands(519-541)**：parallel 步 markexpr 改 `not serial and not perf`、serial 步改 `serial and not perf`、新增可选 `-m perf` 步（默认不入 push，或仅 nightly）。
5. **.github/workflows/quality.yml**：新增独立 perf job（`pytest -m perf tests` + 5 个 main-style 脚本手动命令），不阻塞 quality-gate job。
6. **full gate / scripts/run_quality_gate.py**：**不改**（红线，且 perf marker 对其惰性）。

---

## D. registry 影响

**无须改 tools/test_registry_data.py**。这 3 个被收集文件 + 5 个未收集脚本**全部不在** required regression groups / startup regressions（grep 实测：test_registry_data.py:233 命中的是 `test_ui_browser_geometry_env.py` 而非本批的 `regression_ui_browser_geometry_smoke.py`，是同名前缀不同文件）。打 perf marker 不改变 registry 的 required 覆盖，verifier 核销不受影响。

## E. B-COMPAT pin(禁去重/禁动的逐字红线)

本任务无断言合并，但有 4 条**禁动**红线必须逐字保留：
1. `tools/full_test_debt_shards.py:11-12` 的 `SERIAL_FILE_PATTERNS` 首条 `"tests/regression_ui_browser_geometry_smoke.py"` —— 文件 #3 的 serial 归属，**不可移除/改写**(否则真浏览器 19s 测试错进并行分片，破坏 full gate)。
2. `tools/quality_gate_shared.py:218` `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 含 `"tests/run_complex_excel_cases_e2e.py"`、:252 `REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_complex_excel_cases_e2e.py"] = ["create_test_app","_open_db"]` —— 文件 #4 契约 pin，**禁删该文件、禁改该符号清单**。
3. `tests/regression_request_service_test_factory_invariant.py:17` `import run_complex_excel_cases_e2e as complex_mod` 及 :77 `complex_mod.create_test_app(...)` —— 文件 #4 运行期 import pin。
4. `tests/regression_quality_gate_scan_contract.py:615` `assert "_open_db" in shared_mod.REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_complex_excel_cases_e2e.py"]` —— 文件 #4 契约断言 pin。

## F. 风险 / 阻塞点

- **阻塞性风险：无**。隔离方案不删任何文件、不碰 full gate、对 full gate sharding 正交、对 required 覆盖零影响。
- **次要风险**：
  - daily gate 加 `-m perf` 单独步时若误设 `allow_no_tests=False`，在 perf 集为空时会 exit-5 误判失败 → 实现时该步须 `allow_no_tests=True`，或干脆不在 daily 跑 perf 步(仅 nightly/独立 job)。
  - 若实现者图省事在 8 文件里散点写 `pytestmark` 而非走 conftest 单一真相源 → 偏离现有 serial/required 范式，易与未来打标逻辑冲突。强烈建议走 conftest+PERF 清单。
  - perf marker **必须登记进 pyproject markers**，否则全量收集时刷 `PytestUnknownMarkWarning`(不报错但脏)。
- **越层/分层 AST**：CI perf job 跑的是 tests/ 脚本，不构成生产代码越层，无分层红线影响。
