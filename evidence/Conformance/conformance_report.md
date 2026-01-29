# 实现一致性对标报告（实现 vs 开发文档规划）

- 生成时间：2026-01-30 00:31:42
- 仓库根目录：`D:\Github\APS Test`

## 总结
- 检查项总数：9
- BLOCKER：0
- MAJOR：1
- 结论：不通过（存在差异项）

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
  - `templates_excel/` 文件数：10
  - 缺失模板：无

### 退出自动备份（atexit.register + suffix=auto；不启后台定时线程）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - `app.py` 关键片段（退出自动备份）：
```
  -         try:
  -             backup_manager.backup(suffix="auto")
  -         except Exception as e:
  -             # 退出阶段尽量不抛错，记录到错误日志即可
  -             app.logger.error(f"退出自动备份失败：{e}")
  - 
  -     atexit.register(_backup_on_exit)
  - 
  -     app.logger.info("应用启动完成。")
  -     return app
  - 
  - 
  - app = create_app()
  - 
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
- **结果**：不通过
- **严重性**：MAJOR
- **说明**：排产留痕/事务原子性实现与开发文档要求不一致。
- **证据**：
  - `core/services/scheduler/schedule_service.py` 排产留痕片段：
  - 未找到 action=schedule/simulate 留痕写入逻辑

### 关键路由存在性（对齐系统速查表核心链路）
- **结果**：通过
- **严重性**：INFO
- **证据**：
  - url_map 路由总数：162
  - 关键路由缺失：无

## 差异项清单（便于验收沟通/修复排期）
- **[MAJOR] 排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）**：排产留痕/事务原子性实现与开发文档要求不一致。

