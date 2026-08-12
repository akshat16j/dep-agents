import os
from dotenv import load_dotenv
from changelog import get_github_repo, get_releases, get_release_range
from retrieval import chunk_releases, select
load_dotenv()

owner, repo = get_github_repo("pydantic")
releases = get_release_range(get_releases(owner, repo, os.getenv("GITHUB_TOKEN")),
                             "1.10.0", "2.0.0")
full = "\n\n".join(r.get("body") or "" for r in releases)
chunks = chunk_releases(releases)

print(f"releases {len(releases)} | full text {len(full):,} chars | chunks {len(chunks)}")
print("mentions model_dump :", full.count("model_dump"))
print("mentions .dict      :", full.count(".dict"))
print("\n--- chunks containing the evidence ---")
for c in chunks:
    if "model_dump" in c["text"] or ".dict(" in c["text"]:
        print(f"[{c['tag']}] {c['text'][:200]}\n")

picked, how = select(releases, [{"symbol": "pydantic.BaseModel.dict"}])
print(f"\nselected: {how}, {len(picked)} chunks, {sum(len(c['text']) for c in picked)} chars")
for c in picked[:10]:
    print(f"  {c.get('score', 0):.3f} [{c['tag']}] {c['text'][:90]}")
