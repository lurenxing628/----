---
doc_type: feature-ff-note
feature: win7-portable-release
date: 2026-09-14
requirement: ""
tags: [win7, portable, powershell51, packaging]
---

## 做了什么
默认交付改为内含 Chrome109 的绿色便携 ZIP；解压或整目录复制后使用启动器，运行数据固定在 `user-data/`，不读取旧安装的数据路径和浏览器配置。原安装器保留显式维护入口，旧数据通过备份/恢复迁移。

## 改了哪些
- `web/bootstrap/launcher_paths.py`、`factory.py`、`assets/启动_排产系统_Chrome.bat`：便携标记、数据库/日志/备份/模板/profile 同目录，以及读取、停机与锁路径统一。
- `build_win7_portable.bat`、`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`scripts/portable_release.py`、`validate_dist_exe.py`：默认 ZIP、冷启动和浏览器验收、拒绝夹带运行数据、ZIP 完整性与 SHA-256。
- `.gitattributes`、随包说明及交付文档：PowerShell 5.1 的 ASCII 脚本、UTF-8 输出、参数引号、LF 合同、中文 TXT BOM 和解压办法；依据微软与 Git 官方文档。
- `开发文档/技术债务治理台账.md` 仅更新 16 项已有条目的 `line_start/line_end`；已逐字段确认状态、身份、风险和测试债务上限均未变。

## 怎么验证的
- Python 3.8.10 定向回归：153 passed、1 Windows-only skipped；完整门禁启动链专项另有 114 passed。新增便携用例在全量串行分片中为 24 passed、1 skipped。
- `git -c core.autocrlf=true check-attr text eol` 确认三个启动文件均为 `text: set / eol: lf`；最终 `git diff --check` 通过。
- 真实 Python 3.8 子进程在中文＋空格目录中通过空库启动、首页和健康检查 HTTP 200、旧环境路径隔离、从便携根目录停止及运行锁清理。该验证没有运行 Windows EXE 或 Chrome109。
- 完整门禁以 `--allow-dirty-worktree --long-gate-cache` 执行，前 17 步通过，第 18 步失败；长时间并行分片已主动中止，不能称全量执行完成或 clean proof。结果见 `evidence/QualityGate/quality_gate_manifest.json` 和第 18 步日志。
- 当时收集 9 项失败，其中 6 项在原始 HEAD `84d717f6729159177ea2cf18bb43016896a56dab` 的干净临时检出中同样复现（6 failed、1 passed）：1 项 UI 几何用例与 5 项后台任务用例；后者旧 `compute` 测试桩不接受 `on_progress`。其余 3 项为 `test_final_execution_report_reentry` 的 reports/review 参数及 `test_final_foundation_navigation::test_navigation_scope_and_scroll_contract`。临时检出已移除，对照日志保留在 `/tmp/aps-portable-baseline-comparison-20260914.log`。
- 上述九项已在同日后续任务中修复并全部定点通过，另有三个直接关联契约用例通过，见 `.codestable/issues/2026-09-14-nine-test-failures/nine-test-failures-fix-note.md`。按用户明确要求不重跑完整门禁，历史门禁失败记录不改写为通过。
- 本机为 macOS，未生成 Windows 便携成品，也未签发 PowerShell 5.1 / Win7 真机通过；须在目标打包机运行 `build_win7_portable.bat` 完成真实构建和现场验收。便携版与九项测试修复一同提交交付。
