---
doc_type: issue-fix
issue: wbui-first-round-fixture-initialization
status: fixed
created: 2026-09-12
summary: 显式完成首轮工作台测试库的系统配置初始化，消除维护节流造成的数据基线时序依赖。
tags: [workbench, testing, readonly]
---

# 首轮工作台只读合同的测试夹具修复

## 根因与证据

整仓 parallel-3 报告中，首轮工作台流程的最终业务快照断言发现 `SystemConfig` 从空表变为默认配置，其余 73 张表相同。该测试原先依赖首次 `GET /` 的自动维护完成默认配置初始化，再取得只读基线。

实际调用链为 `factory._open_db` → `SystemMaintenanceService.run_if_due` → `SystemConfigService.get_snapshot` → `ensure_defaults`。`MaintenanceThrottle._last_check_ts` 是进程共享状态；前一个测试可以使本测试首次首页请求被节流，而较晚的旧入口 GET 在节流到期后才补写默认值。本轮确定性复现定位到 `/scheduler/analysis?version=12&plan_role=adopted&date_from=2026-09-12&date_to=2026-09-12`，当前默认配置共 8 项。

新页头的 `help_url` 仅由 `url_for` 生成，受测浏览器请求没有访问 `/manual`。普通首页 GET 触发自动维护还有 `test_entry.py::test_system_overview_skips_maintenance_but_normal_requests_keep_it` 的既有合同，未修改产品维护行为。

## 最小修改

只修改 `tests/web_pages/test_aps_workbench_first_round_flow_contract.py`：在本测试临时库创建 app 后显式调用 `SystemConfigService.ensure_defaults`，随后再发起首页请求并记录基线。没有初始化其他配置表，没有从 `_business_state` 删除 `SystemConfig` 或任何业务表。

新增测试模拟首次维护被节流、后续维护获准的状态切换；独立核对 8 个默认键值，并继续断言完整业务快照不变。

## 验证

- 原完整模块单跑：`1 passed in 5.62s`；默认配置在基线前由首页 GET 补齐。
- 修复前确定性时序复现：`1 failed in 3.76s`；旧分析 GET 将 `SystemConfig` 从 0 写成 8 项。
- 新合同修复前：`1 failed, 1 deselected in 2.00s`，证明被节流的首页不能独立保证测试库初始化。
- 修复后完整模块：`2 passed in 6.42s`。
- 相同确定性时序复现修复后：`1 passed, 1 deselected in 4.26s`。显式初始化在请求外完成 0→8；旧分析 GET 为 8→8。前后 74 张表的业务快照 SHA-256 均为 `a9366dadd22a6b410dab63a063a3ebb2a72b32de242dba4b2b9d9c3c363e435d`。
- Ruff 与该文件 `git diff --check` 通过。

原始日志、JUnit XML、调用栈及逐次快照摘要位于 `/tmp/aps-wbui-config-get-diagnosis/`，汇总见 `evidence.json`。本轮只在原仓及新建的临时测试目录操作，未写入主线程的两个运行中验证副本；未改产品、未暂存或提交。这是 dirty 工作区定点验证，不是整仓门禁或 clean-worktree proof。
