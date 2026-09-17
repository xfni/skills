"""Command-level acceptance for Agent-owned position and controller facts."""
import tempfile
from pathlib import Path
import unittest
import json
import hashlib

from test_flowctl import write_artifact
from flowctl_lib.state import initialize_state, register_artifact, commit_state
from flowctl_lib.resume import resume_flow, reconcile_resume
from flowctl_lib.reviews import has_passed_review
from flowctl_lib.errors import FlowctlError
from flowctl_lib.signals import record_signal
from flowctl_lib.integration_results import validate_integration_results_against_plan
from flowctl_lib.handoff import accept_handoff


class AgentCooperationTests(unittest.TestCase):
    def test_runtime_budget_is_bound_to_current_code_snapshot(self):
        from flowctl_lib.reviews import _runtime_failure_count_for
        state = {'artifacts': {'code:M1': {'type': 'code'}},
            'snapshots': {'code:M1': {'snapshot_digest': 'new'}}, 'reviews': {'attempts': {
                str(i): {'artifact_key': 'code:M1', 'backend': 'cursor', 'classification': 'RUN_ERROR',
                         'artifact_digest': 'same', 'snapshot_digest': 'old'} for i in range(2)}}}
        self.assertEqual(_runtime_failure_count_for(state, 'code:M1', 'cursor', 'same'), 0)

    def test_intermediate_blocked_report_cannot_hide_other_failure(self):
        from flowctl_lib.integration_results import validate_result_replacement
        first = {'digest': 'first', 'integration_results': {'status': 'FAILED', 'test_object': 'build',
            'scenarios': [{'scenario_id': 'A', 'status': 'FAILED'}, {'scenario_id': 'B', 'status': 'FAILED'}]}}
        second = {'digest': 'second', 'integration_results': {'status': 'BLOCKED', 'test_object': 'build',
            'scenarios': [{'scenario_id': 'A', 'status': 'BLOCKED'}]}}
        validate_result_replacement(first, second)
        last = {'digest': 'last', 'integration_results': {'status': 'PASSED', 'test_object': 'build',
            'replaces': 'second', 'scenarios': [{'scenario_id': 'A', 'status': 'PASSED'}]}}
        with self.assertRaisesRegex(FlowctlError, 'INTEGRATION_UNRESOLVED_OBSERVATIONS'):
            validate_result_replacement(second, last)

    def test_old_started_review_does_not_lock_new_object(self):
        from flowctl_lib.reviews import begin_review
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test', stage='flow-spec', milestone='M1')
            first, _ = write_artifact(root, 'spec', milestone='M1', approval_status='DRAFT')
            state = register_artifact(path, first, 'spec', 'M1', 0)
            attempt = begin_review(path, 'gpt', 'flow-spec', 'spec:M1', 'gpt-6-astra', 'medium', state['state_revision'])
            second, _ = write_artifact(root, 'spec', revision=2, milestone='M1', approval_status='DRAFT')
            state = register_artifact(path, second, 'spec', 'M1', attempt['state_revision'])
            fresh = begin_review(path, 'gpt', 'flow-spec', 'spec:M1', 'gpt-6-astra', 'medium', state['state_revision'])
            self.assertNotEqual(attempt['attempt_id'], fresh['attempt_id'])

    def test_success_requires_object_and_readable_execution_evidence(self):
        from flowctl_lib.integration_results import require_completion_evidence
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = {'status': 'PASSED', 'scenarios': [{'scenario_id': 'A', 'status': 'PASSED'}]}
            with self.assertRaises(FlowctlError):
                require_completion_evidence({'integration_results': result}, root)
            result['test_object'] = 'local-service/current-build'
            result['evidence'] = ['missing.log']
            with self.assertRaises(FlowctlError):
                require_completion_evidence({'integration_results': result}, root)
            log = root / 'execution.log'
            log.write_text('fixture: real request returned expected response')
            result['evidence'] = [str(log)]
            require_completion_evidence({'integration_results': result}, root)

    def test_resolved_old_failure_does_not_block_applicability(self):
        from flowctl_lib.dispositions import unresolved_review
        state = {'reviews': {'attempts': {
            'old': {'artifact_key': 'spec:M1', 'artifact_digest': 'a', 'backend': 'gpt',
                    'status': 'FAILED', 'completed_state_revision': 1},
            'new': {'artifact_key': 'spec:M1', 'artifact_digest': 'a', 'backend': 'gpt',
                    'status': 'PASSED', 'completed_state_revision': 2}}}}
        self.assertFalse(unresolved_review(state, 'spec:M1', 'a'))
        state['reviews']['attempts']['new']['status'] = 'INCOMPLETE'
        self.assertTrue(unresolved_review(state, 'spec:M1', 'a'))

    def test_requirement_draft_registration_is_not_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test')
            draft, _ = write_artifact(root, 'requirement', approval_status='DRAFT')
            state = register_artifact(path, draft, 'requirement', None, 0)
            handoff = root / 'handoff.json'
            handoff.write_text(json.dumps({'schema_version': 1, 'signal': 'FLOW_RUN_HANDOFF',
                'issue_id': 'BCS-710', 'run_id': state['run_id'], 'from_stage': 'flow-requirement',
                'next_stage': 'auto', 'artifact_key': 'requirement'}))
            with self.assertRaises(FlowctlError):
                accept_handoff(path, handoff, state['state_revision'])

    def test_partial_pass_cannot_erase_registered_failed_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                                     stage='flow-integration', milestone='M1')
            failed, _ = write_artifact(root, 'integration', milestone='M1', approval_status='FAILED',
                                      integration_results={'status': 'FAILED', 'test_object': 'snapshot-A',
                                                           'scenarios': [{'scenario_id': 'A', 'status': 'FAILED'},
                                                                         {'scenario_id': 'B', 'status': 'FAILED'}]})
            state = register_artifact(path, failed, 'integration', 'M1', 0)
            partial, _ = write_artifact(root, 'integration', milestone='M1', revision=2,
                                       integration_results={'status': 'PASSED', 'test_object': 'snapshot-A',
                                                            'replaces': state['artifacts']['integration:M1']['digest'],
                                                            'scenarios': [{'scenario_id': 'A', 'status': 'PASSED'}]})
            with self.assertRaisesRegex(FlowctlError, 'INTEGRATION_UNRESOLVED_OBSERVATIONS'):
                register_artifact(path, partial, 'integration', 'M1', state['state_revision'])

    def test_legacy_plan_does_not_require_scenario_universe(self):
        result = {'status': 'BLOCKED', 'scenarios': [{'scenario_id': 'startup', 'status': 'BLOCKED'}]}
        plan = {'revision': 1, 'digest': 'sha256:' + '1' * 64, 'integration_scenarios': None}
        self.assertEqual(validate_integration_results_against_plan(result, plan)['status'], 'BLOCKED')

    def test_explicit_pause_identity_prevents_clearing_wrong_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test')
            payload = {'schema_version': 1, 'signal': 'FLOW_RUN_HUMAN_GATE',
                       'issue_id': 'BCS-710', 'run_id': 'run-bcs-710', 'stage': 'flow-requirement',
                       'cause': 'Need scope confirmation', 'evidence': 'Human decision pending',
                       'resume_condition': 'Human confirms scope', 'gate': 'scope'}
            file = root / 'signal.json'
            file.write_text(json.dumps(payload))
            paused = record_signal(path, file, 0)
            payload.update(signal='FLOW_RUN_RESUMED', pause_revision=999)
            file.write_text(json.dumps(payload))
            with self.assertRaises(FlowctlError) as raised:
                record_signal(path, file, paused['state_revision'])
            self.assertEqual(raised.exception.code, 'PAUSE_BINDING_MISMATCH')

    def test_historical_receipt_requires_bound_disposition_and_cannot_revive_revocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                                     stage='flow-spec', milestone='M1')
            artifact, _ = write_artifact(root, 'spec', milestone='M1', approval_status='DRAFT')
            state = register_artifact(path, artifact, 'spec', 'M1', 0)
            report = root / 'receipt.json'
            report.write_text(json.dumps({'status': 'PASSED', 'findings': []}))
            old_digest = state['artifacts']['spec:M1']['digest']
            state['reviews']['attempts']['original'] = {
                'attempt_id': 'original', 'artifact_key': 'spec:M1', 'backend': 'gpt',
                'status': 'PASSED', 'classification': 'REVIEW_RESULT', 'artifact_digest': old_digest,
                'report_path': str(report), 'report_digest': 'sha256:' + hashlib.sha256(report.read_bytes()).hexdigest(),
                'execution_assurance': 'CALLER_ATTESTED',
            }
            state = commit_state(path, state, 'TEST_RECEIPT', {})
            artifact, _ = write_artifact(root, 'spec', revision=2, milestone='M1', approval_status='DRAFT')
            disposition = root / 'disposition.json'
            disposition.write_text(json.dumps({'reason': 'Clarification; scope and reviewed implementation unchanged',
                                              'evidence': [str(report)], 'source_attempts': ['original']}))
            state = register_artifact(path, artifact, 'spec', 'M1', state['state_revision'],
                                      disposition_path=disposition)
            new_digest = state['artifacts']['spec:M1']['digest']
            self.assertTrue(has_passed_review(state, 'spec:M1', 'gpt', new_digest))
            self.assertEqual(state['reviews']['attempts']['original']['artifact_digest'], old_digest)
            state['reviews']['attempts']['later-failed'] = {
                'attempt_id': 'later-failed', 'artifact_key': 'spec:M1', 'backend': 'gpt',
                'artifact_digest': old_digest, 'status': 'FAILED', 'completed_state_revision': 100}
            self.assertFalse(has_passed_review(state, 'spec:M1', 'gpt', new_digest))
            state['reviews']['attempts'].pop('later-failed')
            state['reviews']['attempts']['original']['revoked'] = True
            self.assertFalse(has_passed_review(state, 'spec:M1', 'gpt', new_digest))
            state['reviews']['attempts']['original']['revoked'] = False
            state['artifacts']['spec:M1']['digest'] = 'newer-change'
            self.assertFalse(has_passed_review(state, 'spec:M1', 'gpt', 'newer-change'))

    def test_resume_uses_registered_paths_and_preserves_position(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                                     stage='flow-integration', milestone='M1')
            requirement, _ = write_artifact(root, 'requirement')
            state = register_artifact(path, requirement, 'requirement', None, 0)
            default = root / '.ai' / 'issue' / 'BCS-710'
            default.mkdir(parents=True)
            write_artifact(default, 'requirement', name='conflict.md')
            write_artifact(default, 'requirement', name='other.md', approval_status='REJECTED')
            discovery = resume_flow('BCS-710', root, controller=state)
            recovered = reconcile_resume(path, discovery, state['state_revision'])
            self.assertEqual(recovered['current_stage'], 'flow-integration')
            self.assertEqual(recovered['active_milestone'], 'M1')
            again = resume_flow('BCS-710', root, controller=recovered)
            self.assertEqual(reconcile_resume(path, again, recovered['state_revision']), recovered)

    def test_direct_code_entry_does_not_fabricate_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                                     stage='flow-code', milestone='M1')
            artifact, _ = write_artifact(root, 'code', milestone='M1', approval_status='DRAFT')
            state = register_artifact(path, artifact, 'code', 'M1', state['state_revision'])
            self.assertEqual(state['current_stage'], 'flow-code')
            self.assertEqual(set(state['artifacts']), {'code:M1'})
            self.assertEqual(state['active_milestone'], 'M1')

    def test_registration_preserves_position_and_downstream_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test')
            requirement, _ = write_artifact(root, 'requirement')
            state = register_artifact(path, requirement, 'requirement', None, 0)
            state['current_stage'] = 'flow-code'
            state['artifacts']['code:M1'] = {'type': 'code', 'milestone_id': 'M1', 'digest': 'old'}
            state['snapshots']['code:M1'] = {'snapshot_digest': 'original'}
            state['coder_agent'] = {'coder_thread_id': 'persistent'}
            state = commit_state(path, state, 'TEST_CURRENT_POSITION', {})
            requirement, _ = write_artifact(root, 'requirement', revision=2)
            state = register_artifact(path, requirement, 'requirement', None, state['state_revision'])
            self.assertEqual(state['current_stage'], 'flow-code')
            self.assertIn('code:M1', state['artifacts'])
            self.assertEqual(state['snapshots']['code:M1']['snapshot_digest'], 'original')
            self.assertEqual(state['coder_agent']['coder_thread_id'], 'persistent')

    def test_complete_registration_does_not_reopen_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test')
            state['current_stage'] = 'complete'
            state['pending_action'] = 'complete'
            state = commit_state(path, state, 'TEST_COMPLETE', {})
            artifact, _ = write_artifact(root, 'requirement')
            state = register_artifact(path, artifact, 'requirement', None, state['state_revision'])
            self.assertEqual(state['current_stage'], 'complete')
            self.assertEqual(state['pending_action'], 'complete')

    def test_existing_init_cannot_relocate_or_clear_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test')
            state['pending_signal'] = {'signal': 'FLOW_RUN_HUMAN_GATE'}
            state = commit_state(path, state, 'TEST_PAUSE', {})
            state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                                     stage='flow-code', milestone='M1')
            self.assertEqual(state['current_stage'], 'flow-requirement')
            self.assertEqual(state['pending_signal']['signal'], 'FLOW_RUN_HUMAN_GATE')
