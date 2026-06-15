---
doc_type: audit-index
audit: 2026-06-14-subagent-reference-trace-verification
scope: 对附件中 C1/C3/C4/C5/C6/C7 可见疑似问题做 Subagent 引用链核实
created: 2026-06-14
status: active
total_findings: 11
---

# subagent-reference-trace-verification 审计报告

## 范围

本次只核实用户附件中可见的同类新问题清单，重点下钻：

- C1：固定名文件软链接/路径未守卫。
- C3：`record-resource-change` 内部字段外泄。
- C4：日期范围、分页、列表计算的事后保护。
- C5：筛选条件没有下推到查询层。
- C6：报表坏时间静默跳过。
- C7：部分数据冒充完整、URL 参数空转、回跳丢上下文。

本次没有修代码，只做静态引用链核查。并发峰值 16 个 Subagent，总计成功创建 17 个 Subagent；最初补发 C3 时曾因并发上限失败一次，关闭已完成子代理后补发成功。

## 总评

附件中的可见疑点大多成立，但有几处需要修正口径：

- `7003d6a3` 不是整个 commit 只改两个文件；它共改 9 个文件。但只看软链接安全加固，生产代码主要是 `runtime_log_reader.py` 和 `security.py` 两个点，确实没有抽出全项目通用 helper。
- 启动状态里的 DB 文件名实际是 `aps_db_path.txt`，不是 `aps_db.txt`。
- `execution_review` 无日期分支不是全库全版本，而是当前版本的 adopted/Schedule 行；普通页面通常会补日期，导出路由不带日期可以直达。
- 批次详情不是按窗口左边界取数；它取本批次全量行。真正问题是 `op_count` 用全量行，`span` 只用可解析时间子集。
- 人员列表没有 `status` 筛选条件；人员动作丢的是 `team_id`/页码上下文。
- C3 的指定接口外泄成立，但“唯一净新外泄点”证据不足。

整体根因可以收成三类：固定名文件读写没有统一安全原语；页面/路由接住了筛选和范围，但查询接口没有把条件带到底层；报表层没有接入 scheduler 体系已有的坏数据降级提示。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | security | P1 | high | 固定名运行文件软链接加固半截化 | [finding-01.md](finding-01.md) |
| 2 | performance | P1 | high | 甘特自定义日期跨度缺后端上限 | [finding-02.md](finding-02.md) |
| 3 | performance | P2 | high | 批次/物料/人员列表先全量装配后分页 | [finding-03.md](finding-03.md) |
| 4 | performance | P2 | medium | 计划和现场实际导出无日期时全量装配当前版本 | [finding-04.md](finding-04.md) |
| 5 | performance | P1 | high | 延期诊断不吃页面/导出筛选条件 | [finding-05.md](finding-05.md) |
| 6 | performance | P2 | high | 资源派工和现场任务卡缺精确条件下推 | [finding-06.md](finding-06.md) |
| 7 | bug | P1 | high | 报表坏时间静默跳过导致指标偏小 | [finding-07.md](finding-07.md) |
| 8 | bug | P1 | high | 批次详情 op_count 与 span 口径不一致 | [finding-08.md](finding-08.md) |
| 9 | bug | P1 | high | 超期清单日期参数传播但查询不生效 | [finding-09.md](finding-09.md) |
| 10 | bug | P2 | high | 批次/人员动作回跳丢查询上下文 | [finding-10.md](finding-10.md) |
| 11 | security | P2 | high | 甘特调整资源变更接口整包返回内部字段 | [finding-11.md](finding-11.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---|---|---|---|
| bug | 0 | 3 | 1 | 4 |
| security | 0 | 1 | 1 | 2 |
| performance | 0 | 2 | 3 | 5 |
| maintainability | 0 | 0 | 0 | 0 |
| arch-drift | 0 | 0 | 0 | 0 |
| **合计** | **0** | **6** | **5** | **11** |

## 下一步建议

- **P1 先修**：finding-01、02、05、07、08、09。它们分别对应安全一致性、单请求大范围自伤、导出/诊断浪费、报表误导和用户筛选误导。
- **P2 排期修**：finding-03、04、06、10、11。它们多是随数据量增长、上下文体验或低风险字段外泄问题，但已经有明确引用链。
- **修复入口建议**：按 `cs-issue` 分 3 个问题包更清楚：固定名文件安全包、查询/范围下推包、报表/页面诚实提示包。

