"""Adapt already-read current transaction facts to the common calendar factory."""

from .archived_calendar import ArchivedCalendar


def current_resource_calendar(facts, scope):
    private = facts.raw["resource_pressure"]["calendar"]
    sources = private.get("sources")
    if sources is None:
        return None
    profiles = sources["profiles"]
    shifts = {row["profile_id"]: {key: row[key] for key in ("profile_id", "anchor_date", "cycle_days", "status")}
              for row in profiles if row["profile_id"] is not None}
    periods = [{key: row[key] for key in ("profile_id", "day_offset", "periods_json")}
               for row in sources["patterns"] if row["periods_json"] is not None]
    identities = facts.raw["plan_resource_identities"]
    tables = {"SchemaVersion": facts.raw["SchemaVersion"], "WorkbenchCalendarDefaults": sources["defaults"],
              "WorkCalendar": sources["global"], "OperatorCalendar": sources["personal"],
              "WorkbenchOperatorProfiles": [{key: row[key] for key in ("operator_id", "shift_profile_id")} for row in profiles],
              "WorkbenchShiftProfiles": list(shifts.values()), "WorkbenchShiftPatternDays": sources["patterns"],
              "WorkbenchShiftDayPeriods": periods, "Machines": sources["machines"], "Operators": sources["operators"],
              "MachineDowntimes": sources["downtimes"],
              "WorkbenchEntityRefs": [{"kind": kind, "entity_key": key, "ref": ref, "active": 1}
                                       for kind in ("machine", "operator") for key, ref, _ in identities[kind]]}
    return ArchivedCalendar({"tables": tables}, source_ref=facts.plan["plan_ref"],
                            coverage={"start": scope["range_start"], "end": scope["range_end"]},
                            metadata_basis="current_transaction_snapshot")
