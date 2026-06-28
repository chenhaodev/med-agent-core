# med-agent-core

One medical-QA engine, many knowledge packs. Collapses the six
`med-agent-{ad,neo,sleep,stcc,psy,inner-all}` forks into a single `engine/` plus
one self-describing pack per domain under `packs/` — "one interface, pluggable
backends".

```
engine/        the shared runtime (router, oob, build_prompt, call_llm, postprocess, ask, eval)
packs/<x>/     a domain: pack.yaml manifest + prompts/ + knowledge/ + eval/
schema/        pack.schema.json — the manifest contract
med-agent      dispatcher: ask | route | oob | validate | eval | eval-oob | list-packs | list-domains
docs/          IMPLEMENTATION.md · MIGRATION.md · PACK-AUTHORING.md
```

## Use

```bash
./med-agent list-packs                       # alzheimer internal-med neonatal psy sleep stcc
./med-agent validate --pack alzheimer        # load + validate a manifest
./med-agent oob      --pack alzheimer "我妈帕金森怎么办"     # in_scope / out_of_scope:<type>
./med-agent route    --pack alzheimer "每周做几次有氧"       # routed domains
./med-agent ask      --pack alzheimer "我妈轻度AD每周做几次有氧"   # full answer (needs DEEPSEEK_API_KEY)
./med-agent eval     --pack alzheimer        # graded eval (needs key)
```

Put `DEEPSEEK_API_KEY=...` in `.env` (core or pack). Cached payloads answer with
zero network and no key.

## Add a domain

Write one pack directory — never touch `engine/`. See `docs/PACK-AUTHORING.md`.
The keystone knob is `features.knowledge_injection`: `sections_only` (lite) injects
only `sections/*.md`; `yaml_stack` (advanced) also stacks per-disease knowledge
YAML + guidelines + safety_floor.

## Status

All six forks migrated and parity-verified offline (routing / OOB / prompt
assembly byte-identical to source). os-core and the verifier are wired to the
packs. See `docs/IMPLEMENTATION.md`. The only step needing an API key is the
graded LLM-judge parity gate (PLAN §5).
