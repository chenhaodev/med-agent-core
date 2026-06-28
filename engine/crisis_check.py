#!/usr/bin/env python3
"""crisis_check.py — fail-closed safety gate for crisis-critical packs (e.g. psy).

Some packs carry a higher safety bar than the generic eval: a missed crisis
signal (false negative) is unacceptable, so it is verified deterministically
against an adversarial crisis_gold set — NOT by the LLM and NOT by the heuristic
refusal-detector in eval_oob (which can't see hotline-style refusal copy).

crisis_gold.yaml shape:
    crisis:   [ ... ]   # MUST each escalate to out_of_scope:<crisis_type>
    in_scope: [ ... ]   # MUST NOT escalate (precision control)

Recall is the hard gate: ANY crisis miss → exit 1 (fail the build). Over-escalation
of a benign line is reported but does not fail (these packs are recall-first).

Usage: python3 engine/crisis_check.py <pack_dir> [--crisis-type crisis]
Exit: 0 all crisis intercepted · 1 a crisis was missed · 2 setup error
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from load_pack import load_pack, PackError  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("error: PyYAML required\n")
    sys.exit(2)


def oob_verdict(pack_dir: str, question: str) -> str:
    r = subprocess.run(
        ["bash", os.path.join(HERE, "oob_check.sh"), "--pack", pack_dir,
         "--mode", "patient", question],
        capture_output=True, text=True)
    return r.stdout.strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pack_dir")
    ap.add_argument("--crisis-type", default="crisis",
                    help="oob type that counts as an escalation (default: crisis)")
    args = ap.parse_args(argv[1:])

    try:
        pack = load_pack(os.path.join(args.pack_dir, "pack.yaml"))
    except PackError as exc:
        sys.stderr.write(f"INVALID pack: {exc}\n")
        return 2
    cg = pack["paths"].get("eval_crisis_gold")
    if not cg:
        sys.stderr.write(f"{pack['id']}: no eval.crisis_gold declared — crisis gate N/A\n")
        return 0

    data = yaml.safe_load(open(cg, encoding="utf-8")) or {}
    crisis = data.get("crisis", []) or []
    benign = data.get("in_scope", []) or []
    want = f"out_of_scope:{args.crisis_type}"

    misses, fps = [], []
    for q in crisis:
        if oob_verdict(args.pack_dir, q) != want:
            misses.append(q)
    for q in benign:
        if oob_verdict(args.pack_dir, q) == want:
            fps.append(q)

    recall = len(crisis) - len(misses)
    print(f"━━━ crisis gate: {pack['id']} ━━━")
    print(f"  recall (must intercept) : {recall}/{len(crisis)}")
    print(f"  precision (must not)    : {len(benign)-len(fps)}/{len(benign)}")
    for q in misses:
        print(f"  ✗ MISSED CRISIS: {q}")
    for q in fps:
        print(f"  ⚠ over-escalated benign: {q}")

    if misses:
        print(f"FAIL: {len(misses)} crisis signal(s) not intercepted (fail-closed).")
        return 1
    print("PASS: all crisis signals intercepted, no false negatives.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
