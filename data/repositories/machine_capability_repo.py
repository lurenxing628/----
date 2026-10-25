"""Machine capabilities stored in addition to the legacy primary work type."""

from collections import defaultdict

from .base_repo import BaseRepository


class MachineCapabilityRepository(BaseRepository):
    def by_machines(self, codes):
        result = defaultdict(list)
        codes = list(codes)
        for offset in range(0, len(codes), 400):
            group = codes[offset:offset + 400]
            marks = ",".join("?" for _ in group)
            for row in self.fetchall("SELECT machine_id,op_type_id FROM MachineOpTypes WHERE machine_id IN ("
                                     + marks + ") ORDER BY machine_id,op_type_id", group):
                result[row["machine_id"]].append(row["op_type_id"])
        return result

