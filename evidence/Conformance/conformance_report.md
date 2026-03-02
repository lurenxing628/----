# 实现一致性对标报告（实现 vs 开发文档规划 + 架构合规）

- 生成时间：2026-03-02 11:10:42
- 仓库根目录：`D:\Github\APS Test`

## 总结
- 检查项总数：13
- BLOCKER：0
- MAJOR：0
- 结论：通过

## 逐项对标结果
### 依赖约束（openpyxl-only；不引入 pandas/numpy/schedule）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `requirements.txt` 存在：是
  - 内容摘要：
```
  - # requirements.txt (Python 3.8, V1: openpyxl-only)
  - #
  - # Web framework
  - Flask==2.3.3
  - Werkzeug==2.3.7
  - #
  - # Excel (V1: openpyxl-only)
  - openpyxl==3.0.10
  - #
  - # Date utilities
  - python-dateutil==2.8.2
  - #
  - # Packaging (dev/build machine only; end-user machine does not need Python)
  - # PyInstaller==4.10  # do not use 5.x/6.x
```

### V1 边界：不实现并发锁/资源锁（无 locking.py / 无 ResourceLocks 表）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `core/infrastructure/locking.py` 存在：否
  - `schema.sql` 包含 ResourceLocks 建表语句：否

### 甘特图资源本地化（Frappe Gantt 0.6.1 静态资源在仓库内）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `static/js/frappe-gantt.min.js` 存在：是
  - `static/css/frappe-gantt.css` 存在：是

### 交付模板（templates_excel/ 固定模板文件齐全）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `templates_excel/` 文件数：12
  - 缺失模板：无

### 退出自动备份（atexit.register + suffix=auto；不启后台定时线程）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `app.py` 关键片段（退出自动备份）：
```
  -                 # 退出阶段尽量不抛错，记录到错误日志即可
  -                 try:
  -                     bm.logger.error(f"退出自动备份失败：{e}")
  -                 except Exception:
  -                     pass
  - 
  -         atexit.register(_backup_on_exit)
  -         _EXIT_BACKUP_REGISTERED = True
  - 
  -     app.logger.info("应用启动完成。")
  -     return app
  - 
  - 
  - def create_app() -> Flask:
```

### 排产策略默认值（priority_first；权重 0.4/0.5/0.1）对齐开发文档
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `core/services/scheduler/config_service.py` 默认值片段：
```
  -     DEFAULT_SORT_STRATEGY = "priority_first"
  -     DEFAULT_PRIORITY_WEIGHT = 0.4
  -     DEFAULT_DUE_WEIGHT = 0.5
  -     DEFAULT_READY_WEIGHT = 0.1
  -     DEFAULT_ENFORCE_READY_DEFAULT = "no"  # yes/no：执行排产时默认是否启用“齐套约束”
  -     # 工作日历：假期默认效率（假期安排工作且效率未填时使用）
  -     DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY = 0.8
  - 
  -     # 派工方式（V1.2）：默认保持 V1 行为（batch_order）
  -     DEFAULT_DISPATCH_MODE = "batch_order"  # batch_order/sgs
  -     DEFAULT_DISPATCH_RULE = "slack"  # slack/cr/atc（仅 sgs 生效）
  -     DEFAULT_AUTO_ASSIGN_ENABLED = "no"  # yes/no
```

### Excel 导入留痕 detail 键名（英文固定键）对齐开发文档
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `core/services/common/excel_audit.py`（导入留痕键名）检查：
  - 期望键：['filename', 'mode', 'time_cost_ms', 'total_rows', 'new_count', 'update_count', 'skip_count', 'error_count', 'errors_sample']

### 排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `core/services/scheduler/schedule_persistence.py`（AST）排产留痕检查：
  - - persist_schedule(): line=187
  - - with *.transaction(): line=215
  - - history_repo.create(...): line=132 inside_tx=True
  - - op_logger.info(...): line=178 action_ifexp_ok=True

### 分层架构合规（route 不直接操作 DB，service 不导入 Flask request）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - 违反项数：0

### Schema 表文档化（schema.sql 所有表在开发文档/速查表中有记录）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - schema.sql 表数量：23
  - 未在文档中出现的表：无

### 文件行数约束（核心目录 Python 文件不超过 500 行）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - 超过 500 行的文件数：0

### 模板目录完整性（templates/ 子目录与模块对齐）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - 模板子目录缺失：无
  - 关键模板文件缺失：无

### 关键路由存在性（对齐系统速查表核心链路）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - url_map 路由总数：169
  - 关键路由缺失：无

## 差异项清单（便于验收沟通/修复排期）
- 无

