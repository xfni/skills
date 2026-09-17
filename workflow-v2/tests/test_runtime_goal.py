"""Goal references are runtime context, not stage approval."""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest

import test_flowctl as fixtures
from flowctl_lib import state as controller
from flowctl_lib.cli import _parser, dispatch
from flowctl_lib.errors import FlowctlError


class RuntimeGoalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)
        self.payload = self.root / 'runtime-goal.json'
        self.goal = {'threadId': 'session-1', 'createdAt': 1789530000,
                     'objective': '按 Flow 完成 BCS-710 当前范围及集成验证', 'status': 'active'}

    def record(self, goal=None, revision=None):
        self.assertTrue(callable(getattr(controller, 'record_runtime_goal', None)), 'missing goal writer')
        self.payload.write_text(json.dumps({'goal': goal or self.goal, 'remainingTokens': None}))
        state = controller.load_state(self.path)
        return controller.record_runtime_goal(self.path, self.payload,
                                             state['state_revision'] if revision is None else revision)

    def test_cli_exposes_record_not_fake_runtime_creation(self):
        args = _parser().parse_args(['goal', 'record', '--state', str(self.path),
                                    '--payload', str(self.payload), '--expected-revision', '1'])
        self.assertEqual('record', args.goal_command)

    def test_real_runtime_shape_without_goal_id_is_recorded(self):
        before = controller.load_state(self.path)
        result = self.record()
        self.assertEqual(self.goal, result['runtime_goal'])
        self.assertEqual(before['pending_action'], result['pending_action'])
        self.assertEqual(before['current_stage'], result['current_stage'])
        self.assertEqual(before['reviews'], result['reviews'])
        self.assertEqual(before['artifacts'], result['artifacts'])

    def test_duplicate_record_is_idempotent(self):
        first = self.record()
        self.assertEqual(first['state_revision'], self.record()['state_revision'])

    def test_goal_status_can_refresh_during_human_gate_without_clearing_it(self):
        state = self.record()
        state['pending_signal'] = {'signal': 'FLOW_RUN_HUMAN_GATE'}
        controller.commit_state(self.path, state, 'FIXTURE_HUMAN_GATE', {})
        result = self.record({**self.goal, 'status': 'complete'})
        self.assertEqual('FLOW_RUN_HUMAN_GATE', result['pending_signal']['signal'])
        with self.assertRaisesRegex(FlowctlError, 'FLOW_PAUSED'):
            controller.reject_if_paused(result)

    def test_invalid_snapshot_does_not_write(self):
        self.assertTrue(callable(getattr(controller, 'record_runtime_goal', None)), 'missing goal writer')
        before = self.path.read_bytes()
        self.payload.write_text(json.dumps({'goal': None}))
        with self.assertRaisesRegex(FlowctlError, 'INVALID_RUNTIME_GOAL'):
            controller.record_runtime_goal(self.path, self.payload, controller.load_state(self.path)['state_revision'])
        self.assertEqual(before, self.path.read_bytes())

    def test_new_session_reference_retains_history_but_not_stage_changes(self):
        first = self.record()
        second = self.record({**self.goal, 'threadId': 'session-2', 'createdAt': 1789540000})
        self.assertEqual('session-2', second['runtime_goal']['threadId'])
        self.assertEqual(first['runtime_goal'], second['runtime_goal_history'][-1])
        self.assertEqual(first['pending_action'], second['pending_action'])

    def test_observed_same_thread_replacement_preserves_history_and_flow_pause(self):
        # Characterize recording only: these are fixture observations, not host activation.
        for created_at in (self.goal['createdAt'], self.goal['createdAt'] + 1000):
            with self.subTest(created_at=created_at):
                prior = self.record({**self.goal, 'status': 'blocked'})
                prior['pending_signal'] = {'signal': 'FLOW_RUN_HUMAN_GATE'}
                controller.commit_state(self.path, prior, 'FIXTURE_HUMAN_GATE', {})
                before = controller.load_state(self.path)
                replacement = {**self.goal, 'createdAt': created_at,
                               'objective': '按人类新任务完成 BCS-710 当前批准的接口验证'}
                result = self.record(replacement)
                self.assertEqual(replacement, result['runtime_goal'])
                self.assertEqual(before['runtime_goal'], result['runtime_goal_history'][-1])
                for field in ('current_stage', 'pending_action', 'pending_signal',
                              'artifacts', 'reviews', 'authorizations'):
                    self.assertEqual(before[field], result[field], field)
                with self.assertRaisesRegex(FlowctlError, 'FLOW_PAUSED'):
                    controller.reject_if_paused(result)

    def test_stale_state_revision_still_rejected(self):
        old_revision = controller.load_state(self.path)['state_revision']
        self.record()
        with self.assertRaisesRegex(FlowctlError, 'STATE_CONFLICT'):
            self.record(revision=old_revision)

    def test_cli_records_observed_context_without_approving_stage(self):
        subprocess.run(['git', '-C', str(self.root), 'checkout', '-qb', 'feature-BCS-710-flowctl'], check=True)
        before = controller.load_state(self.path)
        self.payload.write_text(json.dumps({'goal': {**self.goal, 'tokensUsed': 100}}))
        args = _parser().parse_args(['goal', 'record', '--state', str(self.path),
                    '--payload', str(self.payload), '--expected-revision', str(before['state_revision'])])
        result = dispatch(args)
        self.assertTrue(result['ok'])
        self.assertEqual(self.goal, result['state']['runtime_goal'])
        self.assertEqual(before['pending_action'], result['state']['pending_action'])
        self.assertEqual(before['reviews'], result['state']['reviews'])

    def test_malformed_core_fields_leave_context_unchanged(self):
        self.record()
        for field, value in (('threadId', ''), ('objective', None), ('status', []),
                             ('createdAt', True), ('createdAt', 1.5)):
            with self.subTest(field=field, value=value):
                before = self.path.read_bytes()
                with self.assertRaisesRegex(FlowctlError, 'INVALID_RUNTIME_GOAL'):
                    self.record({**self.goal, field: value})
                self.assertEqual(before, self.path.read_bytes())
