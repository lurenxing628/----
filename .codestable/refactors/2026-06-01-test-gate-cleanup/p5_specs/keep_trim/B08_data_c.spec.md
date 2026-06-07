# P5.2 KEEP_TRIM — Batch B08_data_c 修剪规范

适用实现 agent：本文件是唯一可执行依据。只用下面给出的 verbatim 锚点定位，不要相信任何行号（可能已漂移）。除明确列出的删除项外，一律保持原样。绝不删共享 helper（除非本规范明确点名）、绝不破坏 import/fixture、绝不让任一保留函数变成零有效断言。

本批 7 个文件无一在 B-COMPAT B-4 红线清单内（B-4 只针对 `tests/test_enum_display_consistency.py` 与 `tests/regression_schedule_result_view_context.py`），全部 `b4_redline=false`。

两个文件被 registry/group 机制按**文件路径**（非 nodeid 级）引用，见各自小节的 grep 结果——含义是「这个文件必须存在且非空」，因此只允许函数内删行 / 删部分函数、**不允许整文件删空**。本规范的所有删除都保留了大量真契约函数，文件仍非空，故 registry 约束不被破坏。

---

## 文件 1：tests/regression_scheduler_batches_degraded_visibility.py

- 当前行数：377 行。
- TSV L3 裁决理由（value=mid）：
  > build_summary_display_state/history失败不吞 真逻辑 scheduler_summary_display.py 但夹大量模板字符串/CSS class in-source 快照断言(line119-238 reuse/template surfaces)
- 理由把脆性定位在「reuse/template surfaces」这一族——即纯靠 `_read(...)` 把模板/路由源码读成字符串、再 `assert "xxx" in source` / `assert "xxx" not in source` 的 in-source / template-grep 快照。原行号 119-238 已漂移，按下方语义锚点（函数名 + 函数体首行）重新定位。

### registry/contract 耦合 grep 结果（已实跑，排除本文件自身）
- `grep -rn "<每个待删函数名>" tools/ tests/`（排除自身）→ **全部 NO HITS**（5 个函数名逐个查均无引用）。
- `grep -rln "regression_scheduler_batches_degraded_visibility" tools/` → **2 处文件级引用**：
  - `tools/test_registry_data.py:50:    "tests/regression_scheduler_batches_degraded_visibility.py",`
  - `tools/test_registry_groups_misc.py:8:            "tests/regression_scheduler_batches_degraded_visibility.py",`
- 两处均为**文件路径字符串**（required-regression 清单 / group target_paths），不含任何函数名/nodeid。含义：该 .py 必须存在且被 full gate 收集到至少一个测试。本规范删的是 5 个 in-source 快照函数，保留 5 个真契约函数（含真跑 HTTP 的两个 DB 测试），文件仍非空 → registry 约束满足，不悬空。**因此本文件 risk=mid（不可整文件删空），且禁止把保留集删到 0。**

### 整函数删除（5 个，全部为 in-source / template-grep 快照）

> 这 5 个函数没有任何行为断言：它们只把项目源码/模板文件 `_read(...)` 成字符串再 grep 子串存在/不存在。任意一次合法的模板变量改名、CSS class 改名、helper 改名、把断言里写死的源码片段重排，都会让它们红，但这不是行为回归。它们覆盖的「模板确实引用了某 viewmodel 字段」属结构 lint，真正的渲染行为契约由保留的 `test_scheduler_batches_page_renders_provenance_and_hidden_degraded_html`（真跑 `client.get("/scheduler/")` 看 status_code 与降级 HTML）和 `test_scheduler_batches_page_keeps_missing_objective_and_provenance_readonly`（真跑 DB + JSON 断言 degraded/provenance_missing）覆盖。

**删除项 1.1**：整函数 `test_scheduler_batches_route_reuses_shared_degraded_display_builder`
- 分类：`js_source_grep`（此处为路由/viewmodel py 源码 grep，同类脆性）。
- 唯一锚点（函数定义首行，verbatim）：`def test_scheduler_batches_route_reuses_shared_degraded_display_builder() -> None:`
- 函数体全是 `route_source = _read(...)` 等 4 个 `_read` + 约 26 行 `assert "xxx" in/not in *_source`。整段从该 `def` 行删到该函数最后一行 `assert "runtime_config_state" not in route_source`（含），删除其后与下一函数之间一个空行（合并 PEP8 间距）。
- 保留上下文：上方模块 docstring、imports、`REPO_ROOT`、所有模块级 helper（`_read`、`_read_analysis_template`、`_load_schema`、`_build_real_app`、`_mutate_scheduler_config`、`_BatchServiceStub`、`_HistoryServiceStub`、`_build_batches_app`）**全部保留**（被保留测试使用）；下方 `def test_scheduler_batches_latest_history_query_failure_is_not_swallowed` 完整保留。

**删除项 1.2**：整函数 `test_scheduler_batches_template_surfaces_field_level_degraded_warning`
- 分类：`full_page_text`（模板源文本 grep，本函数约 70 行 in/not-in 断言，含 `assert "最近一次排产快照" in template_source` 等中文 UI 文案快照 + CSS class 名快照 `scheduler-config-degraded-summary` 等）。
- 唯一锚点（函数定义首行，verbatim）：`def test_scheduler_batches_template_surfaces_field_level_degraded_warning() -> None:`
- 整段从该 `def` 行删到该函数最后一行 `assert "status_zh.get(latest_history.result_status" not in v2_template_source`（含）。这是全文件最大的一坨纯模板 grep（约 72 行），删除收益最高。
- 保留上下文：上方保留 `test_scheduler_batches_latest_history_query_failure_is_not_swallowed`；下方保留 `test_build_summary_display_state_exposes_filtered_display_secondary_messages`。

**删除项 1.3**：整函数 `test_scheduler_analysis_template_uses_shared_objective_label_helper`
- 分类：`full_page_text`（analysis 模板三件套 `_read_analysis_template()` 文本 grep）。
- 唯一锚点：`def test_scheduler_analysis_template_uses_shared_objective_label_helper() -> None:`
- 整段删到最后一行 `assert "display_summary_degradation_messages" not in template_source`（含）。
- 注意：`_read_analysis_template` helper **保留**（虽然删后无人调用，但它是模块级 helper、删它属额外动作；为最小化 diff 与避免误伤，保留该 helper；若实现 agent 确认无其他引用且团队偏好清理，可顺带删 helper，但**非必须**，默认保留）。

**删除项 1.4**：整函数 `test_scheduler_week_plan_and_history_templates_surface_secondary_degradation_messages`
- 分类：`full_page_text`（week_plan.html / system/history.html 文本 grep）。
- 唯一锚点：`def test_scheduler_week_plan_and_history_templates_surface_secondary_degradation_messages() -> None:`
- 整段删到最后一行 `assert "r.result_summary_display.display_secondary_degradation_messages" in history_source`（含）。

**删除项 1.5**：整函数 `test_scheduler_batches_templates_render_final_secondary_labels_without_template_side_count_suffix`
- 分类：`full_page_text`（batches.html 模板 jinja 片段 grep，只断言 `{% if item.count and item.count > 1 %}` 不在两个模板里）。
- 唯一锚点：`def test_scheduler_batches_templates_render_final_secondary_labels_without_template_side_count_suffix() -> None:`
- 整段删到最后一行 `assert "{% if item.count and item.count > 1 %}" not in v2_template_source`（含）。

### MUST KEEP（本文件保留集，删除后仍 ≥5 个真契约函数）
- `test_scheduler_batches_latest_history_query_failure_is_not_swallowed`：真行为——history 查询抛 RuntimeError 不被吞（`pytest.raises(RuntimeError, match="history query failed")`）。保留。
- `test_build_summary_display_state_exposes_filtered_display_secondary_messages`：真算法——降级事件去重/过滤次级消息、`secondary_degradation_messages` 顺序、`display_secondary_degradation_messages` 为空。保留（其中 `assert [...code...] == ["freeze_window_degraded","merge_context_degraded"]` 是 code/枚举级断言，非中文文案，属真契约）。
- `test_build_summary_display_state_dedupes_counted_primary_degradation_from_secondary`：真算法——计数主降级从次级去重。**注意**：本函数有一行 `assert display["primary_degradation"]["details"] == ["资源池资料不完整（2）"]`（即「资源池资料不完整（2）」）含中文文案，但它是 build_summary_display_state 的**算法产出**（带计数后缀的去重结果），是该函数验证「计数注入 + 去重」逻辑的唯一行为锚点，删它会让函数失去对 details 内容的校验 → **KEEP（BIAS：拿不准留）**，不要碰这行。
- `test_scheduler_batches_page_keeps_missing_objective_and_provenance_readonly`：真行为——真建内存库、跑 `/scheduler/` 两次、断言 ScheduleConfig 未被写回（只读）、`degraded is True`/`provenance_missing is True`/`baseline_label == "基线未记录"`。保留全部（`baseline_label == "基线未记录"` 是结构化字段值契约，非自由文案，保留）。
- `test_scheduler_batches_page_renders_provenance_and_hidden_degraded_html`：真行为——真 app 跑 `/scheduler/` 看 `status_code == 200` + 降级 HTML 透出。**此函数混有脆性中文整句快照**（如 `assert "当前运行配置缺少基线记录，无法确认与任何方案的一致性；请显式保存或重新应用方案。" in body`、`"个需要复核的修正项"`、`"平时不直接显示的设置需要检查"`、`"保存补齐资源"`、`"查看处理提示"`）。但本函数**没有 ErrorCode/稳定 key 可替代**——它是端到端渲染的唯一断言面，`status_code == 200` + `"当前配置状态"`/`"基线未记录"` + `"auto_assign_persist" not in body`（确认隐藏字段不泄漏）是其骨架。
  - 处理（granularity = 函数内删行，保留函数）：**保留** `assert response.status_code == 200`、`assert "当前配置状态" in body`、`assert "基线未记录" in body`、`assert "auto_assign_persist" not in body`（这 4 行是降级页存在 + 隐藏字段不泄漏的真契约）。**删除** 3 行纯整句中文文案快照：
    - 锚点行 1（删）：`    assert "当前运行配置缺少基线记录，无法确认与任何方案的一致性；请显式保存或重新应用方案。" in body`
    - 锚点行 2（删）：`    assert "个需要复核的修正项" in body`
    - 锚点行 3（删）：`    assert "平时不直接显示的设置需要检查" in body`
    - 锚点行 4（删）：`    assert "保存补齐资源" in body`
    - 锚点行 5（删）：`    assert "查看处理提示" in body`
  - 删后该函数仍保留 status_code/「当前配置状态」/「基线未记录」/隐藏字段不泄漏 4 条断言（≥1 有效断言，满足）。这是 5 处 within-function assert 删除。
  - 保守替代说明：「基线未记录」这一短词是 baseline 缺失的稳定标记（也在 viewmodel 字段断言里出现），作为该页降级的 key fragment 保留即可；删的是其后冗长的整句解释文案。

### B-4 红线处理
不适用（本文件不在 B-4 清单）。b4_redline=false。

### META-GATE 注意
本文件被 misc required-regression group 与 test_registry_data 按路径收录，是 scheduler batches 降级可见性契约的一员。删除的 5 个 in-source/template 快照函数**只下降「模板/源码确实写了某字符串」这一层结构 lint 执法**；其覆盖的「降级提示真的渲染出来」由保留的端到端 HTML/JSON 测试覆盖，且文件仍非空、仍被 gate 收集。执法损失评估：仅丢失「模板变量名/CSS class 名/jinja 片段拼写」的 grep 守卫——属可接受的脆性裁剪。

### 风险
**risk = mid**。理由：(1) 文件被 2 处 registry/group 按路径引用——只要不删空文件即安全，本规范保留 5 个真函数；(2) 删除项全为零行为的源码/模板 grep；(3) 在最后一个端到端函数内仅删 5 行整句中文文案、保留 status_code 与 key fragment；(4) 所有模块级 helper/fixture/import 保留。需 mid 是因为「文件不可删空 + 端到端函数内删行需精确」两点不容出错。

### 净行数估计
删 1.1（约 35 行含间距）+ 1.2（约 73 行）+ 1.3（约 12 行）+ 1.4（约 8 行）+ 1.5（约 7 行）+ 端到端函数内 5 行整句文案 ≈ **est_lines_removed = 138**。

---

## 文件 2：tests/regression_scheduler_excel_batches_helper_injection_contract.py

- 当前行数：147 行。
- TSV L3 裁决理由（value=mid）：
  > _batch_baseline_extra_state 真验 autobuild snapshot 委派逻辑 scheduler_excel_batches.py 但 line41-56 inspect.signature 参数名快照属脆性
- 理由把脆性精确定位在 `inspect.signature(...)` 的**参数名顺序快照**——这是按形参名钉死的签名快照，合法的形参重命名/重排会红但非行为回归。原行号 41-56 即 `test_scheduler_excel_batches_helper_signatures_are_service_injected` 函数体，按函数名重新定位。

### registry/contract 耦合 grep 结果
- `grep -rn "test_scheduler_excel_batches_helper_signatures_are_service_injected" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "regression_scheduler_excel_batches_helper_injection_contract" tools/` → **NO HITS**（无 registry/group 路径引用）。
- 结论：无任何耦合，整删该签名函数安全不悬空。

### 整函数删除（1 个）：`test_scheduler_excel_batches_helper_signatures_are_service_injected`
- 分类：`hardcoded_path_list`（此处为 `inspect.signature` 形参名列表快照，同属硬编码 member 清单快照）。
- 唯一锚点（函数定义首行）：`def test_scheduler_excel_batches_helper_signatures_are_service_injected() -> None:`
- 函数体全是 `inspect.signature(...)` 取参数名 + `assert list(...parameters) == [...形参名字面量列表...]` + `assert "conn" not in baseline_sig.parameters`。整段从该 `def` 行删到该函数最后一行 `assert "conn" not in baseline_sig.parameters`（含），删除其后一个空行（合并间距）。
- 为何整删（而非删行）：函数体每一行都是签名形参名快照，无任何行为断言可保留 → 满足整删条件。
- 注意 import：`import inspect`（模块顶部）删后无人使用——但保守起见**保留 import**（删它属额外动作，py 不会因 unused import 失败；linter 若报 F401 由后续统一处理，不在本规范范围）。默认保留 `import inspect`。

### MUST KEEP（保留集）
- `test_scheduler_excel_batches_baseline_only_tracks_uploaded_parts`：真验委派——baseline 只追踪本次上传零件、`parts_snapshot`/`template_ops_snapshot`/`autobuild_*` 结构与调用记录（`part_svc.calls`/`query_svc.calls`/`route_parse_calls`）。保留。
- `test_scheduler_excel_batches_baseline_delegates_autobuild_route_snapshot_to_part_service`：真验委派——`auto_generate_ops=True` 时调 `build_route_parse_baseline_snapshot` 产 autobuild 快照、`route_parse_calls` 带 `part_nos`/`parts_cache_keys`。保留。
- `test_scheduler_excel_batches_baseline_skips_autobuild_snapshot_when_auto_generate_disabled`：真验分支——`auto_generate_ops=False` 时跳过、`route_parse_calls == []`、`query_svc.calls == []`。保留。
- 模块级 stub 类 `_ListStub`/`_PartServiceStub`/`_TemplateQueryStub`：被上述 3 个保留测试使用 → **必须保留**。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = low**。无任何 registry 耦合；删的是纯签名形参名快照；3 个真行为委派测试与全部 stub 类保留。

### 净行数估计
删整函数约 16 行 + 1 个间距空行 ≈ **est_lines_removed = 16**。

---

## 文件 3：tests/regression_scheduler_excel_calendar_strict_numeric.py

- 当前行数：75 行（单测试函数）。
- TSV L3 裁决理由（value=mid）：
  > 真验 calendar preview 拒绝 bool/NaN/Inf parse_finite_float scheduler_excel_calendar.py 但 line101-111 badge-error/badge-new CSS class 计数属 HTML 快照
- 理由定位脆性在「badge-error/badge-new CSS class 计数」——靠正则数 HTML 里 CSS class 出现次数的快照。原行号 101-111 已漂移（文件仅 75 行），按下方语义锚点（断言文本）重新定位。
- granularity = **函数内删行**（整个文件只有一个测试函数，绝不可整删，否则文件空 + 丢真契约）。

### registry/contract 耦合 grep 结果
- `grep -rn "test_scheduler_excel_calendar_strict_numeric" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "regression_scheduler_excel_calendar_strict_numeric" tools/` → **NO HITS**。

### 脆性项（函数内删行）：badge CSS class 计数快照
- 分类：`css_pixel`（此处为 CSS class 名计数 HTML 快照，同属结构/样式快照家族）。
- **删除块 A**（`badge-error` 计数 == 3 的正则 + 注释 + assert，verbatim 多行块）：
  ```python
    # 统计错误行数：badge-error 出现次数
    error_badges = re.findall(r'badge-error', html)
    assert len(error_badges) == 3, (
        f"应有 3 个错误行（bool/NaN/Inf），实际 badge-error 出现 {len(error_badges)} 次"
    )
  ```
  为何脆性：`badge-error` 是 CSS class 名，把错误行数绑定到「某 CSS class 在 HTML 里恰好出现 3 次」，模板换 class 名 / 调整 badge 标记结构即红，非行为回归。错误**行为**已由保留的中文错误信息断言（`"必须是数字"`/`"必须是有限数字"`）覆盖——那两条是 parse_finite_float 拒绝 bool/NaN/Inf 的用户可见保证，且无更稳定的 ErrorCode 锚点（preview 渲染为 HTML 文案）→ 保留中文文案，删 CSS class 计数。
- **删除块 B**（第 4 行正常行的 badge-new/update class 快照，verbatim 多行块）：
  ```python
    # 验证正常行存在（第 4 行应为 new 或 update，不是 error）
    assert "badge-new" in html or "badge-update" in html, (
        "第 4 行（正常数据）应为新增或更新状态"
    )
  ```
  为何脆性：同样是 CSS class 名快照，靠 `badge-new`/`badge-update` class 名断言「正常行不是错误」。这是结构样式快照，class 改名即红。

### MUST KEEP（函数内保留，删后仍有强断言）
- `assert preview_resp.status_code == 200, ...`：HTTP 状态契约。保留。
- `assert "必须是数字" in html, "布尔值应触发 ..."`：bool 被拒的用户可见行为保证（无 ErrorCode 可替代）。保留。
- `assert "必须是有限数字" in html, "NaN/Inf 应触发 ..."`：NaN/Inf 被拒的行为保证。保留。
- `_make_xlsx_bytes` helper、ConfigService 设置、POST 构造：全部保留（构造测试输入的必要前置）。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = low**。删后函数仍有 status_code + 两条「拒绝非法数值」的行为断言（≥1 有效，且正是该测试核心契约）；删的两块纯 CSS class 计数/存在快照。注意 `import re` 删块 A/B 后无人用——保守**保留 import re**（删它属额外动作）。

### 净行数估计
删块 A（5 行）+ 删块 B（4 行）≈ **est_lines_removed = 9**。

---

## 文件 4：tests/regression_unit_excel_converter_diagnostics_visible.py

- 当前行数：147 行（单测试函数 + 1 个 helper `_build_source_xlsx`）。
- TSV L3 裁决理由（value=mid）：
  > UnitExcelConverter.convert 诊断 counters/samples 真逻辑 unit_excel_converter.py 但 line149-154 断言脚本 stdout 中文整句文案属脆性文本快照
- 理由定位脆性在「脚本 stdout 中文整句文案」快照。原行号 149-154（文件仅 147 行）已漂移，按断言文本重新定位。
- granularity = **函数内删行**（唯一测试函数，不可整删）。

### registry/contract 耦合 grep 结果
- `grep -rn "test_unit_excel_converter_diagnostics_visible" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "regression_unit_excel_converter_diagnostics_visible" tools/` → **NO HITS**。

### 脆性项（函数内删行）：脚本 stdout 中文整句文案快照
- 分类：`exact_chinese_snapshot`（脚本输出整句中文文案 `assert "..." in output`）。
- **保留** rc 与结果状态骨架：`assert rc == 0, output`（脚本退出码契约）保留。
- 删除以下纯中文整句 stdout 快照行（逐行 verbatim 锚点，保留 `rc == 0`）：
  - 删：`    assert "转换完成（带退化成功）。" in output, output`
  - 删：`    assert "诊断汇总：" in output, output`
  - 删：`    assert "默认补齐次数：" in output, output`
  - 删：`    assert "推断字段次数：" in output, output`
  - 删：`    assert "兼容行数：" in output, output`
  - 删：`    assert "人员设备关联会输出 工号/设备编号/技能等级/主操设备 四列；默认补齐会进入诊断汇总。" in output, output`
  为何脆性：这 6 行把脚本面向用户的中文打印逐句钉死，任意文案润色（加标点、改措辞）即红，非行为回归。脚本「带退化成功仍返回 0」的行为由保留的 `rc == 0` 覆盖；诊断**数据**是否产出由本函数上半段的 counters/samples 断言覆盖（见保留集）——这些中文 stdout 句子是同一信息的纯展示快照，无独立行为价值。

### MUST KEEP（函数内保留，强度充足）
- 全部 `counters.get(...)` 断言（`default_filled`/`inferred_field`/`compatible_row`/`invalid_step_seq`/`invalid_number`/`non_finite_number` 各 `>= 1`）：真验 convert 把退化逐项计数。保留。
- 全部 `samples.get(...)` 断言（同 6 类）：真验留有样本。保留。
- `assert rc == 0, output`：脚本退出码行为契约。保留。
- `_build_source_xlsx` helper、convert 调用、脚本 argv 构造与 `redirect_stdout`：保留（必要前置；redirect_stdout 仍需以拿到 rc）。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = low**。删后函数仍有 12 条 counters/samples 行为断言 + rc==0；删的 6 行纯中文展示文案。无 registry 耦合。

### 净行数估计
删 6 行整句 stdout 快照 ≈ **est_lines_removed = 6**。

---

## 文件 5：tests/regression_unit_excel_converter_merge_steps_and_classify.py

- 当前行数：243 行（1 个主测试 + helper `_build_source_xlsx`/`_read_headers`/`_assert_op_type_output_layout`）。
- TSV L3 裁决理由（value=high）：
  > UnitExcelConverter 工步并工序/内外协判定/人员解析/工种改名/工时累计真逻辑 unit_excel_converter.py 但 _assert_op_type_output_layout:126-144 断言xlsx freeze_panes/font/列宽属布局快照
- 理由精确点名 helper `_assert_op_type_output_layout` 的 xlsx 布局快照（freeze_panes/font/number_format/列宽）为脆性。原行号 126-144 已漂移，按 helper 名重新定位。
- value=high 但裁决方向明确：删的只是这一个布局快照 helper，主测试的全部业务逻辑断言保留。granularity = 删一个 helper 函数 + 其唯一调用点。

### registry/contract 耦合 grep 结果
- `grep -rn "_assert_op_type_output_layout" tools/ tests/`（排除自身）→ **NO HITS**（仅本文件内定义 1 处 + 调用 1 处）。
- `grep -rn "test_unit_excel_converter_merge_steps_and_classify" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "regression_unit_excel_converter_merge_steps_and_classify" tools/` → **NO HITS**。

### 脆性项 5.1（删 helper 定义）：`_assert_op_type_output_layout`
- 分类：`openpyxl_layout`（xlsx 单元格坐标/字体/冻结/列宽布局快照）。
- 唯一锚点（helper 定义首行）：`def _assert_op_type_output_layout(path: str) -> None:`
- 整段从该 `def` 行删到该 helper 最后一行（`finally:` 块内 `pass` 之后的闭合）——即删除整个 `_assert_op_type_output_layout` 函数（从 `def` 到其 `try/finally` 闭合的最后一行 `pass`）。该 helper 唯一内容是 `assert ws.freeze_panes == "A2"` / `ws["A1"].font.bold` / `ws["A2"].number_format == "@"` / `ws.column_dimensions["A"].width == 14` 等纯布局坐标快照——换 openpyxl 默认、调列宽像素、改冻结行均红，非行为回归。
- 保留上下文：上方 helper `_read_headers` 完整保留（被主测试用于断言表头列契约）；下方 `def test_unit_excel_converter_merge_steps_and_classify(...)` 保留。

### 脆性项 5.2（删调用点）：主测试末尾的 `_assert_op_type_output_layout(...)` 调用
- 唯一锚点（verbatim 单行，主测试函数最后一行）：`    _assert_op_type_output_layout(output_paths["工种配置.xlsx"])`
- 删除该行。删 helper 后必须同删此调用，否则 NameError。
- 保留其上一行 `assert _read_headers(output_paths["供应商配置.xlsx"]) == [...]`（表头列契约，真结构不变量，保留）。删后主测试以表头列契约断言收尾，仍有大量有效断言。

### MUST KEEP（主测试 6 大块业务逻辑全部保留）
- (1) XX-X 工步并工序 + 内外协判定：`routes["P001"] == "5数车10热处理15数铣20总检"`、`routes["P002"] == "5数车（外协）10数铣"`（真算法产出，含「（外协）」改名逻辑——这是规则编码的字符串，非 UI 文案快照）。保留。
- (2) 人员列解析 `"3140124 胡凡 罗辉"`、工号 6 位数字正则、设备名不带「设备」前缀。保留。
- (3) 人员设备关联 4 列 keys + 默认 `normal`/`no`、links 集合。保留。
- (3.1) 供应商 6 列 keys + 默认「启用」/备注 None。保留。
- (4) 工种冲突改名 `数车`=自制 / `数车（外协）`=外协（规则编码）。保留。
- (5) 工步时间累计成工时（数值 1e-6 容差）。保留。
- (6) 导入链路兼容：真 DB 插入 + `preview_import_links` 无 ERROR 行。保留。
- (7) 文件输出完整性：`expected_files.issubset(...)` + `os.path.exists` + `_read_headers(...人员设备关联...) == [...]` + `_read_headers(...供应商配置...) == [...]`（表头列契约，结构不变量）。保留这些；只删第 (7) 段最后那行布局快照调用。
- helper `_build_source_xlsx`、`_read_headers`：保留。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = low**。虽 TSV value=high，但 high 反映「文件整体价值高、删错代价大」，本规范只删 1 个明确点名的 openpyxl 布局快照 helper + 其唯一调用，业务逻辑 6 大块 + 表头列契约全保留，无 registry 耦合，主测试删后仍有数十条强断言。

### 净行数估计
删 helper 定义约 19 行 + 调用 1 行 ≈ **est_lines_removed = 20**。

---

## 文件 6：tests/test_excel_utils_compare_digest_guard.py

- 当前行数：197 行。
- TSV L3 裁决理由（value=mid）：
  > preview_baseline_matches token比对/compare_digest异常降级/拒明文json 真wrapper逻辑 excel_utils.py 但 line127-193 AST遍历 web/routes 强制confirm路由调用顺序属结构lint守卫
- 理由把脆性候选指向 line127-193 的两个 AST 遍历测试（`test_route_preview_baseline_calls_include_rows_fingerprint` + `test_confirm_routes_validate_preview_baseline_after_loading_payload`）。**但本规范判定：这两个 AST 测试不是脆性快照，而是真安全/顺序契约，KEEP（详见下）。** value=mid 且属 META-GATE 范畴 → 保守。

### registry/contract 耦合 grep 结果
- `grep -rn "test_route_preview_baseline_calls_include_rows_fingerprint" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rn "test_confirm_routes_validate_preview_baseline_after_loading_payload" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "test_excel_utils_compare_digest_guard" tools/` → **2 处文件级引用**：
  - `tools/test_registry_data.py:216:    "tests/test_excel_utils_compare_digest_guard.py",`
  - `tools/test_registry_groups_misc.py:134:            "tests/test_excel_utils_compare_digest_guard.py",`
- 两处均为**文件路径**（required-regression / group target_paths），非 nodeid。文件不可删空。

### 判定：本文件【不做任何删除】（净 0 行）
逐项核对，没有一项落在「脆性可删」定义内：
- `test_preview_baseline_matches_returns_true_for_equal_token` / `..._false_for_different_token`：token 相等/不等的比对行为。**真行为契约**，保留。
- `test_preview_baseline_matches_returns_false_when_compare_digest_raises`：`hmac.compare_digest` 抛错时**吞异常返 False 并记日志**——安全降级行为。其 `assert logged == ["检查结果状态比较失败"]` 看似中文文案，但它断言的是「异常路径确实走了日志分支」，是该安全行为的唯一可观测锚点（且无 ErrorCode），属行为断言而非 UI 快照 → 保留。
- `test_preview_baseline_requires_rows`：缺 rows 抛 `TypeError(match="rows")`——指纹必须含 rows 的契约（防止绕过）。保留。
- `test_parse_preview_rows_json_rejects_plain_json_payload`：拒明文 JSON 抛 `ValidationError`（`match` 用 `|` 容忍两种文案）——安全行为。保留。
- `test_load_confirm_payload_missing_baseline_uses_plain_language`：缺基线报「检查结果已失效」且不含「检查基线」黑话——这是「大白话报错」的**行为契约**（差分断言 in / not in 两个词），非纯快照；无 ErrorCode 替代，删则失去该保证 → 保留（BIAS：拿不准留）。
- `test_route_preview_baseline_calls_include_rows_fingerprint`（AST）：扫 web/routes 全部，断言 `build_preview_baseline_token`/`preview_baseline_is_stale` 调用**必须传 rows 关键字且非 None**。这是**防安全回退的结构契约**——漏传 rows 会让基线指纹失效、可被绕过。失败模式不是「样式漂移」而是「真安全漏洞被引入」→ **不是脆性，KEEP**。
- `test_confirm_routes_validate_preview_baseline_after_loading_payload`（AST）：断言所有 excel `/confirm` 路由**先 load_confirm_payload、再 preview_baseline_is_stale 校验、且写库调用不早于基线校验**（调用顺序硬约束）。这是**事务/安全顺序契约**——顺序错（先写库后校验）= 真 bug/越权写入。失败模式是行为/安全回归 → **不是脆性，KEEP**。
- 模块级 helper `_baseline_kwargs`/`_call_name`/`_route_decorator_path`/`_is_confirm_write_call`：被 AST 测试使用，保留。

### META-GATE 注意（关键）
本文件中的两个 AST 测试是**确认路由安全护栏的执法 gate**（强制 rows 指纹 + 强制「先校验后写库」顺序）。L3 理由把它们标为「结构 lint 守卫」，但其失败模式是**安全/事务回归**而非样式漂移——删它们会**直接下降对越权写入/基线绕过的执法**。按 META-GATE CAUTION：对 gate 极度保守，**完整保留**。这正是 BIAS「拿不准留」+「gate 减执法不可删」的叠加场景。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = mid**。本文件是 confirm 路由安全/顺序的执法 gate 且被 registry 按路径收录；本规范判定**不删任何内容**（est_lines_removed=0），是最保守处理，避免下降安全执法。标 mid 以提示实现 agent：此文件**不要动**，若误删 AST 测试将丢失真安全护栏。

### 净行数估计
**est_lines_removed = 0**（无删除）。

---

## 文件 7：tests/test_team_pages_excel_smoke.py

- 当前行数：142 行（单测试函数 + helper `_assert_status`/`_xlsx_headers`）。
- TSV L3 裁决理由（value=mid）：
  > 班组列贯通:模板/导出xlsx列头契约+非法team_id重定向302 真行为 team_pages 但夹大量HTML body中文标签('班组管理'/'车工一组'/'班组筛选')页面快照断言
- 理由定位脆性在 HTML body 中文标签页面快照（`"班组管理"`/`"车工一组"`/`"班组筛选"` 等 `in html` 断言）。真行为是 xlsx 列头契约 + 302 重定向。granularity = **函数内删行**（唯一测试，不可整删）。

### registry/contract 耦合 grep 结果
- `grep -rn "test_team_pages_and_excel_routes_show_team_columns_and_headers" tools/ tests/`（排除自身）→ **NO HITS**。
- `grep -rln "test_team_pages_excel_smoke" tools/` → **NO HITS**。

### 脆性项（函数内删行）：HTML body 中文标签页面快照
- 分类：`full_page_text`（渲染页 HTML body 中文标签子串快照）。
- 待删行（逐行 verbatim 锚点）——删除以下「页面里出现某中文标签/某资源名」的纯渲染文本快照：
  - 删：`    assert "班组管理" in html_team_page`（页面标题文案快照）
  - 删：`    assert "车工一组" in html_team_page`
  - 删：`    assert "车工一组" in html_personnel`
  - 删：`    assert "班组筛选" in html_personnel`（筛选控件文案快照）
  - 删：`    assert "车工一组" in html_equipment`
  - 删：`    assert "班组筛选" in html_equipment`
  - 删：`    assert "班组" in html_operator_excel`（预览页含「班组」字样快照）
  - 删：`    assert "车工一组" in html_operator_excel`
  - 删：`    assert "班组" in html_machine_excel`
  - 删：`    assert "车工一组" in html_machine_excel`
  为何脆性：这些断言把页面渲染出某中文标签/某 team 名当契约，模板文案润色、标签改写、布局调整即红，但班组数据贯通的**真行为**已被保留的 xlsx 列头契约（含「班组」列）+ 路由 status_code + 非法 team_id 302 重定向覆盖。它们是页面文本快照，无 ErrorCode/稳定 key，且贯通行为有更强的结构锚点（列头列表 == 字面量、Location header）。
- **保留** 每个 `client.get(...)` 调用与其紧随的 `_assert_status(...)`（HTTP 状态契约）——删的只是 status 断言之后的 `in html` 文本快照行；保留 `html_xxx = resp.data.decode(...)` 赋值行可不删（删快照行后该局部变量虽未用，但保留赋值不影响运行；为最小 diff，**只删 assert 行，保留 decode 赋值行**）。

### MUST KEEP（真行为契约全保留）
- 两处模板文件 xlsx 表头断言：`_xlsx_headers((test_templates / "人员基本信息.xlsx").read_bytes()) == ["工号","姓名","状态","班组","备注"]`、设备信息 `== ["设备编号","设备名称","工种","班组","状态"]`。**班组列贯通的核心结构契约**，保留。
- 全部 `_assert_status(resp, ...)`（200 状态契约）：保留。
- 非法 team_id 重定向：`assert resp_personnel_invalid.status_code == 302` + `assert resp_personnel_invalid.headers["Location"].endswith("/personnel/")`；equipment 同理。**真行为**（无效筛选回列表页），保留。
- `assert "OP001" in html_personnel` / `assert "MC001" in html_equipment`：这是「team_id=TEAM-01 筛选**确实过滤出**该资源 ID」的行为断言（资源被筛进来），是 ID 级而非文案级，且验证筛选逻辑生效 → **保留**（不是中文标签快照；BIAS 留）。
- 模板/下载/导出/excel-demo 的 `_xlsx_headers(...) == [...]` 共 5 处列头契约：保留（班组列贯通的硬契约）。
- helper `_assert_status`/`_xlsx_headers`、DB 准备、app 构造：保留。

### B-4 红线处理
不适用。b4_redline=false。

### 风险
**risk = mid**。删后函数仍保留：2 处模板 xlsx 表头契约 + 5 处路由 xlsx 表头契约 + 全部 status_code + 2 处 302 重定向 + OP001/MC001 过滤行为 → 远超 ≥1 有效断言。标 mid 因为删行较多（10 行），需精确只删 `in html_*` 文案快照、不误删 status/header/redirect/ID 断言。

### 净行数估计
删 10 行中文标签页面快照 ≈ **est_lines_removed = 10**。

---

## 批次汇总

| 文件 | 行数 | 主脆性类型 | 整删函数 | 函数内删行 | est 删行 | registry 路径引用 | risk |
|---|---|---|---|---|---|---|---|
| regression_scheduler_batches_degraded_visibility.py | 377 | full_page_text/js_source_grep | 5 | 5 | 138 | 有(2,路径级) | mid |
| regression_scheduler_excel_batches_helper_injection_contract.py | 147 | hardcoded_path_list | 1 | 0 | 16 | 无 | low |
| regression_scheduler_excel_calendar_strict_numeric.py | 75 | css_pixel | 0 | 9 | 9 | 无 | low |
| regression_unit_excel_converter_diagnostics_visible.py | 147 | exact_chinese_snapshot | 0 | 6 | 6 | 无 | low |
| regression_unit_excel_converter_merge_steps_and_classify.py | 243 | openpyxl_layout | 0(helper)+调用 | 1 helper+1 call | 20 | 无 | low |
| test_excel_utils_compare_digest_guard.py | 197 | (判定非脆性,不删) | 0 | 0 | 0 | 有(2,路径级) | mid |
| test_team_pages_excel_smoke.py | 142 | full_page_text | 0 | 10 | 10 | 无 | mid |

合计 est_lines_removed ≈ **199**。两个有 registry 路径引用的文件（batches_degraded / compare_digest_guard）均保证文件非空（前者保留 5 真函数、后者不删）。compare_digest_guard 经判定其「AST 守卫」是真安全/顺序契约，按 META-GATE 保守原则零删除。
