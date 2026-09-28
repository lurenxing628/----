"""One optional factory workday rule; absent means the bundled business default."""

from .base_repo import BaseRepository


class CalendarDefaultsRepository(BaseRepository):
    def get(self):
        return self.fetchone("SELECT * FROM WorkbenchCalendarDefaults WHERE singleton=1")

    def set_periods(self, periods_json):
        self.execute("""INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES(1,?)
            ON CONFLICT(singleton) DO UPDATE SET periods_json=excluded.periods_json, revision=revision+1""",
                     (periods_json,))
