import urllib.request, json

pkg = "requests"
url = f"https://pypi.org/pypi/{pkg}/json"
data = json.load(urllib.request.urlopen(url))

print(data["info"]["version"])
print(data["info"]["project_urls"])
print(data["releases"])