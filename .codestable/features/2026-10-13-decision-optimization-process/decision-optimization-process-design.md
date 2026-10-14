---
doc_type: feature-design
feature: decision-optimization-process
status: approved
created: 2026-10-13
roadmap: scheduling-decision-workbench
roadmap_item: decision-optimization-process
requirement: candidate-comparison-business-view
summary: 随候选完成保存真实搜索计数和紧凑进步证据，统一过程阅读、采样覆盖与同源导出
tags: [aps, workbench, optimizer, process, sampling]
---

# 第6阶段：优化过程

## 0. 术语

- 过程成员是独立 `process_candidate_ref`；保存推荐、当前第三查看、当前比较基准和等价复用来源保持各自身份。
- 候选自身耗时与来源优化器耗时分别表示。复用候选的自身搜索计数为0，来源候选的进步轨迹和搜索计数标明原永久引用。
- 评估、接受、严格改善和已记录拒绝是不同计数。接受可包含同分替换；各项按真实记录点累计，解码调用数另列，保存的代表尝试条数表示保留范围。
- 新严格改善与旧含同分的最好解更新分别表示；拒绝理由按真实规范原因累计小字典，导出以有类型的原因／数量行保存数字。公开profile只使用已保存的安全字段。
- 主业务目标来自原 `objective_metric_keys` 第一项及其单位。完整score保持原字段顺序，`failed_ops`承担完成性优先，曲线使用主业务值；未知值保持null。
- 进步事件携当时完整性、已完成批次子集、来源阶段、阶段visit与比较segment。不同目标、完成性或比较阶段分别成段阅读。
- 新过程证据版本与共同52项目录版本分别表达。旧资料使用实际保存的代表尝试与离散轨迹，缺总数、首末或接受/时间时保持缺项。
- 点与代表尝试呈现当时实际目标评价范围；评价内完整性和算法保存统计按原职责展示。旧资料显式未知目标／未知评分策略时，主值与目标评分分量为null，失败工序首项原位保留；已完整批次子集的已知0继续为0。

## 1. 审定范围和约束

第5阶段及第一轮返修已通过主对话独立复验，证据`evidence/decision-stage-acceptance/stage-05-repair-01/`。本阶段按已批准主方案§7.1、§8—10及A12连续实施，复杂度集中于共同采集、采样与三个读取入口。

本阶段完成候选计算来源、实际规则、状态、停止原因、最终保存指标、进步曲线、代表尝试、覆盖说明和同源CSV/XLSX。过程事实随现有artifact完成事务保存，使用现有JSON字段和永久身份。第7阶段历史趋势与第8阶段整体门禁、最终HEAD、clean-worktree和Win7实机按主对话派发推进。选择器、健康规则、排程/采用事务和第0—5阶段有效行为与证据延续。

产品继续Win7 x64、Python3.8、离线单机；图形使用本地SVG及现有React/构建。源头采用实际clock与优化记录点，错误与缺项遵循现有协议。

## 2. 结构

### 2.1 共同事实和读模型

现状：`OptimizationSearchReportState`已记录评估、接受和拒绝，多个`improvement_trace`入口保留前200条，终投影再截前缀；`compact_attempts`按既有排名保存最多12条。`CandidatePlan`由repository逐dataclass字段序列化，与回执在原完成事务落盘。现有42个旧artifact都有report/trace，实际仅1—2点、baseline profile，13个候选为复用。

变化：共同过程collector接真实优化记录点，流式累计计数/阶段摘要，只临时保留有效变化的primitive小事件；候选完成后取真实总耗时T，将除固定锚点外的槽位分为等宽时间桶，取桶末当前最好结果，合并重合事件的标记。首次有效、首次应排完整及最终结果固定保留，artifact每候选最多200点；临时空间随有效事件数变化，完整排程和逐评估列表继续由原求解职责处理。

首次应排完整依据已验证解、实际应排/种子范围、missing/unexpected完整计数与failed_ops；试验性未验证IG结果只按实际工作计数。阶段汇总记录首次开始、最后结束、累计实际耗时、visit和评估/接受/改善/拒绝计数，点保留阶段/segment，沿实际Graph轮转及外层阶段记录。

公开过程使用同一投影：

```text
Process {
  run_ref, capture_ref, scope, baseline,
  candidates[来源/实际规则/自身耗时/状态/停止原因/最终保存指标],
  candidate, source{role: process_anchor, grain, kind, source_candidate_ref,
                    available, evidence_state, evidence_version, profile, rejection_summary},
  objective{name, label, primary_metric_key, primary_metric_label, unit, score_fields},
  summary{own_elapsed_ms, source_solver_elapsed_ms, own_counts, solver_counts,
          saved_attempt_count, retained_point_count, legacy_best_updates,
          rejection_summary, stop_reason, sampling, coverage},
  progress{mode: curve | discrete | none, points <= 200, sampling, coverage},
  stages[], filters, items[], page, process_version
}
```

例：当前查看graph3、基准baseline，展开graph1过程后，scope中的查看/基准保持；`filters.process_candidate_ref`指graph1。graph3复用graph1时，graph3自身耗时/搜索计数另列，progress与attempts每行标graph1永久引用。旧artifact的代表尝试保留原saved_index和真实排名，未保存耗时/accepted为null；report中前12条接受摘要保持独立来源。

定义和影响来源为现有`schedule_optimizer.py`、`optimizer/search_report.py`、`optimizer/search_state.py`、`schedule_candidate_plan.py`、`workbench_run_result_repo.py`、`DecisionSource`及原`decision_export.py`；主业务字段复用`core/models/objective.py`。

### 2.2 编排和共享协议

```text
实际评估/接受/拒绝及Graph阶段
  → 共同collector与最终等宽采样
  → Outcome / CandidatePlan
  → 原候选完成事务artifact及复用永久引用映射
  → candidate_process纯投影
  → decision_process共享selector
  → process GET / 本地SVG与等价表 / CSV及XLSX
```

`GET .../decision/process`沿共同query、envelope及scope/snapshot协议。独立`process_candidate_ref`解析真实成员，allfailed时当前viewer可为空；过程范围是保存的完整候选求解，当前资源窗口用于保留比较上下文。`record_kind=attempts|progress`共用20/50分页，按真实排名、累计毫秒或主目标值排序，null排末、同值用来源引用及原保存索引稳定排序。progress全量最多200点始终供SVG，`items`只返回当前kind页；切kind/anchor/排序更新原leaf并重置相应快照。

新字段缺失的旧artifact原样读取。预启动skip为`source.kind=not_started`，已知零投入证据可查看、曲线为none；已开始预算中断为`budget_skipped`，失败为`failed`，缺完整collector时显示真实状态/原因与null覆盖。自身求解为`own_search`、复用为`reused`；新复用证据指原source，来源搜索与自身投入分别展示。

### 2.3 产品挂载点

- 现有候选表后提供默认折叠的优化过程；候选依据内可打开指定过程成员，打开时按需加载。
- 外层列4/6/8候选来源、规则、耗时、状态、停止及最终保存指标；展开成员显示来源、完整计数、采样、阶段及曲线/代表尝试。
- 本地SVG使用累计求解秒、主业务目标与单位，保留阶段/完整性标记；数值等价表沿progress分页，代表尝试沿attempts分页。最终候选甘特沿既有返回链恢复原第三查看、基准、窗口及过程leaf。
- 点详情、键盘播报和数值行显示实际`objective_scope`：全部评价批次、已完整批次子集、未知或未记录；完整性标签明确为算法评价范围内。原全业务完成性由默认比较入口继续表达。
- 当前过程CSV使用record_kind宽表保留候选摘要、进步点、阶段和代表尝试的来源/数值/单位/null/覆盖；XLSX四个业务grain及口径/范围沿同一selector读取全页。完整XLSX增加四表，普通16表、逐日18表。
- 候选计算grain含`candidate_summary`与`rejection_reason`子记录，后者以规范原因与数字数量展开，身份和来源随行保留。单成员过程导出读取独立anchor；完整导出保存全部同次过程成员。

### 2.4 复杂度和局部整理

采集留在优化器共同state，持久化沿原完成事务，纯归档投影与查询/导出分层。消除本轮实际轨迹入口的前200前缀截断，保留实际选择和旧report语义；采样在共同入口完成。页面只增加process域样式与按需组件，已通过的默认四候选首屏保持原层级。新过程字段承担采集事实，查询无需第二套归档、哈希或独立业务状态。

## 3. 验收契约

| 编号 | 应成立的行为 |
| --- | --- |
| C01 | 超200事件、后半段改善、首次有效/应排完整/final重合与非重合均保持≤200、原值及真实采样覆盖。 |
| C02 | 评估/接受/严格改善/拒绝、解码调用、阶段visit/耗时与完整性来自实际记录，未知主值null，各比较segment语义清楚。 |
| C03 | 新完整artifact沿原完成事务保存；失败、skip和复用身份/自身投入/来源过程准确，旧档不回写。 |
| C04 | 旧代表尝试按原实际保存条数/排名/来源阅读，缺首末时离散，未保存完整计数、耗时及接受情况保持缺项。 |
| C05 | process GET独立anchor、20/50、kind/排序/snapshot及完整返回沿共享协议，第三查看与基准固定。 |
| C06 | 图形和数值表等价，新过程与旧离散来源、阶段/采样可读；两宽浅深及原生缩放、按需加载/取消/切成员/甘特返回通过，默认P5四行保持。 |
| C07 | 原始过程CSV/XLSX及完整导出逐行对应同source/scope，原数、单位、null与采样覆盖相等，原表合同保留。 |
| C08 | 相关Python3.8用例、适用日常及Chrome109离线构建通过；必要的一次隔离新运行有身份、增量归属、旧行/正式v1和34参数保全证据。 |

实际证据优先复用原用例；新增验证集中覆盖采集、上限、锚点、阶段、后半程及旧/失败/skip/复用边界。源码冻结后执行适用检查和一次必要隔离优化运行，参数按原34行恢复。浏览器分页覆盖按真实记录数报告，多页风险由必要API/collector场景锁定。

## 4. 执行和证据

设计和清单在本目录，原始证据统一`evidence/decision-recommendation/phase-06/`。起始实例65050/PID41829，数据库`/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`；旧47批/91工序/11运行/42候选/737任务、正式v1/15行和34参数的9表完整行基线已保存。新事实需要一次既有选批的实际优化运行；新增run及候选/任务单列，旧行与参数逐行保全。

主方案/items、需求、调度与工作台架构、手册、速查按各自职责同步；母`stage-acceptance.md`保持由主对话维护。完成第6阶段后交回独立验收，第7—8阶段等待派发。


## 5. 2026-10-14 已批准的整页接入补充

用户以第二版整页原型批准正式接入并恢复实施。本节覆盖此前默认折叠优化过程和单元格长详情的界面挂载；原真实采集、归档、采样及指标事实继续沿既有职责。原型路径为`/Users/lurenxing/.codex/visualizations/2026/10/12/01a130fb-3ebb-7660-9a39-b2e1eb99e859/aps-decision-prototype.html`，产品从实际运行入口读取，原型内嵌案例与前端演示计算保留在原型。

### 5.1 名词和公共读模型

- 目前查看、固定对照、计算时推荐分别保留真实身份。全部永久候选包含完成、失败、跳过与复用，失败可查看原因且继续禁止作为计算对照或正式采用。
- 交期页按当前实际超期、待料和其他未排组织；差异页按共同工序前后比较筛选。批次完工相同仍检查开工、结束、设备、人员、供应商、来源及排产状态。`delivery_filter`和`selected_batch_ref`读取锚沿同一批次投影，响应`selected_batch`在过滤／分页外保留已选批次，真实`page.total`只计算筛选集合。
- `difference_summary`直接复用三项共同差值和覆盖：超期批次数、拖期工时、已排跨度；零值中性，方向由指标定义决定，缺项保留未知。工序读模型增加双方状态及`changed_fields`，完整当前交付链与变化工序前后两种阅读共用原operations查询。
- 资源使用`grain=hour|shift|day|week`、`pressure_threshold`、小时有效显示窗及可选精确bucket。全部指标来自归档日历和安排区间；实际每资源班段、工时之和／容量之和、日峰值及高负荷时段沿共同投影。资源版本`decision-resource-v4`记录资源旗标和新粒度口径，准备／交付版本维持现行规则。正常零容量休息与班表缺项分开；自然跨度跨非工作窗及保留跨度重叠放详情，班表内安排交集重叠单独说明，实际班外加工缺真实片段时保留缺项。
- 过程公开完整`attempts`与分页`items`共用保存代表尝试；图按同一事件流真实累计毫秒切换已保存指标。完整记录阶梯，采样阶梯明确缺口，旧档离散；标记、悬停和键盘定位真实保存点。`event_index`跳号和被拒尝试造成的segment变化各有原含义，均不据此合成缺失点或重算running-min。
- Job范围复用归档`scope_summary`并提供真实批次业务标识、工序数与保存目标。新运行生命周期时钟保留微秒，旧秒级记录原样；run耗时从保存开始／结束读取，与候选求解耗时分别表达。

### 5.2 编排与共同控件

```text
运行结束 → 共同方案工作台
        → 全候选选择／固定对照／推荐依据
        → 当前交期与未排 | 工序差异 | 资源 | 计算过程
        → 单一全宽选中明细 → 原甘特／预检／采用 → 完整阅读上下文返回
运行中／失败 → 同一Job范围、实际状态、已耗时、具体原因及下一操作
```

准备、切换、全部指标、完整批次工序安排、正式对照、原始导出及两类甘特继续保留。日期、下拉框、数值与键盘交互复用原工作台入口；工厂本地范围使用`data-picker-type="factory-local"`并保留原微秒。资源小时页的实效显示窗绑定筛选和快照，导出去掉纯分页后仍读取同一窗口；精确bucket导出保留独立时段身份。

### 5.3 必要验证与完成边界

复用454f运行DC-02批末相同但首道开工改变、DP-STAGE未知交付但已安排工序改变；7736原算法4/4及其他6/7采样；既有6／8候选运行的复用身份。失败／跳过用现有受控夹具，不为排版重新生成现场数据。验证四粒度、真实班表与夜休、设备／人员、切候选与对照、选中保留、全宽详情、过程真实点、公共控件精度和必要原件同源。纯样式不新增测试，关键新行为补入现有有效用例；完整门禁及最终HEAD仍归第8阶段。当前母stage-acceptance与Git由主对话维护。

用户随后明确要求先生成四套策略、实际结果不同的样例再检查。本轮在原独立验收库增加一组必要真实业务样例及实际排产，配置沿产品候选生成入口，输出由真实求解和完成事务保存。先在私有临时库确认差异场景，再运行正式验收样例；四套原安排按工序、时间与资源逐项区分，切换、推荐、交期、资源及原件验证使用该运行。原1249行及34参数、正式v1原值保全，新样例／新运行单列；7736同结果记录仅覆盖无变化与真实过程采样。DP-STAGE的08:00／13:15变化采用原算法对照graph1，graph1对graph2没有该工序变化，按实际保存记录分别核对。

### 5.4 候选卡信息层级与实际不同结果

候选卡分别承载名称、固定对照／计算推荐身份、指标和操作区；当前查看沿选中边框及 `aria-pressed` 表达。公共 `C.Button` 的真实外层 `.wb-button-host` 参与卡片纵向伸展，名称和身份行按现行字体及胶囊尺寸布局，指标与操作区在同排卡片中对齐。完整覆盖、失败原因、复用来源和指标依据保留在既有保存依据入口。

指标完整时显示原值；整体未知且存在已知成员和保存小计时，用“已知超期／已知拖期”显示该小计，待确认提示在同卡集中表达。全部未知保持未知，已知零保持零；展开依据继续提供完整覆盖和缺项。推荐默认给一项真实收益和一项代价，完整保存主因、目标、规则、容差及全部差值放在原“完整推荐依据”。三项差异摘要归属差异页签。

真实验收运行 `ac9ca5c1428c9b76b12b120abc9e5d1daf1a63df8e7354db` 来自 DQ4- 的12批／48工序、3设备／3人员交叉能力及停机条件；原算法和三档图权重 `(90,0,1)`、`(180,0,1)`、`(270,0,2)` 均完成48道工序且无复用。六对安排逐项比较的变化工序数为48／48／48／12／24／32。累计拖期1587／2090／2092／2112小时，总跨度293.5／265／265／265小时；准备24小时、加工144小时是四方案共同的真实需求。原算法在本样例中拖期较少，三档重点工序方案跨度较短，页面与导出按各自真实指标表达取舍。

本轮追加一组样例和两次真实受理：首次因维护机Python3.8缺少已规定的 `networkx==3.1` 失败，补齐该依赖后第二次完成；首次失败归档保留。配置34行／170字段逐值恢复，新增样例／运行与原记录分开核验；正式采用0次。源头原件和逐对证明见 `evidence/prototype-integration/2026-10-14/four-different-strategies/`。

### 5.5 母验收六项增量返修

- 资源格的数值、颜色、告警、title及ARIA共同消费`cellPresentation`：固定对照取before、当前方案取after，差值分别标出双方来源；明确成立的告警显示在主格，未知依据保留在title／ARIA及原详情／范围说明，原null值保持。
- 无已保存严格改善时固定展示全过程，改善聚焦按钮显示“无改善记录”并禁用，首末真实保存点保留。
- 保存点新增可选`evaluation_scope.incomplete_batch_ids`，内容为真实未排齐批次业务编号；完整集合为`[]`；旧已保存`all_batches`且未排齐批次数0时，共同投影规范化同一已知空集合，部分覆盖缺真实成员／未知时为`null`。同来源、目标范围、完成性及精确评价成员才能连线；搜索阶段、访问或segment变化按原事件说明，真实同成员继续连续。成员变化独立标记，部分旧记录的身份缺项保留点与可见说明。共同投影和CSV/XLSX沿保存字段读取。
- 部分班表的已知保留跨度与工作／非工作窗口沿同一`IntervalIndex`求交，累计精确区间后换算小时；6分钟／42分钟／缺班表一天的最小场景得到已知占用0.8小时、已知班表外跨度0，未知总量保持未知。
- 共同资源出口保证各业务表表头唯一：整窗日峰列仅一组，真实时段占用比例与该日峰分别命名、输出对应原值；跨夜真实场景的43.75%／50%分别保留。宿主原件oracle按当前v4字段、单位及附表同步。
- 关闭资源时段详情恢复原资源与bucket格焦点；原格离开DOM时回到同资源入口。复用原查询上下文和DOM，恢复焦点后清除明细查询，保持键盘后续移动。

六项均在现有共同职责与既有测试函数内完成，新增测试文件／函数0；受影响页面、原生CSV/XLSX、必要正常cold和日常门禁已完成，最后旧全集兼容与密度由相关节点、Node及四项实际回验补充；实施及母验收passed，第7已恢复先前派发；母验收记录继续由主对话维护。
