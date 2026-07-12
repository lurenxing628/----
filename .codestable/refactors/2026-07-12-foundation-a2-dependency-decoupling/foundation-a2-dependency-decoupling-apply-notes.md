---
doc_type: refactor-apply-notes
refactor: 2026-07-12-foundation-a2-dependency-decoupling
status: in-progress
---

# foundation A2 dependency decoupling apply notes

## 用户批准

- 2026-07-12：用户批准按 approved design 实施 A2-01 + A2-02，并同意双轨复审后的生产 import 直连补全。
- 授权边界：可实施和做提交前验证；初始批准不包含 `git commit`、推送或创建 PR。
- 2026-07-12：提交前证明完成后，用户另行授权创建一个 A2 实现提交，并在该提交的干净 HEAD 上运行无缓存、无续跑完整门禁；仍不包含推送、PR 或后续 docs-only 提交。

## 步骤 1：锁定 A2 边界与行为刻画

- 完成时间：2026-07-12
- 改动文件：`tests/models_domain/test_foundation_a2_dependency_boundary.py`
- 验证结果：新增 6 项边界测试；首次运行得到预期红灯 `4 failed, 2 passed in 2.55s`。两个旧合同刻画测试通过；四个失败分别是 `core.errors` 尚不存在、正逆序 canonical import 尚失败、调用方尚未切路径、A2 四目录 SCC 尚存在，没有无关行为失败。
- 行为等价自检：只新增测试，未修改生产代码或数据库行为。
- 偏离：无。

## 步骤 2：把错误合同归到 core.errors

- 完成时间：2026-07-12
- 改动文件：新增 `core/errors.py`；`core/infrastructure/errors.py` 改为显式 re-export；4 个 models、3 个 shared 与 7 个错误响应函数生产调用文件切到 canonical 路径；边界测试拆成可分步验证的 error/migration 子项。
- 验证结果：HEAD 旧实现与新实现 AST 在排除模块 docstring/`__all__` 后完全一致；错误合同、解析、资源过滤、HTTP 边界专项 `66 passed in 1.89s`；目标 Ruff 通过。中间生产扫描为 762 模块，models/shared 已退出 A2，只剩 infrastructure⇄migrations 两成员 10 边，其他 SCC 逐项不变。临时调用图 7329 callable / 25786 edges / 10166 confident / 15620 ambiguous / 8 cycles / 193 islands，按 errors 路径映射后旧新全边集零丢失、零新增。
- 行为等价自检：ErrorCode、异常类、HTTP/响应函数实现原样移动；旧新七个公开对象 `is` 相同，签名、args/cause、序列化、HTTP 状态与中文消息由测试锁定。
- 偏离：为让同一测试文件支持逐步退出信号，把原先合并的 identity/import guard 拆成 error 与 migration 两组测试；未扩大生产行为。

## 步骤 3：把 migration common 归到 infrastructure 父层

- 完成时间：2026-07-12
- 改动文件：新增 `core/infrastructure/migration_common.py`；旧 `migrations/common.py` 改为显式 re-export；7 个 infrastructure 父层调用方、`web/bootstrap/factory.py` 与 migrations 包内 21 个生产模块切到父层路径。
- 验证结果：完整 A2 边界 `8 passed in 2.54s`；migration_db、事件表/序列、v16/v18/v19 与 bootstrap 专项 `145 passed in 6.58s`；目标 Ruff 与 `git diff --check` 通过。AST 证明 common 实现除 `safe_log` 从函数内移到顶层外一致，21 个历史迁移文件归一 import 后 AST 完全一致。双 scope 实际扫描为 production 763 模块 / 4 SCC、with-tests 1458 模块 / 5 SCC；A2 消失，其他 SCC 记录逐项不变，unresolved 仍 6/44，正式旧基线门禁在收紧前通过。
- 行为等价自检：MigrationOutcome、SQLite helper 与 fallback_log 旧新对象 `is` 相同；历史迁移 SQL、函数体、默认值、执行顺序和异常文本未改。
- 偏离：含测试模块数比无新增测试的临时原型多 1，来源仅为 `test_foundation_a2_dependency_boundary.py`，已把终态预期从 1457 校正为 1458。

## 步骤 4：收紧证据并同步当前事实

- 完成时间：2026-07-12
- 改动文件：双 scope import-cycle v2 基线、正式调用图 10 JSON（其中 6 份内容变化）、dead-code 基线、checkup 总入口/README、架构总入口与 scheduler 架构、两份循环/模块审计、dependency roadmap/items 和本 refactor 文档。
- 循环证据：production 763 模块 / 4 hard 目录 SCC，production-and-tests 1458 模块 / 5 SCC；A2 四目录均不在任何 hard SCC，其他目录 SCC 记录逐项不变，unresolved 仍为 6 / 44。双候选基线各删除 28 边 A2 目录块，并把 migration 父包感知文件 SCC 从 21 成员 / 45 边严格缩成 5 成员 / 11 边；其余文件 SCC 记录不变。正式基线与候选逐字节相同，刷新前后双正式门禁都通过。
- 调用图证据：两个独立临时目录的 10 份 JSON 逐文件 SHA 完全相同；7329 callable、25786 edges、10166 confident、15620 ambiguous、typed 0、8 个受限简单循环、193 islands。7 个 errors callable 与 6 个 migration common callable 按新路径映射后，旧新函数集合和 25786 条全边集均零增删。
- dead-code 证据：只把 3 个 AppError 基线身份迁到 `core/errors.py` 并保持排序；起点 HEAD 与当前工作树 quick 扫描都报告同一组 32 个既有新增候选，按 errors 路径映射后集合完全相同，A2 新增 0，未全量 refresh。
- 总证据：`baseline.json` 已写当前 763/1458、4/5、6647/13224 等机器数字，25 项 artifact SHA 全匹配；因工作树未提交，`clean_worktree_proof=false`、proof status=`pending`。
- 行为等价自检：证据变化均由两个实现路径移动、目录消圈和 migration 父包加载圈严格收缩解释；没有基线化新增 SCC、未解析动态导入或调用边损失。
- 偏离：设计原先只预期父包感知 hard 文件 SCC 数仍为 9；实际同一个 migration 文件 SCC 的成员/边还严格缩小。该变化由生产 migrations 直连父层 common 直接导致，属于额外降复杂度，已在 design/checklist/事实文档补记。

## 步骤 5：提交前局部与完整证明

- 完成阶段：2026-07-12 已完成提交前证明并取得一个实现提交及其 clean-HEAD proof 的授权；clean proof 尚待提交后执行。
- 专项回归：A2 边界、`tests/migration_db`、事件基础/序列/v16/v18/v19、错误响应、字段解析、资源过滤、严格解析和 `tests/config` 合计 `365 passed in 12.03s`。
- 静态检查：Ruff 全绿；Pyright gate 为 `0 errors, 15 warnings`（既有 scheduler `__all__` 警告），Pyright tools 为 `0 errors, 0 warnings`。
- Python 3.8 增量证明：从 tracked diff 与 untracked 文件合并、去重得到恰好 48 个本轮改动 Python 文件；逐项作为位置参数传给 `scan_py38plus_syntax.py --json --fail-on-hit`，报告并二次硬断言 `scanned_files=48`、`skipped_files=0`、`total_findings=0`。不接受此前因错误传参得到的 0 文件空扫描。
- Python 3.8 正式证明：完整门禁实际使用的 `scan_aps_three_gap_py38_scope.py --base-ref d4589d77` 扫描 1184 个 Python 文件，读取失败 0、发现 0。原 checklist 的 `core web` 绝对零扫描会在 8 个与起点 HEAD blob 完全相同的范围外文件中报告 11 条存量 future-annotations 风险，因此该命令不能证明 A2 回归；已改为仓库正式的变更范围门禁，没有顺手修改这 8 个范围外文件。
- 循环证明：production 与 production-and-tests 两条正式 `--fail-on-new-cycle` 门禁均通过。
- 完整门禁：`scripts/run_quality_gate.py --allow-dirty-worktree --no-long-gate-cache --no-resume` 从头执行 19/19 步，19 个 receipt 均 `returncode=0`；收集 4724 项测试，`unexpected_failure_count=0`，required regressions 为 253 targets / 2467 nodeids。manifest 状态为预期的 `passed_but_unbound`，proof scope 仅声明 dirty-worktree diagnostic；门禁前后 dirty fingerprint 与 `git status --short` 相同，`tracked_drift_detected=false`。
- 其他检查：`git diff --check` 通过；完整门禁前后均保持同一未提交改动集合。
- 偏离：只修正了一个无法在起点 HEAD 成立的 Python 3.8 全仓绝对零检查口径，并保留失败事实；实现范围、数据库合同、证据生成物和 clean-proof 授权边界均未改变。
