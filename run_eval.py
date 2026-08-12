"""Run the eval set end to end. One LLM call per upgrade, one pinned model, results to CSV."""
import csv, json, time, sys
from collections import defaultdict
from agent import analyze

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.5-flash-lite"
RUN_ID = time.strftime("%Y%m%dT%H%M%S")


def load_ground_truth(path="eval_set.csv"):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    rows = load_ground_truth()
    by_pkg = defaultdict(list)
    for r in rows:
        by_pkg[(r["package"], r["from_version"], r["to_version"],
                r["import_name"], r["source_tier"])].append(r)

    raw_dump = {}
    for (pkg, lo, hi, imp, tier), grows in by_pkg.items():
        print(f"\n=== {pkg} {lo} → {hi}  [tier={tier}]", flush=True)
        try:
            verdicts, meta = analyze(pkg, lo, hi, imp or None, "eval_targets", MODEL)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {str(e)[:160]}", flush=True)
            raw_dump[pkg] = {"error": f"{type(e).__name__}: {e}"}
            continue

        raw_dump[pkg] = {"meta": meta, "verdicts": verdicts}
        if meta.get("error"):
            print(f"  ERROR {meta['error']}", flush=True)
            continue

        # aggregate predictions per symbol (a symbol may appear at several lines)
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
                r["pred_breaking"] = ""      # scanner found no such usage this run
                continue
            r["pred_breaking"] = a["breaking"]
            r["pred_grounded"] = a["grounded"]
            r["pred_evidence_source"] = a["src"]
            r["pred_patch"] = a["patch"]
            r["model"] = MODEL
            r["run_id"] = RUN_ID

        g = sum(v["grounded"] for v in verdicts)
        print(f"  grounded {g}/{len(verdicts)} | "
              f"breaking {sum(1 for v in verdicts if v.get('breaking'))}", flush=True)

    out = f"eval_results_{RUN_ID}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    with open(f"eval_raw_{RUN_ID}.json", "w", encoding="utf-8") as f:
        json.dump(raw_dump, f, indent=2)
    print(f"\nwrote {out} and eval_raw_{RUN_ID}.json")
    report(rows)


def prf(rows, gt_key):
    tp = sum(1 for r in rows if r[gt_key] == 1 and r["pred_breaking"] == 1)
    fp = sum(1 for r in rows if r[gt_key] == 0 and r["pred_breaking"] == 1)
    fn = sum(1 for r in rows if r[gt_key] == 1 and r["pred_breaking"] == 0)
    tn = sum(1 for r in rows if r[gt_key] == 0 and r["pred_breaking"] == 0)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return tp, fp, fn, tn, p, rc


def report(rows):
    scored = []
    for r in rows:
        if r["pred_breaking"] == "":
            continue
        scored.append({
            "package": r["package"], "symbol": r["symbol"], "tier": r["source_tier"],
            "severity": r["gt_severity"],
            "gt_action": int(r["gt_breaking"]),
            "gt_removed": 1 if r["gt_severity"] == "removed" else 0,
            "pred_breaking": int(r["pred_breaking"]),
            "pred_grounded": int(r["pred_grounded"] or 0),
            "src": r["pred_evidence_source"],
        })
    n = len(scored)
    print(f"\n{'='*62}\nEVAL — model={MODEL}  run={RUN_ID}  usages scored={n}\n{'='*62}")

    for label, key in (("PRIMARY (action-required: deprecated counts)", "gt_action"),
                       ("SECONDARY (removed-only)", "gt_removed")):
        tp, fp, fn, tn, p, rc = prf(scored, key)
        acc = (tp + tn) / n if n else 0
        print(f"\n{label}")
        print(f"  TP {tp}  FP {fp}  FN {fn}  TN {tn}")
        print(f"  precision {p:.0%} | recall {rc:.0%} | accuracy {acc:.0%} ({tp+tn}/{n})")

    pos = [r for r in scored if r["pred_breaking"] == 1]
    gr = sum(r["pred_grounded"] for r in pos)
    print(f"\nGROUNDED RATE (positive verdicts citing verifiable text): "
          f"{gr}/{len(pos)} = {gr/len(pos):.0%}" if pos else "\nGROUNDED RATE: no positive verdicts")

    print("\nEVIDENCE SOURCE (grounded positives)")
    srcs = defaultdict(int)
    for r in pos:
        if r["pred_grounded"]:
            srcs[r["src"]] += 1
    for k, v in sorted(srcs.items()):
        print(f"  {k:<16} {v}")

    print("\nFAILURE DECOMPOSITION (missed breaking changes)")
    reasoning, coverage = [], []
    for r in scored:
        if r["gt_action"] == 1 and r["pred_breaking"] == 0:
            (coverage if r["tier"] == "neither" else reasoning).append(r)
    print(f"  reasoning failures      {len(reasoning):>2}  (evidence was in corpus, model missed it)")
    for r in reasoning:
        print(f"      {r['package']}: {r['symbol']} [{r['severity']}]")
    print(f"  source-coverage failures {len(coverage):>2}  (documented outside Releases + changelog)")
    for r in coverage:
        print(f"      {r['package']}: {r['symbol']} [{r['severity']}]")

    fps = [r for r in scored if r["gt_action"] == 0 and r["pred_breaking"] == 1]
    print(f"\nFALSE POSITIVES {len(fps)}")
    for r in fps:
        print(f"      {r['package']}: {r['symbol']} (grounded={r['pred_grounded']})")

    print("\nBY TIER")
    tiers = defaultdict(lambda: [0, 0, 0])   # n, correct, grounded_pos
    for r in scored:
        t = tiers[r["tier"]]
        t[0] += 1
        t[1] += int(r["gt_action"] == r["pred_breaking"])
        t[2] += int(r["pred_breaking"] == 1 and r["pred_grounded"] == 1)
    for k, (tot, corr, gp) in sorted(tiers.items()):
        print(f"  {k:<18} {corr}/{tot} correct   grounded positives: {gp}")


if __name__ == "__main__":
    main()
