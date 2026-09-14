---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "bug-03"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 03：排产来源切换按钮「当前选中」样式静默失效——引用三个全仓不存在的令牌

## 速答

`.scheduling-navigation .btn[aria-pressed="true"]` 引用 `--ui-primary-text` / `--ui-surface-selected` / `--ui-border-strong` 三个全仓零定义的 CSS 变量，全部落到 fallback 后与普通按钮逐属性相同。排产员无法从视觉上确认当前处于「计划版本」还是「排产记录」，属导航定位失效的真 bug。

## 关键证据

- `frontend/workbench/app/styles/34-run.css:158` — 选中态规则三个 `var()` 的首参数在 `frontend/` 全树定义 0 处，全部回退到 `--ui-text` / `--ui-surface` / `--ui-border`。
- `frontend/workbench/app/SchedulingWorkspace.jsx:70-71` — 「计划版本」「排产记录」两个按钮确实输出 `aria-pressed`，读屏可报状态，明眼用户反而得不到。
- 截图佐证：`evidence/workbench-ui/2026-09-12-final/browser-e696/analysis-1366-768-light-selected.png`（整改后 21:48 集合）里「计划版本」处于按下态，外观与「排产记录」完全一致。

## 影响

排产来源切换后用户得不到「当前在哪」的视觉确认。触发条件：进入选择排产方案页的顶部来源切换条。

## 修复方向

换成已定义令牌（如 `color: var(--ui-info-text); background: var(--ui-info-bg); border-color: var(--ui-primary)`），与同文件其他选中态写法对齐。修完在 `tests/workbench/test_ui_refinement_style_gate.py` 补一条「`var()` 首参数必须已定义」的静态扫描，防止再次引用不存在的变量。

## 建议动作

`cs-issue`，静默失效的样式 bug，修法明确。

## 复核记录（2026-09-13）

- 坐标改为源码；补整改后截图佐证。
- 原文引用的 `.seg` / `.rc-tabs` 选中态行号未复核，改为文字描述。

## 实施记录（2026-09-13）

- 状态：resolved。`34-run.css` 选中态改用已定义令牌；`tests/workbench-app-styles.cjs` 新增 `undefined-variable` 规则锁住全仓 `var(--x)` 引用。
- 详见 [remediation-record.md](remediation-record.md)。
