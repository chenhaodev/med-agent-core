#!/usr/bin/env bash
# build_prompt.sh — assemble the DeepSeek API JSON payload for a pack.
# Generic replacement for every fork's bin/build_prompt.sh; branches on the
# pack's features.knowledge_injection:
#   sections_only — inject only sections_dir/<domain>.md (lite ad/neo/sleep/stcc)
#   yaml_stack    — additionally stack per-disease knowledge YAML + guidelines +
#                   safety_floor inline (advanced inner-all/psy)
#
# Usage:
#   engine/build_prompt.sh --pack P [--mode patient|doctor] [--naive] [--reroll] \
#       "domain1 domain2" "问题文本"
# Output: JSON payload on stdout.
#
# --naive  : skip all knowledge injection (diagnostic baseline)
# --reroll : inject VERIFY_FAILED list (read from $_VERIFY_JSON) for --deep self-correct
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_pack.sh
source "$SCRIPT_DIR/lib_pack.sh"

PACK_DIR=""
MODE="patient"
NAIVE=false
REROLL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack)   PACK_DIR="$2"; shift 2 ;;
    --mode)   MODE="$2"; shift 2 ;;
    --naive)  NAIVE=true; shift ;;
    --reroll) REROLL=true; shift ;;
    *) break ;;
  esac
done
[[ -z "$PACK_DIR" ]] && { echo "build_prompt: --pack required" >&2; exit 2; }
PACK_DIR=$(resolve_pack_dir "$PACK_DIR") || { echo "build_prompt: pack not found（--pack 接受包名或含 pack.yaml 的目录）" >&2; exit 2; }
[[ $# -lt 2 ]] && { echo "build_prompt: 用法 --pack P [--mode M] \"domains\" \"问题\"" >&2; exit 1; }

DOMAINS="$1"
QUESTION="$2"
MANIFEST="$PACK_DIR/pack.yaml"

CONFIG=$(python3 "$SCRIPT_DIR/load_pack.py" "$MANIFEST") || {
  echo "build_prompt: pack 校验失败" >&2; exit 1
}

# Model override from env (mirrors the forks sourcing .env for DEEPSEEK_MODEL).
[[ -f "$PACK_DIR/.env" ]] && { set -a; source "$PACK_DIR/.env" 2>/dev/null || true; set +a; }

CONFIG="$CONFIG" DOMAINS="$DOMAINS" QUESTION="$QUESTION" MODE="$MODE" \
NAIVE="$NAIVE" REROLL="$REROLL" MODEL_OVERRIDE="${DEEPSEEK_MODEL:-}" \
VERIFY_JSON="${_VERIFY_JSON:-}" python3 - <<'PY'
import os, json

cfg = json.loads(os.environ["CONFIG"])
domains = os.environ["DOMAINS"].split()
question = os.environ["QUESTION"]
mode = os.environ["MODE"]
naive = os.environ["NAIVE"] == "true"
reroll = os.environ["REROLL"] == "true"
paths = cfg["paths"]
inj = cfg["features"]["knowledge_injection"]

def read(p):
    # rstrip trailing newlines to mirror bash $(cat file) semantics (parity).
    with open(p, encoding="utf-8") as f:
        return f.read().rstrip("\n")

# ─── base prompts (audience variant) ──────────────────────────────────────
if mode == "doctor":
    system_base = read(paths["system_base_doctor"])
    output_schema = read(paths["output_schema_doctor"])
else:
    system_base = read(paths["system_base"])
    output_schema = read(paths["output_schema"])

sections_dir = paths["sections_dir"]
knowledge_dir = paths.get("knowledge")

# ─── knowledge injection ──────────────────────────────────────────────────
chunks = []
seen_specialties = set()

def fmt_baseline(data):
    lines = [f'# 知识栈：{data.get("specialty_zh","")}/{data.get("disease_zh","")}',
             f'## 来源基线（教材）：{data.get("source","")}']
    for e in data.get("entries", []):
        lines.append('')
        lines.append(f'### {e.get("title","")}')
        lines.append(f'来源页：第 {e.get("source_page","?")} 页 | 证据质量：{e.get("evidence_level","")} | 推荐强度：{e.get("recommendation","")}')
        for kp in e.get("key_points", []):
            lines.append(f'- {kp}')
        for mw in e.get("must_warn", []):
            lines.append(f'- ⚠ 必须告知：{mw}')
    return '\n'.join(lines)

def fmt_guideline(data, disease):
    scope = data.get("scope", [])
    if scope and disease not in scope and "all" not in scope:
        return None
    lines = [f'## 指南叠加：{data.get("guideline_name","")} ({data.get("year","")})',
             f'※ 与教材冲突时，以本指南为准（更新于 {data.get("year","")}）']
    for e in data.get("entries", []):
        lines.append('')
        lines.append(f'### {e.get("title","")}')
        lines.append(f'来源：{data.get("guideline_name","")} {data.get("year","")}年 | 证据级别：{e.get("evidence_level","")} | 推荐强度：{e.get("recommendation","")}')
        for kp in e.get("key_points", []):
            lines.append(f'- {kp}')
        for mw in e.get("must_warn", []):
            lines.append(f'- ⚠ 必须告知：{mw}')
    return '\n'.join(lines)

def fmt_floor(data):
    lines = [f'## 患者照护安全底线：{data.get("safety_floor_name","")}',
             '※ 非教材页码来源，系通用患者照护安全网——在「日常该怎么做」或「什么情况要就医」中酌情纳入']
    for e in data.get("entries", []):
        lines.append('')
        lines.append(f'### {e.get("title","")}')
        for item in e.get("items", []):
            lines.append(f'- ⚠ 必须告知：{item}')
    return '\n'.join(lines)

if not naive:
    needs_yaml = inj == "yaml_stack"
    if needs_yaml:
        import yaml
    for tag in domains:
        # sections_only: tag IS the section name. yaml_stack: tag is specialty:disease.
        if needs_yaml:
            specialty, _, disease = tag.partition(":")
            disease = disease or tag
        else:
            specialty, disease = tag, tag
        # section file (load each specialty once)
        if specialty not in seen_specialties:
            seen_specialties.add(specialty)
            sec = os.path.join(sections_dir, f"{specialty}.md")
            if os.path.isfile(sec):
                chunks.append(read(sec))
            else:
                import sys
                sys.stderr.write(f"警告：找不到 section 文件 {sec}，跳过。\n")
        if not needs_yaml:
            continue
        # layer 1: textbook baseline
        baseline = os.path.join(knowledge_dir, specialty, f"{disease}.yaml")
        if os.path.isfile(baseline):
            with open(baseline, encoding="utf-8") as f:
                chunks.append(fmt_baseline(yaml.safe_load(f)))
        # layer 2: guidelines (year-sorted)
        gl_dir = os.path.join(knowledge_dir, specialty, "guidelines")
        if os.path.isdir(gl_dir):
            for gl in sorted(os.listdir(gl_dir)):
                if not gl.endswith(".yaml"):
                    continue
                with open(os.path.join(gl_dir, gl), encoding="utf-8") as f:
                    out = fmt_guideline(yaml.safe_load(f), disease)
                if out:
                    chunks.append(out)
        # layer 3: patient safety floor (patient mode only)
        if mode == "patient":
            floor = os.path.join(knowledge_dir, specialty, "safety_floor", f"{disease}.yaml")
            if os.path.isfile(floor):
                with open(floor, encoding="utf-8") as f:
                    chunks.append(fmt_floor(yaml.safe_load(f)))

sections_content = ""
for c in chunks:
    sections_content += "\n\n---\n\n" + c

# ─── assemble system prompt ───────────────────────────────────────────────
if naive:
    system_prompt = f"{system_base}\n\n---\n\n{output_schema}"
else:
    header = cfg.get("knowledge_header", "以下是与用户问题相关的知识片段，你的回答必须严格基于这些内容：")
    title = cfg.get("knowledge_section_title", "# 当前问题相关知识片段")
    system_prompt = (f"{system_base}\n\n---\n\n{output_schema}\n\n---\n\n"
                     f"{title}\n\n{header}\n{sections_content}")

# ─── user content (reroll injects VERIFY_FAILED) ──────────────────────────
if reroll:
    vj = os.environ.get("VERIFY_JSON", "")
    data = json.loads(vj) if vj.strip() else {}
    failed = [c for c in data.get("claims", []) if c.get("status") == "✗"]
    failed_lines = "\n".join(f"- [{c['kind']}] {c['claim']} — {c['evidence']}" for c in failed)
    schema_note = ("请重新生成完整的证据档案式回答（5段：定义/循证管理/红旗/证据等级汇总/参考）。"
                   if mode == "doctor" else "请重新生成完整的5段式回答。")
    user_content = (f"原始问题：{question}\n\nVERIFY_FAILED — 以下声明在教材原文中找不到支撑，"
                    f"请在修订版中删除或依据注入知识片段更正：\n\n{failed_lines}\n\n{schema_note}")
else:
    user_content = question

# ─── model params from manifest (audience-specific) ───────────────────────
mp = cfg["model"].get(mode) or cfg["model"]["patient"]
model_name = os.environ.get("MODEL_OVERRIDE") or cfg["model"]["name"]

payload = {
    "model": model_name,
    "temperature": mp["temperature"],
    "max_tokens": mp["max_tokens"],
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ],
}
print(json.dumps(payload, ensure_ascii=False))
PY
