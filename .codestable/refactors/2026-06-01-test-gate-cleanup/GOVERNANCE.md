# 测试与门禁专项治理总纲

> 制定：2026-06-01　仓库：APS 排产系统（Python 3.8 / Flask，目标 Win7 离线）
> 性质：行为不变的测试/门禁体系治理。整合三条线 —— **提速（主）+ 删合并 + 可读性** —— 成一个有先后、有依赖、有防回潮的工程。
> 读者：执行人（AI 或人类），按本文逐阶段照做。明细文件清单引用 `L3_verdicts.csv`，无需另查。
> 配套文档：`L3_VERDICTS.md`（逐文件裁决依据）、`BASELINE.md`（度量）、`L3_verdicts.csv` / `test_inventory.csv`（机器可读数据）、`SPEED_AND_READABILITY.md`（提速/可读性细节）。本总纲是**唯一权威执行入口**，其余为支撑。

---

## 第 0 章　治理目标与衡量口径

### 0.1 三个真痛点（用户原话校准）
1. **慢**：每次 commit/push 跑测试太久，挡着干活。
2. **看不懂**：不看内容根本不知道测什么，难维护。
3. （隐含）**繁杂**：同一主题散落几十文件、风格不一、样板重复。

### 0.2 衡量口径（多 KPI 仪表盘，取代单一"文件数"）

> 教训：前期用"可删文件数"当 KPI 严重误导（只占 5%）。治理用下面这组 KPI，每阶段后重测。

| KPI | 清理前（实测） | 治理后目标 | 对应痛点 |
|---|---|---|---|
| **push 典型耗时** | ~95s（最坏 107s） | **<15s** | 慢 ★ |
| commit 耗时 | 0.07s（已最优） | 维持 | 慢 |
| CI 全量门禁 | 227s（full_test_debt 202s 主导） | **<90s** | 慢 |
| 全量测试串行 | 342s | — | 慢 |
| 模块 docstring 覆盖率 | **4.7%** | **100%** | 看不懂 ★ |
| 裸 assert（无消息）占比 | 85% | <40% | 看不懂 |
| main-style 文件 | 196 | **0** | 看不懂+慢 |
| 测试代码行数 | 153561 | ~113000（-26%） | 繁杂 |
| 门禁脚手架行数 | 22786 | ~6000（-74%） | 繁杂 |
| 门禁缓存 | 23.8MB | <1MB | 繁杂 |
| 测试文件数 | 607 | ~490 | 繁杂 |

★ = 用户最痛，优先级最高。

### 0.3 铁律
- **不损失任何真实业务回归覆盖**。删/合并只动死代码、快照、重复脚手架、自指测试。
- **不改 `scripts/run_quality_gate.py` 对外 CLI**（AGENTS.md 硬约束）。
- 每阶段独立分支、独立提交、独立可回滚。
- 每阶段后跑 §0.4 度量脚本回填 KPI。

### 0.4 度量复测（每阶段后必做）
```bash
cd /Users/lurenxing/Documents/GitHub/----
.venv/bin/python scripts/build_test_inventory.py     # 刷新 L2 清单（文件/行数/断言）
# push 耗时实测（模拟改一个文件看 daily gate 选多少、多久）
.venv/bin/python -c "from scripts import run_daily_quality_gate as d; \
  s=d.build_daily_gate_scope(pre_push_changed_paths=['core/services/scheduler/config_service.py']); \
  print(d.daily_gate_scope_payload(s))"
# docstring 覆盖率
.venv/bin/python -c "import glob,ast,io; \
  fs=glob.glob('tests/**/*.py',recursive=True); \
  has=sum(1 for f in fs if (lambda t: bool(ast.get_docstring(ast.parse(t))) if t.strip() else False)(open(f,encoding='utf-8',errors='replace').read())); \
  print(f'docstring: {has}/{len(fs)} = {100*has/len(fs):.1f}%')"
```

---

## 第 1 章　治理全景（依赖与顺序）

```
P0 配置提速 ──────────────┐ (独立,最快见效)
                          │
P1 死代码+docstring ──────┤ (独立,零风险)
                          │
P2 门禁元系统瘦身 ────────┤ (独立,删自指=提速+减体积)
                          │
P3 main-style→pytest ─────┼──→ P4 并行xdist (P4依赖P3的隔离)
   (可读性+并行前置)       │
                          │
P5 业务合并+剪脆性尾 ─────┤ (独立,减维护面)
                          │
P6 目录重组+命名 ─────────┘ (放最后,动import路径)
                          │
P7 固化+防回潮门禁 ───────→ (收尾,防止长回来)
```

**最小可行子集**：只做 **P0 + P1 + P2** 就能解决 80% 痛点（push 快、能看懂、删掉最大一坨自指代码），约 1 周。其余是深度优化。

| 阶段 | 主题 | 工作量 | 风险 | 主收割 KPI |
|---|---|---|---|---|
| P0 | 配置层提速 | 1.5 天 | 低 | push 95→15s |
| P1 | 死代码清除 + docstring | 2-3 天 | 零-低 | docstring 100%、删 32 文件 |
| P2 | 门禁元系统瘦身 | 3-4 天 | 中 | 脚手架 -16000 行、push 自指测试不再跑 |
| P3 | main-style→pytest | 5-8 天（分批） | 中 | main-style 196→0、失败可读 |
| P4 | 启用并行 xdist | 2-3 天 | 中 | CI 227→90s、worst push -85s |
| P5 | 业务合并 + 剪脆性尾 | 4-6 天（分簇） | 中 | 文件 -57、脆性断言大减 |
| P6 | 目录重组 + 命名规范 | 3-4 天 | 中 | 定位 grep→进目录 |
| P7 | 固化 + 防回潮门禁 | 1-2 天 | 低 | 防止复发 |

---

## 第 2 章　P0 — 配置层提速（最快见效，零删除）

> **背景**：实测 push 慢的真因不是测试多（3121 测试合计仅 27s），而是"改了 X 该跑哪些测试"的映射表 `tools/test_registry_groups_scheduler.py` / `test_registry_groups_misc.py` 用了巨型目录通配（`static/**/*` 出现 3 次、`web/viewmodels/**/*.py` 3 次、`core/services/scheduler/**/*.py` 2 次），导致改一个文件命中 5-7 组、跑近百秒。
> **风险**：低（CI 全量兜底）。**收割**：push ~95s → ~15s。

### P0.1 精简 FOCUSED_PYTEST_NODEIDS（5 分钟，先做）
`scripts/run_daily_quality_gate.py:29` 每次 push 固定跑 8 个 nodeid，**其中 4 个是门禁自指**（`test_long_gate_full_test_debt_cache`×2、`test_long_gate_required_regression_cache`、`test_long_gate_startup_regression_cache`），与业务无关。
- **做法**：移除这 4 个 `test_long_gate_*`（CI 全量仍跑）。保留 `test_architecture_fitness`、`test_scheduler_batches_page_viewmodel`、`test_ui_geometry_html_contract` 等真业务冒烟。
- **验证**：`.venv/bin/python -m pytest -q <保留的nodeid> && echo OK`
- **收益**：每次 push -1.5s（纯赚）。

### P0.2 登记 outside-scope 文件 + 未知路径设小默认（半天）
- **问题**：未登记 scope 的路径触发 `all_required_groups=True`（近全量 107s）。`run_daily_quality_gate.py:402-408`。
- **做法**：(a) 用下面命令列出当前所有未登记路径，逐个登记进对应组的 `input_file_scopes`；(b) 把未知路径兜底从"跑全部组"改为"只跑 quality_gate 自测组 + focused"。
```bash
# 找出哪些源文件不被任何组的 scope 覆盖（会触发全量）
.venv/bin/python -c "from scripts import run_daily_quality_gate as d; \
  import glob; \
  [print(p) for p in glob.glob('core/**/*.py',recursive=True)+glob.glob('web/**/*.py',recursive=True) \
   if d.build_daily_gate_scope(pre_push_changed_paths=[p]).get('all_required_groups')][:30]"
```
- **收益**：新增文件场景 107s → ~10s。

### P0.3 收窄 scope 通配（1 天，主菜）
- **做法**：编辑 `tools/test_registry_groups_scheduler.py` + `test_registry_groups_misc.py`，把每个组的 `input_file_scopes` 从目录树通配改成该组真正依赖的文件/子目录。反推方法：看该组的 `target_paths`（它实际跑哪些测试），追这些测试 import 的源模块，scope 只列这些。
  - 例：scheduler_config 组 → `core/services/scheduler/config*.py` + `web/routes/scheduler_config.py`，而非 `core/services/scheduler/**/*.py` + `static/**/*`。
- **保守策略（回应"漏跑"顾虑）**：scope 收窄分两档可选——
  - 激进：精确到文件，push 最快但本地可能漏跑边缘回归（CI 兜底）。
  - 稳健：精确到子目录（如 `core/services/scheduler/config/**`），漏跑风险小、push 仍大幅提速。**建议稳健档起步**。
- **验证**：用 §0.4 的 push 耗时命令，对 5 个代表文件（config_service.py、各 viewmodel、static/js、templates）实测命中组数应从 5-7 降到 1-2。
- **回滚**：scope 是纯配置，`git checkout tools/test_registry_groups_*.py` 即还原。

### P0.4 验证 + 提交
```bash
# 改 scope 后,门禁自检不能挂(它有 scope 一致性契约测试)
.venv/bin/python -m pytest tests/regression_quality_gate_scan_contract.py -q
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree   # 全量兜底确认没改坏
git commit -m "perf: P0 收窄 impact scope,push 快门禁提速"
```

---

## 第 3 章　P1 — 死代码清除 + docstring（零风险，分批）

> **背景**：DROP 类（L3 裁决）是纯快照/死代码/测第三方库，删了零业务影响；docstring 直击"不看内容不知道测什么"。两件都零-低风险，可并行推进。
> **收割**：删 32 文件、docstring 4.7%→100%、减噪声。

### P1.1 删除 DROP 类（32 文件）
完整清单：`L3_verdicts.csv` 筛 `verdict=DROP`。分三批提交便于 review：

**批 A — 纯模板/CSS/JS 快照（18 个）**：全部命名带 "contract" 伪装，实则断言 `aps-xxx` class / grid-template / 像素值出现在源码中。清单见 `L3_VERDICTS.md` §2.1。
```bash
# 从 CSV 提取并删除（先 review 清单）
.venv/bin/python -c "import csv; \
  [print('git rm '+r['file']) for r in csv.DictReader(open('.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv')) \
   if r['verdict']=='DROP' and 'layout_contract' in r['file'] or 'ui_' in r['file']]"
```
**批 B — 反向结构守卫（3 个，把 lint 写成测试）**：`regression_excel_routes_no_tx_surface_hidden.py`、`regression_sp05_followup_contracts.py`、`test_phase6_no_*.py`。若这些约束有价值，转成 ruff 规则或 `quality_gate_scan` 扫描项。
**批 C — 文档/常量快照 + 死代码（剩余）**：`benchmark_fjsp.py`、`tests/regression/__init__.py`、`test_evidence_audit_entrypoints.py` 等。
- **删前自检**：每个文件确认不被 import（`grep -rn "<basename>" --include=*.py .`）。
- **基线刷新**：删后跑 §6 SOP（门禁基线失配防护）。

### P1.2 强制 docstring「一句话测什么」（分批，可 AI 辅助）
- **背景**：仅 4.7% 文件有 docstring。标杆 `regression_app_db_path_no_dirname.py:1-7`（两行说清"测什么+为什么+防哪个 bug"）。
- **做法**：每个测试文件首行加 `"""测 X 在 Y 条件下应 Z。"""`。分批：
  1. 先给 KEEP 的 362 个高价值文件加（最该留的最该说清楚）。
  2. AI 批量生成首句草稿（读文件断言推断），人工核对一遍。
  3. KEEP_TRIM/MERGE 的文件在各自阶段处理时顺带加。
- **门禁联动**：P7 会加"无 docstring 的新测试文件拦截"，防止覆盖率回落。

### P1.3 补 main-style 文件的裸 assert 消息（可与 P3 合并）
- 85% assert 是裸的。main-style 文件因子进程跑，裸 assert 失败只给 `AssertionError` 看不到值。
- **做法**：优先给将保留的 main-style 文件补消息（`assert x==y, f"应为{y}实际{x}"`）。但**注意**：这些文件 P3 要转 pytest（转后有自省，裸 assert 也能看到值）。所以 P1.3 仅处理"P3 暂不转、又常失败"的少数；其余留到 P3 一并解决。

### P1.4 验证 + 提交
```bash
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -3   # 收集数应减少 32
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
git commit -m "test: P1 删除快照/死代码 + 补 docstring"
```

---

## 第 4 章　P2 — 门禁元系统瘦身（删自指 = 提速 + 减体积）

> **背景**：18 个 DROP_WITH_TOOL 是"门禁测门禁自己"的纯自指测试（value 全 self-ref），且**又慢**——`test_long_gate_required_regression_cache` 单文件跑 33.8s、`test_long_gate_full_test_debt_cache` 20.5s。删它们既减 16532 行代码又提速。配合门禁脚手架瘦身（22786→6000 行）。
> **风险**：中（动门禁内部，不碰业务测试）。**收割**：脚手架 -16000 行、缓存 24MB→<1MB、自指慢测试消失。

### P2.1 缓存条目模板族参数化合并（5→1）
`long_gate_entry_cache_template` 簇（`L3_verdicts.csv` 筛该 cluster）：5 个 `test_long_gate_*_cache.py` 结构同构，共享 helper `tests/long_gate_cache_helpers.py` 已存在。
- 新建 `tests/test_long_gate_entry_cache.py` 用 `@pytest.mark.parametrize` 遍历 5 类条目 → 60 函数缩到 ~15。
- **连带改动**：`tools/full_test_debt_shards.py:20-21` 硬编码引用其中 2 个文件名，需同步删。

### P2.2 机制改造（每条独立 commit）
依 `PLAN.md` 第 4 章 M2/M3/M4：
- **M2 增量引擎塌缩**：删 `long_gate_test_body_diff.py`(317行)，简化 `long_gate_full_test_debt.py`(2034→~500行)，缓存退化为"指纹命中整体复用，否则全跑"。node_cache 7.3MB 删除。
- **M3 指纹简化**：`long_gate_fingerprint.py`(1319行) 删 Chrome 指纹部分（目标机 Chrome 永不变）。
- **M4 必跑回归改 pytest 标记**：给必跑回归打 `@pytest.mark.required`，门禁 `pytest -m required`，删 `verify_required_regressions_from_full_test_debt.py`(620行) + `test_registry.py` 大半。**注意**：M4 改门禁编排，需双跑验证（cold + cache）。
- **架构扫描去缓存**：删 `architecture_scan_cache.py`(474行) + 3MB 缓存。

### P2.3 DROP_WITH_TOOL 测试随工具删除（18 个）
清单见 `L3_VERDICTS.md` §3。**绑定 P2.2**：工具删则测试删；工具保留（如 `quality_gate_scan`）则其测试改 REWRITE 去脆性。唯一例外 `regression_quality_gate_scan_contract.py`（KEEP，测业务架构合规）。

### P2.4 验证 + 提交
```bash
du -sh evidence/QualityGate/                        # 应从 24MB 大幅缩小
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache  # 双跑验证缓存仍工作
git commit -m "refactor: P2 门禁元系统瘦身（增量塌缩/指纹简化/必跑改标记/删自指测试）"
```

---

## 第 5 章　P3 — main-style → pytest（可读性 + 并行前置）

> **背景**：196 个 main-style 文件（`def main()`+裸 assert+`find_repo_root` 样板，子进程跑）是"看不懂"和"失败信息差"的最大来源，也是 P4 并行的前置（子进程模型无法 xdist）。转 pytest 一举三得：可读性 + 提速 + 启用并行。
> **风险**：中（全局状态泄漏）。**收割**：main-style 196→0、失败可读、为 P4 铺路。
> 三类归桶（C=3/B=106/A=87）完整清单见 `L3_VERDICTS.md` §9 / `PLAN.md` 第 9 章。

### P3.1 先转 3 个 C 类（污染源，最先）
`regression_ortools_warmstart_skip_nonfinite.py`、`regression_schedule_service_reschedulable_contract.py`、`regression_start_and_rerun_route_resolution.py`——改用 `monkeypatch` fixture。详见 `PLAN.md` §5.1。

### P3.2 抽共享 fixture 到 conftest（R3 抽样板顺带做）
在 `tests/conftest.py` 加 `mem_conn`/`db_conn`/`app_client` fixture（详见 `PLAN.md` §5.2）。这同时消灭 219 份 `find_repo_root` 样板（R3）。

### P3.3 批量转换（B 106 + A 87，每批 ~20 文件一 commit）
配方见 `PLAN.md` §5.3：`def main()`→`def test_xxx()`、删样板、裸 assert 保留（转后有自省=自动可读，**这一步同时完成 R2 可读性**）、22 个灰名单改 monkeypatch。

### P3.4 docstring 补齐（R1 收尾）
转换时给每个文件加 §P1.2 的一句话 docstring（转换已逐文件过一遍，顺手最省）。

### P3.5 移除 main-style collector
196 个转完后删 `conftest.py:51-106` 的子进程机制 + `main_style_regression_runner.py`。

### P3.6 验证 + 提交
```bash
.venv/bin/python -m pytest -q tests 2>&1 | tail -10   # 全量,对比基线 pass 集无新 fail（查泄漏）
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

---

## 第 6 章　P4 — 启用并行 xdist（最大绝对提速）

> **背景**：P3 完成后测试都是进程内函数，可安全并行。本机/CI 多核，全量 342s 可压到 ~60-90s。
> **前置**：P3 完成 + 27 个 serial 测试隔离。**风险**：中（隔离不全会 flaky）。**收割**：CI 227→90s、worst push -85s。

### P4.1 vendor wheel（Win7 离线）
`pytest-xdist` + `execnet` 均纯 Python wheel：`pip download` 后放 `vendor/wheels/`，`requirements-dev.txt` 登记。

### P4.2 serial 隔离
用 `tools/full_test_debt_shards.py` 已有的 serial/parallel 分类，给 27 个固定端口/共享 DB 测试标 `@pytest.mark.serial`，门禁 `pytest -n auto --dist loadgroup`（serial 组串行、其余并行）。

### P4.3 验证
```bash
time .venv/bin/python -m pytest -n auto --dist loadgroup -q tests 2>&1 | tail -5
# 多跑 3 次确认无 flaky（并行最怕偶发）
for i in 1 2 3; do .venv/bin/python -m pytest -n auto --dist loadgroup -q tests >/dev/null 2>&1 && echo "run$i OK" || echo "run$i FLAKY"; done
```

---

## 第 7 章　P5 — 业务测试合并 + 剪脆性尾（减维护面）

> **背景**：MERGE 105 文件→48 簇（净减 57），KEEP_TRIM 77 文件剪脆性尾巴。这是"繁杂"的主体——同一契约散落多文件、真测试夹脆性快照。
> **风险**：中（需逐簇核对断言不丢）。**收割**：文件 -57、脆性断言大减、改文案不再误报红。

### P5.1 MERGE 簇合并（48 簇，每簇独立 commit）
完整簇图见 `L3_VERDICTS.md` §4 / `L3_verdicts.csv` 的 `merge_cluster` 列。**与决策对账**：
- `smoke_phase_suite`(9)+`smoke_web_phase_suite`(2)：D-1 决定**保留 smoke**，不合并。
- `real_db_replay`(3)：e2e 是 load-bearing 保留，仅 check/smoke 走删除。

每簇做法：抽公共 fixture → `@pytest.mark.parametrize` 收差异 → 合并 → `git rm` 原文件 → 跑定向测试 → 核对断言条数 ≥ 合并前之和（去重）。

按收益排序先做大簇：`optimizer_multistart_contract`(4)、`gantt_degradation_surface`(4)、`route-parser-supplier-fallback`(4)、`sgs_unscorable_reject`(3) 等。

### P5.2 KEEP_TRIM 剪脆性尾（77 文件）
清单：`L3_verdicts.csv` 筛 `verdict=KEEP_TRIM`。每个文件保留真实断言、删脆性尾（JS 源 grep / CSS 像素 / 整页文案 / openpyxl 布局 / 精确中文文案 exact-match→改"含关键片段"或 ErrorCode）。重点大文件：`frontend_ui_language_polish.py`(844行)、`excel_template_contracts.py`(842行)、`config_manual_markdown.py`(765行)、`test_win7_launcher_runtime_paths.py`(77测试)。

### P5.3 REWRITE（2 个）+ ISOLATE_PERF（1 个）
- `test_codestable_tools_contract.py`、`regression_aps_three_gap_docs_quality_gate.py`：脆性断言改非脆性。
- `tests/scheduler_graph/test_graph_performance.py`：时间阈值断言标 `@pytest.mark.perf` 隔离（避免 CI 抖动）。

---

## 第 8 章　P6 — 目录重组 + 命名规范（定位）

> **背景**：592 文件平铺一个目录，定位只能 grep。文件名中位 46 字符、实现黑话。`tests/scheduler_graph/`（18 文件组织良好）证明项目有能力做好，只是没推广。
> **风险**：中（动 import 路径）。放最后做。**收割**：定位 grep→进目录。

### P6.1 按被测模块建目录树
```
tests/
  scheduler/{candidate,summary,config,run,graph}/
  gantt/   resource_dispatch/   excel/   batch/   calendar/
  system/{migration,maintenance,runtime,transaction}/
  meta/    （门禁自测，与业务隔离）
```
按"改了模块 X 想跑 X 的测试"组织（优于按 bug 类型）。

### P6.2 迁移 + 文件名去前缀
进目录后 `regression_gantt_zoom_range_guard.py` → `gantt/zoom_range_guard.py`（短一半不丢信息）。一次性脚本化迁移 + 改 `pyproject.toml` 的 testpaths（若需要）。

### P6.3 命名规范（写进 CONTRIBUTING）
后缀词表收敛 3 类：`_contract`（公开输出形状）、`_guard`（边界/拒绝）、`_smoke`（启动冒烟）。废弃 `_semantics`/`_guardrail` 同义词。名字写"可观察行为"不写"实现黑话"。

---

## 第 9 章　P7 — 固化 + 防回潮门禁（防止长回来）

> **背景**：根因是"1 bug=1 文件"习惯 + scope 配置松 + 无 docstring 约束。不加护栏，治理成果会慢慢回潮。这是"治理"区别于"一次性清理"的关键。
> **收割**：成果不退化。

### P7.1 新文件门禁（加进 quality_gate_scan 或新 pre-commit 检查）
1. **拦截 main-style 新文件**：新增 `regression_*.py` 必须有 `def test_`，禁止纯 `def main()`。
2. **强制 docstring**：新增测试文件必须有模块 docstring（照搬 `regression_aps_three_gap_docs_quality_gate.py` 的文档门禁模式）。
3. **scope 登记检查**：新增源文件若无任何测试组 scope 覆盖，CI 警告（防止 P0 的 outside-scope 问题复发）。

### P7.2 基线固化
执行 §6 SOP，把 `required_regressions.json`、`full_test_debt` 基线重建到治理后稳定态。

### P7.3 文档同步 + 验收报告
- 更新 `.codestable/architecture/ARCHITECTURE.md` 测试/门禁现状。
- 写 `acceptance.md`：对照本总纲逐 P 核实 + 用实测值填 §0.2 KPI 仪表盘的"治理后"列。

---

## 第 10 章　基线刷新 SOP（每次删/改测试后必做）

删/改测试改变 nodeid 集合，门禁基线会失配。刷新顺序：
```bash
.venv/bin/python -m pytest --collect-only -q tests > /dev/null
.venv/bin/python tools/check_full_test_debt.py --sharded --shard-count 3
.venv/bin/python tools/verify_required_regressions_from_full_test_debt.py  # P2 M4 后改 pytest -m required
.venv/bin/python scripts/sync_debt_ledger.py check
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

---

## 第 11 章　风险登记

| 风险 | 阶段 | 缓解 |
|---|---|---|
| scope 收窄致本地漏跑 | P0 | 稳健档（子目录级）起步 + CI 全量兜底 |
| 删测试后门禁基线失配 | P1/P2/P5 | 每阶段执行 §10 SOP |
| 漏改 full_test_debt_shards 硬编码 | P2.1 | 同步删 :20-21 |
| 全局状态泄漏致 flaky | P3/P4 | C 类先转 + 22 灰名单改 monkeypatch + 单跑/全量对比 |
| 并行 flaky | P4 | serial 隔离 + 跑 3 次确认 |
| 合并丢覆盖 | P5 | 逐簇核对断言条数 ≥ 合并前之和 |
| 目录重组断 import | P6 | 一次性脚本迁移 + 全量收集验证 |
| 治理成果回潮 | P7 | 新文件门禁（禁 main-style/强制 docstring/scope 登记）|
| 与 resource_dispatch JS 改动冲突 | P5 前端簇 | 等其落定再动前端域 |

---

## 第 12 章　执行建议

1. **立即可做、零风险、最快见效**：P0（1.5天）→ push 95s→15s。**强烈建议先做这个让你立刻解脱。**
2. **最小可行治理**：P0+P1+P2（约1周）解决 80% 痛点。
3. **完整治理**：P0→P7 全程，分阶段独立交付，随时可暂停。
4. **隔离方式**：当前工作区有 resource_dispatch 未提交改动 + 门禁要求 clean worktree。开工前两选一：(甲) 先提交手头改动；(乙) 用 `git worktree` 隔离治理工作。
5. **每阶段后**跑 §0.4 度量回填 KPI 仪表盘，用真实数字证明每步价值。

> 所有文件级明细从 `L3_verdicts.csv` 取（按 verdict/merge_cluster 筛），reason 列附 file:line 证据。本总纲只给阶段编排与方法，不重复明细。
