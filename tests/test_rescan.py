import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from migration_check.cli import main, render_html
from migration_check.comparison import compare, _read

class RescanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root/'src'; self.src.mkdir()
        self.base = self.root/'baseline.json'
    def run_scan(self, baseline=False, private=False):
        argv = ['scan',str(self.src),'--scope-id','shop/src']
        if baseline: argv += ['--baseline',str(self.base),'--fail-on-new']
        if private: argv += ['--private-paths']
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): code = main(argv)
        return code, json.loads(out.getvalue()) if out.getvalue() else None, err.getvalue()
    def save(self, private=False):
        code, report, _ = self.run_scan(private=private)
        self.base.write_text(json.dumps(report),encoding='utf-8')
        return code, report
    def put(self,name,text): (self.src/name).write_text(text,encoding='utf-8')
    def test_three_way_and_line_moves(self):
        self.put('stay.js','createCheckout()');self.put('gone.js','order_created')
        self.save();(self.src/'gone.js').unlink();self.put('stay.js','\n\ncreateCheckout()');self.put('new.js','validateLicense()')
        code,r,_=self.run_scan(True);self.assertEqual(code,3)
        c=r['baseline_comparison']
        self.assertEqual([x['file'] for x in c['new']],['new.js'])
        self.assertEqual(c['retained'][0]['line'],3);self.assertEqual(c['retained'][0]['previous_line'],1)
        self.assertEqual(c['not_observed_now'][0]['file'],'gone.js')
        self.assertEqual(r['new_findings'],c['new']); self.assertEqual(r['verdict'],'MANUAL_REVIEW_REQUIRED')
        self.assertIn('not resolved',render_html(r));self.assertIn('Coverage changes',render_html(r))
    def test_rename_is_not_resolution(self):
        self.put('a.js','createCheckout()');self.save();(self.src/'a.js').rename(self.src/'b.js')
        code,r,_=self.run_scan(True);self.assertEqual(code,3)
        self.assertEqual(len(r['baseline_comparison']['not_observed_now']),1)
        self.assertIn('renaming',r['baseline_comparison']['note'])
    def test_binary_cli_real_exit_and_precedence(self):
        self.put('a.js','createCheckout()');self.save()
        (self.src/'a.js').write_bytes('createCheckout()'.encode('utf-16'))
        self.put('new.js','order_created')
        p=subprocess.run([sys.executable,'-m','migration_check','scan',str(self.src),'--scope-id','shop/src','--baseline',str(self.base),'--fail-on-new'],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,4);r=json.loads(p.stdout)
        self.assertEqual(r['coverage']['binary_files'],1)
        self.assertTrue(r['baseline_comparison']['current_incomplete'])
        self.assertEqual(len(r['new_findings']),1)
        self.assertEqual(r['baseline_comparison']['coverage_changes']['binary_files']['delta'],1)
    def test_incomplete_baseline_retained_as_warning(self):
        (self.src/'a.js').write_bytes(b'\x00createCheckout()')
        self.assertEqual(self.save()[0],4)
        self.put('a.js','nothing')
        code,r,_=self.run_scan(True);self.assertEqual(code,0)
        self.assertTrue(r['baseline_comparison']['baseline_incomplete'])
        self.assertFalse(r['baseline_comparison']['current_incomplete'])
    def test_exclusion_increase_is_visible_not_complete_claim(self):
        self.put('a.js','createCheckout()');self.save();(self.src/'a.js').rename(self.src/'secrets.js')
        code,r,_=self.run_scan(True);self.assertEqual(code,0)
        self.assertEqual(r['baseline_comparison']['coverage_changes']['excluded_entries']['delta'],1)
        self.assertEqual(len(r['baseline_comparison']['not_observed_now']),1)
        self.assertEqual(r['verdict'],'MANUAL_REVIEW_REQUIRED')
    def test_private_diff_does_not_restore_filename(self):
        self.put('personal-name.js','createCheckout()');self.save(True);(self.src/'personal-name.js').unlink()
        code,r,_=self.run_scan(True,True);self.assertEqual(code,0)
        self.assertNotIn('personal-name',json.dumps(r)); self.assertNotIn('personal-name',render_html(r))
    def test_private_baseline_raw_path_refused(self):
        self.put('a.js','createCheckout()');_,base=self.save(True)
        base['findings'][0]['file']='PRIVATE_NAME.js';self.base.write_text(json.dumps(base))
        code,r,err=self.run_scan(True,True);self.assertEqual(code,2)
        self.assertNotIn('PRIVATE_NAME',err)
    def test_baseline_extras_never_exported(self):
        self.put('a.js','createCheckout()');_,base=self.save();base['findings'][0]['label']='PRIVATE_SOURCE';base['findings'][0]['secret']='PRIVATE_SOURCE'
        self.base.write_text(json.dumps(base));(self.src/'a.js').unlink()
        code,r,_=self.run_scan(True);self.assertEqual(code,0);self.assertNotIn('PRIVATE_SOURCE',json.dumps(r))
    def test_malformed_nested_shapes_fail_cleanly(self):
        self.put('a.js','createCheckout()');_,base=self.save()
        mutations=[lambda x:x.update(coverage=[]),lambda x:x['coverage'].update(binary_files=True),lambda x:x.update(truncated=0),lambda x:x['privacy'].update(paths_pseudonymized=0),lambda x:x['findings'][0].update(line=True),lambda x:x['findings'][0].update(rule=[]),lambda x:x['findings'].append(x['findings'][0].copy())]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                obj=json.loads(json.dumps(base));mutate(obj);self.base.write_text(json.dumps(obj))
                code,r,err=self.run_scan(True);self.assertEqual(code,2);self.assertIsNone(r);self.assertNotIn(str(self.root),err)
    def test_duplicate_json_rejected(self):
        self.save();self.base.write_text('{"schema_version":1,"schema_version":1}')
        self.assertEqual(self.run_scan(True)[0],2)
    def test_bounded_read(self):
        self.base.write_bytes(b'x'*100)
        with patch('migration_check.comparison.MAX_BASELINE',32):
            with self.assertRaises(ValueError):_read(self.base)
    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO only')
    def test_fifo_baseline_does_not_block(self):
        os.mkfifo(self.base)
        self.assertEqual(self.run_scan(True)[0],2)
    def test_html_escapes_baseline_filename(self):
        self.put('a.js','createCheckout()');_,b=self.save();b['findings'][0]['file']='<script>bad</script>';self.base.write_text(json.dumps(b));(self.src/'a.js').unlink()
        code,r,_=self.run_scan(True);self.assertEqual(code,0);page=render_html(r)
        self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)

if __name__=='__main__':unittest.main()
