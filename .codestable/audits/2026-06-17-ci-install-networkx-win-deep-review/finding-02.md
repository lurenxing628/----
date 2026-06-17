# Finding 02：手动删除备份绕过固定文件安全删除

- 优先级：P1 阻塞
- 结论：`/system/backup/delete` 和 `/system/backup/delete-batch` 不应该直接 `os.remove()`。

## 根因

仓库已经有固定文件安全删除工具 `remove_fixed_file()`，它会拒绝软链接、非普通文件、硬链接等风险文件。但手动删除备份的路由只校验文件名，再拼出路径并直接 `os.remove()`。

自动清理链路走的是安全工具，手动路由没有走同一套规则，形成了安全口径分叉。

## 调用链

- 页面提交备份删除请求
- `web/routes/system_backup.py::backup_delete()`
- `_validate_backup_filename()`
- `os.path.join(backup_dir, filename)`
- `os.remove(backup_path)`

批量删除同理：

- `web/routes/system_backup.py::backup_delete_batch()`
- `_validate_backup_filename()`
- `os.remove(p)`

## 证据

- `web/routes/system_backup.py:179-188`：单删直接 `os.remove(backup_path)`。
- `web/routes/system_backup.py:208-234`：批删直接 `os.remove(p)`。
- `core/infrastructure/safe_files.py:293-310`：`remove_fixed_file()` 会检查软链接、普通文件、硬链接后再删除。
- `core/infrastructure/backup.py:508` 和 `core/services/system/maintenance/cleanup_task.py:85`：自动清理链路使用安全检查。

## 影响

- 同一类备份文件，自动清理安全，手动删除不安全。
- 如果备份目录里出现软链接或硬链接，手动路由没有复用已有防护。

## 建议

- 手动单删、批删统一收口到 `BackupManager.delete_backup()` 或直接调用 `remove_fixed_file(..., allow_symlink=False)`。
- 补手动删除路由的软链接、硬链接、非普通文件回归测试。
