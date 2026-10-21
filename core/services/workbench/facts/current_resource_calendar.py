"""Adapt already-read current transaction facts to the common calendar factory."""

from .archived_calendar import ArchivedCalendar


def calendar_from_sources(sources, *, schema_version, identities, plan_ref, scope):
    """Use one captured calendar source for both task checks and resource analysis."""
    if sources is None:
        return None
    profiles = sources["profiles"]
    shifts = {row["profile_id"]: {key: row[key] for key in ("profile_id", "anchor_date", "cycle_days", "status")}
              for row in profiles if row["profile_id"] is not None}
    periods = [{key: row[key] for key in ("profile_id", "day_offset", "periods_json")}
               for row in sources["patterns"] if row["periods_json"] is not None]
    tables = {"SchemaVersion": schema_version, "WorkbenchCalendarDefaults": sources["defaults"],
              "WorkCalendar": sources["global"], "OperatorCalendar": sources["personal"],
              "WorkbenchOperatorProfiles": [{key: row[key] for key in ("operator_id", "shift_profile_id")} for row in profiles],
              "WorkbenchShiftProfiles": list(shifts.values()), "WorkbenchShiftPatternDays": sources["patterns"],
              "WorkbenchShiftDayPeriods": periods, "Machines": sources["machines"], "Operators": sources["operators"],
              "MachineDowntimes": sources["downtimes"],
              "WorkbenchEntityRefs": [{"kind": kind, "entity_key": key, "ref": ref, "active": 1}
                                       for kind in ("machine", "operator") for key, ref, _ in identities[kind]]}
    return ArchivedCalendar({"tables": tables}, source_ref=plan_ref,
                            coverage={"start": scope["range_start"], "end": scope["range_end"]},
                            metadata_basis="current_transaction_snapshot")


def current_resource_calendar(facts, scope):
    return facts._calendar_factory
