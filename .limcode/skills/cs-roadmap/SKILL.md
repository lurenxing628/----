---
name: cs-roadmap
description: 对需要分阶段交付的复杂需求制定或更新规划，记录模块职责、跨功能契约和依赖清单。按已授权范围处理多份规划，不把普通功能自动升级为完整规划。
---

# 分阶段规划

启动、授权与续作遵守根目录 `AGENTS.md`；读取或复用 `.codestable/attention.md`。路径、状态与收尾按需查 `.codestable/reference/shared-conventions.md`。

roadmap 记录目标方案和实施顺序；requirements 记录能力愿景，architecture 记录已落地结构。未实现的目标不能提前回写成当前架构。

## 输入与范围

- **new**：为明确的大需求形成方案及子功能依赖。
- **update**：修改已有规划、条目、依赖或接口约定。
- 用户只问建议时只读交付；要求创建或更新规划时才落盘。已知目标与决定直接复用，重大产品取舍未知时再澄清。
- 先检索 roadmap 索引或相关条目防重复，再读目标主文档、items.yaml、相关 req/arch 和讨论记录；不读取全部其他 roadmap。
- 更新契约时核对受影响的 in-progress/done 子功能及其 design/acceptance，不能只改规划文字忽略存量实现。

## 起草与校验

模板按需读 `reference.md`，记录三部分：

1. 模块与职责：说明目标结构、边界和依赖。
2. 跨功能接口契约：共享字段、调用协议、错误语义及状态归属，明确到依赖功能可实现的程度。没有跨模块接口时明确写无。
3. 子 feature：按可独立交付和验证的能力拆分，解释依赖原因，先识别一条可运行的最小闭环。

依赖图必须无循环；共享接口未定且阻断依赖实现时标待决，不假造契约。技术依赖可自行排序，产品优先级存在实质取舍时让用户决定。用户已批准的排序不重复确认。

完整稿自查边界、依赖、存量影响及已知冲突。已授权且决定明确时完成更新；用户要求先审稿或仍有重大取舍时，交付具体方案及待决点，不把未批准方案写成 active。

## 产物与状态

沿用 `.codestable/roadmap/{slug}/`：

- `{slug}-roadmap.md`：背景、范围、模块拆分、接口契约、子 feature 清单、排期思路和观察项。
- `{slug}-items.yaml`：保留 `roadmap`、`created`、条目的 `slug`、`description`、`depends_on`、`status`、`feature` 以及适用的 `minimal_loop`、`notes` 等字段。
- `drafts/` 仅在需要草稿材料时创建。

新规划获准后主文档记 `status: active`、`created`、`last_reviewed`，条目初始 `planned`、`feature: null`。update 更新关联内容和必要变更日志。条目取消改 `dropped` 并留理由，不删除历史；所有条目 done/dropped 后才标 completed。

落盘后用项目 `validate-yaml.py` 校验纯 YAML，并人工核对依赖引用和状态对应；语法通过不代表业务依赖正确。没有授权不修改 req、architecture、业务代码或其他 feature。

## 与功能流程衔接

- 从 roadmap 开始功能时，核对依赖与当前契约，沿用条目 slug。design 带 `roadmap` / `roadmap_item`；实际启动且记录已获授权时 items 条目标 `in-progress`、`feature` 填对应目录名。
- 共享契约不合理时说明对当前与其他功能的影响，在已授权范围更新 roadmap；实质取舍再确认，不能在子 feature 中悄悄绕开。
- `cs-feat-accept` 仅在适用验收真正通过且已授权回写时，把条目标 `done`，同步主文档“子 feature 清单”和机器清单。
- 实现与记录冲突时报告并核实，不把状态改新当成完成证据。

## 完成标准

所选范围已有可执行规划或真实更新；依赖、接口、边界和状态一致；记录未伪造批准或完成。多份规划请求按用户范围分组完成，不以“一次一份”阻断已授权工作。
