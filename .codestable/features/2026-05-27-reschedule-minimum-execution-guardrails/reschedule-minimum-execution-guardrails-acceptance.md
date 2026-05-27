---
doc_type: feature-acceptance
feature: 2026-05-27-reschedule-minimum-execution-guardrails
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: reschedule-minimum-execution-guardrails
created: 2026-05-27
---

# 重排最小现场护栏验收

## 验收结论

已完成。

本阶段把开工和完工现场事实接入普通重排主链路。系统现在不会再把已经开工或已经完工的工序当成普通待排任务随意移动；同时，第 9 项预备好的普通用户开工/完工按钮和直接 POST 已经放开到“最新正式采用方案”。

## 已落地范围

- 新增 `ExecutionFactProvider`，按工序读取执行状态、实际开始、实际完工、实际设备、实际人员和状态版本。
- 普通重排输入阶段读取执行事实：已完工工序从待排集合移除，生产中工序生成 `execution_fact` seed。
- 执行事实 seed 和 freeze window seed 分来源合并；同一道工序两边时间或资源冲突时返回中文 `6003`，不写新排程。
- 落库前重新读取现场状态版本；现场刚刚变化、生产中工序被移动、已完工工序被移动时，都拒绝写入，连 `ScheduleVersionSeq` 版本流水号也一起回滚。
- 执行事实缺少实际设备或实际人员时，直接提示现场反馈记录不完整，不再用 `Schedule` 里的计划资源冒充现场实际资源。
- `simulate=True` 且已有开工/完工事实时只做安全校验，不写 `Schedule / ScheduleHistory / ScheduleVersionSeq`，也不返回可打开版本；周计划页面不会提示“生成版本”，也不会跳到不存在的甘特版本。
- 普通用户可在最新正式采用方案上直接开工/完工，成功后返回刷新后的任务卡和新 `state_revision`。
- 资源派工页按钮提交开工/完工时，`created_by` 来自页面必填“反馈人”；未填写时页面直接提示，不再写固定假用户。
- 候选方案、模拟预览、历史正式方案、非最新正式采用方案仍拒绝开工/完工写入。

## 对抗性审核闭环

- 第 10 项第一轮整阶段复审使用 4 个子代理：
  - Hubble `019e67a2-892a-7270-91ca-81c33aee7e5b`：审重排主链路，发现落库前没有覆盖“输入后现场刚变化”的阻塞项；已补全量 state_revision 复查和测试。
  - Fermat `019e67a2-f4c4-7303-bd58-8f468a1c52c3`：审反馈前后端，发现按钮只渲染但没有 POST 绑定；已补前端点击提交、任务卡局部刷新和静态测试。
  - Bernoulli `019e67a2-f55f-7c90-a3b2-7db95a314a3c`：审执行事实 provider/repository，结论 OK。
  - Dirac `019e67a2-f5dd-7650-b9c5-01c8cdc81037`：审测试和 CodeStable，发现 simulate 冲突和落库前状态变化测试不足；已补测试。
- 第 10 项第二轮整阶段复审使用 4 个子代理：
  - Harvey `019e67af-50f0-71a0-8d03-8b0fde7414ef`：发现 `simulate=True` 已有执行事实时页面仍会误报“生成版本”并跳甘特图；已改为返回不可打开版本并提示“只做安全检查”。
  - Kepler `019e67af-5183-7cb0-82af-695115ae6a43`：审普通用户开工/完工入口，结论 OK。
  - Kuhn `019e67af-5216-7b91-895b-a2897abc1da3`：发现 Python 3.8 不兼容 `tuple[...]` 阻塞，并指出执行事实缺资源时不应回退计划资源；已改为 `Tuple[...]`，缺实际资源直接拒绝。
  - Carver `019e67af-530a-73a0-9906-c9060243c370`：发现同一 Python 3.8 阻塞；修复后扫描通过。
- 第 10 项修复后整阶段复审使用 4 个子代理：
  - Rawls `019e67b9-b680-7352-afa9-902f01bd0053`：审普通重排输入、seed、落库保护、模拟页面和第 13 项边界，结论 OK。
  - Kierkegaard `019e67b9-b706-72a3-8c62-3aeb50cdf893`：审现场反馈入口，结论无阻塞；提示 route 层有重复身份判断，记录为后续可整理项。
  - Lorentz `019e67b9-b792-7310-a458-30b71f6fb34d`：审执行事实读模型、状态版本、分层和 Python 3.8，结论 OK。
  - Carson `019e67b9-b831-7941-a3cb-a3d14f9e27eb`：审 CodeStable 产物和测试，结论无阻塞；提示 items.yaml 测试命令漏列周计划模拟页面测试，已回写。
- 第 10 项追加整阶段复审继续使用子代理：
  - Turing `019e67c6-6336-7ed0-a416-d50929d0bab2`：发现 `simulate=True` 安全检查仍会推进 `ScheduleVersionSeq`；已改为安全检查不分配版本号。
  - Popper `019e67d2-65f1-7751-8db8-c7639f6258c5`：审用户入口和服务写入保护，结论无阻塞。
  - Mendel `019e67d2-6591-7a91-8a71-3adcdb1a90f4`：发现最终落库校验失败时仍可能留下 `ScheduleVersionSeq` 跳号；已把版本号分配和最终保存放进同一事务，并新增回归锁住。
  - Banach `019e67dd-0a0d-74f2-a403-1122571afd22`：发现冻结窗口会把后续工序锁在已完工前道工序的真实完工时间之前；已在 seed 合并后和落库前双层校验，并新增回归锁住。
  - Dalton `019e67eb-9cb3-79d1-a2e6-8e8ef02b1b5d`：发现资源派工页按钮点击路径仍把 `created_by` 固定成“现场反馈”；已改为页面必填“反馈人”，空值直接提示并不发起写入。
- 第 10 项最终整阶段复审使用 5 个无导向只读子代理：
  - Plato `019e67fd-5740-7cd1-9da6-08aa9b8ec695`：审普通重排主链路，结论 OK，阻塞项 0。
  - Darwin `019e67fd-5801-72d1-b5b9-c69b0cee03a7`：审现场反馈写入链路，结论 OK，阻塞项 0；提示 route 层身份判断可后续整理。
  - Pascal `019e67fd-5922-7762-b3ea-191b342ba6ef`：审执行事实读模型、状态版本和事件聚合，结论 OK，阻塞项 0；提示历史排程清理若未来落地需单独保护事件审计。
  - Hooke `019e67fd-5a77-7730-a4fd-7c42be776c7b`：审前端、中文、离线静态资源和页面一致性，结论 OK，阻塞项 0；提示可后续补浏览器级点击测试。
  - Mencius `019e67fd-5b85-7b31-a1a0-bf949eeedfad`：审 CodeStable 产物一致性，结论 OK，阻塞项 0。
- 本轮接手后，在第 4-9 项回溯复审全部阻塞清零后，又对第 10 项做了 5 个中性只读子代理复审（`019e6992-84ec-7350-ad63-13ba62ec4df8`、`019e6993-3ae7-7290-a3e7-116fad7b93f8`、`019e6993-3b5c-7413-98cc-f0a5dfcbd9ea`、`019e6993-3c1c-7760-a4ec-c14c71330fe2`、`019e6993-3cde-7562-bf3d-6f2a61b410d7`），分别覆盖重排主链路、反馈入口、执行事件读模型、CodeStable 产物和横向分层/兼容边界；结论均为 OK，阻塞项 0。非阻塞提醒是当前工作区不是 clean-worktree proof，以及暂停/继续/报异常仍属于第 11 项范围。

最终复审阻塞项为 0，可以继续第 11 项。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py`
  - 结果：`46 passed`；其中第 10 项最小护栏测试新增覆盖“最终落库校验失败时 `ScheduleVersionSeq` 也不能推进”，以及“冻结窗口不能把后续工序锁在已完工真实完工时间之前”。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py`
  - 结果：已通过；覆盖页面存在“反馈人”输入、前端按钮提交不再写固定“现场反馈”、直接 POST 写入和任务卡刷新仍正常。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_persistence_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_event_foundation.py tests/test_schedule_persistence_auto_assign_contract.py::test_simulate_keeps_real_status_and_auto_assign_resources_unchanged tests/regression_schedule_service_facade_delegation.py`
  - 结果：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-27-reschedule-minimum-execution-guardrails/reschedule-minimum-execution-guardrails-design.md --require doc_type --require status`
  - 结果：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-27-reschedule-minimum-execution-guardrails/reschedule-minimum-execution-guardrails-checklist.yaml --yaml-only`
  - 结果：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-27-reschedule-minimum-execution-guardrails/reschedule-minimum-execution-guardrails-acceptance.md --require doc_type --require status`
  - 结果：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only`
  - 结果：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/scheduler/execution_fact_provider.py core/services/scheduler/run/schedule_input_collector.py core/services/scheduler/run/schedule_input_runtime_support.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_persistence.py core/services/scheduler/run/schedule_candidate_persistence_helpers.py core/services/scheduler/schedule_service.py core/services/scheduler/resource_dispatch_execution_service.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/routes/domains/scheduler/scheduler_week_plan.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_operation_execution_feedback_routes.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 不实现暂停、继续生产、报异常、异常原因、严重程度、影响时间、影响资源、处理状态或是否建议重排。
- 不新增 `execution_snapshot_revision`、`execution_snapshot_op_ids`。
- 不接入候选比较、多起点、局部搜索、图排程 ready queue、scenario 保存或 scenario 发布复算。
- 不把 freeze window 当成现场事实。
- 不修改历史计划行表示的原始计划事实。
