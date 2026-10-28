"""Inspect by default. SQLite apply creates a backup; MySQL requires backup acknowledgement."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from app.core.database import engine
from app.core.submission_migration import pending_columns, upgrade


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-confirmed', action='store_true', help='MySQL only: a verified external backup exists')
    args = parser.parse_args()
    missing = pending_columns(engine)
    if not missing:
        print('No migration needed (fresh database or snapshot columns already present).')
        return
    print('Pending columns: ' + ', '.join(missing))
    if not args.apply:
        print('Inspection only. Run with --apply after checking the database destination.')
        return
    if engine.dialect.name == 'sqlite':
        database = engine.url.database
        if not database or database == ':memory:':
            raise SystemExit('Use a file database for the backed-up migration.')
        source = Path(database).resolve()
        destination = source.with_name(source.name + '.' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.bak')
        with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as original:
            with sqlite3.connect(str(destination)) as backup:
                original.backup(backup)
        print('SQLite backup: ' + str(destination))
    elif engine.dialect.name == 'mysql':
        if not args.backup_confirmed:
            raise SystemExit('Back up and verify MySQL first, then add --backup-confirmed. MySQL DDL is not transactionally reversible.')
    else:
        raise SystemExit('This migration supports SQLite and MySQL only.')
    print('Added columns: ' + ', '.join(upgrade(engine)))
    # Re-running is safe after partial MySQL DDL; only missing columns are added.
    if pending_columns(engine):
        raise SystemExit('Migration verification failed.')
    print('Verified. Existing rows retain null snapshots; no historical metadata was inferred.')


if __name__ == '__main__':
    main()
