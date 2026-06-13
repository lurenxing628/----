---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "maintainability-11"
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-issue
status: resolved
---

# Finding 11：备份提示和前台压测脚本的失败边界仍不够清楚

## 速答

`505ea051` 补了备份失败提示和前台压测入口，是有价值的改动。但两个边界还不够清楚：手动备份提示说“完整性检查或写入异常”，实际只捕获 `RuntimeError`；压测脚本复制模板时会直接删除目标目录里的 `templates_excel`。

## 关键证据

- `web/routes/system_backup.py:113` — 手动备份只捕获 `RuntimeError`。
- `web/routes/system_backup.py:117` — 日志文案写的是“完整性检查或写入异常”。
- `web/routes/system_backup.py:118` — 用户提示也写“备份完整性检查失败或备份写入异常”。
- `core/infrastructure/backup.py:328` — 备份过程中会进行 sqlite connect / backup 文件操作，这类错误不一定都是 `RuntimeError`。
- `tests/_scripts_e2e/run_browser_extreme_stress_case.py:70` — 压测脚本复制 Excel 模板。
- `tests/_scripts_e2e/run_browser_extreme_stress_case.py:72` — 如果目标 `template_dir` 已存在，直接 `shutil.rmtree(template_dir)`。

## 影响

备份入口这里，用户提示比实际捕获范围更宽。如果发生的是真正文件系统/数据库异常，可能仍走全局 500，用户看不到这条中文提示。

压测脚本这里，如果调用者把 `--workdir` 指到仓库根目录或其他重要目录，脚本会删除其中的 `templates_excel` 再复制。虽然这是测试脚本，不是生产入口，但它属于容易误用的本地工具。

## 修复方向

备份入口要么缩窄文案，只说捕获到的完整性检查类失败；要么明确捕获备份写入阶段的预期异常，并转成中文提示。压测脚本建议增加 workdir 安全检查，或只允许空的临时目录，危险目录需要显式 `--force`。

## 建议动作

建议走 `cs-issue`，因为这是两个明确失败边界，修复范围都可以很小。
