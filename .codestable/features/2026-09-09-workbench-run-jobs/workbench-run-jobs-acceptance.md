---
doc_type: feature-acceptance
feature: workbench-run-jobs
status: integration-pending
summary: AV独立持久受理与结果恢复写集52项真实SQLite测试通过，主线尚未启用v26与候选目录
tags: [workbench, scheduling, persistence, recovery]
---

# AV 定点验收

## 最终结果

- `.venv/bin/python -m pytest tests/workbench/test_run_jobs*.py -q --disable-warnings --durations=3`：**52 passed in 38.59s**。
- 最慢测试 `test_5000_real_tasks_persist_all_four_candidates`：pytest call **35.45s**。这个值包括测试体中的受理、计算、持久化、重开和保留校验，不是纯优化耗时。
- 最后仅调整路由import排版后的独立路由回归：**11 passed in 0.74s**，没有将重复运行的测试重复计数。
- 本写集10个产品文件、9个专属测试/support文件 Ruff：**All checks passed!**。
- 本写集10个产品文件使用 `pyrightconfig.gate.json`：**0 errors, 0 warnings, 0 informations**。工具提示可升级版本未执行。
- 全部临时SQLite，无生产DB、build、commit、依赖更新。测试使用仓库Python 3.8环境；未做Win7真机验证。

## 真实合同证据

| 专属测试 | 覆盖 |
| --- | --- |
| `test_run_jobs.py` | 真实4候选与完整payload，跨连接/重开永久引用，null授权拒绝、默认关闭、事实漂移、已有正式Schedule/History及旧候选全部保留、真实partial |
| `test_run_jobs_schema.py` | 显式外部事务、只读结构检查、部分schema/全表丢失拒绝修补、调用方回滚整个installer、受理永久不可改 |
| `test_run_jobs_atomic.py` | 受理receipt失败全回滚、第二候选/结果receipt/终态提交阶段失败无半套候选、明确零时长失败与原库保留 |
| `test_run_jobs_concurrency.py` | 12个独立SQLite连接同键只受理一次、不同键旧preflight409、双worker和旧run同锁、running查询、DELETE/WAL另一连接真实commit、真实维护backup与integrity_check |
| `test_run_jobs_recovery.py` | 重开不重算、外国执行者True/False/None证据、未知不看时间猜死、探测异常上抛、明细损坏不报成功、已提交receipt恢复unfinished、待核对queued不可领取 |
| `test_run_jobs_restart.py` | 真子进程在第一候选写入后`os._exit(23)`，SQLite自动回滚半结果；原事实保留；先unknown后根据已退出进程证据interrupted；accept/result COMMIT成功但确认丢失可查询并重放 |
| `test_run_jobs_api.py` | 真实Flask预检/授权preview/202受理/GET/按key核对，开关与dispatcher双门禁，受理后派发失败仍已提交，不因HTTP重放/过期token重复派发 |
| `test_run_jobs_capacity.py` | 100批次乘50工序、100组独立资源、真实4候选各5000完整行，共20000永久明细；重开结果完全一致；原表及schema指纹不变 |

测试对原库保留的断言比较全schema和全部原表，仅排除本写集四张run台账表及动作恰为`scheduling.run`的受理receipt。
完整Schedule、ScheduleHistory、ScheduleCandidate、ScheduleCandidateRows、配置、资源、日历和AJ事实均在比较范围。
计算改用SQLite Backup API的一致内存库，原库不在长读/写事务中。上述DELETE journal并发写与实际维护备份不是只凭WAL推断。

## 容量边界

AV同场景早期试跑分别145.30s、46.11s；最终完整源码全组38.59s、其中容量测试体35.45s。
这些时间受宿主争用和缓存影响，不据此宣称算法提速或Win7性能承诺。
AS先前单设备/人员争用5000工序在340.33s中断仍未通过；AV未重跑或覆盖该结论。
独立内存数据库要容纳完整原库；没有证明任意大历史库的内存上界。

## 集成门禁

- `install_workbench_run_schema`、`register_scheduling_job_routes` 已提供，但未改schema.sql/version/registry/global注册。
- 主线负责v26迁移、宿主独立连接worker dispatcher及启动恢复证据。开关与dispatcher未接好时不签发run授权。
- 服务恢复hook `executor_is_active(ref)` 必须依据真实执行者或既有DB单实例运行锁，未知返回None，不按浏览器timeout判死。
- 新结果只给永久candidate_ref/row_ref，`plans=[]`、`plan_catalog_connected=false`。新candidate catalog和正式采用不属于已完成范围。
- 当前已有大量其他代理的暂存、未暂存、未跟踪改动；本轮新文件也尚未提交。未跑整仓质量门禁，避免把并发变化与未接线入口写成clean proof；本记录仅是dirty工作区的AV定点证据。

## 产品源文件 SHA-256

```text
4fb528f87128c71bee9190ee720954f9f336b7d7a0afabe2f7767d5453da375b  core/infrastructure/workbench_run_schema.py
0caca5b0e849a2430a96961fca7ad2a01511e0a3c58a8d64d872b76ca60bcaaa  core/models/workbench_run_job.py
ad483a3a43b7fcfc63ed994c46b316e2371621ebf1a93a9a8199ba4e60d16589  core/services/workbench/run_jobs.py
8158ab9cc4af7ee3e53a8360761a984721236462f13c1fdb101a3dfa09f306f6  core/services/workbench/run_jobs_facts.py
bf7cb87b8f3cce80534270b7cd8208aafe6526d1339f0a2ca8bff03095a90fde  core/services/workbench/run_worker.py
9228940b2d4d8368c8d374edc839beebc7255a76760d595f5cebffc0cab5145c  core/services/workbench/run_worker_recovery.py
618ac52d8f79f5c387f7a8dff2eb9e5a00472ea4439b981063c039bcac1c1a95  core/services/workbench/run_worker_snapshot.py
ef256966c361ca1c3bcee90ecbd0a8c2aa72db8a6f4afec30fa36573ed368fc2  data/repositories/workbench_run_repo.py
25190e5df9c33b926c490456b473453f18b8357c37342f5ef07a1d26baac69eb  data/repositories/workbench_run_result_repo.py
6b50b624789f21bb85ee6881a2a83143087bfa1dccf6e5c4ba0ae6bd0fb964b8  web/routes/workbench/scheduling_jobs.py
```
