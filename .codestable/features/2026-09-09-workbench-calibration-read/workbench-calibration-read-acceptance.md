---
doc_type: feature-acceptance
feature: workbench-calibration-read
status: passed
summary: 只读子任务331项局部测试通过；生产来源关联不足保持不可建议，采纳和共享集成尚未完成。
tags: [workbench, calibration, verification]
---

# 1. 接口契约核对

独占GET注册入口：`web/routes/workbench/calibration.py:103` 的 `register_calibration_routes(bp)`。
列表、详情、CSV/XLSX在独立真实Flask蓝图中验证；需由主代理接入共享应用蓝图。
DTO和参数完整交接见同目录 `workbench-calibration-read-api.md`。当前模板都有永久operation_ref、当前修订、内容快照、旧定额、样本/排除计数和空写上下文。
分页、详情、导出绑定同scope、as_of和snapshot；过滤条件、页大小或事实变化返回snapshot_stale。
导出包含全部筛选建议行，MIME、文件字节、行数和快照响应头实测；不是仅当前页导出。

# 2. 行为与决策

- `calibration_samples.py:115`仅消费统一ExecutionProjection；所有新旧执行整合仍由原ExecutionLedgerService执行。
- `calibration_method.py:20/40/53`实现近20个有效整道完工实例、至少5、中位数、严格大于20%的相对绝对偏差。
- 排除暂停、异常、数量/小时未知、不完整、非自制加工口径、来源缺失/不同模板/不同修订；不看备注关键词。
- 小时和数量0不变成null，null不变0；旧定额0/null及超浮点表达范围不生成Infinity。
- `calibration_facts.py:31`从实际实例创建无lineage的候选，没有同序号关联，没有原型SEED。
- `workbench_calibration.py:23/27`的adopt/lock恒false，明确adoption_schema_unavailable，不存在采用或锁定POST入口。
- schema和既有批次/计划/执行记录都没有被修改。测试内用query_only和全表/schema快照证明GET/导出无写入。

# 3. 验证记录

运行时：仓库 `.venv/bin/python --version` 实际为 **Python 3.8.10**。

最终命令：

```bash
.venv/bin/python -m pytest -q tests/workbench/test_calibration_method.py tests/workbench/test_calibration_routes.py tests/workbench/test_calibration_integrity.py tests/workbench/test_calibration_scale.py tests/workbench/test_execution_ledger.py tests/workbench/test_execution_ledger_contracts.py tests/workbench/test_execution_ledger_source_integrity.py tests/workbench/test_process_identity_schema.py tests/workbench/test_process_workflow_state.py
```

结果：**331 passed in 27.89s**，其中校准85项，已有执行/模板身份/确认状态回归246项。
覆盖不足5、恰好5、20/25、异常最新样本不挤掉旧有效样本、离群值中位数、精确±20%、0/null、修订不一致、重复实例拒绝、跨计划仅一个实例、更正历史完整、过期快照、公式前缀、破坏源JSON/修订链/身份/DDL、旧原表与归档不一致。
测试中的来源关系只在算法测试内显式声明，不存在测试关联进入生产HTTP或数据库的通道。

大容量：10000模板和10000实例分别恰好可读，10001分别413；JSON/导出字节限制与XLSX长单元格拒绝均覆盖。
另运行 `test_calibration_scale.py::test_many_templates_share_one_projection_without_cartesian_samples`：
**1000模板 + 2000实例，1次project_loaded、84 SQL，读取0.207秒；1 passed in 0.86s。**
这是本机临时SQLite单次观测，不是Win7真机、p95、峰值RSS或整个迁移容量验收。

静态检查：
- scoped `ruff check`：All checks passed。
- scoped `pyright --project pyrightconfig.gate.json`：0 errors, 0 warnings, 0 informations。
- `tools/scan_py38plus_syntax.py --fail-on-hit`：14文件，Python3.8拒绝/后续语义风险均0。
- 门禁扫描API `scan_complexity_entries/scan_oversize_entries`：均空，未改15/500门槛或allowlist。

# 4. 术语一致性

suggestion_ref是模板永久引用；sample_ref是执行实例永久引用；单条报工和更正有各自独立refs。
candidate_count是待核对数，不是有效样本数；同零件候选不冒充同模板修订关联。
generated_at等于该读取快照as_of；快照在SQLite源快照开始后捕获时间，并在投影前复核旧token事实指纹。

# 5. 架构归并

新增9个产品模块：DTO、repository、事实读取、样本核验、来源完整性、统计方法、列表/详情编排、导出和独占路由。
没有修改共享架构文件；按独占写域要求将集成职责交回主代理，不代表中心架构文档已更新。

# 6. 需求回写

只回写本功能专属design/checklist/API/acceptance。批准的D05合同没有被改写。
中心requirements未改，采纳/锁定、导入保护等原迁移要求仍保留。

# 7. Roadmap回写

共享roadmap/items未改。不能把本子任务验收等同于整个wb-calibration条目done。
当前源码schema及两条批次创建路径未保存模板来源永久引用/修订，生产read入口只能给真实模板和不足原因，尚不能给有证据的非空建议值。

# 8. 注意事项

没有写共享attention、memory或test registry。没有启动子代理、spawn/create_thread/fork、依赖升级、生产库迁移或历史回写。
全部18个新增文件保持未提交，未操作原有staged/unstaged/untracked内容。

# 9. 遗留与证明边界

主代理需接入register_calibration_routes和4个test_calibration测试文件的registry，并在整合后的应用执行真实UI回归和完整门禁。
本轮未运行 `scripts/run_quality_gate.py`：共享工作区已有大量并发脏改，该入口要求clean证明并会写共享证据，超出本子任务独占写域；本轮仅为局部dirty验证，**不是clean-worktree proof**。
当前只读服务不要求生产库升级；本轮没有打开或修改生产库。没有声明真实生产数据已有合格样本。
后续公用schema必须提供持久化实例->模板来源修订证据，以及采纳原子审计、锁定、导入前跳过锁定项的保护；详见API文档“当前真实限制”。
