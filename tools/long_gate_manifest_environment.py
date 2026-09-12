"""Select declared test environment inputs without promoting supplemental tests."""

from __future__ import annotations

from typing import List, Optional, Sequence

from tools import test_registry
from tools.long_gate_fingerprint import RUNTIME_FINGERPRINT_KEYS


def registry_test_environment_keys(targets: Optional[Sequence[str]] = None) -> List[str]:
    groups = test_registry.iter_required_regression_groups()
    groups.extend(test_registry.iter_required_regression_groups(
        test_registry.SUPPLEMENTAL_REGRESSION_GROUPS
    ))
    selected = None if targets is None else set(test_registry.normalize_test_paths(targets))
    # Collection observes environment-dependent marks/parameters, not runtime probes.
    return sorted({
        key for group in groups
        if selected is None or selected.intersection(group["target_paths"])
        for key in group["env_keys"] if key not in RUNTIME_FINGERPRINT_KEYS
    })


def full_debt_environment_keys(args: Sequence[str]) -> List[str]:
    keys = registry_test_environment_keys()
    # check_full_test_debt uses these fallbacks only without explicit CLI options.
    if "--sharded" not in args:
        keys.append("APS_FULL_TEST_DEBT_SHARDED")
    if not any(arg.split("=", 1)[0] == "--shard-count" for arg in args):
        keys.append("APS_FULL_TEST_DEBT_SHARD_COUNT")
    return keys
