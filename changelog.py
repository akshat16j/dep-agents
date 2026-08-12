import urllib.request, urllib.error, json
from urllib.parse import urlparse
from collections import Counter
from packaging.version import parse
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

def get_release_range(releases,from_version,to_version):
    lo, hi = parse(from_version), parse(to_version)
    selected = [r for r in releases if lo < parse(r["tag_name"].lstrip("v")) <= hi]
    return sorted(selected, key=lambda r: parse(r["tag_name"].lstrip("v")))

if __name__ == "__main__":
    for p in ["requests", "pydantic", "numpy", "cowsay"]:
        print(p, get_github_repo(p))
