"""设备能做的工种：MachineOpTypes 是唯一存储。"""

import json
from collections import defaultdict

from .base_repo import BaseRepository


class MachineCapabilityRepository(BaseRepository):
    def by_machines(self, codes):
        result = defaultdict(list)
        if not codes:
            return result
        for row in self.fetchall(
            "SELECT machine_id,op_type_id FROM MachineOpTypes "
            "WHERE machine_id IN (SELECT value FROM json_each(?)) ORDER BY machine_id,op_type_id",
            (json.dumps(list(codes)),),
        ):
            result[row["machine_id"]].append(row["op_type_id"])
        return result

