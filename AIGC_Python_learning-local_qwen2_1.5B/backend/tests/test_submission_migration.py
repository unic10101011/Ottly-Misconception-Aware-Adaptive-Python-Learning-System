import os

import pytest
from sqlalchemy import create_engine, text, inspect

from app.core.submission_migration import pending_columns, upgrade, require_current_schema


def check_upgrade(engine):
    # Dedicated test database only. This reproduces an old table with durable learner data.
    with engine.begin() as db:
        db.exec_driver_sql('CREATE TABLE learning_submissions (id INTEGER PRIMARY KEY, problem_id VARCHAR(100), code TEXT)')
        db.execute(text('INSERT INTO learning_submissions (id, problem_id, code) VALUES (1, :problem, :code)'),
                   {'problem':'level2','code':'print(5050)'})
    assert len(pending_columns(engine)) == 4
    with pytest.raises(RuntimeError, match='migration'):
        require_current_schema(engine)
    # Simulate an interrupted MySQL migration; retry must skip the already-added column.
    with engine.begin() as db:
        db.exec_driver_sql('ALTER TABLE learning_submissions ADD COLUMN schema_version VARCHAR(20) NULL')
    assert set(upgrade(engine)) == {'problem_version','difficulty','knowledge_ids'}
    assert upgrade(engine) == []
    require_current_schema(engine)
    with engine.connect() as db:
        row = db.execute(text('SELECT * FROM learning_submissions WHERE id=1')).mappings().one()
        assert row['problem_id'] == 'level2' and row['code'] == 'print(5050)'
        assert all(row[name] is None for name in ('schema_version','problem_version','difficulty','knowledge_ids'))
    assert all(column['nullable'] for column in inspect(engine).get_columns('learning_submissions')
               if column['name'] in {'schema_version','problem_version','difficulty','knowledge_ids'})


def test_old_sqlite_upgrade_is_additive_and_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{(tmp_path / "old.sqlite").as_posix()}')
    check_upgrade(engine)
    engine.dispose()


@pytest.mark.skipif(not os.getenv('CONTRACT_TEST_MYSQL_URL'), reason='dedicated MySQL test database not configured')
def test_old_mysql_upgrade_is_additive_and_idempotent():
    engine = create_engine(os.environ['CONTRACT_TEST_MYSQL_URL'])
    # Never run DDL or cleanup against an ordinary project database.
    assert engine.url.database.startswith('ottly_contract_test_')
    try:
        check_upgrade(engine)
    finally:
        with engine.begin() as db:
            db.exec_driver_sql('DROP TABLE IF EXISTS learning_submissions')
        engine.dispose()
