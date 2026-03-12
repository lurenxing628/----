# Phase0+Phase1 冒烟测试报告（失败）

- 测试时间：2026-03-08 23:38:13
- 错误：no such column: team_id

## Traceback
```
Traceback (most recent call last):
  File "tests/smoke_phase0_phase1.py", line 417, in <module>
    main()
  File "tests/smoke_phase0_phase1.py", line 152, in main
    ensure_schema(old_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=migrate_backups)
  File "D:\Github\APS Test\core\infrastructure\database.py", line 156, in ensure_schema
    conn.executescript(script)
sqlite3.OperationalError: no such column: team_id

```
