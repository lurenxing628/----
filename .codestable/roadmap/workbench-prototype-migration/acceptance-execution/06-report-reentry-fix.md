# Reports / Review 重新进入修复

状态：Reports/Review 定向完整入口修复验证已通过；不等于 B252 或整仓通过。Main 的 B252 原失败证据及 E 原 41 PASS 保持独立。

## 根因与授权

- `ReportWorkspace.jsx` 原初始化从 `initialContext.snapshot_ref` 恢复进程内令牌，又在顶层和 `table` 两处持久化该令牌。`web/routes/workbench/reports.py:25` 通过进程内 registry 解析它，物理重启后旧令牌合法返回 409 `snapshot_stale`。
- Main 给定 B 原目录 `/private/tmp/aps-final-foundation-B.xYPahs/F13-source9-copy-jNxcdz/fixtures/aps-workbench-live-if1sqobh`，四个原响应 `foundation-responses/78791.json`、`80117.json`、`81443.json`、`82769.json` 保留不动。E 只读核对了第一个原响应，确为 `committed:false` / `snapshot_stale`。
- Main 明确授权将持久查看状态与活动令牌分离。没有更改 registry、有效期、服务端拒绝行为、数据库、写命令或计划选择规则。

## 最小产品改动

| 文件 | 变化 | 本阶段 SHA-256 |
|---|---|---|
| `frontend/workbench/app/ReportAPI.js` | 只读表状态白名单；新读取先同范围 page 1，取得新令牌后回到原 page N；已有活动令牌直接读取且不捕获/重试 409；详情核对唯一工序/计划/快照 | `4acaeea96cb63f84f2501f43005d934a493975e1c2924a1d9b9445b2f8e511fc` |
| `frontend/workbench/app/ReportWorkspace.jsx` | 历史及 returnTo 不再保存顶层/表格令牌；接受含旧令牌的历史但不回传；新进入/刷新保留原计划、页、详情引用；显示实际新 as_of | `1908d9d2c06ef3f37cf212f2f4fef79967e63f2dff8979a3508ee48caf863b4e` |

加载顺序仍是现有 `ReportAPI.js` → `ReportControls.jsx` / `ReportDetail.jsx` → `ReportWorkspace.jsx` → `ReviewWorkspace.jsx`。E 没有新增前端叶文件，也没有修改共享 build-order。

## 同时完成的 H 门禁收口

| 文件 / 函数 | 原复杂度 | 当前复杂度 | 文件 SHA-256 |
|---|---:|---:|---|
| `actual_gantt.py` / `workspace` | 16 | 9 | `19dc47f77129b13fcd2357b92f35565a7b3fecabf81553213db1db66ac8c6d43` |
| `actual_gantt_chain.py` / `_result_valid` | 26 | 10 | `2f7a70e795fdb74f5e20ad886bc40da57532b23561f28763cbb9c800a9c0373f` |
| `actual_gantt_chain.py` / `plan_chain` | 21 | 12 | 同上 |

只按执行投影读取、结果结构/边校验、公共展示对象组装分工提取辅助函数。两个文件内最大复杂度为 13；原链引擎算法、默认调用和分钟量纲未更改。`test_final_execution_rejections.py` fixture 改为明确别名绑定，不使用 ignore。

## 验证记录

- 旧完整组：`/tmp/aps-final-e-consolidated.QHAv7t/consolidated-01.xml`，41 passed / 319.11s。build `1417717b6ecfdc897da2af9b5d0302a13f3617ab1ad37b696343df8c9d758c46`，222 files / 314 inputs。这是修复前源版本，不能算本次修复通过。
- 修前定向复现：同目录 `report-reentry-before.xml`，2 failed / 9.44s。Reports、Review 都在同 PID 返回原二页时直接带旧令牌读二页，没有新 page 1 读取；原 JSON 与截图保留。
- 修后首轮：`/tmp/aps-final-e-report-reentry.2ztPbQ/report-reentry-after-01.xml`，164 passed / 3 setup errors / 30.34s。后端关键链及旧 API 回归通过；三个完整入口用例因共享构建 `unlisted=PlanProcessOrder.js` 尚未启动，不能算浏览器通过。
- 定向 Ruff 当前通过；定向 Pyright 当前 0 errors / 0 warnings；没有升级运行时或工具依赖。
- `test_final_execution_report_reentry.py` 的两种视图将验证同 PID 侧栏返回、旧形态 history 的 F5、同端口新 PID 重新读取、目标页大于一、原详情和真实下载字节。另一次保持页面不重新加载的重启，专门验证活动令牌的导出/详情/分页 409 不自动重读。
- 新读取的 `elapsed_since_planned_minutes` 允许随新 as_of 变化，但测试逐项用该响应 as_of 与计划完工时间重算；其余原对象/事实字段完整比较，不整个排除详情或记录。

### 成功的完整入口复测

- `/tmp/aps-final-e-reentry-live.sXWWAA/reentry-01.xml`：**2 passed / 25.19s**，两视图上述全部场景通过，各保持浏览器页面并两次物理重启同端口服务器。全部业务表未变化；每次重启仅新增一条明确的 `plugins/load` 审计及对应序列增量。
- Reports 原目录：`/tmp/aps-final-e-reentry-live.sXWWAA/aps-workbench-live-mrscq2vc/report-reentry-proof.json`，PID `33680 → 33716 → 33727`，端口 `62101`。
- Review 原目录：`/tmp/aps-final-e-reentry-live.sXWWAA/aps-workbench-live-bffdvxmg/report-reentry-proof.json`，PID `33739 → 33789 → 33797`，端口 `62599`。
- 两类初始范围均保留 `query=OP`、原计划 ref、计划完工起止 `2026-09-09`、原专题/排序/size 10/page 2/selected ref。导出分别为全筛选 32 条记录和 65 道工序，不是只导第二页。下载文件与真实响应体逐字节相同，响应 `X-Workbench-Snapshot` / `X-Workbench-As-Of` 对应当前读取。
- 第二次新 PID 后不 reload 的导出、详情、下一页均真实返回 409；没有自动 page 1 请求。明确点击“重新读取”才按 page 1 → page 3 恢复目标页。未知原工序 ref 只请求该 ref 并显示 404，未改选其他对象。
- 旧形态 history 使用同次真实响应的原读取令牌，分别置于旧顶层及旧 `table` 字段测试兼容；未伪造 HTTP 数据。B 原四份 409 证据完全保留，没有覆盖或改写。
- `report-policy-widgets-02.xml` 中 report-policy、report-api、report-widgets、report-ledger-widgets 已通过；同组剩一个旧 Actual Gantt 日期弹层 probe 失败，不能记为全组通过。它不属于本次 Reports 新 PID 阻断。

### Main / B 使用的资产信息

- 完整资产根：`/tmp/aps-final-e-reentry-live.sXWWAA/full-build/static/workbench`。
- build ID：`2ab72cffda0497d97b4576fec291da318c7d5b8cb110bbeab8c23da7012dcfdb`。
- manifest：上述根下 `asset-manifest.json`，SHA-256 `46b8f2f589306a09275adeee3398a2dcc635746804f7fc64332e3c9e3d0f4607`，223 files / 315 inputs，目标 Chrome 109；文件及输入均逐项校验。
- 这是 E 当前源码的完整构建及运行时加载源守卫证据，不是完整源目录副本。B 应使用 Main 的新完整源码快照搭配同一输入版本重新构建/核对；不能把此资产当作旧 F13 源副本的匹配资产。

## 当前边界

- B252 仍需 Main/B 用新的完整源/资产快照重跑；本文件只证明 E 的两视图定向修复。
- Main V、最终完整测试登记、Git 归档及 clean-worktree gate 仍由 Main 统筹。E 不改 Main 的 registry、Git、运行中的其他宿主或原预览。
