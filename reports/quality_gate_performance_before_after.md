# Quality Gate Performance Before / After

## 1. 这份报告的边界

- 这份报告记录的是本轮日常快门禁、long gate cache 自测、启动回归的阶段性提速结果。
- 本轮没有把日常快门禁包装成最终 clean proof。
- 本轮没有在 dirty worktree 上声明 full-test-debt proof。
- 最终合并、发版、收口前仍必须运行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

## 2. Before 基线

| 项目 | Before |
|---|---:|
| `tools/check_full_test_debt.py` 总耗时 | 234.58s |
| full-test-debt 内部 pytest 执行 | 约 233.08s |
| pytest reports duration 总和 | 231.25s |
| pytest collect-only | 1.64s |
| top 10 慢测试文件占比 | 44.5% |
| long gate cache 三个自测文件 | 46.53s |
| 真浏览器 geometry smoke | 16.11s |
| scheduler batches 页面测试 | 13.09s |
| 两个 startup host/portfile 回归 | 约 11.38s |

## 3. After 阶段结果

| 项目 | After | 说明 |
|---|---:|---|
| 日常快门禁 `scripts/run_daily_quality_gate.py` | 2.35s | 只跑日常快速预检，不声明 clean proof |
| 日常快门禁 collect-only | 1.42s | 2307 tests collected |
| long gate cache 三个自测文件 | 34.24s | `199 passed`，保留坏 proof/log 代表路径 |
| 真浏览器 geometry smoke | 16.18s | `2 passed`，减少重复预请求后未明显下降 |
| scheduler batches 页面测试 | 12.05s | `28 passed`，复用进程内 schema 模板库后小幅下降 |
| 两个 startup host/portfile 回归 + host 纯函数测试 | 6.01s | `10 passed`，真实启动入口仍保留 |
| cache / hook / run_quality_gate 相关测试 | 17.13s | `224 passed` |

## 3.1 继续优化补充结果

| 项目 | 继续优化后 | 说明 |
|---|---:|---|
| 真浏览器 geometry smoke | 9.53s | `2 passed`，仍检查 10 个页面 × 2 个宽度，但每页只开 1 个 Chrome 标签并导航 1 次 |
| scheduler resource dispatch invalid query cleanup | 3.66s | `13 passed`，7 个只读重定向场景共用同一个 test client |
| full-test-debt registry contract | 5.86s | `37 passed`，tracked 文件检查从多次 `git ls-files` 改成一次读取 |
| architecture fitness | 6.58s | `21 passed`，AST 解析增加进程内缓存，但单个最慢扫描仍是主要成本 |
| 本轮受影响慢测试组合 | 47.69s | `128 passed`，包含 browser、startup、scheduler、architecture、registry 等 |

## 4. 本轮实际省下来的时间

| 项目 | Before | After | 约省 |
|---|---:|---:|---:|
| long gate cache 三个自测文件 | 46.53s | 34.24s | 12.29s |
| 两个 startup host/portfile 回归 | 11.38s | 6.01s | 5.37s |
| 真浏览器 geometry smoke | 16.11s | 9.53s | 6.58s |
| scheduler resource dispatch invalid query cleanup | 6.29s | 3.66s | 2.63s |
| full-test-debt registry contract | 6.87s | 5.86s | 1.01s |
| 日常 pre-push 入口 | 200s+ | 2.35s | 主要来自不再日常跑完整 full-test-debt |

## 5. 没有做的事

- 没有跳过 full-test-debt。
- 没有放宽 long gate success cache 或 node cache 校验。
- 没有让非测试文件变更命中 nodeid incremental。
- 没有升级 Python、pytest、Node、Chrome 或引入新依赖。
- 没有删掉 `app.py` / `app_new_ui.py` 的真实启动回归。

## 6. 仍待后续处理的慢点

- 真浏览器 geometry smoke 仍未拆分快测 / 严测，但已经把每页两个 Chrome 标签降为一个标签。
- scheduler batches 页面测试已做 schema 模板库复用，但主要耗时仍在重复创建 app、清理 import cache 和 route 级渲染。
- architecture 已加 AST 进程内缓存，但最慢的 repository bundle drift 扫描仍要继续单独优化。
- 最终 clean-worktree proof 需要在提交或清空工作区后运行完整门禁。
