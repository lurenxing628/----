# NetworkX 阶段 1 可选依赖验证

- 日期：2026-05-17
- 执行人：AI assistant
- 仓库分支：feature/networkx-scheduler-graph
- 仓库 commit：cab8d12d4a485d30ed38214982ea9621226eb697
- 工作树状态摘要：执行前已有 `.limcode/progress.md` 修改；本阶段新增 `requirements-optimizer-lite-win7.txt` 与 `evidence/scheduler_graph/phase1/` 下证据文件。`vendor/wheels/` 按 `.gitignore` 策略仅作本地 wheelhouse，不纳入提交。

## 1. 阶段 0 前置证据

检查命令摘要：

```bash
test -f evidence/baseline_pip_freeze_before_networkx.txt
test -f evidence/scheduler_baseline/02_pip_freeze_before_networkx.txt
test -f evidence/scheduler_baseline/case_001_normal_result.json
test -f evidence/scheduler_baseline/case_002_urgent_result.json
test -f evidence/scheduler_baseline/case_003_external_result.json
test -f "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "networkx==3.1" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "不安装 `networkx\[default\]`" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
```

输出摘要：

```text
OK file: evidence/baseline_pip_freeze_before_networkx.txt
OK file: evidence/scheduler_baseline/02_pip_freeze_before_networkx.txt
OK file: evidence/scheduler_baseline/case_001_normal_result.json
OK file: evidence/scheduler_baseline/case_002_urgent_result.json
OK file: evidence/scheduler_baseline/case_003_external_result.json
OK file: 开发文档/ADR/0012-networkx-排产依赖图建模.md
OK ADR contains networkx==3.1
OK ADR contains no networkx[default] statement
```

结论：阶段 0 before_networkx 证据存在，ADR-0012 依赖结论存在。

## 2. Python 环境

```text
python3.8 --version 输出：
Python 3.8.10

sys.version 输出：
3.8.10 (v3.8.10:3d8993a744, May  3 2021, 09:09:08)
[Clang 12.0.5 (clang-1205.0.22.9)]

platform.architecture 输出：
('64bit', '')

当前系统：macOS 25.4.0 arm64
```

说明：本次验证使用 macOS 开发机上的 Python 3.8 x64 解释器完成依赖安装、API smoke 与离线 wheel 安装验证；不是 Win7 实机/虚拟机证据。Win7 实机离线验证如作为发布验收要求，应在目标机补充同类输出。

## 3. 可选依赖文件

新增文件：`requirements-optimizer-lite-win7.txt`

```text
# Optional scheduler graph-analysis dependency.
# Windows 7 x64 + Python 3.8.x compatibility target.
# NetworkX 3.1 is the last NetworkX release supporting Python 3.8.
# Install this file only when graph_analysis_mode=report/on is being validated.
# Keep the dependency pure Python and lightweight; do not install optional NetworkX extras.
networkx==3.1
```

确认：

- [x] 未修改 requirements.txt
- [x] 未修改 requirements-dev.txt
- [x] 未使用 networkx[default]
- [x] 未使用 networkx[all]

备注：为了让禁止 extras 的 grep 门禁可以严格通过，注释中未写入 `networkx[default]` / `networkx[all]` 字面量，改用 “optional NetworkX extras” 表述。

约束检查输出：

```text
OK optional dependency constraints passed
```

## 4. 隔离 venv 安装验证

命令摘要：

```bash
rm -rf /tmp/aps_nx_probe_py38 /tmp/aps_nx_probe_freeze.txt
python3.8 -m venv /tmp/aps_nx_probe_py38
/tmp/aps_nx_probe_py38/bin/python -m pip install --no-cache-dir -r requirements-optimizer-lite-win7.txt
/tmp/aps_nx_probe_py38/bin/python -m pip check
/tmp/aps_nx_probe_py38/bin/python - <<'PY'
import sys
import networkx as nx
from networkx.algorithms import bipartite

print("python=", sys.version)
print("networkx=", nx.__version__)
print("networkx_file=", nx.__file__)
assert nx.__version__ == "3.1"

G = nx.DiGraph()
G.add_node("A", duration_minutes=10)
G.add_node("B", duration_minutes=20)
G.add_edge("A", "B", weight=20)
assert nx.is_directed_acyclic_graph(G)
assert list(nx.topological_sort(G)) == ["A", "B"]
assert nx.dag_longest_path(G, weight="weight") == ["A", "B"]
assert nx.dag_longest_path_length(G, weight="weight") == 20

C = nx.DiGraph()
C.add_edge("A", "B")
C.add_edge("B", "A")
assert not nx.is_directed_acyclic_graph(C)
try:
    nx.find_cycle(C, orientation="original")
except nx.NetworkXNoCycle:
    raise AssertionError("cycle should be detected")

B = nx.Graph()
B.add_node("op:1", bipartite="operation")
B.add_node("machine:M1", bipartite="machine")
B.add_edge("op:1", "machine:M1")
matching = bipartite.maximum_matching(B, top_nodes={"op:1"})
assert matching["op:1"] == "machine:M1"

print("OK: networkx phase1 isolated probe passed")
PY
/tmp/aps_nx_probe_py38/bin/python -m pip freeze > /tmp/aps_nx_probe_freeze.txt
grep -Ei '^(numpy|scipy|pandas|matplotlib|pydot|pygraphviz)==' /tmp/aps_nx_probe_freeze.txt
cat /tmp/aps_nx_probe_freeze.txt
rm -rf /tmp/aps_nx_probe_py38
```

输出摘要：

```text
Collecting networkx==3.1
Downloading networkx-3.1-py3-none-any.whl (2.1 MB)
Successfully installed networkx-3.1
No broken requirements found.
python= 3.8.10 (v3.8.10:3d8993a744, May  3 2021, 09:09:08)
[Clang 12.0.5 (clang-1205.0.22.9)]
networkx= 3.1
networkx_file= /private/tmp/aps_nx_probe_py38/lib/python3.8/site-packages/networkx/__init__.py
OK: networkx phase1 isolated probe passed
== isolated freeze ==
networkx==3.1
```

结论：通过。

## 5. 重依赖检查

隔离 venv `pip freeze`：

```text
networkx==3.1
```

确认：

- [x] 未安装 numpy
- [x] 未安装 scipy
- [x] 未安装 pandas
- [x] 未安装 matplotlib
- [x] 未安装 pydot/pygraphviz

## 6. 离线 wheel

下载命令：

```bash
mkdir -p vendor/wheels
python3.8 -m pip download --only-binary=:all: --no-deps --dest vendor/wheels networkx==3.1
```

manifest 生成命令：

```bash
mkdir -p evidence/scheduler_graph/phase1
python - <<'PY'
from pathlib import Path
import hashlib

wheel_dir = Path("vendor/wheels")
out = []
for path in sorted(wheel_dir.glob("networkx-3.1-*.whl")):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    out.append(f"{path.name}\tsha256={digest}\tsize={path.stat().st_size}")

if not out:
    raise SystemExit("networkx wheel not found")

Path("evidence/scheduler_graph/phase1/networkx_3_1_wheel_manifest.txt").write_text(
    "\n".join(out) + "\n",
    encoding="utf-8",
)
print("\n".join(out))
PY
```

wheel 信息：

```text
wheel 文件名：networkx-3.1-py3-none-any.whl
SHA256：4f33f68cb2afcf86f28a45f43efc27a9386b535d567d2127f8f61d51dec58d36
size：2072251
```

已写入：`evidence/scheduler_graph/phase1/networkx_3_1_wheel_manifest.txt`

## 7. 离线安装验证

命令：

```bash
rm -rf /tmp/aps_nx_offline_probe_py38
python3.8 -m venv /tmp/aps_nx_offline_probe_py38
/tmp/aps_nx_offline_probe_py38/bin/python -m pip install --no-index --no-cache-dir --find-links=vendor/wheels networkx==3.1
/tmp/aps_nx_offline_probe_py38/bin/python -c "import networkx as nx; print(nx.__version__); assert nx.__version__ == '3.1'"
/tmp/aps_nx_offline_probe_py38/bin/python -m pip check
rm -rf /tmp/aps_nx_offline_probe_py38
```

输出摘要：

```text
Looking in links: vendor/wheels
Processing ./vendor/wheels/networkx-3.1-py3-none-any.whl
Installing collected packages: networkx
Successfully installed networkx-3.1
3.1
No broken requirements found.
```

结论：通过。该命令使用 `--no-index --find-links=vendor/wheels`，验证过程不依赖互联网安装源。

## 8. 项目 venv 状态

- [x] 未安装 NetworkX 到项目 venv
- [ ] 已安装 NetworkX 到项目 venv，并已生成 evidence/baseline_pip_freeze_after_networkx.txt

说明：本阶段只使用 `/tmp/aps_nx_probe_py38` 与 `/tmp/aps_nx_offline_probe_py38` 两个隔离临时 venv，执行后均已删除；未生成 `evidence/baseline_pip_freeze_after_networkx.txt`。

## 9. 阶段 1 结论

结论：通过（macOS 开发机 Python 3.8 x64 隔离安装、NetworkX API smoke、重依赖检查、wheel SHA256 留痕、离线 wheel 安装验证均通过）。

阻塞项：无。

后续动作：如发布验收要求 Win7 实机/虚拟机正式证据，需要把 `vendor/wheels/networkx-3.1-py3-none-any.whl` 拷贝到 Win7 x64 + Python 3.8 环境后，重复 `--no-index --find-links` 离线安装验证，并把输出追加到本文档。
