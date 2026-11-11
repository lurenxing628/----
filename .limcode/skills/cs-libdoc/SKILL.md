---
name: cs-libdoc
description: 为库的公开组件、函数或命令创建及维护 API 参考，支持单条目和批量。逐条核对源码中的契约，沿用已有风格和清单，不复制接口名称后猜测内容。
---

# API 参考

启动、授权与续作遵守根目录 `AGENTS.md`；读取或复用 `.codestable/attention.md`。路径、状态、查重与取代关系按需查 `.codestable/reference/shared-conventions.md`。

API 参考回答公开接口的参数、返回值、默认值和行为；任务教程由 `cs-guide` 提供。源码与公开行为是事实源，注释或历史方案可能过时，冲突时核实后写清。

## 范围与输入

- 根据项目类型确定条目：组件、函数族、endpoint 族或 CLI 子命令。已有粒度与路径直接沿用，不重复确认。
- 用户指定既有速查表或普通文档时保留其格式，只更新所选接口与相关引用；不添加 frontmatter、manifest 或整套目录。
- 只有明确新建专用结构化 API 条目时，缺现有路径可用 `docs/api/{slug}.md`，清单为 `docs/api/manifest.yaml`。
- 批量请求先扫描指定公开表面，列出实际条目和未能确定的导出；不因数量大自动缩减用户要求。
- 同目录 `reference.md` 保存 manifest、条目 frontmatter、模板和源码提取清单，仅在需要时读取。

## 生成与更新

1. 查已有文档和 manifest，复用已明确的范围、模板和风格。
2. 每条核对当前 source_files 的签名、类型、默认值、导出及相关行为；相似接口也不能只复制改名。
3. 新建大量文档且用户风格确实未知时，可先完成代表样稿供决定；已有明确样板或本轮已授权风格时直接分批完成，不固定要求 2–3 篇再审批。
4. 动态导出或生成代码先查实际导出/生成源；仍无法确认时标 skipped 或待核实并说明，不硬猜接口。
5. 增量维护只更新受影响条目，必要时依据 last_scanned 后代码变更定位；不能把单条目更新扩大为清理全部 outdated。
6. 自查事实、来源和关联引用。用户要求先审稿时交付完整可审稿；已有明确授权和证据时直接完成，不以单条目人工确认阻断批量工作。

下列元数据仅用于既有 CodeStable 结构化 API 条目，或明确新建的专用结构化 API 文档；不强加给普通文档和接口速查表。保留清单的 `project`、`entry_type`、`source_root`、`last_scanned`、`entries` 及每条 `entry`、`category`、`source_files`、`doc_path`、`status`、`note`。文档保留 `doc_type: lib-api-ref`、`entry`、`category`、`status`、`source_files`、`summary`、`tags`、`last_reviewed`。

状态遵守实际：pending 未开始，draft 待核定，current 当前有效，outdated 过时，skipped 不在当前可生成范围。移出范围的条目留 note，不直接删除历史记录。只读检查不自动改变状态。

## 校验与结束

- 既有结构化 API 条目或明确新建的结构化条目用项目 `validate-yaml.py --file {路径} --require doc_type --require entry --require status`。
- 本次确有创建或更新的 manifest 用 `--file docs/api/manifest.yaml --yaml-only`；批量文档逐一或按项目工具支持的目录选项校验，不依赖不存在的参数。
- 结构化文档核对清单与实际文件、状态及来源一致；普通文档只核对接口来源、相关引用及原有格式。语法校验不代表 API 行为已运行验证。

完成用户所选范围并报告真实条目数、限制和未核实接口，不自动扩写其他指南、归档决定或提交。
