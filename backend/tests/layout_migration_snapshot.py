"""Read-only migration evidence. --session output is private and must not be committed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx
from sqlalchemy import inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import engine, SessionLocal
from app.core.auth import create_access_token, auth_fingerprint
from app.models.user import User


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def session_read(token):
    result = {}
    with httpx.Client(base_url='http://frontend', headers={'Authorization': 'Bearer ' + token}, timeout=15) as client:
        for key, path in [('progress', '/api/v1/code/progress'),
                          ('submissions', '/api/v1/code/submissions?limit=20')]:
            response = client.get(path)
            response.raise_for_status()
            body = response.json()
            assert body.get('code') == 200
            result[key] = {'status': response.status_code, 'sha256': digest(body['data'])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', action='store_true', help='Include a private pre-migration synthetic-user token.')
    parser.add_argument('--compare-session-stdin', action='store_true')
    args = parser.parse_args()
    assert engine.url.get_backend_name() == 'mysql', 'This capture expects the existing MySQL application database.'
    tables = {}
    with engine.connect() as connection:
        connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        connection.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
        server_uuid = connection.exec_driver_sql('SELECT @@server_uuid').scalar_one()
        for name in sorted(inspect(connection).get_table_names()):
            quoted = connection.dialect.identifier_preparer.quote(name)
            result = connection.exec_driver_sql('SELECT * FROM ' + quoted)
            columns = list(result.keys())
            rows = sorted(json.dumps(dict(row._mapping), ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), default=str) for row in result)
            tables[name] = {'rows': len(rows), 'columns': columns, 'sha256': digest(rows)}
        connection.rollback()
    state = {'database': engine.url.database, 'server_uuid': server_uuid, 'tables': tables,
             'auth_configuration_sha256': hashlib.sha256(os.environ['JWT_SECRET'].encode()).hexdigest()}
    if args.session:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username.like('dev12_%'), User.status == 'enabled').order_by(User.id.desc()).first()
            assert user is not None, 'A pre-existing synthetic development user is required.'
            token = create_access_token({'sub': str(user.id), 'v': auth_fingerprint(user)})
            user_id = user.id
        state['session'] = {'user_id': user_id, 'token': token, 'reads': session_read(token)}
    if args.compare_session_stdin:
        before = json.load(sys.stdin)
        assert state['database'] == before['database']
        assert state['server_uuid'] == before['server_uuid'], 'The database identity changed.'
        assert state['tables'] == before['tables'], 'Application data changed.'
        assert state['auth_configuration_sha256'] == before['auth_configuration_sha256'], 'The JWT key changed.'
        reads = session_read(before['session']['token'])
        assert reads == before['session']['reads'], 'The original session reads changed.'
        state['inheritance_checks'] = {'same_database_identity': True, 'all_table_contents_identical': True,
                                       'jwt_configuration_unchanged': True, 'original_session_valid': True,
                                       'progress_and_submission_reads_identical': True}
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
