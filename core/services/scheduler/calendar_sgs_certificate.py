"""Native calendar cache certificates; no policy read or database query is skipped."""

from core.algorithm_runtime.native_snapshot import UNSUPPORTED, make_class_guard, scalar_tuple_snapshot

from .calendar_engine import CalendarEngine, DayPolicy

_ENGINE_GUARD = make_class_guard(CalendarEngine)
_POLICY_GUARD = make_class_guard(DayPolicy)


def policy_snapshot(service, operator_id, service_guard):
    if (operator_id is not None and type(operator_id) is not str) or not service_guard(service):
        return None
    engine = vars(service).get("_engine")
    if not _ENGINE_GUARD(engine):
        return None
    policies = vars(engine).get("_policy_cache")
    if type(policies) is not dict:
        return None
    tokens = vars(engine).setdefault("_sgs_policy_content_tokens", {})
    if type(tokens) is not dict:
        return None
    if len(tokens) > 4096:
        tokens.clear()
    reader = _NativePolicyReader(policies, tokens)
    return reader if operator_id is None else reader.snapshot(operator_id)


class _NativePolicyReader:
    """One scoring round reads only policies previously consumed by its candidates."""

    def __init__(self, policies, tokens):
        self.policies, self.tokens = policies, tokens
        self.guarded = False

    def snapshot(self, operator_id, keys=None):
        entries = []
        selected = self.policies.items() if keys is None else ((key, self.policies.get(key)) for key in keys)
        for key, policy in selected:
            if type(key) is not tuple or len(key) != 2 or any(type(item) is not str for item in key):
                return None
            if key[0] != operator_id:
                continue
            snapshot = self._policy(key, policy)
            if snapshot is None:
                return None
            entries.append((key, snapshot))
        return tuple(entries)

    def _policy(self, key, policy):
        if type(policy) is not DayPolicy:
            return None
        if not self.guarded:
            if not _POLICY_GUARD(policy):
                return None
            self.guarded = True
        data = vars(policy)
        fields, values = tuple(data), tuple(data.values())
        previous = self.tokens.get(key)
        snapshot = scalar_tuple_snapshot(values, previous[1] if previous is not None and previous[0] == fields else None)
        if snapshot is UNSUPPORTED:
            return None
        self.tokens[key] = fields, snapshot
        return fields, snapshot
