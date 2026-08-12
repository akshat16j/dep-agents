import urllib3
from urllib3 import PoolManager, HTTPResponse

http = PoolManager()
raw = http.urlopen("GET", "https://example.com")
old = urllib3.HTTPResponse.from_httplib(raw)
resp = HTTPResponse()
headers = resp.getheaders()
