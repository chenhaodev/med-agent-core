#!/usr/bin/env python3
"""extract_router.py — lift a fork's hardcoded bin/router.sh keyword table into
a pack category_index.yaml (data), preserving check order and tier.

Parses `KW_*="..."` assignments (joining backslash line-continuations) and
`check "specialty:disease" "$KW_*"` calls. A check is tier 2 (specialty-level
fallback, only used when tier 1 misses) iff it sits inside the script's first
`if [[ ${#matched[@]} -eq 0 ]]` fallback block — detected by position, not by
tag name (e.g. infectious:general is a tier-1 catch-all). Rows keep check order.

Usage:
  python3 engine/tools/extract_router.py <fork>/bin/router.sh > category_index.yaml
"""
from __future__ import annotations

import re
import sys


def parse(path: str):
    raw = open(path, encoding="utf-8").read()
    # join backslash continuations
    joined = re.sub(r"\\\n\s*", "", raw)
    # Accept both naming conventions: KW_* (inner-all/psy) and KEYWORDS_* (lite).
    kw = {}
    for m in re.finditer(r'^((?:KW|KEYWORDS)_\w+)="([^"]*)"', joined, re.MULTILINE):
        kw[m.group(1)] = m.group(2)
    # The first `matched==0` block is the specialty-level fallback (tier 2);
    # the second is the LLM fallback. Checks between them are tier 2.
    fb = [m.start() for m in re.finditer(r"\$\{#matched\[@\]\}\s*-eq\s*0", joined)]
    tier2_start = fb[0] if fb else len(joined)
    tier2_end = fb[1] if len(fb) > 1 else len(joined)
    rows = []
    for m in re.finditer(r'check(?:_domain)?\s+"([^"]+)"\s+"\$((?:KW|KEYWORDS)_\w+)"', joined):
        tag, var = m.group(1), m.group(2)
        if var not in kw:
            continue
        tier = 2 if tier2_start <= m.start() < tier2_end else 1
        rows.append((tag, kw[var], tier))
    return rows


def emit(rows, fallback="cardiology:general", max_domains=2):
    def esc(s):
        return s.replace("\\", "\\\\").replace('"', '\\"')
    out = ["# category_index.yaml — extracted from a fork's bin/router.sh by",
           "# engine/tools/extract_router.py (data-driven routing). tier 2 = specialty",
           "# `:general` fallback, only tried when tier 1 (disease-level) misses.",
           f"fallback: {fallback}", f"max_domains: {max_domains}", "domains:"]
    for tag, pat, tier in rows:
        out.append(f'  - domain: "{tag}"')
        if tier != 1:
            out.append(f"    tier: {tier}")
        out.append(f'    patterns: "{esc(pat)}"')
    return "\n".join(out) + "\n"


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    rows = parse(argv[1])
    sys.stderr.write(f"extracted {len(rows)} domains "
                     f"({sum(1 for _,_,t in rows if t==1)} tier-1, "
                     f"{sum(1 for _,_,t in rows if t==2)} tier-2)\n")
    sys.stdout.write(emit(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
