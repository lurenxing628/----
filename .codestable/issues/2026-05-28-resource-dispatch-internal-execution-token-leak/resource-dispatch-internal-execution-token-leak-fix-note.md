---
doc_type: issue-fix
issue: 2026-05-28-resource-dispatch-internal-execution-token-leak
path: fast-track
fix_date: 2026-05-28
status: completed
severity: P2
tags:
  - scheduler
  - resource-dispatch
  - execution-feedback
  - public-output
---

# 资源派工现场反馈内部值外露修复记录

## 问题

资源派工页的“现场反馈”任务卡里，异常任务出现了这些用户不该直接看到的内容：

- `最近反馈：报异常，exception`
- `情况说明 exception`

页面上已经有中文“报异常”“设备问题”“严重”等字段，所以这里再露出 `exception` 会让用户以为系统出了英文错误。

## 根因

这次不是单纯的前端翻译漏了一处，而是写入、汇总、展示三段链路都没有把“内部状态值”和“用户填写说明”分清楚。

真实链路如下：

- 页面提交异常反馈时，route 把 `remark` 和 `reason_detail` 交给 `OperationExecutionFeedbackService`。
- service 只做了必填和枚举校验，没有识别 `exception` 这类内部动作/状态值已经混进了用户说明字段。
- repository 把这些值写进 `OperationExecutionEvents.remark` 和 `OperationExecutionEvents.reason_detail`。
- `operation_execution_state_builder._event_remark()` 又把 `event.remark or event.reason_detail` 当成用户说明，写进 `last_event_remark` 和 `latest_exception_remark`。
- `scheduler_resource_dispatch_execution.build_task_card()` 原样输出这两个字段。
- `static/js/resource_dispatch.js` 的任务卡只是照着后端字段展示，所以浏览器最终看到了 `exception`。

当前运行库里也查到了对应脏数据：某条异常事件的 `event_type`、`reported_status`、`reason_detail`、`remark` 都是 `exception`。这说明页面看到的英文不是前端自己生成的，而是数据库里已经有脏的“用户说明”。

## 修复

这次没有只在前端遮住，而是在公共执行标签模块里增加了统一清洗规则：

- 如果用户说明字段里出现内部状态值、动作值、异常原因值、严重程度值、处理状态值，就不再把它当成用户说明。
- 读取旧数据时，状态汇总层不再把这类内部值放进 `last_event_remark` / `latest_exception_remark`。
- 事件列表 ViewModel 也使用同一套清洗规则，避免从另一个接口继续露出同类内容。
- 新提交现场反馈时，service 会先清洗 `remark` / `reason_detail`。如果异常反馈只填了 `exception` 这类内部值，就按“情况说明没填”处理，直接返回原有中文校验提示，不再写入事件表。

修复后，用户仍能看到：

- 最近动作：`报异常`
- 异常原因：`设备问题`
- 严重程度：`严重`
- 处理状态：`处理中`

但不会再看到孤零零的 `exception` 作为“情况说明”。

> 订正（2026-05-29）：上面描述的第一版清洗用的是“五张 label 字典全部键合成的全局黑名单”，
> 后续 review 发现它有三个问题：会误杀跨记录的合法说明（比如在设备异常里写 `person` 也被清空）、
> 只 `strip` 不归一大小写导致 `Exception` 能绕过、命中清洗无任何日志。已改为按“本条记录自己的
> 结构化码”精准判定：`public_execution_remark(value, internal_tokens=...)` 只在说明等于本记录的
> `event_type / reported_status / reason_code / severity / handling_status` 之一时才清空，判定用
> `casefold` 归一大小写；新增 `internal_remark_tokens_from_event` 供读取侧传入本行码集合。
> 写入 / 汇总 / 展示三段链路改用这套精准判定，既保留对 `exception` 等脏数据的清洗，又不再误杀
> 跨记录的合法英文说明。相关核实与修复留档见
> `.codestable/compound/2026-05-29-verification-resource-dispatch-site-records-review-repair.md`。

## 改动文件

- `core/models/operation_execution_labels.py`
- `core/services/scheduler/operation_execution_labels.py`
- `core/services/scheduler/operation_execution_feedback_service.py`
- `data/repositories/operation_execution_state_builder.py`
- `web/viewmodels/scheduler_resource_dispatch_execution.py`
- `tests/regression_operation_execution_exception_feedback.py`

## 验证

已通过：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_exception_feedback.py
```

结果：`9 passed`

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_state_revision.py
```

结果：`37 passed`

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/regression_resource_dispatch_public_output_contract.py
```

结果：`12 passed`

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile core/models/operation_execution_labels.py core/services/scheduler/operation_execution_labels.py core/services/scheduler/operation_execution_feedback_service.py data/repositories/operation_execution_state_builder.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_operation_execution_exception_feedback.py
```

结果：通过

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/models/operation_execution_labels.py core/services/scheduler/operation_execution_labels.py core/services/scheduler/operation_execution_feedback_service.py data/repositories/operation_execution_state_builder.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_operation_execution_exception_feedback.py
```

结果：`All checks passed!`

同一运行库复查：

- 重启 `http://127.0.0.1:61731` 本地服务后，查询 `op_id=2205` 的现场反馈任务卡。
- 接口返回 `last_event_action_label` 为 `报异常`。
- 接口返回 `last_event_remark` 为 `null`。
- 接口返回 `latest_exception_reason_label` 为 `设备问题`。
- 接口返回 `latest_exception_remark` 为 `null`。
- 事件列表最后一条异常记录的 `action_label` 仍为 `报异常`，`remark` 为 `null`。

## 遗留说明

旧数据库里已经存在的 `OperationExecutionEvents.remark='exception'` / `reason_detail='exception'` 没有被直接改写。这样做是为了不擅自改历史原始记录；页面和接口会在读取时过滤，不再把它当成用户说明展示。
