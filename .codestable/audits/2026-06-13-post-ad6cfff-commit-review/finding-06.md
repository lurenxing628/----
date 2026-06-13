---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "bug-06"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 06：报表页查看旧版本时计划上下文胶囊可能显示空值

## 速答

计划上下文胶囊应该告诉用户当前页面正在看哪个版本、哪个方案、生成时间和策略。报表首页链路只取最新 1 条版本装饰数据；用户通过 URL 查看旧版本报表时，正文可能是旧版本，但胶囊拿不到旧版本对应的生成时间和策略，只能显示 `-`。

## 关键证据

- `web/routes/reports_page_support.py:141` — `reports_index_context` 调用 `_decorated_versions(engine, limit=1)`，只取最新版本。
- `web/routes/reports_page_support.py:160` — 随后按请求上下文发布 report context，版本可能来自 URL 参数，不一定是最新版本。
- `web/viewmodels/plan_context_capsule.py:35` — `history_row_capsule_fields` 只从传入 rows 里找版本。
- `web/viewmodels/plan_context_capsule.py:53` — 找到才返回 `schedule_time` 和 `strategy`。
- `web/viewmodels/plan_context_capsule.py:54` — 找不到直接返回空 dict，胶囊显示 `-`。

## 影响

用户打开旧版本报表时，主体数据按旧版本查，顶部上下文却可能显示“生成时间 - / 策略 -”。这会削弱计划上下文胶囊的核心价值：用户不能快速确认自己看到的是哪一次排产结果。

## 修复方向

报表页如果允许查看指定版本，就应该为指定版本取对应的版本装饰行。可以只补一条按 version 查询，不必为了胶囊加载全历史。若确实决定旧版本不补查，也要在设计文档里明确“旧版本胶囊不展示生成时间/策略”是业务取舍，而不是让用户误以为数据缺失。

## 建议动作

建议走 `cs-issue`，因为这是旧版本报表的上下文展示错误。
