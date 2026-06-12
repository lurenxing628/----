# fusion-backup-health-hint 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-backup-health-hint-design.md（approved，Codex 设计三轮 BLOCK→BLOCK→PASS-WITH-SUGGESTIONS + 实现一轮零阻塞 PASS-WITH-SUGGESTIONS，建议全采纳）

## 1. 接口契约核对

- [x] 与 design 2.1 一致：`BACKUP_STALE_DAYS = 7`（viewmodel 唯一定义点，grep web/ 仅一处）+ `read_latest_backup_time(backup_dir) -> Optional[datetime]`（IO 读取层）+ `build_backup_health_hint(latest, read_error, now) -> Optional[Dict]`（纯决策层）。
- [x] 路由只做 try/except 接线（OSError 只罩 read_latest_backup_time，build 在 try 外——编程错误不伪装 IO 失败）；模板消费 `backup_health_hint` dict 渲染 ui.notice。
- [x] 实现期偏差：零（设计三轮已把 isdir 吞错/max(mtime)/异常分型提前钉死）。实现审核 3 建议追加采纳：S_ISREG 只认普通文件（误放同名目录不参与计时）+ 健康态否定断言收窄 + checklist 状态同步。

## 2. 行为与决策核对

- [x] 决策 1 阈值常量单点：BACKUP_STALE_DAYS=7 仅 viewmodel 一处，docstring 注明与 keep_days 语义无关。
- [x] 决策 2 纯只读不实例化 BackupManager：os.listdir 直扫；仅 listdir 的 FileNotFoundError 归「从未备份」；NotADirectoryError/PermissionError/单文件 stat 失败穿透（py38 isdir 吞 OSError 的坑已绕开）；aps_backup_ 前缀+.db 后缀双过滤 + S_ISREG；max(mtime) 口径；全部备份类型（manual/auto/exit/before_restore/before_migrate）重置计时。
- [x] 决策 3 失败明示：「备份状态读取失败：{原因}」+ logger.error 留痕（测试钉死）。
- [x] 决策 4 两层拆分：IO 层 OSError 穿透 + 决策层四态（失败/从未/超期/健康 None）。
- [x] 决策 5 首页顶部挂载：dashboard.html workbench section 之前条件渲染 ui.notice（role='status'）；裸文本「系统管理 → 数据备份」指引，无链接按钮。
- [x] 决策 6 测试：15 条（IO 6 + 决策 5 + 页面 4），不进 GUARD_TESTS。
- [x] 明确不做反向核对：staged diff 不含 backup.py/system_backup.py（并行 WIP 隔离实证）；无新表/无已读状态/无 url_for 按钮。
- [x] 挂载点 grep 反向核对：backup_health_hint 全仓仅 4 文件（viewmodel/路由/模板/测试）；拔除沙盘：删 viewmodel+测试、回退路由 import+接线+模板 4 行即完全退出。

## 3. 验收场景核对

- [x] S1 播种 8 天前 .db → 首页「已 8 天未备份」+「数据备份」指引（页面测试 + 浏览器截图目检亮/暗双主题）。
- [x] S2 今天的备份 → 无提示；8 天前 .db + 今天 aps_backup_fake.txt + 同名目录 → 仍 8 天态（.txt/目录不洗健康）。
- [x] S2b max(mtime) 反例：文件名新 mtime 旧 / 文件名旧 mtime 今 → 取 mtime 最大者（防退回文件名序）。
- [x] S3 空目录/目录不存在 → 「尚未发现任何备份」；目录不存在断言 not missing.exists()（只读实证不创建）。
- [x] S4 monkeypatch 抛 OSError → 「备份状态读取失败」+ logger.error + 页面 200；单测层 PermissionError/NotADirectoryError 穿透不归 None。
- [x] S5 阈值边界：恰好 7 天 None；第 8 天提示；日历日差（昨天 23:00 → 1 天，健康）。
- [x] S6 BACKUP_STALE_DAYS 唯一定义点 grep 实证。
- [x] S7 零回归：web_pages 全目录 373 passed；daily gate passed（并行 WIP stash 隔离后跑，跑完立即 pop）。
- [x] 浏览器目检：/tmp/backup_hint_shots/ 超期态（顶部琥珀 notice 可见）与健康态（零渲染）双截图核过。

## 4. 术语一致性

- 「从未备份/读取失败/超期/健康」四态口径 design、viewmodel docstring、测试模块 docstring 同口径；「最近备份时间 = max(mtime)」全文一致。

## 5. 架构归并

- [x] ARCHITECTURE.md 首页计划员值班台条目补备份健康提示一句（纯只读扫描/阈值/失败明示/健康零渲染）。

## 6. requirement 回写

design frontmatter `requirement` 为空；roadmap 第 32 条即需求载体（2026-06-11 用户拍板四件之一）。结论：**无独立 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-backup-health-hint `status: done` + feature 字段回填。
- [x] 主文档第 32 条标 ✅ done（含三轮设计审核要点留证）。
- [x] 模块 N 剩余：30（临期预警）/31（周派工单）/33（方案 diff）。

## 8. attention.md 候选盘点

候选 1：「py38 的 os.path.isdir/exists 系内部吞 OSError 返回 False——需要区分『不存在』与『读取失败』的场景必须直接 listdir/stat 让异常穿透，不能用 isdir 先判」。
（仅登记，落不落由用户定。）

## 9. 遗留

- notice 宏无 action 槽，备份页跳转按钮归 fusion-dashboard-cockpit（#19）统一。
- 提醒已读/驳回状态刻意不做（无新表纪律）。
