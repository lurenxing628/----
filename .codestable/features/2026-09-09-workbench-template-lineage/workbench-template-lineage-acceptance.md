---
doc_type: feature-acceptance
feature: workbench-template-lineage
status: passed
summary: CE独占来源实现验收通过：45项专属、376项后端合跑；共享批次旧删除预期和主线集成仍待处理。
tags: [workbench, lineage, verification]
---

# 验收结论

CE授权产品写域已完成；没有把共享迁移、旧批次复制入口、工作台展示、采用锁定或完整工作台迁移标为完成。
schema objects/contract/install已按主线要求冻结；此后产品调整仅涉及读取验证，DDL两个指纹复核未变。

# 实际证据

- 新模板复制原子写operation_ref→template_operation_ref/revision、完整可逆原始行、实例状态指纹。
- 工作台同步创建新永久实例，保留旧来源和退役事件；同request_key重放不新建来源或实例。
- 手工工艺/批次数量变化可追溯，恢复原值仍排除；状态和资源分配变化留版本但不单独污染工艺口径。
- 明确撤回不删原来源；污染实例再复制不重新合格，父实例后续修改也不覆盖复制当时的版本。
- 旧实例及其复制不猜配。5个与模板字段相同且完整报工的未关联实例仍为candidate_count=5、sample_count=0。
- 真5个有来源且完整报工的实例给出中位数3；25个实例只取最近20，中位数15.5。4个保持null。
- 模板改定额修订分组、删除重建模板/实例、改码、执行更正均不会换绑历史来源或执行报工。
- 同revision但完整模板内容不一致、错父来源、损坏指纹/事件标记明确拒绝，未变成空结果或0。
- 创建或同步的来源写入失败恢复批次、原工序、旧来源、事件及序列；caller回滚也保留全部原行。
- BLOB/NULL/0在原表、复制内容和原始事件中保留类型；超16MB证据拒绝复制并回滚，不截断原BLOB。

# 测试

运行时实测：`.venv/bin/python --version` 为 **Python 3.8.10**。

最终后端命令：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_template_lineage_schema.py \
  tests/workbench/test_template_lineage_writes.py \
  tests/workbench/test_template_lineage_calibration.py \
  tests/workbench/test_template_lineage_integrity.py \
  tests/workbench/test_calibration_method.py \
  tests/workbench/test_calibration_integrity.py \
  tests/workbench/test_calibration_routes.py \
  tests/workbench/test_calibration_scale.py \
  tests/workbench/test_execution_ledger.py \
  tests/workbench/test_execution_ledger_contracts.py \
  tests/workbench/test_execution_ledger_source_integrity.py \
  tests/workbench/test_process_identity_schema.py \
  tests/workbench/test_process_workflow_state.py
```

结果：**376 passed in 40.34s**。其中本轮专属45项，既有校准85项，执行/模板身份/工作流246项。
专属fixture固定读主线的schema-v26.sql，只用临时SQLite；没有生产库迁移。

另运行：

```bash
.venv/bin/python -m pytest -q -p tests.workbench.test_template_lineage_batch_support \
  tests/workbench/test_batch_actions.py tests/workbench/test_batch_commands.py \
  tests/workbench/test_batch_execution_ledger_atomic.py \
  tests/workbench/test_batch_execution_ledger_boundaries.py \
  tests/workbench/test_batch_execution_ledger_projection.py \
  tests/workbench/test_batch_files.py tests/workbench/test_batch_transport.py
```

结果：**75 passed, 1 failed in 5.73s**。
失败为`test_delete_preserves_every_unrelated_table_and_other_batch`：原affected集合漏掉新增来源退役事件及该表序列推进。
该共享测试不在写域，已明确通知主线。新增`test_delete_changes_only_target_business_rows_refs_and_append_only_event`
逐表核对无关数据原样，且只有来源事件序列+1，原origin不变；它在上述376项最终命令内通过。
这里没有把76项批次回归报告为通过，也没有修改共享测试来掩盖差异。

# 静态检查

- 全部15个本轮产品/测试文件scoped ruff通过。
- 同范围pyright：0 errors、0 warnings、0 informations。
- Python3.8语法扫描15文件：0读取失败、0拒绝、0后续语义风险。
- 新增模块及改动的calibration_facts/batch_template_ops大小、复杂度扫描均为空；未改门槛或allowlist。
- batch_operations原有sync_preview/update/_validate复杂度为27/17/17；这些函数的原实现未重构。本轮只替换插入接点并在sync删除之前加schema检查，不宣称该原文件复杂度已全绿。

# 交接与边界

对象和API详见同目录api/design。主线统一v27的lineage+trial迁移、真实26→27备份/旧行保留证明及registry不由CE写入。
额外旧入口batch_copy.py、calibration.py来源提示/详情分组以及上述共享测试预期仍需主线接合。
采用、锁定、采用审计和导入锁保护没有实施；capabilities.adopt/lock保持false。

未运行scripts/run_quality_gate.py：共享目录有大量并发脏改，完整门禁会落共享证据，超出独占写域。
本轮是局部dirty验证，不是最终HEAD上的clean-worktree proof，也不是Win7真机验收。
没有触碰生产库、旧预览63938/PID68615，没有spawn/create_thread/fork，没有stage/commit。
本轮新增文件及对三个授权接点的修改均保持未提交；已有暂存、未暂存及未跟踪改动均未回退或清理。
