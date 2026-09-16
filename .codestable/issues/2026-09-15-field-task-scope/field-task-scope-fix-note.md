# 现场记录切换任务后保存刷新失败

## 现场与根因

手动验收从值班台风险进入现场记录，保存第一条任务后切换到第二条任务报工。业务保存成功，随后页面提示“报工已保存，页面刷新失败”，服务端返回“选中的工序和这条任务对不上”。

- `FieldAPI.initial` 把入口的 `task_ref`、`operation_ref` 和原 `plan_ref`、范围一起保留为首次定位参数。
- `FieldWorkspace.openTask` 只切换当前已加载表格里的详情及暂存草稿；不重新查询列表。
- 修改前 `FieldWorkspace.done` 保存后重读只更新 `task_ref`，却沿用入口的 `operation_ref`。第二条任务保存后，读取请求组合成第二条任务与第一条工序。
- `web/routes/workbench/execution.py:39-42` 正确拒绝这一错配，返回 HTTP 409。报工已经提交；失败发生在随后的读取阶段。

定位证据：已运行 `python3 -m tools.symbol_locator whereis FieldWorkspace`（JSX 没有索引结果），随后用 `rg` 查定义和引用；`whereis field_query`、`callers field_query` 确认服务端调用点为 `field_tasks`、`field_task`。

## 修改

- 产品仅修改 `frontend/workbench/app/FieldWorkspace.jsx` 的保存后 `setScope`：当前任务编号和对应工序编号一起更新；没有当前任务时清除工序编号。
- 保留 `current` 中的原计划和筛选范围，只刷新快照并重新定位当前任务。没有扩大到最新正式计划，没有移除服务端配对检查。
- 行切换继续使用已经加载的任务；避免为了更新一次定位参数额外刷新并卸载详情中的暂存草稿。
- `tests/workbench/field_workspace_probe_harness.cjs` 增加显式初始上下文注入，原测试默认上下文不变。
- 新增 `test_field_scope_navigation_browser.py` 与 `field_scope_navigation_browser.cjs`，扩展现有 `test_field_workspace_api.py` 的错配拒绝测试。新增测试文件的登记路径已交给主代理统一处理。

## 修改前复现

在独立临时 SQLite + 真 Flask + Chromium 109 中，带第一条任务/工序定位进入，第一条保存通过，第二条保存后读取 HTTP 409，页面不再显示详情；两次保存请求均已完成。测试未修改真实业务数据库。

- 证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-field-scope-navigation-rv8yx0n9/`。
- `field-scope-navigation.json` SHA-256：`a7f8a7a35ce324ed3aabd8ea9792310402852a30d850dd59967642898ed27d3c`。
- 修改前 `FieldWorkspace.jsx` SHA-256：`c49d2a144062f0dfed3f55502b8f778824a50fdf52baec01dd4d60a42c4f4f7d`。

## 修改后定向验证

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -s -p no:cacheprovider tests/workbench/test_field_scope_navigation_browser.py::test_task_switch_save_rebinds_operation_and_preserves_plan_scope tests/workbench/test_field_workspace_api.py::test_selected_task_operation_pair_is_checked_without_losing_plan_scope tests/workbench/test_field_workspace_api.py::test_pages_filter_detail_scope_and_old_plan_identity
```

结果：**3 passed in 3.83s**。

- 浏览器 5 个流程通过：带第一条定位保存、切第二条保存、第二条更正、收起后刷新同时清除定位引用、翻页不带旧引用并返回原值班台上下文。
- 每次保存后读取均检查原 `plan_ref`、搜索词、批次范围及起止范围保持不变；选中请求的 `task_ref` 和 `operation_ref` 必须同时对应当前任务。
- 第一条新增数量 0、第二条新增数量 1、第二条更正工时为 0，最终仍为各自一条报工；第二条保留两条修订历史。
- API 配对正确时读取成功；故意错配仍返回 `constraint_conflict` / HTTP 409，且读取前后所有数据库行不变。原跨页筛选与历史计划身份用例继续通过。
- Chromium `109.0.5414.46`；页面错误 `[]`、HTTP 错误 `[]`；76 份参与源码 SHA-256 全部一致；临时进程均在测试退出时关闭。
- 修改后证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-field-scope-navigation-0nlx7zoi/`。
- `field-scope-navigation.json` SHA-256：`b50f94f6dc98e40735d7ab7c2ba7633b26b4846420b486e6dafa186bcff9b8a3`。
- 修改后 `FieldWorkspace.jsx` SHA-256：`fd1c81654565a1d257571950d8c9f7c58ffb9e06e32d0dc9dee1e18d60dd8219`。

## 验证边界

未构建共享资产，未操作正在手动验收中的 Chrome 或 IAB，未写入 5000/5001/5002/5003/5004/5005 的业务数据库。浏览器测试写入只发生在测试新建的临时库；本记录不冒充手动验收。

按用户要求未执行全门禁、`run_quality_gate.py` 任何模式或整仓测试。保留原工作区修改，本次没有 clean-worktree proof；上线页面需由主代理统一构建并手动回验。
