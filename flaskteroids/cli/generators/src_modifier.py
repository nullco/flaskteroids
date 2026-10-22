import ast


def add_routes(routes):
    class AddRoutes(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == "register":
                for route in routes:
                    new_stmt = ast.parse(route).body[0]
                    node.body.append(new_stmt)
            return node

    return AddRoutes


def add_imports(imports):
    class AddImports(ast.NodeTransformer):
        def visit_Module(self, node):
            insert_at = 0
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    insert_at = i + 1
                else:
                    break
            for imp in imports:
                import_node = ast.parse(imp).body[0]
                node.body.insert(insert_at, import_node)
                insert_at += 1
            return node

    return AddImports


def add_declarations(declarations):
    class AddDeclarations(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            if not declarations:
                return node
            node.body = [stmt for stmt in node.body if not isinstance(stmt, ast.Pass)]
            insert_at = next(
                (
                    i
                    for i, stmt in enumerate(node.body)
                    if isinstance(
                        stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                ),
                len(node.body),
            )
            node.body[insert_at:insert_at] = [
                ast.Expr(value=ast.parse(value, mode="eval").body)
                for value in declarations
            ]
            return node

    return AddDeclarations


def add_base_cls(base_cls):
    class AddBaseCls(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            new_base = ast.Name(id=base_cls, ctx=ast.Load())
            if not any(
                isinstance(base, ast.Name) and base.id == new_base.id
                for base in node.bases
            ):
                node.bases.append(new_base)
            return node

    return AddBaseCls
