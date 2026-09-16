import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flowctl_lib.errors import FlowctlError


class WorktreeReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'app.py').write_text('answer = 42\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        self.controller = self.root / '.ai/issue/ISSUE-2/flow-state.json'
        self.controller.parent.mkdir(parents=True)
        self.controller.write_text('{}')
        self.module = importlib.import_module('flowctl_lib.review_workspace')

    def test_whole_view_contains_unselected_source_and_artifacts_but_not_credentials(self):
        (self.root / 'caller.py').write_text('from app import answer\n')
        (self.controller.parent / 'spec.md').write_text('full artifact')
        (self.root / '.env').write_text('API_KEY=private-value')
        (self.root / 'credentials.json').write_text('{"api_key":"private-value"}')
        view = Path(self.tmp.name) / 'view'
        manifest = self.module.create_review_view(self.root, view, self.controller)
        self.assertEqual('from app import answer\n', (view / 'caller.py').read_text())
        self.assertTrue((view / '.ai/issue/ISSUE-2/spec.md').exists())
        self.assertFalse((view / '.env').exists())
        self.assertFalse((view / 'credentials.json').exists())
        self.assertFalse((view / '.git').exists())
        self.assertNotIn('private-value', json.dumps(manifest))

    def test_snapshot_detects_untracked_and_ai_input_mutation(self):
        artifact = self.controller.parent / 'spec.md'
        artifact.write_text('before')
        before = self.module.capture_review_snapshot(self.root, self.controller)
        artifact.write_text('after')
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            self.module.verify_review_snapshot(self.root, self.controller, before)

    def test_reviewer_configuration_cannot_register_extra_tools(self):
        config = self.root / '.cursor/mcp.json'
        config.parent.mkdir()
        config.write_text('{"mcpServers":{"extra":{"command":"arbitrary"}}}')
        view = Path(self.tmp.name) / 'view'
        manifest = self.module.create_review_view(self.root, view, self.controller)
        self.assertFalse((view / '.cursor/mcp.json').exists())
        self.assertIn({'path':'.cursor/mcp.json','reason':'REVIEWER_CONFIGURATION'}, manifest['excluded'])

    def test_worktree_gitdir_pointer_is_never_copied(self):
        root = Path(self.tmp.name) / 'worktree-fixture'
        root.mkdir()
        (root / '.git').write_text('gitdir: /private/original/repository/.git/worktrees/feature\n')
        (root / 'app.py').write_text('answer = 42\n')
        view = Path(self.tmp.name) / 'view'
        self.module.create_review_view(root, view)
        self.assertFalse((view / '.git').exists())

    def test_exploration_metadata_records_reads_not_arbitrary_output(self):
        from flowctl_lib.reviews import _exploration_evidence
        digest = 'sha256:' + 'a'*64
        data = {'schema_version':1, 'assurance':'LOCAL_READ_TOOLS','calls':[
            {'tool':'read_file','path':'app.py','source_digest':digest,'result_digest':digest,
             'content':'must not persist contents'}]}
        stderr = 'FLOW_REVIEW_EXPLORATION_BEGIN\n' + json.dumps(data) + '\nFLOW_REVIEW_EXPLORATION_END'
        evidence = _exploration_evidence(stderr, {'files':[{'path':'app.py','digest':digest}]})
        self.assertEqual('app.py', evidence['calls'][0]['path'])
        self.assertNotIn('content', evidence['calls'][0])

    def test_credential_literals_are_excluded_but_variable_references_remain(self):
        for text in ('API_KEY = "example-sensitive-key-123456"',
                     'password = "example-sensitive-key-123456"',
                     'access_token: example-sensitive-key-123456'):
            (self.root / 'settings.py').write_text(text)
            with tempfile.TemporaryDirectory() as tmp:
                view = Path(tmp) / 'view'
                self.module.create_review_view(self.root, view, self.controller)
                self.assertFalse((view / 'settings.py').exists())
        (self.root / 'settings.py').write_text('api_key = os.getenv("API_KEY")')
        view = Path(self.tmp.name) / 'safe-view'
        self.module.create_review_view(self.root, view, self.controller)
        self.assertTrue((view / 'settings.py').exists())

    def test_only_exact_controller_bookkeeping_is_excluded(self):
        before = self.module.capture_review_snapshot(self.root, self.controller)
        self.controller.write_text('{"state_revision":9}')
        (self.controller.parent / 'flow-events.jsonl').write_text('event')
        (self.controller.parent / 'reviews').mkdir()
        (self.controller.parent / 'reviews/result.json').write_text('controller output')
        self.module.verify_review_snapshot(self.root, self.controller, before)
        (self.controller.parent / 'unrelated-review.md').write_text('reviewer write')
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            self.module.verify_review_snapshot(self.root, self.controller, before)

    def test_index_and_file_mode_changes_are_detected(self):
        before = self.module.capture_review_snapshot(self.root, self.controller)
        (self.root / 'app.py').chmod(0o755)
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            self.module.verify_review_snapshot(self.root, self.controller, before)

        (self.root / 'app.py').chmod(0o644)
        (self.root / 'app.py').write_text('answer = 43\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'app.py'], check=True)
        (self.root / 'app.py').write_text('answer = 42\n')
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            self.module.verify_review_snapshot(self.root, self.controller, before)

    def test_head_change_is_detected_even_with_identical_source_and_index(self):
        before = self.module.capture_review_snapshot(self.root, self.controller)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c',
            'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'new head'], check=True)
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            self.module.verify_review_snapshot(self.root, self.controller, before)

    def review_fixture(self):
        from importlib import import_module
        tests = import_module('workflow-v2.tests.test_flowctl')
        from flowctl_lib.state import load_state
        helper = tests.ReviewAndHandoffTests()
        state_path = helper._state_with_spec(self.root, authorize=False)
        state = load_state(state_path)
        prompt = self.root / 'prompt.txt'
        prompt.write_text('Review spec_1.md; verify callers independently.')
        return state_path, state, prompt

    def test_package_includes_unselected_source_without_authorization_gate(self):
        from flowctl_lib.review_package import create_review_package
        _, state, prompt = self.review_fixture()
        (self.root / 'caller.py').write_text('from app import answer\n')
        artifact = state['artifacts']['spec:M1']
        package = create_review_package(state, 'ibrain', 'flow-spec', 'spec:M1', prompt, [artifact['path']])
        self.addCleanup(package.cleanup)
        self.assertTrue((package.workspace_path / 'caller.py').exists())
        self.assertEqual('ORGANIZATION_TRUSTED', package.manifest['authorization_basis'])
        self.assertEqual('PENDING', state['authorizations']['external_review']['status'])

    def test_controller_rejects_report_after_worktree_mutation_without_rollback(self):
        from flowctl_lib.reviews import begin_review, submit_review, run_cursor_review
        from flowctl_lib.state import load_state
        state_path, state, prompt = self.review_fixture()
        gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
        report = self.root / 'gpt.json'
        payload = {'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}
        report.write_text(json.dumps(payload))
        done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
        def mutate(*args):
            (self.root / 'app.py').write_text('answer = 99\n')
            return 0, 'FLOW_REVIEW_REPORT_BEGIN\n' + json.dumps(payload) + '\nFLOW_REVIEW_REPORT_END', '', False
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=mutate):
            result = run_cursor_review(state_path, 'spec:M1', prompt, self.root / 'unused.py',
                                       'fake', 'high', 5, done['state_revision'])
        self.assertEqual('REVIEW_WORKTREE_MUTATED', result['failure_reason'])
        self.assertEqual('UNCLASSIFIED', result['classification'])
        self.assertNotIn('report_path', result)
        self.assertEqual('answer = 99\n', (self.root / 'app.py').read_text())
        self.assertNotEqual('PASSED', load_state(state_path)['reviews']['attempts'][result['attempt_id']]['status'])

    def test_accept_rechecks_source_after_report_parsing(self):
        from flowctl_lib import reviews
        state_path, state, prompt = self.review_fixture()
        gpt = reviews.begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
        report = self.root / 'gpt.json'
        payload = {'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}
        report.write_text(json.dumps(payload))
        done = reviews.submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
        extract = reviews._extract_json_report
        def mutate(*args):
            (self.root / 'app.py').write_text('answer = 999\n')
            return extract(*args)
        output = 'FLOW_REVIEW_REPORT_BEGIN\n' + json.dumps(payload) + '\nFLOW_REVIEW_REPORT_END'
        with patch.object(reviews, '_run_bound_package', return_value=(0, output, '', False)), patch.object(reviews, '_extract_json_report', side_effect=mutate):
            result = reviews.run_cursor_review(state_path, 'spec:M1', prompt, self.root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
        self.assertEqual('UNCLASSIFIED', result['classification'])
        self.assertEqual('REVIEW_WORKTREE_MUTATED', result['failure_reason'])

    def test_legacy_ibrain_frame_repairs_do_not_consume_remaining_real_retry(self):
        from flowctl_lib.reviews import begin_review, submit_review, record_process_result, repair_review_attempt
        state_path, state, _ = self.review_fixture()
        gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
        report = self.root / 'gpt.json'
        report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
        current = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
        for _ in range(2):
            attempt = begin_review(state_path, 'cursor', 'flow-spec', 'spec:M1', 'fake', 'high', current['state_revision'])
            current = record_process_result(state_path, attempt['attempt_id'], 2, '', '', True,
                attempt['state_revision'], self.root / 'reviews' / (attempt['attempt_id'] + '.json'))
        attempt = begin_review(state_path, 'ibrain', 'flow-spec', 'spec:M1', 'glm-5.3', 'medium', current['state_revision'])
        current = record_process_result(state_path, attempt['attempt_id'], 2, '', '', True,
            attempt['state_revision'], self.root / 'reviews' / (attempt['attempt_id'] + '.json'))
        old = []
        for _ in range(2):
            attempt = begin_review(state_path, 'ibrain', 'flow-spec', 'spec:M1', 'glm-5.3', 'medium', current['state_revision'])
            current = record_process_result(state_path, attempt['attempt_id'], 2, '', '', False,
                attempt['state_revision'], self.root / 'reviews' / (attempt['attempt_id'] + '.json'),
                forced_classification='UNCLASSIFIED', forced_reason='INVALID_TERMINAL_REVIEW_REPORT')
            old.append((attempt['attempt_id'], current['evidence_digest']))
        for attempt_id, evidence_digest in old:
            current = repair_review_attempt(state_path, attempt_id, 'duplicate_identical_frames', current['state_revision'])
            self.assertFalse(current['eligible'])
            self.assertEqual(evidence_digest, current['evidence_digest'])
        retry = begin_review(state_path, 'ibrain', 'flow-spec', 'spec:M1', 'glm-5.3', 'medium', current['state_revision'])
        self.assertEqual('STARTED', retry['status'])

    def test_mutation_failure_can_record_despite_frozen_code_snapshot_drift(self):
        from flowctl_lib import reviews
        state_path, state, _ = self.review_fixture()
        attempt = reviews.begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
        with patch.object(reviews, '_verify_attempt_snapshot', side_effect=FlowctlError('CODE_SNAPSHOT_DRIFT')) as verify:
            result = reviews.record_process_result(state_path, attempt['attempt_id'], 2, '', '', False,
                attempt['state_revision'], self.root / 'reviews/failure.json',
                forced_classification='UNCLASSIFIED', forced_reason='REVIEW_WORKTREE_MUTATED')
            verify.assert_not_called()
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual('UNCLASSIFIED', result['classification'])
        self.assertTrue(Path(result['evidence_path']).exists())
