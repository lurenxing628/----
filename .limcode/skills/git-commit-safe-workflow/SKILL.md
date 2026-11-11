---
name: git-commit-safe-workflow
description: Git 提交安全与 PowerShell 编码排障参考；用于明确授权的提交、提交报错或提交信息乱码，不自动重写历史。
---

# Git 提交安全

按需读取 [git-safety.md](git-safety.md)：普通提交关注范围和暂存保护；PowerShell 或乱码问题再读取编码排障部分。macOS / zsh 不套用 PowerShell 命令。

只有用户明确要求时提交；提交、amend、推送和历史重写是不同操作，分别依据已有授权。发现标题重复、乱码或 trailer 不产生自动改写历史的授权。

核对本轮路径与暂存内容，不捎带他人的 staged、unstaged、untracked 修改。中文提交说明目的，多行正文通过可信 UTF-8 文件传给 `git commit -F`，避免 shell 转义改变正文。

worktree 中 `.git` 可能是文件，临时消息路径通过 `git rev-parse --git-path COMMIT_MSG_TMP.txt` 解析，或使用独立临时文件。提交后核对实际提交文件、消息和剩余工作区状态。
