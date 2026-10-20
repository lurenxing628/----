# 开发文档总入口

本页只承担两件事：一是把当前仓库中真实存在的开发文档入口串起来；二是把后续子 plan 可以直接复用的开发基线、测试落点与命名契约写清楚。

## 文档导航

建议按下面顺序阅读：

1. 总体开发说明：`./开发文档.md`
2. 系统速查表：`./系统速查表.md`
3. 面板与接口清单：`./面板与接口清单.md`
4. AI 协作约定与默认工作流：`../AGENTS.md`
5. 决策记录目录：`./ADR/`
6. V1.2 方案目录：`./V1.2/`

### 留存备用方案

- [试调、联动重排与条件试算整体方案](../.codestable/roadmap/trial-scenario-planning/trial-scenario-planning-roadmap.md)：2026-10-13 留存，实施未启动。包含行业做法、现有基础、交互与计算设计、性能取舍、分阶段依赖和验收场景；当前优先跑明白已有功能。
- [APS 与项目管理系统的试调实践调研](../.codestable/compound/2026-10-13-explore-aps-trial-scenario-practices.md)：七款产品的具体机制、资源条件试算、共享资料边界及来源。
- [统一优化与业务多方案重构设计](../.codestable/features/2026-10-13-unified-scheduling-optimization/unified-scheduling-optimization-design.md)：待审方案，实施未授权。取消固定图档，保留最多三份有真实业务取舍的方案；涵盖最好结果共享、跨目标去重、总预算、速度质量验收及排产决策工作台衔接。

### 当前排产实测

- [四方案 Mac 实跑与必要性判断](../.codestable/compound/2026-10-13-explore-four-candidate-mac-run.md)：2026-10-13，93 批/858 工序，31.463 秒；包含四方案差异、预算与改善轨迹、重复排程、完整可行性复核和原始数据库。产品实现未修改。

## 开发基线

在仓库根目录先创建项目自己的 `.venv`，再安装运行依赖、开发依赖并启用本地钩子。依赖安装、hook 安装、推送前快门禁都要使用同一个项目 `.venv` Python，避免系统 Python 和项目 Python 不一致：

```powershell
py -3.8 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-optimizer-lite-win7.txt
.venv\Scripts\python tools/install_git_hooks.py
```

说明：

- `requirements.txt` 是程序运行依赖，`requirements-dev.txt` 是本地检查和托管门禁依赖，`requirements-optimizer-lite-win7.txt` 是图分析/候选方案增强需要的轻量优化依赖；新环境三份都要装。
- 上述三份适用于开发检查环境。Win7 出包使用独立 `.venv-win7-build` 和带哈希的 `requirements-win7-build.txt`；离线材料下载、准备和绿色便携构建见 `../DELIVERY_WIN7.md`，不把开发检查工具装入构建环境。
- `PyYAML` 是 CodeStable YAML 工具的开发期依赖；缺失时工具只支持极简 Markdown frontmatter，不能校验 checklist / manifest 这类纯 YAML 文件。
- `ruff` 版本口径固定为 `>=0.15,<0.16`。
- 若未先在项目 `.venv` 中安装 `requirements.txt`、`requirements-dev.txt` 和 `requirements-optimizer-lite-win7.txt`，`.pre-commit-config.yaml` 中的 `ruff`、提交说明检查、推送前快门禁、图分析增强以及本地启动都可能无法正常运行。
- 推送前快门禁必须使用项目 `.venv` 里的 Python；如果项目 `.venv` 不存在，会直接失败，不会偷偷换成系统 Python，并且会强制使用 UTF-8 环境。本地 hook 不是可选检查，正常提交流程不要绕过它。CI/托管环境会重跑完整质量门禁，不过提交标题检查和“暂存区有没有混入本地运行产物”主要靠本地 hook，绕过后不能当作已经通过本地提交检查。

### Codex hook 授权

项目的 `.codex/hooks.json` 将用户输入和命令检查接入同一套授权规则。用户明确说“把全部改动强推到 main”后，本仓库、当前会话内的 `origin/main` 强推直接执行；普通后续消息保留授权。“不要强推”“撤销授权”或“先只读检查”立即收回相应授权。强推还会核对实际推送地址，远端地址或目标分支变化后需要对应的新授权。

其他受保护操作可用明确命令授权，例如“授权执行 `git reset --hard HEAD`”；放行只覆盖这条命令。引用、示例、工具输出、助手文字以及关于强推的提问不会生成授权。授权记录位于当前 worktree 的 Git 目录下 `codex-hook-authorizations/<session_id>.json`，属于本机会话状态。首次部署到已有会话时，hook 核对会话与仓库后读取已有真实用户消息，沿用已给出的授权和撤销；记录核对失败时保留拦截并报告具体原因。

hook 字段与返回协议见 [OpenAI Hooks 文档](https://learn.chatgpt.com/docs/hooks)。`.codex/hooks.json` 和 Python hook 源码随仓库维护，本机 `.codex/config.toml` 保持本地配置。相关行为回归为 `tests/app_runtime/test_codex_hook_authorization.py`，已登记到运行时职责组。

## 质量治理入口

### 日常开发快门禁

```powershell
.venv\Scripts\python scripts/run_daily_quality_gate.py
```

这条命令是给日常开发用的快速检查。它先判断本次改动：只改 README、开发文档或 CodeStable 记录时，只做运行产物拦截和应用启动、离线静态资源两项冒烟；改了 Python 文件时，对还存在的改动文件跑 `ruff check`，并从登记表选择相关职责组；改了公共配置、门禁工具，或判断不出范围时，跑全仓 `ruff check` 和全部保留的 required 测试。

所有选中的测试和尚未覆盖的冒烟节点合并为一次单进程 pytest。已经选中冒烟文件时直接复用该文件的执行，不重复跑节点，也不启动 xdist worker。日常入口由这一次 pytest 收集实际选中的目标；全仓收集证明仍由完整门禁负责。旧 `--workbench-ui-evidence` 浏览器证据入口已退役，保留的 UI Node 契约进入普通 pytest。

pre-push 从 Git 原始输入识别待推送提交，在对应的临时 worktree 执行快门禁；成功缓存绑定目标 refs、影响范围、工具内容和环境。当前 checkout 的无关 README 修改或提交不触发同一目标重测。手工运行且未指定目标 refs 时，缓存仍要求当前工作区干净。

它不是最终 clean proof：不声明 full-test-debt proof，不声明干净工作区证明，也不代表 CI 或收口门禁已经通过。`.pre-commit-config.yaml` 的 pre-push hook 现在默认跑这条快门禁，目的是先挡明显问题，不再让每次日常 push 都完整执行 full-test-debt。

### 统一完整门禁入口

```powershell
.venv\Scripts\python scripts/run_quality_gate.py
```

这只是普通完整门禁入口，不强制检查工作区是否干净，不能当最终 clean proof。

最终收口或托管环境使用：

```powershell
.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

如果已经激活 `.venv`，也可以把上面的 `.venv\Scripts\python` 简写成 `python`。

用途：统一串联下面这些检查，本地与托管只认这一条入口：

1. 收集测试清单，确认测试能被 pytest 发现。
2. 运行 `.venv\Scripts\python tools/check_full_test_debt.py`，确认 full-test-debt 没有新增未登记失败。
3. 检查 `ruff` 和 `pyright` 版本是不是仓库要求的版本。
4. 跑 `radon` 导入检查、`ruff check`、主链 `pyright` 和工具脚本 `pyright`。
5. 从上述完整 pytest 的实际结果验证 required 覆盖，跑治理台账检查与系统速查表一致性检查。启动链回归已纳入统一 required 清单，不再单独重跑；旧架构适应度 pytest 专项已退役。

完整 pytest 直接运行 `tests` 中的全部保留用例，不再用 `-m "not perf"` 排除测试。旧重浏览器、性能基准及门禁元测试已实际删除；纯 Node UI 契约与 API/事务回归一起执行。两个旧浏览器脚本仅保留退役提示，不再提供测试执行或成功报告。

full-test-debt proof 证明当前没有未登记的 full pytest 失败，并且已登记测试债务仍受台账约束；它不代表历史测试债务已经全部修完。

long gate cache 是给长耗时完整门禁准备的本地成功缓存，需要显式传入 `--long-gate-cache` 才会尝试复用。当前 enabled long gate entry 是 `pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`required_regressions`、`debt_ledger_sync`、`quickref_vs_routes`、`import_cycles_production` 和 `import_cycles_with_tests`。旧 `startup_runtime_regressions` 和 `architecture_fitness` 专项 entry 已退役。

完整门禁在同次缓存判定中共享源码快照与工具 metadata；实际命令执行后会重新取得需要刷新的输入证据。`aps-full-selftest` 核验同 HEAD 的干净证明时，可复用仍匹配输入、环境、日志、输出且与本次 receipt 一致的 long-gate 成功结果；缺少或变化的证据继续重放对应命令，未覆盖的独立步骤照常执行。禁用重放仍是 `STRUCTURAL_ONLY`，不能当作通过证明。

完整输入、输出和日志证据由 long-gate 结果缓存与 shared proof 保存；long-gate summary 只保存执行结果、计数、耗时、变更原因和文件引用。旧 `run-final-quality-gate-if-needed` 入口与 `run-final-quality-gate` 一样进入共同 runner，由同一套 long-gate 规则决定复用；原 `.git/aps-hook-cache` 中复制整套完整门禁证据的顶层缓存已退役，历史文件保留原位。

当前 shared proof/receipt 为 schema 4，manifest、current/summary、专项 proof、receipts 和日志写入 `evidence/QualityGate/v4/`；测试收集写入 `evidence/QualityGate/collect_nodeids.v2.json`。long gate 为版本 2，成功/失败缓存分别写入 `evidence/QualityGate/long_gate/results/<entry>.v2.success.json` 与 `<entry>.v2.failure.json`，对应日志和 summary 使用 `.v2` 文件名。单独运行 `.venv\Scripts\python tools/check_full_test_debt.py` 只写本次 v4 current/summary 证明；要生成完整门禁可复用的成功缓存，运行 `.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。旧文件保留原件，缺少原内容的旧摘要缓存首次明确 miss，由新运行生成当前证明。

GitHub Actions 的外层缓存负责运输上次完整门禁留下的运行产物：在门禁前 restore，成功后按 workflow 条件 save。`.github/workflows/quality.yml` 当前仅提供手动 `workflow_dispatch` 触发；保存条件保留 `push` 或 `workflow_dispatch`，当前实际入口为手动运行。restore/save 使用同一 `quality-long-gate-v2` key，由系统、Python 3.8、`github.ref`、既有 `github.sha`、`github.run_id` 和 `github.run_attempt` 定位；restore-prefix 使用同一系统、Python和ref，旧缓存由新前缀隔开。各 Action 的 `uses@SHA` 固定其版本。运输范围包括 `evidence/QualityGate/long_gate/`、`evidence/QualityGate/v4/`、`evidence/QualityGate/collect_nodeids.v2.json` 及保留的旧 proof 路径；artifact 上传覆盖整个 `evidence/QualityGate/`。恢复后的产物是否可复用，继续由仓库内的完整原内容和真实环境判定。

long gate v2 命中前严格比较实际 command、源码原字节、登记内容、公开环境、工具 metadata、runner/tooling 源内容、stdout/stderr 日志、输出 proof、schema 和 repo identity；shared v4 同时以 `run_id`、`command_index`、路径和完整 receipt JSON 绑定本次执行。字节使用可逆 Base64，结构内容使用完整规范 JSON，布尔、整数和浮点保持区别；缺证据或内容变化就重跑对应命令，实际失败状态继续失败。`--long-gate-cache-explain` 给出 run/reuse/planned 判断，summary counts 汇总执行状态，Actions cache hit 表示产物已取回；最终通过仍由当前完整门禁的实际执行与复用核销给出。未登记的新失败继续阻断，已登记测试债务继续受台账约束。需要强制完整重跑时，使用 clean gate 的 `--no-long-gate-cache`；同时排查断点复用时加 `--no-resume`。对外收口、PR 和 CI 的最终证明按 `--require-clean-worktree --long-gate-cache` 或 `tools\git_hook_checks.py run-final-quality-gate` 口径写。

快速静态预检入口是 `.venv\Scripts\python scripts\run_quality_gate.py --fast-precheck`。它只检查本次改动相关的 Python 文件，默认纳入 staged、unstaged、untracked 三类本地改动，并只跑局部 ruff；pyright 默认跳过，因为局部 pyright 不能代表正式 `pyright_gate_full` 或 `pyright_tools_full`。这只是提前提醒，不能当作完整质量门禁、clean proof 或 long gate proof。

Python 3.8 兼容扫描把语法错误、立即求值的不兼容注解和运行时泛型表达式列为阻断项；启用 `from __future__ import annotations` 的函数/模块/类注解若仅在 `get_type_hints()` 或 `eval()` 时有风险，会单列为非阻断提示。函数局部变量注解不求值，不列为运行风险。`tools/scan_py38plus_syntax.py --fail-on-hit` 按阻断项决定退出码，JSON 的 `blocking_findings` 与 `annotation_evaluation_risks` 分别给出两类数量；解析注解的调用方仍须验证真实反射行为。路线图范围扫描排除 Git 删除项及 `.codestable/`、`.limcode/skills/`、`.limcode/hooks/` 宿主工具，不受本机残留旧文件影响。

### 治理台账写入口

```powershell
.venv\Scripts\python scripts/sync_debt_ledger.py check
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode migrate-inline-facts
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode scan-startup-baseline
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields
.venv\Scripts\python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id <debt-id>
```

说明：

- 治理数据唯一事实源：`./技术债务治理台账.md` 的受控 `json` 结构块，当前包含超长文件、高复杂度、静默回退、测试债务和接受风险。
- `scripts/run_quality_gate.py` 只读不写台账。
- `scripts/sync_debt_ledger.py` 是唯一台账写入口；人工治理字段必须通过 `set-entry-fields` 更新，接受风险必须通过 `upsert-risk` / `delete-risk` 维护。
- `set-entry-fields --status` 当前只接受 `open`、`in_progress`、`blocked`、`fixed`。
- 已登记 full pytest 测试债务修好后，不手删结构块；先运行 `mark-test-debt-fixed --debt-id ...` 标成 `fixed`，再由 full-test-debt proof 确认该测试已普通通过且不再带 xfail 标记。
- `test_debt.ratchet.max_registered_xfail` 必须等于当前 active xfail 数；修掉一条并标成 fixed 后，这个数字要随剩余 active xfail 数下降。
- 静默回退门禁当前分两段运行：启动链按四类分类全量冻结；非启动链仅续管历史 `silent_swallow` 遗留项，不把其余分类扩展为全仓新增门禁。

## 测试目录与命名契约

### 可直接复用的测试落点

- 历史兼容回归目录不再作为新增 `main()` 风格脚本的默认落点；当前没有可直接复跑的专项脚本集合，不能把它当成现成回归集合。
- 保留回归按排产、工作台、运行时与页面、数据导入、模型与事务、日历六个职责组登记在 `tools/test_registry_data.py`。旧分散登记模块和 gate meta 测试已退役；`tests/gate_meta/check_quickref_vs_routes.py` 继续作为完整门禁工具使用。

### 命名契约

- `regression_*.py`：历史 `main()` 风格专项回归文件名；仓库当前已移除 main-style 回归收集器，不再新增这类脚本。
- `test_*.py`：用于标准 `pytest` 用例。
- 禁止在 `regression_*.py` 中同时声明 `main()` 与 `test_` 用例；若需要标准 `pytest` 用例，必须改为 `test_*.py` 命名，避免收集遗漏。
- 仓库当前已移除 main-style 回归收集器；不要再新增带 `main()` 的 `regression_*.py` 脚本，新增回归优先写成标准 `test_*.py` 用例并放进对应业务目录。
- 上述契约依赖当前 `tests/conftest.py` 的收集适配保持不变；`SP01` 只补目录、探针与契约，不修改该实现。
- 新增回归优先复用已有业务测试中的场景，确需新文件时写成标准 `test_*.py` 并放进对应业务目录，在统一登记表说明其职责。

## 对 SP02 的承接边界

以下内容已经准备好，并已由 `SP02` 实际接入：

- 可稳定链接的根入口、开发文档入口与审计入口。
- 本地开发与托管检查共用的开发依赖声明。
- 新增专项回归放到对应业务目录，统一登记到 `tools/test_registry_data.py`；不恢复旧门禁元测试目录或第二份目标清单。
- 已明确写清的命名契约，以及它对当前 `tests/conftest.py` 收集适配前提的依赖。
- 统一质量门禁入口 `.venv\Scripts\python scripts/run_quality_gate.py`；只有已经激活 `.venv` 后，才可以简写成 `python scripts/run_quality_gate.py`。
- 唯一台账写入口 `.venv\Scripts\python scripts/sync_debt_ledger.py`；只有已经激活 `.venv` 后，才可以简写成 `python scripts/sync_debt_ledger.py`。
- 治理数据唯一事实源 `./技术债务治理台账.md`。

向 `SP03` 的直接交接点：

- 启动链基线已冻结到治理台账，后续优先做真实治理，不再重复搭基础设施。
- `web/ui_mode.py` 已按 `startup_guard` / `render_bridge` 分 scope 落账；其中 `render_bridge` 条目继续留给 `SP09`。
- 文档一致性检查已具备阻断语义，后续只需保持实现与速查表同步。

## Pyright 门禁补充

```powershell
.venv\Scripts\python -m pyright --version
.venv\Scripts\python -m pyright -p pyrightconfig.gate.json
.venv\Scripts\python -m pyright -p pyrightconfig.tools.json
.venv\Scripts\python -m pyright -p pyrightconfig.json
```

- `pyright` 版本口径固定为 `==1.1.406`，以 `requirements-dev.txt` 为准。
- `.pre-commit-config.yaml` 安装后会管三件事：提交前跑 `ruff` 和本地临时文件拦截，提交说明阶段拦截过于含糊的标题，推送前快门禁会通过 `tools/git_hook_checks.py run-quality-gate` 使用项目 `.venv` Python 调用 `scripts/run_daily_quality_gate.py`。如果要手动跑最终完整门禁，可以用 `.venv\Scripts\python tools\git_hook_checks.py run-final-quality-gate`，它仍会调用 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 手动快速静态预检可以用 `.venv\Scripts\python tools\git_hook_checks.py run-fast-static-precheck`。它不会改变 `run-quality-gate` 的 daily fast gate 语义，也不会改变 `run-final-quality-gate` 的完整 clean gate 语义。
- 推送前快门禁必须使用项目 `.venv` 里的 Python；如果项目 `.venv` 不存在，会直接失败，不会偷偷换成系统 Python，并且会强制使用 UTF-8 环境。本地 hook 不是可选检查，正常提交流程不要绕过它，绕过后不能当作已经通过本地提交检查。
- `pyright` 不在提交前单独快跑，它由 `scripts/run_quality_gate.py` 和 CI 阻断。
- `scripts/run_quality_gate.py` 包含全仓测试收集、`python tools/check_full_test_debt.py`、工具版本与依赖检查、`ruff check`、主链与工具脚本 `pyright`、import cycle 检查、Python 3.8 语法检查、必需回归结果复用、治理台账检查与速查表核对。
- `pyrightconfig.gate.json` 覆盖 `app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/` 主链，类型检查目标固定为 Windows / Python 3.8，与产品目标一致。
- `pyrightconfig.tools.json` 覆盖门禁和维护脚本，是 `pyright_tools_full` 的正式工具脚本门禁口径。
- `pyrightconfig.json` 保留为全仓类型债务盘点入口，包含 `tests/` 等更宽范围，不直接作为本轮硬门禁。
- 上面这些 Pyright 命令只适合定位问题，不能当成最终 clean proof。最终 clean proof 需要在干净工作区跑 `.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，并且门禁结束后 `git status --short` 仍然没有输出。
- 本地 hook 会拦截已登记的运行产物，例如 `.DS_Store`、`.iris/`、`.playwright-mcp/`、`.limcode_*`、`launcher.log`、任意子目录里的 `launcher.log`、`logs/aps_host.txt`、`logs/aps_port.txt`、`logs/aps_db_path.txt`、`logs/aps_runtime.json`、`logs/aps_runtime.lock`、`logs/aps_secret_key.txt`、`evidence/FullSelfTest/pytest_tests_output.txt` 和 `aps_test.db*`。当前 shared v4 的全部 proof、receipts 和日志由 `evidence/QualityGate/v4/` 统一匹配，long gate v2 的缓存、日志和 summary 由 `evidence/QualityGate/long_gate/` 匹配，测试收集匹配 `evidence/QualityGate/collect_nodeids.v2.json`；`.gitignore` 与 hook 保留旧 proof/collect 路径规则，并追加上述新路径。门禁运行产物从源码提交中排除。
