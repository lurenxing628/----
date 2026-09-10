"""Scoped relation reads; SQL filtering/counting precede bounded pagination."""

from .base_repo import BaseRepository

_MACHINES = """
    SELECT m.machine_id AS business_code,m.name,m.status,m.remark,m.category,
           r.ref,r.revision
    FROM Machines AS m
    LEFT JOIN WorkbenchEntityRefs AS r
      ON r.kind='machine' AND r.entity_key=m.machine_id AND r.active=1
    WHERE m.op_type_id=:op_type
"""
_OPERATORS = """
    WITH selected AS (
        SELECT operator_id FROM OperatorSkill WHERE op_type_id=:op_type
        UNION
        SELECT a.operator_id FROM OperatorMachine AS a
        JOIN Machines AS m ON m.machine_id=a.machine_id WHERE m.op_type_id=:op_type
    )
    SELECT selected.operator_id AS business_code,o.name,o.status,o.remark,
           p.skills_declared,p.inactive_reason,p.operator_id AS profile_operator_id,
           s.op_type_id AS skill_type,s.skill_level,s.is_primary AS skill_is_primary,
           r.ref,r.revision
    FROM selected
    LEFT JOIN Operators AS o ON o.operator_id=selected.operator_id
    LEFT JOIN WorkbenchOperatorProfiles AS p ON p.operator_id=selected.operator_id
    LEFT JOIN OperatorSkill AS s ON s.operator_id=selected.operator_id AND s.op_type_id=:op_type
    LEFT JOIN WorkbenchEntityRefs AS r
      ON r.kind='operator' AND r.entity_key=selected.operator_id AND r.active=1
"""
_SUPPLIERS = """
    WITH selected AS (
        SELECT supplier_id,1 AS legacy,0 AS explicit FROM Suppliers WHERE op_type_id=:op_type
        UNION ALL
        SELECT supplier_id,0,1 FROM WorkbenchSupplierOpTypes WHERE op_type_id=:op_type
    ), sources AS (
        SELECT supplier_id,max(legacy) AS legacy,max(explicit) AS explicit
        FROM selected GROUP BY supplier_id
    )
    SELECT sources.supplier_id AS business_code,s.name,s.status,s.remark,s.default_days,
           s.op_type_id AS legacy_type,t.category AS legacy_category,
           sources.legacy,sources.explicit,p.inactive_reason,r.ref,r.revision
    FROM sources
    LEFT JOIN Suppliers AS s ON s.supplier_id=sources.supplier_id
    LEFT JOIN OpTypes AS t ON t.op_type_id=s.op_type_id
    LEFT JOIN WorkbenchSupplierProfiles AS p ON p.supplier_id=sources.supplier_id
    LEFT JOIN WorkbenchEntityRefs AS r
      ON r.kind='supplier' AND r.entity_key=sources.supplier_id AND r.active=1
"""
_QUERIES = {"machines": _MACHINES, "operators": _OPERATORS, "suppliers": _SUPPLIERS}
_OPERATOR_FACTS = {
    "skills": """SELECT s.*,t.category FROM OperatorSkill AS s
        LEFT JOIN OpTypes AS t ON t.op_type_id=s.op_type_id
        WHERE s.operator_id IN ({marks}) ORDER BY s.operator_id,s.op_type_id,s.id""",
    "authorizations": """SELECT a.*,m.name AS machine_name,m.op_type_id,m.status AS machine_status,
        t.category AS work_type_category,r.ref AS machine_ref,r.revision AS machine_revision
        FROM OperatorMachine AS a
        LEFT JOIN Machines AS m ON m.machine_id=a.machine_id
        LEFT JOIN OpTypes AS t ON t.op_type_id=m.op_type_id
        LEFT JOIN WorkbenchEntityRefs AS r
          ON r.kind='machine' AND r.entity_key=a.machine_id AND r.active=1
        WHERE a.operator_id IN ({marks}) ORDER BY a.operator_id,a.machine_id,a.id""",
}
_SUPPLIER_FACTS = {
    "capabilities": """SELECT c.supplier_id,c.op_type_id,t.category
        FROM WorkbenchSupplierOpTypes AS c
        LEFT JOIN OpTypes AS t ON t.op_type_id=c.op_type_id
        WHERE c.supplier_id IN ({marks}) ORDER BY c.supplier_id,c.op_type_id""",
}


class WorkbenchResourceRelationRepository(BaseRepository):
    def parent(self, code):
        return self.fetchone("SELECT op_type_id,name,category,remark FROM OpTypes WHERE op_type_id=?", (code,))

    def rows(self, code, relation):
        return self.fetchall("SELECT * FROM (" + _QUERIES[relation] + ") ORDER BY business_code", {"op_type": code})

    def page(self, code, relation, query):
        source = " FROM (" + _QUERIES[relation] + ") AS related"
        params = {"op_type": code, "query": query.query, "size": query.size, "offset": (query.number - 1) * query.size}
        if query.query:
            source += " WHERE instr(lower(business_code),lower(:query))>0 OR instr(lower(name),lower(:query))>0"
        total = int(self.fetchvalue("SELECT COUNT(*)" + source, params, default=0))
        rows = self.fetchall("SELECT business_code" + source + " ORDER BY business_code ASC LIMIT :size OFFSET :offset", params)
        return [row["business_code"] for row in rows], total

    def facts(self, relation, codes):
        queries = _OPERATOR_FACTS if relation == "operators" else _SUPPLIER_FACTS if relation == "suppliers" else {}
        result = {key: [] for key in queries}
        # Stay below the SQLite variable limit shipped with Python 3.8 on Win7.
        for start in range(0, max(1, len(codes)), 400):
            chunk = codes[start:start + 400]
            marks = ",".join("?" for _ in chunk) or "NULL"
            for key, sql in queries.items():
                result[key].extend(self.fetchall(sql.format(marks=marks), chunk))
        return result
