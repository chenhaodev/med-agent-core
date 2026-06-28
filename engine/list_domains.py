#!/usr/bin/env python3
"""list_domains.py — enumerate a pack's routable domains.

Used by os-core to generate its domain allowlist (replacing the hardcoded
registry/inner_all_domains.txt) and by humans to inspect a pack.

  - yaml_stack packs: one `specialty:disease` line per knowledge/<sp>/<disease>.yaml
    (the live runtime knowledge catalog).
  - sections_only packs: one line per routing-table domain tag.

Usage: python3 engine/list_domains.py packs/<x>/pack.yaml
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from load_pack import load_pack, PackError  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("error: PyYAML required\n")
    sys.exit(2)


def domains_for(pack: dict) -> list[str]:
    if pack["features"]["knowledge_injection"] == "yaml_stack":
        root = pack["paths"].get("knowledge")
        if not root or not os.path.isdir(root):
            return []
        out = []
        for specialty in sorted(os.listdir(root)):
            sp_dir = os.path.join(root, specialty)
            if not os.path.isdir(sp_dir):
                continue
            for fn in sorted(os.listdir(sp_dir)):
                if fn.endswith(".yaml"):
                    out.append(f"{specialty}:{os.path.splitext(fn)[0]}")
        return out
    # sections_only: routing-table tags
    with open(pack["paths"]["routing_map"], encoding="utf-8") as fh:
        table = yaml.safe_load(fh)
    return [d["domain"] for d in table.get("domains", [])]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    try:
        pack = load_pack(argv[1])
    except PackError as exc:
        sys.stderr.write(f"INVALID {argv[1]}: {exc}\n")
        return 1
    for d in domains_for(pack):
        print(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
