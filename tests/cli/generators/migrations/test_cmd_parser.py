import pytest
from flaskteroids.cli.generators.migrations import cmd_parser


@pytest.mark.parametrize('cmd, expected', [
    (
        'CreateProducts',
        {
            'normalized_cmd': 'create_products',
            'match': {
                'action': 'create_table',
                'captured_groups': ('products',)
            }
        }
    ),
    (
        'AddPriceToProducts',
        {
            'normalized_cmd': 'add_price_to_products',
            'match': {
                'action': 'add_columns_to_table',
                'captured_groups': ('price', 'products')
            }
        }
    ),
    (
        'AddPriceAndTotalToProducts',
        {
            'normalized_cmd': 'add_price_and_total_to_products',
            'match': {
                'action': 'add_columns_to_table',
                'captured_groups': ('price_and_total', 'products')
            }
        }
    )
])
def test_command(cmd, expected):
    res = cmd_parser.parse(cmd)
    assert res['normalized_cmd'] == expected['normalized_cmd']
    assert res['match'] == expected['match']


def test_invalid_command():
    with pytest.raises(Exception):
        cmd_parser.parse('InvalidCommand', *[])
