import pytest
from flaskteroids.actions import ActionParameters
from flaskteroids.exceptions import InvalidParameter, MissingParameter


class TestExpectParameters:

    @pytest.mark.parametrize('raw_input, expect_input, expect_output', [
        (
            {'user': 'admin', 'password': 'S3cr3t!'},
            (['user', 'password'], {}),
            {'user': 'admin', 'password': 'S3cr3t!'},
        ),
        (
            {
                'user': 'admin',
                'profile': {
                    'first_name': 'Juan',
                    'last_name': 'Perez'
                }
            },
            (['user'], {'profile': ['first_name', 'last_name']}),
            [
                {'user': 'admin'},
                {'first_name': 'Juan', 'last_name': 'Perez'}
            ]
        ),
        (
            {
                'owner': 'Juan',
                'pets': [{'name': 'rufo', 'type': 'dog'}]
            },
            (['owner'], {'pets': [['name', 'type']]}),
            [
                {'owner': 'Juan'},
                [{'name': 'rufo', 'type': 'dog'}]
            ]
        ),
        (
            {
                'owner': 'Juan',
                'pets': [{'name': 'rufo', 'type': 'dog', 'toy_ids': [1, 2, 3]}]
            },
            (['owner'], {'pets': [['name', 'type', ('toy_ids', [])]]}),
            [
                {'owner': 'Juan'},
                [{'name': 'rufo', 'type': 'dog', 'toy_ids': [1, 2, 3]}]
            ]
        ),
        (
            {
                'owner': 'Juan',
                'pets': [
                    {
                        'name': 'rufo',
                        'type': 'dog',
                        'toys': [{'name': 'bone'}, {'name': 'ball'}]
                    },
                    {
                        'name': 'garfield',
                        'type': 'cat',
                        'toys': [{'name': 'mouse'}]
                    }
                ]
            },
            (
                ['owner'],
                {
                    'pets': [
                        ['name', 'type', ('toys', [['name']])]
                    ]
                }
            ),
            [
                {'owner': 'Juan'},
                [
                    {
                        'name': 'rufo',
                        'type': 'dog',
                        'toys': [{'name': 'bone'}, {'name': 'ball'}]
                    },
                    {
                        'name': 'garfield',
                        'type': 'cat',
                        'toys': [{'name': 'mouse'}]
                    }
                ]
            ]
        )
    ])
    def test_ok_parameters(self, raw_input, expect_input, expect_output):
        params = ActionParameters.new(raw_input)
        args, kwargs = expect_input
        output = params.expect(*args, **kwargs)
        assert output == expect_output

    @pytest.mark.parametrize('raw_input, expect_input', [
        (
            {'user': 'admin', 'password': 'S3cr3t!'},
            ['user', 'password', 'birthdate']
        )
    ])
    def test_missing_parameters(self, raw_input, expect_input):
        params = ActionParameters.new(raw_input)
        with pytest.raises(MissingParameter):
            params.expect(*expect_input)

    @pytest.mark.parametrize('raw_input, expect_input', [
        (
            {'user': 'admin', 'addesses': 'wrong'},
            ['user', ('addesses', [['street', 'house_number']])],
        )
    ])
    def test_invalid_parameters(self, raw_input, expect_input):
        params = ActionParameters.new(raw_input)
        with pytest.raises(InvalidParameter):
            params.expect(*expect_input)
