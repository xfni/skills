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

    def review(self, backend, status='PASSED', findings=None, kind='spec', resolved_reviews=None):
        state = self.state()
        attempt = begin_review(self.state_path, backend, 'flow-' + kind, kind + ':M1',
            'glm-5.3' if backend == 'ibrain' else 'gpt-6-astra', 'medium', state['state_revision'])
        self.index += 1
        report = self.state_path.parent / f'report-{self.index}.json'
        report.write_text(json.dumps(dict(status=status, findings=findings or [], reviewed_digest=attempt['artifact_digest'], resolved_reviews=resolved_reviews or [])))
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

    def test_invalidated_old_reviews_do_not_exhaust_new_code(self):
        state = self.state()
        state['current_stage'] = 'flow-code'
        commit_state(self.state_path, state, 'TEST_CODE_STAGE', {})
        for revision in (1, 2, 3):
            path, _ = fixtures.write_artifact(self.root, 'code', milestone='M1', revision=revision,
                                             approval_status='DRAFT')
            register_artifact(self.state_path, path, 'code', 'M1', self.state()['state_revision'])
            record_snapshot(self.state_path, 'code:M1', self.state()['state_revision'])
            self.review('gpt', kind='code')
        path, _ = fixtures.write_artifact(self.root, 'code', milestone='M1', revision=4,
                                         approval_status='DRAFT')
        register_artifact(self.state_path, path, 'code', 'M1', self.state()['state_revision'])
        record_snapshot(self.state_path, 'code:M1', self.state()['state_revision'])
        self.assertEqual('review:gpt', self.state()['pending_action'])
        self.review('gpt', kind='code')
        self.assertEqual(4, len(self.state()['reviews']['attempts']))

    def test_current_content_review_limit_still_blocks(self):
        for _ in range(3):
            self.review('gpt', 'INCOMPLETE', [dict(summary='Need remaining observation', blocking_status='NON_BLOCKING')])
        self.assertEqual('repair:review:cycle-limit', self.state()['pending_action'])
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_CYCLE_LIMIT'):
            self.review('gpt', 'INCOMPLETE', [dict(summary='Need remaining observation', blocking_status='NON_BLOCKING')])

    def test_resume_reconciles_approved_replacement_requirement_route(self):
        from flowctl_lib.signals import record_signal
        state = self.state()
        route = self.state_path.parent / 'route.json'
        route.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_ROUTE_BACK',
            issue_id='BCS-710', run_id=state['run_id'], stage='flow-spec',
            next_stage='flow-requirement', owner_stage='flow-requirement',
            cause='Replace scope', evidence='Human scope decision', resume_condition='Approve replacement')))
        record_signal(self.state_path, route, state['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'requirement', revision=2,
                                         approval_status='READY_FOR_INTENT')
        inputs = self.state_path.parent / 'replacement-inputs.json'
        inputs.write_text(json.dumps({'requirement': str(path)}))
        state = self.state()
        discovery = resume_flow('BCS-710', self.root, inputs, controller=state)
        reconciled = reconcile_resume(self.state_path, discovery, state['state_revision'])
        self.assertIsNone(reconciled['route_back_context'])
        self.assertEqual('handoff:requirement', reconciled['pending_action'])
        context = state['route_back_context']
        reconciled['route_back_context'] = context
        reconciled['pending_action'] = 'revise:requirement'
        commit_state(self.state_path, reconciled, 'TEST_LEGACY_STALE_CONTEXT', {})
        repaired = register_artifact(self.state_path, path, 'requirement', None, self.state()['state_revision'])
        self.assertIsNone(repaired['route_back_context'])
        self.assertEqual('handoff:requirement', repaired['pending_action'])
        reconciled = repaired
        before = reconciled['state_revision']
        idem = register_artifact(self.state_path, path, 'requirement', None, before)
        self.assertEqual(before, idem['state_revision'])

    def test_historical_consistency_annotation_does_not_block_fresh_review(self):
        self.review('gpt'); self.review('cursor')
        state = self.state()
        state['reviews']['lanes']['spec:M1']['consistency_attempts'] = 3
        commit_state(self.state_path, state, 'TEST_LEGACY_CONSISTENCY_COUNT', {})
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.review('consistency')
        self.assertEqual('handoff:spec', self.state()['pending_action'])

    def test_draft_replacement_keeps_requirement_route(self):
        from flowctl_lib.signals import record_signal
        state = self.state()
        route = self.state_path.parent / 'route.json'
        route.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_ROUTE_BACK',
            issue_id='BCS-710', run_id=state['run_id'], stage='flow-spec',
            next_stage='flow-requirement', owner_stage='flow-requirement',
            cause='Replace scope', evidence='Human scope decision', resume_condition='Approve replacement')))
        record_signal(self.state_path, route, state['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'requirement', revision=2,
                                         approval_status='DRAFT')
        inputs = self.state_path.parent / 'replacement-inputs.json'
        inputs.write_text(json.dumps({'requirement': str(path)}))
        state = self.state()
        discovery = resume_flow('BCS-710', self.root, inputs, controller=state)
        reconciled = reconcile_resume(self.state_path, discovery, state['state_revision'])
        self.assertIsNotNone(reconciled['route_back_context'])
        self.assertEqual('revise:requirement', reconciled['pending_action'])

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
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.review('consistency')
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.handoff()

    def test_resume_after_cursor_pass_requires_consistency(self):
        self.review('gpt'); self.review('cursor')
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.assertEqual('COMPLETE', self.handoff()['completion_quality'])

    def test_human_gpt_only_needs_no_external_failures(self):
        from flowctl_lib.reviews import degrade_review
        self.review('gpt')
        degrade_review(self.state_path, 'external', 'human', 'Human requests GPT only',
                       self.state()['state_revision'])
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.assertEqual('COMPLETE_WITH_DEFECT', self.handoff()['completion_quality'])
        self.assertEqual(1, len(self.state()['reviews']['attempts']))

    def test_unavailability_allows_external_only_but_not_zero_reviews(self):
        from flowctl_lib.reviews import degrade_review, select_external_review
        degrade_review(self.state_path, 'gpt', 'unavailable', 'Both GPT models unavailable',
                       self.state()['state_revision'])
        with self.assertRaisesRegex(FlowctlError, 'INDEPENDENT_REVIEW_REQUIRED'):
            self.handoff()
        select_external_review(self.state_path, 'ibrain', 'Use available iBrain', self.state()['state_revision'])
        self.review('ibrain')
        self.assertEqual('COMPLETE_WITH_DEFECT', self.handoff()['completion_quality'])

    def test_degrade_does_not_erase_other_lane_blocker(self):
        from flowctl_lib.reviews import degrade_review
        self.review('gpt')
        self.review('cursor', 'FAILED', [dict(summary='Permission bypass', blocking_status='BLOCKING')])
        degrade_review(self.state_path, 'external', 'human', 'GPT only', self.state()['state_revision'])
        with self.assertRaisesRegex(FlowctlError, 'UNRESOLVED_REVIEW_FINDINGS'):
            self.handoff()

    def test_observed_cursor_unavailability_can_use_ibrain_without_fake_attempt(self):
        from flowctl_lib.reviews import degrade_review
        self.review('gpt')
        degrade_review(self.state_path, 'external', 'unavailable', 'Cursor SDK unavailable; iBrain is available',
                       self.state()['state_revision'])
        self.review('ibrain')
        self.assertEqual('COMPLETE', self.handoff()['completion_quality'])
        self.assertFalse(any(a['backend'] == 'cursor' for a in self.state()['reviews']['attempts'].values()))

    def test_registration_releases_old_started_without_changing_its_result(self):
        from flowctl_lib.reviews import degrade_review
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        old = self.state()['reviews']['attempts'][attempt['attempt_id']]
        self.assertEqual('STARTED', old['status'])
        self.assertIsNone(old['classification'])
        self.assertIn('recovery_disposition', old)
        self.assertEqual(attempt['artifact_digest'], old['artifact_digest'])
        self.review('gpt')
        degrade_review(self.state_path, 'external', 'human', 'GPT only', self.state()['state_revision'])
        self.assertEqual('COMPLETE_WITH_DEFECT', self.handoff()['completion_quality'])

    def test_resume_repairs_legacy_started_and_is_idempotent(self):
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        state = self.state()
        state['reviews']['attempts'][attempt['attempt_id']].pop('recovery_disposition', None)
        commit_state(self.state_path, state, 'TEST_LEGACY_STARTED', {})
        recovered = self.resume()
        self.assertIn('recovery_disposition', recovered['reviews']['attempts'][attempt['attempt_id']])
        self.assertEqual(recovered['state_revision'], self.resume()['state_revision'])

    def test_current_started_still_blocks_and_approval_change_does_not_archive_it(self):
        from flowctl_lib.reviews import degrade_review
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        path = Path(self.state()['artifacts']['spec:M1']['path'])
        body, approval = path.read_text().split('--- FLOW APPROVAL BEGIN ---', 1)
        path.write_text(body + '--- FLOW APPROVAL BEGIN ---' + approval.replace('status: APPROVED', 'status: DRAFT'))
        registered = register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual(attempt['artifact_digest'], registered['artifacts']['spec:M1']['digest'])
        self.assertEqual('DRAFT', registered['artifacts']['spec:M1']['approval']['status'])
        self.resume()
        self.assertNotIn('recovery_disposition', self.state()['reviews']['attempts'][attempt['attempt_id']])
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_ATTEMPT_IN_PROGRESS'):
            degrade_review(self.state_path, 'external', 'human', 'GPT only', self.state()['state_revision'])

    def test_paused_resume_releases_legacy_occupancy_without_releasing_pause(self):
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        state = self.state()
        state['reviews']['attempts'][attempt['attempt_id']].pop('recovery_disposition', None)
        pause = dict(signal='FLOW_RUN_BLOCKED', cause='Actual host refusal', stage='flow-spec')
        state['pending_signal'] = pause
        state['pending_action'] = 'blocked:host'
        commit_state(self.state_path, state, 'TEST_LEGACY_PAUSED', {})
        recovered = self.resume()
        self.assertEqual(pause, recovered['pending_signal'])
        self.assertEqual('blocked:host', recovered['pending_action'])
        self.assertEqual('flow-spec', recovered['current_stage'])
        self.assertIn('recovery_disposition', recovered['reviews']['attempts'][attempt['attempt_id']])
        self.assertEqual(recovered['state_revision'], self.resume()['state_revision'])

    def test_replaced_started_cannot_submit_when_digest_returns_to_old_value(self):
        original = self.state()['artifacts']['spec:M1']['path']
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2, name='replacement.md')
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        register_artifact(self.state_path, original, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual(attempt['artifact_digest'], self.state()['artifacts']['spec:M1']['digest'])
        report = self.state_path.parent / 'late.json'
        report.write_text(json.dumps(dict(status='PASSED', findings=[], reviewed_digest=attempt['artifact_digest'])))
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_ATTEMPT_STALE'):
            submit_review(self.state_path, attempt['attempt_id'], report, self.state()['state_revision'])
        self.assertEqual('review:gpt', self.resume()['pending_action'])

    def test_unknown_started_binding_cannot_launch_overlapping_review(self):
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        state = self.state()
        state['reviews']['attempts'][attempt['attempt_id']].pop('artifact_digest')
        commit_state(self.state_path, state, 'TEST_LEGACY_UNKNOWN_BINDING', {})
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_ATTEMPT_IN_PROGRESS'):
            begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                         'gpt-6-astra', 'medium', self.state()['state_revision'])

    def test_other_milestone_started_does_not_occupy_current_route(self):
        from flowctl_lib.reviews import degrade_review
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        state = self.state()
        state['active_milestone'] = 'M2'
        commit_state(self.state_path, state, 'TEST_CURRENT_M2', {})
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M2', name='spec_m2.md')
        register_artifact(self.state_path, path, 'spec', 'M2', self.state()['state_revision'])
        degraded = degrade_review(self.state_path, 'external', 'human', 'GPT only', self.state()['state_revision'])
        self.assertEqual('STARTED', degraded['reviews']['attempts'][attempt['attempt_id']]['status'])
        self.assertNotIn('recovery_disposition', degraded['reviews']['attempts'][attempt['attempt_id']])

    def test_missing_attempt_snapshot_cannot_launch_overlapping_code_review(self):
        state = self.state()
        state['current_stage'] = 'flow-code'
        commit_state(self.state_path, state, 'TEST_CODE', {})
        path, _ = fixtures.write_artifact(self.state_path.parent, 'code', milestone='M1', approval_status='DRAFT')
        register_artifact(self.state_path, path, 'code', 'M1', self.state()['state_revision'])
        record_snapshot(self.state_path, 'code:M1', self.state()['state_revision'])
        attempt = begin_review(self.state_path, 'gpt', 'flow-code', 'code:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        state = self.state()
        state['reviews']['attempts'][attempt['attempt_id']].pop('snapshot_digest')
        commit_state(self.state_path, state, 'TEST_UNKNOWN_CODE_SNAPSHOT', {})
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_ATTEMPT_IN_PROGRESS'):
            begin_review(self.state_path, 'gpt', 'flow-code', 'code:M1',
                         'gpt-6-astra', 'medium', self.state()['state_revision'])

    def test_new_version_retains_known_blocker_until_explicit_handoff_review(self):
        from flowctl_lib.reviews import degrade_review
        self.review('gpt')
        failed = self.review('cursor', 'FAILED', [dict(summary='Permission bypass', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        degrade_review(self.state_path, 'external', 'human', 'GPT only', self.state()['state_revision'])
        self.review('gpt')
        with self.assertRaisesRegex(FlowctlError, 'UNRESOLVED_REVIEW_FINDINGS'):
            self.handoff()
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1',
                               'gpt-6-astra', 'medium', self.state()['state_revision'])
        report = self.state_path.parent / 'handoff-review.json'
        report.write_text(json.dumps(dict(status='PASSED', findings=[], reviewed_digest=attempt['artifact_digest'],
            resolved_reviews=[dict(attempt_id=failed['attempt_id'], evidence='Reproduced original bypass; verified fix and negative test')])) )
        submit_review(self.state_path, attempt['attempt_id'], report, attempt['state_revision'])
        self.assertEqual('COMPLETE_WITH_DEFECT', self.handoff()['completion_quality'])

    def test_arbitrary_entry_full_pass_resumes_handoff(self):
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        self.assertEqual('handoff:spec', self.resume(only_spec=True)['pending_action'])
        self.handoff()

    def test_external_repair_keeps_gpt_and_returns_to_owning_lane(self):
        self.review('gpt')
        self.review('cursor', 'FAILED', [dict(summary='Fix rule', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        state = fixtures.register_clarification(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:cursor:resolve-findings', state['pending_action'])
        state = self.resume()
        self.assertEqual('review:cursor:resolve-findings', state['pending_action'])
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
        self.assertEqual('handoff:spec', self.state()['pending_action'])

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
        fixtures.register_clarification(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:ibrain:resolve-findings', self.resume()['pending_action'])
        self.review('ibrain'); self.review('consistency'); self.handoff()

    def test_consistency_failure_reopens_required_lanes(self):
        self.review('gpt'); self.review('cursor')
        self.review('consistency', 'FAILED', [dict(summary='Cross-lane conflict', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        register_artifact(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.assertEqual('review:consistency:resolve-findings', self.resume()['pending_action'])
        for backend in ('gpt', 'cursor', 'consistency'):
            self.review(backend)
        self.handoff()

    def test_ibrain_repair_runtime_exhaustion_allows_consistency(self):
        self.review('gpt'); self.failure('cursor'); self.failure('cursor')
        failed = self.review('ibrain', 'FAILED', [dict(summary='Fix behavior', blocking_status='BLOCKING')])
        path, _ = fixtures.write_artifact(self.state_path.parent, 'spec', milestone='M1', revision=2)
        fixtures.register_clarification(self.state_path, path, 'spec', 'M1', self.state()['state_revision'])
        self.failure('ibrain'); self.failure('ibrain')
        with self.assertRaisesRegex(FlowctlError, 'UNRESOLVED_REVIEW_FINDINGS'):
            self.handoff()
        self.review('consistency', resolved_reviews=[dict(attempt_id=failed['attempt_id'], evidence='Original finding and repaired rule verified')])
        self.handoff()

    def test_external_runtime_exhaustion_uses_distinct_astra_receipts_and_preserves_gap(self):
        # Existing controlled path, not proof of real vendor/subagent availability.
        with self.assertRaisesRegex(FlowctlError, 'GPT_REVIEW_REQUIRED'):
            self.review('consistency')
        self.review('gpt')  # Helper supplies an Astra/medium primary report.
        primary_id = self.state()['reviews']['lanes']['spec:M1']['gpt']['attempt_id']
        for backend in ('cursor', 'ibrain'):
            self.failure(backend)
            self.failure(backend)
        self.assertEqual('handoff:spec', self.resume()['pending_action'])
        self.review('consistency')
        state = self.state()
        consistency_id = state['reviews']['lanes']['spec:M1']['consistency']['attempt_id']
        self.assertNotEqual(primary_id, consistency_id)
        for attempt_id in (primary_id, consistency_id):
            self.assertEqual('gpt-6-astra', state['reviews']['attempts'][attempt_id]['model'])
            self.assertEqual('medium', state['reviews']['attempts'][attempt_id]['effort'])
        handoff = self.handoff()
        self.assertEqual('COMPLETE_WITH_DEFECT', handoff['completion_quality'])
        self.assertEqual('有条件通过', handoff['stage_summary']['result'])
        state = self.state()
        self.assertEqual('flow-plan', state['current_stage'])
        gap = next(g for g in state['open_gaps'] if g['type'] == 'EXTERNAL_REVIEW_GAP')
        self.assertEqual('OPEN', gap['status'])
        self.assertEqual(4, len(gap['attempt_ids']))
        self.assertFalse(any(a.get('status') == 'PASSED' for a in state['reviews']['attempts'].values()
                             if a['backend'] in ('cursor', 'ibrain')))

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
        self.assertEqual('handoff:spec', self.state()['pending_action'])

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
