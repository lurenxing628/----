---
doc_type: audit-index
audit: 2026-07-10-checkup-baseline
scope: 重新核验 cs-checkup 的 clean HEAD 机器基线、历史水位线和可视化可重放性
created: 2026-07-10
status: active
total_findings: 2
---

# Checkup 基线重验报告

## 范围

- 将 `~/.agents/skills` 下 27 个 `cs` / `cs-*` 技能复制到 `.limcode/skills/`。
- 核验全局 `cs-checkup` 旧路径、缺失 reference 和历史基线来源。
- 在 `git archive HEAD` 的 clean source 隔离快照中注入哈希绑定的只读扫描器，重跑 codemap、callgraph、循环依赖和 dead-code quick。
- 不纳入当前工作树未提交改动，不修改业务代码。

## 总评

代码投影基线已经重新建立在 commit `606bcda1d369914875fe63a5d3657ff4cbc351ac`：codemap 分层违规为 0、调用图可重现、循环依赖没有基线外新增硬环、dead-code quick 经误报核验后复跑无新增。

历史决定和可视化仍有两项明确缺口：决定考古只覆盖到 2026-06-01，后续 332 个提交尚未逐个考古；四张全景 HTML 与输入被 Git 忽略，且缺少三张页面的完整确定性生成器。两项均已在新 `cs-checkup` 中改为显式 pending/local-only，未包装成完成。

## 机器结果

| 检查 | 结果 |
|---|---|
| codemap | 741 模块、145194 行、7370 定义、分层违规 0、解析错误 0 |
| callgraph | 6921 函数、26763 边；clean HEAD 重跑与已提交快照一致 |
| import cycles | 6 个既有目录硬环、0 个文件硬环、无新增，退出码 0 |
| dead-code quick | 82 个基线疑似项，刷新后 0 个新增 |

完整机器清单见 `.codestable/checkup/baseline.json`。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | arch-drift | P1 | high | 决定考古水位线落后代码基线 332 个提交 | [finding-01.md](finding-01.md) |
| 2 | maintainability | P2 | high | 四张全景 HTML 缺少 clean clone 可重放链路 | [finding-02.md](finding-02.md) |

## 本轮已修正

- 27 个 CS 技能已复制为 `.limcode/skills/` 下的实体目录。
- `cs-checkup` 已改成代码基线与决定水位线分离，并补齐 `reference.md`。
- 从 stash 恢复了旧体检核心样本，明确标为历史证据。
- 恢复并重跑了 codemap/dynamic refs 脚本。
- dead-code 基线刷新说明改为记录实际 `mode`，不再把 quick 基线错误提示成 precise 刷新。

## 下一步建议

- **P1**：分批完成 `65870e47..606bcda1` 的 332 个提交决定考古，未完成前保持 watermark 不动。
- **P2**：若仍需要四张全景图作为长期产品，另开 issue 补齐版本化输入与完整生成器；否则把它们明确降为本机一次性材料。
