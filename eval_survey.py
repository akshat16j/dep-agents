"""Survey candidate upgrades: which source tier covers each, and does it document the terms we care about?

Read-only reconnaissance for building eval_set.csv. No LLM calls.
"""
import os, sys, json
from dotenv import load_dotenv
from changelog import get_github_repo, get_releases, get_release_range, get_changelog_file
from retrieval import sections_from_changelog

load_dotenv()
TOKEN = os.getenv("GITHUB_TOKEN")

CANDIDATES = [
    # (pypi_name, from_version, to_version, import_name)
    ("urllib3",      "1.26.0",  "2.0.0",  None),
    ("pydantic",     "1.10.0",  "2.0.0",  None),
    ("requests",     "2.28.0",  "2.31.0", None),
    ("markupsafe",   "1.1.1",   "2.1.0",  None),
    ("jinja2",       "2.11.0",  "3.1.0",  None),
    ("click",        "7.1.2",   "8.1.0",  None),
    ("flask",        "1.1.4",   "2.3.0",  None),
    ("werkzeug",     "1.0.1",   "2.3.0",  None),
    ("attrs",        "20.3.0",  "22.2.0", None),
    ("numpy",        "1.20.0",  "1.24.0", None),
    ("pandas",       "1.5.0",   "2.0.0",  None),
    ("sqlalchemy",   "1.3.24",  "1.4.46", None),
    ("httpx",        "0.23.0",  "0.24.1", None),
    ("scikit-learn", "1.0.2",   "1.3.0",  "sklearn"),
    ("beautifulsoup4", "4.10.0", "4.12.0", "bs4"),
    ("rich",         "12.0.0",  "13.0.0", None),
]


def survey(pkg, lo, hi):
    row = {"package": pkg, "from": lo, "to": hi}
    try:
        got = get_github_repo(pkg)
        if not got:
            return {**row, "tier": "no-repo"}
        owner, repo = got
        row["repo"] = f"{owner}/{repo}"
    except Exception as e:
        return {**row, "tier": f"repo-error:{type(e).__name__}"}

    try:
        rels = get_release_range(get_releases(owner, repo, TOKEN), lo, hi)
    except Exception:
        rels = []
    rel_text = "\n".join(r.get("body") or "" for r in rels)
    row["releases_n"] = len(rels)
    row["releases_ch"] = len(rel_text)

    try:
        name, text = get_changelog_file(owner, repo, TOKEN)
    except Exception:
        name, text = None, None
    secs = sections_from_changelog(text, lo, hi) if text else []
    sec_text = "\n".join(s["body"] for s in secs)
    row["changelog_file"] = name
    row["sections_n"] = len(secs)
    row["sections_ch"] = len(sec_text)

    # crude signal: does either source talk about removals/deprecations at all?
    for label, t in (("rel", rel_text), ("sec", sec_text)):
        row[f"{label}_remove"] = t.lower().count("remov")
        row[f"{label}_deprec"] = t.lower().count("deprecat")

    if row["releases_ch"] > 2000 and row["rel_remove"] + row["rel_deprec"] > 0:
        row["tier"] = "releases"
    elif row["sections_ch"] > 2000 and row["sec_remove"] + row["sec_deprec"] > 0:
        row["tier"] = "changelog_file"
    else:
        row["tier"] = "thin/none"
    return row


if __name__ == "__main__":
    out = []
    for pkg, lo, hi, _imp in CANDIDATES:
        r = survey(pkg, lo, hi)
        out.append(r)
        print(f"{r['package']:<16} {r.get('repo',''):<26} tier={r['tier']:<15} "
              f"rel={r.get('releases_n',0):>3}/{r.get('releases_ch',0):>7,}ch "
              f"file={str(r.get('changelog_file')):<14} sec={r.get('sections_n',0):>3}/{r.get('sections_ch',0):>7,}ch "
              f"rm={r.get('rel_remove',0)}/{r.get('sec_remove',0)} dep={r.get('rel_deprec',0)}/{r.get('sec_deprec',0)}",
              flush=True)
    with open("eval_survey.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
