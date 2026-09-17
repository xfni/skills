"""Progression checks facts needed now, not perfect historical/model metadata."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_flowctl
from flowctl_lib.errors import FlowctlError
from flowctl_lib.handoff import accept_handoff, _read_handoff
from flowctl_lib.reviews import begin_review, submit_review, record_process_result, has_passed_review
from flowctl_lib.state import load_state, commit_state, register_artifact
from flowctl_lib.integration_results import validate_integration_results_against_plan


class MinimumReviewGates(unittest.TestCase):
    def fixture(self, root):
        return test_flowctl.ReviewAndHandoffTests()._state_with_spec(root)

    def review(self, path, root, backend, payload=None):
        state = load_state(path)
        attempt = begin_review(path, backend, 'flow-spec', 'spec:M1',
                               'gpt-6-astra' if backend != 'ibrain' else 'glm-5.3',
                               'medium', state['state_revision'])
        report = root / (backend + '-report.json')
        report.write_text(json.dumps(payload or {
            'status': 'PASSED', 'reviewed_digest': attempt['artifact_digest'], 'findings': [],
        }))
        return submit_review(path, attempt['attempt_id'], report, attempt['state_revision'],
                             controller_executed=backend in {'cursor', 'ibrain'})

    def handoff(self, path, root):
        state = load_state(path)
        document = root / 'next.json'
        document.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF',
            issue_id=state['issue_id'], run_id=state['run_id'], from_stage='flow-spec',
            next_stage='auto', artifact_key='spec:M1')))
        return accept_handoff(path, document, state['state_revision'])

    def test_four_valid_runtime_failures_satisfy_two_failure_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            self.review(path, root, 'gpt')
            for backend in ('cursor', 'ibrain'):
                for index in range(2):
                    state = load_state(path)
                    attempt = begin_review(path, backend, 'flow-spec', 'spec:M1',
                        'glm-5.3' if backend == 'ibrain' else 'cursor', 'medium', state['state_revision'])
                    record_process_result(path, attempt['attempt_id'], 2, '', '', False,
                        attempt['state_revision'], root / f'{backend}-{index}.json')
                # Historical repair can reveal additional genuine attempts.
                state = load_state(path)
                original = [item for item in state['reviews']['attempts'].values()
                            if item['backend'] == backend][-1]
                for index in range(2):
                    extra = copy.deepcopy(original)
                    extra['attempt_id'] = f'historical-{backend}-{index}'
                    state['reviews']['attempts'][extra['attempt_id']] = extra
                commit_state(path, state, 'HISTORICAL_REPAIR_FIXTURE', {})
            self.review(path, root, 'consistency')
            result = self.handoff(path, root)
            self.assertEqual('flow-plan', result['current_stage'])
            self.assertEqual('COMPLETE_WITH_DEFECT', result['completion_quality'])

    def test_changed_unrelated_history_does_not_prevent_current_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            old = Path(load_state(path)['artifacts']['requirement']['path'])
            old.write_text(old.read_text() + '\nHistorical annotation outside the body.\n')
            self.assertEqual('PASSED', self.review(path, root, 'gpt')['status'])

    def test_auxiliary_report_fields_and_missing_digest_do_not_reject_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            result = self.review(path, root, 'gpt', {
                'status': 'PASSED', 'notes': 'No blocking issues.',
            })
            self.assertEqual('PASSED', result['status'])

    def test_failed_review_needs_problem_not_six_exact_finding_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            result = self.review(path, root, 'gpt', {
                'status': 'FAILED', 'findings': [{'summary': 'Request can cross tenant boundary.'}],
            })
            self.assertEqual('FAILED', result['status'])
            self.assertEqual('BLOCKING', result['findings'][0]['blocking_status'])

    def test_unknown_result_never_becomes_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            with self.assertRaises(FlowctlError):
                self.review(path, root, 'gpt', {'notes': 'Looks reasonable'})

    def test_lane_claim_without_review_receipt_cannot_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            state = load_state(path)
            state['reviews']['lanes']['spec:M1'] = {
                name: {'status': 'PASSED', 'digest': state['artifacts']['spec:M1']['digest']}
                for name in ('gpt', 'cursor', 'consistency')}
            commit_state(path, state, 'UNSUPPORTED_LANE_CLAIM', {})
            with self.assertRaises(FlowctlError):
                self.handoff(path, root)

    def test_extra_handoff_metadata_is_not_a_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'handoff.json'
            path.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF',
                issue_id='BCS-710', run_id='run', from_stage='flow-spec',
                next_stage='auto', artifact_key='spec:M1', explanation='Ready for planning.')))
            self.assertEqual('spec:M1', _read_handoff(path)['artifact_key'])

    def test_arbitrary_spec_resume_then_real_reviews_can_enter_plan(self):
        from flowctl_lib.resume import resume_flow, reconcile_resume
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            state = load_state(path)
            spec_path = state['artifacts']['spec:M1']['path']
            state.update(artifacts={}, current_stage='flow-spec',
                target_milestones=[], milestones={}, active_milestone='M1')
            state = commit_state(path, state, 'ARBITRARY_ENTRY_FIXTURE', {})
            inputs = root / 'input-map.json'
            inputs.write_text(json.dumps({'spec:M1': spec_path}))
            discovery = resume_flow(state['issue_id'], root, inputs, controller=state)
            resumed = reconcile_resume(path, discovery, state['state_revision'])
            self.assertEqual({'spec:M1'}, set(resumed['artifacts']))
            self.assertEqual('review:gpt', resumed['pending_action'])
            for backend in ('gpt', 'cursor', 'consistency'):
                self.review(path, root, backend)
            self.assertEqual('flow-plan', self.handoff(path, root)['current_stage'])

    def test_changed_content_gets_controller_revision_even_if_model_forgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.fixture(root)
            self.review(path, root, 'gpt')
            state = load_state(path)
            spec = Path(state['artifacts']['spec:M1']['path'])
            spec.write_text(spec.read_text().replace('--- FLOW BODY END ---',
                'RULE-NEW: Validate the tenant boundary.\n--- FLOW BODY END ---'))
            state = register_artifact(path, spec, 'spec', 'M1', state['state_revision'])
            self.assertEqual(2, state['artifacts']['spec:M1']['revision'])
            self.assertEqual('review:gpt', state['pending_action'])
            self.assertFalse(has_passed_review(state, 'spec:M1', 'gpt', state['artifacts']['spec:M1']['digest']))


class MinimumArtifactAndTestGates(unittest.TestCase):
    def test_explicit_broken_test_outline_is_not_legacy_omission(self):
        from flowctl_lib.artifacts import read_artifact
        from flowctl_lib.resume import _integration_result_valid
        from flowctl_lib.integration_results import require_integration_results
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.md'
            path.write_text('artifact_type: plan\nissue_id: BCS-710\nmilestone_id: M1\nstatus: APPROVED\nintegration_scenarios: {broken json}\n')
            plan = read_artifact(path)
            integration = {'milestone_id': 'M1', 'integration_results': None}
            self.assertFalse(_integration_result_valid(integration, {'plan:M1': plan}))
            with self.assertRaisesRegex(FlowctlError, 'INTEGRATION_RESULTS_REQUIRED'):
                require_integration_results(integration, plan)

    def test_readable_artifact_does_not_need_exact_serialization_or_declared_digest(self):
        import flowctl_lib.artifacts as artifacts
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = test_flowctl.write_artifact(Path(tmp), 'spec', milestone='M1')
            path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes().replace(b'\n', b'\r\n'))
            # Read-only controller ingestion, distinct from optional strict audit.
            self.assertTrue(hasattr(artifacts, 'read_artifact'))
            result = artifacts.read_artifact(path, expected_type='spec', expected_issue='BCS-710')
            self.assertTrue(result['approval']['valid'])
            self.assertTrue(result['warnings'])

    def test_arbitrary_node_without_historical_chain_is_discoverable(self):
        from flowctl_lib.resume import resume_flow
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = root / '.ai' / 'issue' / 'BCS-710'
            issue.mkdir(parents=True)
            test_flowctl.write_artifact(issue, 'spec', milestone='M1', name='behavior-contract.md')
            result = resume_flow('BCS-710', root)
            self.assertIn('spec:M1', result['valid_artifacts'])
            self.assertEqual('flow-spec', result['deepest_valid_stage'])

    def test_test_order_and_redundant_counts_are_not_progression_gates(self):
        digest = 'sha256:' + 'a' * 64
        plan = dict(digest=digest, revision=1, integration_scenarios={
            'schema_version': 1, 'scenarios': [
                dict(scenario_id=name, production_dependency={'required': False})
                for name in ('TESTCASE-A', 'TESTCASE-B')]})
        result = dict(status='PASSED', plan_digest=digest, plan_revision=1,
            executed_count=99, skipped_count=0, gaps=[], warnings=[],
            scenarios=[dict(scenario_id=name, status='PASSED', observation='HTTP 200')
                       for name in ('TESTCASE-B', 'TESTCASE-A')], summary='Both requests ran.')
        normalized = validate_integration_results_against_plan(result, plan)
        self.assertEqual('PASSED', normalized['status'])
        self.assertEqual(2, normalized['executed_count'])

    def test_failed_test_cannot_be_hidden_by_passed_summary(self):
        digest = 'sha256:' + 'a' * 64
        plan = dict(digest=digest, revision=1, integration_scenarios={
            'schema_version': 1, 'scenarios': [
                dict(scenario_id='TESTCASE-A', production_dependency={'required': False})]})
        result = dict(status='PASSED', plan_digest=digest, plan_revision=1,
            executed_count=1, skipped_count=0, gaps=[], warnings=[],
            scenarios=[dict(scenario_id='TESTCASE-A', status='FAILED')])
        # Rejecting or deriving FAILED is safe; silently retaining PASSED is not.
        try:
            normalized = validate_integration_results_against_plan(result, plan)
        except FlowctlError:
            return
        self.assertEqual('FAILED', normalized['status'])

    def test_aggregate_accepts_additional_executed_test_without_declaring_skip(self):
        from flowctl_lib.integration_results import aggregate_integration_results
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = test_flowctl.write_artifact(Path(tmp), 'plan', milestone='M1')
            result = aggregate_integration_results([
                {'scenario_id': 'TESTCASE-DEFAULT', 'status': 'PASSED'},
                {'scenario_id': 'TESTCASE-EXTRA', 'status': 'PASSED'},
            ], plan)
            self.assertEqual(2, result['executed_count'])
            self.assertEqual('PASSED', result['status'])

    def test_status_does_not_audit_historical_content(self):
        from flowctl_lib.cli import _parser, dispatch
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = test_flowctl.ReviewAndHandoffTests()._state_with_spec(root)
            args = _parser().parse_args(['status', '--state', str(path)])
            with patch('flowctl_lib.cli.validate_admission', return_value={}), \
                    patch('flowctl_lib.cli.audit_state', side_effect=AssertionError('global audit')):
                self.assertTrue(dispatch(args)['ok'])
