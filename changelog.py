import urllib.request, urllib.error, json, re
from urllib.parse import urlparse
from collections import Counter
from packaging.version import parse, InvalidVersion
import os
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("GITHUB_TOKEN")
api_key = os.getenv("GEMINI_API_KEY")

CHANGELOG_NAMES = ["CHANGELOG.md", "CHANGES.md", "CHANGELOG.rst", "CHANGES.rst",
                   "HISTORY.md", "HISTORY.rst", "CHANGELOG"]

def get_github_repo(pkg):
    url = f"https://pypi.org/pypi/{pkg}/json"
    data = json.load(urllib.request.urlopen(url))
    urls = data["info"]["project_urls"]
    if not urls:
        return None
    all_pairs = []
    for u in urls.values():
        if "github.com" in u.lower():
            parsed = urlparse(u)
            pair = tuple(parsed.path.strip("/").split("/")[:2])
            if pair[0] == "sponsors":
                continue
            all_pairs.append(pair)
    if not all_pairs:
        return None
    github = Counter(all_pairs).most_common(1)[0][0]

    return github

def get_releases(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req))

def get_changelog_file(owner, repo, token=None):
    """Fetch a changelog file from the repo root. Returns (name, text) or (None, None)."""
    for branch in ("main", "master"):
        for name in CHANGELOG_NAMES:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{name}"
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    return name, r.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError:
                continue
            except Exception:
                continue
    return None, None

_TAG_NUM = re.compile(r"\d+(?:[._]\d+)*")

def tag_version(tag):
    """Best-effort version from a release tag, or None if it carries none.

    Release tags are not PEP 440: 'v2.0.0', 'rel_2_0_52' (SQLAlchemy),
    'release-1.2.3'. Drop any leading prefix, then try the remainder as-is so
    pre-release suffixes survive ('1.2.3-beta1' -> 1.2.3b1); only if that fails
    fall back to the bare numeric run with '_' read as a separator.
    """
    tag = (tag or "").strip()
    first_digit = re.search(r"\d", tag)
    if not first_digit:
        return None
    body = tag[first_digit.start():]
    for candidate in (body, _TAG_NUM.search(body).group(0).replace("_", ".")):
        try:
            return parse(candidate)
        except InvalidVersion:
            continue
    return None

def get_release_range(releases,from_version,to_version):
    """Releases in (from_version, to_version], oldest first.

    Tags that carry no parseable version are skipped — a single odd tag in the
    repo's history must not sink the whole range.
    """
    lo, hi = parse(from_version), parse(to_version)
    selected = []
    for r in releases:
        v = tag_version(r.get("tag_name"))
        if v is not None and lo < v <= hi:
            selected.append((v, r))
    return [r for _, r in sorted(selected, key=lambda pair: pair[0])]

if __name__ == "__main__":
    for p in ["requests", "pydantic", "numpy", "cowsay"]:
        print(p, get_github_repo(p))
