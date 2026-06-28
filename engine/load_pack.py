#!/usr/bin/env python3
"""load_pack.py — loader + validator for packs/<domain>/pack.yaml.

The single contract boundary between the generic engine and a domain pack
(PLAN §1). Validates the manifest, applies feature defaults, resolves every
referenced path relative to the pack root, and checks those paths exist —
so the engine can trust the returned object without re-checking.

Usage:
    python3 engine/load_pack.py packs/alzheimer/pack.yaml        # print normalized JSON
    python3 engine/load_pack.py packs/alzheimer/pack.yaml --field id

Exit codes: 0 valid · 1 validation error · 2 usage/IO error.

Immutable by design: returns a fresh normalized dict; never mutates the parsed
manifest in place.
"""
from __future__ import annotations

import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("error: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)


FEATURE_DEFAULTS = {
    "knowledge_injection": "sections_only",
    "page_traceable": False,
    "ingest": "manual",
    "deep_eval": False,
}

ENUMS = {
    "knowledge_injection": {"sections_only", "yaml_stack"},
    "ingest": {"manual", "pdf", "markdown"},
    "source.kind": {"consensus", "textbook", "protocol", "guideline"},
    "audience": {"patient", "doctor"},
}

REQUIRED_TOP = ("id", "name", "source", "audiences", "features",
                "output_schema", "sections_dir", "routing", "oob", "output", "model", "eval")

DEFAULT_KNOWLEDGE_HEADER = "以下是与用户问题相关的知识片段，你的回答必须严格基于这些内容："
DEFAULT_KNOWLEDGE_SECTION_TITLE = "# 当前问题相关知识片段"


class PackError(Exception):
    """Raised on any manifest validation failure; message is user-facing."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PackError(msg)


def _resolve(pack_root: str, rel: str, *, must_exist: bool, label: str) -> str:
    """Resolve a pack-relative path to absolute and optionally assert existence."""
    abs_path = os.path.normpath(os.path.join(pack_root, rel))
    if must_exist:
        _require(os.path.exists(abs_path), f"{label}: path not found: {rel} ({abs_path})")
    return abs_path


def load_pack(manifest_path: str) -> dict:
    """Load, validate and normalize a pack manifest. Returns a new dict."""
    manifest_path = os.path.abspath(manifest_path)
    _require(os.path.isfile(manifest_path), f"manifest not found: {manifest_path}")
    pack_root = os.path.dirname(manifest_path)

    with open(manifest_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    _require(isinstance(raw, dict), "manifest must be a YAML mapping")

    for key in REQUIRED_TOP:
        _require(key in raw, f"missing required field: {key}")

    # id must equal directory name
    _require(raw["id"] == os.path.basename(pack_root),
             f"id '{raw['id']}' must equal pack dir name '{os.path.basename(pack_root)}'")

    # source.kind enum
    src = raw["source"]
    _require(isinstance(src, dict) and "kind" in src and "title" in src,
             "source must include title and kind")
    _require(src["kind"] in ENUMS["source.kind"],
             f"source.kind must be one of {sorted(ENUMS['source.kind'])}")

    # audiences enum
    audiences = raw["audiences"]
    _require(isinstance(audiences, list) and audiences, "audiences must be a non-empty list")
    for a in audiences:
        _require(a in ENUMS["audience"], f"audience '{a}' invalid")

    # features: apply defaults immutably, validate enums
    features = {**FEATURE_DEFAULTS, **(raw.get("features") or {})}
    _require(features["knowledge_injection"] in ENUMS["knowledge_injection"],
             "features.knowledge_injection invalid")
    _require(features["ingest"] in ENUMS["ingest"], "features.ingest invalid")

    # eval block
    ev = raw["eval"]
    _require(isinstance(ev, dict) and "gold" in ev and "pass_threshold" in ev,
             "eval must include gold and pass_threshold")
    _require(0 <= float(ev["pass_threshold"]) <= 1, "eval.pass_threshold must be in [0,1]")

    # routing block
    routing = raw["routing"]
    _require(isinstance(routing, dict) and "map" in routing, "routing.map required")

    # oob block: typed, ordered, first-match-wins blocklist
    oob = raw["oob"]
    _require(isinstance(oob, dict) and "templates" in oob, "oob.templates required")
    blocklist_raw = oob.get("blocklist") or []
    _require(isinstance(blocklist_raw, list), "oob.blocklist must be a list")
    blocklist = []
    for i, rule in enumerate(blocklist_raw):
        _require(isinstance(rule, dict) and "type" in rule and "pattern" in rule,
                 f"oob.blocklist[{i}] must be a mapping with type and pattern")
        entry = {"type": rule["type"], "pattern": rule["pattern"]}
        if rule.get("unless"):
            entry["unless"] = rule["unless"]
        if rule.get("unless_all"):
            _require(isinstance(rule["unless_all"], list),
                     f"oob.blocklist[{i}].unless_all must be a list")
            entry["unless_all"] = list(rule["unless_all"])
        blocklist.append(entry)

    # output block: per-audience postprocess contract
    out = raw["output"]
    _require(isinstance(out, dict) and "patient" in out, "output.patient required")

    def _audience_output(node, label):
        _require(isinstance(node, dict) and isinstance(node.get("required_sections"), list)
                 and node["required_sections"], f"{label}.required_sections must be a non-empty list")
        return {
            "required_sections": list(node["required_sections"]),
            "citation_pattern": node.get("citation_pattern"),
            "citation_requires": node.get("citation_requires"),
        }

    output = {"oob_exempt_pattern": out.get("oob_exempt_pattern")}
    for aud in audiences:
        _require(aud in out, f"output.{aud} required (audience declared in audiences)")
        output[aud] = _audience_output(out[aud], f"output.{aud}")

    # model block: per-audience params
    mdl = raw["model"]
    _require(isinstance(mdl, dict) and mdl.get("name") and "patient" in mdl,
             "model.name and model.patient required")

    def _model_params(node, label):
        _require(isinstance(node, dict) and "temperature" in node and "max_tokens" in node,
                 f"{label} must include temperature and max_tokens")
        return {"temperature": float(node["temperature"]), "max_tokens": int(node["max_tokens"])}

    model = {"name": mdl["name"]}
    for aud in audiences:
        _require(aud in mdl, f"model.{aud} required (audience declared in audiences)")
        model[aud] = _model_params(mdl[aud], f"model.{aud}")

    # yaml_stack requires a knowledge dir
    if features["knowledge_injection"] == "yaml_stack":
        _require("knowledge" in raw,
                 "knowledge dir required when features.knowledge_injection=yaml_stack")

    # Resolve & existence-check referenced paths
    resolved = {
        "output_schema": _resolve(pack_root, raw["output_schema"], must_exist=True, label="output_schema"),
        "sections_dir": _resolve(pack_root, raw["sections_dir"], must_exist=True, label="sections_dir"),
        "system_base": _resolve(pack_root, raw.get("system_base", "prompts/system_base.md"),
                                must_exist=True, label="system_base"),
        "routing_map": _resolve(pack_root, routing["map"], must_exist=True, label="routing.map"),
        "oob_templates": _resolve(pack_root, oob["templates"], must_exist=True, label="oob.templates"),
        "eval_gold": _resolve(pack_root, ev["gold"], must_exist=True, label="eval.gold"),
    }
    if ev.get("oob_gold"):
        resolved["eval_oob_gold"] = _resolve(pack_root, ev["oob_gold"], must_exist=True, label="eval.oob_gold")
    if ev.get("judge_prompt"):
        resolved["eval_judge_prompt"] = _resolve(pack_root, ev["judge_prompt"], must_exist=True, label="eval.judge_prompt")
    if ev.get("crisis_gold"):
        resolved["eval_crisis_gold"] = _resolve(pack_root, ev["crisis_gold"], must_exist=True, label="eval.crisis_gold")
    if raw.get("knowledge"):
        resolved["knowledge"] = _resolve(pack_root, raw["knowledge"],
                                         must_exist=features["knowledge_injection"] == "yaml_stack",
                                         label="knowledge")

    # Doctor-variant prompt paths (existence-checked only when doctor is an audience).
    if "doctor" in audiences:
        for base_key, suffix_label in (("output_schema", "output_schema"),
                                       ("system_base", "system_base"),
                                       ("oob_templates", "oob.templates")):
            base_abs = resolved[base_key]
            doctor_abs = _doctor_variant(base_abs)
            resolved[base_key + "_doctor"] = _resolve(
                pack_root, os.path.relpath(doctor_abs, pack_root),
                must_exist=True, label=suffix_label + " (doctor variant)")

    return {
        "id": raw["id"],
        "name": raw["name"],
        "source": src,
        "audiences": list(audiences),
        "features": features,
        "knowledge_header": raw.get("knowledge_header", DEFAULT_KNOWLEDGE_HEADER),
        "knowledge_section_title": raw.get("knowledge_section_title", DEFAULT_KNOWLEDGE_SECTION_TITLE),
        "routing": {
            "fallback": routing.get("fallback"),
            "llm_fallback": bool(routing.get("llm_fallback", False)),
        },
        "oob": {"blocklist": blocklist},
        "output": output,
        "model": model,
        "eval": {
            "pass_threshold": float(ev["pass_threshold"]),
            "baseline": ev.get("baseline"),
        },
        "pack_root": pack_root,
        "manifest_path": manifest_path,
        "paths": resolved,
    }


def _doctor_variant(abs_path: str) -> str:
    """foo.md -> foo_doctor.md (preserving directory)."""
    base, ext = os.path.splitext(abs_path)
    return base + "_doctor" + ext


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    manifest_path = argv[1]
    field = None
    if "--field" in argv:
        i = argv.index("--field")
        if i + 1 >= len(argv):
            sys.stderr.write("error: --field requires a name\n")
            return 2
        field = argv[i + 1]
    try:
        pack = load_pack(manifest_path)
    except PackError as exc:
        sys.stderr.write(f"INVALID {manifest_path}: {exc}\n")
        return 1
    except (OSError, yaml.YAMLError) as exc:
        sys.stderr.write(f"error reading {manifest_path}: {exc}\n")
        return 2
    if field:
        print(pack.get(field, ""))
    else:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
