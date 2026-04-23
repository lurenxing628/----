# web/web_new_test remediation implementation plan for findings F002-F007
- Date: 2026-04-02
- Overview: Step-by-step remediation plan derived from the finalized re-verification review, with exact file/function targets, test strategy, sequencing, and acceptance criteria.
- Status: in_progress

## Review Scope
# web/web_new_test 修复实施计划（F002-F007）

- **Date**: 2026-04-02
- **Source of truth**: `.limcode/review/web_deep_review_reverify.md`
- **Current review conclusion**: `overallDecision: conditionally_accepted`
- **Current active findings only**: `F002`, `F003`, `F004`, `F005`, `F006`, `F007`
- **Implementation scope**:
  - `web/`
  - `web_new_test/`
  - 必要时允许最小范围触达 `core/services/scheduler/` 与 `core/services/common/`，但只为消除当前 active findings 的根因
- **Non-goals / 本轮不要顺手改的内容**:
  - 不重新打开已关闭的 `F001`、`F008`、`F009`、`F010`
  - 不改 `web_new_test/static/css/style.css:160-165` 的 `:has()` 兼容路径（当前 `Chrome 109+` 假设成立）
  - 不把 `F003` 的容错改成“summary 脏了就整页 500”
  - 不改已经被回归验证接受的 strict-mode / baseline-guard 行为
  - 不做无关重构、无关命名清洗、无关 UI 改版

---

## 1. 目标与修复原则

本轮修复的目标不是“重写 web 层”，而是把已经在 re-verification 中确认的 **6 个 active findings** 修干净，并保持以下原则：

1. **真实 bug 不再被静默掩盖**
2. **兼容性容错仍保留，但必须有 telemetry / degraded-state signaling**
3. **批量操作失败必须可诊断，不能只有 ID 没有原因**
4. **配置异常不能再静默改写成默认值继续影响导入/页面行为**
5. **修复后必须用现有与新增测试锁住行为**
6. **保持 Python 3.8 / Win7 / PyInstaller 兼容约束，不引入额外运行时风险**

---

## 2. 修复优先级与建议实施顺序

### 2.1 推荐总顺序

1. `F005` —— 真实用户可见 masking bug，优先级最高
2. `F006` —— 多处 bulk route 吞异常，影响排障与用户反馈
3. `F007` —— `holiday_default_efficiency` 读路径静默回退，且会影响 Excel preview/confirm
4. `F002` —— V2 render fallback 无运行期 warning / diagnostics
5. `F003` —— summary 解析失败无 telemetry
6. `F004` —— 清理 `compare_digest()` 异常时退化到 `==` 的不必要 fallback

### 2.2 优先级摘要表

| Priority | Finding | 问题类型 | 主要文件 |
|---|---|---|---|
| P0 | `F005` | 真实状态掩盖 | `web/routes/equipment_pages.py`, `templates/equipment/list.html` |
| P0 | `F006` | 批量操作异常吞没 | `web/routes/equipment_pages.py`, `web/routes/personnel_pages.py`, `web/routes/scheduler_batches.py`, `web/routes/process_parts.py`, `web/routes/system_backup.py` |
| P0 | `F007` | 配置静默回退 | `core/services/scheduler/config_service.py`, `web/routes/scheduler_calendar_pages.py`, `web/routes/scheduler_excel_calendar.py`, `web/routes/personnel_calendar_pages.py`, `web/routes/personnel_excel_operator_calendar.py` |
| P1 | `F002` | V2 render fallback 无运行期告警 | `web/ui_mode.py`, `web/error_handlers.py`, 可选 `templates/base.html`, `web_new_test/templates/base.html` |
| P1 | `F003` | summary 解析失败无 telemetry | `web/routes/dashboard.py`, `web/routes/scheduler_batches.py`, `web/routes/system_history.py` |
| P2 | `F004` | `compare_digest()` 异常时错误退化到 `==` | `web/routes/excel_utils.py` |

---

## 3. 实施前准备（必须先做）

### 3.1 建立修复分支

- [ ] 新建分支，例如：`fix/web-reverify-f002-f007`
- [ ] 在分支说明或首个 commit message 写明来源：`.limcode/review/web_deep_review_reverify.md`

### 3.2 跑一遍 baseline，确认当前状态可复现

先不要改代码，先跑这些已有回归，确认基线是绿的：

```bat
python tests/regression_dashboard_overdue_count_tolerance.py
python tests/regression_excel_preview_confirm_baseline_guard.py
python tests/regression_excel_preview_confirm_extra_state_guard.py
python tests/regression_scheduler_reject_nonfinite_and_invalid_status.py
python tests/regression_scheduler_apply_preset_reject_invalid_numeric.py
python -m pytest tests/test_ui_mode.py -q
```

可选再补：

```bat
python tests/regression_system_health_route.py
python tests/regression_system_logs_delete_no_clamp.py
```

### 3.3 实施原则清单

- [ ] 不要把兼容性容错整体删掉；该保活的页面仍要保活
- [ ] 要把“静默”改成“可见 / 可记录 / 可诊断”
- [ ] 不要引入 Python 3.9+ 才有的语法或依赖，保持 **Python 3.8**
- [ ] 不要引入会影响 Win7 / PyInstaller 的新依赖
- [ ] 不要顺手改 `web_new_test/` 的布局/CSS 行为，除非是 `F002` 的轻量诊断埋点
- [ ] 每个 finding 修完后先跑对应测试，再进入下一个 finding
- [ ] 建议按 finding 分 commit，不要一次性混成一个超大提交

---

## 4. 分 finding 详细实施计划

---

## 4.1 修复 `F005`：`_load_active_downtime_machine_ids()` 不能再把查询失败伪装成“没有计划停机”

### 4.1.1 当前问题

当前调用链：

`equipment.list_page()`
-> `web/routes/equipment_pages.py:_load_active_downtime_machine_ids()`
-> `MachineDowntimeQueryService.list_active_machine_ids_at(now_str)`
-> `_build_machine_list_rows(..., downtime_now_set=...)`

当前代码位置：

- `web/routes/equipment_pages.py:61-67`
- `web/routes/equipment_pages.py:84-114`
- `web/routes/equipment_pages.py:134-144`

当前行为：**任何异常都返回 `set()`**。

后果：设备列表页会把“停机状态查询失败”误显示为“当前无计划停机”，从而把本应显示为 `停机（计划）` 的设备，退回成普通 `MachineStatus` 文案。这是 **真实状态掩盖**，不是单纯 telemetry 问题。

### 4.1.2 目标行为

修完后应变成：

1. 停机查询成功：行为保持不变
2. 停机查询失败：
   - 页面仍然可打开
   - 必须记录异常日志
   - 必须向模板传递显式 degraded-state 标记
   - 页面必须提示：当前计划停机状态读取失败，状态列可能不完整
   - 不能再把失败和“没有停机”混为一谈

### 4.1.3 需要改的文件

**必改**
- `web/routes/equipment_pages.py`
- `templates/equipment/list.html`

**可选**
- 若已有统一 warning/banner 组件可复用，则仅接入；否则直接在页面加轻量 banner

### 4.1.4 实施步骤

#### 步骤 1：修改导入

在 `web/routes/equipment_pages.py` 顶部增加 `current_app` 导入。

当前：

```python
from flask import flash, g, redirect, request, url_for
```

应改为包含 `current_app`。

#### 步骤 2：把 `_load_active_downtime_machine_ids()` 改成结构化返回

不要继续只返回一个 `set`。

推荐返回结构：

```python
{
    "machine_ids": set(...),
    "degraded": False,
}
```

异常时返回：

```python
{
    "machine_ids": set(),
    "degraded": True,
    "reason": "query_failed",
}
```

异常分支必须加：

```python
current_app.logger.exception("设备列表页读取计划停机状态失败（now=%s）", now_str)
```

#### 步骤 3：修改 `list_page()` 对该结构的消费方式

不要再直接写：

```python
downtime_now_set = _load_active_downtime_machine_ids()
```

改成类似：

```python
downtime_state = _load_active_downtime_machine_ids()
downtime_now_set = downtime_state["machine_ids"]
downtime_overlay_degraded = downtime_state["degraded"]
```

并把 `downtime_overlay_degraded` 传给模板。

#### 步骤 4：在 `templates/equipment/list.html` 增加显式 warning

建议增加只在 degraded 时展示的页面级提示，例如：

> 计划停机状态读取失败，当前页面的“状态”列可能未展示“停机（计划）”覆盖状态，请查看日志并稍后刷新。

建议优先用**页面内 banner**，因为这是“当前页状态不完整”，不是普通一次性 flash。

#### 步骤 5：不要重写 `_build_machine_list_rows()` 主逻辑

- [ ] 保持 `machine.machine_id in downtime_now_set` 时显示 `停机（计划）`
- [ ] 本次只解决“查询失败不能伪装成无停机”
- [ ] 不把设备状态整段逻辑一起重构

### 4.1.5 建议新增测试

**新增**：`tests/test_equipment_page_downtime_overlay_degraded.py`

测试点：

- [ ] 正常查询时，页面仍显示 `停机（计划）`
- [ ] monkeypatch `MachineDowntimeQueryService.list_active_machine_ids_at(...)` 抛异常
- [ ] 页面返回 `200`
- [ ] HTML 中出现 degraded warning 文案
- [ ] 页面不会 500
- [ ] 日志中存在 `logger.exception(...)`

### 4.1.6 验收标准

- [ ] 设备页在停机查询失败时不再静默显示为正常
- [ ] 运维/测试人员仅看页面就能知道当前状态不完整
- [ ] 日志可定位异常堆栈
- [ ] 未影响正常列表渲染和分页

---

## 4.2 修复 `F006`：批量操作路由不能再吞掉逐项异常

### 4.2.1 当前问题

受影响位置：

- `web/routes/equipment_pages.py:293-307`
- `web/routes/equipment_pages.py:321-335`
- `web/routes/personnel_pages.py:203-217`
- `web/routes/personnel_pages.py:231-245`
- `web/routes/scheduler_batches.py:199-213`
- `web/routes/process_parts.py:157-171`
- `web/routes/system_backup.py:147-183`

当前共同问题：

- 成功多少、失败多少会显示
- 但失败原因只剩 ID
- `AppError.message` 没保留下来
- unexpected exception 没有统一 `current_app.logger.exception(...)`
- 用户无法区分“业务规则拒绝”和“代码/环境异常”

### 4.2.2 目标行为

修完后要求：

1. 批量操作继续支持部分成功、部分失败
2. 每个失败项至少能看到：
   - 对象 ID
   - 失败原因（业务错误用真实 `AppError.message`，未知错误用通用 message）
3. unexpected exception 必须记录堆栈日志
4. 现有 redirect + flash 交互风格保持不变，不要突然改成整体 500

### 4.2.3 总体实施策略

不要一上来做大重构。推荐先把 `web/routes/scheduler_batches.py:bulk_delete_batches()` 做成参考实现，再平移到其他 bulk route。

统一处理模式建议为：

```python
except AppError as e:
    failed.append(str(item_id))
    failed_details.append(f"{item_id}: {e.message}")
except Exception:
    current_app.logger.exception("...", item_id)
    failed.append(str(item_id))
    failed_details.append(f"{item_id}: 内部错误，请查看日志")
```

最终 flash 建议保留两层：

1. 汇总：
   - `批量删除完成：成功 X，失败 Y。`
2. 明细（最多展示 10 个）：
   - `删除失败（最多展示 10 个）：B001: 已被排程引用；B003: 内部错误，请查看日志`

---

### 4.2.4 `web/routes/scheduler_batches.py`

#### 当前问题点

- `web/routes/scheduler_batches.py:199-213`
- 该文件已经导入 `current_app` 与 `AppError`，适合作为首个参考实现

#### 实施步骤

- [ ] 在 `bulk_delete_batches()` 中把 `except Exception:` 拆成：
  - `except AppError as e:`
  - `except Exception:`
- [ ] 增加 `failed_details: List[str] = []`
- [ ] unexpected exception 增加：

```python
current_app.logger.exception("批量删除批次失败（batch_id=%s）", bid)
```

- [ ] 保留现有 summary flash
- [ ] 第二条 flash 从“只展示 ID”改成“展示 `ID: reason`”

---

### 4.2.5 `web/routes/equipment_pages.py`

#### 当前问题点

- `bulk_set_status()`：`web/routes/equipment_pages.py:293-307`
- `bulk_delete()`：`web/routes/equipment_pages.py:321-335`

#### 实施步骤

- [ ] 顶部导入补上 `current_app`
- [ ] `bulk_set_status()` 中：
  - `AppError` 分支保留业务 message
  - unexpected exception 记录：

```python
current_app.logger.exception("批量设置设备状态失败（machine_id=%s, status=%s）", mid, status)
```

- [ ] `bulk_delete()` 中：
  - `AppError` 分支保留业务 message
  - unexpected exception 记录：

```python
current_app.logger.exception("批量删除设备失败（machine_id=%s）", mid)
```

- [ ] 现有“常见原因：被批次工序/排程引用，请改为停用。”这句不要再覆盖具体原因。若已能展示 `AppError.message`，则让具体原因优先。

---

### 4.2.6 `web/routes/personnel_pages.py`

#### 当前问题点

- `bulk_set_status()`：`web/routes/personnel_pages.py:203-217`
- `bulk_delete()`：`web/routes/personnel_pages.py:231-245`

#### 实施步骤

- [ ] 顶部导入补上 `current_app`
- [ ] `bulk_set_status()` unexpected exception：

```python
current_app.logger.exception("批量设置人员状态失败（operator_id=%s, status=%s）", oid, status)
```

- [ ] `bulk_delete()` unexpected exception：

```python
current_app.logger.exception("批量删除人员失败（operator_id=%s）", oid)
```

- [ ] 第二条 flash 改成带 reason 的样式

---

### 4.2.7 `web/routes/process_parts.py`

#### 当前问题点

- `web/routes/process_parts.py:157-171`
- 文件已导入 `current_app`，改动较小

#### 实施步骤

- [ ] 在 `bulk_delete_parts()` 中拆成 `AppError` 与 unexpected exception 两层
- [ ] unexpected exception：

```python
current_app.logger.exception("批量删除零件失败（part_no=%s）", pn)
```

- [ ] 第二条 flash 改成 `part_no: reason`

---

### 4.2.8 `web/routes/system_backup.py`

#### 当前问题点

- `web/routes/system_backup.py:147-183`
- 该路由不仅涉及 `AppError`，还包含：
  - 非法文件名
  - 文件不存在
  - `os.remove(...)` 失败

#### 推荐策略

不要硬套 `AppError` 模式，直接拆成 3 类明确原因：

1. `_validate_backup_filename(raw)` 失败
   - `"{raw}: 文件名不合法"`
2. 文件不存在
   - `"{fn}: 文件不存在"`
3. `os.remove(...)` 抛异常
   - `"{fn}: 删除失败，请查看日志"`
   - 同时记录 `current_app.logger.exception(...)`

#### 实施步骤

- [ ] 增加 `failed_details: List[str] = []`
- [ ] `_validate_backup_filename(raw)` 失败时不要只记 ID
- [ ] `os.remove(...)` 异常时增加：

```python
current_app.logger.exception("批量删除备份失败（filename=%s）", fn)
```

- [ ] 保留现有 `g.op_logger.info(...)` 汇总日志，但不要把它当成异常堆栈日志替代品

### 4.2.9 建议新增测试

**新增**：`tests/test_bulk_route_error_visibility.py`

建议覆盖：

- [ ] `scheduler_batches.py`：业务异常 message 可见，unexpected exception 有日志
- [ ] `equipment_pages.py`：`bulk/status` 与 `bulk/delete`
- [ ] `personnel_pages.py`：`bulk/status` 与 `bulk/delete`
- [ ] `process_parts.py`：`bulk/delete`
- [ ] `system_backup.py`：非法文件名 / 文件不存在 / 删除异常 三类 reason

### 4.2.10 验收标准

- [ ] bulk route 仍支持部分成功
- [ ] 用户看到的失败样本不再只有 ID
- [ ] `AppError.message` 被保留
- [ ] unexpected exception 都有 stack trace
- [ ] redirect 行为不变

---

## 4.3 修复 `F007`：`holiday_default_efficiency` 不能再在读路径静默坍缩为 `0.8`

### 4.3.1 当前问题

当前受影响位置：

- `web/routes/scheduler_calendar_pages.py:17-24`
- `web/routes/scheduler_excel_calendar.py:123-129`
- `web/routes/scheduler_excel_calendar.py:241-247`
- `web/routes/personnel_calendar_pages.py:35-43`
- `web/routes/personnel_excel_operator_calendar.py:93-99`
- `web/routes/personnel_excel_operator_calendar.py:221-226`

写入路径已经有校验：

- `core/services/scheduler/config_service.py:443-460`

也就是说，**写入**已经会拒绝非有限值/非正数；问题在于 **读取** 时，如果 DB 中已有脏值、手工改坏、旧数据残留，route 层会静默回到 `0.8`。

这不仅影响页面展示，还会影响：

- Excel preview 的 `extra_state`
- Excel confirm 的 baseline 校验
- 假期空效率行的导入默认值

### 4.3.2 目标行为

修完后分两类处理：

#### A. 页面 GET（只读展示）

例如：
- `/scheduler/calendar`
- `/personnel/<operator_id>/calendar`

目标：
- 页面仍可打开，避免纯展示路径直接挂掉
- 但必须：
  - 有 warning 日志
  - 有显式 degraded-state 标记
  - 页面可见当前默认值是“临时 fallback”，而不是“配置正常”

#### B. Excel preview / confirm（会影响导入行为）

例如：
- `scheduler_excel_calendar.py`
- `personnel_excel_operator_calendar.py`

目标：
- **不允许**继续静默用 `0.8` 导入
- 配置非法时应显式拒绝并提示先修复配置

### 4.3.3 根修策略：把“读取并校验 holiday_default_efficiency”收口到 `ConfigService`

### 4.3.4 需要改的文件

**必改**
- `core/services/scheduler/config_service.py`
- `web/routes/scheduler_calendar_pages.py`
- `web/routes/scheduler_excel_calendar.py`
- `web/routes/personnel_calendar_pages.py`
- `web/routes/personnel_excel_operator_calendar.py`

**强烈建议一并对齐**
- `core/services/scheduler/calendar_admin.py`
- `core/services/common/excel_validators.py`

### 4.3.5 实施步骤

#### 步骤 1：给 `ConfigService` 新增严格读取方法

在 `core/services/scheduler/config_service.py` 新增例如：

```python
def get_holiday_default_efficiency(self) -> float:
    raw = self.get("holiday_default_efficiency", default=self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
    v = float(parse_finite_float(raw, field="假期工作效率", allow_none=False) or 0.0)
    if v <= 0:
        raise ValidationError("假期工作效率必须大于 0。", field="假期工作效率")
    return float(v)
```

关键点：
- 不要在该方法里静默回到 `0.8`
- 让脏配置显式变成一个受控错误

#### 步骤 2：修改 `web/routes/scheduler_calendar_pages.py` 与 `web/routes/personnel_calendar_pages.py`

这两个 GET 页面建议采用 **软降级 + 明示 warning**：

- [ ] 调用 `cfg_svc.get_holiday_default_efficiency()`
- [ ] `except ValidationError` 时：
  - 记录 warning 日志
  - 页面继续渲染
  - `hde` 临时使用 `ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY`
  - 同时设置：
    - `holiday_default_efficiency_degraded = True`
    - `holiday_default_efficiency_warning = "配置非法，当前页面临时按 0.8 展示，请先到排产参数中修复"`

#### 步骤 3：修改模板提示

在以下模板增加显式提示：

- `templates/scheduler/calendar.html`
- `templates/personnel/calendar.html`

建议文案：

> 配置项 `holiday_default_efficiency` 当前非法，页面已临时按 `0.8` 展示默认值；请先到排产参数页修复配置，再继续依赖该默认值进行操作。

这样页面仍保活，但不再 silent。

#### 步骤 4：修改 `web/routes/scheduler_excel_calendar.py`

受影响函数：

- `excel_calendar_preview()`
- `excel_calendar_confirm()`

这里建议改成 **硬拒绝**：

- [ ] 不再使用：

```python
try:
    hde = float(cfg_svc.get("holiday_default_efficiency", default=0.8) or 0.8)
    ...
except Exception:
    hde = 0.8
```

- [ ] 改为调用严格 getter
- [ ] 如果配置非法：
  - 记录 warning / error 日志
  - `flash(...)`
  - 返回 `_render_excel_calendar_page(...)`
  - 不继续 preview / confirm

建议提示文案：

> 系统配置项 `holiday_default_efficiency` 非法，无法继续工作日历 Excel 导入，请先在排产参数中修复。

#### 步骤 5：修改 `web/routes/personnel_excel_operator_calendar.py`

该文件当前没有与 `scheduler_excel_calendar.py` 完全对齐的私有 page render helper。建议：

- [ ] 先抽一个小 helper，例如 `_render_excel_operator_calendar_page(...)`
- [ ] 让 `excel_operator_calendar_page()`、`excel_operator_calendar_preview()`、`excel_operator_calendar_confirm()` 都能复用
- [ ] 配置非法时：
  - `flash(...)`
  - 返回这个 render helper
  - 不继续 preview / confirm

#### 步骤 6：对齐 `calendar_admin.py` 与 `excel_validators.py`（强烈建议）

##### `core/services/scheduler/calendar_admin.py:36-51`

当前：任意异常都回退到 `ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY`

建议：
- 直接复用 `ConfigService.get_holiday_default_efficiency()`
- 若出于服务层保活原因仍需 fallback，也必须记录日志，而不是 silent fallback

##### `core/services/common/excel_validators.py:154`

当前：

```python
hde = float(holiday_default_efficiency) if float(holiday_default_efficiency) > 0 else 0.8
```

建议：
- 改成显式校验
- 不再悄悄改成 `0.8`
- 因为 route 层已经应该传入合法值，这里应把非正值视为调用方错误或前置校验失效

### 4.3.6 现有测试要继续保持通过

- `tests/regression_scheduler_reject_nonfinite_and_invalid_status.py`
- `tests/regression_scheduler_apply_preset_reject_invalid_numeric.py`
- `tests/regression_excel_preview_confirm_extra_state_guard.py`

### 4.3.7 建议新增测试

**新增**：`tests/test_holiday_default_efficiency_read_guard.py`

建议覆盖：

1. `SystemConfig.holiday_default_efficiency = "NaN"` 时：
   - [ ] `GET /scheduler/calendar` 仍返回 `200`
   - [ ] 页面出现 degraded warning
2. `SystemConfig.holiday_default_efficiency = "0"` 时：
   - [ ] `GET /personnel/<operator_id>/calendar` 仍返回 `200`
   - [ ] 页面出现 degraded warning
3. 对两个 Excel 路由：
   - [ ] preview 不再默默继续
   - [ ] confirm 不再默默继续
   - [ ] 页面有明确错误提示
4. `tests/regression_excel_preview_confirm_extra_state_guard.py` 仍通过

### 4.3.8 验收标准

- [ ] route 层不再 silent fallback 到 `0.8`
- [ ] GET 页面有可见 degraded 提示
- [ ] Excel preview/confirm 在配置非法时明确拒绝
- [ ] 配置读取校验收口到 `ConfigService`
- [ ] 不破坏现有 write-side validation

---

## 4.4 修复 `F002`：`render_ui_template()` 的 V2 -> V1 env fallback 必须有运行期 warning / diagnostics

### 4.4.1 当前问题

关键位置：

- `web/ui_mode.py:152-158`
- `web/ui_mode.py:223-225`
- `web/ui_mode.py:278-320`
- `web/error_handlers.py:24-63`

当前行为：

- 启动期 `init_ui_mode()` 创建 V2 overlay 失败时，会记录 warning
- 但运行期 `render_ui_template()` 在 `mode == "v2"` 且 `_get_v2_env(app) is None` 时，会直接回退到 `app.jinja_env`
- 该运行期 fallback 本身没有独立 warning
- 同时仍然向模板注入 `ui_mode="v2"`

后果：
- 逻辑上页面仍处于 V2 模式
- 实际渲染 env 已经退回 V1
- 用户/运维不易察觉
- `web/error_handlers.py` 的错误页同样受该行为影响

### 4.4.2 目标行为

最低目标（本轮必做）：

1. `mode == "v2"` 且 `_get_v2_env(app) is None` 时，记录一次运行期 warning
2. warning 只记一次，不刷屏
3. 模板上下文增加诊断字段，让模板/测试知道当前是不是 `v1_fallback`

可选增强：

4. 在 base template 注入诊断 meta tag / comment
5. 在 health 页面或 health endpoint 暴露该状态

### 4.4.3 实施步骤

#### 步骤 1：在 `web/ui_mode.py` 增加“一次性警告”机制

建议新增一个 app extension key，例如：

- `ui_mode.v2_render_fallback_warned`

把当前：

```python
if mode == "v2":
    env = _get_v2_env(app) or app.jinja_env
```

改成：

- [ ] 先取 `v2_env = _get_v2_env(app)`
- [ ] 如果 `v2_env is None`：
  - `env = app.jinja_env`
  - 若本进程/本 app 尚未记录过 warning：
    - `app.logger.warning(...)`
    - 设置 warned 标记
- [ ] 否则 `env = v2_env`

日志文案建议带上：
- `template_name_or_list`
- `request.path`（若有）
- `mode == "v2" but v2_env missing`
- “可能原因：未重新打包 / overlay 创建失败 / 运行旧版本”

#### 步骤 2：把诊断状态注入模板上下文

建议新增：

- `ui_template_env`
  - `"v2"`
  - `"v1"`
  - `"v1_fallback"`
- `ui_template_env_degraded`
  - `True / False`

并同步写入 `g`：

- `g.ui_template_env`
- `g.ui_template_env_degraded`

这样模板、测试、后续健康检查都可以观察。

#### 步骤 3：可选地在模板里埋轻量诊断标记

若希望黑盒更容易测到，推荐只做低风险埋点，不做大范围可见 banner。

可选修改：

- `templates/base.html`
- `web_new_test/templates/base.html`

增加例如：

```html
<meta name="aps-ui-template-env" content="{{ ui_template_env }}">
```

若 degraded：

```html
<meta name="aps-ui-template-env-degraded" content="1">
```

这样：
- 不影响页面布局
- 不打扰普通用户
- E2E / smoke / 运维排查更容易发现 fallback

#### 步骤 4：错误页验证

由于 `web/error_handlers.py` 直接使用 `render_ui_template`，修完 `web/ui_mode.py` 后必须手工验证：

- [ ] 404 HTML error page
- [ ] 500 HTML error page
- [ ] `mode == "v2"` 且无 v2 env 时，错误页也能正常渲染
- [ ] warning 只记录一次

### 4.4.4 建议测试

建议扩展：`tests/test_ui_mode.py`

新增用例：

1. `test_render_ui_template_warns_once_when_v2_env_missing`
2. `test_render_ui_template_sets_degraded_context_when_v2_env_missing`

### 4.4.5 验收标准

- [ ] 运行期 fallback 不再 silent
- [ ] warning 不刷屏
- [ ] 模板/测试可观察到当前实际 env
- [ ] 错误页路径也被覆盖

---

## 4.5 修复 `F003`：`result_summary` 解析失败要保容错，但必须补 telemetry

### 4.5.1 当前问题

受影响位置：

- `web/routes/dashboard.py:27-38`
- `web/routes/scheduler_batches.py:61-73`
- `web/routes/system_history.py:35-48`

当前问题不是“应该直接报错”，而是：

- 页面为了兼容脏数据继续打开，这是对的
- 但解析失败时没有 warning
- `scheduler_batches.py` 把“recent history 加载失败”和“summary 解析失败”混在一个大 try/except 里，导致 summary 坏了时整个 latest-history 卡片都被清空

### 4.5.2 目标行为

1. 保留 tolerant rendering
2. 任何 `result_summary` 解析失败都记录 warning
3. 日志要带可定位信息：
   - `version`
   - 路由名
   - 必要时异常类型
4. `scheduler_batches.py` 必须把：
   - `list_recent()` 失败
   - `json.loads(result_summary)` 失败
   分开处理

### 4.5.3 实施步骤

#### `web/routes/dashboard.py`

- [ ] 顶部增加 `current_app` 导入
- [ ] 在 `json.loads(...)` 的 `except` 中加 `current_app.logger.warning(...)`
- [ ] 日志带 `getattr(latest, "version", None)`
- [ ] 保持 `latest_summary = None`
- [ ] 不修改 `overdue_count` 的兼容逻辑

建议日志：

```python
首页 result_summary 解析失败（version=%s）
```

#### `web/routes/scheduler_batches.py`

当前：

```python
try:
    items = hist_q.list_recent(limit=1)
    latest_history = items[0].to_dict() if items else None
    if latest_history and latest_history.get("result_summary"):
        latest_summary = json.loads(...)
except Exception:
    latest_history = None
    latest_summary = None
```

建议拆成两段：

**段 1：recent history 加载**
- 若失败：
  - `current_app.logger.exception(...)`
  - `latest_history = None`
  - `latest_summary = None`

**段 2：summary 解析**
- 若失败：
  - `current_app.logger.warning(...)`
  - `latest_summary = None`
  - **不要**抹掉 `latest_history`

#### `web/routes/system_history.py`

这里有两类解析：

1. `selected_summary`
2. 列表里的 `result_summary_obj`

建议：

- [ ] 顶部增加 `current_app` 导入
- [ ] `selected_summary` 解析失败时 warning，带 `version=ver`
- [ ] 列表遍历里每个 item 解析失败时 warning，带 `version=item.get("version")`
- [ ] 继续把对象字段设为 `None`

若担心日志过多，可做每请求每 `version` 只记一次 warning 的轻量限流。

### 4.5.4 现有测试要保持通过

- `tests/regression_dashboard_overdue_count_tolerance.py`

### 4.5.5 建议新增测试

**新增**：`tests/test_schedule_summary_observability.py`

建议覆盖：

- [ ] dashboard 脏 summary 仍 `200`，并有 warning log
- [ ] scheduler batches 页面脏 summary 时：
  - latest-history 仍存在
  - latest-summary 为空
  - 有 warning log
- [ ] system history 脏 summary 时：
  - 页面仍 `200`
  - 日志带 version

### 4.5.6 验收标准

- [ ] tolerant behavior 保留
- [ ] 不再 silent
- [ ] `scheduler_batches.py` 不再因坏 summary 把整个 history 卡片一起抹掉

---

## 4.6 修复 `F004`：`preview_baseline_matches()` 不能在 `compare_digest()` 异常时退化到 `==`

### 4.6.1 当前问题

位置：

- `web/routes/excel_utils.py:61-73`

当前代码：

```python
try:
    return hmac.compare_digest(provided, expected)
except Exception:
    return provided == expected
```

在当前支持运行时（Python 3.8）中，该 fallback 没有必要，而且会把“token compare 出现异常”悄悄伪装成普通字符串比较。

### 4.6.2 目标行为

修完后应该：

- `compare_digest()` 正常时：行为不变
- `compare_digest()` 异常时：
  - 记录异常（推荐）
  - 返回 `False`
- **绝不能**退化成 `provided == expected`

### 4.6.3 实施步骤

- [ ] 修改 `web/routes/excel_utils.py`
- [ ] 异常分支中建议：

```python
current_app.logger.exception("预览基线签名比较失败")
return False
```

- [ ] 保持函数签名不变
- [ ] 不修改 baseline token 生成逻辑

### 4.6.4 现有测试要保持通过

- `tests/regression_excel_preview_confirm_baseline_guard.py`
- `tests/regression_excel_preview_confirm_extra_state_guard.py`

### 4.6.5 建议新增测试

**新增**：`tests/test_excel_utils_compare_digest_guard.py`

覆盖：

- [ ] 正常 compare_digest 相等 -> `True`
- [ ] 正常 compare_digest 不等 -> `False`
- [ ] monkeypatch `hmac.compare_digest` 抛异常时 -> `False`
- [ ] 即使 `provided == expected`，也不能因为 compare 异常而返回 `True`

### 4.6.6 验收标准

- [ ] 安全比较路径不再 silently downgrade
- [ ] baseline guard 现有回归仍全绿

---

## 5. 建议改动文件清单

### 5.1 必改文件

- `web/routes/equipment_pages.py`
- `templates/equipment/list.html`
- `web/routes/personnel_pages.py`
- `web/routes/scheduler_batches.py`
- `web/routes/process_parts.py`
- `web/routes/system_backup.py`
- `core/services/scheduler/config_service.py`
- `web/routes/scheduler_calendar_pages.py`
- `web/routes/scheduler_excel_calendar.py`
- `web/routes/personnel_calendar_pages.py`
- `web/routes/personnel_excel_operator_calendar.py`
- `web/ui_mode.py`
- `web/routes/dashboard.py`
- `web/routes/system_history.py`
- `web/routes/excel_utils.py`

### 5.2 强烈建议一并对齐

- `core/services/scheduler/calendar_admin.py`
- `core/services/common/excel_validators.py`
- `templates/scheduler/calendar.html`
- `templates/personnel/calendar.html`

### 5.3 可选诊断增强

- `templates/base.html`
- `web_new_test/templates/base.html`
- （如要暴露 health 诊断）`web/routes/system_health.py`

---

## 6. 建议新增/调整测试清单

### 6.1 必跑旧测试

```bat
python tests/regression_dashboard_overdue_count_tolerance.py
python tests/regression_excel_preview_confirm_baseline_guard.py
python tests/regression_excel_preview_confirm_extra_state_guard.py
python tests/regression_scheduler_reject_nonfinite_and_invalid_status.py
python tests/regression_scheduler_apply_preset_reject_invalid_numeric.py
python -m pytest tests/test_ui_mode.py -q
```

### 6.2 建议新增测试文件

- `tests/test_equipment_page_downtime_overlay_degraded.py`
- `tests/test_bulk_route_error_visibility.py`
- `tests/test_holiday_default_efficiency_read_guard.py`
- `tests/test_schedule_summary_observability.py`
- `tests/test_excel_utils_compare_digest_guard.py`

### 6.3 每阶段完成后的最小回归建议

#### F005 完成后

```bat
python -m pytest tests/test_equipment_page_downtime_overlay_degraded.py -q
```

#### F006 完成后

```bat
python -m pytest tests/test_bulk_route_error_visibility.py -q
```

#### F007 完成后

```bat
python tests/regression_excel_preview_confirm_extra_state_guard.py
python tests/regression_scheduler_reject_nonfinite_and_invalid_status.py
python tests/regression_scheduler_apply_preset_reject_invalid_numeric.py
python -m pytest tests/test_holiday_default_efficiency_read_guard.py -q
```

#### F002 完成后

```bat
python -m pytest tests/test_ui_mode.py -q
```

#### F003 完成后

```bat
python tests/regression_dashboard_overdue_count_tolerance.py
python -m pytest tests/test_schedule_summary_observability.py -q
```

#### F004 完成后

```bat
python tests/regression_excel_preview_confirm_baseline_guard.py
python tests/regression_excel_preview_confirm_extra_state_guard.py
python -m pytest tests/test_excel_utils_compare_digest_guard.py -q
```

---

## 7. 建议的提交切分

### Commit 1
**F005: equipment downtime overlay degraded-state signaling**

- `web/routes/equipment_pages.py`
- `templates/equipment/list.html`
- `tests/test_equipment_page_downtime_overlay_degraded.py`

### Commit 2
**F006: preserve AppError message and log unexpected exceptions in bulk routes**

- `web/routes/scheduler_batches.py`
- `web/routes/equipment_pages.py`
- `web/routes/personnel_pages.py`
- `web/routes/process_parts.py`
- `web/routes/system_backup.py`
- `tests/test_bulk_route_error_visibility.py`

### Commit 3
**F007: centralize holiday_default_efficiency read validation and stop silent route fallback**

- `core/services/scheduler/config_service.py`
- `web/routes/scheduler_calendar_pages.py`
- `web/routes/scheduler_excel_calendar.py`
- `web/routes/personnel_calendar_pages.py`
- `web/routes/personnel_excel_operator_calendar.py`
- `core/services/scheduler/calendar_admin.py`
- `core/services/common/excel_validators.py`
- 相关模板
- `tests/test_holiday_default_efficiency_read_guard.py`

### Commit 4
**F002: add runtime warning and diagnostics for V2 render fallback**

- `web/ui_mode.py`
- 可选 `templates/base.html` / `web_new_test/templates/base.html`
- `tests/test_ui_mode.py`

### Commit 5
**F003/F004: add schedule-summary telemetry and remove compare_digest downgrade**

- `web/routes/dashboard.py`
- `web/routes/scheduler_batches.py`
- `web/routes/system_history.py`
- `web/routes/excel_utils.py`
- `tests/test_schedule_summary_observability.py`
- `tests/test_excel_utils_compare_digest_guard.py`

---

## 8. 最终验收清单

### 8.1 行为层验收

- [ ] `F005`：设备页停机查询失败时有明确 degraded 提示，不再静默当成“无停机”
- [ ] `F006`：bulk route 失败项能看到 `ID: reason`
- [ ] `F006`：unexpected exception 都有 stack trace
- [ ] `F007`：`holiday_default_efficiency` 非法时不再 silent fallback
- [ ] `F007`：Excel preview/confirm 在配置非法时明确拒绝
- [ ] `F002`：V2 render fallback 有运行期 warning，且 warning 不刷屏
- [ ] `F003`：summary 脏数据仍可容错，但日志可观察
- [ ] `F004`：`compare_digest()` 异常时不再退化为 `==`

### 8.2 兼容性验收

- [ ] Python 3.8 兼容
- [ ] 不新增 Win7 / PyInstaller 风险
- [ ] 不破坏现有 V1/V2 模板渲染
- [ ] 不破坏已验证的 Excel strict-mode / baseline-guard 语义
- [ ] 不重新引入旧 `F001` / `F008` / `F009` / `F010`

### 8.3 回归层验收

- [ ] 所有旧回归通过
- [ ] 新增测试通过
- [ ] 关键页面手动 smoke 通过：
  - [ ] `/`
  - [ ] `/scheduler/`
  - [ ] `/system/history`
  - [ ] `/equipment/`
  - [ ] `/scheduler/calendar`
  - [ ] `/personnel/<operator_id>/calendar`
  - [ ] `/scheduler/excel/calendar`
  - [ ] `/personnel/excel/operator_calendar`

### 8.4 review 收口验收

- [ ] 修复完成后，对 `F002-F007` 做 focused re-verification
- [ ] 仅在代码与测试稳定后，再回写/更新 `.limcode/review/web_deep_review_reverify.md`
- [ ] 最终判断是否能从 `conditionally_accepted` 提升为 `accepted`

---

## 9. 执行顺序（一句话版）

1. 先跑 baseline
2. 修 `F005`，把设备停机查询失败显式化
3. 修 `F006`，把 bulk route 的失败原因与日志补齐
4. 修 `F007`，把 `holiday_default_efficiency` 读路径收口到 `ConfigService`，GET 页面明示降级，Excel preview/confirm 明确拒绝
5. 修 `F002`，给 V2 render fallback 加一次性 warning + diagnostics flag
6. 修 `F003`，给脏 `result_summary` 加 warning，并拆开 `scheduler_batches.py` 的大 try/except
7. 修 `F004`，把 `compare_digest()` 异常 fallback 改成 `return False`
8. 跑新旧测试
9. 做 focused re-verification
10. 再更新 review 结论

---

## 10. 实施时的额外提醒

- `F007` 是最容易“只修 route 表面，不修读取收口”的点；务必优先把严格读取逻辑集中到 `ConfigService`
- `F006` 不要只改 flash 文案而不打日志；否则只是把 silent 改成半 silent
- `F002` 不要把 fallback 直接删除；当前目标是“保留可用性 + 增强可观测性”，不是让模板 overlay 缺失时所有页面直接 500
- `F003` 的重点不是把页面搞严格，而是让坏 summary 有日志且 `scheduler_batches.py` 不再把 `latest_history` 整块抹掉
- `F004` 是低风险清理项，但不要漏加回归，避免未来有人又把异常时的 `==` fallback 加回来
- `core/services/common/excel_validators.py` 当前还有一个活跃诊断：`Line 118: [Error] “None”不支持运算符"<=" (Pylance)`。如果在 `F007` 过程中顺带碰到该文件，建议一起确认相关数值校验路径类型收窄是否需要补强，但不要把本轮范围扩成新的独立重构

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: in_progress
- Reviewed modules: pending
- Current progress: 0 milestones recorded
- Total milestones: 0
- Completed milestones: 0
- Total findings: 0
- Findings by severity: high 0 / medium 0 / low 0
- Latest conclusion: pending
- Recommended next action: pending
- Overall decision: pending
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
<!-- no findings -->
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
<!-- no milestones -->
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh69sib-4i8jzv",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": null,
  "status": "in_progress",
  "overallDecision": null,
  "latestConclusion": null,
  "recommendedNextAction": null,
  "reviewedModules": [],
  "milestones": [],
  "findings": []
}
<!-- LIMCODE_REVIEW_METADATA_END -->
