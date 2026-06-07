# 验收报告 — 测试/门禁去冗治理(A,P0–P7)

> 状态:**A 阶段 P0–P7 全部收官**。分支 `cleanup/p3-main-style-to-pytest`,每阶段全门禁 GATE_EXIT=0 +
> 对抗审核零阻塞 + push 验 remote==local。下一步 B(80 条水下债)。各阶段细节见同目录
> `P0_RESULT.md` / `P2_ENGINE_DESIGN.md` / `P6_RESULT.md` 与 `PLAN.md`。

## 一、KPI 仪表盘(治理前 2026-06-05 → 治理后 2026-06-08)

> 治理前基线源:`BASELINE.md` / `baseline.json` / `SPEED_AND_READABILITY.md`(measured_at 2026-06-05)。
> 治理后值:HEAD `05bf1648` 实测。**带 ⚠ 的行口径不同、不可直接相减**,已注明。

### 1.1 规模

| KPI | 治理前 | 治理后 | 来源/口径 |
|---|---|---|---|
| collect 用例数 | 4073 | 3751 | `pytest --collect-only -q tests`(治理前含 197 个会被收集的 main-style item;治理后含 P7 新增 6 个 GUARD 测试) |
| required nodeid | 1790 | 1796 | `iter_required_tests` ∩ collect(P7 新增 anti-regression GUARD +6) |
| serial nodeid | 881 | 770 | `full_test_debt_shards.classify_nodeid`(P6 去 `regression_` 前缀后合法 false-serial shedding) |
| 测试文件(tests/*.py) | 645 | 582 | `find tests -name '*.py'` |
| 收集型测试文件 | — | 543 | 匹配 `python_files` 的文件 |
| `def test_` 函数 | 3158(grep) | 3056(AST) | ⚠ 治理前 grep 行级、治理后 AST 节点级,口径不同 |
| `tests/` 顶层平铺文件 | 626(97%) | 1(仅 conftest.py) | P6 全部迁入 `tests/<模块>/` 子目录 |
| 门禁脚手架行数 | 23026 | 19599 | `cat scripts/run_quality_gate.py run_daily_quality_gate.py sync_debt_ledger.py tools/*.py | wc -l` |
| QualityGate 缓存 | 17MB | 14MB | `du -sh evidence/QualityGate/`(目标 <1MB 未达,属运行时再生产物、`.gitignore` 忽略不入库) |
| scope 通配 `**` | 66 | 收窄至子目录粒度 | P0.3,见 `SPEED_AND_READABILITY.md` |

### 1.2 可读性

| KPI | 治理前 | 治理后 | 来源/口径 |
|---|---|---|---|
| 收集型测试模块 docstring | 4.5%(28/625) | **100%(543/543)** | `ast.get_docstring`;P5.2 docstring-sync + P7 补全最后 14 个 |
| main-style 测试文件 | 197 | **0** | def main 无 def test_ 的收集型文件;P3 转 pytest 清零(23 个 main-style 脚本在 `_scripts_e2e/`、不匹配 `python_files` 不被收集) |
| `find_repo_root`/`sys.path.insert` 样板 | 443(70.9%) | 102 | P6 Phase A 把 185 收集型文件改用 `tests._support.paths.REPO_ROOT`(depth-independent) |
| 裸 assert(无 msg) | ⚠ 85.3%(grep 行级 13696/16065) | ⚠ 84.3%(AST 节点级 12020/14257) | 两口径分母不同,不可直接对比;治理未专项改裸 assert |

### 1.3 时间

| KPI | 治理前 | 治理后 | 来源/口径 |
|---|---|---|---|
| collect-only | 0.87s | 0.77s | `pytest --collect-only -q tests` |
| ⚠ 全量回归 | 330.44s(纯单进程 `pytest -q tests`) | full_test_debt 187.9s(`--sharded --shard-count 3`) | **口径不同**(单进程 vs 3 片);不可写成"330→188 提速" |
| full gate(long gate) | — | executed 9 / failed 0 / 总 210.4s | `evidence/QualityGate/long_gate/summary.json`(head 017c1920,generated 2026-06-08) |
| push / daily gate | 典型 ~40s / 最坏 ~180s(治理前实测) | 未在治理期单独留计时凭证 | ⚠ 诚实标注:P6/P7 阶段 evidence 仅有 full gate 证据;push 提速主要由 P0(scope 收窄)+ P4(xdist 并行)贡献,数据见各自 RESULT |

## 二、P7 防回潮门禁(固化成果不回潮)

`tools/scan_anti_regression_gate.py`,作为质量门禁 command-plan 第 17 步,对「自治理基线 `d4589d77`
以来 `git diff --diff-filter=A` 新增的文件」施加三条硬约束:

1. **main-style**:新增收集型测试文件(匹配 `python_files`)必须含 `def test_`,不得是只有 `def main` 的脚本。
2. **docstring**:新增收集型测试文件必须有模块级 docstring。
3. **scope**:新增生产源文件(core/data/web/desktop/plugins + app/app_new_ui/config.py)必须落在某
   required 回归组 `*_file_scopes` glob 内,否则改它不触发任何回归。

**B-兼容铁律(由 `--diff-filter=A` 机制天然保证)**:门禁只看新增文件,删除/既有文件永不入视野——
B 阶段删 R51 续命测试(`regression_sort_strategy_case_insensitive` / `regression_dispatch_rule_case_insensitive`)
等绝不被阻断,且**零 KEEP/HOLD 禁删白名单依赖**。GUARD 测试 `tests/gate_meta/test_anti_regression_gate.py`
以 tmp git 仓库铁证此点(删既有 + 加新 → 门禁返回 0)。落地态三规则均零违规。

接入:工具登记 `QUALITY_GATE_TOOL_PATHS` + `pyrightconfig.tools.json`(pyright 类检);GUARD 测试登记
`QUALITY_GATE_GUARD_TESTS` + `quality_gate` 组 target_paths/input+tool_file_scopes(编辑工具触发 daily 自测)。

## 三、基线固化(§1.4 SOP)

门禁基线是**代码态**:`tools/test_registry_data.py`(required/startup + `QUALITY_GATE_SELFTEST_PATH`)、
`tools/test_debt_registry.py`(fixed-debt seed)、`开发文档/技术债务治理台账.md`(LIVE 治理台账)——均
git tracked,已随 P1–P7 逐批提交钉死到现状。`evidence/QualityGate/*.json` 是运行时再生产物
(`.gitignore` 显式忽略),不入库、不作基线。

固化 = 跑 §1.4 SOP 五连命令确认当前 HEAD 仍绿,而非重生某 baseline 文件:
```
pytest --collect-only -q tests        # 3751
tools/check_full_test_debt.py --sharded --shard-count 3
tools/verify_required_regressions_from_full_test_debt.py   # 只读核销
scripts/sync_debt_ledger.py check
scripts/run_quality_gate.py --require-clean-worktree        # 17 步全绿
```
P6 终态全门禁已绿、P7 落地后重跑确认仍绿(见提交说明的 GATE_EXIT=0)。
