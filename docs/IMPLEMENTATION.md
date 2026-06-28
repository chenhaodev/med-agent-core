# Implementation — executing PLAN-medagent-consolidation.md

Six homogeneous forks (`med-agent-{ad,neo,sleep,stcc,psy,inner-all}`) collapsed
into one `engine/` + one knowledge pack per domain under `packs/`. This is the
record of how it was built and what is proven. Full fork→pack map + parity
numbers: `docs/MIGRATION.md`. How to add a domain: `docs/PACK-AUTHORING.md`.

## The plan's blind spot (and the fix)

The plan's `pack.yaml` assumed every domain reads a runtime `knowledge/<sp>/<disease>.yaml`
stack. **That is only true for the advanced forks (inner-all, psy).** The lite forks
(ad, neo, sleep, stcc) never read YAML at runtime — they inject only `prompts/sections/*.md`;
their `knowledge/*.yaml` is build-time source. Forcing one contract on both would silently
change lite behavior and blow the parity gate.

**Fix:** `features.knowledge_injection ∈ {sections_only, yaml_stack}` in the manifest.
One engine, two injection strategies, selected per pack. This is the keystone that makes
"one engine for six" hold. Other fork-specific logic likewise became data in `pack.yaml`:
typed `oob.blocklist` (+`unless`/`unless_all` guards), `output.<audience>`
(`required_sections`/`citation_pattern`/`citation_requires`), `model.<audience>`,
`knowledge_header`/`knowledge_section_title`, and two-tier `routing`.

## Status — P0–P4 done, verified offline

**P0 — contract + engine (done):**
`schema/pack.schema.json` · `engine/load_pack.py` (loader/validator) ·
`engine/{router,oob_check,build_prompt,call_llm,postprocess,ask}.sh` ·
`engine/{eval,eval_oob,list_domains}.py` · `med-agent` dispatcher
(`ask|route|oob|validate|eval|eval-oob|list-packs|list-domains`) ·
`engine/tools/{extract_router,migrate_forks}.py`. `llm_fallback` ported.

**P1/P2 — all six packs migrated + parity-verified (done):**
alzheimer, internal-med, neonatal, sleep, stcc, psy. Each reproduces its source
fork byte-for-byte on the deterministic substrate (routing, knowledge injection,
OOB, output structure). Numbers in `docs/MIGRATION.md`; e.g. internal-med routing
180/180 and build_prompt 6/6 byte-identical across patient+doctor.

**P3 — ecosystem wired (done):**
os-core generic `engine_adapter` + `inner_all` → `internal-med` pack (reversible
via `OS_USE_FORK_ADAPTER=1`); domain allowlist regenerated from `list-domains`.
verifier `sync_gold.sh` vendors from the packs (pulled 150+52 gold). End-to-end
adapter run verified on the OOB path + domain filtering (no key needed).

**P4 — archival prepared (decision-gated):**
each fork carries `DEPRECATED.md` → its pack; `scripts/archive_forks.sh` performs
disposal but is **not** run (it is the §7 decision and is irreversible).

## Live gate — run, all six pass

Graded gate run with a key: alzheimer 29.32, internal-med 29.15, neonatal 29.38,
psy 29.77, sleep 27.47, stcc 27.73 (/30) — all clear 25.5 (0.85), zero errors,
no-hallucination 1.00 everywhere. OOB intercept is the deterministic `oob_check`
verdict. Full table + caveats: `docs/MIGRATION.md`.

**psy is a safety-critical tier**, not a peer of the others: it carries a dedicated
fail-closed crisis gate (a missed suicide signal is categorically worse than a low
coverage score). `./med-agent crisis-check --pack psy` → 19/19 recall, 6/6 precision,
deterministic, byte-identical to the fork; exit 1 on ANY miss. psy CI must run it.

Still open: record each fork's pre-migration baseline into `pack.yaml: eval.baseline`
for automatic Δ-gating (the byte-identical payloads mean the engine's scores already
equal the forks').

## Acceptance (plan §6)

`med-agent ask/eval --pack <any>` runs on one shared `engine/` · no `router.sh`
under `packs/` (`grep -rl 'router.sh' packs/` is empty) · every pack within parity
tolerance on the deterministic substrate (live graded gate pending a key).

## Two decisions the plan defers (§7)

1. **Repo shape** — monorepo (this scaffold: `engine/` + `packs/*`, plan's recommendation)
   vs engine-repo + per-pack repos.
2. **Fork disposal** — archive read-only (recommended) vs delete. Either way: pass the
   live parity gate first; `knowledge/` is the moat. Run `scripts/archive_forks.sh` when chosen.
