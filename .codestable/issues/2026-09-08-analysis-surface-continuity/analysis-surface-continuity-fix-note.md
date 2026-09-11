---
doc_type: issue-fix
date: 2026-09-08
slug: analysis-surface-continuity
status: implemented
scope: local workbench reports and execution review
clean_worktree_proof: false
---

# 执行复盘与报表中心的背景和层级

## 问题与最终取舍

用户指出浅色报表中心、执行复盘上下区域割裂，要求检查同类页面。本轮最初尝试将两页主内容区铺白，用户进一步指出它们与其他页面底色不一致。该尝试已撤销，最终不为这两页另设页面底色。

最终采用全站共用层级：页面使用 `--ui-bg`，指标和表格使用 `--ui-card-bg`，表头使用 `--ui-surface-muted`；标题、筛选、说明和分页不再放在额外的整块白色底板上。必要的表头底线、数据行线、指标内部竖线、状态色和焦点标记保持。

用户本轮询问数字是否需要强调色，已提供选择性强调的建议，未据此修改数字颜色、数值或计算口径。

## 根因证据

- 修改前两个工作台根节点都显式设置浅色白底，而其父级透明继承灰色页面底，形成整块白色正文板。
- 内容区域实际 `box-shadow` 为 `none`；顶栏仍有 `0 1px 2px rgba(0,0,0,.05)` 阴影。不能把底色形成的悬浮感全部归为内容投影。
- 明细工具栏使用 17px/24px 的分区标题，表格前还留有报表 2px、复盘 4px 外间距及表头顶线，进一步强化了单独起板的感觉。
- 实测检查 14 个路由。批次表的冻结列细阴影、甘特选中内标记与基础资料已批准的产能链卡片不是同类正文底板问题，未一并删除。

## 修改文件

运行时文件均位于 `前端设计/ui_kits/workbench/`：

| 文件 | 最终修改 |
| --- | --- |
| `AppShell.jsx:54` | 仅 reports/review 添加 `analysis-workspace` 标记，不改变普通页面或数据 |
| `operations-workspaces.css:6` | 仅取消这两页顶栏阴影；没有特殊主区背景覆盖 |
| `report-workbench.css:41` | 去掉工作台根节点浅色白底，明细标题改为 14px/20px，取消表格前外间距及重复顶线 |
| `execution-review.css:27` | 与报表采用相同处理，其他分析小节标题不改 |
| `index.html:28` | 更新四个改动资源的内容哈希，避免入口使用旧缓存 |
| `tests/analysis-surface-continuity.cjs:135` | 新增背景一致性、必要分隔线、主题与真实跨页作用域回归 |

未改报表/复盘 JSX 内容、模型、计算、排序、导出、存储或甘特逻辑。字体、字号体系、表格行高和控件高度均保留，只有明细工具栏标题降一级。

## 最终验证

| 实际运行 | 结果 |
| --- | --- |
| 新增 `analysis-surface-continuity.cjs` | 1126 项通过、64 张截图；1920x1080 / 1392x924、深浅色、5 个报表专题；背景继承、表头/行线/指标竖线、真实侧栏往返和基础资料特殊卡片保持 |
| `analysis-alignment-browser.cjs` | 520 项通过；两页、双尺寸/主题、3 个数据源；筛选对齐、条件展开/清除、所有专题及图表 |
| `workbench-workflow-browser.cjs` | 247 项通过、56 张截图；14 页双尺寸/主题，方案采用、跨页、排产前检查、甘特交互；无运行错误、外部请求、资源失败或整页横向溢出 |
| `workbench-shared-style.cjs` | 1649 项通过，含 1436 个文本检查，最小对比度 4.61；这是 JSDOM 样式合同检查，不替代 Chrome 截图 |
| `workbench-offline-assets.cjs` | 234 项通过；本地资源、语法、固定依赖与许可 |

最终实际颜色：浅色两页与普通页面同为 `rgb(241,245,249)`，工作台和主内容区保持透明；指标/表格仍为白色。明细工具栏与表格间的额外间距实测 0px。

报表表格起点 417.09px，复盘 396.59px。默认数据都能显示 5 条；复杂/密集数据在 1920px 下分别显示 9/10 条，1392px 下均显示 7 条，没有靠缩小正文或压缩行高换取空间。

本轮使用 1 个真实 subagent 编写并运行新增测试，主代理负责运行时修改、截图取舍与原有回归；已检查其实际结果并关闭。所有浏览器测试均使用隔离上下文并已关闭，不修改用户浏览器存储。

## 证据与边界

- `evidence/light-before-after.png`：左侧为本轮开始前，右侧为最终统一灰底版本；上方报表，下方复盘。
- `evidence/*-after.png`：两页两尺寸双主题最终截图，不含已撤销的整页白底试验。
- `evidence/before-surfaces.json`、`alignment-measurements.json`、`continuity-measurements.json`：实际测量。
- 原始快照：`/tmp/aps-surface-continuity-kvCM6H/before-surface-files.tgz`，SHA256 `afe2637da8c9f3bb318380bb3cabd0b9c2821d25736e60af05d9e0a82bd6fbb8`。
- 最终全页截图：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-1qi49w/`；新增测试原始输出：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-analysis-surface-continuity-t14U1j/`。临时目录可能被系统清理，精选证据已复制到本记录目录。

当前工作区已有大量未提交内容，未回退或提交。既有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行新增保持不变；原型目录受现有 Git 忽略规则影响，未强制加入暂存。本记录及原型改动均未提交。

这是本地原型局部验证，不是 clean-worktree proof；未运行生产 Python 整仓门禁或 Win7 实机。未改 Win7/Python3.8 运行时，未引入远程资源或新依赖。
