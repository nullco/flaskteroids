import pytest

from flaskteroids.actions import Parameters
from flaskteroids.exceptions import InvalidParameter, MissingParameter


class TestExpectParameters:
    @pytest.mark.parametrize(
        "attributes, expected",
        [
            ({"completed": True}, {"completed": True}),
            ({"completed": False}, {"completed": False}),
            ({"title": "Task"}, {"title": "Task"}),
            ({"title": None}, {"title": None}),
            ({"title": ""}, {"title": ""}),
            ({"completed": True, "admin": True}, {"completed": True}),
        ],
    )
    def test_nested_fields_are_optional(self, attributes, expected):
        params = Parameters.new({"todo": attributes})

        assert params.expect(todo=["title", "completed"]) == expected
        assert params["todo"] == attributes

    @pytest.mark.parametrize(
        "attributes, expected",
        [
            ({"title": "Task"}, {"title": "Task"}),
            (
                {"profile": {"name": "Alice", "admin": True}},
                {"profile": {"name": "Alice"}},
            ),
            ({"profile": {}}, {"profile": {}}),
            ({"tags": []}, {"tags": []}),
            (
                {"items": [{"name": "One"}, {"completed": False}, {}]},
                {"items": [{"name": "One"}, {"completed": False}, {}]},
            ),
            (
                {"items": [{"details": {"name": "One"}}]},
                {"items": [{"details": {"name": "One"}}]},
            ),
        ],
    )
    def test_optional_fields_are_filtered_recursively(self, attributes, expected):
        params = Parameters.new({"todo": attributes})

        assert (
            params.expect(
                todo=[
                    "title",
                    ("profile", ["name", "email"]),
                    ("tags", []),
                    ("items", [["name", "completed", ("details", ["name", "size"])]]),
                ]
            )
            == expected
        )

    @pytest.mark.parametrize(
        "raw_input", [{}, {"todo": None}, {"todo": {}}, {"todo": {"admin": True}}]
    )
    def test_expect_requires_dictionary_root_after_filtering(self, raw_input):
        params = Parameters.new(raw_input)

        with pytest.raises(MissingParameter):
            params.expect(todo=["title", "completed"])

    @pytest.mark.parametrize("value", [None, "", " \t\n"])
    def test_blank_required_scalars_are_rejected(self, value):
        params = Parameters.new({"title": value})

        with pytest.raises(MissingParameter):
            params.expect("title")

    @pytest.mark.parametrize("value", [False, True, 0, 0.0, "Task"])
    def test_nonblank_required_scalars_keep_dictionary_return_shape(self, value):
        params = Parameters.new({"title": value})

        assert params.expect("title") == {"title": value}

    @pytest.mark.parametrize("schema", [[], [["name"]]])
    def test_empty_required_arrays_are_rejected(self, schema):
        params = Parameters.new({"items": []})

        with pytest.raises(MissingParameter):
            params.expect(items=schema)

    def test_multiple_roots_keep_return_shape_with_partial_attributes(self):
        params = Parameters.new(
            {"owner": "Alice", "todo": {"completed": True}, "profile": {"name": "A"}}
        )

        assert params.expect(
            "owner", todo=["title", "completed"], profile=["name", "email"]
        ) == [{"owner": "Alice"}, {"completed": True}, {"name": "A"}]

    def test_each_requested_root_is_required(self):
        params = Parameters.new({"todo": {"completed": True}})

        with pytest.raises(MissingParameter):
            params.expect(todo=["title", "completed"], profile=["name"])

    def test_positional_dictionary_schema_also_permits_partial_attributes(self):
        params = Parameters.new({"todo": {"completed": True}})

        assert params.expect(("todo", ["title", "completed"])) == {
            "todo": {"completed": True}
        }

    @pytest.mark.parametrize("value", ["wrong", [], False, 0])
    def test_wrong_shaped_dictionary_roots_are_rejected(self, value):
        params = Parameters.new({"todo": value})

        with pytest.raises(InvalidParameter):
            params.expect(todo=["title"])

    @pytest.mark.parametrize(
        "attributes",
        [
            {"title": {}},
            {"profile": "wrong"},
            {"tags": "wrong"},
            {"tags": [{}]},
            {"items": {}},
            {"items": ["wrong"]},
            {"items": [{"name": []}]},
        ],
    )
    def test_expect_rejects_invalid_supplied_nested_fields(self, attributes):
        params = Parameters.new({"todo": attributes})

        with pytest.raises(InvalidParameter):
            params.expect(
                todo=[
                    "title",
                    ("profile", ["name"]),
                    ("tags", []),
                    ("items", [["name"]]),
                ]
            )

    def test_file_upload_is_a_permitted_scalar(self):
        from io import BytesIO

        from werkzeug.datastructures import FileStorage

        upload = FileStorage(BytesIO(b"file"), filename="file.txt")
        params = Parameters.new({"user": {"avatar": upload, "files": [upload]}})
        assert params.expect(user=["avatar", ("files", [])]) == {
            "avatar": upload,
            "files": [upload],
        }

    def test_expect_rejects_arbitrary_objects_as_uploads(self):
        params = Parameters.new({"user": {"avatar": object()}})
        with pytest.raises(InvalidParameter):
            params.expect(user=["avatar"])

    @pytest.mark.parametrize(
        "raw_input, expect_input, expect_output",
        [
            (
                {"user": "admin", "password": "S3cr3t!"},
                (["user", "password"], {}),
                {"user": "admin", "password": "S3cr3t!"},
            ),
            (
                {
                    "user": "admin",
                    "profile": {"first_name": "Juan", "last_name": "Perez"},
                },
                (["user"], {"profile": ["first_name", "last_name"]}),
                [{"user": "admin"}, {"first_name": "Juan", "last_name": "Perez"}],
            ),
            (
                {"owner": "Juan", "pets": [{"name": "rufo", "type": "dog"}]},
                (["owner"], {"pets": [["name", "type"]]}),
                [{"owner": "Juan"}, [{"name": "rufo", "type": "dog"}]],
            ),
            (
                {
                    "owner": "Juan",
                    "pets": [{"name": "rufo", "type": "dog", "toy_ids": [1, 2, 3]}],
                },
                (["owner"], {"pets": [["name", "type", ("toy_ids", [])]]}),
                [
                    {"owner": "Juan"},
                    [{"name": "rufo", "type": "dog", "toy_ids": [1, 2, 3]}],
                ],
            ),
            (
                {
                    "owner": "Juan",
                    "pets": [
                        {
                            "name": "rufo",
                            "type": "dog",
                            "toys": [{"name": "bone"}, {"name": "ball"}],
                        },
                        {
                            "name": "garfield",
                            "type": "cat",
                            "toys": [{"name": "mouse"}],
                        },
                    ],
                },
                (["owner"], {"pets": [["name", "type", ("toys", [["name"]])]]}),
                [
                    {"owner": "Juan"},
                    [
                        {
                            "name": "rufo",
                            "type": "dog",
                            "toys": [{"name": "bone"}, {"name": "ball"}],
                        },
                        {
                            "name": "garfield",
                            "type": "cat",
                            "toys": [{"name": "mouse"}],
                        },
                    ],
                ],
            ),
        ],
    )
    def test_expect_returns_permitted_parameters_in_schema_shape(
        self, raw_input, expect_input, expect_output
    ):
        params = Parameters.new(raw_input)
        args, kwargs = expect_input
        output = params.expect(*args, **kwargs)
        assert output == expect_output

    @pytest.mark.parametrize(
        "raw_input, expect_input",
        [({"user": "admin", "password": "S3cr3t!"}, ["user", "password", "birthdate"])],
    )
    def test_expect_rejects_missing_requested_scalar(self, raw_input, expect_input):
        params = Parameters.new(raw_input)
        with pytest.raises(MissingParameter):
            params.expect(*expect_input)

    @pytest.mark.parametrize(
        "raw_input, expect_input",
        [
            (
                {"user": "admin", "addesses": "wrong"},
                ["user", ("addesses", [["street", "house_number"]])],
            )
        ],
    )
    def test_expect_rejects_invalid_positional_nested_parameters(
        self, raw_input, expect_input
    ):
        params = Parameters.new(raw_input)
        with pytest.raises(InvalidParameter):
            params.expect(*expect_input)
