---
doc_type: feature-ff-note
feature: system-restore-ui
date: 2026-09-10
tags: [workbench, system-maintenance, restore, DU]
---

## 做了什么
- warm 恢复显示外置记录来源、所选备份、保护副本、回滚/未知和整软件重启要求；保留原 key，响应丢失只查询、不重做，业务界面不可操作。
- stopped/cold `/workbench` 返回 HTTP 503 中文只读 HTML，可按原 key 或记录编号查询、导出维护诊断；纯 Jinja 视图不构造正常 app、不打开 SQLite、不修改 journal。未知记录不能解除维护停止状态。

## 写集与接入
- 新增 `frontend/workbench/app/SystemRestoreStatus.js`、`SystemRestorePanel.jsx`；更新 `SystemMaintenanceAPI.js`、`SystemMaintenanceControls.jsx`、`SystemMaintenanceRecords.jsx`、`SystemMaintenanceWorkspace.jsx`、`SystemLive.jsx`。`SystemMaintenanceConfig.jsx` 未修改。
- 新增 `web/bootstrap/workbench_system_restore_view.py`、`templates/workbench/recovery.html`；只在获准的 `web/bootstrap/workbench_system_restore_status.py` 接入页面。模板需要随包交付。
- 顺序：Status -> API -> Controls -> Panel -> Records / Config -> Workspace -> SystemLive。复用已有 React/ReactDOM、ResourceControls、SMIcon 与工作台样式；没有新增依赖或其他全局声明。
- 新增 `tests/workbench/test_du_system_restore_view.py`、`test_du_system_restore_contract.py`、`test_du_system_restore_browser.py`、`du_system_restore_browser.cjs`；同步 `test_system_maintenance_widgets.py`、`system_maintenance_widgets_probe.cjs`、`system_config_saved_probe.cjs` 的新状态合同及隔离夹具。测试 registry 由主线持有，DU 未改。

## 验证
- Python 3.8.10：恢复/维护与新合同组 102 pass；DU Chrome 109.0.5414.46 浏览器组 15 pass；原系统组件 1 pass（内部 93 cases、四视图）、配置回归 5 pass，合计 123 pass。作用域 pyright、ruff 通过。
- Chrome 109 实际手输/点击/下载/截图覆盖 1920x1080、1392x924 浅深；真实恢复成功、丢失响应、真实回滚、回滚失败、cold pending/损坏记录。cold 子进程禁止 SQLite 与普通初始化；页面查询前后数据库/备份/journal 哈希不变。额外后端验证覆盖数据库缺失及混合损坏记录。
- build207 `5b58a5a2100f95b93d58da0c7a6870fcc452ac2928f4921f38364ea23c6e4c19` 的八个 System 模块与当前源码内存编译结果一致；直接用该静态产物、不覆盖源码的真实恢复也通过。DU 未执行全局 build，未动主 preview、factory/entrypoint/runtime/DDL/schema/main，未 stage/commit。
- 证据汇总（含各次源码 SHA-256、实际请求、诊断下载、截图路径）：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-du-restore-evidence-zevFIk/summary.json`。

## 边界
- dirty-worktree 局部证据，不是 clean-worktree proof；未运行全仓 gate，未做 Win7 真机/冻结包验收。主线并发 build、v31 迁移不属于 DU 验证声明。
- 不提供假退出、继续使用或自动恢复按钮，不暴露生命周期 nonce。损坏记录混在清单中时，按 job 扫描可拒绝，按原 key 单条核查仍可成功；不把损坏当空记录。
