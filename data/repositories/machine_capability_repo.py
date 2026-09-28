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

    def replace(self, machine_id, codes, *, primary):
        existing = set(self.by_machines([machine_id])[machine_id])
        additional = set(codes) - {primary}
        for code in sorted(existing - additional):
            self.execute("DELETE FROM MachineOpTypes WHERE machine_id=? AND op_type_id=?", (machine_id, code))
        for code in sorted(additional - existing):
            self.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,?)", (machine_id, code))
        return additional != existing
