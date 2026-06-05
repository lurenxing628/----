# 提速 + 可读性专项方案（2026-06-05 重测，对准真实痛点）

> 触发：用户两个真痛点 —— ①每次 commit/push 跑测试太慢挡着干活 ②不看内容根本不知道测什么、难维护、极其繁杂。
> 本版基于**当前仓库实测**（645 文件）。原始报告见 `speed_report.md`、`readability_report.md`。
> 与删/合并（`L3_VERDICTS.md`）是不同方向：删测试对这两个痛点帮助有限（测试本身才占全量的一小部分），本方案直击时间与可读性。

---

## 第 0 章　颠覆性发现：慢的不是测试，是"选哪些测试跑"的配置

### 0.1 各阶段实测耗时（当前）

| 阶段 | 实测 | 是否瓶颈 |
|---|---|---|
| commit（pre-commit 框架 + staged ruff 0.59s + 拦产物 0.5s + 框架 stash/restore 1-1.5s） | ~2-3s | ❌ 不优化（ruff 全量才 0.07s）|
| **push 典型**（改 1 个路由 → 3 组 89 文件 665 用例） | **38.6s** | ✅ 主痛点 |
| **push 最坏**（命中全 7 组 227 文件 1887 用例） | **178s（2:57）** | ✅✅ |
| push 纯文档改 | ~2s | 0 组 |
| 全量串行（参考） | 330s | CI/手动 |

### 0.2 push 慢的真因（坐实）

链路：`git push` → pre-push → `run_daily_quality_gate.py` 的 **impact pytest**（按改动选测试组）。固定底噪只有 collect 0.89s + focused 1.16s ≈ 2s，**全部波动来自 impact 选组**。

问题出在映射表 `tools/test_registry_groups_scheduler.py` / `test_registry_groups_misc.py`（共 66 个 `**` 通配）：
```
core/**/*.py          ← 出现在 4 个组
web/viewmodels/**/*.py ← 出现在 5 个组
templates/**/*.html   ← 几乎每组
static/**/*           ← 几乎每组
data/**/*.py          ← 多组
```
**后果**：改一个 `.py` 命中 5-7 组、180-227 文件、660-1900 用例，串行无并行。"改 1 个 core 文件 ≈ 改半个项目"。而 7 组去重后总共也才 227 个 target——**"精准命中"相对"全量"省不下多少**（最好 89，多数 180-227）。慢的本质是**广度税**：每条用例都要付 Flask app 构造 / DB 初始化的固定开销（~0.05-0.1s × 几百上千条）。

### 0.3 三个致命放大点（新发现）

1. **working-tree 污染（最隐蔽）**：`_changed_paths()` 永远把当前 `git diff` / `--cached` / `ls-files --others` 追加进 changed paths。**当前工作树里我刚 git add 的 `.codestable/refactors/*.csv` + `scripts/build_test_inventory.py` 都在所有 scope 之外 → 只要它们在暂存区，任何 push 都被强制升级到全量 7 组 227 文件。** 实测确认 12 个代表文件在当前脏树下都报 ALL(7)/227。
2. **outside-scope 即全量**：`_build_impact_plan` 遇到任一不匹配 scope 的 path 立即 `return all_targets`。新增文件、改 `scripts/`、改 `.codestable/` 非文档都触发。
3. **common scope 即全量**：改 `tools/test_registry*`、`pyproject.toml`、`conftest.py`、`requirements*` → 全 7 组（合理但易踩）。

### 0.4 第二个反讽：focused 8 个固定测试，5 个是门禁自指

`FOCUSED_PYTEST_NODEIDS` 每次 push 雷打不动跑 8 个，其中 5 个是 `test_long_gate_*_cache` / `test_architecture_fitness`——测门禁/缓存自己，与业务无关（总耗时 1.16s，省不动但说明设计目标偏了）。

### 0.5 结论
**push 慢与测试数量无关，是 impact 配置太粗（scope 通配）+ 工作树污染升全量。改配置即可，一个测试都不用删。**

---

## 第 1 章　提速方案（按性价比，全部实测支撑）

### 🟢 S0 立刻：清工作树 + 用好已有缓存（零成本，0 分钟）
- 当前暂存的 `.codestable/*.csv` 等 outside-scope 文件正强制每次 push 全量。**提交或移出暂存区后**，push 立刻不再被误升级。
- pre-push 已有缓存（同 HEAD tree + 同 scope payload 秒过，`pre_push_daily_cache_hit`）+ staged ruff 缓存。保持工作树干净，重复 push 自动 ~1s。

### 🟢 S1 装 pytest-xdist 并行 ⭐最高性价比（需 vendor wheel）
- **做法**：daily gate 的 impact pytest 加 `-n auto --dist worksteal`（10 核）。测试已是子进程/独立 app 构造，并行安全度高。
- **收益**：最坏 178s → **~35-55s**（净省 ~120-140s）；典型 38s → **~12-18s**。CI 全量 330s → ~90s。
- **Win7 离线**：`pytest-xdist` + `execnet` 均纯 Python wheel，无 C 扩展，`pip download` 后放 `vendor/wheels/`、登记 `requirements-dev.txt` 即可。
- **风险**：中。需跑一轮 `-n auto` 对账绿（验证少数共享固定路径 DB 的测试并行不打架）。
- **依赖**：需新增 2 个 wheel。

### 🟢 S2 收窄 scope 通配 ⭐高性价比、零依赖
- **做法**：把 `core/**/*.py`、`web/viewmodels/**/*.py` 巨筐拆到子目录粒度（如 `core/services/scheduler/**`、`core/models/**` 分别映射相关组），让"改 1 个 core 文件"从命中 199 降到 1-2 组。
- **收益**：典型源码改从 180-227 文件压到 40-90 文件，省 ~80-140s（最坏）/ ~15-25s（典型）。与 S1 叠加最佳。
- **风险**：中高——收窄=可能漏选受影响测试（假阴性）。必须配 CI 全量兜底 + 人工核每组 target 与 scope 对应。
- **保守档建议**：精确到子目录（非文件），漏跑风险小、仍大幅提速。

### 🟢 S3 登记 outside-scope 高频文件 + 未知路径设小默认 ⭐低风险零依赖
- **做法**：把常改但落 scope 外的（`scripts/`、`.codestable/` 非文档、开发文档/*.md）登记进组或"跳过 impact"白名单（类比 `_is_docs_only_path`）。未知路径兜底从"全 7 组"改为"仅 quality_gate 自测组 + focused"。
- **收益**：消除"误升级全量"，这类 push 从 178s 回到几十秒。

### 🟢 S4 精简 FOCUSED_PYTEST_NODEIDS ⭐5 分钟
- 移除 5 个 `test_long_gate_*`/`test_architecture_fitness` 门禁自指（CI 全量仍跑），focused 只留真业务冒烟。每次 push 省 ~1s。

### 🟡 S5 隔离最慢浏览器/runtime 测试
- `test_ui_browser_geometry_env`(3.18s)、ui geometry / chrome probe 用 env 门控（`APS_BROWSER_SMOKE_REQUIRED` 已有），push 默认跳过留 CI。每次命中省 3-5s。对 push 帮助小（它们多不在 daily 路径），主要利 CI。

### 提速落地顺序
1. **S0（0分钟）→ S4（5分钟）→ S3（半天）→ S2（1天）**：纯配置零删除，push 典型 ~40s → ~10-15s。
2. **S1（2-3天，需 wheel）**：要更快上并行，CI 也减半。

---

## 第 2 章　可读性方案（对准"不看内容不知道测什么"）

### 2.1 实测病灶（当前，全量测算）

| 病灶 | 实测 | 后果 |
|---|---|---|
| 单层平铺文件 | 626（97% 在 tests/ 根） | 定位只能 grep |
| 真正分类子目录 | 仅 2（scheduler_graph/17、regression/2）| 无分层 |
| 模块 docstring | **4.5%**（28/625） | 没有"测什么"说明 |
| 函数 docstring | 1.4%（97/6878） | 函数级也没 |
| 裸 assert（无消息） | **85.3%**（13696/16065）| 失败只见 AssertionError，不知期望 vs 实际 |
| main-style 风格 | **35.8%**（224）| 裸 assert 经子进程跑，失败信息最差 |
| find_repo_root 样板 | **70.9%**（443）| 12 行噪声淹没正文，import 藏函数体内 |
| 文件名长度 | 中位 46 / p90 58 / 最长 73 | 看名字猜，IDE 标签截断 |
| `_contract` 后缀 | 30%（143/469 regression）| 同质化，同模块多个 _contract 必须打开才能区分 |

### 2.2 根因：文件名被迫替代缺失的 docstring + 两套写法 + 1bug=1文件

- docstring 几乎为 0（4.5%），文件名被迫承担全部信息量 → 撑到 73 字符还在 IDE 里被截断、前缀同质化。
- 两套互不兼容写法（pytest 56% / main-style 35.8% / 混血 6.2%），前缀 `regression_` 不指示风格——**看名字不知道该怎么跑、失败长什么样**。
- "1 bug = 1 文件"把同模块拆成几十个兄弟文件（candidate 18、resource_dispatch 15、operation_execution 14）。

### 2.3 main-style 失败有多差（"难维护"第二根源）
main-style 经 conftest 子进程跑，裸 assert 失败 stderr 只有 `AssertionError`（无值），conftest 再包一层"子进程退出码 + traceback"抛出。**85% 裸 assert + 35.8% main-style → 失败时拿不到期望 vs 实际，必须回读源码/加 print/重跑。**

### 2.4 可读性方案（#1#2 直击痛点）

### 🟢 R1 强制模块 docstring「一句话测什么」⭐根治痛点、零风险
- 每文件首行加 `"""测 X 在 Y 条件下应 Z。"""`。加门禁校验拦无 docstring 新文件（照搬现有文档门禁模式）。
- 收益：**直接消灭"不看内容不知道测什么"**——4.5%→100%。可 AI 批量生成首句再人工核。

### 🟢 R2 裸 assert 补消息 ⭐失败即可读
- 新 assert 一律带消息；存量优先 main-style（pytest 有自省可缓）。失败直接看到期望 vs 实际。

### 🟡 R3 抽样板为公共 fixture
- 443 份 find_repo_root/sys.path.insert 收敛到 conftest fixture。每文件省 ~12 行噪声。与 R5 配合（main-style 依赖自带引导）。

### 🟡 R4 目录按被测模块重组
- 626 文件迁进 `tests/<模块>/<子模块>/`，对齐 `core/services/scheduler/...`。文件名去前缀缩短一半。参照已有的 `scheduler_graph/`（短名 + 目录，证明团队能做对）。

### 🔴 R5 统一范式 main-style → pytest（224 文件）
- 转 `def test_xxx()+assert`，删子进程机制 + main_style_regression_runner.py。**一举三得**：可读性（失败可读）+ 删元机制 + 并行（S1）前置。新文件先禁 main-style（门禁拦）。详见 GOVERNANCE P3 / PLAN 三类归桶。

---

## 第 3 章　对准痛点的推荐顺序

| 步骤 | 方案 | 解决 | 工作量 | 风险 | 即时收益 |
|---|---|---|---|---|---|
| 1 | S0 清工作树+用缓存 | 慢 | 0分钟 | 无 | 消除全量误升级 |
| 2 | S4 精简 focused | 慢 | 5分钟 | 极低 | -1s/push |
| 3 | S3 登记 outside-scope | 慢 | 半天 | 低 | 误升级场景 -150s |
| 4 | S2 收窄 scope | 慢 | 1天 | 中 | 典型 40→15s |
| 5 | R1 强制 docstring | 看不懂 | 分批 | 零 | 100% 自解释 |
| 6 | R2 补 assert 消息 | 难维护 | 分批 | 低 | 失败即可读 |
| 7 | S1 pytest-xdist | 更快 | 2-3天 | 中 | 最坏 178→50s、CI 减半 |
| 8 | R5+R3 main-style转pytest+抽样板 | 统一+S1前置 | 大 | 中 | 见 PLAN P3 |
| 9 | R4 目录重组 | 定位 | 中 | 中 | grep→进目录 |

**前 4 步（约 1.5 天）push 典型 ~40s→~15s，零删除零风险。** 第 5-6 步直击"看不懂"，零到低风险。
