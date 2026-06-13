---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "bug-05"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 05：预览/参考方案缺明细时仍会生成 adopted 甘特链接

## 速答

手拼链接收编的目标之一，是避免用户点了预览/参考方案链接，结果静默回到正式方案视角。当前仍有一条链路会 fallback 到 adopted，并继续生成可点击甘特链接。

## 关键证据

- `core/services/scheduler/schedule_plan_query_service.py:123` — 合法对比角色缺明细时允许 fallback 到 adopted。
- `core/services/scheduler/schedule_plan_query_service.py:124` — 注释说明 fallback 会带 `status=fallback_to_adopted` 披露。
- `web/routes/domains/scheduler/scheduler_analysis_links.py:68` — 页面层拿 `resolve_navigation_plan_context` 的结果继续生成导航上下文。
- `web/routes/domains/scheduler/scheduler_analysis_links.py:69` — 使用 `selected_role` 作为 effective role。
- `web/viewmodels/scheduler_workbench_link_query.py:265` — 链接 query 继续附带 `context["plan_role"]`。
- `web/routes/domains/scheduler/scheduler_analysis_links.py:74` — 日期跨度读取还用了宽泛 `except Exception`，容易把服务注入错误或编程错误也转成“日期范围读取失败”。

## 影响

大白话说，用户以为自己点的是“预览方案/参考方案”的甘特图，但系统在缺明细时可能给了“正式采用方案”的链接。即使页面某处有 fallback 提示，链接本身仍然容易误导用户继续走错视角。

## 修复方向

如果产品允许 fallback，就要把“实际生效方案”显眼带进链接标签、disabled_reason 或上下文胶囊，不能让链接看起来还像原方案。如果产品不允许这里 fallback，缺明细时应禁用链接并说明原因。宽泛 `except Exception` 也建议缩窄到预期的数据缺失异常。

## 建议动作

建议走 `cs-issue`，因为这是用户可点击路径的语义错误。
