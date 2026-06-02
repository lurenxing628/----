# 概念身份证 · graph_analysis_mode(工序图分析模式)

- **status**: current
- **owner_area**: scheduler
- **runtime truth(实测)**: `field_type=enum`，`default='on'`，`choices=('off','report','on')`；未知值 strict 下 `raise ValidationError[1001]`。

## 规范定义
调度配置项，控制工序图分析的关闭/只报告/参与排产三态。当前默认 `on`。

| 值 | 含义 |
|---|---|
| `off` | 关闭图分析，不导入图模块，不写 graph_analysis 摘要，不要求 NetworkX |
| `report` | 只生成分析摘要，**不改变排产结果**(只写 result_summary.algo/diagnostics.graph_analysis) |
| `on` | 图可用时**参与排产**：ready 队列 + 图评分 + 候选方案自动选择 |

## 真理之源
- `core/services/scheduler/config/config_field_spec.py`(spec/choices/labels)
- `core/services/scheduler/config/config_snapshot.py:43`(default `'on'`)
- `.codestable/architecture/ARCHITECTURE.md` 第 6 节(:72-78，当前现状)

## ⚠️ 历史/过期来源
- `开发文档/ADR/0012-networkx-graph-foundation-boundary.md`(2026-05-17，状态"已决策")——**口径已过期**：见 `semantic-drift-ledger.md` SEM-0001。

## 禁止含义
- ❌ "on 只保存配置不执行图分析"
- ❌ "report/on 永远不改变排产结果"——**on 已改变排产结果**(ARCHITECTURE.md:78)。

## 守卫
- `.codestable/semantics/tests/test_config_field_properties.py`(默认值自洽 + 未知值 raise)
- `.codestable/semantics/tests/__snapshots__/graph_config_defaults.json`(8 个 graph_* 字段默认值/choices 快照)
