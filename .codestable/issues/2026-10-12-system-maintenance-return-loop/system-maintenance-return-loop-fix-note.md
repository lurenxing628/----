---
doc_type: issue-fix
issue: 2026-10-12-system-maintenance-return-loop
path: fast-track
fix_date: 2026-10-12
status: fixed
tags: [workbench, system, maintenance, navigation]
---

# 系统管理状态查询失败与返回回跳

## 根因

实际产品的 `SystemMaintenanceWorkspace.useCommand` 原先把状态查询错误、状态加载和浏览器存储错误都归入 `suspended`，并据此挂载全屏 `SystemRestorePanel`。该面板设置根界面 inert、拦截后退；“返回工作台”又指向系统管理自身，持续查询失败时形成回跳。

现场触发器最初是独立预览少装 `restore-host` 状态接口。用户随后要求聚焦实际产品缺陷，本轮产品修复及最终验收围绕真实启动链展开。

## 修改

- `SystemMaintenanceWorkspace.jsx` 分离实际维护接管、系统读取暂停和维护写入限制。全屏仅取已确认的非 ready 状态或待确认恢复请求。普通接口错误在页内给出具体原因、重试和工作台首页入口。
- `SystemMaintenanceAPI.js` 区分查询超时与维护提交结果等待，保留 HTTP 状态；维护状态 404、连接失败和响应异常提供对应原因。
- `SystemLive.jsx` 的读取提示复用上述真实原因；`SystemMaintenanceRecords.jsx`、`SystemMaintenanceConfig.jsx` 共用 `lockedReason`，维护写入暂不可用和存储异常各自表达。存储错误由结果区统一显示。
- 暖面板与冷启动模板统一将真实维护期间的入口命名为“重新检查启动状态”，入口指向工作台首页。查询失败页的“返回工作台”直接到首页。
- 已确认正在维护时，后续查询失败保留该状态；真实恢复、本次待确认恢复、进程重启要求继续由现有维护流程执行。

## 验证

- 使用正式 `web.bootstrap.entrypoint.app_main` 启动完整应用；正常 factory、运行时、worker、维护宿主及 WSGI 接口全部参与。数据库、日志、备份与维护记录使用隔离验证目录。启动恢复扫描为空，维护状态返回 ready / operations_available=true。
- Chrome 154 完整页面共 15 项通过：概况与三个维护页签、侧栏往返、浏览器后退、HTTP 404 和网络失败的局部提示、返回首页、重试恢复、已确认维护状态及后续查询失败、状态恢复后释放页面。
- 真实维护服务回归：现有 `test_system_maintenance_restore.py` 5 passed；新增断言确认恢复后访问首页仍返回实际冷维护页面及正确的重新检查入口。
- 现有 `notice_ownership_contract.cjs` 38 项检查通过，覆盖状态分流、恢复请求、只读状态、存储错误及原因唯一性。
- 日常门禁：Ruff 通过，332 passed / 20 skipped。Chrome 109 构建通过；本轮两个 Python 文件的 Python 3.8 语法检查及差异检查通过。
- 证据：`output/playwright/system-maintenance-20261012/` 中的 `daily-gate.log`、`browser-check.js`、`system-normal.png`、`system-query-failure.png`。完整页面位于本机验证实例 18876。

本轮产品文件：`SystemMaintenanceWorkspace.jsx`、`SystemMaintenanceAPI.js`、`SystemLive.jsx`、`SystemMaintenanceRecords.jsx`、`SystemMaintenanceConfig.jsx`、`SystemRestorePanel.jsx`、`SystemRestoreStatus.js`、`templates/workbench/recovery.html`、`web/bootstrap/workbench_system_restore_view.py`；对应现有测试、构建产物与速查入口同步。
