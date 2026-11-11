"""Adapt already-read current transaction facts to the common calendar factory."""

from .archived_calendar import ArchivedCalendar


def calendar_from_sources(sources, *, schema_version, identities, plan_ref, scope):
    """Use one captured calendar source for both task checks and resource analysis."""
    if sources is None:
        return None
    profiles = sources["profiles"]
    tables = {"SchemaVersion": schema_version, "WorkbenchCalendarDefaults": sources["defaults"],
              "WorkCalendar": sources["global"], "OperatorCalendar": sources["personal"],
              "WorkbenchOperatorProfiles": [{key: row[key] for key in ("operator_id", "shift_profile_id")} for row in profiles],
              "WorkbenchShiftProfiles": sources["shift_profiles"], "WorkbenchShiftPatternDays": sources["patterns"],
              "Machines": sources["machines"], "Operators": sources["operators"],
              "MachineDowntimes": sources["downtimes"],
              "WorkbenchEntityRefs": [{"kind": kind, "entity_key": key, "ref": ref, "active": 1}
                                       for kind in ("machine", "operator") for key, ref, _ in identities[kind]]}
    return ArchivedCalendar({"tables": tables}, source_ref=plan_ref,
                            coverage={"start": scope["range_start"], "end": scope["range_end"]},
                            metadata_basis="current_transaction_snapshot")
