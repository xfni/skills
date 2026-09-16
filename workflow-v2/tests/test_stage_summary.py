"""Stage summaries are observation, never additional progression gates."""
import copy
import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class StageSummaryTests(unittest.TestCase):
    def summary(self, state):
        import flowctl_lib.cli as cli
        stage_summary = getattr(cli, 'stage_summary', None)
        self.assertTrue(callable(stage_summary), 'missing normalized stage summary')
        before = copy.deepcopy(state)
        value = stage_summary(state)
        self.assertEqual(before, state)
        return value

    def test_unstarted_is_null(self):
        self.assertEqual({'status': None, 'result': None, 'explanation': '尚未开始'}, self.summary({}))

    def test_handoff_summary_binds_completed_milestone_not_next(self):
        import test_flowctl
        from flowctl_lib.handoff import accept_handoff
        from flowctl_lib.state import load_state, commit_state
        from flowctl_lib.artifacts import read_artifact
        for has_next in (True, False):
            with self.subTest(has_next=has_next), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = test_flowctl.ReviewAndHandoffTests()._state_with_spec(root)
                state = load_state(state_path)
                for kind in ('plan', 'integration'):
                    path, _ = test_flowctl.write_artifact(root, kind, milestone='M1', legacy_plan=True,
                        approval_status='PASSED' if kind == 'integration' else 'APPROVED')
                    state['artifacts'][kind + ':M1'] = read_artifact(path)
                state['current_stage'] = 'flow-integration'
                state['pending_action'] = 'handoff:integration'
                state['target_milestones'] = ['M1', 'M2'] if has_next else ['M1']
                state['milestones'] = {m: {'status': 'pending', 'dependencies': []} for m in state['target_milestones']}
                commit_state(state_path, state, 'SUMMARY_FIXTURE', {})
                handoff = root / 'handoff.json'
                handoff.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF',
                    issue_id='BCS-710', run_id=state['run_id'], from_stage='flow-integration',
                    next_stage='auto', artifact_key='integration:M1')))
                value = accept_handoff(state_path, handoff, load_state(state_path)['state_revision'])
                self.assertEqual('M1', value['stage_summary'].get('milestone_id'))
                self.assertEqual('M2' if has_next else None, value['active_milestone'])
                current = self.summary(load_state(state_path))
                self.assertEqual('flow-spec' if has_next else 'complete', current['stage'])
                self.assertEqual('M2' if has_next else None, current['milestone_id'])

    def test_human_wait_is_distinct_from_agent_wait(self):
        human = self.summary({'current_stage': 'flow-spec', 'pending_action': 'human_gate',
            'pending_signal': {'signal': 'FLOW_RUN_HUMAN_GATE', 'gate': '确认范围', 'resume_condition': '选择 A/B'}})
        self.assertEqual('等待中', human['status'])
        self.assertIsNone(human['result'])
        self.assertIn('选择 A/B', human['explanation'])
        for action in ('review:gpt:await-result', 'review:cursor:retry', 'produce:code'):
            self.assertEqual('进行中', self.summary({'current_stage': 'flow-code', 'pending_action': action})['status'])

    def test_blocked_transport_is_not_rejection(self):
        value = self.summary({'current_stage': 'flow-spec', 'pending_action': 'blocked:review:unclassified'})
        self.assertEqual('阻塞中', value['status'])
        self.assertIsNone(value['result'])

    def test_substantive_rejection_remains_in_progress(self):
        value = self.summary({'current_stage': 'flow-plan', 'pending_action': 'revise:plan',
            'pending_signal': {'signal': 'FLOW_RUN_ROUTE_BACK', 'cause': '规则冲突'}})
        self.assertEqual('进行中', value['status'])
        self.assertEqual('拒绝', value['result'])

    def test_completion_quality_is_independent_result(self):
        for gaps, expected in (([], '通过'), ([{'type': 'EXTERNAL_REVIEW_GAP'}], '有条件通过')):
            value = self.summary({'current_stage': 'complete', 'open_gaps': gaps})
            self.assertEqual('已完成', value['status'])
            self.assertEqual(expected, value['result'])

    def test_legacy_cleanup_annotation_does_not_override_human_wait(self):
        value = self.summary({'current_stage': 'flow-integration', 'pending_action': 'human_gate',
            'authorizations': {'production_replay': {'bindings': [{'evidence': {'status': 'BLOCKED_CLEANUP'}}]}}})
        self.assertEqual('等待中', value['status'])
