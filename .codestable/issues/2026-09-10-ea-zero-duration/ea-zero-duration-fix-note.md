---
doc_type: issue
status: fixed
date: 2026-09-10
owner: EA
scope: authorized-backend
---

# EA 零时长后端交付

## 结论

- 第一条真实链已闭合：实际引擎 -> worker 候选落盘 -> 正式采用 -> 正式读取 -> 试调移动/保存 -> 再采用 -> 新连接重启读取。
- 原 `op_id` / `operation_ref` 不变；正式版本与试调任务各自保留其永久身份，不冒用其他计划任务。
- 合法点始终 `start=end`；不补 epsilon、不删工序、不改 schema、不增加点状态表。
- public 点采用仍关闭，原因仅为点标记尚未完成前端联合接入。普通正时长采用不受该开关影响。
- 本轮只使用临时测试 SQLite；未操作真实 DB、现有 preview，未 stage / commit。工作区起始即存在大量其他修改。

## 合同与来源

- `schedule_payload_contract.build_validated_schedule_payload(..., point_validator=None)` 默认保持 legacy 拒绝零区间。
- 显式内部回调必须返回 `core.algorithm_contracts.schedule_point_evidence.SchedulePointEvidence`；parser 再检查类型、工序、资源、时间、原工时和整数数量。返回 bool、dict 或不匹配证据均不能放行。
- `schedule_orchestrator` 仅转接该可选回调；非 workbench 调用没有自动获得点权限。
- 工时逐项验证后计算：`setup + unit * quantity`。数量 0、setup 2 的工序仍是正时长；数量 0、setup 0 才可能是点。
- 负数相消、未知工时、非有限值和正工时被时间精度压零均拒绝。
- 候选点依据已有不可变受理事实、执行目标量、原引擎结果与 validated payload 一致性，不新增候选表字段。
- 正式点读取由采用回执和 `ScheduleHistory` audit 追到不可变 candidate/scenario，再核对实际 Schedule 行和永久身份。不能仅看当前工时或 `start=end` 猜测。
- 试调复用已有 `original_json` / admission / scenario / receipt，在原工作快照中保存 `point_basis`；不为点创建新表。
- 日历、资源身份/资格、齐套、前后置、锁和执行保护继续验证。点不进入资源占用区间，不与另一正区间产生虚假占用冲突。
- 试调把点放到班次外时直接拒绝；不能只把 end 推到下一班，制造虚假正时长。
- 正式/候选时间查询按 `low <= point < high`；point-only 完整计划保留真实零宽跨度。
- 冻结窗口沿用 legacy 纯重叠 SQL，并由 workbench 专用读取回调补回查询左边界行，再核验证据；右边界和窗外点不冻结。
- `run_input_rows` 使用 `stored_date()` 比较 ready_date，兼容 worker 只读快照实际返回的 `datetime.date`，不改原始事实。

## 可接 DTO

以下字段附加到现有任务 DTO，原身份字段继续保留：

```json
{
  "event_kind": "point",
  "start": "2026-09-09T08:00:00",
  "end": "2026-09-09T08:00:00",
  "duration_seconds": 0,
  "occupies_resources": false
}
```

- 候选继续使用 `operation_ref` / `row_ref`；正式和试调继续使用各自的 `operation_ref` / `task_ref`。
- UI 应用点标记呈现，不修改 start/end 作为显示补偿，也不能把点纳入资源占用工时。
- `WorkbenchRunCandidateAdoptionService` 和 `WorkbenchTrialAdoptionService` 新增宿主构造参数 `point_rendering_enabled=False`。
- 默认含点采用返回 `point_rendering_not_connected`、`can_adopt=false`，不发 write token；采用 guard 同样检查，不能绕过 preview 直接提交。
- 该参数不是 HTTP 输入字段，也不是点证据开关。即使宿主设为 True，仍先完成所有后端事实/约束验证。
- EA 测试仅在内部 service 构造时显式开启它，以验证真实命令、事务、回执、正式写入及重启读取。

## Pieces 协调

- `run_candidate_adoption_validation.py` 和 `trial_adoption_validation.py` 中两个 `piece_adoption_unsupported` guard 均未修改。
- 本轮零时长证据限定 `piece_id is None` 和明确 batch 目标量；不是已经完成了 pieces 点事件证明。
- 主线可在本轮交付后统一接独立 pieces helper。对 pieces 点不能直接拿 batch.quantity 作为 target_quantity，也不能只删 guard。
- 零时长接线位置：`zero_duration.candidate_point_validator`、`zero_duration_evidence.work_point_evidence` / `trial_point_evidence`。共享 witness 可承载独立验证后的数量，但其来源、身份和冻结证据须由主线接齐。

## 精确写集

- 完整逐文件清单：同目录 `ea-write-set.json`，41 个 backend 文件、4 个 EA 新测试文件。
- 新小 helper 包括共享点 witness、冻结种子组装、workbench 左边界种子读取、冻结点证据读取和 point-aware 计划查询。
- 冻结模块按职责拆出种子时间校验与组装，未通过删空行压到 500 行。
- 没有修改 schema.sql、migration v24..v31、official_plan_persistence、前端/静态资源、路由、registry 或 DL/DZ 既有测试。
- `final-file-hashes.json` 记录交付时完整文件 SHA-256；它包含已有现场内容，不宣称整个文件都是 EA 新写。

## 验证

实际运行环境是仓库 `.venv/bin/python`，Python 3.8.10。未在 Win7 实机做打包验证，没有升级依赖。

| 证据 | 结果 | 范围 |
| --- | --- | --- |
| `ea-tests.xml` | 40 passed | 真实完整链、两次采用逐表旧行保留、重启读取、0qty/setup、bad hours、tiny positive、bool 假证据、边界、资源共存、顺序、班次、锁、执行、冻结后再 worker/采用 |
| `shared-tests.xml` | 83 passed | legacy parser/orchestrator、冻结和 seed validator 回归 |
| `regressions.xml` | 508 passed / 1 failed / 2 deselected | 候选、执行、试调原子性/重启、计划日历/占用/交付/基线；失败为旧 zero-quantity 排除断言 |
| `legacy-contracts.xml` | 26 passed / 4 failed | 4 项仍断言合法零时长必须拒绝或 0qty 必须跳过，未修改原测试 |
| 本轮 ruff / Python 3.8 grammar | 45 files passed | 最终 EA Python 写集 |
| 文件大小 / `git diff --check` | 通过 | 本轮文件均不超过 500 行 |

待主线同步的旧合同断言，原测试保留未改：

1. `test_zero_duration_boundaries.py::test_real_engine_point_keeps_original_identity_and_zero_duration_dto`
2. `test_zero_duration_boundaries.py::test_worker_records_failure_without_allocating_candidate_or_official_plan`
3. `test_run_compute_contracts.py::test_zero_hours_preserved_but_existing_payload_rejects_instant_work`
4. `test_run_compute_contracts.py::test_zero_quantity_is_excluded_without_becoming_missing`
5. `test_run_candidate_baseline_queries.py::test_skipped_zero_quantity_and_unselected_baseline_are_not_improvements`

另两项在 schema31 外键约束处中断，未进入本轮产品逻辑；先前已实际运行并记录到会话输出，扩展回归中显式排除，未改 fixture/schema：

- `test_plan_delivery.py::test_requires_callers_transaction_and_never_allocates_missing_ref`：删除 WorkbenchEntityRefs 时外键失败。
- `test_plan_baseline.py::test_schema_error_propagates_not_a_fake_unavailable`：DROP WorkbenchEntityRefs 时外键失败。

## 门禁边界

- 执行了 `scripts/run_quality_gate.py --fast-precheck`，未通过；同目录 `fast-precheck.log` 保存 25 项非 EA 写集的当前静态问题，没有据此修改其他代理文件。
- 依赖扫描结果见 `import-cycles.json`。纯显式 hard 文件环为 0；本轮曾出现的 point 证据延迟调用环已用显式 callback 拆除。
- 整仓依赖基线仍报其他目录/包初始化硬环；未治理无关模块、未刷新 baseline。
- 没有运行整仓 clean gate 或全容量验证。这是 dirty worktree 的定向验证，不是 clean-worktree proof，未把并行现场绑定成最终 HEAD 证明。
- EA 新测试没有登记 registry，因为本轮明确禁止修改 registry；主线可统一完成测试契约与登记收口。
