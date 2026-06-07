# P5.1 MERGE spec — 簇 excel_import_apply_defense（干净簇：无 registry / 无 B-pin）

侦察员只读分析，本文件是合并执行的唯一输入。铁律：合并后断言条数 >= 合并前各文件之和；去重仅限逐字完全重复的同义断言，语义/边界/坏值不同的一律保留。

---

## ① 成员文件（各行数 / test_defs / assert 行）

| 文件 | 行数 | test_defs | assert 行 | 被测 service | 入口签名形态 |
|---|---|---|---|---|---|
| tests/test_machine_excel_import_apply_defense.py | 262 | 6 | 29 | `MachineExcelImportService` | A 型 `apply_preview_rows(rows, *, mode, existing_ids)` |
| tests/test_op_type_excel_import_apply_defense.py | 118 | 3 | 12 | `OpTypeExcelImportService` | A 型 |
| tests/test_operator_excel_import_normalization.py | 195 | 3 | 28 | `OperatorExcelImportService` | A 型 |
| tests/test_supplier_excel_import_remark_normalization.py | 159 | 4 (内含 1 个 parametrize=2 用例) | 33 | `SupplierExcelImportService` | A 型 |
| tests/test_part_operation_hours_import_apply_defense.py | 54 | 2 | 12 | `PartOperationHoursExcelImportService` | **B 型** `apply_preview_rows(rows)`（无 mode/existing_ids） |
| tests/test_part_operation_hours_import_apply_mixed_rows.py | 129 | 2 | 10 | `PartOperationHoursExcelImportService` | **B 型** |
| **合计** | **917** | **20 defs（21 收集用例：supplier parametrize 2 个 id_column）** | **124** | | |

---

## ② 目标合并文件名 + 命名理由

**目标文件：`tests/test_excel_import_apply_defense.py`**

理由：
- 6 个成员的公共语义是「各实体 Excel 导入的 `apply_preview_rows` 防御/规范化」，去掉实体前缀后正是 `excel_import_apply_defense`，与簇名一致、自解释。
- 注意区别既有的 `tests/test_excel_import_hardening.py`（在 `tools/test_registry_data.py:224` 登记为必跑，**不属于本簇、不可覆盖、不可改名**）。本目标文件用 `apply_defense` 而非 `hardening`，无命名冲撞，已 grep 核实仓库无同名文件。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

> 坏值/边界/None/异常断言用 **★** 标记，这些是各实体特有、合并后必须各自保留、不得参数化压平。

### machine（6 defs / 29 assert）— A 型，**ValidationError 整体回滚**语义
1. `test_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes`（5 assert）★
   - 坏值：第二行 `"状态": "BAD"`；`pytest.raises(ValidationError, match="状态不合法")`
   - `exc_info.value.message == "状态不合法，可填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"`（逐字）
   - `exc_info.value.field == "状态"`
   - `_count_machines(conn) == 0`（**整体回滚**：第一行合法也未写入）
2. `test_apply_preview_rows_missing_name_raises_validation_error`（3 assert）★
   - 坏值：`"设备名称": ""`；`match="设备名称不能为空"`
   - `message == "设备名称不能为空"`；`field == "设备名称"`；`_count_machines == 0`
3. `test_apply_preview_rows_missing_status_raises_specific_message`（3 assert）★
   - 坏值：`"状态": ""`；`match="状态不能为空"`
   - `message == "状态不能为空，请填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"`（逐字）
   - `field == "状态"`；`_count_machines == 0`
4. `test_apply_preview_rows_valid_rows_commit_and_trim_fields`（8 assert）★（trim 边界）
   - 入参带前后空格：`"设备编号": " MC001 "`, `"设备名称": " CNC-01 "`, `"状态": "可用"`
   - stats: total=1 / new=1 / error=0
   - 写库结果 trim：`machine_id=="MC001"`, `name=="CNC-01"`, `op_type_id is None`, `status=="active"`（中文「可用」→ "active"）
5. `test_apply_preview_rows_update_without_team_column_preserves_existing_team_id`（5 assert）★（缺列保留语义）
   - 预置 `team_id="TEAM-01"`，UPDATE 行不带「班组」列 → `team_id` 保留 "TEAM-01"；`name=="CNC-01-更新"`, `status=="active"`, update_count==1
6. `test_apply_preview_rows_team_accepts_id_or_name_and_blank_clears`（6 assert）★（班组 id/名称/空清空三态）
   - 班组传 ID "TEAM-01" → team_id=="TEAM-01"
   - 班组传名称 "车工二组" → team_id=="TEAM-02"
   - 班组传 "" → **team_id is None**（显式清空）

### op_type（3 defs / 12 assert）— A 型，**行级错误不回滚**语义
1. `test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors`（4 assert）★（混合行 + category 映射）
   - 坏值：`"归属": "BAD"`（行2）+ `"工种名称": ""`（行3）
   - stats: total=3 / new=1 / error=2（**坏行不阻断合法行**）
   - `[(r["op_type_id"], r["name"], r["category"]) for r in rows] == [("OT001", "数车", "internal")]`（"内部"→"internal"）
2. `test_apply_preview_rows_rejects_duplicate_name_on_create`（4 assert）★（建库重名）
   - 预置 OT001 名"数车"，新建 OT002 同名"数车" → new_count==0, error_count==1
   - `"工种名称“数车”已存在" in ...errors_sample[0].message`（逐字含中文引号 “ ”）
   - 库内仍只有 `[("OT001", "数车")]`
3. `test_apply_preview_rows_rejects_duplicate_name_on_update`（4 assert）★（更新重名）
   - 预置 OT001"数车"/OT002"数铣"，UPDATE OT002 改名为"数车" → update_count==0, error_count==1
   - 同上重名消息逐字；库内 `[("OT001","数车"),("OT002","数铣")]` 不变

### operator（3 defs / 28 assert）— A 型，规范化 + 班组 + **备注 normalize**
1. `test_operator_excel_import_strips_name_and_normalizes_remark`（12 assert）★（strip + 状态归一 + 备注空白→None）
   - 行1：`"工号":" OP001 "`,`"姓名":"  张三  "`,`"状态":"Active"`,`"备注":"  示例备注  "` → operator_id=="OP001", name=="张三", status=="active", **remark=="示例备注"**
   - 行2：`"状态":"INACTIVE"`,`"备注":"   "`（全空白）→ status=="inactive", **remark is None**
   - stats total=2/new=2/error=0
2. `test_operator_excel_import_update_without_team_column_preserves_existing_team_id`（6 assert）★（缺列保留 team + 备注更新）
   - 预置 team_id="TEAM-01"+remark"旧备注"，UPDATE 不带班组列、备注"新备注" → team_id 保留"TEAM-01", remark=="新备注", name=="张三-更新"
3. `test_operator_excel_import_team_accepts_id_or_name_and_blank_clears`（10 assert）★（班组三态 + 备注随行变）
   - 班组 ID "TEAM-01" + 备注"首次导入" → team_id=="TEAM-01", remark=="首次导入"
   - 班组名"车工二组" + 备注"按名称切换" → team_id=="TEAM-02", remark=="按名称切换"
   - 班组 "" + 备注"显式清空" → **team_id is None**, remark=="显式清空"

### supplier（4 defs / 33 assert，含 1 个 parametrize）— A 型，**零值 id + 备注 normalize + 缺列保留 + 空周期拒绝**
1. `test_supplier_excel_import_does_not_treat_zero_id_as_blank`（parametrize `id_column ∈ {"供应商编号","供应商ID"}`，每参 3 assert）★★（0 不当空 + 双列名兼容）
   - 入参 `{id_column: 0, "名称":"零号供应商", ...}`（**整数 0**）
   - `dict(row) == {"supplier_id": "0", "name": "零号供应商"}`（0 → "0" 而非视为空）
   - `stats["new_count"]==1`, `stats["error_count"]==0`
2. `test_supplier_excel_import_normalizes_remark_text`（14 assert）★（strip + status None/“启用”→active + 备注空白→None + default_days float）
   - 行1：`"供应商ID":" S001 "`,`"名称":" 外协-标印厂 "`,`"默认周期":2`,`"状态":None`,`"备注":"  abc  "` → supplier_id=="S001", name=="外协-标印厂", default_days==2.0, **status=="active"（None→active）**, remark=="abc"
   - 行2：`"默认周期":1.0`,`"状态":"启用"`,`"备注":"   "` → status=="active"（中文"启用"→active）, **remark is None**
3. `test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing`（6 assert）★★（OVERWRITE 缺列保留 status+remark）— **本簇唯一在 OVERWRITE 模式下断言"缺列不清空旧值"的语义**
   - 预置 status="inactive"+remark="keep me"，UPDATE 行只给 名称/默认周期 → name=="新供应商", default_days==3.5, **status=="inactive"（保留）**, **remark=="keep me"（保留）**
4. `test_supplier_excel_import_rejects_blank_default_days`（5 assert）★（空周期 → 行级错误 + 不写库）
   - 坏值：`"默认周期":""` → new_count==0, error_count==1
   - `"默认周期" in errors_sample[0].message`
   - 库内 `COUNT WHERE supplier_id="S003" == 0`

### part_operation_hours — defense（2 defs / 12 assert）— **B 型**，`_parse_write_row` 静态 + NaN/Inf
1. `test_parse_write_row_accepts_integer_float_string_forms`（6 assert）★★（解析三态 + 坏值 "5e0"）— 直接调静态方法 `PartOperationHoursExcelImportService._parse_write_row`
   - 整数/浮点形：`{"图号":"P001","工序":5.0,"换型时间(h)":1.0,"单件工时(h)":0.25}` → err is None, `parsed == ("P001", 5, 1.0, 0.25)`
   - 字符串形：`{"工序":"5.0","换型时间(h)":"1.0","单件工时(h)":"0.25"}` → 同上 `("P001", 5, 1.0, 0.25)`
   - **坏值 `"工序":"5e0"`** → `parsed is None`, `err is not None`
2. `test_apply_preview_rows_turns_nan_inf_into_row_errors`（6 assert）★★（NaN/Inf/"abc" → 行级错误）— 用空 `:memory:` **裸连接**，不建 schema
   - 坏值：`float("nan")` / `float("inf")` / `"abc"`
   - stats: total=3 / new=0 / update=0 / skip=0 / error=3
   - `len(errors_sample) >= 1`

### part_operation_hours — mixed_rows（2 defs / 10 assert）— **B 型**，需 seed Part+PartOperation + **monkeypatch 回滚**
1. `test_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors`（6 assert）★（混合：合法/业务错(工序999)/解析错(nan)）
   - 需 `_seed_part_and_internal_op`（插 Parts P001 + PartOperations seq=1 internal）
   - stats: total=3 / new=0 / update=1 / skip=0 / error=2
   - `_get_hours(P001, seq=1) == (2.0, 1.0)`（合法行写入、行级错误不回滚合法行）
2. `test_apply_preview_rows_unexpected_exception_rolls_back_all_changes`（4 assert，**用 monkeypatch fixture**）★★（外层事务回滚）
   - **monkeypatch `svc.part_svc.update_internal_hours`**：第 2 次调用 `raise RuntimeError("boom")`
   - `pytest.raises(RuntimeError)`
   - 回滚后 `_get_hours(P001,1) == (sh0, uh0)`（第一行成功写入也被撤销）

---

## ④ 共享 setup → 建议 fixture（复用 conftest / 缺口）

各文件本地重复定义了大量 helper，合并后统一收口：

| 本地 helper | 出现文件 | 合并后处置 |
|---|---|---|
| `REPO_ROOT` + `_load_schema(conn)` | machine/op_type/operator/supplier/part_mixed（5 处逐字重复） | **复用 conftest `schema_conn`**（已是 `:memory:` + FK ON + Row + 全量 schema.sql + commit，行为完全一致）。删掉本地 `_load_schema`/`REPO_ROOT`。 |
| `conn = sqlite3.connect(":memory:")` + `row_factory=Row` + `PRAGMA FK ON` + `_load_schema` 的 try/finally close 样板 | 上述 5 文件每个 test 内重复 | 改用 `schema_conn` fixture（teardown 自动 close）。 |
| part_defense 的 **空裸连接** `sqlite3.connect(":memory:")`（**不建 schema**，NaN/Inf 在解析层就拦截、不碰库） | part_defense `test_apply...nan_inf` | **复用 conftest `mem_conn`**（空 :memory: + FK ON + Row，不建表，行为一致）。注意：不能用 `schema_conn`，会偏离"无表也能拦坏值"的原意——但用 mem_conn（带 FK/Row）与原裸连接（无 FK/无 Row）的差异**不影响断言**（该用例只读 stats、不查库），可安全替换；保守起见也可保留裸连接。**建议用 `mem_conn`**。 |
| `_pr(data, *, status, row_num)` 工厂 | 全 6 文件（默认 status 不同：A 型默认 `RowStatus.NEW`，part 两文件默认 `RowStatus.UPDATE`） | 合并文件内保留**单个** `_pr`，默认 `status=RowStatus.NEW`；part 用例显式传 `status=RowStatus.UPDATE`（原 part 文件靠默认值，合并后改为显式传参，行为不变）。 |
| `_count_machines(conn)` | machine | 保留（仅 machine 用，可内联或留模块级 helper） |
| `_insert_team(conn, team_id, name)` | machine + operator（逐字重复） | 合并文件内保留**单个** `_insert_team`。 |
| `_seed_part_and_internal_op(conn)` / `_get_hours(conn,*,part_no,seq)` | part_mixed | 保留（仅 part 用例用） |

**缺口**：conftest 无「插 ResourceTeams / 插 Parts+PartOperations seed」的共享 fixture，但这些是实体特有 seed，**不建议**上提到 conftest（只两处用），留作合并文件内的模块级 helper 即可。

---

## ⑤ 参数化方案

**核心判断：本簇被测函数非完全同构，不可整簇压成单一 parametrize。** 分两层处理。

### B 型（part_operation_hours）—— 不参数化，独立保留
入口签名 `apply_preview_rows(rows)` 无 `mode`/`existing_ids`，且有 `_parse_write_row` 静态调用、NaN/Inf 坏值、`part_svc.update_internal_hours` monkeypatch 路径、seed 依赖。与 A 型异构。**4 个 test 函数原样迁入合并文件，函数名加 `part_op_hours_` 前缀去重命名**（原文件无前缀，合并后同文件需防撞名；machine 的 `test_apply_preview_rows_valid_rows...` 等也要加实体前缀，见下）。

### A 型（machine/op_type/operator/supplier）—— 谨慎参数化
A 型 4 实体共享调用形态 `svc.apply_preview_rows(rows, mode=ImportMode.OVERWRITE, existing_ids=...)`，但**断言主体差异极大**（不同列名/不同 service 类/不同坏值消息/不同回滚语义），强行 parametrize 会把断言塞进 if-else 分支、损可读性且违反"差异收进 parametrize 维度"的初衷。

**建议方案（保真优先）**：
- A 型不做跨实体大参数化。各实体的 test 函数原样迁入，函数名加实体前缀消除撞名（如 `test_machine_apply_invalid_status_rolls_back`、`test_op_type_apply_commits_valid_keeps_errors`、`test_operator_strips_name_normalizes_remark`、`test_supplier_zero_id_not_blank` 等）。
- **唯一可安全收进 parametrize 的维度**：supplier 已有的 `id_column ∈ {"供应商编号","供应商ID"}` parametrize **原样保留**（这是真同构差异，已是 parametrize）。
- 可选的轻量 parametrize（不强制，执行者酌情）：machine 的两条"缺名/缺状态"异常用例结构高度相似，可合成 `@pytest.mark.parametrize` 三元组 `(坏值字段, match, 期望 message, 期望 field)`——但 message 逐字不同，收益有限，**默认不做**，保留为独立函数更稳。

**结论：本簇以"统一 fixture + 去重 helper + 实体前缀命名"为主要收益，parametrize 仅保留 supplier 既有的 1 处。** 这是行为保真下的正确取舍——合并价值在消除 5 份重复的 schema/_pr/connect 样板，而非压平异构断言。

---

## ⑥ load-bearing import / importlib 引用（删原文件会断吗？）

已 grep 全仓（`*.py/*.json/*.txt/*.cfg/*.ini/*.toml`）：**6 个测试模块名仅在 `.codestable/refactors/2026-06-01-test-gate-cleanup/summary.json:35-40` 被列为字符串清单**，无任何 Python 代码 `import`/`importlib.import_module` 引用这些测试模块（测试模块本就不该被 import）。

- 删除 6 个原文件 **不会断任何代码**。
- summary.json 的引用是本次 refactor 的计划数据，合并完成后由执行者按 refactor 流程更新（非 spec 范围）。

被测 service 的 import 路径（合并文件需保留这些 import，确认均存在）：
- `from core.services.equipment.machine_excel_import_service import MachineExcelImportService`
- `from core.services.process.op_type_excel_import_service import OpTypeExcelImportService`
- `from core.services.personnel.operator_excel_import_service import OperatorExcelImportService`
- `from core.services.process.supplier_excel_import_service import SupplierExcelImportService`
- `from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService`
- `from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus`
- `from core.infrastructure.errors import ValidationError`（仅 machine 用）

---

## ⑦ registry 影响（tools/test_registry_data.py）

**无。**

精确 grep `tools/test_registry_data.py`：6 个成员文件**均不在 registry 必跑清单**。唯一相关命中是 `tests/test_excel_import_hardening.py`（第 224 行）——那是**另一个文件、不属于本簇**，且本目标文件名 `test_excel_import_apply_defense.py` 与它不冲突，不需改动 registry。

旧→新条目：**无**。

---

## ⑧ B-COMPAT pin（必须逐字保留禁去重的断言）

**无。** 本簇为干净簇：6 文件内无任何 `B-COMPAT`/`B-pin`/`禁去重` 标记（grep 命中的两处 "keep me" 是 supplier 测试的备注数据值，非 pin 标记）。

> 注：虽无 B-pin，仍提醒执行者——以下中文逐字消息属"语义不可改"断言，必须逐字保留（它们是不同实体/不同坏值，本就不是重复，不在去重范围）：machine 的两条状态长消息、op_type 的「工种名称“数车”已存在」（含中文引号）、supplier 的零值 id `"0"`、各 remark 空白→None 语义。

---

## ⑨ 断言条数对账（前总和 → 后预期）

**合并前各文件 assert 行总和 = 29 + 12 + 28 + 33 + 12 + 10 = 124 条。**

**合并后预期 >= 124 条（铁律：保真不减）。**

逐项核对去重情况：
- 各 test 函数体内的断言**一条不删**（无逐字完全重复的同义断言可去——124 条断言分布在 21 个独立用例，针对不同实体/不同列/不同坏值，无一对完全重复）。
- 唯一被"合并"的是**非断言的 setup helper**（`_load_schema`/`_pr`/`connect` 样板/`_insert_team`），这些不计入断言数。
- supplier 的 parametrize 用例（2 个 id_column）合并后保持参数化，断言数不变。

**预期合并后 assert 行 = 124（持平，不减）。** 若执行者把 schema_conn fixture 化省去本地 `_load_schema` 调用，不影响 assert 计数。收集用例数：21（与合并前一致）。

---

## ⑩ 风险 / 阻塞点

1. **【主风险·非阻塞】被测函数异构，禁止整簇压平 parametrize。** part_operation_hours（B 型）签名无 mode/existing_ids，与 A 型 4 实体不同；A 型 4 实体的回滚语义也分两派（machine=ValidationError 整体回滚，op_type/operator/supplier=行级错误不回滚）。spec 已给出"分层处理、仅保留 supplier 既有 parametrize"的方案，执行者**不得**为减行数而合并异构断言。
2. **【命名撞车·需处理】** 多文件存在同名 test（如 machine 的 `test_apply_preview_rows_valid_rows_commit_and_trim_fields`、op_type 的 `test_apply_preview_rows_commits_valid_rows_and_keeps_row_errors`、part 两文件的 `test_apply_preview_rows_turns_nan_inf...` 与 `test_apply_preview_rows_mixed_rows...`）。合并进同一文件**必须加实体前缀**，否则后定义覆盖前定义、静默丢用例。这是合并最大的"静默掉测"陷阱。
3. **【fixture 替换边界·需确认】** part_defense 的 NaN/Inf 用例原用**裸 `:memory:` 连接（无 FK、无 Row、不建 schema）**。建议改 `mem_conn`（带 FK ON + Row、仍不建表）——该用例只断言 stats、不查库，FK/Row 差异不影响结果，可安全替换；执行者若想零风险也可保留裸连接。**不可**误用 `schema_conn`（会建表，偏离"无表也拦坏值"原意，虽不影响本用例断言但语义漂移）。
4. **【part `_pr` 默认值变更·已说明】** part 两文件的 `_pr` 默认 `status=RowStatus.UPDATE`，合并后统一为默认 `NEW`，part 用例需显式传 `status=RowStatus.UPDATE`。执行者须逐个 part 用例核对其 `_pr` 调用是否依赖了 UPDATE 默认（mixed_rows 的合法写库行依赖 UPDATE 语义命中已存在 PartOperation）。**这是行为相关的默认值，迁移时必须显式补 `status=RowStatus.UPDATE`。**
5. **【无 registry / 无 B-pin·低风险】** 不改 test_registry_data.py，不触碰必跑清单，无逐字 pin 约束，合并自由度高。
