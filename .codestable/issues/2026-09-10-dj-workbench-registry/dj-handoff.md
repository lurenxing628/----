---
doc_type: issue-fix
status: partial
created: 2026-09-10
summary: DJ 补齐已完成模块的固定测试清单，并精准修正 schema29 下的测试支持；保留并行开发与 tracked-proof 的真实失败
tags: [workbench, registry, regression, schema29, DJ]
---

# DJ 交接结论

- 局部实施完成：开始时漏登的 16 个文件全部按固定文件名追加；没有 glob target、没有扩大 required 分类、没有改 discovery。
- required 仍是 30 groups，481 -> 494 targets；其中 workbench 22 groups / 221 targets。supplemental 仍是 15 groups，60 -> 63 targets。
- 原有每个 group 的 target 顺序逐项保留为前缀，group ID 顺序完全不变。discovery 函数修改前后的 AST 完全相同。
- trial 的 6 个保留断言失败已消除；CY 浏览器缺 schema 夹具已修正。旧 raw 行及 SQLite 类型仍逐项比较；只允许新增 WorkbenchTaskRefs 对应的 actual/downtime 映射对，不允许任意 DashboardItems 追加。
- 不是全绿门禁或 clean-worktree proof。最终分组结果：meta 382 passed / 2 failed；本轮新增 required 文件 192 passed / 1 failed；trial/schema29 83 passed；浏览器 6 passed。另 Python 3.8.10 运行新增 support 合同 30 passed。
- 不运行共享整库 full gate，不改主 roadmap、固定 schema-v24..28.sql、产品代码或主线构建。不执行 git add/commit。

# 本轮写集

以下都是在原 dirty 内容上做的局部修改；未跟踪文件未暂存。

1. `tools/test_registry_groups_workbench.py`：固定追加 13 required + 3 browser supplemental；新增精确跨模块 input scopes，不扩大 target discovery。
2. `tests/gate_meta/test_workbench_registry_contract.py`：锁住新文件归属、尾部顺序、required/supplemental 分类与实际 changed-source selection；新增 30 个 support 合同用例。
3. `tests/gate_meta/test_long_gate_manifest.py`：明确总数 494，group 数仍为 30；保留此前所有改动。
4. `tests/workbench/trial_adoption_support.py`：旧 DashboardItems 行、类型、永久 ref 不变；新增映射 Counter 必须恰好等于新增任务的 actual/downtime 两项，batch_ref 必须为 NULL；拒绝缺项、重复、旧任务、未知任务、错误类别和非法 ref。
5. `tests/workbench/trial_adoption_widgets_support.py`：使用同一精准映射检查；原 raw/场景/receipt/正式安排/完整性断言全部保留。将数据保留检查独立成方法，避免在原高复杂度 capture_proof 继续堆逻辑。
6. `tests/workbench/trial_adoption_history_widgets_support.py`：保留 DB 原有的 receipt -> official plan -> task 映射检查，移除临时改写 self.before 的兼容过程，直接让父类检查真实原始快照。
7. `tests/workbench/dashboard_widgets_support.py`：missing 分支从只读固定 schema-v28.sql 建独立临时 SQLite；不再把当前 v29 的完整库克隆后叫作缺 schema。
8. 本文。没有修改 `tools/test_registry_data.py`，已有 common workbench scopes 足够。

support 路径均在编辑前告知用户。定位器对未索引的新测试 helper 返回未找到，随后用实际文件和 rg 核查调用方，没有据此改产品函数或重建共享索引。

# 开始时的 16 个漏登文件

| Owner | 类型 | 固定文件名，均位于 tests/workbench/ |
| --- | --- | --- |
| workbench_process | required | test_process_quota_protection.py |
| workbench_process | required | test_process_quota_protection_excel.py |
| workbench_process | required | test_process_quota_protection_routes.py |
| workbench_process | required | test_process_quota_protection_transactions.py |
| workbench_process | required | test_process_quota_protection_stage_regressions.py |
| workbench_process | required | test_process_quota_protection_file_receipts.py |
| workbench_process | required | test_process_quota_protection_file_receipt_failures.py |
| workbench_plans | required | test_plan_adoption_baseline.py |
| workbench_plans | required | test_plan_adoption_baseline_api.py |
| workbench_plans | required | test_plan_adoption_baseline_integrity.py |
| workbench_trial_adoption | required | test_trial_adoption_history.py |
| workbench_trial_adoption | required | test_trial_adoption_history_api.py |
| workbench_trial_adoption | required | test_trial_adoption_history_boundaries.py |
| workbench_browser | supplemental | test_dashboard_widgets.py |
| workbench_browser | supplemental | test_plan_adoption_baseline_browser.py |
| workbench_browser | supplemental | test_trial_adoption_history_widgets.py |

DA 比最初交接多出一个 browser 文件，其完成证据来自现有 DA fix-note，本轮又实际执行通过。没有把 browser、capacity 或 opt-in 文件假登记为 required。

# 复现和最终结果

专属运行目录：`/tmp/aps-dj-registry-pleF4f`，macOS 实际路径可能显示为 `/private/tmp/aps-dj-registry-pleF4f`。XML 和修改前快照均在此，不写主线 evidence/QualityGate。

| 执行范围 | 结果 | 证据 |
| --- | --- | --- |
| 修改前 registry + manifest | 281 passed / 1 failed，16 个漏登文件 | meta-before.xml |
| 修改前 test_trial_adoption.py + test_trial_adoption_raw.py | 19 passed / 6 failed，均为 WorkbenchDashboardItems | adoption-before.xml |
| 先补完固定登记，未新增 support 合同 | 317 passed | meta-registered.xml |
| 最终 registry + manifest + full_test_debt_registry_contract | 382 passed / 2 failed，20.94s | meta-final-2.xml |
| 本轮 13 个新增 required 文件 | 192 passed / 1 failed，59.76s | completed-required.xml |
| 最终 trial 八文件 + calibration/dashboard migration | 83 passed，20.30s | adoption-final.xml |
| 修 CY 前，四个浏览器文件 | 5 passed / 1 failed，103.13s | browser.xml |
| 最终四个浏览器文件 | 6 passed，80.38s | browser-final.xml |
| Python 3.8.10 新增 support 合同 | 30 passed，0.69s，无 skip/deselected | python38-final.xml |

额外真实复现：TrialAdoptionWidgetServer 在独立临时库完成实际 adopt 后，原 capture_proof 在 WorkbenchDashboardItems 处失败；不是根据 DA 旧报告直接改断言。最终 CX/DB Chrome109 用例都通过。

Ruff 对本轮 7 个 Python 文件通过。项目 `scan_py38plus_syntax.py --fail-on-hit` 对同 7 个文件扫描：解析拒绝 0，运行/语义兼容风险 0。Python 3.8.10 已实际 import registry，计数为 30/494/63。

对本轮文件做修改前后 Radon 比较，新增或加重的 >15 复杂度项为 0。仍保留两项未改的既有超限：test_long_gate_manifest.py 中 test_import_cycle_entries_have_stable_ids_hash_and_scope 为 19；trial_adoption_widgets_support.py 中 control 为 16。没有刷新任何基线，未声称全仓静态门禁通过。

# 剩余错误边界

## 1. 并行新增文件继续被 discovery 报出

最终 meta 执行时有 4 个：calibration_adoption_host、process_quota_widgets、system_restore_host、system_restore_host_drain。2026-09-10 10:16:12 +08:00 的只读库存快照增至以下 6 个；这是并行现场变化，不把旧计数冒充最终库存。

```text
tests/workbench/test_calibration_adoption_host.py
tests/workbench/test_outsourcing_facts.py
tests/workbench/test_process_quota_widgets.py
tests/workbench/test_system_restore_host.py
tests/workbench/test_system_restore_host_drain.py
tests/workbench/test_system_restore_host_recovery.py
```

DG/DH/DI 在开发的文件不归 DJ 注册。新增 calibration_adoption_host 不在本轮确认的已完成清单，未找到完成交接证据，也不抢注册。待各 owner 完成并交接后，逐文件复核归属；不能按前缀全部收进来，也不能排除 discovery 来制造通过。

## 2. tracked-proof 是现场约束，不是注册错误

失败位置：[test_full_test_debt_registry_contract.py](/Users/lurenxing/GitHub/----/tests/gate_meta/test_full_test_debt_registry_contract.py:1264)，`test_quality_gate_required_startup_and_full_debt_share_registry` 要求所有 required/startup 文件均 tracked，首先命中未跟踪的 `tests/gate_meta/test_workbench_registry_contract.py`。

10:16 快照中 required 未跟踪文件共 221 个。没有改这个断言，没有 stage 测试伪造 proof；主线经授权整理提交后再做真正的 tracked/clean 验证。

## 3. CW schema28 测试实际使用当前 v29 夹具

失败位置：[test_process_quota_protection.py](/Users/lurenxing/GitHub/----/tests/workbench/test_process_quota_protection.py:117)，`test_schema28_is_not_treated_as_no_locks`。

其 `schema_conn` 来自 [tests/conftest.py](/Users/lurenxing/GitHub/----/tests/conftest.py:134)，读取当前 schema.sql，不是固定 v28。现已真实迁移为 v29，因此 `read_locks([])` 合法返回 `{}`，不会抛原测试期待的 `adoption_schema_unavailable`。

本轮实际双库对照：固定 v28 正确返回 `adoption_schema_unavailable` / 503；当前 v29 正确返回 `{}`；两库所有带类型的 raw table 快照均严格不变。证据指向夹具命名与构造不一致，不是应当让 v29 空锁查询失败。

该测试文件不在 DJ 写范围，共享 schema_conn 也不能为单个旧测试倒退。建议 CW/主线把这一个测试的数据库构造改为读取固定 v28 SQL；保留原错误码、状态码及全表快照断言。DJ 没有改它，没有 skip，也未把 192/1 写成全通过。

# 完整执行命令

以下与实际运行的文件选择、选项一致；实际输出目录是上文专属目录。重跑用新的 mktemp 目录，避免覆盖本轮或其他人的证据。

```bash
cd /Users/lurenxing/GitHub/----
OUT="$(mktemp -d /tmp/aps-dj-registry-rerun-XXXXXX)"

.venv/bin/python -m pytest \
  tests/gate_meta/test_workbench_registry_contract.py \
  tests/gate_meta/test_long_gate_manifest.py \
  tests/gate_meta/test_full_test_debt_registry_contract.py \
  -q --tb=short --show-capture=no -p no:cacheprovider \
  --basetemp="$OUT/meta-final-2" --junitxml="$OUT/meta-final-2.xml"

.venv/bin/python -m pytest \
  tests/workbench/test_process_quota_protection.py \
  tests/workbench/test_process_quota_protection_excel.py \
  tests/workbench/test_process_quota_protection_routes.py \
  tests/workbench/test_process_quota_protection_transactions.py \
  tests/workbench/test_process_quota_protection_stage_regressions.py \
  tests/workbench/test_process_quota_protection_file_receipts.py \
  tests/workbench/test_process_quota_protection_file_receipt_failures.py \
  tests/workbench/test_plan_adoption_baseline.py \
  tests/workbench/test_plan_adoption_baseline_api.py \
  tests/workbench/test_plan_adoption_baseline_integrity.py \
  tests/workbench/test_trial_adoption_history.py \
  tests/workbench/test_trial_adoption_history_api.py \
  tests/workbench/test_trial_adoption_history_boundaries.py \
  -q --tb=short -p no:cacheprovider \
  --basetemp="$OUT/completed-required" --junitxml="$OUT/completed-required.xml"

.venv/bin/python -m pytest \
  tests/workbench/test_trial_adoption.py \
  tests/workbench/test_trial_adoption_raw.py \
  tests/workbench/test_trial_adoption_validation.py \
  tests/workbench/test_trial_adoption_boundaries.py \
  tests/workbench/test_trial_adoption_atomic.py \
  tests/workbench/test_trial_adoption_restart.py \
  tests/workbench/test_trial_adoption_api.py \
  tests/workbench/test_trial_adoption_host.py \
  tests/workbench/test_calibration_dashboard_migration.py \
  -q --tb=short -p no:cacheprovider \
  --basetemp="$OUT/adoption-final" --junitxml="$OUT/adoption-final.xml"

.venv/bin/python -m pytest \
  tests/workbench/test_dashboard_widgets.py \
  tests/workbench/test_plan_adoption_baseline_browser.py \
  tests/workbench/test_trial_adoption_history_widgets.py \
  tests/workbench/test_trial_adoption_widgets.py \
  -q --tb=short --show-capture=no -p no:cacheprovider \
  --basetemp="$OUT/browser-final" --junitxml="$OUT/browser-final.xml"

python3.8 -m pytest \
  tests/gate_meta/test_workbench_registry_contract.py::test_v29_support_accepts_only_exact_new_task_mapping_pairs \
  tests/gate_meta/test_workbench_registry_contract.py::test_v29_support_rejects_non_source_mapping_changes \
  tests/gate_meta/test_workbench_registry_contract.py::test_v29_support_still_rejects_each_old_raw_row_or_type_change \
  tests/gate_meta/test_workbench_registry_contract.py::test_dashboard_missing_schema_support_uses_frozen_v28 \
  -q --tb=short -p no:cacheprovider \
  --basetemp="$OUT/python38-final" --junitxml="$OUT/python38-final.xml"

.venv/bin/python -m ruff check \
  tools/test_registry_groups_workbench.py \
  tests/gate_meta/test_workbench_registry_contract.py \
  tests/gate_meta/test_long_gate_manifest.py \
  tests/workbench/trial_adoption_support.py \
  tests/workbench/trial_adoption_widgets_support.py \
  tests/workbench/trial_adoption_history_widgets_support.py \
  tests/workbench/dashboard_widgets_support.py --no-cache

.venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit \
  tools/test_registry_groups_workbench.py \
  tests/gate_meta/test_workbench_registry_contract.py \
  tests/gate_meta/test_long_gate_manifest.py \
  tests/workbench/trial_adoption_support.py \
  tests/workbench/trial_adoption_widgets_support.py \
  tests/workbench/trial_adoption_history_widgets_support.py \
  tests/workbench/dashboard_widgets_support.py
```

v28/v29 夹具差异的只读复现命令：

```bash
python3.8 -B - <<'PY'
import sqlite3
from pathlib import Path
from core.services.workbench.process_quota_protection import ProcessQuotaProtection
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.process_quota_protection_support import snapshot
for version, schema in ((28, 'tests/workbench/fixtures/schema-v28.sql'), (29, 'schema.sql')):
    with sqlite3.connect(':memory:') as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(Path(schema).read_text(encoding='utf-8'))
        before = snapshot(conn)
        try:
            result = ProcessQuotaProtection(conn).read_locks([])
        except WorkbenchCommandRejected as exc:
            assert version == 28 and exc.code == 'adoption_schema_unavailable' and exc.status == 503
            print('frozen v28: correctly rejected code=%s status=%s' % (exc.code, exc.status))
        else:
            assert version == 29 and result == {}
            print('current v29: correct empty locks=%r' % result)
        assert before == snapshot(conn)
        print('all typed raw table snapshots unchanged')
PY
```

# 保留证明与后续

- 本轮观察的 HEAD：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`。工作区从开始即存在大量他人 staged/unstaged/untracked 内容；不绑定为 clean proof。
- 整个 staged diff SHA-256 前后相同：`952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`。
- 禁改的 `tests/gate_meta/test_frozen_bundle_contract.py` 保持 staged `200+/0-`，文件 SHA-256 仍为 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。
- 五份固定 SQL 的逐文件哈希与本轮开始完全一致，详见专属目录的 `before-hashes.json`、`protected-verification.json`；v28 仍为 `2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52`。
- `tools/test_registry_data.py` 整文件哈希也与开始时相同，没有碰他人改动或非 workbench 段。
- 本轮修改全部未提交，未新增暂存。未改产品数据库；浏览器仅使用临时 SQLite 和自动分配端口，没有全局 build、没有占用既有预览。
- 下一步由 CW/主线修正上述一个固定 v28 测试的构造；待其他 owner 明确完成后再逐个注册新文件，最后由主线统一形成真正的 tracked/clean gate 证据。
