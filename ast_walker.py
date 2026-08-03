import ast

tree = ast.parse(open("target.py").read())

import_map ={}

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for a in node.names:
            print(f"L{node.lineno} import: {a.name} as {a.asname}")
            import_map[a.asname or a.name] = a.name
    elif isinstance(node, ast.ImportFrom):
        for a in node.names:
            print(f"L{node.lineno} import: from {node.module} import {a.name} as {a.asname}")
            import_map[a.asname or a.name] = node.module + "." + a.name

for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value,ast.Name):
                root = node.func.value.id
                if(root in import_map):
                    print(f"L{node.lineno} {import_map[root]}.{node.func.attr}")
        elif isinstance(node.func, ast.Name):
            if( node.func.id in import_map):
                print(f"L{node.lineno} {import_map[node.func.id]}")


print(import_map)