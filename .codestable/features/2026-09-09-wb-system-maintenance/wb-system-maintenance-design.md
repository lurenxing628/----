---
doc_type: feature-design
feature: wb-system-maintenance
status: approved
created: 2026-09-09
summary: 代理V实施系统管理维护能力，恢复解禁和全局挂载由主代理判定。
tags: [workbench, system, maintenance]
---

# 系统管理维护实施与交接

## 授权边界

- 依据已批准 workbench-prototype-migration 路线图第16项、合同第3/8.4节、运营评估第11节。
- 仅新增 workbench_system 模型、workbench/system_* 服务与路由、SystemMaintenance* UI、专属测试和本 feature 文档。
- 不改备份核心、恢复保护、transaction、scheduler、schema、shared transport、main、build、global __init__、系统 overview。
- 不提交、不 build、不 spawn 代理。保留原 dirty/staged。
- 用户补充：新UI先报文件名及顺序；收到落盘同步信号前不新增 app 文件，替换 SystemLive 另行同步。

## API 交接

所有地址前缀 `/api/workbench/v1/system`，独立于 resources namespace。

| 方法/后缀 | 输入 | 结果 |
| --- | --- | --- |
| GET /backups | query/type/status/start/end/page/page_size/snapshot_ref | 全目录过滤后分页；不透明 backup_ref、write_context；文件存在不等于校验通过 |
| POST /backups/create | CommandInput，input={} | 外置 file_operation，不生成SQLite receipt |
| POST /backups/delete | CommandInput，input={backup_ref} | 单文件删除；原请求幂等，目标变化拒绝 |
| POST /backups/restore | CommandInput，input={backup_ref} | 既有独立恢复流程；默认禁用，只有主代理接好全局保护后才解禁 |
| GET /logs | query/type/status/level/file/start/end/page/page_size/snapshot_ref | 三个白名单运行文件各最近200条、OperationLogs最近500条；先限定窗口再筛选 |
| GET /logs/export/csv | 与读取一致的筛选和snapshot_ref | 全筛选窗口，不只是当前页；CSV公式防护、UTF-8 BOM |
| GET /logs/export/zip | 与读取一致的筛选和snapshot_ref | 有界脱敏日志CSV、范围和缺失说明；不是原始日志全历史ZIP |
| GET /config | 无 | 八字段真实只读快照、旧异常/缺省标记、短期write_token |
| POST /config/save | CommandInput，input=八个规范化字段 | 一次SQLite事务：两组设置、before/after审计、普通持久receipt |
| GET /results/<request_key> | 原请求键 | 独立文件结果或普通config receipt；未找到不能认定未执行 |
| GET /jobs/<job_ref> | 外置维护引用 | 不读取被替换数据库，查询原外置结果 |

注册函数：`web.routes.workbench.system_routes.register_system_maintenance_routes(bp)`，主代理调用一次。
未改现有 `system_overview`。

## 主代理需要判定的 pending/recovery

1. 显式配置 `WORKBENCH_SYSTEM_JOURNAL_DIR` 为当前实例专属绝对目录，位于被恢复DB之外、备份目录之外，不参与普通操作日志/备份清理。不配置时禁用文件动作，配置与日志仍可用。
2. 启动前置调用 `core.services.workbench.system_journal.assert_system_maintenance_ready(database_path, journal_dir)`，须早于打开/迁移/普通写入/自动维护/退出备份。不确定、损坏、跨实例journal应阻止使用，不自动恢复或重新执行。
3. 请求侧隔离须覆盖已有旧页和所有写入口，以及已在途写请求；状态查询须在维护状态仍可达，不能依赖被替换的数据库成功打开。
4. 只有上述链路已接通并验证，才安装 `app.extensions['workbench_system_restore_guard']` 可调用钩子。该钩子每次恢复前须确认全局隔离可用并返回精确 `True`；它不是替代隔离的开关。
5. 恢复保持既有 `run_backup_restore`、`maintenance_window`、保护副本、源完整性校验、ensure_schema、自动回滚。专属子类只观察关键阶段/记录保护副本指纹并保留失败代码，不另写恢复算法，不从flash文本推断结果。
6. 外置journal写入意图与阶段采用专属临时文件、flush/fsync、os.replace；POSIX另fsync目录。Win7提供文件fsync+同目录replace，不宣称已实测断电持久性。
7. `rollback_failed/recovery_required` 都不是可继续写入的终结状态。重复POST遇到未终結记录只返回原状态，绝不重执行。
8. 浏览器独立 pending key 拟为 `aps_workbench_system_pending_v1`；只存原请求标识和动作摘要，不存密钥、绝对路径、write_token。断线/重载只查原请求；无结果不得换键重做。由主代理确认命名，与resources存储不混用。

## 前端落盘顺序（待主代理同步）

放在 `SystemLive.jsx` 之前，均来自 `frontend/workbench/app/`：

1. SystemMaintenanceAPI.js
2. SystemMaintenanceControls.jsx
3. SystemMaintenanceRecords.jsx
4. SystemMaintenanceConfig.jsx
5. SystemMaintenanceWorkspace.jsx

延续现有 sm-* 样式、深浅主题与组件，不改全局CSS。整行可进入详情；恢复/单删用同基调确认窗。
日志状态只标已记录，不用级别或字符串推导业务成功；来源、缺失、读取失败与截断分别显示。
不可执行动作显示后端具体原因，不伪报成功。主题、分页、紧凑度不写SystemConfig。

## 验证边界

- 专属fixture使用新的TemporaryDirectory/tmp_path，SQLite连接守卫拒绝任何目录外文件；不启动正常app、不读取真实DB/预览DB。
- 最终44项专属维护测试及5项既有恢复合同回归通过，共49项，1.87秒；补journal损坏/写失败、留痕失败、原库字节保留证明与复制/核验/回滚失败分类。
- 专属Ruff与17文件Python3.8语法扫描通过，Pyright零错误。未更新任何依赖。
- 全局挂载、最终build、所有入口恢复隔离、启动恢复检查均未由V实施，不宣称全页正式发布完成。
- 当前dirty工作区，只提供局部验证，不是clean-worktree proof。
- UI未新增、SystemLive未改、无新功能截图。等待主代理构建清单落盘同步后继续，不以旧页面截图替代新功能证据。
- 未跑全仓质量门禁：它会更新不属于V的全局门禁资料，且目前多代理并行dirty并由主代理整合build；本批仅执行上述明确pathspec的局部验证。

执行命令：

```text
.venv/bin/python -m pytest -q tests/workbench/test_system_maintenance_api.py tests/workbench/test_system_maintenance_restore.py tests/workbench/test_system_maintenance_failures.py tests/migration_db/test_restore_pre_snapshot_failure_contract.py tests/migration_db/test_restore_integrity_check_contract.py -p no:cacheprovider
.venv/bin/python -m ruff check core/models/workbench_system.py core/services/workbench/system_*.py web/routes/workbench/system_*.py tests/workbench/test_system_maintenance*.py
.venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/models/workbench_system.py core/services/workbench/system_*.py web/routes/workbench/system_*.py tests/workbench/test_system_maintenance*.py
.venv/bin/python -m pyright core/models/workbench_system.py core/services/workbench/system_config.py core/services/workbench/system_journal.py core/services/workbench/system_reads.py core/services/workbench/system_restore.py core/services/workbench/system_files.py core/services/workbench/system_exports.py core/services/workbench/system_redaction.py web/routes/workbench/system_actions.py web/routes/workbench/system_context.py web/routes/workbench/system_reads.py web/routes/workbench/system_routes.py web/routes/workbench/system_exports.py
```

## 当前文件清单

- core/models/workbench_system.py
- core/services/workbench/system_config.py
- core/services/workbench/system_exports.py
- core/services/workbench/system_files.py
- core/services/workbench/system_journal.py
- core/services/workbench/system_reads.py
- core/services/workbench/system_redaction.py
- core/services/workbench/system_restore.py
- web/routes/workbench/system_actions.py
- web/routes/workbench/system_context.py
- web/routes/workbench/system_exports.py
- web/routes/workbench/system_reads.py
- web/routes/workbench/system_routes.py
- tests/workbench/test_system_maintenance_api.py
- tests/workbench/test_system_maintenance_failures.py
- tests/workbench/test_system_maintenance_restore.py
- tests/workbench/test_system_maintenance_support.py
- 本feature的design/checklist。

定位工具：运行 `python3 -m tools.symbol_locator callees run_backup_restore` 和 `callers update_backup_settings`。
第一次并行运行触发静态图缓存自动刷新且读到了半写JSON，随后串行重跑成功；不把静态图的ambiguous边当精确调用链证明。未手工改缓存或重置已有工作区。
