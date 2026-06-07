# P5.1 单文件挂靠 spec —— 6 个孤立回归文件并入已有 KEEP 锚点

> 铁律复述：挂靠是**行为保真**的。并入后目标文件的断言条数必须 >= 锚点原断言 + 被挂靠文件断言之和。去重**仅限逐字完全重复的同义断言**（如两文件各有一份 byte-identical 的 `_base_snapshot()` / `_make_xlsx_bytes` helper）；语义 / 边界 / 坏值 / None / 异常不同的断言**一律保留**，差异收进 `parametrize` 维度。
>
> conftest 现有共享 fixture：`db_path` / `db_env` / `app_client`(只 importlib 顶层 `app` 再 `.test_client()`，**库为空 schema、不暴露 app 对象**) / `schema_conn`(:memory:+全 schema) / `mem_conn`(:memory:空表) / `schema_path` / `repo_root`。
>
> **全局结论**：6 节中 4 节锚点不在任何 registry（零 registry 影响）；仅第 4、第 6 节命中 registry（共 7 处条目须改）。无任何 B-COMPAT 红线 pin（这批挂靠都不触碰"禁去重"断言）。最大风险点在第 4 节：成员与锚点都是 e2e、各自带一份 **byte-identical 的 `_build_app`**，挂靠的价值正是把这份 80 行建库样板去重为一份共享 helper —— 但 conftest 的 `app_client` 用不上（需 `app` 对象做 `monkeypatch.setattr(app.logger,"warning",...)`），属真实 fixture 缺口，须保留文件内 `_build_app`。

载荷引用核实（全仓 grep）：6 个被挂靠文件**没有任何 Python `import`/`importlib` 引用**指向它们自身模块（它们是叶子测试文件）。仅第 4、第 6 个文件被 registry 清单按字符串路径登记（详见各节 ⑦）。删原文件不会断 import，只须同步 registry 字符串。

断言计数口径：下文"断言条数"= `assert` 行 + `raise RuntimeError(...)`(成员里当断言用的失败抛出) + `with pytest.raises(...)` 之和（用 `grep -cE "^\s*assert |raise RuntimeError|with pytest.raises"` 量得）。

---

## 节 1：config_validator_relaxed_contract -> `regression_config_validator_preset_degradation.py`

### ① 成员文件
- `tests/regression_config_validator_relaxed_contract.py`（72 行，1 个 test，**17** 断言）

### ② 目标 KEEP 锚点 + 命名理由
- 锚点真实文件：`tests/regression_config_validator_preset_degradation.py`（已存在，6 个 test，47 断言）
- 契约同源核实：✅ 两文件 import 同一组 `from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot` + `from core.services.scheduler.config_validator import normalize_preset_snapshot`，且**各自带一份逐字完全相同的 `_base_snapshot()`**（成员 L7-32 与锚点 L13-38 字段值完全一致）。锚点 docstring 已声明覆盖 "非严格模式下把越界/非法/空白预设字段降级回 base 值并记 degradation_events 与按类计数(number_below_minimum/invalid_number/invalid_choice/blank_required)，消息只暴露中文字段名不泄露内部 key"——成员测的正是这条契约的"10 字段同时坏值"组合。同源。
- 挂靠后文件名**不变**（沿用 `regression_config_validator_preset_degradation.py`，锚点本就是该契约的归集点）。

### ③ test 函数清单 + 断言条数 + 关键断言逐字摘录
成员仅 1 个 test：
- `test_relaxed_preset_numeric_fields_follow_field_coercion_contract`（17 断言，`strict_mode=False`，一次喂 10 个坏字段）
  - 数值/枚举回退（坏值→base）：
    - `assert snap.priority_weight == 0.4`（"abc"→base）
    - `assert snap.holiday_default_efficiency == 0.8`（"0" 越下界→base）
    - `assert snap.ortools_time_limit_seconds == 5`（"bad"→base）
    - `assert snap.time_budget_seconds == 1`（**"0"→钳到最小值 1**，注意不是回 base 20，是钳 min）
    - `assert snap.freeze_window_days == 0`（"-3"→base 0）
    - `assert snap.graph_analysis_mode == "off"`（"bad" 非法枚举→base）
    - `assert snap.graph_block_on_cycle == "no"`（"maybe" 非法 yes/no→base）
    - `assert snap.graph_critical_weight == 0`（**"-1"→钳到最小值 0**，非回 base 500）
    - `assert snap.graph_impact_weight == 10`（"bad"→base）
    - `assert snap.graph_debug_export == "no"`（"maybe"→base）
  - 按类计数（坏值/边界）：
    - `assert int(counters.get("invalid_choice") or 0) >= 3, counters`
    - `assert int(counters.get("invalid_number") or 0) >= 3, counters`
    - `assert int(counters.get("number_below_minimum") or 0) >= 4, counters`
  - 消息只暴露中文字段名、不泄露内部 key（这是该契约的**安全性核心断言**，必须逐字保留）：
    - `assert "优先级权重" in event_messages`
    - `assert "锁定天数" in event_messages`
    - `assert "priority_weight" not in event_messages`
    - `assert "freeze_window_days" not in event_messages`

锚点现有 6 个 test（不动，仅列名核无冲突）：`test_config_validator_preset_degradation_and_min_clamp` / `..._strict_blank_rejected_but_missing_allowed` / `..._relaxed_invalid_numeric_falls_back_with_degradation` / `..._strict_invalid_numeric_still_rejected` / `..._relaxed_invalid_choice_and_yesno_are_observable` / `..._relaxed_blank_choice_and_yesno_emit_blank_required`。**无同名冲突**。

### ④ 共享 setup -> 建议 fixture
- 成员与锚点各有一份 byte-identical 的本地 `_base_snapshot()` helper。挂靠后**删成员那份、复用锚点已有的 `_base_snapshot()`**（这是允许的"逐字完全重复"去重）。
- 无需 conftest fixture（纯函数级单测，不建库、不起 app）。**conftest 缺口：无**。

### ⑤ 参数化方案
- 不建议强行 parametrize。成员这 1 个 test 是"10 字段同时坏值"的整体组合契约，语义独立于锚点 6 个 test（锚点逐字段/逐类拆开测）。**直接把成员函数原样追加为锚点第 7 个 test 即可**（去掉自带 `_base_snapshot`、`from __future__ import annotations` 头改用锚点已有的）。
- 若评审坚持归并：可与锚点 `..._relaxed_invalid_numeric_falls_back_with_degradation` / `..._relaxed_invalid_choice...` 合一个 parametrize，维度 = (输入坏值 dict, 期望回退/钳值映射, 期望 counters 下限)。但成员的"min_clamp(0→1, -1→0)"与"中文字段名不泄露 key"是组合断言，拆进 parametrize 反而降低可读性，**不推荐**。

### ⑥ load-bearing import / importlib
- grep 全仓：无任何文件 import `regression_config_validator_relaxed_contract`。删之安全。

### ⑦ registry 影响
- `regression_config_validator_relaxed_contract.py`：**不在** test_registry_data.py / groups / quality_gate 任何清单。
- 锚点 `regression_config_validator_preset_degradation.py`：**亦不在**任何 registry。
- **registry 改动：无。**

### ⑧ B-COMPAT pin
- 无。（成员断言虽含安全敏感的"中文字段名不泄露内部 key"，但锚点 docstring 已声明同契约，属同源补强，非禁去重红线 pin。）

### ⑨ 断言条数对账
- 前：锚点 47 + 成员 17 = **64**
- 后预期：47 + 17 = **64**（无可去重的断言行；仅去重一份 helper 函数定义，不计入断言）。✅ 保真

### ⑩ 风险 / 阻塞点
- 低风险。唯一注意：成员断言 `time_budget_seconds == 1` 和 `graph_critical_weight == 0` 是**"钳到最小值"而非"回退到 base"**的语义——挂靠搬运时**逐字照搬，不要被锚点其它 test 的"回 base"语义带偏改成 base 值**。

---

## 节 2：process_excel_part_operation_hours_import -> `regression_process_excel_part_operation_hours_append_fill_empty_only.py`

### ① 成员文件
- `tests/regression_process_excel_part_operation_hours_import.py`（237 行，1 个 test，**20** 断言/抛出）

### ② 目标 KEEP 锚点 + 命名理由
- 任务给的"process_excel_part_op_hours 锚点"对应一个**同族 3 文件簇**：
  - `regression_process_excel_part_operation_hours_append_fill_empty_only.py`（append 模式，19 断言）← **建议锚点**
  - `regression_process_excel_part_operation_hours_source_row_num.py`（原始行号回显，13 断言）
  - 成员 `..._import.py`（overwrite 模式 happy + NaN/Inf 拒绝 + external 拒绝，20 断言）
- 契约同源核实：✅ 三文件全测 `/process/excel/part-operation-hours` 的 preview→confirm 全链路，且 `_make_xlsx_bytes` / `_extract_raw_rows_json` / `_extract_hidden_input` / `_assert_status` helper **几乎逐字相同**（`diff` 成员 vs append 的 1-50 行：仅差 append 的模块 docstring + 末尾空行，helper 主体 byte-identical）。
- 命名理由：以 `append_fill_empty_only` 为锚点是因它断言面最广且 helper 集最全；挂靠后**建议把文件重命名为 `regression_process_excel_part_operation_hours_import_modes.py`**（覆盖 overwrite+append+source_row_num 三模式），或保守起见保留 append 文件名直接追加成员 test。若同时合并 source_row_num（见节注），更应改名。

### ③ test 函数清单 + 断言条数 + 关键断言逐字摘录
成员 1 个 test：`test_process_excel_part_operation_hours_import(app_client, db_path)`（20 断言/抛出）。关键坏值/边界：
- external 行预览须报错（`mode=overwrite`）：`if "仅支持内部工序导入工时" not in html_bad: raise RuntimeError("预览未识别外部工序行...")`
- **NaN 拒绝**：`if "必须是有限数字" not in html_nan: raise ...`；confirm 阶段 `if "导入被拒绝" not in html_nan_confirm: raise RuntimeError("confirm 阶段未拒绝 NaN 数据")`
- **Inf 拒绝**：`if "必须是有限数字" not in html_inf: raise ...`；confirm `if "导入被拒绝" not in html_inf_confirm: raise ...`
- 坏值导入后 **DB 不被改写**（边界保真）：查 `PartOperations WHERE part_no='A1001' AND seq=5`，`if abs(float(row_before["setup_hours"] or 0.0))>1e-6 or abs(...unit_hours...)>1e-6: raise RuntimeError("NaN/Inf 预览-确认后不应修改工时")`
- happy（仅内部行）confirm 成功后：seq=5 `source=="internal"` 且 `setup_hours≈1.25 / unit_hours≈0.5`（`abs(...-1.25)>1e-6` 抛错）；seq=10 `source=="external"` 且工时仍为 0（`abs(...)>1e-6` 抛 "外部工序不应被导入工时更新"）。
- `lastrowid is not None` 经 `assert` 间接体现于建库（在 source_row_num/append 同族里也有）。

（append 锚点已覆盖：SKIP/UPDATE/ERROR 标记 + 含 error 行拒绝整批 + 已维护行不被覆盖/空工时补齐/external 不变；source_row_num 覆盖：aps-preview-json-b64 编码 + `__source_row_num=3` 原始行号"第3行"回显不退化为"第2行"。三者**坏值场景互补不重叠**。）

### ④ 共享 setup -> 建议 fixture
- 三文件全用 conftest 的 `app_client` + `db_path`（成员签名即 `(app_client, db_path)`）。✅ **复用 conftest，零缺口。**
- helper 四件套（`_make_xlsx_bytes`/`_extract_raw_rows_json`/`_extract_hidden_input`/`_assert_status`）逐字重复 → 挂靠后**只留一份**（这是允许的去重）。注意 `_assert_status` 在成员与 source_row_num 间签名细节略有差异（成员 `_assert_status(name, resp, expect_code=200)` vs append 同形）——合并时取语义最全的一份，逐字核对参数顺序避免调用点错位。

### ⑤ 参数化方案
- 三 test 各测不同 mode/场景，**不强行 parametrize**；作为同模块 3 个独立 test 函数并存即可（函数名已确认无冲突：`..._import` / `..._append_fill_empty_only` / `..._source_row_num`）。
- 可选轻量 parametrize：NaN 与 Inf 两段在成员内部高度对称（preview "必须是有限数字" + confirm "导入被拒绝"），可在成员 test 内用 `@pytest.mark.parametrize("bad_value", ["NaN", "Inf"])` 折叠——但会拆散"坏值后 DB 不变"的串联校验，**收益小、不推荐跨 test 提取**。

### ⑥ load-bearing import / importlib
- grep 全仓：无文件 import `regression_process_excel_part_operation_hours_import`。删之安全。

### ⑦ registry 影响
- 成员 `..._import.py`：**不在**任何 registry。
- 锚点 `..._append_fill_empty_only.py` 与 `..._source_row_num.py`：**均不在**任何 registry。
- **registry 改动：无。**

### ⑧ B-COMPAT pin
- 无。（NaN/Inf "必须是有限数字"、"导入被拒绝"、external "仅支持内部工序导入工时" 都是常规坏值保真断言，须全保留但非禁去重红线。）

### ⑨ 断言条数对账
- 若仅挂靠成员→append：前 19 + 20 = **39**，后 **39**（仅去重 helper 定义）。✅
- 若三文件全并（推荐改名 import_modes）：19 + 13 + 20 = **52**，后 **52**。✅ 保真

### ⑩ 风险 / 阻塞点
- 中低风险。注意点：
  1. 三文件 helper 有**微小不一致**（source_row_num 的 `_make_xlsx_bytes` 用 `cast(Any, ws)` + `if ws is None: raise`，成员/append 用 `assert ws is not None`）——合并取一份时须确保被合并的 test 不依赖某份 helper 的特定行为；逐字核对后取兼容性最强的一份。
  2. 三 test 都建真库（`db_path`）+ 走 multipart 上传，**单 test 耗时偏高**；并入一个模块不增加单 test 成本，但若被 P5.3 ISOLATE_PERF 名单覆盖须协同（不在本任务范围）。

---

## 节 3：reports_material_weekplan_pages_smoke -> （无现成锚点，需就地保留/或并入 reports 冒烟簇）

### ① 成员文件
- `tests/regression_reports_material_weekplan_pages_smoke.py`（24 行，1 个 test，**1** 断言入口 + 7 次 `_assert_status` HTTP 探活）

### ② 目标 KEEP 锚点 + 命名理由
- 任务给的 "reports_route_smoke 锚点"：**全仓 grep 未找到名为 `reports_route_smoke` / `*reports*smoke*` 的其它文件**——该文件本身就是唯一的 reports/material/weekplan 冒烟入口（其 docstring 明言"旧 smoke_* 脚本不被 pytest 默认收集，这个 regression_* 文件保留同等保护"）。
- **结论：无现成可挂靠锚点。** 候选并入对象：`regression_reports_page_version_default_latest.py`（reports 域、在 registry）或 `regression_reports_workbench_navigation_contract.py`，但二者均是**契约测试**（断言具体内容/版本语义），与本文件的**纯 200 探活冒烟**altitude 不同，强行并入会污染契约文件的语义聚焦。
- **建议处置：① 首选——KEEP 原文件不动**（它已是 regression_* 前缀、能被 pytest 收集，体量 24 行已是最小，无去冗收益）；② 次选——若 P5 必须减少文件数，可并入一个"页面冒烟"聚合文件 `regression_pages_smoke.py`（若该聚合文件后续被建），但**本任务范围内不新建**。**标注：本节不是真正的"挂靠"，应作"无需挂靠/保留"处理。**

### ③ test 函数清单 + 断言摘录
- `test_reports_material_weekplan_pages_smoke(app_client)`：7 条 GET 探活，全期望 200：`/reports/` `/reports/overdue` `/reports/utilization` `/reports/downtime` `/material/materials` `/material/batches` `/scheduler/week-plan`。失败时 `raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body=...")`。

### ④ 共享 setup -> 建议 fixture
- 用 conftest `app_client`（成员签名即 `(app_client)`）。✅ 已最优复用，无缺口。

### ⑤ 参数化方案
- 7 条 URL 已是天然 parametrize 候选；若保留文件可内部 `@pytest.mark.parametrize("path", [...])` 收紧（纯可读性优化，不改行为）。但**不是挂靠诉求**。

### ⑥ load-bearing import / importlib
- grep：无 import 引用。

### ⑦ registry 影响
- 成员**不在**任何 registry。registry 改动：**无**。

### ⑧ B-COMPAT pin
- 无。

### ⑨ 断言条数对账
- 保留不动：1（+7 探活）→ 不变。

### ⑩ 风险 / 阻塞点
- **阻塞性提示：本节找不到任务假设的 `reports_route_smoke` 锚点，建议处置为"保留原文件"而非挂靠。** 需 P5 owner 拍板：保留 / 并入待建的 `regression_pages_smoke.py`。在 owner 拍板前不动此文件。

---

## 节 4：resource_dispatch_partial_overdue_summary_surfaces_warning -> `regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`  ★REGISTRY

### ① 成员文件
- `tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`（104 行，1 个 e2e test，**11** 断言）

### ② 目标 KEEP 锚点 + 命名理由
- 锚点真实文件：`tests/regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`（已存在，102 行，1 个 e2e test，~9 断言）
- 契约同源核实：✅ **近孪生**。两文件：
  - import 同一组 `importlib/json/sys/Path`，同 `REPO_ROOT/SCHEMA_PATH`；
  - **`_build_app(tmp_path, monkeypatch)` 几乎逐字相同**——唯一差异是写入 `ScheduleHistory.result_summary` 的值：成员是含部分有效项的 JSON（`{"overdue_batches":[{"batch_id":"B001","hours":4},{"hours":2},"",null]}`），锚点是坏 JSON 字符串 `"{broken json"`；
  - 同 query `scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1`；
  - 同 `monkeypatch.setattr(app.logger, "warning", _fake_warning)` 捕获日志样板；
  - 同 page+data 双请求结构。
  二者测的是 overdue-marker 浮现契约的两个分支：**partial（部分项坏）vs degraded（全坏 JSON）**。同源、互补。
- 命名理由：以 degraded 文件为锚点（它在 registry 三处都已登记，挂靠后保留它即可少改 registry）；**建议挂靠后把文件重命名为 `regression_resource_dispatch_overdue_summary_surfaces.py`**（同时覆盖 partial+degraded 两面），但改名会牵动 registry 三处路径串——见⑦权衡，**保守方案：不改名，直接把 partial test 追加进 degraded 文件**。

### ③ test 函数清单 + 断言摘录（含坏值/边界）
成员 `test_resource_dispatch_partial_overdue_summary_surfaces_warning(tmp_path, monkeypatch)`（11 断言）：
- `assert page_resp.status_code == 200`；`assert 'id="rdOverdueWarning"' in page_html`
- `assert data_resp.status_code == 200`
- `assert payload.get("success") is True, payload`
- `assert len(data.get("detail_rows") or []) == 1`
- **partial 分支专属边界**：`assert data.get("overdue_markers_degraded") is False`；`assert data.get("overdue_markers_partial") is True`；`assert "已识别" in str(data.get("overdue_markers_message") or "")`
- `assert detail_rows and detail_rows[0].get("is_overdue") is True`
- `assert any("资源排班超期标记部分不完整" in item for item in logged), logged`

锚点 degraded test 专属边界（不动）：`overdue_markers_degraded is True` / `overdue_markers_partial is False` / `"超期" in message` / 日志含 `"资源排班超期标记降级"`。

→ partial 与 degraded 的 3 个核心断言（degraded bool / partial bool / message 文案 / 日志短语）**取值相反**，是不同坏值边界，**必须各自保留**。

### ④ 共享 setup -> 建议 fixture
- **conftest `app_client` 用不上**：本契约需在 create_app 后拿到 `app` 对象做 `monkeypatch.setattr(app.logger, "warning", _fake_warning)`，而 `app_client` 只返回 `.test_client()` 不暴露 app；且需用**特定种子数据**（ResourceTeams/Operators/Machines/Parts/Batches/BatchOperations/Schedule/ScheduleHistory 八表）建库，conftest `db_path` 只建空 schema。→ **真实 fixture 缺口**。
- 建议：挂靠后**把两文件逐字相同的 `_build_app` 去重为模块内一份共享 helper**，参数化 `result_summary` 入参（partial JSON / 坏 JSON）。helper 体（八表 INSERT + importlib app）保留在合并文件内（不强行上提 conftest——这是本组特有的重种子建库，conftest 化收益需另立任务评估）。

### ⑤ 参数化方案
- 维度 = `(result_summary, expect_degraded, expect_partial, expect_message_substr, expect_log_substr)`：
  - partial 行：`(partial_json, False, True, "已识别", "资源排班超期标记部分不完整")`
  - degraded 行：`("{broken json", True, False, "超期", "资源排班超期标记降级")`
- 共享主体：建库（`_build_app(result_summary=...)`）+ 双请求 + `status==200` + `rdOverdueWarning` in html + `success is True` + `len(detail_rows)==1` + `detail_rows[0].is_overdue is True`。
- 注意：partial 的 `detail_rows[0].is_overdue is True` 断言 degraded 文件原本没有——合并 parametrize 时**作为共享断言对两分支都跑**（degraded 分支下该零件是否仍 is_overdue 需实跑确认；若 degraded 分支该断言不成立，则**不能强并进共享段，须留在 partial-only 分支**——这是本节最需实测验证的点）。

### ⑥ load-bearing import / importlib
- grep：无 Python import 指向成员模块。仅 registry 字符串引用（见⑦）。

### ⑦ registry 影响（★精确"旧->新"）
成员 `regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py` 被登记在 **4 处**，锚点 degraded 文件登记在 **3 处**（与成员重叠的 3 处保留锚点条目即可）。挂靠后**删成员的全部 4 条登记**：
1. `tools/test_registry_data.py:207` —— 删 `"tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py",`（同处 L208 的 degraded 条目保留）
2. `tools/test_registry_groups_misc.py:17` —— 在 `scheduler_batches_material_resource` 组 `target_paths` 里删该行（同组 L18 degraded 保留）
3. `tests/test_run_quality_gate.py:664` —— 在 high_value_path 元组里删该行（L665 degraded 保留）
4. `tests/regression_aps_three_gap_docs_quality_gate.py:89` —— 删该行（此处**无** degraded 对应条目，是 partial 独有的三缺口文档门禁登记；删后该清单少一项，须确认 three_gap 门禁不按固定计数断言——**实测核实**）
- 若选择**改名**为 `..._overdue_summary_surfaces.py`：则上述 4 处 partial 路径全删，并把 degraded 的 3 处（data:208/groups_misc:18/quality_gate:665）路径**改为新名**。改名牵动 7 处串、风险更高，**保守方案=不改名、保留 degraded 文件名只删 partial 4 条**。
- **registry 须改条目数（保守不改名方案）：4 条（全删 partial 登记）。**

### ⑧ B-COMPAT pin
- 无禁去重红线。但 partial 与 degraded 的 bool/文案/日志短语相反值**必须各自逐字保留**（语义边界，非重复）。

### ⑨ 断言条数对账
- 前：锚点 ~9 + 成员 11 = **~20**
- 后预期：合并 parametrize 后共享断言跑两遍、分支专属断言各保留 → **>= 20**（去重的只是 `_build_app` helper 与 import 头，不去任何断言）。✅ 保真

### ⑩ 风险 / 阻塞点
- **本批最高风险节。** 阻塞校验点：
  1. ⑤里 `detail_rows[0].is_overdue is True` 在 degraded（坏 JSON）分支下是否成立——合并前必须实跑确认，否则共享段断言会在 degraded 行误报。
  2. ⑦第 4 处 `regression_aps_three_gap_docs_quality_gate.py` 删 partial 路径后，须确认该门禁不依赖固定文件数/不强求 partial 这一条存在。
  3. `_build_app` 八表种子若被 conftest 化是另一任务，本节**不上提**、保留文件内 helper。

---

## 节 5：test_transaction_boundary -> `regression_transaction_savepoint_nested.py`

### ① 成员文件
- `tests/test_transaction_boundary.py`（173 行，**5** 个 test，**20** 断言/抛出/pytest.raises）

### ② 目标 KEEP 锚点 + 命名理由
- 锚点真实文件：`tests/regression_transaction_savepoint_nested.py`（已存在，1 个 mega-test 内含 6 个 Case，~14 断言）
- 契约同源核实：✅ 两文件全 import `from core.infrastructure.transaction import TransactionManager`，测 savepoint 嵌套/失败闭合语义。锚点 docstring：内层失败只回滚内层、外层失败整体回滚、RELEASE/ROLLBACK TO SAVEPOINT/outer commit 失败或连接缺失/读 in_transaction 抛错时抛错并整体回滚。成员补充 `in_transaction_context` + `_current_depth` 失败闭合 + 外部事务 savepoint-only + commit&rollback 双失败 combined error + caplog 文案细节。**同契约族、强互补**。
- 命名理由：以锚点为归集点（regression_ 前缀、mega-test 已是该契约的事实归集）；挂靠后文件名**不变**。成员多为**唯一新增**，本节本质是"把分散的事务边界单测并入事务回归归集文件"。

### ③ test 函数清单 + 断言摘录（标注与锚点重叠/唯一）
成员 5 个 test：
- `test_in_transaction_context_fails_closed_when_depth_lookup_errors`（monkeypatch `_current_depth`→boom）**【唯一】**：`assert tx_mod.in_transaction_context(None) is False`；`assert tx_mod.in_transaction_context(object()) is True`；`assert "读取事务上下文失败" in caplog.text`。锚点无此函数级覆盖。
- `test_transaction_inside_external_transaction_uses_savepoint_only(tmp_path)`**【唯一】**：外部 `conn.execute("BEGIN")` 后进 `with TransactionManager(conn).transaction()`，块后 `assert conn.in_transaction is True`（不夺取外部事务），`conn.rollback()` 后 `assert rows == []`。锚点 Case 用 mem_conn 不测"外部已有 BEGIN 时 savepoint-only 不提交外部"。
- `test_transaction_rolls_back_nested_savepoint_without_affecting_outer(tmp_path)`**【与锚点 Case 1 语义重叠】**：`assert rows == ["outer_ok", "outer_after"]`。锚点 Case 1 是 `["outer_ok","outer_after_inner"]`（值不同但同语义"内层回滚不伤外层"）。→ **保留**（值/写入序不同，非逐字重复）。
- `test_transaction_raises_untrusted_when_outer_rollback_fails(caplog)`**【唯一·细节更强】**：`pytest.raises(RuntimeError, match="事务回滚失败，连接状态不可信")`；`assert "rollback fail" in caplog.text`；`assert "原始异常=original failure" in caplog.text`；`assert "回滚异常=事务回滚失败，连接状态不可信" in caplog.text`。锚点 Case 测了不可信失败但**无 caplog 文案细节**。
- `test_transaction_commit_failure_with_rollback_failure_raises_combined_error`**【唯一】**：`pytest.raises(RuntimeError, match="事务提交失败，且回滚失败；连接状态不可信")`；`assert "commit fail" in str(exc_info.value.__cause__)`。锚点无 commit+rollback 双失败组合。
- `test_nested_savepoint_rollback_failure_blocks_outer_commit(tmp_path, caplog)`**【与锚点 Case 4 重叠·细节更强】**：`pytest.raises(RuntimeError, match="已阻止提交")`；内层 `assert "事务回滚失败，连接状态不可信" in str(exc)`；`assert rows == []`；`assert "事务提交成功" not in caplog.text`。锚点 Case 4 测同根因但 match "事务回滚失败，连接状态不可信"，无"已阻止提交"/"事务提交成功 not in"caplog 维度。→ **保留**。

### ④ 共享 setup -> 建议 fixture
- 成员 3 个 test 用 `tmp_path` 自建 `sqlite3.connect(db_path)` + `CREATE TABLE t (...)`；锚点 mega-test 用 conftest `mem_conn`（:memory: 空表，FK ON+Row）。
- 建议：把成员里 `tmp_path` 文件库 + 手建 `t` 表的样板，**改用 conftest `mem_conn`**（成员这些 test 不需要落盘、只需空表连接，mem_conn 正合）。但成员 `RollbackFailConn`/`CommitAndRollbackFailConn`/`RollbackToFailConn` 等 fake conn 不用真连接，保留原样。→ **复用 conftest `mem_conn`，缺口无**（注意：mem_conn 已 FK ON，成员手建表脚本里若依赖无 FK 行为需核，但 `t` 表无外键，安全）。

### ⑤ 参数化方案
- **不 parametrize**。成员 5 个 test 各测不同失败注入点（depth lookup / external BEGIN / rollback fail / commit+rollback fail / nested rollback-to fail），结构异质，强并 parametrize 会损可读性。直接作为锚点模块新增 5 个独立 test 函数追加（函数名与锚点 `test_transaction_savepoint_nested` 无冲突）。

### ⑥ load-bearing import / importlib
- grep：无 import 指向 `test_transaction_boundary`。删之安全。

### ⑦ registry 影响
- 成员 `test_transaction_boundary.py`：**不在**任何 registry。
- 锚点 `regression_transaction_savepoint_nested.py`：**不在**任何 registry。
- **registry 改动：无。**

### ⑧ B-COMPAT pin
- 无禁去重红线。caplog 文案断言（"原始异常="/"回滚异常="/"已阻止提交"/"事务提交成功" not in）是成员独有的可观测性强断言，**全保留**。

### ⑨ 断言条数对账
- 前：锚点 ~14 + 成员 20 = **~34**
- 后预期：**~34**（成员 5 test 几乎全唯一，仅 2 个 test 与锚点 Case 1/Case4 语义重叠但**值/caplog 维度不同故不去重**）。若评审判定 `..._rolls_back_nested_savepoint_without_affecting_outer` 与锚点 Case 1 逐字同义（**经核：值为 `["outer_ok","outer_after"]` vs `["outer_ok","outer_after_inner"]`，非逐字**）→ 不去重。✅ 保真

### ⑩ 风险 / 阻塞点
- 低风险。注意：成员 `test_transaction_inside_external_transaction_uses_savepoint_only` 显式 `conn.execute("BEGIN")` 测"不夺取外部事务"，若改用 `mem_conn` 须确认 mem_conn 默认隔离级别下手动 BEGIN 行为与原 `sqlite3.connect(file)` 一致（Python sqlite3 默认 `isolation_level=""` 自动 BEGIN 行为，mem 与 file 一致）——**实测核一遍**。

---

## 节 6：test_version_resolution_contract -> `regression_route_version_normalizers_contract.py`  ★REGISTRY

### ① 成员文件
- `tests/test_version_resolution_contract.py`（57 行，**5** 个 test，**21** 断言/pytest.raises）

### ② 目标 KEEP 锚点 + 命名理由
- 锚点真实文件：`tests/regression_route_version_normalizers_contract.py`（已存在，5 个 test，~16 断言）
- 契约同源核实：✅ 两文件都 import `from core.services.scheduler.version_resolution import resolve_version_or_latest` + `from core.infrastructure.errors import ValidationError`，测 `resolve_version_or_latest` 归一化契约。锚点 docstring：None/空当 default、latest/LATEST 当 latest、数字当 explicit、abc/0/-1 抛 ValidationError(field=version) 中文文案、无历史(latest_version=0)不臆造 v1。锚点用 parametrize 覆盖更广，**还额外测 `parse_optional_version_int`**（成员不测）。同契约、锚点是超集归集点。
- 命名理由：锚点已是 registry-登记的归一化契约归集文件，挂靠后文件名**不变**。

### ③ test 函数清单 + 断言摘录（标注重叠/唯一·B-COMPAT 候选）
成员 5 个 test：
- `test_version_resolution_defaults_to_latest`：`resolve_version_or_latest(None, latest_version=7)` → `has_history is True`/`selected_version==7`/`requested_version is None`/`status=="ok"`/`source=="default"`。【与锚点 parametrize 行 `(None,7,7,"default")` 重叠，但成员多 `requested_version is None`、`has_history` 显式断言。】
- `test_version_resolution_accepts_latest_keyword`：`resolve_version_or_latest("latest", latest_version=9)` → `selected_version==9`/`status=="ok"`/`source=="latest"`。【锚点只用 `latest_version=7` 测 latest。值不同，**保留**。】
- `test_version_resolution_reports_no_history_without_fallback_version`：`(None, latest_version=0)` → `has_history is False`/`selected_version is None`/`status=="no_history"`。【与锚点 `test_resolve_version_or_latest_no_history_does_not_synthesize_v1`(遍历 None/""/"latest") 语义重叠，成员是其子集——可去重并入锚点已有 test。】
- `test_version_resolution_reports_missing_explicit_history`**【关键唯一边界·必保】**：`resolve_version_or_latest("5", latest_version=9, version_exists=lambda v: False)` → `has_history is True`/`selected_version is None`/`requested_version==5`/`status=="missing_history"`。**锚点对应 test 用 `latest_version=0` → `has_history is False`**（无历史）。成员是"**有历史(latest=9)但请求的显式版本不存在**"——与锚点的"无历史"是**不同边界**，绝不可去重。
- `test_version_resolution_rejects_invalid_explicit_value`：两段 `pytest.raises(ValidationError, match="版本号不对")`（"bad" 和 "0"），断言 `exc_info.value.message == VERSION_ERROR_MESSAGE` 且 `.field=="version"`。【与锚点 parametrize `["abc","0","-1"]` 重叠，成员少 "-1"、多用了 `VERSION_ERROR_MESSAGE` 常量比对；锚点是字符串字面量比对。语义同。可去重，但成员引用 `VERSION_ERROR_MESSAGE` 常量是更强契约——保留一处对常量的断言。】

### ④ 共享 setup -> 建议 fixture
- 纯函数级，无 fixture、无建库、无 app。**conftest 缺口：无。**

### ⑤ 参数化方案
- 成员 `defaults_to_latest` / `accepts_latest_keyword` 可**并入锚点已有的 `test_core_version_resolution_contract` parametrize**，新增行：`("latest", 9, 9, "latest")`（latest 值=9 的唯一性）；并把成员独有的 `requested_version is None` 断言补进该参数化主体（对 default/latest 源都成立时）。
- 成员 `reports_missing_explicit_history`（latest=9, version_exists=False）**单独新增为锚点的一个 test**（与锚点 `..._missing_explicit_version_is_not_selected` 的 latest=0 版并列）。维度差异 = (latest_version, has_history 期望)：`(0, False)` vs `(9, True)`。可合一个 parametrize `[(0, False, None_selected), (9, True, requested==5)]`。
- 成员 `rejects_invalid_explicit_value` 的 "0"/"bad" 折进锚点 `["abc","0","-1"]` parametrize；保留**一处** `message == VERSION_ERROR_MESSAGE`（常量比对，强于字面量）。

### ⑥ load-bearing import / importlib
- grep：无 Python import 指向成员模块。仅 registry 字符串（见⑦）。

### ⑦ registry 影响（★精确"旧->新"）
成员 `test_version_resolution_contract.py` 登记 **2 处**；锚点 `regression_route_version_normalizers_contract.py` 登记 **3 处**（含成员未覆盖的 quality_gate high_value）。挂靠后**删成员 2 条登记**（锚点 3 条全保留，已覆盖该契约）：
1. `tools/test_registry_data.py:39` —— 删 `"tests/test_version_resolution_contract.py",`（QUALITY_GATE_GUARD_TESTS 内；锚点同清单 L66 保留）
2. `tools/test_registry_groups_scheduler.py:155` —— 删该行（scheduler 组内；锚点同组 L163 保留）
- 锚点已在 `tests/test_run_quality_gate.py:638` high_value 登记，成员不在该清单——无需动 quality_gate test。
- **registry 须改条目数：2 条（删 test_version_resolution_contract 两处登记）。**

### ⑧ B-COMPAT pin
- **强约束（非"禁去重红线"，但语义边界必保，等同 pin 对待）**：成员 `test_version_resolution_reports_missing_explicit_history` 的"**latest_version=9（有历史）+ 请求显式版本不存在 → has_history True / status missing_history / requested_version==5**"边界——锚点同名 test 是 latest_version=0（无历史）分支，**两者取值相反，绝不可合并去重**，挂靠时逐字保留为独立 case。
- 其余无禁去重红线 pin。

### ⑨ 断言条数对账
- 前：锚点 ~16 + 成员 21 = **~37**
- 后预期：可逐字去重的同义断言 = `no_history`（成员 3 条 ⊂ 锚点遍历 test）+ `defaults_to_latest`/`rejects_invalid` 与锚点 parametrize 重叠的若干条 → 估去重约 6-8 条。**后 >= 锚点 16 + 成员唯一(missing_explicit latest=9 的 ~4 条 + latest=9 keyword + requested_version is None + VERSION_ERROR_MESSAGE 常量比对) ≈ 24-29**。
- **保真校验线：合并后必须 >= 锚点原 16（锚点断言一条不丢）+ 成员所有"唯一边界"断言（latest=9 missing/keyword/常量比对）全保留。** 去重的仅限逐字同义行。✅

### ⑩ 风险 / 阻塞点
- 中风险（因 ★REGISTRY + 有边界易混淆）。阻塞校验点：
  1. ⑧的 latest=9 vs latest=0 两个 missing/no_history 边界**极易在 parametrize 折叠时被误并**——务必在合并 spec 落地时把 `has_history` 期望也纳入参数，并实跑确认两行都过。
  2. 删 registry 2 条后，须确认 `regression_quality_gate_registry_split_scope_contract` / `test_full_test_debt_registry_contract` 等元测试不按固定计数断言 GUARD_TESTS 长度（**实测核**）。

---

## 跨节汇总

| 节 | 成员文件(行) | 目标锚点 | 锚点存在 | registry 改动 | B-pin/边界必保 | 断言前→后 |
|---|---|---|---|---|---|---|
| 1 | config_validator_relaxed(72) | preset_degradation | ✅ | 无 | 无 | 64→64 |
| 2 | process_excel_import(237) | part_op_hours_append(+source_row_num) | ✅ | 无 | 无 | 39或52→等量 |
| 3 | reports_weekplan_smoke(24) | **无现成锚点** | — | 无 | 无 | 保留不动 |
| 4 | resource_dispatch_partial(104) ★ | invalid_summary_degraded | ✅ | **4 条删** | partial↔degraded 反值 | ~20→>=20 |
| 5 | test_transaction_boundary(173) | savepoint_nested | ✅ | 无 | 无 | ~34→~34 |
| 6 | version_resolution_contract(57) ★ | route_version_normalizers | ✅ | **2 条删** | latest=9 missing 边界 | ~37→24-29 |

- **registry 总改条目数：6 条**（节 4 删 4 + 节 6 删 2），分布在 `tools/test_registry_data.py`(×2: L39, L207) / `tools/test_registry_groups_misc.py`(×1: L17) / `tools/test_registry_groups_scheduler.py`(×1: L155) / `tests/test_run_quality_gate.py`(×1: L664) / `tests/regression_aps_three_gap_docs_quality_gate.py`(×1: L89)。
- **唯一真正阻塞点**：节 3 找不到任务假设的 `reports_route_smoke` 锚点——建议作"保留原文件"处置，待 P5 owner 拍板是否新建 `regression_pages_smoke.py` 聚合再并入。其余 5 节锚点均已核实存在且契约同源。
- **B-COMPAT 禁去重红线 pin：0 个**（这批挂靠不触碰任何"禁去重"断言）；但节 4（partial↔degraded 反值）、节 6（latest=9 vs latest=0 边界）有 2 处"语义反值边界"必须逐字保留、严禁 parametrize 误并，需在落地时实跑双分支确认。
- **共享 fixture 缺口**：仅节 4 的 `_build_app`（八表种子 + 需 app 对象 monkeypatch app.logger）用不上 conftest `app_client`，须保留文件内共享 helper；节 2/3 直接复用 `app_client`+`db_path`，节 5 建议改用 `mem_conn`，节 1/6 纯函数无需 fixture。
