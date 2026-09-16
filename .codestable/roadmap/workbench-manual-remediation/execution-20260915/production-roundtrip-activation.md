# 文件回导与现场切换修复的最终激活

- 时间：2026-09-15 22:24:39（Asia/Shanghai）。当前主服务为 PID `19236`，exec session `6442`，持续监听 `127.0.0.1:5000`。
- 本阶段接续 `production-final-activation.json`，没有覆盖上一阶段证据。上一阶段后快照与本阶段前快照的 79 张表完全一致。
- 构建编号：`a84d1ede62907382e5987281c0b2dd6986d541aa1c6a3bb2a20481d853d59f01`。静态核对 manifest 的 355 个 inputs，实文件 SHA-256 全部匹配；交付文件 263 个。没有执行 build。

## 激活与数据

重新核验运行时契约、5000 实际 listener、Python 3.8 命令及当前仓库 cwd 后，只向旧 PID `14753` 发送 SIGINT。退出后用原命令 `APS_ENV=production APS_HOST=127.0.0.1 APS_PORT=5000 .venv/bin/python -B app.py` 启动。新 PID、端口、主库路径与运行时契约一致，排产恢复无 pending，dispatcher 已启用。

`production-roundtrip-before.json`、`production-roundtrip-after.json` 沿用前阶段的只读 SQLite 与类型感知行哈希方法：

- 79 张表（含 `sqlite_sequence`）中 77 张完全一致；全部 DDL 与 schema32 相同。
- 所有应用表旧行均保留。只新增 ID `13403` 的插件启动日志，`OperationLogs` 从 13,402 行增至 13,403 行；对应自增计数同步增加 1，其他计数未变。
- 22 个批次、64 道批次工序不变；完整性检查 `ok`，外键检查无问题。
- 手动备份 `aps_backup_20260915_210510_manual_d73e63ee6bab.db` 与迁移前备份 `aps_backup_20260915_210639_before_migrate_v31_to_v32.db` 原位保留，两个阶段前后哈希均相同。

完整结果见 `production-roundtrip-activation.json`。浏览器验收继续由主代理执行。

## 本阶段测试登记

- `test_file_reference_roundtrip.py` 唯一归属 `workbench_resources`；补齐其跨批次文件导入所用模块和 `test_batch_files.py` helper 的依赖范围。
- `test_field_scope_navigation_browser.py` 唯一归属显式浏览器组 `workbench_browser`，不改成默认 required；`field_scope_navigation_browser.cjs` 仅作为依赖。
- 两项均加入 reviewed 记录；只做静态文件存在、唯一 owner、直接本地导入依赖覆盖核对。结果见 `final-target-registration.json`。
- 没有修改既有算法审查清单差异。未运行测试、全门禁、构建、提交或任何 SQL/HTTP 业务写入，既有脏改保留。
