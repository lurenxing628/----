---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-17"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 17：列筛选弹层在任何非弹层内滚动时立即关闭，已勾选未应用的筛选条件丢失

## 速答

表头列筛选弹层用 document 级捕获监听 scroll，除弹层内部滚动外，页面任何位置发生滚动都会关闭弹层——包括与弹层毫无关系的另一个滚动容器。排产员在几十个取值里勾了一半，滚轮碰到表格或页面就全部丢失，只能重来。

## 关键证据

- `frontend/workbench/app/ResourceTableFilter.jsx:111` — `document.addEventListener('scroll', scroll, true)`，捕获阶段监听全文档滚动。
- `ResourceTableFilter.jsx:77-95` — `scroll()`：`:78` 只豁免弹层内部滚动；`:82` 忽略开弹前投递的无位移事件；`:83-92` 容忍列表变短导致的浏览器夹取；其余一律 `:94` `close.current(false)`。对非祖先滚动容器，之前记录的位置为 undefined，直接走关闭分支。
- 对照：`:61-69` 已为祖先链记录滚动位置并在锚点脱离视口时关闭，说明作者意图是「锚点移走才关」，但兜底分支把范围扩到了全文档。

## 影响

筛选是基础资料、批次、工艺等宽表的高频操作，弹层关闭即丢失未应用的勾选，形成重复劳动；触发面覆盖任何滚动容器，滚轮落在可滚动区即触发。

## 修复方向

只在锚点移出视口或祖先容器滚动超过阈值时关闭，非祖先容器的滚动忽略；或关闭时把已勾选值暂存在列状态里，重新打开时恢复。补一条「弹层外无关滚动不丢选择」的探针。

## 建议动作

`cs-issue`，单组件交互修复。

## 复核记录（2026-09-13）

- 本条由原 P2-I12 升级：原文写「弹层外任何滚动即关」偏保守，实际连不相关的滚动容器也会关；「滚轮误触即消失」略夸，需真实发生滚动。升级理由是触发面宽、后果是重复劳动。

## 实施记录（2026-09-13）

- 状态：resolved。`ResourceTableFilter.jsx` `scroll()` 只响应锚点自身滚动祖先的滚动。
- 详见 [remediation-record.md](remediation-record.md)。
