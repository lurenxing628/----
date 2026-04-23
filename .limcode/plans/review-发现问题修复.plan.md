## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 任务1：SGS 探测式自动分配计数污染修复 — auto_assign 增加 probe_only + 局部闭包、sgs 评分传 True、补回归断言  `#T1`
- [x] 任务2：端点扫描回归正则修正 — pat_url_for 增加 (?<!safe_) 负向后顾  `#T2`
- [x] 任务3：Excel 路由数值校验漂移修复 — 日历/工时/供应商三处路由改用严格解析、新建回归测试  `#T3`
- [x] 任务4：静默吞异常护栏升级 — 白名单升级为 file:enclosing_func 指纹并保留同函数命中次数  `#T4`
- [x] 任务5：excel_validators.py 代码风格清理 — 去掉冗余 float() 和多余空行  `#T5`
- [x] 最终验收：联合回归 + ruff + 端点扫描 + aps-post-change-check（已执行；快检对工作区内本次范围外改动给出 lint 失败与复杂度警告）  `#T6`
<!-- LIMCODE_TODO_LIST_END -->

# review 发现问题修复 实施 plan

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：修复两份审查稿（`20260405_uncommitted_changes_deep_review.md` + `第二次未提交修改深度三轮审查.md`）提出的全部 5 个已核实问题（去重后），使代码可以安心收口提交。

**总体做法**：按风险从高到低逐一修复，每个任务先写失败用例再改实现，最后跑全量受影响回归。任务 1-3 属于逻辑/契约修复，任务 4 属于测试护栏加固，任务 5 属于代码风格清理。

**设计原则**：
- **单一来源**：同一校验逻辑只存在一处，路由层复用服务层/共享入口，不手写重复版本
- **显式失败**：非法输入一律显式拒绝并给出有意义的错误信息，不做静默转换或兜底默认值
- **最小改动**：每个修复只改必须改的地方，不做"顺便优化"
- **不留技术债**：新代码不引入新的重复、新的兜底分支、新的 `except Exception: pass`

**涉及技术 / 模块**：
- `core/algorithms/greedy/auto_assign.py`、`core/algorithms/greedy/dispatch/sgs.py`、`core/algorithms/greedy/scheduler.py`
- `tests/regression_template_urlfor_endpoints.py`
- `web/routes/scheduler_excel_calendar.py`、`web/routes/process_excel_part_operation_hours.py`、`web/routes/process_excel_suppliers.py`
- `tests/test_architecture_fitness.py`
- `core/services/common/excel_validators.py`

**问题覆盖矩阵**：

| 来源 | 问题 ID | 级别 | 对应任务 |
|------|---------|------|----------|
| 审查1 | `sgs-auto-assign-probe-counter-inflation` | 中 | 任务 1 |
| 审查2 | `F-sgs-probe-counter` | 中 | 任务 1（同一问题） |
| 审查1 | `template-urlfor-regex-overmatches-safe-url-for` | 中 | 任务 2 |
| 审查1 | `excel-route-strict-numeric-drift` | 中 | 任务 3 |
| 审查1 | `silent-swallow-fitness-count-only-whitelist` | 中 | 任务 4 |
| 审查2 | `F-prev-low-unfixed` | 低 | 任务 5 |

---

## 文件变更概览

| 文件 | 操作 | 职责 |
|------|------|------|
| `core/algorithms/greedy/auto_assign.py` | 修改 | 增加 `probe_only` 参数；用局部 `_count` 闭包简洁切换记数/不记数 |
| `core/algorithms/greedy/scheduler.py` | 修改 | `_auto_assign_internal_resources` 透传 `probe_only` |
| `core/algorithms/greedy/dispatch/sgs.py` | 修改 | 评分阶段调用时传入 `probe_only=True` |
| `tests/regression_sgs_scoring_fallback_unscorable.py` | 修改 | 增加断言：评分探测不污染 `fallback_counts` |
| `tests/regression_template_urlfor_endpoints.py` | 修改 | `pat_url_for` 加负向后顾 `(?<!safe_)` |
| `web/routes/scheduler_excel_calendar.py` | 修改 | 两处 `validate_row` 中 `float()` 替换为 `parse_finite_float` |
| `web/routes/process_excel_part_operation_hours.py` | 修改 | `_parse_seq` 增加布尔拒绝和科学计数法拒绝 |
| `web/routes/process_excel_suppliers.py` | 修改 | `_normalize_supplier_default_days` 改用 `parse_required_float` |
| `tests/regression_excel_route_strict_numeric.py` | 新建 | 覆盖 `True/False/NaN/Inf/"5e0"` 在三类路由中被拒绝 |
| `tests/test_architecture_fitness.py` | 修改 | 白名单改为 `file:enclosing_func` 级指纹 |
| `core/services/common/excel_validators.py` | 修改 | 去掉冗余 `float()` 包装和多余空行 |

---

### 任务 1：SGS 探测式自动分配计数污染修复

**目标**
- SGS 评分阶段的探测性自动分配调用不再污染 `fallback_counts`，排产摘要中的计数仅反映真实排产失败次数。

**文件**
- 修改：`core/algorithms/greedy/auto_assign.py`
- 修改：`core/algorithms/greedy/scheduler.py`
- 修改：`core/algorithms/greedy/dispatch/sgs.py`
- 测试：`tests/regression_sgs_scoring_fallback_unscorable.py`

- [ ] **步骤 1：在 `auto_assign.py` 增加 `probe_only` 参数并用闭包简化**

在 `auto_assign_internal_resources` 签名末尾新增：

```python
def auto_assign_internal_resources(
    scheduler: Any,
    *,
    # ... 现有参数不变 ...
    probe_only: bool = False,
) -> Optional[Tuple[str, str]]:
```

在函数体最开头（`bid = ...` 之前），定义局部闭包：

```python
    _count = increment_counter if not probe_only else lambda *_a, **_kw: None
```

然后将函数体内所有 8 处 `increment_counter(scheduler, ...)` 替换为 `_count(scheduler, ...)`，无需逐个加 `if` 判断。需要替换的调用点（当前行号）：
- 第 47 行：`auto_assign_missing_op_type_id_count`
- 第 81 行：`auto_assign_missing_machine_pool_count`
- 第 88 行：`auto_assign_missing_machine_pool_count`
- 第 95 行：`auto_assign_no_machine_candidate_count`
- 第 105 行：`auto_assign_invalid_total_hours_count`
- 第 108 行：`auto_assign_invalid_total_hours_count`
- 第 223 行：`auto_assign_no_operator_candidate_count`
- 第 225 行：`auto_assign_no_feasible_pair_count`

**为什么用闭包而不是 8 个 if**：一行定义，全部切换，逻辑集中，无重复代码。

- [ ] **步骤 2：在 `scheduler.py` 透传 `probe_only`**

修改 `_auto_assign_internal_resources` 方法（约第 564 行）：

```python
def _auto_assign_internal_resources(
    self,
    *,
    # ... 现有参数 ...
    probe_only: bool = False,
) -> Optional[Tuple[str, str]]:
    return auto_assign_internal_resources(
        self,
        # ... 现有参数 ...
        probe_only=probe_only,
    )
```

注意：第 441 行的正式排产调用处 **不传 `probe_only`**（默认 `False`），保持正式排产的记数行为不变。

- [ ] **步骤 3：在 `sgs.py` 评分调用处传入 `probe_only=True`**

修改 `sgs.py` 约第 222 行处：

```python
chosen = chooser(
    op=op,
    batch=batch,
    batch_progress=batch_progress,
    machine_timeline=machine_timeline,
    operator_timeline=operator_timeline,
    base_time=base_time,
    end_dt_exclusive=end_dt_exclusive,
    machine_downtimes=machine_downtimes,
    resource_pool=(resource_pool if isinstance(resource_pool, dict) else {}),
    last_op_type_by_machine=last_op_type_by_machine,
    machine_busy_hours=machine_busy_hours,
    operator_busy_hours=operator_busy_hours,
    probe_only=True,
)
```

- [ ] **步骤 4：在回归测试中增加探测不污染的断言**

在 `tests/regression_sgs_scoring_fallback_unscorable.py` 的 `main()` 函数末尾（现有断言之后），增加：

```python
    # 关键断言：评分探测不应污染 fallback_counts
    algo_stats = getattr(sched, "_last_algo_stats", {}) or {}
    fc = algo_stats.get("fallback_counts", {}) or {}
    probe_keys = [
        "auto_assign_missing_op_type_id_count",
        "auto_assign_missing_machine_pool_count",
        "auto_assign_no_machine_candidate_count",
        "auto_assign_invalid_total_hours_count",
        "auto_assign_no_operator_candidate_count",
        "auto_assign_no_feasible_pair_count",
    ]
    for k in probe_keys:
        assert fc.get(k, 0) == 0, (
            f"评分探测污染了 fallback_counts[{k!r}]={fc[k]}，"
            "probe_only=True 时不应记数"
        )
```

- [ ] **步骤 5：运行定向验证**

```bash
python -m pytest tests/regression_sgs_scoring_fallback_unscorable.py tests/regression_sgs_penalize_nonfinite_proc_hours.py tests/regression_auto_assign_persist_truthy_variants.py tests/regression_greedy_scheduler_algo_stats_auto_assign.py -q
```

预期：全部通过。

---

### 任务 2：端点扫描回归正则修正

**目标**
- `safe_url_for(...)` 引用的端点不再被 `url_for` 正则误捕获。

**文件**
- 修改：`tests/regression_template_urlfor_endpoints.py`

- [ ] **步骤 1：修正 `pat_url_for` 正则**

将第 60 行：

```python
pat_url_for = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
```

改为负向后顾排除 `safe_` 前缀：

```python
pat_url_for = re.compile(r"(?<!safe_)url_for\(\s*['\"]([^'\"]+)['\"]")
```

**为什么是负向后顾**：`safe_url_for(` 中 `url_for(` 紧跟在 `safe_` 后面，`(?<!safe_)` 精确排除这一情况，不影响独立的 `url_for(`、`{{ url_for(` 等合法模式。一行改动，无新代码，无新函数。

- [ ] **步骤 2：运行测试**

```bash
python tests/regression_template_urlfor_endpoints.py
```

预期：打印 `OK: templates url_for endpoints all registered.`，不出现 `safe_url_for` 端点的误报。

---

### 任务 3：Excel 路由数值校验漂移修复

**目标**
- 三处路由的 Excel 预览/确认阶段数值校验与服务层契约保持一致，`True/False/NaN/Inf/"5e0"` 等脏值在预览阶段即被拒绝，不做静默转换。

**文件**
- 修改：`web/routes/scheduler_excel_calendar.py`
- 修改：`web/routes/process_excel_part_operation_hours.py`
- 修改：`web/routes/process_excel_suppliers.py`
- 新建：`tests/regression_excel_route_strict_numeric.py`

- [ ] **步骤 1：新建回归测试**

创建 `tests/regression_excel_route_strict_numeric.py`：

```python
"""
回归测试：Excel 路由层数值校验必须与服务层契约一致。
覆盖 True/False/NaN/Inf/"5e0" 在路由预览阶段即被拒绝。
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_parse_seq_rejects_bool_and_scientific():
    """_parse_seq 必须拒绝 True/False 和科学计数法字符串。"""
    from web.routes.process_excel_part_operation_hours import _parse_seq
    # 布尔值
    assert _parse_seq(True) is None, "True 应被拒绝"
    assert _parse_seq(False) is None, "False 应被拒绝"
    # 科学计数法字符串
    assert _parse_seq("5e0") is None, '"5e0" 应被拒绝'
    assert _parse_seq("1E2") is None, '"1E2" 应被拒绝'
    # 正常值仍通过
    assert _parse_seq(5) == 5
    assert _parse_seq("10") == 10
    assert _parse_seq(3.0) == 3


def test_supplier_default_days_rejects_bool():
    """_normalize_supplier_default_days 必须拒绝布尔值。"""
    from web.routes.process_excel_suppliers import _normalize_supplier_default_days
    assert _normalize_supplier_default_days({"默认周期": True}) is not None, "True 应被拒绝"
    assert _normalize_supplier_default_days({"默认周期": False}) is not None, "False 应被拒绝"
    # NaN / Inf
    assert _normalize_supplier_default_days({"默认周期": float("nan")}) is not None
    assert _normalize_supplier_default_days({"默认周期": float("inf")}) is not None
    # 正常值仍通过
    assert _normalize_supplier_default_days({"默认周期": 5.0}) is None


if __name__ == "__main__":
    test_parse_seq_rejects_bool_and_scientific()
    test_supplier_default_days_rejects_bool()
    print("OK")
```

注意：日历路由的 `validate_row` 是闭包（定义在路由函数内部），无法直接 import 测试，改为通过 `excel_validators.py` 的共享校验函数间接覆盖——该文件已使用 `parse_finite_float`。路由层修复后与 `excel_validators.py` 行为对齐，由现有回归 `tests/regression_calendar_no_tx_hardening.py` 覆盖端到端契约。

- [ ] **步骤 2：运行测试，确认当前实现下失败**

```bash
python -m pytest tests/regression_excel_route_strict_numeric.py -q
```

预期：2 个测试因路由层放过脏值而失败。

- [ ] **步骤 3：修复日历路由——两处 `validate_row` 中 `float()` 替换为 `parse_finite_float`**

修改 `web/routes/scheduler_excel_calendar.py`：

首先在文件头部增加 import（在现有 `from core.services.common.normalize import is_blank_value` 之后）：

```python
from core.services.common.number_utils import parse_finite_float
```

然后修改预览路由（约第 197-220 行）的 `validate_row` 中"可用工时"校验块，从：

```python
            try:
                v = float(sh)
                if v < 0:
                    return ""可用工时"不能为负数"
                row["可用工时"] = v
            except Exception:
                return ""可用工时"必须是数字"
```

改为：

```python
            try:
                v = parse_finite_float(sh, field="可用工时")
                if v < 0:
                    return ""可用工时"不能为负数"
                row["可用工时"] = v
            except ValidationError as e:
                return e.message
```

同理修改"效率"校验块（约第 214-220 行），将 `float(eff)` 改为 `parse_finite_float(eff, field="效率")`，`except Exception` 改为 `except ValidationError as e: return e.message`。

**同样的修改**需要在确认路由（约第 335-353 行）的 `validate_row` 中重复一次，因为那里有相同的重复代码。

**为什么改用 `parse_finite_float` 而不是 `float()`**：`parse_finite_float` 已内置布尔拒绝 + NaN/Inf 拒绝，与 `CalendarAdmin._normalize_float` 是同一个入口，确保预览和落库契约完全一致。`except Exception` 改为 `except ValidationError` 避免吞掉意外异常。

- [ ] **步骤 4：修复零件工时路由——`_parse_seq` 增加两行防护**

修改 `web/routes/process_excel_part_operation_hours.py` 第 46 行起的 `_parse_seq`：

```python
def _parse_seq(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):   # bool 是 int 子类，必须先拦截
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    s = str(value).strip()
    if not s:
        return None
    if "e" in s.lower():                            # 与服务层 _coerce_int 一致
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    try:
        f = float(s)
        if float(f).is_integer():
            return int(f)
    except Exception:
        return None
    return None
```

关键改动：
1. 第一行从 `if value is None:` 改为 `if value is None or isinstance(value, bool):`
2. 在 `re.fullmatch` 之前新增 `if "e" in s.lower(): return None`

**为什么**：与 `PartOperationHoursExcelImportService._coerce_int()` 的逻辑完全对齐，避免路由层接受了服务层会拒绝的值。

- [ ] **步骤 5：修复供应商路由——改用 `parse_required_float`**

修改 `web/routes/process_excel_suppliers.py` 的 `_normalize_supplier_default_days`（约第 89 行起）：

```python
def _normalize_supplier_default_days(row: Dict[str, Any]) -> Optional[str]:
    raw_value = row.get("默认周期")
    if raw_value is None or str(raw_value).strip() == "":
        return ""默认周期"不能为空"
    try:
        days = parse_required_float(raw_value, field="默认周期", min_value=0, min_inclusive=False)
    except ValidationError as e:
        return e.message
    row["默认周期"] = days
    return None
```

在文件头部增加 import：

```python
from core.services.common.strict_parse import parse_required_float
```

（`ValidationError` 已在第 10 行 import。）

**为什么删除手写 `float()` + `if days <= 0`**：`parse_required_float(min_value=0, min_inclusive=False)` 一步到位完成布尔拒绝 + NaN/Inf 拒绝 + `> 0` 校验，与 `SupplierService._normalize_default_days` 是同一入口。

- [ ] **步骤 6：重新运行定向验证**

```bash
python -m pytest tests/regression_excel_route_strict_numeric.py -q
```

预期：全部通过。

- [ ] **步骤 7：运行受影响回归**

```bash
python -m pytest tests/regression_calendar_no_tx_hardening.py tests/regression_scheduler_excel_calendar_uses_executor.py tests/test_part_operation_hours_import_apply_defense.py tests/regression_process_suppliers_route_reject_blank_default_days.py tests/regression_supplier_service_invalid_default_days_not_silent.py -q
```

预期：全部通过。

---

### 任务 4：静默吞异常护栏升级

**目标**
- `test_no_silent_exception_swallow` 从"文件级数量"升级为"文件+封闭函数名"级指纹，能检测同一文件内"删旧增新"的违规。

**文件**
- 修改：`tests/test_architecture_fitness.py`

- [ ] **步骤 1：新增 `_find_enclosing_name` 辅助函数**

在 `test_no_silent_exception_swallow` 所在区域前（约第 390 行前）添加：

```python
def _find_enclosing_name(node: ast.AST) -> str:
    """上溯 AST 找最近的函数/类名，用作稳定指纹锚点。"""
    cur = node
    while hasattr(cur, "_ast_parent"):
        cur = cur._ast_parent  # type: ignore[attr-defined]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        if isinstance(cur, ast.ClassDef):
            return cur.name
    return "<module>"
```

- [ ] **步骤 2：修改 `_scan_file` 输出格式**

将 `_scan_file` 改为返回 `file:enclosing_name` 形式的指纹列表：

```python
def _scan_file(fp: str) -> List[str]:
    try:
        source = _read(fp)
        tree = ast.parse(source, filename=fp)
    except SyntaxError:
        return []
    # 构建 parent 引用
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._ast_parent = node  # type: ignore[attr-defined]
    out: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for h in node.handlers:
            if not (isinstance(h.type, ast.Name) and h.type.id == "Exception"):
                continue
            body = list(h.body or [])
            hit = False
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                hit = True
            elif len(body) == 1:
                expr_stmt = body[0]
                if isinstance(expr_stmt, ast.Expr) and isinstance(expr_stmt.value, ast.Constant):
                    if expr_stmt.value.value is Ellipsis:
                        hit = True
            if hit:
                enclosing = _find_enclosing_name(h)
                out.append(f"{fp}:{enclosing}")
    return out
```

- [ ] **步骤 3：将 `known_violations` 格式从 `file:line` 改为 `file:enclosing_func`**

先运行一次临时脚本，打印当前所有 hit 的 `file:enclosing_name` 值：

```python
# 临时：在测试中把 assert 改为 print，跑一遍，收集所有指纹
for fp, hits in sorted(violations_by_file.items()):
    for hit in hits:
        print(repr(hit))
```

然后将输出复制为新的 `known_violations` 集合。例如：

```python
known_violations = {
    "core/infrastructure/backup.py:_try_remove",
    "core/infrastructure/backup.py:safe_copy",
    "core/infrastructure/database.py:init_db",
    # ... 按实际输出填充 ...
}
```

- [ ] **步骤 4：修改比较逻辑**

将当前的"按文件计数比较"改为"按指纹精确比较"：

```python
    violations_by_file: Dict[str, List[str]] = {}
    for fp in _collect_py_files(*CORE_DIRS):
        hits = _scan_file(fp)
        if hits:
            violations_by_file[fp] = hits

    new_violations: List[str] = []
    for fp, hits in sorted(violations_by_file.items()):
        for hit in hits:
            if hit not in known_violations:
                new_violations.append(hit)

    assert not new_violations, (
        "新增静默吞异常（except Exception: pass / ...）违反：\n"
        + "\n".join(sorted(new_violations))
        + "\n\n如有合理理由，请添加到 known_violations 白名单并说明原因。"
    )
```

**为什么用 `file:func_name` 而不是 `file:line`**：函数名比行号稳定——在函数内部增删代码不影响指纹，但把吞异常从 A 函数删掉、在 B 函数新增，指纹会变化，从而被检测到。

**为什么不保留计数兜底**：精确指纹已经比计数严格，无需退回粗粒度。

- [ ] **步骤 5：运行验证**

```bash
python -m pytest tests/test_architecture_fitness.py::test_no_silent_exception_swallow -q
```

预期：通过。

- [ ] **步骤 6：验证检测能力**

临时在 `core/infrastructure/backup.py` 的任意 **新函数** 中插入：

```python
def _test_probe():
    try:
        pass
    except Exception:
        pass
```

运行测试确认失败（报出 `core/infrastructure/backup.py:_test_probe` 不在白名单）。然后撤回改动。

---

### 任务 5：excel_validators.py 代码风格清理

**目标**
- 去掉 2 处冗余 `float()` 包装和 2 处连续双空行。

**文件**
- 修改：`core/services/common/excel_validators.py`

- [ ] **步骤 1：去掉冗余 `float()` 包装**

第 194 行，从：
```python
parsed_shift_hours = float(parse_finite_float(sh, field="可用工时", allow_none=False))
```
改为：
```python
parsed_shift_hours = parse_finite_float(sh, field="可用工时", allow_none=False)
```

第 217 行，从：
```python
parsed_efficiency = float(parse_finite_float(eff, field="效率", allow_none=False))
```
改为：
```python
parsed_efficiency = parse_finite_float(eff, field="效率", allow_none=False)
```

**为什么**：`parse_finite_float(..., allow_none=False)` 返回类型已是 `float`（有 `@overload` 注解保证），外层 `float()` 纯冗余。

- [ ] **步骤 2：去掉多余空行**

第 200-201 行：删除一行空行，保留一行。
第 223-224 行：删除一行空行，保留一行。

- [ ] **步骤 3：运行受影响回归**

```bash
python -m pytest tests/regression_calendar_no_tx_hardening.py tests/regression_scheduler_excel_calendar_uses_executor.py tests/test_excel_import_hardening.py -q
```

预期：全部通过。

---

## 最终验收

- [ ] **运行全部受影响测试的联合回归**

```bash
python -m pytest tests/regression_sgs_scoring_fallback_unscorable.py tests/regression_sgs_penalize_nonfinite_proc_hours.py tests/regression_auto_assign_persist_truthy_variants.py tests/regression_greedy_scheduler_algo_stats_auto_assign.py tests/regression_excel_route_strict_numeric.py tests/regression_calendar_no_tx_hardening.py tests/regression_scheduler_excel_calendar_uses_executor.py tests/test_part_operation_hours_import_apply_defense.py tests/regression_process_suppliers_route_reject_blank_default_days.py tests/regression_supplier_service_invalid_default_days_not_silent.py tests/test_architecture_fitness.py tests/test_excel_import_hardening.py -q
```

预期：全部通过。

- [ ] **运行端点扫描**

```bash
python tests/regression_template_urlfor_endpoints.py
```

预期：打印 `OK`。

- [ ] **运行 ruff 检查**

```bash
python -m ruff check core/algorithms/greedy/auto_assign.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/scheduler.py web/routes/scheduler_excel_calendar.py web/routes/process_excel_part_operation_hours.py web/routes/process_excel_suppliers.py core/services/common/excel_validators.py tests/regression_template_urlfor_endpoints.py tests/test_architecture_fitness.py tests/regression_excel_route_strict_numeric.py
```

预期：无新增错误。

- [ ] **改动后快检**

使用 `aps-post-change-check` 做一轮快检收口。
