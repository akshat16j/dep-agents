import urllib.request, json
from urllib.parse import urlparse
from collections import Counter
from packaging.version import parse

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

token = open(".env").read().split("=")[1].strip()

def get_releases(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req))
        
releases = get_releases("psf","requests",token)

def get_release_range(releases,from_version,to_version):
    lo, hi = parse(from_version), parse(to_version)
    selected = [r for r in releases if lo < parse(r["tag_name"].lstrip("v")) <= hi]
    return sorted(selected, key=lambda r: parse(r["tag_name"].lstrip("v")))

versions = get_release_range(releases,"2.28.0","2.31.0")

for v in versions:
    print(v["tag_name"])