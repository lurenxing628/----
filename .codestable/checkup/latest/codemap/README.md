# Codemap 快照说明

本目录由以下脚本对 clean source archive 生成：

```bash
python3.14 .codestable/checkup/scripts/codemap_extract.py
python3.14 .codestable/checkup/scripts/dynamic_refs.py
```

当前快照对应 commit `606bcda1d369914875fe63a5d3657ff4cbc351ac`，生成日期为 2026-07-10。工作树未提交源码改动没有纳入。

两个扫描脚本是在本轮才恢复的，目标 commit 本身不包含它们。重放时先 `git archive 606bcda1...`，再把 `baseline.json` 已记录 SHA256 的扫描器复制到 archive 内运行；`.codestable/` 不属于扫描器的 `FIRST_PARTY_ROOTS`，因此工具注入不会进入模块、行数或依赖统计。完整命令见 `.codestable/checkup/README.md`。

## 可以直接采信的范围

- `summary.json`：模块、行数、定义、import、重复簇的机械统计。
- `layering.json`：按脚本内置规则识别的分层违规候选；本次为 0。
- `import_edges.json` / `layer_edges.json`：静态 import 边。
- `defs.json` / `symbol_index.json`：AST 能解析到的定义及位置。
- `dup_bodies.json`：归一化后相同的小函数体簇，可作为人工去重入口。

本次汇总：741 个模块、145194 行、7370 个定义、2374 条 import 边、14 个重复函数体簇、0 个分层违规候选、0 个解析错误。`dup_bodies.json` 的指纹键依赖 CPython AST dump，本快照按宿主 Python 3.14 生成；跨解释器比较时应按重复簇成员核对，不应只比较指纹字符串。

## 不能直接采信的范围

- `orphan_candidates.json`：零静态入边不等于死代码。
- `orphan_refined.json`：扣除一部分字符串注册和 Flask 路由后仍只是嫌疑清单，本次 109 项。
- `dynamic_refs.json`：只覆盖脚本已认识的动态引用模式，不是完整运行时调用图。
- `dup_bodies.json`：相同样板可能是 dataclass、repository 或协议实现，不能见重复就删。

死代码判定必须补 `git grep`、symbol locator、运行时覆盖或删除后全量测试证据。函数级调用关系优先交叉查看相邻的 `../callgraph/` 快照。
