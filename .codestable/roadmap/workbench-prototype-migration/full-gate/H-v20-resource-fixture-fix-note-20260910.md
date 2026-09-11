# H: v20 资源 Fixture 后续元数据联动

## 结果

- 当前树原用例复现 **1 failed / 1.14s**，失败在旧 `added_tables` 与实际迁移新增表的精确比较；缺少的正是既有 v30/v31 的 7 张表。
- 最终完整 `tests/workbench/test_resource_schema.py`：**145 passed / 10.54s**，0 failures / errors / skips。
- 本次重新运行共享映射 checker 的反向用例：**21 passed / 0.93s**。Ruff 与 Python 3.8 AST 解析均 **PASS**。
- 只改一个测试文件，显式 helper、产品 schema、历史 SQL 和 Git/index 均未改；不是 Main 私有 405/G04 或最终 HEAD 证明。

## 修复与保留

- `test_resource_schema.py:61` 提取本文件内部的精确元数据断言，原旧业务表列、rowid、行值比较不删减。
- 精确新表集合加入 `V30_TABLES` 四表、`V31_TABLES` 三表；空表检查加入外协事实表，复用既有 `assert_v30_source_maps_only` 和 `assert_v31_receipt_maps_only`，没有扩大为集合子集或过滤错误。
- 来源映射只认实际出生证据，没有出生证据保持 NULL；不凭同编号现存批次推断来源，不生成外协回执或 dashboard 处理事实。
- 原主用例仍检查旧 entity ref、inactive / Legacy HOLD 原值、身份时钟、精确 fresh DDL、当前完整 contract、FK、v21 再入幂等和真实备份内的全表/DDL/ref 一致性。
- `test_resource_schema.py:124` 新增 13 个反向用例：7 张后续表逐一缺失、来源映射缺失/猜填批次、凭空回执、旧值变化、旧类型变化、多余表。破坏仅发生在各用例的私有升级数据库内，未修改历史 fixture 文件。

## 实际命令

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph TMPDIR=/tmp/aps-task-h-01a08b02 .venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-task-h-v20-full-v1 --junitxml=/tmp/aps-task-h-v20-full-v1.xml tests/workbench/test_resource_schema.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache .venv/bin/python -B -m ruff check --no-cache tests/workbench/test_resource_schema.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph TMPDIR=/tmp/aps-task-h-01a08b02 .venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-task-h-v20-map-guards-v1 --junitxml=/tmp/aps-task-h-v20-map-guards-v1.xml tests/workbench/test_calibration_dashboard_migration.py::test_old_upgrade_metadata_checker_accepts_only_birth_mapping_and_empty_facts tests/workbench/test_dashboard_external_migration.py::test_additive_mapping_assertion_rejects_missing_guessed_typed_or_invented_evidence
```

- 完整文件 XML：`/tmp/aps-task-h-v20-full-v1.xml`
- XML SHA-256：`7b5eb55166b178b0a4ba75450571ee1b1ad52cb6ab0d688848daeb941607297f`
- 完整文件运行前后，17 个明确输入的 SHA-256 全部一致；这不是整仓源文件冻结扫描。

## 最终文件 SHA-256

`tests/workbench/test_resource_schema.py`

`dbae02d7d89d3179c5fe6b1bb4c50e04c086b50fc6f0684b9c58d911329d8a99`

- 共享 `legacy_migration_current_support.py` 未修改：`952b5b47c60622da1da63c81769c2d1abd9ad5d906906769cb66fe9b5674d04a`。
- frozen `tests/workbench/fixtures/schema-v24.sql` 未修改：`023f7ae15282b1cc0523f218c2b45e1ba6cb4f036d491fe7761cbd8f1f56f03c`。
- `schema.sql` 未修改：`b939a2d6516925863e6f7f0fb3db32ea83a94e4204a8df8c1f6574953bb17b47`。
- 其它 sampled helper、resource schema、三个后续 provider、v30/v31 迁移和 migration_state 均未漂移，完整列表见 evidence JSON。

## 定向检索

- 只检索显式 shared-fixture helper 及已确认消费者。v19 已在 `empty_tables` 纳入 V31、在表集合纳入 V30，并运行两个映射 checker；plan/execution/run/calibration 的已查看完整升级断言也包含后续集合与映射。
- `test_process_identity_schema.py` 的对应合同只执行 v22 单代迁移，不应机械追加 v30/v31。v22 workflow 的完整升级合同已在前一独立交接修复。
- 在上述读取范围内未确认第二处同类遗漏，未改无关测试。这是定向静态检索，不声称覆盖 Main 私有 18 文件的完整清单或执行结果。

## 交接边界

- 观察 HEAD：`830a58e69faaa64a39d7a238ba2a0a0cd5c9047c`；本轮文件仍留给 Main 按哈希同步私有副本和后续 staged。
- 未执行 Git 写入或 hook，未修改原私有临时 405/G04、产品或历史 DDL；未运行浏览器、构建或全门禁。
- 不介入 Main 移往 G05 的未来域 Ruff 闭包，也不伪造 third-party 分类或跳过 hook。
