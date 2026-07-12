# APS Checkup 基线说明

本目录是 `cs-checkup` 的可重跑机器基线。它和 `.codestable/audits/` 的单次体检报告分工不同：

- `checkup/` 保存扫描脚本、最近一次机器快照、门禁基线和历史对比样本。
- `audits/YYYY-MM-DD-checkup/` 保存某一次体检的判断、趋势和人工结论。
- `.limcode/skills/cs-checkup/` 保存 LimCode 执行流程，不保存项目事实。

机器可读总入口：[`baseline.json`](baseline.json)。

## 2026-07-11 终态工具证据重建与 clean HEAD 证明

`baseline.json.code_baseline` 仍保留已提交的历史 clean-source 投影：

- 基线 commit：`606bcda1d369914875fe63a5d3657ff4cbc351ac`
- commit 日期：`2026-07-01`
- 生成方式：`git archive HEAD` 解到 `/tmp` 后扫描
- 历史工作树状态：有未提交改动，但**没有纳入该 clean-source 投影**

2026-07-11 在起点 HEAD `cd6cdf43798e3c6321370e4fceb7150bbe4cef3c` 的脏工作区完成调用图 KISS 收敛、动态 import alias 重绑定修正和终态证据重建；两个临时候选确定性一致后才写正式证据。随后经用户明确授权提交，提交后的干净 HEAD 又无缓存、无续跑执行完整 19 步质量门禁，因此下面结果已从局部验证升级为 **clean-worktree proof**：

| 检查 | 当前结果 | 口径 |
|---|---|---|
| callgraph | 7329 callable、25772 输出边、10152 确信边、15620 模糊边、typed 边 0、8 条受限真实简单循环、解析错误 0 | callable 含 316 个嵌套 def/lambda；simple cycle 长度 2-8、最多 200，不是 SCC；island 193 |
| import cycles（生产非测试） | 750 模块、6 hard 目录 SCC、9 父包感知 hard 文件加载 SCC、0 纯显式 hard 文件 SCC、14/5 个父包感知/纯显式 runtime 文件 SCC | `hard=8809 / cond=4 / lazy=257 / typeonly=135`；父包初始化边 6654 条；unresolved 6 个 |
| import cycles（含测试） | 1443 模块、7 hard 目录 SCC、9 父包感知 hard 文件加载 SCC、0 纯显式 hard 文件 SCC、unresolved 44 个 | 独立 `production-and-tests` v2 基线；比生产多 1 个测试目录 SCC 和 38 个测试动态加载站点 |
| 确定性 | 调用图两个独立临时目录均为同一组 10 个 JSON，逐文件 SHA256 完全一致 | 双 scope 候选基线与正式基线逐字节一致；SCC、圈内边和 unresolved 均无增删 |
| 完整质量门禁 | 19/19 步通过；收集 4712 项；full-test-debt unexpected failure 0；required 253 个目标 / 2467 nodeids | 命令使用 `--require-clean-worktree --no-long-gate-cache --no-resume`，没有复用旧成功缓存 |

`.codestable/checkup/latest/callgraph/` 已由核对通过的临时候选受控覆盖，两份 import-cycle v2 基线也已通过正式 CLI 刷新。`baseline.json.artifact_sha256` 绑定最终四个调用图脚本、四个循环扫描工具、完整 10 个调用图 JSON 和两份循环基线，并记录 `clean_worktree_proof=true`。

完整命令、两次门禁暴露的测试合同缺口及根因修复见 `.codestable/issues/2026-07-11-dependency-proof-rebuild-and-closure/`。本次 clean proof 只证明当前机械证据与质量门禁；`history_baseline` 的决定考古仍是 pending，不能顺带写成已完成。

### 历史 clean-source 机器检查（606bcda1）

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

# 函数级调用图（支持 CHECKUP_CALLGRAPH=/tmp/... 临时输出）
.venv/bin/python .codestable/checkup/scripts/callgraph_extract.py

# APS 正式循环门禁双 scope
.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean
.venv/bin/python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean
.venv/bin/python tools/scan_dead_code_islands.py --mode quick
```

### 复现历史 clean-source 源码投影

历史代码投影对应 `606bcda1...`。下述 archive 流程仍可复现该源码树，但当前调用图/import 扫描器语义已在 2026-07-10 升级（接收者/alias/嵌套 callable、父包初始化、入口/插件 scope），因此用新扫描器重跑旧源码得到的是“新口径投影”，不会也不应复现旧的 20 条函数循环或 0 个父包感知文件 SCC。历史数字只作当时证据。

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
