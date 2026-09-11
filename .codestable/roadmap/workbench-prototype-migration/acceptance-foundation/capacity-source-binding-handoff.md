# Capacity 私有源绑定交接

状态：文件级验证完成；尚未运行新的私有 managed host 或正式 5000。日期：2026-09-11（Asia/Shanghai）。

## 结论与范围

- `final_capacity_probe.py` 的原输入哈希观察器不负责拒绝 origin 读取，`final_capacity_server.py` 原先只调整 `sys.path`；这两个入口现接入真实私有源绑定。
- 复用 G 原样的 `FrozenSourceGuard`（schema_version 2、静态 manifest、SHA/mode、全部文件/namespace/alias、限定 sys.path）和 foundation 原样的 SourceGuard（原树 open/list/SQLite、源码只读、正常 Python 运行时依赖例外）。额外把模块 `__spec__.origin` 送入同一 G 路径检查，不添加名字前缀兜底。
- 正式入口缺少绑定，或 expected root/origin/manifest SHA 不一致，在创建 runtime/数据库、导入 host 前拒绝。协调进程要求两个真实子 PID 的 before/after 回执均 enabled、verified，且 PID/root/origin/manifest 匹配，才能继续报正式成功。
- 未绑定的小档沿用原非正式入口；新增证据明确写 `enabled=false, verified=false`，不会因此取得正式证明。
- 不修改 Main CLI loading 合同、G/foundation 原守卫、产品代码、排产负载参数、时间阈值或 registry。

## 四个代码文件

| 文件（仓库相对路径） | SHA-256 |
| --- | --- |
| tests/workbench/final_capacity_binding.py | b10af534f90882b59f14eafbb5d63b24647390a6ef7a5306f689f850cbcc1d2a |
| tests/workbench/final_capacity_probe.py | 0556c85817a2bc443e38a428d520cbd64e8b1d57a3bd6ea39cfd1536adcf0dea |
| tests/workbench/final_capacity_server.py | 3d8beceb5056e21e4c8cebcaabdf93a7965f0ad774dc48b479f93b3a0853d3fb |
| tests/workbench/test_final_capacity_source_binding.py | 1f8849a6521826394897b1ef8ceeb9da1811bdcf8f7119c4e85b9aeb51deb521 |

`final_capacity_binding.py` 和 `test_final_capacity_source_binding.py` 是本轮新增；另两文件只加来源绑定、证据校验和必要的 host 导入顺序。

## 最终运行协议

Main 提供独立 `source/`、同一 private parent 下的 `harness/`、完整 source manifest 和独占窗口。不要在 F 或其他任务正在运行的 source 上覆盖。

需要四项环境变量：

- `FACTORY_SOURCE_MANIFEST`：Main 新绑定 manifest 的绝对路径。
- `WORKBENCH_CAPACITY_EXPECTED_SOURCE_ROOT`：当前执行入口所属的独立 source 绝对路径，必须与 manifest.root、入口实际 REPO 相同。
- `WORKBENCH_CAPACITY_FORBIDDEN_ORIGIN`：明确禁止回落的原树绝对路径，必须与 manifest.origin_root 相同，不能与 source 嵌套或相同。
- `WORKBENCH_CAPACITY_MANIFEST_SHA256`：上述 manifest 文件的实际 SHA-256。

manifest 必须包含 source 下这三个原始 G 文件，capture 时逐个作为精确 `--extra`：

```text
.codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_guard.py
.codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_binding.py
.codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_inventory.py
```

将同三文件机械复制到 `source.parent/harness/`，文件 SHA、bytes、mode 必须与 manifest 内对应原文件相同；不是从原树运行这些 harness 文件。其余 manifest 按 G 原 capture/check 协议生成，不通过删输入获得通过。原 venv 是只读依赖例外，不把整个原 repo 加入运行时白名单。

原 CLI 参数不变，由 Main 独占窗口给实际值再执行：`--batches 100 --operations 50 --exclusive-window ... --asset-root ... --output ...`。本轮未给任何窗口值，也未执行此命令。

证据：

- 协调进程 `result.json.source_binding.before/after`。
- 每个 host session 的 `capacity-source-binding.json`；协调进程校验后带入 shutdown/restart_shutdown。
- 原 `product-input-proof.json` 仍保留原明确范围，与新增的完整 source manifest 证明分开。

## 验证

命令（当前原 venv Python 3.8.10，完整正常 conftest）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/aps-capacity-binding-B.P2d5HX/pycache .venv/bin/python -B -m pytest -q --tb=short -p no:cacheprovider tests/workbench/test_final_capacity_source_binding.py tests/workbench/test_final_capacity_inputs.py tests/workbench/test_final_capacity_cli_loading.py tests/workbench/test_final_capacity_contract.py -k 'not seed_retains and not full_payload' --basetemp=/private/tmp/aps-capacity-binding-B.P2d5HX/pytest-g-capture-final --junitxml=/private/tmp/aps-capacity-binding-B.P2d5HX/g-capture-final.xml
```

- **56 passed, 7 deselected in 10.40s**；32 项为新来源绑定测试，24 项为原文件冻结、CLI 和参数/保留合同。
- 7 项 deselected 是本轮明确不执行的实际排产计算用例，不是跳过来源检查，也未改原断言。
- 实际负测包括原树文件/SQLite/动态导入、symlink、alias、namespace、spec-only origin、未列入 manifest 的本地模块、源码写入、缺少或错误绑定、前后 bytes/mode 漂移、未启用或 PID/root/origin 错配的子回执。
- 正例使用 G 原 capture 脚本生成小型 fixture 的完整 manifest，实际导入私有叶模块/alias/namespace 和现有 venv Flask，读取合法依赖；不是浏览器或完整工厂证明。
- 四文件 Ruff 通过；Pyright 0 errors、0 warnings。不升级解释器或依赖。
- 原始 JUnit：`/private/tmp/aps-capacity-binding-B.P2d5HX/g-capture-final.xml`，SHA `8ed9f20107e055487e205586b68ab695a154033a4266b4a2e3bf0384a680b93a`。先前 56 项通过的 `file-final.xml` 也保留，最终以本次 G capture 版本为准。
- 先前 fixture 缺少不存在的 `tests/__init__.py`、负测脚本文本替换错误均已修复；失败回执 `file-01.xml`、`file-03.xml` 保留，未改写成通过。

## 保留证明与 H 登记增量

- 根 `common/` 不存在；真实 `core/services/common/` 已被原 core 递归覆盖。为错误根假设加的本轮变更全部撤回，不添加虚构 registry scope/gap，不降格旧 1472 输入证据。
- `final_capacity_sources.py` SHA `7dcc1a2d08cc1b6c5e62ae87fd4da5589ade6d2171b726f48093b357cacf9c23`，`test_final_capacity_inputs.py` SHA `33ecfe2b94f638be5caf7aa01aa9ef9fbe7a262805dda4014588a9a3e8ea0929`，均与旧 F13-source9 B-owned 封板副本字节一致。
- `final_capacity_support.py`、`final_capacity_observation.py` 与同一旧副本 SHA 一致；`accept_and_poll`、`read_all_candidates`、`_verify_managed` 的完整 AST 相同。未改 180 秒、100×50、四候选、资源/工时/数量、事务或重启保留断言。
- Main CLI 当前 SHA `b4f3353c48cf44e4430f8630393dc1addbffee2ac27e1aaa47f84aa3cb132272`，本轮未编辑，原 3 项加载/转发测试均通过。
- H：建议将新增 `test_final_capacity_source_binding.py` 放入既有唯一 owner `workbench_run_compute_capacity`，不新建 group；两个既有 capacity 组的共享输入增量为新 binding helper、既有 foundation source guard、上述三个 G 源文件。live_environment 和其他 capacity 文件原已登记，不重复扩大。
- H：两个 capacity 组增加上述四项环境键。测试 fixture 使用列出的真实七个 B/helper 文件及 G 三个文件，私有目录中生成小型 schema-v2 manifest 和叶模块，不增加正式工作负载。
- 本轮未提交；现有 dirty worktree 和他人的 staged/untracked 保持原样。只有文件级/参数验证，不能称 clean-worktree proof、最终 HEAD proof 或新正式 5000 证明。
