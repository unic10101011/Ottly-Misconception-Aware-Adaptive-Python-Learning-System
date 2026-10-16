"""Additive migration; deliberately never guesses historical lesson metadata."""
from sqlalchemy import Column, Integer, JSON, String, inspect
from sqlalchemy.schema import CreateColumn

SNAPSHOT_COLUMNS = (
    Column('schema_version', String(20), nullable=True),
    Column('problem_version', Integer, nullable=True),
    Column('difficulty', Integer, nullable=True),
    Column('knowledge_ids', JSON, nullable=True),
)


def pending_columns(engine) -> list[str]:
    inspector = inspect(engine)
    if not inspector.has_table('learning_submissions'):
        return []  # A fresh database is created from current model definitions.
    existing = {column['name'] for column in inspector.get_columns('learning_submissions')}
    return [column.name for column in SNAPSHOT_COLUMNS if column.name not in existing]


def upgrade(engine) -> list[str]:
    missing = pending_columns(engine)
    with engine.begin() as connection:
        for column in SNAPSHOT_COLUMNS:
            if column.name in missing:
                ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                connection.exec_driver_sql(f'ALTER TABLE learning_submissions ADD COLUMN {ddl}')
    return missing


def require_current_schema(engine):
    if pending_columns(engine):
        raise RuntimeError('Learning submission schema needs migration. Back up the database and run: python migrate_submissions.py --apply')
