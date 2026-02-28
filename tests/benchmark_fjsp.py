from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import textwrap
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# -------------------------
# Dataset sources (Brandimarte 1993, FJSP)
# - Prefer download from GitHub raw
# - Fallback to embedded mirrors to allow offline reproduction
# -------------------------

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
    jobs: List[List[List[Tuple[int, int]]]]  # job -> op -> options[(machine_idx, duration)]


def _download_text(url: str, timeout_s: float = 15.0) -> str:
    with urllib.request.urlopen(url, timeout=float(timeout_s)) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def load_instance_text(instance_key: str, *, allow_download: bool = True) -> str:
    meta = DATASET_SOURCES.get(instance_key)
    if not meta:
        raise KeyError(f"unknown instance_key: {instance_key!r}")
    url = str(meta.get("raw_url") or "").strip()
    mirror = str(meta.get("mirror_text") or "")
    mirror = textwrap.dedent(mirror).strip()
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
    toks = [t for t in str(text or "").split() if t.strip() != ""]
    if len(toks) < 3:
        raise ValueError(f"{name}: token 太少，无法解析 header")
    pos = 0

    def _next_int() -> int:
        nonlocal pos
        if pos >= len(toks):
            raise ValueError(f"{name}: token 不足（pos={pos} total={len(toks)}）")
        v = toks[pos]
        pos += 1
        try:
            return int(float(v))
        except Exception:
            raise ValueError(f"{name}: 非法整数 token: {v!r} (pos={pos-1})") from None

    num_jobs = _next_int()
    num_machines = _next_int()
    _avg_flex = _next_int()  # ignore

    if num_jobs <= 0 or num_machines <= 0:
        raise ValueError(f"{name}: header 非法 num_jobs={num_jobs} num_machines={num_machines}")

    jobs: List[List[List[Tuple[int, int]]]] = []
    for j in range(num_jobs):
        op_count = _next_int()
        if op_count <= 0:
            raise ValueError(f"{name}: job{j+1} op_count 非法：{op_count}")
        ops: List[List[Tuple[int, int]]] = []
        for k in range(op_count):
            opt_count = _next_int()
            if opt_count <= 0:
                raise ValueError(f"{name}: job{j+1} op{k+1} opt_count 非法：{opt_count}")
            options: List[Tuple[int, int]] = []
            for _ in range(opt_count):
                midx = _next_int()
                dur = _next_int()
                if midx < 1 or midx > num_machines:
                    raise ValueError(f"{name}: job{j+1} op{k+1} machine_index 越界：{midx} not in [1,{num_machines}]")
                if dur <= 0:
                    raise ValueError(f"{name}: job{j+1} op{k+1} duration 非正：{dur}")
                options.append((midx, dur))
            ops.append(options)
        jobs.append(ops)

    # strict consumption: no extra tokens
    if pos != len(toks):
        extra = " ".join(toks[pos : min(len(toks), pos + 10)])
        raise ValueError(f"{name}: 解析后仍有多余 token（pos={pos} total={len(toks)}），extra_sample={extra!r}")

    return FjspInstance(name=name, num_jobs=num_jobs, num_machines=num_machines, jobs=jobs)


def _mid(i: int) -> str:
    return f"MC{int(i):02d}"


def _oid(i: int) -> str:
    return f"OP{int(i):02d}"


def choose_machine_for_op(
    options: List[Tuple[int, int]],
    *,
    strategy: str,
    machine_load_hours: Dict[int, float],
    rng: Optional[Any] = None,
) -> Tuple[int, int]:
    """
    Returns (machine_idx, duration).

    strategy:
      - A_shortest: pick min duration
      - B_balanced: pick min(load[m] + duration)
      - C_random: uniform random (for optional stress test)
    """
    if not options:
        raise ValueError("empty options")
    key = (strategy or "").strip()
    if key == "A_shortest":
        return min(options, key=lambda x: (x[1], x[0]))
    if key == "B_balanced":
        return min(options, key=lambda x: (float(machine_load_hours.get(x[0], 0.0) or 0.0) + float(x[1]), x[1], x[0]))
    if key == "C_random":
        rr = rng or __import__("random")
        return rr.choice(list(options))
    raise ValueError(f"unknown machine fold strategy: {strategy!r}")


def assign_machines(instance: FjspInstance, *, strategy: str, seed: int = 0) -> List[List[Tuple[int, int]]]:
    """
    Returns job_ops[j][k] = (machine_idx, duration).
    """
    import random as _random

    rng = _random.Random(int(seed))
    load: Dict[int, float] = {i: 0.0 for i in range(1, int(instance.num_machines) + 1)}
    out: List[List[Tuple[int, int]]] = []
    for ops in instance.jobs:
        assigned: List[Tuple[int, int]] = []
        for opt_list in ops:
            m, d = choose_machine_for_op(opt_list, strategy=strategy, machine_load_hours=load, rng=rng)
            assigned.append((m, d))
            load[m] = float(load.get(m, 0.0) or 0.0) + float(d)
        out.append(assigned)
    return out


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent] + list(here.parents):
        if (p / "app.py").exists() and (p / "schema.sql").exists():
            return p
    raise RuntimeError("未找到项目根目录（要求存在 app.py 与 schema.sql）")


def seed_calendar_24h(conn, *, start_date: date, days: int) -> None:
    from data.repositories import CalendarRepository

    repo = CalendarRepository(conn, logger=None)
    for i in range(int(days)):
        d = start_date + timedelta(days=i)
        ds = d.isoformat()
        repo.upsert(
            {
                "date": ds,
                "day_type": "workday",
                "shift_start": "00:00",
                "shift_end": "00:00",  # 00:00 <= 00:00 => treated as next day end (24h)
                "shift_hours": 24.0,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": "fjsp_benchmark_24h",
            }
        )


def set_schedule_config(conn, *, algo_mode: str, time_budget_seconds: int) -> None:
    from data.repositories import ConfigRepository

    repo = ConfigRepository(conn, logger=None)
    repo.set("algo_mode", str(algo_mode), description=None)
    repo.set("time_budget_seconds", str(int(time_budget_seconds)), description=None)
    repo.set("objective", "min_overdue", description=None)
    repo.set("dispatch_mode", "batch_order", description=None)
    repo.set("dispatch_rule", "slack", description=None)
    repo.set("freeze_window_enabled", "no", description=None)
    repo.set("freeze_window_days", "0", description=None)
    repo.set("auto_assign_enabled", "no", description=None)
    repo.set("ortools_enabled", "no", description=None)


def insert_minimal_entities(
    conn,
    *,
    instance: FjspInstance,
    machine_assignment: List[List[Tuple[int, int]]],
    due_date: str,
) -> List[str]:
    """
    Insert minimal APS entities for scheduling.
    Returns batch_ids.
    """
    from data.repositories import (
        BatchOperationRepository,
        BatchRepository,
        MachineRepository,
        OperatorMachineRepository,
        OperatorRepository,
        OpTypeRepository,
        PartRepository,
    )

    # 1) OpType
    ot_repo = OpTypeRepository(conn, logger=None)
    ot_repo.create({"op_type_id": "OT_FJSP", "name": "FJSP", "category": "internal", "default_hours": 0, "remark": "benchmark"})

    # 2) Machines / Operators / Links (1:1)
    m_repo = MachineRepository(conn, logger=None)
    o_repo = OperatorRepository(conn, logger=None)
    link_repo = OperatorMachineRepository(conn, logger=None)
    for i in range(1, int(instance.num_machines) + 1):
        m_repo.create(
            {
                "machine_id": _mid(i),
                "name": f"FJSP-M{i}",
                "op_type_id": "OT_FJSP",
                "category": "benchmark",
                "status": "active",
                "remark": instance.name,
            }
        )
        o_repo.create({"operator_id": _oid(i), "name": f"FJSP-O{i}", "status": "active", "remark": instance.name})
        link_repo.add(_oid(i), _mid(i), skill_level="expert", is_primary="yes")

    # 3) Parts / Batches / BatchOperations
    part_repo = PartRepository(conn, logger=None)
    batch_repo = BatchRepository(conn, logger=None)
    op_repo = BatchOperationRepository(conn, logger=None)

    batch_ids: List[str] = []
    for j in range(int(instance.num_jobs)):
        job_no = j + 1
        part_no = f"FJSP-{instance.name}-J{job_no:02d}"
        batch_id = f"B-{instance.name}-J{job_no:02d}"
        part_repo.create({"part_no": part_no, "part_name": part_no, "route_raw": "", "route_parsed": "yes", "remark": instance.name})
        batch_repo.create(
            {
                "batch_id": batch_id,
                "part_no": part_no,
                "part_name": part_no,
                "quantity": 1,
                "due_date": due_date,
                "priority": "normal",
                "ready_status": "yes",
                "ready_date": None,
                "status": "pending",
                "remark": "fjsp_benchmark",
            }
        )
        batch_ids.append(batch_id)

        assigned_ops = machine_assignment[j]
        for k, (midx, dur) in enumerate(assigned_ops):
            seq = k + 1
            op_repo.create(
                {
                    "op_code": f"OP-{instance.name}-J{job_no:02d}-S{seq:02d}",
                    "batch_id": batch_id,
                    "piece_id": "1",
                    "seq": int(seq),
                    "op_type_id": "OT_FJSP",
                    "op_type_name": "FJSP",
                    "source": "internal",
                    "machine_id": _mid(midx),
                    "operator_id": _oid(midx),
                    "supplier_id": None,
                    "setup_hours": 0.0,
                    "unit_hours": float(dur),
                    "ext_days": None,
                    "status": "pending",
                }
            )

    return batch_ids


def run_one_case(
    *,
    repo_root: Path,
    instance_key: str,
    fold_strategy: str,
    algo_mode: str,
    time_budget_seconds: int,
    allow_download: bool,
    calendar_days: int,
    start_dt: datetime,
    due_date: str,
) -> Dict[str, Any]:
    # Local imports (after sys.path)
    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler.schedule_service import ScheduleService
    from data.repositories import ScheduleHistoryRepository, ScheduleRepository

    meta = DATASET_SOURCES[instance_key]
    text = load_instance_text(instance_key, allow_download=allow_download)
    inst = parse_fjsp(text, name=instance_key)

    assignment = assign_machines(inst, strategy=fold_strategy, seed=0)

    out: Dict[str, Any] = {
        "instance": instance_key,
        "jobs": int(inst.num_jobs),
        "machines": int(inst.num_machines),
        "ref_type": meta.get("ref_type"),
        "ref_makespan": meta.get("ref_makespan"),
        "fold_strategy": fold_strategy,
        "algo_mode": algo_mode,
        "time_budget_seconds": int(time_budget_seconds),
    }

    tmpdir = tempfile.mkdtemp(prefix=f"aps_fjsp_{instance_key}_{fold_strategy}_{algo_mode}_")
    db_path = os.path.join(tmpdir, "bench.db")
    ensure_schema(db_path, logger=None, schema_path=str(repo_root / "schema.sql"))
    conn = get_connection(db_path)
    try:
        seed_calendar_24h(conn, start_date=start_dt.date(), days=int(calendar_days))
        set_schedule_config(conn, algo_mode=algo_mode, time_budget_seconds=int(time_budget_seconds))
        batch_ids = insert_minimal_entities(conn, instance=inst, machine_assignment=assignment, due_date=due_date)
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=None)
        run_ret = svc.run_schedule(batch_ids=batch_ids, start_dt=start_dt, simulate=False, enforce_ready=False)
        version = int(run_ret.get("version") or 0)
        out["version"] = version
        out["run_return"] = run_ret

        hist_repo = ScheduleHistoryRepository(conn, logger=None)
        hist = hist_repo.get_by_version(version)
        if not hist or not hist.result_summary:
            raise RuntimeError(f"{instance_key}: 未找到 ScheduleHistory(version={version}) 或 result_summary 为空")
        summary_obj = json.loads(str(hist.result_summary))
        out["result_summary"] = summary_obj

        metrics = ((summary_obj.get("algo") or {}).get("metrics") or {}) if isinstance(summary_obj, dict) else {}
        out["metrics"] = metrics
        out["time_cost_ms"] = int(summary_obj.get("time_cost_ms") or run_ret.get("time_cost_ms") or 0)
        counts = summary_obj.get("counts") or {}
        out["counts"] = counts

        # Derive makespan
        makespan_h = metrics.get("makespan_hours")
        try:
            makespan_h = float(makespan_h) if makespan_h is not None else None
        except Exception:
            makespan_h = None

        span_repo = ScheduleRepository(conn, logger=None)
        span = span_repo.get_version_time_span(version)
        out["schedule_span"] = span
        if makespan_h is None and span:
            st = datetime.strptime(span["start_time"], "%Y-%m-%d %H:%M:%S")
            et = datetime.strptime(span["end_time"], "%Y-%m-%d %H:%M:%S")
            makespan_h = (et - st).total_seconds() / 3600.0
        out["makespan_hours"] = makespan_h

        ref = float(meta.get("ref_makespan") or 0.0)
        out["gap_percent"] = None
        if makespan_h is not None and ref > 0:
            out["gap_percent"] = (float(makespan_h) - ref) / ref * 100.0

        # Validity gate
        failed_ops = None
        try:
            failed_ops = int((counts or {}).get("failed_ops") or 0)
        except Exception:
            failed_ops = None
        out["failed_ops"] = failed_ops
        out["valid"] = bool(failed_ops == 0 and makespan_h is not None)
        out["tmpdir"] = tmpdir
        out["db_path"] = db_path
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _fmt_float(v: Any, nd: int = 4) -> str:
    try:
        f = float(v)
    except Exception:
        return "NA"
    return f"{f:.{nd}f}"


def write_report_md(repo_root: Path, runs: Sequence[Dict[str, Any]]) -> str:
    out_dir = repo_root / "evidence" / "Benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "fjsp_benchmark_report.md"

    # group by instance
    by_inst: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_inst.setdefault(str(r.get("instance") or ""), []).append(r)

    lines: List[str] = []
    lines.append("# FJSP 基准评测报告（APS）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`")
    lines.append("- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。")
    lines.append("- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。")
    lines.append("")

    inst_keys = sorted([k for k in by_inst.keys() if k], key=lambda x: x)
    lines.append("## 汇总（按实例）")
    lines.append("")
    for ik in inst_keys:
        lst = by_inst.get(ik) or []
        if not lst:
            continue
        meta = DATASET_SOURCES.get(ik) or {}
        ref_type = meta.get("ref_type")
        ref_ms = meta.get("ref_makespan")
        jobs = lst[0].get("jobs")
        machines = lst[0].get("machines")
        lines.append(f"- **{ik}**（{jobs} jobs x {machines} machines；{ref_type}={ref_ms}）")

        valids = [x for x in lst if x.get("valid")]
        if valids:
            best = min(valids, key=lambda x: float(x.get("makespan_hours") or 1e18))
            lines.append(
                f"  - 最佳：{best.get('algo_mode')} + {best.get('fold_strategy')} makespan={_fmt_float(best.get('makespan_hours'))}h gap={_fmt_float(best.get('gap_percent'),2)}% time={best.get('time_cost_ms')}ms"
            )
        else:
            lines.append("  - 最佳：NA（所有 run 都无有效排程或 failed_ops>0）")

        # list each run (small, bullet)
        for r in sorted(lst, key=lambda x: (str(x.get("algo_mode")), str(x.get("fold_strategy")))):
            ms = r.get("makespan_hours")
            gap = r.get("gap_percent")
            tc = r.get("time_cost_ms")
            failed = r.get("failed_ops")
            util = ((r.get("metrics") or {}).get("machine_util_avg")) if isinstance(r.get("metrics"), dict) else None
            cv = ((r.get("metrics") or {}).get("machine_load_cv")) if isinstance(r.get("metrics"), dict) else None
            lines.append(
                "  - "
                + f"{r.get('algo_mode')} + {r.get('fold_strategy')}: "
                + f"makespan={_fmt_float(ms)}h gap={_fmt_float(gap,2)}% "
                + f"failed_ops={failed} time={tc}ms "
                + f"util_avg={_fmt_float(util,6)} load_cv={_fmt_float(cv,6)}"
            )
        lines.append("")

    lines.append("## 结论（自动摘要）")
    lines.append("")
    lines.append("- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。")
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="mk01,mk04,mk06,mk08,mk10", help="comma separated instance keys")
    ap.add_argument("--allow-download", action="store_true", help="try downloading raw .fjs from GitHub")
    ap.add_argument("--calendar-days", type=int, default=120, help="how many days to seed 24h calendar")
    ap.add_argument("--time-budget", type=int, default=20, help="time_budget_seconds for improve mode")
    ap.add_argument("--full-matrix", action="store_true", help="run all fold strategies for all algo modes")
    args = ap.parse_args(list(argv) if argv is not None else None)

    repo_root = find_repo_root()
    sys.path.insert(0, str(repo_root))

    selected = [x.strip().lower() for x in str(args.instances or "").split(",") if x.strip()]
    for k in selected:
        if k not in DATASET_SOURCES:
            raise SystemExit(f"unknown instance key: {k!r}")

    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    due_date = "2099-12-31"

    # default minimal matrix:
    # - greedy: A_shortest + B_balanced
    # - improve: B_balanced
    fold_strategies = ["A_shortest", "B_balanced"]
    runs: List[Dict[str, Any]] = []
    for ik in selected:
        for fold in fold_strategies:
            # greedy always
            runs.append(
                run_one_case(
                    repo_root=repo_root,
                    instance_key=ik,
                    fold_strategy=fold,
                    algo_mode="greedy",
                    time_budget_seconds=int(args.time_budget),
                    allow_download=bool(args.allow_download),
                    calendar_days=int(args.calendar_days),
                    start_dt=start_dt,
                    due_date=due_date,
                )
            )
            if args.full_matrix:
                runs.append(
                    run_one_case(
                        repo_root=repo_root,
                        instance_key=ik,
                        fold_strategy=fold,
                        algo_mode="improve",
                        time_budget_seconds=int(args.time_budget),
                        allow_download=bool(args.allow_download),
                        calendar_days=int(args.calendar_days),
                        start_dt=start_dt,
                        due_date=due_date,
                    )
                )
        if not args.full_matrix:
            runs.append(
                run_one_case(
                    repo_root=repo_root,
                    instance_key=ik,
                    fold_strategy="B_balanced",
                    algo_mode="improve",
                    time_budget_seconds=int(args.time_budget),
                    allow_download=bool(args.allow_download),
                    calendar_days=int(args.calendar_days),
                    start_dt=start_dt,
                    due_date=due_date,
                )
            )

    report_path = write_report_md(repo_root, runs)
    print(report_path)
    # also print short console summary
    valid_cnt = sum(1 for r in runs if r.get("valid"))
    print(f"runs={len(runs)} valid={valid_cnt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

