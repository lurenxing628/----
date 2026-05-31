---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "maintainability-09"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 09：报表中心缺少回跳入口，资源过载无法一键定位到甘特或派工

## 速答

报表中心已经能看超期、资源负荷、计划和现场实际、停机影响，但很多报表仍像“看完就结束”的静态结果页。用户在资源负荷里看到设备或人员很忙时，不能一键带着同一版本、日期和资源跳回甘特图或资源派工继续处理。

## 关键证据

- `templates/reports/index.html:35-52` — 报表中心是四张静态入口卡，只有“超期清单”透出最新超期数量，其它入口没有风险摘要。
- `templates/reports/utilization.html:95-120` — 设备负荷表只有设备编号、设备名称、负荷、任务数、可用工时、利用率 6 列，没有“查看甘特”或“查看资源派工”一类回跳入口。
- `templates/reports/execution_review.html:72-76` — 计划和现场实际复盘以宽表为主，现场异常、暂停、偏差、反馈状态都在同一层，不像“先看异常、再钻任务”的处理台。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:235-265` — 调研明确资源负荷应贴近排程结果，而不是只藏在报表里。

## 影响

用户看到“某台设备利用率很高”后，还要自己回到甘特图或资源派工页重新选版本、日期、资源。这个问题不一定会造成数据错误，但会让报表变成死胡同，削弱“发现问题后立刻处理”的工作台体验。

## 修复方向

先不要做大型 BI 或复杂图表。建议在工作台路线里补最小回跳：资源负荷行能带版本、日期和资源跳到资源派工或甘特；计划实际复盘能跳到对应任务；超期清单能跳到同一版本下的甘特或分析证据。

## 建议动作

走 `cs-roadmap` 或后续 `cs-feat-design`。这条优先级低于首页值班台和甘特详情区，但应该作为工作台闭环的一部分排入后续。
