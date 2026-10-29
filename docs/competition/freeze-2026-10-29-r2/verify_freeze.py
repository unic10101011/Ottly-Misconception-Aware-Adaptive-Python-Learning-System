"""Verify a repair freeze across Git line-ending conversions."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    manifest=json.loads((HERE/'source-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        data=(ROOT/entry['path']).read_bytes()
        if entry['text_lf_normalized']:data=data.replace(b'\r\n',b'\n')
        assert hashlib.sha256(data).hexdigest()==entry['sha256_lf'],entry['path']
    for entry in manifest['evidence_files']:
        assert hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
    runtime=json.loads((HERE/'runtime.json').read_text(encoding='utf-8'))
    assert runtime['app_source_digest']==manifest['application_source_digest']
    assert runtime['key_configured'] and not runtime['acceptance_logging_enabled']
    print(json.dumps({'tag':manifest['tag'],'source_files_verified':len(manifest['files']),
                      'evidence_files_verified':len(manifest['evidence_files']),'runtime_source_matches':True}))


if __name__=='__main__':main()
