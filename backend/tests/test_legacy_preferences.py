"""Retired preferences stay absent on new databases and obey account deletion transactions."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.legacy_preferences import delete_legacy_preferences


def test_fresh_database_cleanup_does_not_create_retired_tables():
    engine = create_engine('sqlite://')
    with Session(engine) as db:
        delete_legacy_preferences(db, 1)
        assert inspect(db.connection()).get_table_names() == []
    engine.dispose()


def test_cleanup_handles_partial_legacy_schema_and_can_be_rolled_back():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE user_settings (id INTEGER PRIMARY KEY, user_id INTEGER)'))
        connection.execute(text('CREATE TABLE language_settings (user_settings_id INTEGER)'))
        connection.execute(text('INSERT INTO user_settings VALUES (10, 1), (20, 2)'))
        connection.execute(text('INSERT INTO language_settings VALUES (10), (20)'))
    with Session(engine) as db:
        delete_legacy_preferences(db, 1)
        assert db.execute(text('SELECT user_id FROM user_settings')).scalars().all() == [2]
        assert db.execute(text('SELECT user_settings_id FROM language_settings')).scalars().all() == [20]
        db.rollback()
        assert db.execute(text('SELECT COUNT(*) FROM user_settings')).scalar() == 2
        assert db.execute(text('SELECT COUNT(*) FROM language_settings')).scalar() == 2
    engine.dispose()
