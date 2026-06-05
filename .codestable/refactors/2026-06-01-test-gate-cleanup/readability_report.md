# 测试可维护性分析报告 — APS 项目 `tests/`

分析日期：2026-06-05 ｜ 范围：`/Users/lurenxing/Documents/GitHub/----/tests/`（只读分析）

用户核心痛点（原话）：**“不看内容根本不知道它在测什么，非常难维护，极其繁杂。”**

本报告把“为什么难一眼看懂、难维护”挖到底，全部基于实测数据 + 30+ 文件抽样阅读。

---

## 0. 一句话结论

`tests/` 是一个 **625 个文件平铺在单层目录** 的测试堆。它有两套互不兼容的写法（主流 pytest 风格 + 旧的 `main()`+裸 assert 子进程风格），文件名靠 4-9 个单词拼一条句子来代替文档（因为模块/函数 docstring 几乎为 0），同一个被测模块被“1 个 bug/特性 = 1 个新文件”的习惯拆散成几十个命名各异的兄弟文件。**“难一眼看懂”不是错觉，是结构性的：没有任何分层、没有文档、命名是唯一的信息源，而命名本身已经长到 73 字符还互相同质化。**

---

## 1. 量化总览（全量测算，非抽样）

| 指标 | 数值 |
|---|---|
| `tests/` 单层 `.py` 文件总数 | **626**（含 conftest，分析时按 625 计） |
| 总代码行数 | **158,237 行** |
| 子目录数（真正用于分类的） | **2 个**（`scheduler_graph/` 17 文件、`regression/` 2 文件）→ 即 **97% 的文件平铺在根层** |
| 模块 docstring 覆盖率 | **4.5%**（28/625） |
| 函数 docstring 覆盖率 | **1.4%**（97/6878） |
| 裸 assert 占比（无 message 的 assert / 全部 assert） | **85.3%**（13,696 / 16,065） |
| main-style 文件占比（有 `main()`、无 `test_`） | **35.8%**（224/625） |
| pytest-style 文件占比（有 `test_`、无 `main()`） | **56.0%**（350/625） |
| 同时含 `main()` 和 `test_`（混血/迁移中途） | **6.2%**（39） |
| 既无 `main()` 也无 `test_`（脚本/工具） | **1.9%**（12） |
| 含 `find_repo_root`/`REPO_ROOT`/`parents[N]` 样板的文件 | **70.9%**（443/625） |
| 文件名长度：中位 / p90 / 最长 | **46 / 58 / 73 字符** |

> 注：`regression_` 前缀文件 = 469（75%），`test_` = 116，`smoke*` = 13。前缀并不指示风格——`regression_` 里既有 main-style 也有 pytest-style，**前缀无法告诉你这个文件该怎么跑、失败长什么样**。

---

## 2. 命名：文件名能否自解释测什么？

### 2.1 现象：文件名是一条被迫塞进 80 字符的英文句子

最长的 15 个文件名全部是 `regression_<模块>_<子模块>_<场景>_<行为>_<限定词>` 拼出来的长句：

- `regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`（73）
- `regression_batch_service_legacy_template_resolver_rejects_strict_mode.py`（72）
- `regression_schedule_service_missing_resource_source_case_insensitive.py`（71）

**正面看**：这些名字确实“努力在自解释”——它把场景写进了文件名，所以理论上不用打开就知道在测什么。
**反面看**：这恰恰是问题本身。因为**没有 docstring（模块 4.5%、函数 1.4%）**，文件名被迫承担本该由 docstring 承担的全部信息量，于是被撑到 70+ 字符还不够用，且：
- 在文件树/IDE 标签里被截断，看不到尾部最关键的“断言什么”；
- 多个名字共享 50+ 字符的公共前缀，肉眼扫描时**前缀全一样、要读到第 6、7 个单词才出现区别**。

### 2.2 后缀同质化：`_contract` 通货膨胀

469 个 regression 文件的末位单词分布：

| 末位后缀 | 数量 |
|---|---|
| `contract` | **143（30%）** |
| `guard` | 14 |
| `insensitive` | 12 |
| `visible` | 11 |
| `observability` | 8 |
| `degraded` / `safe` / `normalization` / `fallback` … | 各 5-7 |

**近 1/3 的文件叫 `..._contract.py`。** “contract” 已经稀释成无信息量的口头禅——它不告诉你这是 API 契约、HTML 模板契约、还是 DB schema 契约。要区分 `regression_scheduler_candidate_analysis_contract` / `_config_contract` / `_display_contract` / `_generation_contract`（同模块 4 个 `_contract`），**必须打开文件**——这正是用户痛点的字面复现。

### 2.3 命名模式（regression_X_Y_Z_W…）= 信息密度低的伪层级

文件名里的 `_` 分段其实是“假目录”：`regression_scheduler_candidate_*` 有 18 个文件，`regression_resource_dispatch_*` 15 个，`regression_operation_execution_*` 14 个。这套“用文件名前缀模拟目录”的做法，等于把目录树压平成字符串再拼回文件名，**既丢了目录的可折叠/可导航性，又付出了超长文件名的代价**。

**正例**（项目里已经存在的好样板）：`scheduler_graph/` 子目录下是 `test_metrics_critical_path.py`、`test_precedence_builder.py`、`test_ready_queue.py`——短名 + 目录分类，一眼可读、可折叠。这证明团队知道怎么做对，只是 97% 的文件没这么做。

**naming_problem 小结**：文件名被迫替代缺失的 docstring，导致超长（中位 46、最长 73）；末位 `_contract` 占 30% 造成同质化，同模块多个 `_contract` 文件必须打开才能区分；用 `_` 前缀模拟目录，丢失真目录的导航性又背上长名成本。

---

## 3. 结构：两套写法并存，可读性与失败可诊断性割裂

### 3.1 两种风格占比

- **pytest-style（56%）**：标准 `def test_xxx(tmp_path, monkeypatch)`，pytest 收集、原生 assert 重写、失败定位精确。
- **main-style（35.8%）**：`find_repo_root()` 样板 + `main()` + 裸 assert + `print("OK")` + `if __name__=="__main__"`。**由 conftest.py 拦截、用 `subprocess.run` 子进程跑**。
- **混血（6.2%）** + 脚本（1.9%）。

70.9% 的文件带 `find_repo_root`/`REPO_ROOT`/手动 `sys.path.insert` 样板——这是 main-style 历史遗留的“每个文件自己找根目录、自己接管 import”的复制粘贴税。

### 3.2 main-style 的失败报错有多差（用户痛点的第二个根源）

`conftest.py` 的 `RegressionMainItem.runtest`（第 75-101 行）这样跑 main-style 文件：

```python
completed = subprocess.run([sys.executable, runner, path], capture_output=True, text=True, ...)
if completed.returncode != 0:
    raise AssertionError("\n".join([
        f"{path.name} 子进程执行失败", f"returncode=...", f"cwd=...", f"script=...",
        "stdout:", completed.stdout, "stderr:", completed.stderr,   # ← 整坨拼接
    ]))
```

后果：一个 main-style 用例失败时，pytest 不会告诉你“第 102 行 assert 失败、左值 X 右值 Y”，而是给你**一大坨子进程的 stdout+stderr 文本拼接**。你拿到的是 traceback 的字符串影印件，没有 pytest 的差异高亮、没有变量内省、没有 `-l` 局部变量。要诊断必须：手动复制路径 → 在终端单独跑 `python tests/xxx.py` → 自己读 traceback。**这就是“极其繁杂”在调试环节的具体形态。**

### 3.3 裸 assert：85.3% 没有失败消息

`regression_scheduler_candidate_display_contract.py` 是典型：

```python
assert "analysisCandidateComparisonTable" in source
assert "candidate_comparison_display.rows" in source
assert "plan_role=" not in source
```

pytest-style 下原生 assert 还能被 pytest 重写出可读 diff；但 **main-style 跑在子进程里，assert 失败只剩裸 `AssertionError` 文本**，13,696 处裸 assert 里凡落在 main-style 文件的，失败时几乎不可读。

### 3.4 同名 setup 样板反复重写

抽样 `regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`：第 13-71 行是近 60 行的 `_build_app`（建临时 DB、塞 ResourceTeams/Operators/Machines/Parts/Batches/Schedule…）。这类 DB-seeding 样板在 `resource_dispatch_*`、`schedule_*`、`gantt_*` 等几十个文件里各写一份、互有微差，**没有共享 fixture**。改一次 schema 要扫几十个文件。

**structure_problem 小结**：两套不兼容写法（35.8% main-style 子进程 + 56% pytest）共存于同一目录，前缀不指示风格；main-style 失败被 conftest 降级成 stdout/stderr 整坨拼接，丧失 pytest 的精确定位；85.3% 裸 assert 在 main-style 下不可读；70.9% 文件背着 `find_repo_root`/`sys.path` 样板，且 setup（如 60 行建库）在数十文件里重复手写无共享 fixture。

---

## 4. 定位成本：625 文件平铺单目录

- **97% 文件在根层**，只有 `scheduler_graph/`（17）和 `regression/`（2）做了分目录。
- 要找“调度候选分析”的测试，得在 625 个文件里靠文件名前缀字符串匹配，而非进 `scheduler/candidate/` 目录。
- IDE 的文件树、`ls`、Git 改动列表全部被这一坨淹没。
- **隐藏耦合**：发现 9 个 regression 文件 `from regression_xxx import ...` 直接 import 兄弟文件的内部函数（如 `from regression_scheduler_candidate_analysis_contract import _comparison_summary`）。平铺目录让这种“按文件名跨文件取私有函数”变得容易且无约束——**重命名/移动任一文件都会静默打断这些 import**，是平铺结构催生的维护地雷。

**取舍**：按被测模块分目录（`tests/scheduler/`、`tests/excel/`、`tests/gantt/`…）能立刻把 625 压成十几个可折叠分组，文件名可大幅缩短（目录已承载模块信息），并把 `scheduler_graph/` 的好模式推广开。代价是一次性的批量移动 + 修 import 路径，可脚本化。

---

## 5. 繁杂根源：1 bug = 1 文件

证据链：
1. 同一两词主题散落成几十文件：`scheduler_candidate` 18、`resource_dispatch` 15、`operation_execution` 14、`scheduler_analysis` 11、`schedule_summary` 11…
2. git 首次添加日期呈“每天滴几个”的长期细水（4/3 加 16 个、4/4 加 15 个、6/5 加 14 个……跨数十天均匀分布），不是“一次写一个 suite”的批量节奏——符合“每修一个 bug/加一个特性就新建一个对应 regression 文件”的工作流。
3. 后缀 `_contract`×143、`_guard`×14 等，是“为这次改动起个能塞进文件名的场景标签”的产物。

**链式后果**：1 bug=1 文件 → 同主题散落几十文件 → 每文件要独立命名 → 名字越来越长越同质 → 每文件自带 setup 样板和风格选择 → 风格混杂、样板重复 → **“不看内容不知道测什么 + 极其繁杂”**。这是一条因果链，不是孤立问题。

---

## 6. 建议（按性价比排序，优先解决“不看内容不知道测什么”）

1. **【最高性价比·先做】为每个测试文件补一行模块 docstring**：`"""验证 X 在 Y 条件下应 Z。"""`。当前覆盖率 4.5%，这是把“必须打开才知道测什么”直接逆转的最低成本动作，且可半自动化——文件名已含场景，可由脚本生成初稿 + 人工校。一行 docstring 比 73 字符文件名更可读、可被 grep、出现在测试报告里。
2. **【高】建一个 `pytest --collect-only` 驱动的“测试地图”**：把 625 文件按 `regression_<模块>_` 第二词聚合，输出“模块 → 文件 → 一行 docstring”的索引（Markdown 或 HTML），作为定位入口。不动文件就能先止血“找不到”。
3. **【高】禁止新增 main-style，存量批量迁到 pytest**：把 `main()`+裸 assert 子进程模式收敛为 `def test_*`，删 `find_repo_root`/`sys.path` 样板（70.9% 文件受益），换回 pytest 原生失败定位。优先迁最近还在改的 main-style 文件。可加 pre-commit 守卫：新文件含 `def main()` 且无 `test_` 即拒。
4. **【高】抽公共 fixture 替换重复 setup**：把数十份手写的“建临时 DB + 塞 ResourceTeams/Batches/Schedule”的 60 行样板收进 conftest 的 fixture（如 `seeded_app`），一处改 schema 全量生效。
5. **【中·一次性收益大】按被测模块分目录**：建 `tests/scheduler/`、`tests/excel/`、`tests/gantt/`、`tests/resource/` …把同前缀文件迁入，文件名随之缩短（目录已表达模块）。推广已存在的 `scheduler_graph/` 好样板。脚本化移动 + 全局修 `from regression_xxx import` 路径。
6. **【中】给裸 assert 补消息或改用 pytest 风格**：迁到 pytest 后原生 assert 重写已能给出 diff，可少量手补；对仍保留的关键断言加 message。85.3% 裸 assert 在迁移后大部分问题自然消解。
7. **【低·治本但慢】扭转“1 bug=1 文件”习惯**：约定“同模块同主题的回归用例合并进一个带多 `test_*` 的文件 / 参数化”，新建独立文件需有理由。从源头止住文件数膨胀。

---

## 7. notes（补充观察）

- **前缀不等于风格、不等于分类**：`regression_` 既混 main-style 又混 pytest-style，无法据前缀判断怎么跑、失败长什么样——这本身是迷惑来源。
- **隐藏的跨文件耦合**：9 个 regression 文件直接 import 兄弟 regression 文件的私有函数，平铺目录 + 长文件名让重命名/移动有静默破坏风险，分目录与迁移时需同步修这些 import。
- **混血文件（6.2%，39 个）是迁移中途态**：同时有 `main()` 和 `test_`，说明从 main-style → pytest 的迁移已在进行但未完成，与记忆库“主病是半截迁移”的结论吻合；建议把这 39 个作为迁移收尾的明确清单。
- **超大文件存在**：`test_long_gate_full_test_debt_cache.py` 4052 行、`test_run_quality_gate.py` 2969 行、`regression_gantt_critical_outline_sync.py` 1986 行——这些是质量门禁/缓存类“工具型测试”，与功能回归混在同一目录，进一步加重平铺目录的噪声，建议单独归到 `tests/_gate/` 或 `tools/` 旁。
- **已有正面样板可复制**：`scheduler_graph/` 子目录（短名 + 分类 + 全 pytest + 共享 `_node`/`_edge` 工厂）是团队自己写出来的“对的样子”，所有建议本质是把这个样板推广到其余 97% 的文件。
- 测算方法：风格/样板用正则全量扫描，docstring/assert 用 `ast` 全量解析（0 解析失败，结果可信）；文件名长度/前缀/后缀用 shell 全量统计；另抽样精读 ~12 个跨主题文件（main-style、pytest-style、`_contract`、`scheduler_graph`、超长名、含跨文件 import）交叉验证。
