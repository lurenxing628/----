"""Read explicit person shift patterns without touching per-date exceptions."""

from .base_repo import BaseRepository


class OperatorShiftRepository(BaseRepository):
    def profile_for_operator(self, operator_id):
        return self.fetchone("""SELECT p.shift_profile_id, s.profile_id, s.anchor_date, s.cycle_days, s.status,
            (SELECT COUNT(*) FROM WorkbenchShiftPatternDays AS d WHERE d.profile_id=s.profile_id) AS day_count,
            (SELECT MIN(day_offset) FROM WorkbenchShiftPatternDays AS d WHERE d.profile_id=s.profile_id) AS first_day,
            (SELECT MAX(day_offset) FROM WorkbenchShiftPatternDays AS d WHERE d.profile_id=s.profile_id) AS last_day
            FROM WorkbenchOperatorProfiles AS p LEFT JOIN WorkbenchShiftProfiles AS s ON s.profile_id=p.shift_profile_id
            WHERE p.operator_id=? AND p.shift_profile_id IS NOT NULL""", (operator_id,))

    def pattern_day(self, profile_id, offset):
        return self.fetchone("""SELECT day_offset,is_rest,shift_start,shift_end FROM WorkbenchShiftPatternDays
            WHERE profile_id=? AND day_offset=?""", (profile_id, offset))
