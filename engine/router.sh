#!/usr/bin/env bash
# router.sh — generic, pack-driven domain router.
# Replaces every fork's hardcoded bin/router.sh: reads the keyword table from
# the pack's routing.map (category_index.yaml) instead of inline bash vars.
#
# Usage:
#   engine/router.sh --pack PACK_DIR "问题文本"
#   echo "问题" | engine/router.sh --pack PACK_DIR
# Output: space-separated domain tags (e.g. "lifestyle cognitive"), capped at
# max_domains, in table order; fallback used when nothing matches. When the pack
# sets routing.llm_fallback and a key/cache is available, an unmatched question
# is classified zero-shot by the LLM (parity with the forks' DeepSeek fallback).
#
# Parity contract: same grep -E semantics and list-order/cap behavior as the
# original router.sh, so a migrated pack reproduces the old routing exactly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACK_DIR=""
QUESTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack) PACK_DIR="$2"; shift 2 ;;
    *) QUESTION="$1"; shift ;;
  esac
done
[[ -z "$PACK_DIR" ]] && { echo "router: --pack required" >&2; exit 2; }
[[ -z "$QUESTION" ]] && QUESTION="$(cat)"

MANIFEST="$PACK_DIR/pack.yaml"
CONFIG=$(python3 "$SCRIPT_DIR/load_pack.py" "$MANIFEST") || { echo "router: pack 校验失败" >&2; exit 1; }

CONFIG="$CONFIG" QUESTION="$QUESTION" PACK_DIR="$PACK_DIR" SCRIPT_DIR="$SCRIPT_DIR" python3 - <<'PY'
import os, re, json, subprocess, sys
import yaml

cfg = json.loads(os.environ["CONFIG"])
q = os.environ["QUESTION"]
pack_dir = os.environ["PACK_DIR"]
here = os.environ["SCRIPT_DIR"]

map_path = cfg["paths"]["routing_map"]
with open(map_path, encoding="utf-8") as f:
    table = yaml.safe_load(f)

domains = table.get("domains", [])
cap = int(table.get("max_domains", 2))
fallback = cfg["routing"].get("fallback") or table.get("fallback")

# Tiered matching (parity with inner-all): test tier-1 (disease-level) domains
# first; only if none hit, test tier-2 (specialty `:general` fallbacks). Packs
# without tiers (ad) leave tier=1 on every row → single flat pass.
def match_tier(t):
    return [d["domain"] for d in domains
            if int(d.get("tier", 1)) == t and re.search(d["patterns"], q)]

matched = match_tier(1) or match_tier(2)
if matched:
    print(" ".join(matched[:cap]))
    sys.exit(0)

# No keyword hit. Optional zero-shot LLM fallback (parity with forks).
if cfg["routing"].get("llm_fallback"):
    valid = [d["domain"] for d in domains]
    listing = ", ".join(f"{d['domain']}({d['desc']})" if d.get("desc") else d["domain"]
                        for d in domains)
    payload = {
        "model": cfg["model"]["name"],
        "temperature": 0,
        "max_tokens": 30,
        "messages": [
            {"role": "system",
             "content": ("你是一个分类器。从以下领域中选出1-2个最匹配的，"
                         "只输出领域英文标识，用空格分隔，不要其他文字。\n"
                         f"领域：{listing}")},
            {"role": "user", "content": q},
        ],
    }
    try:
        proc = subprocess.run(
            ["bash", os.path.join(here, "call_llm.sh"), "--pack", pack_dir],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True)
        if proc.returncode == 0:
            picked = [w for w in proc.stdout.split() if w in valid][:cap]
            if picked:
                print(" ".join(picked))
                sys.exit(0)
    except Exception:
        pass

print(fallback or "")
PY
