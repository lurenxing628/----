from __future__ import annotations

from typing import Any, Dict, List

from core.services.common.degradation import DegradationCollector


def record_diagnostic(
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
    *,
    code: str,
    scope: str,
    field: str,
    message: str,
    sample: Any,
) -> None:
    collector.add(
        code=code,
        scope=scope,
        field=field,
        message=message,
        sample=(str(sample)[:200] if sample is not None else None),
    )
    bucket = samples.setdefault(str(code), [])
    if len(bucket) >= 10:
        return
    try:
        bucket.append(sample)
    except Exception:
        bucket.append(str(sample))
