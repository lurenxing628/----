# 测试/门禁提速 + 可复现性 治本方案讨论纪要（2026-06-08）

> 7 维度 ×（recon + 对抗审查）= 14 agent 讨论产物，所有提案喂同一份实测真相源（避免各自瞎测自污染）。
> 当前在 `debt/phase4-underwater` 分支、B(80 债) 执行中，故每条标注 `can_do_during_B`。

## 0. 实测真相源（10 核 mac，.venv，2026-06-08）

| 指标 | 实测 | 含义 |
|---|---|---|
| collect-only 全量 | **0.85s** / 3800 | collect 非瓶颈 |
| 裸解释器启动 | 0.01s | 启动非瓶颈 |
| `pytest tests/ -n auto` 全量墙钟 | **70.2s**（user 446s，6.4x） | 纯并行已很快 |
| `check_full_test_debt --sharded 3`（= full gate 第 2 步） | **188s** | serial 串行 113s + parallel 3 进程 75s |
| 长尾 durations | 浏览器 E2E 21.9s / runtime_stop_cli 12s / startup_host 4.7+4.1s / chrome_probe 3.2s | 真起进程/浏览器 |
| xdist 全并行 | **2 FAIL** | 全局态污染（固定端口 5788 + 模块全局属性竞态） |

## 1. 颠覆性认知（讨论最大产出）

### ① “全量测试慢”和“full gate 188s”是两个不同的问题
- 裸 `pytest -n auto` 早已是 **70s**。
- full gate 188s 慢在自研分片：**serial worker 串行先跑 113s（占墙钟 60%）** + parallel 只开 3 进程（75s）。

### ② full gate 不能简单上 xdist —— 收据架构与 xdist 进程模型不兼容（致命假绿）
full gate 的债务收据由 `tools/collect_full_test_debt.py` 的 `FullTestDebtCollector` in-process plugin 的 `pytest_runtest_makereport` hookwrapper 产出（读 `item`/`call` 算 `strict_xpass`/`xfail_marker_*`）。
**该 hook 在 xdist 下只在 controller 端触发、对远端 worker 执行的用例不触发**（对抗审查实测探针：in-process reports=10，`-n2` 时 controller 端 makereport=0、reports=0）。

→ 给 worker 的 `pytest.main` 加 `-n auto`，worker payload 的 reports 直接为空。`collected_nodeids` 仍由 controller 单进程 `--collect-only` 产出恒非空（**绕过** 空集硬失败护栏）；required 缺 reports 会 `RequiredRegressionProofError` 硬失败（loud，挡得住）；**但非 required 用例的 `strict_xpass` / xfail-marker 漂移信号被静默吞掉 = 假绿**（登记的债务测试偷偷开始通过，门禁看不到）。

→ 所有“给 full gate worker 加 xdist”的提案（含初判“最小改、最高确定性”的 P1）**全部被对抗审查否决**。“裸 pytest 70s / 0 fail”是用没走收据管道的裸 pytest 量的，**不能外推到门禁收据正确性**。

### ③ CI 真门禁 = windows-latest + Python 3.8（`.github/workflows/quality.yml`）
所有方案须过这道门：pytest-forked 不可用（POSIX-only）、testmon 须钉 py3.8 EOL 旧版、full gate 永远全量。

### ④ B 期间 long_gate 缓存基本失效
full_test_debt / pytest_collect_all / required / startup 这 4 个最贵条目的 input scope 都含 `tests/**/*.py` + `conftest.py`，B 每个 commit 必失效全跑。源码类条目（ruff/pyright/...）仍能命中。

### ⑤ fixture 提速的现实墙钟上限是“个位数秒”，不是倍数级
被 `-n auto` 10 核摊薄。真正每测试最大单项成本是 `ensure_excel_templates`（db_env 每测试新建**空**模板目录 → 白写 11 个 xlsx，实测 ~90–188ms/测试），**不是 import、不是 fixture scope**。

## 2. 生存方案（按可落地排序）

### A. 立即可做（不碰 conftest/tests、与 B 并行、零隔离风险）
| # | 方案 | 收益 | 证据 |
|---|---|---|---|
| **A1** | **`requirements-dev.txt` 精确锁** 到当前黄金版本：pytest==8.3.5 / pytest-cov==5.0.0 / radon==6.0.1 / pre-commit==3.5.0 / ruff==0.15.11 / execnet==2.1.2 / PyYAML==6.0.3（现在 pytest/pytest-cov/radon/pre-commit **完全无版本号**） | 消除“别人 pip install 装到不同 pytest/ruff/pyright 次版本 → 门禁假绿/假红、收集顺序漂移”的最大可复现性暗债，是“谁来跑都一致”的根 | measured |
| **A2** | **full gate parallel shard `--shard-count` 3 → 7~8**（改 `tools/.../quality_gate_shared` 数值，每片仍单进程 pytest，**绕开 makereport 假绿陷阱**） | parallel 段 3026 用例并行度翻倍吃满 10 核；188 → 约 **120–150s**（serial 113s 是天花板不变） | inferred，须 benchmark |
| **A3** | **本地默认跑 daily + 文档化分层契约**（run_daily 已 print “not final clean proof”，把约定钉进文档/help） | 0 秒提速，但消除“本地误跑 full 卡 188s”+“误把 daily 当 clean proof”两类人因失误 | measured |

### B. 须等 B 收尾（碰 conftest/tests，与 B 改动同树会撞车）
| # | 方案 | 收益 |
|---|---|---|
| B1 | db_env 改用 session 级预生成的共享 Excel 模板目录（不再每测试白写 11 个 xlsx） | create_app 210→119ms；并行墙钟省 ~0.3–0.6s。**最干净** |
| B2 | create_app 加测试期跳过模板校验开关 | create_app 210→31ms（动生产 `factory.py`，test-only 分支耦合气味，flag 须默认关） |
| B3 | stub 化 chrome_probe spawn 用例（`test_ui_browser_geometry_env.py`） | 3.48s→0.05s，且去本机 Node/Chrome 依赖让 CI/干净机器结果一致 |
| B4 | conftest 给裸 `-n auto` 装护栏（deselect serial，签名须扩 `(config, items)` 否则静默假绿） | 消除人工裸 `-n auto` 的 2 个 flaky FAIL；门禁本不裸跑、墙钟零收益 |
| B5 | Chrome/Node 在干净 CI 默认 skip 开关（`ui_geometry_runtime_support.py`） | 干净 CI 不因 `CI=true` 误判 FAIL（须人拍板：可复现 vs 覆盖度，保留 `APS_BROWSER_SMOKE_REQUIRED=1` 专用 job 兜底） |

### C. 真治本但 blast 最大（唯一能把 full gate → ~70s 的路径）
| # | 方案 | 说明 |
|---|---|---|
| **C1** | **`FullTestDebtCollector` 改写为 xdist-aware**：`pytest_runtest_makereport`(读 item/call) → `pytest_runtest_logreport`(读可序列化 `TestReport.wasxfail`/`outcome`/`keywords`，`-n2` 实测 controller 端能收全 report) + 全套 xfail/strict-xpass 语义回归对账 | 收据重写后 full gate worker 才能安全上 xdist，188 → 逼近 70s。**非平凡工程**，须等 B 收尾单独立项；ROI 由用户决策 |

## 3. 一致否决（不做，附核实理由）
- **lazy-openpyxl**：create_app 在 `factory.py:268` 无条件调 ensure_excel_templates 立即需要 openpyxl，lazy 只挪位置零收益、反把 import 期失败延后成运行时失败
- **--import-mode=importlib**：零提速（实测 +1.6% 在噪声内），仅未来防重名（当前 0 重名 basename，无迫切）
- **-p no:cacheprovider**：<30ms，且丢 `--lf`/`--ff`/`--cache-show`
- **pytest-testmon**：py3.8 EOL（须钉 2.1.x 旧版）+ `.testmondata` 跨机不一致 = 假绿（撞“谁来跑都一致”红线）+ full gate 永远全量零收益
- **pytest-split**：单 windows CI runner，无多机可分发
- **pytest-forked**：Windows CI 不可用（POSIX fork）
- **提 db_path/schema_conn/mem_conn scope**：104 个写库测试污染风险 >> <0.65s 串行收益（并行后近 0）
- **session 复用单 app**：app 冻结 LOG/BACKUP/TEMPLATE_DIR 全套 config，只改 DB 路径会串台、worksteal 下蓝图/g 残留
- **full gate 步间并行**：破坏 resume 续跑前缀契约 + receipt 身份校验 = 假绿隐患，pyright 两进程并发吃内存
- **缓存指纹 scope 收窄**：full_test_debt 是全量债唯一真相源，收窄 = 改了测试但缓存说没事 = 漏回归假绿
- **拆固定端口 5788 / repo_root/logs**：契约文件位置由**生产** `web/bootstrap/paths.py:runtime_base_dir(anchor_file=app.py)` 硬锚定到 app.py 目录、**不读 APS_LOG_DIR**，测试无法靠环境变量搬 tmp，serial 归属是生产设计的必然 → 保持 serial 现状

## 4. 推荐执行序
1. **现在（B 并行，零风险）**：A1 → A3 → A2（配 benchmark 验证收益数字）
2. **B 收尾后**：B1 / B3（最干净）→ B4 / B5 → B2
3. **专项立项决策**：C1（要不要把 full gate 真正拉到 70s，看 ROI）

## 5. 一句话诚实结论
> 在 **B 执行期间、不冒假绿风险**的前提下，full gate 188s 最多降到 ~150s（A2）；要降到 70s 必须做 C1 收据重写大工程。
> 但**“谁来跑都不出错”现在就能大幅改善**：A1 锁版本（根因暗债）+ A3 文档化分层 + B 收尾后的 B4/B5 护栏。
> 测试本身（裸 `-n auto` 70s）并不慢——慢的是 full gate 的自研收据分片，而它慢得有原因（收据完整性），不是单纯没并行。
