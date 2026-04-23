---
name: using-git-worktrees
description: >
  在开始功能开发或执行 plan 前，为当前仓库创建隔离工作树，避免直接在现有工作区或主分支上动手。
  适用于需要隔离开发现场的实现任务。
---

# 使用 git 工作树

## 核心观念

git 工作树可以让你在不切走当前工作区的情况下，为另一条分支开一个独立工作目录。

**核心原则：先选对目录、确认忽略规则、再建工作树、再验基线。**

调用本技能后，先告诉用户：

> 我正在使用 `using-git-worktrees` 来准备隔离工作区。

## 目录选择顺序

按下面顺序决定工作树目录：

### 1. 先看仓库里有没有既有目录

优先检查：

```bash
ls -d .worktrees 2>/dev/null
ls -d worktrees 2>/dev/null
```

规则：

- 两者都存在时，优先 `.worktrees/`
- 只存在一个时，用那个

### 2. 再看项目约定文件

如果仓库里没有现成目录，就检查：

- `AGENTS.md`
- `.limcode/README.md`
- 其他团队约定文档

如果这些文档里明确写了工作树目录偏好，直接遵守。

### 3. 再问用户

如果还没有答案，就问用户：

```text
当前没有现成的工作树目录。你希望我把工作树建在哪？

1. `.worktrees/`（仓库内，隐藏目录）
2. `~/.limcode/worktrees/<项目名>/`（用户目录下的全局位置）

请选择一个。
```

## 安全检查：仓库内目录必须先确认已被忽略

如果工作树目录在仓库内（`.worktrees/` 或 `worktrees/`），必须先确认它已被 git 忽略：

```bash
git check-ignore -q .worktrees
git check-ignore -q worktrees
```

如果没被忽略：

- 先修 `.gitignore`
- 明确告诉用户这是保护措施
- 修好后再继续建工作树

**不能跳过这一步。** 否则工作树内容可能污染仓库状态。

## 创建步骤

### 1. 识别项目名

```bash
git rev-parse --show-toplevel
```

从仓库根目录推导项目名。

### 2. 约定分支名

分支名应与本次任务主题对应，避免含糊命名。

好的例子：

- `feature/scheduler-summary-fix`
- `fix/import-strict-mode`
- `refactor/resource-pool-builder`

### 3. 创建工作树

```bash
git worktree add <工作树路径> -b <分支名>
```

进入工作树后，再开始依赖安装和基线检查。

## 项目初始化

按仓库实际文件自动判断需要做什么：

### Python 项目

如果存在：

- `requirements.txt` → 可安装依赖
- `pyproject.toml` → 看是否需要项目级安装

常见命令：

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 其他技术栈

如果仓库里有别的技术栈文件，再按实际情况处理：

- `package.json`
- `Cargo.toml`
- `go.mod`

## 验证干净基线

工作树建好后，必须先验证“当前基线是不是健康的”。

优先顺序：

1. 跑项目约定的最小基线验证
2. 如果用户要求，再跑更完整测试

如果测试失败：

- 不要直接开始新开发
- 先告诉用户失败情况
- 问用户是继续、先修基线，还是换更小验证集

## 输出模板

准备完成后，向用户报告：

```markdown
## 工作树已准备
- 路径：...
- 分支：...
- 目录选择原因：...
- 忽略规则检查：已通过 / 已修复
- 基线验证：通过 / 失败（详情如下）
```

## 常见错误

### 错误 1：不检查忽略规则

结果：

- 工作树内容跑进 git 状态
- 仓库现场被污染

### 错误 2：目录位置靠猜

结果：

- 违反项目约定
- 以后别人找不到现场

### 错误 3：不验基线就开始开发

结果：

- 后面分不清是旧问题还是新问题

### 错误 4：默认在主分支上直接开改

结果：

- 容易把未完成工作混进主线

## 与其他技能的关系

- `brainstorming`：design 批准后，进入实现前可先开工作树
- `writing-plans`：plan 就绪后，如果要实施，先准备隔离工作区
- `subagent-driven-development` / `executing-plans`：执行前建议先开工作树
- `finishing-a-development-branch`：完成后负责清理工作树

## 最终要求

**先隔离，再实现。**

如果当前任务明显会改代码，而你又没有明确确认工作区隔离策略，那就还没准备好开始写代码。