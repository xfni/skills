"""Local production tests need scope authority, not a sanitizer registry."""
import json
from pathlib import Path
import tempfile
import unittest

import test_flowctl as fixtures
from flowctl_lib.authorizations import decide_authorization, default_authorizations
from flowctl_lib.state import commit_state, load_state, reject_if_paused
from flowctl_lib.errors import FlowctlError
from flowctl_lib.cli import _parser


class LocalProductionPolicyTests(unittest.TestCase):
    def test_local_use_can_be_authorized_without_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = fixtures.ReviewAndHandoffTests()._state_with_spec(Path(tmp))
            state = load_state(state_path)
            state = decide_authorization(state_path, 'production_replay', 'LOCAL_PRODUCTION_REPLAY', state['state_revision'])
            auth = state['authorizations']['production_replay']
            self.assertEqual('LOCAL_PRODUCTION_REPLAY', auth['decision'])
            self.assertEqual([], auth['bindings'])
            self.assertNotIn('raw_persistence', auth)
            self.assertNotIn('cleanup_required', auth)
            self.assertEqual('DENIED', auth['external_model_transmission'])
            self.assertEqual('DENIED', auth['git_tracking'])

    def test_legacy_raw_cleanup_record_does_not_pause_normal_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixtures.ReviewAndHandoffTests()._state_with_spec(Path(tmp))
            state = load_state(path)
            legacy = {'binding_id': 'legacy', 'evidence': {'status': 'INTERRUPTED'}}
            state['authorizations']['production_replay']['bindings'].append(legacy)
            state = commit_state(path, state, 'FIXTURE_LEGACY_REPLAY', {})
            reject_if_paused(load_state(path))
            self.assertEqual(legacy, load_state(path)['authorizations']['production_replay']['bindings'][0])
            from flowctl_lib.stage_summary import stage_summary
            self.assertNotEqual('阻塞中', stage_summary(load_state(path))['status'])

    def test_real_safety_pause_still_blocks(self):
        with self.assertRaisesRegex(FlowctlError, 'FLOW_PAUSED'):
            reject_if_paused({'pending_signal': {'signal': 'FLOW_RUN_BLOCKED'}})

    def test_flow_does_not_execute_replay_adapters(self):
        parser = _parser()
        choices = next(a.choices for a in parser._actions if a.dest == 'command')
        self.assertNotIn('replay', choices)

    def test_defaults_delegate_data_governance_not_transfer_policy(self):
        auth = default_authorizations()['production_replay']
        self.assertNotIn('raw_persistence', auth)
        self.assertNotIn('cleanup_required', auth)
        self.assertNotIn('raw_production_data', auth['exclusions'])
        self.assertEqual('DENIED', auth['external_model_transmission'])
        self.assertEqual('DENIED', auth['git_tracking'])

    def test_obsolete_manifest_metadata_does_not_reject_plan(self):
        from flowctl_lib.integration_results import validate_plan_integration_scenarios
        contract = {'schema_version': 1, 'scenarios': [{'scenario_id': 'TESTCASE-1',
                    'production_dependency': {'required': True, 'replay_manifest_digest': 'old-advisory'}}]}
        self.assertEqual(contract, validate_plan_integration_scenarios(contract))

    def test_legacy_decision_and_bindings_survive_actual_resume(self):
        from flowctl_lib.authorizations import HARD_EXCLUSIONS
        from flowctl_lib.resume import resume_flow, reconcile_resume
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixtures.ReviewAndHandoffTests()._state_with_spec(root)
            state = load_state(path)
            state = decide_authorization(path, 'production_replay', 'SANITIZED_LOCAL_REPLAY', state['state_revision'])
            auth = state['authorizations']['production_replay']
            auth.update(raw_persistence='DENIED', cleanup_required=True, exclusions=list(HARD_EXCLUSIONS))
            auth['bindings'].append({'binding_id': 'legacy', 'evidence': {'status': 'BLOCKED_CLEANUP'}})
            original = json.loads(json.dumps(auth))
            state = commit_state(path, state, 'FIXTURE_LEGACY_AUTHORIZATION', {})
            inputs = root / 'inputs.json'
            inputs.write_text(json.dumps({key: item['path'] for key, item in state['artifacts'].items()}))
            discovery = resume_flow('BCS-710', root, inputs)
            reconcile_resume(path, discovery, state['state_revision'])
            resumed = load_state(path)
            self.assertEqual(original, resumed['authorizations']['production_replay'])
            self.assertEqual('flow-spec', resumed['current_stage'])
            self.assertEqual('review:gpt', resumed['pending_action'])
