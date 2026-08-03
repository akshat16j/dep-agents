import os, json
from google import genai
from dotenv import load_dotenv
from changelog import get_github_repo, get_releases, get_release_range
from prompt import PATCH_PROMPT

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PACKAGE = "pydantic"
FROM_VERSION = "1.10.0"
TO_VERSION = "2.0.0"

usage = {
    "file": "target.py",
    "line": 5,
    "symbol": "pydantic.BaseModel.dict",
    "snippet": "data = user.dict()",
}

owner, repo = get_github_repo(PACKAGE)
releases = get_release_range(
    get_releases(owner, repo, os.getenv("GITHUB_TOKEN")),
    FROM_VERSION, TO_VERSION,
)

changelog_text = "\n\n".join(
    f"## {r['tag_name']}\n{r['body'] or ''}" for r in releases
)

print("changelog chars:", len(changelog_text)) 

prompt = PATCH_PROMPT.format(
    PACKAGE=PACKAGE,
    FROM_VERSION=FROM_VERSION,
    TO_VERSION=TO_VERSION,
    changelog_text=changelog_text,
    usage=usage,
)

resp = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
)

raw = resp.text.strip()
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]


try:
    result = json.loads(raw)
    print(json.dumps(result, indent=2))
except json.JSONDecodeError:
    print("Failed to parse. Raw output:\n", raw)
