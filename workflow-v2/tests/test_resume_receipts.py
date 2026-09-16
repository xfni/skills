"""Recover registered paths and exact receipts, not a fourth review cycle."""
import json
from pathlib import Path
import tempfile
import unittest

import test_flowctl as fixtures
from flowctl_lib.state import load_state, commit_state, register_artifact
from flowctl_lib.snapshot import record_snapshot
from flowctl_lib.reviews import begin_review, submit_review, has_passed_review
from flowctl_lib.resume import resume_flow, reconcile_resume


class ResumeReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        original = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)
        self.path = self.root / '.ai/issue/BCS-710/flow-state.json'
        self.path.parent.mkdir(parents=True)
        original.rename(self.path)
        original.with_name('flow-events.jsonl').rename(self.path.with_name('flow-events.jsonl'))
        state = load_state(self.path)
        state['controller_path'] = str(self.path)
        state['current_stage'] = 'flow-code'
        commit_state(self.path, state, 'TEST_LOCATION', {})
        output = self.root / '.ai/validation/issues/BCS-710'
        output.mkdir(parents=True)
        code, _ = fixtures.write_artifact(output, 'code', milestone='M1', approval_status='DRAFT')
        state = register_artifact(self.path, code, 'code', 'M1', load_state(self.path)['state_revision'])
        record_snapshot(self.path, 'code:M1', state['state_revision'])
        for index in range(3):
            state = load_state(self.path)
            attempt = begin_review(self.path, 'gpt', 'flow-code', 'code:M1',
                                   'gpt-6-astra', 'medium', state['state_revision'])
            report = output / f'gpt-{index}.json'
            report.write_text(json.dumps({'status': 'PASSED', 'findings': [], 'reviewed_digest': attempt['artifact_digest']}))
            submit_review(self.path, attempt['attempt_id'], report, attempt['state_revision'])
        self.last_attempt = attempt['attempt_id']

    def discard_legacy_index(self):
        state = load_state(self.path)
        state['reviews']['lanes'].pop('code:M1')
        for attempt in state['reviews']['attempts'].values():
            if attempt['artifact_key'] == 'code:M1':
                attempt['eligible'] = False
                attempt['invalidated_by'] = 'code:M1'
        commit_state(self.path, state, 'TEST_LEGACY_DISCARD', {})

    def resume(self):
        state = load_state(self.path)
        discovery = resume_flow('BCS-710', self.root, controller=state)
        return reconcile_resume(self.path, discovery, state['state_revision'])

    def test_registered_custom_directory_is_discovered_without_path_prompt(self):
        state = load_state(self.path)
        discovery = resume_flow('BCS-710', self.root, controller=state)
        self.assertIn('code:M1', discovery['valid_artifacts'])
        self.assertEqual('flow-code', discovery['deepest_valid_stage'])

    def test_exact_pass_recovers_missing_index_without_fourth_attempt(self):
        self.discard_legacy_index()
        before = load_state(self.path)
        state = self.resume()
        artifact = state['artifacts']['code:M1']
        self.assertTrue(has_passed_review(state, 'code:M1', 'gpt', artifact['digest']))
        self.assertEqual('review:cursor', state['pending_action'])
        self.assertEqual(len(before['reviews']['attempts']), len(state['reviews']['attempts']))
        self.assertEqual(before['snapshots'], state['snapshots'])

    def test_mutated_report_cannot_restore_pass(self):
        self.discard_legacy_index()
        state = load_state(self.path)
        for attempt in state['reviews']['attempts'].values():
            if attempt['artifact_key'] == 'code:M1':
                Path(attempt['report_path']).write_text('{}')
        state = self.resume()
        self.assertFalse(has_passed_review(state, 'code:M1', 'gpt', state['artifacts']['code:M1']['digest']))

    def test_code_snapshot_drift_cannot_restore_pass(self):
        self.discard_legacy_index()
        (self.root / 'changed.py').write_text('changed = True\n')
        state = self.resume()
        self.assertFalse(has_passed_review(state, 'code:M1', 'gpt', state['artifacts']['code:M1']['digest']))

    def test_newer_failed_result_does_not_fall_back_to_older_pass(self):
        self.discard_legacy_index()
        state = load_state(self.path)
        latest = state['reviews']['attempts'][self.last_attempt]
        latest['status'] = 'FAILED'
        latest['findings'] = [{'blocking_status': 'BLOCKING', 'summary': 'Unresolved acceptance failure'}]
        commit_state(self.path, state, 'TEST_LATEST_FAILURE', {})
        state = self.resume()
        self.assertFalse(has_passed_review(state, 'code:M1', 'gpt', state['artifacts']['code:M1']['digest']))

    def test_upstream_invalidation_survives_snapshot_drift_and_return(self):
        self.discard_legacy_index()
        state = load_state(self.path)
        for attempt in state['reviews']['attempts'].values():
            if attempt['artifact_key'] == 'code:M1':
                attempt['invalidated_by'] = 'plan:M1'
        commit_state(self.path, state, 'TEST_UPSTREAM_INVALIDATION', {})
        changed = self.root / 'changed.py'
        changed.write_text('changed = True\n')
        self.resume()
        changed.unlink()
        state = self.resume()
        self.assertEqual('plan:M1', state['reviews']['attempts'][self.last_attempt]['invalidated_by'])
        self.assertFalse(has_passed_review(state, 'code:M1', 'gpt', state['artifacts']['code:M1']['digest']))

    def test_explicit_same_key_replacement_is_not_overridden_by_registered_path(self):
        state = load_state(self.path)
        replacement, _ = fixtures.write_artifact(self.path.parent, 'code', revision=4, milestone='M1',
                                                approval_status='DRAFT', name='code_replacement.md')
        inputs = self.path.parent / 'inputs.json'
        inputs.write_text(json.dumps({'code:M1': str(replacement)}))
        discovery = resume_flow('BCS-710', self.root, inputs, controller=state)
        self.assertEqual(str(replacement), discovery['valid_artifacts']['code:M1']['path'])

    def test_explicit_generic_kind_replacement_is_not_overridden(self):
        state = load_state(self.path)
        replacement, _ = fixtures.write_artifact(self.path.parent, 'code', milestone='M1',
            approval_status='DRAFT', name='code_replacement.md')
        inputs = self.path.parent / 'inputs.json'
        inputs.write_text(json.dumps({'code': str(replacement)}))
        discovery = resume_flow('BCS-710', self.root, inputs, controller=state)
        self.assertEqual(str(replacement), discovery['valid_artifacts']['code:M1']['path'])
