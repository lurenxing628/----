---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
title: 候选进入试调的来源展示与约束说明纠正
roadmap: workbench-manual-remediation
---

## 现场与根因

主代理在隔离 5001 页面从候选点击“试调”时，实际 input.base 是正确的 candidate_ref，预览也复制了该候选的两道安排；但 `TrialCatalog.SourceCatalog` 的 kind 无条件初始化为 plan，`Create` 又把已有选择统一写成“指定原来源”，导致显示正式计划列表却提交候选来源。

“此功能尚未开通：保存只留下试调方案，不会改变正式计划。”来自 `core/models/workbench_trial.py` 的 validation()。该函数先算真实 constraints_status，再无条件追加 adoption 能力 blocker 并把整体 status 设为 blocked。它并不阻止草稿创建或保存，却被 UI/CSV 当成实际约束冲突。真实采用已经由 `WorkbenchTrialAdoptionService` 独立实施，route 使用 `WORKBENCH_CANDIDATE_ADOPTION_ENABLED`，并不是整个功能未接通。

两道试调未覆盖当前完整正式计划时，原采用 guard 会抛 `official_scope_not_covered`；试调包装层保留代码却把具体原因改成笼统的“没有通过采用前核对”。因此还有实际阻止原因被丢失的问题。

## 修改

- 继承来源时显示对应类型、永久 ref 与明确来源卡；用户点击“更换来源”才展开目录。目录按已有 candidate_ref / plan_ref 初始化，不再固定指向正式计划。
- 试调预览直接返回原有 admission.source.identity 为 base_identity，前端核验它与输入 ref 一致，核对后显示权威名称。没有新增另一套来源身份，也不重查最新计划替代原来源。
- 新 validation.issues 只含真实约束；status 与 constraints_status 一致。can_adopt 保持 false；仅在独立采用预检成功时才获得采用授权。原 adoption 字段改为“正式采用前需要单独预检”，不再报告功能未开通。
- 旧保存快照不重写。UI 和对比 CSV 只排除已确定的历史能力 code `scenario_adoption_not_connected`；所有真实 blocker/warning 保留。原始 JSON 导出仍保留旧事实，输入对象不被修改。
- 覆盖不足现在说明：“试调方案没有覆盖当前正式计划的全部工序。请将相关批次一起排产后再试调。”覆盖、资源、现场记录、原版本和事务 guard 全部保留。
- 创建/保存的确认复选框未在本次范围内移除；本次纠正来源、能力说明和真实拒绝原因。

## 验证

- 已执行 symbol-locator：validation 定义/调用方、preview_create 定义/调用方；来源链按 TrialWorkspace → TrialCatalog → TrialAPI → preview_create → admission.source.identity 核对。
- `.venv/bin/python -m pytest tests/workbench/test_trial_source_presentation.py tests/workbench/test_trial_api_schema.py tests/workbench/test_trial_lifecycle.py tests/workbench/test_trial_validation.py tests/workbench/test_trial_adoption_validation.py tests/workbench/test_trial_adoption_api.py -q`：43 passed / 9.69 秒。
- 新测试用真实临时数据库建立“候选仅含 B1、正式计划仍含 B2”，保存试调后采用预检继续返回 official_scope_not_covered、无 write_token，数据库逐表快照完全不变。真实冲突仍阻止采用；正式/候选来源 identity 与创建后的保存值一致。
- `node tests/workbench/trial_source_presentation_contract.cjs`：通过；当前 JSX 编译后直接验证继承 candidate 类型、权威名称、更换目录初始类型、旧能力说明排除、真实冲突保留和 CSV/原始 JSON 区分。此测试不启动浏览器。
- 更新现有浏览器验收的相关断言，交主代理 IAB 验证；本子任务没有启动或操作 Chrome，没有改 static、构建资源、活服务或真实数据库。
- `git diff --check` 通过。按用户要求没有运行全门禁或整仓测试；仅有 dirty 工作区上的上述专项证明。
