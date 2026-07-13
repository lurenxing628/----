---
doc_type: audit-index
audit: 2026-07-13-unpushed-dependency-governance-review
scope: origin/feat/default-light-improve-sgs..HEAD 的 10 个已提交未推送提交（cd6cdf43..6433599d）
created: 2026-07-13
status: resolved
total_findings: 2
---

# 未推送依赖治理提交审计报告

## 范围

审查当前分支 `feat/default-light-improve-sgs` 相对远端同名分支的全部 10 个未推送提交：

- 基线：`origin/feat/default-light-improve-sgs = cd6cdf43798e3c6321370e4fceb7150bbe4cef3c`
- 终点：`HEAD = 6433599ddb5e5a1132c7d9ecb5eb7dd56905df6d`
- 规模：234 个文件，`+11591 / -3849`
- 批次：依赖治理工具闭环、scheduler A1、foundation A2、algorithms A3，以及各批文档收口

审计重点是 KISS、广泛兜底、静默回退、吞错、行为等价、测试盲区和全局架构取舍。对照了 `.codestable/architecture/`、依赖治理 roadmap 和 A1/A2/A3 的 scan/design/apply 记录，并逐批比较搬迁前后源码。

## 总评

整体架构方向是合理且接近当前约束下的全局较优解：

- A1 用 `scheduler/contracts` 与 `scheduler/execution` 中立叶子解除 run/summary/root/config 反向依赖；
- A2 用零依赖 `core.errors` 和父层 `migration_common` 建立基础层单向结构；
- A3 因 `core.algorithms` 根包必须继续 eager export，选择根外 sibling `algorithm_contracts` / `algorithm_runtime`，比在 `core.algorithms` 子包内绕父包初始化更稳妥；
- 三次生产基线变化各只删除目标 SCC，其他 SCC 的成员和圈内边未变化，也没有新增依赖圈；
- 兼容模块大多是显式同对象 re-export，没有用函数内 import、`TYPE_CHECKING`、动态 `__getattr__` 或吞错伪造消圈。

审计时发现 **2 条**：**1 条 P1、1 条 P2**。P1 是 A3 新 legacy adapter 丢弃 `strict_mode` 并把缺 callback 错误折算；P2 是调用图对同一个 imported-module 属性 callsite 同时生成确信边和模糊边。两条均已在 2026-07-13 按独立标准 issue 修复并补合同测试，当前 open finding 为 0；修复尚未提交，因此仍不能直接 push 或宣称 clean-worktree proof。

未发现本批次新增的 P0、安全问题、性能回退、数据库/迁移语义变化或 Win7/Python 3.8 兼容问题。A1/A2 中的宽容解析、日志 stderr 回退等均是既有冻结行为，本轮没有扩大；工具侧反而移除了 UTF-8 `errors="replace"` 的静默替换。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 状态 | 标题 | 文件 |
|---|---|---|---|---|---|---|
| 1 | bug | P1 | high | resolved | A3 legacy dispatch adapter 绕过 strict-mode 并删除既有执行回退 | [finding-01.md](finding-01.md) |
| 2 | bug | P2 | high | resolved | 调用图把同一 imported-module 调用同时记成确信边和模糊边 | [finding-02.md](finding-02.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---|---|---|---|
| bug | 0 | 1 | 1 | 2 |
| security | 0 | 0 | 0 | 0 |
| performance | 0 | 0 | 0 | 0 |
| maintainability | 0 | 0 | 0 | 0 |
| arch-drift | 0 | 0 | 0 | 0 |
| **合计** | **0** | **1** | **1** | **2** |

## 验证记录

- 远端只读核验：远端分支和本地 tracking ref 都是 `cd6cdf43798e3c6321370e4fceb7150bbe4cef3c`，审计范围确为 ahead 10、behind 0。
- 定向回归：依赖工具、A1/A2/A3 边界、strict-mode 和 greedy 合同共 **213 passed**。
- 正式双 scope import-cycle 门禁：均返回 0，quiet 模式无输出。
- 完整质量门禁：在干净 `HEAD=6433599d` 上以 `--require-clean-worktree --no-long-gate-cache --no-resume` 跑完 **19/19**，收集 4731 项、unexpected failure 0、required 253 targets / 2467 nodeids。
- 机械门禁通过不能反证 Finding 01/02：两条都已用现有测试未覆盖的最小输入独立复现。
- 修复后定向验证：完整 `tests/algorithm` + receiver-resolution 共 574 passed；新增合同测试均经历红灯/绿灯或直接锁定第二入口；双 scope import-cycle 门禁继续通过。
- 调用图证据：两个独立临时目录 10 JSON 逐文件 SHA 相同；只删除 111 条可解释 attr 模糊记录并新增 1 条 strict 校验确信边，正式快照为 7337/25688/10172/15516/195，25 项 artifact SHA 全匹配。
- 修复后完整质量门禁：19/19 receipts returncode 0，4734 collected、unexpected failure 0、required 253 targets / 2467 nodeids；manifest=`passed_but_unbound`、tracked drift=false，wrapper 因工作区 dirty 按合同退出 2。
- 子代理复审未用于结论：当前宿主无法提供 OPUS 模型槽证明，子代理按项目规则停止；本报告由主代理单线程完成源码对照与盲审。

## 收口状态与下一步

- **P0/P1/P2 open finding**：0；两条 finding 的代码、测试、生成证据和事实文档均已收口。
- **行为合同**：legacy strict 输入恢复 fail-loud；缺 callback 采用能力按需专用合同错误，不复制 canonical scheduling 实现，也不在 adapter 构造时过度拒绝无需该能力的路径。
- **治理证据**：imported-module 精确 callsite 不再进入 attr 模糊分支；正式调用图、baseline 数字和 artifact SHA 已更新。
- **剩余动作**：当前修改未 commit、未 push。若用户授权提交，应把两条 issue 文档与修复一起做 scoped commit；随后在固定干净 HEAD 重跑 `--require-clean-worktree --no-long-gate-cache --no-resume`，通过后才建议 push。
