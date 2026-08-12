"""Two-axis retrieval: deterministic version scoping, then semantic usage scoping."""
import re
import numpy as np
from packaging.version import parse, InvalidVersion

CHAR_BUDGET = 12000
_model = None


def _encoder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# A version heading: optional #'s, optional "Version"/"v" prefix, then a number.
# Covers "## 2.0.0", "Version 3.1.0", "v1.26.0", "## [0.24.1] - 2023-05-17", "2.0.0 (2023-04-26)".
_VERSION_LINE = re.compile(r"^(#{1,4}\s*)?(?:version\s+|v)?\[?(\d+\.\d+(?:\.\d+)?)\]?(?![\w.])",
                           re.IGNORECASE)
_UNDERLINE = re.compile(r"^[-=~^+*#]{3,}\s*$")


def _version_headings(text):
    """(line_index, version) for lines that head a version section.

    A markdown sub-heading like '### Removed' is not a boundary — it carries no version —
    so Keep-a-Changelog sections stay whole instead of shattering into fragments.
    """
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        m = _VERSION_LINE.match(s)
        if not m:
            continue
        is_md = bool(m.group(1))
        is_rst = i + 1 < len(lines) and bool(_UNDERLINE.match(lines[i + 1]))
        if is_md or is_rst:
            out.append((i, m.group(2)))
    return out, lines


def sections_from_changelog(text, from_version, to_version):
    """Split a CHANGELOG file on version headings, keep those in (from, to]."""
    heads, lines = _version_headings(text)
    lo, hi, out = parse(from_version), parse(to_version), []
    for n, (start, ver) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        try:
            v = parse(ver)
        except InvalidVersion:
            continue
        if lo < v <= hi:
            out.append({"tag_name": ver, "body": "\n".join(lines[start:end]),
                        "source": "changelog_file"})
    return out


def chunk_releases(releases):
    """One chunk per changelog entry, not per release — a breaking change is a bullet."""
    chunks = []
    for r in releases:
        tag, body = r["tag_name"], (r.get("body") or "")
        source = r.get("source", "releases")
        for block in re.split(r"\n(?=[-*#]|\d+\.)", body):
            text = block.strip()
            if len(text) < 20:
                continue
            chunks.append({"tag": tag, "text": text, "source": source})
    return chunks


def select(releases, usages, char_budget=CHAR_BUDGET, k=400):
    """Return (chunks, how) — 'version_scope_only' or 'semantic_topk'."""
    chunks = chunk_releases(releases)
    total = sum(len(c["text"]) for c in chunks)

    # deterministic filtering was enough — don't reach for embeddings
    if total <= char_budget:
        return chunks, "version_scope_only"

    symbols = sorted({u["symbol"] for u in usages if u.get("symbol")})
    if not symbols:
        # no symbols to rank against: encoding an empty query set makes the score
        # matmul fail, so fall back to version-scoped chunks trimmed to the budget
        picked, used = [], 0
        for c in chunks:
            if used + len(c["text"]) > char_budget:
                break
            picked.append(c)
            used += len(c["text"])
        return picked, "version_scope_truncated"

    queries = [s.replace(".", " ") for s in symbols]

    enc = _encoder()
    C = enc.encode([c["text"] for c in chunks], normalize_embeddings=True)
    Q = enc.encode(queries, normalize_embeddings=True)

    # each chunk scores by its best match against ANY used symbol
    score = (C @ Q.T).max(axis=1)
    order = np.argsort(-score)

    picked, used = [], 0
    for i in order[:k]:
        if used + len(chunks[i]["text"]) > char_budget:
            continue
        picked.append({**chunks[i], "score": float(score[i])})
        used += len(chunks[i]["text"])

    picked.sort(key=lambda c: c["tag"])
    return picked, "semantic_topk"


def render(chunks):
    return "\n\n".join(f"## {c['tag']}\n{c['text']}" for c in chunks)