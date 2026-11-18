import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from migration_check import cli,core
from migration_check.coverage_state import Ledger,load,LIMIT

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.src=self.root/'src';self.src.mkdir()
        # Byte-sensitive fixtures must not undergo platform newline conversion.
        (self.src/'app.py').write_bytes(b'createCheckout()\n')
    def run_scan(self,*args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            rc=cli.main(['scan',str(self.src),*map(str,args)])
        return rc,out.getvalue(),err.getvalue()
    def state(self,name,prior=None,private=False):
        path=self.root/name;args=['--scope-id','synthetic','--coverage-state',path]
        if prior:args+=['--coverage-baseline',prior]
        if private:args+=['--private-paths']
        rc,out,err=self.run_scan(*args);self.assertEqual(rc,0,err)
        return path,json.loads(out)
    def test_full_transitions_and_no_source_export(self):
        (self.src/'same.py').write_text('plain')
        (self.src/'gone.py').write_text('plain')
        first,r=self.state('first');self.assertEqual(r['scan_coverage_comparison']['status'],'not_comparable')
        (self.src/'app.py').write_text('updated')
        (self.src/'gone.py').unlink();(self.src/'added.py').write_text('new')
        second,r=self.state('second',first)
        c=r['scan_coverage_comparison']
        self.assertEqual([c[k] for k in ('changed','unchanged','newly_observed','not_observed_again')],[1,1,1,1])
        self.assertEqual(load(first)['key'],load(second)['key'])
        for value in ('app.py','createCheckout','updated','added.py'):
            self.assertNotIn(value,second.read_text())
    def test_default_has_no_inventory(self):
        rc,out,_=self.run_scan('--private-paths');self.assertEqual(rc,0)
        r=json.loads(out);self.assertEqual(r['scan_coverage_comparison']['status'],'not_comparable')
        self.assertNotIn('files',r);self.assertNotIn('key',r)
    def test_private_and_public_outputs_never_include_state_identifiers(self):
        for private in (False,True):
            p,r=self.state('s'+str(private),private=private)
            text=json.dumps(r)+cli.render_html(r);s=load(p)
            for secret in [s['key'],s['consistency_sha256'],*s['files'],*s['files'].values()]:self.assertNotIn(secret,text)
            if private:self.assertNotIn('app.py',text)
    def test_new_chain_uses_new_key(self):
        a,_=self.state('a');b,_=self.state('b')
        self.assertNotEqual(load(a)['key'],load(b)['key'])
        self.assertNotEqual(load(a)['files'],load(b)['files'])
    def test_old_report_not_silently_inventory(self):
        p=self.root/'old';p.write_text(self.run_scan()[1]);rc,out,err=self.run_scan('--scope-id','synthetic','--coverage-state',self.root/'new','--coverage-baseline',p)
        self.assertEqual(rc,2);self.assertEqual(out,'');self.assertFalse((self.root/'new').exists())
    def test_exclusion_and_binary_are_not_assessed(self):
        p,_=self.state('first');(self.src/'app.py').write_bytes(b'\0')
        ledger=Ledger('synthetic',load(p));r=core.scan(self.src,observed=ledger.observe)
        self.assertEqual(r['coverage']['binary_files'],1)
        self.assertEqual(ledger.summary()['not_observed_again'],1)
        self.assertEqual(ledger.summary()['changed'],0)
        (self.src/'app.py').unlink();(self.src/'.hidden.py').write_text('x')
        ledger=Ledger('synthetic',load(p));core.scan(self.src,observed=ledger.observe)
        self.assertEqual(ledger.summary()['not_observed_again'],1)
    def test_budget_not_observed(self):
        p,_=self.state('old');ledger=Ledger('synthetic',load(p))
        r=core.scan(self.src,max_files=0,observed=ledger.observe)
        self.assertTrue(r['truncated']);self.assertEqual(ledger.summary()['not_observed_again'],1)
    def test_rename_is_not_fix(self):
        p,_=self.state('old');(self.src/'app.py').rename(self.src/'renamed.py')
        _,r=self.state('new',p);c=r['scan_coverage_comparison']
        self.assertEqual(c['newly_observed'],1);self.assertEqual(c['not_observed_again'],1)
        self.assertNotIn('resolved',c)
    def test_bounds_and_malformed_states(self):
        p,_=self.state('old');original=load(p)
        for field,value in [('version',True),('key','bad'),('policy','bad'),('scope','bad space'),('files',{'x':'y'})]:
            s=dict(original);s[field]=value;p.write_text(json.dumps(s))
            with self.assertRaises(ValueError):load(p)
        p.write_text('{"key":"secret-sentinel","key":1}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):load(p)
        p.write_bytes(b' '*(LIMIT+1))
        with self.assertRaises(ValueError):load(p)
    def test_scope_mismatch_and_missing_file(self):
        p,_=self.state('old')
        for prior,scope in ((p,'other'),(self.root/'missing','synthetic')):
            rc,out,_=self.run_scan('--scope-id',scope,'--coverage-state',self.root/'new','--coverage-baseline',prior)
            self.assertEqual(rc,2);self.assertEqual(out,'');self.assertFalse((self.root/'new').exists())
    def test_output_existing_symlink_and_source_location(self):
        p,_=self.state('old');before=p.read_bytes()
        rc,_,_=self.run_scan('--scope-id','synthetic','--coverage-state',p)
        self.assertEqual(rc,2);self.assertEqual(p.read_bytes(),before)
        rc,_,_=self.run_scan('--scope-id','synthetic','--coverage-state',self.src/'state.json')
        self.assertEqual(rc,2);self.assertFalse((self.src/'state.json').exists())
        link=self.root/'link'
        try:link.symlink_to(p)
        except OSError as e:self.skipTest(str(e))
        with self.assertRaises(ValueError):load(link)
    @unittest.skipUnless(os.name=='posix','POSIX mode only; Windows ACL unverified')
    def test_private_mode(self):
        old=os.umask(0o022)
        try:p,_=self.state('private')
        finally:os.umask(old)
        self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
    def test_only_same_bytes_actually_scanned(self):
        ledger=Ledger('synthetic');core.scan(self.src,observed=ledger.observe)
        (self.src/'app.py').write_text('different')
        same=Ledger('synthetic',ledger.state);same.observe('app.py',b'createCheckout()\n')
        self.assertEqual(same.summary()['unchanged'],1)
    def test_real_cli_preserves_crlf_bytes_without_normalizing(self):
        source=self.src/'app.py'
        crlf=b'createCheckout()\r\n'
        source.write_bytes(crlf)
        prior,_=self.state('crlf-prior')
        for index,payload in enumerate((crlf,b'createCheckout()\n')):
            source.write_bytes(payload)
            output=self.root/('crlf-next'+str(index))
            result=subprocess.run([sys.executable,'-m','migration_check','scan',str(self.src),
                '--scope-id','synthetic','--coverage-state',str(output),
                '--coverage-baseline',str(prior)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            comparison=json.loads(result.stdout)['scan_coverage_comparison']
            self.assertEqual(comparison['unchanged'],1 if index==0 else 0)
            self.assertEqual(comparison['changed'],0 if index==0 else 1)
            self.assertEqual(comparison['newly_observed'],0)
            self.assertEqual(comparison['not_observed_again'],0)
            self.assertEqual(source.read_bytes(),payload)
        # Check the actual captured CRLF fingerprint independently of the CLI summary.
        import hashlib
        import hmac
        state=load(prior)
        expected=hmac.new(bytes.fromhex(state['key']),b'content\0'+crlf,hashlib.sha256).hexdigest()
        self.assertEqual(list(state['files'].values()),[expected])

    def test_incomplete_scan_records_and_carries_warning(self):
        p,_=self.state('old')
        (self.src/'app.py').write_bytes(b'\0')
        out=self.root/'partial'
        rc,text,err=self.run_scan('--scope-id','synthetic','--coverage-state',out,'--coverage-baseline',p)
        self.assertEqual(rc,4,err)
        result=json.loads(text)['scan_coverage_comparison']
        self.assertTrue(result['current_incomplete'])
        self.assertEqual(result['not_observed_again'],1)
        self.assertTrue(load(out)['incomplete'])
        (self.src/'app.py').write_text('restored')
        _,r=self.state('restored',out)
        self.assertTrue(r['scan_coverage_comparison']['baseline_incomplete'])
        self.assertEqual(r['scan_coverage_comparison']['newly_observed'],1)

    def test_real_cli_rejects_damaged_state_before_output(self):
        prior,_=self.state('prior')
        original=json.loads(prior.read_text())
        mutations = [('key', '00'*32), ('scope', 'other'), ('policy', '0'*64),
                     ('files', {}), ('incomplete', not original['incomplete']),
                     ('version', 1), ('consistency_sha256', '0'*64)]
        for index,(field,value) in enumerate(mutations):
            altered=dict(original);altered[field]=value
            prior.write_text(json.dumps(altered))
            output=self.root/('next'+str(index))
            report=self.root/('report'+str(index))
            result=subprocess.run([sys.executable,'-m','migration_check','scan',str(self.src),
                '--scope-id','synthetic','--coverage-state',str(output),
                '--coverage-baseline',str(prior),'--json',str(report)],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(result.stdout,'')
            self.assertFalse(output.exists());self.assertFalse(report.exists())
            self.assertNotIn(original['key'],result.stderr)
        altered=dict(original);del altered['consistency_sha256'];altered['version']=1
        prior.write_text(json.dumps(altered))
        with self.assertRaises(ValueError):load(prior)

    def test_consistency_not_authentication_and_json_order_irrelevant(self):
        from migration_check.coverage_state import state_digest
        prior,_=self.state('prior');state=json.loads(prior.read_text())
        state['key']='00'*32
        state['consistency_sha256']=state_digest(state)
        prior.write_text(json.dumps(dict(reversed(list(state.items())))))
        self.assertEqual(load(prior)['key'],'00'*32)

    def test_write_failure_no_stdout_and_no_secret_error(self):
        with patch.object(cli,'write_new',side_effect=OSError('private-sentinel')):
            rc,out,err=self.run_scan('--scope-id','synthetic','--coverage-state',self.root/'new')
        self.assertEqual(rc,2);self.assertEqual(out,'');self.assertNotIn('private-sentinel',err)

if __name__=='__main__':unittest.main()
