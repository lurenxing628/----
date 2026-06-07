# P5.2 KEEP_TRIM — Batch B02_graph 修剪规范

适用实现 agent：本文件是唯一可执行依据。只用下面给出的 verbatim 锚点定位，不要相信任何行号（可能已漂移）。除明确列出的删除项外，一律保持原样。

---

## 文件：tests/scheduler_graph/test_graph_module_skeleton_contract.py

- 当前行数：33 行（末尾有换行，共 34 行含尾行）。
- 函数清单：
  1. `test_graph_module_skeleton_exists`（硬编码文件名清单快照 → **整函数删除**）
  2. `test_graph_modules_do_not_static_import_networkx`（AST 静态 import networkx 架构守卫 → **完整保留**）
- 模块级常量 `GRAPH_DIR`（第 8 行）：**必须保留**，被保留的 import-guard 测试 (`GRAPH_DIR.glob("*.py")`) 依赖。
- 模块 docstring（第 1 行）：**保持原样**，不要改。它同时描述两个守卫，删测试不需要改它，改它属于额外动作、零收益。
- sibling conftest：`tests/scheduler_graph/` 下无 conftest，无 fixture 依赖。

### TSV L3 裁决理由（keep_trim_files.tsv，value=mid）
> networkx no-static-import AST constraint is real arch guard but skeleton-file-existence half is brittle listing — test_graph_module_skeleton_contract.py:9-31

理由把脆性半边定位在“skeleton-file-existence”这一半，真守卫是 networkx AST 约束。原行号 9-31 已轻微漂移，按下方语义锚点（函数体文本）重新定位。

---

### 脆性项 1（唯一脆性项）：整函数删除 `test_graph_module_skeleton_exists`

**分类**：`hardcoded_path_list`（硬编码 `.py` 文件名清单快照）。

**为何脆性**：该函数唯一行为是断言 `{__init__.py, id_policy.py, nx_runtime.py, types.py}` 这 4 个文件名是当前 graph 目录 `*.py` 文件名集合的子集。它是一份按文件名钉死的目录清单快照：
- 任意一次合法重命名/拆分模块（例如把 `id_policy.py` 内容合进 `nx_runtime.py`，或拆出新文件）都会让它红，但这不是行为回归，只是结构漂移。
- 它用 `.issubset(...)` 而非 `==`，对“多出文件”已经宽容（当前 graph 目录实际有 14 个 .py，远多于这 4 个，测试照样过），说明它从设计上就只想钉“这 4 个名字在不在”，恰恰是最纯粹的文件名快照、最低信息量。
- 它不验证这些模块的任何行为、可导入性、内容；文件存在但内容空/坏它也照样过。真正的可导入性/惰性加载契约由第 2 个函数（AST 守卫）覆盖，与本函数不重叠也不依赖本函数。
- 无任何 registry/debt/contract nodeid 清单引用（见下方 grep），删除不会悬空任何引用。

**整函数删除的判定**：函数体只有一个 `expected = {...}` 字面量 + 一行 `assert ... .issubset(...)`，没有任何非脆性断言可保留 → 满足“整函数都是脆性快照”的整删条件（granularity = 整函数删，而非函数内删行）。

**删除锚点（verbatim 多行块，从空行到空行整段删除）**：

```python
def test_graph_module_skeleton_exists() -> None:
    expected = {
        "__init__.py",
        "id_policy.py",
        "nx_runtime.py",
        "types.py",
    }
    assert expected.issubset({path.name for path in GRAPH_DIR.glob("*.py")})
```

**保留上下文（删除后周围必须保留）**：
- 上方：模块 docstring（第 1 行）、`from __future__ import annotations`、`import ast`、`from pathlib import Path`、`GRAPH_DIR = ...`（第 8 行）全部保留。
- 下方：`def test_graph_modules_do_not_static_import_networkx() -> None:` 起的整个函数（含其全部 13 行函数体到 `assert offenders == []`）完整保留。
- 删除后 `GRAPH_DIR = ...`（第 8 行）与保留函数 `def test_graph_modules_...` 之间应保留标准的两个空行（PEP8 顶层定义间距）。原文件里 `GRAPH_DIR` 后跟两个空行再到第一个函数；删第一个函数后，让 `GRAPH_DIR` 与第二个函数之间为两个空行即可。

**registry/contract 耦合 grep 结果（已实跑，排除本文件自身）**：
- `grep -rn "test_graph_module_skeleton_exists" tools/ tests/`（排除自身）→ **NO HITS**
- `grep -rn "test_graph_module_skeleton_contract" tools/ tests/`（排除自身，查文件名/nodeid 级引用）→ **NO HITS**
- `grep -rln "scheduler_graph/test_graph_module_skeleton" tools/` → **NO TOOLS REF**
- `grep -rn "GRAPH_DIR|skeleton_exists" tests/scheduler_graph/`（排除自身）→ **NONE**
- 结论：无 registry/debt-registry/contract nodeid 清单引用，整删安全，不悬空。

---

### 保留项（MUST KEEP，不动）：`test_graph_modules_do_not_static_import_networkx`

真实架构守卫：AST 遍历 graph 目录全部 `*.py`，断言无任何 `import networkx` / `from networkx[. ]...` 静态导入（networkx 必须留给运行时惰性加载）。这是会抓真 bug 的行为/架构契约（误加静态 import 会破坏惰性加载约束）。完整保留，包括 `offenders` 列表逻辑、`ast.Import`/`ast.ImportFrom` 两个分支、`assert offenders == []`。

---

### B-4 红线处理

本文件 **不在** B-COMPAT B-4 红线清单内（B-4 红线只针对 `tests/test_enum_display_consistency.py` 与 `tests/regression_schedule_result_view_context.py`）。b4_redline = false。

### META-GATE 注意

本文件虽是 contract 测试，但删除的只是文件名存在性快照（最弱的一半），保留的 networkx 惰性加载 AST 守卫（理由明确称为“real arch guard”的那一半）完整保留。删第一个函数损失的“enforcement”仅为“这 4 个文件名按名存在”——已被第二个守卫隐式覆盖范围之外的、最低价值的钉名快照，不构成有意义的执法下降。

### 风险

**risk = low**。理由：(1) 无任何 registry/contract/debt 耦合（grep 全 NO HITS）；(2) 删除的函数用 `.issubset` 本就是弱不变量、零行为覆盖；(3) 真架构守卫与共享常量 `GRAPH_DIR` 完整保留，保留测试仍有 ≥1 个有意义断言；(4) 不触碰 import / fixture / docstring。

### 净行数估计

删除整个 `test_graph_module_skeleton_exists` 函数体共 9 行 + 其上方与 `GRAPH_DIR` 之间的两个空行中的一个（合并间距）≈ 删除 9~11 行。净估计 **est_lines_removed = 11**（含函数 9 行 + 多余空行折叠 2 行）。
