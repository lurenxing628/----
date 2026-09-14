---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-14
nature: performance
severity: P1
confidence: medium
suggested_action: cs-feat
status: open
---

# Finding 14：外层候选彼此独立、可进程级并行（机会项，受 Win7 打包与日历连接约束）

## 速答

工作台外层候选严格串行，但候选之间只有三处弱依赖（基线结果供健康度评估、预算顺序反馈、图准备缓存），选优是集合上的确定性 `min`，种子 = plan version，所以并行不破坏可复现性。4 核下 1000×4 约 10.7s → 3.5～4.5s、5000×4 约 89s → 25～35s；线程无收益（纯 Python 不释放 GIL）。

## 关键证据

- `core/services/scheduler/run/schedule_candidate_runner.py:193,218,261-264,334-339`、`:189,217` —— 串行与三处依赖。
- `core/services/scheduler/run/schedule_candidate_selection.py:56,125-130` —— 顺序无关的确定性选优。
- 不可 pickle 对象：`core/services/scheduler/calendar_service.py:32-37`（`conn/_engine/_admin`）、`schedule_input_collector.py:293-294`（`ConfigService(conn)`）、`schedule_execution_reservations.py:67-84`。
- `installer/README_WIN7_INSTALLER.md:14,29` —— PyInstaller 4.10 onedir，需 `spawn`；全仓无 `multiprocessing.freeze_support()`。

## 影响

在不改任何算法的前提下把 5 秒预算里的"2 完成 / 2 跳过"变成 4 完成。

## 修复方向

为 worker 提供"从 db_path 重建只读 CalendarService"合同 + 常驻进程池 + 并行模式停用 `CandidateBudgetFeedback`；先在 macOS/Win10 测 spawn 与 IPC 开销，再决定是否落 Win7。与 finding-06 二选一或叠加：若图档共享内层解码结果，并行收益主要落在基线 vs 首个图档两条线上。

## 建议动作

`cs-feat`，需要 Win7 实机验证与打包改动。
