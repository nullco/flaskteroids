import pytest
from flaskteroids.actions import ActionParameters
from flaskteroids.exceptions import InvalidParameter, MissingParameter


class TestExpectParameters:

    @pytest.mark.parametrize('raw_input, expect_input', [
        (
            {'user': 'admin', 'password': 'S3cr3t!'},
            ['user', 'password']
        ),
        (
            {
                'user': 'admin',
                'profile': {
                    'first_name': 'Juan',
                    'last_name': 'Perez'
                }
            },
            ['user', ('profile', ['first_name', 'last_name'])]
        ),
        (
            {
                'owner': 'Juan',
                'pets': [{'name': 'rufo', 'type': 'dog'}]
            },
            ['owner', ('pets', [['name', 'type']])]
        ),
        (
            {
                'owner': 'Juan',
                'pets': [{'name': 'rufo', 'type': 'dog', 'toy_ids': [1, 2, 3]}]
            },
            ['owner', ('pets', [['name', 'type', ('toy_ids', [])]])]
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
            [
                'owner',
                ('pets', [
                    ['name', 'type', ('toys', [['name']])]
                ])
            ]
        )
    ])
    def test_ok_parameters(self, raw_input, expect_input):
        params = ActionParameters.new(raw_input)
        output = params.expect(expect_input)
        assert output == raw_input

    @pytest.mark.parametrize('raw_input, expect_input', [
        (
            {'user': 'admin', 'password': 'S3cr3t!'},
            ['user', 'password', 'birthdate']
        )
    ])
    def test_missing_parameters(self, raw_input, expect_input):
        params = ActionParameters.new(raw_input)
        with pytest.raises(MissingParameter):
            params.expect(expect_input)

    @pytest.mark.parametrize('raw_input, expect_input', [
        (
            {'user': 'admin', 'addesses': 'wrong'},
            ['user', ('addesses', [['street', 'house_number']])]
        )
    ])
    def test_invalid_parameters(self, raw_input, expect_input):
        params = ActionParameters.new(raw_input)
        with pytest.raises(InvalidParameter):
            params.expect(expect_input)
