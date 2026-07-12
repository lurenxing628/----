---
doc_type: refactor-scan
refactor: 2026-07-10-scheduler-a1-dependency-decoupling
status: selected
scope: core/services/scheduler 根目录、config、run、summary 的 A1 hard 目录 SCC 与直接合同测试
summary: 三组行为等价分层纠偏；用户于 2026-07-12 明确授权启动 A1 实施
---

# scheduler A1 依赖解耦 scan

## 1. 总览

扫描范围锁定 A1 四目录圈及其直接测试。当前扫描证据为 49 条圈内模块边：root→config/run/summary 17 条，config→root 3 条，run→root/config/summary 17 条，summary→root/config/run 12 条。目标不是把所有跨目录依赖都消灭，而是保留 `root → run/summary/config`、`run/summary → config` 等单向主链，移除会闭环的反向实现依赖。

本轮不改变函数/类签名、数据库格式、事务范围、排产结果、摘要字段、错误文案、路由和导出合同；不靠函数内 import 掩盖循环。范围虽超过 15 文件，但这是用户已批准 roadmap 中独立 A1 批次，且有双基线、调用链与专项测试作为边界。

## 2. 选中清单

### A1-01 · 根目录叶子能力归位

- 选择：✓（用户于 2026-07-12 明确授权启动 A1）
- 分类：L3 分层纠偏
- 现象：config/run 反借根 `number_utils`；run/summary 反借根 `degradation_messages`，形成 config/run/summary→root。
- 方案：调用方直接依赖已有 `core.shared` 数字/布尔函数和 `core.models.scheduler_degradation_messages`；根模块保留兼容入口。
- 风险：yes/no 默认值、公开降级文案必须逐字等价。
- 验证：配置快照、freeze、summary degradation 合同测试 + A1 扫描。

### A1-02 · execution 读取/快照族下沉为单向叶子

- 选择：✓（用户于 2026-07-12 明确授权启动 A1）
- 分类：L2 Move Function + L3 Layer Rectification
- 现象：run 顶层依赖 scheduler 根的 `execution_fact_provider`/`execution_snapshot`；这两者还与 scope read/enrichment 组成内聚执行事实族。
- 方案：实现迁到 `scheduler/execution/`，旧根模块只做显式 re-export；run 改依赖新叶子，旧 import 路径继续可用。
- 风险：ExecutionFact/Snapshot identity、快照 hash、计划身份校验、仓储读取和异常表现必须不变。
- 验证：operation execution scope/revision/reschedule 与 gantt publish 快照测试、正逆序独立进程导入。

### A1-03 · summary 被 run 消费的合同/公开投影下沉

- 选择：✓（用户于 2026-07-12 明确授权启动 A1）
- 分类：L1 Parallel Change + L2 Move Function
- 现象：run 顶层依赖 summary 的 graph/public search 投影、SummaryBuildContext 和 parse_summary_count；summary 同时依赖 run 的纯 helper，构成 run⇄summary 目录圈。
- 方案：把 run 需要的纯合同/公开投影实现迁到 `scheduler/contracts/`，summary 旧模块保留 re-export，run 改走 neutral contracts；summary→run 的现有 helper 依赖本批不改业务实现。
- 风险：dataclass 字段顺序/默认值、public projection 白名单/脱敏、count parse 错误文本必须逐字不变。
- 验证：orchestrator、summary v11、optimizer public projection、graph summary、candidate persistence/size guard 合同测试与旧/新 import identity 测试。

## 3. 明确不做

- 不拆 A2-A6，不顺手重命名业务字段或错误码。
- 不移除旧模块 import 路径；兼容层若重新形成 A1 回边则调整为单向 re-export。
- 不改变 `run → config`、`summary → config` 的现有单向读取，只保证 config 不再反向依赖 root。
- 不把 summary→run 改成函数内 import；通过 run→summary 合同下沉解除互环。
