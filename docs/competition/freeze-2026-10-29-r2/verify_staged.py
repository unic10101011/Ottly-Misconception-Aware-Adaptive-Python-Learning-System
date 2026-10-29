"""Check staged bytes so Git newline conversion cannot invalidate old evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    manifest=json.loads((HERE/'source-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        data=subprocess.check_output(['git','show',':'+entry['path']],cwd=ROOT)
        if entry['text_lf_normalized']:data=data.replace(b'\r\n',b'\n')
        assert hashlib.sha256(data).hexdigest()==entry['sha256_lf'],entry['path']
    for entry in manifest['evidence_files']:
        data=subprocess.check_output(['git','show',':'+entry['path']],cwd=ROOT)
        assert hashlib.sha256(data).hexdigest()==entry['sha256'],entry['path']
    paths=[p for p in subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode('utf-8').split('\0') if p]
    assert not any(p=='.env' or p.startswith(('.cache/','frontend/node_modules/')) for p in paths)
    check=subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert check.returncode==0,check.stdout.decode('utf-8')[:1500]
    print(json.dumps({'staged_paths':len(paths),'source_files_verified':len(manifest['files']),
                      'evidence_files_verified':len(manifest['evidence_files']),'whitespace_check_passed':True}))


if __name__=='__main__':main()
