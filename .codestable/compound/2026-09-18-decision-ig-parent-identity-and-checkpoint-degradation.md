---
doc_type: decision
status: active
created_at: 2026-09-18
slug: ig-parent-identity-and-checkpoint-degradation
tags: [scheduler, iterated-greedy, elite-repair, checkpoint, reporting, python38]
---

# 图阶段父方案身份、检查点捕获降级与预算口径

2026-09-18 图阶段只读审查发现：修补与迭代贪心把"父方案"重建成按开始时间排序的工序序列，自动派工场景下重新解码并不能复现父方案；迭代贪心把父方案的重复解码记成 `same_fingerprint` 拒绝，把"父方案解码放不下"记成 `time_budget`；检查点捕获遇到不支持的输入会让整个候选失败；退火温度对整数主目标恒等于贪心，破坏规模一旦到底就再也涨不回来。用户裁决"全修，按你的意见来办"。本决定记录图阶段与迭代贪心这一组的修法；解码加速层与外层候选/局搜/预算分别由另两组处理，保留 Win7 x64 / Python 3.8、离线交付、不跑全门禁。

1. 父方案身份 = 解码出的开工序（`decoded_topological_order`）+ 显式资源覆盖，与改前一致；自动派工资源不钉住，SGS 实际取序不作基座。两种"精确身份"改法都在同日实测后撤回：(i) 钉住合格组合——medium_shift_pool 4 目标、10 秒真实时钟下 IG 400 次解码 0 改进、档位/修补从 28/32 变 13/47、加权拖期差 5%–11%；(ii) 以取序捕获为父顺序——同一基准加权拖期 1128 → 1199.5，按代理文件组覆盖树定位到本组，再对 13 个因素逐个与组合开关，工序级邻域、资源邻域、IG 三处基座都回到改前才恢复 1128，端到端 20 例与黄金向量对它中性。漂移本身就是自动派工与批次重取序场景的搜索自由（finding-07）。保留：`parent_order_consistent` 表示参考捕获逐位复现父方案（按输出指纹，不只比分数），漂移计入 `reference_capture_divergences`。
2. 修补的批次邻域保持只改批次排名的决策，让 SGS 在新排名下重新取用工序；"按父取序整块搬移被移动批次的工序"曾同日落地又撤回——集成后真实时钟端到端 20 例对 HEAD 7 例变差，按文件组覆盖与逐因素开关都只指向它，关闭后逐位回到 HEAD（见 finding-07）。同一精英每个特征基各自记录已消费前缀，中途新增变体不再重排已访问决策。
3. 迭代贪心的解码剖面固定为一份规范剖面（解码器本就忽略权重），父方案剖面不再造成上下文切换。已知方案在迭代贪心上下文下的完整解码是"参考捕获"：复现来源的记 `reference_captures`，不再记拒绝；输出不同的记 `reference_capture_divergences`，若严格更优记 `reference_capture_improvements`，与破坏/修复得到的 `improvements` 分开；轮转反馈以两者之和计事件。`parent_order_consistent` 表示捕获逐位复现父方案，不再只比分数。
4. 起点只对第一次尝试构造交期种子；种子成为参考时 `reference_basis="due_date_seed"`，父方案字段保持空；否则 `reference_basis="parent_order"`。首个池条目捕获失败时按分数尝试其余条目，失败次数记 `pool.start_captures_failed`，全部失败才报 `parent_order_rejected`。
5. 采纳他人改进的现任后，如果新上下文的参考捕获因预算或解码拒绝而失败，回滚到原上下文与原参考并计 `incumbent_adoption_rollbacks`；现任本身仍被采纳。此后续排试算只会因真实缺陷触发签名不一致。
6. 检查点"捕获期"失败（不支持输入、日历不可用、无图键等，即未续排时 `field == "decode_checkpoint"`）一律降级：关闭检查点、以普通完整解码重跑、记 `checkpoint_capture_rejections` 与 `checkpoints.disabled_reason`，同一逻辑解码只计一次。续排后的签名/前缀/范围/尾段不一致仍然直接失败。
7. 预算口径：父方案解码放不进剩余时间时报 `decode_would_overrun` 并写 `decode_admission{policy, estimated_decode_ms, remaining_ms}`，公开文案对应"预计一次完整解码放不进剩余预算"；0 次解码不得报 `time_budget`。剖面阶段因估计成本停止时报 `skipped_by_estimated_decode_cost` 而非空原因；剖面已解码过的阶段只标 `deadline_reached`，不再标成"因时间预算跳过"。
8. 退火默认温度比例改为起 1.0、终 0.01，温度尺度取首个主目标差值：整数主目标早期可按 e^-1 概率接受多一个逾期批次，末期几乎贪心；主目标持平时按首个次级差值退火次级分量，`secondary_temperature_scale` 上报。破坏规模的自适应值夹在最小/最大尺寸对应区间内，步长因子的变化次数封顶为 8，使最小尺寸一次成功即可长一档、最大尺寸一次失败即可缩一档。
9. 剖面阶段连续 6 次解码只得到已见过的排程时提前结束，写 `profile_efficiency.stagnation_stop{consecutive_repeated_outputs, unvisited_profiles}`，轮转启动状态报 `profiles_stagnated`；预解码去重不计入这 6 次。

验收以 HEAD 只读工作树为基线：SMTWT-40（步进时钟，种子 0 的 0/1/2 号实例与种子 1 的 0 号实例）与质量矩阵 tiny / medium_shift_pool 的最终分数逐项相同，`same_fingerprint` 拒绝全部转为 `reference_captures`。合同测试见 `tests/algorithm/test_graph_ready_ig_reference_contract.py`、`test_graph_ready_stage_reporting_contract.py` 及既有 IG 合同的更新；集成后真实时钟复核与两次撤回见 finding-07 处理结果和审计 index 的归因段；未提交，不构成 clean-worktree proof。
