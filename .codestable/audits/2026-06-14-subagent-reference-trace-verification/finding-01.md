---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "security-01"
nature: security
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 01：固定名运行文件软链接加固半截化

## 速答

`7003d6a3` 已经证明固定文件名需要软链接拒读拒写，但同类运行文件和备份文件仍有裸 `open`、`os.stat`、`getmtime`，会跟随软链接。

## 关键证据

- `core/infrastructure/backup.py:471`：`cleanup_old_backups()` 用 `os.path.getmtime(filepath)` 判断过期，再 `os.remove(filepath)` 删除，判断的是链接目标时间，删除的是链接条目。
- `core/infrastructure/backup.py:488`：`list_backups()` 对 `aps_backup_` 文件名直接 `os.stat(filepath)`，缺 `islink`/`lstat`/普通文件守卫。
- `core/services/system/maintenance/cleanup_task.py:84`、`:100`：自动清理同样 `getmtime()` 后 `remove()`。
- `web/bootstrap/launcher_contracts.py:84`、`:89`、`:91`：`aps_port.txt`、`aps_host.txt`、`aps_db_path.txt` 直接 `open(..., "w")`。
- `web/bootstrap/launcher_contracts.py:301`、`:441`：`aps_launch_error.txt` 和 `aps_runtime.json` 写侧直接 `open(..., "w")`。
- `web/bootstrap/launcher_contract_result.py:59`：`aps_runtime.json` 读侧普通 `open()`，没有软链接拒读。
- `web/bootstrap/launcher_observability.py:134`、`:146`：`launcher.log` 追加写和 `aps_launch_error.txt` 覆盖写都没有软链接守卫。
- `web/bootstrap/security.py:61` 是已有对照：写 `aps_secret_key.txt` 前发现软链接会先 `os.remove(secret_file)`，再写真实普通文件。

## 影响

前提是攻击者或误操作能在运行目录、日志目录或备份目录提前放入软链接。Win7/Windows 上创建软链接有权限限制，但代码本身没有防护；一旦软链接存在，普通写入会写穿到链接目标，读取/统计也会读到目标文件。

## 修复方向

把“固定名文件安全读写/统计”抽成统一 helper：读前 `lstat`/拒绝软链接和非普通文件，写前发现软链接则删除链接本体或拒写，备份列表/清理用同一套普通文件判断。

## 建议动作

`cs-issue`，因为这是可达安全一致性问题，且已有 `security.py` 和 `runtime_log_reader.py` 可作为行为样板。
