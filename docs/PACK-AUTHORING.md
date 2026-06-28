# Authoring a pack (= adding a new medical domain)

A domain is **one directory under `packs/`**. You never touch `engine/`.
The engine reads `pack.yaml` (validated by `schema/pack.schema.json`) and the
files it points at. Run the loader to check your pack:

```bash
python3 engine/load_pack.py packs/<your-domain>/pack.yaml   # prints normalized JSON, or INVALID + reason
```

## Layout

```
packs/<domain>/
  pack.yaml                       # the manifest (contract)
  prompts/
    system_base.md                # system prompt (+ system_base_doctor.md if audiences has doctor)
    output_schema.md              # segment format (+ _doctor variant)
    oob_templates.md              # rejection copy, one section per gate type
    sections/<category>.md        # per-category knowledge prose injected at runtime
  knowledge/
    category_index.yaml           # routing table: keyword patterns -> domain tag
    source/ | <specialty>/        # provenance (lite) OR per-disease cards (advanced)
  eval/
    gold.yaml                     # scored Q&A gold
    oob_gold.yaml                 # out-of-scope gold
```

## The one knob that decides everything: `features.knowledge_injection`

The six forks split into two runtime contracts. Pick the matching mode:

| mode | who | runtime reads | `knowledge/` is |
|---|---|---|---|
| `sections_only` | ad, neo, sleep, stcc (lite) | only `sections/*.md` | provenance / build-time source |
| `yaml_stack` | inner-all, psy (advanced) | `sections/*.md` **+** per-disease `knowledge/<sp>/<disease>.yaml` (+ `guidelines/`, `safety_floor/`) stacked inline | the live runtime knowledge |

- **sections_only**: cards live as prose in `sections/`. The YAML under
  `knowledge/source/` is kept only for traceability and for regenerating sections.
- **yaml_stack**: set `knowledge: knowledge/` and lay out `knowledge/<specialty>/<disease>.yaml`
  with `entries[].source_page` / `evidence_level`. Turn on `page_traceable: true` for
  textbook packs to enable folio mapping + page-citation verification.

Other switches (`page_traceable`, `ingest`, `deep_eval`) default off; turn them on
only when the pack needs that capability — the engine has one code path and the
switches gate the optional modules.

## Migrating an existing fork (mechanical, no semantics change)

1. `cp -R <repo>/prompts packs/<x>/prompts` and `<repo>/eval` → `packs/<x>/eval`.
2. Move `knowledge/*.yaml` → `packs/<x>/knowledge/source/` (lite) or `knowledge/<sp>/` (advanced).
3. Lift the `KEYWORDS_*` table out of the fork's `bin/router.sh` into
   `knowledge/category_index.yaml` (`domains: [{domain, patterns}], fallback, max_domains`).
4. Lift the `oob_check.sh` blocklist regexes into `pack.yaml: oob.blocklist`.
5. Write `pack.yaml`; run the loader until it prints valid JSON.
6. **Parity gate (§5)**: record the fork's eval baseline, run `med-agent eval --pack <x>`,
   require Δ within tolerance before retiring the fork. Routing parity is checkable
   offline with the keyword path (see `engine/router.sh`).
