#!/usr/bin/env bash
# call_llm.sh — call the DeepSeek chat API (de-domained lift of every fork's
# bin/call_deepseek.sh; the forks' versions were already domain-free).
# Usage: echo '<json_payload>' | engine/call_llm.sh [--pack PACK_DIR] [--no-cache]
# Output: the model's reply text (plain, no JSON wrapper).
#
# Response cache (on by default): content-addressed by the payload's sha256
# (.cache/deepseek/<sha>.txt under the core root). A hit returns with zero
# network and needs no API key. Bypass: NO_CACHE=1 or --no-cache.
#
# .env lookup (later wins): <core root>/.env then <pack>/.env. Keeps a pack's
# own key/model if present, else falls back to the shared core config.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ROOT="$(dirname "$SCRIPT_DIR")"

NO_CACHE="${NO_CACHE:-0}"
PACK_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cache) NO_CACHE=1; shift ;;
    --pack) PACK_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# shellcheck disable=SC1091
[[ -f "$CORE_ROOT/.env" ]] && source "$CORE_ROOT/.env"
# shellcheck disable=SC1091
[[ -n "$PACK_DIR" && -f "$PACK_DIR/.env" ]] && source "$PACK_DIR/.env"

DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
DEEPSEEK_TIMEOUT="${DEEPSEEK_TIMEOUT:-60}"
DEEPSEEK_MAX_RETRIES="${DEEPSEEK_MAX_RETRIES:-3}"
API_URL="${DEEPSEEK_API_URL:-https://api.deepseek.com/v1/chat/completions}"
CACHE_DIR="$CORE_ROOT/.cache/deepseek"

PAYLOAD="$(cat)"
[[ -z "$PAYLOAD" ]] && { echo "错误：call_llm.sh 未收到任何 JSON payload（stdin 为空）。" >&2; exit 1; }

# ─── cache read (hit = zero network, no key needed) ───────────────────────
CACHE_FILE=""
if [[ "$NO_CACHE" != "1" ]]; then
  CACHE_KEY=$(printf '%s' "$PAYLOAD" | shasum -a 256 2>/dev/null | cut -d' ' -f1) || CACHE_KEY=""
  if [[ -n "$CACHE_KEY" ]]; then
    CACHE_FILE="$CACHE_DIR/${CACHE_KEY}.txt"
    if [[ -s "$CACHE_FILE" ]]; then
      cat "$CACHE_FILE"
      exit 0
    fi
  fi
fi

if [[ -z "$DEEPSEEK_API_KEY" ]]; then
  echo "错误：未设置 DEEPSEEK_API_KEY（缓存未命中需真实调用）。请在 core 或 pack 的 .env 中配置。" >&2
  exit 1
fi

attempt=0
while true; do
  attempt=$((attempt + 1))
  HTTP_RESPONSE=$(curl -s -w "\n__HTTP_STATUS__%{http_code}" \
    --max-time "$DEEPSEEK_TIMEOUT" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
    -d "$PAYLOAD" 2>&1) || { echo "错误：curl 请求失败（网络问题或超时）。" >&2; exit 1; }

  HTTP_BODY="$(echo "$HTTP_RESPONSE" | sed '$d')"
  HTTP_STATUS="$(echo "$HTTP_RESPONSE" | tail -1 | sed 's/__HTTP_STATUS__//')"

  if [[ "$HTTP_STATUS" == "200" ]]; then
    CONTENT=$(echo "$HTTP_BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data['choices'][0]['message']['content']
if not content or not content.strip():
    print('错误：API 返回空 content', file=sys.stderr); sys.exit(1)
print(content)
" 2>&1) || {
      echo "错误：解析 API 响应失败或 content 为空，将重试。" >&2
      if [[ $attempt -ge $DEEPSEEK_MAX_RETRIES ]]; then echo "响应：$HTTP_BODY" >&2; exit 1; fi
      sleep $((attempt * 2)); continue
    }
    if [[ "$NO_CACHE" != "1" && -n "$CACHE_FILE" ]]; then
      mkdir -p "$CACHE_DIR" 2>/dev/null || true
      printf '%s\n' "$CONTENT" > "$CACHE_FILE" 2>/dev/null || true
    fi
    echo "$CONTENT"
    exit 0
  fi

  if [[ "$HTTP_STATUS" == "429" || "$HTTP_STATUS" == "500" || "$HTTP_STATUS" == "502" || "$HTTP_STATUS" == "503" ]]; then
    if [[ $attempt -ge $DEEPSEEK_MAX_RETRIES ]]; then
      echo "错误：API 返回 HTTP ${HTTP_STATUS}，已重试 $attempt 次，放弃。" >&2
      echo "响应：$HTTP_BODY" >&2; exit 1
    fi
    SLEEP_SEC=$((attempt * 2))
    echo "警告：HTTP ${HTTP_STATUS}，${SLEEP_SEC}s 后重试（第 ${attempt}/${DEEPSEEK_MAX_RETRIES} 次）..." >&2
    sleep "$SLEEP_SEC"; continue
  fi

  echo "错误：API 返回 HTTP ${HTTP_STATUS}。" >&2
  echo "响应：$HTTP_BODY" >&2; exit 1
done
