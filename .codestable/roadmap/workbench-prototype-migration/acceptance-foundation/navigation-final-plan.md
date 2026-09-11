---
doc_type: executable-acceptance-plan
status: executable-unit-verified-not-live-verified
date: 2026-09-10
scope: B-owned canonical navigation and focused boot groups
---

# 新增导航与 Boot 分组交接

最新实测已完成：E06 封板源码与 V2 `06ad...` 测试 **252/252 通过**，见 [E06 交接](canonical-boot-e06-handoff.md) 和 [证据](canonical-boot-e06-evidence.json)。这是固定快照证明，不是最终 HEAD/clean 或正式 5000 证明。

以下保留 ea5f 准备阶段的分组、启动约束与当时状态，不代表本轮仍未执行。首轮实际结果仍见 `canonical-boot-ea5f-handoff.md`：216/252，32 项探针问题与 4 项真实只读报表恢复问题分账；原失败记录不回写为通过。

## 首轮准备结论（历史）

- 可执行分组入口、两份剩余 helper 和冻结源检查已完成。24 个定点测试通过；6 个 Python 文件 Ruff/Pyright 通过；6 个 CJS 语法检查通过。
- 新 252 项仍未执行浏览器矩阵，不是 252 PASS，也不是 Mainhost 全链路验证。历史 64b6 的 92/92 结果与原始目录未修改。
- 当前尚未收到 F 完整 source snapshot 的路径与 build/manifest 身份。最新授权要求先完整复制到 B 自有 source/asset 副本；不向正在执行的 F 目录写入任何 overlay。副本核验通过后直接运行 252 项，无须第二次 GO。
- 只改 B 的 tests 和本 acceptance 目录。Mainhost、产品源码、全局 build、capacity 和其他域写集均不在本轮修改范围。

## 固定分母

| 参数 | 浏览器用例 | 重启期间保活原页 |
|---|---:|---:|
| `--groups legacy` | 92 | 4 |
| `--groups canonical` | 212 | 24 |
| `--groups boot` | 40 | 0 |
| `--groups canonical,boot` | 252 | 24 |
| `--groups all` | 344 | 28 |

canonical 的 212 = 6 个正向真实对象 x 4 种恢复方式 x 4 屏幕主题组合 + 24 个 HTTP400 边界 x 4 + 5 个合法但不存在的对象 x 4。boot 为 10 个故障定义 x 4。每组先固定分母，再检查唯一 case 标识、实际执行数量和失败数；不从已完成部分反推分母。

4 组合是 1392x924/1920x1080 各 light/dark。正向对象包括 gantt/analysis/delay 的真实 plan_ref 与范围、reports 的真实 plan/batch/date/query 范围、trial 原来源范围预览、1 个真实既有草稿。

## B 的完整文件清单

以下路径都相对完整 source root；仅这些 12 项允许作为 B tests-only 机械副本覆盖到 B 新复制的 source 副本，不覆盖任何产品文件，绝不写 F 正在使用的 source。逐文件 SHA 和集合 SHA 在 `executable-groups.json`，与 F 原始测试源版本分账。

```text
tests/workbench/final_foundation_live.py
tests/workbench/final_foundation_live_support.py
tests/workbench/final_foundation_live_source_guard.py
tests/workbench/final_foundation_live_nav_cases.py
tests/workbench/final_foundation_navigation_seed.py
tests/workbench/test_final_foundation_live.py
tests/workbench/final_foundation_live.cjs
tests/workbench/final_foundation_live_probe.cjs
tests/workbench/final_foundation_live_actions.cjs
tests/workbench/final_foundation_live_faults.cjs
tests/workbench/final_foundation_live_boot_cases.cjs
tests/workbench/final_foundation_live_navigation.cjs
```

本轮补齐的两份 helper 是 `final_foundation_live_source_guard.py` 与 `final_foundation_live_navigation.cjs`。入口内部复用从 F 完整复制到 B 的 `tests/workbench/final_foundation_host.py`，没有修改它，也没有另造产品 endpoint 或页面 hook。

当前 B tests-only 集合 SHA-256：`ea5f795e8b58ac16dcf21435b2858f1115ec872b2416aa1995290ac548884b16`。计算口径为 `executable-groups.json` 的 path-to-SHA 映射按 key 排序、紧凑 JSON、ASCII 编码后 SHA-256；不是 Git tree SHA，也不是 F 全源码 SHA。

## F Source 要求

1. 必须把 F 的完整独立 source 和实际 build 复制到 B 自有目录，包含产品、模板、构建输入、Mainhost 及其测试宿主依赖；仅 static/full-build 副本不够。复制前后核对逐文件 SHA 与 mode，相同产品和实际资产不重 build；F 原目录全程只读。
2. 只在 B 新副本追加明确的 12 项 tests-only 机械副本，独立记录上述测试快照与覆盖前身份，产品/资产必须仍与 F 逐 SHA/mode 相等。不能用 B 产品覆盖让旧 F build 看似可用。如果此版缺少所需 Main/D/G 产品合同，等待下一份完整快照。
3. `--expected-source-root` 必须等于 B 被执行入口真实所在 repo root；`--forbid-source-root` 包括原工作区 `/Users/lurenxing/GitHub/----`、F 原 source 和原 asset root。Python 源读取、SQLite 连接、产品模块来源及 Node 模块加载均设边界；不允许原树/原 DB 或 F 目录回退。
4. 唯一原树内的 Python 读取例外是实际解释器的 `/Users/lurenxing/GitHub/----/.venv`；外部 stdlib 为 `/Library/Frameworks/Python.framework/Versions/3.8`。二者记录为只读运行时目录，不把整个原树加入白名单。实际 Python 为 3.8.10。
5. B 在自己的 fresh root 建库，F 用另一 DB/root。B 只停止自己记录的 PID，保持浏览器及原页面不关，新宿主用 `--reuse-root` 在相同端口启动。旧 53144 宿主不触碰。
6. 每个 manifest 文件核对实际 bytes/SHA，所有 inputs 与副本源码一致；templates 单独复制核对；宿主第一次与新 PID 启动继续复用 Main 原守护。测试集合在 Node 开始/结束再次校验。源漂移、缺证据或守护违规不计通过。

## 入口与命令

下面这条只打印可执行分组与本轮测试 SHA，不建库、不启动宿主或浏览器。原树与 tests-only 副本中均已定点验证过该入口。

```bash
/Users/lurenxing/GitHub/----/.venv/bin/python -B /Users/lurenxing/GitHub/----/tests/workbench/final_foundation_live.py --groups canonical,boot --describe-groups
```

下面是实际矩阵入口。`F_*` 变量必须由 Main/F 从真实交付设置，`B_*` 是复制且逐 SHA/mode 校验完成的 B 自有目录；没有设置就立即失败，不猜路径。只从 B source root 执行；当前没有执行此命令。

```bash
: "${F_SOURCE_ROOT:?Main/F must supply the full frozen source root}"
: "${F_ASSET_ROOT:?Main/F must supply its matching static/workbench root}"
: "${F_BUILD_ID:?Main/F must supply the actual build_id}"
: "${F_MANIFEST_SHA256:?Main/F must supply the actual manifest SHA256}"
: "${B_SOURCE_ROOT:?B must supply its verified owned full source copy}"
: "${B_ASSET_ROOT:?B must supply its verified byte-and-mode-identical asset copy}"
cd "$B_SOURCE_ROOT"
env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/private/tmp/aps-final-foundation-B.xYPahs/entry-pycache \
  /Users/lurenxing/GitHub/----/.venv/bin/python -B \
  "$B_SOURCE_ROOT/tests/workbench/final_foundation_live.py" \
  --groups canonical,boot \
  --temp-parent /private/tmp/aps-final-foundation-B.xYPahs \
  --expected-source-root "$B_SOURCE_ROOT" \
  --forbid-source-root /Users/lurenxing/GitHub/---- \
  --forbid-source-root "$F_SOURCE_ROOT" \
  --forbid-source-root "$F_ASSET_ROOT" \
  --expected-test-snapshot-sha256 ea5f795e8b58ac16dcf21435b2858f1115ec872b2416aa1995290ac548884b16 \
  --prebuilt-asset-root "$B_ASSET_ROOT" \
  --expected-build-id "$F_BUILD_ID" \
  --expected-manifest-sha256 "$F_MANIFEST_SHA256"
```

`--groups boot` 可单跑 40 个早期故障；`--groups canonical` 可单跑 212 个导航 case。两者仍要求同样的完整冻结 source 和匹配预构建参数。`all` 留待 Main 安排最终总矩阵，不自动运行。

Node/Chromium 默认使用现有本机运行时：bundled Node 与 `/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium`。需要不同位置时显式传 `WORKBENCH_NODE` / `WORKBENCH_BROWSER` / `NODE_PATH`，不会安装依赖或下载浏览器。测试工具运行时不进入 Win7 产品交付。

## 检查行为

- 创建 trial 的唯一写入发生在自有 fresh fixture 的业务基线之前：原 mixed seed 后，通过真实 `WorkbenchTrialService.preview_create/create/get` 创建 1 个完整草稿，保存 request/receipt/前后业务行证据。没有 INSERT 假草稿或使用其他宿主引用。
- 基线之后仅真实 UI/HTTP 读取；trial preview POST 只读，不点击确认创建。原来源预览没有草稿 caption 是正常行为；另有既有真实草稿 case 锁住 identity/status/baseline/range caption。
- 正向页面直接打开带 nav 的 URL、复制该页实际 URL 到同一 context 新标签页、原页全量 reload、原页同端口新 PID 后 reload。请求与原始 API 文件都带 page_id；不能用其他页面响应替代。标题、侧栏、delay 父高亮、真实 DTO scope、caption 和几何都核验。
- `same_tab_f5` 使用 Playwright `page.reload()` 的实际全量文档重载语义；不声称发送了物理 F5 键。历史真实搜索按键检查仍保留原 `pressSequentially`，没有 fill 替代。
- 24 原页面跨宿主重启保活，nonce/PID/page_id/context_id 严格核对。不得清 history、删除 snapshot_ref、改 URL 或换新页来掩盖首次恢复失败。目录列出其他计划不等于选择它；合法未知对象必须真实 404、无替代 DTO/caption，点击真实重读后仍针对原对象。
- HTTP400 使用真实服务端拒绝页，检查无 boot/domain DTO、有新式错误与恢复入口，实际点击打开工作台。boot 的 null/array/bad messages 单独 route 注入，记录命中数及原/注入 SHA、无白屏与真实 reload 恢复。合法旧 POST flash 链、转义、独立关闭、导航清除、未知类别中性显示仍由 Main/G 负责，B 不代签。

## 验证和交接边界

- `executable-unit-verification.json`：本轮 24 项定点、Ruff/Pyright、CJS syntax、CLI describe 与路径阻断证据，明确没有执行浏览器。
- `navigation-case-plan.json` 和 `navigation-preparation-unit.json` 是之前的单位 fixture 编排证据，保留原样。真实矩阵启动后会在新的 root 根据本库真实回执重新生成 `foundation-navigation-case-plan.json`，不得把单位 fixture 的 refs 重放到 F/B 的其他数据库。
- 每次执行输出 root 下的 `foundation-result.json`、`foundation-browser.json`、raw API、截图、source before/after、两个宿主会话保留证据与 source-guard 报告。故障成功仅代表错误边界合同通过，不是业务成功。
- 最新授权允许在 B 完整副本、产品合同与源守护全部核对齐后直接运行 `canonical,boot`，无须再等 Main 第二次 GO。仍是中间 source snapshot，历史 92 不覆盖。
- 未提交本轮 12 项测试与新增交接文件，未触碰他人 staged/untracked。没有整仓 full gate、clean-worktree proof、最终 HEAD 证明或原生 Win7 验收。没有申请全局 freeze，也没有启动 5000/performance 窗口。
