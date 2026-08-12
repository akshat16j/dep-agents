"""Static analysis: which symbols from a given package does a file actually use?"""
import ast
from pathlib import Path


def _root_name(node):
    """Leftmost Name of a possibly-chained expression: pd.DataFrame.foo -> 'pd'."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _resolve(func, import_map, class_bases, var_types):
    if isinstance(func, ast.Name):
        return import_map.get(func.id) or class_bases.get(func.id)

    if isinstance(func, ast.Attribute):
        root = _root_name(func)
        if root is None:
            return None                       # chained call like get_x().y() — unresolvable
        parts, n = [], func
        while isinstance(n, ast.Attribute):
            parts.append(n.attr)
            n = n.value
        parts.reverse()
        base = import_map.get(root) or var_types.get(root) or class_bases.get(root)
        return ".".join([base] + parts) if base else None

    return None


def scan_file(path, package, import_name=None):
    """Return [{file, line, symbol, snippet}] for calls into `package`.

    import_name: PyPI name != import name for many packages
                 (scikit-learn -> sklearn, python-dateutil -> dateutil).
    """
    root_pkg = (import_name or package).replace("-", "_")
    src = Path(path).read_text()
    tree = ast.parse(src)

    # pass 1 — imports to fully qualified names
    import_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                import_map[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                import_map[a.asname or a.name] = f"{node.module}.{a.name}"

    # pass 2 — classes inheriting from an imported symbol
    class_bases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                r = _root_name(base)
                if r in import_map:
                    class_bases[node.name] = import_map[r]
                    break

    # pass 3 — variables assigned from those classes or from imported callables
    var_types = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            # resolve the full callee expression, not just its root: pd.DataFrame() must
            # give "pandas.DataFrame", not "pandas", or df.append() resolves to package level
            base = _resolve(node.value.func, import_map, class_bases, var_types)
            if base:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        var_types[t.id] = base

    # pass 4 — calls, filtered to the package under test
    seen, out = set(), []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        symbol = _resolve(node.func, import_map, class_bases, var_types)
        if not symbol or symbol.split(".")[0] != root_pkg:
            continue
        key = (symbol, node.lineno)
        if key in seen:
            continue
        seen.add(key)
        out.append({"file": str(path), "line": node.lineno, "symbol": symbol,
                    "snippet": ast.get_source_segment(src, node) or ""})

    return sorted(out, key=lambda u: u["line"])


def scan_repo(root, package, import_name=None):
    usages = []
    for p in Path(root).rglob("*.py"):
        if any(x in p.parts for x in ("venv", ".venv", "site-packages", "__pycache__", "build")):
            continue
        try:
            usages.extend(scan_file(p, package, import_name))
        except SyntaxError:
            continue                          # unparseable file — skip, don't crash the scan
    return usages


if __name__ == "__main__":
    import sys, json
    print(json.dumps(scan_repo(sys.argv[1], sys.argv[2]), indent=2))