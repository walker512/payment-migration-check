"""Reproducible subprocess comparison; uses only bundled synthetic source.
Run from repository root: python benchmarks/compare.py > benchmarks/results.json
Requires ripgrep on PATH. Does not download or install anything.
"""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from migration_check.core import RULES, RULESET_FINGERPRINT

ROOT=Path(__file__).resolve().parent
CORPUS=ROOT/'corpus'
truth=json.loads((ROOT/'ground-truth.json').read_text())
positives=set(truth['positives'])
negatives=set(truth['negatives'])

def invoke(args):
    p=subprocess.run(args,cwd=CORPUS,text=True,capture_output=True,check=False)
    if p.returncode not in (0,1):
        raise RuntimeError('ripgrep execution failed: '+p.stderr)
    return p.stdout

def metrics(files):
    files=set(files)
    return {'TP':len(files & positives),'FN':len(positives-files),'FP':len(files & negatives),'TN':len(negatives-files),'missed':sorted(positives-files),'false_positives':sorted(files & negatives)}

def rg_rows(output):
    # Fixture names deliberately have no colons; this parser is benchmark-only.
    return [{'file':line.split(':',2)[0].removeprefix('./'),'line':int(line.split(':',2)[1])} for line in output.splitlines() if line]

keyword_cmd=['rg','--no-heading','--line-number','--color','never','-i','lemonsqueezy','.']
keyword=invoke(keyword_cmd)
keyword_rows=rg_rows(keyword)
strong=[]
strong_raw=[]
commands=[]
for rule,label,pattern in RULES:
    command=['rg','--no-heading','--line-number','--only-matching','--color','never','-i','-e',pattern,'.']
    commands.append(command)
    output=invoke(command)
    strong_raw.append(output)
    rows=rg_rows(output)
    first={}
    for row in rows:
        first.setdefault(row['file'],dict(row,rule=rule))
    strong.extend(first.values())
scanner_command=[sys.executable,'-m','migration_check','scan','benchmarks/corpus']
scanner_process=subprocess.run(scanner_command,cwd=ROOT.parent,text=True,capture_output=True,check=False)
if scanner_process.returncode != 0:
    raise RuntimeError('Scanner CLI failed: '+scanner_process.stderr)
ours=json.loads(scanner_process.stdout)
delivery_checks={
    'cli_exit_code':scanner_process.returncode,
    'review_task_count':len(ours['tasks']),
    'all_tasks_have_action_and_basis':all(isinstance(t.get('action'),str) and bool(t['action']) and isinstance(t.get('basis'),str) for t in ours['tasks']),
    'coverage_files_read':ours['coverage']['files_read'],
    'source_excerpts_exported':ours['privacy']['source_excerpts_exported'],
    'verdict':ours['verdict'],
    'synthetic_private_value_in_stdout_or_stderr':'SYNTHETIC_PRIVATE_VALUE' in scanner_process.stdout+scanner_process.stderr,
}
if (delivery_checks['review_task_count'] != 15
    or not delivery_checks['all_tasks_have_action_and_basis']
    or delivery_checks['coverage_files_read'] != 12
    or delivery_checks['source_excerpts_exported']
    or delivery_checks['verdict'] != 'MANUAL_REVIEW_REQUIRED'
    or delivery_checks['synthetic_private_value_in_stdout_or_stderr']):
    raise RuntimeError('Scanner CLI deliverable validation failed: '+json.dumps(delivery_checks))
ours_rows=[{k:f[k] for k in ('file','line','rule')} for f in ours['findings']]
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(CORPUS.iterdir())}
# Locate the pre-fix Python import gap without changing checked-in implementation.
pre_fix=[]
for path in sorted(CORPUS.iterdir()):
    source=path.read_text()
    for rule,label,pattern in RULES:
        if rule=='sdk':
            pattern=pattern.replace(r"\b(?:from|import)\s+lemonsqueezy\b|", "", 1)
        match=re.search(pattern,source,re.I)
        if match:
            pre_fix.append({'file':path.name,'rule':rule,'line':source.count('\n',0,match.start())+1})
result={
 'fixture':'12 synthetic files: 8 positive, 4 negative; file-level confusion matrix',
 'limitations':'Author-labelled fixture corpus, not field accuracy, usability or speed research. Same-rule rg gets the same matching knowledge as this scanner.',
 'ripgrep_version':invoke(['rg','--version']).splitlines()[0],
 'ruleset_fingerprint':RULESET_FINGERPRINT,
 'corpus_sha256':manifest,
 'keyword_rg':{'command':keyword_cmd,'metrics':metrics(r['file'] for r in keyword_rows),'locations':keyword_rows,'synthetic_private_value_in_output':'SYNTHETIC_PRIVATE_VALUE' in keyword},
 'same_rule_rg':{'commands':commands,'metrics':metrics(r['file'] for r in strong),'locations':strong,'synthetic_private_value_in_output':'SYNTHETIC_PRIVATE_VALUE' in '\n'.join(strong_raw)},
 'migration_check':{'command':['python']+scanner_command[1:],'interpreter_resolution':'Executed with sys.executable; absolute environment path omitted for portability','cwd':'repository root','delivery_checks':delivery_checks,'metrics':metrics(r['file'] for r in ours_rows),'locations':ours_rows,'synthetic_private_value_in_output':'SYNTHETIC_PRIVATE_VALUE' in json.dumps(ours)},
 'pre_fix_scanner':{'metrics':metrics(r['file'] for r in pre_fix),'note':'Original scanner missed Python SDK import. Executed with the original regex branch (the added import branch removed); final scanner and same-rule rg include the fix.'},
 'same_rule_location_parity':sorted(str(r) for r in strong)==sorted(str(r) for r in ours_rows),
 'operator_workflow_not_user_test':{
  'scanner':'One scan invocation emits categorized evidence, 15 review tasks, coverage metadata and JSON; add --html for the report in the same invocation. Human review is still mandatory.',
  'keyword_rg':'One invocation yields locations and full source lines; human must categorize matches and construct review tasks.',
  'same_rule_rg':'This reproducible wrapper uses six rg calls and deduplicates per category/file; equivalent matching can be consolidated into one call plus categorization. Add your own policy checklist/report for the same migration deliverable. No timed human-action claim.'}
}
# Compare canonical tuples, independent of dict construction order.
result['same_rule_location_parity']=sorted((r['file'],r['line'],r['rule']) for r in strong)==sorted((r['file'],r['line'],r['rule']) for r in ours_rows)
print(json.dumps(result,indent=2))
