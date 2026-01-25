# Win7 离线交付与打包说明（V1）

> 目标：把“打包机（Win7）→ 生成 onedir 交付目录 → 冷启动验收 → 交付给目标机”的流程固化，降低现场失败概率。

## 1) 前置条件（打包机）

- **Windows 7 x64**（建议 Win7 SP1）
- **Python 3.8.x x64**
- **PyInstaller 4.10**（必须 4.x，不要用 5.x/6.x）
- **离线依赖准备**（无网环境）：
  - 推荐方式：提前在有网环境下载 wheel 到本地，再拷贝到打包机安装
  - 或者：使用已经安装好依赖的 Python 环境直接打包

## 2) 打包（onedir）

在仓库根目录执行：

```bat
build_win7_onedir.bat
```

成功后产物在：

- `dist/排产系统/排产系统.exe`
- `dist/排产系统/templates/`
- `dist/排产系统/static/`
- `dist/排产系统/templates_excel/`
- `dist/排产系统/plugins/`（可选：自研插件投放目录）
- `dist/排产系统/vendor/`（可选：离线依赖投放目录，会在启动时注入 sys.path）
- `dist/排产系统/schema.sql`

> 说明：`db/ logs/ backups/ templates_excel/` 等目录会在首次运行时自动创建（见 `app.py` 的目录 ensure 逻辑）。

## 3) 冷启动验收（强烈建议）

在打包机执行（会启动 exe 并自动探活关键页面）：

```bat
python validate_dist_exe.py "dist\排产系统\排产系统.exe"
```

若失败，请优先查看：

- `dist/排产系统/logs/aps_error.log`

## 4) 交付目录结构（目标机）

将整个 `dist/排产系统/` 目录复制到目标机即可运行（目标机无需 Python、无需联网）。

目标机运行后会生成（或更新）：

- `db/aps.db`
- `logs/aps.log`、`logs/aps_error.log`
- `backups/*`（退出自动备份、手动备份、恢复前备份等）

## 5) 建议的交付验收清单（人工）

- [ ] 双击 `排产系统.exe` 可启动
- [ ] 浏览器可打开首页 `/`
- [ ] 关键页面可访问：人员/设备/工艺/排产/系统管理
- [ ] 报表中心可访问：超期/利用率/停机影响，且可导出 Excel
- [ ] 导入一份 Excel → 预览 → 确认导入（写入留痕）
- [ ] 执行一次排产，查看甘特图与周计划导出
- [ ] 关闭程序后 `backups/` 出现 `*_auto.db`

