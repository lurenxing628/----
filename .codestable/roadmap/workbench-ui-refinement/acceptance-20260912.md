# 工作台界面整改统一验收

日期：2026-09-12。当前状态：21 项实现完成，最终浏览器矩阵与每日门禁通过。原完整门禁仅有一处旧测试显示预期失败，修正后完整受影响模块通过；按用户明确要求不再为此重跑完整门禁。本记录保留这一验证限制，不宣称完整门禁全绿或 clean-worktree proof。

统一结果见 [最终验证事实](../../../evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json)；仓库相对路径为 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。界面效果见 [截图索引](../../../evidence/workbench-ui/2026-09-12-final/visual-index.md)。

## 1. 接口契约

实施采用 [已批准的合同修订](implementation-20260912.md)。导航保留15个支持视图及原URL/context，侧栏收为12项；分页档位仍来自领域API，游标不虚构总数；显示格式不新增业务范围约束。带时区时刻与工厂本地文本分开处理，缺失、零和非法值保持不同含义。

共享构建顺序显式登记CSS与脚本依赖：核心守卫和Modal宿主拆分，Controls/ListControls按真实依赖加载。完整原型导入快照保持可追溯；清理只删除已证明无创建者或被同条件后置声明覆盖的旧规则，未按截图未出现就认定源码无用。

## 2. 行为与决策

- 长表在有高度预算的区域内部滚动，表头、关键列及操作列保持可用；舒适/紧凑只调整间距。
- 字段错误、加载/空态、分页、详情与禁用说明走共享组件。详情聚焦与关闭返回、只读自动预览不抢焦点分别处理。
- 编辑器、页面导航、前进后退与外部离开共用草稿守卫；待核实命令仍由原请求链保护，拒绝离开时保留URL与输入。
- 正式计划只在没有明确来源时默认选择。正式与候选目录可收起；候选切换后的焦点归还展开入口，初始进入不抢焦点。
- 实际甘特按时间中心和可见时长恢复位置；刷新读取期间改变宽度也保留位置。命中区域可扩大，原时间与点工序不变。
- 报工建议可清空，仅用于新建；复制上一条限制来源与字段。保存继续受成功回执和新的可写上下文共同约束。
- 三步排产、耗时、参数变化失效提示、唯一主操作与系统状态说明已接入。系统诊断默认收起，读取失败保留明确错误及既有维护保护。

各项源文件、挂载点、消费者和局部证据见21个同名 feature 的 design/checklist/acceptance。共同架构已归并到 [workbench-shell](../../architecture/workbench-shell.md)，没有把新能力只留在分支说明中。

## 3. 验收场景与证据

当前产品构建：`e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043`，目标Chrome109，258个发布文件、350个构建输入。6cf构建修正窄屏外壳；末次e696构建补齐7个JSX文件中的8处统一格式显示入口，不改变时间坐标、统计计算、DTO或保存数据。最终浏览器矩阵、原完整门禁及每日门禁均绑定这个产品构建；原完整门禁之后只改变了一个测试文件，产品未改变。

以下各行是不同范围的实际执行结果，不相加冒充去重测试数：

| 范围 | 已完成结果 | 证据 |
| --- | --- | --- |
| 最终e696全站矩阵与显式UI门禁 | 60页面、8交互、4密度全部通过，零错误、零几何失败、零UI豁免；每日门禁末步再次核验通过 | `evidence/workbench-ui/2026-09-12-final/browser-e696/verification.json` |
| 最终每日门禁 | 6步实际通过，exit0；并行11488 passed、串行746 passed、专项5 passed；三组是各自执行范围，不作去重总数 | `evidence/workbench-ui/2026-09-12-final/gate-e696-r2-daily/result.json` |
| 已完成的e696完整门禁 | 16503 collected，16491 passed、1 failed、11 skipped；唯一失败为系统维护KB旧显示预期；第18步退出2，未签发完整门禁通过 | `evidence/workbench-ui/2026-09-12-final/gate-e696-first-complete/QualityGate/current_full_test_debt.json` |
| 唯一失败修正后的完整受影响模块 | 1 passed，7.20秒；37真实动作，实际1306624字节显示为1,276.0 KB；16份DB/备份哈希未变，无HTTP写入；原始311文件已归档并核对SHA | `evidence/workbench-ui/2026-09-12-final/gate-failure-closures/maintenance-size-oracle/index.json` |
| 18bc构建全站矩阵与显式UI门禁 | 60页面、8交互、4密度；零几何失败、零浏览器错误、零豁免，源码与350输入绑定通过；保留为上一构建证据 | `evidence/workbench-ui/2026-09-12-final/browser-release/verification.json` |
| 密度入口与刷新 | 真实Chrome109顶栏/系统双向切换，舒适与紧凑均刷新保留；纯模块的存储异常和事件合同通过 | `density-entry-18bc/report.json`、`contracts-18bc.json` |
| 现场去重与完整报工 | 1 passed，37.16秒；13初始动作、5重启动作、41图和4份导出，7个筛选计数保留，仅4张许可表变化 | `final-regressions/field-noise-final-v2.log`、`final-regressions/final-browser-proof.json` |
| 完整报表 | 17 passed；52个初始/重启场景、56导出、108图，报表页签上下文与真实滚动恢复通过；绑定be2b报表同源构建 | `final-regressions/final-execution-adapt-summary.json` |
| 系统维护与恢复 | 34 passed；4个正常流程变体各201动作/4真实下载，旧令牌拒绝和数据保留断言保留 | `final-regressions/final-operations.json` |
| 规划完整流程 | 4 passed，248.34秒；每组125业务动作+9重启动作，77表oracle无差异，正式v5/v6、13安排及前序30核对通过 | `final-planning/full-planning-final-evidence.json` |
| 整壳排产 | 1 passed，356.34秒；4组原尺寸主题、20份导出；额外1366×768/1280×720浅深色首屏全部通过 | `evidence/workbench-ui/2026-09-12-final/run-presentation/` |
| 候选目录与完整候选 | 1 passed，401.09秒；232原动作、20目录/焦点断言、24导出、12组5000工序容量，源码/CSS与业务数据保留检查通过 | `evidence/workbench-ui/2026-09-12-final/run-candidate/` |
| 实际甘特 | 真实主壳2项通过，含改变宽度、重载、延迟真实读取期间缩放、报工点与返回；另有65标记键盘合同及原实际甘特回归 | `actual-final-point-v4.log`、`actual-keyboard/` |
| 工艺与试调 | 三个测试文件合计5 passed，422.64秒；真实交互、导出与源码绑定通过 | `process-trial-final.log`、`domains/` |
| 运行计算容量 | 5000工序、4候选与20000候选任务通过，原先300秒超时未再出现 | `domains/aps-run-job-widgets-8enijucn/` |
| 导航与共同合同 | 56 passed，70.76秒；含页签修饰键、真实草稿后退、历史、密度、证据拒绝规则及opt-in | `final54-contracts.log` |
| 甘特/资源派工旧夹具 | 334 passed，83.69秒；真实共享依赖、可见诊断、未知语义和几何断言已适配 | `gantt-fixture-targeted-result.txt` |
| 构建依赖 | 5 passed，9.90秒；严格依赖列表与GuardCore/Host边界保持 | `tests/workbench/test_foundation_dependency_scope.py` |
| 窄屏外壳修复 | 390px从侧栏240px、页面492px、时间图区0恢复为侧栏56px、页面390px、时间图区187px；夹具与正式main各6组390/768/1280浅深色均通过；样式合同54 passed | `evidence/workbench-ui/2026-09-12-final/gate-failure-closures/narrow-shell/` |
| 完整明白话交互 | 6cf构建1 passed，10.75秒；56场景、12图，桌面/390px浅深色全部真实pointer，8次精确task_ref/plan_ref/读取范围检查通过 | `evidence/workbench-ui/2026-09-12-final/gate-failure-closures/resources/` |
| 资源编辑与详情旧回归 | 18bc构建资源live224场景、464图、108下载通过；19表中仅预期新增280唯一回执，其余18表相同；详情24场景通过 | `evidence/workbench-ui/2026-09-12-final/gate-failure-closures/resources/index.json` |
| 6cf全站矩阵 | 60页面、8交互、4密度，显式UI门禁通过，无失败、错误或源码漂移；保留为末次格式补齐前的证据 | `evidence/workbench-ui/2026-09-12-final/browser-6cf/verification.json` |
| 格式消费者末次补齐 | 8处接入已闭合；甘特23显示案例/1 pytest通过，系统98场景/1 pytest通过；43构建依赖与共享合同、6登记覆盖通过；Calendar/PICKER等按明确输入精度和原文边界保留 | `evidence/workbench-ui/2026-09-12-final/format-consumer-closure/root-disposition.json` |

首轮54c40205构建的60页面、8交互和4密度矩阵曾零失败；之后发现并修复实际甘特交叉恢复、候选目录首屏和深色数量对比度，之后又修正报表页签返回上下文、计划初始任务恢复生命周期，并移除现场重复统计。18bc与6cf矩阵继续保留原build绑定，最终结果由e696矩阵覆盖。主线程已查看正式计划、候选、实际甘特、批次等关键截图，并查看e696正式甘特深色及报表浅色截图，记录在`current-visual-review.json`；末次窄屏修复还分别验证真实主入口与组件夹具，未用键盘或强制点击替代被遮挡的鼠标操作。

## 4. 术语与数据保留

当前正式、候选、试调、超期、总拖期等标签使用共同术语。内部引用默认收纳，展开后仍可核对完整原值。默认错误不暴露技术内容的测试同时检查诊断原文仍保留，避免靠删除数据通过。报表无现场数据、部分缺失和数字0分别呈现；具体领域数据与回执证明保留在各feature和原始JSON中。

## 5. 架构归并

[工作台架构](../../architecture/workbench-shell.md) 已写入样式层与manifest、共享格式和控件、密度、草稿守卫、计划选择/实际窗口和报工继续流程。挂载点可由build-order及各消费者反向定位；应用层无遗留运行时静态style注入。

## 6. 需求与用户指南

已更新 [工作台业务流程](../../requirements/workbench-production-workflows.md)、[只读甘特](../../requirements/gantt-readonly-result-view.md)、[现场报工](../../requirements/shop-floor-execution-feedback.md) 的相应用户故事及变更日志。`scheduler-daily-workbench` 的风险目标、计算和回跳故事未改变，通用UI变更归入工作台主需求。用户手册已加入导航、密度、目录折叠、草稿保护、报工建议和保存继续的使用说明。

## 7. 路线图状态

21份design/checklist/acceptance均已建立，实现项完成。e696最终矩阵、每日门禁及唯一失败的定向复测已经通过；完整门禁保留原运行的1项失败与不再重跑的用户决定。路线图按本次实施范围收尾，涉及完整门禁全绿的清单不伪改为passed，明确登记其验证限制与关闭重跑要求。

最终清单为64个实现步骤done、51个验收检查passed；另外15条清单记录保留pending并标记`closed_per_user: true`。这15条引用的是同一个“未重跑最后全量门禁”的验证限制，不代表15个未修复的产品问题。

## 8. 门禁与工作区边界

原工作区包含预先已有的调度优化改动及新增测试；未改写原暂存区、未提交。完整门禁在只包含本轮UI及必要门禁辅助修复的隔离副本执行`--allow-dirty-worktree`。首轮期间进行了末次源同步，记录于`final-gate-source-update-full.json`，该轮不能作为冻结快照或clean-worktree proof。

广域daily首轮为28 failed、11834 passed；失败已分流到共享夹具、依赖预期、UI登记、旧迁移漏登记以及原工作区tracked/其他优化改动边界。UI相关夹具已修复并分组通过；末次规划流程补验收口后重新冻结并执行完整门禁，未把中断轮次报为通过。门禁输出规范化的二次方正则回溯已作最小修复并通过46项测试；门禁标准保持不变。

首个完整full-suite实际收集16489项，16451 passed、27 failed、11 skipped；其完整失败记录保留在`gate-first-complete-attempt/`。后续运行在已知失败未关闭时停止，不能作为通过证据。随后先修复全部27个原失败并完成针对性复测，再准备末次统一门禁：26项有现存JUnit逐节点回执，导航模块另有执行结果记录（28 passed，原始日志未单独保存）。不同测试轮次、混合失败轮次、18bc与6cf的构建绑定均在`gate-failure-closures/`中明确区分；这些局部结果不拼接为全仓通过。

6cf轮前17项通过后，验收清单发现格式消费者静态复核尚未闭合，主线程主动停止全量段（exit130），记录保留在`gate-6cf-interrupted/`。随后完成限定静态复核、补齐8处显示并验证，才准备e696末次冻结；不把这次中断升级为完整通过。

e696完整轮于21:47:05至22:43:14实际跑完，16503项中仅`test_final_operations_real_cleanup_and_maintenance_read_controls`失败：其旧断言期待不带千位分组的KB，而已批准的产品显示带分组。随后仅修改`tests/workbench/final_operations_read_controls.cjs`，保持原真实读取、回执和数据断言，完整对应模块1 passed。698路径的前后快照对比证明，仅此测试文件变化；350构建输入和258资产全部不变。之后每日门禁于23:06:59实际完成通过，前后快照无漂移。

用户明确要求不因这一处已修复的小问题再花约一小时重跑完整门禁。遵从该决定，没有启动新一轮完整门禁；验收采用原完整结果、完整受影响模块复测、最终UI矩阵与已运行的每日门禁。此决定仅适用于本轮收尾，不修改项目门禁规则，也不把失败轮次或不同快照的局部结果拼接成完整门禁通过。

## 9. 遗留与范围

本轮产品实现及已发现问题已完成；完整浏览器矩阵、带UI选项的daily入口和定向修复验证均通过。验证限制只有：修正最后一处测试预期后没有重跑完整门禁，因此没有最终全绿full或clean-worktree proof。Win7实体机、打包发布、旧界面退役及其他调度优化任务由各自流程承担，本次不替它们签发验收。原工作区未提交，其他算法改动保留；门禁后仅回填验收文档，不再改产品、测试或构建产物。
