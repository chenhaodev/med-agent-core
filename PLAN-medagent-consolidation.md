# PLAN · med-agent 知识卡代理收敛(N 个 fork → 1 内核 + 知识包)

> 交给 ClaudeCode 执行。目标:把 `med-agent-{ad,neo,sleep,stcc,psy,inner-all}` 这批**同构 fork**
> 塌缩成 **一个引擎 `med-agent-core` + 每领域一个 knowledge-pack**,复用你在 agentmem/agentcurl 上
> 已验证的"一套接口·可插拔后端"范式。os-core 保持为上层编排,改为派发到引擎。
> 作者:chenhao · 日期:2026-06-27

---

## 0. 现状诊断(为何要做)

6 个代理的 `bin/` 高度重复:
```
ad / neo / sleep   = 8 脚本精简版:ask·router·oob_check·build_prompt·call_deepseek·postprocess·eval·eval_oob
stcc               = 上 + build_sections.py / extract_yaml.py(从 markdown 抽 YAML)
inner-all / psy    = 加强版:+ audit_{grounding,pages,routing,schema}·ingest·folio_map·doctor 双模·eval_deep·verify_claims
```
**只有三处随领域变**:`knowledge/*.yaml`(知识卡)、`prompts/{system_base,output_schema,oob_templates,sections}`、`eval/{gold,oob_gold}.yaml`。
框架改一个 bug 现在要改 6 遍;这就是要收敛的根因。

```
旧:6 个 repo,各自一份 copy-paste 的 bin/
新:med-agent-core/
      engine/            ← 唯一一份流水线(inner-all 加强版为超集,精简能力做可选开关)
      packs/<domain>/    ← 每领域:manifest + knowledge + prompts 覆盖 + eval gold
```

---

## 1. 先定 pack 契约(`packs/<domain>/pack.yaml`)

引擎读 manifest 跑;领域作者只写这一包,不碰引擎。

```yaml
id: alzheimer                      # 领域 slug,= 目录名
name: AD 家庭康复顾问
source:                            # 溯源元数据(provenance)
  title: 阿尔茨海默病多元康复干预中国专家共识(2025)
  kind: consensus                  # consensus | textbook | protocol
audiences: [patient]               # [patient] | [patient, doctor]
features:                          # 引擎能力开关——精简包默认全关
  page_traceable: false            # true → 启用 folio_map / audit_pages(教材类)
  ingest: manual                   # manual | pdf(启用 ingest.py 抽卡)
  deep_eval: false                 # true → 启用 eval_deep / verify_claims
output_schema: prompts/output_schema.md   # 段式定义(相对本包)
sections_dir: prompts/sections            # 类别知识片段
knowledge: knowledge/               # YAML 知识卡目录
routing:                           # 关键词 → domain 路由表(原 router.sh 硬编码搬来这)
  map: knowledge/category_index.yaml
oob:                               # 越界拦截
  templates: prompts/oob_templates.md
  blocklist: [帕金森, 干细胞, ...]   # 确定性拦截关键词
eval:
  gold: eval/gold.yaml
  oob_gold: eval/oob_gold.yaml
  pass_threshold: 0.90             # 回归基线(见 §5 parity gate)
```

新增 `schema/pack.schema.json` 校验它;`engine/load_pack.py` 做 loader + 校验(对标 agentmem 的 backend 契约)。

---

## 2. 抽引擎(`engine/`,以 inner-all 为超集基线)

把 inner-all 的加强版流水线**去领域化**,所有领域细节改为从 pack 读:

| 旧(每 repo 一份) | 新(引擎单份,吃 `--pack`) |
|---|---|
| `bin/router.sh`(硬编码类别) | `engine/router.sh --pack P`(读 `pack.routing.map`) |
| `bin/oob_check.sh` | `engine/oob_check.sh --pack P`(读 `pack.oob`) |
| `bin/build_prompt.sh` | `engine/build_prompt.sh --pack P`(拼 `pack.sections_dir` + `output_schema`) |
| `bin/call_deepseek.sh` | `engine/call_llm.sh`(完全领域无关,直接搬,统一 deepseek-v4-flash) |
| `bin/postprocess.sh` | `engine/postprocess.sh --pack P`(按 `pack.output_schema` 校验段式) |
| `bin/eval*.sh` | `engine/eval.sh --pack P` / `eval_oob.sh --pack P` |
| audit/ingest/folio/doctor 双模 | `engine/` 内**可选模块**,仅当 `pack.features.*` 开启时启用 |

统一入口:
```bash
med-agent ask  --pack alzheimer "我爸有高血压,饮食注意啥?"
med-agent eval --pack alzheimer            # 跑该包金标
med-agent eval --pack alzheimer --oob
```
精简包(ad/neo/sleep)`features` 全 false → 只走 8 步主链;加强包(inner-all/psy)开 `page_traceable/deep_eval` → 自动挂上 audit/verify_claims。**一条代码路径,能力靠开关分叉**。

---

## 3. 迁移每个代理 → 一个 pack(机械搬运,不改语义)

逐个把 `med-agent-<x>` 的三处可变内容搬进 `packs/<x>/`:
```
knowledge/*.yaml          → packs/<x>/knowledge/
prompts/{system_base,output_schema,oob_templates,sections} → packs/<x>/prompts/
eval/{gold,oob_gold}.yaml → packs/<x>/eval/
router.sh 里的关键词表    → packs/<x>/knowledge/category_index.yaml + pack.yaml:routing
oob_check.sh 里的 blocklist → pack.yaml:oob.blocklist
source/ pdfs/(若有)      → packs/<x>/source/(provenance,可选)
```
对照表:`alzheimer`(ad,lite)·`neonatal`(neo,lite)·`sleep`(lite)·`stcc`(protocol,lite+sections 生成)·
`psy`(DSM-5,advanced/page_traceable)·`internal-med`(inner-all,advanced/17 专科)。

> stcc 的 `extract_yaml.py / build_sections.py` 是"从 markdown 生成卡片"的**构建期工具**,
> 归入 `engine/tools/`(由 `pack.features.ingest` 触发),不进运行时主链。

---

## 4. 接线 os-core 与 verifier(保持生态自洽)

- **os-core**:`registry/adapters` 里写死的 inner-all adapter → 改为通用 `engine_adapter`,
  按 sub-intent 的 `domain` 调 `med-agent ask --pack <domain> --domain <tag>`。
  `registry/inner_all_domains.txt` → 由 `med-agent list-domains --pack <x>` 动态生成,删硬编码。
  os-core 的五段编排(context/decompose/dispatch/synthesize/persist)**完全不动**。
- **verifier**:`data/book-gold/` 的金标改为从 `packs/{internal-med,psy}/eval/gold.yaml` **同步**
  (`sync_gold.sh` 指向 packs),消除重复维护。与上一份 verifier plan 的两阶段流程不冲突。

---

## 5. Parity gate(高风险重构的安全网 —— 必须有)

收敛是行为等价重构,**唯一硬验收 = 每个 pack 复现其原 repo 的金标分**:
```bash
# 对每个领域:迁移前在老 repo 记录基线,迁移后在引擎复跑,差值需在容差内
med-agent eval --pack <x>     # 新引擎得分
# 对比老 repo eval/results 基线;Δ均分 ≤ 0.5/30 且 OOB 拦截率不下降 → 通过
```
任一 pack 跌出容差即视为引擎引入了回归,**先修引擎再继续**。这是把"改 6 遍易出错"换成"改 1 遍可证等价"的关键。

---

## 6. 执行顺序(给 ClaudeCode 的 sprint)

1. **P0 契约+引擎骨架**:`pack.schema.json` + `load_pack.py` + 从 inner-all 抽 `engine/`(超集),能力做开关。
2. **P1 两个参照包跑通 parity**:`alzheimer`(lite 代表)+ `internal-med`(advanced 代表),各自复现原分(§5)。
   ——这一步通过,才证明引擎设计成立。
3. **P2 迁移其余 4 包**:neonatal / sleep / stcc / psy,逐包过 parity gate。
4. **P3 接线**:os-core 改通用 adapter;verifier `sync_gold.sh` 指向 packs。
5. **P4 收尾**:旧 6 repo 处理(见 §7 决策)+ `docs/PACK-AUTHORING.md`(教别人怎么加一个新领域 = 只写一个 pack)。

**总验收**:`med-agent ask/eval --pack <任一>` 全绿;全家族仅剩一份 `engine/`;
`grep -rl 'router.sh' packs/` 零命中(可变逻辑已无脚本副本)。

---

## 7. 待你拍板的 2 个决策

1. **仓库形态**:`med-agent-core` 单 monorepo(`engine/` + `packs/*/`,**推荐**——收敛本意就是反 N-repo)
   还是 引擎一个 repo + packs 各自 repo?
2. **旧 6 个 repo 去向**:迁移后**归档只读 + README 指向新仓**(推荐,知识卡是你的护城河资产,保留可追溯)
   还是 直接删除?(注意:与 routing 那次不同,这里的 `knowledge/` 是真资产,**务必先迁移再处置**,不可直接删。)
