# 测试与门禁去冗 —— 全面交付计划

> 制定：2026-06-01　仓库：APS 排产系统（Python 3.8 / Flask，目标 Win7 离线）
> 性质：行为不变（behavior-preserving）的测试/门禁结构精简。
> 读者：执行人（可以是另一个 AI 或人类），按本文逐条照做即可，无需再做调研。

---

## 第 0 章　为什么做这件事（背景）

### 0.1 现状一句话
项目有 607 个测试文件、2953 个 `def test_` 函数、再加 196 个"每个起独立子进程"的 main-style 回归脚本。门禁脚手架本身 22786 行代码 + 23.8MB 缓存。跑得慢、改起来牵一发动全身，体验差。

### 0.2 经 7 路深度审计 + grep 实证后，确认的三个病根

**病根一：门禁在"测试门禁自己"（自指复杂度）。**
项目为了"避免每次重复跑分钟级全量测试"，自建了一套"指纹 + 清单 + 函数体级 AST 增量 + 双层结果缓存 + 债务台账"的元系统（22783 行）。然后又写了 **693 个测试函数（占全部的 23.5%）专门验证这套缓存自己算得对不对**。
硬证据：`grep -rE "(from tools|import tools)" core/ web/ app.py` = **0 命中**。也就是说门禁工具对业务代码零引用——删掉整个 `tools/`，APS 系统照常运行，只有这 693 个测试会消失。缓存的复杂度已经超过它要加速的对象。

**病根二："1 个 bug = 1 个新文件"的习惯。**
436 个 regression 文件里 **275 个（63%）只有 ≤2 个测试函数**。每修一个缺陷就新建一个文件，每个文件顶部都重复粘贴一段 `find_repo_root()` 样板——全仓 **230 个文件**有这段。测试数量随提交线性膨胀。

**病根三：把"字符串快照"当契约。**
全仓约 **2477 处**断言在匹配中文文案、HTML 属性顺序、CSS 像素值，甚至压缩后的第三方库 `frappe-gantt.min.js` 源码。改一个字就红，维护成本高、抓不到真 bug。

### 0.3 总目标（量化，基于实测基线）
| 对象 | 清理前（实测） | 目标 | 降幅 |
|---|---|---|---|
| 测试文件总数 | 607 | ~370 | -39% |
| 门禁脚手架代码 | 22786 行 | ~6000 行 | -74% |
| 门禁缓存 | 23.8 MB | <1 MB | -96% |
| meta 自证测试函数 | 693 | ~250 | -64% |
| 全量测试（串行） | 342s（5分42秒） | — | 主要靠并行 |
| 全量测试（并行 xdist） | N/A | <120s | -65% |
| main-style 子进程额外墙钟 | ~54s | <10s | -82% |

> 完整基线测算、测量命令、每 Phase 复测脚本、成果回填表见 **`BASELINE.md`**。所有"清理前"数字均为本机实测（非估算），可复现。

**铁律：不损失任何真实业务回归覆盖。** 所有删除/合并都必须保留每个边界 case 的断言。

### 0.4-bis 分析颗粒度纪律（关于"要不要更细分析"的正式回答）

分析分三层，成本与价值差异极大。**不是越细越好，而是"该细的地方临动手前细"。**

| 层级 | 是什么 | 成本 | 何时做 | 状态 |
|---|---|---|---|---|
| **L1 域级抽样** | 7 路 SubAgent 各精读 15-20 个代表文件，给方向 | 已花 | 一次性 | ✅ 已完成 |
| **L2 全量结构化清单** | 脚本提取**全部 607 文件**的函数数/被测模块/断言数/断言类型/分类标签 | 秒级，可重跑 | 开工前一次 + 每 Phase 后重跑 | ✅ 已生成 |
| **L3 逐函数语义判断** | LLM 逐条读断言，判断价值、核对合并不丢覆盖 | 贵 | **仅对"即将动手的那一簇"，临动手时对着活代码做** | ⏳ 随 Phase 进行 |

**为什么不现在就 L3 全量精读 607 文件？**
- 87 个 A 类是机械转换，现在逐条读不改变任何决策——纯浪费。
- L3 结论会随代码变化过期（尤其 resource_dispatch 正在改），现在 judge 完等动手时还得重读。
- 真正需要 L3 的是"合并簇是否丢覆盖""删除是否安全"——这两件事必须**对着将要修改的活代码**做，提前做反而不准。

> **更新（L3 已全量完成）**：应用户要求,已用 12 个 SubAgent 逐个精读全部 597 文件,产出 `L3_VERDICTS.md` + `L3_verdicts.csv`。**最重要的发现是 L3 比 L1 抽样保守**：实测净减约 96-107 文件（清理后 ~490-500,-18%）,而非抽样估的 -39%。原因是调度核心(134文件0删)、系统域(74文件1删)几乎全是真实业务覆盖。**这验证了"L3 防止过度删除"的价值**——若按抽样的 -39% 去删,会误删真实覆盖。下方"何时做 L3"的论证依然成立（合并/删除的最终确认仍需对着活代码做），但整体方向已由 L3 校准。

**L2 全量清单已落地**（`test_inventory.csv` + `scripts/build_test_inventory.py`），它把 607 文件全量分类如下（实测）：

| 分类 | 文件数 | 行数 | assert数 | 含义 / 处置 |
|---|---|---|---|---|
| 常规 | 224 | 73923 | 10025 | 真业务测试主体，多数保留 |
| 微文件 | 99 | 11664 | 897 | ≤2 函数，Phase 4 并入契约族 |
| 脆性快照 | 75 | 11088 | 1299 | 字符串断言为主，Phase 1/4 瘦身 |
| B2-起db | 70 | 13092 | 494 | main-style，Phase 3 转 db fixture |
| B1-起app | 60 | 17244 | 310 | main-style，Phase 3 转 app fixture |
| A-轻量 | 46 | 6201 | 248 | main-style，Phase 3 脚本批改 |
| **META自指** | **31** | **22556** | **2623** | **门禁测门禁自己，占全仓测试代码 14.5%**，Phase 2 主攻 |
| C-全局污染 | 2 | 462 | 2 | Phase 3.0 最先转（脚本只抓到 2 个，第 9 章人工核为 3 个，见下） |

> **L2 清单的定位（重要）**：它是**导航工具，不是裁决者**。启发式分类有已知误差——例如 `benchmark_fjsp.py`、`conftest.py` 会被误卷入；C 类脚本只抓到 2 个（漏了 `start_and_rerun`，因它的污染是 stdlib subprocess 而非 sys.modules），以第 9 章人工核对的 3 个为准。**用它快速定位候选，用 L3 临动手时定生死。**

**全量清单立刻发现的、抽样漏掉的目标**（证明 L2 的价值）：
- META 自指 31 文件占 22556 行，单文件均 728 行——是全仓最臃肿的一类，"按文件数看占 5%、按代码量看占 14.5%"。
- `regression_models_numeric_parse_hybrid_safe.py` 名字像算法测试，实塞 41 条字符串断言——伪装成业务测试的快照，抽样翻不到。
- 业务模块热度：180 文件测 `core.services.scheduler`、164 测 `database`——量化了 Phase 4 合并空间。

**结论**：计划本身（命令/文件名/代码颗粒度）无需再细化。需要的"更细"是 L2（已补）+ L3（随 Phase 动手时做）。复测脚本每个 Phase 重跑 `build_test_inventory.py`，分类分布的变化本身就是进度证据。

### 0.4 度量纪律（贯穿全程）
- **开工前**：在干净分支跑一次 `BASELINE.md` 第三部分复测脚本 + 全量门禁计时，确认基线（本轮已测的是脏工作区，时间有效但 13 failed 需在干净态复核）。
- **每个 Phase 后**：跑复测脚本，把实测值填进 `BASELINE.md` 第二部分的成果表对应列。
- **最终**：用实测值替换 `BASELINE.md` 第四部分"账单"里的预期值，产出可向决策者展示的 before/after 对比。
- **不回退红线**：每个 Phase 后全量测试 passed 数不得低于该阶段应有值，门禁必须绿（见 `BASELINE.md` §2.4）。

---

## 第 1 章　已拍板的决策（不再纠结）

| 编号 | 决策 | 结论 | 理由 |
|---|---|---|---|
| D-1 | smoke 脚本 + .bat 是否删 | **保留，不删** | 它们不进门禁、不占时间，删了对核心痛点零帮助，却冒"删掉别人验收工具"的险。不划算。 |
| D-2 | 引入 pytest-testmon（增量选测） | **暂不引入** | 用"换一套复杂度"去解决"复杂度太多"自相矛盾。先退回最笨最稳的"全量重跑"，体会到痛再说。 |
| D-3 | 引入 pytest-xdist（并行） | **要，但只在 Phase 3 完成后** | 直接缓解"慢"。但并行要求测试无全局状态污染——必须先做完 Phase 3 清理污染源，否则并行会随机炸。 |
| D-4 | 必跑回归改 pytest 标记、删 verify 链 | **执行** | 删 620+900 行重复机制，且是标准做法。 |
| D-5 | 阶段顺序 | **1→2→3→4→5** | 风险从低到高、解耦优先。前端域（Phase 4.3）等 resource_dispatch JS 拆分落定。 |

---

## 第 2 章　通用规则（每个阶段都遵守）

### 2.1 环境（已验证可用）
- Python：`.venv/bin/python`（3.8.10）
- pytest 8.3.5、ruff 0.15.11，**当前未装 pytest-xdist**
- pre-commit / pre-push hook 已装（`.git/hooks/pre-commit`、`pre-push`）
- 门禁入口：`scripts/run_quality_gate.py`（AGENTS.md 硬约束，**对外 CLI 不可改**）

### 2.2 隔离方式（重要）
gitStatus 显示当前工作区有未提交的 resource_dispatch 改动。**两个选择**：
- **方案甲（推荐）**：用户先把手头 resource_dispatch 提交干净，再从干净起点开工。
- **方案乙**：用独立 git worktree 做清理，与功能改动物理隔离（`git worktree add ../aps-cleanup cleanup/base`）。
无论哪种，每个 Phase 用**独立分支**：`git checkout -b cleanup/phaseN-<topic>`。

### 2.3 每阶段收尾"三连验证"
```bash
cd /Users/lurenxing/Documents/GitHub/----
# ① 收集不掉测试、无 import 错误
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -5
# ② 受影响域定向跑（各阶段给具体命令）
# ③ 全量门禁（最终回归保护，分钟级）
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

### 2.4 门禁基线刷新 SOP（每次删/改测试后**必做**，否则门禁红）
门禁的 `required_regressions.json`、`full_test_debt` 基线是从"当前 nodeid 集合"派生的。删/改测试会让它们失配。刷新顺序：
```bash
.venv/bin/python -m pytest --collect-only -q tests > /dev/null          # 重新收集
.venv/bin/python tools/check_full_test_debt.py --sharded --shard-count 3 # 重建全量债务基线
.venv/bin/python tools/verify_required_regressions_from_full_test_debt.py # 重生成必跑清单
.venv/bin/python scripts/sync_debt_ledger.py check                       # 台账对账
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree     # 确认绿
```
> Phase 2 执行 D-4 后，第 3 行简化为 `pytest -m required` 自检。

### 2.5 回滚
每阶段独立分支独立提交。出问题 `git reset --hard` 或丢弃分支即可，不影响 main 和其它阶段。

### 2.6 红线（绝不触碰）
- ❌ 不改 `scripts/run_quality_gate.py` 对外 CLI（`--require-clean-worktree` / `--long-gate-cache`）
- ❌ 不删第 8 章「不可删清单」中的 load-bearing 脚本
- ❌ 永久保留：`test_architecture_fitness.py`、`scheduler_graph/` 整目录、全部 migration 测试、operation_execution service 层并发测试、各域高价值算法测试（第 7 章列明）

---

## 第 3 章　Phase 1 — 零风险删除

> **背景**：先摘掉"看着就该删、删了绝不出事"的东西，给后续阶段腾出干净视野。
> **风险**：极低（每项都已 grep 证明零代码引用）。**置信度**：高。
> **预计**：删 13 文件 + 1 死分支 + 一批脆性断言。

### 3.1 删 11 个零引用文件
**这些是什么**：早期遗留的手动验证脚本（`smoke_*`、`run_*` 前缀），pytest 根本不收集它们（`pyproject.toml:7` 的 `python_files` 只认 `test_*`/`*_test`/`regression_*`），且全仓无任何 .py/.bat/.yml 引用。
```bash
git rm tests/smoke_web_phase0_5.py tests/run_one_job_and_export_gantt.py \
       tests/run_real_db_replay_check.py tests/run_real_db_replay_smoke.py \
       tests/smoke_phase0_phase1.py tests/smoke_phase2.py tests/smoke_phase3.py \
       tests/smoke_phase4.py tests/smoke_phase6.py tests/smoke_web_phase0_6.py \
       tests/run_xss_excel_to_gantt_popup_check.py
```
**删前自检**（应全部只命中自身或 .md）：
```bash
for b in smoke_web_phase0_5 run_one_job_and_export_gantt run_real_db_replay_check \
         run_real_db_replay_smoke smoke_phase0_phase1 smoke_phase2 smoke_phase3 \
         smoke_phase4 smoke_phase6 smoke_web_phase0_6 run_xss_excel_to_gantt_popup_check; do
  echo "== $b =="; grep -rIn "$b" --include=*.py --include=*.bat --include=*.yml . | grep -v "tests/$b\.py"
done
```
> 注意：D-1 决定**保留** smoke_phase5/7/8/9、smoke_e2e、smoke_phase10、run_synthetic_case（它们有 .bat 或 audit 脚本引用），不在本批。

### 3.2 成对删一次性时长报表工具
**这是什么**：`report_full_test_debt_durations.py` 是个生成"测试耗时报表"的辅助工具，prod 引用=0，唯一引用是它自己的测试。
```bash
git rm tools/report_full_test_debt_durations.py tests/test_report_full_test_debt_durations.py
```
> 必须成对：单删工具会让测试 import 失败。已确认不在 `QUALITY_GATE_TOOL_PATHS`/`pyrightconfig.tools.json`/`test_registry.py`/任何 manifest。

### 3.3 收口死分支 `tools/full_test_debt_shards.py:53`
**真实代码**（已读，:53）：
```python
    if name.startswith("smoke_web_phase") or name.startswith("test_startup"):
        return "serial"
```
`smoke_web_phase*` 永不被收集（前缀规则），这半边恒假。**但 `:18` 的 `SERIAL_FILE_PATTERNS` 已含 `"tests/test_startup*.py"`**，需确认 `:53` 的 `test_startup` 那半是否多余——实测保留它更稳（nodeid 级兜底），故只删 `smoke_web_phase` 那半：
```python
# 改后
    if name.startswith("test_startup"):
        return "serial"
```
验证：`tests/test_full_test_debt_shards.py` 的 parametrize 未覆盖 smoke_web_phase 用例，不会挂。
```bash
.venv/bin/python -m pytest tests/test_full_test_debt_shards.py -q
```

### 3.4 删第三方库源码快照（1 个 test 函数）
`tests/regression_frappe_gantt_short_task_contract.py`：删第 4 个 test（`:259-271`，对压缩后 `frappe-gantt.min.js` 做子串断言——这是在测第三方库本身）。**保留前 3 个**（`:119-256`，用 Node 真实实例化 Gantt 验证 bar 几何，高价值）。

### 3.5 删纯 CSS 视觉快照断言（颗粒细，单独一个 commit）
**这是什么**：约 11 个 `regression_*_layout_contract.py` 里，有「CSS 像素值 / grid-template / max-height」这类断言（如 `regression_gantt_layout_contract.py:32,100-102`）。改个像素值就红，抓不到 bug。
**做法**：逐文件，**只删视觉细节断言行，保留 class 存在性/结构断言**。逐文件人工判断，列出每处删除行号写进 commit message。

### 3.6 Phase 1 验证 + 提交
```bash
.venv/bin/python -m pytest tests/test_full_test_debt_shards.py tests/regression_frappe_gantt_short_task_contract.py -q
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -5
# §2.4 基线刷新
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
git commit -m "test: phase1 删除零引用脚本/一次性工具/第三方库与CSS快照"
```

---

## 第 4 章　Phase 2 — 门禁元系统瘦身（最大冗余源）

> **背景**：这是病根一。门禁自己写了一套"聪明的增量缓存"再写一堆测试证明它聪明，结果整套东西比它要加速的全量测试还重。本阶段把"聪明缓存"降级成"笨但稳"，并删掉验证聪明缓存的自指测试。
> **风险**：中（动门禁内部，不碰业务测试）。**置信度**：中-高。
> **拆分**：建议 2.A（测试合并，低风险）和 2.B（机制改造，中风险）分两个 commit。

### 4.1 子阶段 2.A — 缓存条目模板族参数化合并（5 → 1）
**这 5 个文件干同一件事**：取一个门禁缓存条目 → 改一个文件看指纹 hash 变没变 → 看缓存该复用还是该重跑。只是换了 5 种条目（quickref/startup/required/debt_ledger/collect）。真正的缓存引擎逻辑已在 `test_long_gate_cache.py`(85 函数) 全覆盖。

真实样本 `test_long_gate_quickref_cache.py`（已读）的结构：`_quickref_entry()` 取条目 → `test_..._fingerprint_tracks...` 参数化改文件断言 hash 变 → `test_..._reuse_requires...` 断言 reuse/run。其余 4 个同构。

**做法**：
1. 新建 `tests/test_long_gate_entry_cache.py`，把 5 类条目收进一张表：
```python
ENTRY_CASES = [
    ("quickref_vs_routes", ["开发文档/系统速查表.md", "app.py", ...]),
    ("startup_regressions", [...]),
    ("required_regressions", [...]),
    ("debt_ledger_sync", [...]),
    ("collect_nodeids", [...]),
]
@pytest.mark.parametrize("entry_id, changed_paths", ENTRY_CASES)
def test_entry_fingerprint_and_reuse(entry_id, changed_paths, tmp_path):
    # 复用 tests/long_gate_cache_helpers.py 已有的共享逻辑
    ...
```
2. 删 5 个原文件：
```bash
git rm tests/test_long_gate_quickref_cache.py tests/test_long_gate_startup_regression_cache.py \
       tests/test_long_gate_required_regression_cache.py tests/test_long_gate_debt_ledger_cache.py \
       tests/test_long_gate_collect_cache.py
```
3. **⚠️ 连带改动（之前漏掉、本版补上）**：`tools/full_test_debt_shards.py:20-21` 把其中 2 个文件硬编码进串行清单：
```python
# 删除这两行（文件已不存在）
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
```
（`:19` 的 `"tests/test_long_gate*.py"` 通配已覆盖新文件 `test_long_gate_entry_cache.py`，无需新增。）
4. **§2.4 基线刷新必做**：这些测试是 required_regression / quality_gate 组成员，删后不刷新基线门禁第 10 步会因 nodeid 对不上而红。

验证：
```bash
.venv/bin/python -m pytest tests/test_long_gate_entry_cache.py tests/test_long_gate_cache.py \
     tests/test_full_test_debt_shards.py -q
```

### 4.2 子阶段 2.B — 机制改造（每条独立 commit）

**M2 增量引擎塌缩（最大单项）**
- **现状**：`tools/long_gate_full_test_debt.py`(2034 行) + `tools/long_gate_test_body_diff.py`(317 行) 实现了"改了哪个测试函数体，就只重算那几个 nodeid，其余原样合并旧报告"，配 `full_test_debt_node_cache.json`(7.3MB)。
- **改成**：删 `long_gate_test_body_diff.py`；把 `long_gate_full_test_debt.py` 的"局部重算+合并"删掉，只留"指纹命中→整体复用上次 pass/fail，否则全量重跑"。预计砍 ~1500 行。
- **缓存降级**：不再存逐 nodeid 报告，只存 `last_pass.json`（HEAD + 指纹 + exit code）。24MB→KB 级。
- **代价**：改一个测试就全量重跑一次。对分钟级套件可接受（省下的是"完全没改测试时的重复全量"，占 80% 场景）。这正是 D-2 决定先不上 testmon 的原因——先吃这个笨办法的痛。

**M3 指纹简化**
- **现状**：`tools/long_gate_fingerprint.py`(1319 行) 把 Chrome 路径/版本/可执行 hash 也算进每个缓存条目的指纹。
- **改成**：删 Chrome 相关部分（目标机 Chrome 永不变，是死重量）。指纹 = `git HEAD` + `tests/`/`core/`/`web/` 的 diff hash + 工具版本。预计砍 ~1000 行。

**M4 必跑回归去重（执行 D-4）**
- **现状**：门禁第 2 步全量已覆盖 `tests`，但第 9（architecture）/10（verify_required）/15（startup）又把子集单列、复核、再跑。
- **改成**：给必跑回归打 `@pytest.mark.required`（在对应测试函数加标记），门禁直接 `pytest -m required`，删第 10 步 JSON 复核链。
- **连带砍**：`tools/verify_required_regressions_from_full_test_debt.py`(620 行) + `tools/test_registry.py` 大半（1057→~150）。
- **⚠️ 这改了门禁编排**：需同步改 `scripts/run_quality_gate.py` 的命令计划（`tools/quality_gate_shared.py:711` 的 `build_quality_gate_command_plan`）。改动后必须双跑门禁（cold + cache）验证。

**架构扫描去缓存层（M2 附带）**
- 删 `tools/architecture_scan_cache.py`(474 行) + 3MB 缓存。扫描本身秒级，改为每次直接扫。

### 4.3 Phase 2 验证 + 提交
```bash
.venv/bin/python -m pytest tests/test_long_gate_cache.py tests/test_long_gate_manifest.py \
     tests/test_check_full_test_debt.py tests/test_run_quality_gate.py -q
du -sh evidence/QualityGate/          # 应大幅缩小
# 双跑：cold 建基线 + cache 验证复用仍工作
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
git commit -m "refactor: phase2 门禁元系统瘦身（增量塌缩/指纹简化/必跑改标记）"
```

---

## 第 5 章　Phase 3 — main-style 子进程 → 标准 pytest

> **背景**：196 个 regression 脚本写成了"有 main() 没 test_"的老式可执行脚本，conftest 给每个起一个独立 Python 子进程跑（`conftest.py:79-86`）。196 次解释器冷启动 + 47 个还各自 `create_app`(~0.45s)，白白多花 ~54s。转成标准 pytest 函数后：省时间、能并行、有 fixture 复用、断言失败能自省。
> **风险**：中（全局状态泄漏是唯一陷阱）。**置信度**：A=高、B=高、C=很高。
> **三类归桶已精确完成**（A=87 / B=106 / C=3，完整清单见第 9 章）。**按 C→B→A 逆序做**：先消污染源，再批量转。

### 5.1 子阶段 3.0 — 先转 3 个 C 类（污染源，必须最先）
**为什么最先**：它们 monkeypatch 了全局对象且不恢复。若它们转成 A/B 进了同进程，会污染相邻测试。

| 文件 | 污染点 | 改法 |
|---|---|---|
| `regression_ortools_warmstart_skip_nonfinite.py` | `sys.modules["ortools"]=...`（:89-92）无还原 | 改用 `monkeypatch.setitem(sys.modules, "ortools", fake)`（退出自动撤销） |
| `regression_schedule_service_reschedulable_contract.py` | 8 个模块函数 `schedule_service_mod.X=stub`（:141-148），finally(:327) 不还原 | 8 处全改 `monkeypatch.setattr(schedule_service_mod, "X", stub)` |
| `regression_start_and_rerun_route_resolution.py` | 全局 `subprocess.Popen=_fake`（:171）无还原 | `monkeypatch.setattr(rerun_mod.subprocess, "Popen", _fake_popen)`；其余局部 patch 保留 |

验证：
```bash
.venv/bin/python -m pytest tests/regression_ortools_warmstart_skip_nonfinite.py \
     tests/regression_schedule_service_reschedulable_contract.py \
     tests/regression_start_and_rerun_route_resolution.py -q
```

### 5.2 子阶段 3.1 — 抽共享 fixture 到 conftest
**背景**：当前 `tests/conftest.py` 没有任何 fixture（很干净）。B 类 106 个文件各自重复建 app/db 样板，抽到 conftest 收益最大。
```python
# tests/conftest.py 新增
@pytest.fixture
def mem_conn():
    """内存 sqlite + ensure_schema，供 B-2(59文件) 复用。"""
    ...
@pytest.fixture
def db_conn(tmp_path):
    """临时落盘 sqlite + ensure_schema(schema_path=REPO_ROOT/'schema.sql')。"""
    ...
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """create_app + test_client，供 B-1(47文件) 复用。
    关键：monkeypatch.setenv 设 APS_DB_PATH/APS_ENV/SECRET_KEY（自动还原），
    monkeypatch.delitem(sys.modules,'app'/'app_new_ui') 强制重新 import。"""
    ...
```
> APS_ENV 有 development/production 混用，拆 `dev_client`/`prod_client`/`new_ui_client` 三个变体。

### 5.3 子阶段 3.2 — B 类转换（106 个，每批 ~20 文件一 commit）
**通用配方**（以 A 类样本 `regression_dispatch_rule_case_insensitive.py` 演示，B 类同理 + 换 fixture）：

改前（真实，已读）：
```python
import os
import sys
def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(...):
        return repo_root
    raise RuntimeError(...)
def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from core.algorithms.dispatch_rules import DispatchRule, parse_dispatch_rule
    assert parse_dispatch_rule("CR") == DispatchRule.CR, "CR 大小写容错失败"
    ...
    print("OK")
if __name__ == "__main__":
    main()
```
改后：
```python
from core.algorithms.dispatch_rules import DispatchRule, parse_dispatch_rule
def test_dispatch_rule_case_insensitive() -> None:
    assert parse_dispatch_rule("CR") == DispatchRule.CR, "CR 大小写容错失败"
    ...
```
配方步骤：
1. `def main()` → `def test_<去 regression_ 前缀>()`；删尾部 `if __name__ == "__main__": main()` 和 `print("OK")`
2. 删 `find_repo_root()` 定义 + `sys.path.insert`（`conftest.py:11-13` 已注入 REPO_ROOT）
3. import 可上提到模块顶部
4. 裸 assert 全部保留（转 pytest 后自动 assert-rewrite，失败信息更好）
5. B 类：建 app/db 样板 → 改用 §5.2 fixture 参数
6. **22 个灰名单文件**（patch 全局但有 finally 还原的，清单见第 9 章）：一律改 `monkeypatch.setattr`，**绝不能机械地把 patch 提到函数外**，否则退化成 C 类污染源

### 5.4 子阶段 3.3 — A 类转换（87 个，可脚本批改）
配方同 §5.3 的 1/2/3/4。A 类不涉及 app/db。可写一次性批改脚本，但**跳过 12 个 A-灰名单**（第 9 章），它们要人工改 monkeypatch。

### 5.5 子阶段 3.4 — 移除 main-style collector
196 个全转完后，删 `tests/conftest.py` 的 `pytest_collect_file`/`RegressionMainFile`/`RegressionMainItem`（:51-106）+ `tests/main_style_regression_runner.py`。若保留极少数白名单（如 start_and_rerun），则缩小 collector 到只服务白名单。

### 5.6 子阶段 3.5 — 启用 pytest-xdist（执行 D-3）
- 离线下载 `pytest-xdist` wheel 放 vendor，`requirements-dev.txt` 增依赖
- 串行测试加 `@pytest.mark.serial`，门禁改 `pytest -n auto --dist loadgroup`
- `tools/full_test_debt_shards.py` 的串行分类逻辑可改用标记驱动

### 5.7 Phase 3 验证 + 提交
```bash
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -5    # 收集数应增加
.venv/bin/python -m pytest -q tests 2>&1 | tail -20                  # 全量跑，对比 Phase0 pass 集
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```
> **泄漏自查**：若某测试单跑过、全量跑挂 → 几乎一定是全局状态串味 → 回 §5.1/第 9 章灰名单查 monkeypatch 是否漏改。

---

## 第 6 章　Phase 4 — 业务测试合并（同构簇参数化）

> **背景**：这是病根二。同一个业务契约被拆成 N 个微文件反复测，每个都重复样板。把它们的差异点收进参数化表，合并成 1-N 个文件。
> **风险**：中（需逐簇核对断言不丢覆盖）。**置信度**：中-高。
> **前置门槛**：§6.3 前端域必须等 resource_dispatch JS 拆分落定后再做；其余域可先行。
> **统一做法**：抽公共 fixture → `@pytest.mark.parametrize` 收差异 → 合并 → `git rm` 原文件 → 跑定向测试 → §2.4 刷新基线。

### 6.1 调度域（C agent，按收益排序）
| 簇 | 文件（精确） | 合并到 |
|---|---|---|
| plan_role 解析契约 | `regression_scheduler_candidate_{plan_query,week_plan,resource_dispatch,gantt_plan_role,reports,analysis}_contract.py` + `regression_scheduler_analysis_candidate_links_and_roles.py` + `regression_scheduler_plan_identity_evidence_contract.py` + `regression_scheduler_dispatch_plan_identity_guardrails.py`（9） | 3-4（核心契约 1 + 各页面薄冒烟） |
| 空集合拒绝 | `regression_schedule_service_{reschedulable_contract,empty_reschedulable_rejected,reject_no_actionable_schedule_rows,all_frozen_short_circuit}.py` + `regression_schedule_persistence_{reject_empty_actionable_schedule,reschedulable_contract}.py`（6） | 2（service 1 + persistence 1） |
| result_summary 字段 | `regression_schedule_summary_{algo_warnings_union,cfg_snapshot_contract,end_date_type_guard,fallback_counts_output,freeze_state_contract,input_fallback_contract,invalid_due_and_unscheduled_counts,merge_context_degraded_code,overdue_warning_append_fallback,size_guard_large_lists,v11_contract}.py`（11） | 2-3（正常摘要 / 降级 fallback / size_guard） |
- 先抽 seed 样板 `_seed_candidates`/`_seed_schedule_context`（8 文件共享）、`_make_conn`+`_batch_stub`（6+ 文件）到 conftest
- 60 个 ≤1 函数微文件按被测模块并入对应契约族
```bash
.venv/bin/python -m pytest tests/ -k "schedule or scheduler or sgs or greedy or optimizer" -q
```

### 6.2 数据域（E agent）
| 簇 | 文件（精确） | 合并到 |
|---|---|---|
| 实体 import 守卫 | `test_machine_excel_import_apply_defense.py` / `test_op_type_excel_import_apply_defense.py` / `test_operator_excel_import_normalization.py` / `test_supplier_excel_import_remark_normalization.py` | 1 表驱动 `test_entity_import_apply.py`（按 service/字段/消息参数化） |
| renamed column 冲突 | `test_excel_renamed_column_conflicts.py`（内含 3 实体 × HTTP 往返） | 1 核心单测 + 1 HTTP 冒烟 |
> 高价值算法测试全保留：calendar 跨天工时、resource_pool、supplier 选择、unit 换算、part strict 原子性（第 7 章）。
```bash
.venv/bin/python -m pytest tests/ -k "excel or batch or calendar or supplier or unit or part" -q
```

### 6.3 前端域（D agent）⚠️ 等 JS 拆分落定
| 簇 | 文件（精确） | 合并到 |
|---|---|---|
| degraded/overdue 退化 | `regression_gantt_{bad_time_rows_surface_degraded,invalid_summary_surfaces_overdue_degraded,partial_overdue_summary_surfaces_warning}.py` + `regression_resource_dispatch_{同三个}.py` + `regression_week_plan_bad_time_rows_surface_degraded.py`（7） | 1 service 单测 + 1 页面参数化 |
| version_default_latest | `regression_{analysis,gantt,reports,reports_export}_page_version_default_latest.py`（4） | 1 参数化 |
| resource_dispatch 契约 | `regression_resource_dispatch_site_records_frontend_contract.py` / `regression_resource_dispatch_workbench_lane_contract.py` / `regression_scheduler_ui_range_feedback_contract.py` | 1（URL 抑制抽 helper，删属性顺序/文案黑名单） |
| `*_layout_contract` 快照 | 11 个 | 2-3（CSS 像素断言已在 Phase 1 删） |
| page_header | `regression_page_header_plain_purpose_contract.py` + `regression_scheduler_page_header_contract.py` | 1 |
> 文案巨文件 `regression_frontend_ui_language_polish.py`(22函数) → 删/瘦身（文案不逐字断言）。

### 6.4 杂项域（G agent）
| 簇 | 文件（精确） | 合并到 |
|---|---|---|
| startup_portfile 双子（95%重复） | `regression_startup_host_portfile.py` + `regression_startup_host_portfile_new_ui.py` | 1 参数化(app, ui_mode)。**注**：B-1 类，§5.3 转 pytest 时顺便合并 |
| seed_results | `regression_seed_results_{dedup,drop_duplicate_op_id_and_bad_time,freeze_missing_resource,invalid_op_id_dedup}.py`（4） | 1-2 参数化。**注**：`regression_seed_results_dedup.py` 的 main 已是 `for mode in ("batch_order","sgs")` 循环，天然适合参数化 |
| app_new_ui smoke | `regression_app_new_ui_{create_app_smoke,secret_key_runtime_ensure,security_hardening_enabled,session_contract}.py`（4） | 1（B-1 类，§5.3 顺便合并） |
| operation_execution 跨层重复 | 不删文件，砍 route 层重复的"非官方方案拒绝"×3、状态机穷举 | 57→~40 函数 |
| config 文案否定断言 | `regression_config_field_spec_contract.py:167-190` | 砍 ~30 行否定断言 |
> `OperationExecutionEvents` 全表 DDL 在 `regression_migrations.py` 复制 5-6 次 → 抽共享常量。
> **反向提醒**：migration 无过期、反有缺口（v3/v6/v7/v10-v13/v16/v17 缺 dedicated），**勿误删现有 v2/v4/v5/v8/v9**。

### 6.5 Phase 4 验证（每域独立 commit）
```bash
.venv/bin/python -m pytest --collect-only -q tests 2>&1 | tail -5
.venv/bin/python -m pytest tests/ -k "<该域关键字>" -q
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

---

## 第 7 章　Phase 5 — 收尾、基线固化、文档同步

> **背景**：清理完成后把门禁基线重建到稳定态，更新文档，产出验收报告闭环。

### 7.1 基线全量刷新
执行 §2.4 全套 SOP，确保 `required_regressions.json`、`full_test_debt_summary.json` 等反映清理后的新 nodeid 集合。

### 7.2 文档同步
- `static/docs/scheduler_manual.md` / `web_new_test/static/docs/scheduler_manual.md`：若涉及测试命令说明
- `.codestable/architecture/ARCHITECTURE.md`：更新测试/门禁现状描述
- 写验收报告 `.codestable/refactors/2026-06-01-test-gate-cleanup/acceptance.md`（对照本计划逐 Phase 核实 + 量化收益实测值）

### 7.3 最终验收
```bash
.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
git status --porcelain    # 必须干净（门禁要求 clean worktree proof）
```

---

## 第 8 章　务必保留清单（删了会漏真 bug）

经实读断言确认是真实业务护栏，**任何阶段都不动**：
- **算法内核**：SGS 评分与执行一致性、贪心排序/就绪门控、OR-Tools warmstart 失败契约、优化器种子边界、freeze 窗口上下界、downtime 区间避让
- **数据正确性**：calendar 跨天工时推进、工时 0/负值不静默归零、resource_pool 停机合并、supplier 有效选择、unit Excel 换算、part strict 原子回滚
- **DB 迁移**：v2/v4/v5/v8/v9（其余版本缺 dedicated，是缺口不是冗余）
- **执行反馈**：operation_execution service 层状态机 + `threading` 真并发幂等竞争
- **事务**：savepoint 嵌套回滚/commit 失败闭合
- **架构守卫**：`test_architecture_fitness.py`（route 不直连 SQL、service 不 import flask.request、无循环依赖）
- **scheduler_graph/ 子目录**（17 文件 176 函数）：与 graph 包 1:1 的健康单元测试，整体保留

### 不可删 load-bearing 脚本（禁止 git rm）
- `tests/run_complex_case_and_export_gantt.py`（被 `regression_gantt_critical_outline_sync.py:703,786` importlib 加载）
- `tests/run_complex_excel_cases_e2e.py`（被 `regression_request_service_test_factory_invariant.py:15` import + `quality_gate_shared.py:218,252` 扫描契约）
- `tests/run_real_db_replay_e2e.py`（被 `regression_request_service_test_factory_invariant.py:16` import + `quality_gate_shared.py:217,251` 扫描契约）
- `tools/full_test_debt_shards.py`（被 6+ 处依赖，仅删 :53 死子条件）
- `tools/benchmark_full_test_debt_shards.py`（4 处门禁织入：`quality_gate_shared.py:121`、`pyrightconfig.tools.json:13`、`test_registry.py:152,263`、`test_long_gate_manifest.py:330`。如要删需协调改这 4 处 + 删其测试，本计划不删）

---

## 第 9 章　附录：main-style 196 文件三类归桶（Phase 3 用）

> 判定：`^\s*def main\(` 命中且无 `^\s*def test_`。优先级 C>B>A。完整列表来自专项 SubAgent 逐文件核对。

### C 类（3 个，全局污染未恢复，最先处理）
1. `regression_ortools_warmstart_skip_nonfinite.py`（`sys.modules["ortools"]` 注入 :89-92）
2. `regression_schedule_service_reschedulable_contract.py`（模块函数替换 :141-148，finally :327 不还原）
3. `regression_start_and_rerun_route_resolution.py`（全局 `subprocess.Popen` :171）

### B-1 类（47 个，create_app/test_client → app_client fixture）
含 5 个已 finally 还原的灰名单：`report_export_large_scope_rejects_need_async`、`report_export_size_mode_selection`、`scheduler_run_no_reschedulable_flash`、`scheduler_week_plan_no_reschedulable_flash`、`system_health_route`。完整 47 个列表见审计输出（regression_app_db_path_no_dirname、regression_app_new_ui_* 等）。

### B-2 类（59 个，仅建真实 DB → db_conn/mem_conn fixture）
含 5 个已 finally 还原的灰名单：`schedule_service_all_frozen_short_circuit`、`empty_reschedulable_rejected`、`missing_resource_source_case_insensitive`、`passes_algo_stats_to_summary`、`database_high_version_failfast`。

### A 类（87 个，纯算法/stub → 可脚本批改）
含 12 个 A-灰名单（patch 全局但 finally 还原，**必须改 monkeypatch 不可机械提函数外**）：
`dict_cfg_contract`、`improve_dispatch_modes`、`optimizer_choice_case_normalization`、`optimizer_outcome_algo_stats`、`optimizer_zero_weight_cfg_preserved`、`ortools_budget_guard_skip_when_no_time`、`number_utils_facade_delegates_strict_parse`、`metrics_to_dict_nonfinite_safe`、`gantt_critical_chain_cache_thread_safe`、`runtime_probe_resolution`、`system_maintenance_throttle_short_circuit`、`unit_excel_converter_diagnostics_visible`。

> ⚠️ 灰名单最隐蔽：今天靠 try/finally 安全，机械转换若漏抄 finally 或把 patch 提到函数外，立即退化成 C 类污染源。尤其 `dict_cfg_contract`/`improve_dispatch_modes`/`optimizer_*`（4 个）都 patch 同一个 `schedule_optimizer` 模块，同进程相邻跑时一个 finally 断裂会串味其余三个。

---

## 第 10 章　风险登记

| 风险 | 阶段 | 缓解 |
|---|---|---|
| 全局状态泄漏致串味失败 | Phase 3 | C 类先转 + 22 灰名单改 monkeypatch + 单跑/全量对比 |
| 删测试后门禁基线失配 | Phase 1/2/4 | 每阶段执行 §2.4 SOP |
| 漏改 full_test_debt_shards 硬编码清单 | Phase 2.A | §4.1 第 3 步连带删 :20-21 |
| 误删 load-bearing 脚本 | Phase 1 | 第 8 章清单已 grep 证明，禁止扩列 |
| 合并丢真实覆盖 | Phase 4 | 逐簇核对断言差异，参数化保留每个边界 case |
| 与 resource_dispatch JS 拆分打架 | Phase 4.3 | 设前置门槛，等其落定 |
| 改门禁编排破坏 CLI 契约 | Phase 2.B M4 | 红线：不改对外 CLI，仅改内部命令计划，双跑验证 |

---

## 第 11 章　预计工作量与节奏

| Phase | 子任务数 | 建议 commit 数 | 相对工作量 | 可独立交付 |
|---|---|---|---|---|
| 1 零风险删除 | 5 | 3-4 | 小 | ✅ |
| 2 门禁瘦身 | 2.A + 4 项机制 | 5 | 中 | ✅ |
| 3 子进程转换 | C(3) + fixture + B(106) + A(87) + collector + xdist | 8-12（B/A 分批） | 大 | ✅ 分批 |
| 4 业务合并 | 4 域共 ~10 簇 | 10（每簇1） | 中-大 | ✅ 分域 |
| 5 收尾 | 3 | 2 | 小 | ✅ |

> Phase 3 是工作量大头（193 个文件改写），但**可任意分批**，每批 ~20 文件独立提交、独立验证，随时可暂停。
