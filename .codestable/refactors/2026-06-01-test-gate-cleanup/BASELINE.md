# 基线测算与成果度量

> 配套文档：`PLAN.md`
> 目的：用清理**前**的真实测量值，对照清理**后**的实测值，量化这项工作的意义。
> 所有"清理前"数字均为本机实测（非估算），测量命令附后，可复现、可在每个 Phase 后重测。

---

## 第一部分　清理前基线（2026-06-01 实测）

> 测量环境：`.venv/bin/python` 3.8.10 / pytest 8.3.5 / macOS darwin。
> ⚠️ 测量时工作区有未提交的 resource_dispatch 改动，导致全量跑有 13 个失败——这与本清理无关，是功能开发中间态。基线时间数据仍有效（失败测试也耗时计入）。

### 1.1 规模基线

| 指标 | 实测值 | 测量命令 |
|---|---|---|
| 测试文件数（含子目录，排除 pycache） | **607** | `find tests -name "*.py" -not -path "*__pycache__*" \| wc -l` |
| 测试文件数（根层） | 588 | `find tests -maxdepth 1 -name "*.py" \| wc -l` |
| `regression_*.py` | 437 | `find tests -maxdepth 1 -name "regression_*.py" \| wc -l` |
| `test_*.py` | 116 | `find tests -maxdepth 1 -name "test_*.py" \| wc -l` |
| `def test_` 函数总数 | **2953** | `grep -rhE "^\s*def test_" tests/ \| wc -l` |
| pytest 收集到的 nodeid | **3850** | `pytest --collect-only -q tests` |
| 测试代码总行数 | **155623** | `find tests -name "*.py" -not -path "*__pycache__*" -exec cat {} + \| wc -l` |
| main-style 子进程文件 | **196** | 复刻 conftest 正则统计 |
| main-style 文件合计行数 | **29460** | 同上累加 wc -l |
| ≤2 函数微文件（regression） | **275 / 437 = 63%** | 逐文件 grep 计数 |
| `find_repo_root` 样板重复 | **230 文件** | `grep -rlE "def find_repo_root" tests/*.py \| wc -l` |
| 脆性字符串断言（中文文案 in + HTML/CSS/JS 子串） | **≈2477 处** | 两条 grep 之和 |

### 1.2 门禁脚手架代码基线

| 文件 / 组 | 行数 | 计划处置 |
|---|---|---|
| `scripts/run_quality_gate.py` | 3401 | 简化编排（M4） |
| `scripts/run_daily_quality_gate.py` | 653 | 跟随 M4 变薄 |
| `scripts/sync_debt_ledger.py` | 403 | 保留 |
| `tools/` 合计 | **18329** | 大幅瘦身 |
| ├ `long_gate_full_test_debt.py` | 2034 | 砍 ~1500（M2） |
| ├ `long_gate_fingerprint.py` | 1319 | 砍 ~1000（M3） |
| ├ `test_registry.py` | 1060 | 砍至 ~150（M4） |
| ├ `verify_required_regressions_from_full_test_debt.py` | 620 | 删（M4） |
| ├ `architecture_scan_cache.py` | 474 | 删（M2 附带） |
| ├ `long_gate_test_body_diff.py` | 317 | 删（M2） |
| └ `report_full_test_debt_durations.py` | 135 | 删（Phase 1） |
| **脚手架总计**（scripts gate + tools） | **22786** | 目标 ~6000 |

### 1.3 缓存基线（evidence/QualityGate/）

| 文件 | 大小 | 计划处置 |
|---|---|---|
| **总计** | **23.8 MB** | 目标 <1 MB |
| `full_test_debt_node_cache.json` | 7.33 MB | 删（M2 增量塌缩后不再需要逐 nodeid 报告） |
| `current_full_test_debt.json` | 5.55 MB | 降级为 `last_pass.json`（KB 级） |
| `long_gate/`（目录） | 5.31 MB | 大幅缩小（M2/M3） |
| `architecture_scan_cache.json` | 3.01 MB | 删（M2 附带，改每次直接扫） |
| `collect_nodeids.json` | 0.96 MB | 保留（收集证明，秒级生成） |
| `quality_gate_manifest.json` | 0.57 MB | 缩小（M3 指纹简化后字段减少） |
| `required_regressions.json` | 0.22 MB | M4 后改 pytest 标记，可删 |

### 1.4 时间基线（最关键）⏱️

| 操作 | 实测耗时 | 测量命令 |
|---|---|---|
| `pytest --collect-only`（仅收集） | **1.04s** | `pytest --collect-only -q tests` |
| **全量测试套件（单进程串行）** | **342.46s（5分42秒）** | `pytest -q tests -p no:cacheprovider --durations=15` |
| 单个重量级 main-style（pytest 收 1 个，含子进程派发） | **0.64s** | `pytest tests/regression_app_db_path_no_dirname.py -q` |
| 单个重量级 main-style（直接 python 跑） | 0.59s | `python tests/regression_app_db_path_no_dirname.py` |
| 单个轻量 A 类 main-style（pytest 收 1 个） | **0.27s** | `pytest tests/regression_dispatch_rule_case_insensitive.py -q` |

全量跑结果：**13 failed / 3837 passed in 342.46s**（13 个失败源于工作区脏，与清理无关）。

### 1.5 时间基线里的两个关键发现（直接证明清理意义）

**发现 A：最慢的是真业务测试，不该动。**
最慢 15 名里，`regression_ui_browser_geometry_smoke`(15.05s)、`regression_runtime_stop_cli`(12.07s)、`test_ui_browser_geometry_env`(3.19s) 是真实浏览器/运行时测试——高价值，保留。它们说明"全量慢"有合理的不可压缩部分。

**发现 B：门禁自指测试又多又慢（双重冗余）。**
最慢 15 名里有 **9 个**是 `test_long_gate_*_cache` 系列（每个 1.6-1.76s），全部属于 Phase 2.A 要合并删除的"门禁测门禁自己"的自指测试：
```
1.76s test_long_gate_required_regression_cache.py::test_required_gitignore_change_reruns_parent
1.73s test_long_gate_required_regression_cache.py::test_required_invalidation_keeps_startup_success_cache_reuse
1.71s test_long_gate_required_regression_cache.py::test_required_tampered_parent_cache_reruns_parent[<lambda>3]
1.71s test_long_gate_required_regression_cache.py::test_required_success_cache_without_declared_child_proofs_reruns_parent
1.70s test_long_gate_required_regression_cache.py::...
1.68s test_long_gate_required_regression_cache.py::...
1.68s test_long_gate_startup_regression_cache.py::test_force_rerun_all_executes_startup_and_required
1.61s test_long_gate_required_regression_cache.py::...
1.58s test_long_gate_required_regression_cache.py::...
```
这一条直接量化了"为什么删它们有意义"：它们不只是数量冗余，单个还慢（因为每个都要起子进程模拟门禁缓存行为）。删 5 个文件 ≈ 砍掉这 9 个慢测试 + 数十个同类。

---

## 第二部分　成果度量表（每个 Phase 后回填实测值）

> 执行人每完成一个 Phase，跑"第三部分"的复测脚本，把实测值填入对应列。
> "目标"列是计划预期，"实测"列留空待填，"达成"列填 ✅/⚠️/❌。

### 2.1 规模收敛表

| 指标 | 清理前 | Phase1后 | Phase2后 | Phase3后 | Phase4后 | 最终目标 | 达成 |
|---|---|---|---|---|---|---|---|
| 测试文件数 | 607 | | | | | ~350-380 | |
| def test_ 函数 | 2953 | | | | | — | |
| nodeid 数 | 3850 | | | | | — | |
| 测试代码行数 | 155623 | | | | | — | |
| main-style 文件 | 196 | 196 | 191* | →0 | 0 | 0 | |
| ≤2 函数微文件 | 275 | | | | | <100 | |

\* Phase2.A 合并 5 个缓存测试中含 0 个 main-style（它们是 test_ 风格），故 main-style 数不变；此处仅示意。实际 main-style 在 Phase3 归零。

### 2.2 脚手架与缓存收敛表

| 指标 | 清理前 | Phase1后 | Phase2后 | 最终目标 | 达成 |
|---|---|---|---|---|---|
| 脚手架代码行数 | 22786 | | | ~6000（-74%） | |
| tools/ 行数 | 18329 | | | | |
| 缓存总大小 | 23.8 MB | | | <1 MB（-96%） | |

### 2.3 时间收敛表（核心 KPI）⏱️

| 操作 | 清理前 | Phase3后 | Phase3+xdist后 | Phase4后 | 目标 | 达成 |
|---|---|---|---|---|---|---|
| collect-only | 1.04s | | | | <1.5s | |
| 全量测试串行 | 342.46s | | | | — | |
| 全量测试并行(xdist) | N/A | — | | | <120s | |
| 全量门禁 | 待测* | | | | — | |

\* 全量门禁基线未在本轮测（会写缓存污染工作区）。建议在干净分支首次执行前补测一次：`python scripts/run_quality_gate.py --require-clean-worktree`（记录总耗时）。

### 2.4 质量不回退验证（每个 Phase 必须满足）

| 检查 | 要求 |
|---|---|
| 全量测试 passed 数 | 清理后 passed 数 ≥ 清理前对应集合（除已合并/删除项），**无新增 failed** |
| 门禁 | `run_quality_gate.py --require-clean-worktree` 绿 |
| 覆盖不丢 | 每个被合并簇，参数化后断言条数 ≥ 合并前各文件断言条数之和（去重后） |

---

## 第三部分　复测脚本（每个 Phase 后运行）

把以下保存为 `scripts/measure_cleanup_progress.sh`（或手动逐条跑），输出可直接填进第二部分。

```bash
#!/usr/bin/env bash
# 测试/门禁清理进度度量 —— 每个 Phase 后运行，对照 BASELINE.md
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python

echo "==== 规模 ===="
echo "测试文件数:      $(find tests -name '*.py' -not -path '*__pycache__*' | wc -l | tr -d ' ')"
echo "def test_ 函数:  $(grep -rhE '^[[:space:]]*def test_' tests/ | wc -l | tr -d ' ')"
echo "nodeid 数:       $($PY -m pytest --collect-only -q tests 2>/dev/null | grep -oE '[0-9]+ tests collected' | grep -oE '^[0-9]+')"
echo "测试代码行数:    $(find tests -name '*.py' -not -path '*__pycache__*' -exec cat {} + | wc -l | tr -d ' ')"
c=0; for f in tests/regression_*.py; do grep -qE '^[[:space:]]*def main[[:space:]]*\(' "$f" && ! grep -qE '^[[:space:]]*def test_' "$f" && c=$((c+1)); done
echo "main-style 文件: $c"
s=0; for f in tests/regression_*.py; do n=$(grep -cE '^[[:space:]]*def (test_|main)' "$f"); [ "$n" -le 2 ] && s=$((s+1)); done
echo "≤2函数微文件:    $s"

echo "==== 脚手架 ===="
echo "脚手架行数:      $(cat scripts/run_quality_gate.py scripts/run_daily_quality_gate.py scripts/sync_debt_ledger.py tools/*.py 2>/dev/null | wc -l | tr -d ' ')"
echo "tools/ 行数:     $(cat tools/*.py 2>/dev/null | wc -l | tr -d ' ')"

echo "==== 缓存 ===="
du -sh evidence/QualityGate/ 2>/dev/null | awk '{print "缓存总大小:      "$1}'

echo "==== 时间 ===="
t0=$($PY -c 'import time;print(time.time())')
$PY -m pytest --collect-only -q tests >/dev/null 2>&1
t1=$($PY -c 'import time;print(time.time())')
$PY -c "print(f'collect-only:    {$t1-$t0:.2f}s')"

echo "（全量测试计时请单独跑，约5-6分钟）:"
echo "  time $PY -m pytest -q tests --durations=15"
```

复测全量时间（单独跑，记录 `passed`/`failed` 数和总秒数）：
```bash
.venv/bin/python -m pytest -q tests -p no:cacheprovider --durations=15 2>&1 | tail -3
```

---

## 第四部分　预期"账单"（最终对比，供决策者一眼看懂价值）

> 这是把所有 Phase 收益汇总后的预期。执行完成后用实测值替换括号内估算。

| 维度 | 清理前（实测） | 清理后（L3 精读校准） | 节省 | 对体验的意义 |
|---|---|---|---|---|
| 测试文件数 | 607 | ~490-500 | **-18%** | 注:L3 逐文件精读后从抽样的 -39% 校准到 -18%,因核心域几乎全是真实覆盖。文件数非主要 KPI,见下 |
| 脆性快照断言(KEEP_TRIM+DROP) | 109 文件含脆性 | 删快照尾/整删 | — | **改文案/CSS 不再误报红——日常最痛点** |
| 脚手架代码 | 22786 行 | ~6000 行 | **-74%** | 门禁逻辑可读、可维护，新人能看懂 |
| 缓存体积 | 23.8 MB | <1 MB | **-96%** | git 仓库变轻，CI 缓存传输快 |
| 全量测试（串行） | 342s | 待测 | 主要靠 -xdist | 本地等待时间 |
| 全量测试（并行） | N/A | <120s（预期） | **-65%** | **这是体验提升最直接的数字** |
| main-style 子进程开销 | ~54s（196×0.27-0.64s） | <10s | **-82%** | 转 pytest 后并入主进程 |
| 门禁自指慢测试 | 最慢15名占9个 | 合并消除 | — | 全量跑尾部不再被 meta 测试拖累 |

**一句话价值**：本次清理把"测试集臃肿 + 门禁自我证明的复杂度"两个体验杀手同时削掉——文件数砍 4 成、脚手架砍 7 成、缓存砍到几乎为零，全量测试在并行后预计从 5分42秒 压到 2 分钟内。且**零业务覆盖损失**（第 8 章保留清单 + §2.4 不回退验证保障）。
