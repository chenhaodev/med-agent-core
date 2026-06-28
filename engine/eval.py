#!/usr/bin/env python3
"""eval.py — graded evaluation harness (generic, pack-driven).

Port of every fork's bin/eval.sh: routes each gold question through the engine
pipeline (router → build_prompt → call_llm), then scores the answer with an
LLM judge (eval/judge_prompt.md). Reports per-question scores + averages and
writes a JSON result file. Used for the §5 parity gate (compare avg to the
frozen source baseline).

Usage:
  python3 engine/eval.py <pack_dir> [--limit N] [--id X] [--mode patient|doctor]
                                    [--judge-model M] [--out FILE]

Needs DEEPSEEK_API_KEY (in core or pack .env) unless every payload is cached.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def _run(cmd, stdin=None):
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True)


def pipeline_answer(pack_dir: str, mode: str, question: str) -> str:
    """router → build_prompt → call_llm; returns the model answer or raises."""
    r = _run(["bash", os.path.join(HERE, "router.sh"), "--pack", pack_dir, question])
    domains = (r.stdout or "").strip() or "general"
    bp = _run(["bash", os.path.join(HERE, "build_prompt.sh"), "--pack", pack_dir,
               "--mode", mode, domains, question])
    if bp.returncode != 0:
        raise RuntimeError(f"build_prompt failed: {bp.stderr.strip()}")
    call = _run(["bash", os.path.join(HERE, "call_llm.sh"), "--pack", pack_dir], stdin=bp.stdout)
    if call.returncode != 0:
        raise RuntimeError(f"call_llm failed: {call.stderr.strip()}")
    return call.stdout.strip()


def judge(pack_dir: str, judge_system: str, judge_model: str, qobj: dict, answer: str) -> dict:
    judge_input = {
        "question": qobj["question"],
        "model_response": answer,
        "gold": {k: qobj.get(k) for k in
                 ("expected_topics", "expected_protocol", "must_warn", "consensus_refs", "must_not")
                 if k in qobj},
    }
    payload = {
        "model": judge_model,
        "temperature": 0,
        # Headroom so a reasoning judge model (v4-flash) doesn't spend the whole
        # budget on reasoning_content and return empty content.
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": judge_system},
            {"role": "user", "content": json.dumps(judge_input, ensure_ascii=False)},
        ],
    }
    call = _run(["bash", os.path.join(HERE, "call_llm.sh"), "--pack", pack_dir],
                stdin=json.dumps(payload, ensure_ascii=False))
    if call.returncode != 0:
        raise RuntimeError(f"judge call failed: {call.stderr.strip()}")
    m = re.search(r"\{.*\}", call.stdout, re.DOTALL)
    if not m:
        raise RuntimeError(f"no JSON in judge output: {call.stdout[:200]}")
    return json.loads(m.group())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pack_dir")
    ap.add_argument("--limit", type=int, default=999)
    ap.add_argument("--id", default="")
    ap.add_argument("--mode", default="patient")
    ap.add_argument("--judge-model", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv[1:])

    try:
        pack = load_pack(os.path.join(args.pack_dir, "pack.yaml"))
    except PackError as exc:
        sys.stderr.write(f"INVALID pack: {exc}\n")
        return 1

    gold = yaml.safe_load(open(pack["paths"]["eval_gold"], encoding="utf-8"))
    questions = gold.get("questions", [])
    if args.id:
        questions = [q for q in questions if q.get("id") == args.id]
    else:
        questions = questions[: args.limit]

    jp = pack["paths"].get("eval_judge_prompt")
    if not jp:
        sys.stderr.write("error: pack has no eval.judge_prompt\n")
        return 2
    judge_system = open(jp, encoding="utf-8").read()
    # The forks all judged with deepseek-chat (a cheap non-reasoning scorer),
    # independent of the pack's generation model. Match that default.
    judge_model = args.judge_model or "deepseek-chat"

    rows, errors = [], 0
    tot = {"coverage": 0, "accuracy": 0, "safety": 0, "total": 0}
    print(f"━━━ eval: {pack['id']} ({len(questions)} q, mode={args.mode}) ━━━")
    for i, q in enumerate(questions, 1):
        qid, qtext = q.get("id", f"q{i}"), q["question"]
        try:
            answer = pipeline_answer(args.pack_dir, args.mode, qtext)
            scores = judge(args.pack_dir, judge_system, judge_model, q, answer)
        except RuntimeError as exc:
            errors += 1
            print(f"[{i:2}/{len(questions)}] {qid}  ERROR: {exc}")
            continue
        cov = scores.get("coverage", {}).get("score", 0) if isinstance(scores.get("coverage"), dict) else scores.get("coverage", 0)
        acc = scores.get("accuracy", {}).get("score", 0) if isinstance(scores.get("accuracy"), dict) else scores.get("accuracy", 0)
        saf = scores.get("safety", {}).get("score", 0) if isinstance(scores.get("safety"), dict) else scores.get("safety", 0)
        total = scores.get("total", cov + acc + saf)
        for k, v in (("coverage", cov), ("accuracy", acc), ("safety", saf), ("total", total)):
            tot[k] += v
        rows.append({"id": qid, "question": qtext,
                     "scores": {"coverage": cov, "accuracy": acc, "safety": saf, "total": total},
                     "flags": scores.get("flags", [])})
        print(f"[{i:2}/{len(questions)}] {qid}  {total}/30 (C:{cov} A:{acc} S:{saf})")

    n = len(rows)
    avg = {k: round(v / n, 2) for k, v in tot.items()} if n else {k: 0 for k in tot}
    summary = {"pack": pack["id"], "evaluated": n, "errors": errors, "avg_scores": avg,
               "pass_threshold": pack["eval"]["pass_threshold"],
               "baseline": pack["eval"].get("baseline")}
    print(f"\n━━━ avg total {avg['total']}/30  (C:{avg['coverage']} A:{avg['accuracy']} S:{avg['safety']})  errors={errors} ━━━")
    out = args.out or os.path.join(args.pack_dir, "eval", "results",
                                   f"eval_{pack['id']}_{args.mode}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"summary": summary, "results": rows}, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"→ {out}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
