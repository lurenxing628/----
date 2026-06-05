# 门禁提速分析报告（commit / push 到底在等什么）

项目：/Users/lurenxing/Documents/GitHub/----
分析方式：只读 + 实测计时（.venv/bin/python 3.8.10，10 核 macOS）。

---

## 一句话真因（root bottleneck）

**push 慢的唯一来源是 pre-push 的 daily gate 跑 impact pytest；而 scope 通配符（`core/**/*.py`、`web/viewmodels/**/*.py`、`templates/**/*.html`、`static/**/*`、`data/**/*.py`）宽到几乎任何一处源码改动都命中 5–7 个测试组（180–227 个测试文件、660–1900 条用例），串行无并行，于是典型 push 等 ~40s、最坏 ~180s。commit 本身很快（~2–3s），不是问题。**

---

## 各阶段实测耗时

### commit（pre-commit + commit-msg）—— 不是瓶颈，合计约 2–3s
钩子由 pre-commit 框架驱动，commit 阶段只做两件事 + commit-msg 一件：

| 步骤 | 内容 | 实测 |
|---|---|---|
| ruff (staged) | `run_staged_ruff`：把暂存树导出到临时目录，只对暂存的 .py 跑 ruff，带缓存（同暂存树直接命中） | 0.59s（全量 ruff 才 0.07s，单文件 0.02s） |
| block-local-artifacts | 几个 git 调用 + 路径规则匹配 | 0.50s |
| readable-commit-message | 读 message 文件做标题校验 | <0.1s |
| pre-commit 框架本身 | stash/restore 未暂存改动 + 钩子编排 | ~1–1.5s |

**结论：ruff 极快（0.07s 全量），commit 路径完全不需要优化。**

### push（pre-push daily gate）—— 全部时间花这里
`tools/git_hook_checks.py run-quality-gate` → 命中缓存就秒过（同 HEAD tree + 同 scope），否则跑 `scripts/run_daily_quality_gate.py`，顺序执行：

1. `pytest --collect-only tests -q` —— **实测 0.89s**（4073 条用例收集），**每次 push 固定付**
2. block staged artifacts —— ~0.1s
3. ruff（变更文件 or 全量）—— 0.02–0.07s
4. **impact pytest（按 scope 选的 target_paths）—— 大头**
5. **focused pytest（8 个固定 nodeid）—— 实测 1.16s（10 条用例），每次 push 固定付**

impact pytest 实测：

| 场景 | 命中组 | target 文件 | 用例数 | 实测 wall |
|---|---|---|---|---|
| 改 1 个路由文件 `scheduler_run.py` | 3 组 | 89 | 665 | **38.6s** |
| 改 1 个 core 文件 `scheduler/run.py` | 6 组 | 199 | ~1700 | ~160s（估，与下行同量级） |
| 改 template / static / config / schema / 任意 outside-scope | 7 组（全量） | 227 | 1887 | **178s（2:57）** |
| 纯文档改（README / docs/*.md / .codestable/*.md） | 0 组 | 0 | 0 | 跳过（仅 collect+focused ≈ 2s） |

> 时间分布：178s 里没有单个慢测试主导（durations 最慢的也才 3.18s 的 chrome probe）。成本是“广度税”——每条用例都要付 Flask app 构造 / DB 初始化的固定开销（~0.05–0.1s/条 × 660–1900 条）。其中约 10%（22/227）是 `regression_*.py` main-style 文件，每条用例额外 fork 一个子进程（`main_style_regression_runner.py`），单价更高（~0.5s）。

### CI 全量门禁（参考）
push 的 daily gate 自我声明“只挡明显问题，不是 clean proof”。真正收口是 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，跑全量 4073 条用例。按 collect 0.89s + 全量执行外推 ≈ **300–360s（5–6 分钟）**，本地不在 push 路径上、按需手动跑。

---

## 致命放大点（为什么 scope 这么宽）

1. **working-tree 污染**：`_changed_paths()` 永远把当前 `git diff` / `git diff --cached` / `git ls-files --others` 的结果**追加**到 pre-push 的 changed paths。当前工作树有 15 个暂存文件，其中 `.codestable/refactors/.../*.csv`、`scripts/build_test_inventory.py` 都在所有 scope 之外 → **只要这些脏文件在，任何 push 都被强制升级到全量 7 组 227 文件**。实测确认：所有 12 个代表文件在当前脏树下都报 ALL(7)/227。

2. **outside-scope 即全量**：`_build_impact_plan` 里只要有一个 changed path 不匹配任何组的 scope，立即 `return all_targets`（全 7 组）。新增文件、改 `scripts/`、改 `.codestable/` 非文档、改 `开发文档/技术债务治理台账.md`（被排除出 docs-only）都会触发。

3. **common scope 即全量**：改 `tools/test_registry*.py`、`pyproject.toml`、`conftest.py`、`requirements*.txt`、`scripts/run_quality_gate.py` 等 → 全 7 组。合理但很容易踩。

4. **通配重叠**：`core/**/*.py` 出现在 4 个组、`web/viewmodels/**/*.py` 出现在 5 个组、`templates/**/*.html`+`static/**/*` 几乎每组都有。所以“改 1 个 core 文件”≈“改半个项目”。而 7 组去重后总共也只有 227 个 target 文件——**“精准命中”相对“全量”省不下多少**（89 vs 227 是最好情况，多数源码改动落在 180–227）。

5. **focused 里有自指**：8 个固定 nodeid 中 5 个是门禁/缓存自身的合约测试（`test_long_gate_*_cache.py` ×4、`test_architecture_fitness` ×1），与业务无关；只有 3 个是业务（batches viewmodel ×2、ui geometry ×1）。这 8 个总耗时才 1.16s，省不动，但说明 focused 的设计目标是“盯门禁自身契约”，不是性价比项。

---

## 提速杠杆（按性价比排序）

### L1. 装 pytest-xdist 并行跑 impact/collect ⭐最高性价比
- 怎么做：`pytest -q -n auto --dist worksteal <targets>`（10 核）。测试已是子进程/独立 app 构造，无共享内存态；145 个测试用 tmp_path 隔离，DB 多为每测试新建或 main-style 子进程内自管，并行安全度高。
- 省多少：最坏 178s → 约 **35–55s**（净省 ~120–140s）；典型 38s → 约 **12–18s**（净省 ~20–25s）。不是满 10x（collect 串行 + 22 个子进程测试 + 启动开销）。
- 风险：中。需先验证少数共享固定路径 DB 的测试在并行下不打架（跑一轮 `-n auto` 对账绿）。
- 依赖：**需新依赖** pytest-xdist + execnet（纯 Python wheel）。Win7 离线可行：两者无 C 扩展，提前 `pip download pytest-xdist execnet` 拿 wheel 随项目带走即可，加进 requirements-dev.txt。

### L2. 收窄 scope 通配 + 拆 `core/**/*.py` ⭐高性价比、零依赖
- 怎么做：把 `core/**/*.py`、`web/viewmodels/**/*.py` 这种巨筐拆成子目录粒度（如 `core/services/scheduler/**`、`core/services/report/**`、`core/models/**` 分别映射到真正相关的组），让“改 core 一个文件”从命中 199 降到命中其真实相关的 1–2 组。
- 省多少：把典型源码改从 180–227 文件压到 40–90 文件，省 ~80–140s（最坏场景）/ ~15–25s（典型）。与 L1 叠加效果最好。
- 风险：中高。收窄 scope = 可能漏选真正受影响的测试（假阴性），削弱门禁保护力。必须配合“漏网就让 CI 全量兜底”的约定，且要人工核每个组的 target 与 scope 是否真对应。
- 依赖：无。改 `tools/test_registry_groups_*.py`。

### L3. 登记 outside-scope 高频文件 ⭐中性价比、低风险、零依赖
- 怎么做：把经常改但落在 scope 外的目录（`scripts/`、`.codestable/` 非文档、`开发文档/*.md`）显式登记：要么进某组 input_file_scopes，要么进“纯文档/纯工具→跳过 impact”的白名单（类比现有 `_is_docs_only_path`）。同时清理当前脏树里的 `.codestable/refactors/*.csv`（它们正强制每次 push 全量）。
- 省多少：消除“误升级全量”，把这类 push 从 178s 拉回到真实相关的几十秒。频次取决于你多常改这些目录。
- 风险：低。只影响选择逻辑，不动测试本身。
- 依赖：无。

### L4. 隔离最慢的 chrome/runtime 测试 ⭐低性价比
- 怎么做：`test_ui_browser_geometry_env.py`（单测 3.18s，最慢）、ui geometry / chrome probe 类用环境变量门控（已有 `APS_BROWSER_SMOKE_REQUIRED` / `chrome_*` env_keys），push 时默认跳过浏览器实跑，留给 CI。
- 省多少：每次命中 ui 组省 ~3–5s。量小，因为没有单点大头。
- 风险：低（这些测试本就靠 env 门控）。
- 依赖：无。

### L5. 缓存友好工作流（已有，用好它）⭐零成本
- 现状：pre-push 已有缓存（同 HEAD tree + 同 scope payload 直接秒过，见 `pre_push_daily_cache_hit`）；staged ruff 也有缓存。
- 怎么做：保持工作树干净（清掉脏 csv），同一棵树重复 push 自动命中缓存（0 秒）。这不是改代码，是用法纪律。
- 省多少：重复 push 从 40–178s → ~1s。
- 风险：无。依赖：无。

---

## 落地建议顺序
1. 立刻：清当前脏树里的 outside-scope csv（消除全量误升级）+ 用好已有缓存（L5/L3 的免费部分）。
2. 一次性最大收益：装 pytest-xdist 并 `-n auto`（L1），把 daily gate 命令加 `-n auto`。Win7 离线提前 download wheel。
3. 中期：拆 `core/**`、`viewmodels/**` 巨筐 scope（L2），配 CI 全量兜底。
4. 顺带：env 门控浏览器测试（L4），登记 scripts/.codestable 高频路径（L3 剩余部分）。
