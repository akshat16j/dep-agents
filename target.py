import requests
import requests as rq
from requests import Session
import os
import urllib3
from urllib3 import PoolManager, HTTPResponse
from pydantic import BaseModel

class User(BaseModel):
    name: str

user = User(name="x")
data = user.dict()

r = requests.get("https://example.com")
s = rq.Session()
sess = Session()
os.path.join("a","b")

http = PoolManager()
raw = http.urlopen("GET", "https://example.com")

old = urllib3.HTTPResponse.from_httplib(raw)
resp = HTTPResponse()
headers = resp.getheaders()