# H: Foundation / Navigation Supplemental 登记

## 结果

- 已将 5 个正式 pytest 文件显式登记到既有 `workbench_browser`，每个文件恰好一个 supplemental owner，不加入 required。
- 小范围 registry 验证 **85 passed / 895 deselected / 7.39s**；四个修改文件 Ruff **PASS**，Python 3.8 AST 解析 **PASS**。
- 原 required 清单与全部旧 group/target 顺序哈希完全不变。观察时当前 required 583、supplemental 91；这两个数只是当前快照，未写入测试断言。
- 两份历史合同仍保留 required **582**、supplemental **85** 及原哈希、owner、顺序。没有扩大错误过滤、没有按文件名前缀排除后来测试。

## 登记与依赖

- `tests/workbench/test_final_foundation_navigation.py`
- `tests/workbench/test_final_foundation_live.py`
- `tests/workbench/test_final_navigation_host.py`
- `tests/workbench/test_final_navigation_boot.py`
- `tests/workbench/test_final_legacy_navigation.py`

- Python/CJS live、host、navigation、probe、actions、faults 等 15 个 helper 只作为依赖，不是测试 target。另验证 11 个明确的宿主/导航/构建源码依赖。
- 现有 `_BROWSER_SCOPES` 已覆盖这 26 个依赖；本轮未重复添加范围，也未改变任何 owner 的 `input_file_scopes`。
- 新增元测试验证真实测试定义、唯一归属、不自动进入 daily required，以及 26 个依赖文件内容变化均使 owner 文件指纹失效。
- `POST_ROUND1_TARGETS` 从 R1 测试移入既有 `workbench_round1_registry_support.py`，只列之前已登记的 lazy-export/CLI 两项及本轮五项。另有反向检查确保不吞掉未审查路径、重复路径或原顺序。

## 历史断言修正

登记前定向执行旧断言：**4 failed / 10 passed / 934 deselected / 2.72s**。其中两项仍要求 scheduler 历史队尾，一项仍要求 capacity 仅一个 target，一项直接把当前 required 总数比较到 582。它们与已经存在的 H3 lazy-export/H5 CLI 登记不兼容，不是本轮产品错误。

本轮将这些历史比较统一使用相同的精确 R1 过滤规则，保留全部历史期望。追加本轮五项后，不将当前总数硬编码回去；新增 owner 检查与旧 owner/顺序哈希检查分别负责新增与保留边界。

## 实际命令

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph TMPDIR=/tmp/aps-task-h-01a08b02 .venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-task-h-foundation-registry-v1 --junitxml=/tmp/aps-task-h-foundation-registry-v1.xml tests/gate_meta/test_workbench_registry_contract.py tests/gate_meta/test_workbench_round1_registry_contract.py -k 'existing_groups_remain_an_unchanged_prefix or raw_targets_and_group_ids_are_unique or run_targets_keep_fixed_owners_order_and_gate_classification or completed_busy_block_files_are_fixed_required_scheduler_targets or new_browser_and_capacity_inventory_never_enters_daily_required_targets or heavy_browser_opt_in_platform_and_build_targets_are_not_must_pass_by_registration or completed_dx_browser_keeps_exact_inputs_and_inventory_counts or round1_preserves_every_old_owner_and_target_order or reviewed_files_append_to_exact_owner_without_promoting_browser or stable_final_capacity or final_capacity_cli_loading or final_foundation'
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache .venv/bin/python -B -m ruff check --no-cache tools/test_registry_groups_workbench.py tests/gate_meta/test_workbench_registry_contract.py tests/gate_meta/test_workbench_round1_registry_contract.py tests/gate_meta/workbench_round1_registry_support.py
```

- XML：`/tmp/aps-task-h-foundation-registry-v1.xml`
- XML SHA-256：`3ac1239258717a1dc5762ae69136b3c0200c20e62c379b905415968521bad6d2`
- 本轮未执行这五个域测试，未复用原 Main 25 checks、B 92-case 功能快照或旧 API 结果作为当前证明。

## H 修改文件 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `tools/test_registry_groups_workbench.py` | `9c180651fa4dde81a5d20a430ba8af47908d00615dce62e465f3b38213f812ce` |
| `tests/gate_meta/test_workbench_registry_contract.py` | `462a9983445d2f74b7286d269b6d395a7d9cae3c9fca1e661b4aa49abe8d3893` |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | `5b4c0624f8d81b5dd9bb1547833c65fa60066c99b27655cdaf4f4a19c69f9b21` |
| `tests/gate_meta/workbench_round1_registry_support.py` | `0e455503b9ca98c65d66dbe4866d6a6b8644981af0f9f648abb2300f7638be81` |

## 并行施工单列

观察区间：`2026-09-10T13:29:23.657001+00:00` 至 `2026-09-10T13:32:36.443725+00:00`。以下只读文件发生外部修改，H 未写入；这里记录两个时点，不将后一个哈希绑定到旧 API/浏览器测试结果。

| 文件 | 前 SHA-256 | 后 SHA-256 |
| --- | --- | --- |
| `tests/workbench/test_final_legacy_navigation.py` | `172e2c6ceec554ded4e6b2bbc4ee0c7bbf7ded45f4ad46d66a76ce84b49405af` | `905a653bda26d9e82a0ccd7d29a397ddea82712092e21d44393f2a3a65e0cb49` |
| `web/routes/workbench/legacy_navigation.py` | `e99b7a973ee2f802b332e45eb822d0da43b458c16e0a6db1b2dc1d2ae620b69f` | `e9a34d9a91a3f2939ac6fe48c5a55cdc8a9bfecdf6ad2ac36e2674625c7deda9` |

- 其余被观察的 target/helper/product 文件在该区间未变。这只覆盖明确列出的文件，不代表整仓源码冻结。
- 四个 H 修改文件哈希用于登记交接；完整前后观察、归属、结构比较、依赖范围哈希和命令结果见同名 evidence JSON。
- 未改其它施工域测试、产品、schema、baseline 或私有 stageG04；未执行 Git 写入、浏览器、全量构建、容量或全门禁。
- 观察 HEAD：`830a58e69faaa64a39d7a238ba2a0a0cd5c9047c`。当前为 dirty 局部 registry 证据，不是 final-HEAD/clean-worktree proof。
- 本轮另有单独授权的 v22 fixture 修复，两文件及完整 65 passed 结果已交接在 `H-v22-fixture-generation-fix-note-20260910.md`，不混入本 registry 结果。
