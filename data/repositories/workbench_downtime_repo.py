"""Raw downtime facts with permanent dashboard identities."""

from .base_repo import BaseRepository


class WorkbenchDowntimeRepository(BaseRepository):
    def rows(self, machine_id):
        return self.fetchall("""SELECT d.*, r.ref, r.revision FROM MachineDowntimes d
            LEFT JOIN WorkbenchDashboardDowntimeRefs r ON r.source_id=d.id AND r.active=1
            WHERE d.machine_id=? ORDER BY d.start_time,d.id""", (machine_id,))
