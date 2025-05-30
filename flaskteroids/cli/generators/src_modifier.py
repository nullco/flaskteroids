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


def add_rules(rules):
    class AddRules(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call) and
                    isinstance(decorator.func, ast.Name) and
                    decorator.func.id == "rules"
                ):
                    for rule in rules:
                        rule_node = ast.parse(rule, mode='eval').body
                        decorator.args.append(rule_node)
            return node
    return AddRules


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
