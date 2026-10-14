---
doc_type: feature-design
feature: decision-comparison-loop
status: approved
created: 2026-10-13
roadmap: scheduling-decision-workbench
roadmap_item: decision-comparison-loop
summary: 同次候选比较、保存选择依据、明确基准与差值、甘特回跳、总览导出和采用闭环
tags: [aps, workbench, candidate-comparison]
---

# 第 0 阶段收敛与第 1 阶段实施

## 0. 共同术语

- 本次候选：同一 `run_ref` 保存的全部候选，包含失败与跳过记录。
- 查看基准：用户选择的已产出候选，默认原算法候选；全部差值为候选减查看基准。
- 当时的选择依据：保存的推荐、原始分数最佳候选与算法健康基准，查看基准切换保持这些事实固定。
- 受理时正式计划：旧单项比较的独立基准，保留清楚标签。
- 完整性：搜索覆盖、应排工序覆盖、业务交付覆盖分别表达；合法待料暂缓单列。

## 1. 决策与约束

用户已授权连续完成本阶段设计、实现、验证与相关文档同步。复杂度采用现有离线单机产品规模；保留 SQLite 保存事务、永久身份和必要引用/范围校验。

第 0 阶段决定：

1. 一次读取运行收据、归档事实和候选全集，形成一个 decision 总览；前端与导出共同消费指标目录和差值。
2. 指标覆盖和差值在服务负责，前端只验证 envelope 与身份；删除生成资料中重复的业务指标展示。
3. 比较快照保存范围及实际身份字段，通过直接字段比较匹配；归档共同入口读取 JSON、Schema 与永久引用，移除重复 SHA256 计算。
4. 基准、所选候选和资源范围由服务返回；前端保持最少选择状态，甘特回跳携带该上下文。
5. 第 1 阶段保留既有算法资源摘要并标明原口径。共同班表率、准备需求分解、逐批影响新明细、过程曲线和历史趋势由第 2—8 项继续建设。
6. 复用采用预检与正式采用事务。业务样例与采用仅发生在专用隔离实例。
7. 完工跨度与工种切换次数的收益按实际已排工序集合比较；集合不同且应排范围仍有缺口时，差值标明覆盖不同。指标目录版本直接进入快照状态。

## 2. 名词与编排

### 2.1 现状与变化

现状：`CandidateStore` 保存全集，`WorkbenchRunCandidateQueryService` 按单项加载，`RunCandidateControls.Catalog` 展示三个数值，`candidate_analysis` 与正式基准比较。

变化：新增 `read_run_decision`，输入共同 query，输出 `run/scope/candidates/metric_definitions/recommendation/selection_basis/baseline/resource_cohort`。MetricValue 共用 `value/state/known_subtotal/known_count/unknown_count/total_count/reason`；MetricDelta 共用 `value/state/direction/reference_value/selected_value`。

`GET /api/workbench/v1/scheduling/runs/<run_ref>/decision` 和 `/decision/export` 使用现有 envelope 和快照注册。例：`?reference_candidate_ref=<候选B>&selected_candidate_ref=<候选A>` 读取同次全集，推荐固定，差值统一相对 B。导出 `format=csv|xlsx`、`section=overview`，带屏幕返回的 `snapshot_ref`。

### 2.2 编排

真实排产保存 → 同次总览 → 选择候选与查看基准 → 甘特核对 → 回到原比较 → 现有采用预检 → 正式采用。

主页面按原型的推荐结论、收益和代价、当前选择动作、候选常用指标表排序，复用当前工作台组件、颜色、密度及浅深主题。候选按行比较完整性、交期、跨度、切换和变化；全部指标通过同区展开矩阵访问。搜索覆盖在范围栏显示一次，算法技术角色归入折叠的当时选择依据。失败与跳过行保留具体原因；普通漏排、待料暂缓、交付覆盖和数值缺项始终可见。

2026-10-13 主对话首轮验收返修确定新总览按报表语义输出：普通文字原样、空值留空；CSV 仅处理实际公式前缀与数字文本编号，XLSX 使用文本单元格保留身份。读取端使用标准 CSV/XLSX 结果直接核对业务字段。

### 2.3 挂载点

- 现有 scheduling 候选路由注册 decision 及总览导出。
- `RunCandidateWorkspace` 的 analysis 视图挂载同次比较主区，gantt 保留独立页面并提供回跳。
- 既有 `renderAdoption` 接入当前所选候选，沿用既有预检与提交契约。

### 2.4 推进策略

后端负责归档、指标与选择依据；前端负责呈现与导航；Web/导出统一接入；隔离运行和行为契约共用真实引擎与既有 fixture。文件所有权分开，主代理整合。

### 2.5 结构健康度

必要重构集中于归档读取、保存选择映射和指标目录。保留旧单项 API 兼容入口；本轮移除重复展示和无用归档摘要校验，迁移影响由相关既有测试核对。

## 3. 验收契约

- C01：真实同次全部候选可见，失败/跳过也有行和原因；任选已产出候选作基准，所选减基准正确。
- C02：推荐、raw_score_best 和 health_reference 固定来自保存事实；第三候选作查看基准时保持固定。
- C03：搜索、应排、交付覆盖分别显示，合法 stage 暂缓与普通漏排分开；不同覆盖的交期指标差值有明确状态。
- C04：归档回看保持排产依据，导出与屏幕身份、基准、范围、单位、数值及差值一致；错误归属/范围和过期快照有明确返回。
- C05：浏览器完成运行→比较→甘特→回跳→采用，回跳恢复比较上下文；浅深主题有实际界面证据。
- C06：针对性验证与项目日常门禁执行，离线静态资产随包构建；保留已有 README 修改，保持本轮未提交状态。

反向核对：比较入口消费共同服务；导出消费同一返回值和目录；采用保留原事务入口；业务指标集中于主比较区域。

## 4. 项目文档关系

完成后同步 `requirements/candidate-comparison-business-view.md`、`architecture/service-scheduler.md`、`architecture/workbench-shell.md`、路线图和 `开发文档/系统速查表.md`，并在本目录记录实际验证与界面证据。
