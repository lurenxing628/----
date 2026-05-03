---
doc_type: dev-guide
slug: aps-browser-scheduler-qa-replay
component: scheduler-browser-qa
status: current
summary: APS 排产浏览器复验和复杂压测的可复用造数、操作和对账步骤。
tags:
  - aps
  - scheduler
  - browser-qa
  - gantt
last_reviewed: 2026-05-03
---

# APS 排产浏览器复验记录与复用手册

## 这份文档干什么用

这份文档记录排产修复后的浏览器复验过程。2026-05-01 的记录是一套最小复验数据，2026-05-03 又补了一套 12 个成功批次加多种失败批次的复杂压测数据。下次要复测“模拟排产后甘特图不空白”“失败提示要具体”“多批次多资源压测边界”这几类问题时，可以照着这里重新建临时库、手填数据、触发边界、再用接口和数据库对账。

本轮原则：

- 业务数据全部从浏览器页面录入。
- 数据库只做只读核对，不直接写业务数据。
- 不碰现有业务库。
- 失败场景不能静默成功，提示要能让用户看懂下一步该补什么。

## 2026-05-03 复杂压测实跑记录

这一轮按“浏览器录入 + 临时库 + 数据库只读对账”的原则执行。业务数据通过浏览器页面和浏览器提交表单进入系统，数据库只用来核对结果，没有直接写业务数据。

### 本轮隔离环境

| 项目 | 本轮实际值 |
|---|---|
| 临时目录 | `/tmp/aps-browser-scheduler-stress.IXpgq8` |
| 数据库 | `/tmp/aps-browser-scheduler-stress.IXpgq8/aps.db` |
| 日志目录 | `/tmp/aps-browser-scheduler-stress.IXpgq8/logs` |
| 浏览器访问地址 | `http://127.0.0.1:61661` |
| 浏览器造数表单 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/setup-driver.html` |
| 浏览器补工序表单 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/op-update-driver.html` |
| 失败场景记录 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/failure-results.json` |
| 模拟排产记录 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/simulate-result.json` |
| 正式排产记录 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/formal-result.json` |
| 甘特图截图 | `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/gantt-v2-machine.png` |

注意：

- Flask 启动输出显示 `http://127.0.0.1:61661` 可访问，实际请求 `61661` 返回 `200`。
- 本轮 `logs/aps_runtime.json` 和 `logs/aps_port.txt` 写出了 `5000`，但 `5000` 实际不通。这条只作为本轮环境现象记录，复跑时仍以真实可访问地址为准。

### 本轮浏览器录入的数据量

| 表 | 条数 |
|---|---:|
| `OpTypes` | 5 |
| `Suppliers` | 1 |
| `Operators` | 4 |
| `Machines` | 5 |
| `OperatorMachine` | 10 |
| `WorkCalendar` | 3 |
| `OperatorCalendar` | 2 |
| `MachineDowntimes` | 2 |
| `Parts` | 3 |
| `PartOperations` | 8 |
| `Batches` | 26 |
| `BatchOperations` | 53 |

### 基础资料

#### 工种

| 工种编号 | 工种名称 | 归属 |
|---|---|---|
| `OTQA-TURN` | `压测数车` | 自制 |
| `OTQA-MILL` | `压测数铣` | 自制 |
| `OTQA-GRIND` | `压测磨工` | 自制 |
| `OTQA-ASSY` | `压测装配` | 自制 |
| `OTQA-HEAT` | `压测热处理` | 外协 |

#### 供应商

| 供应商编号 | 名称 | 对应工种 | 默认周期 |
|---|---|---|---:|
| `SQA-HEAT` | `压测热处理供应商` | `压测热处理` | 1 天 |

#### 人员、设备和人机关系

| 设备 | 工种 | 可操作人员 |
|---|---|---|
| `MCQA-T1` / `压测数车1` | `压测数车` | `OPQA-A`、`OPQA-B` |
| `MCQA-T2` / `压测数车2` | `压测数车` | `OPQA-A`、`OPQA-C` |
| `MCQA-M1` / `压测数铣1` | `压测数铣` | `OPQA-B`、`OPQA-C` |
| `MCQA-G1` / `压测磨工1` | `压测磨工` | `OPQA-C`、`OPQA-D` |
| `MCQA-A1` / `压测装配1` | `压测装配` | `OPQA-A`、`OPQA-D` |

人员：

- `OPQA-A`：压测人员A，启用。
- `OPQA-B`：压测人员B，启用。
- `OPQA-C`：压测人员C，启用。
- `OPQA-D`：压测人员D，启用。

### 日历和停机边界

| 类型 | 对象 | 日期/时间 | 设置 |
|---|---|---|---|
| 全局日历 | 全部 | `2026-05-04` | 工作日，08:00-12:00，4 小时短班 |
| 全局日历 | 全部 | `2026-05-06` | 假期，不允许普通件，不允许急件 |
| 全局日历 | 全部 | `2026-05-09` | 周末加班，08:00-17:00，只允许急件/特急 |
| 个人日历 | `OPQA-B` | `2026-05-05` | 请假，0 工时 |
| 个人日历 | `OPQA-D` | `2026-05-09` | 加班，08:00-17:00 |
| 设备停机 | `MCQA-T1` | `2026-05-04 10:00` 到 `2026-05-04 12:00` | 计划维护 |
| 设备停机 | `MCQA-M1` | `2026-05-05 08:00` 到 `2026-05-05 10:00` | 计划维护 |

### 零件路线

| 图号 | 名称 | 工艺路线 | 解析结果 |
|---|---|---|---|
| `PQA-MULTI` | 压测多工序零件 | `10压测数车20压测数铣30压测磨工40压测装配` | 4 道自制 |
| `PQA-EXT` | 压测外协零件 | `10压测数车20压测热处理30压测装配` | 2 道自制，1 道外协 |
| `PQA-SHORT` | 压测短工序零件 | `10压测数车` | 1 道自制 |

### 成功路径批次

这 12 个批次用于模拟排产和正式排产。它们合计不是原计划估算的 36 道工序，而是实际生成 39 道工序：`PQA-MULTI` 每批 4 道，`PQA-EXT` 每批 3 道，`PQA-SHORT` 每批 1 道。

| 批次号 | 图号 | 数量 | 优先级 | 交期 | 齐套 |
|---|---|---:|---|---|---|
| `PT-CRIT-001` | `PQA-MULTI` | 3 | 特急 | `2026-05-08` | 齐套 |
| `PT-URG-002` | `PQA-MULTI` | 5 | 急件 | `2026-05-09` | 齐套 |
| `PT-NORM-003` | `PQA-MULTI` | 4 | 普通 | `2026-05-12` | 齐套 |
| `PT-EXT-004` | `PQA-EXT` | 2 | 急件 | `2026-05-10` | 齐套 |
| `PT-EXT-005` | `PQA-EXT` | 6 | 普通 | `2026-05-13` | 齐套 |
| `PT-LONG-006` | `PQA-MULTI` | 8 | 特急 | `2026-05-14` | 齐套 |
| `PT-SHORT-007` | `PQA-SHORT` | 1 | 急件 | `2026-05-07` | 齐套 |
| `PT-READYDATE-008` | `PQA-MULTI` | 2 | 普通 | `2026-05-15` | 齐套，齐套日期 `2026-05-07` |
| `PT-MIX-009` | `PQA-MULTI` | 7 | 急件 | `2026-05-11` | 齐套 |
| `PT-EXT-LONG-010` | `PQA-EXT` | 10 | 特急 | `2026-05-16` | 齐套 |
| `PT-COLLIDE-011` | `PQA-MULTI` | 6 | 普通 | `2026-05-17` | 齐套 |
| `PT-TINY-012` | `PQA-SHORT` | 1 | 普通 | `2026-05-18` | 齐套 |

### 成功路径工序补充规则

| 批次 | 工序10 | 工序20 | 工序30 | 工序40 |
|---|---|---|---|---|
| `PT-CRIT-001` | `MCQA-T1` / `OPQA-A` / `0.25+1.00` | `MCQA-M1` / `OPQA-B` / `0.20+0.80` | `MCQA-G1` / `OPQA-C` / `0.10+0.60` | `MCQA-A1` / `OPQA-D` / `0.20+0.50` |
| `PT-URG-002` | `MCQA-T1` / `OPQA-B` / `0.50+0.70` | `MCQA-M1` / `OPQA-C` / `0.20+1.10` | `MCQA-G1` / `OPQA-D` / `0.15+0.70` | `MCQA-A1` / `OPQA-A` / `0.25+0.55` |
| `PT-NORM-003` | `MCQA-T2` / `OPQA-A` / `0.25+0.90` | `MCQA-M1` / `OPQA-B` / `0.30+0.75` | `MCQA-G1` / `OPQA-C` / `0.10+0.60` | `MCQA-A1` / `OPQA-D` / `0.20+0.45` |
| `PT-EXT-004` | `MCQA-T2` / `OPQA-C` / `0.30+1.20` | `SQA-HEAT` / `1.00天` | `MCQA-A1` / `OPQA-A` / `0.20+0.60` | - |
| `PT-EXT-005` | `MCQA-T1` / `OPQA-A` / `0.40+0.85` | `SQA-HEAT` / `1.50天` | `MCQA-A1` / `OPQA-D` / `0.30+0.55` | - |
| `PT-LONG-006` | `MCQA-T1` / `OPQA-B` / `1.00+1.50` | `MCQA-M1` / `OPQA-C` / `0.60+1.10` | `MCQA-G1` / `OPQA-D` / `0.50+0.90` | `MCQA-A1` / `OPQA-A` / `0.40+0.70` |
| `PT-SHORT-007` | `MCQA-T2` / `OPQA-A` / `0.00+0.25` | - | - | - |
| `PT-READYDATE-008` | `MCQA-T2` / `OPQA-C` / `0.20+0.70` | `MCQA-M1` / `OPQA-C` / `0.20+0.70` | `MCQA-G1` / `OPQA-C` / `0.20+0.50` | `MCQA-A1` / `OPQA-D` / `0.20+0.45` |
| `PT-MIX-009` | `MCQA-T1` / `OPQA-A` / `0.60+1.00` | `MCQA-M1` / `OPQA-B` / `0.35+0.85` | `MCQA-G1` / `OPQA-D` / `0.25+0.75` | `MCQA-A1` / `OPQA-A` / `0.30+0.50` |
| `PT-EXT-LONG-010` | `MCQA-T1` / `OPQA-B` / `0.75+1.25` | `SQA-HEAT` / `2.00天` | `MCQA-A1` / `OPQA-D` / `0.40+0.65` | - |
| `PT-COLLIDE-011` | `MCQA-T1` / `OPQA-A` / `0.50+1.10` | `MCQA-M1` / `OPQA-B` / `0.30+1.00` | `MCQA-G1` / `OPQA-C` / `0.20+0.80` | `MCQA-A1` / `OPQA-D` / `0.20+0.55` |
| `PT-TINY-012` | `MCQA-T2` / `OPQA-C` / `0.05+0.10` | - | - | - |

表中 `0.25+1.00` 这类写法表示：换型工时 `0.25` 小时，单件工时 `1.00` 小时。

### 失败边界批次

| 批次号 | 用途 | 本轮状态 |
|---|---|---|
| `PT-NOTREADY-013` | 未齐套拦截 | 工序已补齐资源，齐套状态为未齐套 |
| `PT-PARTIAL-014` | 部分齐套拦截 | 工序已补齐资源，齐套状态为部分齐套 |
| `PT-MISS-101` 到 `PT-MISS-111` | 11 条缺资源，验证最多展示 10 条并提示剩余数量 | 全部保留缺设备、人员 |
| `PT-BADHOURS-201` | 负工时录入边界 | 浏览器保存工序时被拒绝，HTTP `400`，提示 `工时不能为负数`，负数没有进库 |

`PT-BADHOURS-201` 的实际结果和原计划不同：系统不允许通过浏览器保存负工时，所以这条数据没有进入排产层。后续选择它排产时，提示的是缺设备/人员，而不是负工时。

### 失败边界验证结果

| 场景 | 页面提示 | 结论 |
|---|---|---|
| 不选批次直接排产 | `请至少选择 1 个批次执行排产。` | 通过 |
| `PT-NOTREADY-013` + `PT-PARTIAL-014` | `以下批次未齐套，禁止排产：PT-NOTREADY-013，PT-PARTIAL-014` | 通过，没有露内部字段 |
| `PT-MISS-101` 到 `PT-MISS-111` | 前 10 条逐条展示，最后提示 `还有 1 条未展示。请先到批次工序补充页补齐后重试。` | 通过 |
| 结束日期早于开始日期 | `结束日期不能早于开始时间所在日期` | 通过，没有露内部字段 |
| `PT-BADHOURS-201` 保存负工时 | HTTP `400`，错误页提示 `工时不能为负数` | 通过，非法数据未入库 |

### 模拟排产结果

本轮提交：

```text
POST /scheduler/simulate
batch_ids = PT-CRIT-001, PT-URG-002, PT-NORM-003, PT-EXT-004, PT-EXT-005, PT-LONG-006, PT-SHORT-007, PT-READYDATE-008, PT-MIX-009, PT-EXT-LONG-010, PT-COLLIDE-011, PT-TINY-012
start_dt = 2026-05-04T08:00
end_date = 2026-05-20
strict_mode = yes
enforce_ready = on
```

页面结果：

```text
模拟排产部分完成：生成版本 1（不影响批次状态）。
排产执行遇到问题，请联系管理员查看日志。
排程数据存在异常，可能影响甘特图展示，请检查数据。
```

跳转地址：

```text
/scheduler/gantt?view=machine&start_date=2026-05-04&end_date=2026-05-10&version=1
```

数据库结果：

| 字段 | 值 |
|---|---|
| `ScheduleHistory.version` | `1` |
| `ScheduleHistory.result_status` | `simulated` |
| `ScheduleHistory.batch_count` | `12` |
| `ScheduleHistory.op_count` | `39` |
| `Schedule` 行数 | `38` |
| 完成状态 | `partial` |
| 失败原因 | `PT-COLLIDE-011_40` 预计 `2026-05-21 08:18` 完工，超过 `2026-05-20` 窗口 |

说明：

- 这不是甘特图空白问题。版本 1 有可保存排程行，也能打开甘特图。
- 这组数据把截止日期压得很紧，系统把最后一道超窗工序挡住了，所以结果是部分完成。

### 正式排产结果

正式排产使用同一批 12 个批次、同一开始时间、同一截止日期。

页面结果：

```text
排产部分完成（版本 2）：成功 38/39，失败 1。超期 5 个。
超期批次（最多展示10个）：PT-URG-002，PT-NORM-003，PT-EXT-005，PT-MIX-009，PT-COLLIDE-011
排产执行遇到问题，请联系管理员查看日志。
错误摘要：1 条 排产执行遇到问题，请联系管理员查看日志。
```

数据库结果：

| 字段 | 值 |
|---|---|
| `ScheduleHistory.version` | `2` |
| `ScheduleHistory.result_status` | `partial` |
| `ScheduleHistory.batch_count` | `12` |
| `ScheduleHistory.op_count` | `39` |
| `Schedule` 行数 | `38` |
| 已推进到 `scheduled` 的批次 | 11 个 |
| 仍为 `pending` 的压测批次 | 15 个，包括失败边界批次和 `PT-COLLIDE-011` |

`PT-COLLIDE-011` 只有前 3 道工序进入版本 2，缺少第 40 道 `压测装配`。这条是本轮最重要的压力边界。

### 甘特图接口对账

#### 设备视图

请求：

```text
GET /scheduler/gantt/data?view=machine&start_date=2026-05-04&end_date=2026-05-20&version=2
```

结果：

| 字段 | 值 |
|---|---|
| `success` | `true` |
| `data.version` | `2` |
| `data.task_count` | `38` |
| `data.week_start` | `2026-05-04` |
| `data.week_end` | `2026-05-20` |
| 批次覆盖 | 12 个成功路径批次都能在任务里看到 |
| 设备覆盖 | `MCQA-A1`、`MCQA-G1`、`MCQA-M1`、`MCQA-T1`、`MCQA-T2`、`外协/未分配` |

#### 人员视图

请求：

```text
GET /scheduler/gantt/data?view=operator&start_date=2026-05-04&end_date=2026-05-20&version=2
```

结果：

| 字段 | 值 |
|---|---|
| `success` | `true` |
| `data.version` | `2` |
| `data.task_count` | `38` |
| 人员覆盖 | `OPQA-A`、`OPQA-B`、`OPQA-C`、`OPQA-D`、`外协/未分配` |
| 批次覆盖 | 12 个成功路径批次都能在任务里看到 |

浏览器打开正式排产甘特图：

```text
/scheduler/gantt?view=machine&start_date=2026-05-04&end_date=2026-05-20&version=2
```

页面检查结果：

- 页面有甘特图标题。
- 页面能看到 `v2`。
- 页面能看到 `PT-CRIT-001`。
- 页面能看到 `PT-COLLIDE-011`。
- 截图已保存到 `/tmp/aps-browser-scheduler-stress.IXpgq8/browser-artifacts/gantt-v2-machine.png`。

### 只读 SQL

```sql
SELECT version, result_status, batch_count, op_count, created_by
FROM ScheduleHistory
ORDER BY version;

SELECT version, COUNT(*)
FROM Schedule
GROUP BY version
ORDER BY version;

SELECT
  bo.batch_id,
  COUNT(*) AS schedule_rows,
  MIN(s.start_time) AS first_start,
  MAX(s.end_time) AS last_end
FROM Schedule s
JOIN BatchOperations bo ON bo.id = s.op_id
WHERE s.version = 2
GROUP BY bo.batch_id
ORDER BY bo.batch_id;

SELECT bo.batch_id, bo.seq, bo.op_type_name
FROM BatchOperations bo
WHERE bo.batch_id IN (
  'PT-CRIT-001', 'PT-URG-002', 'PT-NORM-003', 'PT-EXT-004',
  'PT-EXT-005', 'PT-LONG-006', 'PT-SHORT-007', 'PT-READYDATE-008',
  'PT-MIX-009', 'PT-EXT-LONG-010', 'PT-COLLIDE-011', 'PT-TINY-012'
)
AND NOT EXISTS (
  SELECT 1 FROM Schedule s
  WHERE s.version = 2 AND s.op_id = bo.id
)
ORDER BY bo.batch_id, bo.seq;
```

最后一条 SQL 本轮只返回：

```text
PT-COLLIDE-011 / 工序40 / 压测装配
```

### 本轮发现的待跟进点

- 部分完成时，页面能说出“成功 38/39，失败 1”，但具体失败原因在页面提示里仍偏泛，只显示“排产执行遇到问题，请联系管理员查看日志”。数据库里的具体原因是：`PT-COLLIDE-011_40` 预计 `2026-05-21 08:18` 完工，超过 `2026-05-20` 窗口。后续如果继续优化提示，应该把这类窗口超限原因直接显示给用户。
- 本轮运行时文件写出的端口是 `5000`，但实际服务在 `61661`。复跑时要以真实可访问地址为准，不能只看 `aps_port.txt`。

---

下面保留 2026-05-01 的最小复验数据。它适合快速验证“单批次模拟排产后甘特图不空白”和几个最基本失败提示；上面的复杂压测适合验证多批次、多资源、多边界。

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
