---
doc_type: issue-fix
issue: 2026-09-22-win7-portable-handoff
path: fast-track
fix_date: 2026-09-22
tags: [win7, portable, packaging, offline]
---

# Win7 绿色便携版验证材料补齐

## 根因与范围

基线为 `ab66d6b032773509489212d616c892423a144c72`，与当时 GitHub main 一致。`build_win7_portable.bat` 调用的 PowerShell 脚本只存在本机，被 `.git/info/exclude` 的 `/.limcode/` 隐藏；Git 归档内缺失该文件，相关测试出现 3 个 FileNotFoundError。交付文档同时引用开发依赖，漏装 PyInstaller，且没有完整离线材料及逐项现场验收表。

本轮只补交付工具、依赖清单、相关回归和说明；未修改产品业务逻辑、生产数据、系统配置或 Git 全局忽略规则。

## 修复

- 将 `aps-package-win7` 的脚本和配套技能说明按明确路径纳入 Git，增加跟踪状态回归，防止“本机存在”冒充“仓库已交付”。
- `requirements-win7-build.txt` 锁定 22 个 wheel 的版本及哈希，隔离运行／打包依赖与开发检查工具；`packaging/win7/offline-manifest.json` 保存全部 24 个外部文件的来源、大小和 SHA-256。
- `scripts/prepare_win7_offline.py` 提供下载与纯离线核验，校验失败不出可用文件、不静默替换已有文件；实际材料保存在忽略的 `offline/win7/`。
- `setup_win7_build.bat` 创建专用构建环境；构建入口调用 `scripts/check_win7_build.py`，在删除 build/dist 前核对 Win7 SP1、Python 3.8 x64、所有锁定依赖及 pip check。
- 便携 ZIP 强制附带 BOM 编码的 `WIN7_ACCEPTANCE.txt`，覆盖启动、业务流程、恢复、搬迁和账户占用；同步 README、交付说明及历史安装版说明。

## 已执行验证

- 下载并校验 24 个真实文件，共 153196475 字节；来源为 Python 官方、PyPI 和 ungoogled-chromium 发布仓库。Python 安装器另与官方发布页 MD5 对照，浏览器 SHA-256 与项目发布清单对照。
- 检查 22 个 wheel 的 ZIP CRC、名称、版本、Requires-Python；按 Windows / CPython 3.8.10 计算的 17 条生效依赖全部满足，含 pefile、pywin32-ctypes、colorama。NetworkX 与仓库附带 wheel 完全一致。
- Chrome ZIP CRC 正常；实际 chrome.exe 及 PyInstaller Windows bootloader 均为 AMD64 PE；浏览器 chrome.dll、icudtl.dat、resources.pak 和中英文 locale 完整。
- 9 个直接相关测试文件：109 passed、1 skipped。跳过的是本机没有 Windows PowerShell 5.1 的真实解析测试。
- 仅导出暂存 Git 树复验相同测试：108 passed、2 skipped；第二个跳过因源码归档没有 Git 索引。归档确实包含打包脚本、依赖清单、准备工具和验收表。
- 改动 Python 的 Ruff、diff 空白检查、技能 frontmatter／本地链接及 Windows 脚本 ASCII／LF／BOM 合同通过。
- 在 macOS 实际运行构建预检，明确拒绝非 Win7 主机及不匹配依赖，未启动构建。
- 日常门禁 `scripts/run_daily_quality_gate.py` 返回 0：收集 15851 项，全仓 Ruff 通过，并行 10905 passed、串行 959 passed、重点冒烟 7 passed。该入口不是最终完整门禁或 clean proof。

## 现场仍需完成

Win7 SP1 x64 和 PowerShell 5.1 必须已就绪；系统更新不由便携包代装。将源码与离线材料一同带到现场，按 DELIVERY_WIN7.md 准备独立构建环境、生成 EXE／ZIP，再填写随包验收表。

本轮没有 Windows EXE、PowerShell 5.1 执行或 Win7 浏览器真机通过证据；没有执行最终完整门禁，不声明 full-test-debt 或 clean-worktree proof。大型外部材料不进入源码 Git，也未发布 GitHub Release。
