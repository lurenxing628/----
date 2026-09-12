---
doc_type: issue-fix
status: fixed
created: 2026-09-12
summary: 恢复工作台外壳原有窄屏侧栏与页头换行，390/768/1280 两主题定点几何通过
tags: [workbench, ui, css, responsive, regression]
---

# 修复与边界

- 只修改产品文件 `frontend/workbench/app/styles/10-shell.css:50-64`，恢复原有窄屏支持。没有修改业务数据、甘特算法、测试断言或其他产品源文件，也没有添加 overflow 隐藏来掩盖问题。
- 本次是脏工作区定点验证；**尚无本轮完整门禁通过结论，也不是 clean-worktree proof**。正式验证入口为真实 `WorkbenchShell` 加已选择的正式计划；夹具入口为 `AppShell operations` 加真实当前组件、模拟只读计划数据。

# 根因

`10-shell.css:7` 的 `flex-basis:var(--sidebar-width)` 仍取桌面值 240px，覆盖了旧 `operations-workspaces.css:9` 在 ≤900px 下的侧栏 `width:56px`；第 21 行主区 `max-width` 也继续扣除 240px。新增规则还压过了旧窄屏导航组隐藏、导航间距及页头/页面断点。

390px 的失败现场中，主区只有 150px，计划选择器溢出，页面 `scrollWidth=492`；甘特滚动区宽 100px，小于冻结标签列的 125px，时间区实际可见宽度为 0。不是计划时间范围或零时长数据错误。

修复在 ≤900px 的 `.operations-shell` 上统一把侧栏变量设为 56px，同时恢复原导航与页面间距。页头和控件条允许换行并随内容增高，以容纳正式入口的实例标签、帮助、主题和密度控件；≤600px 恢复原小屏横向间距与标题字号。

# 定点结果

| 宽度 | 修前侧栏 / 页面宽 / 时间区宽 | 修后侧栏 / 页面宽 / 时间区宽 |
| --- | --- | --- |
| 390 | 240 / 492 / 0 | 56 / 390 / 187 |
| 768 | 240 / 768 / 353 | 56 / 768 / 504 |
| 1280 | 240 / 1280 / 820 | 240 / 1280 / 820 |

- 每行均执行 light/dark 两主题。修后夹具 6 组与正式入口 6 组均无页面溢出、无未被局部滚动容器容纳的越界节点、无页面错误；正式页头全部交互控件位于视口内，当前正式计划胶囊存在。
- Chromium `109.0.5414.46`。正式入口使用 root 统一构建 `6cf12853223f40cd6f2a24c3df59a28c4b6225b8701ee886378298dd6a83e542`，冻结时源文件差异为空；夹具修后采样是旧构建上加载当前源 CSS，单独记录，未冒充新构建验证。
- root 已执行样式合同：54 passed，1.23 秒；本代理没有重复执行。隔离正式服务已正常关闭，冻结资产及业务状态前后哈希一致。

# 证据

- [完整汇总与逐文件 SHA-256](/Users/lurenxing/GitHub/----/evidence/workbench-ui/2026-09-12-final/gate-failure-closures/narrow-shell/summary.json)
- [修前全部越界节点与矩形](/Users/lurenxing/GitHub/----/evidence/workbench-ui/2026-09-12-final/gate-failure-closures/narrow-shell/before/report.json)
- [修后夹具原始结果](/Users/lurenxing/GitHub/----/evidence/workbench-ui/2026-09-12-final/gate-failure-closures/narrow-shell/fixture-after/report.json)
- [修后正式入口原始结果](/Users/lurenxing/GitHub/----/evidence/workbench-ui/2026-09-12-final/gate-failure-closures/narrow-shell/main-after/report.json)

CSS SHA-256：`6aa5660eff3167561c250957546fa40767a9dcb37cda88aa4d192922770fbfb8`。两份执行脚本、前后 CSS 字节、18 张截图、样式合同日志/JUnit、正式构建清单和服务退出证据均已归档；目录未包含数据库或完整运行 fixture。
