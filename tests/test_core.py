import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from migration_check.core import scan, load_profile, build_report, MAX_FILE
from migration_check.cli import main, render_html

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def put(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p
    def report(self, private=False):
        return build_report(scan(self.root), load_profile(None), private)
    def test_sdk_checkout_catalog(self):
        self.put('src/pay.ts', "import '@lemonsqueezy/lemonsqueezy.js';\ncreateCheckout();\nprocess.env.LEMONSQUEEZY_VARIANT_ID")
        self.assertEqual({f['rule'] for f in self.report()['findings']}, {'sdk','checkout','catalog'})
    def test_line_number(self):
        self.put('pay.py', '\n\n# order_created')
        self.assertEqual(self.report()['findings'][0]['line'], 3)
    def test_unknown_is_not_ready(self):
        r = self.report()
        self.assertEqual(r['verdict'], 'MANUAL_REVIEW_REQUIRED')
        self.assertTrue(all(t['status']=='unverified' for t in r['tasks']))
    def test_no_secret_excerpt(self):
        self.put('pay.js', 'createCheckout("SUPER_SECRET_SENTINEL")')
        self.assertNotIn('SUPER_SECRET_SENTINEL', json.dumps(self.report()))
    def test_secret_and_dotfile_exclusion(self):
        for p in ['.env', 'secrets.json', 'credentials.ts', '.config/pay.js', 'node_modules/pay.js']:
            self.put(p, 'createCheckout()')
        self.assertEqual(self.report()['findings'], [])
    def test_symlink_file(self):
        p=self.put('real.txt', 'createCheckout()')
        (self.root/'link.js').symlink_to(p)
        self.assertEqual(self.report()['findings'], [])
        self.assertEqual(self.report()['coverage']['symlinks_skipped'], 1)
    def test_symlink_dir(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other,'pay.js').write_text('createCheckout()')
            (self.root/'linked').symlink_to(other, target_is_directory=True)
            self.assertEqual(self.report()['findings'], [])
    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX only')
    def test_fifo_never_blocks(self):
        os.mkfifo(self.root/'pipe.js')
        self.assertEqual(self.report()['coverage']['excluded_entries'], 1)
    def test_oversize(self):
        self.put('big.ts','x'*(MAX_FILE+1))
        self.assertEqual(self.report()['coverage']['oversize_files'], 1)
    def test_invalid_utf8(self):
        (self.root/'bad.js').write_bytes(b'\xffcreateCheckout()')
        self.assertEqual(self.report()['coverage']['non_utf8_files'], 1)
    def test_binary(self):
        (self.root/'bad.js').write_bytes(b'\x00createCheckout()')
        self.assertEqual(self.report()['coverage']['binary_files'], 1)
    def test_budget(self):
        self.put('a.js','createCheckout()'); self.put('b.js','order_created')
        self.assertTrue(scan(self.root,max_files=1)['truncated'])
    def test_bytes_budget(self):
        self.put('a.js','createCheckout()')
        self.assertTrue(scan(self.root,max_bytes=1)['truncated'])
    def test_private_paths(self):
        self.put('person-private/pay.js','createCheckout()')
        r=self.report(True)
        self.assertNotIn('person-private',json.dumps(r))
        self.assertTrue(r['findings'][0]['file'].startswith('file-'))
    def test_html_escape(self):
        self.put('payment.js','createCheckout()')
        report=self.report()
        # Test hostile report labels without creating a Windows-invalid filename.
        report['findings'][0]['file']='<script>alert(1)<script>.js'
        page=render_html(report)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn("default-src 'none'", page)
    def test_empty_report_html_and_syntax_smoke(self):
        import ast
        page=render_html(self.report())
        self.assertIn('<td colspan="4">No candidate identifiers found.',page)
        package=Path(__file__).resolve().parents[1]/'migration_check'
        for source in package.glob('*.py'):
            # Best-effort parser smoke only; real Python 3.10 CI is authoritative.
            ast.parse(source.read_text(encoding='utf-8'),feature_version=(3,10))
    def test_repeated_matches_bounded(self):
        self.put('a.js','createCheckout()\n'*100)
        self.assertEqual(len(self.report()['findings']),1)
    def test_profile_strict(self):
        for obj in [{'email':'private@example.com'},{'licenses':True},{'licenses':'maybe'},[]]:
            p=self.put('profile.json',json.dumps(obj))
            with self.assertRaises(ValueError): load_profile(p)
    def test_profile_status(self):
        p=self.put('profile.json',json.dumps({'paypal_subscriptions':'yes','managed_payments_eligibility':'confirmed'}))
        r=build_report(scan(self.root),load_profile(p))
        self.assertEqual(next(t for t in r['tasks'] if t['id']=='eligibility')['status'],'review')
        self.assertEqual(r['verdict'],'MANUAL_REVIEW_REQUIRED')
    def test_all_bundled_rule_categories(self):
        fixture=Path(__file__).resolve().parents[1]/'examples'/'store'
        r=scan(fixture)
        self.assertEqual({f['rule'] for f in r['findings']},{'sdk','checkout','webhook','license','catalog','affiliate'})
        self.assertEqual(len(r['findings']),6)
    def test_malformed_baseline_privacy(self):
        p=self.put('bad.json',json.dumps({'schema_version':1,'findings':[],'privacy':[]}))
        self.assertEqual(self.invoke('scan',str(self.root),'--baseline',str(p)),2)
    def test_profile_deep_input_fails_cleanly(self):
        p=self.put('bad.json','['*2000+']'*2000)
        self.assertEqual(self.invoke('scan',str(self.root),'--profile',str(p)),2)
    def test_python_sdk(self):
        self.put('payment.py','from lemonsqueezy import Client')
        self.assertEqual(self.report()['findings'][0]['rule'],'sdk')
    def test_baseline_ruleset_change_rejected(self):
        self.put('src/a.js','createCheckout()')
        p=self.root/'baseline.json'
        self.invoke('scan',str(self.root/'src'),'--json',str(p))
        obj=json.loads(p.read_text()); obj['ruleset_fingerprint']='different';p.write_text(json.dumps(obj))
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(p)),2)
    def test_baseline_scope_change_rejected(self):
        self.put('src/a.js','createCheckout()')
        p=self.root/'baseline.json'
        self.invoke('scan',str(self.root/'src'),'--json',str(p))
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(p),'--scope-id','different/root'),2)
    def test_documentation_only_is_not_scanned(self):
        self.put('docs/README.md', '# Synthetic migration notes\ncreateCheckout() order_created validateLicense()')
        result=self.report()
        self.assertEqual(result['findings'],[])
        self.assertEqual(result['coverage']['files_read'],0)
        self.assertEqual(result['coverage']['unsupported_files'],1)
        self.assertEqual(result['verdict'],'MANUAL_REVIEW_REQUIRED')
    def test_no_network_imports(self):
        import ast
        package=Path(__file__).resolve().parents[1]/'migration_check'
        imported=set()
        for p in package.glob('*.py'):
            for n in ast.walk(ast.parse(p.read_text())):
                if isinstance(n,ast.Import): imported.update(a.name.split('.')[0] for a in n.names)
                elif isinstance(n,ast.ImportFrom) and n.module: imported.add(n.module.split('.')[0])
        self.assertFalse(imported & {'requests','http','urllib','socket','subprocess'})
    def invoke(self,*args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(list(args) + (["--scope-id", "fixture/src"] if "--scope-id" not in args else []))
    def test_cli_outputs_and_no_overwrite(self):
        self.put('src/pay.ts','createCheckout()')
        out=self.root/'out.json'; page=self.root/'out.html'
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--json',str(out),'--html',str(page)),0)
        original=out.read_bytes()
        self.assertIn('Migration work queue',page.read_text())
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--json',str(out)),2)
        self.assertEqual(out.read_bytes(),original)
    def test_symlink_output_refused(self):
        target=self.put('target.txt','unchanged'); link=self.root/'report.json';link.symlink_to(target)
        self.assertEqual(self.invoke('scan',str(self.root),'--json',str(link)),2)
        self.assertEqual(target.read_text(),'unchanged')
    def test_ci_new_candidate(self):
        self.put('src/a.js','createCheckout()')
        baseline=self.root/'baseline.json'
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--json',str(baseline)),0)
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(baseline),'--fail-on-new'),0)
        self.put('src/b.js','order_created')
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(baseline),'--fail-on-new'),3)
    def test_ci_line_moves_not_new(self):
        self.put('src/a.js','createCheckout()')
        baseline=self.root/'baseline.json'
        self.invoke('scan',str(self.root/'src'),'--json',str(baseline))
        self.put('src/a.js','\n\ncreateCheckout()')
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(baseline),'--fail-on-new'),0)
    def test_incomplete_exit(self):
        self.put('big.ts','x'*(MAX_FILE+1))
        self.assertEqual(self.invoke('scan',str(self.root)),4)
    def test_bad_baseline(self):
        p=self.put('bad.json','{}')
        self.assertEqual(self.invoke('scan',str(self.root),'--baseline',str(p)),2)
    def test_privacy_baseline_mismatch(self):
        self.put('src/a.js','createCheckout()')
        p=self.root/'baseline.json'
        self.invoke('scan',str(self.root/'src'),'--json',str(p))
        self.assertEqual(self.invoke('scan',str(self.root/'src'),'--baseline',str(p),'--private-paths'),2)

if __name__=='__main__': unittest.main()
