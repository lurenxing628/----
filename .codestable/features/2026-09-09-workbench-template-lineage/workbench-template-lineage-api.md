---
doc_type: feature-implementation
feature: workbench-template-lineage
status: implemented
summary: CE来源记录与真实校准事实交接，DDL已冻结，迁移及剩余共享接点由主线负责。
tags: [workbench, lineage, integration]
---

# Schema接合

```python
from core.infrastructure.workbench_template_lineage_schema import (
    objects,
    contract_issues,
    install,
)

# 主线统一v27迁移持有事务，不要用executescript引入隐式提交。
with TransactionManager(conn).transaction():
    install(conn)
    assert contract_issues(conn) == []
```

前置为已安装的metadata、process永久身份及plan永久身份。没有clock/seed初始化行。
第一次安装不创建任何旧实例来源或birth；已有完整结构重复安装仅检查，部分结构不修复。
`objects()` 返回15项DDL；可以合入新库schema，版本登记仍由主线执行。
冻结指纹及不得静默修改DDL约定见design“主线协调项”。

# 写入API

```python
writer = TemplateLineageWriter(conn)
writer.require_ready()
new_id = writer.copy_template(batch_id, template_id)
new_id = writer.copy_instance(batch_id, source_operation_id)
changed = writer.withdraw(operation_ref, reason)
```

以上全部要求调用方已持有事务；复制内部使用SAVEPOINT，不提交外层事务。
template_id/source_operation_id由服务器真实写链取出，不是让HTTP提交未经证实的来源声明。
copy_template每次创建新实例并保存当时真实模板ref/revision/完整行；不读model的NULL默认值。
copy_instance不重新匹配当前模板：有已知来源就保存父来源和复制时事件版本，无来源就仍然无来源。
来源已污染或撤回的复制仍保留原来源，`source_eligible=0`，不能产生有效校准样本。
withdraw只追加明确原因，不删原来源，不改执行ledger；当前无HTTP撤回入口，也不是报工更正或校准采用。
复制的命令幂等由既有WorkbenchCommandService的request_key/回执实现，不用same-code当幂等键。

已接入授权写链：

- batch_operations.insert_operation：工作台同步与批量复制。
- batch_template_ops.create_batch_from_template_no_tx：BatchService模板创建以及旧Excel auto_generate_ops导入。
- 工序UPDATE、批次数量/零件变化、删除/REPLACE：来源专属触发器只追加原始状态和退役记录。

`core/services/scheduler/batch_copy.py`仍需主线接合：在其现有事务中，用writer.copy_instance替代batch_op_repo.create/model重建。
这是额外入口，不得把当前CE接合写成所有旧复制入口已经迁移。

# 只读来源API

`TemplateLineageQuery(conn).read(operation_refs)` 返回available、origins、events、current、templates、lineages、problems。
可以包含验证所需祖先，调用方按明确operation_ref取结果；不能把祖先一起当本次执行样本。
模板证据指纹、birth、实例原始状态、事件污染标记、来源复制版本和同修订模板完整内容均被复核。
历史来源可读，不要求当前模板或实例还活着；退休/污染/撤回分别保留明确排除原因。
无schema返回available=false而不写入；部分/损坏schema或矛盾证据明确失败。
读取上限为10000来源实例/100层复制祖先、50000状态事件；模板/实例证据及事件原始字节分组上限16MB，不截断。

# 校准事实接合

`CalibrationFacts.read`已真实调用来源查询，不再恒template=None。每个执行实例只走一次共享ledger投影。
返回原有rows/fingerprint/snapshot，以及：

| 字段 | 含义 |
| --- | --- |
| samples_by_template | 按模板永久ref分组的有明确来源实例；各行仍可能因旧revision/污染/未完工而排除 |
| unbound_samples_by_part | 没有明确来源的同零件核对项，永远不是有效样本 |
| samples_by_part | 全部审计实例集合；不是特定模板详情的selected样本集合 |
| source_constraints | 按实际缺来源状态生成的限制，不能继续写死全部未关联 |
| lineage_available | 当前读取是否有完整来源schema |
| unbound_instance_count | 未关联实例数，不是样本数 |

建议rows已按准确模板ref/revision计算近20、至少5、中位数；source_constraints和详情适配尚属主线。
`core/services/workbench/calibration.py`建议改用facts.source_constraints；详情样本使用
`samples_by_template[template_ref] + unbound_samples_by_part[part_no]`，对后者继续明确标为未关联候选。
candidate_scope_basis应体现明确关联加同零件未关联核对项，不再声称全部样本未关联。
写上下文和adopt/lock依旧false；本任务没有采用锁定、导入跳过锁定或审计采用事务。

# 测试登记

主线registry应登记4个真实测试文件：test_template_lineage_schema.py、test_template_lineage_writes.py、
test_template_lineage_calibration.py、test_template_lineage_integrity.py，共45项。
test_template_lineage_support.py只作专属fixture，读取主线固定的fixtures/schema-v26.sql。
test_template_lineage_batch_support.py是显式`-p`加载的临时库安装插件，不是产品或正式迁移入口。
共享test_batch_commands.py的删除affected集合需主线纳入来源事件和该表的sqlite_sequence推进；专属删除测试已逐表证明其余数据不变。
