"""FJSP benchmark dataset mirrors, parser, and machine-folding helpers."""

from __future__ import annotations

import textwrap
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Brandimarte 1993 FJSP sources. Prefer GitHub raw, fallback to embedded
# mirrors so benchmark proof remains reproducible without network access.
DATASET_SOURCES: Dict[str, Dict[str, Any]] = {
    "mk01": {
        "jobs": 10,
        "machines": 6,
        "ref_type": "BKS",
        "ref_makespan": 40,
        "raw_url": "https://raw.githubusercontent.com/Lei-Kun/FJSP-benchmarks/main/1_Brandimarte/BrandimarteMk1.fjs",
        "mirror_text": """
10 6 2
 6 2 1 5 3 4 3 5 3 3 5 2 1 2 3 4 6 2 3 6 5 2 6 1 1 1 3 1 3 6 6 3 6 4 3
 5 1 2 6 1 3 1 1 1 2 2 2 6 4 6 3 6 5 2 6 1 1
 5 1 2 6 2 3 4 6 2 3 6 5 2 6 1 1 3 3 4 2 6 6 6 2 1 1 5 5
 5 3 6 5 2 6 1 1 1 2 6 1 3 1 3 5 3 3 5 2 1 2 3 4 6 2
 6 3 5 3 3 5 2 1 3 6 5 2 6 1 1 1 2 6 2 1 5 3 4 2 2 6 4 6 3 3 4 2 6 6 6
 6 2 3 4 6 2 1 1 2 3 3 4 2 6 6 6 1 2 6 3 6 5 2 6 1 1 2 1 3 4 2
 5 1 6 1 2 1 3 4 2 3 3 4 2 6 6 6 3 2 6 5 1 1 6 1 3 1
 5 2 3 4 6 2 3 3 4 2 6 6 6 3 6 5 2 6 1 1 1 2 6 2 2 6 4 6
 6 1 6 1 2 1 1 5 5 3 6 6 3 6 4 3 1 1 2 3 3 4 2 6 6 6 2 2 6 4 6
 6 2 3 4 6 2 3 3 4 2 6 6 6 3 5 3 3 5 2 1 1 6 1 2 2 6 4 6 2 1 3 4 2
""",
    },
    "mk04": {
        "jobs": 15,
        "machines": 8,
        "ref_type": "BKS",
        "ref_makespan": 60,
        "raw_url": "https://raw.githubusercontent.com/Lei-Kun/FJSP-benchmarks/main/1_Brandimarte/BrandimarteMk4.fjs",
        "mirror_text": """
15 8 2
8 1 1 6 2 1 6 7 9 2 6 7 3 1 2 4 2 7 5 3 1 8 3 9 8 9 3 2 3 4 8 3 2 2 5 5 6 7 2 6 1 4 7
7 1 6 1 2 6 1 4 7 1 1 6 2 6 7 3 1 3 2 3 4 8 3 2 1 6 2 1 7 2
6 1 6 1 3 2 3 4 8 3 2 3 3 2 7 1 4 4 2 4 2 7 5 2 1 7 3 7 2 4 4 3 1
5 1 7 2 1 1 6 2 1 6 7 9 2 6 7 3 1 2 4 5 5 7
7 1 7 2 2 1 6 7 9 2 4 4 3 1 3 1 8 3 9 8 9 2 1 7 3 7 3 2 3 4 8 3 2 2 4 5 5 7
9 1 6 2 2 4 4 3 1 3 3 2 7 1 4 4 2 6 1 4 7 2 4 5 5 7 3 1 8 3 9 8 9 2 1 7 3 7 1 6 1 2 1 6 7 9
5 2 5 5 6 7 2 1 7 3 7 2 6 1 4 7 1 6 2 2 6 7 3 1
6 2 4 5 5 7 2 5 5 6 7 3 2 3 4 8 3 2 1 6 2 1 6 1 2 1 6 7 9
9 1 1 6 2 1 6 7 9 2 4 4 3 1 3 1 8 3 9 8 9 2 4 2 7 5 2 6 1 4 7 1 7 2 2 1 7 3 7 3 2 3 4 8 3 2
5 2 5 5 6 7 1 1 6 1 7 2 2 4 5 5 7 2 1 6 7 9
4 3 1 8 3 9 8 9 1 1 6 3 2 3 4 8 3 2 2 4 2 7 5
6 2 4 2 7 5 1 6 1 1 1 6 2 1 7 3 7 3 1 8 3 9 8 9 1 7 2
4 1 6 2 2 6 7 3 1 2 6 1 4 7 2 5 5 6 7
3 2 5 5 6 7 1 6 1 2 4 2 7 5
6 2 4 5 5 7 1 7 2 3 1 8 3 9 8 9 3 2 3 4 8 3 2 3 3 2 7 1 4 4 1 1 6
""",
    },
    "mk06": {
        "jobs": 10,
        "machines": 10,
        "ref_type": "BKS",
        "ref_makespan": 57,
        "raw_url": "https://raw.githubusercontent.com/Lei-Kun/FJSP-benchmarks/main/1_Brandimarte/BrandimarteMk6.fjs",
        "mirror_text": """
10 10 3
15 4 2 8 6 3 7 2 9 5 2 9 7 1 2 5 7 4 1 4 9 1 2 7 10 4 2 1 1 8 2 3 7 5 3 8 5 8 5 1 3 8 8 2 5 3 8 10 9 3 5 6 1 1 6 2 5 2 5 1 9 9 1 5 7 4 6 2 10 6 1 2 2 7 9 5 6 2 4 8 7 2 5 2 1 5 8 4 2 1 8 3 7 3 10 2 8 9 4 5 3 7 5 3 7 9 3 3 9 4 5 8 1 1
15 5 1 3 8 8 2 5 3 8 10 9 5 7 4 1 4 9 1 2 7 10 4 3 5 6 1 1 6 2 5 2 1 5 8 4 2 1 8 3 7 2 4 8 7 2 2 10 6 1 2 3 10 2 8 9 4 5 2 7 9 5 6 3 7 5 3 7 9 3 3 7 5 3 8 5 8 3 9 4 5 8 1 1 2 9 7 1 2 2 1 1 8 2 4 2 8 6 3 7 2 9 5 5 2 5 1 9 9 1 5 7 4 6
15 2 1 1 8 2 2 7 9 5 6 2 10 6 1 2 2 4 8 7 2 5 2 1 5 8 4 2 1 8 3 7 3 9 4 5 8 1 1 2 9 7 1 2 3 7 5 3 7 9 3 5 7 4 1 4 9 1 2 7 10 4 4 2 8 6 3 7 2 9 5 5 1 3 8 8 2 5 3 8 10 9 3 10 2 8 9 4 5 5 2 5 1 9 9 1 5 7 4 6 3 5 6 1 1 6 2 3 7 5 3 8 5 8
15 3 5 6 1 1 6 2 5 2 5 1 9 9 1 5 7 4 6 5 1 3 8 8 2 5 3 8 10 9 5 2 1 5 8 4 2 1 8 3 7 2 4 8 7 2 2 10 6 1 2 3 7 5 3 8 5 8 2 9 7 1 2 3 7 5 3 7 9 3 3 9 4 5 8 1 1 4 2 8 6 3 7 2 9 5 2 1 1 8 2 5 7 4 1 4 9 1 2 7 10 4 2 7 9 5 6 3 10 2 8 9 4 5
15 3 10 2 8 9 4 5 2 1 1 8 2 3 9 4 5 8 1 1 2 9 7 1 2 3 7 5 3 8 5 8 5 2 1 5 8 4 2 1 8 3 7 3 5 6 1 1 6 2 3 7 5 3 7 9 3 4 2 8 6 3 7 2 9 5 2 10 6 1 2 5 7 4 1 4 9 1 2 7 10 4 2 7 9 5 6 5 2 5 1 9 9 1 5 7 4 6 5 1 3 8 8 2 5 3 8 10 9 2 4 8 7 2
15 3 7 5 3 8 5 8 5 1 3 8 8 2 5 3 8 10 9 2 7 9 5 6 3 5 6 1 1 6 2 5 2 5 1 9 9 1 5 7 4 6 2 4 8 7 2 2 9 7 1 2 5 2 1 5 8 4 2 1 8 3 7 5 7 4 1 4 9 1 2 7 10 4 4 2 8 6 3 7 2 9 5 2 1 1 8 2 3 7 5 3 7 9 3 2 10 6 1 2 3 9 4 5 8 1 1 3 10 2 8 9 4 5
15 3 5 6 1 1 6 2 3 10 2 8 9 4 5 3 7 5 3 8 5 8 5 1 3 8 8 2 5 3 8 10 9 2 1 1 8 2 2 9 7 1 2 5 2 1 5 8 4 2 1 8 3 7 3 7 5 3 7 9 3 5 7 4 1 4 9 1 2 7 10 4 3 9 4 5 8 1 1 2 10 6 1 2 4 2 8 6 3 7 2 9 5 2 7 9 5 6 2 4 8 7 2 5 2 5 1 9 9 1 5 7 4 6
15 5 7 4 1 4 9 1 2 7 10 4 3 7 5 3 7 9 3 3 7 5 3 8 5 8 2 1 1 8 2 3 5 6 1 1 6 2 5 2 5 1 9 9 1 5 7 4 6 3 10 2 8 9 4 5 3 9 4 5 8 1 1 2 9 7 1 2 4 2 8 6 3 7 2 9 5 5 1 3 8 8 2 5 3 8 10 9 2 4 8 7 2 2 10 6 1 2 5 2 1 5 8 4 2 1 8 3 7 2 7 9 5 6
15 4 2 8 6 3 7 2 9 5 3 9 4 5 8 1 1 3 7 5 3 8 5 8 5 7 4 1 4 9 1 2 7 10 4 5 2 1 5 8 4 2 1 8 3 7 2 4 8 7 2 2 9 7 1 2 3 10 2 8 9 4 5 5 1 3 8 8 2 5 3 8 10 9 2 10 6 1 2 5 2 5 1 9 9 1 5 7 4 6 3 7 5 3 7 9 3 2 7 9 5 6 2 1 1 8 2 3 5 6 1 1 6 2
15 2 1 1 8 2 4 2 8 6 3 7 2 9 5 3 10 2 8 9 4 5 3 7 5 3 8 5 8 3 7 5 3 7 9 3 2 10 6 1 2 2 7 9 5 6 3 9 4 5 8 1 1 5 7 4 1 4 9 1 2 7 10 4 5 2 5 1 9 9 1 5 7 4 6 5 1 3 8 8 2 5 3 8 10 9 3 5 6 1 1 6 2 5 2 1 5 8 4 2 1 8 3 7 2 4 8 7 2 2 9 7 1 2
""",
    },
    "mk08": {
        "jobs": 20,
        "machines": 10,
        "ref_type": "BKS",
        "ref_makespan": 523,
        "raw_url": "https://raw.githubusercontent.com/Lei-Kun/FJSP-benchmarks/main/1_Brandimarte/BrandimarteMk8.fjs",
        "mirror_text": """
20 10 1.5
10 2 7 18 4 5 2 5 7 7 7 1 3 19 1 7 14 2 4 5 10 12 1 1 10 1 10 18 2 7 10 8 19 2 3 11 8 9 2 3 5 8 12
12 1 2 5 2 7 18 4 5 2 3 5 8 12 1 1 10 1 10 19 2 3 15 4 19 1 7 14 1 5 9 2 5 14 9 5 1 1 19 2 7 10 8 19 1 1 16
14 2 5 14 9 5 1 1 19 1 1 10 1 3 19 2 7 18 4 5 2 4 5 10 12 2 3 5 8 12 1 10 10 1 5 9 1 1 7 2 7 10 8 19 1 1 10 1 10 19 1 10 18
10 1 10 10 2 5 7 7 7 1 7 14 1 1 10 1 10 18 2 3 15 7 13 2 10 14 5 7 2 3 11 8 9 1 9 11 1 5 9
12 1 5 9 2 5 14 9 5 2 7 18 4 5 2 3 11 8 9 1 1 10 1 9 11 1 1 7 1 7 14 2 4 5 10 12 2 3 15 4 19 1 8 18 1 10 19
10 2 3 15 7 13 1 3 19 1 5 9 1 10 19 2 3 5 8 12 2 7 18 4 5 2 8 14 10 9 2 4 5 10 12 1 10 18 1 1 7
12 1 1 10 1 10 18 1 1 7 1 5 9 2 8 14 10 9 2 7 10 8 19 2 3 15 4 19 2 10 14 5 7 1 8 18 1 10 19 1 1 19 1 1 10
11 1 1 10 1 7 14 1 1 10 2 3 15 4 19 2 5 14 9 5 2 7 18 4 5 1 3 19 1 1 19 2 4 5 10 12 1 5 9 1 10 19
14 2 7 10 8 19 2 8 14 10 9 1 1 19 1 10 19 2 10 14 5 7 1 2 5 2 4 5 10 12 2 5 7 7 7 1 1 16 1 1 7 1 9 11 1 3 19 1 1 10 1 10 18
11 1 10 19 2 10 14 5 7 1 8 18 2 3 11 8 9 1 1 7 1 1 10 2 5 14 9 5 2 3 15 4 19 1 10 18 1 3 19 1 1 19
11 2 5 14 9 5 1 1 10 1 8 18 2 3 15 4 19 2 7 10 8 19 2 3 5 8 12 2 3 11 8 9 2 8 14 10 9 1 10 10 1 9 11 1 3 19
10 1 10 19 2 3 11 8 9 2 5 7 7 7 1 1 16 1 7 14 2 7 18 4 5 2 4 5 10 12 1 1 10 1 8 18 2 5 14 9 5
11 2 10 14 5 7 1 10 19 2 7 10 8 19 2 3 15 4 19 1 1 19 1 8 18 2 8 14 10 9 2 3 11 8 9 1 10 18 2 5 14 9 5 1 2 5
11 1 1 10 2 5 7 7 7 1 1 10 1 9 11 1 7 14 2 3 15 7 13 2 8 14 10 9 1 1 16 2 3 5 8 12 2 5 14 9 5 1 2 5
11 2 5 14 9 5 2 5 7 7 7 1 7 14 1 10 10 2 7 10 8 19 2 3 15 4 19 2 7 18 4 5 1 1 7 2 3 11 8 9 1 1 19 1 8 18
11 1 2 5 2 7 10 8 19 1 10 10 1 9 11 1 8 18 2 10 14 5 7 2 5 14 9 5 1 1 10 1 1 19 2 3 15 7 13 2 8 14 10 9
13 1 10 10 2 5 14 9 5 1 5 9 1 10 19 1 1 10 2 3 5 8 12 1 2 5 2 10 14 5 7 1 1 10 2 8 14 10 9 2 3 15 7 13 1 1 16 1 7 14
11 2 3 15 7 13 1 2 5 1 10 19 1 3 19 1 8 18 1 1 7 1 5 9 1 7 14 2 7 18 4 5 1 1 10 2 5 14 9 5
10 2 7 10 8 19 1 2 5 2 3 11 8 9 1 9 11 2 4 5 10 12 1 10 18 2 7 18 4 5 2 8 14 10 9 2 3 5 8 12 1 10 19
10 1 10 18 1 10 10 1 7 14 1 9 11 2 3 15 7 13 1 2 5 2 8 14 10 9 2 3 5 8 12 1 5 9 1 1 16
""",
    },
    "mk10": {
        "jobs": 20,
        "machines": 15,
        "ref_type": "UB",
        "ref_makespan": 193,
        "raw_url": "https://raw.githubusercontent.com/Lei-Kun/FJSP-benchmarks/main/1_Brandimarte/BrandimarteMk10.fjs",
        "mirror_text": """
20 15 3
12 2 6 5 2 5 2 7 11 6 11 1 2 5 4 8 10 3 18 4 10 9 7 2 7 9 1 7 4 1 8 7 14 9 12 4 7 3 4 13 8 8 2 6 5 3 8 1 19 9 13 10 19 2 16 5 2 16 10 9 3 12 4 11 5 15 2 9 10 10 5 3 7 5 2 8 4 7 4 1 6 6 13 5 11 10 7
13 2 7 11 6 11 4 2 16 10 9 5 9 8 16 2 6 5 2 5 2 2 11 1 9 2 3 12 7 15 4 4 11 10 14 5 10 7 15 4 3 8 1 12 5 5 13 11 5 3 8 1 19 9 13 10 19 2 16 3 4 13 8 8 2 6 4 8 10 3 18 4 10 9 7 4 1 16 5 11 10 17 3 6 2 9 10 10 5 2 5 11 2 11
11 4 3 8 1 12 5 5 13 11 2 2 11 1 9 2 7 9 1 7 2 6 5 2 5 4 1 6 6 13 5 11 10 7 2 9 10 10 5 5 3 8 1 19 9 13 10 19 2 16 4 8 10 3 18 4 10 9 7 4 2 16 10 9 5 9 8 16 2 3 12 7 15 2 2 5 9 19
11 4 4 11 10 14 5 10 7 15 5 3 8 1 19 9 13 10 19 2 16 1 5 15 1 2 5 2 9 10 10 5 2 7 11 6 11 4 1 16 5 11 10 17 3 6 2 10 13 6 11 2 2 5 9 19 3 4 13 8 8 2 6 4 8 10 3 18 4 10 9 7
14 2 7 11 6 11 2 9 10 10 5 4 5 11 7 8 10 11 2 16 2 10 13 6 11 4 1 16 5 11 10 17 3 6 2 7 9 1 7 4 3 8 1 12 5 5 13 11 1 2 5 4 2 16 10 9 5 9 8 16 3 1 15 2 19 9 9 4 1 6 6 13 5 11 10 7 2 2 11 1 9 4 4 11 10 14 5 10 7 15 5 3 8 1 19 9 13 10 19 2 16
11 3 1 15 2 19 9 9 2 7 9 1 7 4 8 10 3 18 4 10 9 7 2 2 5 9 19 4 5 11 7 8 10 11 2 16 4 1 6 6 13 5 11 10 7 2 7 11 6 11 1 2 5 3 7 5 2 8 4 7 4 3 8 1 12 5 5 13 11 1 5 15
14 1 2 5 2 7 11 6 11 2 2 11 1 9 2 9 10 10 5 4 8 10 3 18 4 10 9 7 3 1 15 2 19 9 9 3 7 5 2 8 4 7 4 2 16 10 9 5 9 8 16 4 1 6 6 13 5 11 10 7 1 5 15 4 7 13 10 19 6 18 4 8 4 3 8 1 12 5 5 13 11 4 1 16 5 11 10 17 3 6 2 7 9 1 7
13 4 8 10 3 18 4 10 9 7 2 10 13 6 11 4 5 11 7 8 10 11 2 16 3 4 13 8 8 2 6 5 2 16 10 9 3 12 4 11 5 15 3 1 15 2 19 9 9 4 3 8 1 12 5 5 13 11 3 7 5 2 8 4 7 4 7 13 10 19 6 18 4 8 4 1 6 6 13 5 11 10 7 2 6 5 2 5 4 1 16 5 11 10 17 3 6 4 2 16 10 9 5 9 8 16
11 2 7 11 6 11 3 7 5 2 8 4 7 4 8 10 3 18 4 10 9 7 2 9 10 10 5 4 2 16 10 9 5 9 8 16 3 4 13 8 8 2 6 4 7 13 10 19 6 18 4 8 5 2 16 10 9 3 12 4 11 5 15 4 1 8 7 14 9 12 4 7 2 6 5 2 5 2 2 11 1 9
12 2 9 10 10 5 1 5 15 2 2 5 9 19 3 1 15 2 19 9 9 5 2 16 10 9 3 12 4 11 5 15 4 1 6 6 13 5 11 10 7 4 2 16 10 9 5 9 8 16 4 1 16 5 11 10 17 3 6 2 6 5 2 5 2 3 12 7 15 4 4 11 10 14 5 10 7 15 4 8 10 3 18 4 10 9 7
10 5 2 16 10 9 3 12 4 11 5 15 4 5 11 7 8 10 11 2 16 4 7 13 10 19 6 18 4 8 2 9 10 10 5 1 5 15 2 2 11 1 9 3 4 13 8 8 2 6 2 2 5 9 19 4 8 10 3 18 4 10 9 7 4 1 16 5 11 10 17 3 6
11 2 10 13 6 11 1 5 15 2 9 10 10 5 4 1 8 7 14 9 12 4 7 4 3 8 1 12 5 5 13 11 3 4 13 8 8 2 6 3 7 5 2 8 4 7 1 2 5 4 1 6 6 13 5 11 10 7 4 2 16 10 9 5 9 8 16 2 7 9 1 7
11 3 7 5 2 8 4 7 2 2 5 9 19 4 1 8 7 14 9 12 4 7 4 5 11 7 8 10 11 2 16 3 1 15 2 19 9 9 4 1 16 5 11 10 17 3 6 2 6 5 2 5 2 7 11 6 11 5 3 8 1 19 9 13 10 19 2 16 4 8 10 3 18 4 10 9 7 3 4 13 8 8 2 6
10 2 5 11 2 11 4 8 10 3 18 4 10 9 7 2 7 9 1 7 2 6 5 2 5 4 3 8 1 12 5 5 13 11 1 5 15 2 9 10 10 5 4 1 16 5 11 10 17 3 6 3 4 13 8 8 2 6 2 3 12 7 15
12 4 8 10 3 18 4 10 9 7 1 5 15 3 1 15 2 19 9 9 4 7 13 10 19 6 18 4 8 4 2 16 10 9 5 9 8 16 4 1 8 7 14 9 12 4 7 3 7 5 2 8 4 7 2 10 13 6 11 2 9 10 10 5 2 3 12 7 15 2 6 5 2 5 4 3 8 1 12 5 5 13 11
14 2 7 11 6 11 1 5 15 2 2 5 9 19 4 1 8 7 14 9 12 4 7 1 2 5 4 3 8 1 12 5 5 13 11 3 4 13 8 8 2 6 3 1 15 2 19 9 9 4 4 11 10 14 5 10 7 15 2 6 5 2 5 2 9 10 10 5 2 5 11 2 11 5 3 8 1 19 9 13 10 19 2 16 2 10 13 6 11
13 4 7 13 10 19 6 18 4 8 5 2 16 10 9 3 12 4 11 5 15 3 4 13 8 8 2 6 2 7 11 6 11 2 10 13 6 11 4 2 16 10 9 5 9 8 16 4 8 10 3 18 4 10 9 7 4 3 8 1 12 5 5 13 11 2 6 5 2 5 2 7 9 1 7 4 1 16 5 11 10 17 3 6 2 2 5 9 19 5 3 8 1 19 9 13 10 19 2 16
11 4 7 13 10 19 6 18 4 8 4 1 6 6 13 5 11 10 7 4 2 16 10 9 5 9 8 16 2 10 13 6 11 2 2 5 9 19 2 5 11 2 11 5 2 16 10 9 3 12 4 11 5 15 2 6 5 2 5 3 1 15 2 19 9 9 1 2 5 4 4 11 10 14 5 10 7 15
13 2 2 5 9 19 2 6 5 2 5 3 4 13 8 8 2 6 2 7 9 1 7 2 3 12 7 15 1 5 15 4 1 16 5 11 10 17 3 6 3 1 15 2 19 9 9 2 10 13 6 11 2 2 11 1 9 3 7 5 2 8 4 7 4 3 8 1 12 5 5 13 11 4 5 11 7 8 10 11 2 16
13 4 1 16 5 11 10 17 3 6 3 1 15 2 19 9 9 4 3 8 1 12 5 5 13 11 2 2 5 9 19 4 2 16 10 9 5 9 8 16 1 5 15 4 5 11 7 8 10 11 2 16 4 8 10 3 18 4 10 9 7 2 7 11 6 11 4 1 8 7 14 9 12 4 7 4 7 13 10 19 6 18 4 8 2 3 12 7 15 2 7 9 1 7
""",
    },
}


@dataclass
class FjspInstance:
    name: str
    num_jobs: int
    num_machines: int
    jobs: List[List[List[Tuple[int, int]]]]


def _download_text(url: str, timeout_s: float = 15.0) -> str:
    with urllib.request.urlopen(url, timeout=float(timeout_s)) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def load_instance_text(instance_key: str, *, allow_download: bool = True) -> str:
    meta = DATASET_SOURCES.get(instance_key)
    if not meta:
        raise KeyError(f"unknown instance_key: {instance_key!r}")
    url = str(meta.get("raw_url") or "").strip()
    mirror = textwrap.dedent(str(meta.get("mirror_text") or "")).strip()
    if allow_download and url:
        try:
            txt = _download_text(url)
            if txt and txt.strip():
                return txt
        except Exception:
            pass
    if mirror:
        return mirror
    raise RuntimeError(f"{instance_key} 既无法下载也缺少 mirror_text")


def parse_fjsp(text: str, *, name: str) -> FjspInstance:
    tokens = [token for token in str(text or "").split() if token.strip()]
    parser = _TokenParser(tokens=tokens, name=name)
    num_jobs = parser.next_int()
    num_machines = parser.next_int()
    parser.next_int()
    if num_jobs <= 0 or num_machines <= 0:
        raise ValueError(f"{name}: header 非法 num_jobs={num_jobs} num_machines={num_machines}")
    jobs = _parse_jobs(parser, num_jobs=num_jobs, num_machines=num_machines)
    parser.assert_consumed()
    return FjspInstance(name=name, num_jobs=num_jobs, num_machines=num_machines, jobs=jobs)


class _TokenParser:
    def __init__(self, *, tokens: List[str], name: str) -> None:
        if len(tokens) < 3:
            raise ValueError(f"{name}: token 太少，无法解析 header")
        self.tokens = tokens
        self.name = name
        self.pos = 0

    def next_int(self) -> int:
        if self.pos >= len(self.tokens):
            raise ValueError(f"{self.name}: token 不足（pos={self.pos} total={len(self.tokens)}）")
        token = self.tokens[self.pos]
        self.pos += 1
        try:
            return int(float(token))
        except Exception:
            raise ValueError(f"{self.name}: 非法整数 token: {token!r} (pos={self.pos-1})") from None

    def assert_consumed(self) -> None:
        if self.pos == len(self.tokens):
            return
        extra = " ".join(self.tokens[self.pos : min(len(self.tokens), self.pos + 10)])
        raise ValueError(
            f"{self.name}: 解析后仍有多余 token（pos={self.pos} total={len(self.tokens)}），extra_sample={extra!r}"
        )


def _parse_jobs(
    parser: _TokenParser,
    *,
    num_jobs: int,
    num_machines: int,
) -> List[List[List[Tuple[int, int]]]]:
    jobs: List[List[List[Tuple[int, int]]]] = []
    for job_index in range(num_jobs):
        jobs.append(_parse_job(parser, job_index=job_index, num_machines=num_machines))
    return jobs


def _parse_job(
    parser: _TokenParser,
    *,
    job_index: int,
    num_machines: int,
) -> List[List[Tuple[int, int]]]:
    op_count = parser.next_int()
    if op_count <= 0:
        raise ValueError(f"{parser.name}: job{job_index+1} op_count 非法：{op_count}")
    return [_parse_options(parser, job_index=job_index, op_index=op_index, num_machines=num_machines) for op_index in range(op_count)]


def _parse_options(
    parser: _TokenParser,
    *,
    job_index: int,
    op_index: int,
    num_machines: int,
) -> List[Tuple[int, int]]:
    option_count = parser.next_int()
    if option_count <= 0:
        raise ValueError(f"{parser.name}: job{job_index+1} op{op_index+1} opt_count 非法：{option_count}")
    return [_parse_machine_option(parser, job_index=job_index, op_index=op_index, num_machines=num_machines) for _ in range(option_count)]


def _parse_machine_option(
    parser: _TokenParser,
    *,
    job_index: int,
    op_index: int,
    num_machines: int,
) -> Tuple[int, int]:
    machine_index = parser.next_int()
    duration = parser.next_int()
    if machine_index < 1 or machine_index > num_machines:
        raise ValueError(
            f"{parser.name}: job{job_index+1} op{op_index+1} machine_index 越界：{machine_index} not in [1,{num_machines}]"
        )
    if duration <= 0:
        raise ValueError(f"{parser.name}: job{job_index+1} op{op_index+1} duration 非正：{duration}")
    return machine_index, duration


def choose_machine_for_op(
    options: List[Tuple[int, int]],
    *,
    strategy: str,
    machine_load_hours: Dict[int, float],
    rng: Optional[Any] = None,
) -> Tuple[int, int]:
    if not options:
        raise ValueError("empty options")
    key = (strategy or "").strip()
    if key == "A_shortest":
        return min(options, key=lambda item: (item[1], item[0]))
    if key == "B_balanced":
        return min(options, key=lambda item: (_projected_load(item, machine_load_hours), item[1], item[0]))
    if key == "C_random":
        rr = rng or __import__("random")
        return rr.choice(list(options))
    raise ValueError(f"unknown machine fold strategy: {strategy!r}")


def _projected_load(option: Tuple[int, int], machine_load_hours: Dict[int, float]) -> float:
    machine_index, duration = option
    return float(machine_load_hours.get(machine_index, 0.0) or 0.0) + float(duration)


def assign_machines(instance: FjspInstance, *, strategy: str, seed: int = 0) -> List[List[Tuple[int, int]]]:
    import random as _random

    rng = _random.Random(int(seed))
    load: Dict[int, float] = {index: 0.0 for index in range(1, int(instance.num_machines) + 1)}
    assigned_jobs: List[List[Tuple[int, int]]] = []
    for ops in instance.jobs:
        assigned_jobs.append(_assign_job_ops(ops, strategy=strategy, machine_load_hours=load, rng=rng))
    return assigned_jobs


def _assign_job_ops(
    ops: List[List[Tuple[int, int]]],
    *,
    strategy: str,
    machine_load_hours: Dict[int, float],
    rng: Any,
) -> List[Tuple[int, int]]:
    assigned: List[Tuple[int, int]] = []
    for option_list in ops:
        machine_index, duration = choose_machine_for_op(
            option_list,
            strategy=strategy,
            machine_load_hours=machine_load_hours,
            rng=rng,
        )
        assigned.append((machine_index, duration))
        machine_load_hours[machine_index] = float(machine_load_hours.get(machine_index, 0.0) or 0.0) + float(duration)
    return assigned
