# 测试与门禁去冗 —— 执行明细计划（2026-06-05 重做）

> 配套：`GOVERNANCE.md`（总纲入口，先读它）、`L3_VERDICTS.md`（裁决依据）、`BASELINE.md`（度量）、`SPEED_AND_READABILITY.md`（提速/可读性细节）、`L3_verdicts.csv`（文件级明细）。
> 本文是各阶段的执行明细。文件清单从 `L3_verdicts.csv` 取（按 verdict/merge_cluster 筛），不在此重复罗列长清单。
> **入场基线快照（2026-06-05 重做时的历史值，非现状）**：645 文件 / 3158 函数 / 4073 item / 197 main-style / 脚手架 23026 行 / 缓存 17MB / 全量 330s / push 典型 40s 最坏 180s。**现状见 §P3 进度段（2026-06-06 实测：tests/ 约 606 文件、79 纯 main-style，其中 `regression_*.py` 内 52 待转）。**

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
- M4 必跑回归改 `@pytest.mark.required`，核销器瘦身。**改门禁编排，双跑验证**。
  - **✅ M4a 已落地（commit `eaf83cbf`，2026-06-06 02:55）**：required 改 `@pytest.mark.required`（conftest 按 registry 自动打标 1821 nodeid）；`verify_required_regressions_from_full_test_debt.py` 620→268 行瘦身为**只读核销 CLI**（保留 payload 校验/核销/组覆盖检查，删父子证明捆绑 + schema v4 机器）；§1.4 SOP 第 3 行已对齐为只读 CLI 形态。
  - **✅ B-14 已按其修法消解（B-14 当时准确，非失实）**：B-14（2026-06-05）准确预警「删 verify_required 会炸 `run_quality_gate.py:25` 顶层 import，须同一原子提交改接」——经核 **eaf83cbf 父提交 `:25` 确为 `from tools import verify_required_regressions_from_full_test_debt`**。eaf83cbf（M4a）**正是这么修的**：同一提交删该顶层 import 行（diff 实证 `-from tools import verify_required...`）+ 删 `_load_required_regressions_verifier_proof` + 核销器 620→268 行瘦身。**现状（消解后）**：`:25` 上移为 architecture_scan_cache（即 B-12 那行），verify_required 无任何顶层 import、仅子进程命令字符串在 `:1654`，模块 11758B；实跑 `import scripts.run_quality_gate` 成功且 sys.modules 不含它。后续若进一步退役该模块，残留点是 `:1654` 子进程调用 + §1.4 SOP 直跑，非顶层 import。
  - **M4 剩余（按需）**：`test_registry.py` 大半删减、核销器进一步退役（若仍计划）走 `:1654` 子进程点 + §1.4 SOP，不涉顶层 import。
- **塌缩 architecture_scan_cache（⚠B-12 HIGH，见 `_B_COMPAT_SAFEGUARDS.md`）**：不可裸删——`test_architecture_fitness.py`（已锁 KEEP）与 `run_quality_gate.py:26` live 门禁经 `quality_gate_operations.py:5` 三段顶层硬 import 直连它，裸删 = collection-error / live 门禁 ImportError。须在删模块的**同一原子提交**里保留 `architecture_*_scan_map`/`aggregate_architecture_scan`/`scan_files_with_cache` 公共 API + 改接 `quality_gate_operations.py:5`、`run_quality_gate.py:26` import + 同步 `test_architecture_scan_cache.py`。

### P2.3 DROP_WITH_TOOL 随工具删（7 个）
见 `L3_VERDICTS.md` §3。**修正**：`test_architecture_fitness.py` 保留（验证业务架构合规）；`test_regression_main_isolation_contract.py` 待 P3 删 collector 后清理。

### P2.4 验证
```bash
.venv/bin/python -m pytest tests/test_architecture_fitness.py --collect-only  # B-12:删cache后collection不炸(锁KEEP的守卫仍可import)
.venv/bin/python -c "import scripts.run_quality_gate"  # B-12:删architecture_scan_cache(:25顶层import)后不炸;verify_required本无顶层import(M4a已消解B-14)
du -sh evidence/QualityGate/   # 应大幅缩小
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

---

## 第 5 章　P3 — main-style → pytest（可读性 + 并行前置）

> 背景：main-style（`def main` 无 `def test_`）是"看不懂"+"失败信息差"最大来源，也是 P4 并行前置。conftest 子进程机制在 `tests/conftest.py`（pytest_collect_file/_is_main_style_regression/RegressionMainFile/RegressionMainItem）。
>
> **进度（2026-06-06 实测，10-agent 核验对齐）**：438 个 `regression_*.py` = **52 纯 main-style(待转)** + 367 已转 native + 19 个 `main`+`test_` 并存（精确闭合，零未归类）。collect **3811**、`-m required` **1821 nodeid**、`iter_required_tests()` **210** 项全程不变（净零）。
> **分支 `cleanup/p3-main-style-to-pytest` 累计转 141 个**：本会话最近 5 commit 共 65（e91b80b6 T1=20 / 1ceba4a2 T2a=15 / 42403977 migration=11 / b9b34f44 T2尾=13 / 30c3d1f2 mem_conn=6）+ 此前 4 批 76（af630f64 先导=10 含拆 R51 BLOCKER / 8e157e40 批次2=41 / 5a7c6ee5 批次3a=16 / 885cec82 批次3b=9），均全门禁 + 多 agent 对抗 + push 验 remote==local。
>
> **🎯 P3 完成定义 = 纯 main-style 52→0**。那 19 个 `main`+`test_` 并存文件是历史**双入口设计**（`def main` 在 `if __name__=="__main__"` 下作命令行入口 + `def test_` 供 pytest），早已 native 收集、import 期零副作用、不被 conftest 判为 main-style——**不在 P3 工作面**(可作独立风格清理，绝非验收门槛)。完成线按 52→0 判，不是 71→0。

### P3.1 先转污染源 C 类（最先，防同进程串味）
从 `L3_verdicts.csv` 找 main-style 中 monkeypatch 全局且无 finally 的（如 ortools sys.modules 注入、schedule_service 模块函数替换、subprocess.Popen 全局替换）→ 改 `monkeypatch` fixture。

### P3.2 抽共享 fixture 到 conftest（同时做 R3）—— ✅ 已落地（42403977 等）
conftest 已加 7 个 fixture：`db_path`(tmp文件库+生产 ensure_schema 全表)、`db_env`(db_path+APS_*五件套 monkeypatch.setenv 自动还原)、`app_client`(importlib import_module("app").create_app().test_client()，**只导顶层 app**)、`schema_conn`(:memory:+全量schema.sql,FK ON+Row)、`mem_conn`(空:memory:,FK ON+Row)、`schema_path`、`repo_root`。消灭 find_repo_root 样板。
- **待补 `app_new_ui_client`**(对称 app_client 但导 `app_new_ui`，收口 4 个纯 app_new_ui 测试 create_app_smoke/secret_key_runtime_ensure/security_hardening_enabled/session_contract)：依赖 `db_env`+`monkeypatch`，进入前+退出后各 `monkeypatch.delitem(sys.modules,"app_new_ui",raising=False)`、`monkeypatch.setenv("SECRET_KEY",...)`。⚠ `system_health_route`/`runtime_lock_reloader_parent_skip` 因 production env + 双导 app+app_new_ui 不能用此 fixture，仍手搓。

### P3.3 批量转换（每批 ~20 文件一 commit）
`def main()`→`def test_xxx(<fixtures>)`、删 find_repo_root/序章/footer、裸 assert 保留(转后自省=自动可读，**R2**)、补 docstring(**R1**)。每批闭环：转换→ruff→同进程实跑→多 agent 对抗→全门禁→push 验 remote==local。

**剩余 52 推荐 3 批(风险同质,3-agent 复核 2026-06-06)：**
- **批 A(~18,零进程副作用,一刀切收益最纯)**：纯路由 `app_client`/`db_env`(reports/system_logs/calendar/operator/excel 等)，env 五件套由 db_env 自动还原=转换收益点。
- **批 B(~17,受控猴补,统一手法)**：ReportEngine/ScheduleService 类猴补统一改 `monkeypatch.setattr`；带 `sys.modules.pop("app")` 的(`scheduler_run`/`week_plan_no_reschedulable_flash`、`gantt_calendar_load_failed_degraded`)补 `monkeypatch.delitem(sys.modules,"app",raising=False)`。
- **批 C(~11-13,高风险手搓+逐个实跑对抗)**：app_new_ui×4(用新 fixture) + `ortools_warmstart`(sys.modules 注入假 ortools 4键**全文无还原→必须 monkeypatch.setitem + _FakeCpModel 类态重置**) + scheduler 双 flash + `safe_next_url_hardening`/`tojson_zh_autoescape`(**需 app 对象非 test_client，不能套 app_client**；tojson 还是 `APS_ENV=production`) + check_manual_layout(HTTPServer) + validate_dist + shared_runtime(sys.modules.pop 重导) + system_health(production 双导) + runtime_lock(atexit/signal,最重之一) + config_manual(subprocess node,最重) + `app_db_path_no_dirname`(纯文件名契约+os.chdir,**不套 fixture**，须 monkeypatch.setenv+chdir(tmp_path))。
- **🥇 优先 11 个门禁必跑成员（两类，删 collector 前必须转完，10-agent 核验更正）**：① **7 个 `required`**（`QUALITY_GATE_REQUIRED_TESTS`，带 required marker，在 `iter_required_tests()` 210 项内）——dashboard_overdue_count_tolerance、gantt_calendar_load_failed_degraded、gantt_url_persistence、report_export_large_scope/size_mode、safe_next_url_hardening、scheduler_analysis_observability：删 collector 后**静默少跑**（silent skip，required marker 只能打在已收集 item）；② **4 个 startup-regression**（`QUALITY_GATE_STARTUP_REGRESSION_ARGS`，经 `pytest -q` 显式路径命令跑）——app_new_ui_secret_key/security_hardening/session_contract、runtime_lock_reloader：删 collector 后被显式路径命令 **loud fail**（no tests collected / exit 4-5，反而易发现）。两类危害形态不同，但都必须转完。
- **🔴 显式验收(P4 前置)**：每文件不得遗留无 finally 还原的 `sys.modules[...]=`/`module.attr=`/`Class.method=`(memory「module-attr-patch-is-global」铁律)。验收=单跑 + 同进程跑两遍幂等 + 多 agent 对抗。优先收口 ortools 注入 + 2 个 flash。
- **三陷阱(已踩)**：①PEP604/585 注解(`int|str`/`HTTPServer|None`/`list[str]`)即使 `from __future__ import annotations` 也被 py38 门禁(`tools/scan_aps_three_gap_py38_scope.py`)判 fail→转 `typing.Union/Optional/List`(start_and_rerun/runtime_probe 均踩)；②`cmd|tail;echo $?` 捕获的是 tail 退出码非 cmd，验退出码用 `cmd >log 2>&1;echo $?`；③`app_client` 只导 app，app_new_ui/需 app 对象的(safe_next_url/tojson)不能套。

### P3.4 移除 collector
全转完(纯 main-style==0)后删 conftest 的 collector(pytest_collect_file/_is_main_style_regression/RegressionMainFile/RegressionMainItem) + `main_style_regression_runner.py`，并清理 `test_regression_main_isolation_contract.py`。**conftest 其余职责(test_debt strict-xfail / required marker / 7 个共享 fixture)与 collector 独立，删 collector 不牵连。**

> **🔴 删 collector 卡点（3 条 AND，机器可判，见 `_B_COMPAT_SAFEGUARDS.md` §8）**：
> 1. **纯 main-style == 0**：`for f in tests/regression_*.py; grep 'def main(' "$f" && ! grep 'def test_' "$f"` 计数为 0。
> 2. **删 collector 同提交自带「无残留 main-style」守卫断言** —— ⚠ 真正怕的是 **7 个 `required` 成员**（见 §P3.3）：删 collector 后它们"收集 0 项 / 静默少跑"（required marker 只能打在已收集 item 上，收集 0 项即无 item 可标）。M4a（`eaf83cbf`）已把核销器瘦身为只读 CLI、§1.4 SOP 仍跑它但语义是事后核销非阻断收集——**守卫断言是唯一能在删 collector 当下抓到「main-style 残留」的硬兜底**（另 4 个 startup 成员走显式路径命令会 loud fail，不靠守卫）。
> 3. 删后 `pytest --collect-only` 总数不净减 + `pytest -m required` 数 == 清单应有数。
>
> **R51 续命文件状态(2026-06-06 更新)**：`regression_sort_strategy_case_insensitive.py` / `regression_dispatch_rule_case_insensitive.py` 已在 `af630f64` 转 pytest(`def test_` 各 1，坏值断言体逐字保留，不违 B-1 语义)，原 BLOCKER「P3.3 不转→删 collector 后静默归零」已拆除；但守卫断言仍须保留(防任何新增 main-style 残留触发同型假绿)。

### P3.5 验证
```bash
.venv/bin/python -m pytest -q tests 2>&1 | tail -10                           # 全量,对比基线无新fail(查泄漏)
.venv/bin/python -m pytest -p no:randomly <本批+污染源victim> -q              # 同进程跑两遍幂等(查进程级泄漏)
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

---

## 第 6 章　P4 — 启用并行 xdist

> 前置：P3 完成(纯 main-style==0) + **P3 污染彻底还原**(每文件无未 finally 还原的 sys.modules/module.attr/Class.method 全局写，见 P3.3 🔴 显式验收) + serial 隔离。⚠ **未还原的进程污染(如 ortools `sys.modules` 注入假模块、ScheduleService 类猴补)在子进程隔离下无害，转 xdist 同进程后会随 worker 随机分配制造 flaky**——这是把"污染还原"前移为 P3 验收标准的根因。详见 `SPEED_AND_READABILITY.md` S1。
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
- **⚠ 新增（2026-06-06，10-agent 核验）**：P6 迁子目录会触发**两个独立机制的失效，修法不同**（勿混述为「硬校验 required」）：
  - **(硬失败)** `tools/test_registry.py:64-65/77` 的 `count("/")==1` 单层校验作用于 **test-only helper 路径**（`_is_top_level_test_only_helper_path`）与 **helper-impact 目标**（`_is_regular_helper_impact_target`）——**非 required**。P6 迁子目录会让这些 helper 路径 `raise ValueError`（硬失败），须放开该单层校验或同步改 `TEST_ONLY_HELPER_IMPACT` 路径。
  - **(软失配)** required/startup 清单走 `normalize_test_paths`（:111-124）**无单层校验、不 raise**，P6 迁子目录后经精确路径匹配**静默失配 / 报 missing**（软失败），须批量重写 `test_registry_data.py` 的 required + startup 路径。
  - **(c)** 「旧→新」映射须**同时覆盖 B 的 199 dossier 锚点 + A 的 required/startup 清单两套**（本章原只列了 B 锚点）。

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
