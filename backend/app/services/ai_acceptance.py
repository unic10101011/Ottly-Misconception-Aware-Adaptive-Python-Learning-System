"""Opt-in developer evidence for a bounded AI acceptance run, never a public response."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
from uuid import uuid4


logger = logging.getLogger(__name__)
_record = ContextVar('ai_acceptance_record', default=None)


def acceptance_event(stage: str, **details):
    record = _record.get()
    if record is not None:
        record['events'].append({'stage': stage, **details})


@contextmanager
def acceptance_record(problem_id: str, feedback_kind: str):
    path = os.getenv('AI_ACCEPTANCE_LOG', '').strip()
    if not path:
        yield
        return
    record = {'record_id': uuid4().hex, 'started_at': datetime.now(timezone.utc).isoformat(),
              'problem_id': problem_id, 'feedback_kind': feedback_kind, 'events': []}
    token = _record.set(record)
    try:
        yield
    finally:
        _record.reset(token)
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        try:
            # Explicit fields only: no HTTP headers, credentials, hidden cases or reasoning_content.
            with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600),
                      'w', encoding='utf-8') as target:
                target.write(json.dumps(record, ensure_ascii=False) + '\n')
        except OSError:
            logger.warning('AI acceptance record could not be written', exc_info=True)
