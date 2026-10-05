"""Pure write-state assembly shared by single-row and batched fact readers."""

from dataclasses import asdict

from core.models.workbench_supplier import supplier_state


def machine_write_state(identity, record, profile, dependencies, op_types, group):
    primary = next((item for item in op_types if item["identity"]["entity_key"] == record["op_type_id"]), None)
    return {"identity": asdict(identity), "record": record, "profile": profile, "dependencies": dependencies,
            "op_type": primary, "op_types": op_types, "group": group}


def operator_write_state(identity, record, profile, dependencies, skills, skill_types,
                         authorizations, authorized_machines, shift, pattern):
    return {"identity": asdict(identity), "record": record, "profile": profile, "dependencies": dependencies,
            "skills": skills, "skill_types": skill_types, "machine_authorizations": authorizations,
            "authorized_machines": authorized_machines, "shift": shift, "shift_pattern": pattern}


def supplier_write_state(identity, supplier):
    return {"identity": asdict(identity), "supplier": supplier,
            "state": supplier_state(supplier["status"], supplier["profile"])}
