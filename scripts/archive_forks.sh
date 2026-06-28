#!/usr/bin/env bash
# archive_forks.sh — dispose of the migrated forks (PLAN §7).
#
# DESTRUCTIVE / decision-gated: do NOT run until (1) every pack has passed the
# live parity gate (med-agent eval) and (2) you've chosen archive vs delete.
# Requires --yes to actually act; without it, prints what it would do (dry-run).
#
# Modes:
#   --mode readonly  (default) chmod -R a-w each fork (reversible: chmod -R u+w)
#   --mode move      move each fork into ../_archived-forks/
#   --mode delete    rm -rf each fork  (only after archiving knowledge elsewhere!)
set -euo pipefail

FORKS=(med-agent-ad med-agent-inner-all med-agent-neo med-agent-sleep med-agent-stcc med-agent-psy)
CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FOCUS="$(dirname "$CORE")"
MODE="readonly"
CONFIRM=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --yes)  CONFIRM=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

dryrun=$([[ $CONFIRM -eq 1 ]] && echo "" || echo "[DRY-RUN] ")
echo "${dryrun}mode=$MODE  forks=${#FORKS[@]}  base=$FOCUS"

for f in "${FORKS[@]}"; do
  dir="$FOCUS/$f"
  [[ -d "$dir" ]] || { echo "  skip (missing): $f"; continue; }
  case "$MODE" in
    readonly) cmd=(chmod -R a-w "$dir") ;;
    move)     mkdir -p "$FOCUS/_archived-forks"; cmd=(mv "$dir" "$FOCUS/_archived-forks/") ;;
    delete)   cmd=(rm -rf "$dir") ;;
    *) echo "bad mode: $MODE" >&2; exit 2 ;;
  esac
  if [[ $CONFIRM -eq 1 ]]; then
    echo "  ${cmd[*]}"; "${cmd[@]}"
  else
    echo "  would: ${cmd[*]}"
  fi
done
echo "${dryrun}done."
[[ $CONFIRM -eq 0 ]] && echo "Re-run with --yes to apply."
