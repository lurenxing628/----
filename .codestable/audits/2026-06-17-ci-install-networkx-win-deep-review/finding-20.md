# Finding 20：首页备份健康扫描会跟随软链接，可能隐藏真实未备份风险

- 优先级：P1 阻塞
- 结论：首页备份提醒扫描 `aps_backup_*.db` 时使用 `os.stat()`，会跟随软链接。备份目录里如果出现符合命名的软链接，页面会把链接目标的 mtime 当成最新备份时间。

## 根因

固定名文件安全链路已经强调不要跟随 symlink，但首页备份健康是另一条只读扫描链路。它用 `os.stat()` 看文件状态，`stat` 默认跟随软链接；随后 `S_ISREG` 看到的是目标文件类型，不是链接本身。

大白话说：首页想确认“备份目录里有没有真正的备份文件”，但它会顺着快捷方式看外面的文件，然后把外面的文件当成本目录备份。

## 调用链

- 首页路由 `web/routes/dashboard.py`
- `read_latest_backup_time(current_app.config["BACKUP_DIR"])`
- `build_backup_health_hint(...)`
- 首页展示备份健康提示

## 证据

- `web/viewmodels/dashboard_backup_health.py:27-52`：扫描文件名后调用 `os.stat(os.path.join(...))`，然后用 `S_ISREG` 判断。
- `web/routes/dashboard.py:441-445`：首页读取备份目录失败才提示错误；成功读到时间就继续构建健康提示。
- `tests/web_pages/test_dashboard_backup_health.py:45-80`：现有测试覆盖前缀、后缀、目录、缺目录、stat 失败，但没有覆盖 symlink。
- 主线程只读复现：备份目录中放入旧的真实备份，再放入名为 `aps_backup_link.db` 的 symlink 指向外部新文件，`read_latest_backup_time()` 返回外部新文件时间，`link_is_symlink=True`。

## 影响

- 首页可能显示“最近已备份”，但真实备份目录里只有旧备份或没有可用新备份。
- 用户会错过备份提醒，恢复数据时才发现没有想要的备份。

## 建议

- 使用 `os.lstat()` 先拒绝 symlink，再对普通文件读取 mtime。
- 增加 symlink/hardlink 测试，确保链接不参与最新备份时间。
- 和备份清理、固定名文件安全 helper 统一口径。
