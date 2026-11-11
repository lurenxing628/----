# 项目子代理角色

本目录是角色正文源，不自动注册代理。授权、模型、审查深度、结束条件按根 `AGENTS.md`；宿主适配按需读 `.limcode/skills/_shared/subagent-compat.md`。

| 任务 | 角色 |
|---|---|
| 独立可验证的实现任务 | `plan-implementer.md` |
| 定向核对需求和范围 | `spec-reviewer.md` |
| 定向核对实现质量 | `code-quality-reviewer.md` |
| 整体独立审查 | `code-reviewer.md` |
| 一个问题族的只读调查 | `deep-investigate-worker.md` |
| 对调查或设计声明独立核实 | `independent-auditor.md` |
| 明确范围内抽取文档声明 | `aps_doc_scan.md` |

角色按需要选择，不默认串成“每任务实现、两次审查、最终再审”的固定流水线。明确双轨或完整验收时按用户范围完成。主代理负责合并发现、复核证据、决定下一步；审查角色不授予修复权限。

新任务由当前 CodeStable 入口组织。旧 LimCode 注册配置只在该宿主需要时参考 `.limcode/subagents/README.md`。
