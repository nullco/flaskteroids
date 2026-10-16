"""Data-only schema snapshots. Importing a snapshot never connects to a database."""

import sqlalchemy as sa


class Snapshot:
    def __init__(self):
        self.metadata = sa.MetaData()

    def create_table(self, name, *elements, **options):
        return sa.Table(name, self.metadata, *elements, **options)

    def create_index(
        self, name, table_name, columns, *, unique=False, schema=None, **options
    ):
        key = f"{schema}.{table_name}" if schema else table_name
        table = self.metadata.tables[key]
        expressions = [
            table.c[column] if isinstance(column, str) else column for column in columns
        ]
        index = sa.Index(name, *expressions, unique=unique, **options)
        if index.table is None:
            table.append_constraint(index)
        return index
