---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-14"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 14：候选甘特无颜色图例，且红色语义与计划甘特冲突

## 速答

计划甘特有 7 项完整色块图例，其中 critical 红 = 「预计超期」（坏事）；候选甘特只有一行文字说明，且 critical 红 = 「重叠拆轨」（中性显示手段）。排产员带着计划甘特的经验看候选甘特，会把中性拆轨误判为超期告警。

## 关键证据

- `frontend/workbench/app/PlanGantt.jsx:149-152` — 计划甘特 7 项图例：安排 / 已确认准时 / 预计超期（critical）/ 资源重叠 / 初始计划 / 零工时工序 / 今日·数据时点。
- `frontend/workbench/app/RunCandidateGantt.jsx:31` — `tone = … row.normalLaneCount > 1 ? 'critical' : 'primary'`，同一资源多子轨即着 critical 色；`:110` — 唯一说明是一行文字「… 重叠拆轨（不等同于业务冲突结论） · 外协独立色」，没有色块图例。

## 影响

同一颜色在两个核心视图语义相反，是「每个页面都要重学」的典型来源；误判候选方案的冲突状况可能导致错误的采用决策。

## 修复方向

① 候选甘特补色块图例组件，复用计划甘特图例的呈现方式；② 两张图统一 critical 语义，或给「重叠拆轨」换一个不与告警冲突的颜色或纹理。文案按词表口径改「时间重叠的安排分行显示」「外协工序用另一种颜色」。

## 建议动作

`cs-issue`，与 finding-01（色盲双通道）同批实施。

## 复核记录（2026-09-13）

- 事实核实无误；坐标由构建产物（`PlanGantt.js:481-510`、`RunCandidateGantt.js:365,93`）改为源码。
- 原截图引用 `run-presentation/1920x1080-light-candidate-target-1366.png` 属 09-12 18:09 中间集合，改以代码为准。

## 实施记录（2026-09-13）

- 状态：resolved。`RunCandidateGantt.jsx` 色块图例；重叠不再用 critical 红。
- 详见 [remediation-record.md](remediation-record.md)。
