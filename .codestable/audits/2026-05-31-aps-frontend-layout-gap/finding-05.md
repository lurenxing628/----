---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "maintainability-05"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-roadmap
status: open
---

# Finding 05：甘特页缺少任务详情抽屉和资源负荷摘要

## 速答

当前甘特页已经能只读查看排程结果，但还不像成熟 APS 的排产工作台：任务详情靠弹窗，资源负荷在报表页，模拟调整和正式采用页面入口仍未开放。

## 关键证据

- `templates/scheduler/gantt.html:160-177` — 页面明确是查看模式，“模拟调整”按钮禁用。
- `templates/scheduler/gantt.html:182-257` — 时间粒度、配色、批次筛选、资源筛选、仅超期等高频控制在“筛选与配色”折叠区。
- `.codestable/architecture/ui-gantt.md:58-60` — `simulate` 模式只保留事件出口，页面不能创建 Draft 或保存 Scenario。
- `.codestable/architecture/ui-gantt.md:73-75` — 后端已有校验试算接口，但页面没有注入入口地址。
- `.codestable/architecture/ui-gantt.md:123` — 后端已有 Scenario 正式采用能力，但页面不开放正式采用按钮。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:191-216` — 调研明确甘特应和表格、详情、资源负荷联动，并点名当前短板。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md:520-543` — 页面级建议明确补高频控制外露、任务详情抽屉、表格甘特联动和资源负荷摘要。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md:942-953` — 三差距调研也建议延期解释第一版先放在超期清单和排产分析，第二版再接入甘特 tooltip 和任务详情抽屉。

## 影响

计划员可以“看条”，但很难在同一页完成“点一条任务、看完整上下文、看资源是否过载、判断为什么红、再去处理”的连续动作。后端已经有不少模拟/发布地基，工作台路线图也已承接，但真实甘特页面还没有把这些能力组织出来。

## 修复方向

不要一口气开放拖拽发布。建议先做低风险工作台增强：固定任务详情区、资源负荷 Top 摘要、超期任务解释入口、表格和甘特互相定位。拖拽/正式采用应单独走更高风险 feature。

## 建议动作

走 `cs-roadmap` 拆分，后续每个子项再进入 `cs-feat-design`。
