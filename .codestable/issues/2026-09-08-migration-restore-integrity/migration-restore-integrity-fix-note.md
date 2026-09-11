---
doc_type: issue-fix
issue: 2026-09-08-migration-restore-integrity
path: fast-track
fix_date: 2026-09-08
tags: [migration, sqlite, backup, integrity, rollback]
---

# 迁移回滚备份完整性修复

## 1. 范围与起点

- 本轮已授权局部后端实施，不改前端、不操作真实业务库、不改公共台账或门禁基线，不执行 git add / commit / push。
- 已读取 AGENTS.md、.codestable/attention.md、.codestable/reference/system-overview.md 和项目版 cs-issue-fix；已检索 compound 中相关备份/恢复记录。
- 修改前执行 git status --short，工作区已有大量 tracked / untracked 改动，以及他人的暂存内容。
- 起始源码快照：`/tmp/aps-backend-closeout.9GGk2u/starting-tree.tar.gz`。
- 快照 SHA-256：`b490aef78cc9913c5f31d48c4ee5de35faf7b94cf031f961259870b6636dfd23`。
- 本轮编辑前，migration_backup.py、backup.py、test_database_migration_runner_delegation.py 和原有未跟踪 test_restore_integrity_check_contract.py 均与快照逐字节一致。
- 已先运行 symbol_locator 的 whereis / callers / callees restore_db_file_from_backup；输出标记为旧快照，因此另读当前源码和测试核实。当前产品调用方是 migration_runner.py:266 的 _rollback_from_backup，实际调用在 :273。

## 2. 根因

起始版本 `core/infrastructure/migration_backup.py:55-62` 读取普通文件字节后，直接检查目标文件、清理 WAL/SHM/JOURNAL 并替换主库，没有验证字节是否构成完整 SQLite 数据库。普通文件检查不能发现空文件、截断页或损坏的 B-tree。

`backup.py` 的既有 dirty 改动已经给 BackupManager 的备份创建、恢复和自动回滚增加完整性校验，但迁移回滚走独立的文件替换入口，没有经过该校验。

最初新增的 12 项回归在旧产品代码上得到 **11 failed, 1 passed**：8 种坏文件、实际读取 payload 校验、重试期间备份变坏及迁移调用方错误传播均暴露缺口；原有正常字节恢复场景通过。

## 3. 修复方案

- `core/infrastructure/migration_backup.py:55-58`：每次重试读取 backup_payload 后立即校验；通过之前不调用目标 stat、sidecar 清理或主库替换。通过后写入的仍是同一份不可变 bytes，不再读取备份路径取得另一份内容。
- `core/infrastructure/sqlite_integrity.py:31-64`：先检查 SQLite 文件头、页大小与完整页长度，再将捕获的字节写入独立 TemporaryDirectory，通过只读 SQLite URI 执行完整性检查。SQLite 不打开备份源或真实恢复目标；WAL 模式所需的临时 sidecar 也限制在隔离目录内。
- 打开 SQLite 前关闭暂存文件，清理目录前关闭连接；失败不吞错，校验异常保留 cause。文件头或校验不通过抛 BackupIntegrityError，校验临时目录的文件系统异常继续上抛。
- `core/infrastructure/sqlite_integrity.py:14-28`：原样提取现有 BackupIntegrityError 和完整性检查函数；函数仅将名称从 _run_sqlite_integrity_check 改为 run_sqlite_integrity_check。
- `core/infrastructure/backup.py:46-47`：导入并保留原类名和函数别名。已用起始文本重建预期差异，逐字节确认本轮仅提取类/函数并增加两个导入；备份保留数量、维护锁、错误码及其余已有 dirty 改动不变。
- 文件占用识别、默认 6 次尝试、线性退避、首次警告、重试耗尽抛原异常及非文件锁错误不重试的既有行为均不改动。

## 4. 本轮修改文件

1. `core/infrastructure/migration_backup.py`：接入同一 payload 校验。
2. `core/infrastructure/sqlite_integrity.py`：新增窄职责共享校验叶子。
3. `core/infrastructure/backup.py`：仅提取并重新导入原有校验。
4. `tests/migration_db/test_database_migration_runner_delegation.py:272-346`：三个文件/sidecar 保护测试使用真实有效备份，仍验证原有拒绝分支。
5. `tests/migration_db/test_migration_restore_integrity.py:65-251`：坏文件与 sidecar 保留、最终 payload、校验失败与隔离副本清理、迁移调用方异常、不同页大小及 WAL/DELETE 模式。
6. `tests/migration_db/test_migration_restore_retry_contract.py:28-115`：文件锁成功重试、耗尽、默认次数、非锁错误。
7. 本 fix-note。

原有未跟踪的 `tests/migration_db/test_restore_integrity_check_contract.py` 保持逐字节不变。上述清单是本轮写集，不代表整个共享工作区的 git diff。

## 5. 实际验证

环境：macOS，仓库 `.venv/bin/python` 为 Python 3.8.10，SQLite 3.35.5；未安装或升级依赖。

| 验证 | 结果 |
| --- | --- |
| 修改前 migration runner delegation / backup integrity / restore integrity 三个现有测试文件 | 21 passed |
| 新增回归在旧产品实现上 | 11 failed, 1 passed，确认缺陷存在 |
| `.venv/bin/python -m pytest -q tests/migration_db` | 135 passed |
| maintenance_window_mutex / backup_cleanup_min_keep_floor / backup_create_integrity_error_message / restore_success_condition 四个既有文件 | 12 passed |
| 最终将 tests/migration_db 与上述四个文件合并运行 | 147 passed in 4.20s |
| `.venv/bin/python -m ruff check`，下列六个本轮产品/测试文件 | All checks passed |
| quality_gate_scan 的 scan_oversize_entries / scan_complexity_entries，仅三个产品文件 | oversize=[]，complexity=[] |
| git diff --check，仅本轮 tracked 写集 | 通过 |
| backup.py 相对起始文本的精确提取核对 | 通过；旧类和校验正文保持原样 |
| 暂存 diff 与本轮核对前基准比较 | 一致；本轮未执行任何暂存操作 |

ruff 的精确文件参数：

```text
core/infrastructure/migration_backup.py
core/infrastructure/sqlite_integrity.py
core/infrastructure/backup.py
tests/migration_db/test_migration_restore_integrity.py
tests/migration_db/test_migration_restore_retry_contract.py
tests/migration_db/test_database_migration_runner_delegation.py
```

最终合并回归命令：

```bash
.venv/bin/python -m pytest -q tests/migration_db tests/calendar_maintenance/test_maintenance_window_mutex.py tests/calendar_maintenance/test_backup_cleanup_min_keep_floor.py tests/app_runtime/test_backup_create_integrity_error_message.py tests/app_runtime/test_restore_success_condition.py
```

坏备份测试使用临时生成的 SQLite 文件和三个 sidecar 标记文件，逐一比对主库及 sidecar 的字节、inode、mtime_ns 和大小，并断言目标 stat 与 sidecar 清理未被调用。覆盖空文件、非 SQLite、短文件头、仅文件头、缺最后一字节、半截页、缺整页及坏 B-tree。

有效备份覆盖 512/4096/65536 字节页和 DELETE/WAL 模式；检查连接为只读 URI、读取隔离副本，隔离目录包含空格及 `#?%` 时仍可使用，连接关闭后不残留隔离文件。额外测试证明源文件读取后被改写时恢复的仍是已校验字节；重试重新读到坏备份时不会再次清理/替换目标。

## 6. 未通过项与边界

- 额外只读命令 `.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean` 实际退出 1：报告基线外两个硬加载文件环（算法包和 process/unit_excel 包）及一条目录圈内边（web.bootstrap.startup_config -> config），不包含本轮三个产品模块。未修复、未刷新基线。
- 上述导入环所涉 26 份源码中，23 份与起始快照一致；external_groups.py、run_context.py、scheduler.py 与快照不同，但均不在本轮写集，本轮未修改，也不对其他工作区变化归因。该结果不能写成整仓导入门禁通过。
- 初次直接按脚本路径启动 import-cycle 工具报 ModuleNotFoundError: tools；改为上述模块调用后才得到实际扫描结果，没有修改工具。
- 未运行完整 `scripts/run_quality_gate.py`：本轮限定写集，且该入口会清理/写入共享门禁产物；当前大量 dirty 下也不能形成 clean-worktree proof。上面的局部测试和只读扫描不等价于完整门禁。
- 未在 Win7 真机验证原生文件占用。Python 3.8.10 本机测试通过；PermissionError 和 winerror 5/32/33 的文件锁路径通过注入验证。
- 完整性检查证明可读取的 SQLite 结构，不证明业务内容正确或备份足够新；不新增业务 schema 校验，也不消费备份旁边的 WAL 来拼出另一份恢复数据。
- 仅承诺本次读取的坏 payload 在该次尝试触碰目标主库/sidecar 前被拒绝。校验通过后发生写入、替换或后置清理错误，仍沿用既有错误处理；本次没有把整段恢复改造成事务。若前一次有效 payload 已进入 sidecar 清理，后续重试读取的备份变坏，不声称可撤销前一次尝试的清理。
- 隔离校验需要临时磁盘空间，并增加一次字节写入和 SQLite 检查；未做大库性能测试。
- 只在测试临时库执行恢复；没有对真实业务库执行恢复。前端、公共台账和门禁基线均未由本轮修改。所有本轮修改保持未提交，其他人的暂存、未暂存及未跟踪改动保留。
