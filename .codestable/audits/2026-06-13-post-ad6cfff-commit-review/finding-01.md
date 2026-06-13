---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "security-01"
nature: security
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 01：运行日志页面仍可能读取软链接日志

## 速答

诊断包下载已经拒绝软链接日志，但运行日志页面仍直接读取固定文件名对应的路径。如果日志目录里有白名单名字的软链接，页面查看日志这条链路仍可能读到不该读的文件。

## 关键证据

- `web/routes/system_runtime_logs.py:47` — 页面入口直接 `os.path.join(LOG_DIR, selected_file)` 得到日志路径。
- `web/routes/system_runtime_logs.py:51` — 页面随后调用 `read_log_entries_tail(log_path)` 读取内容，中间没有判断 `os.path.islink(log_path)`。
- `core/services/system/runtime_log_reader.py:197` — 诊断包链路已经有 `os.path.islink(path)` 拦截，说明项目已经承认“白名单文件名 + 软链接”是需要挡住的风险。
- `tests/web_pages/test_diagnostic_package_security.py:77` — 测试只覆盖诊断包下载链路播种 symlink，没有覆盖页面查看链路。

## 影响

大白话说，下载诊断包这扇门已经补锁了，但“网页上直接看日志”这扇门还没补同样的锁。只要运行环境允许在日志目录里放软链接，就有机会让页面读取到白名单名字背后的其他文件。

另一个测试风险是：当前 symlink 测试直接调用 `os.symlink`。Win7/Windows 环境可能没有创建软链接权限，测试可能因为系统权限失败，而不是因为产品逻辑失败。

## 修复方向

把诊断包链路的软链接拦截规则复用到页面读取链路：页面选定日志文件后，先确认目标不是 symlink、确实是普通文件，再允许 `read_log_entries_tail`。同时给页面链路补测试，并让 symlink 测试在不支持 symlink 的环境里明确 skip。

## 建议动作

建议走 `cs-issue`，因为这是一个明确的安全边界遗漏，不是重构。
