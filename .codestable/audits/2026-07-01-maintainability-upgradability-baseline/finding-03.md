---
doc_type: audit-finding
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
finding_id: "maintainability-03"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 03：Win7 与离线交付链限制升级

## 速答

项目清楚知道自己要兼容 Win7 x64、Python 3.8 和离线交付，但当前持续集成不是 Win7 真机，离线依赖和双安装包链还需要更强的可复跑证明。

## 关键证据

- `pyproject.toml:3` — 项目声明 `requires-python = ">=3.8"`。
- `pyproject.toml:26-56` — Ruff 目标版本是 `py38`，并忽略 Python 3.8 不支持的新类型写法升级。
- `requirements.txt:4-14` — 运行依赖较少且锁版本，但 `PyInstaller==4.10` 只写在注释里。
- `requirements-dev.txt:3-11` — `pytest`、`pytest-cov`、`radon`、`pre-commit` 未全部锁死版本。
- `requirements-optimizer-lite-win7.txt:1-6` — 明确 `NetworkX 3.1` 是支持 Python 3.8 的最后一版。
- `.github/workflows/quality.yml:12-18` — CI 跑 `windows-latest`，不是 Win7。
- `.github/workflows/quality.yml:27-46` — CI 安装 Python 3.8 和 `networkx==3.1`，能证明 Python 3.8 口径，但不能证明 Win7 真机口径。
- `installer/README_WIN7_INSTALLER.md:10-16` — 正式打包机要求 Win7 x64、Python 3.8 x64、PyInstaller 4.10、完整离线依赖、Inno Setup 6。
- `installer/README_WIN7_INSTALLER.md:50-65` — 正式双包入口是 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`，它会串联主程序冷启动和浏览器运行时冒烟。
- `installer/README_WIN7_INSTALLER.md:256-269` — 验收建议明确要求至少在一台实际 Win7 机器上完成端到端冒烟。
- `DELIVERY_WIN7.md:60-72` — 离线安装依赖依靠 `C:\wheelhouse`。

## 影响

这会直接影响可升级性：

- 依赖升级不是“版本号改一下”，必须证明 Python 3.8 和 Win7 还能装、还能打包。
- CI 绿不等于 Win7 目标机绿。
- 离线 wheelhouse 不固化，打包机环境就可能变成口口相传。

## 修复方向

补一份“交付链证明清单”：

- 当前可用 wheelhouse 的来源、内容、hash。
- Win7 打包机的 Python、PyInstaller、Inno Setup 版本。
- `package_win7.ps1` 最新一次完整出包记录。
- `APS_Main_Setup.exe` 与 `APS_Chrome109_Runtime.exe` 的目标机冒烟记录。

## 建议动作

走 `cs-issue` 建一个“交付证明缺口”问题单，目标不是改业务代码，而是把可复跑证据补齐。
