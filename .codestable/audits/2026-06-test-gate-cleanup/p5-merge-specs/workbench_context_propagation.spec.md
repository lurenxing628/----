# P5.1 MERGE 簇侦察 spec — workbench_context_propagation

> 状态：侦察完成（只读分析）。本文件是唯一写出物，未改任何被测/注册表文件、未跑门禁、未 git 操作。
> 铁律遵守：合并行为保真，参数化后断言条数 ≥ 合并前各文件之和；去重仅限逐字完全重复的同义断言；语义/边界/坏值不同一律保留。
> ★ 本簇含 REGISTRY 改动 + B-6 红线（R57 PIN）。

---

## ① 成员文件（行数）

| 文件 | 行数 | required? | 注册表登记? | 数据 setup |
|---|---:|---|---|---|
| `tests/regression_aps_workbench_first_round_flow_contract.py` | 254 | **否** | **未登记**（grep 全仓零命中：不在任何 QUALITY_GATE 列表、不在 groups、不在 split-scope 契约） | **自带独立** setup：`monkeypatch` + 本地 `_LinkCollector` + `_insert_first_round_data`（种 `B-WORK`/`B-PENDING`/version=12，`overdue_batches.count=2`，`candidate_comparison` 完整块） |
| `tests/regression_aps_workbench_flow_contract.py` | 433 | **是 (required)** | data:99, groups_scheduler:302, helper-impact:251, split-scope契约:87 | **复用共享** `_client()`（来自 `reports_workbench_backlink_helpers`，种 `B-RPT`/`M-RPT`/`O-RPT`/`SCENARIO-RPT`） |
| `tests/regression_aps_workbench_report_row_links_contract.py` | 88 | **是 (required)** | data:100, groups_scheduler:303, split-scope契约:88 | **复用共享** `_client()`（同上） |

合计 775 行。

---

## ② 目标合并文件名 + 命名理由

**建议合并落点：`tests/regression_aps_workbench_context_propagation_contract.py`**

命名理由：
- 三个文件的共同语义内核是「workbench/首页/报表行 的链接在跳转时**保真透传上下文**（version/plan_role/date 窗/batch/resource）」——`context_propagation` 精确概括，且与簇名一致。
- 不沿用任一旧名（`flow_contract` / `report_row_links_contract`），避免读者误以为只是其中一个文件的扩写；新名表达「合并体」。
- 仍带 `regression_aps_workbench_` 前缀，归入 scheduler 报表组的既有命名族，注册表分组归属不变。

> ⚠ **阻塞性裁断点（见 ⑩）**：成员 1（first_round）的数据 setup 与成员 2/3 **不可互换**。是否把 first_round 一并并入、还是只合并 2+3（两个 required、同 `_client()` 设施）保持 first_round 独立，需 owner 拍板。本 spec 给出**两种方案**，默认推荐**方案 B（只合 2+3）**——风险最低、registry 改动最干净。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

> 断言条数说明：`grep "assert "` 严重**低估**——大量断言藏在 `_assert_*` 辅助里、且在 `for` 循环里按元组条数倍乘。下表给出**展开后的断言等价条数**（含辅助内部 assert × 循环次数）。

### 成员 1 — `regression_aps_workbench_first_round_flow_contract.py`（1 个 test）

`test_first_round_workbench_flow_preserves_context_from_homepage_links(monkeypatch)`
- 顶层文案断言 9 条（`计划工作台`/`首页值班台`/`今日待处理`/`超期批次需要先看`/`方案需要确认`/`资源负荷偏高`/`现场情况待确认`/长文案/`必须补录` not in）
- `INTERNAL_VISIBLE_TOKENS` 循环 6 条（首页）
- 6 个入口 query 校验：analysis(4) / gantt(5) / dispatch(5, 含 `scope_type==["operator"]`) / execution(4) / overdue(4) / utilization(5) = 27 条
- `target_pages` 6 元组循环 × (status 200 + 计划工作台 + 首页值班台 + expected_text + 6×token) = 6 × 10 = 60 条
- **小计 ≈ 102 条断言等价**

关键/坏值/边界逐字摘录（**保真不可漏**）：
```python
assert "待处理项根据当前数据实时生成，暂不保存已处理状态。" in visible_text
assert "必须补录" not in visible_text          # 反向断言（must-NOT）
assert dispatch["scope_type"] == ["operator"]  # first_round 特有：未带 resource_id 时回落 operator 视角
assert resp.status_code == 200, f"{label} -> {href} 返回 {resp.status_code}"
```
- 数据特征：`_insert_first_round_data` 种 `overdue_batches.count=2`、`candidate_comparison.planned=3/completed=2/adopted_key="graph_w1_of_3"`、有 `B-PENDING`（pending 状态批次）。这套数据让「超期批次需要先看 / 方案需要确认」等首页卡片**有内容**——与成员 2/3 的 `_seed_reports_data`（`overdue_batches.count=1`、无 candidate_comparison）**语义不同，不可合并去重**。

### 成员 2 — `regression_aps_workbench_flow_contract.py`（4 个 test，含 R57 PIN）

`test_workbench_main_flow_from_home_keeps_context_and_reaches_first_version_pages`
- 顶层 3 文案 + `_assert_public_visible_text`(6) + `_assert_public_output_boundaries`(visible6+payload6+attr4+links4=20)
- `_assert_home_workspace_links_keep_context` 4 标签 × 各 query 多键 ≈ 4 标签命中 + seen==set = 17 条
- `expectations` **7 元组**循环 × (query 多键校验 ~7 + target_text in + public_visible(6) + boundaries(20) + home_link query ~7) ≈ 7 × 41 ≈ 287 条
- **小计 ≈ 333 条**

`test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese`  ← **★ B-6 / R57-PINNED**
- `_assert_no_execution_review_links`(1) + `:346` + `:347` + `_assert_public_visible_text`(6) + `:352`/`:353`/`:354`/`:355` + 第二轮 home 页 `_assert_no_execution_review_links`(1) + `:360` ≈ 16 条

`test_workbench_scenario_preview_home_entry_is_read_only_and_does_not_use_current_summary`
- `测试模拟方案` in + `_assert_read_only_home_gap`（4 must-in + 5 must-not-in-visible + 3 must-not-in-surface = 12）+ no_review(1) + `计划和现场实际只复盘正式采用方案` in + public_visible(6) + boundaries(20) + analysis query 8 键 ≈ 49 条

`test_workbench_superseded_adopted_home_entry_keeps_guardrail`（先 `_seed_newer_executable_version(13)`）
- home_query 7 键 + `历史正式方案（已被新版本替代）` in + `_assert_read_only_home_gap`(12) + boundaries(20) + no_review(1) + `这是历史正式方案，只能查看` in ≈ 42 条
- **成员 2 小计 ≈ 333 + 16 + 49 + 42 = 440 条断言等价**

### 成员 3 — `regression_aps_workbench_report_row_links_contract.py`（1 个 public test + 2 私有 helper）

`test_workbench_report_rows_keep_batch_and_resource_context_when_returning_to_action_pages`
→ 调 `_assert_overdue_row_workbench_links`（overdue gantt 6 键 + dispatch 6 键 = 12）+ `_assert_utilization_row_workbench_links`（row_dispatch 5 键 + row_gantt 4 键 = 9）
- **小计 ≈ 21 条断言等价**

---

## ④ 共享 setup → 建议 fixture（复用 conftest 哪个 / 缺口）

| setup 元素 | 成员 1 (first_round) | 成员 2/3 (flow + report_row) | 复用建议 |
|---|---|---|---|
| 建库 + schema | 本地 `_prepare_env`+`ensure_schema` | helper `_prepare_env`+`ensure_schema`（`_client()` 内） | **不复用 conftest 的 `app_client`**：本簇必须用 `reports_workbench_backlink_helpers._client()`，因为它装载的是 **v1 UI（cookie `aps_ui_mode=v1`）+ 专用 reports 种子**，conftest 的 `app_client` 只导顶层 `app` 不带这套种子/cookie。 |
| app 装载 | 本地 `_load_app`（清 `app`/`entrypoint`/`factory`） | helper `_load_app`（**额外清 `web.routes.scheduler*` / `web.routes.domains.scheduler*`**） | 成员 2/3 的清模块范围更宽（含 scheduler 路由），first_round 的窄——**这是 setup 不兼容的第二个证据**。 |
| 数据种子 | `_insert_first_round_data`：B-WORK/B-PENDING、count=2、candidate_comparison | `_seed_reports_data`：B-RPT/M-RPT/O-RPT/SCENARIO-RPT、count=1、无 candidate | **语义不同，不可合并** |
| HTML 解析 | 本地 `_LinkCollector`（轻量，只 links+visible） | helper `_PageParser`（重，含 inputs/public_payload/public_attribute） | 成员 1 的断言只需 links+visible；若并入须改用 `_PageParser` 重跑——可行但要核 `public_attribute_parts` 不引入新失败 |

**结论**：成员 2 + 3 共享 `_client()` / `_parser_for` / `_query` 等 helper，零设施缺口，**直接合并即可**。成员 1 自带一套独立设施，**conftest 无对应 fixture**，强行并入需把它的 4 个本地函数（`_prepare_env`/`_load_app`/`_insert_first_round_data`/`_collector_for_home`）整段搬进合并文件并保留 `monkeypatch` 入参——可行但放大 diff 与回归面。

> conftest 缺口记录：本簇所需的「v1 UI + reports workbench 种子 client」已由 `tests/reports_workbench_backlink_helpers._client()` 提供，**不建议**为此再往 conftest 加 fixture（该 helper 已是 4 个测试的共享真相源，见 registry `TEST_ONLY_HELPER_IMPACT`）。

---

## ⑤ 参数化方案（差异收进 parametrize 的维度）

### 方案 B（推荐）：只合 2+3 → `regression_aps_workbench_context_propagation_contract.py`

合并体保留 **5 个 test 函数**（成员2 的 4 个 + 成员3 的 1 个），共用模块顶部 import（合并两份 import，去重逐字相同的 `from tests.reports_workbench_backlink_helpers import (...)`、`_assert_query_values` 同名同体只留一份）。

- **`_assert_query_values`**：成员2(:22) 与成员3(:13) **逐字完全相同**（`for key,value in expected.items(): assert query[key]==[value], (key,query)`）→ 这是唯一允许去重的逐字重复，合并后只留一份。
- 不做激进 parametrize：成员2 的 4 个 test 语义边界各异（主流程 / 非adopted禁用 / 场景预览只读 / 历史方案护栏），各自的 must-in / must-not / 第二跳页面断言不同，**强行 parametrize 会丢边界**。保持独立 def，仅共享 helper 与 `_client()`。
- 成员3 的 2 个私有 helper（`_assert_overdue_row_workbench_links`/`_assert_utilization_row_workbench_links`）原样搬入。

### 方案 A（如 owner 要求三合一）：额外并入成员1

- 成员1 整套本地设施（4 函数 + `_LinkCollector` + 常量）搬入，保留其 `monkeypatch` 参数化注入；该 test 不与 2/3 共享 `_client()`（数据不同）。
- 这等于「同一文件里两套 client 工厂并存」，可行但 diff 大、回归面广。**不推荐**。

无论 A/B，**参数化均不跨越数据语义边界**——count=1 vs count=2、有无 candidate_comparison、operator 回落 vs machine 视角，全部各自保留。

---

## ⑥ load-bearing import / importlib 引用（删原文件会断吗？）

grep 核实结论：
- **无任何 `.py` 用 `from tests.regression_aps_workbench_* import` 或 importlib 引用这三个成员**（跨文件 import 命中数 = 0）。三者是叶子测试文件，文件名仅作为「字符串」出现在注册表/契约里。
- 因此**删原文件本身不会断 import**；但文件名字符串出现在注册表 4 处（见 ⑦）+ 一处契约硬编码集合，**这些字符串必须同步改名/合并**，否则：
  - `regression_quality_gate_registry_split_scope_contract.py::test_workbench_flow_regression_is_required_and_grouped` 的 `assert test_paths <= QUALITY_GATE_REQUIRED_TESTS` 会**红**（旧名已不在注册表）。
  - 门禁按注册表跑 required 时，旧路径不存在 → collection error。
- 成员 1（first_round）**未被任何注册表/契约引用**，删它/留它都不触发门禁断裂（方案 B 下保持原样即可）。

---

## ⑦ registry 影响：须改 `tools/test_registry_data.py` 等条目（精确「旧→新」）

> 设合并落点 = `tests/regression_aps_workbench_context_propagation_contract.py`（记作 NEW）。**方案 B（合 2+3）须改 4 处文件、共 6 行**：

**`tools/test_registry_data.py`**
- L99 `"tests/regression_aps_workbench_flow_contract.py",`  → 改为  `"tests/regression_aps_workbench_context_propagation_contract.py",`
- L100 `"tests/regression_aps_workbench_report_row_links_contract.py",`  → **删除此行**（已被 NEW 取代；两行合一）
- L251 （在 `TEST_ONLY_HELPER_IMPACT["tests/reports_workbench_backlink_helpers.py"]` 元组内）`"tests/regression_aps_workbench_flow_contract.py",`  → 改为 NEW（report_row 原本不在此元组，无需加）

**`tools/test_registry_groups_scheduler.py`**（scheduler 组 `target_paths`）
- L302 `"tests/regression_aps_workbench_flow_contract.py",`  → 改为 NEW
- L303 `"tests/regression_aps_workbench_report_row_links_contract.py",`  → **删除此行**

**`tests/regression_quality_gate_registry_split_scope_contract.py`**（硬编码断言集合，函数 `test_workbench_flow_regression_is_required_and_grouped`）
- L87 `"tests/regression_aps_workbench_flow_contract.py",`  → 改为 NEW
- L88 `"tests/regression_aps_workbench_report_row_links_contract.py",`  → **删除此行**
  （集合去重后只剩 NEW 一条；其余 6 条不动。该契约的 `assert test_paths <= REQUIRED_TESTS` 与 `<= target_paths` 才会继续通过。）

> 方案 A（三合一）：在方案 B 基础上**无新增 registry 改动**——因 first_round 本就未登记；它的内容并入 NEW 后，NEW 已在注册表，覆盖即可。

> registry 改动 = **3 个文件**（data / groups_scheduler / split-scope契约），共 **6 行**（3 改名 + 2 删除 + L251 改名）。这正是本簇 ★REGISTRY 标记的来源。

---

## ⑧ B-COMPAT pin：必须逐字保留、禁去重的断言（R57-PINNED）

> **R57 PIN — 有意 fallback 透传**：当 `plan_role=baseline_best`（非 adopted）时，「计划和现场实际」复盘入口被**有意禁用**且首页链接**逐字透传非 adopted 的 plan_role**（不被偷偷改写成 adopted）。以下断言极易被误判为「与 adopted 主流程冗余」而去重——**逐条保留，标 R57-PINNED**。

来自 `tests/regression_aps_workbench_flow_contract.py`，函数 `test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese`，逐字：

```python
# :345
_assert_no_execution_review_links(parser)
# :346  R57-PINNED — 禁用态以 aria-disabled 暴露，禁去重
assert 'aria-disabled="true"' in html
# :347  R57-PINNED — 明语文案，禁去重
assert "计划和现场实际只复盘正式采用方案" in html
# ...
# :350-:351 取首页值班台 href 与 query
home_query = parse_qs(urlparse(home_href).query)
# :352  R57-PINNED — version 透传
assert home_query["version"] == ["12"]
# :353  R57-PINNED — ★核心：非 adopted 的 plan_role 原样透传，绝不改写成 adopted
assert home_query["plan_role"] == ["baseline_best"]
# :354  R57-PINNED — date 窗透传
assert home_query["date_from"] == ["2026-05-06"]
# :355  R57-PINNED — date 窗透传
assert home_query["date_to"] == ["2026-05-06"]
```

任务点名的 `:346 / :347 / :353` 全部覆盖；连带 `:352/:354/:355` 同属该透传簇，一并 PIN（同一 test 内、同一语义，拆开保留无意义）。**合并后此函数整体原样搬入，不得与主流程 adopted 断言做任何「同义合并」。**

附带 PIN（同一红线族，禁去重）：
- 成员2 `_assert_no_execution_review_links`（:44-49）+ 第二轮 home 页再断一次 no-review-link（:359）+ `:360` `计划和现场实际只复盘正式采用方案` ——这是「禁用态二次确认（首页同样禁用）」，与首页主流程不同语义。

---

## ⑨ 断言条数对账（前总和 → 后预期）

| 项 | 成员1 | 成员2 | 成员3 | 合计 |
|---|---:|---:|---:|---:|
| 展开后断言等价条数 | ~102 | ~440 | ~21 | **~563** |

- **方案 B（合 2+3）**：合并前 2+3 = ~440+21 = **~461**；合并后预期 **≥ 461**。唯一去重项 = `_assert_query_values` 函数体（**逐字完全相同**，:22 vs :13）保留一份——这是「同一辅助函数定义」去重，**不减少任何运行时断言**（两边调用点都仍调它）。故后预期断言条数 = **461，保真不减**。
- **方案 A（三合一）**：合并前 = ~563；后预期 ≥ 563。成员1 与 2/3 数据不同、零语义重叠，无可去重断言，后 = **563**。
- 红线复核：参数化未压缩任何元组维度（7-tuple / 6-tuple / 4-标签 全保留），无断言被 parametrize 吞掉。**结论：满足「后 ≥ 前」。**

---

## ⑩ 风险 / 阻塞点

1. **【阻塞·需 owner 裁断】方案 A vs B**：成员1（first_round）的数据 setup（B-WORK/count=2/candidate_comparison/B-PENDING）与成员2/3（B-RPT/count=1/无candidate）**语义不可互换**，且 `_load_app` 清模块范围不同（first_round 不清 scheduler 路由）。
   - 推荐 **方案 B（只合 2+3）**：两个 required、共用 `_client()`、registry 改动干净（6 行），first_round 原样保留为独立文件。
   - 方案 A 强行三合一会让一个文件里并存两套 client 工厂 + 两套种子，放大 diff/回归面，收益低。
2. **【高·registry 红线】split-scope 契约硬编码**：`regression_quality_gate_registry_split_scope_contract.py:87-88` 用**字面集合**断言两个旧名都 ∈ required ∧ ∈ target_paths。合并改名后**必须同步**该集合（见 ⑦），否则该契约测试直接红。这是「改注册表的同时要改校验注册表的测试」的连环点，最易漏。
3. **【中·R57 红线】B-pin 去重风险**：`:346/:347/:352/:353/:354/:355` 透传断言与主流程 adopted 断言形似，合并时**禁止**做「同义合并」。已在 ⑧ 逐字钉死。
4. **【中·helper 影响表】**`TEST_ONLY_HELPER_IMPACT["tests/reports_workbench_backlink_helpers.py"]`（data:249-254）含 flow_contract:251——改名须同步，否则该 helper 变更不会触发 NEW 重跑（影响面登记失真，门禁增量选择会漏跑）。report_row 原本不在此表，无需加。
5. **【低·解析器差异】**若走方案 A，成员1 须从本地 `_LinkCollector` 切到 helper `_PageParser`；`_PageParser` 会额外采集 `public_attribute_parts`，须确认 first_round 页面不因新采集面引入 `INTERNAL_*` token 误报（理论不会，但需实跑验证）。
6. **【低·文案/docs】**`docs/dev/aps_three_gap_quality_gate.md` 经 grep 未引用这三个文件名，**无需改文档**（已核实）。
7. **【提醒】**合并后须实跑 NEW 全量 + `regression_quality_gate_registry_split_scope_contract.py` + `tools/test_registry*`，确认 collection 无旧路径残留、契约不红——本 spec 不执行测试，按任务约束只读分析。
