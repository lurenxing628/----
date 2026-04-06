# Win7 离线交付与直拷说明（V2）

> 目标：把“打包机（Win7）→ 生成 onedir 交付目录 → 冷启动验收 → 交付给目标机”的流程固化，同时与双包安装器口径保持一致。

## 0) 先明确三种交付口径

### A. 正式安装包交付（推荐）

- `APS_Main_Setup.exe`
- `APS_Chrome109_Runtime.exe`

说明：这是对外正式交付口径。详见 `installer/README_WIN7_INSTALLER.md`。

补充说明：

- `APS_Chrome109_Runtime.exe` 是 **APS 专用浏览器运行时**，目标是打开本机 APS 页面，不是完整桌面 Chrome 交付
- 正式运行时包仅保留 `locales\zh-CN.pak` 与 `locales\en-US.pak`
- 正式运行时包会移除 `chrome_proxy.exe`、`chrome_pwa_launcher.exe`、`notification_helper.exe`、`elevation_service.exe`
- 正式运行时包继续保留 `chrome_wer.dll` 与 `First Run`，兼顾崩溃诊断与首启稳定性
- 正式安装口径为：**管理员统一安装 + 共享数据目录 + 仅允许单活用户**
- 若目标机已存在旧 APS 安装或残留目录，`APS_Main_Setup.exe` / `APS_Legacy_Full_Setup.exe` 会在复制文件前弹出一次“强制清理”确认框
- 你确认后，安装器会删除旧主程序安装目录、`C:\ProgramData\APS\shared-data`、当前安装账户 `%LOCALAPPDATA%\APS\排产系统`
- 上述强制清理**不会**删除 `%LOCALAPPDATA%\APS\Chrome109Profile`，也不会删除独立 Chrome109 运行时目录；`APS_Chrome109_Runtime.exe` 仍保持独立安装/卸载边界
- 如果你取消确认，安装器会退出且不执行清理

安装后启动与排障：

- 主程序 `排产系统.exe` 只负责在后台启动本地服务；双击它时如果没有弹出窗口，不代表启动失败。
- 正常入口是开始菜单或桌面快捷方式 **“排产系统”**，其实际执行安装目录根下的 `启动_排产系统_Chrome.bat`。
- 若快捷方式只闪一下且未打开 Chrome，请先查看共享数据目录下的 `logs\launcher.log`
  - 默认安装时通常是：`C:\ProgramData\APS\shared-data\logs\launcher.log`
  - 如果共享数据目录被自定义，应到该共享目录下查看 `logs\launcher.log`
- `launcher.log` 会记录 `env_APS_CHROME_DIR`、`reg_HKLM_ChromeDir`、`reg_HKCU_APS_CHROME_DIR`、`chrome_source`、`chrome_exe`、`chrome_run_dir` 与 `chrome_cmd`
- 现场排障时，可把 `launcher.log` 里的 `chrome_cmd` 整行复制到 `cmd` 中执行，用于区分“bat 启动方式问题”和“Chrome 本体问题”
- 启动器的浏览器查找顺序是：`APS_CHROME_EXE` → 当前进程 `APS_CHROME_DIR` → 机器级注册表 `HKLM\SOFTWARE\APS\ChromeDir` → 兼容旧版注册表 `HKCU\Environment\APS_CHROME_DIR` → 默认 `C:\Program Files\APS\Chrome109` / `%LOCALAPPDATA%\APS\Chrome109` → legacy `tools\chrome109`
- 若另一账户正在使用共享数据目录，启动器会直接阻止第二个账户进入，而不是复用已有实例

### B. 最小直拷交付（支持）

- 只复制 `dist/排产系统/`
- 允许直接运行 `排产系统.exe`
- **不承诺** 内置浏览器运行时

### C. legacy 自包含直拷（仅内部/应急）

- `dist/排产系统/` 内额外带 `tools/chrome109/`
- 并放入 `启动_排产系统_Chrome.bat`
- 只用于现场应急或回退，不作为常规交付

## 1) 前置条件（打包机）

- **Windows 7 x64**（建议 Win7 SP1）
- **Python 3.8.x x64**
- **PyInstaller 4.10**（必须 4.x，不要用 5.x/6.x）
- **离线依赖准备**（无网环境）：
  - 推荐方式：提前在有网环境下载 wheel 到本地，再拷贝到打包机安装
  - 或者：使用已经安装好依赖的 Python 环境直接打包

## 2) 生成最小直拷目录（支持）

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
- `dist/排产系统/vendor/`（可选：离线依赖投放目录，会在启动时注入 `sys.path`）
- `dist/排产系统/schema.sql`

> 说明：`db/ logs/ backups/ templates_excel/` 等目录会在首次运行时自动创建（见 `app.py` / `config.py` 的运行目录逻辑）。

## 3) 冷启动验收（强烈建议）

在打包机执行：

```bat
python validate_dist_exe.py "dist\排产系统\排产系统.exe"
```

若失败，请优先查看：

- `dist/排产系统/logs/aps_error.log`

> 注意：`validate_dist_exe.py` 只验证主程序 `exe` 冷启动与 HTTP 页面，不覆盖快捷方式、批处理脚本、环境变量刷新时序或 Chrome 启动链路。

## 4) 最小直拷交付怎么用

将整个 `dist/排产系统/` 目录复制到目标机即可运行（目标机无需 Python、无需联网）。

目标机运行后会生成（或更新）：

- `db/aps.db`
- `logs/aps.log`、`logs/aps_error.log`
- `backups/*`（退出自动备份、手动备份、恢复前备份等）

### 浏览器怎么打开

最小直拷目录默认有两种方式：

1. 直接双击 `排产系统.exe` 启动程序，再手工打开浏览器访问实际 URL
2. 如果目标机已经安装过 `APS_Chrome109_Runtime.exe`，可额外把 `assets/启动_排产系统_Chrome.bat` 复制到 `dist` 目录旁边，使用启动器打开

> 注意：实际 URL 不一定是 `http://127.0.0.1:5000/`，应以 `logs/aps_host.txt` 与 `logs/aps_port.txt` 为准。
>
> 该运行时包只保证 `chrome.exe --app=http://{HOST}:{PORT}/` 这条 APS 启动链路，不承诺 PWA/系统通知/文件关联等完整桌面浏览器能力。

## 5) legacy 自包含直拷（仅内部/应急）

如果确实需要“目录一拷就能用启动器 + 浏览器运行时”的 self-contained 交付，只能走 legacy 路线：

```bat
build_win7_onedir.bat
stage_chrome109_to_dist.bat
copy /y "assets\启动_排产系统_Chrome.bat" "dist\排产系统\启动_排产系统_Chrome.bat"
```

此时 `dist/排产系统/` 内会包含：

- `排产系统.exe`
- `启动_排产系统_Chrome.bat`
- `tools/chrome109/`

> 该路线仅用于内部应急，不是常规交付方案。

## 6) 建议的直拷交付验收清单（人工）

- [ ] 双击 `排产系统.exe` 可启动
- [ ] `logs/aps_host.txt` / `logs/aps_port.txt` 已生成且可读
- [ ] 关键页面可访问：人员 / 设备 / 工艺 / 排产 / 系统管理
- [ ] 报表中心可访问：超期 / 利用率 / 停机影响，且可导出 Excel
- [ ] 导入一份 Excel → 预览 → 确认导入（写入留痕）
- [ ] 执行一次排产，查看甘特图与周计划导出
- [ ] 关闭程序后：若已启用“自动备份”，`backups/` 出现 `*_exit.db`；未启用时不生成退出备份

## 7) 与安装包口径的关系

- 正式对外交付优先使用双包安装器
- 双包安装器与最小直拷的运行边界不同：
  - 双包安装器：共享同一套数据，要求只允许单活用户
  - 最小直拷：目录自包含，仍按当前目录生成 `db/logs/backups`
- `dist/排产系统/` 的价值主要是：
  - 冷启动验收
  - 内部直拷调试
  - 现场应急回退
- 不要再默认把“直拷目录”理解成“天然自带浏览器运行时的自包含安装包”
- 不要把 `APS_Chrome109_Runtime.exe` 理解成完整 Chrome 安装器；它是为 APS 本地页面访问裁剪过的运行时

