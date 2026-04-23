---
name: git-commit-safe-workflow
description: 在 PowerShell 环境执行稳定的 Git 提交流程，覆盖提交前后门禁、中文提交信息生成、乱码诊断与修复、重复提交信息修订、Co-authored-by 处理。适用于用户提到提交失败、提交乱码、重写提交信息、共同作者尾注、PowerShell 提交报错等场景。
---

# Git 提交安全流程

## 适用场景（触发词）

- 提交失败 / 提交报错 / PowerShell 提交问题
- 提交乱码 / 中文提交信息异常
- 重写提交信息 / amend / 历史修订
- 共同作者尾注（`Co-authored-by`）处理

## 根因速记

### 为什么会提交失败

- PowerShell 不是 Bash，`&&` 在当前环境下常触发解析失败。
- 中文 + 多行 + 引号/转义叠加时，内联字符串容易被 PowerShell 先截断。
- 把 `git commit` 当“试命令”反复执行，历史很快漂移。

### 为什么会提交乱码

- 提交信息不是稳定 UTF-8 字节（被代码页/错误转码污染）。
- 终端“看起来像显示问题”，但 Git 对象内容可能已损坏。
- 从污染文本继续复制会扩散乱码。
- 在 PowerShell 命令链中内联中文时，文本可能在写文件前就已被错误解码；即便后续 `write_text(..., encoding='utf-8')`，也会把“已乱码文本”写成合法 UTF-8，造成 strict 解码通过但语义仍错误。

## 硬性约束（必须遵守）

- 仅在用户明确要求时执行 `git commit`。
- 提交信息必须是中文，且表达“为什么改”，避免空泛标题。
- 禁止内联中文提交正文；统一使用 `UTF-8 文件 + git commit -F`。
- 禁止在 shell 命令行直接放中文正文（含 `python -c "...中文..."` / here-string）；中文正文必须先落盘为独立 UTF-8 文件，并在提交前人工核对可读性。
- 发生两次引号/转义失败后，立即切换低风险方案，不再堆叠复杂命令。
- 历史重写前必须创建备份分支：`backup/rewrite-msg-YYYYMMDD-HHMMSS`。

## 标准 SOP

### Step 1：提交前门禁

依次执行并确认范围：

```powershell
git status --short
git diff --cached --name-only
git diff --cached --stat
git log -1 --format=%s
```

### Step 2：生成并核对提交信息（UTF-8）

```powershell
# 1) 用编辑器/补丁工具创建 .git/COMMIT_MSG_TMP.txt（UTF-8）
# 2) 只做字节校验（strict 通过不等于语义正确）
python -c "from pathlib import Path; b=Path('.git/COMMIT_MSG_TMP.txt').read_bytes(); b.decode('utf-8','strict'); print('MSG_UTF8_OK', len(b))"
# 3) 人工核对正文可读性（必须）
python -c "from pathlib import Path; s=Path('.git/COMMIT_MSG_TMP.txt').read_text(encoding='utf-8'); Path('.git/COMMIT_MSG_PREVIEW.txt').write_text(s, encoding='utf-8')"
```

### Step 3：执行提交（PowerShell 安全模式）

```powershell
$ErrorActionPreference = 'Stop'
git commit -F .git/COMMIT_MSG_TMP.txt
$ec = $LASTEXITCODE
Remove-Item .git/COMMIT_MSG_TMP.txt -ErrorAction SilentlyContinue
if ($ec -ne 0) { exit $ec }
```

### Step 4：提交后门禁

```powershell
git show --name-only --oneline -1
git status --short
git log -2 --pretty=fuller
python -c "import subprocess; subprocess.check_output(['git','log','-1','--format=%B']).decode('utf-8','strict')"
python -c "import subprocess, pathlib; s=subprocess.check_output(['git','log','-1','--format=%B']).decode('utf-8','strict'); pathlib.Path('.git/LAST_COMMIT_MSG_CHECK.txt').write_text(s, encoding='utf-8')"
```

## 异常分支

### A. PowerShell 解析失败

- 典型现象：`&&` 错误、here-string 缺少终止符、unexpected token。
- 处理：停止内联字符串，直接走 `-F` 文件提交流程。

### B. 提交信息乱码

先确认是“显示问题”还是“对象损坏”：

```powershell
python -c "import subprocess, pathlib; b=subprocess.check_output(['git','log','-1','--format=%B']); s=b.decode('utf-8','strict'); print(b[:48]); pathlib.Path('.git/LAST_COMMIT_MSG_CHECK.txt').write_text(s, encoding='utf-8')"
```

- 若 strict 解码失败：说明对象已污染，使用可信 UTF-8 文本执行 `git commit --amend -F` 修复。
- 若 strict 解码通过：必须查看 `.git/LAST_COMMIT_MSG_CHECK.txt`。
  - 文件内容也乱码：说明对象内容已污染，立即备份分支并 `git commit --amend -F` 修复。
  - 文件内容正常但终端显示异常：按终端编码问题处理，不改 Git 对象。

### C. 最近两条提交信息重复/粗略

- 用 `git log -2 --pretty=fuller` 检查。
- 分别重写两条提交信息，正文明确“改动目的 + 影响范围 + 风险控制”。

### D. 自动追加 `Co-authored-by`

- 若用户不接受该 trailer，先尝试 `--amend` 修复。
- 若环境仍自动注入：先建备份分支，再用 `git commit-tree` 重建提交对象并替换分支头。

## 给用户的结果回报模板

```markdown
已完成提交处理。

- 提交哈希：<hash>
- 提交标题：<中文标题>
- 门禁检查：已执行提交前/后门禁
- 编码检查：UTF-8 strict 解码通过
- 剩余改动：<git status --short 摘要>
- 备注：<是否重写历史/是否处理 Co-authored-by>
```
