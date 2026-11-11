"""Assemble connection-free CalendarInputs from workbench captures, fact mappings, or snapshots."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

from core.services.scheduler.calendar.engine import CalendarInputs
from data.repositories.calendar_defaults_repo import CalendarDefaultsRepository


def _scope_operator_tables(
    scoped_ids: Optional[FrozenSet[str]],
    personal_days: Optional[Sequence[Dict[str, Any]]],
    operator_profiles: Optional[Sequence[Dict[str, Any]]],
    shift_profiles: Optional[Sequence[Dict[str, Any]]],
    shift_patterns: Optional[Sequence[Dict[str, Any]]],
) -> Tuple[
    Optional[Sequence[Dict[str, Any]]],
    Optional[Sequence[Dict[str, Any]]],
    Optional[Sequence[Dict[str, Any]]],
    Optional[Sequence[Dict[str, Any]]],
]:
    if scoped_ids is None:
        return personal_days, operator_profiles, shift_profiles, shift_patterns
    scoped_personal = (
        None
        if personal_days is None
        else tuple(row for row in personal_days if row["operator_id"] in scoped_ids)
    )
    scoped_profiles = (
        None
        if operator_profiles is None
        else tuple(row for row in operator_profiles if row["operator_id"] in scoped_ids)
    )
    referenced_profile_ids = frozenset(
        row["shift_profile_id"]
        for row in (scoped_profiles or ())
        if row["shift_profile_id"] is not None
    )
    scoped_shift_profiles = (
        None
        if shift_profiles is None
        else tuple(row for row in shift_profiles if row["profile_id"] in referenced_profile_ids)
    )
    scoped_shift_patterns = (
        None
        if shift_patterns is None
        else tuple(row for row in shift_patterns if row["profile_id"] in referenced_profile_ids)
    )
    return scoped_personal, scoped_profiles, scoped_shift_profiles, scoped_shift_patterns


def calendar_inputs_from_capture(
    capture: Any, *, operator_ids: Optional[Iterable[str]] = None,
) -> CalendarInputs:
    scoped_ids = None if operator_ids is None else frozenset(operator_ids)
    personal_days, operator_profiles, shift_profiles, shift_patterns = _scope_operator_tables(
        scoped_ids,
        capture.business_table("OperatorCalendar"),
        capture.business_table("WorkbenchOperatorProfiles"),
        capture.business_table("WorkbenchShiftProfiles"),
        capture.business_table("WorkbenchShiftPatternDays"),
    )
    return CalendarInputs(
        defaults=capture.business_table("WorkbenchCalendarDefaults"),
        public_days=capture.business_table("WorkCalendar"),
        personal_days=personal_days,
        operator_profiles=operator_profiles,
        shift_profiles=shift_profiles,
        shift_patterns=shift_patterns,
        decoded_periods=capture.decoded_periods,
    )


def calendar_inputs_from_facts(facts: Mapping[str, Any]) -> CalendarInputs:
    return CalendarInputs(
        defaults=facts["defaults"],
        public_days=facts["global"],
        personal_days=facts["personal"],
        operator_profiles=facts["profiles"],
        shift_profiles=facts["shift_profiles"],
        shift_patterns=facts["patterns"],
    )


def calendar_inputs_from_archive_tables(tables: Mapping[str, Any]) -> CalendarInputs:
    return CalendarInputs(
        defaults=tables["WorkbenchCalendarDefaults"],
        public_days=tables["WorkCalendar"],
        personal_days=tables["OperatorCalendar"],
        operator_profiles=tables["WorkbenchOperatorProfiles"],
        shift_profiles=tables["WorkbenchShiftProfiles"],
        shift_patterns=tables["WorkbenchShiftPatternDays"],
    )


def calendar_inputs_from_connection(
    conn: Any,
    *,
    public_days: Sequence[Dict[str, Any]],
) -> CalendarInputs:
    row = CalendarDefaultsRepository(conn).get()
    return CalendarInputs(
        defaults=() if row is None else (row,),
        public_days=public_days,
    )
