---
doc_type: fix-note
date: 2026-09-10
status: completed
scope: R1-K SGS, import resolver and SQLite support increments
---

# R1-K 最后增量冻结交接

最终状态：后续已获准的候选 schema/v9 fixture 登记由主线核验闭环，当前为 582/85/33，详见文末“主线最终确认”。以下 581 数字及对应源哈希保留为该时点记录。

## 当前计数与边界

- 已完成 SGS/L 两个指定新文件和 MAIN SQLite support 影响面接合，代码写集再次冻结。
- **581 required / 85 supplemental / 33 required groups**；required coverage 的 missing、duplicates、unknown 全空，required 无缺文件，workbench 真实测试发现无漏登。
- 308 个 required 仍 untracked，即原 280 加本轮 28。无 stage/commit，唯一既有 staged 文件及整个 staged patch hash 保持不变。
- 这是首批 579 登记的授权增量；没有重跑原 1323 项全套。D/L 产品或工具业务验证由相应 owner/主线负责，K 只做本登记必要验证。

## 两个新增文件

| 实际文件 | 唯一 required owner | 冻结 SHA-256 |
| --- | --- | --- |
| `tests/algorithm/test_sgs_explicit_piece_scope.py` | `scheduler_run_core` | `0d256a2357637d4e9e852324c19df398d1b3ae88286959ffe3b2e5e0f91c9fc6` |
| `tests/gate_meta/test_round1_import_resolver.py` | `quality_gate` | `195d3c3e5ffb69fa107c82936dc1107b9d32beaf1e41569e90b2029cf8027327` |

- `tools/test_registry_data.py` 显式登记两条路径；`tools/test_registry_groups_scheduler.py` 追加到对应现有组，不创建新组、不用 target glob。
- `core/algorithms/greedy/dispatch/sgs.py` 通过原 `scheduler_run_core` 的 `core/**/*.py` scope 选择新增 SGS 测试，`all_required_groups=False`。新合同固定唯一 owner、required 分类、真实测试函数和源变更选择。
- L 的 `tools/import_cycle_analysis.py`、`tools/import_cycle_graph.py`、`tools/scan_import_cycles.py` 已在 `quality_gate` 的原 scope 中；这些基础工具原本也属于显式 common gate scope，变更时按原合同选择全组，不是 unknown fallback。没有修改该策略或 baseline。
- L 真实读取的 `tests/_support/paths.py` 及三处动态导入样本仅补为 quality_gate 输入；没有修改受保护的 `test_frozen_bundle_contract.py`。
- SGS 新文件实际收集到 **10** 个用例；L 新文件实际收集到 **49** 个用例。L 所述联合 scanner 75 项不是新文件单独的收集数量，K 不把收集当作执行通过。

## SQLite Support

- MAIN 新 `tests/_support/sqlite_snapshot.py` SHA-256：`9d420f33f20226ba065f6afa1f304339e519d2f321c79740df2fb4b8f8e86bf1`。
- 只读 AST 追踪现有测试的显式模块导入链，得到 20 个 required、10 个 supplemental 实际消费组；原来 helper 路径仅命中 `workbench_registry`。映射证据在 `/tmp/aps-r1-k-XINZqC/sqlite-support-impact.json`。
- `tools/test_registry_groups_workbench.py` 的 `_SQLITE_SNAPSHOT_GROUPS` 逐项声明 29 个工厂生成的实际消费组；原 `workbench_registry` 已由 `tests/**/*.py` 覆盖，合计 30 组。没有将该路径无条件塞给所有组。
- `tests/gate_meta/test_workbench_round1_registry_contract.py` 固定精确组集合、不走 fallback、helper 不冒充 test，以及逐组文件内容变化必须让指纹失效。
- MAIN 新增的 `test_shared_sqlite_snapshots_keep_original_objects_rows_and_schema` 已实际执行通过，证明旧 facade 保留同对象、schema/typed rows 和只读行为。K 未改 snapshot 实现、旧 facade 或 web_pages 消费者。

## 定点结果

全部命令使用 `.venv/bin/python`、私有 `APS_*` 目录、`PYTHONPYCACHEPREFIX`、pytest cache 与 basetemp，根目录为 `/tmp/aps-r1-k-XINZqC/`。

| 检查 | 结果 / 证据 |
| --- | --- |
| SGS 增量登记及相关原合同 | 86 passed，20.96s；`sgs-registry.xml` |
| SGS + L 最后登记、旧顺序/计数、源指纹 | 58 passed，18.77s；`last-registry.xml` |
| SQLite support 精确 scope、30 组 fingerprint、MAIN 同对象/只读合同 | 35 passed，2.51s；`snapshot-registry.xml` |
| 新文件收集 | SGS 10 collected，1.48s；L 49 collected，0.64s；不是业务测试执行证明 |
| Ruff | 七个相关文件全部通过 |
| 定点 Pyright | 三个 registry 工具文件 0 error / 0 warning；两个新增 meta 文件 0 error / 0 warning |

最终 scope/计数/哈希机器记录：`/tmp/aps-r1-k-XINZqC/last-support-freeze.json`。上述集合有重叠，不相加成独立总数。

## 最终源 Hash

| 文件 | SHA-256 |
| --- | --- |
| `tools/test_registry_data.py` | `b2e4547379d4ef3311d6c2dbda9d031b4dab98d23aabdb993f8842b168dc6140` |
| `tools/test_registry_groups_scheduler.py` | `32bd554d5750d925a8d78eff9e012de929fb135e5362787753e7417cde59b377` |
| `tools/test_registry_groups_workbench.py` | `143f58be0a06294a55297bd0fa50e1fdb068fbcfea6b7e9c4ab4855cea8e241d` |
| `tests/gate_meta/test_workbench_registry_contract.py` | `ace20917502109021b7aff0812a51f5fb6b37370fa118f92ee7cf1c314407ed5` |
| `tests/gate_meta/test_long_gate_manifest.py` | `14d009512533d3a8edc452e8209435d331b219169e67c5cbdd600bc56531cb2c` |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | `15004502ab9c723701933d67ee3abf55db997c59285ffcfe51c57d8ea4f5681b` |
| `tests/gate_meta/workbench_round1_registry_support.py` | `c64b916c7897ce9b95ddc129a5a6d52c4a5906bc1b3514146fd3962ba3417f94` |

- required registry hash：`0936914ee40277a834a9103ead0469cd2de299d6903b456bce7d0d6b4bde6841`。
- group registry hash：`92958018b4da923218ac409dc5392e87b0e8d581e48915f38e9dd61d79f25871`。
- staged patch SHA-256：`952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`，未变。

## 581 时的待办

- I 的 `tests/migration_db/fixtures/schema-v9.sql` 已出现，SHA-256 为 `f2451893212a29118dc1378770dbac18b33d3f5b10a44b8d87d9bf8aeef255a4`；原 `tests/candidate/test_scheduler_candidate_schema_contract.py` **并不在 required 或 supplemental target 登记中**，实际 owner 查询为空。
- 因此“只补 fixture scope 即运行原 required owner，且不增加 required 数”当前无法成立。K 已向主线报告并请求选择，没有虚构 owner，也没有擅自把这个存量测试升级 required。若主线选择升级，581 将再加 1 为 582；此处未宣称 v9 fixture 接合已完成。
- 未修改 D 的 `sgs.py`、L 的三个 scanner 工具、I 的候选 schema 测试或 v9 fixture、MAIN 的 snapshot/启动/构建源码；未执行全门禁、5000 压测、全局 build、预览切换、生产 DB、Win7 发布或旧 UI 下线。

## MAIN 末次既有 Fixture 核验

- 用户随后修正 identity v19 fixture 的 v30/v31 精确差集，并把三个 v31 纯 helper 移到既有 `legacy_migration_current_support.py`；没有新增测试文件。
- K 仅调用真实 daily impact planner 验证，未重跑用户正在负责的 187 项或其他业务回归。三个 support 都命中已有 `tests/workbench/*_support.py`，各选择原有 25 个 workbench 相关组；`test_identity_metadata.py` 选择原 `workbench_foundation` 及 `workbench_registry`。四条路径均选择 identity 原合同，`all_required_groups=False`，support 都不是 target。
- 登记仍为 581/85/33；K 的九个登记相关源 hash drift 为空，staged patch hash 不变，因此没有再写 registry 源。
- 实际记录：`/tmp/aps-r1-k-XINZqC/main-late-fixture-check.json`。当时四文件 SHA-256 分别为：identity support `c155a48b2e93f26c4987ee49d3e1244f01ec3f61052bb29eb50b6168a6b9ab29`；identity test `b8884f51c2286d18704dfd892058b8b249b54fe245aa192a0f64eab34daa43bd`；dashboard migration support `84787723980578575d4da5e494bac9289ba852fb2d86a478dc9297ccb86d99b0`；legacy current support `952b5b47c60622da1da63c81769c2d1abd9ad5d906906769cb66fe9b5674d04a`。这是 scope 核验，不是最新业务代码执行证明。

## SGS 测试类型收窄后的最终 Hash

- MAIN 仅将新 SGS 测试中的状态、结果和派工规则换成真实 `ScheduleRunState`、`ScheduleResult`、`DispatchRule`，并显式断言 graph 非空；原 2 x 5 参数组合仍在，产品源码由 MAIN 保持不改。
- K 已读取最新测试文件，将上表冻结 SHA-256 更新为 `0d256a2357637d4e9e852324c19df398d1b3ae88286959ffe3b2e5e0f91c9fc6`；取代先前的 `a46b4e1f8753d539f7362f7eb611463a8f32bd9a658cd6201b2dabc98cf278a5`。历史 `last-support-freeze.json` 不重写，最新变更记录为 `/tmp/aps-r1-k-XINZqC/sgs-final-source-hash.json`。
- 唯一 owner 仍为 `scheduler_run_core`；581/85/33、required/group registry hash、九个登记相关源和 staged patch hash 均未变。K 本次只更新源绑定，没有重跑 1323 项或业务测试；主线所述 822 项联合运行仍待最终结果，不记为已通过。

## 主线最终确认

- 已明确批准并完成 `tests/candidate/test_scheduler_candidate_schema_contract.py` 晋升 required，唯一 owner 为已有的 `scheduler_run_core`，与候选持久化合同一致；真实 `tests/migration_db/fixtures/schema-v9.sql` 只作该组输入，不是 pytest target，变更能使实际文件指纹失效。
- 最终 **582 required / 85 supplemental / 33 groups**，missing、duplicates、unknown 全空；该旧测试已经被 Git 跟踪，因此 required untracked 仍为 **308**。
- 最后候选/登记增量初次 12 passed。随后增加的文件指纹测试曾误读 `hash` 字段，产生 1 个 KeyError；改为真实 API 的 `content_hash` 后单例通过。主线随后把整个 `test_workbench_round1_registry_contract.py` 连同候选 schema 两例完整复跑：**163 passed，18.52 秒，0 failure/error/skipped**。没有隐藏该中间失败或放松指纹断言。
- 最后两个 meta 文件定点 Pyright 0 errors / 0 warnings，相关五文件 Ruff 通过。其间产品代码没有变化；主线最终业务联合实际为 **821 passed**，不是此前传递的预估 822。
- 主线实际日志、XML 和类型结果：`output/workbench-migration/verification/round1-20260910/registry-final.log`、`registry-final.xml`、`registry-types-final.json`。
- `agents/K/final-582-freeze.json` 是最后增量快照；其中 meta 合同随后追加了上述已通过的文件指纹测试，最新主线源绑定另存 `registry-sources-final.sha256`，不改写旧快照或冒用旧 hash。
- 最终 required registry hash：`db3806e40da7b1065623ac4f7800f4896108cad326f974482d9e3acaf099e557`；group registry hash：`76cd6dbe0a2e5d4c7c665968caf7fedd1ad508c6c53dfe9890553ab0c386f39a`。主线再次调用真实 coverage API，计数和哈希均匹配。
- K 已停止，不留后续登记待办；原 staged patch hash 未变。仍不是 full-gate 或 clean-worktree proof。
