"""Dump candidate breaking-change lines for a package range, so eval labels come from text, not memory."""
import os, re, sys
from dotenv import load_dotenv
from changelog import get_github_repo, get_releases, get_release_range, get_changelog_file
from retrieval import sections_from_changelog

load_dotenv()
TOKEN = os.getenv("GITHUB_TOKEN")
PAT = re.compile(r"remov|deprecat|renam|no longer|replaced by|dropped", re.I)
CODE = re.compile(r"``([^`]+)``|`([^`]+)`")


def dump(pkg, lo, hi, want=None, limit=40):
    owner, repo = get_github_repo(pkg)
    rel = get_release_range(get_releases(owner, repo, TOKEN), lo, hi)
    rel_text = "\n".join(f"[rel {r['tag_name']}] {r.get('body') or ''}" for r in rel)
    name, text = get_changelog_file(owner, repo, TOKEN)
    secs = sections_from_changelog(text, lo, hi) if text else []
    sec_text = "\n".join(f"[file {s['tag_name']}] {s['body']}" for s in secs)

    print(f"### {pkg} {lo} -> {hi}  ({owner}/{repo}, file={name})")
    for label, blob in (("RELEASES", rel_text), ("FILE", sec_text)):
        hits = []
        for line in blob.split("\n"):
            s = line.strip()
            if len(s) < 25 or not PAT.search(s):
                continue
            if not CODE.search(s):
                continue
            if want and not re.search(want, s, re.I):
                continue
            hits.append(s[:210])
        print(f"-- {label}: {len(hits)} candidate lines")
        for h in hits[:limit]:
            print("   ", h)
    print()


if __name__ == "__main__":
    pkg, lo, hi = sys.argv[1], sys.argv[2], sys.argv[3]
    want = sys.argv[4] if len(sys.argv) > 4 else None
    dump(pkg, lo, hi, want)
