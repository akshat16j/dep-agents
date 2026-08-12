# DEFENCE.md — how I know this evaluation measures something

Run: `gemini-3.5-flash-lite`, single pinned model, 13 upgrades / 41 usages, 2026-08-12.
Raw model output: `eval_raw_20260812T122812.json`. Scored: `eval_results_20260812T122812_rescored.csv`.

## What the tool claims

Given a repo, a package, and a version range, it finds the places the repo actually calls into
that package (AST, type-aware), retrieves the changelog text covering that range, and returns a
per-usage verdict on whether the upgrade breaks it — **with a verbatim quote from the retrieved
notes**, which is then checked mechanically.

The claim is *not* "the model knows what breaks". It is "every breaking verdict is traceable to
a line of changelog text that provably exists".

## Headline

Correct breaking-change verdicts on **39 of 41** real package usages across 13 upgrades using one
pinned model, with **100% of positive verdicts (12/12) citing changelog text that mechanically
verifies**. Zero false positives. Of the 2 failures, **0 were reasoning errors** and **2 were
source-coverage failures** — packages that document breaking changes outside both GitHub Releases
and their repo changelog.

| definition | precision | recall | accuracy |
|---|---|---|---|
| **Primary** — action-required (deprecation counts as breaking) | 100% | 86% | 95% (39/41) |
| Secondary — removed-only | 75% | 82% | 88% (36/41) |

The headline depends on a definitional choice, so both are reported. Primary is primary because a
tool that stays silent until your build breaks is useless; a scheduled removal is actionable now.
Under the secondary definition the three correctly-detected deprecations
(`urllib3.getheaders`, `attrs.set_run_validators`, `werkzeug.make_line_iter`) count as false
positives. Both numbers are true; they answer different questions.

## Ground truth came from fetched text, never memory

Every `gt_breaking=1` row in `eval_set.csv` carries `gt_evidence_doc` and `gt_evidence_quote` —
the file and the verbatim line the label came from, fetched at build time by `eval_evidence.py`.

This rule exists because memory produced a wrong label earlier in this project. "Everyone knows
pydantic removed `.dict()`" is true, but the belief that this was *documented in the release
notes* was false — and an eval built on that assumption would have scored a retrieval failure as
a reasoning success.

## The first positive control was vacuous

To check that mechanical citation verification wasn't simply rejecting everything, I ran a
positive control on `urllib3 1.26 → 2.0` with three symbols: `PoolManager`, `PoolManager.urlopen`,
`disable_warnings`. All three returned `breaking: false`, grounded rate 0%.

That result proved nothing, because **all three of those APIs still exist in urllib3 2.0**.
`breaking: false` was the correct answer. A control that cannot fail is not a control.

I re-picked from the removals urllib3's changelog actually documents — `HTTPResponse.from_httplib`
(removed) and `HTTPResponse.getheaders` (deprecated with a scheduled removal) — and got
`breaking: true` with verifiable quotes for both, alongside correct negatives for the still-valid
symbols. Only then was the 0% grounded rate on pydantic interpretable as a real finding rather
than a broken checker.

## `confidence` is self-reported and does not track anything

The prompt instructs: when no supplied note supports a verdict, return
`evidence_quote: null, confidence: 0.0`. Observed on null-evidence verdicts: **1.0** on urllib3,
**0.5** on pydantic. The field ignores its own instruction.

I had intended to analyse whether `confidence` was calibrated. It isn't even instruction-following,
so calibration is not a meaningful question to ask of it. It was removed from the decision path
entirely and replaced with mechanical citation verification — a check the model cannot influence
by asserting harder. This is a better result than the calibration analysis would have been.

## Three bugs caught by validation, each of which would have produced a plausible wrong number

1. **Changelog sectioner missed RST and "Version N" headings.** urllib3's headings carry a date
   (`2.0.0 (2023-04-26)`); pallets uses `Version 3.2.0`; Keep-a-Changelog files were being split
   on `### Removed` sub-headings into version-less fragments. flask yielded **0** sections before
   the fix and **15** after; attrs went 461 → 14,849 chars. Unfixed, all five `changelog_file`-tier
   packages would have scored as source-coverage failures and the eval would have measured my
   parser rather than the agent.

2. **Citation verification was markup-sensitive.** The first full run showed urllib3 failing the
   two symbols it had passed in the validated control. The model was right both times: it quoted
   `Removed urllib3.HTTPResponse.from_httplib (#2648).` while the corpus — now sourced from
   `CHANGES.rst` rather than Releases — read ``Removed ``…`` (`#2648 <url>`__).``. The strict
   substring check discarded three correct verdicts as ungrounded. Comparison now reduces both
   sides to lowercase alphanumerics: formatting and punctuation are ignored, word and digit
   content must still match verbatim and in order. Verified to still reject both a fabricated
   quote and a near-miss (`Added` vs `Removed`). Recall 64% → 86%.

3. **Type resolution stopped at package level.** `df = pd.DataFrame(...)` then `df.append(...)`
   resolved to `pandas.append`, because the assignment pass took the callee's root name instead of
   resolving the full expression. Now `pandas.DataFrame.append`, which is what "type-aware
   detection" has to mean to be worth claiming.

Bug 2 was caught only because the control had been validated first — the regression was visible
as *a package that used to pass*. Without a known-good baseline it would have been indistinguishable
from a model reasoning failure, and would have been reported as one.

## Source coverage is a finding, not a gap to paper over

Three tiers, measured per verdict via `evidence_source`:

| tier | packages | grounded positives |
|---|---|---|
| `releases` | urllib3, attrs, numpy, httpx | 4 |
| `changelog_file` | flask, jinja2, click, markupsafe, werkzeug | 8 |
| `neither` | pydantic, pandas | 0 |
| `none-documented` (true negatives) | requests, scikit-learn | 0 |

Both remaining failures are tier `neither`, and both were traced to where the evidence actually
lives: pydantic's `.dict()` → `model_dump()` rename appears only in `docs/migration.md`, as a
two-cell Markdown table row; pandas' `DataFrame.append` removal only in
`doc/source/whatsnew/v2.0.0.rst`. Neither is in GitHub Releases; neither is in a root changelog.

This is deliberately not fixed. Adding those sources needs table-aware chunking and per-project
docs-path heuristics, which is a large fragile surface. Reporting the coverage boundary precisely
is more useful than a parser that half-covers it and hides the boundary.

Note the failure *mode* matters as much as the count: on pydantic the tool returns
`breaking: false, evidence_quote: null` — an honest miss. An earlier version of this pipeline
returned `breaking: false` with confident prose reasoning about instantiation, having silently
answered from training knowledge. The current design cannot do that, because a verdict without a
verifiable citation is mechanically downgraded and the model's original claim is preserved in
`breaking_raw` for audit.

## Known limitations

- **41 usages, 13 upgrades.** Small. Confidence intervals are wide; treat as directional.
- **One model.** Results are not portable across models and are labelled accordingly.
- Detection covers `ast.Call` nodes only — bare attribute access (`np.float`) and decorators
  (`@attrs.define`) are invisible.
- Fixtures are synthetic (`eval_targets/`), not harvested from real repositories.
- The retrieval corpus is capped at 12,000 chars; for numpy the in-range release text is 474,176
  chars, so selection is doing heavy lifting that this eval does not isolate.
- `pandas` and `scikit-learn` expose no root changelog file, so tier assignment for them rests on
  GitHub Releases alone.
