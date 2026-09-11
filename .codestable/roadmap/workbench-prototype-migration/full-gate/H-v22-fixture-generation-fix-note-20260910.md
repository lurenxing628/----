# H: v22 后续 generation 合同修复

## 结论

- 原树复现：`test_v22_upgrade_preserves_every_business_row_and_identity_and_adds_no_confirmations` **1 failed / 1.44s**，失败在迁移前 `assert_v22_schema` 的完整错误集合比较。
- 最终两文件源码上，完整 `tests/workbench/test_process_workflow_schema.py` **65 passed / 6.82s**；Ruff **PASS**。
- 共享 v30/v31 映射校验的定向反向测试 **21 passed / 1.13s**。这是局部验证，不是 G04、最终 HEAD 或 clean-worktree proof。

## 修改

- `tests/workbench/process_v22_migration_support.py:64` 显式加入 outsourcing 20、plan write guard 2、dashboard external 13 个后续对象；精确缺失前缀与各 provider 保持一致。仍要求这些对象不存在于 v22，仍完整比较错误集合，没有子集判断或错误过滤。
- `tests/workbench/process_v22_migration_support.py:152` 将 v30/v31 新增的 7 张表纳入精确新表集合；复用 `legacy_migration_current_support.py` 的源出生证据、NULL 未知归属、空事实表、回执到 item 的一一对应及 FK 校验。
- `tests/workbench/test_process_workflow_schema.py:97` 新增 46 个反向用例：35 个诊断逐一缺失、1 个未知诊断、7 张后续表逐一缺失、2 种错误来源映射、1 张多余表。
- 原完整迁移用例不删减：真实备份、所有旧表列/FK/rowid/值/SQLite 类型、旧 DDL、实体 ref、执行历史原始列与绑定、二次启动不迁移、重开后的整表/DDL 一致性均保留。

## 最终命令

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph TMPDIR=/tmp/aps-task-h-01a08b02 .venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-task-h-v22-full-v2 --junitxml=/tmp/aps-task-h-v22-full-v2.xml tests/workbench/test_process_workflow_schema.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache .venv/bin/python -B -m ruff check --no-cache tests/workbench/process_v22_migration_support.py tests/workbench/test_process_workflow_schema.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph TMPDIR=/tmp/aps-task-h-01a08b02 .venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-task-h-v22-map-guards-v1 --junitxml=/tmp/aps-task-h-v22-map-guards-v1.xml tests/workbench/test_calibration_dashboard_migration.py::test_old_upgrade_metadata_checker_accepts_only_birth_mapping_and_empty_facts tests/workbench/test_dashboard_external_migration.py::test_additive_mapping_assertion_rejects_missing_guessed_typed_or_invented_evidence
```

- 完整文件 XML：`/tmp/aps-task-h-v22-full-v2.xml`
- XML SHA-256：`5a4aa0688fb2dbcdb940c116f2d03c455d3bc7d9b9dec1e29f1565485567b404`
- 最终完整测试前后，对 12 个明确输入文件采样的 SHA-256 全部相同；更早的全文件测试与 Ruff 导入排序修正分别记录，不作为最终文件哈希的结果。

## 源码 SHA-256

| 文件 | 最终 SHA-256 |
| --- | --- |
| `tests/workbench/process_v22_migration_support.py` | `69400b86c459303f00d88b2ea6e292bb53c5ae6119e006ae0c32c88b01d3e847` |
| `tests/workbench/test_process_workflow_schema.py` | `a1cebbc09332c1fdc627d41751fa65fc0227835e48a105c9900793579e5bbe1c` |

- `tests/workbench/fixtures/schema-v24.sql` 前后不变：`023f7ae15282b1cc0523f218c2b45e1ba6cb4f036d491fe7761cbd8f1f56f03c`。
- `schema.sql` 前后不变：`b939a2d6516925863e6f7f0fb3db32ea83a94e4204a8df8c1f6574953bb17b47`。
- 三个 provider、v30/v31 迁移、migration_state 和两个复用的测试 helper 均在采样范围内，未发生漂移，完整哈希见同名 evidence JSON。

## 边界

- 只修改上述两个测试侧文件，未修改产品 schema、历史 SQL、基线或 Main 的私有 G04 副本；未执行 Git 写入、浏览器、业务容量或全门禁。
- 观察到的 HEAD 为 `830a58e69faaa64a39d7a238ba2a0a0cd5c9047c`，不是本轮最终 HEAD 证明。
- Main 可按这两个文件的精确哈希机械更新其私有副本后重跑自己的 21 targets；H 不将原 G04/旧 API 结果改写为最新结果。
