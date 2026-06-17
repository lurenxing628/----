---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "security-11"
nature: security
severity: P2
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 11：甘特调整资源变更接口整包返回内部字段

## 速答

`record-resource-change` 把 `ScheduleAdjustmentChange` 模型对象直接 `to_dict()` 后返回，包含 DB 主键和内部计划身份字段。

## 关键证据

- `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:59-74`：资源变更接口 `data = change.to_dict()` 后直接 `jsonify`。
- `core/models/schedule_adjustment.py:99-140`：`ScheduleAdjustmentChange` 含 `id/draft_id/schedule_id/op_id` 等字段，`to_dict()` 直接返回 `self.__dict__`。
- `data/repositories/schedule_adjustment_repo.py:157`：插入后把 `cur.lastrowid` 填回 `item.id`。
- 子代理前端核查：正式甘特页面目前没有接入调整接口 URL；测试只直接请求接口并断言 `change_type`，没有证据证明前端需要这些内部字段。
- 限定：只能证明此接口成立，不能证明它是“唯一净新外泄点”。

## 影响

当前调整功能未在页面开放，实际暴露风险较低；但接口响应面没有白名单，一旦被前端接入或被调用，会返回不需要给用户的内部字段。

## 修复方向

为调整接口定义公开响应白名单，只返回前端需要的状态、公开消息和必要展示字段；内部主键和 schedule 身份留在服务端。

## 建议动作

`cs-issue`，因为这是响应字段边界问题，修复时需要配测试锁住公开字段。
