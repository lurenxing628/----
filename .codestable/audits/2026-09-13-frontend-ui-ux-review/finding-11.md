---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "bug-11"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 11：资料总览页窗口聚焦即整表重置——回第 1 页、清空选中与详情

## 速答

资料总览页监听 window focus 事件：每次窗口重新获得焦点就整表重读并强制回到第 1 页，同时清空当前选中行与详情面板。排产员对照 Excel / ERP 准备导入数据时，每次切回浏览器都丢失页码、滚动位置和已打开的资料详情。

## 关键证据

- `frontend/workbench/app/MasterOverviewWorkspace.jsx:53-55` — `changed = () => setRequest({ scope: currentScope.current, page: 1 })`，同时挂在 `window.addEventListener('focus', changed)` 与 `aps:master-data-changed` 上。
- `MasterOverviewWorkspace.jsx:65` — 重读前 `setResult(null); setSelected(null); setDetail(null)`。
- 对照：`aps:master-data-changed` 事件是数据真的变了，走同一重置路径合理；focus 不应同罪。

## 影响

跨窗口工作（对照 Excel 录入 / 核对）时每切一次窗口就被打断，需重新筛选定位。触发条件：资料总览页 + 任何窗口切换。

## 修复方向

focus 重读改为「数据可能已更新」提示条加用户手点刷新；或至少保留 page / selected / detail 状态，只静默刷新数据。保留 `aps:master-data-changed` 的重置语义不变。

## 建议动作

`cs-issue`，局部交互逻辑修改，补一条「切窗不丢位置」的针对性测试。

## 复核记录（2026-09-13）

- 事实核实无误；坐标由构建产物 `:127-131,156-158` 改为源码 `:53-55,65`。

## 实施记录（2026-09-13）

- 状态：resolved。`MasterOverviewWorkspace.jsx` focus 只标记 stale 并提供「刷新本页」原地重读，保留页码 / 选中 / 详情。
- 详见 [remediation-record.md](remediation-record.md)。
