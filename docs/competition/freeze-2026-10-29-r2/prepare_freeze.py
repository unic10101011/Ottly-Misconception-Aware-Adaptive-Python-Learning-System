"""Bind the reviewed repair to source and evidence without publishing credentials."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DOCS=HERE.parent
TAG='acceptance-baseline-2026-10-29-r2'
EVIDENCE_DIRS=['core72-2026-10-29','core72-live-2026-10-29','core72-review-2026-10-29',
               'core72-final-2026-10-29','core72-fixes-2026-10-29','core72-fixes-review-2026-10-29',
               'c54-protection-fix-2026-10-29','c54-protection-review-2026-10-29']


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git_paths(*args):
    return [p for p in subprocess.check_output(['git',*args,'-z'],cwd=ROOT).decode('utf-8').split('\0') if p]


def main():
    assert not (HERE/'source-manifest.json').exists(),'Never overwrite a freeze manifest.'
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    assert branch=='main',branch
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    review=read(DOCS/'c54-protection-review-2026-10-29/human-review-summary.json')
    assert review['eligible_for_repair_freeze_stage'] and review['human_qualified']==11
    state=read(DOCS/'c54-protection-fix-2026-10-29/application-state-final.json')
    for e in state['files']:
        assert sha((ROOT/e['path']).read_bytes().replace(b'\r\n',b'\n'))==e['sha256_lf'],e['path']
    checks=[]
    for directory,manifest,key in [
        ('core72-2026-10-29','design-lock.json','files'),
        ('core72-live-2026-10-29','evidence-manifest.json','files'),
        ('core72-review-2026-10-29','review-manifest.json','immutable_files'),
        ('core72-final-2026-10-29','final-manifest.json','files'),
        ('core72-fixes-2026-10-29','fixes-manifest.json','files'),
        ('core72-fixes-review-2026-10-29','review-manifest.json','files'),
        ('c54-protection-fix-2026-10-29','manifest.json','files'),
        ('c54-protection-review-2026-10-29','review-manifest.json','files')]:
        entries=read(DOCS/directory/manifest)[key]
        for e in entries:assert sha((DOCS/directory/e['path']).read_bytes())==e['sha256'],e['path']
        checks.append({'directory':directory,'locked_files_verified':len(entries)})
    for directory in ['core72-fixes-review-2026-10-29','c54-protection-review-2026-10-29']:
        for e in read(DOCS/directory/'review-manifest.json')['sources']:
            assert sha((DOCS/e['path']).read_bytes())==e['sha256'],e['path']
    before=read(DOCS/'layout-migration-2026-10-28/source-manifest.json')
    frontend=[e for e in before['files'] if e['path'].startswith('frontend/')]
    for e in frontend:
        data=(ROOT/e['path']).read_bytes()
        assert sha(data.replace(b'\r\n',b'\n') if e['text_lf_normalized'] else data)==e['sha256_lf'],e['path']
    all_paths=set(git_paths('ls-files','--cached','--others','--exclude-standard'))
    sources=sorted(p for p in all_paths if p.startswith(('backend/','frontend/')) or '/' not in p)
    assert not any(Path(p).name=='.env' or p.startswith('.cache/') for p in sources)
    text_ext={'.py','.js','.cjs','.jsx','.ts','.tsx','.css','.html','.json','.yaml','.yml','.md','.txt','.lock','.toml','.bat','.ps1','.sh','.example'}
    entries=[]
    for name in sources:
        path=ROOT/name;data=path.read_bytes()
        text_file=path.suffix.lower() in text_ext or b'\0' not in data[:8000]
        entries.append({'path':name,'sha256':sha(data),'sha256_lf':sha(data.replace(b'\r\n',b'\n') if text_file else data),
                        'text_lf_normalized':text_file})
    artifacts=[p for directory in EVIDENCE_DIRS for p in sorted((DOCS/directory).rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.log'}]
    credentials={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line or line.lstrip().startswith('#'):continue
        key,value=line.split('=',1);value=value.strip().strip('"\'')
        if key.strip() in {'DEEPSEEK_API_KEY','JWT_SECRET','DB_PASSWORD','DB_ROOT_PASSWORD'} and len(value)>=8:
            credentials[key.strip()]=value.encode()
    candidates=set(git_paths('diff','--name-only')) | set(git_paths('ls-files','--others','--exclude-standard'))
    leaked=[]
    for name in candidates:
        path=ROOT/name
        if not path.is_file():continue
        data=path.read_bytes()
        leaked.extend({'path':name,'credential_name':key} for key,value in credentials.items() if value in data)
    assert not leaked,json.dumps(leaked,ensure_ascii=False)
    write('source-manifest.json',{'tag':TAG,'previous_tag':'acceptance-baseline-2026-10-29',
          'application_source_digest':state['app_source_digest'],'files':entries,
          'evidence_files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes())} for p in artifacts]})
    write('freeze-checks.json',{'created_at':datetime.now(timezone.utc).isoformat(),'previous_head':head,'branch':'main',
          'tag':TAG,'application_source_files_verified':len(state['files']),'evidence_checks':checks,
          'unchanged_frontend_files_verified':len(frontend),'credential_value_scan_passed':True,
          'credential_types_checked':sorted(credentials),'candidate_files_scanned':len(candidates),
          'software_regression':review['software_regression'],'human_retest':{'AI_qualified':11,'AI_expected':11,'correct_skip':1},
          'all_project_acceptance_complete':False})
    print(json.dumps({'source_files':len(entries),'evidence_files':len(artifacts),'frontend_unchanged':len(frontend),
                      'credential_value_scan_passed':True,'tag':TAG},ensure_ascii=False))


if __name__=='__main__':main()
