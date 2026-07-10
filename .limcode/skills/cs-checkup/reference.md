# cs-checkup 参考

## 1. 基线文件

机器事实入口：`.codestable/checkup/baseline.json`。

关键字段：

- `status`：整体状态；历史未补齐时必须保留 `history_pending` 含义。
- `code_baseline.commit`：机器投影对应的已提交 commit。
- `code_baseline.worktree_changes_included`：正式基线应为 `false`。
- `mechanical_checks`：codemap、callgraph、循环依赖、dead-code 的结果和统计。
- `history_baseline.decision_watermark_commit`：决定考古真实覆盖到的 commit。
- `history_baseline.pending_commit_count_to_code_baseline`：仍待考古的提交数。
- `artifact_sha256`：关键脚本和摘要的完整性校验。

历史对比样本：

```text
.codestable/checkup/legacy/2026-06-01-foundation-maturity/
```

它来自 stash 的 untracked 文件树，只能做历史证据；详见其中 `PROVENANCE.md`。

## 2. clean HEAD 重验方法

工作树有未提交改动时，不要原地覆盖正式快照。CodeStable/LimCode 的本机分析工具使用宿主 Python 3.14；APS 运行代码、测试与打包仍按项目 `.venv` 的 Python 3.8 / Win7 合同验证。

如果目标 commit 早于本轮恢复的 codemap 脚本，`git archive` 中不会自然存在这两个文件。必须把 manifest 已记录 SHA256 的扫描器注入 clean source archive；扫描器所在 `.codestable/` 不在 `FIRST_PARTY_ROOTS` 中，不会污染源码统计。

```bash
ROOT=$(pwd)
TARGET_COMMIT=HEAD
HOST_PY=$(command -v python3.14)
APS_PY="$ROOT/.venv/bin/python"
TMP=$(mktemp -d /tmp/aps-checkup-XXXXXX)
git archive "$TARGET_COMMIT" | tar -x -C "$TMP"

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

先比较临时产物：

- 脚本退出码是否正常。
- parse errors 是否为空。
- `layering.json` 是否为空。
- import cycles 是否出现基线外新增硬环。
- dead-code 是否出现新增项。

只有核验完才把临时输出复制到 `.codestable/checkup/latest/` 并更新 `baseline.json`。

## 3. 机器检查矩阵

| 检查 | 命令 | 正式产物 | 通过条件 |
|---|---|---|---|
| codemap | `python3 .codestable/checkup/scripts/codemap_extract.py` | `latest/codemap/` | parse errors 为空、分层违规 0 或已标红 |
| dynamic refs | `python3 .codestable/checkup/scripts/dynamic_refs.py` | `latest/codemap/dynamic_refs.json`、`orphan_refined.json` | 只产候选，不直接裁死代码 |
| callgraph | `python3 .codestable/checkup/scripts/callgraph_extract.py` | `latest/callgraph/` | parse errors 为空；模糊边明确保留 |
| import cycles | `python3 -m tools.scan_import_cycles --json --fail-on-new-cycle` | 基线文件不自动改 | 无基线外新增硬环 |
| dead-code | `python3 tools/scan_dead_code_islands.py --mode quick` | 基线文件不自动改 | 无新增，或新增已逐项核验 |

### 受控刷新规则

- import cycle：只有明确接受当前硬环集合时才用 `--update-baseline`。
- dead-code：项目 pre-push 使用 quick，刷新也必须用 `--mode quick --refresh`。
- dead-code 新项先做调用、运行时或测试核验；dataclass `__post_init__`、属性读取、鸭子接口、反射和重导出是已知误报源。
- precise 模式不能拿来覆盖 quick 基线；运行前还需要新鲜 SCIP 索引。

## 4. 14 个固定分区

分区名保持稳定，路径规模和文件数每轮现算，不沿用 2026-06 的旧数字。

1. `scheduler-run`
   - `core/services/scheduler/run/**`
2. `scheduler-dispatch`
   - `core/services/scheduler/dispatch/**`
   - `core/services/scheduler/resource_dispatch_*.py`
3. `scheduler-config-summary`
   - `core/services/scheduler/config/**`
   - `core/services/scheduler/summary/**`
   - scheduler 顶层配置/汇总兼容壳
4. `scheduler-exec-diag`
   - execution fact、operation execution、snapshot、delay diagnosis 相关模块
5. `scheduler-gantt`
   - `core/services/scheduler/gantt/**`
   - `core/services/scheduler/gantt_*.py`
   - `desktop/` 中仍存活的甘特接线
6. `scheduler-graph-misc`
   - graph、analysis、calendar、batch、plan identity/version resolution 等其余 scheduler 业务族
7. `core-algorithms`
   - `core/algorithms/**`
8. `core-infra`
   - `core/infrastructure/**`
   - `core/shared/**` 涉及基础设施边界的部分
9. `core-models`
   - `core/models/**`
10. `core-svc-domain`
    - scheduler 之外的 `core/services/**`
    - process/common/system/personnel/equipment/material/report 等
11. `data-repos`
    - `data/repositories/**`
12. `web-routes`
    - `web/routes/**`
13. `web-viewmodels`
    - `web/viewmodels/**`
14. `web-boot-ui`
    - `web/bootstrap/**`
    - `web/` 顶层启动/错误边界/UI 模式
    - `app.py` 等真实入口；已删除目录不得继续写进现状定义

分区重叠时按“更专用者优先”归类，例如 scheduler 模块不再重复计入 `core-svc-domain`。

## 5. 分区输出格式

每个分区至少输出：

```text
分区：<key>
结论：健康 / 有风险 / 证据不足
当前范围：<真实路径与规模>
机器证据：<codemap/callgraph/门禁>
代码证据：<file:line，3-8 条>
与上次相比：升 / 降 / 持平 / 不可比
阻塞项：<如有>
在途项：<关联 roadmap，标“别动”>
建议：<只列，不顺手修>
```

## 6. LimCode/Sub2API 只读切片模板

```text
你是本轮 cs-checkup 的只读分区审查子代理。不要改文件，不要刷新基线，不要启动其他子代理。

基线 commit：<commit>
分区：<key + 路径>
机器输入：<summary / candidates 路径>
历史对比：<legacy module finding 路径>

回答：
1. 结论：健康 / 有风险 / 证据不足
2. 当前真实边界与主要调用链
3. 机器候选逐项裁定
4. 与旧评分的可比变化
5. 证据：文件路径 + 行号
6. 未覆盖范围：没有就写“无”
```

不自动启动 Claude Code bridge。原生子代理不可用或失败时，主代理按同一模板降级执行并如实报告。

## 7. 决定考古分量规则

每个待审提交至少记录：

- commit hash / 日期 / message
- churn（新增 + 删除）
- 文件数
- 是否触及核心目录
- 是否必须看 diff
- 发现的新决定 / 推翻 / 无长期决定

强制看 diff：

- 触及核心架构或关键业务合同；或
- churn ≥ 150；或
- message 简单且 churn ≥ 80。

只有连续区间全部处理完，才能推进决定水位线。部分处理只能记录进度，不能把 watermark 跳到区间末尾之外。

## 8. 可视化限制

`docs/_panorama_data/` 和四张全景 HTML 当前被 Git 忽略，且缺少三张页面的完整确定性生成器。它们只能是本机辅助阅读材料。

体检报告可以：

- 报告本机页面是否存在、数据日期是否过期。
- 在已有输入上本地重生可重生的页面。

体检报告不可以：

- 把 ignored HTML 当版本化事实源。
- 在缺生成器时声称四张图全部可从 clean clone 重建。
- 为了凑退出条件手工改日期冒充刷新。
