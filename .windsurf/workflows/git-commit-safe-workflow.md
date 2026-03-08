---
description: 在 PowerShell 环境安全执行 Git 提交：提交前后门禁、UTF-8 提交信息、乱码诊断、amend/重写历史与 Co-authored-by 处理
---
当用户提到“提交失败 / 提交乱码 / 重写提交信息 / amend / 共同作者尾注 / PowerShell 提交报错”时，使用本 workflow。

1. 先确认用户是否**明确要求执行 `git commit`**。
   - 如果没有明确要求，只做分析、生成提交信息建议或检查，不实际提交。

2. 牢记硬约束。
   - 提交信息必须中文，并说明“为什么改”。
   - 禁止在命令行内联中文提交正文。
   - 统一使用 `UTF-8 文件 + git commit -F`。
   - 若连续两次因引号/转义失败，立即切换低风险方案，不再堆复杂命令。
   - 若需要 `--amend`、`rebase` 等重写历史，先创建备份分支。

3. 执行提交前门禁。
   - `git status --short`
   - `git diff --cached --name-only`
   - `git diff --cached --stat`
   - `git log -1 --format=%s`

4. 准备提交信息文件。
   - 用编辑器或补丁工具创建 `.git/COMMIT_MSG_TMP.txt`，编码必须为 UTF-8。
   - 不要把中文正文直接塞进 PowerShell 命令。
   - 先做 UTF-8 字节校验，再人工核对正文可读性。

5. 用 PowerShell 安全模式执行提交。
   - 运行 `git commit -F .git/COMMIT_MSG_TMP.txt`。
   - 提交后清理临时文件。

6. 执行提交后门禁。
   - `git show --name-only --oneline -1`
   - `git status --short`
   - `git log -2 --pretty=fuller`
   - 再次校验最新提交正文能被 UTF-8 严格解码，并人工确认没有乱码。

7. 处理常见异常分支。
   - PowerShell 解析失败：停止继续堆叠命令，回到 `-F` 文件方案。
   - 提交信息乱码：不要复用污染文本，重新生成 UTF-8 文件并复核。
   - 最近两条提交信息重复/过粗：在重写前先建备份分支，再执行 amend。
   - `Co-authored-by`：仅在用户需要共同作者尾注时处理。

8. 向用户回报时至少包含。
   - 是否实际提交成功。
   - 最新 commit 摘要。
   - 是否存在乱码、重复信息或需要继续修订的风险。
