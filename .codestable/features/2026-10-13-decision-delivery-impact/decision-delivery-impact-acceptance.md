---
doc_type: feature-acceptance
feature: decision-delivery-impact
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第 2 阶段共同交付、逐批工序影响、正式归档与导出实施验收通过，待主对话独立复核
tags: [aps, workbench, delivery, candidate-comparison]
---

# 第 2 阶段实施验收

**第 2 阶段实施验收通过。** 共同交期/完成性、正式归档模式、逐批交付/工序变化、筛选分页、双方甘特定位及明细导出均已实现。最终日常门禁、五次真实浏览器往返和原始导出核对通过。主对话独立验收已通过，两项P3关闭；第3阶段已派发，第4—8阶段等待。

设计输入为 [decision-delivery-impact-design.md](decision-delivery-impact-design.md)，交接与复核入口见 [decision-delivery-impact-handoff.md](decision-delivery-impact-handoff.md)。本轮为未提交工作区阶段验收。

## 1. 接口契约核对

- 总览 `GET .../runs/<run_ref>/decision` 支持 `comparison_mode=candidates|admission_official`。正式模式使用受理归档身份，候选模式可任选同次已产出候选；固定算法推荐与查看基准分开。
- `/decision/batches`、`/decision/operations` 要求明确所选候选，返回同一 scope、双方基准、完整范围 summary、筛选选项、行明细及分页。默认 20 行，可选 50；过滤后稳定排序，未知值排末，永久引用固定同值顺序。
- `/decision/reference-workspace` 读取同一受理正式基准，保留多段、未排和缺时间事实，能力为只读。基准范围限定本次选批/工序。
- `/decision/export` 支持 `section=overview|batches|operations|all`；CSV 为单分区，XLSX 完整比较为五表。`filter_section` 明确当前页签筛选，其他分区使用共同范围；当前页码不限制整表导出。快照核对身份、范围、指标版本与筛选。
- 前后端均核对候选/正式身份、成对时间窗、明细条件和快照。显式 URL 的正式只读上下文要求运行、所选候选与计划身份；正式模式混入候选基准实际返回 400 和具体原因，见 `final-navigation-probe.json`。

## 2. 行为与决策核对

- 共同 `project_delivery_batch / delivery_summary / delivery_batch_delta` 负责交期、全链完成性、覆盖、小计与差值；候选、正式计划、值班台、试调及其导出消费同一规则。非法或缺交期仍保留工艺完成状态，未指定交期为 `not_applicable`，其拖期为 null。
- 搜索覆盖、可排工序覆盖与全链交付独立。合法待料后道为 `deferred`，普通漏排为 `incomplete`；既有算法分数和正式采用事务沿原职责。
- 正式基准从归档按“每道工序在受理版本及以前的最后正式安排”归并；只读取绑定的不可变候选/试调来源，恢复原资源身份、待料和零工时实际工作。当前 Schedule 或主数据变化不回填历史，原受理归档保持原样。
- 当前候选分析/值班台与新比较页使用同一正式基准；显式历史版本 API 保留指定版本范围。真实回归中最新版本只含 B1，当前比较保留 B1+B2，旧版本入口仍保留原来一批范围。
- 双方实际工作集合一致才计算跨度与切换差值；交付收益按共同完成批次计算，同时显示全范围未知覆盖。缺正式基准保持完成性与差值未知。
- 工序需求采用保存工艺的标准工时，执行/保护与锁定标记分别标明来源。实际准备排槽分解沿第 4 阶段；本阶段没有把标准需求充当实际耗时。
- 挂载点已核对：decision 路由注册总览/批次/工序/正式工作区/导出，build-order 挂入 API/明细/总览，`RunCandidateWorkspace` 按模式读取双方甘特，旧交付调用者和 UI 枚举使用共同规则。移除新路由/组件即可卸除新明细，旧计划/试调领域入口保持各自职责；共同交付入口属于系统规则，不能只移除单页时一并撤回。

## 3. 验收场景与实际证据

| 场景 | 当前结果 | 证据 |
| --- | --- | --- |
| C01 三种交期、覆盖与原分数 | passed | 真实 21 批/42 工序：18 指定、1 未指定、2 缺交期；21 批全链完成，已知 18、未知 2、评价 20，总拖期 null，已知小计 74.5h。全未指定、非法历史值、微秒精度与原分数由共同投影/决策回归锁定。 |
| C02 完整、普通漏排与合法待料 | passed | 普通部分运行双方分别只完成不同批次，共同完成集合为空，收益为空；stage 运行本次可排 1 道完成、后道 1 道合法暂缓，全链为 deferred、交付未知。候选→正式采用→试调待料身份回归通过。 |
| C03 候选与正式归档、当前资料变化 | passed | 当前资料交期/名称/标准工时/设备名修改后归档结果保持；正式来源、多段、零工时、资源身份恢复、部分新版及缺基准回归通过。生成/现场核对的 raw JSON 和当前字段回看在 evidence 目录。 |
| C04 身份、变化、排序与分页 | passed | 真实 21 批跨 20 行分页、42 工序跨多页，按筛选/排序拼接与整表一致；20/50、变化类型、空值末尾和永久身份稳定顺序由 API 回归锁定。12 份真实 HTTP 响应、142 条明细的实际组件契约通过。 |
| C05 实际界面、双方定位回跳 | passed | 候选模式批次/工序双方四次回跳与四个桌面浅深截图通过；正式详情布尔格式错误在共同入口修正后，实际正式往返通过。9 项上下文、15 行列表和原查看窗保持；正确定位 v1/目标工序、只读能力、12 个执行字段，最终 console 0 errors / 0 warnings。 |
| C06 两明细双格式原始读取 | passed | 最终 60154 实例的 11 个既定场景、18 份原始文件、743 业务行通过；批次 38 列/工序 49 列共 14568 格按标准读取逐值核对，其中 3320 个数字格。单明细、当前筛选排序的全页和 all 五表范围一致；包含正式模式。root 另直接读取真实 21 行批次 CSV/XLSX，普通名称原样、空值为空、数字为数值类型。 |
| C07 全调用者、日常、离线与文档 | passed | 正式详情修正后的日常门禁 400 passed / 20 skipped，62.68s，116 个必跑目标，Ruff 全通过；新增实际完整正式 Detail 渲染回归、decision Node 与最终 Chrome109 构建通过。架构、需求、速查表和说明已同步。 |

原始证据目录：`evidence/decision-delivery-impact/aps-decision-workbench-20261013/`。`delivery-fixtures.json` 与 `delivery-verification.json` 保存早期生成/查询的 58521 实例身份，最终服务与最终检查以 `runtime-current.json` 及最终浏览器/导出记录为准。

最终只读查询为 `final-query-verification.json`；五次往返与四个有效截图汇总于 `browser/browser-verification.json`，正式完整上下文和只读定位为 `browser/formal-reference-return-context.json`。最后正式页面使用当前产物实际复验，前四次候选回跳和未受字段格式修复影响的布局/导出结果复用。失败原始响应、console 和截图保留历史，不列为最终通过截图。

材料初次交付检查：本 feature 4 份及路线图 2 份 YAML/frontmatter 全通过；quickref routes 为 OK，`git diff --check` 退出0。交接清单86个路径条目与当时19个本地证据链接均存在。另补 `browser/formal-reference-detail-success-dark-1920x1080.png`，主代理实际目视确认修复后v1只读详情与12个执行字段同屏可读。

现场边界：运行生产者拒绝非法非空日期，缺交期允许受理。实际混合输入使用 18 个合法日期、1 个 `9999-12-31` 和 2 个 null；非法字符串的预检拒绝保存在 `mixed_due/invalid-date-producer-boundary.json`，历史非法值的共同投影由测试核对。

## 4. 术语一致性

- `DueState / DeliveryRisk / DeliveryCompletionState` 与前端共享交期、风险和完成性枚举对应；`specified / unspecified / invalid`、`complete / deferred / incomplete / unknown` 分别使用。
- 三组交期计数合计批次数，评价计数为指定加无效，已知加未知合计评价范围。`full_admission` 汇总与行筛选明确分开，实际标准工时依据和保存锁定标记均有来源标签。
- 原资源身份缺项在共同归档入口恢复后同步移除；仍缺原身份或真实名称时保留具体 gap，避免已解决缺项使资源变化误显示未知。

## 5. 架构归并

- `architecture/service-scheduler.md` 写入共同交付合同、计数、不变历史、正式归并来源、当前/显式历史入口范围、同工作比较和明细模块职责。
- `architecture/workbench-shell.md` 写入三页签、全范围目录、筛选分页、五表导出范围、双方甘特及只读正式入口和完整回跳上下文。
- `开发文档/系统速查表.md` 写入实际模块、三组枚举/计数及三条新增路由；route quickref 检查已通过。

## 6. Requirement 回写

`requirements/candidate-comparison-business-view.md` 已增加本 feature 到 implemented_by，并更新逐批/工序用户故事、正式归档范围、共同交付、分页钻取和明细导出能力；保留原完整愿景和历史变更记录。`static/docs/scheduler_manual.md` 同步当前操作。

## 7. Roadmap 回写

本阶段已回写done / implementation_acceptance=passed / parent_acceptance=passed。母任务的 `stage-acceptance.md` 和独立审查证据由主对话维护。第3阶段已派发，第4—8阶段保持planned。

## 8. Attention 候选盘点

本阶段沿用现有产品/宿主运行时与隔离验证工具，未暴露需要新增到 attention.md 的长期环境约定。

## 9. 遗留与交付边界

- 后续阶段继续共同班表资源、准备需求分解、完整推荐解释、优化过程、历史趋势与整体集成验收。
- 当前验证为 Mac / Python 3.8.10 和离线 Chrome109 构建；Win7 真机、最终整体门禁与发布按母任务交付阶段执行。
- 本轮源码、静态产物与记录未提交。既有 `开发文档/README.md` 并发改动原样保留；工作区持续包含第 0/1 阶段实现与本阶段改动。

## 10. 主对话复核修正

- 直接预览的4条URL已补齐顶层 `view=analysis`，与 `nav.view` 一致。实际打开本文件交接中的混合交期链接：身份/页签正确，第一页20行/共21批与API一致。其余3条按同一URL规则核对通过，同批材料的同类遗漏已清理。
- 正式主时间行使用已有 `data.reference`，可见标签、行标题和canvas可访问名称统一为“正式归档”；普通候选语义保留。两种身份的实际组件核对1 passed，Chrome109离线构建通过，真实正式v1/DC-04工序1截图与10项窄域核对通过。
- 本次复用400项主体日常门禁、导出和归档结果，增量证据为 `link-repair-01/` 的链接及正式行标签JSON/截图。具体链接与动作见 handoff 第7节；主对话独立验收仍为pending，第3阶段等待派发。

## 主对话独立验收回执

2026-10-13 主对话确认第2阶段正式通过，两项P3关闭。直接从当前handoff抽取4条URL并实际打开正式对照，15行正常加载，DC-04定位、两条主行可见文案/title/canvas可访问名称均为“正式归档”，无alert；其余交付/归档/API/导出/分页往返证据沿首轮主审复用。独立证据在 `evidence/decision-stage-acceptance/stage-02/repair-01/` 的 `formal-lane-verification.json` 和 `formal-lane-label-1920.jpg`。母stage-acceptance由主对话维护；第3阶段已派发，第4—8阶段等待。本文件前文保留各次交付当时状态。
