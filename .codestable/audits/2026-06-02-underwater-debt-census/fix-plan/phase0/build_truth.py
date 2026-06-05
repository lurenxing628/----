#!/usr/bin/env python3
"""Phase 0 deterministic truth-source for the underwater-debt fix plan.

Reads the two committed findings JSON (the ONLY source of truth), recomputes the
§5.1 coupling graphs from scratch (never trust hand-counted numbers), flags which
debts land on load-bearing files, cross-links the adversarial verdicts, and
validates the §5.2 17-bucket partition (80 debts, mutually exclusive, full coverage).

Self-pollution guard: this script reads ONLY the findings JSON, never any draft plan.
"""
import json
import os
import re
from collections import defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "findings")
REAL = json.load(open(os.path.join(BASE, "_real_debt.json")))
LB = json.load(open(os.path.join(BASE, "_load_bearing.json")))

real = REAL["findings"]          # 72 -> R1..R72
lb = LB["findings"]              # 8  -> LB1..LB8
verdicts = LB["verdicts"]        # 27 adversarial verdicts

assert len(real) == 72, f"expected 72 real, got {len(real)}"
assert len(lb) == 8, f"expected 8 LB, got {len(lb)}"

# ---- canonical debt map -------------------------------------------------
PATH_RE = re.compile(r"[A-Za-z_][\w/]*\.(?:py|html|sql|js|yaml|yml)")

def files_in(loc):
    """Extract distinct file paths referenced in a location string."""
    return sorted(set(PATH_RE.findall(loc or "")))

def basename_set(loc):
    return sorted({p.split("/")[-1] for p in files_in(loc)})

debts = {}  # id -> record
for i, f in enumerate(real, 1):
    did = f"R{i:02d}"
    debts[did] = {
        "id": did, "kind": "real",
        "pathology": f.get("pathology", ""),
        "severity": f.get("severity", ""),
        "load_bearing": f.get("load_bearing"),
        "needs_adversarial": f.get("needs_adversarial"),
        "partition": f.get("_partition", ""),
        "title": f.get("title", ""),
        "location": f.get("location", ""),
        "files": files_in(f.get("location", "")),
        "basenames": basename_set(f.get("location", "")),
    }
for i, f in enumerate(lb, 1):
    did = f"LB{i:02d}"
    debts[did] = {
        "id": did, "kind": "load_bearing",
        "pathology": f.get("pathology", ""),
        "severity": f.get("severity", ""),
        "load_bearing": f.get("load_bearing"),
        "needs_adversarial": f.get("needs_adversarial"),
        "partition": f.get("_partition", ""),
        "title": f.get("title", ""),
        "location": f.get("location", ""),
        "files": files_in(f.get("location", "")),
        "basenames": basename_set(f.get("location", "")),
        "adv_refuted": f.get("_adv_refuted"),
        "adv_precondition": f.get("_adv_precondition", ""),
    }

# ---- §5.2 bucket partition (the proposed starting cut, to VALIDATE) ------
BUCKETS = {
    "B01": ["LB01","LB02","LB05","LB06","LB03","R54","R56","R57","R58","R62","R07","R42","R60","R66","R08"],
    "B02": ["R22","R23","R72","R21","R44"],
    "B03": ["LB07","R71","R47","R45","R48"],
    "B04": ["LB04","R41"],
    "B05": ["R04","R09","R28","R29","R50","R59"],
    "B06": ["R15","R30","R33","R49","R51"],
    "B07": ["R05","R67"],
    "B08": ["R11","R63","R12","R55"],
    "B09": ["R02","R06","R25","R52"],
    "B10": ["LB08","R46"],
    "B11": ["R13","R14","R16","R17","R18","R24"],
    "B12": ["R34","R35","R37","R38","R39","R36"],
    "B13": ["R20","R26","R31","R43","R19"],
    "B14": ["R01","R10","R03","R27"],
    "B15": ["R68","R69","R70"],
    "B16": ["R32","R40"],
    "B17": ["R64","R65","R61","R53"],
}

all_ids = set(debts.keys())
assigned = []
for _bucket, members in BUCKETS.items():
    assigned += members
dup = [x for x in assigned if assigned.count(x) > 1]
missing = sorted(all_ids - set(assigned))
extra = sorted(set(assigned) - all_ids)
home = {}
for b, members in BUCKETS.items():
    for m in members:
        home[m] = b

print("=" * 70)
print("§5.2 BUCKET PARTITION VALIDATION")
print("=" * 70)
print(f"total debts in findings: {len(all_ids)} (72 real + 8 LB)")
print(f"total bucket assignments: {len(assigned)}")
print(f"duplicates (debt in >1 bucket): {sorted(set(dup)) or 'NONE ✓'}")
print(f"missing (debt with no bucket): {missing or 'NONE ✓'}")
print(f"extra (bucket id not in findings): {extra or 'NONE ✓'}")
# per-bucket LB count check
print("\nper-bucket sizes:")
for b, members in BUCKETS.items():
    lbs = [m for m in members if m.startswith("LB")]
    print(f"  {b}: {len(members):2d} members  ({len(lbs)} LB: {lbs})")
lb_all = [m for b in BUCKETS.values() for m in b if m.startswith("LB")]
print(f"\nLB coverage: {sorted(lb_all)} -> {len(set(lb_all))}/8 distinct")

# ---- §5.1(a) same-file coupling: recompute from basenames ---------------
# A debt's "primary file(s)" = basenames in its location. Two debts couple if
# they share a basename. We report groups keyed by basename with >=2 debts.
by_basename = defaultdict(set)
for did, rec in debts.items():
    for bn in rec["basenames"]:
        by_basename[bn].add(did)
samefile_groups = {bn: sorted(ids) for bn, ids in by_basename.items() if len(ids) >= 2}

print("\n" + "=" * 70)
print("§5.1(a) SAME-FILE COUPLING (recomputed from location basenames)")
print("=" * 70)
print(f"basenames hit by >=2 debts: {len(samefile_groups)}")
for bn in sorted(samefile_groups, key=lambda x: (-len(samefile_groups[x]), x)):
    ids = samefile_groups[bn]
    # mark cross-bucket
    homes = sorted({home.get(i, "?") for i in ids})
    cross = "CROSS-BUCKET" if len(homes) > 1 else "same-bucket"
    print(f"  {bn:48s} {ids}  buckets={homes} [{cross}]")

# ---- load-bearing FILES: any file referenced by an LB finding -----------
lb_files = set()
for _did, rec in debts.items():
    if rec["kind"] == "load_bearing":
        lb_files |= set(rec["basenames"])
print("\n" + "=" * 70)
print("LOAD-BEARING FILES (basenames referenced by any LB finding)")
print("=" * 70)
print(sorted(lb_files))
# which real debts also touch a load-bearing file?
print("\nReal debts that also touch a load-bearing file (co-located risk):")
for did in sorted(d for d in debts if d.startswith("R")):
    rec = debts[did]
    overlap = sorted(set(rec["basenames"]) & lb_files)
    if overlap:
        print(f"  {did} [{home.get(did,'?')}] touches LB file(s): {overlap}")

# ---- adversarial verdicts cross-link ------------------------------------
# Map verdicts to R-ids by matching title+location against real findings.
print("\n" + "=" * 70)
print("ADVERSARIAL VERDICTS -> debt id (by title match)")
print("=" * 70)
title_to_id = {}
for did, rec in debts.items():
    title_to_id[rec["title"].strip()] = did
verdict_map = {}
for v in verdicts:
    t = (v.get("_title") or "").strip()
    did = title_to_id.get(t)
    verdict_map[did or f"?({t[:30]})"] = {
        "refuted": v.get("refuted"),
        "bucket": v.get("_bucket"),
        "verdict_kind": v.get("verdict"),
    }
for did in sorted(verdict_map, key=lambda x: (x.startswith("?"), x)):
    info = verdict_map[did]
    print(f"  {did:10s} refuted={str(info['refuted']):5s} kind={info['verdict_kind']:18s} bucket={info['bucket']}")

# ---- needs_adversarial but no verdict (the 27 vs needs flag) ------------
needs_adv = sorted(d for d in debts if debts[d].get("needs_adversarial"))
have_verdict = {d for d in verdict_map if not d.startswith("?")}
print(f"\nneeds_adversarial=True debts: {len(needs_adv)} -> {needs_adv}")
print(f"of those WITHOUT a matched verdict: {sorted(set(needs_adv)-have_verdict)}")

# ---- pathology distribution ---------------------------------------------
print("\n" + "=" * 70)
print("PATHOLOGY / SEVERITY DISTRIBUTION")
print("=" * 70)
patho = defaultdict(list)
sev = defaultdict(list)
for did, rec in debts.items():
    patho[rec["pathology"]].append(did)
    sev[rec["severity"]].append(did)
for p in sorted(patho):
    print(f"  pathology {p!r:16s}: {len(patho[p]):2d}  {sorted(patho[p])}")
print()
for s in sorted(sev):
    print(f"  severity {s!r:10s}: {len(sev[s]):2d}  {sorted(sev[s])}")

# ---- dump machine-readable truth ----------------------------------------
truth = {
    "debts": debts,
    "buckets": BUCKETS,
    "home": home,
    "samefile_groups": samefile_groups,
    "load_bearing_files": sorted(lb_files),
    "verdict_map": {k: v for k, v in verdict_map.items() if not k.startswith("?")},
    "partition_check": {
        "total": len(all_ids),
        "duplicates": sorted(set(dup)),
        "missing": missing,
        "extra": extra,
        "lb_distinct": len(set(lb_all)),
    },
}
out = os.path.join(os.path.dirname(__file__), "_truth.json")
json.dump(truth, open(out, "w"), ensure_ascii=False, indent=2)
print(f"\nwrote {out}")
