from __future__ import annotations

import os
import sys
from typing import List


def bootstrap_vendor_paths(base_dir: str) -> List[str]:
    """
    将交付目录下的 vendor/ 注入到 sys.path（用于 Win7 离线“可选依赖包”投放）。

    兼容常见结构：
    - vendor/
    - vendor/site-packages/
    - vendor/Lib/site-packages/（某些 pip --target 的结果）
    """
    base = os.path.abspath(base_dir or ".")
    candidates = [
        os.path.join(base, "vendor"),
        os.path.join(base, "vendor", "site-packages"),
        os.path.join(base, "vendor", "Lib", "site-packages"),
    ]
    added: List[str] = []
    for p in candidates:
        try:
            ap = os.path.abspath(p)
            if os.path.isdir(ap) and ap not in sys.path:
                sys.path.insert(0, ap)
                added.append(ap)
        except Exception:
            continue
    return added

