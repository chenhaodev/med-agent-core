#!/usr/bin/env bash
# lib_pack.sh — shared pack resolver, sourced (never executed) by the engine
# scripts and the top-level med-agent dispatcher.
#
# A --pack value may be a pack NAME (resolved to <core>/packs/<name>) or a path
# to a pack directory (anything containing a pack.yaml). Keeping the resolution
# here means `med-agent <cmd> --pack internal-med` and a direct
# `engine/<cmd>.sh --pack internal-med` behave identically — no more "works via
# med-agent, 'manifest not found' when called directly".
#
# resolve_pack_dir <name|dir>
#   prints the resolved pack directory on stdout and returns 0, or returns 1
#   (printing nothing) when neither a directory nor a packs/<name> match exists.
resolve_pack_dir() {
  local p="$1"
  [[ -z "$p" ]] && return 1
  if [[ -d "$p" && -f "$p/pack.yaml" ]]; then printf '%s\n' "$p"; return 0; fi
  local core_root
  core_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [[ -f "$core_root/packs/$p/pack.yaml" ]]; then printf '%s\n' "$core_root/packs/$p"; return 0; fi
  return 1
}
