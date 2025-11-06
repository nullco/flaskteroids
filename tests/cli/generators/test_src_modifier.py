import ast
import pytest
from flaskteroids.cli.generators.src_modifier import add_routes, add_imports, add_rules, add_base_cls


class TestAddRoutes:
    """Tests for add_routes function."""

    def test_add_routes_to_register_function(self):
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

    def test_add_routes_no_register_function(self):
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

    def test_add_routes_empty_list(self):
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

    def test_add_imports_to_module(self):
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
        assert isinstance(new_tree.body[0], ast.Import) and new_tree.body[0].names[0].name == "os"
        assert isinstance(new_tree.body[1], ast.ImportFrom) and new_tree.body[1].module == "flask"
        assert isinstance(new_tree.body[2], ast.Import) and new_tree.body[2].names[0].name == "sys"
        assert isinstance(new_tree.body[3], ast.ImportFrom) and new_tree.body[3].module == "collections"
        assert isinstance(new_tree.body[4], ast.FunctionDef)

    def test_add_imports_no_existing_imports(self):
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

    def test_add_imports_empty_list(self):
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


class TestAddRules:
    """Tests for add_rules function."""

    def test_add_rules_to_class_with_rules_decorator(self):
        """Test adding rules to a class decorated with @rules."""
        source = """
@rules(
    belongs_to('user'),
    validates('title', presence=True)
)
class Post(Model):
    pass
"""
        tree = ast.parse(source)
        rules = ["has_many('comments')", "validates('content', presence=True)"]
        transformer = add_rules(rules)()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify rules decorator has additional arguments
        class_def = new_tree.body[0]
        rules_decorator = class_def.decorator_list[0]
        assert len(rules_decorator.args) == 4  # original 2 + 2 new

    def test_add_rules_to_class_without_rules_decorator(self):
        """Test adding rules when class has no @rules decorator."""
        source = """
class Post(Model):
    pass
"""
        tree = ast.parse(source)
        rules = ["belongs_to('user')"]
        transformer = add_rules(rules)()
        new_tree = transformer.visit(tree)

        # Should remain unchanged
        class_def = new_tree.body[0]
        assert len(class_def.decorator_list) == 0

    def test_add_rules_multiple_decorators(self):
        """Test adding rules when class has multiple decorators."""
        source = """
@other_decorator
@rules(belongs_to('user'))
class Post(Model):
    pass
"""
        tree = ast.parse(source)
        rules = ["has_many('comments')"]
        transformer = add_rules(rules)()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Verify only the @rules decorator is modified
        class_def = new_tree.body[0]
        assert len(class_def.decorator_list) == 2
        rules_decorator = next(d for d in class_def.decorator_list if isinstance(d, ast.Call))
        assert len(rules_decorator.args) == 2  # original 1 + 1 new

    def test_add_rules_empty_list(self):
        """Test adding empty rules list."""
        source = """
@rules(belongs_to('user'))
class Post(Model):
    pass
"""
        tree = ast.parse(source)
        transformer = add_rules([])()
        new_tree = transformer.visit(tree)

        # Should remain unchanged
        class_def = new_tree.body[0]
        rules_decorator = class_def.decorator_list[0]
        assert len(rules_decorator.args) == 1


class TestAddBaseCls:
    """Tests for add_base_cls function."""

    def test_add_base_cls_to_class_without_base(self):
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

    def test_add_base_cls_to_class_with_existing_bases(self):
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

    def test_add_base_cls_already_exists(self):
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

    def test_add_base_cls_multiple_classes(self):
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