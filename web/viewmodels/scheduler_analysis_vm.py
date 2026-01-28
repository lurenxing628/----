from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or str(v).strip() == "":
            return int(default)
        return int(float(v))
    except Exception:
        return int(default)


def extract_metrics_from_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    algo = summary.get("algo") if isinstance(summary, dict) else None
    if isinstance(algo, dict):
        m = algo.get("metrics")
        if isinstance(m, dict) and m:
            return m
    return None


def build_svg_polyline(values: List[Tuple[int, float]], *, width: int = 520, height: int = 120, pad: int = 18) -> Optional[Dict[str, Any]]:
    """
    把 (x_label, y) 序列转为简单折线图（SVG polyline）。
    - 不依赖任何外部 JS/库，适合 Win7 离线环境。
    """
    if not values:
        return None
    vals = [(int(x), float(y)) for x, y in values]
    if len(vals) < 2:
        return None

    ys = [y for _, y in vals]
    y_min = min(ys)
    y_max = max(ys)
    rng = (y_max - y_min) if (y_max - y_min) != 0 else 1.0

    xs = [x for x, _ in vals]
    x_min = min(xs)
    x_max = max(xs)
    x_rng = (x_max - x_min) if (x_max - x_min) != 0 else 1.0
    x_span = float(width - 2 * pad)
    y_span = float(height - 2 * pad)

    pts: List[Tuple[float, float]] = []
    for x0, y in vals:
        xx = float(pad) + ((float(x0) - float(x_min)) / float(x_rng)) * x_span
        # y 越大越靠上：反向映射到画布坐标
        yy = float(height - pad) - ((float(y) - float(y_min)) / rng) * y_span
        pts.append((xx, yy))

    points_str = " ".join([f"{round(x, 2)},{round(y, 2)}" for x, y in pts])
    last_xy = pts[-1]
    return {
        "width": int(width),
        "height": int(height),
        "pad": int(pad),
        "points": points_str,
        "y_min": float(y_min),
        "y_max": float(y_max),
        "last_x": float(last_xy[0]),
        "last_y": float(last_xy[1]),
        "x_labels": [x for x, _ in vals],
    }


def score_key(score: Any) -> Tuple[float, ...]:
    """
    attempts 的 score 排序 key（越小越好）。
    - score 为空/不合法时视为 +inf（排到最后）
    """
    if not isinstance(score, list) or not score:
        return (float("inf"),)
    out: List[float] = []
    for x in score:
        try:
            out.append(float(x))
        except Exception:
            out.append(float("inf"))
    return tuple(out)

