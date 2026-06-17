# Finding 11：plan_context_token 仍允许裸 scenario_id 回退

- 优先级：P2，需要产品口径确认
- 结论：如果 plan_context_token 的目标是访问门禁，当前实现没有收口；如果目标只是 URL 脱敏，则需要把文档和测试写清楚。

## 根因

非空 token 会走登记和过期校验，但请求里没有 token 时，代码会直接接受 `scenario_id`。这意味着拿到裸 `scenario_id` 的请求可以绕过 token 的登记、过期、失效提示。

## 调用链

- `web/routes/domains/scheduler/scheduler_plan_context_token.py::request_scenario_id_from_args()`
- 如果 `plan_context_token` 非空：`resolve_public_token()`
- 如果 token 空：读取 `scenario_id`
- Gantt、周计划、周计划打印、资源派工、报表等入口再用这个 scenario_id 读取场景方案

## 证据

- `web/public_token_registry.py:62-82`：token 颁发并写过期时间。
- `web/public_token_registry.py:85-100`：非空 token 会校验登记和过期。
- `web/routes/domains/scheduler/scheduler_plan_context_token.py:30-35`：token 空时直接回退 `scenario_id`。
- `web/routes/domains/scheduler/scheduler_gantt.py:132-140`：Gantt 入口有同样的 raw `scenario_id` 回退。
- `web/routes/domains/scheduler/scheduler_week_plan.py:74-79`：周计划入口同理。
- `web/routes/domains/scheduler/scheduler_week_plan_print.py:118-119`：周计划打印入口同理。
- `web/routes/domains/scheduler/scheduler_resource_dispatch_query.py:61-65`：资源派工入口同理。
- `web/routes/reports_request_support.py:53-54`：报表请求支持层同理。
- `tests/gantt/test_gantt_draft_save_and_preview.py:315-326`：测试仍直接用 raw `scenario_id` 并期待成功。
- `tests/web_pages/test_scenario_preview_secondary_outputs.py:228`：二级输出页面测试仍保留 raw `scenario_id` 访问预览上下文。

## 影响

- 如果业务期待“公开链接过期后不可访问”，裸 scenario_id 会绕过这个期待。
- 如果业务只是期待“链接上不要暴露真实 id”，那当前代码可以成立，但需要把它说清楚，避免把脱敏误当权限。

## 建议

- 先拍板 token 的含义：
  - 如果是访问门禁：删除裸 `scenario_id` 回退，并迁移测试。
  - 如果只是脱敏：文档、注释、页面文案都明确“不是权限控制”。
