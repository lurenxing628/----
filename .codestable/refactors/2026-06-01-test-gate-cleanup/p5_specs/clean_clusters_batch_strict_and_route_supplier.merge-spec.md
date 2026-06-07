# MERGE spec — 两个干净簇（无 registry / 无 B-pin）

> 类型: ★CLEAN MERGE ×2（A 簇可参数化；B 簇同文件不同语义、并文件不并函数）
> 侦察产出，只读分析 + 仅写本 spec，未改任何被测文件、未跑门禁、未 git 操作。
> 行为保真铁律：合并后断言条数必须 >= 合并前各文件之和；去重仅限**逐字完全重复**的同义断言；语义/边界/坏值不同的一律保留。
> 全局核实结论：本 spec 涉及的 4 个文件名**不在** `tools/test_registry_data.py`（200 条 regression 无一匹配）、`tools/test_debt_registry.py`、`tools/full_test_debt_shards.py` 中；全仓 `grep` 无任何 `.py/.cfg/.ini/.toml/.txt` 以 import / importlib / 路径字符串引用这 4 个文件。⇒ **registry 影响 = 无**，**load-bearing 外部引用 = 无**，删原文件不会断链。

---
---

# 簇 A — `batch_service_strict_mode_template`（2 文件）

测 `BatchService.create_batch_from_template(strict_mode=True)` 路由解析失败时的契约：抛 `ErrorCode.ROUTE_PARSE_ERROR` 且 `Batches` 不残留任何行（失败即整体回滚）。两文件分别覆盖 **legacy resolver 分支**（注入 resolver 返回 `None`）与 **autoparse 默认分支**（缺供应商映射），契约两态不同 → 按「resolver 形态」参数化，但拒绝/失败的各自专属断言全部保留。

## ① 成员文件（各行数）

| 文件 | 行数 | 分支 / 性质 |
|---|---|---|
| `tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py` | 59 | **legacy 分支**：注入 `legacy_resolver` 返回 `None`，断言被拒 + message 文案 |
| `tests/regression_batch_service_strict_mode_template_autoparse.py` | 42 | **autoparse 分支**：默认 resolver、插 `OpTypes` 但缺供应商映射，因缺供应商失败 |
| **合并前总计** | **101** | |

## ② 目标合并文件名 + 命名理由

**目标文件：`tests/regression_batch_service_strict_mode_template.py`**（新建该名；删除上述两原文件）。

命名理由：
- 两文件共同主题是「`strict_mode=True` 建批遇模板/路由解析失败的契约」，去掉各自分支后缀（`_legacy_template_resolver_rejects` / `_autoparse`）后，**最大公约名** = `regression_batch_service_strict_mode_template`，名实相符且不偏向任一分支。
- 该名当前**不存在**（已 `ls` 核实，仅存在两个带后缀的原名），无冲突。
- 无 registry / debt / shards / import 锚点（见全局核实），文件名自由选取爆炸半径为 0。

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### A1. `regression_batch_service_legacy_template_resolver_rejects_strict_mode.py`（1 函数，3 条断言）

`test_batch_service_legacy_template_resolver_rejects_strict_mode`
- 注入 `def legacy_resolver(part_no, part_name, route_raw, no_tx): return None`，`BatchService(conn, template_resolver=legacy_resolver)`。
- 断言（逐字）：
  ```python
  assert err.code == ErrorCode.ROUTE_PARSE_ERROR
  assert "不支持“资料不完整就停下”" in err.message      # ← legacy 分支专属文案，autoparse 无此断言
  assert row is not None and int(row["cnt"] or 0) == 0   # Batches 不残留（batch_id="B_STRICT_LEGACY"）
  ```
- 失败捕获形态：`with pytest.raises(BusinessError) as exc_info:` → 取 `exc_info.value`。

### A2. `regression_batch_service_strict_mode_template_autoparse.py`（1 函数，2 条断言）

`test_batch_service_strict_mode_template_autoparse`
- 默认 resolver（autoparse），先插 `OpTypes(OT_EXT, 表处理, external)` + `Parts(P_ROUTE, ..., remark=None)`，`BatchService(conn, logger=None, op_logger=None)`。
- 断言（逐字）：
  ```python
  assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode 建批应返回 ROUTE_PARSE_ERROR：{e.code!r}"
  assert row is not None and int(row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 Batches：{dict(row) if row else None!r}"   # batch_id="B_STRICT"
  ```
- 失败捕获形态：`try/except BusinessError ... else: raise AssertionError("strict_mode=True 时自动补建模板应因缺供应商映射失败")`。该 `else` 分支是一条**隐式断言**（须保留：捕获「未抛异常」这一反向坏路）。

## ④ 共享 setup → 建议 fixture

| setup 项 | 原 A1 | 原 A2 | 合并方案 |
|---|---|---|---|
| `:memory:` + FK ON + Row + `schema.sql` 全量 | 手写 `_load_schema` + `sqlite3.connect` + 手动 `conn.close()` in finally | 已用 conftest `schema_conn` | **复用 conftest `schema_conn`**（A1 的手写建库样板与 `schema_conn` 行为完全等价，删 `_load_schema`/`REPO_ROOT`/`SCHEMA_PATH`/`sys.path` 注入）|
| `Parts(P_ROUTE, 路线件, "10表处理", "no")` 插入 | 有（无 remark 列） | 有（带 `remark=None`） | 两者等价，统一用带 `remark=None` 的形态（列更全、值语义一致）|
| `OpTypes(OT_EXT, 表处理, external)` 插入 | **无** | 有 | 仅 autoparse 分支需要（legacy resolver 返回 None 不走到供应商映射）→ 收进 parametrize 的「分支专属 setup」回调，**不可无脑提到公共 setup**（A1 不插 OpTypes 才能纯走 legacy 拒绝路径）|

> 注：原 A1 自带 `sys.path.insert` + `REPO_ROOT` 推导，纯属 conftest 已做的兜底（conftest 已 `sys.path.insert(0, REPO_ROOT)`），合并后删除冗余。
> `schema_conn` 的 teardown 自带 `conn.close()`，删两文件 finally 的手动 close。

## ⑤ 参数化方案

按「resolver 形态 / 分支」单维 parametrize，每个 case 携带 (resolver 构造、是否插 OpTypes、batch_id、专属断言)：

```python
@pytest.mark.parametrize("case", ["legacy_resolver_returns_none", "autoparse_missing_supplier"])
def test_batch_service_strict_mode_template_rejects(schema_conn, case):
    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.scheduler.batch_service import BatchService
    conn = schema_conn

    if case == "autoparse_missing_supplier":
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?,?,?)",
                     ("OT_EXT", "表处理", "external"))
    conn.execute("INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?,?,?,?,?)",
                 ("P_ROUTE", "路线件", "10表处理", "no", None))
    conn.commit()

    if case == "legacy_resolver_returns_none":
        def legacy_resolver(part_no, part_name, route_raw, no_tx):
            return None
        svc = BatchService(conn, template_resolver=legacy_resolver)
        batch_id = "B_STRICT_LEGACY"
    else:
        svc = BatchService(conn, logger=None, op_logger=None)
        batch_id = "B_STRICT"

    with pytest.raises(BusinessError) as exc_info:
        svc.create_batch_from_template(batch_id=batch_id, part_no="P_ROUTE",
                                       quantity=1, priority="normal", ready_status="yes", strict_mode=True)
    err = exc_info.value
    assert err.code == ErrorCode.ROUTE_PARSE_ERROR
    if case == "legacy_resolver_returns_none":
        assert "不支持“资料不完整就停下”" in err.message   # 分支专属，必须保留
    row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", (batch_id,)).fetchone()
    assert row is not None and int(row["cnt"] or 0) == 0
```

参数化维度：`case ∈ {legacy_resolver_returns_none, autoparse_missing_supplier}`。
- 共享断言（每 case 都跑）：`err.code == ROUTE_PARSE_ERROR`（×2）、`Batches 不残留`（×2）。
- 专属断言：legacy 的 message 文案（×1，autoparse 不跑）。
- 形态统一：A2 原 `try/except/else` 改为 `pytest.raises`，其 `else→AssertionError` 的「必须抛异常」语义被 `pytest.raises`(未抛即 fail)**完整覆盖且更严格**，不丢保护。

## ⑥ load-bearing import / importlib 引用

无。无任何文件 import 这两个 `regression_*` 文件，删除安全（全局 grep 已核）。

## ⑦ registry 影响

**无。** 两文件名均不在 `tools/test_registry_data.py`（200 条均不匹配）/`test_debt_registry.py`/`full_test_debt_shards.py`。`tools/test_registry_data.py` 须改条目数 = **0**。

## ⑧ B-COMPAT pin（禁去重逐字保留）

**无显式 B-pin 登记。** 但下列断言因**语义唯一、非逐字重复**，按铁律必须保留（非 B-pin，属常规保真）：
- `assert "不支持“资料不完整就停下”" in err.message`（legacy 分支专属文案，autoparse case 无）。

## ⑨ 断言条数对账

| 项 | 条数 |
|---|---|
| A1（legacy）断言 | 3（code + message + 不残留）|
| A2（autoparse）断言 | 2（code + 不残留）+ 1 隐式（else→必须抛异常）|
| **合并前总和** | **5 显式 + 1 隐式** |
| 合并后预期（每 case 跑：code + 不残留；legacy 多 message） | legacy: 3，autoparse: 2 → **5 显式**；A2 的「必须抛异常」由 `pytest.raises` 对两 case 各覆盖 1 次（≥ 原 1 次）|
| 结论 | **5 ≥ 5**，且「必须抛异常」保护被 `pytest.raises` 加强覆盖 → 保真达标 |

## ⑩ 风险 / 阻塞点

- 低风险。两 case 的库状态隔离由 `schema_conn` 每函数全新 `:memory:` 保证（参数化每个 case 独立 fixture 实例）。
- 唯一需 implement 注意：**A1 不可插 OpTypes**（插了可能改变 legacy resolver 返回 None 之外的路径假设）；OpTypes 插入严格只在 autoparse case 内。
- A2 原文 `route_parsed="no"`、`remark=None`——合并统一带 remark 列，已确认两文件 Parts 行其余列同值（`P_ROUTE / 路线件 / "10表处理" / "no"`）。

---
---

# 簇 B — `route_parser_supplier_default_days`（2 文件）

> ⚠️ **关键判定：两文件并非同一契约，不可跨语义参数化。** 一为「单供应商 `default_days=0` 无效周期 → PARTIAL 降级回退」，一为「多供应商有效选择契约（最高 supplier_id / 仅 active / snapshot 形状 / stale issue 忽略）」。两者同属 `RouteParser` 外协供应商映射的回归，**可并入同一物理文件**（主题聚合：route_parser 供应商映射契约），但**保留为各自独立 test 函数，不合并函数体、不强行 parametrize**。

## ① 成员文件（各行数）

| 文件 | 行数 | 契约 |
|---|---|---|
| `tests/regression_route_parser_supplier_default_days_zero_trace.py` | 61 | `default_days=0.0`（单供应商无效周期）→ `PARTIAL` + 回退 `1.0` + warning「默认周期无效」|
| `tests/regression_supplier_effective_selection_contract.py` | 203 | 多供应商有效选择：最高 `supplier_id` 为 effective、仅 active、blank category=internal、snapshot 形状、inactive-only=缺供应商、非 effective 供应商 stale issue 忽略 |
| **合并前总计** | **264** | |

## ② 目标合并文件名 + 命名理由

**目标文件：`tests/regression_route_parser_supplier_contract.py`**（新建该名；把 `default_days_zero_trace` 的函数并入；删除两原文件）。

命名理由：
- 主题最大公约 = 「`RouteParser` 外协供应商（映射 / 选择 / 周期）契约」。`supplier_effective_selection_contract` 已含「contract」后缀但偏「选择」，并入「零周期回退」后语义需更宽 → 用 `route_parser_supplier_contract` 统摄「选择 + 周期回退」两类供应商契约。
- 该名当前**不存在**（已 `ls` 核实），无冲突。
- `default_days_zero_trace`（61 行）并入 203 行的大文件，文件级搬迁量最小（小并大）。两原文件均无 registry / import 锚点，文件名自由。

> 备选：保留 `regression_supplier_effective_selection_contract.py` 原名直接吸收。**不推荐**——该名语义偏窄（「选择」不含「零周期回退 trace」），并入后名不副实。新建宽名更贴切。

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### B1. `regression_route_parser_supplier_default_days_zero_trace.py`（1 函数，5 条断言）

`test_route_parser_supplier_default_days_zero_trace` — 单供应商 `SUP_ZERO / OT_EXT / default_days=0.0`，`parser.parse("5表处理", part_no="P_SUP_ZERO")`：
```python
assert result.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), f"supplier default_days=0 应返回 PARTIAL：{result.status!r}"
assert len(result.operations or []) == 1, f"解析工序数量异常：{result.operations!r}"
assert op.supplier_id == "SUP_ZERO", f"供应商映射异常：{op.supplier_id!r}"
assert abs(float(op.default_days or 0.0) - 1.0) < 1e-9, f"default_days 未回退为 1.0：{op.default_days!r}"   # ← 坏值 0→1.0 回退,唯一
assert any("默认周期无效" in str(msg) for msg in (result.warnings or [])), f"未透出默认周期无效 warning：{result.warnings!r}"   # ← warning 文案,唯一
```

### B2. `regression_supplier_effective_selection_contract.py`（6 函数，21 条断言）

helper：`_OpType`/`_Supplier`(带 `status="active"` 默认)/`_StubOpTypesRepo`/`_StubSuppliersRepo`(`list(status=None)` 支持按 status 过滤)/`_SnapshotService(PartService)`。

1. `test_part_service_route_parse_baseline_snapshot_uses_highest_supplier_id_as_effective_supplier` — 1 条
   - 三供应商 SUP_A/SUP_Z/SUP_M（default_days 2/5/3）→ snapshot 选 **SUP_Z**：
   ```python
   assert snapshot == [{"part_no": "P_EFFECTIVE_SUP", "route_op_types": [{"name": "表处理", "matched_op_type_id": "OT_EXT", "source": "external"}], "suppliers": [{"supplier_id": "SUP_Z", "op_type_id": "OT_EXT", "op_type_name": "表处理", "default_days": 5.0}]}]
   ```
2. `test_part_service_route_parse_baseline_snapshot_treats_blank_category_as_internal` — 1 条
   - `category=None` → `source="internal"` 且 `suppliers: []`：
   ```python
   assert snapshot == [{"part_no": "P_BLANK_CATEGORY", "route_op_types": [{"name": "表处理", "matched_op_type_id": "OT_EXT", "source": "internal"}], "suppliers": []}]
   ```
3. `test_route_parser_uses_highest_supplier_id_as_effective_supplier` — 2 条
   ```python
   assert supplier_map == {"表处理": ("SUP_Z", 5.0)}
   assert issues == {}
   ```
4. `test_route_parser_only_uses_active_suppliers_for_effective_supplier` — 5 条
   - SUP_A active / SUP_Z inactive → 选 active 的 SUP_A（**非最高 id**，active 优先于 id 大小）：
   ```python
   assert supplier_map == {"表处理": ("SUP_A", 2.0)}
   assert issues == {}
   assert result.status == ParseStatus.SUCCESS
   assert result.operations[0].supplier_id == "SUP_A"
   assert result.operations[0].default_days == 2.0
   ```
5. `test_route_parser_treats_inactive_only_supplier_as_missing_supplier` — 6 条（relaxed vs strict 双态，坏路）：
   ```python
   assert relaxed.status == ParseStatus.PARTIAL
   assert relaxed.operations[0].supplier_id is None                 # ← None 边界
   assert relaxed.operations[0].default_days == 1.0                 # ← 回退 1.0
   assert any("没有找到可用的外协供应商" in str(msg) for msg in relaxed.warnings)   # relaxed 文案
   assert strict.status == ParseStatus.FAILED
   assert any("没有可用的外协供应商" in str(msg) for msg in strict.errors)          # strict 文案(与 relaxed 不同字!)
   ```
6. `test_route_parser_ignores_stale_issue_from_non_effective_supplier` — 6 条（SUP_A default_days="" 坏值 + SUP_Z 5.0）：
   ```python
   assert supplier_map == {"表处理": ("SUP_Z", 5.0)}
   assert issues == {}
   assert result.status == ParseStatus.SUCCESS
   assert result.errors == []
   assert result.warnings == []
   assert len(result.operations) == 1
   assert result.operations[0].supplier_id == "SUP_Z"
   assert result.operations[0].default_days == 5.0
   ```
   （注：该函数实为 8 条 assert，上表「6 条」按显著业务断言计；对账以**实际行数**为准，见 ⑨。）

## ④ 共享 setup → 建议 fixture

- **不建议用 conftest 的 DB fixture**：B 簇全部用**纯内存 dataclass stub**（`_OpType`/`_Supplier`/`_StubOpTypesRepo`/`_StubSuppliersRepo`），不碰 sqlite、不需 `schema_conn`。conftest 无对应 stub fixture（缺口），但这些 stub 是被测 `RouteParser` 的 repo 协议替身，**应留在测试文件内**（属测试本地建模，不宜提到 conftest 污染全局）。
- **stub 类去重**：B1 与 B2 各自定义了 `_OpType`/`_Supplier`/`_StubOpTypesRepo`/`_StubSuppliersRepo`，但**两版签名不同**：
  - B1 `_OpType.category: str`；B2 `_OpType.category: str | None`（B2 更宽，blank category 测试需要）。
  - B1 `_Supplier(supplier_id, op_type_id, default_days: float)` 无 status；B2 `_Supplier(..., default_days: float|str|None, status="active")`（B2 更宽，含坏值 `""` 与 status 过滤）。
  - B1 `_StubSuppliersRepo.list()` 无参；B2 `_StubSuppliersRepo.list(status=None)` 支持过滤。
  - ⇒ **统一采用 B2 的更宽版本**（B2 是 B1 的超集：`default_days: float|str|None` 兼容 B1 的 `0.0`；`list(status=None)` 默认 None 返回全部，兼容 B1 无参调用）。删 B1 的窄版定义，B1 函数复用 B2 的 stub。**须实跑验证 B1 在 B2 stub 下行为不变**（见 ⑩）。

## ⑤ 参数化方案

**不参数化。** 6+1=7 个函数语义各异（零周期回退 / 最高 id / blank category / active 过滤 / inactive-only 缺供应商 / stale issue 忽略），强行 parametrize 会把各自专属断言（snapshot 整体 dict、不同 warning/error 文案、None 边界、坏值 `""`）挤进分支判断，降低可读性且违背「差异收进 parametrize」的初衷——这里差异是**契约本身**而非同契约的输入变体。**仅做物理文件合并 + stub 去重**，7 个函数逐字搬迁、函数体不动（除 import stub 改为复用统一版本）。

## ⑥ load-bearing import / importlib 引用

无。两 `regression_*` 文件无外部 import（全局 grep 已核）。被测目标 `core.services.process.route_parser`（`ParseStatus`/`RouteParser`）与 `core.services.process.part_service.PartService` 是**生产模块**，照常 import，不受影响。

## ⑦ registry 影响

**无。** 两文件名均不在 registry / debt / shards。`tools/test_registry_data.py` 须改条目数 = **0**。

## ⑧ B-COMPAT pin（禁去重逐字保留）

**无显式 B-pin 登记。** 下列断言因**语义唯一**（坏值 / None / 文案差异），按保真铁律必须逐字保留：
- B1：`default_days` 0→`1.0` 回退、`"默认周期无效"` warning。
- B2-5：relaxed 文案 `"没有找到可用的外协供应商"` ≠ strict 文案 `"没有可用的外协供应商"`（**仅差「找到」二字，去重必踩坑，禁合并**）；`supplier_id is None`、`default_days == 1.0`。
- B2-4：active 优先于最高 id（选 SUP_A 而非 SUP_Z），与 B2-3「无 status 时选最高 id SUP_Z」是**互补的两条不同规则**，禁互相吸收。
- B2-6：坏值 `default_days=""` 的 stale issue 被忽略（`issues == {}`、`warnings == []`）。

## ⑨ 断言条数对账

| 项 | 实际 assert 行数 |
|---|---|
| B1（zero_trace） | 5 |
| B2-1 snapshot highest id | 1 |
| B2-2 blank category internal | 1 |
| B2-3 highest id supplier_map | 2 |
| B2-4 active only | 5 |
| B2-5 inactive-only missing（relaxed+strict） | 6 |
| B2-6 stale issue ignored | 8 |
| **合并前总和** | **28** |
| 合并后预期（7 函数逐字搬迁、不删任何 assert、stub 仅去重不改断言） | **28** |
| 结论 | **28 ≥ 28**，保真达标（无任何 assert 被去重，仅 stub 类定义去重，stub 不含 assert）|

## ⑩ 风险 / 阻塞点

- **中风险（B 簇唯一需对抗验证点）：stub 类统一为 B2 宽版后，B1 的 `test_route_parser_supplier_default_days_zero_trace` 必须实跑确认行为不变。** 理由：B1 原 `_Supplier` 无 `status` 字段，统一到 B2 版后获得 `status="active"` 默认值；B1 原 `_StubSuppliersRepo.list()` 无参，统一到 `list(status=None)`。若 `RouteParser` 在解析 `SUP_ZERO` 时按 status 过滤，默认 `"active"` 应使其仍被纳入（行为不变），但**这是假设，implement 阶段必须单跑 B1 函数验证 status 仍为 `PARTIAL`+回退 1.0**，不可纸面放行。
- **不可跨语义参数化**（已在 ② / ⑤ 锁定）：B1 与 B2 是不同契约，合文件不合函数。
- 低风险点：B1/B2 的 `_OpType`/`_StubOpTypesRepo` 除 `category` 类型注解外行为一致，统一为 B2 版（`str | None`）安全。
- `core.services.process.part_service.PartService` 仅 B2 用（`_SnapshotService` 继承它），B1 不依赖——并文件后该 import 移到文件头，B1 函数不触发，无副作用。
