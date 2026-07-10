# APS Checkup 基线说明

本目录是 `cs-checkup` 的可重跑机器基线。它和 `.codestable/audits/` 的单次体检报告分工不同：

- `checkup/` 保存扫描脚本、最近一次机器快照、门禁基线和历史对比样本。
- `audits/YYYY-MM-DD-checkup/` 保存某一次体检的判断、趋势和人工结论。
- `.limcode/skills/cs-checkup/` 保存 LimCode 执行流程，不保存项目事实。

机器可读总入口：[`baseline.json`](baseline.json)。

## 2026-07-10 重验结论

本次基线只覆盖已提交的 `HEAD`：

- 基线 commit：`606bcda1d369914875fe63a5d3657ff4cbc351ac`
- commit 日期：`2026-07-01`
- 生成方式：`git archive HEAD` 解到 `/tmp` 后扫描
- 工作树状态：有未提交改动，但**没有纳入基线**
- 总状态：`mechanical_ready_history_pending`

这样做是为了避免把正在开发中的改动混进“已提交基线”，也避免在脏工作树上声称 clean-worktree proof。

### 机器检查

| 检查 | 结果 | 关键数据 |
|---|---|---|
| codemap | 通过 | 741 模块、145194 行、7370 定义、2374 条 import 边、分层违规 0、解析错误 0 |
| callgraph | clean HEAD 重跑结果与已提交快照一致 | 6921 函数、26763 条边、20 个函数级环、164 个孤岛、解析错误 0 |
| import cycles | 通过“无新增硬环”门禁 | 6 个既有目录硬环、0 个文件硬环、退出码 0 |
| dead-code quick | 经核验后刷新并复跑通过 | 164 候选、82 已解释、82 个基线疑似项、0 个新增 |

`codemap/orphan_refined.json` 的 109 项只是“静态和已识别动态引用均未命中”的候选，**不能直接当死代码**。

### dead-code 基线为何允许刷新

刷新前出现 7 个“新增疑似项”。已在 clean HEAD 上用 `git grep` 核验：

- `BuildOutcome.has_events`：生产代码和测试均有属性读取。
- `registered_neighborhoods`：公开导出并有合同测试。
- `VnsState.__post_init__`：dataclass 生命周期回调。
- `graph_score_requested`、`graph_score_weight`、`graph_score_weights`、`score_disabled_public_fields`：通过重导出/别名在生产链与测试中使用。

它们属于 quick AST 使用图的已知误报，不是本轮要删除的死代码。按 `.codestable/attention.md` 的项目口径，用 `--mode quick --refresh` 收敛了基线；没有用 precise 口径覆盖 quick 门禁基线。

## 两条水位线必须分开

`baseline.json` 同时记录两类水位线，不允许混成一个：

1. **代码投影基线**：当前为 `606bcda1...`。codemap、callgraph、循环依赖和 dead-code 都对它负责。
2. **决定考古水位线**：仍为 `65870e4786f3fea1e45c259e9d209ee6e1598a31`（2026-06-01）。

旧水位线到代码基线之间有 **332 个提交**。这些提交尚未逐个做分量分级和必要 diff 考古，因此本轮没有把决定水位线冒进到 HEAD。

只有完成全部待审提交的决定考古，才能更新 `history_baseline.decision_watermark_commit`。单纯重跑代码扫描不能证明历史决定已覆盖。

## 历史基线来源

2026-06-01 的首次地基体检从未进入正式提交，只保存在 Git stash 的 untracked 快照：

- stash merge commit：`cb79bf9577268869c48fcd69f4012a729ab7eb91`
- untracked 文件树：`725cca792aedc8571d8210bdc5b4b41ac83e2800`
- 当时基于的业务 commit：`b08162cd6c1edc1c9ce4f5ab43f0381740457ba8`

本次只恢复了做趋势对比所需的核心样本，放在：

```text
.codestable/checkup/legacy/2026-06-01-foundation-maturity/
```

这些文件是**历史证据，不是当前事实**。旧报告中的模块文件数、行数、schema 版本、路径和健康度必须重新核验后才能引用。

## 可重跑命令

### 当前工作树快检

下面命令扫描当前工作树。CodeStable/LimCode 的本机分析工具使用宿主 Python 3.14；APS 运行代码、测试和打包仍以项目 `.venv` 的 Python 3.8 / Win7 兼容性为准。

```bash
# 模块/import/定义/重复/分层投影（本机分析工具）
python3.14 .codestable/checkup/scripts/codemap_extract.py
python3.14 .codestable/checkup/scripts/dynamic_refs.py

# 函数级调用图
python3.14 .codestable/checkup/scripts/callgraph_extract.py

# APS 门禁口径
.venv/bin/python -m tools.scan_import_cycles --json --fail-on-new-cycle
.venv/bin/python tools/scan_dead_code_islands.py --mode quick
```

### 复现正式 clean-source 基线

本次代码投影对应 `606bcda1...`，而两个 codemap 脚本是在本轮才恢复的，旧 commit 本身不包含它们。真实重放方法是：先解出只含目标 commit 的源码，再把当前 manifest 已记录 SHA256 的扫描器复制进去。扫描器位于 `.codestable/`，不属于脚本的 `FIRST_PARTY_ROOTS`，不会进入模块、行数或依赖统计。

```bash
ROOT=$(pwd)
BASELINE_COMMIT=606bcda1d369914875fe63a5d3657ff4cbc351ac
HOST_PY=$(command -v python3.14)
APS_PY="$ROOT/.venv/bin/python"
TMP=$(mktemp -d /tmp/aps-checkup-XXXXXX)

# 只解出目标 commit 的源码。
git archive "$BASELINE_COMMIT" | tar -x -C "$TMP"

# 注入本轮固定版本的只读扫描器；baseline.json 用 SHA256 绑定其内容。
mkdir -p "$TMP/.codestable/checkup/scripts"
cp "$ROOT/.codestable/checkup/scripts/codemap_extract.py" \
   "$ROOT/.codestable/checkup/scripts/dynamic_refs.py" \
   "$TMP/.codestable/checkup/scripts/"

cd "$TMP"
CHECKUP_OUT="$TMP/_baseline/codemap" \
  "$HOST_PY" .codestable/checkup/scripts/codemap_extract.py
CHECKUP_OUT="$TMP/_baseline/codemap" \
  "$HOST_PY" .codestable/checkup/scripts/dynamic_refs.py
CHECKUP_CALLGRAPH="$TMP/_baseline/callgraph" \
  "$HOST_PY" .codestable/checkup/scripts/callgraph_extract.py

"$APS_PY" -m tools.scan_import_cycles --json --fail-on-new-cycle
"$APS_PY" tools/scan_dead_code_islands.py --mode quick
```

正式落盘前先比较临时输出、核对 parse errors / layering / 新增硬环 / dead-code 新项，并复算 `baseline.json` 的关键 SHA256。受控刷新 dead-code 基线前，必须逐项动态或调用证据核验；刷新命令是：

```bash
python3 tools/scan_dead_code_islands.py --mode quick --refresh
```

## 全景 HTML 的限制

以下文件当前存在于本机，但被 `.gitignore` 排除：

- `docs/项目全景图.html`
- `docs/项目全景图-大白话版.html`
- `docs/项目演进时间线.html`
- `docs/边界防线全景图.html`
- `docs/_panorama_data/`

因此它们只能作为本机预览，不能作为“新克隆可重生”的证明。`cs-checkup` 在生成器和输入没有正式入库前，必须把可视化结论标为 `blocked` 或 `local-only`，不能假装四张图已具备完整可重放链路。
