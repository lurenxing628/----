---
doc_type: feature-implementation
feature: workbench-calibration-read
status: implemented
summary: BV只读校准后端交接，独立注册函数和稳定DTO，来源不足如实返回。
tags: [workbench, calibration, api]
---

# 集成入口

主代理在共享蓝图注册处导入并调用：

```python
from web.routes.workbench.calibration import register_calibration_routes
register_calibration_routes(bp)
```

本任务没有修改 `web/routes/workbench/__init__.py`、schema、registry、构建或已有process/execution服务。
只注册以下GET；不存在采用/锁定/普通工时update的别名。

| 方法和路径 | 行为 |
| --- | --- |
| `GET /api/workbench/v1/calibration` | 分页列表 |
| `GET /api/workbench/v1/calibration/<suggestion_ref>` | 当前筛选范围内建议及完整待核对实例出处 |
| `GET /api/workbench/v1/calibration/export` | 当前筛选的全部建议行，不只当前页；CSV或XLSX |

统一外壳：`{ok:true,schema_version:1,data,meta:{source:"production",time_basis:"factory_local",request_ref,as_of,snapshot_ref},warnings:[]}`。
错误沿用工作台JSON外壳，GET失败始终 `committed:false`。成功及失败均不缓存。

# 参数与快照

| 参数 | 允许值/默认值 |
| --- | --- |
| `query` | 图号、零件名、工序名、序号的字面子串搜索，忽略大小写，最多200字；`%_`不是通配符 |
| `part_ref` | 可选48位永久零件引用，不能传图号 |
| `source` | 可选 `internal/external/unknown` |
| `status` | `all`（默认）、`suggested`、`insufficient_data` |
| `deviation` | `all`（默认）、`over_20_percent`（严格绝对相对偏差大于20%，不含恰好20%） |
| `page/size` | 默认1/20；页码1至1000000，每页1至200 |
| `sort` | `part_no`（默认）、`operation_label`、`old_unit_hours`、`suggested_unit_hours`、`sample_count`、`absolute_deviation_percent` |
| `direction` | `asc`（默认）或`desc`；未知数值在两种排序下均最后，永久引用稳定破同值 |
| `snapshot_ref` | 第一页可不传；后续页、详情、导出必须传 |
| `format` | 仅导出支持 `csv`（默认）或`xlsx` |

未知/重复参数明确拒绝。`as_of`由服务端在SQLite读取快照开始后捕获，不接受调用方伪造历史时点。
Scope含上述筛选、排序、size、kind和method_version，不含page；详情、导出必须原样带回非默认筛选/size。
同快照内容与generated_at稳定，TTL沿用公共令牌900秒；数据/范围变化或过期返回 `snapshot_stale`，不静默刷新。
先对原始事实做指纹校验，再在原as_of投影，避免把快照后新增的合法报工误报为来源损坏。

# DTO

列表 `data`：`items[]`、`page:{number,size,total,total_pages,has_more}`、`summary:{total,suggested,insufficient_data,over_20_percent}`、`scope`、`source_constraints`、`capabilities`、`blocked_reasons`、`exports`。

每行包括：
- `suggestion_ref/operation_ref/template_operation_ref`：同一个永久模板工序引用，不是内部行号或执行实例。
- `template_revision/template_snapshot`：当前模板行修订与内容指纹；`part_ref/part_no/part_name/sequence/operation_label/source`提供业务显示字段。
- `old_unit_hours/suggested_unit_hours`：小时/件，0与null分开。
- `deviation_percent/absolute_deviation_percent`：百分数，不是比例；`over_20_percent`由未四舍五入的Decimal运算判断。
- `deviation_basis`：`relative/old_zero/old_unknown/suggestion_unavailable/not_representable`；不能有限表示时不输出Infinity。
- `sample_count`：选中有效样本数0至20；`eligible_sample_count`：裁近20前的有效数；`candidate_count/excluded_count`：待核对实例/未选数。
- `sample_refs/sample_revisions`：选中执行工序引用及样本指纹、模板修订、报工修订引用。
- `exclusion_reasons[]:{code,message,count}`：按实例去重计数，同一实例可有多种排除原因。
- `method_version/generated_at/as_of/snapshot_ref`、`status`、`capabilities`、`blocked_reasons`、空写入上下文。

详情 `data.suggestion`是同一行；`data.samples[]`是该零件的完整待核对执行实例，**不是已证实的模板样本关联**。
`candidate_scope_basis="same_part_unbound_not_template_match"` 必须保留语义；UI不可把candidate_count当sample_count。
每个实例有 `sample_ref/execution_operation_ref`、批次/工序业务号、nullable来源模板/修订/证据、sample_revision、报工/修订refs、完整reports及correction_history、legacy_facts、data_gaps、qty/hours、eligible/selected和逐项排除原因。

# 当前真实限制

来源核对证据：`schema.sql` 的 `BatchOperations` 字段，`core/services/workbench/batch_operations.py:insert_operation` 和
`core/services/scheduler/batch_template_ops.py:_build_batch_op_payload` 都没有保存模板永久引用及复制时修订。
当前生产入口的lineage恒为None，故所有有效样本计数为0、建议值为null、状态为insufficient_data。
这不是示例或故障降级：模板原定额和执行待核对记录均来自真实库。不能通过同part_no/seq、工种、当前相同工时来猜关联。
算法正确性测试使用真实执行投影，并仅在测试内显式声明来源关系；不代表生产DB已有这种关系。

`adopt/lock`始终false，`write_context.capabilities=[]/write_token=null`；清楚返回 `adoption_schema_unavailable`。
未来公用层必须提供：
1. 创建/复制批次工序时原子保存实例永久引用 -> 模板永久引用 + 当时修订 + 来源证据，不追溯猜配旧数据。
2. 采纳时重新核对完整样本来源/修订、方法、旧定额及模板修订；不能只验证一个前端建议数值。
3. 同一事务更新模板定额、采用来源/人员/时间/原因/锁定状态；建立可查审计与明确失败回执。
4. 工时导入先跳过锁定项并汇报数量/原因，不能覆盖后补标记；普通工时更新不能冒充采用。
5. 既有批次、历史计划和实际事实不回写；只影响后续模板使用。

# 导出与上限

CSV为UTF-8 BOM；XLSX含“校准建议”和“范围与口径”。每个导出行含模板引用/修订、定额、样本refs/修订、排除计数、方法、生成时间、as_of、snapshot和筛选范围。
样本完整历史通过详情读取；导出是全部筛选建议行，不把同零件候选重复展开成笛卡尔积。
文本公式前缀 `= + - @` 及前导空白/制表符/换行经过文本转义；快照令牌若以 `-` 开头也可能加单引号，含义不变。
响应头 `X-Workbench-Snapshot/As-Of/Row-Count`提供未转义快照和实际导出行数，文件名固定由服务端时点构造。
上限：当前零件范围最多10000个模板、10000个执行实例；修订沿用共享50000行/投影16MB限制；JSON 8MB、导出16MB，XLSX单元格32767字符。
超限明确413；XLSX长单元格要求改用CSV，不截断。空导出422；损坏源500/明确409，不包装为空列表。
搜索/来源筛选在有界模板集内完成；超过10000模板时先使用part_ref缩小源范围。
