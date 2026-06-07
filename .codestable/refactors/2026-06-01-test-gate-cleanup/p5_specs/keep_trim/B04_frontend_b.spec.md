# P5.2 KEEP_TRIM 规范 — 批次 B04_frontend_b

源 TSV: `.codestable/refactors/2026-06-01-test-gate-cleanup/p5_specs/keep_trim_files.tsv`
本规范是实现 agent 的唯一执行依据。所有删除以 **唯一锚点字符串** 定位，禁止凭行号机械删（行号会漂）。
偏置原则：拿不准 = KEEP。脆性只删纯 cosmetic/源码 grep 尾巴，行为契约一律保留。

## 全批次 registry 耦合结论（重要，先读）

`grep -rn` 对每个"整函数删除"候选的函数名扫 `tools/ tests/`：**全部 0 命中函数级引用**。

`tools/test_registry_data.py` / `tools/test_registry_groups_*.py` 对本批多个文件有引用，但**全是按文件路径的成员清单**（不是函数名、不是函数计数、不是 nodeid 列表）。KEEP_TRIM 只删文件内部的函数/断言，文件本身继续存在且每个文件都保留 ≥1 个测试函数 → 这些路径成员引用不会悬空。

`tests/test_full_test_debt_registry_contract.py` 的 `ALLOWED_TEST_DEBT_NODEIDS` 只锁 xfail nodeid 清单；本批 15 个文件无一出现在其中，且本批无 xfail 函数 → 无 nodeid 耦合。

因此本批所有删除对 registry / debt-ledger **均安全**。下面各文件 registry_refs_found 记录的是"文件路径成员引用"（信息性，非阻塞），不是函数级引用。

---

## 1. tests/regression_gantt_url_persistence.py  (304 行)

L3 reason: node 实跑 applyUiFromUrl/persistUiToUrl 真逻辑有价值；main 的 HTML in html 与 needle in src 源码 grep 快照(L266-297)是脆性尾巴。

KEEP（真契约）：
- `_assert_js_url_contract`（L40-229）整块：node 真实启动 gantt_ui.js，验 URL 参数→state→控件/链接回写、跨视角同步、旧 gantt_vm 兼容、非法值回退 day。全部保留。
- `test_gantt_url_persistence_contract` 里：DB 播种、`resp.status_code == 200`、`_assert_js_url_contract(repo_root)` 末行调用，保留。

TRIM（脆性，在保留的 `test_gantt_url_persistence_contract` 函数内删行）：

- 脆性块 A = HTML 控件标记快照。锚点起（保留其上的注释与 status 检查）：
  - 起：`    html = resp.data.decode("utf-8", errors="ignore")`（此行**保留**）之后的 7 行 `_assert_true('id="ganttZoomLevel"' in html, ...)` 至 `_assert_true('id="ganttFilterBatch"' in html, "缺少 ganttFilterBatch 控件")`。
  - 处理：**保守保留**。这些是"控件必须存在"的结构存在性检查，属可接受的弱结构契约，且删除收益低。标记为可选；默认 **不删**。

- 脆性块 B = 读 gantt_ui.js 源码 + needle grep + 语义默认值 grep（**删**）。唯一锚点（删除从这行开始的整段，直到 `_assert_js_url_contract(repo_root)` 之前）：
  ```
      ui_js_path = os.path.join(repo_root, "static", "js", "gantt_ui.js")
      with open(ui_js_path, "r", encoding="utf-8") as f:
          src = f.read()
  ```
  连同其后的 `for needle in (... ):` 整块、`# 轻量级语义检查` 注释、及 4 行 `_assert_true('level === "day"' in src, ...)` / `url.searchParams.delete("gantt_vm")` / `ui.colorMode === "batch"` / `ui.depsMode === "critical"`。
  删到（不含）：`    _assert_js_url_contract(repo_root)`（保留此行）。
  why-brittle：纯 JS 源码文本 grep（`needle in src` / `'level === "day"' in src`），只在源码改写时炸，行为已由 node 真跑覆盖。

注意：删块 B 后 `src`/`ui_js_path`/`needle` 局部变量随之消失；`os`/`open` 仍被其它代码用，import 不动。
预计净删 ≈ 22 行（仅块 B）。risk=low。

---

## 2. tests/regression_reports_default_range_from_version_span.py  (79 行)

L3 reason: 真DB播种version9排程跨度再验默认日期范围自动取自该版本(行为真)，但经 HTML form value 与中文 hint 逐字匹配脆。

判定：**不删（KEEP 全文）**。
- `value="2099-01-10"` 的 form-value 检查是**算法输出**（默认日期由版本跨度计算得出），属行为契约，非 cosmetic。
- 中文 hint "已按所选版本的排程范围自动带入日期。" 无 ErrorCode/稳定 key 可替代，本身即"提示必须出现"的契约（spec：当精确串即契约且无其它锚点时 KEEP）。
- `MC_R1` 行存在性是数据驱动结果。
- mid risk + 全文唯一函数，删任一断言都接近清空覆盖。按偏置 KEEP。

est_lines_removed=0。risk=low（不动）。

---

## 3. tests/regression_reports_page_version_default_latest.py  (149 行)

L3 reason: 真验版本解析 latest->7 / invalid->400 / 999->404 / 无 history 不露 v0 + 日期校验逻辑真，但夹 value=7 selected / aps-disabled-button 等 HTML 快照。

KEEP（真契约，全部保留）：
- 所有 `status_code == 400/404/200`（核心 load-bearing）。
- `VERSION_ERROR_MESSAGE in invalid_html`（导入的稳定常量）、`"version 不合法" not in`。
- 404 文案 `"排产版本不存在，请先选择已有版本。"`（无 ErrorCode 锚点，是契约）。
- 日期校验文案 `"缺少开始日期或结束日期"` / `"日期格式不正确"`（行为分支输出）。
- 无 history：`"暂无排产历史"` / `"v0" not in`（防 v0 泄露契约）。
- `_assert_selected_latest(html, 7)`（默认选中最新版本 = 行为输出；`value="7" selected` 是该行为的载体）→ **保留**。

TRIM（在 `test_reports_page_version_default_latest` 函数内删脆性 label 快照行）：
- 删锚点行：`    assert "v7 · 部分成功" in overdue_html`（出现 3 处：overdue/utilization/downtime，全删）
- 删锚点行：`    assert "模拟排产）" not in overdue_html`
- 删锚点行：`    assert "aps-disabled-button" in overdue_html`（出现 3 处，全删）
why-brittle：`v7 · 部分成功` 是版本 label 拼写快照；`aps-disabled-button` 是 CSS class 存在性；`模拟排产）` 是文案否定串。三者均 cosmetic，导出禁用真行为已由别处（reports_workbench 系列的 aria-disabled / 404 导出）覆盖。

保守提示：若实现 agent 担心"导出按钮禁用"无其它覆盖，可保留 1 处 `aps-disabled-button`。默认按上删。
注意：保留 `_assert_selected_latest`，`assert ... selected` 不动。
est_lines_removed ≈ 7。risk=mid（label 快照与禁用态相关，删后靠 status/selected 兜底）。

---

## 4. tests/regression_reports_workbench_backlink_contract.py  (482 行)

L3 reason: 多场景验报表回链 URL 上下文透传 + 导出 XLSX scope 过滤 + compute_downtime_impact 真重叠算法有价值，但夹 report_plan_filter.js 与模板源码 grep(L240-248)脆性尾。

KEEP（真契约）：除下述一处外**全部保留**——URL query 透传、`_assert_query_values`、导出 XLSX scope 过滤行、`compute_downtime_impact` 算法断言（`downtime_hours==0.07` 等）、status 码、空态、隐藏内部表头。

TRIM（在 `test_report_filters_keep_scenario_on_submit_and_clear_when_plan_changes` 内删源码 grep 段，保留运行时段）：
- 删从函数体首行开始的源码 grep 段。唯一锚点（删除起点，含该行）：
  ```
      script = (REPO_ROOT / "static" / "js" / "report_plan_filter.js").read_text(encoding="utf-8")
  ```
  连删：`assert all(token in script for token in (...))`、`for rel_path in ("overdue.html", "utilization.html", "downtime.html"):` 整个循环（含 `source = (REPO_ROOT / "templates" / "reports" / rel_path)...`、两个 assert）、以及：
  ```
      overdue_source = (REPO_ROOT / "templates" / "reports" / "overdue.html").read_text(encoding="utf-8")
      assert "r.quantity or '-'" not in overdue_source
      assert "r.quantity if r.quantity is not none else '-'" in overdue_source
  ```
  删到（不含）此行——**保留**：`    client = _client()`
- 保留运行时契约段（`for path in (...): parser = _parser_for(client, path); assert _input_values(parser)["scenario_id"] == ["SCENARIO-RPT"]`）——这是真行为（提交后 scenario_id 仍在表单）。
why-brittle：`token in script`（JS 源码 grep）、`token in source`（jinja 模板 grep）、`"r.quantity if ... is not none ..." in overdue_source`（模板写法逐字快照）。仅在源码改写炸，无行为意义。

级联清理：删后 `REPO_ROOT` 在本文件仅剩此处使用 → **从顶部 import 块删 `REPO_ROOT,`**（`from tests.reports_workbench_backlink_helpers import (REPO_ROOT, ...)` 中该行）。`Tuple`/其它 helper 不受影响。
est_lines_removed ≈ 10。risk=mid（删后该函数仅剩运行时断言，仍有意义；勿误删运行时段）。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:243: `"tests/regression_reports_workbench_backlink_contract.py",`（reports_workbench_backlink_helpers 的消费者清单）

---

## 5. tests/regression_reports_workbench_navigation_contract.py  (495 行)

L3 reason: 实跑 build_scheduler/report_navigation_links 防交叉接线 + plan_role 守卫 + 后端 scope 过滤 + 冲突 400 真导航逻辑，但夹 ui_macros.html 源码 grep(L142-148)脆性尾。

KEEP（真契约）：除下述一处外**全部保留**——所有 `build_scheduler_navigation_links`/`build_report_navigation_links`/`publish_*_navigation_context` 实跑、disabled/url/guard 字段、scope 过滤、conflict 400、不交叉接线 gantt_resource。

脆性候选 = `test_scheduler_nav_template_uses_python_link_builder`（读 ui_macros.html 源码，断言 `build_scheduler_navigation_links(active)` 在、`request.args.get`/`url_for(` 不在）。

判定：**保守保留（不删）**，risk=mid。理由：
1. 这是模板"只用 Python 链接构造器、不在模板里读 request.args/url_for"的**唯一解耦守卫**；否定断言（`request.args.get not in macro` / `url_for( not in macro`）能抓真实回归（模板重新内联耦合）。虽以源码 grep 实现，但属架构不变量，非 cosmetic。spec：结构不变量 MUST KEEP；拿不准 KEEP。
2. 删整函数会使 `REPO_ROOT`（仅此处用）变成死 import，连带清理。
若 P5 必须减脆性：可仅删正向存在性断言 `assert "build_scheduler_navigation_links(active)" in macro`，**保留两条否定耦合守卫**。默认建议整函数保留。

est_lines_removed=0（默认不动）。risk=mid。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:91: `"tests/regression_reports_workbench_navigation_contract.py",`
- tools/test_registry_data.py:244: `"tests/regression_reports_workbench_navigation_contract.py",`（backlink_helpers 消费者清单）
- tools/test_registry_groups_scheduler.py:281: `"tests/regression_reports_workbench_navigation_contract.py",`

---

## 6. tests/regression_resource_dispatch_actual_task_key_frontend_contract.py  (65 行)

L3 reason: 验 task_key 路由从 task_key 派生身份、接受剥离 legacy 字段的前端 payload + 事件序列 + 数量字符串强转真路由逻辑，但夹 not in payload 自验脆性(L58-60)。

KEEP（真契约）：
- `_frontend_payload` helper（剥离 legacy 字段构造）保留。
- `resp = client.post(...)`、`events = _events_for_card(...)`。
- `assert resp.status_code == 200, _json(resp)`（真路由接受）。
- `assert [row["event_type"] for row in events] == ["start", "finish"]`（事件序列）。
- `assert events[1]["quantity_done"] == 10` / `== 0`（字符串"10"/"0"强转为 int）。

TRIM（在 `test_task_key_actual_route_accepts_frontend_payload_without_legacy_identity_fields` 内删自验断言）：
删这 3 行连续锚点：
```
    assert "expected_state_revision" not in payload
    assert "schedule_id" not in payload
    assert "operator_id" not in payload
```
why-brittle：这是对测试自身 `_frontend_payload` 已 `payload.pop(...)` 的同义反复自验——不测被测系统行为，只测试本身刚做的事。删后函数仍保留 status/事件序列/数量强转等真断言。
est_lines_removed=3。risk=low。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:194: `"tests/regression_resource_dispatch_actual_task_key_frontend_contract.py",`
- tools/test_registry_groups_scheduler.py:296: `"tests/regression_resource_dispatch_actual_task_key_frontend_contract.py",`

---

## 7. tests/regression_resource_dispatch_public_output_contract.py  (338 行)

L3 reason: 实跑 decorate+build_workbook+filename+sanitizer 验公开标签映射 / 不泄露 internal 枚举与 op_id / 非法字符清洗 / 日历明细构造真公开边界转换，但末尾 resource_dispatch.html 源码 grep(L332-336)脆。

KEEP（真契约，全部保留 L83-331）：标签映射（自制/外协/已锁定…）、`forbidden not in all_values` 内部枚举/op_id 防泄露、文件名 sanitizer、坏时间 label、日历明细 header/row 快照（编码"公开列正确 + 内部字段不泄露"契约，属结构不变量，保留）。

TRIM（**整函数删除**）：`test_resource_dispatch_template_version_summary_prefers_public_schedule_time`（文件末尾）。唯一锚点（删整函数，含 def 行到文件尾）：
```
def test_resource_dispatch_template_version_summary_prefers_public_schedule_time() -> None:
    template = (REPO_ROOT / "templates" / "scheduler" / "resource_dispatch.html").read_text(encoding="utf-8")

    assert "schedule_time_display or selected_version_row.item.schedule_time" in template
    assert "ui.summary_item('时间', selected_version_row.item.schedule_time)" not in template
```
grep 结果：`grep -rn test_resource_dispatch_template_version_summary_prefers_public_schedule_time tools/ tests/` → 0 命中（除自身）。
why-brittle：纯 jinja 模板源码逐字 grep（`"... or selected_version_row.item.schedule_time" in template`），只在模板改写炸。

级联清理：删后 `REPO_ROOT`（L18 定义，仅此函数用）变死 → 删 `REPO_ROOT = Path(__file__).resolve().parents[1]`；连带 `from pathlib import Path`（仅 L18 用）也变死 → 一并删。`io`/`openpyxl`/其它 import 仍被用，不动。
est_lines_removed ≈ 8（函数 5 + REPO_ROOT 行 + Path import + 空行）。risk=low。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:171: `"tests/regression_resource_dispatch_public_output_contract.py",`
- tools/test_registry_groups_misc.py:13: `"tests/regression_resource_dispatch_public_output_contract.py",`

---

## 8. tests/regression_resource_dispatch_site_records_frontend_contract.py  (465 行)

L3 reason: 4 个测真后端守卫 `_execution_review_link`/`_request_kwargs`/incomplete-plan 400 值得留，但主体是 JS/CSS/模板逐字串 in source 海量快照应删。

KEEP（真后端/页面行为契约）：
- `test_resource_dispatch_page_has_site_records_words_and_excel_entries`（L30-91）：**保留**。status 200 + data-actual-*-url 模板/查询参数（真写 URL 行为）+ 旧术语否定守卫。其中 `source = read_resource_dispatch_script_bundle()` + `page_contract = body + source` 段属轻度混入，但函数整体是页面行为契约，保守保留全函数。
- `test_resource_dispatch_actual_record_url_uses_normalized_filters_when_query_date_missing`（L94-111）：URL 归一行为，保留。
- `test_resource_dispatch_read_only_page_does_not_emit_actual_write_urls`（L114-144）：只读不发写 URL 防泄露 + status，保留。
- `test_resource_dispatch_unqueryable_write_page_does_not_render_none_links`（L147-169）：`href="None"`/`href=""` 反 bug + status，保留。
- `test_resource_dispatch_history_and_scenario_pages_do_not_emit_review_or_write_urls`（L172-203）：保留。
- `test_resource_dispatch_execution_entry_rejects_incomplete_plan_context`（L206-230）：400 + error payload 结构 + missing_fields，保留。
- `test_execution_review_link_keeps_server_side_guard_fields`（L232-282）：`_execution_review_link` 守卫逻辑，保留。
- `test_resource_dispatch_request_kwargs_preserve_batch_id`（L284-297）：`_request_kwargs`，保留。

TRIM（**整函数删除 3 个纯 JS/CSS/模板源码 grep**）：
1. `test_resource_dispatch_frontend_uses_actual_record_form_and_one_click_import`（L299-440）。锚点 def 行：
   `def test_resource_dispatch_frontend_uses_actual_record_form_and_one_click_import() -> None:`
   删到（不含）下一个 `def test_resource_dispatch_execution_buttons_follow_available_actions_contract`。
   why-brittle：读 script bundle / template / css / page_css，海量 `_assert_contains_all`/`_assert_contains_none` 逐字源码串。
2. `test_resource_dispatch_execution_buttons_follow_available_actions_contract`（L443-456）。锚点 def 行同名。删到（不含）下一个 def。
   why-brittle：`extract_js_function(source, "renderExecutionActions")` 后逐字 grep JS 片段。
3. `test_manual_actual_save_refreshes_dispatch_views_after_updating_task_card`（L459-466，文件尾）。锚点 def 行同名，删到文件尾。
   why-brittle：`extract_js_function(source, "postExecutionAction")` 后逐字 grep + `.index()` 顺序。

grep 结果（3 函数名 over tools/ tests/）：全部 0 命中（除自身）。

级联 import 清理（删 3 函数后变死）：
- `read_resource_dispatch_script_bundle` 仍被 L41 的保留函数用 → **保留**。
- 从 `from tests.operation_execution_feedback_test_support import (...)` 删 `RESOURCE_DISPATCH_TEMPLATE,` 与 `UI_CONTRACT_CSS,`（仅 L301/L302 用，都在删除函数内）。
- 整块 `from tests.resource_dispatch_frontend_support import (RESOURCE_DISPATCH_CSS, extract_js_function,)` 两符号均变死（仅 L303/L445/L461 用）→ **删整个 import 块**。
- `Tuple`（L5）仍被 `_assert_contains_all/none` 签名用（保留函数 L30 系列调用）→ 保留。

est_lines_removed ≈ 175（3 函数主体）。risk=mid（删除量大但纯源码 grep；务必精确按 def 边界删，勿误伤 L284-297 的 `_request_kwargs` 真测）。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:200: `"tests/regression_resource_dispatch_site_records_frontend_contract.py",`
- tools/test_registry_groups_scheduler.py:286: `"tests/regression_resource_dispatch_site_records_frontend_contract.py",`

---

## 9. tests/regression_resource_dispatch_workbench_lane_contract.py  (298 行)

L3 reason: 真测 build_task_card 与 node 实跑 resource_execution_cards.js DOM 回退及 delta 计算晚12分钟/早2分钟有价值，但夹 template/script 顺序/JS 源码 grep(L100-159,207-215)脆性。

KEEP（真契约）：
- `test_resource_dispatch_execution_scripts_are_loaded_by_responsibility`（L130-147）：**保守保留**。其 `_script_index` 顺序断言偏脆，但 `for name in ordered: assert (REPO_ROOT/static/js/name).exists()` 是"这些 JS 文件必须存在"的真文件存在性契约（删了文件会炸）。整函数保留。
- `test_task_card_uses_plain_fallback_when_part_is_missing`（L166-184）：`build_task_card` 兜底 label，保留。
- `test_execution_cards_render_dom_fallbacks_for_missing_part_and_operation`（L187-208）：node 真跑 resource_execution_cards.js 验 DOM 兜底输出，保留。
- `test_resource_dispatch_keeps_execution_inside_existing_page`（L211-219）：`"/scheduler/resource-execution" not in source` 路由反耦合守卫，保守保留（廉价结构守卫）。
- `test_execution_data_contains_part_time_delta_and_record_labels`（L222-274）：核心价值——晚12分钟/早2分钟 delta 计算、status、`source_table not in events[0]` 防泄露，保留。
- `test_nonformal_resource_dispatch_pages_do_not_emit_write_addresses`（L276-298）：反写 URL 泄露 + status，保留。

TRIM（**整函数删除 2 个纯模板/JS 源码 grep**）：
1. `test_resource_dispatch_template_separates_planner_and_site_lanes`（L104-128）。锚点 def 行：
   `def test_resource_dispatch_template_separates_planner_and_site_lanes() -> None:`
   删到（不含）`def test_resource_dispatch_execution_scripts_are_loaded_by_responsibility`。
   why-brittle：读 template+css，`_lane_group` 正则切块后断言 tab id / 中文 tab 名 / CSS class 存在与 `.index()` 顺序——纯模板结构快照。
2. `test_resource_dispatch_frontend_consumes_execution_lane_fields`（L149-163）。锚点 def 行同名。删到（不含）`def test_task_card_uses_plain_fallback_when_part_is_missing`。
   why-brittle：`source = read_resource_dispatch_script_bundle()` 后逐字 grep `task.part_label` 等 JS 字段名。

grep 结果（2 函数名）：全部 0 命中（除自身）。

级联清理（删 #1 后）：
- helper `_lane_group`（L37-43）仅被 #1 用 → **删该 helper**。
- `import re`（L8）仅被 `_lane_group` 用 → **删 `import re`**。
- `RESOURCE_DISPATCH_CSS`（L22 import）仅 L106（#1 内）用 → 从 `from tests.resource_dispatch_frontend_support import (...)` 删该符号。
删 #2 后：
- `read_resource_dispatch_script_bundle`（L23 import）仅 L150（#2 内）用 → 该 import 块两符号（RESOURCE_DISPATCH_CSS + read_...）均死 → **删整个 `from tests.resource_dispatch_frontend_support import (...)` 块**。
- `_source`（L29）仍被 L131/L219 用 → 保留。`_script_index`（L33）仍被 L143 用 → 保留。`RESOURCE_DISPATCH_TEMPLATE` 仍被 L131/L213 用 → 保留。`subprocess`/`json`/`re`(已删)/`Path`：`_run_node_json` 用 subprocess+json，保留。

est_lines_removed ≈ 40（#1 25 行 + #2 15 行 + helper/import 清理，净增删抵消）。risk=mid（级联 import 清理较多，按上逐项核对）。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:201: `"tests/regression_resource_dispatch_workbench_lane_contract.py",`
- tools/test_registry_groups_scheduler.py:287: `"tests/regression_resource_dispatch_workbench_lane_contract.py",`

---

## 10. tests/regression_scheduler_analysis_candidate_links_and_roles.py  (263 行)

L3 reason: 实跑 analysis 页 candidate 对比行 role/label/links 与明细未存/失败/跳过/状态过期时隐藏链接真 viewmodel，但夹 AST 验常量单一定义结构守卫(L48-65)。

判定：**不删（KEEP 全文）**，risk=high（若误删）。理由：
- `test_candidate_role_and_source_constants_have_one_definition`（L50-67）虽被 reason 点名，但它是 **plan_role 三角色常量"单点定义、无重复"** 的结构守卫。按项目记忆，plan_role 单一真相源是"灵魂线"(R51 相关)，此 AST 守卫是防常量复制漂移的**唯一**强制。spec 明列"结构不变量 MUST KEEP"。`_direct_string_assignments` 是真 AST 逻辑，非文本快照。
- 其首断言 `{ROLE_ADOPTED,...} == {"adopted",...}` 是值契约，保留。
- 其余函数（L70-263）全是真 viewmodel 契约（角色顺序、中文 label、5 链接生成、failed/skipped/missing/stale 隐藏链接分支），全部保留。

est_lines_removed=0。risk=low（不动）。误删该 AST 守卫的风险 = high。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:113: `"tests/regression_scheduler_analysis_candidate_links_and_roles.py",`
- tools/test_registry_groups_scheduler.py:312: `"tests/regression_scheduler_analysis_candidate_links_and_roles.py",`

---

## 11. tests/regression_scheduler_analysis_workbench_layout.py  (250 行)

L3 reason: 实跑 analysis_action_hub 链接上下文透传 / 日期缺失禁用 / 可见文案无内部术语真 viewmodel，但夹模板 include 顺序 source grep(L79-99)脆性。

KEEP（真契约）：所有 `_render_part` 真渲染 + `_payload` 实跑路由的函数（L104-251）——action_hub 链接上下文、缺日期禁用、`VISIBLE_FORBIDDEN_TERMS` 防内部术语泄露、详情区不重复推荐。全部保留。

TRIM（**整函数删除 2 个纯模板源码 .index() 顺序 grep**）：
1. `test_analysis_page_places_action_hub_before_detailed_sections`（L81-93）。锚点 def 行：
   `def test_analysis_page_places_action_hub_before_detailed_sections() -> None:`
   删到（不含）`def test_analysis_action_hub_places_diagnostics_before_next_actions`。
   why-brittle：读 analysis.html，`source.index("_action_hub.html")` 等比较 include 段先后——纯模板顺序快照。
2. `test_analysis_action_hub_places_diagnostics_before_next_actions`（L96-101）。锚点 def 行同名。删到（不含）`def test_analysis_route_exposes_action_hub_with_context_links`。
   why-brittle：读 _action_hub.html，`source.index("analysis_action_hub.recommendation_card")` 等比较 jinja 变量引用先后——纯源码顺序快照。

grep 结果（2 函数名）：全部 0 命中（除自身）。

级联清理：删 #1 后 `ANALYSIS_TEMPLATE`（L21 定义）仅 L82（#1 内）用 → **删 `ANALYSIS_TEMPLATE = PROJECT_ROOT / "templates/scheduler/analysis.html"`**。`PROJECT_ROOT` 仍被 `_render_part`(L62)/`ACTION_HUB_TEMPLATE` 等用 → 保留。`Path` 仍被 L20 用 → 保留。
est_lines_removed ≈ 16（#1 13 + #2 6 - 顺延空行；含 ANALYSIS_TEMPLATE 行）。risk=low。
registry_refs_found：无（grep tools/ 无此文件路径成员引用）。

---

## 12. tests/regression_scheduler_candidate_config_contract.py  (405 行)

L3 reason: 真测 config 字段默认/choices/严格数字校验/preset 归一向后兼容/orchestrator 按 graph_analysis_mode 开关方案对比与 runtime 字段透传真逻辑，但夹模板缺串 grep(L306-313)脆性尾。

KEEP（真契约）：除下述行外**全部保留**——`default_for`/`choices_for`、`coerce_config_field` 严格校验（pytest.raises）、`missing_required_preset_fields`/`normalize_preset_snapshot` 向后兼容、`graph_downstream_weight` 内部参数边界、orchestrator `_candidate_comparison_enabled`/`_candidate_*` 分支、`orchestrate_schedule_run` 透传 runtime 字段、off/report 单方案模式。

TRIM（在 `test_graph_analysis_mode_controls_candidate_comparison_without_user_visible_toggle` 内删模板 grep 段，保留前后真断言）：
- KEEP（函数内，删点之前）：L297-306 的 `_candidate_comparison_enabled`/`_candidate_weight_count`/`_candidate_selection_policy`/`_candidate_overdue_tolerance_count`/`_candidate_tardiness_tolerance_ratio` 断言。
- 删模板 grep 块。唯一锚点（删起点，含此 for）：
  ```
      for rel_path in (
          "templates/scheduler/config.html",
          "templates/scheduler/_run_panel.html",
          "web_new_test/templates/scheduler/config.html",
      ):
          assert "candidate_comparison_enabled" not in (REPO_ROOT / rel_path).read_text(encoding="utf-8")
      assert "run_time_budget_seconds" not in (REPO_ROOT / "templates/scheduler/config.html").read_text(encoding="utf-8")
      assert "run_time_budget_seconds" not in (REPO_ROOT / "web_new_test/templates/scheduler/config.html").read_text(encoding="utf-8")
  ```
  删到（不含）此行——**保留**：`    payload = _collect_scheduler_config_form_payload(`
- KEEP（删点之后）：L316-323 的 `_collect_scheduler_config_form_payload({...}) == {"graph_analysis_mode": "on", "graph_candidate_weight_count": "5"}`——这是真行为（内部字段 `run_time_budget_seconds` 被表单收集剥离），覆盖了"不暴露给用户"的同一契约。
why-brittle：`"candidate_comparison_enabled" not in (REPO_ROOT/rel_path).read_text()` 与 `"run_time_budget_seconds" not in ...` 是模板源码否定 grep；同契约已由 `_collect_scheduler_config_form_payload` 运行时断言覆盖。

注意：`REPO_ROOT`（L31）仍被 L32 `SCHEMA_PATH` 用、`SCHEMA_PATH` 被 L209 用 → import 不动。删后该函数仍有大量真断言。
est_lines_removed ≈ 9。risk=low。
registry_refs_found：无（grep tools/ 无 config_contract 文件路径成员引用）。

---

## 13. tests/regression_scheduler_candidate_display_contract.py  (184 行)

L3 reason: 实跑 build_candidate_comparison_display：按 source_table 判对比态/失败跳过候选 surface/内部失败原因译为用户话/隐藏旧标签真 viewmodel，但夹 _candidate_comparison.html 源码 grep(L17-35)脆性。

KEEP（真契约）：所有 `build_candidate_comparison_display(...)` 调用 + 返回 viewmodel 断言（L40-184）——对比态、失败候选 surface、内部原因翻译、隐藏旧标签 `关键链最好`/`graph_w`、不重复采用后缀。全部保留。

TRIM（**整函数删除纯模板源码 grep**）：`test_analysis_template_uses_viewmodel_candidate_rows_and_route_built_links`（L19-37，文件首个测试函数）。锚点 def 行：
`def test_analysis_template_uses_viewmodel_candidate_rows_and_route_built_links() -> None:`
删到（不含）`def test_candidate_display_marks_baseline_best_as_adopted_when_baseline_is_selected`。
why-brittle：读 _candidate_comparison.html，逐字 grep `analysisCandidateComparisonTable`/`candidate_comparison_display.rows`/否定 `plan_role=`/`关键链最好`/`row.score_label`/`>评分<`——纯模板快照。隐藏旧标签的真契约已由 L144-166 的 viewmodel 输出断言覆盖。

grep 结果：0 命中（除自身）。
级联清理：删后 `from pathlib import Path`（L6）仅 L21（函数内）用 → **删 `from pathlib import Path`**。`json`（L5）仍被 L154/L163 用 → 保留。
est_lines_removed ≈ 20。risk=low。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:116: `"tests/regression_scheduler_candidate_display_contract.py",`
- tools/test_registry_groups_scheduler.py:315: `"tests/regression_scheduler_candidate_display_contract.py",`

---

## 14. tests/regression_scheduler_candidate_gantt_plan_role_contract.py  (484 行)

L3 reason: 端到端 gantt/data plan_role 解析读候选行/critical_chain 不可用降级公开契约不泄露内部 id/无效角色回退 adopted/超期标记从候选行算不复用历史真逻辑，但夹 gantt 页 HTML 与 boot.js substring(L386-402)脆性。

KEEP（真契约）：所有端到端函数（L220-385, L407-485）——status 码、`requested/effective_plan_role`、`source_table`、critical_chain 脱敏（`INTERNAL-CANDIDATE-ID not in str(data)`）、`degradation_events` code、回退 adopted、超期标记从候选行算、400 拒未知 plan_role。全部保留。

TRIM（在 `test_gantt_page_and_boot_preserve_plan_role` 内删 boot.js 源码 grep 行，保留 HTML 行为断言）：
- KEEP（函数内）：`resp`/`html`、`status_code == 200`、`'name="plan_role"' in html`、`'data-plan-role="baseline_best"' in html`、`"plan_role=baseline_best" in html`、`/scheduler/analysis?version=...&amp;plan_role=... in html`、`"当前查看的是“原算法代表方案”" in html`、`"这是一套对比参考方案" in html`（页面真携带 plan_role 上下文 + 对比提示，行为输出）。
- 删 boot.js 读取行。唯一锚点（删此行）：
  ```
      boot_js = (REPO_ROOT / "static/js/gantt_boot.js").read_text(encoding="utf-8")
  ```
- 删这 2 行（boot.js 源码 grep）：
  ```
      assert "planRole: ds.planRole" in boot_js
      assert 'url.searchParams.set("plan_role", String(cfg.planRole))' in boot_js
  ```
why-brittle：`... in boot_js` 是 JS 源码逐字 grep，只在 boot.js 改写炸；plan_role 端到端透传已由 gantt/data 系列真断言覆盖。

注意：删后 `boot_js` 局部消失；`REPO_ROOT` 仍被 `_build_app`/`_build_empty_app`/`_seed`（L152/170/193/211 等）大量使用 → import 不动。函数保留全部 HTML 行为断言。
est_lines_removed=3。risk=low。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:112: `"tests/regression_scheduler_candidate_gantt_plan_role_contract.py",`
- tools/test_registry_groups_scheduler.py:311: `"tests/regression_scheduler_candidate_gantt_plan_role_contract.py",`

---

## 15. tests/regression_scheduler_candidate_plain_language.py  (451 行)

L3 reason: 实跑 build_candidate_comparison_display/build_diagnostic_sections/format_public_datetime：推荐卡白话/未完成不伪造/坏值译公开错误标签/不泄露内部字段真 viewmodel，但夹 _candidate_comparison.html 源码 grep(L181-256)脆性。

KEEP（真契约）：所有实跑 `build_candidate_comparison_display`/`build_diagnostic_sections`/`build_primary_degradation`/`format_public_datetime` 的函数（L92-180, L261-451）——白话推荐卡、缺失/未知 reason_code/未完成不伪造、坏值译"记录异常"、`_assert_payload_not_leaking_internal_text`（对真 viewmodel 输出查 INTERNAL_VISIBLE_TERMS 不泄露，这是真防泄露契约）。全部保留。

TRIM（**整函数删除 3 个纯模板源码 grep**）：
1. `test_candidate_link_empty_state_uses_plain_public_reason`（L183-192）。锚点 def 行：
   `def test_candidate_link_empty_state_uses_plain_public_reason() -> None:`
   删到（不含）`def test_candidate_recommendation_template_only_reads_public_card_fields`。
   why-brittle：读 _candidate_comparison.html，`source.index(...)` 切 link_block 后 grep `row.detail_saved`/`row.source_table`/`candidate_id` 不在——模板源码快照。
2. `test_candidate_recommendation_template_only_reads_public_card_fields`（L194-219）。锚点 def 行同名。删到（不含）`def test_candidate_summary_cards_template_uses_public_fields_after_recommendation`。
   why-brittle：切 recommendation block 后 grep 公开字段在 + 内部术语不在——模板源码快照。
3. `test_candidate_summary_cards_template_uses_public_fields_after_recommendation`（L222-258）。锚点 def 行同名。删到（不含）`def test_candidate_recommendation_visible_payload_hides_internal_fields`。
   why-brittle：切 summary block 后 grep + `.index()` 顺序断言——模板源码快照。

grep 结果（3 函数名）：全部 0 命中（除自身）。
**防泄露契约不丢**：L261/280/291 等运行时 `_assert_payload_not_leaking_internal_text` 已对真 viewmodel 输出强制 INTERNAL_VISIBLE_TERMS 不泄露，模板 grep 版是冗余脆性副本。

级联清理：删 3 函数后 `REPO_ROOT`（L20）仅 L184/195/223（均删除函数内）用 → **删 `REPO_ROOT = Path(__file__).resolve().parents[1]`**；`from pathlib import Path`（L6）仅 L20 用 → 一并删。`json`（L5）/`Any,Iterable,List`（L7）仍被保留函数与 helper 用 → 保留。
est_lines_removed ≈ 78（3 函数 + REPO_ROOT/Path 行）。risk=low（防泄露由运行时断言兜底）。
registry_refs_found（文件路径成员，非函数级）：
- tools/test_registry_data.py:117: `"tests/regression_scheduler_candidate_plain_language.py",`
- tools/test_registry_groups_scheduler.py:316: `"tests/regression_scheduler_candidate_plain_language.py",`

---

## B-4 红线核对

本批 15 个文件中 **无** `test_enum_display_consistency.py`、**无** `regression_schedule_result_view_context.py` — 两条 B-COMPAT B-4 红线文件均不在 B04_frontend_b。故本批 `b4_redline` 全为 false，无需特殊差分守卫处理。

## 实现 agent 注意事项汇总

1. 整函数删除一律按 **def 行锚点 → 下一个 def 行（不含）** 的边界删，勿凭行号。
2. 级联 import / 模块级常量清理（REPO_ROOT / Path / re / 各 helper import）务必逐文件按上文核对，删后 `python -c "import ast; ast.parse(open('<file>').read())"` 自检无 NameError 隐患（未用 import 不致命，但本规范已指明应删的死 import）。
3. 文件 #2(default_range)、#5(navigation 守卫)、#10(AST 单点定义守卫) 默认 **不动**，按偏置 KEEP。
4. registry：所有耦合均为文件路径成员级，文件不删 → 不悬空；无函数级/nodeid/计数耦合，删函数安全。
