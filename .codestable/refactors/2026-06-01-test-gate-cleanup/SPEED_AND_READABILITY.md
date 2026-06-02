# 提速 + 可读性专项方案（对准真实痛点）

> 制定：2026-06-01
> 触发：用户明确两个真痛点 —— ①每次 commit/push 跑测试太慢挡着干活 ②不看内容根本不知道测什么、难维护
> **重要**：本方案与 `L3_VERDICTS.md`（删/合并测试）是**不同方向**。删测试优化的是"代码体积",但**对这两个痛点几乎没用**。本方案直击时间和可读性。

---

## 第 0 章　颠覆性发现：慢的不是测试，是"选哪些测试跑"的配置

### 0.1 实测数据（本机坐实，非估算）

| 你以为在等的 | 实测真相 |
|---|---|
| "测试太多所以慢" | ❌ 3121 个测试加起来才 **27 秒**，单个均 8.7ms |
| commit 慢 | ❌ pre-commit ruff 只要 **0.07s**，已是 Rust 极限，不用动 |
| push 慢 | ✅ **真痛点**：典型 ~95s，最坏 107s |

### 0.2 push 慢的真正机制（坐实）

链路：`git push` → pre-push hook → `scripts/run_daily_quality_gate.py`（按改动选测试）。

固定底噪只有 ~2.5s。**全部波动来自"impact 选择"步骤**——它根据你改了哪些文件，决定跑哪些测试组。问题出在这张映射表 `tools/test_registry_groups_scheduler.py` / `test_registry_groups_misc.py`：

每个测试组登记的"我依赖哪些源文件"用了**巨型目录通配**：
```
"static/**/*"              ← 出现 3 次（改任何 static 文件命中 3 组）
"web/viewmodels/**/*.py"   ← 出现 3 次
"templates/**/*.html"      ← 出现 3 次
"core/services/scheduler/**/*.py"  ← 出现 2 次
```
**后果**：你改一个 `.py` 文件，daily gate 以为"这影响了 5-7 个组、135 个文件"，于是跑掉近 100 秒。实测：
```
改 core/services/scheduler/config_service.py    → 命中 7 组 135 文件 (~95s)
改 web/viewmodels/scheduler_resource_dispatch.py → 命中 5 组 111 文件 (~75s)
改 static/js/resource_execution.js（你正在改的）  → 命中 7 组 135 文件 (~95s)
```

### 0.3 第二个反讽：每次 push 强制跑的 8 个固定测试，4 个是门禁自指

`run_daily_quality_gate.py:29 FOCUSED_PYTEST_NODEIDS` 每次 push 雷打不动跑 8 个 nodeid，其中 4 个是 `test_long_gate_*`——测门禁缓存引擎自己，和你改的业务代码无关。

### 0.4 结论
**push 慢与测试数量无关，是 impact 配置太粗 + 固定跑无关自指测试。改配置即可，一个测试都不用删。**

---

## 第 1 章　提速方案（按性价比排序，全部实测支撑）

### 🟢 方案 S1：收窄 impact scope 通配 —— 性价比最高，零依赖零删除

**问题**：`tools/test_registry_groups_scheduler.py` + `test_registry_groups_misc.py` 共 63 处 `**` 通配。
**做法**：把每个组的 `input_file_scopes` 从"整个目录树"改成"这个组真正依赖的那几个文件/子目录"。例如 scheduler_config 组只关心 `core/services/scheduler/config*.py`，不该写 `core/services/scheduler/**/*.py`。
**收益**：典型改动从命中 5-7 组（~95s）降到 1-2 组（~10-15s）。**省 ~80s**。
**风险**：中——切太细可能漏跑相关回归。缓解：CI 全量兜底已存在（GitHub Actions 跑全量），本地快门禁漏一点由 CI 补。建议按每个组的 `target_paths`（它实际跑哪些测试）反推最小 scope。
**工作量**：1 天。改的是配置，不碰测试代码。
**验证**：改完用几个代表性文件实测 impact 选组数：
```bash
# 模拟改一个文件，看 daily gate 选多少组
.venv/bin/python -c "from scripts import run_daily_quality_gate as d; \
  scope=d.build_daily_gate_scope(pre_push_changed_paths=['core/services/scheduler/config_service.py']); \
  print(d.daily_gate_scope_payload(scope))"
```

### 🟢 方案 S2：登记 outside-scope 文件 + 未知路径设小默认 —— 零依赖

**问题**：未登记 scope 的路径直接触发 `all_required_groups=True`（近全量 107s）。本分支有 14 个新文件未登记。
**做法**：(a) 把未登记文件登记进对应组；(b) 把"未知路径"兜底从"跑全部组"改成"只跑 quality_gate 自测组 + focused"。
**收益**：新增文件场景 107s → ~10s。**省 ~95s**。
**风险**：低（CI 全量兜底）。
**工作量**：半天。

### 🟢 方案 S3：精简 FOCUSED_PYTEST_NODEIDS —— 5 分钟

**问题**：每次 push 固定跑的 8 个里，4 个是 `test_long_gate_*` 门禁自指，与业务无关。
**做法**：把这 4 个门禁自指移出 focused（它们在 CI 全量里仍会跑）；focused 只保留真正该每次把关的业务冒烟（如 architecture_fitness、batches viewmodel）。
**收益**：每次 push 省 ~1.5s（小，但是纯赚）。
**风险**：极低。

### 🟡 方案 S4：pytest-xdist 并行 —— 省最多绝对值，需 vendor wheel

**现状**：未装 xdist，本机 10 核，全量串行 342s。
**做法**：`pytest-xdist` + `execnet` 都是纯 Python wheel（符合 Win7 离线），下载放 `vendor/wheels/`，门禁跑 `pytest -n auto --dist loadgroup`。
**收益**：worst-case impact 107s → ~20-25s；CI 全量 309s in-test → ~60s。
**前置**：必须先做 Phase 3（main-style 转 pytest）或至少补 conftest 的 DB/端口隔离 fixture——27 个测试用固定端口/共享 DB，并行会抢占 flaky。用 `tools/full_test_debt_shards.py` 已有的 serial/parallel 分类喂 xdist。
**风险**：中（隔离没做好会 flaky）。
**工作量**：2-3 天（含补隔离）。

### 🟡 方案 S5：隔离最慢的浏览器/runtime 测试 —— 仅对 CI 有效

**事实**：`ui_browser_geometry_smoke`(10.8s)、`startup_host_portfile`×2(5.5s)、`runtime_stop_cli`(1.7s) 是最慢的。
**关键**：它们**已经不在 daily gate 里**，只在 CI/长门禁跑。所以对 push 提速无帮助，只省 CI ~16s。
**做法**：标 `@pytest.mark.slow`，CI 分独立 job。
**优先级**：低（不解决 push 痛点）。

### 提速方案落地顺序
1. **S3（5分钟）→ S2（半天）→ S1（1天）**：纯配置，零依赖零删除，push 典型场景 ~95s → ~15s。**这是你"挡着干活"的直接解药。**
2. **S4（2-3天）**：要更快再上并行，CI 也受益。
3. **S5**：CI 优化，最后做。

---

## 第 2 章　可读性方案（对准"不看内容不知道测什么"）

### 2.1 实测的可读性病灶

| 病灶 | 实测 | 后果 |
|---|---|---|
| 模块 docstring 覆盖率 | **4.7%**（26/554） | 没有"这文件测什么"的一句话说明 |
| 函数 docstring | 1.1% | 函数级也没说明 |
| 裸 assert（无消息） | **85%**（13262/15606） | 失败只看到 `AssertionError`，不知道期望 vs 实际 |
| main-style 风格 | 35%（196 文件） | 裸 assert 经子进程跑，失败信息最差 |
| `find_repo_root` 样板 | 219 文件重复 | 12 行噪声淹没正文，import 藏函数体内 |
| 平铺目录 | 592 文件挤在 tests/ 根 | 定位只能靠 grep |
| 文件名 | 中位 46 字符、堆 5-6 个词、实现黑话 | 看名字猜不出测什么 |

### 2.2 可读性方案（按性价比，#1#2 直击痛点）

### 🟢 方案 R1：强制模块 docstring「一句话测什么」—— 根治痛点，零风险

**做法**：每个测试文件首行加 `"""测 X 在 Y 条件下应 Z。"""`。加一条门禁校验（项目已有 `regression_aps_three_gap_docs_quality_gate.py` 这类文档门禁可照搬）拦住无 docstring 的新文件。
**收益**：**直接消灭"不看内容不知道测什么"**——从 4.7% 到 100%。这是唯一能根治你原话痛点的低成本动作。
**风险**：零（只加注释，不碰逻辑），可增量推进。
**标杆**：`regression_app_db_path_no_dirname.py:1-7` 已有的好 docstring——两行说清"测什么+为什么存在+防哪个历史 bug"。
**工作量**：可分批，每批几十个文件。也可先用 AI 批量生成首句 docstring 再人工核。

### 🟢 方案 R2：裸 assert 补消息 —— 失败即可读

**做法**：新 assert 一律带消息；存量优先补 main-style 文件（pytest 文件有自省可缓）。
**收益**：失败时直接看到期望 vs 实际，砍掉"读源码+加 print+重跑"的调试循环。
**风险**：低。

### 🟡 方案 R3：抽样板为公共 fixture

**做法**：219 份 `find_repo_root` + 289 份 `sys.path.insert` 收敛到 conftest 一个 fixture。
**收益**：每文件省 ~12 行噪声，正文立刻浮现。
**注意**：main-style 因子进程机制依赖自带引导，需配合 R5 一起做。

### 🟡 方案 R4：目录按被测模块重组

**做法**：592 文件迁进 `tests/<模块>/<子模块>/`，对齐 `core/services/scheduler/...` 源码结构。迁移后文件名去冗余前缀（`regression_gantt_zoom_range_guard.py` → `gantt/zoom_range_guard.py`，短一半）。
**收益**：定位从"grep 592 文件"→"进目录看十来个"；天然索引；改哪个模块就知道去哪个测试目录。
**成本**：动 import 路径，一次性规模操作，放 R1/R2 之后。
**参照**：`tests/scheduler_graph/`（18 文件组织良好）证明项目有能力做好，只是没推广。

### 🔴 方案 R5：统一范式 main-style → pytest

**做法**：196 个 main-style 转 `def test_xxx()+assert`，删子进程收集机制（conftest.py:51-105）+ main_style_regression_runner.py。
**收益**：消灭最差失败体验（子进程退出码+裸 AssertionError）；享受 pytest 自省/参数化；删一整套元机制。**同时这也是 S4 并行的前置**（双重收益）。
**成本**：最高，196 文件逐个改+验证。
**策略**：新文件先一律禁止 main-style（加门禁拦），存量分批转。详见 `PLAN.md` Phase 3（已有完整的 A/B/C 三类归桶）。

---

## 第 3 章　对准痛点的推荐执行顺序

把"立竿见影、零风险"的排前面：

| 步骤 | 方案 | 解决 | 工作量 | 风险 | 即时收益 |
|---|---|---|---|---|---|
| 1 | S3 精简 focused | push 慢 | 5分钟 | 极低 | -1.5s/push |
| 2 | S2 登记 outside-scope | push 慢 | 半天 | 低 | 新文件场景 -95s |
| 3 | S1 收窄 scope 通配 | push 慢 | 1天 | 中 | 典型 -80s（95→15s）|
| 4 | R1 强制 docstring | 看不懂 | 分批 | 零 | 100% 文件自解释 |
| 5 | R2 补 assert 消息 | 难维护 | 分批 | 低 | 失败即可读 |
| 6 | S4 pytest-xdist | 更快 | 2-3天 | 中 | worst -85s、CI减半 |
| 7 | R5+R3 main-style转pytest+抽样板 | 统一+前置S4 | 大 | 中 | 见 PLAN.md Phase 3 |
| 8 | R4 目录重组 | 定位 | 中 | 中 | grep→进目录 |

**前 3 步（1.5 天）就能把 push 从 ~95s 砍到 ~15s，且不删任何测试、不碰测试逻辑。** 这是对你"挡着干活"最快的解药。

**第 4-5 步**直击"不看内容不知道测什么"，零到低风险，可增量。

**第 6 步起**是更深的结构改造，与 `PLAN.md` 的 Phase 3 衔接。

---

## 第 4 章　与之前文档的关系

| 文档 | 优化目标 | 对你痛点的作用 |
|---|---|---|
| **本文档 SPEED_AND_READABILITY.md** | **时间 + 可读性** | ✅ 直击两个真痛点 |
| `PLAN.md` | 代码体积/结构 | Phase 3（main-style 转换）与本文档 S4/R5 重合，是前置 |
| `L3_VERDICTS.md` | 删/合并测试 | 对时间帮助小（测试本身才占 27s）；价值在减脆性快照（间接帮可读性）|
| `BASELINE.md` | 度量 | 需补"push 耗时"作为核心 KPI |

**修正认知**：之前三份文档围绕"删多少测试/砍多少行"，但实测证明**那不是你痛点的解药**。本文档才是。删测试仍有价值（减脆性、降维护面），但**优先级应让位于 S1-S3 提速 + R1-R2 可读性**。

---

## 第 5 章　待你拍板

1. **是否先做前 3 步提速（S3→S2→S1，1.5 天，零删除）？** 这是 push 慢的直接解药。
2. **可读性先做 R1（docstring）还是 R2（assert 消息）？** 我建议 R1，因为它直接对应你"不看内容不知道测什么"的原话。
3. **S1 收窄 scope 有"漏跑"风险**——你能接受"本地快门禁漏一点、由 CI 全量兜底"吗？还是要更保守（scope 收窄幅度小一点、宁可慢一点也不漏）？
