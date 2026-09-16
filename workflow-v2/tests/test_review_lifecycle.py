"""Regression paths for draft registration, lane repair and resumability."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_flowctl as fixtures
from flowctl_lib.artifacts import read_artifact
from flowctl_lib.errors import FlowctlError
from flowctl_lib.handoff import accept_handoff
from flowctl_lib.resume import resume_flow, reconcile_resume
from flowctl_lib.reviews import begin_review, submit_review, record_process_result, run_cursor_review, has_passed_review
from flowctl_lib.snapshot import record_snapshot
from flowctl_lib.state import load_state, commit_state, register_artifact


class ReviewLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        original = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)
        self.state_path = self.root / '.ai/issue/BCS-710/flow-state.json'
        self.state_path.parent.mkdir(parents=True)
        original.rename(self.state_path)
        original.with_name('flow-events.jsonl').rename(self.state_path.with_name('flow-events.jsonl'))
        state = load_state(self.state_path)
        commit_state(self.state_path, state, 'TEST_CONTROLLER_LOCATION', {})
        self.index = 0

    def state(self):
        return load_state(self.state_path)

    def review(self, backend, status='PASSED', findings=None, kind='spec'):
        state = self.state()
        attempt = begin_review(self.state_path, backend, 'flow-' + kind, kind + ':M1',
            'glm-5.3' if backend == 'ibrain' else 'gpt-6-astra', 'medium', state['state_revision'])
        self.index += 1
        report = self.state_path.parent / f'report-{self.index}.json'
        report.write_text(json.dumps(dict(status=status, findings=findings or [], reviewed_digest=attempt['artifact_digest'])))
        return submit_review(self.state_path, attempt['attempt_id'], report, attempt['state_revision'],
                             controller_executed=backend in {'cursor', 'ibrain'})

    def failure(self, backend):
        state = self.state()
        attempt = begin_review(self.state_path, backend, 'flow-spec', 'spec:M1',
            'glm-5.3' if backend == 'ibrain' else 'gpt-6-astra', 'medium', state['state_revision'])
        self.index += 1
        return record_process_result(self.state_path, attempt['attempt_id'], 2, '', '', False,
            attempt['state_revision'], self.state_path.parent / f'error-{self.index}.json')

    def resume(self, only_spec=False):
        state = self.state()
        paths = {key: item['path'] for key, item in state['artifacts'].items()
                 if not only_spec or key == 'spec:M1'}
        inputs = self.state_path.parent / 'inputs.json'
        inputs.write_text(json.dumps(paths))
        discovery = resume_flow(state['issue_id'], self.root, inputs, controller=state)
        return reconcile_resume(self.state_path, discovery, state['state_revision'])

    def handoff(self):
        path = self.state_path.parent / 'handoff.json'
        path.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF', issue_id='BCS-710',
            run_id=self.state()['run_id'], from_stage='flow-spec', next_stage='auto', artifact_key='spec:M1')))
        return accept_handoff(self.state_path, path, self.state()['state_revision'])

    def test_drafts_can_register_and_review_but_not_handoff(self):
        for kind in ('spec', 'plan', 'code'):
            with self.subTest(kind=kind):
                state = self.state()
                state['current_stage'] = 'flow-' + kind
                commit_state(self.state_path, state, 'TEST_STAGE', {})
                path, _ = fixtures.write_artifact(self.state_path.parent, kind, milestone='M1', approval_status='DRAFT')
                state = register_artifact(self.state_path, path, kind, 'M1', self.state()['state_revision'])
                self.assertFalse(state['artifacts'][kind + ':M1']['approval']['valid'])
                if kind == 'code':
                    record_snapshot(self.state_path, kind + ':M1', state['state_revision'])
                for backend in ('gpt', 'cursor', 'consistency'):
                    self.review(backend, kind=kind)
                self.assertEqual('approve:' + kind, self.state()['pending_action'])
                handoff = self.state_path.parent / 'draft-handoff.json'
                handoff.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF', issue_id='BCS-710',
                    run_id=self.state()['run_id'], from_stage='flow-' + kind, next_stage='auto', artifact_key=kind + ':M1')))
                with self.assertRaises(FlowctlError):
                    accept_handoff(self.state_path, handoff, self.state()['state_revision'])

    def test_envelope_approval_does_not_invalidate_receipts(self):
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', approval_status='DRAFT')
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        before = self.state()
        text = path.read_text()
        body, envelope = text.split('--- FLOW APPROVAL BEGIN ---', 1)
        path.write_text(body + '--- FLOW APPROVAL BEGIN ---' + envelope.replace('status: DRAFT', 'status: APPROVED'))
        state = register_artifact(self.state_path, path, 'spec', 'M1', before['state_revision'])
        self.assertEqual(before['artifacts']['spec:M1']['digest'], state['artifacts']['spec:M1']['digest'])
        self.assertTrue(state['artifacts']['spec:M1']['approval']['valid'])
        self.assertTrue(all(item['eligible'] for item in state['reviews']['attempts'].values()))
        self.assertEqual('handoff:spec', state['pending_action'])
        self.assertEqual('flow-plan', self.handoff()['current_stage'])

    def test_draft_resume_does_not_go_back_to_requirement(self):
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', approval_status='DRAFT')
        state = self.state()
        state['artifacts']['spec:M1'] = read_artifact(path)
        commit_state(self.state_path, state, 'TEST_DRAFT', {})
        state = self.resume()
        self.assertEqual('flow-spec', state['current_stage'])
        self.assertEqual('review:gpt', state['pending_action'])

    def test_resume_after_ibrain_pass_runs_consistency_not_cursor(self):
        self.review('gpt')
        self.failure('cursor'); self.failure('cursor')
        self.review('ibrain')
        self.assertEqual('review:consistency', self.resume()['pending_action'])
        self.review('consistency')
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.handoff()

    def test_resume_after_cursor_pass_requires_consistency(self):
        self.review('gpt'); self.review('cursor')
        self.assertEqual('review:consistency', self.resume()['pending_action'])

    def test_arbitrary_entry_full_pass_resumes_handoff(self):
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        self.assertEqual('handoff:spec', self.resume(only_spec=True)['pending_action'])
        self.handoff()

    def test_external_repair_keeps_gpt_and_returns_to_owning_lane(self):
        self.review('gpt')
        self.review('cursor', 'FAILED', [dict(summary='Fix rule', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        state = register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:cursor', state['pending_action'])
        state = self.resume()
        self.assertEqual('review:cursor', state['pending_action'])
        self.assertTrue(has_passed_review(state, 'spec:M1', 'gpt', state['artifacts']['spec:M1']['digest']))
        self.review('cursor'); self.review('consistency')
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.handoff()

    def test_incomplete_blocker_returns_to_repair_not_retry(self):
        self.review('gpt')
        self.review('cursor', 'INCOMPLETE', [dict(summary='Blocking evidence', blocking_status='BLOCKING')])
        self.assertEqual('revise:spec', self.state()['pending_action'])
        self.assertEqual('revise:spec', self.resume()['pending_action'])

    def test_incomplete_nonblocking_can_retry_same_content(self):
        self.review('gpt')
        self.review('cursor', 'INCOMPLETE', [dict(summary='Need remaining observation', blocking_status='NON_BLOCKING')])
        self.assertEqual('review:cursor:retry', self.state()['pending_action'])
        self.review('cursor')
        self.assertEqual('review:consistency', self.state()['pending_action'])

    def test_package_exception_finishes_attempt_without_pass_or_fallback(self):
        self.review('gpt')
        prompt = self.state_path.parent / 'prompt.txt'
        prompt.write_text('Review the current Spec, report the evidence and conclusions.')
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=FlowctlError('REVIEW_PACKAGE_DRIFT')):
            try:
                run_cursor_review(self.state_path, 'spec:M1', prompt, self.root / 'runner.py',
                                  'cursor', 'high', 5, self.state()['state_revision'])
            except FlowctlError:
                pass
        state = self.state()
        attempts = [a for a in state['reviews']['attempts'].values() if a['backend'] == 'cursor']
        self.assertEqual(['INCOMPLETE'], [a['status'] for a in attempts])
        self.assertEqual('UNCLASSIFIED', attempts[0]['classification'])
        self.assertEqual('review:cursor:retry', state['pending_action'])
        self.review('cursor')

    def test_custom_code_evidence_can_be_approved_after_review(self):
        state = self.state()
        state['current_stage'] = 'flow-code'
        commit_state(self.state_path, state, 'TEST_CODE_STAGE', {})
        path, _ = fixtures.write_artifact(self.root, 'code', milestone='M1', approval_status='DRAFT')
        register_artifact(self.state_path, path, 'code', 'M1', self.state()['state_revision'])
        record_snapshot(self.state_path, 'code:M1', self.state()['state_revision'])
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend, kind='code')
        body, envelope = path.read_text().split('--- FLOW APPROVAL BEGIN ---', 1)
        path.write_text(body + '--- FLOW APPROVAL BEGIN ---' + envelope.replace('status: DRAFT', 'status: COMPLETE'))
        register_artifact(self.state_path, path, 'code', 'M1', self.state()['state_revision'])
        from flowctl_lib.snapshot import verify_recorded_snapshot
        verify_recorded_snapshot(self.state(), 'code:M1')
        self.assertEqual('handoff:code', self.state()['pending_action'])

    def test_ibrain_repair_returns_to_ibrain_after_resume(self):
        self.review('gpt'); self.failure('cursor'); self.failure('cursor')
        self.review('ibrain', 'FAILED', [dict(summary='Fix behavior', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:ibrain', self.resume()['pending_action'])
        self.review('ibrain'); self.review('consistency'); self.handoff()

    def test_consistency_failure_reopens_required_lanes(self):
        self.review('gpt'); self.review('cursor')
        self.review('consistency', 'FAILED', [dict(summary='Cross-lane conflict', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:gpt', self.resume()['pending_action'])
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        self.handoff()

    def test_ibrain_repair_runtime_exhaustion_allows_consistency(self):
        self.review('gpt'); self.failure('cursor'); self.failure('cursor')
        self.review('ibrain', 'FAILED', [dict(summary='Fix behavior', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.failure('ibrain'); self.failure('ibrain')
        self.assertEqual('review:consistency', self.state()['pending_action'])
        self.review('consistency')
        self.handoff()

    def test_exception_between_begin_and_bind_closes_attempt(self):
        self.review('gpt')
        prompt = self.state_path.parent / 'prompt.txt'
        prompt.write_text('Review current Spec.')
        from flowctl_lib.review_package import create_review_package
        calls = 0
        def fail_fresh(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise FlowctlError('REVIEW_INPUT_UNAVAILABLE')
            return create_review_package(*args, **kwargs)
        with patch('flowctl_lib.review_package.create_review_package', side_effect=fail_fresh):
            with self.assertRaisesRegex(FlowctlError, 'REVIEW_INPUT_UNAVAILABLE'):
                run_cursor_review(self.state_path, 'spec:M1', prompt, self.root / 'runner.py',
                                  'cursor', 'high', 5, self.state()['state_revision'])
        attempts = [a for a in self.state()['reviews']['attempts'].values() if a['backend'] == 'cursor']
        self.assertEqual(['INCOMPLETE'], [a['status'] for a in attempts])
        self.review('cursor')

    def test_missing_pass_receipt_can_be_recreated_by_review(self):
        self.review('gpt')
        passed = self.review('cursor')
        Path(passed['report_path']).unlink()
        self.assertEqual('review:cursor', self.resume()['pending_action'])
        self.review('cursor')
        self.assertEqual('review:consistency', self.state()['pending_action'])

    def test_old_stage_approval_refresh_preserves_current_action(self):
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        self.handoff()
        before = self.state()
        path = Path(before['artifacts']['spec:M1']['path'])
        body, envelope = path.read_text().split('--- FLOW APPROVAL BEGIN ---', 1)
        envelope = envelope.replace('controller_run_id: run-bcs-710', 'controller_run_id: metadata-refresh')
        path.write_text(body + '--- FLOW APPROVAL BEGIN ---' + envelope)
        register_artifact(self.state_path, path, 'spec', 'M1', before['state_revision'])
        self.assertEqual(before['current_stage'], self.state()['current_stage'])
        self.assertEqual(before['pending_action'], self.state()['pending_action'])
