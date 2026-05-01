---
doc_type: dev-guide
slug: aps-browser-scheduler-qa-replay
component: scheduler-browser-qa
status: current
summary: APS 排产浏览器复验的可复用造数、操作和对账步骤。
tags:
  - aps
  - scheduler
  - browser-qa
  - gantt
last_reviewed: 2026-05-01
---

# APS 排产浏览器复验记录与复用手册

## 这份文档干什么用

这份文档记录 2026-05-01 这轮排产修复后的浏览器复验过程。下次要复测“模拟排产后甘特图不空白”和“失败提示要具体”这两类问题时，可以照着这里重新建临时库、手填数据、触发边界、再用接口和数据库对账。

本轮原则：

- 业务数据全部从浏览器页面录入。
- 数据库只做只读核对，不直接写业务数据。
- 不碰现有业务库。
- 失败场景不能静默成功，提示要能让用户看懂下一步该补什么。

## 本轮隔离环境记录

本轮使用的是临时目录，服务已经在复验后关闭：

| 项目 | 本轮实际值 |
|---|---|
| 临时目录 | `/tmp/aps-fix-browser.A4GaFV` |
| 数据库 | `/tmp/aps-fix-browser.A4GaFV/aps.db` |
| 日志目录 | `/tmp/aps-fix-browser.A4GaFV/logs` |
| 浏览器访问地址 | `http://127.0.0.1:61661` |
| 测试开始时间 | `2026-05-04T08:00` |
| 测试结束日期 | `2026-05-20` |
| 模拟排产生成版本 | `2` |
| 模拟排产跳转地址 | `/scheduler/gantt?view=machine&start_date=2026-05-04&end_date=2026-05-10&version=2` |

下次重跑时不要复用上面的临时目录。用新的目录启动，例如：

```bash
RUN_DIR="$(mktemp -d /tmp/aps-browser-scheduler-qa.XXXXXX)"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/backups" "$RUN_DIR/templates_excel" "$RUN_DIR/browser-artifacts"

APS_DB_PATH="$RUN_DIR/aps.db" \
APS_LOG_DIR="$RUN_DIR/logs" \
APS_BACKUP_DIR="$RUN_DIR/backups" \
APS_EXCEL_TEMPLATE_DIR="$RUN_DIR/templates_excel" \
APS_PORT=61661 \
.venv/bin/python app.py
```

启动后以实际输出或运行时文件为准：

- `logs/aps_host.txt`
- `logs/aps_port.txt`
- `logs/aps_db_path.txt`
- `logs/aps_runtime.json`

## 本轮浏览器手填的基础资料

### 工种

页面入口：`工艺管理 -> 工种管理`

| 字段 | 值 |
|---|---|
| 工种编号 | `OTQA` |
| 工种名称 | `QA数车` |
| 类型 | 内部工种 |

### 人员

页面入口：`人员管理 -> 新增人员`

| 字段 | 值 |
|---|---|
| 人员编号 | `OPQA1` |
| 姓名 | `复验人员` |
| 状态 | 启用 |

### 设备

页面入口：`设备管理 -> 新增设备`

| 字段 | 值 |
|---|---|
| 设备编号 | `MCQA1` |
| 设备名称 | `复验设备` |
| 所属工种 | `QA数车` |
| 状态 | 启用 |

### 人机关系

页面入口：`设备管理 -> MCQA1 详情 -> 添加人员关联`

| 字段 | 值 |
|---|---|
| 设备 | `MCQA1 复验设备` |
| 人员 | `OPQA1 复验人员` |
| 能力等级 | 普通即可 |

### 零件路线

页面入口：`工艺管理 -> 零件 -> 新增零件`

| 字段 | 值 |
|---|---|
| 图号 | `PQA1` |
| 零件名称 | 可填 `复验零件` |
| 工艺路线 | `10QA数车` |

路线解析结果应为：

- 共 1 道工序。
- 内部工序 1 道。
- 外协工序 0 道。

## 本轮浏览器手填的批次

页面入口：`排产调度 -> 批次管理 -> 新增批次`

### 可成功模拟的批次

| 字段 | 值 |
|---|---|
| 批次号 | `QA-SIM-OK` |
| 图号 | `PQA1` |
| 数量 | `2` |
| 优先级 | 急件 |
| 交期 | `2026-05-20` |
| 齐套状态 | 已齐套 |

创建后进入批次详情，编辑工序 `10 / QA数车`：

| 字段 | 值 |
|---|---|
| 设备 | `MCQA1` |
| 人员 | `OPQA1` |
| 换型工时 | `0.5` |
| 单件工时 | `1.25` |

这道工序的预期排程时长：

- 换型 `0.5` 小时。
- 数量 `2`，单件 `1.25` 小时，共 `2.5` 小时。
- 总时长 `3` 小时。
- 从 `2026-05-04 08:00:00` 开始，应到 `2026-05-04 11:00:00` 结束。

### 未齐套批次

| 字段 | 值 |
|---|---|
| 批次号 | `QA-NOTREADY` |
| 图号 | `PQA1` |
| 数量 | `2` |
| 优先级 | 普通或急件都可 |
| 交期 | `2026-05-20` |
| 齐套状态 | 未齐套 |

这个批次用于验证“启用齐套约束时，页面要明确说哪个批次未齐套”。

### 缺资源批次

| 字段 | 值 |
|---|---|
| 批次号 | `QA-MISSING` |
| 图号 | `PQA1` |
| 数量 | `2` |
| 优先级 | 普通或急件都可 |
| 交期 | `2026-05-20` |
| 齐套状态 | 已齐套 |

创建后不要给工序填设备、人员、换型工时、单件工时。这个批次用于验证“缺设备/人员时，页面要说清楚是哪道工序缺什么”。

## 本轮验证的失败边界

### 不选批次直接执行排产

页面入口：`排产调度 -> 执行排产`

操作：

1. 不勾选任何批次。
2. 点击 `执行排产`。

预期提示：

```text
请至少选择 1 个批次执行排产。
```

验收点：

- 不能显示泛泛的“参数填写不正确”。
- 横幅有关闭按钮。
- 点击关闭后横幅消失。

### 未齐套批次

操作：

1. 勾选 `QA-NOTREADY`。
2. 开始时间填 `2026-05-04T08:00`。
3. 结束日期填 `2026-05-20`。
4. 勾选严格校验。
5. 勾选齐套约束。
6. 点击 `执行排产`。

预期提示：

```text
以下批次未齐套，禁止排产：QA-NOTREADY
```

验收点：

- 必须包含批次号 `QA-NOTREADY`。
- 不能出现 `ready_status` 这种内部字段。
- 不能变成“请检查排产条件”这种泛化文案。

### 缺设备和人员

操作：

1. 勾选 `QA-MISSING`。
2. 开始时间填 `2026-05-04T08:00`。
3. 结束日期填 `2026-05-20`。
4. 勾选严格校验。
5. 勾选齐套约束。
6. 点击 `执行排产`。

预期提示：

```text
本次排产没有生成可保存结果，存在内部工序缺设备/人员：QA-MISSING / 工序10 / QA数车 缺设备、人员。请先到批次工序补充页补齐后重试。
```

验收点：

- 必须包含批次号 `QA-MISSING`。
- 必须包含工序号 `工序10`。
- 必须包含工序名 `QA数车`。
- 必须说清楚缺 `设备、人员`。
- 不能显示旧文案“本次排产没有生成可保存的有效排程结果，请检查排产条件后重试。”

### 结束日期早于开始日期

操作：

1. 勾选 `QA-SIM-OK`。
2. 开始时间填 `2026-05-04T08:00`。
3. 结束日期填 `2026-05-01`。
4. 勾选严格校验。
5. 勾选齐套约束。
6. 点击 `执行排产`。

预期提示：

```text
结束日期不能早于开始时间所在日期
```

验收点：

- 不能显示 `end_date`、`start_dt` 这类内部字段。
- 不能变成“参数填写不正确”。

## 本轮验证的模拟排产

操作：

1. 选择 `QA-SIM-OK`。
2. 开始时间填 `2026-05-04T08:00`。
3. 结束日期填 `2026-05-20`。
4. 勾选严格校验。
5. 勾选齐套约束。
6. 执行模拟排产。

预期跳转：

```text
/scheduler/gantt?view=machine&start_date=2026-05-04&end_date=2026-05-10&version=2
```

预期页面：

- 页面标题是 `甘特图（设备视图）`。
- 日期范围显示 `2026-05-04 ～ 2026-05-10`。
- 当前版本是 `v2`。
- 页面能看到 `QA-SIM-OK`。
- 甘特图不是空白。
- 页面提示 `模拟排产完成：生成版本 2（不影响批次状态）。`

说明：

- 本轮浏览器自动化点击页面上的 `模拟排产（插单模拟）` 时，工具会自动取消确认弹窗。
- 为了验证后端跳转和页面结果，本轮临时创建了一个本地 HTML 表单，提交到同一个 `/scheduler/simulate` 接口。
- 人工复测时，直接在页面确认弹窗点确认即可，不需要这个本地 HTML 表单。

本轮用于提交模拟排产的本地 HTML 表单内容如下：

```html
<!doctype html>
<meta charset="utf-8">
<title>simulate check</title>
<form method="post" action="http://127.0.0.1:61661/scheduler/simulate">
  <input name="batch_ids" value="QA-SIM-OK">
  <input name="start_dt" value="2026-05-04T08:00">
  <input name="end_date" value="2026-05-20">
  <input name="strict" value="on">
  <input name="enforce_ready" value="on">
  <button type="submit">提交模拟排产</button>
</form>
```

## 本轮接口和数据库对账

### 设备甘特接口

请求：

```text
GET /scheduler/gantt/data?view=machine&start_date=2026-05-04&end_date=2026-05-10&version=2
```

本轮结果：

| 字段 | 值 |
|---|---|
| `data.version` | `2` |
| `data.week_start` | `2026-05-04` |
| `data.week_end` | `2026-05-10` |
| `data.task_count` | `1` |
| `data.tasks[0].id` | `QA-SIM-OK_10` |
| `data.tasks[0].start` | `2026-05-04 08:00:00` |
| `data.tasks[0].end` | `2026-05-04 11:00:00` |
| `data.tasks[0].meta.batch_id` | `QA-SIM-OK` |
| `data.tasks[0].meta.seq` | `10` |
| `data.tasks[0].meta.machine_id` | `MCQA1` |
| `data.tasks[0].meta.operator_id` | `OPQA1` |

注意：

- 接口返回结构是 `{ "success": true, "data": {...} }`。
- 任务列表在 `data.tasks`，不是顶层 `tasks`。

### 人员甘特接口

请求：

```text
GET /scheduler/gantt/data?view=operator&start_date=2026-05-04&end_date=2026-05-10&version=2
```

本轮结果：

| 字段 | 值 |
|---|---|
| `data.version` | `2` |
| `data.task_count` | `1` |
| `data.tasks[0].meta.operator_id` | `OPQA1` |

### 数据库只读核对

本轮数据库里版本 `2` 的排程底账：

| 字段 | 值 |
|---|---|
| `Schedule.version` | `2` |
| `BatchOperations.batch_id` | `QA-SIM-OK` |
| `BatchOperations.seq` | `10` |
| `BatchOperations.op_type_name` | `QA数车` |
| `Schedule.machine_id` | `MCQA1` |
| `Schedule.operator_id` | `OPQA1` |
| `Schedule.start_time` | `2026-05-04 08:00:00` |
| `Schedule.end_time` | `2026-05-04 11:00:00` |
| `ScheduleHistory.result_status` | `simulated` |

本轮版本统计：

| 版本 | 状态 | 批次数 | 工序数 | 排程明细数 |
|---|---|---:|---:|---:|
| `1` | `simulated` | `1` | `1` | `1` |
| `2` | `simulated` | `1` | `1` | `1` |

可复用 SQL：

```sql
SELECT
  s.version,
  s.op_id,
  s.machine_id,
  s.operator_id,
  s.start_time,
  s.end_time,
  bo.batch_id,
  bo.seq,
  bo.op_type_name,
  b.priority,
  h.result_status
FROM Schedule s
JOIN BatchOperations bo ON bo.id = s.op_id
JOIN Batches b ON b.batch_id = bo.batch_id
LEFT JOIN ScheduleHistory h ON h.version = s.version
WHERE s.version = 2
ORDER BY s.start_time, s.id;

SELECT version, result_status, batch_count, op_count
FROM ScheduleHistory
ORDER BY version;

SELECT version, COUNT(*)
FROM Schedule
GROUP BY version
ORDER BY version;
```

## 本轮修复后必须继续守住的点

- 模拟排产成功后，不能再按今天所在周打开甘特图。
- 模拟排产跳转必须带上本次结果版本号。
- 模拟排产跳转必须带上本次排程所在日期范围。
- 排产失败不能吞掉服务层已经知道的业务原因。
- 未齐套、没选批次、日期错误、缺设备/人员，都要显示具体原因。
- 未知异常仍然只能显示安全提示，不能把内部堆栈、路径、对象名暴露给页面用户。
- 缺资源提示最多展示 10 条问题对象，超出的数量用“还有 X 条未展示”说明。
- 不能为了让页面好看，把空排程伪装成成功。
- 不能在甘特图接口里伪造任务。
- 不能绕过严格校验、齐套校验或资源校验。

## 本轮已经跑过的自动化检查

```bash
.venv/bin/pytest \
  tests/test_scheduler_run_view_result_contract.py \
  tests/regression_scheduler_run_surfaces_resource_pool_warning.py \
  tests/regression_schedule_service_reject_no_actionable_schedule_rows.py \
  tests/regression_scheduler_week_plan_no_reschedulable_flash.py
```

结果：

```text
21 passed in 1.04s
```

代码检查：

```bash
.venv/bin/ruff check \
  web/routes/domains/scheduler/scheduler_run.py \
  web/routes/domains/scheduler/scheduler_week_plan.py \
  web/routes/domains/scheduler/scheduler_user_messages.py \
  core/services/scheduler/run/schedule_input_collector.py \
  core/services/scheduler/run/schedule_orchestrator.py \
  core/services/scheduler/run/schedule_persistence.py \
  tests/test_scheduler_run_view_result_contract.py \
  tests/regression_scheduler_run_surfaces_resource_pool_warning.py \
  tests/regression_schedule_service_reject_no_actionable_schedule_rows.py
```

结果：

```text
All checks passed!
```

空白和换行检查：

```bash
git diff --check
```

结果：无输出，表示通过。

## 下次复测的最短清单

1. 用新的临时目录启动服务。
2. 浏览器手填 `OTQA`、`OPQA1`、`MCQA1`、人机关系、`PQA1`。
3. 浏览器手填 `QA-SIM-OK`、`QA-NOTREADY`、`QA-MISSING`。
4. 给 `QA-SIM-OK` 的 `10 / QA数车` 工序填 `MCQA1`、`OPQA1`、`0.5`、`1.25`。
5. 触发“不选批次”，检查提示和关闭按钮。
6. 触发 `QA-NOTREADY`，检查未齐套提示。
7. 触发 `QA-MISSING`，检查缺设备/人员提示。
8. 触发结束日期早于开始日期，检查日期提示。
9. 对 `QA-SIM-OK` 执行模拟排产。
10. 确认自动跳到 `2026-05-04` 所在周，版本号是新生成版本。
11. 打开设备甘特和人员甘特 data 接口。
12. 用只读 SQL 对账 `Schedule`、`BatchOperations`、`Batches`、`ScheduleHistory`。
