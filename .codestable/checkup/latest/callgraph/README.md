# 调用图快照说明

本目录保存最近一次调用图体检的机器可读快照,不是临时缓存。

## 来源

- 生成脚本: `.codestable/checkup/scripts/callgraph_extract.py`
- 输出目录: `.codestable/checkup/latest/callgraph/`
- 脚本说明: 只读源码,用函数级调用图和关键值数据流追踪生成嫌疑清单,减少人工审查只看显眼位置的偏差。

## 为什么要提交

- `summary.json` 保存本次扫描的总体计数,例如函数数、调用边、循环、孤岛、风险数据流数量。
- `functions.json` 和 `edges.json` 保存函数级节点与边,方便后续复查某个调用关系为什么被标记。
- `risk_dataflow.json`、`dynamic_unresolved.json`、`high_fan_in.json` 等文件保存可继续下钻的审查入口。

## 后续维护规则

- 重新运行 `.codestable/checkup/scripts/callgraph_extract.py` 后,如果结果用于本次体检或审计结论,应一起提交本目录快照。
- 如果只是本地试跑,不要覆盖并提交本目录。
- 这些文件只代表生成时刻的快照,不是运行时代码依赖。
