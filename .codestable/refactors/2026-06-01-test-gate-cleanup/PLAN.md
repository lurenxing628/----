# 测试与门禁去冗 —— 执行明细计划（2026-06-05 重做）

> 配套：`GOVERNANCE.md`（总纲入口，先读它）、`L3_VERDICTS.md`（裁决依据）、`BASELINE.md`（度量）、`SPEED_AND_READABILITY.md`（提速/可读性细节）、`L3_verdicts.csv`（文件级明细）。
> 本文是各阶段的执行明细。文件清单从 `L3_verdicts.csv` 取（按 verdict/merge_cluster 筛），不在此重复罗列长清单。
> 基于当前仓库实测：645 文件 / 3158 函数 / 4073 item / 197 main-style / 脚手架 23026 行 / 缓存 17MB / 全量 330s / push 典型 40s 最坏 180s。

---

## 第 1 章　通用规则

### 1.1 环境（已验证）
- `.venv/bin/python` 3.8.10、pytest 8.3.5、ruff 0.15.11、**未装 pytest-xdist**
- pre-commit/pre-push hook 已装；门禁入口 `scripts/run_quality_gate.py`（对外 CLI 不可改）

### 1.2 隔离（重要）
门禁要求 clean worktree，且 `_changed_paths()` 会把暂存的 outside-scope 文件（如本治理产出的 `.codestable/*.csv`）算进 impact → 强制全量。**开工前两选一**：
- 甲：先把手头改动 + 治理产出提交干净。
- 乙：`git worktree add` 隔离治理工作。
每阶段独立分支：`git checkout -b cleanup/pN-<topic>`。

### 1.3 每阶段三连验证
```bash
cd /Users/lurenxing/Documents/GitHub/----
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -3   # 收集不掉
.venv/bin/python -m pytest tests/ -k "<受影响域>" -q                # 定向
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree # 全量兜底
```

### 1.4 基线刷新 SOP（每次删/改测试后必做，否则门禁红）
```bash
.venv/bin/python -m pytest --collect-only -q tests > /dev/null
.venv/bin/python tools/check_full_test_debt.py --sharded --shard-count 3
.venv/bin/python tools/verify_required_regressions_from_full_test_debt.py  # P2 后为只读核销 CLI(不写文件)
.venv/bin/python scripts/sync_debt_ledger.py check
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```
> P2.2-M4 后人工直跑必跑回归的入口：`pytest -m required`（conftest 按 registry 分组自动打标，1821 个 nodeid）。

### 1.5 红线
- 不改 run_quality_gate.py 对外 CLI
- 不删 `L3_VERDICTS.md` 第五章 load-bearing 脚本
- 永久保留：`test_architecture_fitness.py`、`scheduler_graph/`、全部 migration、operation_execution 并发测试、各域高价值算法测试
- **🔴 B-兼容红线**：P1/P2/P3/P5/P6 前必读 `_B_COMPAT_SAFEGUARDS.md`；`regression_sort_strategy_case_insensitive.py` 标 `HOLD_FOR_R51` 不合并不删（绑 R51 灵魂线）；严禁裸筛 csv `verdict` 后机械 `git rm`（`DROP_WITH_TOOL`/`HOLD_FOR_R51` 都不可删）。

---

## 第 2 章　P0 — 配置层提速（最快见效，零删除）

> 详见 `SPEED_AND_READABILITY.md` 第 1 章。背景：push 慢的真因是 scope 通配过宽（66 个 `**`）+ 工作树污染升全量，非测试多。

### P0.0 清工作树（0 分钟）
提交或移出暂存区的 outside-scope 文件（治理产出的 `.codestable/*.csv` 等），消除"强制全量"。

### P0.1 精简 FOCUSED_PYTEST_NODEIDS（5 分钟）
`scripts/run_daily_quality_gate.py` 的 `FOCUSED_PYTEST_NODEIDS`（8 个，5 个门禁自指）移除 `test_long_gate_*`/`test_architecture_fitness`（CI 全量仍跑），留真业务冒烟。

### P0.2 登记 outside-scope + 未知路径设小默认（半天）
- 找出触发全量的未登记路径：
```bash
.venv/bin/python -c "from scripts import run_daily_quality_gate as d; import glob; \
  [print(p) for p in glob.glob('core/**/*.py',recursive=True)+glob.glob('web/**/*.py',recursive=True) \
   if d.build_daily_gate_scope(pre_push_changed_paths=[p]).get('all_required_groups')][:40]"
```
- 登记进对应组，未知路径兜底改为"仅 quality_gate 自测组 + focused"。

### P0.3 收窄 scope 通配（1 天，主菜）
- 编辑 `tools/test_registry_groups_scheduler.py`（36 个 `**`）+ `test_registry_groups_misc.py`（30 个 `**`）。
- 把 `core/**/*.py`、`web/viewmodels/**/*.py`、`static/**/*`、`templates/**/*.html` 拆到子目录粒度。反推法：看该组 `target_paths` → 追测试 import 的源模块 → scope 只列这些。
- **保守档起步**：精确到子目录（非文件），漏跑风险小。
- 验证：
```bash
.venv/bin/python -c "from scripts import run_daily_quality_gate as d; \
  [print(f, '->', len(d.daily_gate_scope_payload(d.build_daily_gate_scope(pre_push_changed_paths=[f])).get('target_paths',[])),'文件') \
   for f in ['core/services/scheduler/run.py','web/viewmodels/scheduler_resource_dispatch.py','static/js/resource_execution.js','templates/gantt.html']]"
```
命中目标数应从 180-227 降到 40-90。

### P0.4 验证 + 提交
```bash
.venv/bin/python -m pytest tests/regression_quality_gate_scan_contract.py -q  # 门禁scope契约自检
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
git commit -m "perf: P0 收窄impact scope+清污染,push快门禁提速"
```

---

## 第 3 章　P1 — 死代码清除 + docstring（零风险，分批）

### P1.1 删 DROP（38 个）
清单 `L3_verdicts.csv` 筛 `verdict=DROP`。分三批（见 `L3_VERDICTS.md` §2）：模板快照(24)、反向结构守卫(5)、文档/死代码(剩余)。
```bash
# 提取并 review
.venv/bin/python -c "import csv; [print(r['file']) for r in csv.DictReader(open('.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv')) if r['verdict'].strip()=='DROP']"
# 删前逐个确认不被 import
```
反向结构守卫（test_phase6_no_*、sp05/sp06）若约束有价值，转 ruff 规则。删后跑 §1.4 基线刷新。

### P1.2 强制 docstring（分批，可 AI 辅助）
- 先给 KEEP 的 429 个高价值文件加首句 docstring（B-COMPAT 调整后 KEEP=429，标杆 `regression_app_db_path_no_dirname.py:1-7`）。
- AI 批量生成草稿 + 人工核。KEEP_TRIM/MERGE 文件在各自阶段顺带加。

### P1.3 验证 + 提交
```bash
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -3  # 收集数减~38
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
git commit -m "test: P1 删快照/死代码 + 补docstring"
```

---

## 第 4 章　P2 — 门禁元系统瘦身（删自指=提速+减体积）

> 背景：DROP_WITH_TOOL 7 个是门禁自指，且 KEEP_TRIM 里 `test_run_quality_gate.py`(2970行)、`test_full_test_debt_registry_contract.py`(1449行)、`test_git_hook_checks.py`(970行) 都是门禁自测。这批又慢（最慢榜 ~12 个 test_long_gate_*_cache）。

### P2.1 缓存条目模板族合并
`L3_verdicts.csv` 看 `long_gate_cache_engine` / `long_gate_*` 相关簇：结构同构，共享 `tests/long_gate_cache_helpers.py`，参数化合并。**连带**：`tools/full_test_debt_shards.py` 硬编码的文件名同步删。

### P2.2 脚手架瘦身（每条独立 commit）
- M2 增量引擎塌缩：删 `long_gate_test_body_diff.py`、简化 `long_gate_full_test_debt.py`，缓存退化"指纹命中整体复用否则全跑"。
- M3 指纹简化：`long_gate_fingerprint.py` 删 Chrome 指纹部分。
- M4 必跑回归改 `@pytest.mark.required`，删 `verify_required_regressions_from_full_test_debt.py` + `test_registry.py` 大半。**改门禁编排，双跑验证**。
  - **🟠 B-兼容 HIGH（B-14，见 `_B_COMPAT_SAFEGUARDS.md` §8）**：`scripts/run_quality_gate.py:25` 是 `verify_required_regressions_from_full_test_debt` 的**无条件顶层 import**（与 B-12 的 :26 同型，首版漏钉）。删该模块必须在**同一原子提交**里改接/移除 `:25` import + `:1858` 使用点 + §1.4 SOP 第 3 行（换 `pytest -m required`），否则 `run_quality_gate` 一 load 即 ImportError，连 A 自己的 P2.4 验证都起不来。落地验 `python -c "import scripts.run_quality_gate"` 不炸。
- **塌缩 architecture_scan_cache（⚠B-12 HIGH，见 `_B_COMPAT_SAFEGUARDS.md`）**：不可裸删——`test_architecture_fitness.py`（已锁 KEEP）与 `run_quality_gate.py:26` live 门禁经 `quality_gate_operations.py:5` 三段顶层硬 import 直连它，裸删 = collection-error / live 门禁 ImportError。须在删模块的**同一原子提交**里保留 `architecture_*_scan_map`/`aggregate_architecture_scan`/`scan_files_with_cache` 公共 API + 改接 `quality_gate_operations.py:5`、`run_quality_gate.py:26` import + 同步 `test_architecture_scan_cache.py`。

### P2.3 DROP_WITH_TOOL 随工具删（7 个）
见 `L3_VERDICTS.md` §3。**修正**：`test_architecture_fitness.py` 保留（验证业务架构合规）；`test_regression_main_isolation_contract.py` 待 P3 删 collector 后清理。

### P2.4 验证
```bash
.venv/bin/python -m pytest tests/test_architecture_fitness.py --collect-only  # B-12:删cache后collection不炸(锁KEEP的守卫仍可import)
.venv/bin/python -c "import scripts.run_quality_gate"  # B-14:删verify_required/architecture_scan_cache后顶层import(:25/:26)不炸
du -sh evidence/QualityGate/   # 应大幅缩小
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

---

## 第 5 章　P3 — main-style → pytest（可读性 + 并行前置）

> 背景：197 个 main-style（35.8%）是"看不懂"+"失败信息差"最大来源，也是 P4 并行前置。conftest 子进程机制在 `tests/conftest.py:51-106`（pytest_collect_file/RegressionMainFile/RegressionMainItem）。

### P3.1 先转污染源 C 类（最先，防同进程串味）
从 `L3_verdicts.csv` 找 main-style 中 monkeypatch 全局且无 finally 的（如 ortools sys.modules 注入、schedule_service 模块函数替换、subprocess.Popen 全局替换）→ 改 `monkeypatch` fixture。

### P3.2 抽共享 fixture 到 conftest（同时做 R3）
当前 conftest 无 fixture。加 `mem_conn`/`db_conn`/`app_client`（monkeypatch.setenv 设 APS_* 自动还原、delitem sys.modules 强制重 import）。消灭 443 份 find_repo_root 样板。

### P3.3 批量转换（每批 ~20 文件一 commit）
`def main()`→`def test_xxx()`、删样板、裸 assert 保留（转后自省=自动可读，**同时完成 R2**）、给每文件加 docstring（**同时完成 R1**）。

### P3.4 移除 collector
全转完后删 `conftest.py:51-106` + `main_style_regression_runner.py`，并清理 `test_regression_main_isolation_contract.py`。

> **🔴 B-兼容 BLOCKER（见 `_B_COMPAT_SAFEGUARDS.md` §8）**：删 collector 前必须确认**无残留 main-style `regression_*` 文件**（`def main` 无 `def test_`），否则它们会被标准收集器静默跳过（收集 0 项、exit 0、零报错=假绿）。**特别是 B-1 锁了 `HOLD_FOR_R51` 的 `regression_sort_strategy_case_insensitive.py` 与 `regression_dispatch_rule_case_insensitive.py`（R51 续命测试，A 不许转/删）——P3.3 不会转它们 → P3.4 删 collector 后它们静默归零，R51（Batch-7，远晚于 P3）执行时删的是尸体、中间回归无网。** 二选一:①P3.3 把这两文件也转 pytest（`def main→def test_`、`:25` 坏值断言体逐字保留，不违 B-1 语义）;②删 collector 前加守卫断言「无残留 main-style」。删后跑 `pytest tests/regression_sort_strategy_case_insensitive.py --collect-only` 应 >0 用例。

### P3.5 验证
```bash
.venv/bin/python -m pytest -q tests 2>&1 | tail -10  # 全量,对比基线无新fail(查泄漏)
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

---

## 第 6 章　P4 — 启用并行 xdist

> 前置：P3 完成 + serial 隔离。详见 `SPEED_AND_READABILITY.md` S1。
- vendor `pytest-xdist`+`execnet` wheel，登记 requirements-dev.txt
- serial 测试标 `@pytest.mark.serial`（用 `tools/full_test_debt_shards.py` 已有分类），门禁 `pytest -n auto --dist worksteal`
- 验证：跑 3 次确认无 flaky

---

## 第 7 章　P5 — 业务合并 + 剪脆性尾

### P5.1 MERGE 簇合并（11 多文件簇 + 6 单挂靠）
清单见 `L3_VERDICTS.md` §4。**对账**：`real_db_replay_e2e` 簇的 e2e 是 load-bearing 保留、删 check/smoke。每簇抽 fixture → 参数化 → git rm → 核对断言不丢。

> **⚠ B-兼容（见 `_B_COMPAT_SAFEGUARDS.md`）**：
> - `sort_strategy_case_insensitive` 簇**已解散**：`regression_sort_strategy_case_insensitive.py`→`HOLD_FOR_R51`（绑 R51 灵魂线整体退场，A 不动）；`priority` 文件→独立 KEEP（存活算法，契约不同）。**B-1 BLOCKER，勿重新合并。**
> - `workbench_links_viewmodel` 簇合并**禁对 guard 四态断言去重**（B-2 / R54·LB02·LB05），记录函数迁入位置，**与 B 的 G04/G05 错开窗口**。
> - `workbench_context_propagation` 簇标 `R57-PINNED 勿去重`，逐条保留 `:346/:347/:353`（B-6）。
> - `scheduler_route_registration` 簇合并 commit 记录 wrapper import 锚点新位置（B-5 / R43）。

### P5.2 KEEP_TRIM 剪脆性尾（123 个，28.2% 行）
清单 `L3_verdicts.csv` 筛 `verdict=KEEP_TRIM`。保留真实断言、删脆性尾。重点大文件见 `L3_VERDICTS.md` §5（test_run_quality_gate 2970行、win7_launcher 1919行、frontend_ui_language_polish 845行等）。

### P5.3 REWRITE(3) + ISOLATE_PERF(8)
见 `L3_VERDICTS.md` §6/§7。性能/重 E2E 标 `@pytest.mark.perf`/`slow` 从 push 剔除。

---

## 第 8 章　P6 — 目录重组 + 命名规范

- 626 文件迁 `tests/<模块>/<子模块>/`（参照 scheduler_graph/）。文件名去前缀。
- 后缀词表收敛 3 类：`_contract`/`_guard`/`_smoke`，废弃同义词。名字写可观察行为。
- 一次性脚本迁移 + 改 testpaths + 全量收集验证。
- **⚠ B-兼容（B-3，见 `_B_COMPAT_SAFEGUARDS.md`）**：P6 会令 B 约 **199 个 dossier 锚点**路径整体失效（git mv 内容不变，按符号可重定位）。**必须等全部 P0-P7 跑完、tests 定稿后再启动 B，严禁迁移中途穿插 B**；迁移脚本须**产出「旧路径→新路径」映射表**交给 B 一次性重生成锚点；提醒 B 把写死 `tests/<文件>.py` 的 ~22 条 grep 命令升级为 `rg -rn PATTERN tests/`。

---

## 第 9 章　P7 — 固化 + 防回潮门禁

- 新文件门禁（加进 quality_gate_scan）：①拦 main-style 新文件（须有 def test_）②强制 docstring ③新源文件须有 scope 覆盖
- **⚠B-兼容**：P7 防回潮门禁**不得拿 KEEP / `HOLD_FOR_R51` 清单当「禁删既有测试」白名单**——B 仍要删 R51 续命测试（`regression_sort_strategy_case_insensitive.py`、`regression_dispatch_rule_case_insensitive.py`）等,门禁只拦「新增违规」,不锁既有测试的删除。
- 基线固化（§1.4 SOP）
- 写 acceptance.md，KPI 仪表盘填治理后实测值

---

## 第 10 章　风险登记

| 风险 | 阶段 | 缓解 |
|---|---|---|
| scope 收窄致漏跑 | P0 | 保守档（子目录级）+ CI 兜底 |
| 工作树污染升全量 | P0 | 提交/移出 outside-scope 暂存文件 |
| 删测试后基线失配 | P1/P2/P5 | §1.4 SOP |
| 全局泄漏 flaky | P3/P4 | C 类先转 + monkeypatch + 单跑/全量对比 |
| 并行 flaky | P4 | serial 隔离 + 跑3次 |
| 合并丢覆盖 | P5 | 断言条数 ≥ 合并前之和 |
| 目录重组断 import | P6 | 脚本迁移 + 全量收集验证 |
| 成果回潮 | P7 | 防回潮门禁 |
| **与 80 债(B)交接** | P1/P2/P5/P6 | 见 `_B_COMPAT_SAFEGUARDS.md`：1 blocker(sort_strategy 绑 R51)+2 high(workbench 合并去重 / P6 锚点漂移)+8 medium；先 A 后 B，P6 定稿后批量重映射 B 锚点 |
