---
doc_type: feature-acceptance
feature: wb-field-workspace-ak
status: passed
summary: AK 本域实现和临时库验证完成；非主线发布或 clean-worktree proof
tags: [workbench, field, execution, validation]
---

# 结论

AK 自有产品源码已冻结。九个 Field 前端模块、两个 execution 路由模块、五个 field 服务模块和专属测试已落盘，未改禁止范围。源码全部处于既有 dirty worktree 的未提交状态，没有 build/commit，没有访问 productionDB。

本域查询和文件流程已使用 AJ 唯一执行投影及普通命令事务；原始旧事实保留、更正约束和累计状态均由 AJ 提供。本域没有第二套状态累计逻辑。

# 验证结果

| 验证 | 实际结果 | 边界 |
| --- | --- | --- |
| AK 专属 pytest | 26 passed | 真临时 SQLite/Flask + XLSX codec |
| AK + AJ 联合 pytest | 90 passed / 34.91s | 不含整仓完整门禁；AJ scale 单独由 AJ 验证 |
| Chrome 109 | 44 场景通过，0 failed | 1920x1080、1392x924，浅色/深色；mock 与真实 Flask 分开命名 |
| 浏览器证据 | 60 张截图、192 次真实 API 请求、0 pageerror | 只有 pytest fixture DB，不是 productionDB |
| 源码绑定 | 40 个已记录源文件 SHA-256 复核无漂移 | 本包、直接共享前端和 ledger 依赖；不宣称全仓/最终 bundle 哈希绑定 |
| Ruff | All checks passed | AK 自有 Python 文件 |
| 门禁同口径复杂度/大小扫描 | complexity=[] / size=[] | `tools.quality_gate_scan`，未加白名单 |
| Python 3.8 语法 | 12 files passed | host AST feature_version=(3,8)，不冒称 Win7 真机运行 |
| git diff --check | 通过 | 不改变暂存区/其他人文件 |

# 关键场景

- 查询/preview 在 `PRAGMA query_only=ON` 真库连接中通过；原始表快照不变，领域缺失时明确不可用。
- 未读、失败、空范围、已知 0、数量/有效小时未知、部分完工、正常报齐及合法旧 finish 区分。
- 多次新增、未知补齐、明确更正、原 revision_ref 冲突、原请求幂等回放、同键异载荷拒绝。
- 跨版本 operation_ref 关联真实记录，recorded_against_task_ref/plan_ref 不改；旧 task 不用于新安排录入。
- 初始 task_ref 定位第三页，旧计划中找不到该原 task 时拒绝；设备/人员、批次、计划重叠范围与日期 scope 保留。
- 每次结束不生成 finish；剩余全部完工仍提交逐次报工，由 AJ 投影确认整道完成。
- 明确 legacy_fact_ref + reason 补齐旧完工，原始事件逐行保留，不重复累计。
- 十列 Excel 5000 边界、数字/日期/空白/0、公式/合并/越列拒绝；全 scope 导出覆盖非当前页。
- 上传真实预检、确认、重复导入 unchanged、未知补齐、已知冲突、超量整批拒绝、问题清单下载。
- 已提交文件请求在内存 preview 清除后仍按原 request_key 回放，异 preview_ref 拒绝。
- 键盘输入、统一数字/日期/选项控件、鼠标选择资源、取消、回来源、刷新、六次报工时间线及更正历史。
- 模拟断网未知提交后，本页写入/分页/刷新/返回锁定；重新加载只查询原 request_key，未发第二次写入。
- 未读取失败不显示“当前范围没有任务”；错误 execution operation_ref 在前端拒绝。
- 本页自带 plana scope；弹窗 fixed、不透明背景、可见图标、历史全宽、两尺寸无横向溢出。

# 证据与复现

最终浏览器证据目录：`/tmp/ak-field-probe-bound/`。

- 汇总：`/tmp/ak-field-probe-bound/field-probe.json`。
- 前一完整功能轮：`/tmp/ak-field-probe-final/`。此轮共享依赖有漂移，不作为最终绑定证据；后续 bound 轮已补齐。
- 探针：`tests/workbench/field_workspace_probe.cjs`，harness 仅在测试进程内编译当前 JSX，读取既有本地基础资产，没有全量 build。
- 测试服务：`tests/workbench/field_workspace_probe_server.py`，目录必须是 checkout 外新建临时目录，拒绝已有目录；本轮启动的服务均由探针退出时关闭。

```bash
.venv/bin/python -m pytest -q tests/workbench/test_field_workspace_api.py tests/workbench/test_field_files_api.py tests/workbench/test_field_files_codec.py tests/workbench/test_execution_ledger.py tests/workbench/test_execution_ledger_commands.py tests/workbench/test_execution_ledger_constraints.py tests/workbench/test_execution_ledger_scope.py tests/workbench/test_execution_ledger_legacy.py tests/workbench/test_execution_ledger_contracts.py

NODE_PATH=/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules WORKBENCH_BROWSER=/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium node tests/workbench/field_workspace_probe.cjs /tmp/ak-field-probe-new-run
```

# 主线剩余边界

- 主线负责 v25 显式安装、registration/main/build 接合和旧批次/调度/报表消费者保护；本记录不替代主线验收。
- 未运行 `scripts/run_quality_gate.py` 全流程，因为本任务独有写范围、禁止 build/commit，且主线及多个共享模块仍并行变更；完整门禁和最终 bundle 验证由主线接合后统一执行。
- 没有 clean-worktree proof，没有 Win7 真机证据，没有将演示数据当生产连接回退。
