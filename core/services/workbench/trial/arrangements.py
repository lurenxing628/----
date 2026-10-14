"""Trial geometry stays separate from saved standard requirement evidence."""

ARRANGEMENT_FIELDS = ("machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end")


def arrangement_geometry(value):
    return {key: value[key] for key in ARRANGEMENT_FIELDS}


def same_arrangement(before, after):
    return arrangement_geometry(before) == arrangement_geometry(after)
