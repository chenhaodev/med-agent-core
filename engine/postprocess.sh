#!/usr/bin/env bash
# postprocess.sh — validate the model's answer against the pack's output contract.
# Generic replacement for every fork's bin/postprocess.sh: required section
# markers + citation pattern come from the manifest (output.<audience>) instead
# of being hardcoded.
#
# Usage: echo "回复" | engine/postprocess.sh --pack P [--mode patient|doctor]
# Output:
#   pass  → original text on stdout, exit 0
#   gaps  → warning on stderr, original text on stdout, exit 1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACK_DIR=""
MODE="patient"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack) PACK_DIR="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -z "$PACK_DIR" ]] && { echo "postprocess: --pack required" >&2; exit 2; }

RESPONSE="$(cat)"
[[ -z "$RESPONSE" ]] && { echo "错误：postprocess.sh 收到空响应。" >&2; exit 1; }

CONFIG=$(python3 "$SCRIPT_DIR/load_pack.py" "$PACK_DIR/pack.yaml") || {
  echo "postprocess: pack 校验失败" >&2; exit 1
}

# Deterministic structure + citation check in Python (stable regex semantics).
MISSING=$(CONFIG="$CONFIG" RESPONSE="$RESPONSE" MODE="$MODE" python3 - <<'PY'
import os, re, json

cfg = json.loads(os.environ["CONFIG"])
resp = os.environ["RESPONSE"]
mode = os.environ["MODE"]
spec = cfg["output"].get(mode) or cfg["output"]["patient"]

missing = [s for s in spec["required_sections"] if s not in resp]

exempt = cfg["output"].get("oob_exempt_pattern")
is_oob = bool(exempt and re.search(exempt, resp))
cite = spec.get("citation_pattern")
requires = spec.get("citation_requires")
if not is_oob and cite and (requires is None or re.search(requires, resp)):
    if not re.search(cite, resp):
        missing.append("【依据】/引用标记")

print("\n".join(missing))
PY
)

if [[ -z "$MISSING" ]]; then
  echo "$RESPONSE"
  exit 0
fi

MISSING_LIST=$(echo "$MISSING" | paste -sd"、" -)
echo "⚠️  输出结构不完整，缺少：${MISSING_LIST}" >&2
echo "$RESPONSE"
exit 1
