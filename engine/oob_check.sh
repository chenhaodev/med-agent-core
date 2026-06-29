#!/usr/bin/env bash
# oob_check.sh — generic, pack-driven out-of-bounds detector (no API, <10ms).
# Replaces every fork's hardcoded bin/oob_check.sh: reads the typed blocklist
# from the pack manifest (oob.blocklist) instead of inline KEYWORDS_* vars.
#
# Usage:
#   engine/oob_check.sh --pack <name|dir> [--mode patient|doctor] "问题文本"
#   echo "问题" | engine/oob_check.sh --pack <name|dir>
#
# Output (action-based model, identical to the forks):
#   in_scope                  — enters the normal pipeline
#   out_of_scope:<type>       — first matching blocklist rule's type
#
# Parity contract: rules are tested in manifest order, first match wins; a rule
# fires only when `pattern` matches AND its optional `unless` guard does not —
# reproducing each fork's "comorbidity is still in-scope" exclusions exactly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_pack.sh
source "$SCRIPT_DIR/lib_pack.sh"

PACK_DIR=""
MODE="patient"
QUESTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack) PACK_DIR="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    *) QUESTION="$1"; shift ;;
  esac
done
[[ -z "$PACK_DIR" ]] && { echo "oob_check: --pack required" >&2; exit 2; }
PACK_DIR=$(resolve_pack_dir "$PACK_DIR") || { echo "oob_check: pack not found（--pack 接受包名或含 pack.yaml 的目录）" >&2; exit 2; }
[[ -z "$QUESTION" ]] && QUESTION="$(cat || true)"
[[ -z "$QUESTION" ]] && { echo "in_scope"; exit 0; }

MANIFEST="$PACK_DIR/pack.yaml"
# Pull the normalized blocklist through the validated loader (single source of truth),
# then match in Python to keep regex semantics platform-independent.
QUESTION="$QUESTION" MANIFEST="$MANIFEST" SCRIPT_DIR="$SCRIPT_DIR" python3 - <<'PY'
import os, re, json, subprocess, sys

here = os.environ["SCRIPT_DIR"]
manifest = os.environ["MANIFEST"]
question = os.environ["QUESTION"]

out = subprocess.run(["python3", os.path.join(here, "load_pack.py"), manifest],
                     capture_output=True, text=True)
if out.returncode != 0:
    sys.stderr.write(out.stderr)
    print("in_scope")  # fail open: never wrongly block on a loader error
    sys.exit(0)

cfg = json.loads(out.stdout)
for rule in cfg["oob"]["blocklist"]:
    if not re.search(rule["pattern"], question):
        continue
    guard = rule.get("unless")
    if guard and re.search(guard, question):
        continue
    guard_all = rule.get("unless_all")
    if guard_all and all(re.search(g, question) for g in guard_all):
        continue
    print("out_of_scope:" + rule["type"])
    sys.exit(0)
print("in_scope")
PY
