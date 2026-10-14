---
doc_type: feature-acceptance
feature: decision-preparation-events
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第4阶段共同需求账、准备加工分解、实际工种事件、原始导出和真实场景验收
tags: [aps, workbench, operation-effort, changeovers]
---

# 第4阶段实施验收

**第4阶段实施和主对话独立验收通过。** 共同需求账、准备／加工明细、实际工种事件、甘特往返、旧同义消费者及原始导出均已完成。相关回归、日常检查、最终布局、键盘及原生缩放验证通过。主对话未新增返修项，已派发第5阶段，第6—8阶段等待。

主对话独立证据位于`evidence/decision-stage-acceptance/stage-04/`，结论记录在母任务维护的[阶段验收](../../roadmap/scheduling-decision-workbench/stage-acceptance.md#第-4-阶段主对话独立验收)。独立复算31道账／310字段、4候选准备14.5h／加工45.55h、3次实际工种切换、712数值格／32空值格及正式来源和实际往返均通过。

依据为[设计](decision-preparation-events-design.md)与[执行清单](decision-preparation-events-checklist.yaml)，文件范围、实例及直接入口见[交接](decision-preparation-events-handoff.md)。本轮继续第0—3阶段未提交工作区。

## 1. 接口契约核对

- 总览目录为52项，版本`decision-preparation-v4`：原42项保留自身事实来源，新增准备／加工8项及实际切换2项。`changeover_count`标“算法工种切换”，`type_changeover_count`标“工种切换次数”。正式归档缺保存算法统计时保持缺项，共同实际事件另列。
- `GET .../decision/preparation`按永久工序配对两侧runtime需求、归档标准、实际归属和安排，覆盖整次受理。批次、设备、所选归属筛选及稳定排序，20／50分页；汇总和筛选目录保留完整范围。
- `GET .../decision/changeovers`提供所选及基准侧事件、设备、真实工种身份、前后永久工序／行身份、窗口前驱、冲突及钻取。设备、事件侧筛选及稳定排序，20／50分页。
- 原工序详情新增`runtime_effort.before/after`，候选和正式工作区已排／未排记录新增compact`operation_effort`。新永久工种字段可选并逐项校验；归档缺项有完整状态。
- 快照绑定共同模式、候选／基准、窗口、资源视角和业务筛选；显示页码不改变事实范围。准备为`full_admission`，切换为`fixed_changeover_window`，资源内部投影继续`available_occupancy_v1`。
- CSV支持准备和切换分区；XLSX完整比较9表、单资源逐日入口11表。准备86列、事件33列、工序109列，runtime列前缀唯一；数字原生、空值留空，来源与身份可追溯。

## 2. 行为与决策核对

- `internal_requirement_parts`同时供实际排槽及`OperationEffort`构造，准备＋加工＝实际标准需求。分件自身量1，共同工序按批次自身量计一次；外协周期、合并组独立于内制标准小时。
- 运行完成事务一次保存带永久引用的需求账，候选以自己的实际安排判定新排、普通未排及暂缓归属。试调保存实际新槽分解，原样／执行／完成安排保留原来源；几何变化与需求元信息分开。
- 原需求`target_quantity/quantity_basis`及标准小时保持原值，本次受理／试调创建AJ的执行目标、数量依据和余量独立。正式before也使用本次AJ执行数量，标准及原需求来自该工序最后采用来源。
- 新排、保留、执行、完成、未构造及外协各有状态。旧runtime缺失时保留缺项，原标准可独立查看；正式原来源标准缺失时保持缺项。真实开工未复核由现行预检保护，完成账保持原实际时段与标准需求。
- AJ完成状态为`complete`，旧完工事实为`completed`；两个字段分别按真实域读取。原需求和本次执行量各自绑定明确来源，跨运行数量变化保持可核对。
- 工种切换按真实ID判断，先建立完整设备非零内制序列，再按后序开始落入左闭右开窗口。首道、同ID和零时点为0；同ID不同工序名称仍同工种，不同ID同名仍切换。缺身份是屏障，重叠附冲突与已知小计。
- 评价计数、原生插入惩罚、候选／正式／试调事件消费同一规则。新结果及种子保存实际ID；旧trace完全无ID字段沿自己的原输入读取，显式None保持未知。覆盖不同或统计未知时切换差值中性。

## 3. 验收场景与实际证据

| 场景 | 当前结果 | 实际证据 |
| --- | --- | --- |
| C01 共同实际需求、零工时及数量 | passed | 真实31项收据930字段独立核对；DP-NORMAL准备2＋加工5＝7h，真实零时点保留。源头8项及实际worker接口回归通过。 |
| C02 执行、完成、冻结种子 | passed | 真实start目标3／余量未知，预检`execution_review_required`且收据数保持；真实完工worker保留08:00–10:00／M1／O1，原标准0／0.75／0.75h，余量0。真实31scope冻结1条原安排、旧需求分解缺项，执行目标20独立显示。Trial真实完工无anchor仍归completed，原10件／7h与当前20件／余量0保持。 |
| C03 分件、共同工序、外协 | passed | 真实6道件别工序：共同目标2、自身目标1，分别保存；外协周期0.25d，内制标准0。源头及既有外协／分件回归复用，同义试调读取通过。 |
| C04 永久保存、正式来源及旧档 | passed | 实际4候选各30安排／31项账，artifact v4；真实SQLite完整v1＋manual部分v2旧档fixture核每道最后来源，v2缺账／标准保持未知，v1原target6／4h与本次执行20分开，B2真实新排target20／4h。旧42工序runtime未知、归档标准已知；当前修改后原snapshot保持。 |
| C05 相同准备、漏排及暂缓 | passed | 4实际候选新排准备均14.5h、加工45.55h，差值相同；待料1道未进入runtime构造，pending总值null、已知小计与缺项并列。普通漏排真实SQLite worker证明少安排的准备降低为中性／different_coverage；旧ordinary_partial归档复用。 |
| C06 真实工种事件、前驱及覆盖 | passed | 两侧6事件与独立实际序列一致，每候选3次、原算法新计数3；同工种及点事件计0。窄窗保留前驱、右端排除；核心5项和真实SQLite/API未知／重叠场景通过。原候选、正式和试调显式None屏障已统一。 |
| C07 界面、稳定分页、往返与导出 | passed | 31／旧42工序20／50同快照、批次筛选全汇总通过；5案例7份原始导出899行、42,897格／11,347数字通过，含单人员逐日11表。真实准备所选／正式、切换前序／后序4次往返恢复完整上下文。1392／1920深浅两页8张最终图、原生依据Enter／Space及准备汇总／逐道表125／150%缩放滚动通过。 |
| C08 日常、离线、资料与文档 | passed | Python3.8.10日常461 passed／20 skipped，127必跑目标、Ruff全通过，70.44s；日常后布局增量的2项Node及10文件Chrome109构建通过。实际浏览器155加载本地资产；原7运行／34候选、正式v1／15行及参数保存，当前同库10运行／38候选含2失败历史。需求、架构、路线图、手册、速查表和本阶段材料已同步。 |

证据根目录：`evidence/decision-preparation-events/`。最初20工序受理因件别完整排产规则失败；19工序变体因缺正式12工序失败，两份记录保留。完整31工序方案先静态核正式覆盖、件别、容量和预检，再使用原10月30日截止参数受理成功；分析仍使用10月13日00:00至17日00:00共同窗。普通未排使用真实SQLite/API及已有归档证明。

- [实际运行及原数据保全](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/preparation-complete-formal-scope-fixture.json)、[静态范围与容量](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/complete-formal-scope-static-plan.json)
- [第4阶段原始证据索引](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/evidence-index.json)：19张有效截图和2张修正前布局分别列出，原始失败受理及最终成功记录保留。
- [需求与事件独立核对](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/preparation-verification.json)、[收据原账](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/saved-operation-effort-complete-formal-scope.json)
- [原始导出核对](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/exports/export-verification.json)、[真实DTO与shipped组件修正后证明](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/frontend-final-contract-repair.json)
- [单人员逐日11表核对](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/exports/all-operator-days-eleven-tables/verification.json)、[四条真实入口](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/link-verification.json)
- [最终浏览器、四次往返与布局原生缩放](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/browser/verification.json)、[日常后布局增量](../../../evidence/decision-preparation-events/quality/frontend-layout-incremental.json)、[冷启动后的事实一致性](../../../evidence/decision-preparation-events/aps-decision-workbench-20261013/final-query-reuse.json)
- [日常原日志](../../../evidence/decision-preparation-events/quality/daily-final.log)、[质量摘要](../../../evidence/decision-preparation-events/quality/summary.json)、[253条路由对账](../../../evidence/decision-preparation-events/quality/quickref_vs_routes.md)

## 4. 术语一致性

标准准备、标准加工、排槽标准需求与班表内资源占用分别表达。原需求目标、本次执行目标和余量分别显示；原标准依据独立展开。准备汇总覆盖整次受理，切换按后序开始裁窗；页面、详情和导出共用同一分解。常用候选行保留值、状态、已知小计和缺项数量，准备汇总采用8行对照、名称集中在表头；完整理由用原生可键盘展开的依据显示。缺账、未构造、已知0及外协不适用各有状态。正式来源缺标准保持未知。

## 5. 架构归并

已同步调度架构的共同公式、需求账、保存事务、来源解析、角色和真实工种规则；工作台架构同步两新页签、compact／side合同、筛选分页、甘特返回和9／11表导出。标准小时属于调度需求，日历效率后的占用属于共同资源；计数与事件复用相同真实身份规则。共享源头被实际排槽、评价、原生插入及旧消费者使用，页签属于新增查询与展示。

## 6. Requirement 回写

`candidate-comparison-business-view`更新当前52项目录、共同需求账、数量来源、准备／加工归属、真实事件、往返和导出。手册同步用户操作和单位。完整推荐解释、过程及历史继续按后续路线图推进。

## 7. Roadmap 回写

母方案4.4补入原需求目标与本次执行量字段及准确来源。第3阶段主对话已passed；本阶段记录done／实施passed／主对话passed，第5阶段已派发，第6—8阶段planned。母独立验收记录由主对话维护。

## 8. Attention候选盘点

当前兼容性、永久身份、保存事务和验证约定继续适用。新增领域合同已进入需求、架构、手册及速查表，后续按这些共同入口扩展。

## 9. 遗留与交付边界

- 当前实例及直接入口以交接和最终证据索引为准，同库46批／90工序／10运行／38候选／613任务，正式v1／15行保存。
- 源码、静态资产和材料继续处于第0—4阶段累计未提交工作区，README原有10行并发新增保留；本轮交付本阶段实施证据和适用日常结果。最终HEAD、clean-worktree证明、Win7实机及整体边界性能由第8阶段验收。
- 第4阶段主对话独立验收已通过，第5阶段已派发，第6—8阶段等待。
