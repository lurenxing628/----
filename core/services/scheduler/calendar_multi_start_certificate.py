"""CalendarService-initialization evidence for run-level decision deduplication."""

from core.algorithm_runtime.native_snapshot import UNSUPPORTED, make_class_guard, native_record_snapshot
from data.repositories.calendar_repo import CalendarRepository
from data.repositories.operator_calendar_repo import OperatorCalendarRepository
from data.repositories.operator_shift_repo import OperatorShiftRepository

from .calendar_engine import CalendarEngine, DayPolicy
from .operator_shift_calendar import OperatorShiftCalendar

# Imported during CalendarService initialization, never by a later optimizer run.
# Repository guards include their BaseRepository MRO and inherited instance shadows.
_NATIVE_GUARDS = {cls: make_class_guard(cls) for cls in (
    CalendarEngine, DayPolicy, OperatorShiftCalendar,
    CalendarRepository, OperatorCalendarRepository, OperatorShiftRepository,
)}


def multi_start_calendar_snapshot(service, service_guard):
    if not service_guard(service):
        return None
    fields = vars(service)
    engine, connection = fields.get("_engine"), fields.get("conn")
    if not _NATIVE_GUARDS[CalendarEngine](engine) or vars(engine).get("conn") is not connection:
        return None
    if not _repositories_match(engine, connection):
        return None
    policies = _policy_contents(vars(engine).get("_policy_cache"))
    return None if policies is None else (engine, connection, policies)


def _repositories_match(engine, connection):
    fields = vars(engine)
    shift = fields.get("operator_shift_calendar")
    if not _NATIVE_GUARDS[OperatorShiftCalendar](shift):
        return False
    repositories = (
        (fields.get("repo"), CalendarRepository),
        (fields.get("operator_calendar_repo"), OperatorCalendarRepository),
        (vars(shift).get("repo"), OperatorShiftRepository),
    )
    return all(_NATIVE_GUARDS[cls](repo) and vars(repo).get("conn") is connection for repo, cls in repositories)


def _policy_contents(policies):
    if type(policies) is not dict:
        return None
    snapshots = []
    for key, policy in policies.items():
        if type(key) is not tuple or len(key) != 2 or any(type(value) is not str for value in key):
            return None
        # Every policy must pass its own shadow check, including later cache rows.
        if not _NATIVE_GUARDS[DayPolicy](policy):
            return None
        snapshot = native_record_snapshot(policy, (DayPolicy,))
        if snapshot is UNSUPPORTED:
            return None
        snapshots.append((key, snapshot))
    # Both policy-map order and every native policy field remain part of the key.
    return tuple(snapshots)
