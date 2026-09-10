---
doc_type: issue-fix
status: fixed
created: 2026-09-10
summary: DZ 修复 DS 当前版本夹具并登记已完成 DX browser；局部验证通过，保留开发中 discovery 和 untracked-proof 失败
tags: [workbench, schema31, outsourcing, registry, DZ]
---

# 结论与范围

- 本轮授权工作完成，不代表完整门禁或 clean-worktree proof。
- 只手工修改四个测试/support/登记文件及本文。产品、source repo、schema.sql、所有 migrations、固定历史 SQL、DX/旧 UI、DU 和 main live server 均未修改。
- 没有全局 build、stage、commit，没有操作旧 preview 或真实业务数据库。
- 测试使用仓库 `.venv/bin/python`，实际 Python 3.8.10。修改后验证使用独立 `/tmp`、显式测试路径及 `-p no:cacheprovider`；未新增依赖，未在 Win7 实机运行。

# 已完成修改

| 文件 | 修改 |
| --- | --- |
| tests/workbench/outsourcing_targets_labels_support.py | 真实 ensure_schema/get_connection 当前库断言改为 CURRENT_SCHEMA_VERSION；ensure_current_schema_contract 读取真实库版本，不再传入 30 |
| tests/workbench/test_outsourcing_targets_labels.py | 仅将 test_current30_http_labels_preserve_old_fields_and_all_storage 更名为 test_current_http_labels_preserve_old_fields_and_all_storage |
| tools/test_registry_groups_workbench.py | 在 workbench_browser 末尾追加 test_dashboard_external_handling_widgets.py；补20个实际编译源码和10个support/probe/运行输入的确切 scopes |
| tests/gate_meta/test_workbench_registry_contract.py | 同步 completed browser 末尾项，锁住 required520/supplemental66、输入范围及 source selection |

- DS 原意是当前真实连接，不是历史 v30：没有把31重标30，也不需要引入历史起点。DX 自己的固定历史30组件夹具原样保留。
- AST 比较证明 DS 测试除函数名外完全相同；nullable/ref/BLOB/替换/分页snapshot/readonly/存储异常传播断言全部保留。storage/target_rows/change_origin 三个函数 AST 原样不变。
- required 32 groups / 520 targets 完全不变，workbench required 247；supplemental 65 -> 66，旧 targets/scopes 顺序全部保留为前缀，其他 supplemental groups 完全不变。
- coverage missing/duplicates/unknown 均为空；required registry hash 仍为 `ae7b1a0b43b751d3e42c2bb95c1f8a0b957322a8e2389ba03fd58963b4776d4b`。
- `tests/gate_meta/test_long_gate_manifest.py` 无需修改，与本轮开始时字节完全相同；不覆盖 DY 已有改动。
- discovery 函数 AST 完全不变。DU/EA 没有提前登记，main 的既有 test_run_live_server.py target 没有新增 glob。

# 真实验证

证据根目录：`/tmp/aps-dz-schema31-DRq7IG`。

| 范围 | 结果 | 证据 |
| --- | --- | --- |
| 修改前 DS 原文件 | 35 errors，全部停在夹具 assert version == 30 | 本轮终端回执 |
| 修改后 DS 单独执行 | 35 passed | ds-after.xml |
| 最终导入格式整理后 DS 再执行 | 35 passed | ds-final.xml |
| DS + DY主迁移 + DT/DO + 旧外协 | 314 passed，52.34s | backend.xml |
| DX3 + 旧 Dashboard2 + 旧外协UI2 | 7 passed，81.54s | ui.xml |
| registry + long manifest + full-debt registry | 494 passed / 2 failed，21.97s | meta.xml |
| 收尾重跑两项 remaining | 同样2 failed，0.74s | remaining-final.xml |

- 后端314不重复计数：DS35 + 9个主迁移文件106（DY36包含其中）+ DT5/DO3文件84 + 旧外协5文件89。精确文件集及所有 nodeid 见 backend.xml。
- 各次运行之间有重叠，不把上表相加冒充唯一用例数。上述修改后测试没有 skip。
- 四个修改的 Python 文件 Ruff 全部通过；五个授权 Python 文件通过 Python3.8 AST 解析；tracked `git diff --check` 通过。
- 实际 Chromium `109.0.5414.46`：DX 4场景/38图/9边界/4次重启；旧 Dashboard 4场景/36图/8边界/4次重启；旧外协 4场景/46图/17边界/4次重启。
- 三组 UI 的 errors/external 均空、server_stopped=true、compile_global_build=false；源码 SHA 和逐表保留断言通过。DX报告实际20个 report.sources 均有确切登记。
- 已查看 DX 1920浅色处置表单、1392深色独立事实截图；该两图未见异常遮挡。浏览器汇总见 ui-summary.json，各组完整来源与SQL/DDL证据保存在对应 ui 子目录。

# 真实 Remaining

1. `tests/gate_meta/test_workbench_registry_contract.py::test_discovery_reports_unregistered_real_tests_without_expanding_targets`：最终实查缺 `tests/workbench/test_du_system_restore_browser.py`、`tests/workbench/test_du_system_restore_view.py`、`tests/workbench/test_ea_zero_duration_chain.py`。这些是并行开发文件，未获本轮登记授权；DX已从缺失清单消失。保留原检查，不忽略或伪造通过。
2. `tests/gate_meta/test_full_test_debt_registry_contract.py:1264`：`test_quality_gate_required_startup_and_full_debt_share_registry` 仍首先因 untracked 的 `tests/gate_meta/test_workbench_registry_contract.py` 拒绝。实际 required 未 tracked 共247个；这是合法 tracked-proof 前提，未 stage 或放宽断言来规避。

这是本轮明确执行范围的完整失败清单，不是全仓错误清单。没有在该组合中发现需新增产品修复的失败；未把 in-flight 资产差异或上述状态失败称为产品 bug。完整 gate 未运行：工作区并行开发、required尚未tracked，本轮按授权保持局部验证，不触发共享构建/门禁产物改写。

# 保留与交接

- 原稿及哈希：before/、before-hashes.json；46个受保护文件前后全字节不变，详见 protected-verification.json，含schema.sql、v1..31 migrations、固定SQL、migration_state/database、外协source repo及frozen_bundle。
- 固定 schema-v30.sql SHA-256：`16460ac6d0f95373eca466b101cfcc46097187760e2438fb3a8c292c28761b2e`，未修改。
- 起止 staged diff SHA-256：`952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`。
- 暂存区仍只有 `tests/gate_meta/test_frozen_bundle_contract.py`，保持200+/0-；四个本轮代码文件及本文未暂存、未提交，其他已有dirty/untracked内容未回退或清理。
- 主代理可继续下一版 build；DU/EA 待各 owner 完成交接后再准确登记。只有真实满足tracked和最终HEAD门禁前提后，才能另行出相应proof。
