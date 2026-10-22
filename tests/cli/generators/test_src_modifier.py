import ast

import pytest

from flaskteroids.cli.generators.src_modifier import (
    add_base_cls,
    add_declarations,
    add_imports,
    add_routes,
)


class TestAddRoutes:
    """Tests for add_routes function."""

    def test_add_routes_appends_to_register_function(self):
        """Test adding routes to a register function."""
        source = """
def register(router):
    router.get("/", to="welcome#index")
"""
        tree = ast.parse(source)
        routes = ["router.get('/about', to='pages#about')", "router.resources('posts')"]
        transformer = add_routes(routes)()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify the register function now has two additional statements
        register_func = new_tree.body[0]
        assert len(register_func.body) == 3  # original + 2 new
        assert isinstance(register_func.body[1], ast.Expr)
        assert isinstance(register_func.body[2], ast.Expr)

    def test_add_routes_preserves_modules_lacking_register_function(self):
        """Test adding routes when no register function exists."""
        source = """
def other_func():
    pass
"""
        tree = ast.parse(source)
        routes = ["router.get('/test', to='test#index')"]
        transformer = add_routes(routes)()
        new_tree = transformer.visit(tree)

        # Should remain unchanged
        assert len(new_tree.body) == 1
        assert new_tree.body[0].name == "other_func"

    def test_add_routes_preserves_function_for_empty_input(self):
        """Test adding empty routes list."""
        source = """
def register(router):
    pass
"""
        tree = ast.parse(source)
        transformer = add_routes([])()
        new_tree = transformer.visit(tree)

        # Should remain unchanged
        register_func = new_tree.body[0]
        assert len(register_func.body) == 1  # only pass


class TestAddImports:
    """Tests for add_imports function."""

    def test_add_imports_inserts_after_existing_imports(self):
        """Test adding imports to a module."""
        source = """
import os
from flask import Flask

def func():
    pass
"""
        tree = ast.parse(source)
        imports = ["import sys", "from collections import defaultdict"]
        transformer = add_imports(imports)()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify imports are inserted after existing imports
        assert len(new_tree.body) == 5
        assert (
            isinstance(new_tree.body[0], ast.Import)
            and new_tree.body[0].names[0].name == "os"
        )
        assert (
            isinstance(new_tree.body[1], ast.ImportFrom)
            and new_tree.body[1].module == "flask"
        )
        assert (
            isinstance(new_tree.body[2], ast.Import)
            and new_tree.body[2].names[0].name == "sys"
        )
        assert (
            isinstance(new_tree.body[3], ast.ImportFrom)
            and new_tree.body[3].module == "collections"
        )
        assert isinstance(new_tree.body[4], ast.FunctionDef)

    def test_add_imports_inserts_at_start_of_module(self):
        """Test adding imports when no imports exist."""
        source = """
def func():
    pass
"""
        tree = ast.parse(source)
        imports = ["import json"]
        transformer = add_imports(imports)()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Import should be inserted at the beginning
        assert len(new_tree.body) == 2
        assert isinstance(new_tree.body[0], ast.Import)
        assert new_tree.body[0].names[0].name == "json"
        assert isinstance(new_tree.body[1], ast.FunctionDef)

    def test_add_imports_preserves_module_for_empty_input(self):
        """Test adding empty imports list."""
        source = """
import os

def func():
    pass
"""
        tree = ast.parse(source)
        transformer = add_imports([])()
        new_tree = transformer.visit(tree)

        # Should remain unchanged
        assert len(new_tree.body) == 2


class TestAddDeclarations:
    @pytest.mark.parametrize(
        "body",
        [
            "    pass",
            "    belongs_to('user')",
            "    belongs_to('user')\n    def title(self): pass",
        ],
    )
    def test_add_declarations_extends_class_body_before_methods(self, body):
        tree = ast.parse("class Post(Model):\n" + body)
        transformer = add_declarations(
            ["has_many('comments')", "validates('title', presence=True)"]
        )()
        node = transformer.visit(tree).body[0]
        calls = [
            stmt.value.func.id
            for stmt in node.body
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
        ]
        expected = ["belongs_to"] if "belongs_to" in body else []
        assert calls == [*expected, "has_many", "validates"]
        assert not any(isinstance(stmt, ast.Pass) for stmt in node.body)
        if "def title" in body:
            assert isinstance(node.body[-1], ast.FunctionDef)

    def test_add_declarations_preserves_docstrings_and_decorators(self):
        tree = ast.parse(
            '@other_decorator\nclass Post(Model):\n    """A post."""\n    pass\n'
        )
        node = add_declarations(["belongs_to('user')"])().visit(tree).body[0]
        assert ast.get_docstring(node) == "A post."
        assert node.decorator_list[0].id == "other_decorator"
        assert node.body[1].value.func.id == "belongs_to"

    def test_add_declarations_preserves_class_for_empty_input(self):
        tree = ast.parse("class Post(Model):\n    pass\n")
        expected = ast.dump(tree)
        assert ast.dump(add_declarations([])().visit(tree)) == expected


class TestAddBaseCls:
    """Tests for add_base_cls function."""

    def test_add_base_cls_adds_first_base(self):
        """Test adding base class to a class with no bases."""
        source = """
class Post:
    pass
"""
        tree = ast.parse(source)
        transformer = add_base_cls("Model")()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify base class is added
        class_def = new_tree.body[0]
        assert len(class_def.bases) == 1
        assert isinstance(class_def.bases[0], ast.Name)
        assert class_def.bases[0].id == "Model"

    def test_add_base_cls_appends_to_existing_bases(self):
        """Test adding base class to a class with existing bases."""
        source = """
class Post(BaseModel):
    pass
"""
        tree = ast.parse(source)
        transformer = add_base_cls("Model")()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify new base class is added
        class_def = new_tree.body[0]
        assert len(class_def.bases) == 2
        base_ids = [base.id for base in class_def.bases]
        assert "BaseModel" in base_ids
        assert "Model" in base_ids

    def test_add_base_cls_preserves_existing_base(self):
        """Test adding base class when it already exists."""
        source = """
class Post(Model):
    pass
"""
        tree = ast.parse(source)
        transformer = add_base_cls("Model")()
        new_tree = transformer.visit(tree)

        # Should not add duplicate
        class_def = new_tree.body[0]
        assert len(class_def.bases) == 1
        assert class_def.bases[0].id == "Model"

    def test_add_base_cls_updates_each_class(self):
        """Test adding base class affects all classes in module."""
        source = """
class Post:
    pass

class Comment:
    pass
"""
        tree = ast.parse(source)
        transformer = add_base_cls("Model")()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Both classes should get the base
        assert len(new_tree.body) == 2
        for class_def in new_tree.body:
            assert len(class_def.bases) == 1
            assert class_def.bases[0].id == "Model"
