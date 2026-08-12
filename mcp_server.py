"""MCP server exposing the dependency-upgrade agent as tools other clients can call.

Wraps the existing pipeline — no logic lives here. Tools:
  scan_repo     : AST usage resolution only, no LLM, no network
  check_upgrade : full pipeline — scan, retrieve, verdict, grounding verification
  fetch_evidence: retrieval corpus only, for inspecting what the model would see
"""
import sys, json, functools
from typing import Optional
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer   # SDK 2.0; FastMCP was removed in this release

from ast_walker import scan_repo as _scan
from retrieval import select, render

load_dotenv()
mcp = MCPServer("dep-agent")

# stdout carries the JSON-RPC frames; anything printed there corrupts the stream and the
# client silently shows no tools. stderr is captured to the client's MCP server log, so
# progress lines stay visible for debugging.
_stderr_log = functools.partial(print, file=sys.stderr, flush=True)


@mcp.tool()
def scan_repo(path: str, package: str, import_name: Optional[str] = None) -> str:
    """Find every call into `package` in the Python files under `path`.

    Static analysis only — no network, no LLM. Returns resolved symbols with
    file, line and source snippet. `import_name` is needed when the PyPI name
    differs from the import name (scikit-learn -> sklearn).
    """
    usages = _scan(path, package, import_name)
    if not usages:
        return json.dumps({
            "usages": [],
            "warning": "No calls into this package were found. Check the import "
                       "name before treating this as safe to upgrade — an empty "
                       "scan is indistinguishable from a clean repo."}, indent=2)
    return json.dumps({"usages": usages, "count": len(usages)}, indent=2)


@mcp.tool()
def fetch_evidence(package: str, from_version: str, to_version: str,
                   symbols: Optional[list[str]] = None) -> str:
    """Return the changelog evidence the agent would retrieve, without asking an LLM.

    Useful for checking whether a breaking change is documented at all before
    spending a model call on it.
    """
    from agent import gather              # one implementation of source selection

    sections, meta = gather(package, from_version, to_version, log=_stderr_log)
    if sections is None:
        return json.dumps({"error": meta.get("error"), "package": package}, indent=2)

    # full-shape usages, so these stay valid if they are ever handed to ask()
    usages = [{"symbol": s, "file": "<query>", "line": 0, "snippet": ""}
              for s in (symbols or [])]
    chunks, how = select(sections, usages)
    evidence = render(chunks)
    return json.dumps({**meta, "retrieval": how, "chunks": len(chunks),
                       "chars": len(evidence),
                       "truncated": len(evidence) > 6000,
                       "evidence": evidence[:6000]}, indent=2)


@mcp.tool()
def check_upgrade(path: str, package: str, from_version: str, to_version: str,
                  import_name: Optional[str] = None) -> str:
    """Full check: resolve usage, retrieve version-scoped notes, produce verdicts.

    Every positive verdict must cite verbatim changelog text; citations are
    verified mechanically against the retrieved corpus and downgraded if they
    do not match. Returns one verdict per usage.
    """
    from agent import run_check          # keep the pipeline in one place
    return json.dumps(
        run_check(path, package, from_version, to_version, import_name, log=_stderr_log),
        indent=2)


if __name__ == "__main__":
    mcp.run()