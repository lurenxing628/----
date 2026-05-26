---
doc_type: roadmap-draft
roadmap: aps-three-gap-directions
created: 2026-05-25
source: subagent-reference-chain-review
---

# APS 三个差距方向 Subagent 引用链证据账本

本文件持续记录 2026-05-25 为起草 `aps-three-gap-directions` roadmap 以及后续同范围对抗性审核启动的真实 Subagent。

这些 Subagent 都是只读调查或只读审核，没有改文件。主代理根据它们的结果写入 roadmap、items、原 explore 作废提示和本账本；原 explore 文件继续作为研究证据保留，但不再作为实现口径。

## 调用清单

| 序号 | agent_id | 昵称 | 调查范围 | 关键结论 |
| --- | --- | --- | --- | --- |
| 1 | `019e5af3-35aa-7692-9bc4-1ceaf6d748de` | Carson | 候选方案生成、选择、持久化 | 已有多候选生成和代表方案落库；第一版只能承诺代表三方案，不能承诺全候选明细大屏。 |
| 2 | `019e5af3-3613-7080-9354-9cc745cb0469` | Kant | 候选方案 UI、ViewModel、模板、跳转 | 当前是指标表；推荐卡、摘要卡、指标差值、跳转增强应拆开做。 |
| 3 | `019e5af3-3675-7bc0-8516-57bb12d2e281` | Bernoulli | 超期/延期计算基础链路 | 当前只判断已排程逾期和未排程逾期，不能可靠输出根因，只能输出事实、线索、证据和缺口。 |
| 4 | `019e5af3-36d4-7551-b87e-92b79ab18110` | Cicero | 关键链、停机、资源、物料线索 | critical chain 是全局链路，不是单批次根因；资源高负荷、停机、齐套只能作为证据。 |
| 5 | `019e5af3-3726-7313-8ce9-e306991b7a79` | Nash | 资源派工、计划身份、方案来源 | 资源派工能看正式、候选、scenario；确认派工和现场反馈只能基于正式 adopted。 |
| 6 | `019e5af3-3785-7232-89d3-c0c858034342` | Goodall | 车间执行状态现状 | 现有 `Schedule` 和 `BatchOperations.status` 不能当现场事实；必须新增执行事件和状态读模型。 |
| 7 | `019e5af3-37db-75e3-827a-4b6304635222` | Mendel | 车间异常反馈 | 没有异常反馈入口；异常反馈要独立拆分，不能和开工/完工最小闭环混在一起。 |
| 8 | `019e5af3-3855-78e0-b5ff-7df830381c07` | Einstein | 甘特 scenario、草稿、发布链路 | scenario 后端可预览和发布，但前端拖拽未开放；scenario 必须发布成正式版本后才可派工。 |
| 9 | `019e5af3-38c3-7c60-823c-c29463936e45` | Gibbs | 重排输入和执行事实 | 当前靠冻结窗口，不读现场事实；`processing` 仍可重排，后续要新增 ExecutionFactProvider。 |
| 10 | `019e5af3-3931-78b3-a377-6d5978d07bd2` | Laplace | 计划 vs 实际复盘 | 当前没有真正计划 vs 实际；复盘依赖执行事件字段，最小视图应显示开始/完工偏差和异常。 |
| 11 | `019e5af3-398b-7990-ad84-72d2c3811912` | Volta | 测试、质量门禁、fixture | 现有测试可复用；每条 feature 要写正常、空数据、非法状态、Win7/offline/Chrome109 验收。 |
| 12 | `019e5af3-39e4-7182-b1e9-12ab3885c259` | Avicenna | Win7、Python 3.8、离线约束、市场差距边界 | 本 roadmap 是局部路线图，不覆盖全局优先级；必须写入 Win7 x64、Python 3.8、离线本地静态资源硬约束。 |
| 13 | `019e5af3-3a46-7423-bb58-8dab60a24b2f` | Sartre | CodeStable roadmap 格式 | 应新增 `.codestable/roadmap/aps-three-gap-directions/`；validate-yaml 只校验 YAML 和必填字段，不校验 DAG。 |
| 14 | `019e5af3-3aaa-7772-8b1e-c6c3f9e85180` | Mill | 目标 explore 文档迁移边界 | explore 前半保留为证据，后半迁到 roadmap；指出旧行号和拟新增文件要标清。 |
| 15 | `019e5af3-3b09-7c92-8e0b-57362d6be40d` | Huygens | Web 路由/API 边界和错误处理 | 三方向继续放 `/scheduler/...` 和 `/reports/...`；JSON 错误复用现有 `success=false/error` 形状。 |
| 16 | `019e5af3-3b9b-7e50-b708-6f48ed78da18` | Boole | schema、迁移、repository 模式 | 新表要走 `schema.sql` + 迁移版本 + repository + 测试，不能只在 service 裸写 SQL。 |

## 写入 roadmap 的关键修正

- 原 explore 中 `schedule_orchestrator.py:366-404` 已过期，当前候选比较证据应改看 `schedule_orchestrator.py:237-250` 和 `schedule_orchestrator.py:309-313`。
- 方案对比第一版只承诺 `adopted / baseline_best / critical_best` 三类代表方案。
- 延期解释不能写“根因定位”，只能写“已确认事实 / 可能原因 / 证据 / 缺口 / 建议动作”。
- critical chain 是全局链路，不能直接当单个批次根因链。
- 资源派工页能读取正式、候选、scenario；但写现场反馈只能基于正式 adopted。
- scenario 后端发布链路存在，但前端拖拽未开放，不可写成“甘特拖拽可用”。
- 当前没有独立执行事件；`Schedule`、`BatchOperations.status`、`Schedule.lock_status` 都不能当现场事实源。
- 异常反馈要单独拆，不塞进开工/完工最小闭环。
- 重排现在不尊重现场事实；必须等执行事件和状态读模型后再接入。
- 数据库新增能力必须走迁移和 repository。
- 第一轮里“诊断返回补 audit_snapshot”是旧说法；当前已统一为轻量 `DiagnosisTraceMeta`，后续不要再新增重型诊断快照，除非另起持久化设计。

## 后续可复查命令

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items
```

## 第十轮对抗性审核

2026-05-25 第九轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 本轮还要求继续检查用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束

本轮 16 个 Subagent 全部只读审核，均已完成。本轮归并结论是：仍存在阻塞项，主要集中在计划身份字段漏项、用户可见旧词、证据事实结构、超期导出工作表名、原型页越界承诺、资源派工公开 JSON、幂等冲突顺序、执行状态字段、最小重排职责边界、Python 3.8 注解，以及第八轮变更日志证据口径。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5c2c-11b3-7311-9337-920f9966ed84` | Ramanujan the 2nd | 依赖图和整体拆解 | OK | 无阻塞；保持当前 DAG 和最小闭环口径。 |
| 2 | `019e5c2c-1312-7460-88d0-0f2f6e81de9b` | Descartes the 2nd | PlanIdentity 字段完整性 | 有阻塞 | `PlanIdentity` 退出检查补 `candidate_key`、`label`、`is_official`、`is_preview`、`detail_saved`。 |
| 3 | `019e5c2c-15c4-75f1-97a2-3c644d54a2d0` | Hume the 2nd | 用户可见“基准方案 / 基准版本”旧词 | 有阻塞 | 调整周计划、甘特调整、方案查询、模拟发布等用户可见文案，改成“预览依据 / 调整依据 / 所选方案”等大白话。 |
| 4 | `019e5c2c-179f-7512-bc2d-1bdf201ce398` | Archimedes the 2nd | 延期诊断事实结构和超期导出 | 有阻塞 | `confirmed_facts` 改为每条事实绑定证据；超期导出工作表名改为“超期清单”。 |
| 5 | `019e5c2c-1998-7133-bdd8-12f50f3636c8` | Galileo the 2nd | 原型页方案对比是否越界 | 有阻塞 | 原型页第一版收窄为推荐卡、三方案摘要、总指标差值和跳转入口；批次、设备、人员细明细改成后续版本空状态。 |
| 6 | `019e5c2c-1d51-7850-b1af-1310a5da4613` | Harvey the 2nd | 异常反馈和按钮边界 | OK | 无阻塞；保持按钮放开顺序和异常状态边界。 |
| 7 | `019e5c2c-2221-7143-9bb3-2a6e7b9f16f2` | Epicurus the 2nd | 资源派工公开 JSON | 有阻塞 | `scheduler_resource_dispatch.py` 对 `plan_role_options` 只公开 `role / label / is_comparison`，并补公开 JSON 脱敏测试。 |
| 8 | `019e5c2c-2447-7882-810d-3834c3e8df63` | Raman the 2nd | 执行事件幂等和 UNIQUE 冲突 | 有阻塞 | 明确任何 UNIQUE 冲突后先按 `idempotency_key` 查同 key；同内容返回已有事件，不同内容返回 `idempotency_conflict`。 |
| 9 | `019e5c2c-26b2-78b3-9218-76f7ac982f6e` | Gauss the 2nd | `OperationExecutionState` 字段完整性 | 有阻塞 | 补 `current_status_label`、实际设备/人员、最后事件中文动作/备注、最新异常全套字段和 `updated_at`。 |
| 10 | `019e5c2c-2a23-7e12-9149-a8a68aa96cbc` | Socrates the 2nd | 颗粒度和能否照着做 | OK | 无阻塞；继续保持 items 的文件范围、退出检查和测试入口。 |
| 11 | `019e5c2c-2dd9-7d62-983e-e35460e636c6` | Einstein the 2nd | 最小重排和完整重排边界 | 有阻塞 | `reschedule-minimum-execution-guardrails` 只管开工/完工最小护栏；完整快照、候选、多起点、图排程和 scenario 保存/发布归完整重排条目。 |
| 12 | `019e5c2c-3159-7830-a668-37c7bf251220` | Franklin the 2nd | 复盘和报表边界 | OK | 无阻塞；保持复盘路由和导出列边界。 |
| 13 | `019e5c2c-33df-7c90-9665-3bf0d7ab9e41` | Confucius the 2nd | 文档整体一致性 | OK | 无阻塞；保持 roadmap 与 items 主口径一致。 |
| 14 | `019e5c2c-37a1-7542-adf6-094ca4455f7a` | Meitner the 2nd | 用户可见旧词和“分数”表达 | 有阻塞 | 配置、手册、页面说明中把“整体分数 / 分数高”改成“整体表现 / 内部参考值”等低门槛表达。 |
| 15 | `019e5c2c-3a48-7e82-8bb7-f2ab380bb3b2` | Newton the 2nd | Python 3.8 注解兼容 | 有阻塞 | 将被点名测试里的 `set[str] / list[str] / dict[str, ...] / tuple[str, ...] / re.Match[str]` 改回 Python 3.8 可读写法，并补 docs-quality Python 3.8 扫描命令。 |
| 16 | `019e5c2c-40f5-7c22-beab-035b5ab4eaaf` | Hegel the 2nd | 账本和变更日志证据口径 | 有阻塞 | 第八轮变更日志改为诚实口径：按主代理归并记录修复；逐个 agent_id 证据缺口只在本账本说明，不补编不存在的 id。 |

第十轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：公开 JSON 纳入“不露内部字段”规则；`confirmed_facts` 改为绑定证据的结构；修正幂等冲突顺序；收窄最小重排条目边界；修正第八轮变更日志证据口径。
- `aps-three-gap-directions-items.yaml`：补 PlanIdentity 字段、延期诊断 facts 结构、超期导出中文工作表名、执行事件幂等顺序、`OperationExecutionState` 字段、最小重排边界和 docs-quality Python 3.8 扫描要求。
- `core/services/report/exporters/xlsx.py`：超期导出工作表名改为“超期清单”。
- `core/services/scheduler/week_plan_excel.py`、`core/services/scheduler/schedule_plan_query_service.py`、`core/services/scheduler/gantt_adjustment_*`：清理用户可见“基准方案 / 基准版本”旧词。
- `core/services/scheduler/config/config_field_spec.py`、`web/viewmodels/page_manuals_scheduler_outputs.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`：清理用户可见“分数”旧表达。
- `docs/aps_frontend_workbench_mockup.html`：把批次级和资源级影响清单改为“后续版本再补”的空状态，不再承诺第一版有细明细。
- `web/viewmodels/scheduler_resource_dispatch.py`、`tests/test_resource_dispatch_viewmodel.py`：资源派工公开 JSON 脱敏并补测试。
- `tests/regression_frontend_offline_static_assets.py`、`tests/regression_config_manual_markdown.py`、`tests/regression_page_manual_registry.py`、`tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`：改回 Python 3.8 可读的类型写法。

第十轮存在阻塞且已修复。后续必须继续启动第十一轮同范围 16 个 Subagent 复审；第十一轮范围不能缩小，也不能只盯着第十轮刚修的问题。

## 第十一轮对抗性审核

2026-05-25 第十轮修复和验证后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束

本轮正式计入的 16 个 Subagent 全部只读审核，均已完成并关闭。第十一轮正式启动前曾误触发 1 个单独子代理 `019e5c4c-2f38-7830-9844-0d484943bbbe`，已立即关闭，不计入本轮。本轮归并结论是：仍存在阻塞项，主要集中在公开 JSON 规则和接口契约冲突、资源派工 filters/client_filters 脱敏、`execution/data` 任务卡字段、最小重排和完整重排职责边界、原型页旧词、资源负荷工作表名、docs-quality 命令可执行性、候选失败原因、模拟预览命名、异常字段中文名一致性，以及“程序内部传参”和“用户能看到的文字”没有拆清。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5c4d-cbd7-7e23-b580-d60501c5c7b5` | Aristotle the 3rd | CodeStable 格式、DAG 和整体颗粒度 | 有阻塞 | `docs-quality-gate` 命令改为当前真实存在的测试，Python 3.8 扫描命令改为位置参数。 |
| 2 | `019e5c4d-cc3c-7b41-8351-0306a6635943` | Curie the 2nd | 用户可见大白话和前端原型 | 有阻塞 | 清理原型页 `18h/24h/计划 vs 实际`，并把前端旧词加入离线大白话测试。 |
| 3 | `019e5c4d-cd20-7b22-90e4-e017af8152c1` | Darwin the 2nd | 公开 JSON 和程序字段边界 | 有阻塞 | roadmap 改成“程序内部字段可传参但不能展示”，并要求同时提供中文 label/message。 |
| 4 | `019e5c4d-d1d7-7e60-93b9-15df81c87d64` | Euclid the 2nd | 资源派工脱敏 | 有阻塞 | `resource_dispatch` payload filters 和 client_filters 去掉计划身份、来源表和候选内部字段，并补测试。 |
| 5 | `019e5c4d-d3d4-7b72-86b4-b46f33efd26b` | Faraday the 2nd | 车间反馈 `execution/data` 契约 | 有阻塞 | `execution/data` 补 `plan_identity_label`、最后事件、更新时间，并把按钮字段改为 `available_actions`。 |
| 6 | `019e5c4d-d736-7390-81a0-3be9d8619734` | Galileo the 3rd | POST 成功/失败 JSON 和错误 reason | 有阻塞 | roadmap 明确 POST 请求体和响应里的程序字段只给前端逻辑使用，页面只显示中文字段。 |
| 7 | `019e5c4d-db32-7472-8f59-86c67d549934` | Hume the 3rd | 候选失败原因用户文案 | 有阻塞 | `scheduler_analysis_candidates.py` 增加失败原因中文映射，避免 `candidate_time_budget_reached` 等内部值显示给用户。 |
| 8 | `019e5c4d-dd76-7030-9435-5b5e80c64f5e` | Kant the 3rd | 模拟预览名称和错误提示 | 有阻塞 | 新模拟预览无名称时使用“模拟预览（未命名）”，发布缺参提示改成“模拟预览不能为空”。 |
| 9 | `019e5c4d-e0d3-7211-867d-9ed7fc55ed83` | Laplace the 3rd | 最小重排护栏边界 | 有阻塞 | 从最小护栏移除 scenario publish revision 测试，保留开工固定、完工剔除和普通重排最小冲突检查。 |
| 10 | `019e5c4d-e4b4-7570-92ff-cdc78d992b4e` | Leibniz the 2nd | 完整重排职责 | 有阻塞 | 完整重排依赖理由改成只复用最小护栏已落地规则；完整执行快照和 scenario 发布冲突检查在完整重排新增。 |
| 11 | `019e5c4d-e77d-76c2-9e40-6f97ec08f09f` | Maxwell the 2nd | 资源负荷 Excel 用户可见工作表 | 有阻塞 | 资源负荷导出工作表名改为“设备负荷 / 人员负荷”，测试和手册同步。 |
| 12 | `019e5c4d-ebb9-74c1-a539-07b2da770afa` | Noether the 2nd | 异常反馈中文固定表 | 有阻塞 | `external` 用户中文统一为“外协问题”，roadmap 和 items 保持一致。 |
| 13 | `019e5c4d-ed6d-72c3-a2d7-1bc6d6cdb321` | Pascal the 2nd | docs-quality 收口命令 | 有阻塞 | 删除当前不存在测试的必跑命令，把实施后新增测试写成条件说明，避免照抄失败。 |
| 14 | `019e5c4d-f05e-7f93-ab77-08f9eb93daf5` | Poincare the 2nd | 资源派工 URL/hidden input 边界 | 有阻塞 | roadmap 明确 URL、hidden input、data 属性可作为程序内部传参，但不能当可见文案或导出内容。 |
| 15 | `019e5c4d-f378-7243-89e3-60fa86a97e72` | Raman the 3rd | 测试覆盖和可照做性 | 有阻塞 | 补 filters/client_filters 脱敏断言、失败原因映射测试和原型旧词扫描。 |
| 16 | `019e5c4d-f867-7b92-b45b-6a3e79dbff69` | Turing the 2nd | 总体阻塞压力测试 | 有阻塞 | 合并修正代码、测试、roadmap、items 和本账本；修复后必须继续第十二轮同范围 16 个 Subagent 复审。 |

第十一轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：拆清程序内部传参与用户可见文案边界；`execution/data` 改为 `available_actions`，补 `plan_identity_label`、最后事件字段和 `updated_at`；异常原因 `external` 统一为“外协问题”；补第十轮和第十一轮变更日志。
- `aps-three-gap-directions-items.yaml`：修正 `resource-dispatch-start-finish-feedback` 的任务卡字段；从最小重排护栏移除 scenario 发布测试；修正完整重排依赖理由；docs-quality 命令改成当前可运行的测试和 Python 3.8 扫描命令。
- `web/viewmodels/scheduler_resource_dispatch.py`、`tests/test_resource_dispatch_viewmodel.py`、`tests/regression_scheduler_candidate_resource_dispatch_contract.py`：资源派工公开 payload 和 client_filters 去掉计划身份、来源表、候选、模拟预览等内部字段，内部页面上下文和导出日志仍保留程序字段供服务端使用。
- `core/services/report/exporters/xlsx.py`、`tests/regression_report_export_size_mode_selection.py`、`tests/regression_reports_export_version_default_latest.py`、`tests/regression_scheduler_candidate_reports_contract.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`：资源负荷工作表和用户说明改为“设备负荷 / 人员负荷”。
- `web/viewmodels/scheduler_analysis_candidates.py`、`tests/regression_scheduler_candidate_analysis_contract.py`：候选失败原因先映射成中文大白话，未知内部英文或堆栈不原样展示。
- `core/services/scheduler/gantt_adjustment_scenario_service.py`、`core/services/scheduler/gantt_adjustment_publish_service.py`：模拟预览无名称时不拼内部编号，缺参提示不再说“编号”。
- `docs/aps_frontend_workbench_mockup.html`、`tests/regression_frontend_offline_static_assets.py`：原型页继续清理旧词，新增旧词扫描。

第十一轮存在阻塞且已修复。后续必须继续启动第十二轮同范围 16 个 Subagent 复审；第十二轮范围不能缩小，也不能只盯着第十一轮刚修的问题。

## 第十二轮对抗性审核

2026-05-25 第十一轮修复和验证后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束

本轮 16 个 Subagent 全部只读审核，均已返回；结果已消费，已逐个关闭或发起关闭。关闭 `019e5c6c-3973-7de0-9a67-4bdf8eac6d13` 时工具提示 `agent not found`，本账本不伪造关闭成功，只记录该子代理结果已被消费。本轮归并结论是：仍存在阻塞项，主要集中在 active explore 旧词、原型页旧异常原因、测试仍保护旧标签、普通用户错误提示暴露内部工序 ID、现场反馈失败 JSON 缺中文字段名、docs-quality Python 扫描范围容易漏后续新增代码。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5c6c-0cf5-7521-bba6-74fb6dc49407` | 未记录 | CodeStable/账本格式 | OK | 无阻塞；保持账本诚实记录真实 agent id 和轮次状态。 |
| 2 | `019e5c6c-0d62-7b52-a3b5-fd7b763cd401` | 未记录 | 用户可见错误提示 | 有阻塞 | `operation_edit_service.py` 和 `schedule_service.py` 的工序不存在提示改为中文大白话，不再显示 `ID=...`。 |
| 3 | `019e5c6c-0e4e-7d90-aa6e-0781cdef3daa` | 未记录 | 公开 JSON / 程序字段边界 | OK | 无阻塞；继续保持程序字段只给前端逻辑，用户只看中文 label/message。 |
| 4 | `019e5c6c-0fee-7c12-82ff-5e3a10576c0c` | 未记录 | 资源派工 / 计划身份 | OK | 无阻塞；保持正式采用方案才能写反馈的边界。 |
| 5 | `019e5c6c-119a-7e92-ac1e-8e2c272e9876` | 未记录 | POST 失败 JSON 字段中文名 | 有阻塞 | roadmap 和 items 补 `details.field_label`；`core/shared/field_labels.py` 补现场反馈字段中文名映射并加测试。 |
| 6 | `019e5c6c-1545-79d1-9904-b774db04f3d1` | 未记录 | 执行事件 / 幂等 / 错误码 | OK | 无阻塞；保持幂等优先和 6003/409 冲突口径。 |
| 7 | `019e5c6c-19a3-7891-8481-65da932f3ef1` | 未记录 | 候选方案 role label 测试 | 有阻塞 | `tests/regression_scheduler_analysis_candidate_links_and_roles.py` 期望改为“正式采用方案 / 原算法代表方案 / 重点工序优先代表方案”。 |
| 8 | `019e5c6c-1cc7-7b01-84e8-727bcd51adbb` | 未记录 | 模拟预览命名 | OK | 无阻塞；保持“模拟预览（未命名）”兜底。 |
| 9 | `019e5c6c-205f-77c2-ba24-7516b82f658a` | 未记录 | 最小重排 / 完整重排边界 | OK | 无阻塞；保持最小护栏只管开工/完工安全补洞。 |
| 10 | `019e5c6c-25db-74e2-b4fd-94bc272a63b6` | 未记录 | 原型页和 explore 旧词 | 有阻塞 | 清理原型页和 explore 中“设备故障 / 缺料 / 换型等待 / 影响交期 / 已停工”等旧词，改成设备问题、物料问题、工艺问题、严重、紧急。 |
| 11 | `019e5c6c-28b0-7560-84cb-cdf363fcb8b4` | 未记录 | 延期诊断 / 证据 / 导出 | OK | 无阻塞；保持只说可能线索和证据不足，不编造原因。 |
| 12 | `019e5c6c-2cd5-7651-ad6a-688135adadde` | 未记录 | active explore 旧词 | 有阻塞 | `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md` 继续清理“计划 vs 实际”等旧词。 |
| 13 | `019e5c6c-2fc4-7540-aff3-46fe829ca93e` | 未记录 | docs-quality 命令 | OK | 无阻塞；现有命令可跑，但本轮另补扫描范围不能只照抄固定文件。 |
| 14 | `019e5c6c-3459-7ad1-bd80-ee8016e2c4b9` | 未记录 | 原型 / 离线资源 | OK | 无阻塞；继续用离线静态资源测试锁原型页。 |
| 15 | `019e5c6c-3809-7c81-91fe-917d38286e36` | 未记录 | items 颗粒度 / DAG | OK | 无阻塞；保持当前拆分粒度。 |
| 16 | `019e5c6c-3973-7de0-9a67-4bdf8eac6d13` | 未记录 | 原型旧词和 docs-quality 扫描范围 | 有阻塞 | 原型“对照基线”改成“对比参考”；docs-quality 补必须汇总本 roadmap 所有已完成 feature 新增/修改 Python 文件后扫描。 |

第十二轮修复采纳后，主代理已继续修改：

- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`、`.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：清理会误导后续实现的旧说法，统一成“正式采用方案 / 原算法代表方案 / 重点工序优先代表方案”“计划和现场实际”“设备问题 / 物料问题 / 工艺问题 / 外协问题”“轻微 / 一般 / 严重 / 紧急”等口径。
- `docs/aps_frontend_workbench_mockup.html`、`tests/regression_frontend_offline_static_assets.py`：原型页清理“对照基线、设备故障、缺料、换型等待”等旧词，并把更多禁词加入测试。
- `tests/regression_scheduler_analysis_candidate_links_and_roles.py`：同步新的三方案中文标签。
- `core/services/scheduler/operation_edit_service.py`、`core/services/scheduler/schedule_service.py`：普通用户错误提示不再暴露内部工序 ID。
- `core/shared/field_labels.py`、`tests/regression_scheduler_user_visible_messages.py`：补现场反馈字段中文名映射和测试，避免页面显示 `created_by / reason_code / severity / expected_state_revision` 等程序字段。
- `aps-three-gap-directions-roadmap.md`、`aps-three-gap-directions-items.yaml`：失败 JSON 契约补 `details.field_label`；docs-quality 补清 Python 3.8 扫描范围必须覆盖所有已完成 feature 的新增/修改 Python 文件，不能只照抄固定示例命令。

第十二轮存在阻塞且已修复。后续必须继续启动第十三轮同范围 16 个 Subagent 复审；第十三轮范围不能缩小，也不能只盯着第十二轮刚修的问题。

## 第十三轮对抗性审核

2026-05-25 第十二轮修复和验证后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 16 个 Subagent 全部只读审核，均已返回；结果已消费。大多数子代理已成功关闭，关闭 `019e5c86-fed5-77b0-9d52-cae8c65257e7` 时工具提示 `agent not found`，本账本不伪造关闭成功，只记录该子代理结果已被消费。本轮归并结论是：仍存在阻塞项，主要集中在另一个 active explore 旧路线误导、现场反馈字段中文名漏项、用户可见旧词、执行事件 repository 契约不够细、`report_exception` 和数据库 `exception` 映射不够硬、开工/完工按钮放开验收断点、原型禁词缺漏。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5c86-dae4-7c41-ac96-595cf8f65275` | Ptolemy the 3rd | 旧前端布局 explore 是否还会被照做 | 有阻塞 | `2026-05-23-explore-aps-frontend-layout-benchmark.md` 改为 `status: superseded`、`confidence: mixed`，补 `superseded-by` 和顶部提示；清理“影响清单”“暂停/继续/报异常”被当作第一版照做的风险。 |
| 2 | `019e5c86-db45-7763-82a7-1ddf6408aff8` | Hypatia the 3rd | 用户可见字段中文名和错误提示 | 有阻塞 | `core/shared/field_labels.py` 和测试补 `requested_plan_role / effective_plan_role / schedule_id / schedule_version / source_table / scenario_id / op_id / plan_role` 中文名。 |
| 3 | `019e5c86-dc69-7203-b304-025fc552e18f` | Hubble the 3rd | 工序编号和停机记录错误提示 | 有阻塞 | `operation_edit_service.py` 的 `工序ID 不合法` 改为“工序编号不正确，请刷新批次详情后重试。”；停机记录不存在提示不再显示内部 ID。 |
| 4 | `019e5c86-df0d-7e42-b84b-b85ceecc4ca9` | Epicurus the 3rd | 配置、手册和导出里的旧词 | 有阻塞 | 配置项改为“正式方案选择方式 / 系统自动挑正式采用方案”；候选保存错误改为“方案对比缺少正式采用方案”；Excel 手册把 preview 过期和预览基线改成“检查结果过期 / 检查时的数据状态”。 |
| 5 | `019e5c86-e2d8-7080-b3b1-a78acc17c415` | Aristotle the 3rd | 执行事件 repository 颗粒度 | 有阻塞 | roadmap 和 items 写明 `data/repositories/operation_execution_event_repo.py`、`OperationExecutionEventRepo` 以及按 id、幂等键、op_id、op_ids、最近事件、最近异常、聚合状态等方法。 |
| 6 | `019e5c86-e4c5-7300-a0b3-3e23b30cf193` | Zeno the 3rd | `report_exception` 和数据库事件类型映射 | 有阻塞 | route 的 `/report-exception`、程序动作 `report_exception`、数据库 `event_type='exception'`、返回 `action_label='报异常'` 的映射写进 roadmap 和 items；页面和导出不得显示 `exception/report_exception`。 |
| 7 | `019e5c86-e670-7073-b81e-8395cf7f5b56` | Rawls the 3rd | 开工/完工按钮放开顺序 | 有阻塞 | `reschedule-minimum-execution-guardrails` 补资源派工模板、JS、反馈 route、POST 测试；明确本条完成后才解除上一条普通用户按钮隐藏/禁用，并同时验收页面按钮和直接 POST。 |
| 8 | `019e5c86-ebb3-74e0-8c1c-30221931ce47` | Mendel the 3rd | docs-quality、Win7、Python 3.8 | OK | 无阻塞；继续保留 Python 3.8、Win7 x64、离线静态资源和 docs-quality 收口要求。 |
| 9 | `019e5c86-f10e-70e0-a4a6-1f02610a01ed` | Planck the 3rd | items 颗粒度和能否照着做 | OK | 无阻塞；本轮只按其他子代理指出的局部缺口继续补细。 |
| 10 | `019e5c86-f576-78e3-ae64-ab9fc394ce22` | McClintock the 3rd | 原型页旧词测试 | 有阻塞 | `tests/regression_frontend_offline_static_assets.py` 禁词补“缺料 / 影响交期 / 已停工”，只锁原型页，不全仓禁止业务可理解词。 |
| 11 | `019e5c86-f90f-79f0-91f7-82678371ff95` | Archimedes the 3rd | 资源派工隐藏字段和用户可见边界 | 非阻塞 | `plan_role / scenario_id` 在 URL、hidden input、data 属性中作为程序传参可保留；roadmap 已明确这些不能当可见文案或导出内容。 |
| 12 | `019e5c86-fc80-7391-959d-87d469f1db2e` | Pascal the 3rd | POST 失败字段 label 和字段覆盖 | 有阻塞 | 现场反馈字段中文名映射扩展到计划身份、排程记录、模拟预览、工序编号等内部提交字段，失败响应页面只能显示 `field_label`。 |
| 13 | `019e5c86-fed5-77b0-9d52-cae8c65257e7` | Huygens the 3rd | 执行事件幂等和 repository 回查 | 有阻塞 | 捕获 `idempotency_key` UNIQUE 冲突后必须通过 `OperationExecutionEventRepo.get_by_idempotency_key()` 回查，service 不能临时裸写 SQL。 |
| 14 | `019e5c87-01d5-7103-890b-98aeed5ecdfd` | Popper the 3rd | 旧 explore 与 roadmap 冲突 | 有阻塞 | 前端布局 explore 标废并加顶部提示；把方案对比细明细、异常解释和车间反馈旧第一版口径改成“后续按 roadmap 单独做”。 |
| 15 | `019e5c87-050b-7941-a85c-d0dea6c76d00` | Curie the 3rd | 用户可见大白话一致性 | 有阻塞 | 页面、导出、按钮、表格、错误提示、手册继续改成中文大白话；配置和 Excel 手册同步清理旧内部词。 |
| 16 | `019e5c87-0849-7a41-8385-4ad003b5fc95` | Lorentz the 3rd | 总体阻塞压力测试 | 有阻塞 | 合并修正代码、测试、roadmap、items、旧 explore 和本账本；修复后必须继续第十四轮同范围 16 个 Subagent 复审。 |

第十三轮修复采纳后，主代理已继续修改：

- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`：改为 superseded，补 `superseded-by` 和顶部提示，清理会把方案对比细明细、暂停/继续/报异常误当第一版照做的旧口径。
- `aps-three-gap-directions-roadmap.md`、`aps-three-gap-directions-items.yaml`：补执行事件 repository 的具体文件、类和方法；写死 `report_exception` 到数据库 `exception` 的转换；补开工/完工按钮放开时必须同批验收页面按钮和直接 POST；补现场反馈字段中文名覆盖范围。
- `core/shared/field_labels.py`、`tests/regression_scheduler_user_visible_messages.py`：补计划身份、排程记录、模拟预览、工序编号等字段中文名。
- `core/services/scheduler/operation_edit_service.py`、`core/services/scheduler/config/config_field_spec.py`、`core/services/scheduler/run/schedule_candidate_persistence.py`、`core/services/equipment/machine_downtime_service.py`、`web/viewmodels/page_manuals_excel_demo.py`、`tests/regression_config_field_spec_contract.py`：清理用户可见旧词和旧测试期望。
- `tests/regression_frontend_offline_static_assets.py`：原型禁词补“缺料 / 影响交期 / 已停工”。

第十三轮存在阻塞且已修复。后续必须继续启动第十四轮同范围 16 个 Subagent 复审；第十四轮范围不能缩小，也不能只盯着第十三轮刚修的问题。

## 第十四轮对抗性审核

2026-05-25 第十三轮修复和验证后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 16 个 Subagent 都真实创建成功；其中 14 个返回了有效只读审核结果，2 个在等待结果时返回 429，主代理不能把这 2 个当成有效审核结果。本轮结果已消费，并已对已返回或报错的子代理发起关闭。本轮归并结论是：仍存在阻塞项，主要集中在主 roadmap 变更日志缺第十二/十三轮记录、旧 explore 仍可能被当成第一版照做、原型页把后续异常能力放在当前第一眼、`exception` 同时表示状态和动作容易混、items 个别路径仍写得太粗、Excel 手册仍有“预览过期”旧词，以及本轮账本未补。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5cbb-6a73-7ca1-83f2-8cfc36183202` | Fermat | roadmap 变更日志和轮次证据 | 有阻塞 | 主 roadmap 补第十二、十三、十四轮变更日志；本账本补第十四轮真实 agent_id 和结果。 |
| 2 | `019e5cbb-6ac7-72f3-b24a-e6e2a881658e` | Sartre | CodeStable 格式和旧 explore 状态 | 有阻塞 | 两份旧 explore 保持 `status: superseded / confidence: mixed / superseded-by`，顶部继续强调执行以 roadmap/items 为准。 |
| 3 | `019e5cbb-6b25-7562-950b-af1452e12270` | Goodall | 前端布局旧 explore 越界承诺 | 有阻塞 | 继续把“影响清单”改成后续细明细，把暂停/继续/报异常收窄为后续独立条目，避免被当成第一版范围。 |
| 4 | `019e5cbb-6b87-7402-b6f7-07ff442cefd7` | Euler | 原型页当前阶段范围 | 有阻塞 | `docs/aps_frontend_workbench_mockup.html` 当前车间反馈屏只展示开工/完工，不再把后续报异常和复杂现场原因放在第一眼。 |
| 5 | `019e5cbb-6be5-71b0-b5ac-d3a571027219` | Galileo | 原型禁词和离线前端测试 | 有阻塞 | `tests/regression_frontend_offline_static_assets.py` 补锁“后续：报异常 / 后续异常反馈 / 开工暂停完工”等会把后续能力摆到当前原型的旧词。 |
| 6 | `019e5cbb-6c3a-73e3-b3ab-210857d51dda` | Ramanujan | items 颗粒度和路径是否能照做 | 有阻塞 | `candidate-drilldown-empty-states`、执行事件、复盘报表、完整重排等条目补具体文件路径、拟新增文件和导出入口。 |
| 7 | `019e5cbb-6c97-7e71-ab17-87b61099cf3b` | Curie | 用户可见中文大白话 | 有阻塞 | 原型、旧 explore、Excel 手册继续清理不适合用户直接看到的旧词；页面当前阶段只讲开工/完工。 |
| 8 | `019e5cbb-6cef-72f0-ae1e-217483f8bda3` | Kuhn | 异常状态和动作边界 | 429 无有效结果 | 本代理等待结果时报 429，不能计为有效审核；同类问题由其他返回结果和主代理归并处理。 |
| 9 | `019e5cbb-6d48-7eb2-ae53-27aa0cfaf2e4` | Gibbs | `exception` 映射冲突 | 有阻塞 | roadmap 和 items 明确 `current_status/reported_status exception -> 异常中`，`event_type=exception -> action=report_exception -> 报异常`，要求状态中文名和动作中文名分开实现。 |
| 10 | `019e5cbb-6d9e-7f01-8129-3b618b41d079` | Herschel | 延期诊断和物料线索口径 | 429 无有效结果 | 本代理等待结果时报 429，不能计为有效审核；后续第十五轮仍按同范围复审。 |
| 11 | `019e5cbb-6dfa-7832-bf60-0ed4ec2db9cf` | Peirce | 旧 explore 研究证据和执行口径 | 有阻塞 | 保留历史研究证据，但把会误导实施的“第一版直接做”口气改成“历史草案 / 后续按 roadmap 单独做”。 |
| 12 | `019e5cbb-6e55-7232-920d-c0c6a27ba915` | Volta | 执行事件迁移和 repository 文件 | 有阻塞 | items 补 `core/infrastructure/migrations/__init__.py`、`v{next}.py`、`data/repositories/__init__.py`、`operation_execution_event.py`、`operation_execution_state.py` 等具体路径。 |
| 13 | `019e5cbb-6eb1-7793-a93b-f371c3a5c6a1` | Ptolemy | 复盘报表和导出路径 | 有阻塞 | `plan-vs-actual-review` 补 `report_engine.py`、`exporters/xlsx.py`、`templates/reports/index.html`、拟新增 `execution_review.html`、`page_manuals_reports.py`。 |
| 14 | `019e5cbb-6f10-7333-9138-65fc1b56a9d6` | Mendel | 最小重排按钮放开验收 | 有阻塞 | `reschedule-minimum-execution-guardrails` primary_paths 补 `tests/regression_frontend_offline_static_assets.py`，保持按钮放开和直接 POST 同批验收。 |
| 15 | `019e5cbb-6f6a-7b10-b5db-42c774977e2b` | Locke | Excel 手册旧词 | 有阻塞 | `web/viewmodels/page_manuals_excel_demo.py` 把“这就是预览过期”改为“这就是检查结果过期”。 |
| 16 | `019e5cbb-6fc4-73a2-9a5f-64320d21000a` | James | 总体阻塞压力测试 | 有阻塞 | 合并修正 roadmap、items、旧 explore、原型、测试和本账本；修复后必须继续第十五轮同范围 16 个 Subagent 复审。 |

第十四轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：补第十二、十三、十四轮变更日志；把用户可见文案映射拆成计划身份/现场状态、现场事件动作、异常原因、严重程度等几类；明确 `exception` 的状态中文名和动作中文名必须分开。
- `aps-three-gap-directions-items.yaml`：补执行事件迁移、repository、模型、复盘报表、导出工作簿、完整重排和最小重排测试的具体路径；在执行事件和异常反馈条目里写明不能复用同一个 `exception` 映射函数。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`、`.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`：继续清理会被误当第一版范围的旧口径，把“影响清单 / 物料未齐 / 异常上报”等说法改成更保守的后续明细、物料线索待核对或异常反馈口径，并保留顶部 superseded 提示。
- `docs/aps_frontend_workbench_mockup.html`、`tests/regression_frontend_offline_static_assets.py`：原型页当前车间反馈屏只展示开工/完工；测试新增禁词防止后续报异常、复杂现场动作又出现在当前原型第一眼。
- `web/viewmodels/page_manuals_excel_demo.py`：Excel 手册旧词改为“检查结果过期”。

第十四轮存在阻塞且已修复，但本轮有 2 个子代理等待结果时报 429，所以不能把第十四轮当作“全部有效通过”。后续必须继续启动第十五轮同范围 16 个 Subagent 复审；第十五轮范围不能缩小，也不能只盯着第十四轮刚修的问题。

## 第十五轮对抗性审核

2026-05-25 第十四轮修复和验证后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 16 个 Subagent 都真实创建成功；其中 7 个返回有效只读审核结果，9 个返回 `stream disconnected before completion: stream closed before response.completed`，主代理不能把这 9 个当成有效审核结果。本轮有效结果归并结论是：仍存在阻塞项，主要集中在原型页复盘入口提前出现、旧 explore 仍残留异常第一阶段暗示、复盘导出文件名和工作表名不够固定、最小重排条目前端离线/Chrome109 约束漏项、失败 JSON 缺 `action_label` 硬契约、原型页用户可见英文时间单位、通用 Excel 错误提示仍露“检查基线”。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5cef-7af2-7e63-87da-71ed6b0344b5` | Ampere | CodeStable 格式、账本和原型大白话 | 有阻塞 | 原型页 `46.5h / 1h20m` 等英文时间单位改为“小时 / 分钟”，并在前端原型测试中加入时间缩写扫描。 |
| 2 | `019e5cef-7c9e-7450-a6fc-a9405593ea60` | Meitner | 旧 explore 状态 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 3 | `019e5cef-7cf3-7e03-8c90-7ec79b8a7e75` | Russell | 原型页当前阶段范围 | 有阻塞 | 原型报表中心移除当前阶段“计划和现场实际 / 查看偏差”入口，改为当前可用的报表说明；禁词测试补“计划和现场实际 / 查看偏差 / 后续复盘视图”。 |
| 4 | `019e5cef-7d55-7d01-9b50-0f102edd3b8a` | Raman | `exception` 双重含义 | OK | 无阻塞；确认状态中文名和动作中文名已拆开。 |
| 5 | `019e5cef-7dbb-7e12-bbb9-5c84df986541` | Averroes | items 颗粒度 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 6 | `019e5cef-7e1f-7561-aa52-617f6298a0bd` | Boole | 执行事件和失败 JSON | 有阻塞 | roadmap 和 items 补失败 JSON 的 `details.action / details.action_label`，要求页面只能显示“开工 / 完工 / 报异常”等中文动作名。 |
| 7 | `019e5cef-7e80-7f23-a5f8-7a07dd550bbe` | Hubble | 用户可见文案 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 8 | `019e5cef-7ee1-7892-93d7-05e51ae1654d` | Hegel | 延期诊断和物料线索 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 9 | `019e5cef-7f37-7562-9b15-abb43a17a16e` | Dirac | 最小重排护栏 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 10 | `019e5cef-7f97-7602-96f1-500ce2d3bfb6` | Banach | 复盘报表和旧 explore | 有阻塞 | 旧 explore “第一版按钮：开工、完工、异常”改成历史草案且异常入口不属于当前第一阶段；前端布局 explore “完工/异常弹窗”改为完工弹窗和后续异常弹窗；复盘导出固定中文文件名和工作表名。 |
| 11 | `019e5cef-7ff7-7221-b6e9-d4c990f9656f` | Ohm | Win7 / Python 3.8 / Chrome109 / 离线 | 有阻塞 | `reschedule-minimum-execution-guardrails` 补“新前端资源不走 CDN、外链字体、外链脚本、外链样式，不引入新前端框架或 Chrome 109 不支持能力”。 |
| 12 | `019e5cef-8063-7eb1-89ab-768650510c4e` | Noether | 账本和 Subagent 闭环 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 13 | `019e5cef-80c4-7010-829e-1aaceb000232` | Dalton | DAG 和整体颗粒度 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 14 | `019e5cef-8123-78b0-a22e-72e4016bdc3c` | Darwin | 方案对比边界 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 15 | `019e5cef-817f-7701-a311-8f085cb796cc` | Erdos | Excel 手册和通用错误 | 有阻塞 | `web/routes/excel_utils.py` 通用确认错误从“缺少检查基线”改为“检查结果已失效”，并补 `load_confirm_payload` 测试锁住用户可见文案。 |
| 16 | `019e5cef-81dc-7e12-b241-d003e0eaeeec` | Plato | 总体压力测试 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |

第十五轮修复采纳后，主代理已继续修改：

- `docs/aps_frontend_workbench_mockup.html`、`tests/regression_frontend_offline_static_assets.py`：原型移除当前阶段复盘入口，时间单位改为中文，测试补复盘入口和英文时间缩写禁词。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`、`.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`：旧 explore 继续收窄第一阶段异常暗示，保留为历史素材但不再可直接照做。
- `aps-three-gap-directions-roadmap.md`、`aps-three-gap-directions-items.yaml`：失败 JSON 补 `action_label`，复盘导出文件名和工作表名固定为中文格式，最小重排条目补 Chrome 109 / 离线前端硬约束。
- `web/routes/excel_utils.py`、`tests/test_excel_utils_compare_digest_guard.py`：通用 Excel 确认写入错误提示改为“检查结果已失效”，并加测试防止“检查基线”回到用户可见错误里。

第十五轮存在阻塞且已修复；同时本轮有 9 个子代理工具流中断，所以不能把第十五轮当作有效通过。后续必须继续启动第十六轮同范围 16 个 Subagent 复审；第十六轮范围不能缩小，也不能只盯着第十五轮刚修的问题。

## 第十六轮对抗性审核

2026-05-25 第十五轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 16 个 Subagent 都真实创建成功；其中 11 个返回有效只读审核结果，4 个返回 `stream disconnected before completion: stream closed before response.completed`，1 个返回 `429 Too Many Requests`。主代理不能把这 5 个无有效结果当成有效审核结果。本轮有效结果归并结论是：仍存在阻塞项，主要集中在主 roadmap 变更日志漏第十五轮、原型页当前阶段仍有“分析复盘 / 风险复盘入口”、旧前端 explore 仍把异常原因塞进开工/完工第一阶段、排产分析优化过程表格直接展示内部评分串、docs-quality 的质量门禁命令使用 `--allow-dirty-worktree` 导致成功也返回特殊码。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5d0a-0ecd-7eb1-ae5a-7080d9666113` | Chandrasekhar | 账本和主 roadmap 变更日志 | 有阻塞 | 主 roadmap 变更日志补第十五轮和第十六轮修复记录。 |
| 2 | `019e5d0a-0f26-7e91-96c0-204b945a2f5f` | Nietzsche | 旧 explore 作废和第一版边界 | OK | 无阻塞；确认旧 explore 顶部已标废且第一版按钮边界大体正确。 |
| 3 | `019e5d0a-0f84-76c2-9bb5-fe972bf66ee0` | Singer | 用户可见文案 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 4 | `019e5d0a-1002-7050-a853-ed92e1dd85ff` | Jason | `exception` 状态和动作映射 | OK | 无阻塞；确认“异常中”和“报异常”映射已分开。 |
| 5 | `019e5d0a-105b-7e33-9fb2-1cb8c825104a` | Bernoulli | 依赖图和颗粒度 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 6 | `019e5d0a-10b6-7030-9517-4e8a39024738` | Aristotle | 路线图整体一致性 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 7 | `019e5d0a-1119-7061-950c-e0b336cb1e68` | Parfit | 用户可见内部评分串 | 有阻塞 | 排产分析优化过程表去掉直接展示 `r.score` 的列，并加测试防止内部评分串回到普通页面。 |
| 8 | `019e5d0a-1178-7192-a2fe-4c858a35cb16` | Pasteur | 执行事件和错误提示 | 工具流中断 | `stream disconnected before completion`，无有效审核结果；已发起关闭。 |
| 9 | `019e5d0a-11d7-7e23-bbb6-499ffc45c86c` | Leibniz | 旧前端 explore 的异常反馈边界 | 有阻塞 | 旧前端 explore 移除开工/完工第一阶段里的“异常原因”字段暗示，改成后续异常反馈条目再做。 |
| 10 | `019e5d0a-123a-77d0-af65-f0ee6149ce5e` | Hooke | 原型当前阶段复盘入口 | 有阻塞 | 原型页把“分析复盘 / 风险复盘入口”改成“查看排产结果 / 风险查看入口”，并补禁词测试。 |
| 11 | `019e5d0a-12a6-7d23-930a-a053324e151c` | Harvey | docs-quality 验收命令和变更日志 | 有阻塞 | docs-quality 的质量门禁测试命令改为 `--require-clean-worktree --long-gate-cache`，保留 dirty 模式只能当本地反馈的说明。 |
| 12 | `019e5d0a-130c-7ad1-bf81-28c6be303c87` | Wegener | 账本和主 roadmap 一致性 | 有阻塞 | 主 roadmap 变更日志补第十五轮记录，避免账本和主文档断链。 |
| 13 | `019e5d0a-1380-72c0-92dc-d425b82842dc` | Kierkegaard | DAG、最小闭环和顺序 | OK | 无阻塞；确认 14 条 item、唯一最小闭环和依赖顺序可照做。 |
| 14 | `019e5d0a-13da-7fa1-917a-d40cee405e54` | Carver | 方案对比边界和旧 explore | OK | 无阻塞；确认第一版不承诺批次/资源细明细。 |
| 15 | `019e5d0a-1436-7d31-b59f-26e200b05857` | Bohr | 总体复审 | 429 无有效结果 | 等待结果时报 `429 Too Many Requests`，不能计为有效审核；已发起关闭。 |
| 16 | `019e5d0a-1491-7b50-8e2c-a9d485bcd541` | Hume | 变更日志和整体可执行性 | 有阻塞 | 主 roadmap 变更日志补第十五轮记录，确认 items 颗粒度整体够细。 |

第十六轮修复采纳后，主代理已继续修改：

- `docs/aps_frontend_workbench_mockup.html`、`tests/regression_frontend_offline_static_assets.py`：原型页当前阶段不再展示“分析复盘 / 风险复盘入口”，测试补禁词防回退。
- `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md`：旧前端 explore 中开工/完工第一阶段不再包含异常原因字段，异常和暂停原因统一标为后续 `shop-exception-feedback` 条目。
- `templates/scheduler/analysis_parts/_optimization_process.html`、`tests/regression_frontend_ui_language_polish.py`、`tests/regression_scheduler_analysis_observability.py`：普通用户页面不再直接展示内部评分串。
- `aps-three-gap-directions-items.yaml`：docs-quality 收口命令改为 clean proof 质量门禁，避免把 dirty feedback 当正式通过。
- `aps-three-gap-directions-roadmap.md`、本账本：补第十五轮和第十六轮变更记录。

第十六轮存在阻塞且已修复；同时本轮有 5 个子代理无有效结果，所以不能把第十六轮当作有效通过。后续需要继续同范围复审，范围不能缩小，也不能只盯着第十六轮刚修的问题。2026-05-25 后用户更新口径：后续不再要求固定 16 个 Subagent，按合适颗粒度覆盖风险面即可。

## 第十七轮对抗性审核

2026-05-25 第十六轮修复后，主代理一开始仍按旧口径尝试启动第十七轮 16 个 Subagent；这属于调度口径滞后。随后用户明确更新要求：不用固定 16 个，按合适颗粒度分 Subagent。第十七轮仍按同范围审核，不缩小范围：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮有效结果里，至少两个子代理指出同一个阻塞：原 explore 文件里仍有旧车间反馈草案会误导实现，把“暂停、继续、报异常、异常原因”提前塞进开工/完工第一阶段。部分子代理因 429、stream disconnected 或后续关闭无有效结果，不能计为有效通过。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5d2b-64ac-7883-b40d-adf66100f821` | Poincare | 原 explore 和 roadmap/items 的车间反馈边界一致性 | 有阻塞 | 旧 explore 的任务卡、按钮表、完工弹窗、验收和测试建议收窄到当前第一阶段只做开工/完工；暂停、继续、报异常、异常原因统一放到后续 `shop-exception-feedback`。 |
| 2 | `019e5d2b-64f5-7f10-99bd-539b7649e342` | Socrates | 整体可执行性和是否会被旧草案误导 | 有阻塞 | 同上；把旧按钮表和旧验收项改成当前阶段可照做口径，并加明示“历史草案，不能照做”。 |
| 3 | `019e5d2b-6620-7033-8582-b22a2919dd60` | Lorentz | Python 3.8 / Win7 / 离线和整体压力测试 | OK，有观察项 | 未判阻塞；观察到 `tools/quality_gate_shared.py` 有 `tuple[...]`，但当前固定扫描范围和已验证导入未证明会卡住本路线图。后续 docs-quality 可继续扩大 Python 3.8 扫描。 |
| 4 | `019e5d2b-655c-79b1-9eee-ea10cf0c398f` | Lagrange | 只读审核 | 429 无有效结果 | 不能计为有效审核；已关闭。 |
| 5 | `019e5d2b-643a-7743-8f87-1777fd22d4bd` | Bacon | 只读审核 | 429 无有效结果 | 不能计为有效审核；已关闭。 |
| 6 | `019e5d2b-6398-71c3-9976-8697535bbd1a` | Mencius | 只读审核 | 工具流中断 | `stream disconnected`，不能计为有效审核；已关闭。 |

第十七轮修复采纳后，主代理已继续修改：

- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：任务卡不再包含“异常或暂停原因”；按钮表只保留开工、完工、查看记录；完工弹窗移除“异常原因”；暂停、继续生产、报异常和异常测试全部标为后续 `shop-exception-feedback`；资源派工页面改动也不再把异常列和报异常按钮放进当前阶段。
- `aps-three-gap-directions-roadmap.md`：补第十七轮变更日志，说明旧 explore 已继续收窄，后续复审按用户新口径不再固定 16 个 Subagent。

第十七轮存在阻塞且已修复。后续继续同范围复审，但按用户最新口径使用合适颗粒度的小组 Subagent，不再硬性固定 16 个。

## 第十八轮对抗性审核

2026-05-25 第十七轮修复和本地验证后，主代理按用户最新口径启动 5 个真实 Subagent，不再固定 16 个。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 5 个 Subagent 都真实创建成功，均已返回并关闭。本轮归并结论是：仍存在阻塞项，主要集中在旧 explore 前部“第一版异常原因”残留、反馈人占位旧口径、撤销/误点处理前置关系不清、开工/完工字段校验不够细、用户帮助和手册里的英文单位/英文选项，以及质量门禁 helper 的 Python 3.8 注解风险。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5d3d-9389-77c0-b03a-1df71bd11112` | Carson | 旧 explore 残留和跨文档一致性 | 有阻塞 | 旧 explore 前部外部调研摘要改为当前第一阶段只做任务卡、开工、完工和备注；异常原因放到后续 `shop-exception-feedback`。 |
| 2 | `019e5d3d-d2e8-7df0-9b83-22b006843410` | Franklin | 用户可见中文大白话 | 有阻塞 | 页面帮助和手册里的 `Day / Week / Month`、`(h)`、`2h / 5h / 10h`、工时表头等改成中文大白话；同步清理工艺相关用户说明里的英文单位。 |
| 3 | `019e5d3e-119a-7393-9403-1693c0528ea2` | Turing | items 颗粒度、DAG 和测试命令 | OK | 无阻塞；确认 14 条 item 粒度、依赖和最小闭环可照做。 |
| 4 | `019e5d3e-5296-7d43-95fe-346d36254c6e` | Euclid | Win7、Python 3.8、离线和质量门禁 | 有阻塞 | `tools/quality_gate_shared.py` 的 `tuple[...]` 改为 `Tuple[...]`；docs-quality 扫描清单纳入 `scripts/run_quality_gate.py` 和 `tools/quality_gate_shared.py`。 |
| 5 | `019e5d3e-8cf6-70c2-a1a5-09fc4192946d` | Confucius | 总体压力测试 | 有阻塞 | 清理反馈人占位旧口径；明确不做完整撤销事件但按钮放开前必须有确认提示、状态版本校验、事件审计和计划员人工处理说明；补开工/完工字段中文名、必填、非法值、数量范围和错误返回规则。 |

第十八轮修复采纳后，主代理已继续修改：

- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：前部外部调研摘要、反馈人、撤错/撤销口径继续收窄，避免把异常原因、假用户或完整撤销误读成当前阶段前置工作。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md`：补开工/完工字段校验表，明确 `operator_id / machine_id / quantity_done / quantity_scrapped / remark` 的中文名、必填规则、非法值处理和错误码；修正撤销观察项。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml`：补开工/完工字段退出检查、误点处理边界，docs-quality 将质量门禁入口和 helper 纳入 Python 3.8 扫描。
- `web/viewmodels/page_manuals_scheduler_outputs.py`、`web/viewmodels/page_manuals_process.py`、`web/viewmodels/page_manuals_process_excel.py`、`web/viewmodels/page_manuals_equipment.py`、`web/viewmodels/page_manuals_scheduler.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`：用户可见说明里的英文单位和英文选项改成中文大白话。
- `tools/quality_gate_shared.py`：Python 3.8 不兼容的 `tuple[...]` 注解改为 `Tuple[...]`。

本轮修复后已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md --require doc_type --require roadmap --require created --require source

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit scripts/run_quality_gate.py tools/quality_gate_shared.py tests/regression_frontend_offline_static_assets.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py web/viewmodels/page_manuals_scheduler_outputs.py web/viewmodels/page_manuals_process.py web/viewmodels/page_manuals_process_excel.py web/viewmodels/page_manuals_equipment.py web/viewmodels/page_manuals_scheduler.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_frontend_ui_language_polish.py tests/regression_frontend_offline_static_assets.py tests/test_codestable_tools_contract.py tests/test_scan_py38plus_syntax.py
```

第十八轮存在阻塞且已修复。后续继续按同范围复审，但仍按用户最新口径使用合适颗粒度的小组 Subagent。

## 第十九轮对抗性审核

2026-05-25 第十八轮修复后，主代理继续按用户最新口径启动 5 个真实 Subagent，同范围复审，不固定 16 个。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 检查颗粒度是否足够细，是否能直接照着做

本轮 5 个 Subagent 都真实创建成功，均已返回并关闭。归并结论：4 个方向 OK，1 个方向发现用户可见页面帮助仍有英文短语 `step-by-step`，属于阻塞，因为用户明确要求前端和手册尽量用中文大白话。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5d54-36f0-7fc3-bc9f-96739b6c0d9d` | Godel | 旧 explore 和 roadmap/items 一致性 | OK | 无阻塞；确认异常反馈、反馈人、撤销边界已对齐。 |
| 2 | `019e5d54-79ac-77c2-a784-5c1d792e8647` | Linnaeus | 用户可见中文大白话 | 有阻塞 | `web/viewmodels/page_manuals_equipment.py` 里的 5 处 `step-by-step` 标题改成中文；`tests/regression_page_manual_registry.py` 加禁词，防止页面帮助再出现该英文短语。 |
| 3 | `019e5d54-b9d8-7100-ba60-16077eed4eb3` | Descartes | Win7、Python 3.8、离线和质量门禁 | OK | 无阻塞；确认 Python 3.8 扫描、离线资源约束和 clean proof 口径通过。 |
| 4 | `019e5d54-fa78-7352-94ff-1ede0a982ab0` | Boyle | items 颗粒度、DAG 和接口契约 | OK | 无阻塞；确认 14 条 item、DAG、开工/完工字段和 docs-quality 边界可照做。 |
| 5 | `019e5d55-4be7-7ec3-aec3-7534ba0ab7be` | Lovelace | 总体压力测试 | OK | 无阻塞；确认主路线图、items、账本和旧 explore 核心口径已对齐。 |

第十九轮修复采纳后，主代理已继续修改：

- `web/viewmodels/page_manuals_equipment.py`：将“新增设备（step-by-step）”“批量操作（step-by-step）”“单机新增停机（step-by-step）”“添加人员关联（step-by-step）”“创建批量停机（step-by-step）”改成中文标题。
- `tests/regression_page_manual_registry.py`：页面帮助禁词增加 `step-by-step`，避免用户可见帮助文案回退。

本轮修复后已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_page_manual_registry.py tests/regression_config_manual_markdown.py tests/regression_frontend_ui_language_polish.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/page_manuals_equipment.py tests/regression_page_manual_registry.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md --require doc_type --require roadmap --require created --require source

git diff --check
```

第十九轮存在阻塞且已修复。后续继续同范围复审，但按用户最新口径只启动必要的小组 Subagent。

## 第二十轮最终复审

2026-05-25 第十九轮修复和验证后，主代理按用户最新口径启动 2 个真实 Subagent 做同范围最终复审。范围仍覆盖：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 用户可见页面、导出、手册、公开 JSON、原型和 Python 3.8 / Win7 离线约束
- 颗粒度和后续是否能直接照着做

本轮 2 个 Subagent 都真实创建成功，均已返回并关闭。归并结论：无阻塞项。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5d60-31bd-73e2-8084-c043a0731fbc` | Huygens | 用户可见中文大白话最终复审 | OK | 确认用户可见帮助、手册、原型中没有 `step-by-step`，也未发现 `Day/Week/Month`、`(h)`、`scenario_id`、`latest`、`trace_meta`、`source_table`、`event_type`、`score tuple` 等明显残留；`step-by-step` 只保留在测试禁词和开发记录里。 |
| 2 | `019e5d60-72c4-7c81-a677-a7e77c711f28` | Aquinas | 总体压力测试 | OK | 确认 roadmap、items、账本、旧 explore 之间没有阻塞级矛盾，关键接口、字段、错误码、依赖和测试命令已经写到可继续 feature-design 的程度。 |

本轮复审前后主代理已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md --require doc_type --require roadmap --require created --require source

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit scripts/run_quality_gate.py tools/quality_gate_shared.py tests/regression_frontend_offline_static_assets.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py web/viewmodels/page_manuals_scheduler_outputs.py web/viewmodels/page_manuals_process.py web/viewmodels/page_manuals_process_excel.py web/viewmodels/page_manuals_equipment.py web/viewmodels/page_manuals_scheduler.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_page_manual_registry.py tests/regression_config_manual_markdown.py tests/regression_frontend_ui_language_polish.py tests/regression_frontend_offline_static_assets.py tests/test_codestable_tools_contract.py tests/test_scan_py38plus_syntax.py tests/regression_scheduler_analysis_observability.py tests/test_excel_utils_compare_digest_guard.py

git diff --check
```

第二十轮最终复审无阻塞项。本轮结束后没有保留开放子代理。

## 第八轮修复记录

2026-05-25 第七轮复审后，主代理继续按同范围处理阻塞项。本段只记录第八轮修复采纳结果；历史轮次顺序因多次追加存在乱序，后续读取时以每段标题和日期为准，不按文件中的物理顺序推断先后。

本轮修复重点：

- `docs/aps_frontend_workbench_mockup.html`：把用户第一眼能看到的旧词改成中文大白话；不再展示“异常解释”“评分”“业务主方案”“基线方案”“最终推荐”等容易让普通用户误解的词。
- `tests/regression_frontend_offline_static_assets.py`：新增用户可见原型文案红线，后续如果旧词重新出现在原型页，测试会直接失败。
- `aps-three-gap-directions-roadmap.md`：补清 `source_table=schedule` 不能决定用户身份、`ExecutionFeedbackContext.requested_plan_role`、执行事件只保存 `previous_state_revision`、幂等和并发冲突、异常字段展示、POST 成功/失败结构、重排执行事实、`simulate=True` 不落库等口径。
- `aps-three-gap-directions-items.yaml`：同步补细执行事件、派工、异常反馈、复盘导出、重排护栏、未来测试命令说明和各条 feature 的验收点。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：在旧蓝图附近补“历史草案，已作废，不能照做”提示，避免后续实现误读旧方案。
- `web/viewmodels/page_manuals_scheduler_outputs.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`：补回“输入 `abc` 这类不是数字的版本号”这种用户能看懂的例子。
- `templates/system/logs.html`：把“日志内部号”改为“排查用的记录号”。
- `web/viewmodels/page_manuals_scheduler.py`、`web/viewmodels/page_manuals_scheduler_admin.py`：把用户帮助文案里的“基线方案”改成“当前按哪个配置来算 / 配置来源 / 当前配置状态”。

第八轮修复后已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_schedule_result_view_context.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_frontend_offline_static_assets.py

git diff --check
```

第八轮修复完成后，需要继续启动第九轮同范围 16 个 Subagent 复审，检查范围仍然不能缩小。

## 第九轮对抗性审核

2026-05-25 第八轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，没有分批。统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 检查颗粒度是否足够细，是否能直接照着做
- 检查用户可见文案是否为中文大白话，不能把内部字段名、英文参数、内部编号直接展示给用户
- 检查前端页面、导出文件、手册和原型页面是否还会把程序员看的词露给普通用户

本轮 16 个 Subagent 已全部成功启动、返回并关闭。由于当前会话在上下文压缩后没有完整保留第九轮逐个 `agent_id` 表，本账本不补编单个 agent id；只记录本轮归并结论、采纳修复和验证要求。第八轮原始 agent 明细也没有在当前上下文完整留存，只能记录第八轮修复采纳和验证；第九轮已把这个证据缺口本身列为需要修正的账本问题。

本轮归并结论是：仍存在阻塞项，主要集中在执行状态字段边界、子任务依赖理由、重排条目边界、导出真实路径、离线原型验收、用户可见旧词和资源派工公开数据泄露风险。

本轮确认的阻塞项：

- `OperationExecutionState` 的“最后一条事件”和“最近一次异常”字段没有彻底分清。完工后仍要保留最近异常信息，不能把暂停原因或完工备注塞进异常字段。
- `items.yaml` 每条 `depends_on` 缺少理由，后续实现者只能猜为什么要按这个顺序做。
- `reschedule-minimum-execution-guardrails` 和 `reschedule-respects-execution-facts` 边界仍有重叠。前者应只做开工/完工的最小安全补洞；后者才处理暂停、异常和完整执行事实。
- `aps-three-gap-docs-quality-gate` 虽然测试命令包含 `tests/test_codestable_tools_contract.py`，但退出条件没有明确必须跑。
- 本账本第八轮原始 Subagent 明细不完整，不能伪造 agent id，需要明确记录这个证据缺口。
- 执行事件幂等和并发优先级还需要更硬：同一个 `idempotency_key` 重复提交时，必须先查幂等键，不能先报状态版本过期。
- `candidate-drilldown-empty-states` 漏掉资源负荷、停机影响导出的真实路由和生成路径，导出文件名仍可能露内部字段。
- 离线静态资源验收没有明确扫描 `docs/aps_frontend_workbench_mockup.html`，原型页面可能重新引入外链或旧词。
- 用户可见页面、手册、原型里仍有“评分”“最终采用”“原算法最好”等旧词风险，应统一改成中文大白话。
- 原型里的“恢复”“一键开工”等文案容易让用户误解，后续必须按真实能力和上线顺序收敛。
- 资源派工公开 data、导出列名和导出文件名仍有泄露 `schedule_id / op_id / source_table / candidate_id / scenario_id` 等内部字段的风险。
- 计划身份状态里旧 `selected` 口径和 roadmap 的 `resolved_adopted / resolved_comparison` 冲突，必须统一。

第九轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：把执行状态读模型中的 `last_event_*` 和 `latest_exception_*` 拆开；明确幂等键必须先于状态版本冲突判断；补第九轮变更日志。
- `aps-three-gap-directions-items.yaml`：每条 item 补 `depends_on_reasons`；`candidate-drilldown-empty-states` 纳入 `web/routes/reports.py` 和 `core/services/report/report_engine.py`；资源负荷/停机影响导出文件名要求不露内部字段；`operation-execution-event-foundation` 补幂等优先级和 last/latest 异常字段分离；两个重排条目补清最小护栏和完整接入边界；docs-quality 收尾明确必须运行 `tests/test_codestable_tools_contract.py`，并把原型 HTML 纳入离线资源验收。
- 代码和用户文案侧已清理多处旧词、内部字段泄露和模拟预览兜底显示；这些真实代码改动不在本账本逐行展开，最终以 git diff 和测试结果为准。

第九轮修复后需要执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_schedule_result_view_context.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/regression_scenario_preview_secondary_outputs.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_frontend_offline_static_assets.py tests/test_codestable_tools_contract.py
git diff --check
```

第九轮存在阻塞且已修复，后续必须继续启动第十轮同范围 16 个 Subagent 复审；第十轮范围不能缩小，也不能只盯着第九轮刚修的问题。

## 第六轮对抗性审核

2026-05-25 第五轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 用户可见文案是否为中文大白话，不能把内部字段名、英文参数、内部编号直接展示给用户

本轮 16 个 Subagent 全部只读审核，均已完成并关闭。本轮归并结论是：仍存在阻塞项，主要集中在旧 explore 个别小节仍像可照做草案、延期诊断缺物料/齐套事实源、最小重排护栏完成前普通 POST 写入开工/完工的后端拒绝口径、模拟预览导出泄露内部编号、Excel 表头和说明书仍保留旧内部词。

本轮修复采纳后，主代理已继续修改：

- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：在 `3.2 第一版业务流程`、`3.13 路由建议`、`3.17 第一版验收标准` 标题下补“历史草案，已作废，不能照做”的醒目标注，明确实施必须看 roadmap/items。
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md` 和 items.yaml：补延期诊断第一版只能读取 `Batches.ready_status / ready_date` 与 `BatchMaterials` 明细，缺数据输出“数据不足/建议复核”，不能编造缺料原因；补最小重排护栏完成前普通用户直接 POST 开工/完工也必须服务端拒绝，默认 `6003 / 409`。
- `templates/scheduler/week_plan.html`、`templates/scheduler/resource_dispatch.html`、`templates/reports/*.html`、`web/routes/domains/scheduler/scheduler_week_plan.py`、`core/services/scheduler/week_plan_excel.py`、`web/viewmodels/scheduler_resource_dispatch.py`、`core/services/scheduler/resource_dispatch_excel.py`：模拟预览页面、导出文件名和 Excel 摘要不再给用户展示内部 `scenario_id`；无名称时统一显示“模拟预览（未命名）”。
- `core/services/common/excel_template_defaults.py`、工种/供应商导入导出服务、相关模板和测试：工种/供应商面向用户的表头统一为“工种编号 / 供应商编号”，保留旧表头兼容读取。
- `web/viewmodels/page_manuals_common.py`、`web/viewmodels/page_manuals_scheduler_week_plan.py`、`web/viewmodels/page_manuals_reports.py`、`static/docs/scheduler_manual.md`、`web_new_test/static/docs/scheduler_manual.md`：继续清理用户说明里的 `latest`、`工种ID/供应商ID`、`part_name`、`capacity_hours`、技能等级英文值、备份用途英文值、旧版起止日期字段和“模拟方案编号”等内部词，改成中文大白话。
- `tests/regression_scenario_preview_secondary_outputs.py`、`tests/regression_unit_excel_template_headers.py`、`tests/regression_page_manual_registry.py`：同步新口径，明确文件名/Excel 摘要不得包含内部方案编号，表头必须是“工种编号 / 供应商编号”，页面说明不得回退到旧内部词。

第六轮修复后已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/drafts/subagent-reference-chain-ledger.md
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile core/services/scheduler/resource_dispatch_excel.py core/services/scheduler/schedule_plan_query_service.py core/services/scheduler/week_plan_excel.py web/routes/domains/scheduler/scheduler_week_plan.py web/viewmodels/scheduler_resource_dispatch.py core/services/common/excel_template_defaults.py core/services/process/op_type_service.py core/services/process/supplier_service.py core/services/process/unit_excel/route_sheet_builder.py core/services/process/op_type_excel_import_service.py core/services/process/supplier_excel_import_service.py web/routes/process_excel_op_types.py web/routes/process_excel_suppliers.py web/viewmodels/page_manuals_common.py web/viewmodels/page_manuals_scheduler_week_plan.py web/viewmodels/page_manuals_reports.py web/viewmodels/page_manuals_process_excel.py web/viewmodels/page_manuals_scheduler_outputs.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_offline_static_assets.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_week_plan_filename_uses_normalized_version.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_unit_excel_template_headers.py tests/regression_page_manual_registry.py tests/test_codestable_tools_contract.py
git diff --check
```

校验结果：三份 CodeStable 文档校验通过；相关 Python 文件编译通过；目标回归测试 37 个全部通过；`git diff --check` 通过。第六轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。因本轮存在阻塞并已修复，后续必须继续启动第七轮同范围 16 个 Subagent 复审。

## 第七轮对抗性审核

2026-05-25 第六轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据
- 检查颗粒度是否足够细，是否能直接照着做
- 检查用户可见文案是否为中文大白话，不能把内部字段名、英文参数、内部编号直接展示给用户

本轮 16 个 Subagent 全部只读审核，均已完成并关闭。本轮归并结论是：仍存在阻塞项，主要集中在 items 缺每条独立入口和测试命令、延期诊断证据缺口不能硬填内部表名、导出表头还用了“诊断规则版本 / 输入指纹”这类用户看不懂的词、现场反馈接口返回结构不够硬、异常字段枚举缺固定表，以及少量页面/说明/测试仍残留旧内部词或 Python 3.8 不兼容写法。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5baf-8a25-7522-b239-17824cd4f672` | Parfit the 2nd | 整体颗粒度和路线图可执行性 | OK | 无阻塞；确认拆分方向基本可跟做。 |
| 2 | `019e5baf-8abd-7400-9ce1-f00974fc1491` | Russell the 2nd | items 入口、测试命令和实现闭环 | 有阻塞 | 14 条 item 全部补 `entrypoints` 和 `test_commands`。 |
| 3 | `019e5baf-8b23-7e71-beb4-daea082306b8` | Kant the 2nd | 现场反馈接口和计划身份 | 有阻塞 | 补 `execution/data` 固定返回结构、POST `requested_plan_role`、成功/失败 JSON 和 details reason。 |
| 4 | `019e5baf-8bb2-7e33-9b7c-148a273fcbe2` | Planck the 2nd | 计划身份和派工写入边界 | OK | 无阻塞；严格 can_write_feedback 口径保留。 |
| 5 | `019e5baf-8c15-7db2-8bd0-b2620c3d7008` | Beauvoir the 2nd | 用户可见中文大白话 | OK | 无阻塞；继续保持页面和导出不露内部字段。 |
| 6 | `019e5baf-8c83-7803-a2b2-ed5c0583f847` | Mill the 2nd | 延期诊断导出和追溯字段 | 有阻塞 | 导出用户表头改为“本次诊断编号 / 生成依据摘要 / 核对信息 / 证据来源 / 证据缺口”等大白话，不再把“诊断规则版本 / 输入指纹”作为用户表头。 |
| 7 | `019e5baf-8d18-7123-8341-507dd3ce000b` | Helmholtz the 2nd | EvidenceLink 证据协议 | 有阻塞 | `source_table` 改为行级证据必填，聚合和缺数据证据可空；缺数据证据必须写清缺什么、查过哪里、影响谁和检查时间，不能填假表名。 |
| 8 | `019e5baf-8d74-7870-b432-f9cfc6aee094` | Wegener the 2nd | 异常反馈字段和状态流转 | 有阻塞 | 补 reason_code、severity、handling_status、suggest_reschedule 的程序值、中文显示和校验规则固定表。 |
| 9 | `019e5baf-8dc9-7f91-919a-92ec8085d6fe` | Locke the 2nd | 前端 mock 和未开工异常入口 | 有阻塞 | `docs/aps_frontend_workbench_mockup.html` 移除未开工任务上的“报异常”示例按钮。 |
| 10 | `019e5baf-8e37-73f2-9b88-b1e11232134a` | Noether the 2nd | schema、迁移和 Python 3.8 | OK | 无阻塞；后续又额外修正 `tests/test_codestable_tools_contract.py` 的 `dict | None`。 |
| 11 | `019e5baf-8ea8-7c72-b750-a1a7d3fed821` | Peirce the 2nd | 依赖图和最小闭环 | OK | 无阻塞；唯一最小闭环保留为超期清单延期解释入口。 |
| 12 | `019e5baf-8f0f-7920-bb47-becb4dcdf076` | Carson the 2nd | 模拟预览名称和二级页面导出 | 有阻塞 | 资源排班、甘特、周计划、资源负荷、停机影响和导出统一使用“模拟预览（未命名）”，不显示内部方案编号。 |
| 13 | `019e5baf-8f6c-76d0-b9a8-fbbbb3038a91` | Sagan the 2nd | 用户说明和 Excel 表头 | 有阻塞 | 手册和蓝图继续清理 `manual / before_restore`、工种/供应商旧内部词；测试同步“供应商编号”。 |
| 14 | `019e5baf-902f-7021-adce-72ffd87cedf0` | Hubble the 2nd | 原 explore 作废状态 | OK | 无阻塞；作废提示继续保留。 |
| 15 | `019e5baf-9081-7e21-9a1d-482ba2544ab5` | Lorentz the 2nd | Win7、离线和前端资源 | OK | 无阻塞；离线静态资源测试继续保留。 |
| 16 | `019e5baf-90f4-7e10-9430-576679406da7` | McClintock the 2nd | 文档收口和质量门禁 | OK | 无阻塞；docs-quality-gate 继续包含 CodeStable 工具契约测试。 |

第七轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：`EvidenceLink.source_table` 改为可空并补行级/聚合/缺数据证据规则；延期诊断导出表头改成大白话；补异常反馈字段固定表；写死 `execution/data`、现场反馈 POST 成功和失败 JSON 形状，以及 `details.reason` 固定含义。
- `aps-three-gap-directions-items.yaml`：14 条 item 全部补 `entrypoints` 和 `test_commands`；同步证据缺口、导出表头、现场反馈接口、异常字段表等退出检查。
- `templates/scheduler/resource_dispatch.html`、`templates/scheduler/gantt.html`、`core/services/scheduler/schedule_result_view_context.py`、`tests/regression_scenario_preview_secondary_outputs.py`：模拟预览无名称时统一显示“模拟预览（未命名）”，不退回内部编号或正式方案名。
- `web/viewmodels/page_manuals_system.py`、`docs/frontend_manual_audit_and_rewrite_blueprint.md`、`tests/regression_unit_excel_converter_merge_steps_and_classify.py`：继续清理用户可见的英文备份用途和旧 `供应商ID / 工种ID` 表头。
- `docs/aps_frontend_workbench_mockup.html`：未开工任务不再展示“报异常”按钮。
- `tests/test_codestable_tools_contract.py`：把 `dict | None` 改成 Python 3.8 兼容的 `Optional[dict]`。

第七轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。因本轮存在阻塞并已修复，后续必须继续启动第八轮同范围 16 个 Subagent 复审。

## 第二轮对抗性审核

2026-05-25 第一轮修复后，用户要求继续“同范围”对抗性审核：不能只盯着刚修过的问题，必须再次完整看 roadmap 主文档、items.yaml、本账本、原 explore，以及必要的 CodeStable 约束和代码证据。

主代理一次性启动 16 个真实 Subagent，全部为只读审核，均已完成并关闭。本轮归并结论是：仍存在会阻塞后续 feature-design 或实现的口径问题，需要继续修 roadmap、items 和原 explore 提示。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5b21-cedf-7bf0-8675-55d86f4f386f` | Descartes | 计划身份、正式版本、锁定状态边界 | 有阻塞 | 拆清 `is_current_executable_version`、`is_superseded_by_newer_version`、`schedule_lock_status`；反馈写入只看最新正式 adopted。 |
| 2 | `019e5b21-cf3e-7c90-866c-aff7a11db96b` | Ohm | 候选方案来源和业务角色 | 有阻塞 | 明确 `baseline_best / critical_best` 是业务角色，不固定等于候选表；即便来源是 `schedule` 也只能按对比参考展示。 |
| 3 | `019e5b21-cfa6-78d2-bfd2-6ba79c27b8d0` | Turing | 证据链和聚合证据 | 有阻塞 | `EvidenceLink` 增加 `evidence_scope / aggregation_key / contributing_count`，区分行级、聚合、缺数据证据。 |
| 4 | `019e5b21-d007-7991-9d90-77d8e97cf0bf` | Hume | 延期诊断追溯和不能硬说根因 | 有阻塞 | 把重审计快照改成轻量 `DiagnosisTraceMeta`；`primary_operation_clue` 改为 `suggested_operation_clue`；补 `rule_version / ranking_inputs / clue_selection_trace / input_fingerprint`。 |
| 5 | `019e5b21-d06c-70f1-88d8-5b05b0ab27e3` | Galileo | 方案对比路由和差值规则 | 有阻塞 | 删除 `compare_plan_role` 自由比较口径；第一版所有差值固定相对 `adopted`；补 `score_display` 和“评分不能第一眼露出”。 |
| 6 | `019e5b21-d0d9-7243-af40-10533a0ed911` | Noether | 执行事件表、约束、索引 | 有阻塞 | 补外键、CHECK、UNIQUE、索引、`request_fingerprint`、幂等顺序、并发冲突规则。 |
| 7 | `019e5b21-d148-74c0-ac04-fdae1b23b33f` | Dewey | 用户可见文案和小白可理解性 | 有阻塞 | 新增用户可见文案总规则；页面、导出、按钮、弹窗、错误提示不得露内部字段名或英文枚举。 |
| 8 | `019e5b21-d1a2-72d1-a74d-4617c7208dfe` | Jason | 派工反馈接口和计划身份 | 有阻塞 | `GET /scheduler/resource-dispatch/execution/data` 明确带 `version / plan_role / scenario_id`；POST 必带完整身份和 `request_fingerprint`。 |
| 9 | `019e5b21-d20e-71d2-99e9-83b91189ff6b` | Sagan | 执行事实跨版本聚合 | 有阻塞 | 明确执行事实以 `op_id` 聚合，`schedule_id / schedule_version` 只记录事件发生时用户看到的计划行。 |
| 10 | `019e5b21-d27c-7e62-86e3-b639df99a281` | Dirac | 重排输入、现场固定和发布冲突 | 有阻塞 | 已完工从待排输入剔除；生产中/暂停用 execution fixed seed；`execution_snapshot_revision` 写入 `ScheduleHistory.result_summary`；普通重排和 scenario publish 都要检查 revision。 |
| 11 | `019e5b21-d2df-7213-ae9b-0c53a1a1589a` | Socrates | 实现颗粒度和能否照着做 | 有阻塞 | 把“反馈上线”和“最小重排护栏”绑定验收；补每条 item 的具体测试入口和退出条件。 |
| 12 | `019e5b21-d3a4-7a41-a37c-107f41218dd6` | McClintock | 异常反馈边界 | 有阻塞 | 异常反馈继续独立；补异常页面、导出、按钮、弹窗不能露内部字段；补离线静态资源测试。 |
| 13 | `019e5b21-d41b-7a62-96d1-44e22bc45c10` | Franklin | 复盘路由和报表边界 | 有阻塞 | 复盘第一版收窄为 `/reports/execution-review` 和 `/reports/execution-review/export`，不新增 `/scheduler/execution-review`。 |
| 14 | `019e5b21-d484-7583-ae87-282fff756be3` | Hooke | schema 迁移检测 | 有阻塞 | 迁移契约补 `detect_schema_is_current()` 对表、字段、索引的检测，缺表必须判定为非当前结构。 |
| 15 | `019e5b21-d4f4-75e2-b413-06e292c1ebea` | Ramanujan | 依赖图、DAG 和最小闭环 | 有阻塞 | 保持唯一最小闭环为 `delay-diagnosis-overdue-report-entry`；补重排最小护栏和完整重排的依赖关系。 |
| 16 | `019e5b21-d586-7040-8b2a-2f4b7f479ae3` | Chandrasekhar | 文档收口和质量门禁 | 有阻塞 | `aps-three-gap-docs-quality-gate` 补精准测试、回归清单、Win7/offline 验收手册和内部字段泄露检查。 |

本轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：修正计划身份、证据协议、延期诊断追溯、方案对比、执行事件、重排、复盘、迁移和用户可见文案规则。
- `aps-three-gap-directions-items.yaml`：补齐各子 feature 的退出条件、测试文件、重排护栏、异常/复盘大白话验收、docs 收口测试。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：顶部加醒目提示，说明后半旧路线草案已被 roadmap 覆盖。

第二轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。

## 第三轮对抗性审核

2026-05-25 第二轮修复后，用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据

本轮 16 个 Subagent 全部只读审核，均已完成并关闭。本轮归并结论是：仍存在阻塞项，主要集中在旧 explore 误导、执行事件并发口径、scenario 发布快照、异常反馈上线顺序、导出/页面内部字段泄露、离线静态资源测试文件缺失。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5b3b-8734-7bb1-a258-630320e02593` | Anscombe | 原 explore 作废状态和旧口径残留 | 有阻塞 | 将 explore frontmatter 改为 `status: superseded`、`confidence: mixed`，补 `superseded-by`；清理旧“主原因/主要原因/primary_reason/旧 exception 路由/system 录入人”实现口径。 |
| 2 | `019e5b3b-87a6-7a32-88ef-4ce73239b725` | Boyle | docs-quality-gate 用户文档和开发文档边界 | 有阻塞 | 改成用户说明/页面/导出/用户示例不得出现内部字段；开发说明允许写内部结构，但必须标注“仅给开发和测试使用，不给用户看”。 |
| 3 | `019e5b3b-8809-7ef2-82b8-b0635cefaea4` | Confucius | 离线前端资源测试是否真实存在 | 有阻塞 | 新增 `tests/regression_frontend_offline_static_assets.py`，覆盖模板和静态资源不得引外链脚本、样式、字体和常见 CDN。 |
| 4 | `019e5b3b-8874-76a2-964e-e0a1e0072d68` | Singer | 执行事件幂等和前端指纹可信度 | 有阻塞 | 改为 `request_fingerprint` 服务端重算，输入包含完整计划身份、状态版本、动作和载荷；同幂等键但任一关键项不一致返回 409。 |
| 5 | `019e5b3b-88ef-7821-a9da-8829e0fed659` | Nietzsche | 状态版本生成口径 | 有阻塞 | `state_revision` 不再依赖本次刚插入后才知道的事件 id；改为用写入前已提交事件聚合旧 revision，写入后再聚合新 revision。 |
| 6 | `019e5b3b-895c-7990-8172-86b8a39945ee` | Hegel | schedule_id / schedule_version / op_id 绑定 | 有阻塞 | 要求同一事务重新查库确认 `schedule_id / schedule_version / op_id / batch_id` 属于同一条正式计划行。 |
| 7 | `019e5b3b-89d6-7681-8932-84981fda7f35` | Copernicus | schema 当前性检测 | 有阻塞 | `detect_schema_is_current()` 必须检测表、字段、FK、CHECK、UNIQUE、索引列和索引唯一性，不能只看名字。 |
| 8 | `019e5b3b-8a4f-7663-9e92-1e70c7c70fcd` | Euler | execution/data 返回结构 | 有阻塞 | 要求每张任务卡返回 `op_id`、`schedule_id`、当前现场状态、`state_revision`、可用动作、每个不可用动作的中文原因；按钮可用性由服务端给。 |
| 9 | `019e5b3b-8ac6-7ca2-9ea4-566ec602a90c` | Tesla | ExecutionFact 无事件场景 | 有阻塞 | `ExecutionFact` 改为 `last_event_schedule_id / last_event_schedule_version` 可空；无事件的 `not_started` 不伪造当前 `Schedule.id`。 |
| 10 | `019e5b3b-8b40-70f2-8a76-116e730bef4b` | Pascal | execution_snapshot_revision 范围 | 有阻塞 | 补 `execution_snapshot_op_ids`、op_id 数量、清单摘要或完整清单位置；快照复算必须使用同一批 op_id。 |
| 11 | `019e5b3b-8ba3-7fd1-a879-f00854956d00` | Zeno | scenario 保存和发布快照 | 有阻塞 | 把 `gantt_adjustment_scenario_service.py`、scenario repo、schema/migration 纳入重排护栏条目；scenario 保存时记录 revision 和 op_id 集合，发布时复算。 |
| 12 | `019e5b3b-8c1c-77b0-977e-510a2188687c` | Curie | 开工完工反馈与重排护栏空窗 | 有阻塞 | 保持细颗粒度，但要求开工/完工写入不能单独对用户放开，必须和最小重排护栏同批验收，或按钮保持隐藏/禁用。 |
| 13 | `019e5b3b-8c9e-7111-b7d9-49a19826d59c` | Hilbert | 异常反馈状态流转和字段表 | 有阻塞 | 明确不允许 `not_started -> exception`；补异常原因、严重程度、处理状态、是否建议重排的程序值到中文显示到校验规则表；异常反馈不能早于异常重排护栏上线。 |
| 14 | `019e5b3b-8d0b-72c2-ada1-54e58afb2eae` | Pauli | 派工导出和资源页内部字段泄露 | 有阻塞 | `dispatch-plan-identity-guardrails` 纳入 `resource_dispatch_excel.py` 和 `scheduler_resource_dispatch.py` viewmodel；页面、Excel 内容、Excel 文件名不得露内部字段。 |
| 15 | `019e5b3b-8d6a-7361-93d4-7a2a691b8ce6` | Darwin | 资源负荷页、停机影响页 scenario 兜底 | 有阻塞 | `candidate-drilldown-empty-states` 纳入 `templates/reports/utilization.html` 和 `templates/reports/downtime.html`，要求缺模拟名称时显示“模拟预览（未命名）”。 |
| 16 | `019e5b3b-8dc6-7050-9d94-fec245a8eb14` | Mencius | 错误码和复盘导出列 | 有阻塞 | 不再用 `6004` 表示“不是最新正式采用方案”；改为 `6003 / 409` 加 `details.reason=not_current_official_plan`；复盘导出列名固定，并在无事件时写“暂无现场反馈”。 |

第三轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：补正式可写条件、服务端重算指纹、状态版本生成、状态流转、执行快照 op_id 集合、scenario 保存/发布检查、错误码冲突、迁移检测深度、复盘导出列。
- `aps-three-gap-directions-items.yaml`：补真实测试文件、资源负荷/停机页面、派工 Excel 和 viewmodel、执行 data 返回结构、异常反馈字段对照表、scenario schema/repo/service、文档用户/开发边界。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：改为 superseded，修正候选证据行号，清理后半旧路线草案里的危险旧实现口径。
- `tests/regression_frontend_offline_static_assets.py`：新增离线静态资源红线测试。

第三轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。

## 第四轮对抗性审核

2026-05-25 第三轮修复后，用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据

本轮 16 个 Subagent 全部只读审核，均已完成并关闭。本轮归并结论是：仍存在阻塞项，主要集中在周计划和导出漏掉、重排护栏缺少图排程固定路径、开工/完工按钮放开太早、异常反馈上线顺序、错误码口径、未来测试文件描述方式、以及原 explore 旧大白话口径残留。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5b58-0c63-7361-bf39-d5e6b94d250a` | Pasteur | 周计划页面、路由和导出是否遗漏 | 有阻塞 | 将 `templates/scheduler/week_plan.html`、`web/routes/domains/scheduler/scheduler_week_plan.py`、`core/services/scheduler/week_plan_excel.py` 纳入候选钻取和计划身份清理范围。 |
| 2 | `019e5b58-0cc3-78b0-852a-751aaf201056` | Feynman | 超期导出真实生成路径 | 有阻塞 | 将 `core/services/report/report_engine.py`、`core/services/report/exporters/xlsx.py` 纳入延期解释最小闭环，导出列名和内容必须用中文大白话。 |
| 3 | `019e5b58-0d30-7791-aee4-cd83f68e5ef5` | Carver | 图排程 fixed/seed 路径 | 有阻塞 | 将 `schedule_graph_dispatch_context.py`、`schedule_seed_contracts.py`、`sgs_graph.py` 纳入最小重排护栏。 |
| 4 | `019e5b58-0d88-7e12-9a51-bb374b007586` | Linnaeus | 开工/完工反馈和重排护栏上线顺序 | 有阻塞 | 开工/完工条目改为后端写入能力和任务卡预备，按钮默认隐藏或禁用；最小重排护栏完成后才允许对普通用户放开按钮。 |
| 5 | `019e5b58-0de3-7aa0-a430-a2bf0e9d6623` | Kuhn | 异常反馈和自动重排冲突 | 有阻塞 | 异常反馈同批加入“异常中阻止普通自动重排”的最小后端护栏，完整算法接入仍放在后续重排条目。 |
| 6 | `019e5b58-0e3d-7b70-88a5-ae8448f9e743` | Faraday | 非正式方案写反馈的错误码 | 有阻塞 | 收窄为 `6003 / 409`，`details.reason=not_current_official_plan`；权限不足才使用 `1004 / 403`。 |
| 7 | `019e5b58-0e95-76f0-9fb3-5a09c367512d` | Hypatia | 测试文件是否被写成当前已存在入口 | 有阻塞 | 在 items 顶部说明 `tests/regression_*.py` 是实施对应子 feature 时要新增或更新的测试；多处命令改为“实施本条 feature 时必须新增或更新并通过”。 |
| 8 | `019e5b58-0eef-79f2-8f02-aaa6d2c832ec` | Averroes | 原 explore 是否还会误导实现 | 有阻塞 | 清理“未开工直接报异常”“第一卡点”“原因列”等旧口径，改成“建议先复核”“可能线索”等低门槛表达。 |
| 9 | `019e5b58-0f57-7ef2-ad3b-ccfd4d696da0` | Helmholtz | 派工确认条件是否足够严格 | 有阻塞 | 主 roadmap 将派工确认条件改为必须 `PlanIdentity.can_dispatch=true`，并展开最新正式采用方案、未被新版本替代、未被锁定等条件。 |
| 10 | `019e5b58-0fa9-7601-9b08-1016a612f653` | Harvey | 异常 request_fingerprint 字段 | 有阻塞 | `request_fingerprint` 补入异常严重程度、影响分钟数、影响设备、影响人员、处理状态、是否建议重排。 |
| 11 | `019e5b58-100f-78a3-bb1f-72aa8eb42d60` | Raman | 任务卡返回结构和按钮可用性 | 有阻塞 | `execution/data` 补 `op_id`、`schedule_id`、当前现场状态、`state_revision`、可用动作、不可用动作的中文原因；按钮可点由服务端返回。 |
| 12 | `019e5b58-1068-7580-8dc0-a5e3c1cdc8dc` | Locke | 异常处理状态第一版边界 | 有阻塞 | 明确 `handling_status` 第一版只记录不更新，避免把异常处理闭环误写进本路线图。 |
| 13 | `019e5b58-10c0-7850-9196-78c0dd7c7271` | Leibniz | 周计划和模拟名称兜底文案 | 有阻塞 | 周计划页面、导出工作簿、导出文件名不得显示 `scenario_id`；无名称时显示“模拟预览（未命名）”。 |
| 14 | `019e5b58-1125-7e53-9b64-5fa089406ff6` | Ampere | 文档变更日志和复审证据 | 有阻塞 | 主 roadmap 补第三轮和第四轮变更日志，说明本轮修正范围。 |
| 15 | `019e5b58-1187-73b3-bba4-e872b037ae6c` | Maxwell | 离线静态资源检查覆盖度 | 有阻塞 | `tests/regression_frontend_offline_static_assets.py` 补协议相对 URL 检查，覆盖 script/link/import/font-face。 |
| 16 | `019e5b58-11dc-7fc3-942d-510218db3095` | Hubble | 整体颗粒度和能否照着做 | 有阻塞 | items 补更细的文件范围、退出条件和实施时验收命令，避免后续 feature-design 还要回头猜。 |

第四轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：补周计划、超期导出、图排程 fixed/seed、严格派工条件、任务卡返回结构、异常阻止普通自动重排、第三/第四轮变更日志。
- `aps-three-gap-directions-items.yaml`：补周计划页面/路由/导出、报告导出器、图排程路径、按钮上线顺序、异常反馈最小护栏、错误码收窄、未来测试文件说明。
- `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md`：清理“未开工直接报异常”“第一卡点”“原因列”等容易误导实现和用户文案的旧表达。
- `tests/regression_frontend_offline_static_assets.py`：增强协议相对 URL 检查，避免离线页面悄悄依赖外部资源。

第四轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。

## 第五轮对抗性审核

2026-05-25 第四轮修复后，主代理按用户要求继续同范围对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围仍为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据

本轮 16 个 Subagent 全部只读审核，均已完成并关闭。本轮归并结论是：仍存在阻塞项，主要集中在错误码口径、超期导出真实链路、导出追溯字段的用户表头、重排执行事实读取路径、开工/完工按钮验收话术、离线资源测试覆盖、CodeStable 工具 Python 3.8 兼容，以及用户能看到的英文参数、英文缩写和导出文件名。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5b72-ee30-76a3-adc8-8aeab874a5e5` | Lovelace | CodeStable 格式、依赖图和整体一致性 | OK | 无阻塞；确认 14 条 item、唯一最小闭环和 DAG 基本一致。 |
| 2 | `019e5b72-ee98-77c2-b03f-f2b0e8bd6408` | Kierkegaard | 计划身份、派工和反馈写入边界 | OK | 无阻塞；确认 `can_dispatch / can_write_feedback` 严格度足够。 |
| 3 | `019e5b72-ef03-7ad1-9abf-c0a430c7b062` | James | 延期诊断、超期清单、报表导出和追溯信息 | 有阻塞 | 将 `web/routes/report_plan_preview.py` 纳入超期导出真实链路；要求“诊断依据”表头中文化，不能把 `trace_meta / rule_version / input_fingerprint` 原样给用户看。 |
| 4 | `019e5b72-ef65-7ca2-98e4-458d6a4bab74` | Bohr | 候选方案、周计划、资源负荷、停机影响和资源派工跳转 | OK | 无阻塞；确认第四轮漏项已在 roadmap/items 覆盖。 |
| 5 | `019e5b72-effc-78d2-81dd-4face78a78c9` | Kepler | 执行事件、并发、幂等和错误码 | 有阻塞 | 将 `1004 / 403` 收窄为权限不足；当前状态不允许、状态刚变、旧 revision 被消费、同幂等键不同内容等统一走 `6003 / 409`。 |
| 6 | `019e5b72-f054-75c0-88d4-358a827eefe4` | Laplace the 2nd | 开工/完工和最小重排护栏空窗 | OK | 无阻塞；确认按钮放开必须等最小重排护栏。 |
| 7 | `019e5b72-f0c1-7390-9c2c-30d175429532` | Pasteur the 2nd | 异常反馈、异常状态流转和异常中阻止普通重排 | OK | 无阻塞；确认未开工不能直接报异常。 |
| 8 | `019e5b72-f11f-7a93-a964-d2162dcd8cf3` | Bacon the 2nd | 重排执行事实、图排程 fixed/seed、scenario 保存/发布快照 | OK | 无阻塞；确认图排程和 scenario 路径已覆盖。 |
| 9 | `019e5b72-f194-75d3-8aa6-aa0e201201d3` | Fermat the 2nd | 计划和现场实际复盘路由与导出列 | OK | 无阻塞；确认只走 `/reports/execution-review`，不误新增 scheduler 复盘路由。 |
| 10 | `019e5b72-f1f8-7242-aafe-a1b812a41cde` | Dewey the 2nd | schema 迁移、repository 和 Python 3.8/Win7 约束 | OK | 无阻塞；确认新增表和深度检测要求在 roadmap/items 中足够明确。 |
| 11 | `019e5b72-f25d-7c23-9a4e-42f9797b2a7f` | Carver the 2nd | 用户可见中文大白话 | 有阻塞 | 用户手册不再教用户填 `latest`；资源排班导出表头改为“排程编号 / 工序编号”；周计划、资源负荷、停机影响导出文件名改用中文“至”。 |
| 12 | `019e5b72-f2c2-7140-ac57-14516aefbbe8` | Chandrasekhar the 2nd | 离线静态资源测试覆盖 | 有阻塞 | `tests/regression_frontend_offline_static_assets.py` 补 JS 动态 import、静态 import 和 CSS `@import "..."` 外链检查。 |
| 13 | `019e5b72-f33b-7420-a46e-04a488359392` | Goodall the 2nd | 原 explore 是否还会误导实现 | OK | 无阻塞；确认 `status: superseded` 和顶部作废提示足够清楚。 |
| 14 | `019e5b72-f396-72c1-a4ab-7e21e056da20` | Hooke the 2nd | items 颗粒度和重排路径完整性 | 有阻塞 | `reschedule-minimum-execution-guardrails` 和 `reschedule-respects-execution-facts` 补执行事实读取路径：执行反馈服务、未来 `ExecutionFactProvider`、repository。 |
| 15 | `019e5b72-f3fd-7713-994c-52cc5b369edc` | Hypatia the 2nd | 第四轮账本一致性 | OK | 无阻塞；确认第四轮 16 个 agent 和修复采纳已记录。 |
| 16 | `019e5b72-f491-7341-8c5c-cc0162f01a8a` | Bernoulli the 2nd | 总体验收压力测试 | 有阻塞 | 开工/完工 item 改清“服务端受控写入，普通用户按钮先隐藏或禁用”；`.codestable/tools/validate-yaml.py` 和 `search-yaml.py` 改回 Python 3.8 可用类型写法。 |

第五轮修复采纳后，主代理已继续修改：

- `aps-three-gap-directions-roadmap.md`：补 `web/routes/report_plan_preview.py` 导出链路，明确导出追溯表头必须中文化，统一 `1004 / 403` 和 `6003 / 409` 口径。
- `aps-three-gap-directions-items.yaml`：补超期导出链路、导出追溯中文表头、重排执行事实读取路径、开工/完工按钮上线边界。
- `tests/regression_frontend_offline_static_assets.py`：补 JS `import()`、静态 `import ... from`、CSS `@import "..."` 外链检查。
- `.codestable/tools/validate-yaml.py`、`.codestable/tools/search-yaml.py`：把新式类型注解改回 Python 3.8 可运行写法，避免 CodeStable 必跑工具卡住 Win7/Python 3.8 场景。
- `web/viewmodels/page_manuals_scheduler_outputs.py`、`static/docs/scheduler_manual.md`、`core/services/scheduler/resource_dispatch_excel.py`、`web/routes/domains/scheduler/scheduler_week_plan.py`、`core/services/report/report_engine.py`：清理用户可见的 `latest`、`ID`、`_to_` 旧表达，改成中文大白话。
- `tests/regression_week_plan_filename_uses_normalized_version.py`、`tests/test_scheduler_resource_dispatch_smoke.py`：同步新文件名和新导出表头期望。

第五轮结束状态：16 个 Subagent 均已关闭，没有保留开放子代理。因本轮存在阻塞并已修复，后续必须继续启动第六轮同范围 16 个 Subagent 复审。

## 第一轮对抗性审核

2026-05-25 用户要求同范围 Subagent 对抗性审核。主代理一次性启动 16 个真实 Subagent，统一范围为：

- roadmap 主文档
- items.yaml
- 本证据账本
- 原 explore 证据文件
- 必要时读取 CodeStable 约束和路线图引用到的代码证据

全部 Subagent 都是只读审核，均已完成并关闭。第 16 个创建成功后，主代理额外发出的第 17 个创建请求被宿主拒绝为 `agent thread limit reached`，不计入本轮。

| 序号 | agent_id | 昵称 | 审核重点 | 结论 | 采纳修复 |
| --- | --- | --- | --- | --- | --- |
| 1 | `019e5b0c-5d13-7281-b626-b7ca10fc4508` | Schrodinger | CodeStable 结构、颗粒度、接口硬度 | 有阻塞 | 统一执行状态；补 Python 3.8 写法；补反馈路由请求体；补共享结构字段 |
| 2 | `019e5b0e-239f-7083-b2c1-4c9ae66c3b29` | Aquinas | 原 explore 证据一致性 | 无阻塞，有建议 | 将“主要原因”改成“可能线索 / 建议先复核” |
| 3 | `019e5b0e-2403-7fd0-bb2c-4840bf34e5ed` | Poincare | 后端接口、数据模型、迁移 | 有阻塞 | 反馈写入强制计划身份；补 state_revision；补异常影响字段；新增重排最小护栏 |
| 4 | `019e5b0e-2480-79e1-8596-b1ce2e61a39f` | Halley | 前端大白话和低认知门槛 | 有阻塞 | 新增用户可见文案总规则；补内部值到中文文案映射；约束错误提示必须中文大白话 |
| 5 | `019e5b0e-24e1-7012-be99-f7712723c5e9` | Erdos | Win7、Python 3.8、离线资源 | 有阻塞 | 全部契约示例改 Python 3.8 写法；每条前端 item 补 Chrome 109 / 离线 / 不引外链验收 |
| 6 | `019e5b0e-2539-7173-8956-3e867f03fd3a` | Dalton | 依赖图、最小闭环、实施顺序 | 有阻塞 | 新增 `reschedule-minimum-execution-guardrails`；调整完整重排依赖；拍板 `created_by` 第一版页面必填 |
| 7 | `019e5b0e-25a2-7b21-a9f2-3377c259032b` | Aristotle | 三方案对比和排程语义 | 有阻塞 | 方案对比路由改为 plan_role 口径；can_dispatch/can_write_feedback 补当前可执行版本条件 |
| 8 | `019e5b0e-261a-7b70-8865-9f1e524e4b3f` | Herschel | 延期诊断和不能乱说根因 | 有阻塞 | 字段从 primary reason 口径改为 leading clue；页面禁用“主要原因 / 根因” |
| 9 | `019e5b0e-2679-7851-a3fa-7a3d9015f190` | Heisenberg | 资源派工、现场反馈、执行状态 | 有阻塞 | 写入接口强制正式 adopted 计划；执行状态统一为 processing/completed；foundation 补派生执行状态验收 |
| 10 | `019e5b0e-26f3-75f0-9ed2-b1632658affc` | Gauss | 现有路由和模块注册 | 有阻塞 | 车间反馈路由落回资源派工上下文；不新增未注册独立 execution feedback 模块 |
| 11 | `019e5b0e-275e-72e1-8318-2a552f0f97b0` | Plato | 验收、测试和质量门禁 | 有阻塞 | 每条高风险 item 补测试文件和精准 pytest；最小闭环补诊断服务测试；质量门禁不替代单条验收 |
| 12 | `019e5b0e-27bf-7592-8fc2-c2c497f669db` | Bacon | 数据血缘、证据链接、审计追溯 | 有阻塞 | EvidenceLink 补 source_table/source_row_id/plan_identity；诊断返回补 audit_snapshot；新增本对抗审核账本 |
| 13 | `019e5b0e-283a-7f03-8ab0-52b2466e2fe3` | Banach | 范围漂移和过度设计 | 有阻塞 | 第一版硬路由收窄到现有页面上下文；确认派工写入降为后续 feature；公共协议切窄为读取身份和证据 |
| 14 | `019e5b0e-288e-7d70-bb07-948698c156d5` | Rawls | 文档一致性和术语边界 | 有阻塞 | 统一现场状态枚举；明确 roadmap 最终口径覆盖 explore 草案路由 |
| 15 | `019e5b0e-2911-7113-8e9f-c32a7f399aef` | Parfit | 实现者照着做压力测试 | 有阻塞 | 明确推荐卡不提前做差值；确认派工不做写入；异常/复盘字段补进执行事件和状态读模型 |
| 16 | `019e5b0e-296e-72b2-b0a5-4650b963a930` | Russell | 安全、幂等、并发、误操作 | 有阻塞 | 反馈写入增加 expected_state_revision；服务端事务内校验状态版本；补并发冲突测试 |

本轮修复后已执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items
```
