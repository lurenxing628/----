# P5.2 KEEP_TRIM 规格 — 批次 B07_data_b

来源 TSV: `.codestable/refactors/2026-06-01-test-gate-cleanup/p5_specs/keep_trim_files.tsv`
所有文件 L3 verdict = `mid`（剪脆性尾，保业务契约）。
本规格是实现 agent 的唯一依据。每个删除/改写点都给了**当前文件**里的逐字锚点（TSV 里的行号已过时，已按断言文本重新定位）。

通用红线：
- 本批次 5 个文件，没有"整函数删除"。所有 trim 都是**保留函数内**剪脆性断言行 / 把超长中文逐字快照收窄成稳定关键片段。
- registry 耦合：只有 `regression_operation_execution_exception_surfaces.py` 被按**文件路径**钉在 `tools/test_registry_data.py:185` 与 `tools/test_registry_groups_scheduler.py:292`（文件清单型 registry，只要文件存在即可）。因此**绝不可删整文件、绝不可删唯一的测试函数**——只能剪函数体内的断言行。其余 4 个文件无任何 registry/contract 引用。
- 函数名 grep（`grep -rn <funcname> tools/ tests/` 排除自身）全部为空命中：6 个测试函数名均无外部引用。

---

## 文件 1 — tests/regression_operation_execution_exception_surfaces.py（当前 81 行）

单测试函数：`test_exception_details_are_visible_in_detail_rows_gantt_popup_source_and_export`
TSV 理由：异常详情贯通到 detail_rows + 经 ResourceDispatchService 的 Excel 导出；**剪掉 Excel 表头/取值逐字快照块（TSV 称 line 71-79，已过时）**。

**registry**：本文件路径被钉在两处文件清单 registry（见通用红线）。只能剪函数体内断言，禁删函数/文件。

### KEEP（真契约，不动）
- L18-41 setup（建 app、start、report-exception、GET resource-dispatch/data）——真行为路径，必须保留。
- L42-51 `detail_row` 标签断言块：
  - 锚点起始 `detail_row = _json(data_resp)["data"]["detail_rows"][0]`
  - 这些断言（`execution_status_label == "异常中"` … `latest_exception_remark == "等待维修"`）虽含中文，但断言的是 **payload 的 label 字段映射**（状态/原因/严重度→中文标签是 viewmodel 的映射逻辑产物，不是纯排版）。它们是本测试唯一的读侧映射契约面，**KEEP**。
- L53-67 经 `ResourceDispatchService.get_dispatch_payload` + `decorate_resource_dispatch_payload` + `build_resource_dispatch_workbook` 构出 workbook——真路径，**保留**。

### TRIM（脆性尾：openpyxl 单元格逐字值快照）
- 类型：`openpyxl_layout` / exact_chinese_snapshot。
- 当前位置 L73-81，`row_map[...]` 取值断言块。
- 为什么脆：`row_map` 是把 Excel 第 2 行按表头中文键映射后逐字断言每个单元格的中文值（包括 `"二号设备\n完整身份：M2 二号设备"` 这种含换行的拼接排版串）。这些值与 L43-51 的 detail_rows 断言来自**同一个 decorated payload**——同一份数据换个表面再断言一遍，且断言的是 Excel 单元格里的最终排版文案。表头改名、换行格式微调、字段顺序调整都会误失败，而 detail_rows 块已证明数据正确。属于冗余的排版快照尾。
- **删除指令**：删掉从
  ```
      headers = [cell.value for cell in ws[1]]
      values = [cell.value for cell in ws[2]]
      row_map = dict(zip(headers, values))
      assert row_map["现场状态"] == "异常中"
  ```
  起，直到文件末尾的
  ```
      assert row_map["情况说明"] == "等待维修"
  ```
  共 9 行赋值/断言（L72-81，含 `row_map = dict(...)` 与 8 条 `assert row_map[...]`）。
- **保留其上的结构证明**（KEEP，不删）：
  ```
      wb = openpyxl.load_workbook(io.BytesIO(buffer.getvalue()))
      ws = wb["任务明细"]
  ```
  这两行（L68-69）证明 workbook 成功构建且含 `任务明细` sheet——保留它们即可保住"Excel 导出贯通"的结构契约，不残留空函数。
- **必须补一行结构断言**以免 `ws` 变量未被使用 / 函数尾失去 Excel 侧断言：在 `ws = wb["任务明细"]` 后**新增一行**断言该 sheet 至少有 2 行数据：
  ```
      assert ws.max_row >= 2
  ```
  （这是结构不变量而非排版快照，保住"导出含明细行"的可证伪契约。）
- 净删：约 8 行（删 9 行赋值/断言 − 补 1 行结构断言；`headers`/`values` 局部变量随之删除）。

### 风险
mid。被两处文件清单 registry 钉住，但只剪函数体不删文件/函数，引用不悬空。detail_rows 块完整保留了读侧映射契约；Excel 侧降为结构断言。

---

## 文件 2 — tests/regression_operator_machine_detail_readside_normalization.py（当前 92 行）

单测试函数：`test_operator_machine_detail_readside_normalization`
TSV 理由：读侧 legacy 归一 skilled→expert / 是→yes / off→no 且 link/update 写回落库；**HTML-attr 正则耦合是脆性尾（TSV 称 line 94/120，已过时）**。

**结论：本文件建议 KEEP 全部 / 不剪（under-trim 安全）。**

### 判定依据
- L84-90 DB 写回断言（`skill1 == "expert"` / `primary1 == "yes"` / `primary2 == "no"`）是硬契约，必留。
- L59-66 读侧 HTML 显示断言依赖两个正则 helper：
  - `_selected_skill_value`（L15-17）正则匹配 `<option value="(beginner|normal|expert)" selected>`；
  - `_is_primary_checked`（L20-22）正则匹配 `name="is_primary" value="yes" form="..." checked`。
  - 这两个确实是 HTML-attr-source 文本耦合（模板属性顺序/写法变动会误失败），表面上符合"JS/HTML source 文本断言"脆性画像。
- 但 grep 证实：`<option ... selected>` 这类**渲染页面读侧归一显示**断言**仅本文件存在**（`grep -rln 'option value="(beginner|normal|expert)' tests/` 只命中本文件；`_selected_skill_value`/`_is_primary_checked` 无第二处使用）。
- 服务层 `normalize_skill_level`（含 skilled→expert、空→default 等）已被 `tests/test_skill_level_normalization_contract.py` 与 `tests/regression_normalization_matrix_single_source.py` 完整覆盖——但那是**服务层**口径，不覆盖"详情页 GET（在任何 POST 写回之前）就把 legacy 值渲染为已归一的选中 option / 勾选框"这条端到端读路径。
- 即：L59-66 是本测试**独有的读侧渲染归一覆盖**，删之即丢真覆盖；且断言的是"选中项 = 归一后的值"这一行为映射，而非纯像素/几何排版。
- 依据 BIAS=不确定就 KEEP（欠剪可逆、过剪静默丢覆盖），本文件**不剪**。

### 实现 agent 动作
无。`whole_functions_deleted=[]`，`assert_only_trim_count=0`。记录正则 helper 的脆性为已知风险，留待后续若模板大改再单独评估，本批次不动。

### 风险
mid（脆性确实存在但覆盖独有且为行为映射，保守保留）。

---

## 文件 3 — tests/regression_operator_machine_dirty_flags_visible.py（当前 58 行）

单测试函数：`test_operator_machine_dirty_flags_visible`
TSV 理由：dirty_fields 检测 {skill_level,is_primary} 是真的，但 line 70-94（已过时）钉死逐字中文 reason 文本 + HTML 子串；剪文案，保服务行为。

**registry**：无引用（grep 空）。

### KEEP（真契约，不动）
- L16-33 建库 + 跑 `OperatorMachineQueryService(conn).list_simple_rows()`——真服务调用。
- L35-36、L41-42 行定位 + 存在性断言。
- L37 `assert set(row_invalid.get("dirty_fields") or []) == {"skill_level", "is_primary"}` —— 结构集不变量，**真契约 KEEP**。
- L43 `assert set(row_blank.get("dirty_fields") or []) == {"skill_level", "is_primary"}` —— 同上 **KEEP**。
- L47-48 `app_client.get("/personnel/OP200")` + `_assert_status(...)` —— HTTP 200 契约 **KEEP**。
- L51 `assert "以下 2 条记录中有部分字段的旧格式已被系统自动修正" in html` —— **KEEP**：此句含**计数 "2"**（编码"2 条脏记录"这一规则），且证明脏提示区在页面渲染（契约"对用户可见"的最小结构锚）。属带规则的结构断言而非纯文案，保留。
- L52-54 `"涉及字段："` / `"技能等级"` / `"主操设备"` in html —— **KEEP**：短稳定字段标签，证明受影响字段渲染到页面（契约"受影响字段对用户可见"）。

### TRIM A：服务层 dirty_reasons 逐字整句等值断言 → 收窄为 key 存在/片段
- 类型：exact_chinese_snapshot（服务层用户文案）。
- 当前 L38、L39、L44、L45，4 条形如
  `assert "历史技能等级写法较旧，系统已先按能识别的中文选项处理。" == str((row_invalid.get("dirty_reasons") or {}).get("skill_level") or "")` 的整句等值。
- 为什么脆：钉死完整中文整句，文案润色即误失败；真信号是"该字段产生了 dirty_reason"（key 有非空值）。
- **改写指令**（4 条，逐条把整句等值换成 key 非空检查，保留行为信号、去掉整句脆性）：
  - L38 锚点 `assert "历史技能等级写法较旧，系统已先按能识别的中文选项处理。" == str((row_invalid.get("dirty_reasons") or {}).get("skill_level") or ""), row_invalid`
    → 改为 `assert str((row_invalid.get("dirty_reasons") or {}).get("skill_level") or "") != "", row_invalid`
  - L39 锚点 `assert "历史主操标记写法较旧，系统已先按"否"处理。" == str((row_invalid.get("dirty_reasons") or {}).get("is_primary") or ""), row_invalid`
    → 改为 `assert str((row_invalid.get("dirty_reasons") or {}).get("is_primary") or "") != "", row_invalid`
  - L44 锚点 `assert "历史技能等级为空，系统已先按"普通"处理。" == str((row_blank.get("dirty_reasons") or {}).get("skill_level") or ""), row_blank`
    → 改为 `assert str((row_blank.get("dirty_reasons") or {}).get("skill_level") or "") != "", row_blank`
  - L45 锚点 `assert "历史主操标记为空，系统已先按"否"处理。" == str((row_blank.get("dirty_reasons") or {}).get("is_primary") or ""), row_blank`
    → 改为 `assert str((row_blank.get("dirty_reasons") or {}).get("is_primary") or "") != "", row_blank`
- 净行数：0（4 改写，不增不减）。

### TRIM B：HTML 逐字整句 reason 文案 dump → 删除
- 类型：full_page_text（渲染页逐字中文整句）。
- 当前 L55-58，4 条 `assert "旧格式已自动修正：……。" in html, html`：
  ```
      assert "旧格式已自动修正：历史技能等级写法较旧，系统已先按能识别的中文选项处理。" in html, html
      assert "旧格式已自动修正：历史主操标记写法较旧，系统已先按“否”处理。" in html, html
      assert "旧格式已自动修正：历史技能等级为空，系统已先按“普通”处理。" in html, html
      assert "旧格式已自动修正：历史主操标记为空，系统已先按“否”处理。" in html, html
  ```
- 为什么脆：把服务层整句文案又在 HTML 里逐字断言一遍（双重快照），且前缀"旧格式已自动修正："+ 整句，文案任何润色即失败。"提示对用户可见"已由 L51-54（计数行 + 涉及字段 + 字段标签）结构性证明；服务层 reason 产生已由 TRIM A 的 key 非空证明。这 4 条是纯冗余渲染文案 dump。
- **删除指令**：删除 L55-58 这 4 行整句 HTML 断言（连续 4 行，文件末尾）。删除后函数仍以 L51-54 的结构 HTML 断言收尾，非空函数。
- 净删：4 行。

### 风险
mid。dirty_fields 集不变量、HTTP 200、计数提示行、字段标签全保留；服务层 reason 降为 key 非空；删冗余整句 HTML dump。契约"脏字段检测 + 对用户可见"的可证伪骨架完好。

---

## 文件 4 — tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py（当前 415 行，2 个测试函数）

函数 A：`test_process_excel_part_operation_hours_append_fill_empty_only`（L53-226）
函数 B：`test_process_excel_part_operation_hours_import`（L229-415）
TSV 理由：append 只补空工时 SKIP/UPDATE/ERROR + 原子拒绝 + DB 验 seq5 不变/seq10 补齐/seq20 external 不变；**剪逐字中文 preview-msg 子串（TSV 称 line 247-258，已过时）**。

**registry**：无引用（grep 空，含 `..._import` 函数名也空）。

### KEEP（真契约，不动 —— 两个函数的核心都保留）
- 函数 A 的 DB 验证块 L194-224（seq5 保持 1.0/0.5、seq10 补齐 0.8/0.4、seq20 external 不变 + source 校验）—— **硬契约 KEEP**，这是"只补空工时"语义的最终落库证明。
- 函数 A 的原子拒绝 L162 `if "导入被拒绝" not in html_mixed_confirm:` —— **KEEP**，"含 error 行→整批拒绝"是原子性契约（短稳定片段，非整句）。
- 函数 A 页面隐藏 replace L118-121（`value="replace"` 不应出现 / `只补空工时` 应出现）—— **KEEP**：`value="replace"` 是结构开关不变量；`只补空工时` 是短语义片段。属业务开关契约，保留。
- 函数 A 短稳定错误片段 L142 `"仅支持内部工序导入工时"`、L144 `"工序不存在"` —— **KEEP**：短、稳定、即错误分类语义本身（external→ERROR / 不存在→ERROR）。
- 函数 B 整体 **KEEP**：其 preview 断言（L285 `仅支持内部工序导入工时`、L298/L329 `必须是有限数字`、L316/L347 `导入被拒绝`）都是**短的错误分类关键短语**，且各自配有 DB 不变更/更新成功的独立证明（L351-362、L390-414）。这些不是整句 UI 文案快照，属错误分类契约，**不剪**。

### TRIM：函数 A 两条超长中文整句 preview 子串 → 收窄为稳定关键片段
- 类型：exact_chinese_snapshot（preview 页超长整句）。
- 当前 L138、L140：
  - L138 `if "已存在，选择"只补空工时"时会跳过" not in html_mixed:` —— 超长整句，含 UI 文案"选择"只补空工时"时"。真信号是"已维护行被判为 SKIP（会跳过）"。
  - L140 `if "工时为空，选择"只补空工时"时会补齐" not in html_mixed:` —— 同上，真信号是"空工时行被判为补齐（会补齐）"。
- 为什么脆：钉死整句 UI 措辞，文案润色即误失败；而 SKIP/UPDATE 分类的**最终效果**已由 DB 验证块（seq5 不变 / seq10 补齐）独立证明。保留分类的 preview 可见性即可，无需整句。
- **改写指令**（把整句子串换成稳定关键片段，保留 RuntimeError 报错语义）：
  - L138 锚点 `if "已存在，选择“只补空工时”时会跳过" not in html_mixed:`
    → 改为 `if "会跳过" not in html_mixed:`
  - L140 锚点 `if "工时为空，选择“只补空工时”时会补齐" not in html_mixed:`
    → 改为 `if "会补齐" not in html_mixed:`
  - 其下 `raise RuntimeError(...)` 两行原样保留（描述文案可不动）。
- 净删：0（2 处收窄改写，不增不减）。

### 风险
mid（实际偏 low）。仅收窄函数 A 两条整句 preview 子串；SKIP/UPDATE/ERROR 分类与原子拒绝均由 DB 验证 + 短稳定片段双重保住。函数 B 完全不动。无 registry 耦合。

---

## 文件 5 — tests/regression_process_reparse_part_surfaces_warning_text.py（当前 77 行）

单测试函数：`test_process_reparse_part_surfaces_warning_text`
TSV 理由：reparse 建 1 op + surfaces warning 分类是真的，但 line 63-67（已过时）钉死逐字中文 flash 整句；剪文案，保 op-count + category。

**registry**：无引用（grep 空）。

### KEEP（真契约，不动）
- L50-59 建 app + POST reparse —— 真路径。
- L61 `assert resp.status_code in (301, 302)` —— 重定向契约 **KEEP**。
- L62-63 取 `_flashes` —— 取数据，保留。
- L71-75 DB op-count：`assert row is not None and int(row["cnt"] or 0) == 1` —— **硬契约 KEEP**（reparse 写入恰 1 道工序）。
- flash 的 **category 维度**（`cat == "success"` / `cat == "warning"`）—— **KEEP**，契约明确要求"既 flash success 又 flash warning"。

### TRIM：两条 flash 整句逐字子串 → 收窄为稳定关键片段（保 category + 语义）
- 类型：exact_chinese_snapshot（flash 整句 UI 文案）。
- 当前 L65-69，`any(...)` 内的整句子串：
  - L65 `assert any(cat == "success" and "工艺路线解析完成：共 1 道工序" in msg for cat, msg in flashes), flashes`
  - L66-69 warning：`assert any(cat == "warning" and "工种"表处理"没有找到可用的外协供应商，本次会先按 1 天安排。建议补好供应商和周期。" in msg for cat, msg in flashes), flashes`
- 为什么脆：success 句"工艺路线解析完成：共 1 道工序"与 warning 整句都是完整 UI 文案，措辞/标点润色即误失败。真信号是"有 success 类 flash 且提示解析完成"与"有 warning 类 flash 且提示无外协供应商"。op-count=1 已由 DB（L71-75）独立证明，无需 success 句里再断言"共 1 道工序"的字面。
- **改写指令**（保 category + 收窄到稳定语义片段）：
  - L65 锚点 `assert any(cat == "success" and "工艺路线解析完成：共 1 道工序" in msg for cat, msg in flashes), flashes`
    → 改为 `assert any(cat == "success" and "解析完成" in msg for cat, msg in flashes), flashes`
  - L66-69 锚点（多行 `any(...)`）：
    ```
        assert any(
            cat == "warning" and "工种“表处理”没有找到可用的外协供应商，本次会先按 1 天安排。建议补好供应商和周期。" in msg
            for cat, msg in flashes
        ), flashes
    ```
    → 把内部整句子串换成稳定语义片段 `"没有找到可用的外协供应商"`，即：
    ```
        assert any(
            cat == "warning" and "没有找到可用的外协供应商" in msg
            for cat, msg in flashes
        ), flashes
    ```
- 净删：0（2 处收窄改写，不增不减）。

### 风险
mid（实际偏 low）。success/warning 两个 category 维度 + 各自语义片段 + op-count=1 全保留；仅去掉两条整句 UI 文案的字面脆性。

---

## 批次净删估算
- 文件 1：约 8 行净删（Excel openpyxl 值快照块）。
- 文件 2：0（不剪）。
- 文件 3：4 行净删（HTML 整句 reason dump）+ 4 处服务层整句→key 非空改写（0 行）。
- 文件 4：0（2 处整句子串收窄改写）。
- 文件 5：0（2 处整句子串收窄改写）。
- **批次净删合计 ≈ 12 行**；另含 8 处"整句→稳定片段"收窄改写（不改变行数但去脆性）。
- 无整函数删除，无文件删除，无 registry 引用悬空。
