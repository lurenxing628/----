---
doc_type: issue-fix
date: 2026-09-09
slug: system-maintenance-navigation
status: implemented
scope: local system overview maintenance shortcuts
clean_worktree_proof: false
---

# 系统管理维护摘要整行入口

用户指出三项维护摘要只有右侧小箭头可点击，批准保留状态摘要、整行可点击并收紧高度的方案。原实现 `sm-work-row` 是普通 div，点击处理只绑定到内部 32px 箭头按钮。

## 修改

文件均在 `前端设计/ui_kits/workbench/`：

- `SystemManagementScreen.jsx`：将三项摘要统一渲染为原生 `button type="button"`。标题、描述、左侧图标、箭头及空白区域共用一个事件。箭头仅作装饰，不再形成独立焦点；保留原操作名称、状态描述和数据源边界。
- `SystemManagementScreen.jsx`：在原 `onTab` 中统一将焦点移至目标页签，复用既有页签定位方式，移除方向键处理里的重复聚焦调用。
- `system-workbench.css`：整行悬停反馈、内部蓝色键盘焦点、原状态色和行间分隔线；减少垂直留白，保留页面其他区域及桌面双栏/窄屏堆叠规则。
- `index.html`：更新上述两个资源的内容哈希。
- `tests/system-maintenance-navigation.cjs`：新增实际命中区域、键盘、焦点、紧凑布局、只导航不执行维护的浏览器回归。

没有修改备份、恢复、清理、导出、参数保存、数据源或模型逻辑。三项仍分别进入备份恢复、运行日志、配置页签，不直接执行任何维护动作。

## 验证

| 实际运行 | 结果 |
| --- | --- |
| 整行导航 Chrome | 1510 项通过；1920x1080、1392x924、390x844，双主题、当前原型/管理样例；点击图标、标题、描述、箭头、空白处，Tab/Shift+Tab、Enter/Space、焦点跟随及原状态保留 |
| 系统页完整布局/交互 Chrome | 3630 项通过、32 状态、52 截图；双桌面尺寸/主题、两数据源及四个页签，包含原导出、记录详情、参数校验和主题配置流程 |
| 系统页 DOM | 159 项通过；含原下载内容、配置、详情焦点等合同 |
| 系统模型 | 108 项通过；包含 10000 行样例压力场景 |
| 全站共享样式 | 1643 项通过、1436 个文本检查，最小对比度 4.61；JSDOM 样式检查，不替代真实浏览器 |
| 离线资源/语法 | 234 项通过；两个资源缓存版本与最终文件哈希一致 |

整行导航专项没有产生请求或下载，前后管理样例、配置及隔离上下文 localStorage 保持一致；正式维护操作仍不可用。原有系统布局测试中的主动导出另行正常执行，不与“导航不产生下载”混为一谈。

桌面当前原型三项行高从约 98/111/86px 收紧到 90/91/67px，合计减少约 47px；窄屏允许文字自然换行，不强制压缩高度。已检查实际浅色、深色、悬停及键盘焦点截图。

## 证据及边界

- `evidence/before-after.png`：左侧修改前，右侧修改后整行悬停。
- `evidence/navigation-measurements.json`、`before.json`：实际断言及修改前尺寸。
- 原始快照、专项与完整布局输出：`/tmp/aps-system-row.UQHVOZ/`；精选截图已复制至本记录，临时目录可能被清理。

此次局部实施未使用 subagent，所有浏览器为隔离上下文并已关闭。未修改用户浏览器存储或执行实际本机维护。

当前工作区已有大量未提交内容，未回退或提交。既有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行新增保持不变；原型目录仍受既有 Git 忽略规则影响，未强制加入暂存。本次仅验证本地原型，未运行生产 Python 整仓门禁或 Win7 实机，不是 clean-worktree proof；未引入新依赖或改变 Win7/Python3.8 运行时。
