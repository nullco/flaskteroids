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
