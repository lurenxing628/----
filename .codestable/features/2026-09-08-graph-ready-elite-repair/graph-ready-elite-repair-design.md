---
doc_type: feature-design
feature: graph-ready-elite-repair
status: approved
summary: 在正式 GraphReady v2 phase 中接入少量精英、双预算、正式 SGS 的最小 repair
tags: [scheduler, graph-ready, elite-repair]
requirement: null
roadmap: scheduler-global-optimizer
roadmap_item: graph-ready-v2-elite-local-repair
---

# 0. 范围

依据本轮用户批准实施和 roadmap items 第149行起合同。前端、ALNS、大统一候选池、公共 roadmap/registry/基线不修改；不提交。保留共享 dirty。A18 评价口径和全局保守接受规则由主代理负责。

# 1. 决策与约束

- 走现有 Python 3.8 / Win7 / 离线档位，不加依赖。
- 配置仅复用 `candidate_construction.graph_ready_optimization` 的内部字典；默认 `elite_repair={enabled: true, top_k: 3, max_neighbors_per_elite: 8}`。时间从进入 repair 时实际剩余预算派生，候选数从既有 `max_candidate_profiles` 减去已启动 profile 数派生；支持同入口关闭做对照，不增加配置页参数。
- top_k/max_neighbors 系统上限分别 8/32；生成邻居前和正式调用 SGS 前都检查 deadline，构造耗时跨过 deadline 则记生成后预算跳过，不计已评估。单次 SGS 不可抢占，已启动的 decode 必须完成评价，允许单次 decode 造成时间超出并如实报告。
- 所有候选仍通过 `evaluate_graph_ready_candidate`；不创建可变时间、结果或固定 seed，不削弱图/资源/执行态约束。
- 仅接受完整 score 严格更好、真实输出不同于 parent/seen 且既有比较/接受链允许的候选。

# 2. 现状与变化

## 2.1 名词

现状：`optimizer_graph_ready.py:_run_weight_profiles` 只消费 profile；`optimizer_graph_ready_candidates.py:evaluate_graph_ready_candidate` 已负责 SGS -> metrics -> objective；`optimizer_graph_ready_profiles.py` 已有 repaired origin。

变化：内部 elite 是已正式解码的 v2 候选及其 profile/指纹。repair 决策只含 batch order 和对应 mutable graph priority；报告是阶段级 `elite_repair`，按 roadmap 区分 generated/evaluated/pruned/rejected/skipped。例如 8 个邻居中 2 个重复、6 个正式解码且无改进，报告 8/6/2，accepted=false，而不是成功修补。

## 2.2 编排

```mermaid
flowchart LR
  A[正式 profile 解码] --> B[保留不同输出 top K]
  B --> C[有剩余时间和候选预算]
  C --> D[有限邻居与 decision 去重]
  D --> E[正式 SGS 与统一评价]
  E --> F[输出指纹与严格接受]
  F --> G[best 和阶段报告]
```

现状：benchmark 的 swap/insert 不在 core，不能算生产能力。
变化：生产 v2 phase 尾部直接运行 repair。邻域来自 elite decoded order，adjacent swap、风险批次有限 insert、延期边界 move；由 version 派生稳定顺序。SGS 图键高于 batch_order，因此 repair 把批次顺序编成图键前缀，只改变 ready 决策优先级。

## 2.3 挂载点

- 正式 GraphReady phase 尾部的 repair 调用。
- 正式候选评估器的 repair 优先决策输入。
- SearchReport 的阶段级 elite_repair 报告；公开摘要复用既有 profile.message 白名单，完整统计沿 diagnostics.attempts 保存，不改公共投影模块。

## 2.4 推进步骤

1. 内部合同与窄职责邻域：预算、候选空间、确定性决策有边界测试。
2. 生产编排和正式评估接线：真实 SGS、指纹、严格接受与统计可验证。
3. 验收和同预算多 seed：现有 GraphReady 合同、新合同、真实对比与准确收益记录。

## 2.5 结构健康度

已检查架构入口和 compound 相关约束。结论：不做独立微重构；既有 graph phase 已接近文件上限，新 repair 按配置/邻域/执行职责落窄模块，不继续把所有逻辑堆到入口。目录沿现有 optimizer_graph_ready 命名族。若评估/A18 或公开投影需要写集外改动，通知主代理负责，不扩大写集。

# 3. 验收契约

- top-K、每 elite 邻居数、候选总预算和真实 deadline 均能截断，跳过原因独立可查。
- 重复 decision 在 decode 前去重；相同输出只能拒绝，不能计为改进。
- equal/worse score 不采纳；decode ValidationError 非 strict 记录 rejected，strict 或合同错误 fail-loud。
- 所有新增候选经过正式 schedule_fn、metrics、objective、fingerprint 和严格接受；保护 seed、图边、资源传参不变。
- 无 elite、预算不足、无严格改进、全部拒绝均明确报告；公开只聚合，不泄漏内部 ID/hash/trace。
- 复用已有真实 tiny 数据和 longrun 比较口径，多 seed 同数据同目标同预算，报告 wins/ties/losses 和耗时/候选数。dirty 仅为局部未绑定证据，不声称全局最优。
- 反向核对：不修改前端/ALNS/公共台账/全局基线，不运行长时间全库门禁，不 git add/commit/push。

# 4. 协调

公共报告投影、A18 评价参数与旧 benchmark 支持迁移已通知主代理。检查现行投影后，公开计数和中文拒绝摘要可通过既有 profile.message 落地，完整报告保留在原有 diagnostics.attempts。专属旧 GraphReady v2 harness 和两条旧 scope 断言迁移到生产 core，不改公共比较器或基线。A18 尚未收到新签名，保持 compute_metrics(res, batches)，主代理后续只需接这一份正式评估器。roadmap 状态由主代理统一收口，本 feature 不回写公共文件。
