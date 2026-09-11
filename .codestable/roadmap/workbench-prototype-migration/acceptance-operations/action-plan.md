# 任务 F 动作分母与执行计划

- 范围：dashboard 14 + system 19，共 33 个冻结能力族；不修改 `workbench-capabilities.json` 的 planning 206 族基线。
- 动作分母：**228**，其中 DASH 97、SYS 131。稳定 ID 为 `WBP-DASH-001.metric-delivery` 形式，完整清单由 `tests/workbench/final_operations_actions.py` 定义。SYS 额外保留本轮明确要求的备份下载及数据库 payload 校验，不因当前缺入口删除。
- B：真实服务、真实文件 SQLite、真实 factory 与受管 worker/restore；纯浏览器偏好对 B 标明不适用原因，不能用 mock 代替。
- K：完整 `/workbench` 主入口，Chromium 109 实际输入、点击、键盘操作；不挂独立组件、不覆盖产品脚本。
- V：1920×1080、1392×924 的浅色/深色截图，交 Main 审视；截图生成不自动记为 Main V 通过。
- P：页面刷新、原回执查询、关闭并重启本任务自己的进程；恢复后只读和失败留存分别记录。
- 顺序：动作冻结 → 私有主入口夹具 → 值班台/外协/系统正常操作 → 恢复/停止故障 → 证据、源 hash、剩余项交接。Main 负责统一门禁、正式性能窗口和最终归档。
- 专属运行根：`/tmp/aps-final-operations-F.TQejHX`。不接触生产库、53144/PID73298、旧 preview 根、staged 文件及两个源码归档。
- 构建复用：`output/workbench-migration/verification/round1-20260910/offline-build/asset-manifest.json`，build_id `eaa69eec9bf98dbecac97b6be1baa322ff34c2a5df4ca1264ddd0bd4548bf8bf`。2026-09-10 本轮核对全部输入无漂移；旧构建可承载新浏览器运行，旧测试不冒称新测试。

## 当前缺口

- 备份下载：`frontend/workbench/app/SystemMaintenanceRecords.jsx` 的备份详情仅恢复、删除；`frontend/workbench/app/SystemMaintenanceAPI.js` 仅提供日志下载；`web/routes/workbench/system_routes.py` 无备份下载路由。最小修法是新建基于现有 `backup_ref` 的只读文件下载并接详情按钮。待 Main 批准和实施，本任务不改共享 route/host/restore/transaction。
  后续 Main 已明确批准最小写集，现已实施并有 16 项下载定点验证；本段保留发现当时事实，当前状态见 `implementation.md`。
- planning 原型中部分风险条图、候选 radio 和摘要弹窗，在当前真实值班台被表格及候选目录替代。逐项保留原动作，后续以实际浏览器证据和批准的处置决定记状态，不能把跨页目录自动当作原动作通过。

## 边界

当前文档是执行计划，不是验收通过。所有 B/K/V/P 结论另附真实运行证据；未执行、阻断和不适用分别列出。工作区原有大量 dirty，任何本轮局部验证均不是 clean-worktree proof。

## 19:23 主线更新后的复核

- Main 通知本地提交 `c0097278` 完成，tracked unstaged 在钩子短暂 stash 后已恢复；本任务未执行 Git 写操作。
- 后续首个浏览器测试在构建源绑定处 fail closed，尚未启动浏览器。实测漂移为 `theme.js`、`main.jsx`、`build-order.json`，属于 Main 明确新增导航的源变化，不判产品 bug。失败保留在私有 `browser1-results.xml`。
- 使用既有 `scripts/workbench/build.py` 在私有 `build-v2/` 完整构建当前源；不改共享构建入口、不发布静态目录、不更新旧预览。后续新运行显式传入此构建路径，Main 最终统一构建仍单独验收。
