# F 实施与验证阶段记录

状态：实施中，尚未宣告 228 个动作或全站验收通过。所有失败文件保留，没有修改 planning 206 族基线。

## 已批准的产品修改

- `web/routes/workbench/system_backup_export.py:43`：新增只读备份下载；`resolve_context("backup", backup_ref)` 与集合 snapshot 双重核对。16 行起复核筛选内目标、读取前后签名、字节数和 SQLite 文件头，变化/删除/过期/错误格式明确失败。
- `web/routes/workbench/system_routes.py:19`：只新增 `GET /api/workbench/v1/system/backups/<backup_ref>/download`。旧 HTML 下载路由没有改动。
- `frontend/workbench/app/SystemMaintenanceAPI.js`：下载核对 SQLite 头、MIME、文件名、大小和原 ref，不保存错误 JSON；增加仅只读字段的 page-context 校验，拒绝混入确认态、原请求和写 token。
- `frontend/workbench/app/SystemMaintenanceRecords.jsx`：真实下载按钮；只读筛选、页码、snapshot、选中 key/备份 ref 回传。只从新读取页精确恢复原记录，不保留整行 DTO 或写 token；原记录不在当前页明确提示，不自动选别人。
- `frontend/workbench/app/DashboardWorkspace.jsx`：按 Main 批准新增顶层无条件 caption/page-context hook。caption 只用真实当前正式计划 DTO；加载/错误/外协登记子视图为空。page-context 只记录 scope、tab、item_ref、history_page。
- `frontend/workbench/app/SystemLive.jsx`、`SystemMaintenanceWorkspace.jsx`：只读视图恢复接线；维护请求、恢复确认、配置草稿仍保留原协议，不写进 history。
- 本域四个旧 CJS 加载列表补充 caption/page-context：`dashboard_widgets_probe.cjs`、`dashboard_external_handling_widgets_probe.cjs`、`outsourcing_widgets_probe.cjs`、`du_system_restore_browser.cjs`。未改共享 build-order。

## 本轮真实结果

专属根：`/tmp/aps-final-operations-F.TQejHX`，系统实际解析为 `/private/tmp/aps-final-operations-F.TQejHX`。

- `host2-results.xml`：2 passed，3.42s。真实 app_main/factory/受管 worker 四候选、四类风险、原锁及正常停止；此时自动退出备份关闭，明确为 skip，非成功备份证明。
- `download1-results.xml`：16 passed，6.93s。真实 factory、SQLite 完整 payload/中文名/大小/原业务行，失效 ref/错范围/文件变化/删除/读取期间变化及前端错误 payload 拒绝。
- `operations-regression1.xml`：68 passed，66.25s。全新执行既有强故障测试，覆盖维护 API、连接/响应/worker drain、丢 ACK、保护副本、失败回滚、冷恢复不打开数据库。不是旧测试结果重新计数。
- `download-config2-results.xml`：22 passed，42.86s。上述下载测试及五种配置回执/草稿状态和维护控件回归；组件用例明确仅补充，不能冒充全站主入口。
- 备份新路由/注册及下载测试的首次定向 pyright：0 errors / 0 warnings。随后扩展到全部新测试时发现 test host 的 Flask `jinja_loader` 类型赋值问题，改为真实 `jinja_env.loader`，待重跑。
- `browser5-results.xml` 中真实 fullbuild 恢复 + 进程重启 1392 浅色 1 passed。正常主入口链仍在迭代，不能将局部动作或截图写成整例 passed。

## 构建与失败边界

- `eaa69…` 仅在初次输入 hash 全匹配时用于 host 烟测；Main 导航修改后已过期，严格构建 guard 保留失败，未继续拿旧包做新源码验收。
- 私有 v2 全构建失败：Main 导航 `scrollX, scrollY` 全局分析尚未接齐，已经报告，没有绕过分析器。
- 私有 v3 完整构建 `e09173b0bc08b022e9a365d516f555338a4a4cd2fc8f2a983ae012328abbe6cf`，211 文件；新增 caption 前的正常链已实跑到 141 个操作记录，尚有测试定位器失败，不记通过。
- 私有 v4 完整构建 `2d2692788ae7c931c471471b292d47b2289b20bfc4f91265ba3df6f0e1cd0cde`，213 文件；后续 page-context 修改使其过期。
- 私有 v5 全构建曾因其他域 `RunCandidateControls.js: M` 未解析失败；随后小范围读取发现该域已补 `window.RunCandidateModel`，可重建核对。这是并行源状态，不擅自修改其他域。
- 浏览器迭代失败依次为：重复选择当前筛选无请求、重开后备注已是重开原因、Chromium109 整秒日期 fill 格式、偏好下拉的隐式标签包含选项文字。均修测试与真实当前语义对齐，未删产品断言或调阈值。

## Main 接线与收尾

- Main 的 `main.jsx` 调用 `SystemLive` 必须传已有 `initialContext`；截至本记录写入时仍未传。域组件已实现接收与校验，没有越权编辑主入口。
- 最终统一 freeze 后须重建 fullbuild，跑四组正常主入口、八组恢复/故障用例和 page-context F5/后退/侧栏恢复。截图生成仅为 V 待审，不冒称 Main 已审。
- 后续 v6 全构建阻于其他域 `ResourceWorkspace.js → ProcessWorkspace.js` 加载顺序。误启动的八个整页恢复用例均在缺 manifest 的前置阶段失败；同组七个旧组件补充通过。记录保留，今后只在 build exit 0 后启动依赖它的测试。
- 最终新增 Python 11 文件 pyright 为 0 errors / 0 warnings；Ruff 格式修正后全部通过。完整阶段结果、27 文件 hash 和待执行项见 `handoff.md`、`source-hashes.json`、`action-evidence.json`。
- 所有已有 dirty/staged、源码归档和旧预览均未被本任务改动或清理；本任务没有 Git 写操作。完整门禁、正式容量、旧 UI 退役总归档由 Main 统一处理。
