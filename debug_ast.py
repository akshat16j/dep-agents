import sys, ast
from pathlib import Path
from ast_walker import scan_file

root, package = sys.argv[1], sys.argv[2]
for p in Path(root).rglob("*.py"):
    if any(x in p.parts for x in ("venv", ".venv", "site-packages", "__pycache__")):
        continue
    print(f"\n=== {p}")
    try:
        src = p.read_text()
        tree = ast.parse(src)
    except Exception as e:
        print(f"  PARSE FAILED: {type(e).__name__}: {e}")
        continue

    imports = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names: imports[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names: imports[a.asname or a.name] = f"{n.module}.{a.name}"
    print("  imports :", imports)
    print("  classes :", [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
    calls = [ast.dump(n.func)[:70] for n in ast.walk(tree) if isinstance(n, ast.Call)]
    print("  calls   :", calls)
    print("  RESOLVED:", scan_file(p, package))