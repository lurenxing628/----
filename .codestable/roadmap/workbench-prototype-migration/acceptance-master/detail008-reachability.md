---
doc_type: explore
type: question
date: 2026-09-10
status: evidence_ready
capability_id: WBP-DETAIL-008
decision_owner: Main
proposed_resolution: needs_main_scope_decision
confirmed_ui_reachability: legacy_batch_via_existing_native_form
production_verification: not_run
confidence: high_for_reproduced_counterexample
---

# DETAIL-008 原型可达性证据

## 结论

**发现真实 UI 可达反例，不能作 `not_applicable_confirmed_unreachable` 决定。** 在同一份冻结原型中，从“基础资料 → 物料 → 新增物料”，用现有表单填入物料编号 `B202605-018` 并保存，再点击新行编号，就会进入统一详情中的旧 batch 记录及其页脚。

此前从初始样例行出发的 15 入口及详情关联检查没有达到目标，但这不足以覆盖“现有表单可新增编号”的状态。最初不可达建议在补查此分支后撤回；原始取证文件保留，不覆盖历史结果。

- 已找到真实入口，按要求停止继续扩展验证，交回 Main 决定是排除这个类型串用的错误入口，还是另定所需语义。本报告不建议据此补造旧业务界面。
- 保留 `WBP-DETAIL-008` 这 1 个能力族及独立决定，不删除 ID，不并入 205 项通过数。旧方案、generic 是否也可经其他状态到达，本轮不再继续穷举，也不宣称已验证。
- 本报告没有修改 `workbench-capabilities.json` 或 `acceptance-planning/`。清单原有 `needs_reachability_decision` 状态仍由 Main 单独处理。
- 没有补造旧样例界面，没有直接调用 `APSDetail.open`，没有把当前 BATCH 详情或当前计划工序详情误算成旧统一详情。
- 这是原型可达性证据，不是生产 B/K/V/P 验收，不扩大为所有潜在页面、任意代码注入或后续版本永久不可达。

## 已复现的真实路径

最新正例证据目录：

`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-BkBzFJ`

1. 从原始 index 的真实侧栏点击“基础资料”，再点击“物料”。
2. 点击现有“新增物料”。通过真实键盘输入编号 `B202605-018`、名称 `DETAIL008 reachability probe`。
3. 点击“保存并加入列表”。此时只在隔离的原型页面 DOM 中增加 1 行，原型提示“示例数据，刷新后恢复”。
4. 点击该行实际显示的 `B202605-018` 链接，打开的抽屉类型为 **batch**，标题“生产批次”，内容为旧样例的回转壳体 A、12 件、05-24 12:00、工序进度 30 / 60。
5. 实际页脚显示“在甘特图中定位此批次”和“查看延期说明”。到此已命中目标，未继续点页脚或扩展其他类别。

这是现有按钮、表单、保存和编号链接组成的 UI 路径，不是调用隐藏 API 或人为注入 DOM。测试没有直接调用 `APSDetail.open`，没有创建新界面；临时行由原型已有 `showFormModal` 自己生成。

- [真实输入、保存、新行和旧批次抽屉记录](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-BkBzFJ/reachability.json)
- [旧批次抽屉和物料页同屏证据](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-BkBzFJ/screenshots/FOUND-batch-through-native-form.png)

根因链：`plana-logic.js:1483` 的物料编号是普通输入；`:1752` 只校验非空，`:1756` 调用 `addRowToTable(buildRow(entity, vals))`；`:1533` 的 buildRow 把编号生成通用 `a.lnk`；`:1916` 点击仅检查全局 `APSDetail.has(code)`，没有把物料和 batch 的记录类型隔离。`B202605-018` 已存在于全局 RECORDS，因此被当作旧批次打开。这是原型类型串用，不证明生产环境存在相同问题。

本次正例于 `2026-09-10T15:30:42Z` 至 `15:30:44Z` 完成，7 个 click 事件全部 trusted，另外记录 2 次真实键盘输入。浏览器与只读 HTTP 服务正常关闭；原型 539 文件和冻结规划前后完全相同；无外部请求和浏览器错误。没有写入任何生产数据。

## 初始样例检查

作为背景保留的完整 15 入口证据目录：

`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt`

运行时间为 `2026-09-10T15:25:23Z` 至 `15:26:02Z`，Chromium `109.0.5414.46`，1392×900、浅色、新建隔离 context。通过真实鼠标点击导航和关联链接，未模拟业务 API。

| 检查范围 | 实测结果 |
| --- | --- |
| 主路由 | dashboard、gantt、run、analysis、delay、review、reports、calib、batches、process、field、fieldgantt、basedata、system 全部实际打开；delay 经 analysis 的“交付风险”进入 |
| 独立入口 | 从真实侧栏链接进入 trial-sample.html；其页面没有 APSDetail API |
| 基础资料 | 实际点击工艺、物料、自制工种、设备、人员、外协工种、供应商、日历 8 个节点 |
| 校准入口 | 实际点击 5 行图号链接；只有 P-1042、T-1009、T-1021 三个不同图号，全部是已有 part 记录 |
| 统一详情入口 | 29 个不同直接记录；含关联点击后的闭包为 31 个记录，只有 material、part、op_int、op_ext、equip、people、supplier 7 类 |
| 嵌套关联 | 从初始行可达的详情中，对 21 条不同关联边逐条实际点击；这些关联目标没有继续进入 batch/plan/generic 的链接 |
| 抽屉记录 | 保存 79 次渲染观测，包含关联后重新打开父记录，不代表 79 个能力或不同记录 |
| 当前批次详情 | 点击 B202605-018、-021、-011、-024、-017，全部进入当前 BatchDetail；统一抽屉数量始终为 0 |
| 当前方案 | 实际点击“基准方案 / 均衡方案 / 交付优先”3 个选项，再经“查看此方案甘特”点击 8 个工序；全部使用当前方案界面，未打开旧统一详情 |
| 输入和截图 | 196 条操作记录；离开 index 前保存的 195 个 click 事件全部 isTrusted=true，最后一条为进入 trial 的真实链接点击；25 张截图 |

可直接查看：

- [真实点击与 DOM 结果](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/reachability.json)
- [当前批次详情截图](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/screenshots/current-batch-B202605-018.png)
- [真实统一工种详情截图](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/screenshots/drawer-op_int.png)
- [当前计划工序详情截图](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/screenshots/current-plan-operation.png)

## 静态闭环

不能只搜索当前 JSX 是否引用旧详情。原型先加载 `_ds_bundle.js`，其中确实仍有旧页面和旧详情代码，本轮已一起核查。

| 证据 | 对可达性的意义 |
| --- | --- |
| `前端设计/ui_kits/workbench/app.jsx:85`、`AppShell.jsx:27` | 当前 switch 挂载 14 个页面，侧栏另有 trial；没有挂载 BasicDataScreen 或 BaseDataScreen |
| `前端设计/ui_kits/workbench/index.html:309`、`:346` | 先加载 bundle，再加载当前 JSX；“脚本被加载”不能替代“页面实际挂载” |
| `前端设计/_ds_bundle.js:16223` | AST 提取的 open 函数原文 SHA 与浏览器实际函数 SHA 完全一致：d8345c32376b72e054045c2ab00f681c58daf05c568c8ef76072c599eecf2868。实际统一详情实现来自 bundle，不是后载 detail-drawer.js 的重定义 |
| `前端设计/ui_kits/workbench/detail-drawer.js:7` | 已有 APSDetail 时直接返回，与上述运行时来源吻合；浏览器记录图据实际加载的 RECORDS 提取 |
| `前端设计/ui_kits/workbench/CalibScreen.jsx:12`、`:47` | 活动的无 has 前置检查入口只有固定 5 行中的 3 个图号；全都在 RECORDS，搜索和采纳标记不会引入新图号 |
| `前端设计/ui_kits/workbench/plana-logic.js:1910` | 活动的编号、行按钮入口均先检查 APSDetail.has；这只限制编号存在，不限制实体类型，正是物料编号串入旧 batch 的路径 |
| `前端设计/ui_kits/workbench/BasicDataScreen.jsx:150` | 此文件有旧入口，但只被加载和导出，没有当前挂载链；不能凭函数存在将它算作可达 |
| `前端设计/ui_kits/workbench/BaseBatches.jsx:170`、`:447` | 当前批次按钮调用本地 openDetail → BatchDetail，未调用 APSDetail；与 5 个真实批次点击一致 |
| `前端设计/ui_kits/workbench/AnalysisScreen.jsx:14`、`GanttBoard.jsx:28` | 当前方案选择、查看甘特、工序点击走当前计划状态及内嵌详情，不进入旧方案 RECORDS |
| `前端设计/_ds_bundle.js:16198`、`:16213`、`:16261` | 嵌套链接只能 render 已有 RECORDS；页脚只有旧批次“定位”向外导航，其余为 toast；genericRecord 只在 open 找不到记录时建立 |

已校验全部实际加载脚本的源 SHA，再用原型自带 Babel AST 提取调用点。5 个含 APSDetail 的已加载源文件共 17 个 open 调用点：bundle 12 个、当前 plana-logic 2 个、未挂载 BasicDataScreen 2 个、当前 CalibScreen 1 个。旧 bundle 的页面函数被当前 JSX 覆盖；实际函数文本及当前 DOM 已保存，未把旧 bundle 调用点当成现行页面入口。

实际 RECORDS 共 57 条、38 条有向关联边。仅在这个记录间链接图中，进入旧 batch/plan 的边为 **0**；初始行闭包内的 21 条边已全部真实点击。**该有限图没有覆盖新增表单生成的新 UI 根，因此不能据此推导整体不可达。** 图提取仅将纯 body 字符串展开到 detached DOM，明确属于静态图证据，不记为真实 UI 打开。

- [AST 调用点及实际详情函数来源](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/static-call-evidence.json)
- [浏览器实际页面函数文本](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-detail008-prototype-AgSqWt/runtime-functions.json)

## 保留与边界

- 只读快照包含原型 539 个文件、35,252,995 字节，逐文件保存 SHA/bytes/mode；HTTP 只从捕获字节提供 GET/HEAD，不访问生产 host/DB，未使用原有 53144 预览。
- 实际加载 101 个不同资源，全部返回 200，无外部请求；浏览器 pageerror/console error 为 0。
- **不掩盖 bundle 原有异常**：`APSDesignSystem_edbc5d.__errors` 保留 1 条 `app.jsx: createRoot(...): Target container is not a DOM element.`。bundle 在 head 内尝试启动旧 App，此时 body 的 root 尚未出现；后续当前 App 正常挂载。本次未修该原型问题。
- 原型全量前后 `source_changes=[]`；冻结规划及 206 能力族清单前后完全相同。清单 SHA 为 `0cad8e05a5adbadacf0c2ecef1e56f38bb4c97e6948c1dc5a2fc847bcec1ffb2`，845,275 字节。
- 浏览器及临时只读服务均已正常关闭，四轮 browser probe 命令全部结束；没有提交、暂存、修改产品或冻结规划。正例只有隔离浏览器中的 1 条临时原型 DOM 行，不冒充初始数据完全只读检查。
- 先行 inventory 根 `aps-detail008-prototype-2LJHOO` 与首轮点击根 `aps-detail008-prototype-jW6BQa` 原样保留。后一轮仅补了等待 CSS 动画自然结束的截图时机；原半透明中间帧截图和原始结果未覆盖。
- 本次没有运行生产全门禁，也不是 clean-HEAD proof。此前 C 的 ProcessTable 修复全应用 28/28、44 个缩放合同结果仍单独保留，未被本报告重新计算或扩大。

关键证据 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| BkBzFJ/reachability.json，真实可达正例 | 1d5d116424eb8986462dcd2ac10a5152476cb7915909119374494c29bf796eae |
| reachability.json | 6fe1a0fd819e42ef1029858e049082d9c58d9cf6346307925a9d1c11594d93e0 |
| static-call-evidence.json | 687ab8469fbc90edd8a5c0b9a300f4cdcd0562ae03ffa9c4007a28c220718386 |
| source-before.json | c67c486bc453a45f72aec4cda65c58da845ecba4d295c5b02fede6f2507b3692 |
| runtime-functions.json | 86228e9bdcdfda89f262ccc9fdda9b78d7d6d7b14eb27c50681587ffed2b4536 |
| planning-before.json | 94e8d1a626fe71536524b33ca051c15edeaf89fd28924198fe5c2ad6ac76d58a |

复跑脚本为 `tests/workbench/detail008_prototype_probe.cjs`，支持模块为 `detail008_prototype_support.cjs`、`detail008_prototype_links.cjs`；需要现有 Playwright 与 Chromium 109 路径。用 `DETAIL008_CASE=code-collision` 运行最新正例，遇到实际旧 batch 抽屉即停止。默认模式保留初始样例的完整 15 入口检查，该模式打印目录后可运行 `node tests/workbench/detail008_prototype_static.cjs <目录>`。四个 CJS 均通过 Node 语法检查；正例 browser probe、初始完整 browser probe 和静态 probe 均 exit 0。
