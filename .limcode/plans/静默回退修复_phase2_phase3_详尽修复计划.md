## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [ ] ExternalGroupService._apply_separate_mode 兼容模式补 guarded logger.warning（HIGH）  `#FIX-1`
- [ ] process_parts.py::set_group_mode 改为注入 current_app.logger  `#FIX-2`
- [ ] BatchService.import_from_preview_rows 增 strict_mode 参数并保持默认 False  `#FIX-3`
- [ ] batch_excel_import.py 透传 strict_mode 到 create_batch_from_template_no_tx  `#FIX-4`
- [ ] scheduler_excel_batches.py 增 strict_mode helper/UI/confirm 透传，并显式传 BatchService logger  `#FIX-5`
- [ ] scheduler_excel_batches.py 将 strict_mode 纳入 preview_baseline extra_state  `#FIX-6`
- [ ] 模板 templates/scheduler/excel_import_batches.html 直接补 strict_mode checkbox/hidden field（不假定组件复用）  `#FIX-7`
- [ ] 回归测试：ExternalGroupService compatible fallback logger（mock logger）  `#FIX-8`
- [ ] 回归测试：batch Excel strict_mode 硬失败 + 原子回滚  `#FIX-9`
- [ ] 回归测试：batch Excel strict_mode preview/confirm 漂移需重新预览  `#FIX-10`
- [ ] _build_overdue_items 做最小 non-silent fallback（cleanup，非阻塞）  `#FIX-11`
- [ ] _config_snapshot_dict / _extract_freeze_warnings 仅做轻量增强或延期，不做大签名改造  `#FIX-12`
<!-- LIMCODE_TODO_LIST_END -->

# 静默回退修复 Phase 2/3 详尽修复计划（深审修订版）

## 0. 背景与本次修订说明

本计划是在以下材料基础上重写的修订版：

1. 既有计划：`.limcode/plans/静默回退修复_phase2_phase3_详尽修复计划.md`
2. 既有三轮审查：`.limcode/review/静默回退修复_phase23_三轮审查报告.md`
3. 本轮深度审查：`.limcode/review/20260402_静默回退修复_phase23_深度审查报告.md`
4. 运行时与脚本证据：
   - `python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --file core/services/scheduler/batch_service.py`
   - `python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --file core/services/scheduler/schedule_summary.py`
   - `create_app()` + `test_request_context()` 最小脚本
   - 针对 `_build_overdue_items()` / `_extract_freeze_warnings()` / `_config_snapshot_dict()` 的最小脚本

本版计划遵循三个修订原则：

- **事实 / 判断 / 建议分开写**，不把建议写成既成事实；
- **优先保留已验证高风险问题**，降低“看起来有问题但主链风险不高”的事项优先级；
- **控制改动面**，优先修复 strict_mode 与 logger 可观测性主线，不默认扩大到 schema / summary 大改造。

---

## 1. 深审后的关键纠偏结论

## 1.1 必须保留并优先执行的结论

### C1. `ExternalGroupService._apply_separate_mode()` compatible fallback 仍是本轮最高优先级问题

已验证事实：
- `strict_mode=False` 时，非法 `per_op_days` 仍直接回退为 `1.0` 并写库；
- 当前无 logger / warning / counter；
- 这是当前最明确、最可复现的“兼容路径静默回退”。

### C2. batch Excel import 的 strict_mode 缺口确实存在

已验证事实：
- `BatchService.import_from_preview_rows()` 无 `strict_mode` 参数；
- `batch_excel_import.import_batches_from_preview_rows()` 无 `strict_mode` 参数；
- `_apply_row_no_tx()` 调 `create_batch_from_template_no_tx(..., rebuild_ops=True)` 未传 `strict_mode`；
- `scheduler_excel_batches.py` 当前无 strict_mode UI / route 透传。

### C3. 本轮 logger 注入方案必须改写为 `current_app.logger` 的局部修复，不直接照搬 `g.app_logger`

已验证事实：
- 当前 runtime 下 `g.app_logger` 未赋值；
- `current_app.logger` 可用；
- 因此计划中若直接写 `logger=getattr(g, "app_logger", None)`，修完后仍可能得到 `None`。

### C4. 新增 service logger 调用必须使用 guard

已验证事实：
- 现有测试大量直接 `ExternalGroupService(conn)` / `BatchService(conn)` / `PartService(conn)`，不传 logger；
- 若直接新增 `self.logger.warning(...)` 而不做 `if self.logger:` guard，会直接引入回归。

---

## 1.2 必须补入计划但原版遗漏的结论

### C5. batch Excel strict_mode 不仅要 hidden field 透传，还要纳入 preview/confirm baseline guard

已验证事实：
- `scheduler_excel_batches.py::_batch_baseline_extra_state()` 当前只包含：
  - `auto_generate_ops`
  - `parts_snapshot`
  - `template_ops_snapshot`
- 现有 `tests/regression_excel_preview_confirm_extra_state_guard.py` 已证明 extra_state 是 preview → confirm 状态一致性的正式守卫。

修订结论：
- 若 strict_mode 只做表单透传，不加入 baseline extra_state，则 preview/confirm 的“严格/兼容语义”仍可漂移；
- 因此 strict_mode 必须同时进入：
  - route 读取
  - render context
  - hidden field
  - `preview_baseline` 的 extra_state

### C6. batch Excel strict_mode 回归测试目标必须是“硬失败 + 原子回滚”，不是“按行计错继续”

已验证事实：
- `execute_preview_rows_transactional()` 默认 `continue_on_app_error=False`；
- `tests/regression_excel_failure_semantics_contracts.py` 已把 batch import 定义为 hard-fail 合同；
- `scheduler_excel_batches.py::excel_batches_confirm()` 也没有 catch `svc.import_from_preview_rows()` 的 `AppError`。

修订结论：
- 新测试不应写成 `error_count += 1` 后继续；
- 正确验收语义应为：
  - service / route 抛错或走错误页；
  - `Batches` / `BatchOperations` 无残留；
  - 整体事务回滚。

### C7. `scheduler_excel_batches.py` 的 logger 传递要从“顺手检查”升级为本轮必改项

已验证事实：
- `BatchService._default_template_resolver()` 会把 `self.logger` 继续传给 `PartService`；
- 所以 Excel 批次导入路径能否看到 fallback warning，取决于 route 是否给 `BatchService` 显式传 logger。

修订结论：
- `scheduler_excel_batches.py` 必须显式传 `logger=current_app.logger`；
- 这不是“可选优化”，而是让本轮可观测性修复真正生效的必要条件。

---

## 1.3 需要降级的结论

### C8. `_build_overdue_items()` 的 `except: pass` 存在，但主链风险低于原计划表述

已验证事实：
- 真实调度 summary 类型来自 `core.algorithms.types.ScheduleSummary`，`warnings` 类型就是 `List[str]`；
- append 失败更偏向防御性分支，而不是主链高频故障。

修订结论：
- 不再将其作为与 strict_mode 同等级的阻塞项；
- 如修复，采用最小 non-silent fallback 即可；
- 若时间紧张，可作为本轮 cleanup 或下一批 follow-up。

### C9. `_extract_freeze_warnings()` broad except 是坏味道，但在当前调用链上几乎是死分支

已验证事实：
- 唯一调用点先经过 `_warning_list()` / `_merge_warning_lists()` 归一化；
- 传入 `_extract_freeze_warnings()` 的实际对象已经是 `List[str]`。

修订结论：
- 可以清理，但不应继续当作本轮必须项；
- 不强制为“坏对象导致整体清空”编写专项 regression，因为这与当前调用链不一致。

### C10. `_config_snapshot_dict()` 的异常分支确实无留痕，但不在本轮默认做大签名改造

已验证事实：
- 主契约已有测试覆盖；缺的是异常路径专项覆盖；
- 若把 `_config_snapshot_dict()` 改成 tuple / metadata 返回，会扩大影响面。

修订结论：
- 本轮至多做：
  - logger/traceability 补强；或
  - 在 `algo` 下新增可选 sibling 字段；
- 不默认改 `_config_snapshot_dict()` 返回形态；
- 可明确延后到 follow-up。

---

## 2. 修复任务分层（修订后）

## A. 本轮阻塞项（必须修）

### A1. 修复 `ExternalGroupService._apply_separate_mode()` compatible 静默回退

**目标**：兼容行为不变，但 fallback 可见。

**位置**：
- `core/services/process/external_group_service.py::_apply_separate_mode()`
- `web/routes/process_parts.py::set_group_mode()`

**修复要求**：

#### A1-1 service 层补 guarded logger.warning

在 `_apply_separate_mode()` 中：
- 保留 strict_mode 现有拒绝逻辑不变；
- compatible 分支中补 warning；
- warning 文案至少包含：
  - `seq`
  - `op_type_name`
  - 原始 `raw` 值
  - 已按 `1.0` 天回退
  - 当前为 compatible mode
- **必须使用 guard**：

```python
if self.logger:
    try:
        self.logger.warning(...)
    except Exception:
        pass
```

建议文案：

> 外部工序 10（表处理）周期输入无效（raw=''），compatible mode 已按 1.0 天回退写入 ext_days

#### A1-2 route 层改为注入 `current_app.logger`

`web/routes/process_parts.py::set_group_mode()` 当前：

```python
svc = ExternalGroupService(g.db, op_logger=getattr(g, "op_logger", None))
```

本轮计划改为：

```python
svc = ExternalGroupService(
    g.db,
    logger=current_app.logger,
    op_logger=getattr(g, "op_logger", None),
)
```

**注意**：
- `process_parts.py` 当前未导入 `current_app`，需要显式补 import；
- 本轮**不把全局补 `g.app_logger`** 作为先决条件。

#### A1-3 可选增强（非阻塞）

如后续需要统一留痕，可评估 op_logger 中记录 fallback_count / fallback_seqs；
但本轮不强行扩大范围。

**验收标准**：
- compatible mode 仍写 1.0；
- 日志中可见 fallback；
- strict_mode 仍抛 `ValidationError`；
- 现有 strict_mode regression 不回归。

---

### A2. 补齐 batch Excel import 的 strict_mode 全链贯通

**目标**：让 scheduler Excel 批次导入在 auto_generate_ops 路径下也能真正进入 strict_mode。

**位置**：
- `web/routes/scheduler_excel_batches.py`
- `core/services/scheduler/batch_service.py::import_from_preview_rows()`
- `core/services/scheduler/batch_excel_import.py::import_batches_from_preview_rows()`
- `templates/scheduler/excel_import_batches.html`

#### A2-1 `BatchService.import_from_preview_rows()` 增参数

新增：

```python
strict_mode: bool = False
```

并透传给：

```python
batch_excel_import.import_batches_from_preview_rows(..., strict_mode=bool(strict_mode))
```

**契约要求**：
- 默认值保持 `False`；
- 不破坏现有 direct-call tests；
- 不改变非 strict 调用语义。

#### A2-2 `batch_excel_import.py` 透传 strict_mode

`import_batches_from_preview_rows()` 增参数：

```python
strict_mode: bool = False
```

并在 `_apply_row_no_tx()` 中改为：

```python
svc.create_batch_from_template_no_tx(
    ...,
    rebuild_ops=True,
    strict_mode=bool(strict_mode),
)
```

**说明**：
- 本路径仍沿用当前 hard-fail/transactional 语义；
- 不改成 row-error continue。

#### A2-3 `scheduler_excel_batches.py` 补 strict_mode route/UI/logger

必须完成以下动作：

1. 新增 `_strict_mode_enabled(raw_value)` helper；
2. `excel_batches_page()` / `preview()` / `confirm()` 均维护 `strict_mode` 状态；
3. `_render_excel_batches_page()` 增加：
   - `strict_mode_supported=True`
   - `strict_mode=bool(strict_mode)`
   - `strict_mode_label`
   - `strict_mode_help`
4. 所有相关 `BatchService(...)` 构造改为显式传：

```python
logger=current_app.logger,
op_logger=getattr(g, "op_logger", None),
```

5. 调 `svc.import_from_preview_rows(...)` 时传 `strict_mode=strict_mode`。

#### A2-4 strict_mode 纳入 `preview_baseline` 的 extra_state

这是本轮新增的硬要求，不再作为隐含事项。

`_batch_baseline_extra_state()` 需要纳入：

```python
"strict_mode": bool(strict_mode)
```

并让 preview / confirm 两端计算 baseline 时使用同一值。

**目的**：
- 防止 preview 使用 compatible，而 confirm 被改成 strict（或反之）仍不触发“需重新预览”。

#### A2-5 模板改动走“当前页面最短路径”

`templates/scheduler/excel_import_batches.html` 当前是自定义模板，不是直接 include 通用组件的页面。

因此本轮计划按最短路径执行：
- **直接修改该模板本身**；
- 不再假定“复用 `components/excel_import.html` 的 strict_mode 插槽”已经是现状；
- 若实施时愿意做局部模板重构，可作为可选优化，但不写成必经步骤。

模板最低要求：
- preview form 有 strict_mode checkbox；
- confirm form 有 strict_mode hidden field；
- 页面顶部“导入选项”区能显示当前 strict_mode 状态，避免用户误判。

#### A2-6 本轮保持当前 route 错误语义

本轮不默认重构 `excel_batches_confirm()` 的错误 UX。

也就是说：
- strict_mode 导致模板补建失败时，继续沿用当前 hard-fail 语义；
- 如 route 最终走全局 `AppError` handler，视为当前合同的一部分；
- 若要改成页面内 flash/回填，这是额外 UX 议题，不纳入本批默认范围。

**验收标准**：
- UI 可勾选 strict_mode；
- preview → confirm 不丢 strict_mode；
- strict_mode 进入 baseline extra_state；
- auto_generate_ops=True 且模板补建需要 fallback 时，strict_mode=True 会 hard-fail 且无残留；
- 默认不勾选时仍保持兼容行为。

---

## B. 本轮建议修，但不再与主线同等级阻塞

### B1. `_build_overdue_items()` 做最小 non-silent fallback

**当前定位**：cleanup / 低风险。

**建议修法**：
- 保持返回值 contract 不变；
- 优先做“安全追加”而不是直接大改函数签名；
- 最低可接受方案：append 失败时补一条 append-failure logger；
- 更稳妥但仍小改的方案：尝试把 `summary.warnings` 归一化为 list 后再补写，失败再记录 logger。

**明确不做**：
- 本轮不默认把 `_build_overdue_items()` 改成 tuple 返回。

### B2. `_config_snapshot_dict()` 只做轻量增强或延后

**当前定位**：follow-up 决策项。

可选方案：
1. 仅补 logger/traceability；
2. 在 `algo` 下新增：
   - `config_snapshot_incomplete`
   - `config_snapshot_issue_count`
   - `config_snapshot_issue_keys_sample`

**明确不做**：
- 不默认把 `_config_snapshot_dict()` 改为 tuple 返回；
- 不默认提升 `summary_schema_version`。

### B3. `_extract_freeze_warnings()` broad except 清理

**当前定位**：低优先级整理项。

建议：
- 如顺手修改，可改成逐项容错；
- 若本轮时间不足，可明确延后；
- 不强制为“坏对象丢失 freeze warnings”编写专项 regression。

---

## 3. 逐文件修改清单（修订后）

## 3.1 `core/services/process/external_group_service.py`

### 必改
- `_apply_separate_mode()` compatible fallback 增加 guarded `logger.warning`。

### 注意点
- strict_mode 分支文案与字段名保持稳定；
- compatible 分支只增强可观测性，不改变写库值；
- `float(dv)` 落库逻辑不改；
- 不引入对 logger 非空的隐式依赖。

---

## 3.2 `web/routes/process_parts.py`

### 必改
- `from flask import current_app, flash, g, redirect, request, url_for`
- `set_group_mode()` 中 `ExternalGroupService(...)` 改为传 `logger=current_app.logger`

### 不在本轮强制处理
- 其他 `PartService(...)` 构造点是否全面改 logger，不作为本批阻塞项；
- 本轮只修与本次新增日志直接相关的构造点。

---

## 3.3 `core/services/scheduler/batch_service.py`

### 必改
- `import_from_preview_rows(..., strict_mode: bool = False)`
- 透传到 `batch_excel_import.import_batches_from_preview_rows(...)`

### 契约要求
- 默认值必须是 `False`；
- 不改变现有 batch import hard-fail 语义。

---

## 3.4 `core/services/scheduler/batch_excel_import.py`

### 必改
- `import_batches_from_preview_rows(..., strict_mode: bool = False)`
- `_apply_row_no_tx()` 中把 `strict_mode` 透传给 `create_batch_from_template_no_tx()`

### 可选
- `result["strict_mode"] = bool(strict_mode)` 可作为诊断信息；
- 但不是主验收项。

---

## 3.5 `web/routes/scheduler_excel_batches.py`

### 必改
- 新增 `_strict_mode_enabled()` helper
- `page / preview / confirm` 状态维护
- `BatchService(..., logger=current_app.logger, op_logger=...)`
- `_render_excel_batches_page()` 扩 strict_mode context
- `_batch_baseline_extra_state()` 纳入 `strict_mode`
- `svc.import_from_preview_rows(..., strict_mode=strict_mode)`

### 说明
- 当前文件已 import `current_app`，优先局部修复；
- 不额外引入 `g.app_logger` 依赖。

---

## 3.6 `templates/scheduler/excel_import_batches.html`

### 必改
- preview form 增 strict_mode checkbox
- confirm form 增 strict_mode hidden field
- 页面显示当前 strict_mode 状态

### 说明
- 当前页面是自定义模板；
- 本轮直接修改该模板，不把“组件复用重构”设为前置条件。

---

## 3.7 `core/services/scheduler/schedule_summary.py`

### 本轮最多做
- `_build_overdue_items()` 最小 non-silent fallback
- `_config_snapshot_dict()` 轻量留痕（若决定同批处理）
- `_extract_freeze_warnings()` 顺手整理（可选）

### 明确控制改动面
- 不默认改返回值 contract；
- 不默认改 `summary_schema_version`；
- 不默认做大范围结构化重构。

---

## 4. 回归测试计划（修订后）

## 4.1 必增测试

### T1. `regression_external_group_service_compatible_mode_logs_fallback.py`

覆盖：
- `strict_mode=False`
- 非法 `per_op_days`（如 `""`、`0`、`"abc"`）
- 显式注入 mock logger

断言：
- `ext_days` 仍落库为 `1.0`
- logger 收到 warning
- 文案包含 seq / raw / fallback / compatible mode

**说明**：
- 此测试不依赖 Flask `g` 或全局 logger 注入。

### T2. `regression_batch_excel_import_strict_mode_hardfail_atomic.py`

覆盖：
- scheduler batch Excel import
- `auto_generate_ops=True`
- `strict_mode=True`
- 模板补建需要 fallback（如缺供应商映射）

断言：
- 调用为 hard-fail，而不是 `error_count+=1` 继续
- `Batches` 无残留
- `BatchOperations` 无残留

### T3. `regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py`

覆盖：
- preview 时 `strict_mode=yes`
- confirm 人工改成 `strict_mode=no`（或反向）

断言：
- baseline 校验失败
- 页面提示“需重新预览”

### T4. route/template 表面契约测试（可与 T3 合并）

覆盖：
- `/scheduler/excel/batches` 页面与 preview 页

断言：
- 存在 `name="strict_mode"`
- preview 后 confirm 区有 strict_mode hidden field

---

## 4.2 条件性新增测试（仅在实现对应 cleanup 时补）

### T5. `_build_overdue_items` cleanup regression

仅当本轮实际修改 `_build_overdue_items()` 时新增：
- 构造非 list warnings 容器
- 断言不再完全静默

### T6. `_config_snapshot_dict` exceptional-path regression

仅当本轮实际修改 `_config_snapshot_dict()` 异常路径时新增：
- `to_dict()` 抛异常
- 某 getter 抛异常
- 断言新增留痕字段或 logger 行为

**明确不强制新增**：
- 针对 `_extract_freeze_warnings()` 的“坏对象导致整体清空”专项测试

---

## 4.3 需要回归重跑的现有测试

### ExternalGroup / strict mode
- `tests/regression_external_group_service_strict_mode_blank_days.py`
- `tests/regression_external_group_service_merge_mode_case_insensitive.py`
- `tests/regression_part_service_create_strict_mode_atomic.py`
- `tests/regression_batch_service_strict_mode_template_autoparse.py`
- `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`

### Batch Excel import / baseline
- `tests/regression_batch_import_unchanged_no_rebuild.py`
- `tests/regression_excel_failure_semantics_contracts.py`
- `tests/regression_excel_preview_confirm_baseline_guard.py`
- `tests/regression_excel_preview_confirm_extra_state_guard.py`
- `tests/regression_excel_import_result_semantics.py`
- `tests/smoke_web_phase0_6.py`
- `tests/smoke_e2e_excel_to_schedule.py`

### schedule_summary（仅当同批动到 cleanup）
- `tests/regression_schedule_summary_v11_contract.py`
- `tests/regression_schedule_summary_algo_warnings_union.py`
- `tests/regression_dict_cfg_contract.py`

---

## 5. 实施顺序（修订后）

## Phase A：先修高风险主线
1. 修 `ExternalGroupService._apply_separate_mode()` 的 guarded warning
2. 修 `process_parts.py::set_group_mode()` 的 `current_app.logger` 注入
3. 补 T1
4. 跑 external_group_service / strict_mode 相关测试

## Phase B：修 batch Excel strict_mode 全链
1. 改 `BatchService.import_from_preview_rows()`
2. 改 `batch_excel_import.py`
3. 改 `scheduler_excel_batches.py` route/logger/baseline
4. 改 `templates/scheduler/excel_import_batches.html`
5. 补 T2 / T3 / T4
6. 跑 batch Excel / preview-confirm / smoke 相关测试

## Phase C：决定是否纳入低风险 cleanup
1. 若时间充足，再处理 `_build_overdue_items()`
2. 评估 `_config_snapshot_dict()` 是否只做轻量留痕
3. `_extract_freeze_warnings()` 仅顺手整理，不单独阻塞
4. 若有改动，再补 T5 / T6 并跑 schedule_summary 相关测试

## Phase D：复核
1. 第一轮：源码链复核
2. 第二轮：契约与兼容性复核
3. 第三轮：测试覆盖与 smoke 复核

---

## 6. 三轮复核执行清单（修订后）

## 第 1 轮：源码链复核

逐项确认：
- `ExternalGroupService` compatible fallback 是否可见
- route 是否使用 `current_app.logger` 而非无效的 `g.app_logger`
- batch Excel strict_mode 是否从 route/template → service → no_tx → template resolver 全链贯通
- strict_mode 是否进入 preview_baseline extra_state
- `scheduler_excel_batches.py` 的 BatchService 构造是否显式传 logger

## 第 2 轮：契约复核

逐项确认：
- compatible mode 默认行为不变
- strict_mode 仅在 opt-in 时触发拒绝
- batch Excel 仍保持 hard-fail 合同
- 未引入对 logger 非空的运行时依赖
- 若做 schedule_summary cleanup，未破坏 `summary_schema_version=1.1`

## 第 3 轮：测试复核

逐项确认：
- T1 / T2 / T3 / T4 全通过
- 既有 regression 不回归
- smoke/import 相关路径无行为漂移
- 若未实现 cleanup，则不为 cleanup 人为制造伪覆盖

---

## 7. 本轮明确不做的事

1. **不把全局补 `g.app_logger` 作为当前计划前置阶段**
   - 可做，但不是本轮唯一可行路径；
   - 本轮优先局部 `current_app.logger`。

2. **不把模板重构为组件复用作为前置条件**
   - 当前页面是自定义模板；
   - 本轮直接改模板即可。

3. **不默认把 batch Excel strict_mode 改成页面内按行容错**
   - 保持当前 hard-fail 合同；
   - UX 重构另议。

4. **不默认对 `_config_snapshot_dict()` 做大签名改造**
   - 控制影响面；
   - 若要做，另起 follow-up 更稳。

---

## 8. 最终交付标准（修订后）

本计划完成后，应满足：

1. **高风险静默回退主线收敛**
   - `ExternalGroupService._apply_separate_mode()` compatible 路径不再完全无痕。

2. **batch Excel strict_mode 入口真正贯通**
   - route / template / service / no_tx / template resolver 全链可达；
   - strict_mode 受 preview_baseline 保护，不会 preview/confirm 漂移。

3. **logger 注入方案与实际 runtime 一致**
   - 本批修改的关键 route 使用 `current_app.logger`；
   - service 新日志均具备 guard。

4. **测试闭环正确对齐合同**
   - ExternalGroup compatible fallback 有 mock logger regression；
   - batch Excel strict_mode 以 hard-fail + atomic rollback 验收；
   - baseline drift 有重新预览 regression。

5. **低风险 cleanup 不挤占主线优先级**
   - `_build_overdue_items()` / `_extract_freeze_warnings()` / `_config_snapshot_dict()` 只在控制改动面的前提下处理；
   - 若不处理，计划中要明确延后，而不是继续与主线并列阻塞。

---

## 9. 一句话执行口径

> 先把 **compatible fallback 可观测性** 和 **batch Excel strict_mode 全链贯通 + baseline 一致性** 两条主线修实，再决定是否顺带清理 `schedule_summary.py` 的低风险残留；本轮不再把 `g.app_logger` 全局改造、模板重构、summary 大签名改造混入主线。