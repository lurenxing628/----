# 静默回退修复 Phase 2/3 计划 三轮审查报告（对抗性修正版）

- Date: 2026-04-02
- Status: completed
- Overall Decision: conditionally_accepted_after_revision
- Target: `.limcode/plans/静默回退修复_phase2_phase3_详尽修复计划.md`

---

## 0. 修订说明

本版报告是在“**默认先前结论均未验证**”的前提下重写的对抗性修正版。

本次改写遵循三条规则：

1. **事实 / 判断 / 建议分离**：
   - 事实：必须由源码或 runtime 证据支撑；
   - 判断：只能从已验证事实推出；
   - 建议：属于实现路径选择，不能写成既成事实。
2. **优先最小可证伪结论**：不把“可选修复路径”误写成“唯一必须路径”。
3. **重新校正原报告中的过强结论**：尤其是 `g.app_logger`、模板复用、测试依赖这三类问题。

---

## 1. 对抗性审查后的总体结论

### 1.1 总体判定

原计划对以下核心问题的**代码现状描述基本准确**：

- `ExternalGroupService._apply_separate_mode()` 的 compatible fallback 仍完全静默；
- batch Excel import 链路确实未贯通 `strict_mode`；
- `schedule_summary.py` 中 `_build_overdue_items()` / `_extract_freeze_warnings()` / `_config_snapshot_dict()` 确有残留 silent pass / broad except。

因此，**计划主体方向是成立的**。

### 1.2 本次对抗性修正后的关键结论

原审查报告中，以下结论需要纠偏：

1. **`g.app_logger` 未赋值是事实，但“不先做全局 Phase 0 就不能实施本计划”不是已证事实。**
2. **`scheduler_excel_batches.py` 的 logger 传递问题存在，但原计划并非完全漏掉，只是没有把它收敛成硬要求。**
3. **T1（compatible mode logger fallback 测试）不依赖全局 logger 修复，可以通过注入 mock logger 独立完成。**
4. **`excel_import_batches.html` 当前不是复用通用组件，这一事实成立；但“因此必须直接改自定义模板”只是实现建议，不是唯一可行路径。**
5. **`config_snapshot` 并非“整体无测试覆盖”；真正缺的是异常分支的专项覆盖。**

### 1.3 修正后的总判定

> **计划可执行，但应先修正文案与实施路径。**
>
> 需要修正的是：
> - logger 注入方案的写法；
> - 对 `scheduler_excel_batches.py` 的 logger 收敛要求；
> - 测试依赖关系的表述；
> - `_config_snapshot_dict()` 覆盖结论的准确性。
>
> **不需要把“全局补 `g.app_logger`”上升为当前计划的唯一前置步骤。**

---

## 2. 证据等级说明

为避免把建议写成事实，本报告将证据分为三类：

### A 级：源码 + runtime 双证据
已通过实际运行最小用例验证。

### B 级：源码证据
已逐文件核对源码，但未做 runtime 复现。

### C 级：实现建议 / 审阅判断
不是事实性缺陷，仅是更稳妥或更低成本的实施建议。

---

## 3. 已验证事实（按证据等级）

## 3.1 A级事实：`g.app_logger` 当前请求链路下确实未赋值

### 源码证据
`web/bootstrap/factory.py::_open_db()`（L262-294）中仅设置：

- `g.db`
- `g.op_logger`

并**未设置** `g.app_logger`。

相关片段：

```python
if "db" not in g:
    g.db = get_connection(app.config["DATABASE_PATH"])
    g.op_logger = OperationLogger(g.db, logger=app.logger)
```

### 搜索证据
全局搜索：
- `g.app_logger =` → 在 `web/` 下返回 **0 条结果**
- `setattr(g, "app_logger"` → 返回 **0 条结果**

### runtime 证据
做了最小验证：

- `from app import create_app`
- `app = create_app()`
- `with app.test_request_context('/scheduler/'):`
- `app.preprocess_request()`

实际输出：

- `has_db True`
- `has_op_logger True`
- `has_app_logger False`

### 结论
这是**已验证事实**：

> 当前生产请求链路下，`getattr(g, "app_logger", None)` 会返回 `None`。

---

## 3.2 A级事实：现有大量 route 确实把 `None` logger 传给 service

### 源码证据
全局搜索 `logger=getattr(g, "app_logger", None)`，在 `web/routes/` 下找到 **48 处** 调用。

代表性位置包括：

- `web/routes/scheduler_batches.py`
- `web/routes/scheduler_batch_detail.py`
- `web/routes/scheduler_week_plan.py`
- `web/routes/scheduler_run.py`
- `web/routes/process_excel_suppliers.py`
- `web/routes/dashboard.py`
- 等

### runtime 证据
对 `web/routes/scheduler_batches.py::batches_page()` 做了最小 stub 验证，分别拦截：

- `BatchService(...)`
- `ConfigService(...)`
- `ScheduleHistoryQueryService(...)`

在请求上下文只设置 `g.db` / `g.op_logger` 时，捕获结果为：

- `batch_logger_is_none True`
- `config_logger_is_none True`
- `hist_logger_is_none True`

### 结论
这也是**已验证事实**：

> 当前 `logger=getattr(g, "app_logger", None)` 这套 route 写法，在 runtime 下确实会把 `None` 传给 service。

---

## 3.3 A级事实：service 层新增 logger 调用必须做 guard

### 证据 1：现有测试大量直接实例化 service，未传 logger

例如：

- `tests/regression_external_group_service_strict_mode_blank_days.py`
  - `svc = ExternalGroupService(conn)`
- `tests/regression_external_group_service_merge_mode_case_insensitive.py`
  - `svc = ExternalGroupService(conn)`
- `tests/regression_batch_import_unchanged_no_rebuild.py`
  - `svc = BatchService(conn)`
- `tests/regression_excel_failure_semantics_contracts.py`
  - `part_svc = PartService(conn)`
  - `batch_svc = BatchService(conn)`

### 证据 2：当前工程已有 guard 模式可复用
`core/services/process/part_service.py::_coerce_external_default_days()` 中已有成熟模式：

```python
if self.logger:
    try:
        self.logger.warning(message)
    except Exception:
        pass
```

### 结论
这条不是建议，而是**硬约束**：

> 本轮凡是在 service 层新增 `self.logger.warning(...)` 的地方，都必须使用 `if self.logger:` guard。

否则将直接引入回归风险。

---

## 3.4 B级事实：`ExternalGroupService._apply_separate_mode()` compatible fallback 仍完全静默

### 源码证据
`core/services/process/external_group_service.py`（L127-139）：

```python
for op in ops:
    d = per_op_days.get(int(op.seq))
    dv = self._normalize_float(d)
    seq = int(op.seq)
    if dv is None or dv <= 0:
        if strict_mode:
            ...
            raise ValidationError(...)
        dv = 1.0
    self.op_repo.update(part_no, seq, {"ext_days": float(dv)})
```

### 结论
原计划对此处现状的判断**成立**：

- compatible mode 下非法值回退为 `1.0`
- 无 logger / warning / counter / 留痕

---

## 3.5 B级事实：batch Excel import 链路确实未贯通 strict_mode

### 源码证据
#### `core/services/scheduler/batch_service.py`
`import_from_preview_rows()` 当前无 `strict_mode` 参数。

#### `core/services/scheduler/batch_excel_import.py`
`import_batches_from_preview_rows()` 当前无 `strict_mode` 参数。

在 `_apply_row_no_tx()` 内：

```python
if auto_generate_ops:
    svc.create_batch_from_template_no_tx(
        ...,
        rebuild_ops=True,
    )
```

调用 `create_batch_from_template_no_tx()` 时**未传 `strict_mode`**。

### 结论
原计划关于 F-007 的判断**成立**。

---

## 3.6 B级事实：`scheduler_excel_batches.py` 当前既没 strict_mode helper，也没传 logger

### 源码证据
`web/routes/scheduler_excel_batches.py`：

- 无 `_strict_mode_enabled()` helper
- 4 处 `BatchService(...)` 均只传 `op_logger`
  - L144
  - L195
  - L273
  - L411
- `_render_excel_batches_page()` 当前无 strict_mode 参数

### 结论
这条**事实成立**。

但它对应的审查结论需要纠偏，见后文第 4 节。

---

## 3.7 B级事实：`excel_import_batches.html` 当前不是复用通用组件的页面

### 源码证据
`templates/scheduler/excel_import_batches.html` 是独立模板，包含自定义：

- “导入选项”卡片
- 自定义 confirm form
- 自定义 preview form

且当前文件中**没有**：

```jinja2
{% include "components/excel_import.html" with context %}
```

对比：
`templates/scheduler/excel_import_calendar.html` 明确 include 了通用组件：

```jinja2
{% include "components/excel_import.html" with context %}
```

### 结论
原审查中“当前状态下该页面不是通过组件复用 strict_mode 插槽”的事实**成立**。

但“因此必须直接改自定义模板”不是事实，只是一个实现建议。

---

## 3.8 B级事实：`config_snapshot` 已有契约测试覆盖，缺的是异常路径覆盖

### 现有测试证据
至少已有以下测试覆盖：

- `tests/regression_schedule_summary_v11_contract.py`
  - 断言 `summary_schema_version == "1.1"`
  - 断言 `algo.config_snapshot.objective` 等关键字段
- `tests/regression_dict_cfg_contract.py`
  - 断言 `config_snapshot.freeze_window_enabled`
  - `config_snapshot.freeze_window_days`
  - `config_snapshot.auto_assign_enabled`
  - 并校验 dict cfg 与 object cfg 摘要一致

### 结论
因此，原审查报告中的：

> “缺 `_config_snapshot_dict()` 专项 regression”

表述不准确。

更准确的说法应是：

> **`config_snapshot` 主契约已有覆盖；若本轮修改 `_config_snapshot_dict()` 的异常分支，则应新增针对异常路径的最小 regression。**

---

## 4. 对原审查结论的逐条纠偏

## 4.1 原 R1-BLOCK-1：问题事实成立，但“必须新增 Phase 0”结论过强

### 原结论的问题
原报告将以下两件事混在了一起：

1. **事实**：`g.app_logger` 当前未赋值；
2. **建议**：必须新增 Phase 0，在 `factory.py::_open_db()` 中补 `g.app_logger = current_app.logger`。

第 1 条是事实，第 2 条不是唯一可推出的结论。

### 为什么“必须新增 Phase 0”过强？
因为当前工程里已存在一条成熟且已被大量使用的 logger 路径：

- `current_app.logger`

并且 `factory.py` 已将：

```python
app.logger.handlers = app_logger.logger.handlers
app.logger.setLevel(app_logger.logger.level)
```

即：

> `current_app.logger` 已经绑定到了工程当前使用的 AppLogger handler/level。

### 更准确的结论
应改写为：

> `g.app_logger` 当前为空，这一事实成立；
> 但对本计划而言，更小、更稳的修复方式是：
> - 在 `process_parts.py` / `scheduler_excel_batches.py` 直接传 `current_app.logger`；或
> - 全局补 `g.app_logger`；
> 二者都可行，**不应把全局补 g.app_logger 写成当前计划的唯一前置步骤**。

### 修正后的级别
- 问题事实：**HIGH（计划中 proposed 写法会失效）**
- 修复建议：**不强制 Phase 0，全局与局部两种方案并存**

---

## 4.2 原 R1-MEDIUM-1：事实成立，但“必须直接改模板”属于实现建议

### 原报告成立的部分
- `excel_import_batches.html` 当前确实不是 include 通用组件的页面
- 因而原计划中“复用组件 strict_mode 插槽”的表述不够精确

### 原报告过强的部分
原报告把这进一步写成：

> “strict_mode 控件必须直接加到自定义模板中”

这个“必须”无法从事实推出。

### 更准确的结论
应改为：

> 当前页面是自定义模板；若不做模板重构，最短路径是在该模板内补 strict_mode 字段。  
> 但是否直接改模板，还是做局部重构 / 抽 macro / 重新 include 组件，属于实现选择，不是事实性约束。

### 修正后的级别
- 级别：**LOW / docs**
- 性质：**计划文案精度问题，不是阻塞项**

---

## 4.3 原 R2-MEDIUM-1：问题存在，但“计划完全漏掉”不准确

### 原报告成立的部分
`scheduler_excel_batches.py` 当前确实没有给 `BatchService(...)` 传 logger。

### 但原报告忽略了原计划已有 B3
原计划中已有：

### `B3. route 层和 service 层 logger 注入一致性收敛`

其中明确提到：

- `BatchService(...)`
- `scheduler_excel_batches.py`

也就是说：

> 原计划并不是“完全漏掉这件事”，而是“提到了，但没有收敛为强制动作”。

### 更准确的结论
应改写为：

> `scheduler_excel_batches.py` 的 logger 传递问题存在；原计划 B3 已部分覆盖该方向，但未把它落成显式的必改清单。建议本轮把它从“顺手检查”提升为“如果新增日志，相关 route 必须显式传 logger”。

### 修正后的级别
- 级别：**LOW-MEDIUM**
- 性质：**收敛项，不应当作为新的阻塞性发现**

---

## 4.4 原 R2-LOW-1：不是事实发现，更像计划澄清建议

### 原报告的问题
“`_config_snapshot_dict()` 修复范围模糊”更多是在评价计划写法是否明确，而不是在报告一个代码缺陷。

### 更准确的处理方式
这类内容应归入：

- **计划澄清建议**
- **实施前决策点**

而不应与真正的代码问题并列为正式 finding。

### 修正后的定位
- 不列为核心缺陷
- 保留为实施备注：
  > 若本轮要改 `_config_snapshot_dict()`，建议明确选择“仅补日志”还是“做结构化增强”

---

## 4.5 原 R3-MEDIUM-1：T1 依赖全局 logger 修复 —— 不成立

### 原报告原话的问题
原报告说：

> T1（compatible mode logger fallback）测试依赖 R1-BLOCK-1 修复

这条**不成立**。

### 为什么不成立？
T1 是 service 级 regression test，完全可以这样写：

```python
svc = ExternalGroupService(conn, logger=mock_logger)
```

它不依赖：

- `g.app_logger`
- route 注入
- `factory.py::_open_db()`

### 更准确的结论
应改为：

> T1 不依赖全局 logger 链路修复；只需在测试中显式注入 mock logger 即可。

### 处理方式
- 删除“依赖 R1-BLOCK-1”这一说法
- 改为测试实现备注

---

## 4.6 原 R3-LOW-1：应从“缺专项 regression”改为“缺异常路径 regression”

### 原报告的问题
“缺 `_config_snapshot_dict()` 专项 regression”说得太宽，容易误导成“整体无测试覆盖”。

### 更准确的结论
应改为：

> `config_snapshot` 主契约已有测试覆盖；若本轮修改 `_config_snapshot_dict()` 的异常路径，应补一条针对 `to_dict()` 抛异常 / `getattr()` 抛异常 的最小 regression。

---

## 5. 纠偏后的三轮审查结论

## 第一轮：源码链结论（修正版）

### 仍然成立的部分
- `ExternalGroupService._apply_separate_mode()` compatible fallback 确实完全静默
- batch Excel import strict_mode 缺口确实存在
- `schedule_summary.py` 观测链残留确实存在
- `scheduler_excel_batches.py` 当前未传 logger / 未贯通 strict_mode

### 需要修正的部分
- 不应把 `g.app_logger` 问题直接升级为“必须全局 Phase 0”
- 不应把模板现状升级成“只能直接改自定义模板”

---

## 第二轮：契约兼容性结论（修正版）

### 成立的部分
- compatible mode 保留 `1.0` 行为的兼容性策略正确
- `strict_mode: bool = False` 的签名扩展向后兼容
- `_extract_freeze_warnings()` 改为逐项容错不会破坏 summary schema

### 需要修正的部分
- `scheduler_excel_batches.py` 的 logger 问题属于“原计划收敛不够硬”，不是“全新漏点”
- `_config_snapshot_dict()` 项更适合作为澄清项，不应上升成正式缺陷

---

## 第三轮：测试覆盖结论（修正版）

### 成立的部分
- T2 / T3 / T4 的测试设计方向正确
- 现有 regression 回归清单整体完整

### 需要修正的部分
- T1 可独立实现，不依赖全局 logger 注入链修复
- `_config_snapshot_dict()` 不是“无专项覆盖”，而是“异常路径无专项覆盖”

---

## 6. 修正后的最小结论集（建议作为正式审查结论）

## 6.1 应保留的正式结论

### F-1（HIGH）
原计划中的 logger 注入写法 **`logger=getattr(g, "app_logger", None)` 不应直接照抄执行**。  
原因：当前 runtime 下该表达式会得到 `None`。

### F-2（HIGH）
本轮 service 层若新增 logger 调用，**必须使用 `if self.logger:` guard**。  
原因：现有测试与脚本大量直接实例化 service 且未传 logger。

### F-3（MEDIUM）
batch Excel import strict_mode 缺口判断成立，应继续按原计划修复。

### F-4（MEDIUM）
`scheduler_excel_batches.py` 的 logger 传递问题存在，建议将原计划 B3 的“顺手检查”升级为显式动作。

---

## 6.2 应降级为备注 / 澄清的项

### N-1（LOW / docs）
模板当前不是复用通用组件；“直接改模板”只是最短路径，不是唯一方案。

### N-2（LOW / clarification）
`_config_snapshot_dict()` 本轮到底只补日志还是做结构化增强，需要在实施前明确。

### N-3（LOW / test note）
若修改 `_config_snapshot_dict()` 异常路径，应补最小 regression。

---

## 6.3 应删除的原结论

以下原结论不建议保留：

1. **“必须新增 Phase 0：先在 factory.py 里补 g.app_logger”**
   - 过强
   - 属于修复方案选择，不是唯一可推出结论

2. **“T1 测试依赖 R1-BLOCK-1 修复”**
   - 不成立
   - T1 可通过注入 mock logger 独立完成

---

## 7. 对原计划的最小修订建议（修正版）

## 7.1 A1-2 route 层补 logger 注入 —— 改写建议

原计划写法：

```python
logger=getattr(g, "app_logger", None)
```

建议改写为以下二选一：

### 方案 A：局部修复（推荐，最小改动）
- `web/routes/process_parts.py`：新增 `current_app` import，传 `logger=current_app.logger`
- `web/routes/scheduler_excel_batches.py`：该文件已 import `current_app`，直接传 `logger=current_app.logger`

### 方案 B：全局修复（可选，范围扩大）
- 在 `factory.py::_open_db()` 中补 `g.app_logger = current_app.logger`
- 然后保留原计划的 `getattr(g, "app_logger", None)` 风格

### 对当前计划的推荐
**优先方案 A，不强制新增全局 Phase 0。**

---

## 7.2 A1 service 层日志 —— 改写建议

明确写入计划：

> 所有新增 logger 调用必须使用 guard：

```python
if self.logger:
    try:
        self.logger.warning(...)
    except Exception:
        pass
```

---

## 7.3 A2-1 模板改动 —— 改写建议

原计划中“复用组件 strict_mode 插槽”应改为：

> `templates/scheduler/excel_import_batches.html` 当前为自定义模板。若不做模板重构，最短路径是在该模板中直接补 strict_mode checkbox / hidden field；若愿意做局部模板重构，也可复用组件能力。

---

## 7.4 B3 logger 收敛 —— 改写建议

将原计划的：

> “顺手检查 / 如涉及新日志则同步注入 logger”

改为更可执行的要求：

> **若本轮修改的 route 会触发新增 service 日志，则相关 service 构造必须显式传 logger。**

特别是：

- `process_parts.py::set_group_mode()`
- `scheduler_excel_batches.py` 中所有相关 `BatchService(...)` 构造

---

## 7.5 测试计划 —— 改写建议

### T1
保留，但改成：

> 在测试中显式注入 `mock_logger`，不依赖 Flask `g.app_logger`。

### `_config_snapshot_dict()`
保留备注：

> 仅当本轮真的修改异常路径时，再补专项 regression。

---

## 8. 修正后的最终判定

### 判定
> **有条件接受，但应先修正实施路径，而不是扩大前置范围。**

### 更准确的执行顺序

```text
Phase A：修 ExternalGroupService compatible fallback + route/service 层安全日志写法 + T1
    |
Phase B：补 batch Excel strict_mode 贯通 + 必要的 logger 显式传递 + T2
    |
Phase C：补 schedule_summary 观测链残留 + T3/T4
    |
Phase D：复核 + 回归
```

### 不再坚持的旧结论
- 不再坚持“必须先做全局 Phase 0”
- 不再坚持“T1 依赖全局 logger 修复”

---

## 9. 证据文件索引

### A级事实证据
- `web/bootstrap/factory.py` L262-294
- `web/bootstrap/factory.py` L216-224
- `web/routes/scheduler_batches.py` L25-67
- `tests/regression_scheduler_route_enforce_ready_tristate.py` L40-76
- 最小 runtime 验证：
  - `create_app()` + `app.test_request_context('/scheduler/')` + `app.preprocess_request()`
  - 输出：`has_app_logger False`
- 最小 route runtime 验证：
  - stub `BatchService/ConfigService/ScheduleHistoryQueryService`
  - 输出：`batch_logger_is_none True` / `config_logger_is_none True` / `hist_logger_is_none True`

### B级事实证据
- `core/services/process/external_group_service.py` L127-139
- `web/routes/process_parts.py` L207-235
- `core/services/scheduler/batch_service.py` L389-405
- `core/services/scheduler/batch_excel_import.py` L10-106
- `core/services/scheduler/batch_template_ops.py` L75-134
- `web/routes/scheduler_excel_batches.py` L1-443
- `core/services/scheduler/schedule_summary.py` L37-85 / L280-327 / L352-362
- `templates/scheduler/excel_import_batches.html` L21-80
- `templates/components/excel_import.html` L38-70
- `templates/scheduler/excel_import_calendar.html` L1-25
- `core/services/process/part_service.py` L81-110
- `tests/regression_external_group_service_strict_mode_blank_days.py`
- `tests/regression_external_group_service_merge_mode_case_insensitive.py`
- `tests/regression_batch_import_unchanged_no_rebuild.py`
- `tests/regression_schedule_summary_v11_contract.py`
- `tests/regression_dict_cfg_contract.py`

---

## 10. 一句话结论

> 原计划主方向成立；原审查报告中最重要的事实判断——`g.app_logger` 当前链路为空——也成立。  
> 但“因此必须先做全局 Phase 0”这一结论过强；更稳妥的修正是：**局部改用 `current_app.logger` + service 日志 guard + 保持本轮修复聚焦。**
