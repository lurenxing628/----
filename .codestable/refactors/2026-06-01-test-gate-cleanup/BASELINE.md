# 基线测算与成果度量（2026-06-05 重测）

> 配套：`GOVERNANCE.md`（总纲）、`L3_VERDICTS.md`、`SPEED_AND_READABILITY.md`、`L3_verdicts.csv` / `test_inventory.csv` / `baseline.json` / `summary.json`（机器可读）。
> 本版基于**当前仓库实际状态**重测（此前 6-01 旧基线已因 +38 文件、14 次提交而过时）。所有"清理前"数字均为本机实测（非估算），命令附后、可复现。

---

## 第一部分　清理前基线（2026-06-05 实测）

> 环境：`.venv/bin/python` 3.8.10 / pytest 8.3.5 / macOS 10 核 / 单进程无 xdist。

### 1.1 规模基线

| 指标 | 实测值 | 6-01 旧值 | 变化 |
|---|---|---|---|
| 测试文件数（含子目录，排 pycache） | **645** | 607 | +38 |
| `def test_` 函数（grep 口径） | **3158** | 2953 | +205 |
| pytest 收集 item 数（含 main-style + 参数化） | **4073** | 3850 | +223 |
| 测试代码总行数 | **161986** | 155623 | +6363 |
| main-style 子进程文件（有 main 无 test_） | **197** | 196 | +1 |
| 门禁脚手架代码行数（scripts gate + tools/） | **23026** | 22786 | +240 |
| 门禁缓存 evidence/QualityGate/ | **17 MB** | 24 MB | **-7（已自行瘦身）** |
| scope 通配符总数（两个 groups 文件的 `**`） | **66** | — | — |

### 1.2 健康度

全量 **4073 passed / 0 failed**，退出码 0。**工作树干净健康**（不同于 6-01 测时有 13 failed 的脏树——那是当时 resource_dispatch 改到一半）。本版基线是干净基线，可直接作为"不回退"对照。

### 1.3 时间基线（核心 KPI）⏱️

| 操作 | 实测 | 说明 |
|---|---|---|
| `pytest --collect-only` | **0.87s** | 4073 item，每次 push 固定付 |
| **全量测试套件（单进程串行）** | **330.44s（5分30秒）** | 4073 passed / 0 failed |
| commit（pre-commit 框架 + staged ruff + 拦产物） | **~2-3s** | staged ruff 0.59s、全量 ruff 0.07s、框架 stash/restore ~1-1.5s |
| **push（pre-push daily gate）典型** | **~40s** | 改 1 个路由文件命中 3 组 89 文件 665 用例 38.6s |
| **push 最坏** | **~180s（2:57）** | 命中全 7 组 227 文件 1887 用例 |
| push 纯文档改 | ~2s | 0 组，仅 collect+focused |
| CI 全量门禁（参考） | ~300-360s | `run_quality_gate.py --require-clean-worktree --long-gate-cache` |

### 1.4 最慢测试 top（实测 durations）

| 耗时 | 测试 | 性质 |
|---|---|---|
| **19.37s** | `regression_ui_browser_geometry_smoke`（真浏览器几何 smoke） | 真业务，单点拖尾，应隔离非删 |
| 3.18s | `test_ui_browser_geometry_env`（chrome probe spawn） | 真业务 |
| 2.75s / 2.72s | `regression_startup_host_portfile` ×2（启动+端口文件） | 真业务，子进程 |
| 1.73s / 1.59s / 1.58s / 1.51s | runtime_stop_cli / probe_resolution / manual_layout / lock_reloader | 真业务，子进程 |
| **1.1-1.34s × 约 12 个** | `test_long_gate_*_cache`（门禁缓存自指契约） | **门禁测自己,又多又慢** |

### 1.5 时间基线的两个决定性发现

**发现 A：最慢的是真业务测试，不该删。** 最慢 8 名全是真浏览器/启动/runtime 测试——高价值，保留（可隔离）。说明"全量慢"有合理的不可压缩部分。

**发现 B：门禁自指测试又多又慢（双重冗余）。** 最慢榜里 ~12 个是 `test_long_gate_*_cache`（每个 1.1-1.34s），全是"门禁测缓存引擎自己"。它们既是 DROP_WITH_TOOL 候选（删工具随之消失），又拖慢全量尾部——删它们一举两得。

### 1.6 复现命令
```bash
cd /Users/lurenxing/Documents/GitHub/----
PY=.venv/bin/python
$PY -m pytest --collect-only -q tests                       # 收集数+耗时
$PY -m pytest -q tests -p no:cacheprovider --durations=20    # 全量+最慢20（~5.5min）
find tests -name '*.py' -not -path '*__pycache__*' | wc -l   # 文件数
grep -rhE '^[[:space:]]*def test_' tests/ | wc -l            # 函数数
du -sm evidence/QualityGate/                                 # 缓存MB
cat scripts/run_quality_gate.py scripts/run_daily_quality_gate.py scripts/sync_debt_ledger.py tools/*.py | wc -l  # 脚手架行数
$PY scripts/build_test_inventory.py                          # 重建 L2 清单
```

---

## 第二部分　L3 全量裁决分布（645 文件逐个精读）

> 12 路 SubAgent 对**当前 645 个文件**逐个 Read 判定（非抽样），数据见 `L3_verdicts.csv`。

### 2.1 按文件数

| 裁决 | 文件数 | 占比 | 含义 |
|---|---|---|---|
| KEEP | 427 | 66.2% | 真实逻辑，原样保留（※ B-COMPAT 调整后 KEEP=429 / MERGE=37 / DROP_WITH_TOOL=6 / +HOLD_FOR_R51=1，见 `_B_COMPAT_SAFEGUARDS.md` §6；本表为 L3 原始快照）|
| KEEP_TRIM | 123 | 19.1% | 逻辑有价值但夹脆性快照尾，剪尾 |
| MERGE | 39 | 6.0% | 同契约参数化合并（11 多文件簇 + 6 单挂靠）|
| DROP | 38 | 5.9% | 纯快照/死代码，整删 |
| ISOLATE_PERF | 8 | 1.2% | 性能/重 E2E，标记隔离非删 |
| DROP_WITH_TOOL | 7 | 1.1% | 门禁自指，随工具删 |
| REWRITE | 3 | 0.5% | 测保留工具但断言脆，重写 |

### 2.2 按代码行数（更能反映冗余实质）

| 裁决 | 行数 | 占比 |
|---|---|---|
| KEEP | 96991 | 59.6% |
| **KEEP_TRIM** | **45778** | **28.2%** ← 脆性尾巴在这里 |
| MERGE | 6662 | 4.1% |
| DROP | 4658 | 2.9% |
| DROP_WITH_TOOL | 2031 | 1.3% |
| ISOLATE_PERF | 5121 | 3.2% |
| REWRITE | 1390 | 0.9% |
| **直接可删（DROP+DROP_WITH_TOOL+MERGE）** | **13351** | **8.2%** |

### 2.3 清理后预测（保守、准确口径）

| 维度 | 现状 | 清理后 | 降幅 |
|---|---|---|---|
| 测试文件数 | 645 | **~589** | -9%（整删45 + 合并净减11） |
| 测试代码行数 | 161986 | ~140000 | -14%（删 8.2% + 剪 KEEP_TRIM 尾巴约 6%） |

> **重要**：按文件数只降 9% —— 这是真相，不是失败。真正的价值在三处（见 GOVERNANCE §0）：① 提速（纯配置，不删文件）② 剪 KEEP_TRIM 的 28% 脆性尾巴（消除"改文案就红"）③ main-style 转 pytest（35.8% 文件，可读性 + 并行前置）。**文件数从来不是这次治理的主 KPI。**

---

## 第三部分　成果度量表（每阶段后回填实测）

> 每完成一个 Phase，跑第四部分复测脚本，把实测值填入对应列。

### 3.1 时间 KPI（核心）⏱️

| 操作 | 清理前 | P0后 | P3后 | P4(xdist)后 | 目标 |
|---|---|---|---|---|---|
| commit | ~2-3s | | | | <3s |
| push 典型 | ~40s | | | | **<10s** |
| push 最坏 | ~180s | | | | <30s |
| 全量串行 | 330s | | | | — |
| 全量并行 | N/A | — | — | | **<90s** |

### 3.2 可读性 KPI

| 指标 | 清理前 | 治理后目标 |
|---|---|---|
| 模块 docstring 覆盖率 | **4.5%** | 100% |
| 函数 docstring 覆盖率 | 1.4% | — |
| 裸 assert 占比 | **85.3%** | <40% |
| main-style 文件数 | 197 | **0** |
| find_repo_root 样板文件 | 443（70.9%） | 0 |
| 平铺单层目录文件 | 626（97%） | 按模块分目录 |

### 3.3 规模/体积 KPI

| 指标 | 清理前 | 治理后目标 |
|---|---|---|
| 测试文件数 | 645 | ~589 |
| 测试代码行数 | 161986 | ~140000 |
| 门禁脚手架行数 | 23026 | ~7000 |
| 门禁缓存 | 17 MB | <1 MB |

### 3.4 不回退验证（每阶段必满足）
- 全量 passed 数 ≥ 该阶段应有值，**无新增 failed**。
- 门禁 `run_quality_gate.py --require-clean-worktree` 绿。
- 每个合并簇：参数化后断言条数 ≥ 合并前各文件之和（去重）。

---

## 第四部分　复测脚本（每阶段后运行）

```bash
#!/usr/bin/env bash
cd /Users/lurenxing/Documents/GitHub/----
PY=.venv/bin/python
echo "文件数:     $(find tests -name '*.py' -not -path '*__pycache__*' | wc -l | tr -d ' ')"
echo "test_函数:  $(grep -rhE '^[[:space:]]*def test_' tests/ | wc -l | tr -d ' ')"
c=0; for f in tests/regression_*.py; do grep -qE '^[[:space:]]*def main[[:space:]]*\(' "$f" 2>/dev/null && ! grep -qE '^[[:space:]]*def test_' "$f" 2>/dev/null && c=$((c+1)); done; echo "main-style: $c"
echo "脚手架行数: $(cat scripts/run_quality_gate.py scripts/run_daily_quality_gate.py scripts/sync_debt_ledger.py tools/*.py 2>/dev/null | wc -l | tr -d ' ')"
du -sh evidence/QualityGate/ 2>/dev/null | awk '{print "缓存:       "$1}'
# docstring 覆盖率
$PY -c "import glob,ast; fs=[f for f in glob.glob('tests/**/*.py',recursive=True) if '__pycache__' not in f]; h=sum(1 for f in fs if (lambda t: bool(ast.get_docstring(ast.parse(t))) if t.strip() else False)(open(f,encoding='utf-8',errors='replace').read())); print(f'docstring:   {h}/{len(fs)} = {100*h/len(fs):.1f}%')"
# push 耗时模拟
$PY -c "from scripts import run_daily_quality_gate as d; s=d.build_daily_gate_scope(pre_push_changed_paths=['core/services/scheduler/run.py']); p=d.daily_gate_scope_payload(s); print('改 run.py 命中组数/目标数:', p.get('group_count','?'), len(p.get('target_paths',[])))"
# 全量计时(单独跑,~5.5min)
echo "全量计时单独跑: time $PY -m pytest -q tests --durations=20"
```

---

## 第五部分　预期"账单"（最终对决策者）

| 维度 | 清理前（实测） | 治理后（预期） | 节省 | 对体验的意义 |
|---|---|---|---|---|
| **push 典型** | ~40s | **<10s** | -75% | **挡着干活的痛点直接解除** |
| **push 最坏** | ~180s | <30s | -83% | 改 core/template 不再卡 3 分钟 |
| 全量并行 | N/A | <90s | — | CI 与本地全量大降 |
| docstring 覆盖 | 4.5% | 100% | — | **不看内容就知道测什么** |
| 裸 assert | 85% | <40% | — | 失败直接看到期望 vs 实际 |
| main-style | 197 | 0 | — | 失败可读、可并行、删一套元机制 |
| 脚手架代码 | 23026 行 | ~7000 行 | -70% | 门禁可读可维护 |
| 缓存 | 17 MB | <1 MB | -94% | 仓库变轻 |
| 测试文件 | 645 | ~589 | -9% | 减一点，但非主目标 |

**一句话价值**：本次治理**主攻"慢"和"看不懂"**——push 从 ~40s（最坏 180s）压到 <10s（纯配置改、不删测试）、docstring 从 4.5% 到 100%、main-style 35.8% 清零。删/合并是配菜（文件 -9%、行 -8%），但其中删门禁自指测试同时也提速。**零业务覆盖损失**（KEEP 427 个 + §3.4 不回退验证保障）。
