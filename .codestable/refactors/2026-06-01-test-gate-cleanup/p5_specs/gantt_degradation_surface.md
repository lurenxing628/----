# P5.1 MERGE 簇 spec — gantt_degradation_surface

> 状态:REGISTRY 簇(3/4 成员在 `QUALITY_GATE_GUARD_TESTS` required 真相源)。合并后路径变化必须同步改 4 处门禁引用,否则 required 自动打标静默失效 = 少跑。
> 铁律遵守:本簇 4 个文件各覆盖**不同的退化语义**(坏时间行 / 日历加载失败 / 非法摘要全降级 / 部分逾期降级),无逐字重复断言,合并仅做"同进程化建库样板"层面的去重,业务断言一条不删,并入 parametrize 后断言条数 >= 合并前之和。

---

## ① 成员文件(各行数)

| 文件 | 行数 | test 函数数 | required? | 建库方式 |
|---|---|---|---|---|
| `tests/regression_gantt_bad_time_rows_surface_degraded.py` | 84 | 1 | ✅ required(GUARD_TESTS:113) | 裸 `sqlite3.connect(":memory:")` + 手 `_load_schema`,**直接调 `GanttService(...).get_gantt_tasks()`**(不走 HTTP) |
| `tests/regression_gantt_calendar_load_failed_degraded.py` | 67 | 1 | ✅ required(GUARD_TESTS:112) | 复用 `app_client`/`db_path`/`repo_root` fixture + `mock.patch` build_calendar_days,走 HTTP `/scheduler/gantt(/data)` |
| `tests/regression_gantt_invalid_summary_surfaces_overdue_degraded.py` | 90 | 1 | ❌ 非 required(门禁真相源/守卫中完全不出现) | 自建 `_build_app(tmp_path, monkeypatch)`,走 HTTP |
| `tests/regression_gantt_partial_overdue_summary_surfaces_warning.py` | 95 | 1 | ✅ required(GUARD_TESTS:73) | 自建 `_build_app(tmp_path, monkeypatch)`,走 HTTP |

合计 336 行,4 个 test 函数。

---

## ② 目标合并文件名 + 命名理由

**`tests/regression_gantt_degradation_surface.py`**

理由:
- 4 个文件共同主题是"甘特图在多种坏数据/失败下的**退化(degradation)呈现表面(surface)**契约",簇名即 `gantt_degradation_surface`,直接复用为文件名语义最准。
- `surface` 沿用 3 个成员文件名里已有的 `_surface` / `surfaces` 词根(bad_time_rows_**surface**_degraded、invalid_summary_**surfaces**_overdue、partial_overdue_summary_**surfaces**_warning),语义连续。
- ⚠️ 由于本文件被 required 真相源精确登记,路径改名是 breaking 的,见 ⑦ + ⑩。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### A. bad_time_rows_surface_degraded —— `test_gantt_bad_time_rows_surface_degraded`(断言 14 条)

DB/服务层(直接调 `GanttService`,无 HTTP):
- `assert cur1.lastrowid is not None` / `assert cur2.lastrowid is not None`(2)
- `assert int(data.get("task_count") or 0) == 1`(坏时间那行被跳过,只剩 1)
- `assert data.get("degraded") is True`
- `assert int(counters.get("bad_time_row_skipped") or 0) == 1`
- `assert data.get("empty_reason") is None`(**坏值边界**:仅部分过滤,空原因码须为 None)
- `assert events and events[0].get("code") == "bad_time_row_skipped"`

坏值构造(load-bearing,禁改):第二条 Schedule 写入 `start_time = "2026-03-02 99:00:00"`(小时 99 = 非法时间)。

JS 静态契约(7 条,逐字):
- `assert "buildDegradationMessages" in gantt_boot_js`
- `assert "bad_time_row_skipped" in gantt_contract_js`
- `assert "all_rows_filtered_by_invalid_time" in gantt_contract_js`(统一空原因码)
- `assert "已过滤 " in gantt_contract_js`
- `assert "已过滤 \" + badTimeSkipped + \" 条开始或结束时间写法不对的排程记录。当前区间没有可显示排程" in gantt_render_js`
- `assert "当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。" in gantt_render_js`
- `assert "当前筛选条件下暂无可显示任务。" in gantt_render_js`

### B. calendar_load_failed_degraded —— `test_gantt_calendar_load_failed_degraded`(断言 12 条)

依赖 `mock.patch("core.services.scheduler.gantt_service.build_calendar_days", side_effect=_calendar_failed)`,`_calendar_failed` 返回 `BuildOutcome.from_collector([], collector, empty_reason="calendar_load_failed")`,collector 含 `sample="RuntimeError"`。

- page:`_assert_status(page_resp, ...)`(200)
- `assert 'id="ganttDegradationWarning"' in html`
- `assert "工作日历加载失败，当前不显示假期/停工背景标注。" not in html`(**边界**:内部 message 不得泄漏到页面 HTML)
- data:`_assert_status(data_resp, ...)`(200)
- `assert payload.get("success") is True`
- `assert data.get("degraded") is True`
- `assert data.get("empty_reason") == "calendar_load_failed"`
- `assert int(counters.get("calendar_load_failed") or 0) == 1`
- `assert any(str(evt.get("code") or "") == "calendar_load_failed" for evt in events)`
- `assert "RuntimeError" not in str(events)`(**安全边界**:sample 中的内部异常类名不得外泄)
- `assert all("sample" not in evt for evt in events if isinstance(evt, dict))`(**边界**:events 不带 sample 字段)
- JS:`assert "ganttDegradationWarning" in gantt_boot_js` / `assert "buildDegradationMessages" in gantt_boot_js` / `assert "calendar_load_failed" in gantt_contract_js`

### C. invalid_summary_surfaces_overdue_degraded —— `test_gantt_invalid_summary_surfaces_overdue_degraded`(断言 10 条)

坏值构造(load-bearing):`ScheduleHistory.result_summary = "{broken json"`(不可解析 JSON)。

- `assert lastrowid is not None`
- `assert page_resp.status_code == 200`
- `assert 'id="ganttOverdueWarning"' in page_html`
- `assert data_resp.status_code == 200`
- `assert payload.get("success") is True`
- `assert int(data.get("task_count") or 0) == 1`
- `assert data.get("overdue_markers_degraded") is True`(**全降级**:整段 JSON 坏,标记降级)
- `assert data.get("overdue_markers_partial") is False`(与 D 互斥:全降级时 partial 为 False)
- `assert "超期" in str(data.get("overdue_markers_message") or "")`
- `assert any("甘特图超期标记降级" in item for item in logged)`(logger.warning 被注入捕获)

### D. partial_overdue_summary_surfaces_warning —— `test_gantt_partial_overdue_summary_surfaces_warning`(断言 11 条)

坏值构造(load-bearing,与 C 不同):`result_summary` = `{"overdue_batches": [{"batch_id": "B001", "hours": 4}, {"hours": 2}, "", None]}`——**有效 + 缺字段 + 空串 + None 混合**(部分坏值,非全坏)。

- `assert lastrowid is not None`
- `assert page_resp.status_code == 200`
- `assert 'id="ganttOverdueWarning"' in page_html`
- `assert data_resp.status_code == 200`
- `assert payload.get("success") is True`
- `assert int(data.get("task_count") or 0) == 1`
- `assert data.get("overdue_markers_degraded") is False`(**与 C 镜像互斥**:部分坏不是全降级)
- `assert data.get("overdue_markers_partial") is True`
- `assert "已识别" in str(data.get("overdue_markers_message") or "")`(文案与 C 的"超期"不同)
- `assert tasks and tasks[0].get("meta", {}).get("is_overdue") is True`(有效那条仍标记 overdue)
- `assert any("甘特图超期标记部分不完整" in item for item in logged)`(warning 文案与 C 不同)

C 与 D 是**故意成对的镜像边界**(degraded/partial 两态互斥 + 三段不同文案"甘特图超期标记降级"/"甘特图超期标记部分不完整"/"超期"/"已识别"),严禁去重为一条。

---

## ④ 共享 setup -> 建议 fixture(复用 conftest 哪个 / 缺口)

| 成员 | 现状 setup | 建议复用 conftest fixture | 缺口 |
|---|---|---|---|
| B calendar | 已用 `app_client` + `db_path` + `repo_root`(3 个 conftest fixture) | 全部复用,保持 | 无缺口,B 已是标准范式 |
| C invalid_summary | 自造 `_build_app(tmp_path, monkeypatch)`(ensure_schema + 建表 + importlib app) | 改用 `db_env` 建库 + `app_client`?**不能直接换**(见下) | 见缺口① |
| D partial | 同 C 的 `_build_app`,唯一差异是 `result_summary` 内容 | 同 C | 同 C |
| A bad_time | 裸 `:memory:` + 手 `_load_schema` + **直接 `GanttService`** | 可复用 `schema_conn`(:memory: + 全量 schema.sql + FK ON + Row) | 见缺口② |

**缺口①(C/D 与 app_client 的偏差):**
- C/D 的 `_build_app` 用 `Parts.route_raw="[]"`,而 A 用 `Parts.route_parsed="yes"`——两套字段不同,是各自被测路径需要的种子,**不能统一**。
- C/D 在 `app_client` fixture 之外**还要 monkeypatch `app.logger.warning`** 捕获日志(断言 logged),`app_client` 直接返回 `test_client()` 拿不到 `app` 对象。
  - 解决:合并后 C/D 不复用 `app_client`,改为**簇内私有 helper `_build_overdue_app(db_env, ...)`** 返回 `(app, client)`;`db_env` 提供 APS_* 环境与库,helper 内仅做"插种子数据 + importlib create_app + monkeypatch logger.warning"。这把建表/建环境 38 行样板(C/D 逐字重复)收敛到 db_env + 一个 helper。
  - C/D 的种子数据差异仅 `result_summary` 一处 → 收进 parametrize(见 ⑤)。

**缺口②(A 直连服务):**
- A 不走 HTTP、直接 `GanttService(conn, ...).get_gantt_tasks(view=..., week_start=..., version=...)`,且建库种子用 `route_parsed="yes"`(与 C/D 的 `route_raw="[]"` 不同)。
- A 可复用 `schema_conn`(替掉自写 `_load_schema` + `sqlite3.connect`),但**仍需自己插业务种子行**(Machines/Operators/Parts/Batches/2×BatchOperations/2×Schedule/ScheduleHistory)。A 的 JS 断言用 `REPO_ROOT`,合并后改用 `repo_root` fixture。
- A 的形态(服务层直连 + 坏小时 99)与 B/C/D(HTTP)差异大,**不并入同一 parametrize**,作为独立 test 函数保留在合并文件内。

结论:`repo_root`、`db_env` 可复用;A 复用 `schema_conn`;C/D 共享簇内 helper(基于 `db_env`)。无需新增 conftest fixture。

---

## ⑤ 参数化方案

合并后 3 个 test 函数(不是 1 个),parametrize 只收 C/D 这一对同形态差异:

1. **`test_gantt_bad_time_rows_surface_degraded`** —— 独立,不 parametrize(服务层直连 + JS render 7 条断言独有)。
2. **`test_gantt_calendar_load_failed_degraded`** —— 独立,不 parametrize(mock build_calendar_days + 安全断言 RuntimeError/sample 不外泄独有)。
3. **`test_gantt_overdue_markers_summary[invalid|partial]`** —— C/D parametrize,维度:

```
@pytest.mark.parametrize("case", [
  # id="invalid"  全坏 JSON → 全降级
  dict(result_summary='{broken json',
       expect_degraded=True, expect_partial=False,
       expect_message_kw="超期",
       expect_log_kw="甘特图超期标记降级",
       expect_task_overdue=None),       # invalid 分支不断言 tasks[0].meta
  # id="partial"  混合坏值 → 部分降级
  dict(result_summary=json.dumps({"overdue_batches":[{"batch_id":"B001","hours":4},{"hours":2},"",None]}, ensure_ascii=False),
       expect_degraded=False, expect_partial=True,
       expect_message_kw="已识别",
       expect_log_kw="甘特图超期标记部分不完整",
       expect_task_overdue=True),        # partial 分支额外断言 tasks[0].meta.is_overdue is True
])
```

注意:partial 分支多一条 `tasks[0].meta.is_overdue is True` 断言,invalid 分支没有 → 用 `if case["expect_task_overdue"] is not None:` 守护,**不丢断言**。degraded/partial/message/log 四个维度对两 case 都断言(互斥镜像,全保留)。

---

## ⑥ load-bearing import / importlib 引用(删原文件会断吗?已 grep 核实)

- **无任何 `.py` 以 `import` / `importlib.import_module` 方式引用这 4 个测试文件**(测试文件名不是模块导入目标)。`grep` 全仓确认:除自身外的引用全部是"字符串路径登记/清单",非 Python import。
- 4 个文件内部的 `importlib.import_module("app")` 是导入**被测的 app 模块**,与文件名无关,合并后照常工作。
- 删原文件本身不会因 import 断;**会断的是下面 ⑦ 的字符串路径登记**(门禁/守卫按精确路径匹配)。

全仓引用清单(非自身):
- 门禁真相源 / 分组:`tools/test_registry_data.py`、`tools/test_registry_groups_scheduler.py`(见 ⑦)
- 门禁守卫测试:`tests/test_run_quality_gate.py`、`tests/regression_aps_three_gap_docs_quality_gate.py`(见 ⑦)
- 纯文档/历史产物(**不影响门禁运行,不必改**,改了更干净但非阻塞):`.codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-items.yaml`、`.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml`、`.codestable/refactors/2026-06-01-test-gate-cleanup/summary.json`

---

## ⑦ registry 影响:须改的条目("旧 -> 新")

合并目标 = `tests/regression_gantt_degradation_surface.py`。旧 3 个 required 路径 + 1 个非 required 路径在以下 **4 处精确登记**必须同步;否则 required 自动打标(conftest `iter_required_tests` 按路径前缀匹配 nodeid)对新文件失效 = 静默少跑。

> 真相链:`tests/conftest.py:iter_required_tests()` → `tools.test_registry.iter_required_tests(QUALITY_GATE_REQUIRED_TESTS)` → `QUALITY_GATE_REQUIRED_TESTS = (QUALITY_GATE_SELFTEST_PATH, *QUALITY_GATE_GUARD_TESTS)`(`tools/test_registry_data.py:241`)。所以 **`QUALITY_GATE_GUARD_TESTS` 是 required 单一真相源**。

### 改动点 1 —— `tools/test_registry_data.py`(required 真相源,**必须改**)
3 个 required 文件的字符串删除并替换为合并文件名(invalid_summary 本就不在此处,无需动)。建议删 3 行、在原位置之一新增 1 行:
- 旧(line 73):`"tests/regression_gantt_partial_overdue_summary_surfaces_warning.py",`
- 旧(line 112):`"tests/regression_gantt_calendar_load_failed_degraded.py",`
- 旧(line 113):`"tests/regression_gantt_bad_time_rows_surface_degraded.py",`
- 新(三者合一,放在 line 112-113 位置即可):`"tests/regression_gantt_degradation_surface.py",`

⚠️ `test_run_quality_gate.py:629` 断言 `REQUIRED_TEST_ARGS` 去重(`len == len(set(...))`),所以新路径只能加 **1 次**,3 删 1 增。

### 改动点 2 —— `tools/test_registry_groups_scheduler.py`(分组 `scheduler_analysis_gantt_reports_week_plan` 的 `target_paths`,**必须改**)
- 旧(line 263):`"tests/regression_gantt_partial_overdue_summary_surfaces_warning.py",`
- 旧(line 311):`"tests/regression_gantt_calendar_load_failed_degraded.py",`
- 旧(line 312):`"tests/regression_gantt_bad_time_rows_surface_degraded.py",`
- 新(三合一,放 line 311-312 位置):`"tests/regression_gantt_degradation_surface.py",`

### 改动点 3 —— `tests/test_run_quality_gate.py`(守卫测试,**必须改**,否则该测试 fail)
该文件 line 632-699 的 `high_value_path` 元组逐条 `assert high_value_path in module.REQUIRED_TEST_ARGS`,含:
- 旧(line 647):`"tests/regression_gantt_calendar_load_failed_degraded.py",`
- 旧(line 648):`"tests/regression_gantt_bad_time_rows_surface_degraded.py",`
- 新:替换为单行 `"tests/regression_gantt_degradation_surface.py",`(partial/invalid 不在这个 high_value 列表里,无需动)

### 改动点 4 —— `tests/regression_aps_three_gap_docs_quality_gate.py`(REGRESSION_TESTS 清单,**必须改**)
- 旧(line 78):`"tests/regression_gantt_partial_overdue_summary_surfaces_warning.py",`
- 新:`"tests/regression_gantt_degradation_surface.py",`
> 该 partial 路径同时被 dev guide markdown `docs/dev/aps_three_gap_quality_gate.md` 第 3 节列出,经 `regression_quality_gate_registry_split_scope_contract.py::test_three_gap_dev_guide_regression_list_is_required_and_grouped` 校验"列出的测试 ⊆ required 且 ⊆ grouped"。**改 registry 后该 guide markdown 里的 partial 路径也必须一并改名**,否则该守卫 fail。→ **新增改动点 4b。**

### 改动点 4b —— `docs/dev/aps_three_gap_quality_gate.md`(dev guide 第 3 节,**必须改**,被守卫钉)
把第 3 节里 `tests/regression_gantt_partial_overdue_summary_surfaces_warning.py` 改名为合并文件名。(本侦察未逐行读该 md,执行时须先 grep 确认 partial 路径在第 3 节出现的精确行;若 calendar/bad_time/invalid 也出现需一并处理。)

---

## ⑧ B-COMPAT pin(必须逐字保留、禁去重的断言)

无显式 `_B_COMPAT_SAFEGUARDS.md` 锚点命中本簇(执行时仍建议对照该文件确认)。但以下断言**承载行为契约,等同 B-pin,禁去重/禁弱化**:

- B 的安全断言对(内部异常/采样不外泄):
  - `assert "RuntimeError" not in str(events)`
  - `assert all("sample" not in evt for evt in events if isinstance(evt, dict))`
  - `assert "工作日历加载失败，当前不显示假期/停工背景标注。" not in html`
- C/D 的互斥镜像四元组(全降级 vs 部分降级,严禁合并成一条):
  - C:`overdue_markers_degraded is True` + `overdue_markers_partial is False` + `"超期" in message` + log `"甘特图超期标记降级"`
  - D:`overdue_markers_degraded is False` + `overdue_markers_partial is True` + `"已识别" in message` + log `"甘特图超期标记部分不完整"`
- A 的 render 层中文文案 3 条(逐字含标点,B-pin 级):`已过滤 ... 条开始或结束时间写法不对的排程记录。当前区间没有可显示排程` / `当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。` / `当前筛选条件下暂无可显示任务。`

逐字保留的断言数:**9 条**(2 安全 + 1 html-not-in + C/D 各 4 中互斥 4 条计为 4 + render 3 条 = 但仅统计"绝对禁去重的硬契约":2+1+render 3 = 6,加上 C/D 镜像不可合并那 1 组按差异维度计 3 ≈ 共 9)。执行时全部照搬。

---

## ⑨ 断言条数对账

| 文件 | 合并前断言数 |
|---|---|
| A bad_time | 14 |
| B calendar | 12 |
| C invalid_summary | 10 |
| D partial | 11 |
| **前总和** | **47** |

合并后预期(parametrize 不丢断言):
- `test_gantt_bad_time_rows_surface_degraded`:14
- `test_gantt_calendar_load_failed_degraded`:12
- `test_gantt_overdue_markers_summary[invalid]`:10
- `test_gantt_overdue_markers_summary[partial]`:11
- **后预期合计:47**(逐条搬运,partial 分支的 `tasks[0].meta.is_overdue` 用 if 守护保留)

47 -> 47,**保真,无去重损失**(本簇 4 文件断言无逐字重复项可删)。

---

## ⑩ 风险 / 阻塞点

1. **[阻塞级] required 静默失效**:`tools/test_registry_data.py` 是 required 真相源(conftest 据此打标)。若改文件名但漏改此处,合并文件**不会再被打 required marker**,`pytest -m required` 静默少跑 3 个高价值降级契约,无任何报错——这正是任务点名的最大坑。必须先改 ⑦ 改动点 1。
2. **[守卫硬失败] 4 处字符串引用联动**:改动点 1/2/3/4/4b 任一漏改都会让对应守卫测试 fail(去重断言 line 629、high_value `in REQUIRED_TEST_ARGS` line 699、split_scope 的 dev-guide ⊆ required/grouped 断言)。5 处必须同提交一起改。
3. **[去重红线] C/D 镜像不可合并**:degraded/partial 是互斥两态,文案/日志各不同(超期 vs 已识别、降级 vs 部分不完整),必须保留为 parametrize 两 case,不得"优化"成一条。
4. **[形态差异] A 不可并入 HTTP parametrize**:A 走服务层直连 + 独有 7 条 JS render 文案断言,B 走 HTTP + mock。强行并参会丢断言或引入无关分支,保持 3 个独立函数 + 1 个 parametrize 对。
5. **[种子字段差异] route_parsed vs route_raw**:A 用 `Parts.route_parsed="yes"`,C/D 用 `Parts.route_raw="[]"`,B 用 conftest `db_path`(经 ensure_schema 不插 Parts,靠 mock)。建库种子不可统一,合并时各自保留。
6. **[非阻塞] 文档/roadmap 残留路径**:`.codestable/roadmap/*.yaml`、`summary.json` 内旧路径不影响门禁运行,改名后这些只是历史记录失准,可选清理,非阻塞。
