"""Delete retired preference rows during account deletion without recreating tables."""
from sqlalchemy import Column, Integer, MetaData, Table, delete, inspect, select


def delete_legacy_preferences(db, user_id: int):
    existing = set(inspect(db.connection()).get_table_names())
    if 'user_settings' not in existing:
        return

    metadata = MetaData()
    settings = Table('user_settings', metadata, Column('id', Integer), Column('user_id', Integer))
    settings_ids = select(settings.c.id).where(settings.c.user_id == user_id)
    for name in ('notification_preferences', 'language_settings'):
        if name in existing:
            children = Table(name, metadata, Column('user_settings_id', Integer))
            db.execute(delete(children).where(children.c.user_settings_id.in_(settings_ids)))
    db.execute(delete(settings).where(settings.c.user_id == user_id))
