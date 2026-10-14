---
doc_type: feature-acceptance
feature: decision-resource-impact
status: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第3阶段共同资源计算、设备人员明细、热力图、甘特往返、导出与旧消费者实施及主对话独立验收通过
tags: [aps, workbench, resource, candidate-comparison]
---

# 第3阶段实施验收

**第3阶段实施和主对话独立验收通过。** 共同归档日历、固定资源集合、两种视角、设备／人员资源表、逐日热力图、压力和冲突、甘特往返及旧同义消费者均已实现。相关回归、日常检查、最终原始导出及真实浏览器验证通过。主对话未新增返修项，已派发第4阶段，第5—8阶段等待。

依据为 [设计](decision-resource-impact-design.md) 与 [执行清单](decision-resource-impact-checklist.yaml)，实际文件范围、实例和直接复核入口见 [交接](decision-resource-impact-handoff.md)。本轮继续未提交工作区的第0—2阶段实现。

## 1. 接口契约核对

- decision共同query增加 `resource_view=selected_batches|full_candidate`，scope包含同次全部候选与基准的固定永久设备／人员集合。窗口为工厂本地左闭右开；切换同次查看候选及基准保持分母。
- `GET .../decision/resources` 提供设备或人员的整窗双方明细、完整集合汇总、覆盖、压力／增长Top10和当前资源页的逐日热力图。筛选支持资源、压力状态，排序稳定、未知末尾，资源页为20／50行；热力图日期页为7／14／31天。
- `GET .../decision/resource-days` 明确指定单资源，日期升序20／50分页，保留整窗汇总，实际任务和冲突携带永久工序、行身份与甘特定位。
- 总览42项指标包含24项共同资源指标；共同业务指标、原算法保存统计各自保留来源。快照绑定视角、窗口、资源集合和业务筛选；列表／日期页只控制显示。
- 单资源逐日仅计算目标资源两侧。归档、索引和日历按请求复用；原总览、批次、工序和导出沿同一scope。
- CSV支持资源及单资源逐日，XLSX完整比较为7表，逐日入口为9表。数量为原生数字，覆盖和冲突成员分别逐条保存在“覆盖工序”“资源冲突”；所有工作表保持同一身份及范围。
- URL按现行白名单校验，顶层 `view=analysis` 与 `nav.view=analysis` 对齐。[四条入口核对](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/link-verification.json)已通过。

## 2. 行为与决策核对

- 归档日历工厂适配保存Schema、全局／个人日历、轮班、停机、资源状态和永久身份，复用领域日历引擎。夜班包含前日尾段；默认规则按保存版本解释。当前资料变化不回填历史。
- 可用容量为窗口并集；班内占用为安排与容量窗口交集并集；独立工序先合并重复片段再求累计需求。班外、重复负荷、实际并发时段和冲突成员各有对应字段；零时点事件不占资源。
- 日峰与任一日90%高压力覆盖完整窗口。已知0容量与unknown分开；零容量有安排保留true／null／false。缺比较对象的占用／需求为null，独立已知容量仍显示；已知空安排为0。
- 固定集合包含正容量空闲0；汇总按容量加权，CV包含全部正容量完整资源。已知自然日小计可进入已知比率；工作不完整的下界不进入CV，整窗均值0时CV不适用。
- `selected_batches` 表达本次贡献，`full_candidate` 表达候选自身全部安排。正式覆盖与采用预检共用集合规则，正式缺口、普通未排和合法待料分别呈现；缺基准时其覆盖待确认，导出跳过不存在的基准侧。
- 候选分析／比较、值班台和试调同义读取已迁移共同规则。旧墙钟并集、独立工序跨度和实际并发别名保留原语义；共同班内字段和 `decision-resource-v3`／`available_occupancy_v1` 明确来源。当前值班台为 `current_transaction_snapshot`，历史为 `archived_resource_calendar`。
- 已实际检索路由注册、build-order、主候选组件、URL白名单、采用预检和旧消费者挂载。拔除推演：资源路由和新组件控制新增查询／展示；共同日历与计量属于共享规则，已被旧候选、值班台、试调消费。撤回单个页签须保留这些共同职责及已迁移调用关系。正式采用事务沿既有入口。

## 3. 验收场景与实际证据

| 场景 | 状态 | 实际证据 |
| --- | --- | --- |
| C01 固定集合、共同窗口、空闲0与加权CV | passed | 真实4候选各11设备／2人员，容量185.5／31.5h，独立核对260个资源单元；同次切换、Top10展开、20／50同快照一致。旧8候选窄窗证明有容量未使用为0；核心回归锁定跨日、相接、重复及不同容量权重。 |
| C02 保存日历、夜班、零与未知 | passed | 7项归档日历回归包含旧／新Schema、全局、个人、轮班、停机、夜班、局部损坏、永久身份及当前修改后只读归档；真实轮班／个人／停机容量已独立核对。真实旧8候选2个0容量窗口的6个空比率均显示“不适用（零容量）”。 |
| C03 需求、占用、冲突、班外、日峰 | passed | 14项资源内核回归覆盖独立工序并集、负荷、重叠、班外、零时点、日裁剪、日峰／90%压力及unknown小计。真实260格与归档区间独立计算一致；实际引擎场景重叠为0。临时SQLite／API回归核对真实重叠区间；XLSX写入边界另以3成员×2侧核对6条明细。 |
| C04 两视角、覆盖、缺对象及旧消费者 | passed | 8组真实HTTP与已构建React核对54资源行、24日期行、162日格及54钻取；15条实际正式缺口标签正确。普通缺基准页面与导出保持待确认／缺项；共同正式覆盖与原采用拒绝一致。8项旧消费者新增真实SQLite及原路径回归通过。 |
| C05 界面、筛选、分页与甘特返回 | passed | 三次真实资源往返通过：所选设备、候选基准人员、正式v1设备；逐字段恢复完整查看窗和资源条件，实际资源／工序高亮正确。浅深主题1920／1392、Top10展开、热图键盘及100／125／150%已实测；修正sticky首格遮挡和缩放表宽后复验通过。 |
| C06 原始双格式、身份及scope | passed | 最终56030实例5个受影响案例、7份CSV／XLSX、894业务行通过；16,239格、7,105数值格，覆盖表177条完整身份，最长文本48字符，原生计数及7／7／9表结构通过。两张实际冲突表0行与API一致；root直接读CSV及XLSX数值类型。写入器2400覆盖身份和6条冲突成员边界回归通过。 |
| C07 日常、离线、性能及文档 | passed | 日常437 passed／20 skipped，67.38s，122必跑目标，Ruff全通过。最后UI定点Node及Chrome109本地10文件构建通过。Python3.8.10的20k／对象、4／6／8候选加基准跨40,200资源日完整汇总通过；设计、清单、验收、交接、需求、架构、手册和路线图已同步。 |

原始证据根目录：`evidence/decision-resource-impact/`。资源数学／HTTP核对初次运行于54056/PID37685；[最终同库复用证明](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/final-runtime-reuse.json)证实56030/PID56365的资源data相同，原区间及容量核对保持有效。最终导出以 `exports/coverage-cell-repair-01/export-verification.json` 为准；旧 `exports/export-verification.json` 保留修正前历史记录，未受影响的窄窗／零容量和CSV结果按对应场景复用。

最终文档检查：本feature4份及路线图2份YAML／frontmatter通过，4个执行步骤done、7项检查passed，阶段3实施通过／主对话pending与第4—8阶段planned一致；handoff74条路径及feature39个本地链接均存在。4条交付URL与HTTP／导航／公共API证据逐项一致，第一条已在真实浏览器打开11台设备。速查表251条路由核对OK，最终 `git diff --check` 退出0；README原有10行并发新增保留。

- [真实生成及原数据保全](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-fixture.json)、[资源独立核对](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-verification.json)
- [真实HTTP与已构建组件](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-ui-render.json)、[缺口标签](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-coverage-label-render.json)、[零容量文案](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/resource-zero-capacity-label-render.json)
- [最终导出](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/exports/coverage-cell-repair-01/export-verification.json)、[Excel原截断复现](../../../evidence/decision-resource-impact/performance/xlsx-coverage-cell-boundary-before.json)
- [最终浏览器](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/browser/verification.json)、[完整证据索引](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/evidence-index.json)
- [最终日常](../../../evidence/decision-resource-impact/quality/daily-final.log)；首轮Ruff脚本文字格式与旧notice fixture失败保留在同目录两份before日志。真实原因均已修正并复验。最后UI/CSS增量仅重验相应Node、构建和真实浏览器；后端计算及导出保持冻结。

## 4. 术语一致性

浏览器为真实Chrome154；构建目标为Chrome109，两个事实分别记录。原生125／150%缩放的表宽1400px、框宽792／607px，实际横滚608／793.33px；首格均完整可见。1392的浅深截图使用修正后的最终图；1920先前有效颜色／字体／布局按未受影响范围复用。早期遮挡／窄列截图保留为修正前证据，并在最终JSON明确排除。

班内占用、独立工序需求、墙钟跨度、班外和冲突分别展示。日格与资源表使用同一日事实；任务详情的单位为“段安排记录”，永久工序数量另列。正式身份按保存批次／工序标签呈现。未知、已知0、不适用和缺比较对象各自显示具体状态；缺基准的覆盖显示待确认。指标目录的常用标记与真实来源独立表达。

## 5. 架构归并

已更新 `architecture/service-scheduler.md` 的共同日历／区间／汇总、固定集合、scope、按需查询及旧消费者职责；已更新 `architecture/workbench-shell.md` 的资源表、热图、逐日、压力、甘特过滤及完整返回。`开发文档/系统速查表.md` 同步共同模块、两条资源路由和指标版本，251条路由核对OK。全部导出以同一scope及逐条覆盖／冲突明细表达。

## 6. Requirement 回写

`requirements/candidate-comparison-business-view.md` 已增加本feature到 `implemented_by`，同步设备／人员、两视角、归档日历、压力冲突、甘特往返和导出能力，保留完整愿景与历史变更日志。手册已更新实际操作和导出结构。

## 7. Roadmap 回写

第3项已回写 `done / implementation_acceptance=passed / parent_acceptance=passed`，主方案同步实际交付。第4阶段已派发，第5—8项维持planned。母任务 `stage-acceptance.md` 和独立复验证据由主对话维护。

## 8. Attention候选盘点

沿用现有Win7／Python3.8／离线约定和已明确的宿主验证工具。零、未知、保存版本与资源集合均写入实际设计／合同；本阶段未产生额外长期环境约定，attention无需新增。

## 9. 遗留与交付边界

- 当前隔离实例 `http://127.0.0.1:56030`、PID56365，同库41批／73工序／7运行／34候选／493安排；正式历史仍v1、正式15行。本阶段只新增一个实际资源运行，原30候选和旧正式资料保留，生成配置已恢复。
- Python3.8.10核心边界：4／6／8候选加基准，20k安排／对象，索引加整窗汇总1.745／2.451／3.179s；含生成输入总计1.922／2.703／3.500s，8候选进程累计峰值333,725,696B。每对象402资源×100日分40,000+200资源日两块，容量与占用完整。原宿主Python3.14证据另存，未当作产品运行时结果。
- 真实典型4／6／8候选HTTP于55291/PID48832各测一次：总览17.6／24.8／27.7ms，单资源逐日13.8／16.7／17.6ms，CSV20.4／22.1／24.5ms，XLSX60.7／43.0／33.2ms，服务采样峰值105,856KiB。[原始性能](../../../evidence/decision-resource-impact/aps-decision-workbench-20261013/performance/performance.json)保留端口和采样分段；最终56030导出由原始回读验收。Win7实机性能与完整整体验收沿第8阶段完成。
- 本轮源码、静态资产和材料处于未提交工作区，包含前阶段及并发改动；`开发文档/README.md` 原有改动保留。当前为本阶段实施验收与适用日常检查，最终HEAD／clean-worktree证明沿整体收口执行。
- 主对话独立第3阶段验收已通过，第4阶段准备／切换已派发；第5—8阶段推荐、优化过程、历史及整体接入继续等待派发。

## 主对话独立验收回执

2026-10-13 主对话确认第3阶段通过，无新增返修项。共同日历、区间、汇总、正式覆盖、旧消费者、导出职责和挂载已独立核对；实际4候选固定11设备／2人员，185.5h／31.5h容量、占用率和容量加权CV独立重算一致，窄窗保留8个正容量未用资源为0。热图Home首格、Enter逐日5／7h、设备所选日和人员候选基准甘特往返的可见条件／原窗／焦点一致。正式完整视角15条缺失工序名称、4人员并集／闲置0、1392浅色及1920深色布局通过。标准读取11行资源、23行人员逐日CSV／XLSX，684个重点数值字段、30空值及30行覆盖身份核对通过；其余日常、实际日历数学、正式甘特、原始导出与性能证据复用。独立证据在 `evidence/decision-stage-acceptance/stage-03/`，母验收由主对话维护；前文保留实施交付当时状态。
