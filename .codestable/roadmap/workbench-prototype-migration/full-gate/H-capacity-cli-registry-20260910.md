# H 容量 CLI 守卫登记交接

- 状态：Main 的新 CLI 守卫已登记；H 轻量回归与含 tests 导入扫描通过。
- 本轮只修改 registry 与两个现有 meta 测试文件，不修改 Main 的 CLI/新测试、其他容量文件或产品。
- 原容量 5000 x 4 正式交接保持原样，不重写为新 HEAD proof；H 没有重跑正式容量或 Main 的真实小档业务 CLI。

## 登记

- `tests/workbench/test_final_capacity_cli_loading.py` 的唯一 owner 为既有 `workbench_run_compute_capacity`，分类 **supplemental**。这是容量域的轻量 CLI 守卫，不把 stub 委托当作业务容量测试。
- `tools/test_registry_groups_workbench.py` 仅增加上述一个 target；既有 `_FINAL_CAPACITY_INPUT_SCOPES` 已覆盖 `scripts/workbench/verify_final_capacity.py` 与执行器/宿主 helper，无需重复新增依赖。
- `tests/gate_meta/test_workbench_registry_contract.py` 补唯一 owner、非 required、真实测试定义、CLI/执行器输入范围和不被 daily 自动提升为 required 的断言。
- `tests/gate_meta/test_workbench_round1_registry_contract.py` 仅把这一个明确批准的后续 CLI guard 加入 R1 历史集合之外的精确清单。R1 原 582/85、原哈希与全部原 owner/顺序继续核验，不把当前总数硬编码进新断言。
- 本次观察为 583 required / 86 supplemental；所有 missing/duplicates/unknown 为空。删除新增 CLI 这一条后，所有旧 target 的 owner 与顺序和本次修改前完全相同。

## 实际验证

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache \
  CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph \
  TMPDIR=/tmp/aps-task-h-01a08b02 \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  --basetemp=/tmp/aps-task-h-cli-registry-v1 \
  --junitxml=/tmp/aps-task-h-cli-registry-v1.xml \
  tests/workbench/test_final_capacity_cli_loading.py \
  tests/gate_meta/test_workbench_registry_contract.py \
  tests/gate_meta/test_workbench_round1_registry_contract.py \
  -k 'test_help_and_invalid_arguments_do_not_import_test_executor or test_valid_cli_delegates_exact_arguments_without_changing_thresholds or stable_final_capacity or final_capacity_cli_loading or round1_preserves_every_old_owner_and_target_order'
```

结果：**28 passed / 923 deselected，2.09 秒，exit 0**。包含新 CLI 3 项、唯一 owner 1 项、稳定 helper 22 项及 R1 历史集合 2 项。两个冷进程证明 help/非法参数不加载测试执行器或 factory；第三项明确用 stub 校验精确委托，不能升级为业务证据。未选中的测试不计为通过。

三个 H 修改文件 Ruff `check --no-cache` 实际通过。H 另外真实执行 JSON 形式的含 tests 导入扫描：

```bash
.venv/bin/python -B -m tools.scan_import_cycles --json --fail-on-new-cycle --include-tests
```

结果：**exit 0**，2625 modules；现有 1 目录环 / 8 文件环 / 43 动态未解析位置；parse errors 0，`new_dir/new_file/new_dir_edges/new_file_edges/new_unresolved_dynamic_imports` 全空。之前由顶层 CLI 导入产生的目录环阻断已消除；不是全仓零历史债务。baseline SHA 与 H 先前记录一致，没有刷新 baseline。

该结论是对 Main 修复的复核，不能写成 H 修改了 CLI。`--quiet-when-clean` 的 Main 空输出 exit 0 与本次 JSON 结果相符。

## 哈希与边界

| 文件 | SHA-256 |
| --- | --- |
| `tools/test_registry_groups_workbench.py` | `96bf5fa8f06d7551ace111d411d92e7f748407da6950877888ce0c1237a47270` |
| `tests/gate_meta/test_workbench_registry_contract.py` | `edaf8173f52b011feb3d1d0ce73deeddfc617c04c603214a5c85948e3d4f5ae0` |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | `709e2f4037bbcb2b23c461da800ca712e7e57b65c70dc6cde89d11ceea283e53` |
| Main CLI（H 只读） | `b4f3353c48cf44e4430f8630393dc1addbffee2ac27e1aaa47f84aa3cb132272` |
| Main 新测试（H 只读） | `612f4d240ea8a230502dbe91a1e6f8dfe8375bef30adbf31a1cc5e6b656d0466` |

JUnit `/tmp/aps-task-h-cli-registry-v1.xml` SHA-256：`37e15a17d5b6ec61eadd6ed51bdd983c24bceb08faaec2da057c487c4b342d87`。原命令、扫描 JSON 摘要、返回码、baseline/hash 和 target 前后比较在 `H-capacity-cli-registry-evidence-20260910.json`。

- Main 的 2 batch x 3 operation 真实小档结果由 Main 另行保存 exact result/source hash；本轮未把 stub 或 scanner 算作该业务结果的独立复验。
- scheduler 两源 + 35 项新测试的独立三文件交接继续使用 `H-lazy-exports-source-addendum-20260910.json`；不能因其哈希匹配就替代最终 HEAD 的完整 gate。
- H 无 Git 写，保留已有 dirty、原归档和原预览。没有当前 full gate，也不重跑或改写 5000 正式容量记录；继续等 Main 最终 HEAD。
