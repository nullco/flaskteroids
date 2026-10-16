import importlib
import sys
from textwrap import dedent

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import Session, selectinload

from flaskteroids._models.mapping import discover_models
from flaskteroids.exceptions import ProgrammerError

SCHEMA = """\
import sqlalchemy as sa
from flaskteroids.schema import Snapshot
snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table("authors", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(), nullable=False))
snapshot.create_table("categories", sa.Column("id", sa.Integer(), primary_key=True))
snapshot.create_table("posts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(), nullable=False), sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id"), nullable=False), sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")))
"""
BASE = """\
from flaskteroids.model import Model
class ApplicationModel(Model):
    __abstract__ = True
    def greeting(self):
        return f"Hello, {self.name}"
    @property
    def uppercase_name(self):
        return self.name.upper()
"""
AUTHOR = """\
from .application_model import ApplicationModel
from flaskteroids.model import has_many
from flaskteroids.rules import rules
@rules(has_many("posts", dependent="destroy"))
class Author(ApplicationModel):
    pass
"""
POST = """\
from .application_model import ApplicationModel
from flaskteroids.model import belongs_to
from flaskteroids.rules import rules
@rules(belongs_to("author"))
class Post(ApplicationModel):
    pass
"""


@pytest.fixture
def model_package(discovery_package):
    def create(schema=SCHEMA, author=AUTHOR, post=POST, extra_files=None):
        files = {
            "__init__.py": "",
            "app/models/__init__.py": "",
            "app/models/application_model.py": BASE,
            "app/models/author.py": dedent(author),
            "app/models/post.py": dedent(post),
        }
        if schema is not None:
            files["db/schema.py"] = schema
        files.update(extra_files or {})
        return discovery_package(files)

    return create


def load_models(package):
    return discover_models(f"{package}.app.models")


def test_declarations_and_discovery_do_not_import_snapshot_or_connect(
    model_package, mocker
):
    connect = mocker.patch(
        "sqlalchemy.engine.Engine.connect", side_effect=AssertionError
    )
    package = model_package(schema='raise AssertionError("snapshot loaded too early")')
    models = load_models(package)
    assert list(models) == ["Author", "Post"]
    assert f"{package}.db.schema" not in sys.modules
    assert all("__mapper__" not in vars(model) for model in models.values())
    assert discover_models(f"{package}.app.models") == models
    connect.assert_not_called()


def test_mapping_requires_snapshot_only_when_used(model_package, mocker):
    connect = mocker.patch(
        "sqlalchemy.engine.Engine.connect", side_effect=AssertionError
    )
    package = model_package()
    models = load_models(package)
    author, post = models["Author"], models["Post"]
    assert author.prepare() is author
    assert inspect(author).relationships.posts.mapper.class_ is post
    assert inspect(post).relationships.author.mapper.class_ is author
    assert set(inspect(author).columns.keys()) == {"id", "name"}
    assert {mapper.class_ for mapper in author.registry.mappers} == {author, post}
    assert "categories" in author.metadata.tables
    connect.assert_not_called()


def test_snapshot_location_is_independent_of_cwd_and_importable_db_packages(
    model_package, tmp_path, monkeypatch
):
    from types import ModuleType

    package = model_package(
        extra_files={"app/schema.py": 'raise AssertionError("legacy snapshot loaded")'}
    )
    monkeypatch.setitem(sys.modules, "db", ModuleType("db"))
    monkeypatch.setitem(sys.modules, "db.schema", ModuleType("db.schema"))
    monkeypatch.chdir(tmp_path)
    author = load_models(package)["Author"]
    assert author(name="Ada").name == "Ada"


def test_snapshot_dependency_file_errors_are_not_disguised(model_package):
    models = load_models(
        model_package(schema='open("missing_snapshot_dependency_123")')
    )
    with pytest.raises(FileNotFoundError) as error:
        models["Author"].prepare()
    assert error.value.filename == "missing_snapshot_dependency_123"


def test_native_inspection_and_column_expressions_prepare_lazily(model_package):
    models = load_models(model_package())
    assert "authors.name" in str(models["Author"].name == "Ada")
    assert inspect(models["Post"]).class_ is models["Post"]
    assert "authors" in str(select(models["Author"]))


def test_native_identity_inverse_assignment_and_history(model_package):
    models = load_models(model_package())
    author, post = models["Author"], models["Post"]
    author.prepare()
    engine = create_engine("sqlite://")
    try:
        author.metadata.create_all(engine)
        with Session(engine) as session:
            ada = author(name="Ada").apply_changes()
            first = post(title="First", author=ada).apply_changes()
            assert ada.posts == [first]
            assert ada.greeting() == "Hello, Ada"
            assert ada.uppercase_name == "ADA"
            session.add(first)
            session.flush()
            assert session.get(author, ada.id) is ada
            assert session.scalar(select(post)) is first
            ada.name = "Grace"
            assert not session.is_modified(ada)
            ada.apply_changes()
            assert inspect(ada).attrs.name.history.added == ["Grace"]
            session.flush()
            assert session.scalar(select(author.name)) == "Grace"
    finally:
        engine.dispose()


def test_native_relationship_escape_hatch_and_loading(model_package):
    package = model_package(
        author="""
        from .application_model import ApplicationModel
        from sqlalchemy.orm import relationship
        class Author(ApplicationModel):
            posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
        """,
        post="""
        from .application_model import ApplicationModel
        from sqlalchemy.orm import relationship
        class Post(ApplicationModel):
            author = relationship("Author", back_populates="posts")
        """,
    )
    models = load_models(package)
    author, post = models["Author"], models["Post"]
    assert author.posts is not None
    engine = create_engine("sqlite://")
    queries = []
    event.listen(engine, "before_cursor_execute", lambda *args: queries.append(args[2]))
    try:
        author.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    author(
                        name=str(i), posts=[post(title=str(i)).apply_changes()]
                    ).apply_changes()
                    for i in range(3)
                ]
            )
            session.commit()
        with Session(engine) as session:
            queries.clear()
            authors = session.scalars(
                select(author).options(selectinload(author.posts))
            ).all()
            assert [entry.posts[0].title for entry in authors] == ["0", "1", "2"]
            assert len(queries) == 2
            session.delete(authors[0])
            session.flush()
            assert len(session.scalars(select(post)).all()) == 2
    finally:
        engine.dispose()


def test_abstract_behavior_bases_skip_lookup(model_package):
    package = model_package(
        author="""
    from .application_model import ApplicationModel
    from flaskteroids.model import has_many
    from flaskteroids.rules import rules
    @rules(has_many("posts"))
    class NamedModel(ApplicationModel):
        __abstract__ = True
        def display_name(self):
            return self.name
    class Author(NamedModel):
        pass
    """
    )
    models = load_models(package)
    assert models["Author"](name="Ada").display_name() == "Ada"


@pytest.mark.parametrize("schema", [None, "metadata = None"])
def test_missing_or_invalid_snapshot_does_not_block_import(model_package, schema):
    models = load_models(model_package(schema=schema))
    assert "__mapper__" not in vars(models["Author"])
    with pytest.raises(ProgrammerError, match="snapshot|metadata"):
        models["Author"].prepare()


def test_missing_related_table_fails_before_any_mapper_is_published(model_package):
    package = model_package(
        schema=SCHEMA[: SCHEMA.index('snapshot.create_table("posts"')]
    )
    models = load_models(package)
    with pytest.raises(ProgrammerError, match="Post.*posts.*migrations"):
        models["Author"].prepare()
    assert all("__mapper__" not in vars(model) for model in models.values())


def test_snapshot_import_dependencies_are_not_disguised(model_package):
    models = load_models(model_package(schema="import missing_snapshot_dependency_123"))
    with pytest.raises(ModuleNotFoundError) as error:
        models["Author"].prepare()
    assert error.value.name == "missing_snapshot_dependency_123"


@pytest.mark.parametrize("field", ["greeting", "save", "metadata"])
def test_snapshot_columns_cannot_replace_model_api(model_package, field):
    package = model_package(
        schema=SCHEMA.replace('sa.Column("name",', f'sa.Column("{field}",')
    )
    models = load_models(package)
    with pytest.raises(ProgrammerError, match="conflicts with model API"):
        models["Author"].prepare()


def test_behavior_property_cannot_replace_snapshot_column(model_package):
    models = load_models(
        model_package(
            author=AUTHOR.replace(
                "    pass", "    name = property(lambda self: 'override')"
            )
        )
    )
    with pytest.raises(ProgrammerError, match="Author.name.*conflicts"):
        models["Author"].prepare()


def test_concrete_model_inheritance_is_not_supported_even_before_mapping(model_package):
    author = load_models(model_package())["Author"]
    with pytest.raises(ProgrammerError, match="inherits concrete model"):
        type("SpecialAuthor", (author,), {})


def test_duplicate_names_fail_but_normal_imports_preserve_identity(model_package):
    package = model_package()
    models = load_models(package)
    assert (
        importlib.import_module(f"{package}.app.models.author").Author
        is models["Author"]
    )
    base = importlib.import_module(
        f"{package}.app.models.application_model"
    ).ApplicationModel
    with pytest.raises(ProgrammerError, match="Duplicate model name"):
        type("Author", (base,), {})


def test_shared_classes_can_serve_independent_engines(model_package):
    author = load_models(model_package())["Author"].prepare()
    engines = [create_engine("sqlite://"), create_engine("sqlite://")]
    try:
        for engine, name in zip(engines, ("Ada", "Grace"), strict=True):
            author.metadata.create_all(engine)
            with Session(engine) as session:
                session.add(author(name=name).apply_changes())
                session.commit()
        with Session(engines[0]) as first, Session(engines[1]) as second:
            assert first.get(author, 1).name == "Ada"
            assert second.get(author, 1).name == "Grace"
            assert first.get(author, 1) is not second.get(author, 1)
    finally:
        for engine in engines:
            engine.dispose()


def test_separate_applications_with_same_names_have_isolated_registries(
    discovery_package,
):
    files = {"__init__.py": ""}
    for name in ("first", "second"):
        files.update(
            {
                f"{name}/__init__.py": "",
                f"{name}/db/schema.py": SCHEMA.replace(
                    "sa.String()", f"sa.String({20 if name == 'first' else 40})"
                ),
                f"{name}/app/models/__init__.py": "",
                f"{name}/app/models/application_model.py": BASE,
                f"{name}/app/models/author.py": AUTHOR,
                f"{name}/app/models/post.py": POST,
            }
        )
    package = discovery_package(files)
    first = load_models(f"{package}.first")["Author"].prepare()
    second = load_models(f"{package}.second")["Author"].prepare()
    assert first.registry is not second.registry
    assert first.metadata is not second.metadata
    assert inspect(first).columns.name.type.length == 20
    assert inspect(second).columns.name.type.length == 40
    assert (
        inspect(first).relationships.posts.mapper.class_
        is not inspect(second).relationships.posts.mapper.class_
    )


@pytest.mark.parametrize(
    "declaration",
    [
        "belongs_to('')",
        "has_many('posts', foreign_key='')",
        "has_many('posts', dependent='delete')",
    ],
)
def test_bad_decorator_options_fail_clearly(model_package, declaration):
    package = model_package(
        author=f"""
    from .application_model import ApplicationModel
    from flaskteroids.model import belongs_to, has_many
    from flaskteroids.rules import rules
    @rules({declaration})
    class Author(ApplicationModel): pass
    """
    )
    with pytest.raises(ProgrammerError):
        load_models(package)


def test_bad_association_target_is_a_lazy_configuration_error(model_package):
    models = load_models(
        model_package(
            author=AUTHOR.replace(
                'has_many("posts",', 'has_many("posts", class_name="MissingPost",'
            )
        )
    )
    with pytest.raises(
        ProgrammerError, match="Unknown association target 'MissingPost'"
    ):
        models["Author"].prepare()
    assert "__mapper__" not in vars(models["Author"])


def test_unknown_foreign_key_is_checked_before_mapping(model_package):
    models = load_models(
        model_package(
            author=AUTHOR.replace('dependent="destroy"', 'foreign_key="missing_id"')
        )
    )
    with pytest.raises(ProgrammerError, match="posts.missing_id"):
        models["Author"].prepare()
    assert "__mapper__" not in vars(models["Author"])


def test_concurrent_first_use_publishes_one_mapping(model_package, mocker):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    models = load_models(model_package())
    author = models["Author"]
    barrier = Barrier(4)
    connect = mocker.patch(
        "sqlalchemy.engine.Engine.connect", side_effect=AssertionError
    )

    def prepare(_):
        barrier.wait(timeout=10)
        return author.name, inspect(author)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(prepare, range(4)))
    assert all(
        attribute is results[0][0] and mapper is results[0][1]
        for attribute, mapper in results
    )
    assert len(list(author.registry.mappers)) == 2
    connect.assert_not_called()


def test_has_one_uses_native_inverse_without_discarding_staged_primary_key(
    model_package,
):
    package = model_package(
        schema=SCHEMA
        + '\nsnapshot.create_table("profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id")))\n',
        author=AUTHOR.replace("import has_many", "import has_many, has_one").replace(
            'has_many("posts", dependent="destroy")',
            'has_many("posts", dependent="destroy"), has_one("profile")',
        ),
        extra_files={
            "app/models/profile.py": (
                "from .application_model import ApplicationModel\n"
                "from flaskteroids.model import belongs_to\n"
                "from flaskteroids.rules import rules\n"
                "@rules(belongs_to('author'))\n"
                "class Profile(ApplicationModel): pass\n"
            )
        },
    )
    models = load_models(package)
    author = models["Author"](id=23, name="Ada")
    profile = models["Profile"]()
    author.profile = profile
    assert author.changes["id"] == 23
    assert profile.author is author
    author.apply_changes()
    profile.apply_changes()
    engine = create_engine("sqlite://")
    try:
        author.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(author)
            session.flush()
            assert profile.author_id == author.id == 23
    finally:
        engine.dispose()
