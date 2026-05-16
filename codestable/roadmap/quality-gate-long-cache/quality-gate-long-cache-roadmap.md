---
doc_type: roadmap
slug: quality-gate-long-cache
status: completed
created: 2026-05-12
last_reviewed: 2026-05-16
tags: [quality-gate, cache, full-test-debt, pyright, ruff]
related_requirements: []
related_architecture: [codestable/architecture/ARCHITECTURE.md]
---

# 质量门禁长耗时缓存路线

## 1. 当前状态确认

这份 roadmap 已完成 NEXT-1 到 NEXT-13 和 P6 的既定收口；它记录的是本轮 long gate cache 路线的历史和最终口径，不代表所有慢门禁都已经缓存。`static-formal-cache` 已完成正式 ruff / pyright 静态门禁 success cache，`debt-ledger-sync-cache` 已完成债务台账同步检查 success cache，`quickref-vs-routes-cache` 已完成系统速查表与真实路由对账检查 success cache，NEXT-13 已完成文档、状态回写和最终 clean proof 收口，P6 已让 GitHub Actions 在完整门禁前恢复 long gate 运行产物缓存、在完整门禁成功后保存缓存。`full_test_debt` 先支持整项成功复用，现在又补了安全的 nodeid 级增量和台账-only 路径；`startup_runtime_regressions` 和 `required_regressions` 已支持整组成功复用；NEXT-8 `architecture-scan-file-cache` 已完成文件级扫描事实缓存，但它只缓存单文件事实，不启用 `architecture_fitness` 整项成功复用；NEXT-9 `fast-static-precheck` 已完成局部 ruff 快速预检，pyright 默认跳过并明确不代表正式 pyright gate。当前 enabled long gate entry 是 `pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`required_regressions`、`debt_ledger_sync`、`startup_runtime_regressions` 和 `quickref_vs_routes`。`architecture_fitness` 仍保持 planned；如果后续要启用它，应另起新的 feature / roadmap。

`pre-push-long-gate-cache` 是历史完成项：完成当时把本地 pre-push hook 接到了完整 clean gate + long gate cache。后续为了避免日常 push 每次都被完整 full-test-debt 拖住，pre-push 已改为运行 `scripts/run_daily_quality_gate.py`。当前最终完整门禁仍由 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 承担，也可以通过 `tools/git_hook_checks.py run-final-quality-gate` 手动触发；这不会额外启用仍处于 planned 的 `architecture_fitness`。

已经完成并可以继续沿用：

| 范围 | 当前状态 |
|---|---|
| CodeStable 路线和 feature 文档 | 已建立 `codestable/roadmap/quality-gate-long-cache/` 和各阶段 feature 文档。 |
| 基础模块 | 已有 `tools/long_gate_manifest.py`、`tools/long_gate_fingerprint.py`、`tools/long_gate_cache.py`、`tools/long_gate_collect.py`。 |
| 已启用成功缓存 | `pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`required_regressions`、`debt_ledger_sync`、`startup_runtime_regressions` 和 `quickref_vs_routes`。分别对应 collect-only、`python tools/check_full_test_debt.py`、正式 `python -m ruff check`、正式 `python -m pyright -p pyrightconfig.gate.json`、正式 `python -m pyright -p pyrightconfig.tools.json`、真实 command plan 里的 required pytest 整组命令、`python scripts/sync_debt_ledger.py check`、真实 command plan 里的 startup pytest 整组命令，以及 `python tests/check_quickref_vs_routes.py`。 |
| runner 参数 | 已有 `--long-gate-cache`、`--no-long-gate-cache`、`--long-gate-cache-explain`、`--long-gate-cache-dir`、`--long-gate-force-rerun`、`--long-gate-force-rerun-all`。 |
| collect 输出 | collect-only 成功后可写 `evidence/QualityGate/collect_nodeids.json`。 |
| receipt 字段 | 已有 `execution_mode`、`reused_from`、耗时字段、`timed_out`、`interrupted`、`partial_write`。 |
| 缓存安全底线 | 已校验 entry、command、fingerprint、log、output、路径逃逸、损坏 JSON、cache/fingerprint schema、runner/tooling hash 和 repo identity；后续只能继续加固，不能放松。 |
| 防提交保护 | `evidence/QualityGate/long_gate/`、`evidence/QualityGate/collect_nodeids.json`、`evidence/QualityGate/current_full_test_debt.json`、`evidence/QualityGate/full_test_debt_summary.json`、`evidence/QualityGate/full_test_debt_node_cache.json`、`evidence/QualityGate/startup_runtime_regressions.json`、`evidence/QualityGate/required_regressions.json`、`evidence/QualityGate/architecture_scan_cache.json`、`evidence/QualityGate/ruff_check_full.json`、`evidence/QualityGate/pyright_gate_full.json`、`evidence/QualityGate/pyright_tools_full.json`、`evidence/QualityGate/debt_ledger_sync.json` 和 `evidence/Conformance/quickref_vs_routes.md` 已被 `.gitignore` 或本地 hook 保护，运行产物不能混入提交。 |
| CI 缓存持久化 | `.github/workflows/quality.yml` 使用 pinned `actions/cache/restore` / `actions/cache/save`；restore 在完整门禁前，save 只在完整门禁成功后执行，fork PR 不 save。缓存只覆盖已忽略的 long gate 运行产物，不包含已跟踪的 `evidence/Conformance/quickref_vs_routes.md`。 |

目前只是候选，不能说已经启用成功复用：

- `architecture_fitness`

NEXT-1 已完成并可以继续沿用：

- 统一 `summary.json` / `summary.md`。
- 开头完整决策表和结束统一汇总。
- 失败时统一打印 FAILED entry、copyable command、pytest nodeid、receipt、stdout/stderr tail。

NEXT-2 已完成并可以继续沿用：

- 自定义 success cache 目录，但目录必须留在 `evidence/QualityGate/long_gate/` 本身或它的子目录下。
- 可强制指定 enabled entry 重跑，也可强制所有 enabled entry 重跑。
- force 只影响 success cache 复用决策，不改变真实 command plan，也不启用 planned entry。

## 2. 总体原则

后续每打开一个 entry 的复用，都必须同时满足这些原则：

| 原则 | 大白话说明 |
|---|---|
| 不改命令身份 | 命令必须来自真实 `build_quality_gate_command_plan()`，不能在缓存代码里手写 required/startup 清单。 |
| 证据完整才复用 | success cache、receipt、stdout/stderr log、输出文件、hash 任何一个不完整，都重新执行。 |
| explain 不是 proof | explain 只展示“现在会怎么决定”，不执行命令，不生成正式证明。 |
| dirty worktree 保守 | 脏工作区、失败续跑、输出不完整时，不写新的 success cache。 |
| 先整项，后增量 | 复杂 entry 先做“整项成功复用”，确认安全后再做 nodeid 或文件级增量。 |
| 默认谨慎 | 本地可以显式启用，CI 默认是否启用要单独评估，不能一上来默认全开。 |
| 可回滚 | 任一 entry 出问题时，能通过移出 enabled 列表或 `--no-long-gate-cache` 立即回到全量执行。 |

## 3. 模块拆分（概设）

```text
质量门禁长耗时缓存
├── 长耗时清单模块：从真实 command plan 识别哪些命令可复用
├── 输入指纹模块：把命令、文件、配置、依赖、环境变成稳定 hash
├── 成功缓存模块：读写上次成功结果并判断复用还是重跑
├── summary 模块：把决策、执行、复用、失败和日志位置写成统一报告
├── CLI 控制模块：cache dir、force rerun、explain、禁用缓存等入口
├── 门禁接入模块：把复用决策接入 run_quality_gate.py 的命令循环
├── 专项缓存模块：collect-only、full-test-debt、回归组、架构体检、台账、quickref、ruff/pyright
└── 测试和文档模块：合同测试、双跑验证、README、CodeStable 状态回写
```

## 4. 模块间接口契约 / 共享协议（架构层详设）

这一节是后续 feature-design 的硬约束。后续实现如果发现这些结构不够用，要先回到本 roadmap 更新，不要在单个 feature 里偷偷改另一套口径。

### 4.1 Manifest 和启用状态

Manifest 必须继续从 `tools.quality_gate_shared.build_quality_gate_command_plan()` 生成。entry 可以被识别为 long candidate，但只有进入 enabled 列表后才允许 success cache 复用。

当前已经 enabled：

```text
pytest_collect_all
full_test_debt
ruff_check_full
pyright_gate_full
pyright_tools_full
required_regressions
debt_ledger_sync
startup_runtime_regressions
quickref_vs_routes
```

后续 planned：

```text
architecture_fitness
```

Hash 口径必须保持一致：

- `quality_gate_plan_hash`、`command_hash`、`paths_hash`、`content_hash`、`nodeid_hash` 和 `generated_from_stdout_sha256` 使用裸 64 位十六进制字符串。
- `fingerprint.hash` / `current_fingerprint_hash` 这类展示用总指纹带 `sha256:` 前缀。

### 4.1.1 CI cache persistence

GitHub Actions 里的缓存只做“把上次成功留下的可复用运行产物带回来”，不改变门禁命令，也不降低证明要求。

- restore 步骤必须在 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 之前。
- save 步骤只能在完整门禁成功之后执行。
- fork pull request 不允许 save，避免把外部 fork 的运行产物写回主仓库缓存。
- 缓存路径只允许放已被忽略、long gate 复用确实需要的 `evidence/QualityGate/` 产物：`long_gate/`、`collect_nodeids.json`、full-test-debt/current/summary/node cache、architecture scan file cache、startup/required/debt ledger/static proof JSON。
- 不缓存已跟踪的 `evidence/Conformance/quickref_vs_routes.md`；它来自仓库 checkout，不能被 Actions cache 覆盖。
- CI 里看到 actions/cache 的 cache hit，只代表旧运行产物被恢复到工作区；最终 proof 仍然只看完整门禁命令是否通过，以及命令结束后工作区是否仍干净。

### 4.2 统一 CacheDecision

`decide_reuse()` 输出必须能同时服务 runner、summary 和 explain。

```json
{
  "entry_id": "pytest_collect_all",
  "decision": "reuse | run | planned_only | disabled",
  "reuse_allowed": true,
  "reason": "previous successful fingerprint matched",
  "invalidated_by": [],
  "previous_completed_at": "2026-05-12T00:00:00",
  "previous_result_path": "evidence/QualityGate/long_gate/results/pytest_collect_all.success.json",
  "current_fingerprint_hash": "sha256:..."
}
```

统一拒绝复用的情况：

- 上次不是 passed。
- 上次 returncode 非 0。
- timeout。
- interrupted。
- partial_write。
- JSON 损坏。
- 必填字段缺失。
- stdout/stderr log 缺失。
- stdout/stderr log hash 不一致。
- output file 缺失。
- output file hash 不一致。
- `entry_id` 不匹配。
- `command_hash` 不匹配。
- cache schema 版本不匹配。
- fingerprint schema 版本不匹配。
- fingerprint hash 自身不一致。
- success cache、log、output 路径逃出 repo root。
- symlink 指向 repo 外。

### 4.3 Summary 输出协议

后续新增 `tools/long_gate_summary.py`，正式运行结束后写：

```text
evidence/QualityGate/long_gate/summary.json
evidence/QualityGate/long_gate/summary.md
```

`summary.json` 顶层结构：

```json
{
  "schema_version": 1,
  "run_id": "...",
  "generated_at": "...",
  "repo_root": "...",
  "head_sha": "...",
  "worktree_clean": true,
  "cache_enabled": true,
  "cache_dir": "evidence/QualityGate/long_gate",
  "mode": "run | explain",
  "counts": {
    "executed": 0,
    "reused": 0,
    "failed": 0,
    "planned_only": 0,
    "disabled": 0
  },
  "entries": [],
  "failure": null
}
```

失败时 `failure` 结构：

```json
{
  "entry_id": "...",
  "display": "...",
  "copyable_command": "python -m pytest -q ...",
  "copyable_nodeids": ["tests/x.py::test_y"],
  "receipt_path": "...",
  "stdout_tail": "...",
  "stderr_tail": "..."
}
```

约束：

- 正式运行无论成功失败，都尽量写 summary。
- explain 第一版只打印，不写 summary；后续如果要写，也必须叫 `summary.explain.json`，避免被误当 proof。
- summary 写入失败时，不允许写新的 success cache。
- 中断时如果能进入 finally，就记录 `partial_write: true`，但这种 summary 不能作为 success cache 证据。

### 4.4 CLI 参数优先级

这些参数已经落地：

```text
--long-gate-cache-dir PATH
--long-gate-force-rerun ENTRY_ID
--long-gate-force-rerun-all
```

优先级从高到低：

1. `--no-long-gate-cache`：不读、不写 long gate success cache。
2. 现有失败续跑逻辑优先于 long gate success cache。
3. `--long-gate-cache-explain`：只展示决策，不执行、不写 success cache。
4. `--long-gate-force-rerun-all`：所有已启用 success cache 的 entry 都强制 run，成功后可刷新 success cache。
5. `--long-gate-force-rerun ENTRY_ID`：指定已启用 success cache 的 entry 强制 run，成功后可刷新 success cache；如果指定的是 planned entry，只记录 force 被忽略，不启用缓存。
6. 正常 `decide_reuse()`。

自定义 cache dir 第一版安全规则：

- 默认仍是 `evidence/QualityGate/long_gate/`。
- PATH 可以是相对路径或绝对路径。
- 解析后必须在 repo root 内。
- 不能通过 symlink 指到 repo 外。
- 第一版必须位于 `evidence/QualityGate/long_gate/` 本身或它的子目录下面。
- 不满足就直接报错，不偷偷降级到默认目录。

### 4.5 专项输出文件协议

每个 entry 必须声明自己的 output file，并在 success cache 中保存 hash：

| entry | 输出文件 |
|---|---|
| `pytest_collect_all` | `evidence/QualityGate/collect_nodeids.json` |
| `full_test_debt` | `evidence/QualityGate/current_full_test_debt.json`、`evidence/QualityGate/full_test_debt_summary.json` |
| `startup_runtime_regressions` | `evidence/QualityGate/startup_runtime_regressions.json` |
| `required_regressions` | `evidence/QualityGate/required_regressions.json` |
| `architecture_fitness` | `evidence/QualityGate/architecture_scan_cache.json` |
| `ruff_check_full` | `evidence/QualityGate/ruff_check_full.json` |
| `pyright_gate_full` | `evidence/QualityGate/pyright_gate_full.json` |
| `pyright_tools_full` | `evidence/QualityGate/pyright_tools_full.json` |
| `debt_ledger_sync` | `evidence/QualityGate/debt_ledger_sync.json` |
| `quickref_vs_routes` | `evidence/Conformance/quickref_vs_routes.md` |

输出文件只要缺失或 hash 不一致，就必须重新执行。

## 5. 后续实施阶段

### NEXT-1：统一 long gate summary 输出

状态：done。对应 feature：`2026-05-13-long-gate-summary-output`。

目标：补齐完整决策表、`summary.json`、`summary.md` 和失败重跑提示。

需要修改：

- `scripts/run_quality_gate.py`
- `tools/long_gate_cache.py`
- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`

建议新增：

- `tools/long_gate_summary.py`
- `tests/test_long_gate_summary_output.py`
- `codestable/features/2026-05-13-long-gate-summary-output/`

输出：

- `evidence/QualityGate/long_gate/summary.json`
- `evidence/QualityGate/long_gate/summary.md`

测试重点：

- explain 模式打印完整决策表。
- explain 模式不执行命令、不写 success cache。
- 正式运行成功后写 summary。
- counts 包含 executed/reused/failed/planned_only/disabled。
- 每个 entry 都有 reason 和 invalidated_by。
- 失败时记录 FAILED entry、copyable command、pytest nodeid、receipt、stdout tail、stderr tail。
- summary 写入失败时不写 success cache。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_summary_output.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_collect_cache.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/long_gate_summary.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/quality_gate_shared.py tools/test_registry.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/long_gate_summary.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/quality_gate_shared.py tools/test_registry.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain
```

完成说明：已新增 summary 模块和 runner 接入；正式 `--long-gate-cache` 运行会写 `summary.json` / `summary.md`，explain 仍只打印不写 proof，summary 写入失败时不写新的 success cache。planned long entry 如果作为真实门禁命令失败，也会写入 failure 证据。该阶段完成时 enabled 范围为 `pytest_collect_all` 单项，其它 long entry 保持 planned；NEXT-4 后 `full_test_debt` 已单独启用。`tests/test_long_gate_summary_output.py` 已纳入正式 quality gate 必跑集合。

回滚方式：移除 summary 调用，保留已有 collect-only 缓存逻辑。

### NEXT-2：补齐 CLI 控制参数

状态：done。对应 feature：`2026-05-13-long-gate-cli-controls`。

目标：补齐 cache dir 和强制重跑控制。

需要修改：

- `scripts/run_quality_gate.py`
- `tools/long_gate_cache.py`
- `tools/long_gate_manifest.py`
- `tools/git_hook_checks.py`
- `.gitignore`
- `README.md`
- `开发文档/README.md`

建议新增：

- `tests/test_long_gate_cli_controls.py`
- `codestable/features/2026-05-13-long-gate-cli-controls/`

新增参数：

- `--long-gate-cache-dir PATH`
- `--long-gate-force-rerun ENTRY_ID`
- `--long-gate-force-rerun-all`

测试重点：

- 自定义 cache dir 命中。
- 自定义 cache dir 不读取默认目录。
- repo 外目录被拒绝。
- symlink 到 repo 外被拒绝。
- force 单个 entry 后不复用。
- force all 后全部不复用。
- `--no-long-gate-cache` 下不读不写 success cache。
- 不存在 ENTRY_ID 报错。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cli_controls.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/long_gate_cache.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_summary.py tools/test_registry.py tests/test_long_gate_cli_controls.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/long_gate_cache.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_summary.py tools/test_registry.py tests/test_long_gate_cli_controls.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain --long-gate-cache-dir evidence/QualityGate/long_gate/manual --long-gate-force-rerun pytest_collect_all
```

完成说明：已新增 cache-dir 和 force CLI 控制；自定义目录必须留在默认 long gate 目录树内，非法路径会直接失败；读取旧 success cache 时会确认日志仍属于当前 cache dir，仓库根路径走 symlink 时也会写成规范的仓库内相对路径；force entry / force all 只让 enabled entry 放弃旧 success cache 并真实执行，成功后仍按原有干净工作区规则刷新 success cache。planned entry 即使被显式 force，也只记录为 planned_only，不会写 success cache。`tests/test_long_gate_cli_controls.py` 已纳入正式 quality gate 必跑集合。

回滚方式：保留参数解析，但临时禁用自定义目录，继续使用默认目录。

### NEXT-3：共用缓存安全和证据链加固

状态：done。对应 feature：`2026-05-13-long-gate-cache-safety-hardening`。

目标：把 schema、版本、路径、symlink、runner hash 等共用安全规则集中化。

需要修改：

- `tools/long_gate_cache.py`
- `tools/long_gate_fingerprint.py`
- `tools/long_gate_manifest.py`
- `scripts/run_quality_gate.py`
- `tests/test_long_gate_cache.py`

建议新增：

- `tools/long_gate_paths.py`，集中处理 repo 内路径、symlink、rel/abs 转换。
- `tools/long_gate_schema.py`，集中放 cache/fingerprint/summary schema version。

新增 success cache 字段建议：

- `cache_schema_version`
- `fingerprint_schema_version`
- `runner_version_hash`
- `tooling_version_hash`
- `cache_dir`
- `repo_root_realpath`
- `git_common_dir_realpath`

测试重点：

- cache schema 变化全失效。
- fingerprint schema 变化全失效。
- runner hash 变化失效。
- stdout/stderr log 缺失或 hash mismatch 失效。
- output file 缺失或 hash mismatch 失效。
- top-level JSON 不是 object 失效。
- symlink 指 repo 外不读取目标内容。
- absolute path 在 repo 内可规范化，repo 外报错。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py
```

完成说明：已新增 `tools/long_gate_paths.py` 和 `tools/long_gate_schema.py`；success cache 现在写入并校验 cache schema、fingerprint schema、runner hash、tooling hash、cache dir、repo root realpath 和 git common dir realpath。损坏 JSON、缺字段、bool 或坏字符串冒充数字、坏 `duration_s`、坏 fingerprint 结构、repo 外普通路径、repo 外 glob、repo 外 symlink、runner/tooling 自身的 repo 外 symlink、repo identity 不一致、runner/tooling 变化、日志/输出证据不完整都会稳定 `decision=run`，不会崩溃或误复用，也不会读取仓库外目标内容。该阶段完成时 enabled 范围未改变，为 `pytest_collect_all` 单项；NEXT-4 后 `full_test_debt` 已单独启用。planned entry 仍真实执行但不会写 success cache。

回滚方式：不要放宽安全规则；若本加固本身出问题，回退本 feature 的 schema/path/hash/repo identity 改动即可。NEXT-3 没有启用新的 entry，不存在把新增 entry 移回 planned 的动作。

### NEXT-4：full-test-debt 整项成功复用

目标：为 `python tools/check_full_test_debt.py` 做整项成功复用，不做 nodeid 增量。

需要修改：

- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`
- `tools/long_gate_cache.py`
- `scripts/run_quality_gate.py`
- `tools/check_full_test_debt.py`，只在确实需要补输出时改。
- `tools/collect_full_test_debt.py`，只在确实需要补输出时改。

建议新增：

- `tests/test_long_gate_full_test_debt_cache.py`
- `codestable/features/2026-05-13-full-test-debt-success-cache/`

输入范围：

- `tests/**/*.py`
- `tests/**/conftest.py`
- `conftest.py`
- `core/**/*.py`
- `web/**/*.py`
- `data/**/*.py`
- `plugins/**/*.py`
- `app.py`
- `app_new_ui.py`
- `config.py`
- `schema.sql`
- `开发文档/技术债务治理台账.md`
- `tools/check_full_test_debt.py`
- `tools/collect_full_test_debt.py`
- `tools/test_debt_registry.py`
- `tools/quality_gate_shared.py`
- `tools/quality_gate_support.py`
- `scripts/run_quality_gate.py`
- pytest 配置和依赖文件。
- `evidence/QualityGate/collect_nodeids.json` 的 `nodeid_hash`。

输出：

- `evidence/QualityGate/current_full_test_debt.json`
- `evidence/QualityGate/full_test_debt_summary.json`

复用条件：

- 上次 success cache status 是 passed。
- command hash 一致。
- fingerprint hash 一致。
- collect nodeid hash 一致。
- 债务台账 hash 一致。
- 两个输出文件都存在且 hash 匹配。
- stdout/stderr log 存在且 hash 匹配。
- 无 timeout/interrupted/partial_write。

失效条件：

- tests/core/web/data/plugins/app/config/schema 任一输入变化。
- templates/static/templates_excel/docs/audit/evidence/assets/installer/.limcode/codestable tools 等完整 pytest 会读取的仓库资产变化。
- pytest 配置变化。
- 依赖文件变化。
- collector/checker 脚本变化。
- collect nodeid 缺失或 `nodeid_hash` 变化。
- 债务台账变化。
- 输出文件缺失或 hash 不一致。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_full_test_debt_cache.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain
```

回滚方式：从 enabled 列表移除 `ENTRY_FULL_TEST_DEBT`。

状态：done。对应 feature：`2026-05-13-full-test-debt-success-cache`。

完成说明：已只把 `full_test_debt` 加入 enabled。该阶段完成当时，enabled 范围是 `pytest_collect_all` + `full_test_debt`；startup、required、ruff、pyright、architecture、debt ledger、quickref 在当时都尚未启用 success cache。`full_test_debt` 成功缓存会绑定完整输入指纹、`collect_nodeids.json` 的结构化 proof、两个输出文件、stdout/stderr 日志、repo identity、runner/tooling hash 和 NEXT-3 schema 安全规则。`collect_nodeids.json` 缺失、损坏、schema/status/nodeids/count/hash/by_file 不一致、nodeid hash 变化、输出文件缺失或 hash 不一致、日志缺失或非 UTF-8、timeout/interrupted/partial_write 都会重跑。runner 在同一轮 collect 刷新后会重新核对 `full_test_debt` 决策；collect 修好后可安全复用，collect hash 变化会整项重跑。没有实现 nodeid 级增量，也没有新增 `full_test_debt_node_cache.json`。

### NEXT-5：full-test-debt nodeid 级增量复用

目标：在整项成功复用稳定后，只在安全场景下支持部分测试文件变化时重跑相关 nodeid。

需要修改：

- `tools/check_full_test_debt.py`
- `tools/collect_full_test_debt.py`
- `tools/long_gate_collect.py`
- `scripts/run_quality_gate.py`
- `tools/long_gate_manifest.py`

建议新增：

- `tools/long_gate_full_test_debt.py`
- 继续扩展 `tests/test_long_gate_full_test_debt_cache.py`
- `codestable/features/2026-05-13-full-test-debt-nodeid-cache/`

输出：

- `evidence/QualityGate/full_test_debt_node_cache.json`

第一版策略：

- 只有测试文件变化时，才尝试按 `collect_nodeids.json` 的 `nodeids_by_file` 找相关 nodeid。
- 源码变化、conftest 变化、pytest 配置变化，整体失效。
- 只改债务台账，不重跑 pytest，只重新做台账校验和 summary。
- 映射不到 nodeid 时，整体重跑。

测试重点：

- 只改一个测试文件时只选择该文件对应 nodeid。
- 源码变化时整体失效。
- 只改台账时不重跑 pytest，只重做台账校验。
- node cache JSON 损坏时整体重跑。

状态：done。对应 feature：`2026-05-13-full-test-debt-nodeid-cache`。

完成说明：已新增 `evidence/QualityGate/full_test_debt_node_cache.json`，它只作为 `full_test_debt` 内部辅助证据，不是新的 long gate entry，也不会提交进仓库。runner 的顺序保持为：先判断 NEXT-4 整项 success cache 是否可复用；如果整项不能复用，再判断是否只有普通 `tests/**/*.py` 文件变化且 `collect_nodeids.json.nodeids_by_file` 能映射到 nodeid；能映射时只重跑相关 nodeid，把新报告合并回完整 `current_full_test_debt.json`，再用原有台账规则重算 `full_test_debt_summary.json`。如果只改 `开发文档/技术债务治理台账.md`，则不跑 pytest，只读取可信旧 current payload，用当前台账重算 summary。

安全边界：源码、`conftest.py`、pytest 配置、依赖、collector/checker/runner/schema/cache/fingerprint/manifest/summary/registry 工具、模板、静态资源、Excel 模板、安装脚本、`.limcode` 旧资产、CodeStable 文档或 `collect_nodeids.json` 损坏都会整体重跑。测试文件如果被其它测试文件静态 import、`importlib.import_module()` 动态 import、`__import__()` 动态 import，或遇到无法安全解析的动态导入，也会整体重跑。node cache JSON 损坏、schema/hash 不一致、日志缺失或 hash 不一致、旧 success cache 未声明 node cache、测试文件 hash 在非本次改动文件上不一致、current payload 与 collect nodeids 不一致，也会整体重跑。增量 pytest 失败、collector 输出不合法或合并后台账校验失败，会直接失败，不能复用旧成功掩盖。

执行模式：receipt/summary 现在能区分 `reused_success_cache`、`executed`、`nodeid_incremental`、`ledger_only`。`--long-gate-force-rerun full_test_debt`、`--long-gate-force-rerun-all`、`--no-long-gate-cache` 都不会走 nodeid 增量；`--long-gate-cache-explain` 只打印决策，不写 proof。

回滚方式：禁用 `scripts/run_quality_gate.py` 中的 `try_run_special_full_test_debt_mode` 分支，保留 NEXT-4 整项 success cache 即可。

### NEXT-6：startup runtime regressions 整组复用

状态：done。对应 feature：`2026-05-13-startup-runtime-regression-cache`。

完成说明：已为 `startup_runtime_regressions` 增加整组成功复用。命令仍从真实 `build_quality_gate_command_plan()` 动态生成，再由 manifest 根据 pytest args 识别；缓存逻辑没有复制 startup 测试清单。NEXT-6 完成时，enabled long gate entry 只从 `pytest_collect_all`、`full_test_debt` 扩展为 `pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions`；NEXT-7 已在后续完成，当前 required 状态见下一节。

安全边界：startup 指纹覆盖真实 startup 测试文件、`web/bootstrap/**/*.py`、`app.py`、`app_new_ui.py`、`config.py`、`schema.sql`、模板、静态资源、插件和启动相关源码、pytest 配置、依赖文件、runner/cache/schema/fingerprint/manifest/test registry 工具，以及 `APS_ENV`、`APS_DB_PATH`、`APS_LOG_DIR`、`APS_BACKUP_DIR`、`APS_EXCEL_TEMPLATE_DIR`、`APS_CHROME_PATH`、`PYTHONPATH`、`PYTHONUTF8`、`PYTHONIOENCODING`、Python/pytest/platform 信息。普通无关 markdown 不进入 startup 指纹。

输出：startup 成功执行后写 `evidence/QualityGate/startup_runtime_regressions.json`。proof 记录 schema、entry、动态 command plan hash、命令序号、display、args、command hash、fingerprint hash、returncode、pytest exit code、测试数量、HEAD、run id，以及长期 success cache stdout/stderr 日志路径和 hash。通用 success cache 会再次记录并校验 proof 文件 hash 和 stdout/stderr 长期日志 hash；proof 缺失、JSON 损坏、schema 不匹配、日志缺失或 hash 不一致、输入/环境变化都会整组重跑。

执行模式：`--long-gate-cache-explain` 只打印决策，不写 proof；`--no-long-gate-cache` 不读写 startup cache；`--long-gate-force-rerun startup_runtime_regressions` 和 `--long-gate-force-rerun-all` 会让 startup 整组重跑。startup 第一版不做 nodeid 级增量。

回滚方式：把 `ENTRY_STARTUP_RUNTIME_REGRESSIONS` 从 enabled 列表移回 planned，删除 startup output 绑定和 proof 写入；NEXT-5 的 `full_test_debt` 整项复用、nodeid 增量和台账-only 路径可以保留。

### NEXT-7：required regressions 整组复用

状态：done。对应 feature：`2026-05-13-required-regression-cache`。

完成说明：已为 `required_regressions` 增加整组成功复用。命令仍从真实 `build_quality_gate_command_plan()` 动态生成，再由 manifest 根据 pytest args 识别；缓存 proof 和 required target 都从当前 entry 的 `args[4:]` 派生，不在缓存逻辑里复制 `QUALITY_GATE_REQUIRED_TESTS`。该阶段完成当时，enabled long gate entry 只从 `pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions` 扩展为 `pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions`、`required_regressions`；NEXT-8 以及 ruff、pyright、architecture、debt ledger、quickref 在当时都尚未启用 success cache。

需要修改：

- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`
- `tools/quality_gate_shared.py`
- `tools/quality_gate_support.py`
- `scripts/run_quality_gate.py`
- `.gitignore`
- `tools/git_hook_checks.py`
- `tests/test_long_gate_manifest.py`
- `tests/test_long_gate_startup_regression_cache.py`
- `tests/test_run_quality_gate.py`
- `tests/test_git_hook_checks.py`

建议新增：

- `tests/test_long_gate_required_regression_cache.py`
- `codestable/features/2026-05-13-required-regression-cache/`

安全边界：

- required test target 来自 entry args，不复制 registry 清单。
- 指纹覆盖 required 测试文件、`tests/conftest.py`、required 会调用的门禁工具、pytest 配置、依赖文件、runner/cache/schema/fingerprint/manifest/test registry 工具。
- 指纹覆盖被测源码和资源：`core/**/*.py`、`web/**/*.py`、`data/**/*.py`、`plugins/**/*.py`、`app.py`、`app_new_ui.py`、`config.py`、`schema.sql`、模板、静态资源、Excel 模板。
- 指纹覆盖 required 测试真实读取的文档和旧资产：说明书相关 docs、static docs、evidence/audit README、`.limcode/skills/aps-full-selftest/scripts/run_full_selftest.py`、`.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`、`开发文档/开发文档.md`、`开发文档/阶段留痕与验收记录.md`、`开发文档/技术债务治理台账.md`。
- 不把 `docs/**/*.md`、`audit/**/*.md`、`开发文档/**/*.md` 这种宽泛普通 markdown 全部纳入 required 指纹，避免无关说明文件误伤 required。
- 指纹覆盖 Python executable realpath、Python version、pytest version、pytest plugin versions、platform、`PYTHONPATH`、`PYTHONUTF8`、`PYTHONIOENCODING`、`PYTEST_ADDOPTS`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD`、`PYTEST_PLUGINS`，以及会影响 APS/浏览器 smoke 的 `APS_ENV`、`APS_DB_PATH`、`APS_LOG_DIR`、`APS_BACKUP_DIR`、`APS_EXCEL_TEMPLATE_DIR`、`APS_CHROME_PATH`、Chrome/Node 解析结果。

输出：

- `evidence/QualityGate/required_regressions.json`

proof 字段：required 成功执行后写 `evidence/QualityGate/required_regressions.json`。proof 记录 schema、status、entry、generated_at、HEAD、run id、动态 command plan hash、命令序号、display、args、command hash、capture/output 策略、required target 数量和路径、target hash、fingerprint schema/hash、returncode、pytest exit code、execution mode、duration、长期 success cache stdout/stderr 日志路径和 hash、timed_out、interrupted、partial_write。通用 success cache 会再次记录并校验这个 proof 文件 hash 和 stdout/stderr 长期日志 hash；proof 缺失、JSON 损坏、schema 不匹配、日志缺失或 hash 不一致、输入/环境变化都会整组重跑。

执行模式：`--long-gate-cache-explain` 只打印决策，不写 proof；`--no-long-gate-cache` 不读写 required cache；`--long-gate-force-rerun required_regressions` 和 `--long-gate-force-rerun-all` 会让 required 整组重跑。required 第一版不做 nodeid 级增量。

测试重点已落地：

- required args 来自真实 command plan。
- required 分类不依赖 command plan 里的位置。
- required test file 变化失效。
- 被测源码变化失效。
- pytest 配置或依赖变化失效。
- required 真实读取的模板、静态资源、Excel 模板、文档、`.limcode` 脚本和门禁工具变化失效。
- Python/pytest/platform、pytest 环境变量、APS/浏览器相关环境变化失效。
- 输出 JSON 或 log 缺失时不复用。
- 无关普通 markdown 变化不误伤 required。
- explain/no-cache/force 行为符合预期。
- collect、full-test-debt、startup 既有复用能力不被 required 失效拖坏。

验证结果：

- `tests/test_long_gate_required_regression_cache.py` 通过。
- long gate 相关回归组合通过。
- 当时的 `scripts/run_quality_gate.py --long-gate-cache-explain` 显示 enabled 只新增 `required_regressions`，NEXT-8 和后续仍 planned。
- ruff、pyright、本 roadmap items/checklist YAML、`git diff --check` 通过。
- 最终 clean-worktree proof 必须在本 feature 提交完成后运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 才算绑定最终 HEAD；如果提交后又 amend，必须重新跑。

回滚方式：把 `ENTRY_REQUIRED_REGRESSIONS` 从 enabled 列表移回 planned，删除 required output 绑定和 proof 写入；NEXT-1 到 NEXT-6 的 collect、full-test-debt、startup 复用能力可以保留。

### NEXT-7.5：pre-push 接入已有 long gate cache

状态：done。对应 feature：`2026-05-13-pre-push-long-gate-cache`。

历史目标：让本地 pre-push hook 调用 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。完成当时，pre-push 仍是正式质量门禁，仍要求干净工作区；只是允许已经 enabled、证据可信的 long gate entry 复用上次成功结果。

当前口径：这个目标已经被 2026-05-14 的日常快门禁调整覆盖。现在 pre-push 默认调用 `scripts/run_daily_quality_gate.py`，只挡暂存区运行产物、pytest 收集失败、ruff 失败和一组重点 pytest 失败；它不声明 full-test-debt proof，也不声明 clean-worktree proof。最终完整门禁和 CI 仍运行 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，并且只允许已经 enabled 且证据可信的 entry 复用。

明确不做：

- 不启用 NEXT-8 到 NEXT-13。
- 不做 hook 级整体缓存。
- 不把日常快门禁当作最终 clean proof。
- 不加 force/explain。
- 不降低 CI 或最终 clean gate 要求。

验证重点：

- 历史验收证明当时 hook command 同时包含 `--require-clean-worktree` 和 `--long-gate-cache`。
- 当前 pre-push 真实入口是 `tools/git_hook_checks.py run-quality-gate`，它调用 `scripts/run_daily_quality_gate.py`。
- 手动最终完整门禁入口是 `tools/git_hook_checks.py run-final-quality-gate`，它调用 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- planned entry 仍 planned。
- README 和开发文档 long gate enabled 口径同步。

实际验证：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_git_hook_checks.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cli_controls.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_required_regression_cache.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/git_hook_checks.py tests/test_git_hook_checks.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/git_hook_checks.py tests/test_git_hook_checks.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-checklist.yaml`
- `git diff --check`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`

最终 clean-worktree proof 在 NEXT-7.5 收尾阶段运行通过；后续提交已经改变 pre-push 入口，因此这条 proof 只代表当时 HEAD，不代表当前 HEAD 的最终 clean proof。当前 HEAD 若要声明完整 clean-worktree proof，仍必须重新运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 或等价的 `tools/git_hook_checks.py run-final-quality-gate`。

### NEXT-8：architecture fitness 文件级扫描缓存

状态：done。已完成 `2026-05-15-architecture-scan-file-cache`。

目标：让 architecture fitness 的 AST 扫描按文件复用；跨文件规则仍每次重新聚合。

需要修改：

- `tools/quality_gate_scan.py`
- `tests/test_architecture_fitness.py`
- `scripts/run_quality_gate.py`
- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`

实际新增：

- `tools/architecture_scan_cache.py`
- `tests/test_architecture_scan_cache.py`
- `codestable/features/2026-05-15-architecture-scan-file-cache/`

需要拆出的函数：

```python
scan_single_file_architecture(rel_path)
scan_files_with_cache(paths, rule_context)
aggregate_architecture_scan(file_results)
```

实际落地名：

- `scan_single_file_architecture_fact(rel_path, context=None, fact_kinds=None)`
- `scan_files_with_cache(paths, cache_path=None, force=False, context=None, fact_kinds=None)`
- `aggregate_architecture_scan(file_facts, mode="architecture", include_all_complexity=False)`

输出：

- `evidence/QualityGate/architecture_scan_cache.json`

复用条件：

- 文件 sha 没变。
- scanner hash 没变。
- scan schema version 没变。
- Python version 没变。
- 多文件规则每次重新聚合。

失效条件：

- scanner 代码变化。
- scan schema 变化。
- 文件 sha 变化。
- 文件新增/删除。
- cache JSON 损坏。
- 单文件 cache 缺字段。

完成边界：

- 只缓存单文件 AST/source 派生事实，不缓存最终 pass/fail。
- `architecture_fitness` 仍是 planned long gate success cache entry，未加入 enabled 列表。
- ledger allowlist、new/stale/mismatch、accepted risks、fixed 条目拒绝仍每次重新 aggregate 和比对。
- `generated_at` 只作记录；缺失会判坏重扫，值变化不参与复用判断。
- `evidence/QualityGate/architecture_scan_cache.json` 是运行产物，已被 `.gitignore` 和本地 hook 拦截。
- 本次 `scripts/run_quality_gate.py --long-gate-cache-explain` 只用于确认 planned/enabled 决策，不是 clean proof。

回滚方式：architecture fitness 继续全量扫描，不启用 file cache。

### NEXT-9：快速静态预检

状态：done。对应 feature：`2026-05-15-fast-static-precheck`。

目标：新增快速预检，只检查本次改动的 Python 文件。它是提前提醒，不替代正式全量门禁。

需要修改：

- `scripts/run_quality_gate.py`
- `tools/git_hook_checks.py`，如需接入 hook。
- `README.md`
- `开发文档/README.md`

建议新增：

- `tools/fast_static_precheck.py`
- `tests/test_fast_static_precheck.py`
- `codestable/features/2026-05-15-fast-static-precheck/`

命令形式建议两个都支持：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.fast_static_precheck
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck
```

测试重点：

- staged/unstaged/untracked Python 文件会被纳入。
- 非 Python 改动不触发 ruff。
- 删除的 Python 文件不传给 ruff。
- 文件名带空格时命令参数正确。
- 局部 ruff 失败时 precheck 失败。
- pyright 默认跳过，并输出“不是 pyright_gate_full / pyright_tools_full”。
- 输出明确“不能替代正式全量门禁”。
- 不写 long gate success cache。

回滚方式：移除 runner 参数，必要时保留独立脚本。

完成说明：已新增 `tools/fast_static_precheck.py`，默认收集 staged、unstaged、untracked 的 `.py` 文件，跳过非 Python、删除、不存在、目录、运行产物和 ruff exclude 类路径；路径使用 NUL 分隔和 list args，不拼 shell 字符串。`scripts/run_quality_gate.py --fast-precheck` 会在完整 command plan 前早退，不写 manifest、receipt、summary 或 long gate success cache；`tools/git_hook_checks.py run-fast-static-precheck` 是独立手动入口，不改变 daily gate 和 final clean gate。pyright 默认跳过，并在输出中说明不是 `pyright_gate_full` / `pyright_tools_full`。本阶段不启用任何新的 long gate success cache entry。

### NEXT-10：ruff / pyright 正式全量缓存

状态：done，feature 目录为 `codestable/features/2026-05-15-static-formal-cache/`。

目标：为正式静态命令做 success cache。

目标命令：

- `python -m ruff check`
- `python -m pyright -p pyrightconfig.gate.json`
- `python -m pyright -p pyrightconfig.tools.json`

完成说明：已按阶段启用 `ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`。`pyright_tools_full` 原命令会读取 `pyrightconfig.json`，而该配置排除了 `scripts` 和 `tools`；2026-05-15 只读复验显示，单独对 `tools/long_gate_manifest.py` 运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright --verbose tools/long_gate_manifest.py` 时输出 `No source files found`，对完整 `QUALITY_GATE_TOOL_PATHS` 展开命令运行 `--verbose` 时只输出 `Found 2 source files`。因此不能缓存这个空覆盖结果。当前实现已新增 `pyrightconfig.tools.json`，正式命令改为 `python -m pyright -p pyrightconfig.tools.json`，runner 额外用 include 对账和 JSON 输出 `filesAnalyzed` 复查，避免空覆盖结果写入 success cache。

需要修改：

- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`
- `scripts/run_quality_gate.py`
- `tools/quality_gate_shared.py`，只在需要暴露 tool path hash 时改。
- `pyrightconfig.tools.json`

本阶段新增或复用：

- `codestable/features/2026-05-15-static-formal-cache/`
- `pyrightconfig.tools.json`
- `tests/test_long_gate_manifest.py`
- `tests/test_long_gate_cache.py`
- `tests/test_run_quality_gate.py`
- `tests/test_git_hook_checks.py`

输入范围：

- ruff：所有 Python 文件、ruff 配置、pre-commit 配置、依赖文件、ruff version、Python version。
- pyright gate：`pyrightconfig.gate.json`、gate 覆盖范围、依赖文件、pyright version、Python version、`PYTHONPATH`。
- pyright tools：用 `pyrightconfig.tools.json` 修真实覆盖问题；启用 cache 时绑定 `QUALITY_GATE_TOOL_PATHS` 列表 hash、对应文件内容、import closure helper、配置、依赖文件、pyright version、Python version。

输出：

- `evidence/QualityGate/ruff_check_full.json`
- `evidence/QualityGate/pyright_gate_full.json`
- `evidence/QualityGate/pyright_tools_full.json`

测试重点：

- 任意 Python 文件变化使 ruff full 失效。
- pyright config 变化使 pyright gate 失效。
- dependency 文件变化使 pyright/ruff 失效。
- `QUALITY_GATE_TOOL_PATHS` 变化使 pyright tools 失效。
- 工具版本变化使对应 cache 失效。

回滚方式：先保留快速预检，禁用正式静态缓存。

### NEXT-11：debt ledger sync 缓存

目标：为 `python scripts/sync_debt_ledger.py check` 做整项成功复用，并在 architecture scan cache 完成后复用同一套文件级扫描事实。

状态：已完成。NEXT-11 当时只新增启用 `debt_ledger_sync` success cache，`architecture_fitness` 和 `quickref_vs_routes` 在 NEXT-11 完成时都尚未启用 success cache；其中 `quickref_vs_routes` 已在后续 NEXT-12 启用。

本阶段已修改：

- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`
- `scripts/run_quality_gate.py`
- `tools/quality_gate_shared.py`
- `tools/quality_gate_support.py`
- `tools/git_hook_checks.py`
- `tools/test_registry.py`
- `.gitignore`

本阶段新增或复用：

- `tests/test_long_gate_debt_ledger_cache.py`
- `codestable/features/2026-05-15-debt-ledger-sync-cache/`

输入范围：

- `开发文档/技术债务治理台账.md`
- `scripts/sync_debt_ledger.py`
- `tools/quality_gate_ledger.py`
- `tools/quality_gate_operations.py`
- `tools/quality_gate_scan.py`
- `tools/test_debt_registry.py`
- `tools/check_full_test_debt.py`
- `tools/collect_full_test_debt.py`
- `core/**/*.py`
- `web/**/*.py`
- `data/**/*.py`
- `tests/**/*.py`
- `scripts/**/*.py`
- `tools/**/*.py`
- `codestable/roadmap/**/*.md`
- `codestable/roadmap/**/*.yaml`
- `codestable/features/**/*.md`
- `codestable/features/**/*.yaml`
- config / dependency / Python env / architecture scan metadata

输出：

- `evidence/QualityGate/debt_ledger_sync.json`

测试重点：

- 台账变化失效。
- sync 脚本、ledger、operations、scan 工具变化失效。
- core/web/data/tests 变化失效。
- 输出 JSON 或 log 缺失时不复用。
- 如果 architecture scan cache 参与，ledger allowlist 变化只重新聚合，不重扫 AST。

完成说明：已为 `debt_ledger_sync` 增加整项成功复用。命令仍来自真实 `build_quality_gate_command_plan()`，身份是 `python scripts/sync_debt_ledger.py check`。success cache 绑定台账、roadmap/feature、sync 脚本、ledger/operations/scan/architecture helper、源码、配置、依赖、Python/env、architecture scan metadata、声明输出 proof path 和 stdout/stderr long-gate 日志。`evidence/QualityGate/debt_ledger_sync.json` 是单条 entry 的 proof JSON，缺失或被篡改会重新执行；它被 `.gitignore`、`tools/git_hook_checks.py` 和 clean-worktree generated path 排除清单保护，不能混入提交。`architecture_scan_cache.json` 本身是 helper 运行产物，不作为 debt entry 的输入指纹，避免生成时间造成指纹抖动。`scripts/sync_debt_ledger.py check` 语义没有改成刷新台账或直接写 proof；proof 由 runner 在 long gate 路径里写。`--long-gate-cache-explain`、cache hit、`debt_ledger_sync.json` 都不是 clean-worktree final proof。本阶段未完成 clean-worktree full proof。

回滚方式：把 `ENTRY_DEBT_LEDGER_SYNC` 从 enabled 列表移回 planned；保留 proof path 和 artifact hygiene 也不会改变实际复用行为。

### NEXT-12：quickref vs routes 缓存

状态：done。对应 feature：`2026-05-16-quickref-vs-routes-cache`。

目标：为 `python tests/check_quickref_vs_routes.py` 做整项成功复用。

需要修改：

- `tools/long_gate_manifest.py`
- `tools/long_gate_fingerprint.py`
- `scripts/run_quality_gate.py`
- `tests/check_quickref_vs_routes.py`，只在确实需要规范输出时改。

建议新增：

- `tests/test_long_gate_quickref_cache.py`
- `codestable/features/2026-05-16-quickref-vs-routes-cache/`

输入范围：

- `tests/check_quickref_vs_routes.py`
- `开发文档/系统速查表.md`
- `app.py`
- `web/routes/**/*.py`
- `web/bootstrap/**/*.py`
- `templates/**/*.html`
- `static/**/*`
- `config.py`
- `schema.sql`
- dependency files。
- 导航入口相关文件。
- `APS_ENV`、`PYTHONPATH`、`PYTHONUTF8`、`PYTHONIOENCODING` 和脚本实际读取的其它环境变量。

输出：

- `evidence/Conformance/quickref_vs_routes.md`

测试重点：

- 系统速查表变化失效。
- route/bootstrap/template/static/app/config/schema/dependency 变化失效。
- 关键环境变量变化失效。
- `quickref_vs_routes.md` 缺失或 hash mismatch 时不复用。
- route 新增但速查表没变时必须执行。

回滚方式：把 `ENTRY_QUICKREF_VS_ROUTES` 从 enabled 列表移出，让它恢复为候选但不复用 success cache 的状态。

完成说明：已为 `quickref_vs_routes` 增加整项成功复用。命令仍来自真实 `build_quality_gate_command_plan()`，身份是 `python tests/check_quickref_vs_routes.py`。success cache 绑定系统速查表、app/bootstrap/routes/web 代码、模板、静态资源、配置、依赖、Python/env、声明输出 path、`evidence/Conformance/quickref_vs_routes.md` hash 和 stdout/stderr long-gate 日志。quickref stdout 已改为仓库相对路径，并在路由扫描期间静音 app 启动日志，避免本机路径、临时目录和时间戳进入稳定输出。`evidence/Conformance/quickref_vs_routes.md` 是运行产物，已被 `.gitignore`、`tools/git_hook_checks.py` 和 clean-worktree generated path 说明保护。本阶段没有启用 `architecture_fitness`，没有改变 daily/pre-push/CI final 语义，也未运行 clean-worktree final quality gate，不能把本次验证说成最终 clean proof。

### NEXT-13：文档、最终收口和干净证明

状态：done。对应 feature：`2026-05-16-long-gate-docs-final-proof`。

目标：把用户文档、开发文档、CodeStable 状态、最终验收命令统一收口。

需要修改：

- `README.md`
- `开发文档/README.md`
- 本 roadmap。
- 本阶段 feature 的 design / checklist / acceptance，以及必要的历史状态说明。

必须说明：

- explain 模式不是 proof。
- cache 命中不等于跳过安全校验。
- 当前哪些 entry 已启用，哪些只是候选。
- CI 默认启用要谨慎。
- 证据不完整时会重新执行。
- 运行产物不能提交。
- force rerun 参数的用法。
- 自定义 cache dir 的路径限制。
- 快速预检不能替代正式全量门禁。
- 失败时如何根据 summary 找 command、nodeid、receipt 和日志 tail。

最终验收：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_long_gate_full_test_debt_cache.py \
  tests/test_long_gate_startup_regression_cache.py \
  tests/test_long_gate_required_regression_cache.py \
  tests/test_architecture_scan_cache.py \
  tests/test_fast_static_precheck.py \
  tests/test_long_gate_manifest.py \
  tests/test_long_gate_cache.py \
  tests/test_run_quality_gate.py \
  tests/test_git_hook_checks.py \
  tests/test_long_gate_debt_ledger_cache.py \
  tests/test_long_gate_quickref_cache.py \
  tests/test_long_gate_summary_output.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_long_gate_cache.py \
  tests/test_long_gate_manifest.py \
  tests/test_run_quality_gate.py \
  tests/test_architecture_fitness.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

如果没有跑完整 clean-worktree full proof，提交说明必须明确写：

```text
未完成 clean-worktree full proof，不能宣称本 PR 已通过完整 clean-worktree quality gate。
```

完成说明：已统一 README、开发文档、roadmap、items 和 NEXT-13 acceptance 的 proof 口径；最终 clean proof 仍以本阶段提交后的 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 和 `git status --short` 为准。

## 6. 子 feature 清单

详细机器可读清单在 `quality-gate-long-cache-items.yaml`。这里保留人读版顺序：

1. `long-gate-manifest-probe`：done，已从真实 command plan 生成清单。
2. `long-gate-cache-core`：done，已建立输入指纹和 success cache 核心。
3. `collect-only-cache-output`：done，已生成 collect nodeid 输出。
4. `quality-gate-runner-collect-cache`：done，已接入 collect-only 成功复用。
5. `long-gate-summary-output`：done，已补统一 summary 和失败提示。
6. `long-gate-cli-controls`：done，已补 cache dir 和 force rerun 参数。
7. `long-gate-cache-safety-hardening`：done，已加固共用 schema、runner/tooling hash、repo identity、路径和损坏证据拒绝规则。
8. `full-test-debt-success-cache`：done，已完成 full-test-debt 整项复用。
9. `full-test-debt-nodeid-cache`：done，已完成 full-test-debt nodeid 增量和台账-only 路径。
10. `startup-runtime-regression-cache`：done，已完成 startup 整组复用。
11. `required-regression-cache`：done，已完成 required 整组复用。
12. `pre-push-long-gate-cache`：done，历史上曾让 pre-push 正式质量门禁接入已有 enabled long gate cache；当前 pre-push 已由后续日常快门禁替代，最终完整门禁仍可手动运行。
13. `architecture-scan-file-cache`：done，已完成 architecture 文件级扫描事实缓存；`architecture_fitness` 整项 success cache 仍未启用。
14. `fast-static-precheck`：done，已完成快速静态预检。
15. `static-formal-cache`：done，已完成 ruff/pyright 正式全量缓存；`pyright_tools_full` 已改用 `pyrightconfig.tools.json`，并用 include 对账 + `filesAnalyzed` 自检防止缓存只找到 2 个 source files 的结果。
16. `debt-ledger-sync-cache`：done，已完成 `debt_ledger_sync` 整项 success cache；manifest entry `debt_ledger_sync` 已 enabled，proof 写入 `evidence/QualityGate/debt_ledger_sync.json`。
17. `quickref-vs-routes-cache`：done，已完成 `quickref_vs_routes` 整项 success cache；manifest entry `quickref_vs_routes` 已 enabled，报告写入 `evidence/Conformance/quickref_vs_routes.md`。
18. `long-gate-docs-final-proof`：done，已完成文档、状态回写和最终干净证明。
19. `github-actions-long-gate-cache-persistence`：done，已完成 GitHub Actions long gate cache restore/save 持久化，fork PR 不保存缓存，CI 命令仍是 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。

## 7. 推荐提交颗粒度

不要把多个 entry 的启用混在一笔提交里。推荐每个 NEXT 阶段至少拆成“基础结构 / runner 接入 / 测试文档 / 最后启用”几个小提交。

关键边界：

- summary 不混入 full-test-debt。
- CLI 控制参数不混入新增 entry 启用。
- 共用安全加固不混入业务 entry 复用。
- full-test-debt 整项复用不混入 nodeid 增量。
- startup 和 required 拆开做。
- fast precheck 不混入 ruff/pyright formal cache。
- debt ledger sync 和 quickref 拆开做。
- 每个 entry 的 enabled 改动必须放在该 entry 测试和文档完成之后。

## 8. 测试计划总表

后续至少新增或扩展这些测试文件：

| 测试文件 | 覆盖重点 |
|---|---|
| `tests/test_long_gate_summary_output.py` | explain、summary.json、summary.md、失败输出、tail、counts、force reason、dirty 状态。 |
| `tests/test_long_gate_cli_controls.py` | cache dir、force rerun、force all、no cache、路径逃逸、planned entry 守护。 |
| `tests/test_long_gate_full_test_debt_cache.py` | full-test-debt 整项复用、输出文件、collect nodeid、台账、源码、collector、node cache。 |
| `tests/test_long_gate_startup_regression_cache.py` | startup 动态 args、环境变量、bootstrap/template/static/app/config/schema、输出文件。 |
| `tests/test_long_gate_required_regression_cache.py` | required 动态 args、测试文件、被测源码、模板、静态资源、Excel 模板、真实读取的文档和 `.limcode` 脚本、pytest 配置、依赖、环境变量、坏 proof、坏日志、force/no-cache/explain。 |
| `tests/test_architecture_scan_cache.py` | 单文件扫描复用、单文件变更、ledger allowlist、scanner hash、跨文件聚合。 |
| `tests/test_fast_static_precheck.py` | staged/unstaged/untracked Python 文件、无 Python 文件 skip、ruff 失败、pyright skip 文案、不能替代正式门禁。 |
| `tests/test_long_gate_manifest.py` / `tests/test_long_gate_cache.py` / `tests/test_run_quality_gate.py` / `tests/test_git_hook_checks.py` | ruff/pyright formal cache、工具版本、配置、依赖、`QUALITY_GATE_TOOL_PATHS`、static proof 和 artifact hygiene。 |
| `tests/test_long_gate_debt_ledger_cache.py` | 台账、sync 脚本、scanner、core/web/data/tests、共享 scan cache。 |
| `tests/test_long_gate_quickref_cache.py` | 速查表、路由、模板、静态资源、输出 md、环境变量。 |

## 9. 注意事项

1. required/startup 测试清单必须来自真实 `build_quality_gate_command_plan()`，不要在缓存代码里复制 `QUALITY_GATE_REQUIRED_TESTS` 或 startup 清单。
2. 不要提交运行产物，尤其是：
   - `evidence/QualityGate/long_gate/`
   - `evidence/QualityGate/collect_nodeids.json`
   - `evidence/QualityGate/*_regressions.json`
   - `evidence/QualityGate/*_cache.json`
   - `evidence/Conformance/quickref_vs_routes.md`
3. 不要默认所有慢命令都已经可缓存。每个 entry 只能在对应测试和文档完成后，从 planned 改成 enabled。
4. explain 模式不是 proof。它只是决策预览。
5. cache 命中不等于跳过安全校验。命中前必须重新校验 command、fingerprint、日志、输出文件、schema、路径。
6. 不要为了提高命中率加宽松兜底。证据不完整就重新执行。
7. symlink 策略继续保守。仓库外目标不读取内容，直接失效或拒绝。
8. 自定义 cache dir 只能在 repo root 内，并且最好限制在已被忽略的 evidence 子目录下。
9. CI 当前执行完整质量门禁时已经显式传入 `--long-gate-cache`；当前 enabled entry 是 `pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`required_regressions`、`debt_ledger_sync`、`startup_runtime_regressions`、`quickref_vs_routes`，planned entry 不会因此复用。后续任何新 entry 进入 enabled，都必须单独评估 CI 下复用证据是否可靠。
10. CI cache hit 不是 proof。它只是恢复旧运行产物，真正的 proof 仍然是 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 通过。
11. 每个 PR 的最终说明都要写清楚：本 PR 新启用了哪些 entry，哪些仍然只是候选。

## 10. 观察项

- 当前路线图是规划层，不改 `codestable/requirements/` 和 `codestable/architecture/`。真正落地后由 feature acceptance 再回写现状档案。
- 架构扫描文件级缓存会触碰 `tools/quality_gate_scan.py` 的内部结构，风险高于命令级缓存，应放到 collect-only/full-test-debt/回归组稳定之后。
- full-test-debt 的 nodeid 级增量缓存已经落地；后续如果继续细化依赖映射，仍要先证明映射可信，不能提前承诺精准增量。
- ruff / pyright 的 formal cache 影响面大，建议先做 fast precheck，再逐个启用正式全量缓存。

## 11. 变更日志

- 2026-05-12：按用户提供的细粒度方案新建 roadmap，只做规划落盘；已核对当前 HEAD、真实 command plan、现有 receipt / resume 入口和 CodeStable 目录约定。
- 2026-05-12：完成 `long-gate-manifest-probe`，新增只读 long gate manifest 探测工具、CLI 和测试，并把 PR-0 状态回写为 done。
- 2026-05-12：完成 `long-gate-cache-core`，新增输入指纹、success cache 读写和复用决策核心，并把 PR-1 状态回写为 done。
- 2026-05-12：完成 `collect-only-cache-output`，新增 collect nodeid 输出 payload、collect entry scope 和输入变化失效测试，并把 PR-2 状态回写为 done。
- 2026-05-12：完成 `quality-gate-runner-collect-cache`，把 collect-only success cache 接入 `scripts/run_quality_gate.py`，新增 CLI 开关、决策表、复用 receipt 字段、receipt 耗时字段和双跑合同测试，并把 PR-3 状态回写为 done。
- 2026-05-12：按对抗审核结果补强 PR-0 到 PR-3：long gate 工具纳入 `QUALITY_GATE_TOOL_PATHS` 和 gate source proof，指纹补 runtime facts 和 schema hash，缓存路径禁止逃出仓库，未知 pytest 命令不再按位置误分类，失败续跑 receipt 明确标 `resumed_success_prefix`，dirty 快速反馈不写 success cache。
- 2026-05-13：按用户提供的新后续实施计划更新 roadmap：把 summary、CLI 控制、安全加固、full-test-debt 整项和增量、startup、required、architecture、fast precheck、formal static、debt ledger、quickref、最终文档证明拆成更细的 NEXT 阶段；该规划时点 enabled 范围为 collect-only。
- 2026-05-13：完成 `long-gate-summary-output`，新增 `tools/long_gate_summary.py`，正式 long gate cache 运行写 `summary.json` / `summary.md`，失败时输出 copyable command/nodeid、receipt 和 stdout/stderr tail；planned long entry 真实失败时也写 failure 证据；summary 专项测试已纳入正式 quality gate 必跑集合；explain 仍只打印不写 proof，未启用任何新的 planned entry。
- 2026-05-13：完成 `long-gate-cli-controls`，新增 `--long-gate-cache-dir`、`--long-gate-force-rerun`、`--long-gate-force-rerun-all`；自定义 success cache 目录被限制在 `evidence/QualityGate/long_gate/` 下；force 只影响 enabled entry 的复用决策，不改变 command plan，不启用任何新的 planned entry。
- 2026-05-13：完成 `long-gate-cache-safety-hardening`，新增 `tools/long_gate_paths.py` 和 `tools/long_gate_schema.py`；success cache 显式记录并校验 cache/fingerprint schema、runner/tooling hash、cache dir、repo identity；坏 JSON、坏类型、坏 fingerprint 结构、repo 外输入路径、repo 外 symlink、日志/输出缺失、repo identity 不一致都会重新执行；该阶段完成时 enabled 范围为 `pytest_collect_all` 单项。
- 2026-05-13：完成 `full-test-debt-success-cache`，只把 `full_test_debt` 加入 enabled；输入指纹覆盖完整 pytest 会读取的测试、源码、模板、静态资源、Excel 模板、安装脚本、`.limcode` 旧资产、CodeStable 工具、文档、台账、collector/checker、pytest 配置、依赖和 `collect_nodeids.json` 结构化 proof；输出绑定 `current_full_test_debt.json` 和 `full_test_debt_summary.json`；NEXT-5 的 nodeid 级增量仍保持 planned。
- 2026-05-13：完成 `full-test-debt-nodeid-cache`，新增 `full_test_debt_node_cache.json` 和 `tools/long_gate_full_test_debt.py`；只有普通测试文件变化且 nodeid 映射可信时才走 nodeid 增量，只改台账时走 ledger-only；源码、conftest、pytest 配置、依赖、工具、模板、静态资源、Excel 模板、安装脚本或坏证据都会整体回退；完成时 enabled 范围为 `pytest_collect_all` 和 `full_test_debt`。
- 2026-05-13：完成 `startup-runtime-regression-cache`，只新增启用 `startup_runtime_regressions`；startup 命令从真实 command plan 动态定位，不复制测试清单；proof 写入 `evidence/QualityGate/startup_runtime_regressions.json`，绑定 command/fingerprint/returncode/测试数量/HEAD/长期日志路径和 hash；坏 proof、坏日志、输入或环境变化都会整组重跑；该阶段完成时 required 和 NEXT-7 之后条目仍保持 planned。
- 2026-05-13：完成 `required-regression-cache`，只新增启用 `required_regressions`；required 命令和 target 从真实 command plan entry 动态定位，不复制 `QUALITY_GATE_REQUIRED_TESTS`；proof 写入 `evidence/QualityGate/required_regressions.json`，绑定 command/fingerprint/returncode/target/HEAD/长期日志路径和 hash；坏 proof、坏日志、required 测试、被测源码、模板、静态资源、Excel 模板、真实读取的文档、`.limcode` 脚本、门禁工具、pytest 配置、依赖或关键环境变化都会整组重跑；NEXT-8 和后续条目仍保持 planned。
- 2026-05-13：完成 `pre-push-long-gate-cache`，只让本地 pre-push 正式质量门禁在保留 `--require-clean-worktree` 的同时传入 `--long-gate-cache`；不启用 NEXT-8 到 NEXT-13，不做 hook 级整体缓存，不做 pre-commit 快速化；收尾完整 clean-worktree quality gate 已通过。
- 2026-05-15：同步 2026-05-14 之后的实际口径：pre-push 当前默认运行 `scripts/run_daily_quality_gate.py`，只作为日常快门禁；最终完整门禁和 CI 仍运行 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。本次只是文档口径收口，不改变代码行为，不代表启用 NEXT-8 到 NEXT-13。
- 2026-05-15：完成 `architecture-scan-file-cache`。新增 architecture 单文件扫描事实缓存，缓存只保存单文件 fact，不保存 architecture fitness pass/fail，也不启用 `architecture_fitness.success.json`；坏 JSON、缺字段、未知 fact_kinds、明细缺字段、file sha、scanner/schema/Python/radon 变化都会重扫；最终判断仍每次 aggregate。`--long-gate-cache-explain` 已确认 `architecture_fitness` 仍 planned，但 explain 不是 clean proof。
- 2026-05-15：完成 `static-formal-cache`。已启用 `ruff_check_full`、`pyright_gate_full` 和 `pyright_tools_full` 的正式 success cache；三条 static entry 都绑定专属输入边界、配置、依赖、工具版本、Python 环境、声明输出 proof JSON 和 long-gate 日志；`pyright_tools_full` 原命令只找到 2 个 source files 的阻塞已通过 `pyrightconfig.tools.json`、include 对账和 `filesAnalyzed` 自检处理，不能把空覆盖结果缓存成成功。本次未运行 clean-worktree final quality gate，不能把本次验证说成最终 clean proof。
- 2026-05-15：完成 `debt-ledger-sync-cache`。只新增启用 `debt_ledger_sync`，不启用 `architecture_fitness` 或 `quickref_vs_routes`；proof 写入 `evidence/QualityGate/debt_ledger_sync.json`，绑定命令、fingerprint、台账 counts、architecture scan metadata、stdout/stderr 日志和声明输出 hash；台账、roadmap/feature、sync 脚本、扫描 helper、源码、配置、依赖、Python/env、architecture scan metadata 或 proof/log 变化都会重跑；`architecture_scan_cache.json` 本身不进 fingerprint；本次未运行 clean-worktree final quality gate，不能把本次验证说成最终 clean proof。
- 2026-05-16：完成 `quickref-vs-routes-cache`。只新增启用 `quickref_vs_routes`，不启用 `architecture_fitness`；报告写入 `evidence/Conformance/quickref_vs_routes.md`，绑定命令、fingerprint、系统速查表、app/bootstrap/routes/web 代码、模板、静态资源、配置、依赖、Python/env、stdout/stderr 日志和声明输出 hash；quickref stdout 改为仓库相对路径并静音 app 启动日志；本次未运行 clean-worktree final quality gate，不能把本次验证说成最终 clean proof。
- 2026-05-16：完成 `github-actions-long-gate-cache-persistence`。`.github/workflows/quality.yml` 使用 pinned `actions/cache/restore` / `actions/cache/save` 持久化 long gate 运行产物；restore 在完整门禁前，save 在完整门禁成功后；fork PR 不 save；缓存只包含已忽略的 `evidence/QualityGate/` long gate 运行产物，不包含已跟踪的 `evidence/Conformance/quickref_vs_routes.md`；CI 命令仍是 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，cache hit 不是 proof。
