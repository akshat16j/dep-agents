import os, re, json, argparse
from google import genai
from dotenv import load_dotenv
from changelog import (get_github_repo, get_releases, get_release_range,
                       get_changelog_file)
from prompt import PATCH_PROMPT
from ast_walker import scan_repo
from retrieval import select, render, sections_from_changelog

load_dotenv()
MODEL = "gemini-3.5-flash-lite"

_client = None


def client():
    """Built on first use, not on import — `import agent` must not require an API key."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _norm(s):
    """Comparison key that survives the same sentence being rendered in RST or Markdown.

    One changelog line reaches us as ``x`` (`#1 <url>`__) in RST and `x` ([#1](url)) in
    Markdown, and a model quoting either strips the markup. Reducing both sides to
    lowercase alphanumerics ignores formatting and punctuation, while the word and digit
    content must still appear verbatim and in order — so a fabricated quote is still
    caught. Without this, correct verdicts are discarded as ungrounded.
    """
    s = re.sub(r"https?://\S+", "", s)     # issue links differ between renderings
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def verify(verdicts, chunks):
    """Mechanically confirm each evidence_quote actually appears in the retrieved notes."""
    per_chunk = [(_norm(c["text"]), c.get("source", "releases")) for c in chunks]
    norm = _norm(" ".join(c["text"] for c in chunks))
    for v in verdicts:
        q = v.get("evidence_quote")
        nq = _norm(q)[:120] if q else ""
        v["grounded"] = bool(nq) and nq in norm
        if v["grounded"]:
            v["evidence_source"] = next((s for t, s in per_chunk if nq in t), "unattributed")
        else:
            v["evidence_source"] = "none"
        v["breaking_raw"] = bool(v.get("breaking"))     # keep the model's claim auditable
        if v.get("breaking") and not v["grounded"]:
            v["breaking"] = False
            v["note"] = "UNGROUNDED — claim not supported by retrieved notes; downgraded"
    return verdicts


def ask(package, from_version, to_version, chunks, usages, model):
    usages_text = "\n\n".join(
        f"- Symbol: {u['symbol']}\n"
        f"  File: {u['file']}\n"
        f"  Line: {u['line']}\n"
        f"  ```python\n  {u['snippet']}\n  ```"
        for u in usages
    )
    prompt = PATCH_PROMPT.format(
        PACKAGE=package,
        FROM_VERSION=from_version,
        TO_VERSION=to_version,
        changelog_text=render(chunks),
        usages_text=usages_text,
    )
    resp = client().models.generate_content(model=model, contents=prompt)
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, raw


def gather(package, from_version, to_version, log=print):
    """Collect the evidence corpus: GitHub Releases unioned with the repo's changelog file.

    The union is unconditional because it costs one plain HTTP fetch and no LLM call, and a
    size threshold does not identify the packages that need it — flask ships 5,413 chars of
    release bodies containing zero removal lines while its CHANGES.rst has 48.
    """
    got = get_github_repo(package)
    if not got:
        return None, {"error": "no GitHub repo in PyPI project_urls"}
    owner, repo = got
    releases = get_release_range(
        get_releases(owner, repo, os.getenv("GITHUB_TOKEN")),
        from_version, to_version,
    )
    meta = {"repo": f"{owner}/{repo}", "releases_n": len(releases),
            "releases_ch": sum(len(r.get("body") or "") for r in releases)}

    entries = list(releases)
    name, text = get_changelog_file(owner, repo, os.getenv("GITHUB_TOKEN"))
    secs = sections_from_changelog(text, from_version, to_version) if text else []
    entries.extend(secs)
    meta.update({"changelog_file": name, "sections_n": len(secs),
                 "sections_ch": sum(len(s["body"]) for s in secs)})
    log(f"  sources: releases {meta['releases_n']}/{meta['releases_ch']:,}ch + "
        f"{name} {len(secs)}/{meta['sections_ch']:,}ch")
    return entries, meta


def analyze(package, from_version, to_version, import_name=None, repo_path="eval_targets",
            model=MODEL, log=print):
    """One upgrade, one LLM call. Returns (verdicts, meta)."""
    usages = scan_repo(repo_path, package, import_name)
    if not usages:
        return [], {"error": "NO_USAGES_FOUND"}
    log(f"  usages: {len(usages)}")

    entries, meta = gather(package, from_version, to_version, log=log)
    if entries is None:
        return [], meta

    chunks, how = select(entries, usages)
    meta.update({"retrieval": how, "chunks": len(chunks), "corpus_ch": len(render(chunks))})
    log(f"  retrieval: {how} | {len(chunks)} chunks | {meta['corpus_ch']:,} chars")

    result, raw = ask(package, from_version, to_version, chunks, usages, model)
    if result is None:
        meta["error"] = "unparseable JSON"
        meta["raw"] = raw
        return [], meta

    verdicts = verify(result.get("verdicts", []), chunks)
    meta["model"] = model
    return verdicts, meta


def run_check(path, package, from_version, to_version, import_name=None, model=MODEL,
              log=lambda *a, **k: None):
    """Public entry point: analyse one upgrade against one repo. Importable, no side effects.

    Returns a single JSON-serialisable dict — the shape an MCP tool can hand straight back.
    """
    verdicts, meta = analyze(package, from_version, to_version, import_name, path, model, log)
    if meta.get("error") == "NO_USAGES_FOUND":
        return {"verdict": "NO_USAGES_FOUND", "package": package,
                "note": "Static analysis found no calls into this package. "
                        "Check the import name before treating this as safe."}
    if meta.get("error"):
        return {"verdict": "ERROR", "package": package, "error": meta["error"]}

    grounded = sum(bool(v.get("grounded")) for v in verdicts)
    breaking = [v for v in verdicts if v.get("breaking")]
    return {"package": package, "from": from_version, "to": to_version,
            "model": model, "retrieval": meta.get("retrieval"),
            "chunks": meta.get("chunks"), "changelog_file": meta.get("changelog_file"),
            "verdicts": verdicts,
            "breaking_count": len(breaking),
            "grounded_rate": grounded / max(len(verdicts), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package", nargs="?", default="pydantic")
    ap.add_argument("from_version", nargs="?", default="1.10.0")
    ap.add_argument("to_version", nargs="?", default="2.0.0")
    ap.add_argument("--import-name", default=None)
    ap.add_argument("--repo-path", default="eval_targets")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    verdicts, meta = analyze(args.package, args.from_version, args.to_version,
                             args.import_name, args.repo_path, args.model)
    if meta.get("error"):
        print(json.dumps(meta, indent=2))
        raise SystemExit(1)

    print(json.dumps({"verdicts": verdicts}, indent=2))
    g = sum(v["grounded"] for v in verdicts)
    srcs = {v["evidence_source"] for v in verdicts if v["grounded"]}
    print(f"\n{args.package} {args.from_version} → {args.to_version} [{meta['model']}]")
    print(f"grounded rate: {g/len(verdicts):.0%} ({g}/{len(verdicts)})")
    print(f"evidence_source: {'|'.join(sorted(srcs)) if srcs else 'none'}")


if __name__ == "__main__":
    main()
