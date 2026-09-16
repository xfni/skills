"""Human-selected iBrain is a route, not a fabricated Cursor failure."""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import test_flowctl as fixtures
from flowctl_lib import reviews
from flowctl_lib.state import load_state, register_artifact
from flowctl_lib.errors import FlowctlError
from flowctl_lib.handoff import accept_handoff
from flowctl_lib.resume import resume_flow, reconcile_resume
from flowctl_lib.cli import _parser, dispatch


class ExternalReviewSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)
        state = load_state(self.path)
        attempt = reviews.begin_review(self.path, 'gpt', 'flow-spec', 'spec:M1',
                                       'gpt-6-astra', 'medium', state['state_revision'])
        report = self.root / 'gpt.json'
        report.write_text(json.dumps({'status': 'PASSED', 'findings': []}))
        reviews.submit_review(self.path, attempt['attempt_id'], report, attempt['state_revision'])

    def select(self):
        self.assertTrue(callable(getattr(reviews, 'select_external_review', None)), 'missing route selection')
        return reviews.select_external_review(self.path, 'ibrain', '人类明确要求本次运行仅用iBrain',
                                              load_state(self.path)['state_revision'])

    def test_default_still_requires_cursor_failures(self):
        state = load_state(self.path)
        self.assertEqual('review:cursor', state['pending_action'])
        with self.assertRaisesRegex(FlowctlError, 'CURSOR_RETRY_REQUIRED'):
            reviews.begin_review(self.path, 'ibrain', 'flow-spec', 'spec:M1',
                                 'glm-5.3', 'medium', state['state_revision'])

    def test_cli_selection_binds_run_without_review_attempt(self):
        subprocess.run(['git', '-C', str(self.root), 'checkout', '-qb', 'feature-BCS-710-flowctl'], check=True)
        before = load_state(self.path)
        args = _parser().parse_args(['review', 'select-external', '--state', str(self.path),
            '--backend', 'ibrain', '--reason', '人类明确指定iBrain',
            '--expected-revision', str(before['state_revision'])])
        state = dispatch(args)['state']
        self.assertEqual('review:ibrain', state['pending_action'])
        self.assertEqual(before['reviews']['attempts'], state['reviews']['attempts'])

    def test_selection_preserves_gpt_and_does_not_fabricate_attempts(self):
        before = load_state(self.path)
        state = self.select()
        self.assertEqual('review:ibrain', state['pending_action'])
        self.assertEqual(before['reviews']['attempts'], state['reviews']['attempts'])
        self.assertEqual(before['reviews']['lanes'], state['reviews']['lanes'])
        self.assertEqual(before['artifacts'], state['artifacts'])
        attempt = reviews.begin_review(self.path, 'ibrain', 'flow-spec', 'spec:M1',
                                       'glm-5.3', 'medium', state['state_revision'])
        self.assertEqual('ibrain', attempt['backend'])
        self.assertFalse(any(a['backend'] == 'cursor' for a in load_state(self.path)['reviews']['attempts'].values()))

    def test_selected_ibrain_disallows_cursor_and_requires_external_receipt(self):
        state = self.select()
        with self.assertRaisesRegex(FlowctlError, 'EXTERNAL_BACKEND_SELECTED'):
            reviews.begin_review(self.path, 'cursor', 'flow-spec', 'spec:M1', 'cursor', 'high', state['state_revision'])
        with self.assertRaisesRegex(FlowctlError, 'EXTERNAL_REVIEW_REQUIRED'):
            reviews.begin_review(self.path, 'consistency', 'flow-spec', 'spec:M1',
                                 'gpt-6-astra', 'medium', state['state_revision'])

    def test_idempotent_selection_and_candidate_refresh_keep_route(self):
        first = self.select()
        self.assertEqual(first['state_revision'], self.select()['state_revision'])
        state = register_artifact(self.path, first['artifacts']['spec:M1']['path'], 'spec', 'M1', first['state_revision'])
        self.assertEqual('review:ibrain', reviews.next_review_action(state, 'spec:M1'))

    def test_real_controlled_ibrain_pass_requires_fresh_consistency(self):
        state = self.select()
        prompt = self.root / 'prompt.txt'
        prompt.write_text('Review current behavior independently.')
        def transport(package, *args):
            self.assertEqual('ibrain', package.manifest['backend'])
            report = {'status': 'PASSED', 'findings': [], 'reviewed_digest': package.manifest['artifact_digest']}
            return 0, reviews.REPORT_BEGIN + '\n' + json.dumps(report) + '\n' + reviews.REPORT_END, '', False
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=transport):
            result = reviews.run_ibrain_review(self.path, 'spec:M1', prompt, self.root / 'unused.py',
                                             5, state['state_revision'])
        self.assertEqual('PASSED', result['status'])
        state = load_state(self.path)
        self.assertEqual('review:consistency', state['pending_action'])
        attempt = reviews.begin_review(self.path, 'consistency', 'flow-spec', 'spec:M1',
                                       'gpt-6-astra', 'medium', state['state_revision'])
        self.assertEqual('consistency', attempt['backend'])
        report = self.root / 'consistency.json'
        report.write_text(json.dumps({'status': 'PASSED', 'findings': []}))
        result = reviews.submit_review(self.path, attempt['attempt_id'], report, attempt['state_revision'])
        handoff = self.root / 'handoff.json'
        handoff.write_text(json.dumps({'schema_version': 1, 'signal': 'FLOW_RUN_HANDOFF',
            'issue_id': 'BCS-710', 'run_id': 'run-bcs-710', 'from_stage': 'flow-spec',
            'next_stage': 'flow-plan', 'artifact_key': 'spec:M1'}))
        accepted = accept_handoff(self.path, handoff, result['state_revision'])
        self.assertEqual('flow-plan', load_state(self.path)['current_stage'])
        self.assertFalse(load_state(self.path)['open_gaps'])

    def test_resume_preserves_direct_selection(self):
        state = self.select()
        inputs = self.root / 'inputs.json'
        inputs.write_text(json.dumps({'spec:M1': state['artifacts']['spec:M1']['path']}))
        discovery = resume_flow('BCS-710', self.root, inputs, controller=state)
        resumed = reconcile_resume(self.path, discovery, state['state_revision'])
        self.assertEqual('ibrain', resumed['reviews']['external_backend'])
        self.assertEqual('review:ibrain', resumed['pending_action'])

    def test_direct_ibrain_runtime_exhaustion_goes_to_consistency_not_cursor(self):
        state = self.select()
        for index in range(2):
            attempt = reviews.begin_review(self.path, 'ibrain', 'flow-spec', 'spec:M1',
                                          'glm-5.3', 'medium', state['state_revision'])
            reviews.record_process_result(self.path, attempt['attempt_id'], None, '', '', True,
                                         attempt['state_revision'], self.root / f'failure-{index}.json')
            state = load_state(self.path)
        self.assertEqual('review:consistency', state['pending_action'])
        self.assertFalse(any(a['backend'] == 'cursor' for a in state['reviews']['attempts'].values()))
        with self.assertRaisesRegex(FlowctlError, 'IBRAIN_RETRY_EXHAUSTED'):
            reviews.begin_review(self.path, 'ibrain', 'flow-spec', 'spec:M1',
                                 'glm-5.3', 'medium', state['state_revision'])

    def test_selection_does_not_hide_blocking_consistency_findings(self):
        # Build real terminal receipts before changing the route.
        state = load_state(self.path)
        prompt = self.root / 'prompt.txt'
        prompt.write_text('Review behavior.')
        def transport(package, *args):
            report = {'status': 'PASSED', 'findings': [], 'reviewed_digest': package.manifest['artifact_digest']}
            return 0, reviews.REPORT_BEGIN + '\n' + json.dumps(report) + '\n' + reviews.REPORT_END, '', False
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=transport):
            reviews.run_cursor_review(self.path, 'spec:M1', prompt, self.root / 'unused.py',
                                     'cursor', 'high', 5, state['state_revision'])
        state = load_state(self.path)
        attempt = reviews.begin_review(self.path, 'consistency', 'flow-spec', 'spec:M1',
                                       'gpt-6-astra', 'medium', state['state_revision'])
        report = self.root / 'consistency.json'
        report.write_text(json.dumps({'status': 'FAILED', 'findings': [{'id': 'F-1',
            'severity': 'Blocker', 'summary': 'Incorrect accepted boundary', 'blocking_status': 'BLOCKING',
            'recurrence_key': 'incorrect-boundary', 'evidence': 'Current acceptance contradicts intent'}]}))
        reviews.submit_review(self.path, attempt['attempt_id'], report, attempt['state_revision'])
        selected = self.select()
        self.assertEqual('revise:spec', selected['pending_action'])
        self.assertTrue(selected['reviews']['attempts'][attempt['attempt_id']]['eligible'])

    def test_selected_lane_can_supersede_old_nonblocking_incomplete_cursor(self):
        state = load_state(self.path)
        prompt = self.root / 'prompt.txt'
        prompt.write_text('Review behavior independently.')
        def transport(package, *args):
            report = {'status': 'INCOMPLETE' if package.manifest['backend'] == 'cursor' else 'PASSED',
                      'findings': [], 'reviewed_digest': package.manifest['artifact_digest']}
            if package.manifest['backend'] == 'cursor':
                report['findings'] = [{'id': 'N-1', 'severity': 'Note', 'summary': 'Supplementary coverage limited',
                    'blocking_status': 'NON_BLOCKING', 'recurrence_key': 'coverage-limit',
                    'evidence': 'Supplementary historical context unavailable'}]
            return 0, reviews.REPORT_BEGIN + '\n' + json.dumps(report) + '\n' + reviews.REPORT_END, '', False
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=transport):
            reviews.run_cursor_review(self.path, 'spec:M1', prompt, self.root / 'unused.py',
                                     'cursor', 'high', 5, state['state_revision'])
            state = self.select()
            reviews.run_ibrain_review(self.path, 'spec:M1', prompt, self.root / 'unused.py',
                                     5, state['state_revision'])
        state = load_state(self.path)
        attempt = reviews.begin_review(self.path, 'consistency', 'flow-spec', 'spec:M1',
                                       'gpt-6-astra', 'medium', state['state_revision'])
        report = self.root / 'consistency.json'
        report.write_text(json.dumps({'status': 'PASSED', 'findings': []}))
        result = reviews.submit_review(self.path, attempt['attempt_id'], report, attempt['state_revision'])
        handoff = self.root / 'handoff.json'
        handoff.write_text(json.dumps({'schema_version': 1, 'signal': 'FLOW_RUN_HANDOFF',
            'issue_id': 'BCS-710', 'run_id': 'run-bcs-710', 'from_stage': 'flow-spec',
            'next_stage': 'flow-plan', 'artifact_key': 'spec:M1'}))
        accept_handoff(self.path, handoff, result['state_revision'])
        self.assertEqual('flow-plan', load_state(self.path)['current_stage'])
