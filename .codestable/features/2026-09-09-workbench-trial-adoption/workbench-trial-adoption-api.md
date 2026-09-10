---
doc_type: feature
status: implemented
created: 2026-09-10
feature: workbench-trial-adoption
summary: CQ 场景正式采用给 UI 的稳定接口与回执合同
tags: [workbench, trial, api]
---

# 路径与请求

`S = /api/workbench/v1/trial/scenarios/<scenario_ref>`，引用来自原保存结果或场景目录，绝不把 candidate_ref/plan_ref 填入此路径。

1. `POST S/adopt-preview`，JSON 必须为 `{}`，不接受 URL 参数或可见范围。
2. `POST S/adopt`，JSON 严格为下列 CommandInput；`input.confirm` 必须是真布尔 true，原因最长1000字符，声明人最长100字符，两者去首尾空白后不能为空。
3. `GET S/adoption-commands/<request_key>`，仅查询原 key，不接受 URL 参数。全局 `/api/workbench/v1/commands/<request_key>` 也保留原通用回执查询。

```json
{
  "write_token": "采用预览返回的令牌",
  "request_key": "本次确认的原唯一请求标识",
  "input": {"confirm": true, "reason": "正式采用原因", "declared_operator": "声明操作人"}
}
```

request_key 沿用通用命令合同，不从时间戳拼短值，不在未知结果后换新 key 重发。确认内容一旦与原 key 绑定，不可更改 reason/declared_operator/scenario_ref 后复用。

# 采用预览

HTTP 200 沿用 `{ok:true,schema_version:1,data,meta,warnings:[]}`；`meta.source=production`、`time_basis=factory_local`，Cache-Control=no-store。

合法 `data`：

```json
{
  "scenario_ref": "原场景永久引用",
  "draft_ref": "原草稿永久引用",
  "baseline": {"plan_ref": "原正式基线引用或null", "version": 1},
  "task_count": 2,
  "scope_complete": true,
  "validation": {"status": "valid", "can_adopt": true, "issues": []},
  "write_context": {
    "write_token": "短期写令牌", "expires_at": "本机时间",
    "capabilities": {"trial.scenario.adopt": true}, "blocked_reasons": []
  }
}
```

业务阻断 `data` 包含原 `scenario_ref`、`validation={status:blocked,can_adopt:false,issues:[...]}`，write_token/expires_at 为 null，capability 为 false，blocked_reasons 为真实问题。此时未完成完整身份验证，不提供猜测的 draft_ref/task_count。issues 包含 code/message/severity，可带场景 task_ref/related_task_ref。

原 `GET S` 是保存当时的只读完整快照，其历史 validation 仍可能写着 `scenario_adoption_not_connected`。**现在是否可采用只认本次 adopt-preview**，不可重写原场景或把历史 validation 当成实时状态。采用预览不返回替代任务安排、不重新排产、不切换当前基础。

# 确认成功

HTTP 200：`{ok:true,result:committed,data,receipt_ref,replayed,warnings:[]}`。

`data={scenario_ref,draft_ref,row_count,official_plan}`；official_plan 包含新 `plan_ref/version/kind:official/is_current_official:true/display_name/baseline_ref/completeness:complete/capabilities/blocked_reasons`，及真实 `source_scenario_ref/source_draft_ref`。不含伪造 candidate_ref/run_ref/source_run_ref。

正式页面使用新 `official_plan.plan_ref`。原场景引用和内容永不改变；旧正式/执行不删除。同 key 同意图重放返回原 receipt_ref，replayed=true，不追加版本。回执中的 is_current_official 描述原提交时状态，重放后要重新读取当前正式目录，不能把旧回执当作新的当前状态证据。

# 失败与未知

- 参数错误400/422；基线、执行、输入漂移或约束冲突409；结构未安装503。`{ok:false,committed:false,error}` 沿通用错误合同。
- 分件场景仍受现有共用正式采用校验的证明边界约束，返回 `piece_adoption_unsupported` 或明确的上游分件输入缺证据原因，不显示可采用。
- 持久化异常 HTTP 500，`committed:unknown`，error 包含原 request_key、result_target=`S/adoption-commands/<原key>`、retryable=false。不能画“未保存”，不能自动采用第二次。
- 场景回执查询仍为查询 envelope。data=`{state:committed|not_observed,receipt:原命令结果|null,may_be_in_flight:boolean,can_retry_automatically:false}`。
- not_observed 仅证明这次没看到已提交回执，不能证明在途请求永远不会提交。重新预览不等于授权自动重做原命令。
- 所有采用都沿现有 WORKBENCH_CANDIDATE_ADOPTION_ENABLED 真 host 合同、全局 run 锁和 HTTP draining，没有独立场景启用开关。

# 本轮不接 UI

本文件供下一 UI slice 使用。CQ 未修改前端、主蓝图、DDL/迁移、registry/build，主线已接合路由。仅在临时测试数据库验证，不启动用户预览。
