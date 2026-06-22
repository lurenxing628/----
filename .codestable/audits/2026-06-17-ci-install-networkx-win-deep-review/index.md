# ci/install-networkx-win 分支深度 Review

执行日期：2026-06-17

## 审查范围

- 目标分支：`ci/install-networkx-win`
- 目标提交：`313f6528ed2d42cdbe306110189623100bf962b7`
- 基线提交：`d4589d77d9b642fe3b16a891fe4f40f9aede1f93`
- 范围：`d4589d77..313f6528`
- 提交数：291
- 文件改动：1799 个文件，`+163295 / -45885`
- 目标提交本身：只改 CodeStable issue 文档，不改运行代码。

## 当前工作区排除项

以下 7 个未提交/暂存文件不是本轮主审范围，不能据此下结论：

- `.codestable/architecture/ARCHITECTURE.md`
- `.codestable/features/2026-06-14-fusion-due-soon-alert/fusion-due-soon-alert-acceptance.md`
- `.codestable/features/2026-06-14-fusion-due-soon-alert/fusion-due-soon-alert-checklist.yaml`
- `.codestable/requirements/scheduler-daily-workbench.md`
- `.codestable/roadmap/aps-frontend-fusion/aps-frontend-fusion-items.yaml`
- `.codestable/roadmap/aps-frontend-fusion/aps-frontend-fusion-roadmap.md`
- `tests/web_pages/test_dashboard_near_due_hero.py`

本报告文件是本轮新增审计产物，不属于被审代码修复。

## 子代理执行矩阵

探针：

- Helmholtz：`019ed29b-0f45-7933-8692-286586dd325f`，验证 `spawn_agent` 可用。

第一轮按提交顺序广度审查：

- G01 Aquinas：`019ed29c-0bd5-7ee2-a2ae-a91898b3c752`，2026-05-27 至 2026-06-02，37 个提交。
- G02 Copernicus：`019ed29c-3b6d-7bb2-8d00-f347e447e10e`，2026-06-03 至 2026-06-05，16 个提交。
- G03 Kuhn：`019ed29c-6eec-75c3-ac2a-c3665ad84ad3`，2026-06-06，24 个提交。
- G04 Kepler：`019ed29c-a7ca-7383-a759-219b112453f7`，2026-06-07，37 个提交。
- G05 Linnaeus：`019ed2ac-444a-7cf3-800b-998635364ec9`，2026-06-08，47 个提交。
- G06 Ohm：`019ed2ac-44cb-7c83-ae1a-cbe7fe79c9b2`，2026-06-09，22 个提交；派出 3 个二层子代理。
- G07 Newton：`019ed2ac-4549-74d3-a5c1-008b3c7876a3`，2026-06-10，33 个提交。
- G08 Sagan：`019ed2ac-45df-76b3-9418-7714011f6ab7`，2026-06-11，26 个提交；派出 3 个二层子代理。
- G09 Bohr：`019ed2b5-7319-7f33-a49b-8ef7b299003b`，2026-06-12，24 个提交。
- G10 Curie：`019ed2b5-73b5-72b1-80fa-39e884252d8c`，2026-06-13 至 2026-06-14，18 个提交；派出 3 个二层子代理。
- G11 Meitner：`019ed2b8-2a31-7752-9fec-ab609c87f3dc`，2026-06-15，7 个提交。

第二轮高风险深钻：

- D1 Zeno：`019ed2c5-94d7-7760-8553-8a5ec81a953e`，质量门禁、缓存、serial/parallel、skip、daily gate；派出 3 个二层子代理。
- D2 Einstein：`019ed2c5-9568-7b83-ac32-0e5607f819a2`，固定文件、SQL 时间、token、坏时间业务链；派出 3 个二层子代理。
- D3 Ampere：`019ed2c5-95fd-7d82-ab88-074f1833a968`，Windows NetworkX CI、Win7/Python 3.8、旧 selftest 路径。

第三轮盲审：

- B1 Kierkegaard：`019ed2c5-9683-7343-95d6-1ef86b78cf00`，不告知前两轮结论，尝试推翻“实现满足需求、没有静默回退、全局最优”的判断；派出 3 个二层子代理，其中 1 个二层因模型容量错误未产出。

第四轮同类问题补洞：

- T1 Hooke：`019ed3ba-41ca-78f0-8a28-6448ef2b2cba`，门禁缓存、浏览器运行时、proof 复核；派出并关闭 2 个二层子代理。
- T2 Popper：`019ed3ba-6889-78b3-ad48-2f4178a1c704`，固定名文件和安全写删链路复核。
- T3 Pauli：`019ed3ba-8fcf-7792-ab3a-012d2b5f34e0`，时间、数字、数据语义复核。
- T4 Rawls：`019ed3ba-b7f2-7242-b255-b72b67c7a314`，公开 token、裸 id、跨页入口复核。
- T5 Carver：`019ed3ba-e649-7063-bc90-729c7a889077`，README、开发文档、架构文档、旧入口复核；派出并关闭 2 个二层子代理。

第五轮全面盲审对抗：

- B2 Mencius：`019ed3ca-c13f-7303-867d-a8957d6e1ea2`，不读既有报告，盲审 CI、NetworkX、Win7、门禁 proof。
- B3 Turing：`019ed3ca-eb58-75f1-ad89-193c1046ede0`，不读既有报告，盲审固定文件、token、日志、诊断包。
- B4 Parfit：`019ed3cb-17bd-7db2-a8cb-ad5af537fcac`，不读既有报告，盲审排产、报表、工作台跨页一致性；派出并关闭 2 个二层子代理。
- B5 Sagan：`019ed3cb-42b2-7f42-bd1e-0cb5430f0193`，不读既有报告，盲审文档和迁移路径。
- B6 McClintock：`019ed3cb-747e-7171-9eae-6554ef04d834`，不读既有报告，盲审测试登记、required registry、迁移后目录；派出并关闭 2 个二层子代理。

已知可统计子代理数：

- 探针子代理：1 个。
- 一层子代理：26 个。
- 二层子代理：至少 26 个被创建，其中部分历史通知显示 stream disconnected，但一层结果已汇总可用。
- 可确认总数：至少 53 个子代理。
- 实际并发控制：每波一层最多 4 个；每个一层最多 3 个二层；未使用第三层。

## 总体结论

不能建议直接放行。

好的部分：

- Windows CI 安装 NetworkX 的方向是对的：`.github/workflows/quality.yml` 使用 `windows-latest`、Python 3.8，并额外安装 `requirements-optimizer-lite-win7.txt`。
- `requirements-optimizer-lite-win7.txt` 固定 `networkx==3.1`，这个版本符合 Python 3.8 约束，且是纯 Python 依赖。
- NetworkX 没有变成普通启动就必须 import 的依赖，代码走运行时懒加载。

不能放行的原因：

- 多条门禁证明链存在漏洞，尤其是 full-test-debt serial 分片不独占、required_regressions 缓存没有钉住本轮 payload、Windows-only skip 在 POSIX 也会被接受。
- 手动备份删除绕过已有 fixed-file 安全删除工具。
- Excel 模板自动生成/修复也绕过 fixed-file 安全写入，启动时可写穿同名软链接。
- SQL 时间下推和 Python 严格解析不一致，会让部分坏时间行消失在提示链外。
- 报表默认日期、超期清单、资源派工现场记录、首页备份提醒等用户可见链路仍有“数据不完整但页面装作正常”的风险。
- `.limcode/skills/aps-*` 仍被项目允许参考，但多个入口已经指向不存在的旧测试路径。
- README、开发文档、架构文档和专项回放文档没有跟上测试迁移和 NetworkX 默认开启，照文档执行会跑空目录或找不到文件。

## Findings

- P1：`finding-01.md`，full-test-debt 的 serial 分片并没有独占运行。
- P1：`finding-02.md`，手动删除备份绕过固定文件安全删除。
- P1：`finding-03.md`，SQL 时间判断和 Python 时间解析口径不一致。
- P1：`finding-04.md`，required_regressions 的 skipped 白名单没有平台限制。
- P1：`finding-05.md`，required_regressions 缓存没有钉住本轮 full-test-debt payload。
- P2：`finding-06.md`，拆分后的 test registry 文件没有进工具门禁源码清单。
- P2：`finding-07.md`，full_test_debt 缓存没有覆盖分片规则实现文件。
- P2：`finding-08.md`，daily fast gate 允许 impact 两个 pytest 分支同时空跑。
- P2：`finding-09.md`，旧 APS 专项入口仍指向迁移前测试路径。
- P2：`finding-10.md`，本地安装文档漏掉默认图分析所需的 NetworkX 依赖。
- P2：`finding-11.md`，plan_context_token 仍允许裸 scenario_id 回退，需要产品口径确认。
- P3：`finding-12.md`，提交范围内存在大量 diff-check 空白问题。
- P1：`finding-13.md`，目标提交 clean gate 失败在债务台账同步。
- P1：`finding-14.md`，full-test-debt long gate 缓存没有钉住真实 Chrome 运行时身份。
- P1：`finding-15.md`，Excel 模板自动生成/修复绕过固定文件安全写入。
- P1：`finding-16.md`，报表默认日期范围用 raw 文本 MIN/MAX，可能算出反向跨度。
- P1：`finding-17.md`，超期/延期统计遇到坏 due_date 会静默跳过整批。
- P2：`finding-18.md`，现场记录任务卡丢弃降级事件，页面会显示“暂无任务卡”。
- P1：`finding-19.md`，README、开发文档、架构文档和专项回放文档仍引用迁移前路径。
- P1：`finding-20.md`，首页备份健康扫描会跟随软链接，可能隐藏真实未备份风险。
- P1：`finding-21.md`，超期清单行级跳转丢日期，用户看到的操作入口会被禁用。
- P2/证据不足：`finding-22.md`，Win7 离线包是否包含 NetworkX 还没有可审 proof。

## 非阻塞建议

- `evidence/DeepReview/reference_trace.md` 目前是辅助审计，不是质量门禁的一部分；如果后续依赖它证明引用完整性，需要先把它接进 gate。
- 架构文档和系统速查表仍有旧路径、旧版本号口径，建议补“文档引用路径存在”和“常量同步”检查。
- 工序保存 token 的安全测试存在，但未进入 required registry，可考虑加入强制回归清单。
- 诊断包当前按日志后缀白名单收普通 `*.log`，虽然排除了 symlink 和密钥文件，但建议再确认是否真的要允许任意本地日志进入导出包。
- illegal next URL 会被日志记录；如果 URL 内含公开 token，后续诊断包可能间接带出 token，建议按日志策略统一脱敏。
- GitHub workflow 有 NetworkX 安装步骤，但还没有专门的 gate meta 测试锁住“必须安装 `requirements-optimizer-lite-win7.txt`”和 cache key 依赖。

## 证据不足

- GitHub 上没有绑定 `313f6528ed2d42cdbe306110189623100bf962b7` 的 check-run 或 status proof。`gh api .../check-runs` 返回 `total_count=0`。
- 没有 Win7 x64 实机安装包 proof；只能确认 CI 使用 Windows runner、Python 3.8、NetworkX 3.1。
- 没有可审的 Win7 离线包内容清单 proof；`vendor/wheels/` 被 `.gitignore` 忽略，`build_win7_onedir.bat` 只是在 `vendor/` 存在时打包目录，不能证明 NetworkX 已经被放进交付物。
- `plan_context_token` 到底是“访问权限”还是“URL 脱敏”需要产品口径确认；本报告按风险边界处理，不直接假设它一定是权限系统。

## 验证命令

- `git status --short --branch`：确认当前分支和 7 个既有暂存/未提交文件。
- `git merge-base origin/main HEAD`：确认基线为 `d4589d77d9b642fe3b16a891fe4f40f9aede1f93`。
- `git log --reverse --format=... d4589d77..313f6528 | wc -l`：确认 291 个提交。
- `git diff --stat d4589d77..313f6528`：确认 1799 文件、`+163295 / -45885`。
- `git diff --check d4589d77..313f6528`：失败，3848 行空白问题。
- 目标 pytest：`tests/gate_meta/test_verify_required_regressions_from_full_test_debt.py`、`test_collect_full_test_debt_sharded.py`、`test_full_test_debt_shards.py`、`test_long_gate_full_test_debt_cache.py`、`test_run_daily_quality_gate.py`，结果 105 passed；说明现有测试没有覆盖本报告中的几个反例。
- Python 3.8 语法扫描：对范围内新增/修改的 530 个 Python 文件执行 `tools/scan_py38plus_syntax.py --json`，结果 `total_findings=0`。
- 本轮新增审计报告仍是 untracked 文件，普通 `git diff --check` 不覆盖它们；已逐个用 `git diff --no-index --check -- /dev/null <报告文件>` 检查，结果通过。
- 第二轮同类问题复核包含只读复现：Excel 模板 broken symlink 写穿、SQL raw MIN/MAX 反向日期、坏 due_date 被空结果吞掉、资源派工 execution payload 丢 `degradation_events`、首页备份扫描跟随 symlink。
- 第二轮盲审额外跑了超期清单 backlink 现有测试：`tests/web_pages/test_reports_workbench_backlink_contract.py::test_overdue_rows_link_to_workbench_with_batch_context` 通过，但没有覆盖行级链接被禁用的反例。
- 临时 clean worktree：`/private/tmp/codex-review-313f6528-j9hgA9/wt`，固定到 `313f6528`。
- clean gate 第一次运行：失败在 pyright，因为临时 worktree 没有 `.venv`，无法作为目标提交 proof。
- clean gate 第二次运行：失败。第 1-10 步通过，第 11/17 步 `python scripts/sync_debt_ledger.py check` 失败，错误为 `oversize:core-infrastructure-backup` 的 `current_value` 与当前扫描不一致。

## clean proof 状态

没有 clean-worktree proof。

第二次临时 clean worktree 门禁固定在 `313f6528ed2d42cdbe306110189623100bf962b7`，并确认工作区干净。它通过了 full-test-debt、ruff、pyright、architecture fitness、required_regressions，但失败在第 11/17 步：

```text
ERROR: oversize 条目 current_value 与当前扫描不一致：oversize:core-infrastructure-backup
```

因此，本轮结论是：该分支不能直接合并，后续修复后必须在最新 HEAD 上重新跑 clean gate。

## 处理进展（2026-06-23）

本节为深审后处理状态汇总，便于追溯；上方 findings 原文保持不动作为历史证据。

已修（深审后三批提交）：

- 门禁证明链 `9fc827f9`：finding 01/04/05/06/07/08/14。
- 后端安全写删 / 时间口径统一 / 坏数据诚实降级 `cd95b8b0`：finding 02/03/15/16/17/18/20。
- 文档与测试迁移路径 / NetworkX 安装 / 图分析默认值同步 `12f4b879`：finding 09/10/19。
- finding-13（clean gate 失配）：台账 oversize `current_value` 已与现扫描一致（backup.py 577），`python scripts/sync_debt_ledger.py check` 通过，阻塞解除；backup.py 仍是登记在册的超长文件债（限 500）。

本批（2026-06-23）落地：

- finding-22（离线包是否含 NetworkX 无 proof）：① `vendor/wheels/networkx-3.1-*.whl` 改为随仓库提交（`.gitignore` 放行）；② `build_win7_onedir.bat` 增构建前从仓库内 wheel 离线装 networkx 的步骤（缺 wheel / 装失败 / 版本不符均 fail-loud，退出码 5/6/7）；③ `validate_dist_exe.py` 增"包内含 networkx 目录"冒烟；④ `tests/gate_meta/test_win7_networkx_package_contract.py` 增锁离线装步骤 + wheel 在仓库。运行时缺库已有 `NetworkXUnavailable` 显式报错（非静默 off）。
- finding-11（无 token 时裸 scenario_id 回退）：本应用无登录 / 单租户 / 全无网单机离线交付，`plan_context_token` 仅 URL 脱敏、非权限门（进程内存、12h 过期、不绑身份）；评估为**不适用**，保留回退（删除只会弄坏既有测试且无安全收益），在 `web/routes/domains/scheduler/scheduler_plan_context_token.py` 加设计口径注释结案。

延后（用户裁定）：

- finding-21（超期清单行级灰按钮）：随进行中的前端全面重设计一并处理，已记入 `.codestable/roadmap/aps-frontend-fusion` 观察项；不单独修。
- finding-12（diff-check 空白噪音，P3）：对比 `origin/main` 现仅剩约 1 处，基本清零，不单列任务。

仍需 Win7 真机 / 虚拟机（Mac 开发机无法销）：

- 台账 4 条 accepted risk（绑端口 / 杀进程不误杀普通 Chrome / 运行锁契约 / 运行根 owner），`review_after` 2026-05-31 已过期；管理员 + 域账户共机场景需重点复验运行锁与 owner 归属。
