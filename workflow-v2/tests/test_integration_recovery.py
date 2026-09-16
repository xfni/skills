"""Environment blockers do not require a completed integration contract."""
import json
from pathlib import Path
import tempfile
import unittest

import test_flowctl as fixtures
from flowctl_lib.state import load_state, commit_state
from flowctl_lib.signals import record_signal
from flowctl_lib.resume import resume_flow, reconcile_resume
import test_resume_receipts as receipt_fixtures


class IntegrationRecoveryTests(unittest.TestCase):
    def test_accepted_code_handoff_survives_auxiliary_snapshot_drift(self):
        fixture = receipt_fixtures.ResumeReceiptTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        state = load_state(fixture.path)
        state['current_stage'] = 'flow-integration'
        commit_state(fixture.path, state, 'HANDOFF_ACCEPTED', {
            'issue_id': state['issue_id'], 'run_id': state['run_id'],
            'from_stage': 'flow-code', 'next_stage': 'flow-integration', 'artifact_key': 'code:M1',
        })
        (fixture.root / 'test_probe.py').write_text('probe = True\n')
        state = load_state(fixture.path)
        discovery = resume_flow(state['issue_id'], fixture.root, controller=state)
        result = reconcile_resume(fixture.path, discovery, state['state_revision'])
        self.assertEqual('flow-integration', result['current_stage'])
        self.assertEqual('inspect:integration-snapshot', result['pending_action'])
        self.assertFalse(result['reviews']['attempts'][fixture.last_attempt]['eligible'])
        self.assertEqual(len(state['reviews']['attempts']), len(result['reviews']['attempts']))

    def test_drift_without_accepted_handoff_does_not_skip_code(self):
        fixture = receipt_fixtures.ResumeReceiptTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        (fixture.root / 'business.py').write_text('changed = True\n')
        state = fixture.resume()
        self.assertEqual('flow-code', state['current_stage'])
        self.assertFalse(state['reviews']['attempts'][fixture.last_attempt]['eligible'])

    def test_upstream_registration_invalidates_accepted_position(self):
        fixture = receipt_fixtures.ResumeReceiptTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        state = load_state(fixture.path)
        state = commit_state(fixture.path, state, 'HANDOFF_ACCEPTED', {
            'issue_id': state['issue_id'], 'run_id': state['run_id'],
            'from_stage': 'flow-code', 'next_stage': 'flow-integration', 'artifact_key': 'code:M1',
        })
        commit_state(fixture.path, state, 'ARTIFACT_REGISTERED', {'artifact_key': 'plan:M1'})
        state = fixture.resume()
        self.assertEqual('flow-code', state['current_stage'])

    def test_startup_blocker_without_results_or_plan_contract_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixtures.ReviewAndHandoffTests()._state_with_spec(root)
            state = load_state(path)
            state['current_stage'] = 'flow-integration'
            state = commit_state(path, state, 'TEST_INTEGRATION_ENTRY', {})
            payload = root / 'signal.json'
            payload.write_text(json.dumps({
                'schema_version': 1, 'signal': 'FLOW_RUN_BLOCKED',
                'issue_id': state['issue_id'], 'run_id': state['run_id'],
                'stage': 'flow-integration', 'cause': 'Local bind refused',
                'evidence': 'Startup exited before any HTTP request',
                'resume_condition': 'Obtain permission and retry local startup',
            }))
            record_signal(path, payload, state['state_revision'])
            result = load_state(path)
            self.assertEqual('FLOW_RUN_BLOCKED', result['pending_signal']['signal'])
            self.assertEqual('flow-integration', result['current_stage'])
            self.assertEqual(state['reviews'], result['reviews'])
