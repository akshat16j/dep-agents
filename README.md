# dep-agent — Static-Analysis-Driven Dependency Upgrade Checker

**Independent Project** · Python · AST · RAG · MCP · Gemini API

Given a repository and a package version bump, `dep-agent` resolves which symbols the code
actually uses, retrieves the release notes covering that version range, and produces a
per-symbol verdict on whether the upgrade breaks anything — with every positive claim required
to cite verbatim changelog text, verified mechanically.

Exposed as an [MCP](https://modelcontextprotocol.io) server, so LLM clients (Claude Code,
Claude Desktop, Cursor) can call it as a tool.

---

## Results

Evaluated on **41 hand-labelled usages across 13 real package upgrades**, single pinned model.

| | Precision | Recall | Accuracy |
|---|---|---|---|
| **Primary — action-required** (deprecation counts) | **100%** | **86%** | **95%** (39/41) |
| Secondary — removed-only | 75% | 82% | 88% (36/41) |

- **Grounded rate: 12/12.** Every positive verdict cites changelog text that passes mechanical
  verification against the retrieved corpus.
- **Zero false positives.**
- **Failure decomposition: 0 reasoning failures, 2 source-coverage failures.** Both are packages
  that document the breaking change outside GitHub Releases and outside their changelog file.
- Evidence for grounded positives came from the changelog file in 8 cases and GitHub Releases in 4.

*"Breaking" is definitionally ambiguous for deprecations — code still runs, with a warning. Ground
truth carries a `severity` column (`removed` / `deprecated` / `none`) and both definitions are
reported. Primary is action-required, because a tool that stays silent until the build breaks is
not useful.*

**41 usages is a small sample.** These numbers are directional, and 100% precision on 12 positives
should be read as "no false positives observed", not as a rate.

---

## How it works

### 1. Static analysis — what does this repo actually use?

Four passes over the AST, each feeding the next:

1. **Imports** → fully qualified names, including aliases (`import requests as rq`)
2. **Class definitions** inheriting from an imported symbol (`class User(BaseModel)`)
3. **Variable assignments** from those classes or from imported callables
   (`user = User(...)`, `df = pd.DataFrame(...)`)
4. **Calls**, resolved through all three maps and filtered to the package under test

The chain matters. `user.dict()` shares no text with the word "pydantic" — resolving it to
`pydantic.BaseModel.dict` requires following import → inheritance → instance assignment. No
regex or grep can do that.

**Known limits:** no cross-file type propagation, no scope handling (a local variable shadowing
a module name resolves wrongly), no reassignment tracking, and chained calls like
`get_client().request()` are unresolvable. This is shallow local type inference, not a type
checker. A real type checker would resolve more but would require a working install of the
target's dependencies; this runs on any repo with zero setup.

**Empty scans are treated as dangerous, not clean.** A scan returning no usages is
indistinguishable from a repo that genuinely doesn't use the package — most often it means the
import name differs from the PyPI name (`scikit-learn` → `sklearn`). The agent refuses to
produce a verdict in that case.

### 2. Retrieval — two axes of narrowing

**Version scope (deterministic).** Only release notes strictly between the from- and
to-version. Dumping the full changelog wastes context and invites hallucinated breaking changes
from versions the user isn't moving through.

**Source union.** GitHub Releases plus a changelog file from the repo root
(`CHANGELOG.md` / `CHANGES.rst` / `HISTORY.md` and variants), sectioned by version heading.
The union is unconditional — the fetch is plain HTTP with no model cost, and a size-based
trigger doesn't work: Flask's release bodies run to 5,413 characters while containing zero
removal lines. `evidence_source` records which source each citation came from.

**Usage scope (semantic, conditional).** If the version-scoped corpus exceeds the context
budget, chunks are embedded (`all-MiniLM-L6-v2`) and ranked by maximum cosine similarity
against the symbols static analysis found in use. Chunking is per changelog *entry*, not per
release, because the unit of a breaking change is a bullet.

The conditional is the design decision: deterministic filtering runs first and semantic search
only fires when structure runs out. There is no vector database, deliberately — the corpus is
fetched per query and discarded, so cosine similarity over a few hundred vectors in a NumPy
array is the correct tool. A persistent store would be engineering theatre at this scale.

### 3. Grounded generation, verified mechanically

The model returns one verdict per usage, each requiring `evidence_tag` and a verbatim
`evidence_quote`. If no supplied note supports a verdict, it must return `breaking: false` with
`evidence_quote: null` — never infer from prior knowledge.

**Citations are then checked in code.** Each quote is normalised to lowercase alphanumerics and
matched against the retrieved corpus. Any `breaking: true` whose quote does not appear is
downgraded and flagged. The model's original claim is preserved in `breaking_raw` so a
downgrade remains diagnosable.

**Self-reported confidence is not used anywhere in the decision path.** The prompt specifies
`confidence: 0.0` for null-evidence verdicts; observed values were 1.0 and 0.5. It does not
track anything, so the mechanically verified `grounded` flag is the trustworthy signal. This
also replaced a planned confidence-calibration analysis — a field that ignores its own
instruction cannot be calibrated.

### 4. Abstention

When retrieval yields no verifiable evidence and no breaking claim is made, the agent returns
**`INSUFFICIENT_EVIDENCE`**, not a pass:

```
sources: releases 45/341,448ch + CHANGES.rst — stub (240 chars, 0 sections) 0/0ch
verdict: INSUFFICIENT_EVIDENCE
note:    No verifiable changelog evidence found for sqlalchemy 1.4.0→2.0.0.
         This is NOT a safety verdict — the package may document breaking
         changes outside GitHub Releases and its changelog file.
```

`breaking: false` and "I could not find out" must not render identically. For an
upgrade-safety tool, a silent false negative is the worst-shaped failure available.

---

## MCP server

Three tools, separated by cost profile so a client can check cheaply before paying:

| Tool | Cost | Purpose |
|---|---|---|
| `scan_repo` | local, free | AST usage resolution only — no network, no model |
| `fetch_evidence` | network | The retrieval corpus, without a model call |
| `check_upgrade` | model call | Full pipeline: scan, retrieve, verdict, verification |

`check_upgrade` calls the same `run_check()` used by the eval harness, so the demo and the
reported numbers come from identical code.

Logging goes to **stderr, never stdout** — on stdio transport a stray `print` lands mid-frame
and corrupts the JSON-RPC stream, and the symptom is a client showing no tools rather than a
readable error.

---

## Source coverage is the real limitation

The largest gap is not reasoning quality. It is that **release notes and changelog files do not
reliably document breaking changes.** Three widely used packages fail this, by three
independent mechanisms:

| Package | Mechanism |
|---|---|
| SQLAlchemy | `CHANGES.rst` exists but is a 240-character "MOVED" redirect stub |
| pandas | No changelog at the repository root at all |
| pydantic | `HISTORY.md` yields in-range sections; they don't document the breaks |

In each case the evidence exists — in `docs/migration.md`, `doc/source/whatsnew/v2.0.0.rst`,
`doc/build/changelog/migration_20.rst` — but at a different path, in a different format, per
package. No single fallback closes this, which is why the agent abstains rather than guessing.
SQLAlchemy's `Engine.execute` removal appears in **0 of 661** retrieved chunks.

---

## Bugs worth recording

Five, of which four would have shipped a plausible wrong number.

**The evaluation caught three.** A `verify()` regression discarded three *correct* verdicts:
unioning the changelog file switched urllib3's corpus from Markdown to RST, the model stripped
markup when quoting, and a strict substring check rejected the quotes. Recall read 64% instead
of 86%. It was only visible because a validated positive control existed to regress against —
without it, this would have been reported as "the model missed three breaking changes."
Rescoring cost zero API quota: the corpus is a pure function of package, versions and usages,
so the saved raw model output could be replayed through the fixed checker.

A changelog sectioner silently produced zero sections for RST files (version headings carry a
date before the underline) and shattered Keep-a-Changelog files on `### Removed` sub-headings.
Uncaught, all five changelog-tier packages would have scored as source-coverage failures —
**the eval would have measured the parser, not the agent.**

The first positive control was vacuous: it used three urllib3 APIs that still exist in 2.0, so
their `breaking: false` verdicts were correct and proved nothing about whether verification
worked. Re-picked from documented removals.

**The MCP integration caught one the eval could not.** Release tags are not PEP 440 —
SQLAlchemy tags releases `rel_2_0_52` — and `packaging.parse()` on a raw tag name raised,
killing every check for that package. All 13 eval packages have conventional tags, so the eval
was structurally incapable of finding this. An eval and an integration test measure different
things.

---

## Limitations

- 41 usages across 13 packages is a small sample; per-tier numbers are directional
- Ground truth labels are the author's, verified against changelog text but not independently reviewed
- Single model, single prompt — no ablation over either
- Free-tier quota (20 requests/day/model) capped the eval size
- AST resolution limits as described above
- Source coverage as described above

## Run it

```bash
pip install -r requirements.txt
# .env: GEMINI_API_KEY, GITHUB_TOKEN

python ast_walker.py . requests            # static analysis alone
python agent.py flask 1.1.4 2.3.0          # full check
python run_eval.py                         # 13-package eval (spends quota)
python rescore.py                          # replay saved output, zero quota

python mcp_server.py                       # MCP server over stdio
```

Register with an MCP client:

```bash
claude mcp add dep-agent /path/to/venv/bin/python /path/to/dep-agent/mcp_server.py
```

`eval_set.csv`, `eval_targets/` and the raw run output are committed, so every number above is
reproducible from this repository.
