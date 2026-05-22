---
doc_type: verification
slug: p1-silent-fallback-verification-repair-plan
status: completed
created_at: 2026-05-21
updated_at: 2026-05-22
confidence: high
source_inventory: .codestable/compound/2026-05-20-explore-current-silent-fallback-inventory.md
closeout_inventory: .codestable/compound/2026-05-20-explore-current-silent-fallback-inventory.md
closeout_evidence_dir: evidence/QualityGate/silent_fallback_inventory_acceptance/
scope: P1 silent fallback verification and repair plan
tags:
  - silent-fallback
  - p1
  - verification
  - repair-plan
  - scheduler
  - quality-gate
---

# P1 静默回退全面核实与修复计划

## 0. 说明

本文件汇总对 `.codestable/compound/2026-05-20-explore-current-silent-fallback-inventory.md` 中 **P1 静默回退**条目的只读核实结果与修复计划。

- 本轮未进入 Plan Mode。
- 本轮未修改业务代码。
- 主代理读取原始 inventory 后，并行调用 11 个前台 Sub Agent 分模块深入引用链核查。
- 主代理仅做结论合并、去重、优先级归并与修复计划整理。

### 0.1 2026-05-22 收口状态

本文件已从“待执行计划”关闭为历史核实与修复计划留档，不再代表当前仍有一轮 active work 正在等待执行。

- 2026-05-21 的“本轮未进入 Plan Mode / 本轮未修改业务代码”只描述当日只读核实轮次。
- 2026-05-22 已发生后续修复、严格扫描 CLI 补齐、回归验证和证据补档；当前可复现收口入口以 `source_inventory` / `closeout_inventory` 指向的 inventory 文档为准。
- 真实严格扫描命令是 `.venv/bin/python -m tools.quality_gate_scan --strict`，成功时保持无输出；计数快照命令是 `.venv/bin/python -m tools.quality_gate_scan --strict --json`。
- 当前质量门禁边界是 `tools.quality_gate_operations.architecture_silent_scan_entries()` 与 `开发文档/技术债务治理台账.md` 的交集口径，不是本计划原始静态清单的 181 / 77 文件历史口径。
- 当前台账检查快照：`silent_fallback_count=100`，证据见 `evidence/QualityGate/silent_fallback_inventory_acceptance/quality_gate_ledger_check.log`。

收口证据索引：

- 最新验收表：`.codestable/compound/2026-05-20-explore-current-silent-fallback-inventory.md` 的“当前验收结果”。
- 命令 receipt：`evidence/QualityGate/silent_fallback_inventory_acceptance/*.log`。

核查覆盖模块：

1. 排产算法与排序基础解析：`dispatch_rules.py`、`date_parsers.py`、`sort_strategies.py`
2. Greedy scheduler seed 链路：`core/algorithms/greedy/scheduler.py`
3. OR-Tools warm-start：`core/algorithms/ortools_bottleneck.py`
4. 排产日历引擎：`core/services/scheduler/calendar_engine.py`
5. 排产持久化：`core/services/scheduler/run/schedule_persistence.py`
6. 甘特关键链：`core/services/scheduler/gantt_critical_chain.py`
7. 排产摘要链路：`core/services/scheduler/summary/*`
8. 工艺路线 / 外协导入：`core/services/process/*`
9. 仓储 / 版本号 / 配置：`data/repositories/*`
10. 备份维护锁：`core/infrastructure/backup.py`
11. 启动链进程探针：`web/bootstrap/launcher_processes.py`

---

## 1. 总体结论

原 inventory 的 P1 清单采用“保守静态口径”。人工沿调用链核实后，可以分成三类。

### 1.1 确认为真 P1，需要优先修

这些问题可能导致排产结果、配置、持久化、摘要可信度或系统可用性被静默破坏：

1. `core/algorithms/greedy/scheduler.py::_valid_seed_result`
   - 可导致 seed 工序先从待排 operations 中被过滤，又没有进入结果，最终出现“工序消失但排产成功”。

2. `core/services/scheduler/calendar_engine.py::_parse_shift_start`
   - inventory 中描述为回退 `00:00`，当前代码实际回退 `08:00`。
   - 问题仍成立：非空非法班次时间会静默改写排产日历。

3. `core/services/scheduler/summary/*`
   - `_metric_int`、`_meta_int`、size guard minimal summary、warning append failure 会让降级原因、风险计数、用户提示被吞掉或弱化。

4. `data/repositories/config_repo.py::count_all`
   - 转换异常返回 `0`，可能把非空配置库误判为空库，进而默认值 bootstrap 覆盖用户配置。

5. `data/repositories/external_group_repo.py::update`
   - `UPDATE 0 rows` 不报错。直接 repo 调用会静默成功；服务并发场景可能部分提交后才失败。

6. `core/infrastructure/backup.py::maintenance_window`
   - 维护锁 metadata 写入失败后仍进入维护窗口，可能留下不可自愈空锁，导致系统长期 503 / busy。

7. `core/services/process/unit_excel/parser.py`
   - `_to_float()` 非空非法数值静默变 `None`，工时 / 外协周期样本被丢弃。
   - `_parse_step_seq()` 无法解析工序号时缺少字段级诊断。

8. `core/services/process/route_parser_constraints.py::_resolve_supplier_op_type_name`
   - 供应商工种映射加载失败只进日志，用户只看到泛化“无供应商”，根因静默。

9. `core/services/scheduler/run/schedule_persistence.py`
   - inventory 命中的错误 tuple 本身不是静默落库，但核查发现更大风险：非 datetime 时间、internal 缺资源、source 不合法可能通过 payload 校验，造成晚失败或不可信落库。

10. `core/services/scheduler/gantt_critical_chain.py`
    - `_eligible_process_edge` / `_eligible_resource_edge` 的 `except -> False` 可能静默丢边，最终返回 `available=True` 但关键链错误。

### 1.2 不是排产正确性 P1，但需要可观测治理

1. `core/algorithms/ortools_bottleneck.py`
   - OR-Tools 只是可选 warm-start，失败不会直接生成错误排程。
   - 但用户启用 `ortools_enabled=yes` 时，依赖缺失、模型异常、求解失败会被压成 `None`，绕过现有 degradation。

2. `core/algorithms/greedy/date_parsers.py`
   - 低层 `parse_date` / `parse_datetime` 兼容返回 `None` 可以保留。
   - 但排序、FIFO、SGS 评分链路里非法日期会被当成“缺失日期”，需要 warning / counter。

3. `web/bootstrap/launcher_processes.py`
   - 强杀链路基本 fail-closed，不会身份未知仍强杀。
   - 但 legacy bool 探针把 `unknown` 折叠成 `False`，例如质量门禁可能把“无法确认 PID 状态”当 stale。

4. `core/algorithms/dispatch_rules.py` / `core/algorithms/sort_strategies.py`
   - 生产主链目前主要走 strict 校验，不直接用这些兼容 helper。
   - helper 本身仍有 silent default，建议改成 strict + compatible wrapper。

### 1.3 静态清单中部分为误报或已可观测

1. `part_route_validation.coerce_external_default_days`
   - 已进入 `ParseResult.warnings`，非严格模式用户可见，严格模式上游会失败。

2. `route_parser_constraints._resolve_supplier_default_days`
   - 默认 1 天会进入 warnings / errors，非静默。

3. `gantt_critical_chain.compute_critical_chain_from_rows`
   - candidate rows 异常会返回 `available=false`，经 API/UI 展示黄条，不是静默。
   - 但 adopted 方案计算异常边界仍需补齐。

4. `backup._copy_db_file` 的 busy_timeout PRAGMA `pass`
   - 已有 sqlite connect timeout + backup retry，不会静默复制半份 DB。
   - 属 best-effort，可最后治理。

---

## 2. 去重后的优先级总表

| 模块 | 核实结论 | 优先级 |
|---|---|---|
| greedy seed `_valid_seed_result` | 真 P1，可能工序消失但成功 | 最高 |
| calendar_engine shift_start | 真 P1，非法日历静默改写排产 | 最高 |
| summary `_metric_int` / size guard | 真 P1，降级原因和风险计数丢失 | 最高 |
| config_repo count_all | 真 P1，可能覆盖用户配置 | 最高 |
| backup maintenance lock metadata | 真 P1，可能长期 503/busy | 最高 |
| schedule_persistence validation gaps | 真 P1，可能晚失败或不可信落库 | 高 |
| unit_excel `_to_float` / `_parse_step_seq` | 真 P1，导入字段静默丢弃 | 高 |
| supplier op_type mapping | 半静默，根因不可见 | 高 |
| external_group update 0 rows | 真风险，需 repo 层拒绝 | 高 |
| schedule_history get_latest_version | 不致版本冲突，但隐藏历史/冻结窗口 | 中高 |
| critical_chain `_eligible_*` | 潜在真静默丢边 | 中高 |
| OR-Tools | 非正确性 P1，但启用后失败不可见 | 中 |
| date_parsers | 调用层需可观测，低层可兼容 | 中 |
| dispatch/sort helper | 当前主链低风险，做 strict/兼容分层 | 中低 |
| launcher_processes | 强杀安全基本闭合，修 unknown 折叠 | 中低 |
| part_route_validation default_days | 已可观测，非 P1 | 无需优先 |
| `_copy_db_file` busy_timeout pass | best-effort，非 P1 | 最后 |

---

## 3. 详细修复计划

# P1-0：防止 Greedy seed 工序消失

## 3.1 涉及文件

- `core/algorithms/greedy/scheduler.py`
- `core/algorithms/greedy/seed.py`
- `core/services/scheduler/run/schedule_seed_contracts.py`
- 可能涉及：
  - `core/algorithms/greedy/run_state.py`
  - result summary invariant 测试

## 3.2 当前问题

调用链：

```text
GreedyScheduler.schedule
  -> normalize_seed_results()
       返回 normalized_seed, seed_op_ids
  -> _drop_seeded_operations()
       根据 seed_op_ids 过滤原 operations
  -> _apply_seed_results()
       _valid_seed_result(result)
       非 datetime / op_id 异常时返回 False
```

真实风险：

- seed 的 `op_id` 已进入 `seed_op_ids`。
- 原 operation 被 `_drop_seeded_operations` 过滤。
- `_apply_seed_results` 又静默跳过 seed。
- 结果：该工序既不在原排产，也不在 seed 结果。
- summary 可能仍然 `success=True`，且 `total_ops` 被低估。

## 3.3 修复策略

1. 保证不变量：进入 `seed_op_ids` 的 seed 必须一定能 apply。

   在 `normalize_seed_results()` 阶段完成：

   - `op_id` 必须可规范化为正整数。
   - `start_time/end_time` 必须是 `datetime` 或可被明确转换成 `datetime`。
   - `start_time < end_time`。
   - 不满足则：
     - strict：抛 `ValidationError`
     - non-strict：drop seed，加入 warning/counter，但不得加入 `seed_op_ids`

2. 修 `coerce_seed_results()`。

   `schedule_seed_contracts.py` 当前允许字符串时间通过。应改成：

   - 字符串 ISO/标准格式可解析为 `datetime`；
   - 无法解析直接 `ValidationError(field="seed_results")`；
   - 不允许把字符串时间留给算法层。

3. `_apply_seed_results` 不再静默跳过。

   `_valid_seed_result` 不应只返回 bool。建议：

   ```python
   validate_seed_result(result) -> None
   ```

   非法直接抛内部 invariant 错误，或者返回结构化 issue，由 scheduler 汇总为 `ValidationError`。

4. 增加 seed count 一致性校验。

   在 `_prepare_run_state` 后检查：

   ```text
   state.seed_count == len(normalized_seed)
   ```

   不一致直接失败，不能成功返回。

5. 统一 op_id 解析。

   `_safe_op_id` 返回 0 是诊断降级。建议新增统一 helper：

   ```python
   normalize_positive_op_id(value, field="op_id") -> int
   ```

   覆盖：

   - `_safe_op_id`
   - `operation_sort_key`
   - result builder
   - SGS candidate meta

## 3.4 测试建议

1. seed 时间是字符串：
   - 修复策略若选择转换：结果包含 seed 行，后续工序从 seed end 后开始。
   - 修复策略若选择 fail-fast：抛 `ValidationError`。
   - 不能出现“只剩后续工序，seed 工序消失且 success”。

2. seed op_id 合法但时间非 datetime：
   - 不得进入 `seed_op_ids` 后又被 `_apply_seed_results` 跳过。

3. `op.id == "1.0"` / `op.id == "bad"`：
   - 要么统一转换，要么明确报错。
   - 不允许 `_safe_op_id` 静默 0 后继续。

4. batch_order 和 SGS 两种 dispatch 都覆盖。

---

# P1-1：排产日历读链 fail-fast

## 4.1 涉及文件

- `core/services/scheduler/calendar_engine.py`
- `core/services/scheduler/calendar_admin.py`
- `core/services/common/datetime_normalize.py`
- 日历 repo / 排产集成测试

## 4.2 当前问题

inventory 说回退 `00:00`，当前代码实际回退 `08:00`。

但问题仍成立：

```text
非空非法 shift_start
  -> except
  -> time(8, 0)
  -> DayPolicy
  -> adjust_to_working_time / add_working_hours / get_efficiency
  -> 错误起止时间、资源占用、甘特图、报表
```

## 4.3 修复策略

1. `_parse_shift_start()` 改为：

   - `None` / 空字符串：允许默认 `08:00`；
   - 合法 `HH:MM` / `HH:MM:SS` / 全角冒号：正常解析；
   - 非空非法：抛 `ValidationError` 或 `BusinessError(ErrorCode.CALENDAR_ERROR)`。

2. 同步修 `_override_shift_hours_by_shift_end()`：

   - 空 `shift_end`：使用原 `shift_hours`；
   - 非空非法 `shift_end`：fail-fast；
   - 保留跨午夜逻辑。

3. 读链复用写链的 `normalize_hhmm()`，避免 Admin 与 Engine 规则不一致。

4. 错误消息包含：

   - 日期；
   - 是否个人日历；
   - operator_id；
   - 原始字段；
   - 期望格式。

5. 如果产品必须兼容历史脏数据，则至少：

   - `logger.warning`；
   - summary degradation；
   - 页面提示“工作日历非法，本次排产不可用或已降级”。

   但对 P1 推荐 fail-fast，避免生成错误排程。

## 4.4 测试建议

1. `shift_start=None` / `""` 默认 08:00。
2. `shift_start="07:30"`、`"07:30:00"`、`"07：30"` 正常。
3. `shift_start="7.30"`、`"25:00"`、`"abc"` 抛业务错误。
4. 全局日历正确、个人日历非法：使用该 operator 排产时报错。
5. 合法跨午夜 `20:00-04:00` 不被破坏。
6. 非法跨午夜开始时间 `20点-04:00` fail-fast。

---

# P1-2：排产摘要可信度

## 5.1 涉及文件

- `core/services/scheduler/summary/schedule_summary.py`
- `core/services/scheduler/summary/schedule_summary_degradation.py`
- `core/services/scheduler/summary/summary_runtime_state.py`
- `core/services/scheduler/summary/summary_size_guard.py`
- `web/viewmodels/scheduler_degradation_presenter.py`
- 分析页 viewmodel / metrics

## 5.2 `_metric_int`：最高优先级

### 当前问题

```python
_metric_int(... except Exception: return 0)
```

影响字段：

- `invalid_due_count`
- `unscheduled_batch_count`

这些直接影响：

- result summary；
- degradation events；
- 分析卡片；
- 延期风险提示。

### 修复策略

1. 不再返回裸 int，改为状态对象：

   ```python
   MetricIntParse(
       value: int | None,
       present: bool,
       valid: bool,
       error: str | None,
   )
   ```

2. 对关键计数以 runtime 重算为主，metrics 仅做对照。

3. metrics 缺失、非法、与 runtime 不一致时，写入：

   - `summary_metric_parse_failed`
   - 或复用 `summary_merge_failed`
   - 或 diagnostics 字段。

4. 不能再用：

   ```python
   metric_count or runtime_count
   ```

   因为无法区分合法 0 与解析失败。

### 测试建议

- `best_metrics.invalid_due_count="bad"`，实际有非法 due date：
  - top-level `invalid_due_count` 不能是 0；
  - 有 summary metric parse failed 诊断。

- `best_metrics.unscheduled_batch_count="bad"`，实际有未排批次：
  - `unscheduled_batch_count` 正确；
  - 分析卡片仍显示。

## 5.3 size guard minimal summary 保留降级原因

### 当前问题

`summary_size_guard._minimal_summary_for_size_guard()` 会保留：

- `degraded_success`
- `invalid_due_count`
- `unscheduled_batch_count`

但可能丢掉：

- `degradation_events`
- `degradation_counters`
- `degraded_causes`
- `warnings`

结果：

- 页面只知道 `degraded_success=True`；
- 但没有主提示原因。

### 修复策略

minimal summary 必须保留有界降级信息：

```python
degraded_success
degraded_causes
degradation_events  # capped
degradation_counters
degradation_events_truncated
warning_count
warnings_sample
```

### 测试建议

构造超大 summary 触发 size guard，原始有：

```python
degraded_success=True
degraded_causes=["downtime_avoid_degraded"]
degradation_events=[...]
```

断言裁剪后：

- `degradation_events` 或 `degraded_causes` 仍存在；
- `build_primary_degradation()` 仍能生成主提示；
- `summary_truncated=True`。

## 5.4 `_meta_int` downtime meta

### 当前问题

downtime partial fail count 转换失败返回 0，会弱化或丢失停机降级细节。

### 修复策略

1. `_meta_int` 改状态返回。
2. count 字段存在但非法时：
   - 不当 0；
   - 若 sample 非空，可按 `len(sample)` 或至少 1；
   - 添加 meta parse failed 诊断。
3. `_compute_downtime_degradation()` 把 meta parse failed 也视为降级原因。

### 测试建议

- `downtime_partial_fail_count="bad"` 且 sample 非空：
  - 产生 downtime degradation；
  - 不静默当 0。

## 5.5 `_append_summary_warning`

### 当前问题

warnings 写回失败返回 False，只靠 logger，不进 summary degradation。

### 修复策略

1. `build_overdue_items()` meta 中返回：

   ```python
   warning_appended
   warning_append_failed
   ```

2. summary degradation 中增加：

   - `summary_warning_append_failed`
   - 或复用 `summary_merge_failed`

### 测试建议

不可设置 warnings 的 summary 对象 + 非法 due date：

- `invalid_due_date` event 存在；
- warning append failure 也可观测。

## 5.6 `serialize_end_date`

### 当前问题

`isoformat()` 异常后 `pass`，继续 `str(end_date)`，可能输出无意义对象字符串。

### 修复策略

- end_date 序列化失败时返回 `None` 或安全文本；
- 加 summary field degradation；
- 不把对象 repr 暴露给用户。

---

# P1-3：排产持久化 payload 校验边界

## 6.1 涉及文件

- `core/services/scheduler/run/schedule_persistence.py`
- `core/services/scheduler/run/schedule_orchestrator.py`
- `data/repositories/schedule_repo.py`

## 6.2 核实结论

inventory 命中的：

- op_id 转换失败返回 tuple；
- 时间不可比较返回 tuple；

本身不是静默落库，因为 `build_validated_schedule_payload()` 会收集并抛 `ValidationError`，且发生在版本分配前。

但核查发现更大的 P1 风险：

1. `_result_identity()` getter 异常会静默丢 identity 字段。
2. start/end 只校验可比较，不要求 `datetime`。
3. internal 行可能缺 `machine_id/operator_id` 仍保存。
4. `source` 未校验合法性，也未与原 operation source 对齐。
5. payload 通过后晚失败会造成版本跳号；更严重的是错误结果可能成功保存。

## 6.3 修复策略

1. `_result_identity()` 不再静默丢字段。

   建议输出安全占位：

   ```text
   op_id=<unreadable:ValueError>
   ```

   或在 details 里加入：

   ```python
   identity_read_errors
   ```

2. `_build_validated_schedule_row()` 严格校验时间：

   - `start_time/end_time` 必须是 `datetime`；
   - 或明确 normalize 字符串到 datetime；
   - 失败统一 `invalid_schedule_rows`。

3. 校验 source：

   - 仅允许 `internal` / `external`；
   - 缺 source 可用 operation.source 补齐；
   - result.source 与 operation.source 不一致应拒绝或以 DB 为准并记录。

4. internal 资源校验：

   - source 为 internal 时，`machine_id/operator_id` 必须非空；
   - 更稳：以原始 operation source 为准，不完全信任 result.source。

5. `persist_schedule_core_in_tx()` 加二次 invariant，防绕过 payload builder：

   - rows 非空；
   - op_id 不重复；
   - start/end 是 datetime；
   - internal 资源非空；
   - op_id 在 reschedulable scope 内。

## 6.4 测试建议

- result.op_id property 抛异常：错误 details 仍能定位 index，并标记 unreadable。
- start/end 是字符串：payload 阶段失败，不到 `_format_dt()` 才炸。
- internal 缺 machine/operator：拒绝保存，不更新 op/batch 状态。
- source 缺失/不一致：行为固定，不静默保存。
- 手工构造非法 `ValidatedSchedulePayload` 直接调用 persist：二次拒绝并回滚。

---

# P1-4：仓储 / 配置 / 版本号

## 7.1 `ConfigRepository.count_all`

### 当前风险

```python
except Exception:
    return 0
```

调用链：

```text
count_all()
  -> is_pristine_store()
  -> ensure_defaults()
  -> bootstrap_registered_defaults(existing_keys=set())
  -> set_batch(... ON CONFLICT DO UPDATE)
```

一旦 count 转换异常返回 0，可能把已有配置当空库，默认值覆盖用户配置。

### 修复策略

1. `count_all()` 转换异常 fail-fast：

   ```python
   except Exception as e:
       raise AppError(ErrorCode.DB_QUERY_ERROR, "读取排产配置数量失败", cause=e)
   ```

2. `is_pristine_store()` 不要 `or 0` 掩盖异常。

3. `ensure_defaults()` 不应只凭 count 决定覆盖路径。更稳：

   - 读取 existing keys；
   - 只插入缺失 key；
   - bootstrap 默认值用 insert-missing 语义，避免覆盖已有用户配置。

### 测试建议

- 已有用户配置 `sort_strategy=weighted`；
- mock `count_all()` 返回不可转 int；
- 调 `get_snapshot()` 或 `ensure_defaults()`：
  - 修复后抛 AppError；
  - 用户配置不被覆盖。
- 空库正常 bootstrap。
- 非空缺少新 key 时只补缺失，不覆盖已有。

## 7.2 `ScheduleHistoryRepository.get_latest_version`

### 核实结论

- 不会直接造成新版本冲突，因为写入用 `allocate_next_version()`。
- 但返回 0 会误导 latest、报表、甘特、冻结窗口，以为无历史。

### 修复策略

1. `get_latest_version()` 转换异常 fail-fast，不返回 0。
2. version < 0 也报错。
3. 更新过期注释：新版本不是 `MAX(version)+1`，而是 `ScheduleVersionSeq`。

### 测试建议

- `fetchvalue()` 返回 `"bad-version"`：
  - 抛 AppError；
  - 不返回 0。
- latest 页面 / report / freeze window 对异常版本给用户可见错误。

## 7.3 `ExternalGroupRepository.update`

### 当前风险

- PRAGMA `pass` 只影响 `updated_at`，不是核心。
- 真风险是 `UPDATE 0 rows` 不报错。

### 修复策略

1. PRAGMA 失败至少 warning。
2. repo 层检查 rowcount：

   ```python
   cur = self.execute(...)
   if cur.rowcount == 0:
       raise BusinessError(... "外协组不存在或已删除")
   ```

3. service 层把 `_get_group_or_raise()` 放事务内，缩小并发删除窗口。
4. 路由校验 `group_id` 是否属于 URL 里的 `part_no`。

### 测试建议

- 不存在 group_id 调 update：抛错。
- 并发删除场景：PartOperations 不被部分提交。
- 路由错误 group_id 不 flash success。

---

# P1-5：维护锁

## 8.1 涉及文件

- `core/infrastructure/backup.py`
- `web/bootstrap/factory.py`
- `web/routes/system_backup*.py`
- `core/services/system/maintenance/backup_task.py`

## 8.2 当前真 P1

```python
lock_fd = os.open(...)
try:
    os.write(lock_fd, payload)
except Exception:
    pass
```

如果 lock 文件创建成功但 metadata 写失败：

- 维护窗口继续执行；
- 进程崩溃后可能留下空锁；
- parser 得不到 pid/ts；
- stale 自愈无法判断；
- 系统长期 503 / backup busy / restore busy。

## 8.3 修复策略

1. metadata 写失败必须视为获取锁失败：

   - close fd；
   - delete lock file；
   - release mutex；
   - 抛 `MaintenanceWindowError(code="lock_metadata_write_failed")`。

2. 处理短写：

   - 循环写满；
   - 或 `os.fdopen(...).write()` + flush；
   - 实际写入不足视为失败。

3. 可选 fsync lock fd。

4. lock 内容增加版本和完整性字段：

   ```text
   version=1 pid=... action=... ts=... complete=1 nonce=...
   ```

5. malformed / empty lock 状态分类：

   ```python
   valid_metadata
   malformed
   parse_errors
   mtime_age_seconds
   ```

6. malformed lock 自愈策略：

   - 短时间内仍 active；
   - 超过阈值后可自愈删除；
   - 必须记录 warning；
   - 更优长期方案：heartbeat 或 OS 文件锁。

7. 线程本地 state 清理：

   - cleanup 前先 `state["depth"] = 0`；
   - nested 判断必须检查 `depth > 0`、db_path 匹配、lock file 存在；
   - 清理失败 warning。

## 8.4 测试建议

- mock `os.write` 抛异常：
  - 抛 MaintenanceWindowError；
  - lock 文件不存在；
  - mutex 释放；
  - 后续可重试。
- mock `os.write` 短写：同上。
- 空 lock 文件 stale：
  - 按设计自愈或明确阻断；
  - 不无诊断永久 503。
- 残留 thread-local depth=0：
  - 不应走 nested。
- `_copy_db_file` PRAGMA 失败：
  - 仍可成功复制，作为 best-effort 测试。

---

# P1-6：工艺路线 / 外协导入残余静默

## 9.1 `route_parser_constraints._resolve_supplier_op_type_name`

### 当前问题

op_type repo 读取失败：

- 只 `safe_warning(logger)`；
- 返回 None；
- 用户最多看到泛化“无供应商”，看不到根因。

### 修复策略

1. `SupplierConstraintResolver` 返回 global issues：

   ```python
   supplier_map, supplier_issues, global_issues
   ```

2. `RouteParser.parse()`：

   - non-strict：global issues 进入 warnings；
   - strict：global issues 进入 errors。

3. 更优：`RouteParser` 已加载 op_types，可构造 `op_type_by_id` 传 resolver，避免 resolver 二次 repo.get。

### 测试建议

- op_types_repo.get 抛异常：
  - non-strict：`ParseResult.warnings` 包含“供应商工种映射加载失败”；
  - strict：`ParseResult.errors`，`ParseStatus.FAILED`。
- supplier.op_type_id 不存在：
  - 同样显性化。

## 9.2 `unit_excel/parser.py`

### 当前问题

1. `_to_float()`：

   - `"abc"`、`True`、`inf`、`nan`、0、负数都可能变 `None` 或错误正数；
   - 后续工时样本被静默忽略；
   - 只在部分 builder 路径有泛化 diagnostics。

2. `_parse_step_seq()`：

   - 无法解析工序号时返回 None；
   - 后续 builder 跳过；
   - 缺行号 / 字段级提示。

### 修复策略

1. `StepRecord` 增加：

   ```python
   row_num
   diagnostics/issues
   ```

2. `_to_float()` 改结构化解析：

   ```python
   ParsedFloat(
       value,
       issue_code,
       message,
       raw_value,
       row_num,
       field,
   )
   ```

3. 规则：

   - 空白：允许 None，不 warning；
   - bool：invalid_number；
   - 非数字：invalid_number；
   - NaN/Inf：non_finite_number；
   - <=0：number_below_minimum；
   - 每项进入 diagnostics sample。

4. `_parse_step_seq()` 改结构化结果：

   ```python
   StepSeqParseResult(seq, has_step_code, issue_code, message)
   ```

5. builder 把 StepRecord issues 汇总到 `ConvertedTemplates.diagnostics`。

6. CLI / exporter 显示诊断：

   - stdout 打印 counters；
   - 可选输出 `转换诊断.json` 或 `转换诊断.xlsx`。

### 测试建议

- `step_text="ABC粗车"`：
  - diagnostics 有 `invalid_step_seq`，含 row/part_no/machine_id。
- 工时字段填 `"abc"`、`True`、`"inf"`、`"nan"`、0、-1：
  - diagnostics 有 invalid / non-finite / below-minimum；
  - 不静默生成 0 工时。
- 外协周期样本部分有效、部分无效：
  - 有效样本仍参与；
  - 无效单元格也显性化。

---

# P1-7：关键链静默丢边

## 10.1 涉及文件

- `core/services/scheduler/gantt_critical_chain.py`
- `core/services/scheduler/gantt_critical_chain_provider.py`
- `core/services/scheduler/gantt_service.py`
- `core/services/scheduler/gantt_contract.py`

## 10.2 核实结论

- `compute_critical_chain_from_rows()` 返回 `_unavailable_result("rows_exception")` 是可观测的，不是静默。
- 但 `_eligible_process_edge` / `_eligible_resource_edge` 的 `except -> False` 会静默丢前驱边。
- `compute_critical_chain()` adopted 方案只捕获 repo load，不捕获计算异常，可能导致甘特 500，而不是 graceful unavailable。

## 10.3 修复策略

1. 删除 helper 内 broad catch：

   - 缺字段 / 缺 datetime：显式返回 False；
   - 非预期异常：抛出，让外层转 unavailable。

2. `compute_critical_chain()` adopted 方案对齐 rows 方案：

   ```python
   try:
       return _compute_critical_chain_from_loaded_rows(rows)
   except Exception:
       logger.exception(...)
       return _unavailable_result("rows_exception")
   ```

3. 加服务端日志：

   - version；
   - plan role / source / candidate_id；
   - row_count；
   - reason code；
   - exception stack。

4. public payload 可继续不泄露内部 `rows_exception`，但服务端必须可诊断。

## 10.4 测试建议

- monkeypatch `_eligible_process_edge` 抛异常：
  - `compute_critical_chain_from_rows()` 返回 `available=False`；
  - 不返回 `available=True` 的错误关键链。
- adopted rows 加载成功但计算异常：
  - `/scheduler/gantt/data` 返回 200；
  - `critical_chain.available=False`；
  - `degraded=True`；
  - UI 可显示黄条；
  - 不泄露异常详情。

---

# P1-8：OR-Tools 可选降级显性化

## 11.1 涉及文件

- `core/algorithms/ortools_bottleneck.py`
- `core/services/scheduler/run/schedule_optimizer_steps.py`
- `core/services/scheduler/summary/*`

## 11.2 核实结论

不是“排程正确性 P1”：

- OR-Tools 只是可选 warm-start；
- 后续 multi-start / greedy 仍会给结果。

但是真实可观测缺陷：

- import 失败返回 None；
- 模型异常被 catch-all 吞掉；
- solver 非成功状态返回 None；
- 上层 `_record_ortools_failure()` 被绕过；
- 用户启用 `ortools_enabled=yes` 也不知道没跑成功。

## 11.3 修复策略

推荐结构化 outcome：

```python
WarmStartOutcome(
    status,
    order,
    reason,
    details,
)
```

状态建议：

```text
SUCCESS
NO_CANDIDATE
SKIPPED_BUDGET
DEPENDENCY_UNAVAILABLE
SOLVER_UNKNOWN
SOLVER_MODEL_INVALID
SOLVER_INFEASIBLE
FAILED_EXCEPTION
```

上层规则：

- `NO_CANDIDATE` / `SKIPPED_BUDGET`：debug，不用户告警。
- `DEPENDENCY_UNAVAILABLE`：用户启用时 warning + degradation。
- `MODEL_INVALID` / `INFEASIBLE` / `FAILED_EXCEPTION`：warning + `ortools_warmstart_failed_count`。
- `UNKNOWN`：通常 info/debug，不强告警。

如果短期小改，可加 callback：

```python
on_event("dependency_unavailable", details)
on_event("failed_exception", details)
```

## 11.4 测试建议

- 模拟 import 失败：
  - 继续普通排程；
  - `ortools_warmstart_failed_count` 或新 code 增加；
  - summary 有 degradation。
- fake solver `Solve()` 抛异常：
  - 不阻断主排程；
  - failure 可见。
- solver status：
  - OPTIMAL / FEASIBLE 返回 order；
  - UNKNOWN 不误报 failure；
  - MODEL_INVALID / INFEASIBLE 进入 degradation。

---

# P1-9：日期解析、排序策略、派工规则治理

## 12.1 `date_parsers.py`

### 当前问题

低层 parser 返回 None 可作为兼容合同，但调用层把坏值当缺失：

- due_date 非法 -> 无交期；
- ready_date 非法 -> readiness gate 失真；
- FIFO created_at 非法 -> 排最后；
- SGS scoring due_date 非法 -> 当无交期。

### 修复策略

1. 新增状态解析：

   ```python
   parse_date_state(value) -> (date | None, invalid: bool)
   parse_datetime_state(value) -> (datetime | None, invalid: bool)
   ```

   空值：`(None, False)`
   非空非法：`(None, True)`

2. `parse_date()` / `parse_datetime()` 保留兼容包装。

3. 调用层补 warning / counter：

   - `ordering.build_batch_sort_inputs`
   - `_build_batch_order`
   - optimizer `_build_order`
   - SGS scoring due_date 解析

4. strict 继续抛 `ValidationError`。

### 测试建议

- 非 strict 非法 due_date：
  - 仍可排产；
  - warning/counter 可见；
  - 行为固定为“无交期”。
- strict 非法 due_date：
  - 抛 `ValidationError`。
- ready_date / created_at 同理。

## 12.2 `dispatch_rules.parse_dispatch_rule` / `sort_strategies.parse_strategy`

### 核实结论

当前生产主链基本不用这些 helper，而是走 strict 配置校验。不是当前 P1 主链风险。

### 修复策略

1. 保留兼容 helper，但只捕获 `ValueError` / `TypeError`。
2. 新增 strict 函数：

   ```python
   require_dispatch_rule(...)
   require_sort_strategy(...)
   ```

3. 兼容 fallback 时必须有 collector / on_fallback 或台账 accepted risk。

## 12.3 `build_dispatch_key._safe_positive`

### 核实结论

多数非法工时上游已校验。不是当前 P1，但兜底不可观测。

### 修复策略

- 改 `_finite_positive_or_none()`；
- fallback 移到有 ctx / algo_stats 的调用层；
- 记录 `dispatch_proc_hours_defaulted_count` 等 counter。

---

# P1-10：launcher_processes 结构化 unknown

## 13.1 涉及文件

- `web/bootstrap/launcher_processes.py`
- `web/bootstrap/launcher_stop.py`
- `scripts/run_quality_gate.py`

## 13.2 核实结论

- 停止 / 强杀链路基本 fail-closed。
- 身份未知不会强杀。
- 但 `_pid_exists()` / `runtime_pid_exists()` 把 unknown 折成 False，可能被外部调用方误判 stale。

## 13.3 修复策略

1. 收紧异常捕获：

   - `_parse_pid()` 只捕获 `(TypeError, ValueError, OverflowError)`。
   - `_query_process_executable_path()` 同理。

2. 新增结构化结果：

   ```python
   runtime_pid_state(pid) -> True | False | None
   ProcessIdentityProbeResult(...)
   PowerShellResult(...)
   ```

3. 改 `scripts/run_quality_gate.py::_pid_signal()`：

   - False -> STALE
   - True -> 继续 exe match
   - None -> UNKNOWN

4. stop 失败原因更精确：

   - `pid_state_unknown`
   - `pid_identity_unknown`
   - `powershell_unavailable`

5. 强杀条件不放松：

   ```text
   pid_exists is True AND pid_match is True
   ```

## 13.4 测试建议

- Windows tasklist 抛异常：
  - `runtime_pid_state(pid) is None`
  - lock active fail-closed；
  - quality gate 返回 UNKNOWN。
- PowerShell 不可用：
  - 不强杀；
  - stop 返回失败；
  - 日志可读。
- pid_match None / pid_exists None / pid_match False：
  - 均不调用 kill。

---

## 14. 建议落地顺序

### 第一批：直接影响排产结果 / 配置 / 系统可用性

1. Greedy seed 工序消失。
2. calendar_engine 非法班次时间 fail-fast。
3. summary 关键计数 + size guard 降级信息保留。
4. ConfigRepository.count_all 防覆盖。
5. backup maintenance_window 锁 metadata 写失败。
6. schedule_persistence payload 校验补强。

### 第二批：导入与仓储一致性

7. unit_excel parser 结构化 diagnostics。
8. supplier op_type mapping root cause 显性化。
9. external_group update 0 行检查。
10. schedule_history get_latest_version fail-fast。

### 第三批：分析 / 可观测性治理

11. critical_chain 删除 helper broad catch + adopted compute unavailable。
12. OR-Tools structured outcome。
13. date parser 状态解析 + 排序 / SGS warning。
14. dispatch / sort 兼容 helper strict 化。
15. launcher_processes unknown 三态化。

### 第四批：质量门禁和台账

16. 更新静默回退扫描器识别：
    - 允许结构化 outcome；
    - 允许有 warning / counter / degradation 的兼容 fallback；
    - 不再把已显性化 helper 误归入 P1。
17. 每批修完刷新该 inventory / 技术债务台账。
18. 给所有 accepted risk 补明确注释和测试。

---

## 15. 本轮不建议优先修改的项

| 项 | 原因 |
|---|---|
| `part_route_validation.coerce_external_default_days` | 已进入 `ParseResult.warnings`，非严格用户可见，严格上游失败。 |
| `route_parser_constraints._resolve_supplier_default_days` | 默认 1 天已进入 warnings/errors。 |
| `gantt_critical_chain.compute_critical_chain_from_rows` | candidate rows 异常已 API/UI 可观测。 |
| `backup._copy_db_file` busy_timeout PRAGMA | connect timeout + retry 已存在，不会静默复制半份 DB。 |
| `ortools_bottleneck` 成功日志失败 pass | logger 自身失败可接受，不应影响排产。 |
| launcher 强杀失败 return False | 已 fail-closed，不会身份不明强杀。 |

---

## 16. 验收标准

2026-05-22 收口说明：以下标准是本计划制定时的预期验收口径；实际收口证据已落在 `closeout_inventory` 和 `closeout_evidence_dir`。以后复核时不要只看本节文字，应以可执行命令和日志 receipt 为准。

当前可复现验收命令索引：

| 验收项 | 命令 | 证据 |
|---|---|---|
| 严格静默回退门禁 | `.venv/bin/python -m tools.quality_gate_scan --strict` | `evidence/QualityGate/silent_fallback_inventory_acceptance/strict_scan.log` |
| 严格门禁计数快照 | `.venv/bin/python -m tools.quality_gate_scan --strict --json` | `evidence/QualityGate/silent_fallback_inventory_acceptance/strict_scan_json.log` |
| 严格扫描 CLI 合同 | `.venv/bin/python -m pytest tests/regression_quality_gate_scan_contract.py -q` | `evidence/QualityGate/silent_fallback_inventory_acceptance/strict_cli_contract_pytest.log` |
| 台账一致性检查 | `.venv/bin/python scripts/sync_debt_ledger.py check` | `evidence/QualityGate/silent_fallback_inventory_acceptance/quality_gate_ledger_check.log` |
| diff 空白检查 | `git diff --check` | `evidence/QualityGate/silent_fallback_inventory_acceptance/git_diff_check.log` |
| 定向核心回归 | `.venv/bin/python -m pytest tests/regression_model_helper_silent_fallback_contract.py tests/regression_models_numeric_parse_hybrid_safe.py tests/regression_strict_parse_blank_required.py tests/regression_schedule_summary_fallback_counts_output.py tests/regression_metrics_to_dict_nonfinite_safe.py tests/regression_calendar_invalid_shift_window_contract.py tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py tests/regression_seed_results_dedup.py tests/regression_unit_excel_converter_diagnostics_visible.py tests/regression_unit_excel_converter_merge_steps_and_classify.py -q` | `evidence/QualityGate/silent_fallback_inventory_acceptance/targeted_core_pytest.log` |
| 启动链 / UI mode / runtime 回归 | `.venv/bin/python -m pytest tests -q -k 'launcher or runtime or startup or stop or ui_mode or render_bridge' -p no:cacheprovider` | `evidence/QualityGate/silent_fallback_inventory_acceptance/web_startup_pytest.log` |
| Excel 模板合同脚本 | `.venv/bin/python tests/regression_excel_template_contracts.py` | `evidence/QualityGate/silent_fallback_inventory_acceptance/excel_template_contract_script.log` |
| 系统维护坏 JSON / 页面可见性合同 | `.venv/bin/python -m pytest tests/regression_maintenance_window_mutex.py tests/test_history_summary_parser.py tests/regression_system_logs_presenter_contract.py tests/regression_system_request_services_contract.py -q` | `evidence/QualityGate/silent_fallback_inventory_acceptance/system_maintenance_bad_json_pytest.log` |
| 指标 JSON 安全脚本 | `.venv/bin/python tests/regression_metrics_to_dict_nonfinite_safe.py` | `evidence/QualityGate/silent_fallback_inventory_acceptance/metrics_json_script.log` |

历史速记中的 `58 passed` / `141 passed` 没有可审计命令 receipt，已由上述 2026-05-22 证据取代，不再作为当前收口判断依据。

完成修复后，至少应满足：

1. P1 主链不再存在“错误被默认值掩盖并成功返回”的路径。
2. 允许保留的兼容 fallback 必须满足至少一项：
   - 有 warning；
   - 有 counter；
   - 有 degradation event；
   - 有 structured outcome；
   - 或明确登记 accepted risk 并有测试锁定语义。
3. 排产成功结果不能丢工序、不能静默改写日历、不能保存 internal 缺资源结果。
4. summary 即使被 size guard 裁剪，也必须保留降级原因。
5. 配置 bootstrap 不得因 count 转换异常覆盖用户配置。
6. 维护锁 metadata 写失败不得进入维护窗口，不得留下不可自愈 lock。
7. 扫描器再次扫描时，真 P1 数量应显著下降；剩余项应被归类为 observable_degrade、cleanup_best_effort 或 accepted risk。
