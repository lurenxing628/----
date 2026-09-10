---
doc_type: issue-fix
status: partial
created: 2026-09-10
summary: DV 修复固定 v29 DI fixture 和 CY 外协零数据预期，完成已交付测试登记；后端及 UI 通过，保留开发中 discovery 与 untracked-proof 失败
tags: [workbench, schema30, outsourcing, regression, registry, DV]
---

# 结论与边界

- 本轮授权修复和登记完成。不是全仓门禁通过，也不是 clean-worktree proof。
- 手工修改六个测试/support/登记文件及本文；没有修改产品、固定 SQL、历史 migration、主线 v30 测试/support、DN UI 文件或 main live support/server。
- 所有执行使用项目 Python 3.8.10 `.venv/bin/python`、独立临时 SQLite/host、显式 pytest 路径、`-p no:cacheprovider`、独立 `--basetemp` 和 `--junitxml`。
- 证据目录：`/tmp/aps-dv-schema30-A9HLXZ`。未运行 fullgate、全局前端 build、stage/commit，未停止任何旧 preview。

# 修改文件

| 文件 | 精确修改 |
| --- | --- |
| tests/workbench/outsourcing_support.py | 从固定 schema-v29.sql 构造旧库；读取同一份字节先校验 SHA，再执行 DDL；验证版本 29、外协对象和两个 v30 identity guards 均不存在，然后显式 install DI |
| tests/workbench/test_outsourcing_schema.py | 新增两个拒绝非固定源的测试：current schema 与改变过字节的 v29 必须在创建数据库前失败 |
| tools/test_registry_groups_workbench.py | 追加五个 required 和一个 supplemental；补确切 source/support scopes，原 group/target 顺序保留 |
| tests/gate_meta/test_workbench_registry_contract.py | 同步精确归属与追加顺序、v29 SHA、source selection 和 supplemental 合同；discovery 函数 AST 不变 |
| tests/gate_meta/test_long_gate_manifest.py | required targets 506 -> 511；仍为 32 groups |
| tests/workbench/dashboard_widgets_probe.cjs | 固定 v28 SHA；current30 external 完整读取无数据必须 no_data/risk_count=0/unknown_count=0/entry.enabled=true；固定旧库缺 schema 必须 503 对应错误且不显示零；未知齐套总风险仍为 null |

DI 原 87 项未删除、未 skip，rawfacts、原始 blob/date、同 key 重放/并发、rollback、refs 与历史断言保留。DDL rollback/partial/missing 仍在真实固定 v29 加显式 DI 的基线上执行，不是完整 v30 改成 29 标签。

固定 v29 SHA-256：`d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648`。
固定 v28 SHA-256：`2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52`。

DS labels 的 current30 support 和 35 项测试原样通过，无需修改期待；可空标签、旧字段精确集合、未知不猜、同编号替换、只读快照与存储失败传播的断言没有放宽。

# 新增登记

以下路径均在 `tests/workbench/` 下，都是固定 target，不使用测试路径 glob。

| group | 分类 | 文件 |
| --- | --- | --- |
| workbench_outsourcing | required | test_outsourcing_targets_labels.py |
| workbench_dashboard | required | test_dashboard_external_reads.py |
| workbench_dashboard | required | test_dashboard_external_identity.py |
| workbench_dashboard | required | test_dashboard_external_snapshot.py |
| workbench_mainmigration | required | test_outsourcing_identity_migration.py |
| workbench_browser | supplemental | test_outsourcing_widgets.py |

全仓 required 为 32 groups / 511 targets；workbench required 238；supplemental 65 targets。现存 group IDs 和 target 顺序均保留为原前缀，coverage 的 missing/duplicates/unknown 全空。DN 依本轮后续明确授权登记；DP 和 DT 开发中文件未抢登记。

# 真实测试结果

| 范围 | 结果 | XML |
| --- | --- | --- |
| 修改前 DI 最小复现 | 1 fixture setup error，停在旧版本断言 | fixture-before.xml |
| 修复后 DI 原五文件 | 87 passed | di-after.xml |
| 原 DI 87 + 原相邻 20 | 107 passed，25.09s | di-neighbor.xml |
| DI schema，含两个新增拒绝合同 | 20 passed | di-schema-contract.xml |
| DO 三文件 + DS + 主迁移 + Dashboard host + calibration host | 94 passed | external-current.xml |
| 原 Dashboard 八文件 + DO 三文件 | 118 passed | do-combination.xml |
| 最终后端 22 文件联合执行 | 264 passed，45.80s | backend-final.xml |
| 修改前 CY | 1 failed / 1 passed，精确复现禁止 external 显示 0 的旧断言 | cy-before.xml |
| 修改后 CY + DN UI | 4 passed，61.46s | ui-after.xml |
| registry + manifest + full-debt registry contract | 444 passed / 2 failed | meta.xml |
| 真实 registry 消费端三个文件 | 57 passed | registry-consumers.xml |

原相邻 20 的实际三文件为 `test_dashboard_host_connection.py`、`test_dashboard_schema.py`、`test_execution_ledger_commands.py`，由 DI 原 `/tmp/aps-di-neighbor-pytest-cache/v/cache/nodeids` 核对，原 107 确实单独执行过。

最终 264 项不重复计数：DI 89 + execution ledger commands 10 + Dashboard 118 + DS 35 + 主迁移 6 + managed host 6。managed host 是 `test_run_adoption_host.py`、`test_trial_adoption_host.py`、`test_calibration_adoption_host.py` 各两项。

计数澄清：DO 三个新文件本身是 47 项，不是 124 项。加原 Dashboard 71 项为 118，再加主迁移 6 为 124；这 124 项全部在最终组合中实跑通过。DS35 + 主迁移6 = 41，以及主迁移6 + managedhost6 = 12，也都是该次联合执行的可核对通过子集，不冒充独立执行回执。

上述执行无 skip。107/118/264 三次中的两条 warning 来自原 `record_property` 与 `junit_family=xunit2` 的格式提示，不是产品失败。

UI 使用 Chromium `109.0.5414.46`，没有重建共享 assets。CY 实测四场景/36 图/8 边界/4 次重启；DN 本轮最终源码实测四场景/46 图/17 边界/4 次重启。两者 errors/external 均空，临时 server 均正常关闭；源码 SHA 与服务端原始表保留验证通过。已人工查看 CY 浅色 1392 概览、深色 1920 处置表单，未见遮挡。

五个本轮 Python 文件 Ruff 全过，Python 3.8 语法扫描解析拒绝 0、语义风险 0；probe `node --check` exit 0。没有声称在 Win7 真机运行。

# 剩余失败

1. `test_discovery_reports_unregistered_real_tests_without_expanding_targets`：执行时剩余八个开发中测试。DT 的 `test_dashboard_external_handling_api.py`、`test_dashboard_external_handling_atomic.py`、`test_dashboard_external_handling_commands.py`、`test_dashboard_external_handling_identity.py`、`test_dashboard_external_handling_schema.py`；DP 的 `test_system_restore_entrypoint.py`、`test_system_restore_entrypoint_fail_closed.py`、`test_system_restore_entrypoint_recovery.py`。discovery 没有过滤或降级，等待各 owner 完成交接。
2. `test_quality_gate_required_startup_and_full_debt_share_registry`：`tests/gate_meta/test_full_test_debt_registry_contract.py:1264` 首先命中 untracked 的 `tests/gate_meta/test_workbench_registry_contract.py`。本轮库存 required 未 tracked 共 238 个；没有 stage 来伪造 tracked-proof，也没有放宽该断言。

本轮没有发现需派产品 repair 的新失败。两项 meta 失败均为登记/工作区状态，不是产品故障；初始 DI setup error 也没有误报为产品坏。

# 保留证据

- HEAD：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`；六个本轮文件均保持未提交。
- 42 个受保护文件哈希前后一致，包括 schema.sql、v1..30 migrations、固定 v24..29、主线外协迁移 test/support、DS labels test/support 和 frozen_bundle。
- 整个 staged diff SHA-256 前后均为 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`；frozen_bundle 仍为 staged 200+/0-。
- 原稿在证据目录的 `before/`；`before-hashes.json`、`protected-verification.json`、`registry-inventory.json`、`test-receipts.json` 保存修改范围、原顺序、真实逐项结果和完整剩余清单。
- 各次测试有重叠，不把各行相加为唯一用例数。完整精确文件集见 `test-receipts.json`；复跑需使用新的临时目录，不覆盖本证据。
