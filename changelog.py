import urllib.request, json
from urllib.parse import urlparse
from collections import Counter

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
        

for p in ["requests", "pydantic", "numpy", "cowsay"]:
    print(p, get_github_repo(p))