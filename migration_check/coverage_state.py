"""Opt-in local scan ledger. Keys and keyed fingerprints never enter public reports."""
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from .comparison import _read, _pairs
from .core import MAX_FILES, RULESET_FINGERPRINT

LIMIT = 4 * 1024 * 1024
NOTE = ('Counts describe successfully assessed UTF-8 files in this bounded scan only. '
        'Not observed again is not deleted, fixed or migrated. Renames appear as new and '
        'not observed again. Equal bytes do not prove equal runtime behavior. Local states '
        'and scope labels are not authenticated; no source or fingerprint is exported here.')

def state_digest(state):
    """Detect accidental edits, not forgery: anyone holding the state can recompute."""
    payload = {key: value for key, value in state.items() if key != 'consistency_sha256'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()

def load(path):
    raw = _read(Path(path))
    if len(raw) > LIMIT:
        raise ValueError('Coverage state exceeds bound')
    obj = json.loads(raw.decode('utf8'), object_pairs_hook=_pairs)
    if not isinstance(obj,dict) or set(obj) != {'version','key','scope','policy','files','incomplete','consistency_sha256'}:
        raise ValueError('Missing or invalid local coverage inventory; old reports are not coverage states')
    if type(obj['incomplete']) is not bool:
        raise ValueError('Invalid coverage completeness')
    if type(obj['version']) is not int or obj['version'] != 2:
        raise ValueError('Unsupported coverage state')
    if not isinstance(obj['key'],str) or not re.fullmatch('[0-9a-f]{64}',obj['key']):
        raise ValueError('Invalid coverage key')
    if not isinstance(obj['scope'],str) or not re.fullmatch('[A-Za-z0-9._/-]{1,100}',obj['scope']):
        raise ValueError('Invalid coverage scope')
    if obj['policy'] != RULESET_FINGERPRINT:
        raise ValueError('Coverage scan policy differs')
    if not isinstance(obj['files'],dict) or len(obj['files']) > MAX_FILES:
        raise ValueError('Invalid coverage inventory')
    for key,value in obj['files'].items():
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key) or not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
            raise ValueError('Invalid coverage record')
    digest = obj['consistency_sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Missing or invalid coverage consistency digest')
    if not hmac.compare_digest(digest, state_digest(obj)):
        raise ValueError('Coverage state consistency mismatch; cannot compare')
    return obj

class Ledger:
    def __init__(self,scope,prior=None):
        if not isinstance(scope,str) or not re.fullmatch('[A-Za-z0-9._/-]{1,100}',scope):
            raise ValueError('Coverage requires a non-sensitive explicit scope ID')
        if prior is not None and prior['scope'] != scope:
            raise ValueError('Coverage scope differs')
        self.prior=prior
        self.state={'version':2,'key':prior['key'] if prior else secrets.token_hex(32),
                    'scope':scope,'policy':RULESET_FINGERPRINT,'files':{},'incomplete':True}

    def observe(self,relative,raw):
        key=bytes.fromhex(self.state['key'])
        name=hmac.new(key,b'path\0'+relative.encode('utf8'),hashlib.sha256).hexdigest()
        value=hmac.new(key,b'content\0'+raw,hashlib.sha256).hexdigest()
        if name in self.state['files'] or len(self.state['files']) >= MAX_FILES:
            raise ValueError('Coverage identity collision or limit')
        self.state['files'][name]=value

    def summary(self):
        current=self.state['files']
        if self.prior is None:
            return {'status':'not_comparable','reason':'No prior local coverage inventory supplied; a legacy baseline report alone cannot establish file coverage.',
                    'current_incomplete':self.state['incomplete'],'assessed_now':len(current),'unchanged':None,'changed':None,'newly_observed':None,'not_observed_again':None,'note':NOTE}
        old=self.prior['files'];both=old.keys() & current.keys()
        unchanged=sum(old[k]==current[k] for k in both)
        return {'status':'compared','baseline_incomplete':self.prior['incomplete'],'current_incomplete':self.state['incomplete'],'assessed_now':len(current),'unchanged':unchanged,
                'changed':len(both)-unchanged,'newly_observed':len(current.keys()-old.keys()),
                'not_observed_again':len(old.keys()-current.keys()),'note':NOTE}

    def serialized(self):
        sealed = dict(self.state, consistency_sha256=state_digest(self.state))
        text=json.dumps(sealed,sort_keys=True,ensure_ascii=True,indent=2)+'\n'
        if len(text.encode('utf8')) > LIMIT:
            raise ValueError('Coverage state exceeds bound')
        return text
