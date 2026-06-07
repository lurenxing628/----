# 合并簇 spec：workbench_links_viewmodel（★REGISTRY + B-2 红线）

> 类型：P5.1 MERGE（行为保真合并）。本簇含 B-COMPAT 红线（B-2），含 registry 登记，含跨文件文档门禁波及点。
> 侦察员只读分析 + 只写本 spec，未改任何代码 / 未跑门禁 / 未 git 操作。

## ① 成员文件（各行数）

| 文件 | 行数 | test 函数数 | assert 行数(含 helper) |
| --- | --- | --- | --- |
| `tests/regression_scheduler_workbench_link_guardrails.py` | 258 | 10 | 45 |
| `tests/regression_scheduler_workbench_links_contract.py` | 473 | 6 | 83 |
| 合计 | 731 | 16 | 128 |

两文件被测对象完全相同：`web/viewmodels/scheduler_workbench_links.py`。import 块逐字一致，唯 contract 多 `from typing import Tuple`（仅用于其 helper 类型注解）。两文件各自定义了同名 helper `_query_values`（逐字一致，可去重为一份）。

## ② 目标合并文件名 + 命名理由

**目标文件：`tests/regression_scheduler_workbench_links_contract.py`（保留 contract，guardrails 迁入并删除）**

命名理由：
- 两份都是 `scheduler_workbench_links` viewmodel 的契约/护栏回归。"contract" 命名更概括（护栏是契约的一部分），且 registry/groups 两处都已登记此名。
- **关键收益（见 ⑥⑩）**：`guardrails` 文件名被 three_gap 文档门禁硬编码，`contract` 文件名不被该门禁引用。保留 contract、删 guardrails 可把文档门禁波及面收敛到"仅删一个文件名引用"，而非"删一个+改另一个"。
- 合并后建议在文件内用注释分区：`# --- 链接构造正向契约（原 ..._links_contract.py） ---` 与 `# --- 护栏与坏值拦放（原 ..._link_guardrails.py，B-2 红线，禁去重） ---`，以满足"合并 commit 须记录原 test 函数迁入新文件位置"的要求（见 commit 记录段）。

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### A. guardrails（10 函数，45 assert）—— 整体属 B-2 红线域，护栏断言禁去重

1. `test_feedback_write_url_guardrail_is_explicit`（assert：1 helper 调用 ×12 cases + 4 直接 = can_emit 四态/坏值矩阵核心）
   - 逐字关键（坏值/边界，B-pin）：
     - `assert can_emit_feedback_write_urls(context) is expected`（helper，对 12 个 case 逐一断言 True/False）
     - 12 cases 覆盖：current_official+dispatch+write→True；缺 can_dispatch / 缺 can_write_feedback / result_summary_parse_failed / 仅 can_write_feedback / 仅 plan_role=adopted / effective_plan_role=baseline_best / requested_plan_role 冲突 / plan_role=baseline_best / scenario_id 存在 → 全 False
     - `assert read_only_context["can_write_feedback"] is False`
     - `assert "只能查看" in read_only_context["guardrail_text"]`
     - `assert implicit_context["can_write_feedback"] is False`
2. `test_reports_index_requires_version_context`（3 assert）：`disabled is True` / `url == ""` / `"还没有排产版本" in disabled_reason`
3. `test_workbench_view_links_require_date_range`（3 assert，循环 4 页）：`disabled is True` / `url == ""` / `"日期范围" in disabled_reason`
4. `test_manual_disabled_link_requires_public_reason`（3 assert）：`disabled is True` / `url == ""` / `"暂时不可用" in disabled_reason`
5. `test_execution_review_guardrail_cannot_be_overridden_by_enabled_flag`（3 assert ×2 入口 direct/from_specs）：`disabled is True` / `url == ""` / `"只复盘正式采用方案" in disabled_reason`
6. `test_execution_review_guardrail_uses_full_plan_identity`（6 conflict_contexts ×3 + historical ×3 = 含 is_comparison/is_superseded，B-pin）
   - conflict_contexts：effective_plan_role=baseline_best / requested_plan_role=baseline_best / is_scenario_preview=True / is_current_executable_official_version=False / **is_comparison=True** / 缺 is_current_executable_official_version → 全 `"只复盘正式采用方案"`
   - historical：`dict(base, is_superseded_by_newer_version=True)` → `"历史正式方案" in disabled_reason`
7. `test_execution_review_requires_current_executable_identity_before_read_only_review`（逐步翻 is_current_executable_official_version False→True）：未设/False→disabled；True→`disabled is False` + `"plan_role=adopted" in url` + `"scenario_id" not in _query_values(url)` + `can_write_feedback is False`
8. `test_workbench_links_explain_blocking_identity_and_summary_parse_failure`（坏值解析）：
   - `"方案身份不可用" in dispatch["disabled_reason"]`（plan_identity_blocking_error）
   - `"当前排产摘要读取失败" in` / `"排产摘要内容不是有效 JSON" in` / `"json_decode_error" not in`（内部原因不外泄）
   - unknown reason：`"当前排产摘要结构无法安全解析" in` / `"debug_stack_code" not in`
9. `test_execution_review_rejects_scenario_identity_from_extra_params`（**forbidden_keys 红线**，B-pin）：
   - `forbidden_keys = ("scenario_id", "plan_role", "is_comparison", "can_write_feedback")`
   - 对每个 key：`build_workbench_link(..., extra_params={key:"leaked"})` 必须 raise ValueError 且 `"extra_params" in str(exc)`；否则 `raise AssertionError(f"...不能允许 extra_params 追加 {key}")`
10. `test_workbench_link_specs_fail_loudly_when_target_is_missing`：缺 target_page→ValueError `"target_page" in str(exc)`；非字典 spec→ValueError `"必须是字典" in str(exc)`

### B. contract（6 函数，83 assert，多在 helper）—— 正向 URL 参数保真矩阵

helper（被多个 test 复用，去重为一份）：`_query_values` / `_operator_context` / `_assert_url_fragments` / `_assert_gantt_link` / `_assert_dispatch_link` / `_assert_week_plan_link` / `_assert_utilization_link` / `_assert_execution_review_link` / `_machine_context_without_period` / `_assert_shared_context_fragments` / `_assert_dashboard_analysis_reports_context` / `_assert_dispatch_and_overdue_context` / `_assert_delay_context`

1. `test_workbench_context_and_link_keep_plan_date_and_resource_params`：operator 上下文五种页 URL 片段（gantt/dispatch/week_plan/utilization/execution_review），逐字片段含 `view=operator`、`gantt_batch=B202605-001`、`required_params` 顺序列表逐字。
2. `test_all_target_pages_preserve_full_workbench_context_matrix`：machine 视角，11 个 target_page × expected_query 全矩阵（dashboard/analysis/gantt/week_plan/resource_dispatch/overdue_report/delay_diagnosis/utilization_report/downtime_report/execution_review/reports_index），每页断言 `disabled is False` + query 值 + key in required_params。注意 gantt 用 `start_date/end_date`、dispatch 用 `period_preset=custom`+`scope_type/scope_id/machine_id`、utilization/downtime 用 `start_date/end_date`、其余用 `date_from/date_to`。
3. `test_preview_context_keeps_view_links_but_disables_execution_review`（preview/baseline_best + scenario）：`"scenario_id=scenario-secret" in overdue["url"]` / `"plan_role=baseline_best" in` / `context_summary.startswith("v12，模拟方案甲")` / review `disabled is True` + `url == ""` + `"只复盘正式采用方案"` + `"scenario_id" not in review["required_params"]`
4. `test_primary_resource_links_disable_unsupported_team_context`（team 维度坏值）：9 页 `disabled is True` + `"当前页面暂不支持班组维度筛选" in disabled_reason`；dispatch 例外 `disabled is False`+`scope_type=team`/`scope_id=T1`/`team_id=T1`，且 `"resource_type=team" not in`；gantt `"resource_type=team" not in`/`"resource_id=T1" not in`/`"team_id=T1" not in`/`"gantt_resource=T1" not in`
5. `test_dashboard_analysis_and_reports_links_keep_context_without_inventing_period`（无 period）：dashboard/analysis/reports 共享片段 + machine 片段；dispatch `period_preset=custom`+`scope_type=machine`+`machine_id=M1`；delay `/reports/overdue?` + `label == "查看延期说明"`
6. `test_target_pages_and_public_label_mappings_are_fixed`（标签映射 + 未知回退坏值）：
   - `set(TARGET_PAGE_PATHS) == {11 个页名}` 逐字
   - `plan_role_label("baseline_best") == "原算法代表方案"` / `plan_role_label("future_role") == "未知方案身份"`
   - `guardrail_reason_label("data_gap") == "数据不足，暂时不能判断"` / `("future_reason") == "未知限制原因"`
   - `resource_type_label("machine") == "设备视角"` / `("future_resource") == "未知资源视角"`
   - `period_preset_label("custom") == "自定义"` / `("future_range") == "未知日期范围"`
   - `gantt_view_label("operator") == "人员甘特"` / `("future_view") == "未知甘特视图"`

## ④ 共享 setup → 建议 fixture（标注复用 conftest / 缺口）

- **不需要 conftest 的 DB/app fixture**：本簇是纯 viewmodel 单元测试，无 DB、无 app_client、无 schema。`tests/conftest.py` 的 db_path/db_env/app_client/schema_conn/mem_conn/schema_path/repo_root 均**不适用**，不引入。
- 合并内部去重：两文件各有一份逐字相同的 `_query_values` → 保留一份模块级 helper。
- contract 的 `_operator_context()` / `_machine_context_without_period()` / 各 `_assert_*` helper 全部随 test 函数一并迁入（被对应 test 调用，不可丢）。
- guardrails 的 `_assert_feedback_write_allowed` helper 迁入。
- **缺口**：无。所有 setup 都是函数内 `build_workbench_plan_context(...)` 直接构造，无跨用例共享可抽 fixture 的状态（每个 test 的 context 参数各异，抽 fixture 反而损失差异覆盖）。建议保持 plain 函数 + helper，不引 fixture。

## ⑤ 参数化方案（差异收进 parametrize 的维度）

保守策略：**默认不强行 parametrize**，因 B-2 红线要求护栏断言逐条保留、可读可审。合并 = 物理并入同一文件 + 去重唯一一份 `_query_values`。可选的安全 parametrize 仅限以下"纯坏值回退表"，且参数化后断言条数 >= 原条数：

- 候选 1（contract test 6 标签回退）：`plan_role_label/guardrail_reason_label/resource_type_label/period_preset_label/gantt_view_label` 的 (输入, 期望) 可收进 `@pytest.mark.parametrize` 维度 `(label_fn, value, expected)`。**注意**：每个 (已知值→中文 / 未知值→"未知…") 对必须成为独立参数项，禁止合并任何两个标签断言。
- 候选 2（guardrails test 2/3/4 的 disabled+url+reason 三连）：可按 (target_pages, expected_reason_substr) 参数化，但 test 3 已是 4 页循环、test 2/4 各单页且 reason 文案不同，参数化收益小、易掩盖文案差异，**建议不动**。

**红线约束**：guardrails 的 test_1（12-case can_emit 矩阵）、test_6（6 conflict + historical）、test_9（4 forbidden_keys）属 B-2 parity oracle，**禁止 parametrize 跨 case 去重**，必须逐 case 保留为可见列表/循环（保持现状即可）。

## ⑥ load-bearing import / importlib 引用（删原文件会断吗？已 grep 核实）

grep `regression_scheduler_workbench_link`（全仓库，排除 .venv 与自身）命中 3 处外部引用 —— **全部是字符串路径登记，无 Python `import`/`importlib`**：

1. `tools/test_registry_data.py:103-104` —— 两文件各占一行（见 ⑦）。
2. `tools/test_registry_groups_scheduler.py:306-307` —— `SCHEDULER_REQUIRED_REGRESSION_GROUPS` 某组 `target_paths` 内两文件各占一行（见 ⑦）。
3. `tests/regression_aps_three_gap_docs_quality_gate.py:84` —— `REGRESSION_TESTS` 元组内**仅** `..._link_guardrails.py`（不含 contract），该门禁断言此路径字符串必须出现在文档 `docs/dev/aps_three_gap_quality_gate.md` 里（见 ⑩ 阻塞点）。

无任何模块用 `import tests.regression_scheduler_workbench_link...` 或 importlib 动态加载这两个测试模块；删原文件不会断 import。断点全在"字符串路径登记/文档门禁"层，已在 ⑦⑩ 给出精确改法。

## ⑦ registry 影响（精确"旧 → 新"）

**A. `tools/test_registry_data.py`（★必改）**
- 第 103-104 行当前：
  - `    "tests/regression_scheduler_workbench_links_contract.py",`
  - `    "tests/regression_scheduler_workbench_link_guardrails.py",`
- 改为（保留 contract 行，删 guardrails 行）：
  - `    "tests/regression_scheduler_workbench_links_contract.py",`  ← 保留
  - 删除 `    "tests/regression_scheduler_workbench_link_guardrails.py",` 整行

**B. `tools/test_registry_groups_scheduler.py`（★必改，同提交）**
- 第 306-307 行当前在某组 `target_paths` 内：
  - `            "tests/regression_scheduler_workbench_links_contract.py",`  ← 保留
  - `            "tests/regression_scheduler_workbench_link_guardrails.py",` ← 删除整行
- 注：本文件不是 `test_registry_data.py`，但属 registry 体系且与 data 同步校验（groups 的 target_paths 通常须是 registry 已登记文件的子集）。**必须与 test_registry_data.py 同提交修改**，否则 registry split-scope contract 门禁会因 guardrails 路径不一致而红。

**C. `docs/dev/aps_three_gap_quality_gate.md:107`（★文档门禁波及，非 registry 但同提交必改）**
- 第 107 行当前：`- \`tests/regression_scheduler_workbench_link_guardrails.py\``
- 须改为指向合并后文件：`- \`tests/regression_scheduler_workbench_links_contract.py\``（若该 contract 行尚未在文档列出则替换；若文档已另有 contract 行则直接删除本行避免重复）。
- 同步检查 `tests/regression_aps_three_gap_docs_quality_gate.py:84` 的 `REGRESSION_TESTS` 元组：把 `..._link_guardrails.py` 改为 `..._links_contract.py`，与文档保持一致（否则 test_developer_guide_lists_regression_tests_and_key_python_files 红）。
- `items.yaml`（`.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml`）grep 确认**不含**这两文件名，test_developer_guide_mentions_every_item_test_command_file 不受影响，无需改。

## ⑧ B-COMPAT pin：必须逐字保留、禁去重的断言

> B-2 红线：这是 R54「删手维 guard 面」所依赖的逐键四态拦放 parity oracle。以下断言**禁止任何去重/合并/parametrize 折叠**，必须逐条逐字保留在合并后文件。

**(1) forbidden_keys 红线（guardrails test_9）：**
```python
forbidden_keys = ("scenario_id", "plan_role", "is_comparison", "can_write_feedback")
for key in forbidden_keys:
    try:
        build_workbench_link(context, "execution_review", extra_params={key: "leaked"})
    except ValueError as exc:
        assert "extra_params" in str(exc)
    else:
        raise AssertionError(f"计划和现场实际入口不能允许 extra_params 追加 {key}")
```

**(2) can_emit 四态/坏值矩阵（guardrails test_1，全 12 case 逐条保留）：**
```python
assert can_emit_feedback_write_urls(context) is expected
```
对应 12 cases（含期望值，逐项不可折叠）：
```python
(dict(current_official, can_dispatch=True, can_write_feedback=True), True),
(dict(current_official, can_dispatch=True, can_write_feedback=False), False),
(dict(current_official, can_dispatch=False, can_write_feedback=True), False),
(dict(current_official, can_write_feedback=True, result_summary_parse_failed=True), False),
({"can_write_feedback": True}, False),
({"plan_role": "adopted", "can_write_feedback": True}, False),
(dict(current_official, can_write_feedback=True), False),
(dict(current_official, effective_plan_role="baseline_best", can_write_feedback=True), False),
({"requested_plan_role": "adopted", "effective_plan_role": "baseline_best",
  "is_current_executable_official_version": True, "can_write_feedback": True}, False),
(dict(current_official, requested_plan_role="baseline_best", can_write_feedback=True), False),
({"plan_role": "baseline_best", "can_write_feedback": True}, False),
({"scenario_id": "preview-1", "can_write_feedback": True}, False),
```
以及其后：
```python
assert read_only_context["can_write_feedback"] is False
assert "只能查看" in read_only_context["guardrail_text"]
assert implicit_context["can_write_feedback"] is False
```

**(3) is_comparison / is_superseded 全身份识别（guardrails test_6，6 conflict + historical 逐条保留）：**
```python
conflict_contexts = [
    dict(base, effective_plan_role="baseline_best"),
    dict(base, requested_plan_role="baseline_best"),
    dict(base, is_scenario_preview=True),
    dict(base, is_current_executable_official_version=False),
    dict(base, is_comparison=True),
    missing_current_identity,
]
for context in conflict_contexts:
    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""
    assert "只复盘正式采用方案" in link["disabled_reason"]

historical = build_workbench_link(dict(base, is_superseded_by_newer_version=True), "execution_review")
assert historical["disabled"] is True
assert historical["url"] == ""
assert "历史正式方案" in historical["disabled_reason"]
```

**(4) is_current_executable_official_version 逐态翻转 + can_emit 后置（guardrails test_7）：**
```python
context["is_current_executable_official_version"] = True
link = build_workbench_link(context, "execution_review")
assert link["disabled"] is False
assert "plan_role=adopted" in link["url"]
assert "scenario_id" not in _query_values(link["url"])
assert context["can_write_feedback"] is False
```

**(5) preview/comparison 上下文下 execution_review 禁开 + scenario_id 不入 required_params（contract test_3）：**
```python
assert review["disabled"] is True
assert review["url"] == ""
assert "只复盘正式采用方案" in review["disabled_reason"]
assert "scenario_id" not in review["required_params"]
```

> 上述 5 段是 guard 面的 parity oracle 核心，含全部 forbidden_keys / is_superseded / is_comparison / can_emit 逐字段断言。合并时整段平移，禁改禁删禁折叠。

## ⑨ 断言条数对账（前总和 → 后预期）

- 合并前：guardrails 45 + contract 83 = **128 条 assert（grep "assert" 行计，含 helper 内 assert 与 `raise AssertionError` 计在 grep 的 assert 之外）**。
  - 补充：guardrails 含 2 处 `raise AssertionError`（test_9、test_10 的 else 分支）、contract 0 处；这些是显式失败路径，等同断言，须保留。
- 去重项：两份逐字相同的 `_query_values` helper 内**无 assert**（仅 return），去重不减 assert。
- 合并后预期：**>= 128 条 assert**（物理并入，唯一去重的是无断言的 helper 定义）。若采用 ⑤ 候选 1 标签 parametrize，10 条标签断言转为 10 个独立参数项 → assert 行数表面减少但参数项数不减、覆盖不减；为满足"断言条数 >= 之和"的保真口径，**建议本簇不做标签 parametrize，直接平移 128 条**，对账最干净：128 → >=128 ✓。

## ⑩ 风险 / 阻塞点

- **【阻塞·高】three_gap 文档门禁链条（必须同提交一并改，否则 daily/full gate 红）**：
  - `tests/regression_aps_three_gap_docs_quality_gate.py:184-191` 的 `test_developer_guide_lists_regression_tests_and_key_python_files` 断言 `REGRESSION_TESTS`（含 `..._link_guardrails.py`，line 84）每一条都必须出现在 `docs/dev/aps_three_gap_quality_gate.md` 文本中。
  - 删原 guardrails 文件后，若不同步改 (a) 门禁文件 line 84 的元组项、(b) dev guide line 107 的文件名，则该门禁立即红。
  - 收口动作（同提交）：line 84 与 dev guide line 107 均把 `..._link_guardrails.py` → `..._links_contract.py`；若文档/元组已存在 contract 行则改为删除 guardrails 行避免重复。
  - 注意：本波及点**超出"只改 test_registry_data.py"的常规口径**，是本簇最易漏的红线，已在 ⑦C 给出精确行号。执行者务必把 4 个文件视为一个原子提交：合并后的测试文件 + test_registry_data.py + test_registry_groups_scheduler.py + (门禁py line84 & dev guide line107)。
- **【中】registry split-scope 一致性**：`tests/regression_quality_gate_registry_split_scope_contract.py`（已在 registry 第 110 行登记）通常校验 groups 的 target_paths 是 data 已登记集合的子集。data 与 groups 两处必须同步删 guardrails 行，否则该 contract 红。
- **【低】helper 同名冲突**：两文件均有 `_query_values`，逐字一致，合并去重为一份即可，无语义分叉风险。`from typing import Tuple` 来自 contract，须随其 helper 一并保留。
- **【红线·禁去重】** 见 ⑧：can_emit 12-case / forbidden_keys 4-key / is_comparison / is_superseded / required_params scenario_id 排除，全部逐条保留，禁 parametrize 折叠。

## 合并 commit 须记录的"原 test 函数 → 新文件位置"映射

合并后文件 = `tests/regression_scheduler_workbench_links_contract.py`，建议物理顺序：先保留 contract 原 6 函数（# 正向契约区），再追加 guardrails 原 10 函数（# 护栏与坏值拦放区 / B-2 红线）。commit message 须列出：

迁入自 `regression_scheduler_workbench_link_guardrails.py`（10 函数，删除原文件）：
- test_feedback_write_url_guardrail_is_explicit
- test_reports_index_requires_version_context
- test_workbench_view_links_require_date_range
- test_manual_disabled_link_requires_public_reason
- test_execution_review_guardrail_cannot_be_overridden_by_enabled_flag
- test_execution_review_guardrail_uses_full_plan_identity
- test_execution_review_requires_current_executable_identity_before_read_only_review
- test_workbench_links_explain_blocking_identity_and_summary_parse_failure
- test_execution_review_rejects_scenario_identity_from_extra_params
- test_workbench_link_specs_fail_loudly_when_target_is_missing

保留于 `regression_scheduler_workbench_links_contract.py`（6 函数）：
- test_workbench_context_and_link_keep_plan_date_and_resource_params
- test_all_target_pages_preserve_full_workbench_context_matrix
- test_preview_context_keeps_view_links_but_disables_execution_review
- test_primary_resource_links_disable_unsupported_team_context
- test_dashboard_analysis_and_reports_links_keep_context_without_inventing_period
- test_target_pages_and_public_label_mappings_are_fixed

去重：唯一一份 `_query_values`（两文件逐字相同的无断言 helper）。
