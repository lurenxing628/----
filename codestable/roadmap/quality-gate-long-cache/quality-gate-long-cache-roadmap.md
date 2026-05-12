---
doc_type: roadmap
slug: quality-gate-long-cache
status: active
created: 2026-05-12
last_reviewed: 2026-05-12
tags: [quality-gate, cache, full-test-debt, pyright, ruff]
related_requirements: []
related_architecture: [codestable/architecture/ARCHITECTURE.md]
---

# 质量门禁长耗时缓存路线

## 1. 背景

这份 roadmap 承接用户给出的细粒度实施方案，只做后续开发的规划落盘，不直接修改门禁代码。当前本地仓库 HEAD 已核对为 `5a3e0d1e7313ce27c6ac29786c86b6832b72f496`，也就是方案声明的基准提交。

现在仓库的统一质量门禁入口是 `scripts/run_quality_gate.py`。这个入口不是单跑一个测试，而是串起测试收集、full-test-debt proof、`ruff`、`pyright`、架构体检、必跑回归、债务台账检查、启动链回归和速查表一致性检查。当前 `tools/quality_gate_shared.py::build_quality_gate_command_plan()` 会动态生成真实命令计划，本地核对到当前共有 13 步命令。

本 roadmap 要解决的问题很直接：如果门禁输入完全没变，长耗时命令不应该每次都重新跑；但也不能为了快就假装通过。只有上一次成功、日志和输出文件都还在、命令身份没变、工具版本没变、配置没变、相关输入文件没变，才允许复用。只要有一点对不上，就重新执行。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 从真实 `build_quality_gate_command_plan()` 生成长耗时门禁清单，不手写固定测试清单。
- 为每条可复用命令建立输入指纹，覆盖文件新增、删除、改名、内容变化、配置变化、依赖变化、关键环境变量变化。
- 为上一次成功结果建立缓存记录，校验 result JSON、stdout/stderr 日志、声明输出文件的 hash。
- 在 `scripts/run_quality_gate.py` 里保留现有“上次失败后跳过成功前缀继续跑”的能力，再新增“上次成功且输入没变时复用单条/单组成功结果”的能力。
- 先做 collect-only、full-test-debt、启动/必跑回归、架构体检、债务台账、quickref、ruff/pyright 等门禁项的保守整项复用，再逐步引入更细粒度缓存。
- 输出能让普通维护者看懂的决策表：哪些是真跑、哪些是复用、为什么复用、为什么失效、失败时怎么复制命令重跑。
- 新增足够的合同测试，保证“该重跑时一定重跑，该复用时才复用”。

### 明确不做

- 不把定向测试、fast precheck 当成正式全量门禁。它们只能提前发现问题，不能替代 `scripts/run_quality_gate.py --require-clean-worktree`。
- 不把 CI 的 `actions/cache` 作为第一阶段目标。先让本地缓存机制稳定，再决定 CI 是否接入。
- 不手写 required regression 或 startup regression 清单。所有这些清单只能从真实命令计划里提取。
- 不删除旧 receipt 或旧 long gate cache。缓存损坏时只解释并绕过，不擅自清理证据。
- 不改变 full-test-debt、架构体检、债务台账本身的业务判定规则；第一阶段只包一层“输入没变就复用上次成功”的能力。
- 不放宽 clean-worktree proof。最终可合并证明仍然要绑定干净工作区和最终 HEAD。

## 3. 模块拆分（概设）

```text
质量门禁长耗时缓存
├── 长耗时清单模块：从真实 command plan 识别哪些命令可复用
├── 输入指纹模块：把命令、文件、配置、依赖、环境变成稳定 hash
├── 成功缓存模块：读写上次成功结果并判断复用还是重跑
├── 门禁接入模块：把复用决策接入 run_quality_gate.py 的命令循环
├── 专项缓存模块：collect-only、full-test-debt、回归组、架构体检、台账、quickref、ruff/pyright
└── 输出和测试模块：决策表、summary、失败重跑提示、合同测试
```

### 长耗时清单模块

- **职责**：新增 `tools/long_gate_manifest.py`，只负责从 `build_quality_gate_command_plan()` 生成清单和分类结果。
- **不做**：不执行门禁、不读写 success cache、不复制 `tools/test_registry.py` 里的测试列表。
- **承载的子 feature**：`long-gate-manifest-probe`。
- **触碰的现有代码 / 模块**：`tools/quality_gate_shared.py` 只作为读取来源，第一步不改它。

### 输入指纹模块

- **职责**：新增 `tools/long_gate_fingerprint.py`，把“这条命令依赖了什么”变成可比较的稳定 JSON 和 hash。
- **不做**：不根据模糊规则猜测业务影响；只记录被声明的输入范围、工具版本、配置、环境和文件集合。
- **承载的子 feature**：`long-gate-cache-core`。
- **触碰的现有代码 / 模块**：新增工具模块，后续被 cache 和 runner 调用。

### 成功缓存模块

- **职责**：新增 `tools/long_gate_cache.py`，读取 `evidence/QualityGate/long_gate/results/*.success.json`，判断 `reuse` 还是 `run`，并写入新的成功记录。
- **不做**：不删除损坏缓存，不把失败结果写成 success cache。
- **承载的子 feature**：`long-gate-cache-core`。
- **触碰的现有代码 / 模块**：新增工具模块，`.gitignore` 需要忽略 `evidence/QualityGate/long_gate/`。

### 门禁接入模块

- **职责**：在 `scripts/run_quality_gate.py` 命令循环里接入 long gate decision；现有失败续跑能力先执行，未被续跑跳过的命令再判断是否复用上次成功。
- **不做**：不伪造真实执行。receipt 必须明确写 `execution_mode`，让人看出这一步是执行、失败续跑复用，还是成功缓存复用。
- **承载的子 feature**：`quality-gate-runner-collect-cache`。
- **触碰的现有代码 / 模块**：`scripts/run_quality_gate.py`、`tools/quality_gate_shared.py` 的 receipt schema 相关辅助函数。

### 专项缓存模块

- **职责**：按风险从低到高逐步接入 collect-only、full-test-debt、startup runtime regression、required regression、architecture fitness、debt ledger sync、quickref vs routes、ruff/pyright。
- **不做**：不一口气把所有门禁都改成缓存模式。每类门禁必须有对应测试和失效原因展示。
- **承载的子 feature**：`collect-only-cache-output`、`full-test-debt-success-cache`、`runtime-and-required-regression-cache`、`architecture-file-scan-cache`、`debt-ledger-and-quickref-cache`、`static-check-cache-and-fast-precheck`。
- **触碰的现有代码 / 模块**：`tools/check_full_test_debt.py`、`tools/collect_full_test_debt.py`、`tools/quality_gate_scan.py`、`scripts/sync_debt_ledger.py`、`tests/check_quickref_vs_routes.py` 等。

### 输出和测试模块

- **职责**：把每次运行的 long gate 决策写入 `summary.json`、`summary.md`，并用测试锁住复用、失效、损坏缓存、失败提示等行为。
- **不做**：不只写快乐路径测试。缓存损坏、日志丢失、输出文件丢失、命令变化、schema 变化都必须覆盖。
- **承载的子 feature**：`long-gate-summary-and-contract-tests`。
- **触碰的现有代码 / 模块**：新增 `tests/test_long_gate_*.py` 系列测试，必要时补 `tests/test_run_quality_gate.py` 的集成合同。

## 4. 模块间接口契约 / 共享协议（架构层详设）

这一节是后续 feature-design 的硬约束。后续实现如果发现这些结构不够用，要先回到本 roadmap 更新，不要在单个 feature 里偷偷改另一套口径。

### 4.1 长耗时清单入口

**方向**：`run_quality_gate.py` / CLI → `tools.long_gate_manifest`

**形式**：函数调用和命令行探测。

**契约**：

```python
LONG_GATE_SCHEMA_VERSION = 1

def build_long_gate_manifest(repo_root: str | os.PathLike[str]) -> LongGateManifest: ...

def classify_quality_gate_command(command: Mapping[str, object]) -> str: ...

def build_manifest_from_quality_gate_plan(
    command_plan: Sequence[Mapping[str, object]],
    *,
    receipts: Sequence[Mapping[str, object]] | None = None,
) -> LongGateManifest: ...
```

命令行入口：

```bash
python -m tools.long_gate_manifest --print
python -m tools.long_gate_manifest --print --include-local-receipts
```

约束：

- `command_plan` 必须来自 `tools.quality_gate_shared.build_quality_gate_command_plan()`。
- required regression 和 startup regression 只能从 `command_plan` 的 pytest 命令里提取，不能复制动态注册表。
- 未识别但耗时较长的 receipt command 要在输出里 warning，不要静默丢弃。

### 4.2 Manifest 顶层结构

**方向**：`tools.long_gate_manifest` → `tools.long_gate_cache` / summary 输出。

**形式**：deterministic JSON。

**契约**：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-12T00:00:00",
  "repo_root": "/abs/path",
  "head_sha": "5a3e0d1e7313ce27c6ac29786c86b6832b72f496",
  "quality_gate_plan_hash": "0123456789abcdef...",
  "entries": []
}
```

每个 entry 必须至少包含：

```json
{
  "schema_version": 1,
  "entry_id": "pytest_collect_all",
  "entry_type": "pytest_collect_all",
  "command_name": "python -m pytest --collect-only -q tests",
  "display": "python -m pytest --collect-only -q tests",
  "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
  "capture_output": true,
  "output_policy": "normalized",
  "command_hash": "0123456789abcdef...",
  "input_file_scopes": [],
  "config_file_scopes": [],
  "tool_file_scopes": [],
  "dependency_file_scopes": [],
  "env_keys": [],
  "output_result_files": [],
  "reuse_allowed": true,
  "force_invalidate_on": [],
  "fingerprint": null,
  "previous_success": null,
  "last_success_fingerprint": null
}
```

约束：

- 当前命令分类必须覆盖：`pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`architecture_fitness`、`required_regressions`、`debt_ledger_sync`、`startup_runtime_regressions`、`quickref_vs_routes`、`version_or_env_probe`。
- `version_or_env_probe` 只记录环境，不作为长耗时复用主目标。
- `QUALITY_GATE_TOOL_PATHS` 和 `QUALITY_GATE_SOURCE_FILES` 必须直接纳入相关指纹范围。

### 4.3 输入指纹结构

**方向**：`tools.long_gate_fingerprint` → `tools.long_gate_cache`。

**形式**：deterministic JSON + hash。

**契约**：

```python
def fingerprint_entry(entry: LongGateEntry, repo_root: str | os.PathLike[str]) -> FingerprintResult: ...

def fingerprint_files(paths_or_patterns: Sequence[str], repo_root: str | os.PathLike[str]) -> FileSetFingerprint: ...

def fingerprint_command(command: Mapping[str, object]) -> str: ...

def fingerprint_environment(keys: Sequence[str]) -> dict[str, str | None]: ...

def diff_fingerprints(previous: Mapping[str, object], current: Mapping[str, object]) -> InvalidationReason: ...
```

单文件指纹：

```json
{
  "path": "tests/example.py",
  "exists": true,
  "kind": "file",
  "size": 1234,
  "mode": "100644",
  "sha256": "abc...",
  "source": "tracked"
}
```

文件集合指纹：

```json
{
  "paths_hash": "0123456789abcdef...",
  "content_hash": "0123456789abcdef...",
  "files": []
}
```

Hash 口径：`quality_gate_plan_hash`、`command_hash`、`paths_hash`、`content_hash`、`nodeid_hash` 和 `generated_from_stdout_sha256` 目前都是裸 64 位十六进制字符串；只有 `fingerprint.hash` / `current_fingerprint_hash` 这类总指纹展示字段带 `sha256:` 前缀。

约束：

- 路径枚举优先用 `git ls-files -z` 获取 tracked 文件。
- 允许 dirty worktree 的本地场景还要读取 `git ls-files --others --exclude-standard -z`，避免新测试文件未提交时被漏掉。
- 所有路径统一 `/` 分隔，排序去重。
- hash 使用 `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`。
- 文件新增、删除、改名、内容变化、空文件替换、同内容但路径变化，都必须让指纹变。

### 4.4 成功缓存结构和复用决策

**方向**：`tools.long_gate_cache` → `run_quality_gate.py`。

**形式**：函数调用 + success JSON。

**契约**：

```python
def load_previous_success(entry_id: str) -> CachedResult | None: ...

def decide_reuse(entry: LongGateEntry, current_fingerprint: FingerprintResult) -> CacheDecision: ...

def write_success(entry: LongGateEntry, fingerprint: FingerprintResult, command_result: Mapping[str, object], output_files: Sequence[str]) -> None: ...

def write_failure(entry: LongGateEntry, fingerprint: FingerprintResult, command_result: Mapping[str, object]) -> None: ...
```

`CacheDecision`：

```json
{
  "entry_id": "pytest_collect_all",
  "decision": "reuse",
  "reuse_allowed": true,
  "reason": "fingerprint matched previous successful result",
  "invalidated_by": [],
  "previous_completed_at": "2026-05-12T00:00:00",
  "previous_result_path": "evidence/QualityGate/long_gate/results/pytest_collect_all.success.json",
  "current_fingerprint_hash": "sha256:..."
}
```

成功缓存路径：

```text
evidence/QualityGate/long_gate/
  manifest.json
  summary.json
  summary.md
  cache_index.json
  results/
  logs/
```

约束：

- 只有 `status == "passed"` 且 `returncode == 0` 才能复用。
- timeout、interrupt、partial write 一律不能复用。
- JSON decode error、缺字段、stdout/stderr log 缺失、output file 缺失、hash 不一致，一律 `decision=run`。
- 损坏缓存不要删除，要写进 summary 解释本次为什么绕过。

### 4.5 `run_quality_gate.py` 接入顺序

**方向**：`scripts/run_quality_gate.py` → long gate 模块。

**形式**：命令循环扩展。

**契约**：

```text
1. 构造 command plan。
2. 先执行现有 resume-from-failure 决策。
3. 对未被 resume-prefix 跳过的 command，再做 long gate success cache 决策。
4. 非 long gate command 正常执行。
5. 真实执行通过后写现有 receipt，再写 long gate success cache。
6. 复用时不要伪装成真实执行，receipt 写 execution_mode。
```

receipt 新增字段：

```json
{
  "execution_mode": "executed",
  "reused_from": null,
  "started_at": "2026-05-12T00:00:00",
  "ended_at": "2026-05-12T00:00:01",
  "duration_s": 1.23,
  "timed_out": false,
  "interrupted": false
}
```

`execution_mode` 允许值：

```text
executed
reused_success_cache
resumed_success_prefix
```

约束：

- 旧 receipt 没有 duration 字段时不能报错。
- 统计慢命令时，旧 receipt duration 缺失只标 `duration_unknown`。
- cache 复用判定不依赖 duration。
- `--long-gate-cache-explain` 只输出决策，不执行命令。

### 4.6 collect-only 输出结构

**方向**：collect-only 命令处理 → full-test-debt / required regression 后续逻辑。

**形式**：`evidence/QualityGate/collect_nodeids.json`。

**契约**：

```json
{
  "schema_version": 1,
  "status": "passed",
  "nodeids": [],
  "nodeid_count": 0,
  "nodeid_hash": "0123456789abcdef...",
  "nodeids_by_file": {},
  "pytest_version": "x.y.z",
  "generated_from_stdout_sha256": "0123456789abcdef...",
  "collect_stdout_log_path": "evidence/QualityGate/logs/..."
}
```

约束：

- 真实执行时用现有 collect stdout 解析逻辑生成 nodeids。
- 复用时必须校验 `collect_nodeids.json` 存在且 hash 匹配。
- 后续需要 nodeid proof 时，不能重新跑 collect，只能读取已校验的缓存输出。

### 4.7 专项输出文件协议

**方向**：各专项缓存 → success cache。

**形式**：每类专项声明自己的 output file，并在 success cache 中保存 hash。

必须覆盖：

- `full_test_debt`：`evidence/QualityGate/current_full_test_debt.json`、`evidence/QualityGate/full_test_debt_summary.json`。
- `startup_runtime_regressions`：`evidence/QualityGate/startup_runtime_regressions.json`。
- `architecture_fitness`：`evidence/QualityGate/architecture_scan_cache.json`。
- `required_regressions`：`evidence/QualityGate/required_regressions.json`。
- `debt_ledger_sync`：`evidence/QualityGate/debt_ledger_sync.json`。
- `quickref_vs_routes`：`evidence/Conformance/quickref_vs_routes.md`。

约束：

- 输出文件只要缺失或 hash 不一致，就必须重新执行。
- full-test-debt 第一阶段只做整项成功复用；nodeid 级增量是第二阶段增强。
- architecture fitness 可以先做命令级复用，再把 `tools/quality_gate_scan.py` 拆成文件级扫描缓存。

## 5. 子 feature 清单

1. **long-gate-manifest-probe** — 新增长耗时清单模块和探测命令，只展示真实 command plan、分类结果和本地 receipt 慢命令信息。
   - 所属模块：长耗时清单模块。
   - 依赖：无。
   - 状态：done。
   - 对应 feature：`2026-05-12-long-gate-manifest-probe`。
   - 备注：已新增只读清单工具和合同测试；这一步没有接入真实门禁，不改变任何门禁结果。

2. **long-gate-cache-core** — 新增输入指纹和成功缓存核心模块，覆盖文件集合、环境、命令身份、损坏缓存和失效原因。
   - 所属模块：输入指纹模块、成功缓存模块。
   - 依赖：`long-gate-manifest-probe`。
   - 状态：done。
   - 对应 feature：`2026-05-12-long-gate-cache-core`。
   - 备注：已新增输入指纹和 success cache 核心库，并用临时目录单测锁住复用/失效判定。

3. **collect-only-cache-output** — 为 `python -m pytest --collect-only -q tests` 生成 `collect_nodeids.json`，并锁住新增/删除/修改测试文件后的失效行为。
   - 所属模块：专项缓存模块。
   - 依赖：`long-gate-cache-core`。
   - 状态：done。
   - 对应 feature：`2026-05-12-collect-only-cache-output`。
   - 备注：已补 collect-only 输入 scope、输出 payload 和失效合同；仍未接入整个门禁循环。

4. **quality-gate-runner-collect-cache** — 把 long gate decision 接入 `scripts/run_quality_gate.py`，但第一轮只对 collect-only 开启成功缓存复用。
   - 所属模块：门禁接入模块、输出和测试模块。
   - 依赖：`collect-only-cache-output`。
   - 状态：done。
   - 对应 feature：`2026-05-12-quality-gate-runner-collect-cache`。
   - 备注：已完成最小闭环。`--long-gate-cache` 会先输出 collect-only 决策表；单测里第一次走 collect 执行分支并写 `collect_nodeids.json` / success cache，第二次输入没变时复用 collect；receipt 明确写 `execution_mode`、`reused_from`、耗时字段和完整性字段；失败续跑前缀会写 `execution_mode=resumed_success_prefix`，dirty 快速反馈不会写 long-gate success cache。完整 summary.json/summary.md 留到第 10 条收口。

5. **full-test-debt-success-cache** — 为 `python tools/check_full_test_debt.py` 做整项成功复用，并为后续 nodeid 级增量缓存打下结构。
   - 所属模块：专项缓存模块。
   - 依赖：`quality-gate-runner-collect-cache`。
   - 状态：planned。
   - 对应 feature：未启动。
   - 备注：第一阶段任何源码、测试、台账、collector、pytest 配置变化都整体失效。

6. **runtime-and-required-regression-cache** — 从真实 command plan 提取 startup runtime regression 和 required regression 两组 pytest 命令，做保守整组成功复用。
   - 所属模块：专项缓存模块。
   - 依赖：`full-test-debt-success-cache`。
   - 状态：planned。
   - 对应 feature：未启动。
   - 备注：必须证明 `tools/test_registry.py` 或动态 args 变化会强制失效。

7. **architecture-file-scan-cache** — 把 `tools/quality_gate_scan.py` 的架构扫描拆成文件级缓存，再让 `tests/test_architecture_fitness.py` 复用未变化文件的扫描结果。
   - 所属模块：专项缓存模块。
   - 依赖：`runtime-and-required-regression-cache`。
   - 状态：planned。
   - 对应 feature：未启动。
   - 备注：先复用 AST/扫描结果，聚合规则仍每次重算。

8. **debt-ledger-and-quickref-cache** — 为 `scripts/sync_debt_ledger.py check` 和 `tests/check_quickref_vs_routes.py` 做成功复用，并声明台账、扫描脚本、路由、模板、速查表等输入范围。
   - 所属模块：专项缓存模块。
   - 依赖：`architecture-file-scan-cache`。
   - 状态：planned。
   - 对应 feature：未启动。
   - 备注：quickref 的 `evidence/Conformance/quickref_vs_routes.md` 必须作为输出文件校验。

9. **static-check-cache-and-fast-precheck** — 为 formal `ruff`/`pyright` 全量命令做成功缓存，并新增只面向改动 Python 文件的 fast precheck。
   - 所属模块：专项缓存模块。
   - 依赖：`debt-ledger-and-quickref-cache`。
   - 状态：planned。
   - 对应 feature：未启动。
   - 备注：fast precheck 只能提前反馈，不能替代 formal full gate。

10. **long-gate-summary-and-contract-tests** — 收口所有 summary 输出、失败重跑提示、损坏缓存提示、双跑验证、文档说明和合同测试。
    - 所属模块：输出和测试模块。
    - 依赖：`static-check-cache-and-fast-precheck`。
    - 状态：planned。
    - 对应 feature：未启动。
    - 备注：最终要能清楚回答“这次为什么快了，以及它凭什么可信”。

**最小闭环**：第 4 条 `quality-gate-runner-collect-cache` 已完成代码和单测级双跑验证：第一次走 collect-only 执行分支并写成功缓存，第二次在测试文件、pytest 配置、依赖和门禁脚本都没变时复用 collect-only，同时 receipt 明确写出复用来源。完整 summary.json/summary.md 和最终干净工作区双跑仍放在第 10 条收口。

## 6. 排期思路

推荐顺序沿用原方案的保守路线：先做清单和缓存骨架，不接入真实门禁；再拿 collect-only 做最小闭环；确认“该重跑就重跑、该复用才复用”以后，再扩大到 full-test-debt、回归组、架构扫描、台账、quickref、静态检查。

这个顺序的好处是风险最小。collect-only 的输出是 nodeid 清单，比较稳定，而且后面的 full-test-debt 和回归组都需要它；如果连 collect-only 都解释不清楚，就不应该直接动 full-test-debt 或 pyright 这种影响更大的门禁项。

每个阶段都要有自己的退出条件：功能代码、合同测试、失效原因输出、双跑验证。不能只因为第二次跑得快，就认为缓存可信。

## 7. 观察项

- 当前 `.gitignore` 已忽略 `evidence/QualityGate/quality_gate_manifest.json`、`receipts/`、`logs/`、`long_gate/`、`collect_nodeids.json`、`current_full_test_debt.json`，本地缓存和门禁运行产物不会进入提交。
- 当前 `scripts/run_quality_gate.py` 的失败续跑只在 `--allow-dirty-worktree` 场景下使用，且明确不是完整通过证明；新增成功缓存时要避免把“快速反馈”和“clean proof”混在一起。
- 当前 README 和 `开发文档/README.md` 都强调最终 clean proof 需要干净工作区。long gate cache 即使启用，也不能绕开这个口径。
- 架构扫描文件级缓存会触碰 `tools/quality_gate_scan.py` 的内部结构，风险高于命令级缓存，应放到 collect-only/full-test-debt/回归组稳定之后。
- full-test-debt 的 nodeid 级增量缓存需要更强的依赖映射。第一阶段只做整项成功复用，不提前承诺精准增量。

## 8. 变更日志

- 2026-05-12：按用户提供的细粒度方案新建 roadmap，只做规划落盘；已核对当前 HEAD、真实 command plan、现有 receipt / resume 入口和 CodeStable 目录约定。
- 2026-05-12：完成 `long-gate-manifest-probe`，新增只读 long gate manifest 探测工具、CLI 和测试，并把 PR-0 状态回写为 done。
- 2026-05-12：完成 `long-gate-cache-core`，新增输入指纹、success cache 读写和复用决策核心，并把 PR-1 状态回写为 done。
- 2026-05-12：完成 `collect-only-cache-output`，新增 collect nodeid 输出 payload、collect entry scope 和输入变化失效测试，并把 PR-2 状态回写为 done。
- 2026-05-12：完成 `quality-gate-runner-collect-cache`，把 collect-only success cache 接入 `scripts/run_quality_gate.py`，新增 CLI 开关、决策表、复用 receipt 字段、receipt 耗时字段和双跑合同测试，并把 PR-3 状态回写为 done。
- 2026-05-12：按对抗审核结果补强 PR-0 到 PR-3：long gate 工具纳入 `QUALITY_GATE_TOOL_PATHS` 和 gate source proof，指纹补 runtime facts 和 schema hash，缓存路径禁止逃出仓库，未知 pytest 命令不再按位置误分类，失败续跑 receipt 明确标 `resumed_success_prefix`，dirty 快速反馈不写 success cache。
