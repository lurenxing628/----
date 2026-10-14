---
doc_type: feature-design
feature: decision-recommendation
status: approved
created: 2026-10-13
roadmap: scheduling-decision-workbench
roadmap_item: decision-recommendation
requirement: candidate-comparison-business-view
summary: 保存实际选择证据，统一固定推荐与当前查看取舍，解释完成集合、真实成本和支撑钻取
tags: [aps, workbench, recommendation, completion, tradeoff]
---

# 第5阶段：推荐、收益与代价

## 0. 术语

- 保存推荐为本次完成事务保存的 `selected_candidate_ref`，查看第三候选或改变比较基准后保持原身份。
- `raw_score_best_candidate_ref` 是按实际目标完整评分及既有并列规则得到的最优候选，承担 balanced 容差比较。`health_reference_candidate_ref` 是健康计算使用的本次原算法候选。
- 当前查看候选、当前收益/代价的查看基准、保存推荐、两条算法基准分别表达；推荐理由来自保存事实，当前取舍来自共同指标差值。
- 搜索覆盖、可排工序覆盖、业务交付覆盖分别展示。兄弟候选失败或预算跳过影响搜索覆盖；推荐自身的漏排、合法暂缓和未知完成性按实际集合解释。
- `common_completed_batches` 是推荐与当前基准都完整完成的批次交集。整次受理交付的未知值与此交集的可比较值使用各自范围。

## 1. 决策与约束

第4阶段已通过主对话独立验收，无新增返修。主对话按审定主方案第5节及8、10、11派发第5阶段完整实施、相关测试、适用日常检查、离线构建、真实浏览器和原始导出验收。完成后交回独立验收，第6—8阶段继续等待派发。

沿用实际选择器、健康计算器、目标顺序、业务交期和采用事务；新增事实由原计算入口在当时保存。选择规则版本保持 `candidate-selection-v1`，新增选择及健康证据各自带版本。共同指标版本沿用 `decision-preparation-v4`；推荐读模型使用 `decision-recommendation-v1`。存储沿用收据与候选 JSON 完成事务，无新增 Schema。

旧记录保存了什么就解释什么。缺少细分裁决、容差检查或未舍入健康分量时逐项列缺项；已有评分、推荐引用、原容差和健康摘要继续可读。

产品继续支持 Win7 x64、Python3.8、离线单机及 Chrome109。当前隔离实例、原运行、正式v1和参数保留；仅补充一项必要 balanced 正向选择的真实运行场景，执行前核对具体实例、数据范围和静态可行性，完成后恢复生成参数。

## 2. 名词与编排

### 2.1 现状与变化

现状：`decision_selection.recommendation()` 根据推荐候选的当前差值列出收益/代价，缺少三类推荐分类、完整共同完成集合和具体剩余需求。页面另有 `selectionReasons` 文案表；值班台局部组件在前端自行相减。选择器已保存固定三引用、策略、目标和容差，细分并列裁决、实际容差检查和健康组成尚未保存。

变化：选择器及健康计算器保存实际使用的原始数、阈值与裁决步骤；持久化统一映射永久候选引用。共同完成性投影生成完整批次集合、普通缺排/合法暂缓/未知集合、真实剩余工序与需求。后端推荐服务统一生成结论、原因、最多3项主要收益和3项主要代价、全部差值及支撑引用。页面和导出消费同一事实。

### 2.2 主流程与合同

```text
实际选择/健康计算
  → 完成事务保存选择证据和候选健康证据
  → 归档共同完成集合 + 指标目录/差值 + 固定推荐投影
  → 紧凑推荐区 + 既有明细钻取 + CSV/XLSX
  → 用户点击采用时进入既有当前预检及事务复验
```

`selection.decision_evidence` 使用 `candidate-selection-evidence-v1`：

- `anchors.raw_score_best / health_reference` 与 `selected` 保存实际评分、主目标、漏排、超期数和总拖期。
- `tiebreak` 保存完整score优先、baseline优先、sequence升序的规则；实际主目标/完整评分并列引用、次优引用、决定步骤和score字段索引。
- `balanced_checks` 保存实际资格、是否检查、未检查原因、四项条件的原始两侧数/实际限制/是否通过、是否接受及是否真正覆盖raw最优。已选raw自身时容差代价为0。
- 完成事务把临时候选key递归映射为永久ref。当前请求的查看基准不参与这些事实。

候选 `health.decision_evidence` 使用 `candidate-health-evidence-v1`，保存原计算入口的未舍入差值、每分量容差及贡献、实际阈值、共同时间原点和指标来源。只保存delta的松弛来源保持两侧level缺项。

推荐读模型包含固定推荐身份、当前查看身份、三类推荐类别、三轴完成性、固定选择解释、当前比较取舍和支撑钻取。主要条目按完成性、交付、压力/冲突、准备/切换、稳定性、时间的业务优先级及目录顺序确定；单位不同的指标分别评价。

默认推荐区保留一条保存事实生成的真实选择主因，并以可见短列头说明“保存推荐相对当前基准”的取舍关系。首屏合并重复标题／正文／覆盖表达，保留13px正文和完整3+3；通过局部支撑按钮、卡片及面板余白控制高度。完整选择证据和全部差值继续按需展开。

```text
selection_basis {
  原固定字段, selection_evidence_version, decision_evidence,
  health_decision_evidence, explanation {headline, entries[], issues[]}
}
recommendation {
  recommendation_version, state, candidate_ref, viewed_candidate_ref,
  recommendation_type: complete | schedulable_scope | partial | null,
  headline, axes {algorithm, completion {search, schedulable, delivery},
                  preflight {state: not_checked, source: existing_adoption_preview}},
  completion_scope, current_comparison {state, candidate_ref, viewed_candidate_ref,
    reference, benefits[<=3], costs[<=3], all_differences[], common_completed_delivery}
}
completion_groups[] {
  group_index, source_available, candidate_refs, complete_batch_count,
  sample_complete_batch_refs[<=3]
}
```

`completion_scope` 保留完整/未完整/普通缺排/合法暂缓/未知的批次数量和未排/暂缓工序数量、各类最多3个支撑批次、同源剩余需求汇总与完整明细入口。`GET /decision/completion-batches` 按独立 `completion_candidate_ref` 分页读取该候选的完整受理批次集合，支持 `all/complete/unfinished/ordinary/deferred/unknown` 筛选，逐行显示完成状态、剩余需求及具体批次入口。完成组共享完整完成集合；组内各候选的剩余工序和需求分别读取。`work_scope=remaining` 在既有准备明细、分页和导出中筛选该候选实际未安排工序；与批次、设备及安排侧筛选取交集，空集合保持空结果。全部精确集合和工序事实仍由请求内共同领域缓存提供。`current_comparison.common_completed_delivery` 保留独立 `common_completed_batches` 范围、交集数量、样例引用、两侧交期摘要及差值。当前查看的 `full_admission` 指标与未知覆盖继续保留。

既有v1 `recommendation.reason_code / selection_basis / benefits / costs` 保留兼容读取；收益/代价列表直接筛选同一 `all_differences`，保持原 `metric_key / label / value / unit`，不重复计算。新页面从 `current_comparison` 消费主要取舍与全部差值，选择解释从 `selection_basis.explanation` 消费。

分类：业务和可排范围完整时显示“推荐方案”；合法按工序待料暂缓且本次应排齐全时显示“本次可排范围推荐”；其余显示“算法选中的部分结果”，具体缺排/暂缓/未知集合优先说明。推荐仍保存实际算法身份，全部候选部分、单候选和兄弟失败均按真实三轴呈现。

部分候选按 exact 完整批次集合分组。推荐相对当前基准的交付取舍使用共同完成批次交集；空交集为缺少可比较集合，全部未指定交期为不适用，非法交期与不完整工艺保持未知。整次受理的未知摘要继续显示。未安排或暂缓使准备需求减少时，文案为“少安排的准备需求”，保持中性并指向具体剩余工序。

概览仅提供有界支撑引用、集合数量及既有分页明细入口。完整批次/剩余工序按同一领域事实用于明细和分行导出。聚合批次、资源、准备和切换支撑进入固定推荐的现有明细；具体工序或切换事件沿保存的真实 `drill` 直接进入甘特并准确定位，允许原合法定位扩窗。推荐移除安排时使用真实基准侧安排定位；支撑仅采样调整统计中的已知变化，双方未安排、纯未知及多段未知覆盖保持各自状态。返回恢复原候选、基准、范围、页签、筛选、分页及快照；经支撑页进入的甘特先恢复该支撑页，再返回原比较。

### 2.3 挂载点与所有权

- `schedule_candidate_selection.py`、候选健康计算和 `workbench_run_result_repo.py`：保存实际选择证据，沿用原选择行为及完成事务。
- `facts/completion_scope.py`、`facts/common_completed_delivery.py` 与 `run/decision_delivery.py`：共同完成集合、交付算术和剩余需求事实。
- `run/decision_selection.py` 及必要推荐/导出叶模块、`decision.py`、导出路由：推荐纯投影、缺项、排序、支撑及三张分行导出表。
- `RunDecisionComparison.jsx`、推荐组件、`RunDecisionAPI.js`、相关样式及构建：后端事实展示、原生展开和既有明细导航。
- 值班台实际取舍入口接共同服务；试调保存后进入采用预检的文案准确表达。旧候选分析的 `recommendation:null` 尚无理由消费者，按实际使用保持原合同。
- 主代理维护导航公共白名单、测试登记、项目文档与阶段状态。验证代理维护真实实例、浏览器和原始导出证据。

### 2.4 推进策略

1. 保存事实与共同领域投影，锁定固定身份、真实裁决、共同完成交期及剩余需求。
2. 推荐模板、全部差值与3+3主项、缺项和分行导出，页面与旧实际消费者接同一合同。
3. 复用有效4/6/8候选、部分、暂缓、复用和正式基准案例，补真实 balanced 正向取舍。
4. 相关回归、日常检查、Chrome109构建、双主题/双窗口浏览器、键盘钻取返回及原始CSV/XLSX逐项核对，同步文档并交接。

### 2.5 结构健康度

选择事实生产者与业务解释分层；模板依据共同指标目录和领域差值，不重复选择、健康、交期或准备公式。完成集合与剩余需求是共同事实，整次摘要、推荐和导出复用。采用复用当前preview与事务复验，查看旧推荐保持只读。

推荐导出为“推荐说明 / 完成集合 / 剩余需求”三表：前者按结论、固定选择、容差、健康、并列、复用、差值和支撑分行；后两表按批次和工序分行。CSV用同一宽表头及 `record_kind` 逐行表达；数字保持数字，null保持缺项。共同记录run/capture、保存推荐、当前查看/基准、窗口、资源视角和两项版本。

## 3. 验收契约

- C01：固定推荐、raw最优和健康基准及实际目标/策略/容差证据保持；第三候选/查看基准/正式模式只影响当前取舍。
- C02：完成性主因先显示，3+3确定性主要条目与全部差值均来自共同事实；保交期同时增加压力/切换的收益代价真实。
- C03：三类推荐、搜索与自身完成性分离；部分集合不同按共同完成交期，空集/未指定/非法/未知和普通缺排/合法暂缓及真实剩余需求正确。
- C04：实际目标并列、baseline/sequence裁决、等价复用来源和策略记录可追；balanced解释健康改善、实际接受的超期/拖期代价和容差。
- C05：新保存精确证据与历史缺项分别可读；0、不适用和未知独立；同源事实与旧实际取舍入口一致，采用状态复用当前预检。
- C06：推荐紧凑布局保留候选区空间，全部依据原生展开；批次/资源/工序/准备/切换支撑定位及甘特完整返回，键盘交互有效。
- C07：CSV/XLSX推荐说明、完成集合和剩余需求与页面/DTO同事实；数字、文本、引用、缺项、共同scope和snapshot正确。
- C08：相关回归、适用日常、Chrome109离线构建、真实实例、浅深1392/1920浏览器和文档同步通过；原记录、正式v1和生成参数保留。

## 4. 项目文档与状态

设计、执行、验收及交接在本目录；原始证据在 `evidence/decision-recommendation/`。同步需求、调度与工作台架构、操作手册、接口速查、主方案和items。实施方验收和主对话独立验收分别记录；本阶段结束后第6—8阶段仍待派发。
