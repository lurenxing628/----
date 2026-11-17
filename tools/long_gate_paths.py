from __future__ import annotations

import os
from dataclasses import dataclass

LONG_GATE_CACHE_DIR_REL = os.path.join("evidence", "QualityGate", "long_gate").replace("\\", "/")
LONG_GATE_RESULTS_DIR_NAME = "results"
LONG_GATE_LOGS_DIR_NAME = "logs"
LEDGER_REL = "开发文档/技术债务治理台账.md"


def resolve_repo_root() -> str:
    """门禁工具所属仓库根的唯一解析：tools/ 的上一级。

    各 CLI 入口调用一次，再把根显式传给库函数；外部 CLI 指定的目标仓库（如 Git toplevel、cwd）不走这里。
    """
    return os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


@dataclass(frozen=True)
class GateContext:
    """一次门禁运行的仓库上下文；台账路径由同一个根派生，不另存第二份来源。"""

    repo_root: str

    @property
    def ledger_path(self) -> str:
        return os.path.join(self.repo_root, LEDGER_REL.replace("/", os.sep))


def real_repo_root(repo_root: str) -> str:
    return os.path.realpath(os.path.abspath(repo_root))


def is_within_repo(abs_path: str, repo_root: str) -> bool:
    """路径解析符号链接后等于 repo_root 或位于其下；Windows 上按 normcase 比较，大小写不同的同一路径算同一处。"""
    root = os.path.normcase(real_repo_root(repo_root))
    real_path = os.path.normcase(os.path.realpath(os.path.abspath(abs_path)))
    return real_path == root or real_path.startswith(os.path.join(root, ""))


def resolve_repo_path(repo_root: str, path: str, *, description: str = "cache path") -> str:
    root = real_repo_root(repo_root)
    raw_path = str(path or "").replace("\\", "/")
    if not raw_path:
        raise ValueError(f"{description} is empty")
    if os.path.isabs(raw_path):
        abs_path = os.path.realpath(raw_path)
    else:
        abs_path = os.path.realpath(os.path.join(root, raw_path.replace("/", os.sep)))
    if not is_within_repo(abs_path, root):
        raise ValueError(f"{description} escapes repo root: {raw_path}")
    return abs_path

