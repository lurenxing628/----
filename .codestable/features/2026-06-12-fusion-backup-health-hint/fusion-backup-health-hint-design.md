---
doc_type: feature-design
feature: 2026-06-12-fusion-backup-health-hint
requirement:
roadmap: aps-frontend-fusion
roadmap_item: fusion-backup-health-hint
status: approved
summary: 备份健康提示——首页顶部纯只读扫描 backups/ 目录（不实例化 BackupManager）取 aps_backup_*.db 最大 mtime，超 7 天琥珀 notice「已 N 天未备份」（阈值常量单点）；读取失败明示不静默（4.11）
tags: [frontend, dashboard, backup, module-n]
---

# fusion-backup-health-hint design

## 0. 术语约定

| 术语 | 定义 | 防冲突结论 |
|---|---|---|
| 最近备份时间 | backups/ 目录下 aps_backup_*.db（前缀+后缀双过滤）的最大 mtime | 与「自动备份开关/退出备份」机制正交——本 feature 纯只读扫描不碰备份执行，也不实例化 BackupManager（其 __init__ 有建目录副作用） |
| 健康提示 | 首页顶部琥珀 notice（ui.notice tone=warning） | 与 data_gap 同为 warning 级提醒但形态不同（data_gap 走 workbench 待办卡，本提示是新增的顶部 notice） |

## 1. 决策与约束

**需求摘要**（roadmap 第 32 条，模块 N，契约 4.11，2026-06-11 用户拍板）：现场常忘备份——首页给「已 N 天未备份」琥珀提示；读取失败明示。半天级小件。

**复杂度档位**：Web 应用默认档位，无偏离。

**关键决策**：

1. **阈值常量单点**：新 viewmodel `web/viewmodels/dashboard_backup_health.py` 公开 `BACKUP_STALE_DAYS = 7`（模块 docstring 注明唯一真相源；与 BackupManager keep_days 的 7 是不同语义——那是清理保留期，这是提醒阈值，刻意不共享常量但值相同，注释言明）。
2. **读取走 viewmodel 自带纯只读扫描，不实例化 BackupManager**（Codex 审核两阻塞拍板）：① `BackupManager.__init__` 有 `os.makedirs(backup_dir)` 副作用——首页访问创建目录违反 4.11 只读契约，且把「目录不存在」态偷改成「空目录」态；② `list_backups()` 按文件名倒序取首条 ≠ 最大 mtime（复制/touch/人工搬运后文件名序失真）。viewmodel 提供 `read_latest_backup_time(backup_dir) -> Optional[datetime]`：直接 `os.listdir`，仅 **listdir 抛 `FileNotFoundError`** 归「从未备份」态（目录不存在与空目录对用户语义相同）；`NotADirectoryError`（路径被文件挡住=配置/文件系统错误）及**其余 OSError 一律穿透**到失败态；单文件 stat 失败同样穿透（不跳过不洗白）——刻意不用 `os.path.isdir` 先判（py38 genericpath.isdir 内部吞 OSError 返回 False，会把权限失败伪装成「从未备份」，撞 4.11 失败态诚实；Codex 复审阻塞拍板）；扫 `aps_backup_` 前缀且 `.db` 后缀文件（比 list_backups 的纯前缀判断多一道 .db 过滤，aps_backup_fake.txt 不算备份）取 **max(mtime)**。备份类型语义拍板：manual/auto/exit/before_restore/before_migrate 全部算「备份」重置计时——它们都是可恢复的库快照，用户语义上「有最近的可恢复点」即健康；不区分主动/被动。**从未备份也提示**：「尚未发现任何备份」同琥珀级。
3. **失败明示不静默（4.11 红线）**：扫描抛 OSError → notice 文案「备份状态读取失败：{原因}」（tone=warning），logger.error 留痕；不吞错不假装健康。
4. **viewmodel 分两层：IO 读取层 + 纯决策层**：`read_latest_backup_time(backup_dir)`（IO 层，OSError 穿透）+ `build_backup_health_hint(latest, read_error, now) -> Optional[Dict]`（纯决策层）——健康（≤7 天）返回 None（首页零噪音），超期/从未/失败返回 {"title", "body", "tone"}；路由只做 try/except 接线。
5. **挂载首页顶部**：dashboard.html workbench section 之前插 `{% if backup_health_hint %}{{ ui.notice(...) }}{% endif %}`——ui.notice 宏现成（data_gap 是 workbench 待办卡，形态不同，不混用）；点击引导文案含「去备份页」裸文本指引（不加链接按钮——notice 宏不带 action 槽，加链接归 dashboard-cockpit 重构时统一）。
6. **测试**：viewmodel 单测（健康 None/超期 N 天文案/从未备份/读取失败四态 + 阈值边界 7 天整 + aps_backup_fake.txt 不算备份）+ 页面契约测试（首页渲染含/不含提示）；不进 GUARD_TESTS（非安全红线；普通回归覆盖，失败态由本 feature 测试直接断言）。

**明确不做**：不加备份页跳转按钮（notice 宏无 action 槽，归 dashboard-cockpit）；不动 BackupManager/自动备份机制；不做提醒已读/驳回状态（无新表纪律，与 fusion-todo-ack-state 的范围区隔）；不做邮件/弹窗等主动通知。

## 2. 名词与编排

### 2.1 名词层

**现状**：BackupManager.list_backups()（backup.py:484——按文件名倒序非 mtime 序，且 __init__ 有 makedirs 副作用，故不用）；dashboard 路由已装配 workbench_summary；ui.notice 宏（ui_macros:108）；数据缺口提醒先例（dashboard_workbench_data_gap.py）。

**变化**：
- 新增 `web/viewmodels/dashboard_backup_health.py`（~60 行）：常量 + read_latest_backup_time 只读扫描函数 + build_backup_health_hint 四态决策函数。
- 修改 `web/routes/dashboard.py`：取清单（try/except OSError）→ build → render_template 传 backup_health_hint。
- 修改 `templates/dashboard.html`：顶部条件渲染 notice。
- 新增 `tests/web_pages/test_dashboard_backup_health.py`。

接口示例：

```python
# web/viewmodels/dashboard_backup_health.py
BACKUP_STALE_DAYS = 7  # 提醒阈值唯一真相源（与 BACKUP_KEEP_DAYS 清理语义无关，值巧合相同）

def read_latest_backup_time(backup_dir: str) -> Optional[datetime]:
    # 纯只读：os.listdir 直扫；仅 listdir 的 FileNotFoundError → None（从未备份）
    # NotADirectoryError/PermissionError 等其余 OSError 穿透，单文件 stat 失败同样穿透
    # （不用 isdir——py38 isdir 吞 OSError 会把权限失败伪装成从未备份）
    # 扫 aps_backup_*.db 取 max(mtime)；刻意不实例化 BackupManager（__init__ makedirs 副作用）

def build_backup_health_hint(
    *, latest: Optional[datetime], read_error: Optional[str], now: datetime
) -> Optional[Dict[str, str]]:
    # 失败 → {"title": "备份状态读取失败", "body": "...{原因}...", "tone": "warning"}
    # latest None → {"title": "尚未发现任何备份", ...}
    # 日历日差 > 7 → {"title": "已 N 天未备份", ...}
    # 健康 → None
```

### 2.2 编排层

```mermaid
flowchart LR
  A[dashboard 路由] --> B[read_latest_backup_time 纯只读扫描<br/>try/except OSError]
  B --> C[build_backup_health_hint 纯函数四态]
  C --> D[dashboard.html 顶部 ui.notice<br/>健康时零渲染]
```

**流程级约束**：
- mtime 直接来自 os.stat（不经 isoformat 字符串往返，少一道解析失败面）；仅 os.listdir 的 FileNotFoundError 归「从未备份」；NotADirectoryError 与单文件 stat 失败均按读取失败态处理（4.11）——不许大 except 包整函数把 stat 竞态洗成「从未备份」。
- 天数计算用日历日差（date 相减）而非 86400 秒整除——「昨天备份的」显示 1 天而非 0 天，符合用户直觉。
- 路由 try/except 只罩 read_latest_backup_time（IO），不罩 build_backup_health_hint（编程错误不得伪装成 IO 失败）。

### 2.3 挂载点清单

1. viewmodel：`web/viewmodels/dashboard_backup_health.py` — 新文件
2. 路由装配：`web/routes/dashboard.py` — 修改
3. 模板：`templates/dashboard.html` 顶部 — 修改
4. 测试：`tests/web_pages/test_dashboard_backup_health.py` — 新文件（不进 GUARD_TESTS）

### 2.4 推进策略

1. viewmodel + 单测四态 → 绿
2. 路由 + 模板 + 页面契约测试 → 浏览器目检超期/健康两态
3. required 快测 + daily gate → 绿

### 2.5 结构健康度与微重构

##### 评估
新增 2 文件（viewmodel ~60 行/测试 ~80 行）；dashboard.py +~10 行（当前 364 行）；零结构问题。

##### 结论：不做

## 3. 验收契约

关键场景：
1. 播种 8 天前 mtime 的 aps_backup_*.db → 首页顶部琥珀「已 8 天未备份」+ 去备份页指引。
2. 播种今天的备份 → 首页无提示；播种 8 天前的 .db + **今天的 aps_backup_fake.txt** → 仍提示「已 8 天未备份」（.txt 不得把状态洗成健康）。
2b. max(mtime) 反例钉死：文件名时间戳较新但 mtime 8 天前 + 文件名较旧但 mtime 今天 → 不提示（防实现偷偷退回按文件名取）。
3. 空备份目录/目录不存在 → 「尚未发现任何备份」；**目录不存在的场景断言不创建目录**（只读实证）。
4. monkeypatch read_latest_backup_time 抛 OSError → 「备份状态读取失败」+ logger.error 留痕；页面 200。单测层：PermissionError/NotADirectoryError 从 read_latest_backup_time 穿透不归 None（仅 listdir 的 FileNotFoundError 归 None）。
5. 阈值边界：恰好 7 天 → 不提示；8 天 → 提示（单测钉死 > 语义）。
6. BACKUP_STALE_DAYS 唯一定义点（grep web/ 仅 viewmodel 一处）。
7. dashboard 既有测试零回归；required 快测绿。

明确不做的反向核对：
- BackupManager/system_backup.py 零 diff（注意：并行会话正在改这两文件，工作区已有 M 态——验收用 **staged/commit diff** 单独核对本 feature 改动集不含这两文件，不能只看 git status）。
- 无新表/无已读状态持久化；无备份页跳转 url_for（裸文本指引）。

## 4. 与项目级架构文档的关系

验收时归并：ARCHITECTURE.md 首页值班台条目补一句备份健康提示；roadmap 第 32 条回写 done。模块 N 还剩 30（临期预警）/31（周派工单）/33（方案 diff）。
