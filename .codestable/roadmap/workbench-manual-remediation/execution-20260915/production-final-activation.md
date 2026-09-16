# 真实主服务最终激活与数据保留

- 时间：2026-09-15 22:12:35（Asia/Shanghai）。
- 地址：`http://127.0.0.1:5000/workbench`。
- 当前 PID：`14753`；exec session：`83327`。服务持续运行，交由主代理完成浏览器最终验收。
- 构建编号：`b5b59b1812bdf2ef8fc26e2702bcaa45cf7fc8b8a661232c661b1396bb9e7a04`。

## 激活范围

先核验 `lsof` 的 5000 监听进程、`ps` 命令、进程 cwd 以及 `logs/aps_runtime.json`、`logs/aps_db_path.txt`。旧监听进程确认为 PID `96869`，在当前仓库以 Python 3.8 执行 `-B app.py`，数据库路径为 `/Users/lurenxing/GitHub/----/db/aps.db`。

只对核验过的旧 PID 发送 SIGINT；待进程与监听均退出后，在原仓库使用以下命令启动最终后端：

```sh
APS_ENV=production APS_HOST=127.0.0.1 APS_PORT=5000 .venv/bin/python -B app.py
```

新运行时契约与监听 PID 一致；启动日志记录数据库结构检查完成、run recovery 无待恢复任务、dispatcher 已启用。本次没有修改环境配置、没有操作其他端口、没有重建前端。

## 主库保留证据

`production-final-before.json` 与 `production-final-after.json` 使用 SQLite URI `mode=ro`、`PRAGMA query_only=ON` 和只读事务采集。每列同时记录 SQLite `typeof()` 参与行哈希；BLOB 采用十六进制、REAL 采用 `float.hex()`，按行哈希多重集合比较，避免行顺序影响。每表 DDL 和全部 sqlite_master 定义另行比较。

- 共 79 张表（包含 `sqlite_sequence`），77 张完全相同。
- `OperationLogs` 从 13,401 行增至 13,402 行；全部旧行保留，只新增 ID `13402` 的 `plugins / load / runtime / plugins` 启动日志。
- `sqlite_sequence` 仅对应 `OperationLogs` 的计数从 `13401` 变为 `13402`；其他计数相同。
- 所有应用表旧行的字段值、SQLite 类型均保留；全部 DDL 与 schema32 记录相同。
- 22 个批次、64 道批次工序保持不变；两个新扩展表仍为空。
- 前后 `PRAGMA integrity_check` 均为 `ok`；外键检查均无问题。

两份指定备份文件仍在原位，大小均为 16,412,672 字节；前后 SHA-256 完全相同。手动备份哈希同时与首次升级前证据匹配：

- `backups/aps_backup_20260915_210510_manual_d73e63ee6bab.db`
- `backups/aps_backup_20260915_210639_before_migrate_v31_to_v32.db`

完整差异、备份哈希、PID/session 和快照路径见 `production-final-activation.json`。先前 v31→v32 的旧表保留证据仍以 `production-before-update.json`、`production-after-update.json` 为准；本记录覆盖 schema32 的最终后端激活。

## 边界

未发起 SQL 或 HTTP 业务写入，未执行测试、构建、质量门禁或提交；没有清理、覆盖既有脏改。本记录证明本次激活及数据保留，不属于 clean-worktree proof，也不替代浏览器功能验收。
