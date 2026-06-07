# MERGE spec — 簇 `scheduler_route_registration`

> 类型: ★REGISTRY MERGE + B-5 锚点(R43 wrapper import)
> 侦察产出，只读分析 + 仅写本 spec。行为保真：合并后断言条数必须 >= 合并前各文件之和；去重仅限逐字完全重复的同义断言。

---

## ① 成员文件（各行数）

| 文件 | 行数 | 性质 |
|---|---|---|
| `tests/test_scheduler_route_registration_contract.py` | 101 | subprocess 探针验「惰性注册 / 叶子隔离 / 幂等」结构不变式 |
| `tests/test_scheduler_routes_still_registered_by_factory.py` | 42 | 经 `create_app()` 工厂烟测 4 条 scheduler 路由确已挂上 url_map |
| **合并前总计** | **143** | |

两文件主题同属「scheduler 路由注册契约」：前者从**模块加载层**（不经工厂、用子进程隔离 import 副作用）验注册器惰性与幂等；后者从**应用工厂层**（真实 `create_app`）验路由最终可达。互补不重叠，合并成单一「scheduler 路由注册契约」文件天然成立（与 `_CROSS_IMPACT_REPORT.md` 簇 1 判定一致）。

---

## ② 目标合并文件名 + 命名理由

**目标文件：`tests/test_scheduler_route_registration_contract.py`**（保留较大的 contract 文件名，把 factory 烟测函数并入，删除 `test_scheduler_routes_still_registered_by_factory.py`）。

命名理由：
- contract 文件已是 registry / SP05 / R43 多处锚点（见 ⑥⑦⑧），保留其文件名 = registry 字符串路径只需删 1 行、不需新增；B-5 的 R43 锚点函数仍在同一文件内，漂移最小。
- 「route_registration_contract」语义已涵盖「factory 注册」这一子契约，factory 烟测函数作为该契约的「工厂层证据」并入名实相符。
- 反向：若新建第三文件名，registry 两处都要「删 2 改 1」、R43 锚点文件也整体搬迁，无谓放大爆炸半径。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### A. `test_scheduler_route_registration_contract.py`（3 函数，10 条断言）

共享 helper：`_run_probe(source, *args)` — 子进程 `[sys.executable, "-c", source, *args]`，cwd=REPO_ROOT，解析 stdout 最后一行 JSON。其内含 1 条**结构性断言**（非业务契约，属 helper 自检）：
```python
assert completed.returncode == 0, (completed.stdout, completed.stderr)
```

1. `test_import_scheduler_root_does_not_register_full_scheduler_graph` — 3 条
   ```python
   assert payload["registered"] is False
   assert payload["loaded_analysis"] is False
   assert payload["loaded_run"] is False
   ```
   语义：纯 import `web.routes.scheduler` 根包**不得**触发注册、**不得**加载 analysis/run 叶子（惰性）。

2. `test_explicit_scheduler_registration_imports_route_graph_once` — 4 条
   ```python
   assert payload["registered"] is True
   assert payload["loaded_analysis"] is True
   assert payload["loaded_run"] is True
   assert payload["stable_after_second_register"] is True
   ```
   语义：显式 `register_scheduler_routes()` 才加载全图；**二次调用幂等**（`loaded_after == loaded_before`）。

3. `test_legacy_leaf_import_loads_only_requested_leaf` — 4 条 **【B-5 / R43 锚点函数】**
   ```python
   assert payload["loaded_root"] is False
   assert payload["loaded_registrar"] is False
   assert payload["loaded_analysis"] is False
   assert payload["loaded_run"] is True
   ```
   探针体内含 R43 要改的锚点行（原文件 :88）：
   ```python
   importlib.import_module("web.routes.scheduler_run")
   ```
   语义：直接 import 旧叶子 wrapper `web.routes.scheduler_run`**只**加载该叶子，不连带拉根包/registrar/analysis。

小计：`_run_probe` 自检 1 + 业务 11 = 文件内 `assert` 物理 12 条；**业务契约断言 11 条**（=3+4+4，其中 helper 自检 1 条不计入「业务断言对账」但合并后必须随 helper 保留）。

### B. `test_scheduler_routes_still_registered_by_factory.py`（1 函数，4 条断言）

私有 helper：`_load_app_factory(tmp_path, monkeypatch)` — 建 runtime/logs/backups/templates_excel 四目录，`monkeypatch.setenv` 五件套（APS_ENV=development / APS_DB_PATH / APS_LOG_DIR / APS_BACKUP_DIR / APS_EXCEL_TEMPLATE_DIR），`ensure_schema(...)` 建库，`sys.modules.pop("app", None)`，返回 `importlib.import_module("app").create_app`。

1. `test_scheduler_routes_are_registered_by_factory(tmp_path, monkeypatch)` — 4 条
   ```python
   assert "/scheduler/run" in rules
   assert "/scheduler/gantt" in rules
   assert "/scheduler/analysis" in rules
   assert "/scheduler/resource-dispatch" in rules
   ```
   `rules = {rule.rule for rule in app.url_map.iter_rules()}`。
   语义：真实工厂 `create_app()` 后 4 条 scheduler 路由 URL 规则确已挂上。**这 4 条是字面 URL 路径**——属边界/契约性字面值，不可与 A 文件任何断言去重。

小计：业务断言 4 条。

---

## ④ 共享 setup → 建议 fixture（标注复用 conftest 哪个 / 缺口）

- A 文件**无 DB/app 依赖**，全靠子进程 `_run_probe` 隔离副作用，**不引入任何 conftest fixture**。`_run_probe` + 模块级 `REPO_ROOT` 原样保留（B-5 锚点探针依赖它）。
- B 文件的 `_load_app_factory` 做的正是 conftest **`app_client` fixture 的等价物 + 还多 `sys.modules.pop("app")`**。但二者有**不可忽视的差异，不能直接换成 `app_client`**：
  - conftest 的 `app_client` 返回 **`app.test_client()`**，而 B 测试需要 **`app.url_map.iter_rules()`**（要的是 `app` 对象本身，非 test_client）。
  - conftest 的 `db_env` fixture（`app_client` 依赖它）已覆盖五件套 env + `ensure_schema` 建库，**与 `_load_app_factory` 的 env/建库部分逐项等价**。
  - **建议**：B 函数改用 conftest **`db_env`** fixture（已含五件套 env + ensure_schema 建库 + monkeypatch 自动还原），函数体内只保留：
    ```python
    sys.modules.pop("app", None)
    app = importlib.import_module("app").create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    ```
    复用 `db_env` 即可删掉 `_load_app_factory` 整个私有 helper（四目录创建 + 五件套 setenv + ensure_schema 全由 `db_env` 承担）。
  - **缺口**：conftest **无**「返回 app 对象（而非 test_client）」的 fixture。本簇**不新增** app-object fixture（仅此一处需要，`importlib.import_module("app").create_app()` 单行成本低于新增 fixture 的维护面）；保持 B 函数内联建 app。
  - **保真注意**：`sys.modules.pop("app", None)` 必须保留——它是 `app.py` 顶层重跑 create_app 的触发点，conftest 的 `_isolate_factory_exit_backup_globals` / `_isolate_os_environ` autouse 会兜住其 atexit/env 副作用，但 pop 本身的语义（强制 reimport 拿到当前 env 下的工厂）仍需显式写。

---

## ⑤ 参数化方案（差异收进 parametrize 的维度）

A 文件 3 个 `_run_probe` 探针的 **source 各不相同**（import 的模块、检查的副作用、调用序列都不同），强行 parametrize 会把三段异构 source 压成一个难读的数据表，**降低可读性且无收益**——**建议不 parametrize A 的三个探针函数**，原样保留三个独立 test 函数。

唯一可做的轻量参数化（可选，非必须）：B 函数的 4 条字面 URL 断言可收进 `@pytest.mark.parametrize("rule", ["/scheduler/run", "/scheduler/gantt", "/scheduler/analysis", "/scheduler/resource-dispatch"])`，但这样会**把 1 个测试拆成 4 个 node**，改变 nodeid 拓扑（影响 registry「文件级」登记无碍，但 P4 serial 分类按 nodeid，需复核）。**建议保守不拆**：保留单函数 4 条 `in rules` 断言（4 条全部逐字保留，见 ⑨）。

> 结论：本簇本质是**两文件物理合并 + B 复用 `db_env` 删私有 helper**，**不做断言层 parametrize**（异构探针 + 字面 URL 边界值都不宜合并维度）。这是行为保真最稳的形态。

---

## ⑥ load-bearing import / importlib 引用（grep 核实）

- **无任何 Python `from tests.xxx import` / `import test_scheduler_*`** 引用——已 grep 核实（`grep -rn "from tests.test_scheduler_route_registration_contract|import ..." → 无 Python import 引用`）。两文件均**仅以字符串路径**被 registry 登记。
- 因此**删 `test_scheduler_routes_still_registered_by_factory.py` 不会断任何 Python import**；唯一断点是 registry 字符串路径（见 ⑦）。
- 文件**内部** importlib 引用（探针 source 内的 `importlib.import_module("web.routes.scheduler...")`）是被测对象、随函数体保留，不受合并影响。

---

## ⑦ registry 影响：须改的 `tools/test_registry_data.py` 条目（精确旧 → 新）

合并后 `test_scheduler_routes_still_registered_by_factory.py` 被删，其字符串路径登记须**删除**（contract 文件路径保留不动）。共 **2 个文件、各 1 处**：

1. **`tools/test_registry_data.py`** — `QUALITY_GATE_GUARD_TESTS`（行 33-34）
   - 旧（两行）：
     ```python
     "tests/test_scheduler_route_registration_contract.py",
     "tests/test_scheduler_routes_still_registered_by_factory.py",
     ```
   - 新（删第二行，保留第一行）：
     ```python
     "tests/test_scheduler_route_registration_contract.py",
     ```

2. **`tools/test_registry_groups_scheduler.py`** — group `scheduler_run_core` 的 `target_paths`（行 149-150）
   - 旧（两行）：
     ```python
     "tests/test_scheduler_route_registration_contract.py",
     "tests/test_scheduler_routes_still_registered_by_factory.py",
     ```
   - 新（删第二行，保留第一行）：
     ```python
     "tests/test_scheduler_route_registration_contract.py",
     ```

> ★REGISTRY 红线：合并 commit 必须**同提交**改这 2 处，否则 `test_full_test_debt_registry_contract` / SP05 拓扑契约会因「登记了不存在文件」loud fail。`test_registry_data.py` 自身又在 `config_file_scopes`/`tool_file_scopes`，改它会触发 required-regression 全跑——属预期，非阻塞。
> 须改条目数：**2**（题目口径若仅计 `test_registry_data.py` 则为 1；本 spec 按「实际须改的 registry 数据文件」计为 2，含 groups_scheduler）。

---

## ⑧ B-COMPAT pin：必须逐字保留禁去重的断言

本簇 B-5 锚点（来自 `_B_COMPAT_*` / R43 dossier），合并后**必须逐字保留、禁去重**：

1. **B-5 / R43 wrapper import 锚点**（最高优先级，供 R43 按符号重定位）：
   ```python
   importlib.import_module("web.routes.scheduler_run")
   ```
   位于 `test_legacy_leaf_import_loads_only_requested_leaf` 探针 source 内（原文件 :88）。**禁删、禁改字符串**（R43-Batch-D 会把它改成 import 根包/domains 叶子；改的是 R43 不是本合并）。

2. **legacy 叶子隔离 4 条断言**（守 `web.routes.scheduler_run` 旧 wrapper 的「只加载自己」契约）：
   ```python
   assert payload["loaded_root"] is False
   assert payload["loaded_registrar"] is False
   assert payload["loaded_analysis"] is False
   assert payload["loaded_run"] is True
   ```

3. **B 文件 4 条字面 URL 边界断言**（URL 路径字面值即对外契约，禁与任何断言去重）：
   ```python
   assert "/scheduler/run" in rules
   assert "/scheduler/gantt" in rules
   assert "/scheduler/analysis" in rules
   assert "/scheduler/resource-dispatch" in rules
   ```

> **B-pin 断言计数：9 条**（4 叶子隔离 + 4 URL + 1 锚点 import 行本身按「禁改字符串」单列）。其中函数 `test_legacy_leaf_import_loads_only_requested_leaf` 整体禁动（函数名是 R43 的符号重定位入口）。

---

## ⑨ 断言条数对账（前总和 → 后预期）

| 维度 | 合并前 | 合并后预期 |
|---|---|---|
| A 文件业务断言 | 11（3+4+4） | 11（原样保留，三探针不合并） |
| A 文件 `_run_probe` 自检 assert | 1 | 1（helper 保留） |
| B 文件业务断言 | 4（字面 URL） | 4（逐字保留，不去重、不 parametrize） |
| **业务断言合计** | **15** | **≥ 15**（=15，无可去重项：A/B 无任何逐字完全重复的同义断言） |
| 物理 `assert` 行合计 | 16（含 helper 自检 1） | 16 |

**去重核查**：A 的 `payload["loaded_run"] is True`（叶子隔离场景）与 B 的 `"/scheduler/run" in rules` 语义完全不同（一个是模块加载层、一个是 URL 注册层），**不构成逐字重复，全部保留**。A 三探针的 `registered`/`loaded_*` 断言虽字段名重叠，但分属「不注册 / 显式注册 / legacy 叶子」三种不同场景，**断言期望值不同（False vs True 组合不同）**，禁去重。

> 结论：合并后业务断言 **15 → 15**，满足 `合并后 >= 合并前各文件之和`。无任何断言被删。

---

## ⑩ 风险 / 阻塞点

1. **【阻塞性·★REGISTRY】** 必须**同提交**改 ⑦ 的 2 处 registry 字符串路径（`test_registry_data.py:34` + `test_registry_groups_scheduler.py:150`），否则登记指向已删文件 → SP05 / full_test_debt_registry 契约 loud fail。这是本簇唯一硬阻塞前置。
2. **【B-5 锚点漂移·告知 R43】** R43 原按裸行号 `:88` 定位 wrapper import。合并后该锚点**仍在 `test_scheduler_route_registration_contract.py`（文件名不变）的 `test_legacy_leaf_import_loads_only_requested_leaf` 函数内**，但**行号会因 B 函数并入而下移**（B 的 1 个 test 函数 + 可能保留的注释会追加在文件尾或之间）。
   - **新位（供 R43 按符号重定位，弃裸行号）**：
     - 函数名：`test_legacy_leaf_import_loads_only_requested_leaf`（**不变**，R43 用它 rg 定位）。
     - import 字符串：`importlib.import_module("web.routes.scheduler_run")`（**不变**，R43 用它 rg 定位）。
     - 预期新位置：仍是该函数探针 source 内的同一行；**建议合并时把 A 三函数（含本锚点函数）整体置于文件前段、B 的 factory 函数追加在文件末尾**，使锚点函数相对位置最稳（紧随 `_run_probe` helper 之后，约 :25-101 区间不变）。R43-Batch-D 执行时以 `rg 'importlib.import_module\("web.routes.scheduler_run"\)' tests/test_scheduler_route_registration_contract.py` 重新取行号即可，**禁依赖本 spec 写死的任何行号**。
3. **【保真】** B 函数复用 `db_env` 后必须保留 `sys.modules.pop("app", None)` + `importlib.import_module("app").create_app()`（不可改用 `app_client`，因需 app 对象取 `url_map`）；conftest autouse（`_isolate_factory_exit_backup_globals`/`_isolate_os_environ`）会兜 atexit/env 副作用，但 pop 语义须显式写。
4. **【低·serial 分类】** 合并后文件含子进程探针（A）+ 同进程工厂建 app（B）。B 原是 `tmp_path`/`monkeypatch` 隔离，A 是子进程隔离，合并后**同进程内先后跑**——`pytest_collection_modifyitems` 按 `classify_nodeid` 自动打 serial 标，文件级合并不改 nodeid 文件名，分类应延续；合并后建议 full gate 复核该文件是否被判 serial（B 的 create_app 同进程化可能要求 serial，与 conftest 既有机制一致，非新增风险）。
5. **【非阻塞】** 改 `test_registry_data.py` / `test_registry_groups_scheduler.py` 落在 `config_file_scopes`+`tool_file_scopes`，会触发 required-regression 全量重跑——预期成本，非风险。
