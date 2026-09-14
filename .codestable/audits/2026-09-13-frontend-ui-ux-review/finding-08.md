---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-08"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 08：排产长任务没有任何进度指示，只有「已耗时 X 秒」

## 速答

排产计算可能数分钟，但轮询界面只有阶段文字加「已耗时 X 秒」，无进度条、无计数、无心跳；切走页面还会暂停查询，提示是一行小字。排产员无法判断是正常在算还是卡死，容易误刷新、误重复提交。后端返回体里的 `progress` 字段是硬编码的 `None`，前端契约又把它钉死为 null，所以进度量化必须前后端同一次改。

## 关键证据

- 前端：`frontend/workbench/app/RunJobControls.jsx:12` 只显示 `RunPresentation.stage(run)` 与已耗时；`:91` 「页面切走了，已暂停查询」为行内小字。`RunPresentation.js:3` 四态阶段枚举，`:5-16` 已耗时由前端用 started_at / accepted_at 自算。轮询 `RunJobAPI.js:213`，退避 `:223`（2s 到 30s）；`RunJobPanel.jsx:37` 在 `document.hidden` 时暂停。
- 后端返回体无进度：`data/repositories/workbench_run_repo.py:82` `"progress": None` 为常量；路由 `web/routes/workbench/scheduling_jobs.py:108`。
- 契约双向钉死：`RunJobAPI.js:48` 键集精确白名单、`:51` `v.progress === null`，后端单方面加字段会让前端报「读到的排产数据不完整」。
- 库表无心跳列：`core/infrastructure/workbench_run_schema.py:12-26` 只有 accepted_at / started_at / finished_at，CHECK 约束与触发器锁住状态跃迁。
- 可挂的计数点：`core/services/scheduler/run/schedule_candidate_runner.py:188` 逐候选方案外循环，`:142` 与 `:190` 已在算 deadline；可数单位是候选方案，不是批次。
- 优点对照：防重复提交与跨页锁已做，缺的只是进度反馈。

## 影响

主流程上最长的等待环节是反馈黑洞；用户焦虑后重复提交或刷新。触发条件：每次跑排产候选。

## 修复方向

前端先行：不确定进度条（indeterminate）加显眼常驻的「正常计算中，请勿关闭」；切页暂停提示升级为醒目状态条。进度量化按「已算完 X/Y 个候选方案」口径，需要后端字段、`RunJobAPI.js:48-51` 契约、库表心跳列同一批改。

## 建议动作

`cs-issue`，前端提示部分可先修；进度量化单独立项（见 remediation-plan 4.1）。

## 复核记录（2026-09-13）

- 坐标改为源码；补契约钉死、库表约束、计数单位三个事实。
- 原修改方案 4.1 的「已处理 X/Y 批」口径更正为候选方案。

## 实施记录（2026-09-13）

- 状态：resolved。新增进程内进度账本 `core/services/workbench/run_progress.py`，候选运行器逐候选上报，查询只在 running/computing 附带；前端计数 + progressbar + 提示；测试 `test_run_progress_ledger.py`。
- 详见 [remediation-record.md](remediation-record.md)。
