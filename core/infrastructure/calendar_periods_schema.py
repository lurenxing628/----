"""Optional multiple daily work periods without reinterpreting legacy rows."""

from .migration_common import column_exists
from .workbench_metadata_schema import canonical_sql


def objects():
    return {
        "WorkbenchCalendarDefaults": """CREATE TABLE WorkbenchCalendarDefaults (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            state_ref TEXT NOT NULL DEFAULT (lower(hex(randomblob(24)))),
            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), periods_json TEXT NOT NULL)""",
        "WorkbenchShiftDayPeriods": """CREATE TABLE WorkbenchShiftDayPeriods (
            profile_id TEXT NOT NULL, day_offset INTEGER NOT NULL, periods_json TEXT NOT NULL,
            PRIMARY KEY(profile_id, day_offset),
            FOREIGN KEY(profile_id, day_offset) REFERENCES WorkbenchShiftPatternDays(profile_id, day_offset)
                ON DELETE CASCADE)""",
        **{("wb_shift_periods_" + event.lower()): """CREATE TRIGGER wb_shift_periods_""" + event.lower() + """
            AFTER """ + event + """ ON WorkbenchShiftDayPeriods BEGIN
                UPDATE WorkbenchEntityRefs SET revision=revision+1
                    WHERE kind='shift_profile' AND active=1 AND entity_key=""" + alias + """.profile_id;
            END""" for event, alias in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD"))},
    }


def contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    issues = [("missing_calendar_periods:" if name not in actual else "invalid_calendar_periods:") + name
              for name, sql in objects().items()
              if name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "")]
    issues.extend("missing_calendar_periods:" + table + ".periods_json"
                  for table in ("WorkCalendar", "OperatorCalendar") if not column_exists(conn, table, "periods_json"))
    return issues


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Calendar period installation requires a migration transaction.")
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects()) or any(column_exists(conn, table, "periods_json")
                                    for table in ("WorkCalendar", "OperatorCalendar")):
        issues = contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial calendar periods: " + ";".join(issues))
        return
    for table in ("WorkCalendar", "OperatorCalendar"):
        conn.execute("ALTER TABLE " + table + " ADD COLUMN periods_json TEXT")
    for sql in objects().values():
        conn.execute(sql)
