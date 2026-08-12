"""Re-verify saved model outputs against a rebuilt corpus. No LLM calls.

The retrieval corpus is a pure function of (package, versions, usages), so it can be
reconstructed exactly. Only the mechanical citation check changes — the model's raw
verdicts are replayed untouched.
"""
import csv, json, glob, sys
from collections import defaultdict
from agent import verify, gather
from ast_walker import scan_repo
from retrieval import select
import run_eval

RAW = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("eval_raw_*.json"))[-1]


def main():
    saved = json.load(open(RAW, encoding="utf-8"))
    rows = run_eval.load_ground_truth()
    by_pkg = defaultdict(list)
    for r in rows:
        by_pkg[(r["package"], r["from_version"], r["to_version"],
                r["import_name"], r["source_tier"])].append(r)

    for (pkg, lo, hi, imp, tier), grows in by_pkg.items():
        blob = saved.get(pkg)
        if not blob or "verdicts" not in blob:
            continue
        verdicts = blob["verdicts"]
        # undo the previous run's downgrade so the model's original claim is re-judged
        for v in verdicts:
            v["breaking"] = bool(v.get("breaking")) or bool(v.get("note"))
            v.pop("note", None)

        usages = scan_repo("eval_targets", pkg, imp or None)
        entries, _meta = gather(pkg, lo, hi, log=lambda *a, **k: None)
        chunks, _how = select(entries, usages)
        verify(verdicts, chunks)

        agg = defaultdict(lambda: {"breaking": 0, "grounded": 0, "src": "none", "patch": ""})
        for v in verdicts:
            a = agg[v.get("symbol", "")]
            a["breaking"] = max(a["breaking"], int(bool(v.get("breaking"))))
            a["grounded"] = max(a["grounded"], int(bool(v.get("grounded"))))
            if v.get("grounded"):
                a["src"] = v.get("evidence_source", "none")
            if v.get("patch"):
                a["patch"] = v["patch"]

        for r in grows:
            a = agg.get(r["symbol"])
            if a is None:
                r["pred_breaking"] = ""
                continue
            r["pred_breaking"] = a["breaking"]
            r["pred_grounded"] = a["grounded"]
            r["pred_evidence_source"] = a["src"]
            r["pred_patch"] = a["patch"]
            r["model"] = blob.get("meta", {}).get("model", "")
            r["run_id"] = RAW.replace("eval_raw_", "").replace(".json", "") + "-rescored"
        print(f"{pkg:<14} grounded {sum(v['grounded'] for v in verdicts)}/{len(verdicts)}", flush=True)

    out = RAW.replace("eval_raw_", "eval_results_").replace(".json", "_rescored.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")
    run_eval.MODEL = "gemini-3.5-flash-lite (rescored)"
    run_eval.RUN_ID = RAW
    run_eval.report(rows)


if __name__ == "__main__":
    main()
