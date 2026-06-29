#!/usr/bin/env bash
# ask.sh — end-to-end question pipeline for a pack.
# oob_check → router → build_prompt → call_llm → postprocess.
# Generic replacement for every fork's bin/ask.sh.
#
# Usage:
#   engine/ask.sh --pack <name|dir> [--mode patient|doctor] [--domain D] [--debug] "问题"
# (prefer the top-level dispatcher: `med-agent ask --pack <name|dir> ...`)
# --pack accepts a pack name (resolved to packs/<name>) or a pack directory.
#
# --domain D : force a routing tag, skip the router
# --debug    : print routing / payload diagnostics to stderr
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_pack.sh
source "$SCRIPT_DIR/lib_pack.sh"

PACK_DIR=""
MODE="patient"
FORCE_DOMAIN=""
DEBUG=false
QUESTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack) PACK_DIR="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --domain) FORCE_DOMAIN="$2"; shift 2 ;;
    --debug) DEBUG=true; shift ;;
    *) QUESTION="$1"; shift ;;
  esac
done
[[ -z "$PACK_DIR" ]] && { echo "ask: --pack required" >&2; exit 2; }
PACK_DIR=$(resolve_pack_dir "$PACK_DIR") || { echo "ask: pack not found（--pack 接受包名或含 pack.yaml 的目录）" >&2; exit 2; }
[[ -z "$QUESTION" ]] && { echo "用法：med-agent ask --pack <包名|目录> [--mode M] [--domain D] \"问题\"" >&2; exit 1; }

# ─── 0. OOB ────────────────────────────────────────────────────────────────
OOB_RESULT=$("$SCRIPT_DIR/oob_check.sh" --pack "$PACK_DIR" --mode "$MODE" "$QUESTION" 2>/dev/null || echo "in_scope")
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] OOB → $OOB_RESULT" >&2

if [[ "$OOB_RESULT" != "in_scope" ]]; then
  OOB_TYPE="${OOB_RESULT#out_of_scope:}"
  TEMPLATES="$PACK_DIR/prompts/oob_templates.md"
  [[ "$MODE" == "doctor" && -f "$PACK_DIR/prompts/oob_templates_doctor.md" ]] && TEMPLATES="$PACK_DIR/prompts/oob_templates_doctor.md"
  REPLY=$(OOB_TYPE="$OOB_TYPE" TEMPLATES="$TEMPLATES" python3 - <<'PY'
import os, re
with open(os.environ["TEMPLATES"], encoding="utf-8") as f:
    content = f.read()
m = re.search(rf"## {re.escape(os.environ['OOB_TYPE'])}\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
print(m.group(1).strip() if m else "很抱歉，您的问题超出了本系统的覆盖范围，建议咨询专科医生。")
PY
)
  printf '\n═══════════════════════════════════════════════════════\n%s\n═══════════════════════════════════════════════════════\n\n' "$REPLY"
  exit 0
fi

# ─── 1. route ──────────────────────────────────────────────────────────────
if [[ -n "$FORCE_DOMAIN" ]]; then
  DOMAINS="$FORCE_DOMAIN"
else
  DOMAINS=$("$SCRIPT_DIR/router.sh" --pack "$PACK_DIR" "$QUESTION" 2>/dev/null) || DOMAINS=""
fi
[[ -z "$DOMAINS" ]] && DOMAINS=$(python3 "$SCRIPT_DIR/load_pack.py" "$PACK_DIR/pack.yaml" --field routing | python3 -c "import sys,json;print(json.load(sys.stdin).get('fallback','') or '')" 2>/dev/null || true)
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] route → $DOMAINS" >&2

# ─── 2. build prompt ───────────────────────────────────────────────────────
PAYLOAD=$("$SCRIPT_DIR/build_prompt.sh" --pack "$PACK_DIR" --mode "$MODE" "$DOMAINS" "$QUESTION") || {
  echo "错误：构建 prompt 失败。" >&2; exit 1
}
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] payload bytes: $(printf '%s' "$PAYLOAD" | wc -c)" >&2

# ─── 3. call LLM ───────────────────────────────────────────────────────────
RESPONSE=$(printf '%s' "$PAYLOAD" | "$SCRIPT_DIR/call_llm.sh" --pack "$PACK_DIR") || {
  echo "错误：API 调用失败。" >&2; exit 1
}

# ─── 4. postprocess ────────────────────────────────────────────────────────
VALIDATED=$(printf '%s' "$RESPONSE" | "$SCRIPT_DIR/postprocess.sh" --pack "$PACK_DIR" --mode "$MODE") || VALIDATED="$RESPONSE"

printf '\n═══════════════════════════════════════════════════════\n%s\n═══════════════════════════════════════════════════════\n\n' "$VALIDATED"
