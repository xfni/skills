import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flowctl_lib.authorizations import default_authorizations
from flowctl_lib.errors import FlowctlError


class ReviewPackageTests(unittest.TestCase):
    def test_package_round1_quoted_credentials_are_rejected(self):
        for value in ('{"api_key":"lure"}', '{"password":"lure"}', 'token=lure',
                      "'authorization': 'lure'", 'secret: lure'):
            self.prompt.write_text(value)
            with self.subTest(value=value), self.assertRaises(FlowctlError):
                self.package()

    def test_package_round1_untrusted_adapter_never_executes(self):
        from flowctl_lib.reviews import _run_bound_package
        package = self.package()
        self.addCleanup(package.cleanup)
        runner = self.root / 'liar.py'
        runner.write_text('print("untrusted")')
        with patch('flowctl_lib.reviews.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{"workspace_exploration":true,"write_tools":false}', '')) as run:
            result = _run_bound_package(package, runner, 'ibrain', 'fake', 'high', 5)
        self.assertEqual(result[0], 2)
        run.assert_not_called()

    def test_package_round1_pins_backend_and_executes_captured_adapter(self):
        from flowctl_lib.reviews import _run_bound_package
        package = self.package()
        self.addCleanup(package.cleanup)
        official = ROOT.parent / 'skills/ibrain-review/scripts/ibrain_review.py'
        source = official.read_text()
        relocated = self.root / 'adapter.py'
        relocated.write_text(source)
        with patch('flowctl_lib.reviews.subprocess.run') as run:
            rejected = _run_bound_package(package, relocated, 'cursor', 'fake', 'high', 5)
        self.assertEqual(rejected[0], 2)
        run.assert_not_called()
        def execute(command, **kwargs):
            self.assertEqual(command[:3], [sys.executable, '-I', '-c'])
            self.assertEqual(command[3], source)
            if '--check-capabilities' in command:
                relocated.write_text('raise RuntimeError("substituted")')
                return subprocess.CompletedProcess([], 0, '{"workspace_exploration":true,"write_tools":false}', '')
            self.assertEqual(command[command.index('--expected-request-digest') + 1], package.digest)
            return subprocess.CompletedProcess([], 0, '', '')
        with patch('flowctl_lib.reviews.subprocess.run', side_effect=execute) as run:
            self.assertEqual(_run_bound_package(package, relocated, 'ibrain', 'fake', 'high', 5)[0], 0)
        self.assertEqual(run.call_count, 2)

    def test_package_round1_replacement_at_launch_has_zero_sends(self):
        from flowctl_lib.reviews import _run_bound_package
        package = self.package()
        self.addCleanup(package.cleanup)
        official = ROOT.parent / 'skills/ibrain-review/scripts/ibrain_review.py'
        spec = importlib.util.spec_from_file_location('launch_race_adapter', official)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def execute(command, **kwargs):
            if '--check-capabilities' in command:
                return subprocess.CompletedProcess([], 0, '{"workspace_exploration":true,"write_tools":false}', '')
            package.request_path.chmod(0o600)
            package.request_path.write_text(package.request_path.read_text().replace('Review spec.md', 'LURE_REPLACEMENT'))
            args = SimpleNamespace(request_file=command[4], no_tools=True, model='glm-5.3', timeout_seconds=5,
                                   expected_request_digest=command[command.index('--expected-request-digest') + 1])
            return subprocess.CompletedProcess([], module.run_review(args, 'key'), '', '')
        with patch.object(module, 'request_json') as send, patch('flowctl_lib.reviews.subprocess.run', side_effect=execute):
            result = _run_bound_package(package, official, 'ibrain', 'fake', 'high', 5)
        self.assertEqual(result[0], 2)
        send.assert_not_called()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        from importlib import import_module
        write_artifact = import_module('workflow-v2.tests.test_flowctl').write_artifact
        self.file, ref = write_artifact(self.root, 'spec', issue='ISSUE-2', milestone='M1', name='spec.md')
        self.prompt = self.root / 'prompt.txt'
        self.prompt.write_text('Review spec.md')
        self.state = dict(issue_id='ISSUE-2', run_id='run-2', worktree_path=str(self.root),
                          current_stage='flow-spec', artifacts={'spec:M1': {'path':str(self.file), 'digest':ref['digest'], 'type':'spec'}},
                          authorizations=default_authorizations())
        self.state['authorizations']['external_review'].update(status='GRANTED', revision=1,
            authorization_id='auth-1', issue_id='ISSUE-2', run_id='run-2', worktree_path=str(self.root))

    def package(self, paths=None):
        from flowctl_lib import review_package
        return review_package.create_review_package(self.state, 'cursor', 'flow-spec', 'spec:M1',
                                                   self.prompt, paths or [self.file])

    def test_package_api_exists(self):
        self.assertTrue((ROOT / 'flowctl_lib/review_package.py').exists())

    def test_package_exact_outbound_bytes_and_cleanup(self):
        lure = self.root / 'lure.txt'
        lure.write_text('DO NOT TRANSMIT LURE')
        package = self.package()
        self.addCleanup(package.cleanup)
        request = json.loads(package.request_path.read_text())
        self.assertEqual(request['prompt'], self.prompt.read_text())
        self.assertIn('lure.txt', {item['path'] for item in request['files']})
        self.assertEqual((package.workspace_path / 'spec.md').read_text(), self.file.read_text())
        self.assertEqual((package.workspace_path / 'lure.txt').read_text(), lure.read_text())
        self.assertEqual(request['capabilities'], {'workspace_exploration':True, 'write_tools':False})
        self.assertNotIn(str(self.root), package.request_path.read_text())
        self.assertNotIn(lure.read_text(), package.request_path.read_text())
        package.verify()
        package.cleanup()
        self.assertFalse(package.root.exists())

    def test_package_rejects_undeclared_escape_and_sensitive_prompt(self):
        lure = self.root / 'lure.txt'
        lure.write_text('outside approved artifact chain')
        link = self.root / 'link.md'
        link.symlink_to(self.file)
        for paths in (['../lure'], ['/etc/passwd']):
            with self.subTest(paths=paths), self.assertRaises(FlowctlError):
                self.package(paths)
        for prompt in ('api_key=secret-value',):
            self.prompt.write_text(prompt)
            with self.subTest(prompt=prompt), self.assertRaises(FlowctlError):
                self.package()

    def test_package_mutation_and_single_use_binding(self):
        from flowctl_lib.review_package import bind_package, consume_binding
        package = self.package()
        self.addCleanup(package.cleanup)
        binding = bind_package(self.state, package)
        consume_binding(self.state, package, binding['binding_id'])
        with self.assertRaises(FlowctlError):
            consume_binding(self.state, package, binding['binding_id'])
        package.request_path.chmod(0o600)
        package.request_path.write_text('{}')
        with self.assertRaises(FlowctlError):
            package.verify()

    def test_package_capability_check_fails_closed(self):
        from flowctl_lib.review_package import validate_capabilities
        for capabilities in ({}, {'local_tools':True,'implicit_indexing':False},
                             {'local_tools':False,'implicit_indexing':True}):
            with self.assertRaises(FlowctlError):
                validate_capabilities(capabilities)
        validate_capabilities({'workspace_exploration':True, 'write_tools':False})

    def test_package_source_drift_is_rejected(self):
        import hashlib
        self.state['artifacts']['spec:M1']['digest'] = 'sha256:' + hashlib.sha256(b'original').hexdigest()
        with self.assertRaises(FlowctlError):
            self.package()

    def test_package_invalid_registered_digest_is_rejected(self):
        self.state['artifacts']['spec:M1']['digest'] = 'invalid'
        with self.assertRaises(FlowctlError):
            self.package()

    def test_package_never_leaks_worktree_location_inside_file(self):
        self.file.write_text(self.file.read_text().replace('confirmer: ORCHESTRATED', 'confirmer: ORCHESTRATED\nworkspace=' + str(self.root)))
        package = self.package()
        self.addCleanup(package.cleanup)
        self.assertNotIn(str(self.root), package.request_path.read_text())
        self.assertIn(str(self.root), (package.workspace_path / 'spec.md').read_text())

    def test_package_validated_manifest_has_fresh_binding_for_fallback(self):
        from flowctl_lib.review_package import bind_package
        cursor = self.package()
        self.addCleanup(cursor.cleanup)
        first = bind_package(self.state, cursor)
        from flowctl_lib.review_package import create_review_package
        fallback = create_review_package(self.state, 'ibrain', 'flow-spec', 'spec:M1', self.prompt, [self.file])
        self.addCleanup(fallback.cleanup)
        second = bind_package(self.state, fallback)
        self.assertNotEqual(first['binding_id'], second['binding_id'])
        self.assertNotEqual(first['package_digest'], second['package_digest'])

    def test_package_rejects_stage_outside_persisted_authorization_scope(self):
        from flowctl_lib.review_package import create_review_package
        self.state['current_stage'] = 'flow-plan'
        self.state['authorizations']['external_review']['allowed_stages'] = ['flow-spec']
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_ARTIFACT_STAGE_MISMATCH'):
            create_review_package(
                self.state, 'cursor', 'flow-plan', 'spec:M1', self.prompt, [self.file]
            )

    def test_package_cli_exposes_validate(self):
        from flowctl_lib.cli import _parser
        parser = _parser()
        self.assertIn('validate', parser._subparsers._group_actions[0].choices['authorization']._subparsers._group_actions[0].choices)

    def test_package_dangerous_capabilities_prevent_egress(self):
        from flowctl_lib.reviews import _run_bound_package
        package = self.package()
        self.addCleanup(package.cleanup)
        for key in ('workspace_exploration', 'write_tools'):
            capabilities = {'workspace_exploration':True,'write_tools':False}
            capabilities[key] = not capabilities[key]
            with patch('flowctl_lib.reviews.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(capabilities), '')) as run:
                result = _run_bound_package(package, ROOT.parent / 'skills/cursor-review/scripts/cursor_review.py', 'cursor', 'fake', 'high', 5)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-1], '--check-capabilities')
            self.assertNotIn(str(package.request_path), run.call_args.args[0])
            self.assertEqual(result[0], 2)

    def test_package_added_file_and_stale_authorization_fail_closed(self):
        from flowctl_lib.review_package import bind_package, consume_binding
        package = self.package()
        self.addCleanup(package.cleanup)
        binding = bind_package(self.state, package)
        self.state['authorizations']['external_review']['revision'] += 1
        consume_binding(self.state, package, binding['binding_id'])
        package.root.chmod(0o700)
        (package.root / 'lure').write_text('undeclared')
        with self.assertRaises(FlowctlError):
            package.verify()


class ReviewRunnerTests(unittest.TestCase):
    def test_review_round1_replaced_request_is_never_sent(self):
        module = self.load_runner('ibrain')
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp).resolve() / 'request.json'
            raw = json.dumps({'schema_version':1, 'prompt':'approved', 'files':[],
                             'manifest':{}, 'capabilities':{'workspace_exploration':True,'write_tools':False}}).encode()
            request.write_bytes(raw)
            expected = 'sha256:' + hashlib.sha256(raw).hexdigest()
            request.write_bytes(raw.replace(b'approved', b'REPLACED_LURE'))
            args = SimpleNamespace(request_file=str(request), expected_request_digest=expected,
                                   no_tools=True, model='glm-5.3', timeout_seconds=10)
            with patch.object(module, 'request_json', return_value={'status':'completed','output_text':'report'}) as send:
                self.assertEqual(module.run_review(args, 'key'), 2)
                send.assert_not_called()

    def load_runner(self, backend):
        path = ROOT.parent / 'skills' / (backend + '-review') / 'scripts' / (backend + '_review.py')
        spec = importlib.util.spec_from_file_location(backend + '_review_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_review_ibrain_capabilities_are_zero_tools(self):
        module = self.load_runner('ibrain')
        self.assertTrue(hasattr(module, 'capabilities'))
        self.assertEqual(module.capabilities(), {'workspace_exploration':True, 'write_tools':False})

    def test_review_ibrain_sends_exact_materialized_request(self):
        module = self.load_runner('ibrain')
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp).resolve() / 'request.json'
            request.write_text(json.dumps({'schema_version':2,'prompt':'review','files':[],
                                          'manifest':{'artifact_digest':'sha256:' + 'a'*64},'capabilities':{'workspace_exploration':True,'write_tools':False}}))
            args = SimpleNamespace(request_file=str(request), workspace=str(request.parent), model='glm-5.3', timeout_seconds=10,
                                   expected_request_digest='sha256:' + hashlib.sha256(request.read_bytes()).hexdigest())
            with patch.object(module, 'request_json', return_value={'status':'completed','output_text':'report'}) as send:
                self.assertEqual(module.run_review(args, 'key'), 0)
                self.assertEqual(send.call_args.kwargs['payload']['model'], 'glm-5.3')
                self.assertEqual({tool['name'] for tool in send.call_args.kwargs['payload']['tools']}, {'list_files','read_file','search'})

    def test_review_cursor_cannot_claim_unproven_capabilities(self):
        runner = ROOT.parent / 'skills/cursor-review/scripts/cursor_review.py'
        result = subprocess.run([sys.executable, str(runner), '--check-capabilities'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {'workspace_exploration':True,'write_tools':False})


if __name__ == '__main__':
    unittest.main()
