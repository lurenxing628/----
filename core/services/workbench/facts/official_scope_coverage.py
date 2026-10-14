"""One operation coverage rule for adoption and archived resource pressure."""


def official_scope_coverage(official_operations, candidate_operations):
    """Compare operation identities supplied in the caller's identity system."""
    official, candidate = set(official_operations), set(candidate_operations)
    covered = official & candidate
    missing = sorted(official - candidate)
    return {"covers_official_scope": not missing, "official_operation_count": len(official),
            "covered_official_operation_count": len(covered), "missing_official_operations": missing}
