"""Final review regressions at the controller and outbound boundaries."""
import contextlib
import hashlib
import json
import io
import subprocess
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_flowctl import write_artifact
import test_flowctl
import test_replay
import test_review_runners
from flowctl_lib.errors import FlowctlError


class CleanupBlockerTests(unittest.TestCase):
    def test_actual_authorization_amendment_preserves_cleanup_obligation(self):
        from flowctl_lib.authorizations import decide_authorization, begin_authorization_amendment
        from flowctl_lib.state import initialize_state, commit_state, reject_if_paused
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'flow-state.json'
            state = initialize_state(path, 'ISSUE-2', root, 'feature-ISSUE-2-fixture')
            state = decide_authorization(path, 'production_replay', 'SANITIZED_LOCAL_REPLAY', state['state_revision'])
            state['authorizations']['production_replay']['bindings'].append({
                'binding_id':'failed-replay', 'status':'CONSUMED', 'evidence':{'status':'INTERRUPTED'}})
            state = commit_state(path, state, 'FIXTURE_INTERRUPTED', {})
            state = begin_authorization_amendment(path, 'production_replay', 'SKIP_PRODUCTION_REPLAY', state['state_revision'])
            state = decide_authorization(path, 'production_replay', 'SKIP_PRODUCTION_REPLAY', state['state_revision'])
            with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
                reject_if_paused(state)

    def test_cleanup_evidence_blocks_all_progression_entrypoints(self):
        from flowctl_lib.state import reject_if_paused
        from flowctl_lib.resume import reconcile_resume
        from flowctl_lib.signals import record_signal
        state = {'authorizations': {'production_replay': {'bindings': [{
            'binding_id': 'interrupted', 'evidence': {'status': 'BLOCKED_CLEANUP'},
        }]}}, 'issue_id': 'ISSUE-2', 'run_id': 'run', 'current_stage': 'flow-integration'}
        @contextlib.contextmanager
        def locked(*args):
            yield state
        with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
            reject_if_paused(state)
        with patch('flowctl_lib.resume.locked_state', locked):
            with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
                reconcile_resume('unused', {}, 0)
        with patch('flowctl_lib.signals.locked_state', locked), patch('flowctl_lib.signals._load', return_value={}):
            with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
                record_signal('unused', 'unused', 0)

    def test_missing_results_only_legacy_plan_can_resume(self):
        from flowctl_lib.resume import _integration_result_valid
        integration = {'milestone_id': 'M1', 'integration_results': None}
        self.assertFalse(_integration_result_valid(integration, {
            'plan:M1': {'integration_scenarios': {'schema_version': 1, 'scenarios': []}},
        }))

    def test_new_plan_cannot_omit_results_at_register_handoff_or_resume(self):
        from flowctl_lib.artifacts import verify_artifact
        from flowctl_lib.state import initialize_state, commit_state, register_artifact
        from flowctl_lib.handoff import accept_handoff
        from flowctl_lib.resume import resume_flow
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue_dir, paths, refs = test_flowctl.ResumeTests._write_resume_prefix(root)
            state_path = issue_dir / 'flow-state.json'
            state = initialize_state(state_path, 'BCS-710', root, 'feature-BCS-710-fixture')
            state.update(current_stage='flow-integration', active_milestone='M1',
                target_milestones=['M1'], milestones={'M1':{'status':'pending','dependencies':[]}},
                artifacts={(kind + ':M1' if kind in {'spec','plan','code'} else kind):verify_artifact(path) for kind,path in paths.items()})
            state = commit_state(state_path, state, 'FIXTURE_ADMITTED', {})
            integration, _ = write_artifact(issue_dir, 'integration', milestone='M1', upstream=refs, name='integration_M1.md')
            with self.assertRaisesRegex(FlowctlError, 'INTEGRATION_RESULTS_REQUIRED'):
                register_artifact(state_path, integration, 'integration', 'M1', state['state_revision'])
            self.assertNotIn('integration:M1', resume_flow('BCS-710', root)['valid_artifacts'])
            state['artifacts']['integration:M1'] = verify_artifact(integration)
            state = commit_state(state_path, state, 'FIXTURE_OLD_CHECKPOINT', {})
            handoff = issue_dir / 'handoff.json'
            handoff.write_text(json.dumps(dict(schema_version=1, signal='FLOW_RUN_HANDOFF', issue_id='BCS-710',
                run_id=state['run_id'], from_stage='flow-integration', next_stage='auto', artifact_key='integration:M1')))
            with self.assertRaisesRegex(FlowctlError, 'INTEGRATION_RESULTS_REQUIRED'):
                accept_handoff(state_path, handoff, state['state_revision'])


class ReplayPlanTests(unittest.TestCase):
    setUp = test_replay.ReplayTests.setUp
    set_command = test_replay.ReplayTests.set_command
    bind = test_replay.ReplayTests.bind
    approve_plan = test_replay.ReplayTests.approve_plan
    def test_missing_plan_rejected_before_spawn(self):
        self.state['current_stage'] = 'flow-requirement'
        self.manifest_path.write_text(json.dumps(self.manifest))
        with patch.object(self.replay, '_execute') as spawn:
            with self.assertRaisesRegex(FlowctlError, 'REPLAY_PLAN_BINDING_REQUIRED'):
                self.replay.validate_replay_manifest('unused', self.manifest_path, 0)
            spawn.assert_not_called()

    def test_plan_and_stage_drift_rejected_before_execution(self):
        binding = self.bind()
        for key in self.replay.PLAN_BINDING_KEYS:
            self.assertEqual(binding.get(key), self.manifest[key])
        for change in ('stage', 'plan', 'scenario'):
            with self.subTest(change=change), patch.object(self.replay, '_execute') as execute:
                original = json.loads(json.dumps(self.state))
                if change == 'stage':
                    self.state['current_stage'] = 'flow-code'
                elif change == 'plan':
                    self.state['artifacts']['plan:M1']['revision'] += 1
                else:
                    self.state['artifacts']['plan:M1']['integration_scenarios']['scenarios'][0]['production_dependency']['required'] = False
                with self.assertRaises(FlowctlError):
                    self.replay.run_replay('unused', binding['binding_id'], 1)
                execute.assert_not_called()
                self.state.clear()
                self.state.update(original)

    def test_cleanup_recovery_proves_removal_after_amendment(self):
        self.set_command('cleanup', 'from pathlib import Path\nPath(' + repr(str(self.root / 'private/replay.jsonl')) + ').unlink(missing_ok=True)\n')
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        self.state['authorizations']['production_replay']['mode'] = 'SKIP_PRODUCTION_REPLAY'
        recover = getattr(self.replay, 'recover_replay_cleanup', None)
        self.assertIsNotNone(recover, 'controller cleanup-proof recovery is required')
        result = recover('unused', binding['binding_id'], 2)
        self.assertEqual(result['status'], 'PASSED')
        self.assertFalse(list((self.root / 'private').iterdir()))
        self.replay.reject_unresolved_cleanup(self.state)

    def test_recovery_does_not_delegate_deletion_even_for_owned_final(self):
        destination = self.root / 'private/replay.jsonl'
        marker = self.root / 'cleanup-ran'
        self.set_command('cleanup', 'from pathlib import Path\n'
            'Path(' + repr(str(marker)) + ').write_text("ran")\n'
            'Path(' + repr(str(destination)) + ').unlink(missing_ok=True)\n')
        binding = self.interrupt_after_publication()
        original = destination.read_bytes()
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertEqual(result['status'], 'FAILED')
        self.assertFalse(marker.exists())
        self.assertEqual(destination.read_bytes(), original)

    def test_recovery_removes_only_proven_random_staging_without_adapter(self):
        binding = self.bind()
        original_spawn = self.replay.subprocess.Popen
        cleanup_source = (self.root / 'cleanup.py').read_text()
        def interrupt_cleanup(command, **kwargs):
            if len(command) > 4 and command[4] == cleanup_source:
                raise KeyboardInterrupt
            return original_spawn(command, **kwargs)
        with patch.object(self.replay.subprocess, 'Popen', side_effect=interrupt_cleanup), \
                patch.object(self.replay, '_record', side_effect=FlowctlError('REPLAY_OUTPUT_INVALID')):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        self.assertEqual(len(list((self.root / 'private').iterdir())), 1)
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertEqual(result['status'], 'PASSED')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def interrupt_after_publication(self):
        binding = self.bind()
        original_spawn = self.replay.subprocess.Popen
        cleanup_source = (self.root / 'cleanup.py').read_text()
        def interrupted_spawn(command, **kwargs):
            if len(command) > 4 and command[4] == cleanup_source:
                raise KeyboardInterrupt
            return original_spawn(command, **kwargs)
        with patch.object(self.replay.subprocess, 'Popen', side_effect=interrupted_spawn):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        self.assertTrue((self.root / 'private/replay.jsonl').is_file())
        return binding

    def test_recovery_rejects_replaced_owned_destination_before_cleanup(self):
        destination = self.root / 'private/replay.jsonl'
        marker = self.root / 'cleanup-ran'
        self.set_command('cleanup', 'from pathlib import Path\n'
            'Path(' + repr(str(marker)) + ').write_text("ran")\n'
            'Path(' + repr(str(destination)) + ').unlink(missing_ok=True)\n')
        binding = self.interrupt_after_publication()
        destination.rename(destination.with_suffix('.owned'))
        destination.write_text('replacement owner')
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertEqual(result['status'], 'FAILED')
        self.assertFalse(marker.exists())
        self.assertEqual(destination.read_text(), 'replacement owner')

    def test_recovery_rejects_changed_owned_bytes_before_cleanup(self):
        destination = self.root / 'private/replay.jsonl'
        self.set_command('cleanup', 'from pathlib import Path\n'
            'Path(' + repr(str(destination)) + ').unlink(missing_ok=True)\n')
        binding = self.interrupt_after_publication()
        destination.write_text('changed bytes on same inode')
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(destination.read_text(), 'changed bytes on same inode')

    def test_recovery_without_persisted_ownership_stays_blocked(self):
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        self.state['authorizations']['production_replay']['bindings'][0].pop('cleanup_ownership')
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertEqual(result['status'], 'FAILED')
        with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
            self.replay.reject_unresolved_cleanup(self.state)

    def test_recovery_does_not_delete_staging_created_after_absence_check(self):
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        staging = self.state['authorizations']['production_replay']['bindings'][0]['cleanup_targets'][0]
        path = self.root / 'private' / staging
        original_stat = self.replay.os.stat
        created = False
        def racing_stat(target, **kwargs):
            nonlocal created
            if target == staging and 'dir_fd' in kwargs and not created:
                path.write_text('concurrent staging owner')
                created = True
            return original_stat(target, **kwargs)
        with patch.object(self.replay.os, 'stat', side_effect=racing_stat):
            result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], self.state['state_revision'])
        self.assertTrue(path.exists(), 'recovery must not unlink a staging name without ownership')
        self.assertEqual(path.read_text(), 'concurrent staging owner')
        self.assertEqual(result['status'], 'FAILED')

    def test_failed_cleanup_recovery_keeps_global_blocker(self):
        self.set_command('cleanup', 'raise SystemExit(2)\n')
        binding = self.bind()
        result = self.replay.run_replay('unused', binding['binding_id'], 1)
        self.assertEqual(result['status'], 'BLOCKED_CLEANUP')
        recovered = self.replay.recover_replay_cleanup('unused', binding['binding_id'], result['state_revision'])
        self.assertEqual(recovered['status'], 'FAILED')
        with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
            self.replay.reject_unresolved_cleanup(self.state)

    def test_recovery_does_not_delete_unproven_destination(self):
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        destination = self.root / 'private/replay.jsonl'
        destination.write_text('unproven concurrent owner')
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], 2)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(destination.read_text(), 'unproven concurrent owner')

    def test_recovery_never_runs_destructive_cleanup_on_unowned_destination(self):
        destination = self.root / 'private/replay.jsonl'
        marker = self.root / 'cleanup-ran'
        self.set_command('cleanup', 'from pathlib import Path\n'
            'Path(' + repr(str(marker)) + ').write_text("ran")\n'
            'Path(' + repr(str(destination)) + ').unlink(missing_ok=True)\n')
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        destination.write_text('concurrent owner')
        result = self.replay.recover_replay_cleanup('unused', binding['binding_id'], 2)
        self.assertFalse(marker.exists(), 'unowned destination must prevent cleanup execution')
        self.assertEqual(destination.read_text(), 'concurrent owner')
        self.assertEqual(result['status'], 'FAILED')
        with self.assertRaisesRegex(FlowctlError, 'REPLAY_CLEANUP_REQUIRED'):
            self.replay.reject_unresolved_cleanup(self.state)

    def test_successful_cleanup_recovery_is_terminal(self):
        destination = self.root / 'private/replay.jsonl'
        marker = self.root / 'cleanup-ran'
        self.set_command('cleanup', 'from pathlib import Path\n'
            'Path(' + repr(str(marker)) + ').write_text("ran")\n'
            'Path(' + repr(str(destination)) + ').unlink(missing_ok=True)\n')
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay('unused', binding['binding_id'], 1)
        recovered = self.replay.recover_replay_cleanup('unused', binding['binding_id'], 2)
        self.assertEqual(recovered['status'], 'PASSED')
        marker.unlink(missing_ok=True)
        destination.write_text('later owner')
        repeated = self.replay.recover_replay_cleanup('unused', binding['binding_id'], recovered['state_revision'])
        self.assertFalse(marker.exists(), 'terminal recovery must not execute cleanup again')
        self.assertEqual(destination.read_text(), 'later owner')
        self.assertEqual(repeated, recovered)


class ReviewMetadataTests(unittest.TestCase):
    setUp = test_review_runners.ReviewPackageTests.setUp
    package = test_review_runners.ReviewPackageTests.package
    def test_absolute_resolved_path_is_neutralized_but_source_bound(self):
        from flowctl_lib.review_package import digest
        self.file.write_text(self.file.read_text().replace('resolved_path: pending', 'resolved_path: ' + str(self.file)))
        original = self.file.read_bytes()
        package = self.package()
        self.addCleanup(package.cleanup)
        request = json.loads(package.request_path.read_text())
        self.assertNotIn(str(self.root), package.request_path.read_text())
        self.assertEqual(next(item for item in request['manifest']['files'] if item['path'] == 'spec.md')['source_digest'], digest(original))
        self.assertEqual(next(item for item in request['manifest']['files'] if item['path'] == 'spec.md')['digest'], digest((package.workspace_path / 'spec.md').read_bytes()))

    def test_explicit_source_context_allowed_and_bound(self):
        source = self.root / 'feature.py'
        source.write_text('def feature(): return 42\n')
        package = self.package([self.file, source])
        self.addCleanup(package.cleanup)
        request = json.loads(package.request_path.read_text())
        self.assertTrue({'spec.md', 'feature.py'}.issubset({f['path'] for f in request['files']}))
        self.assertIn('source_snapshot', request['manifest'])

    def test_code_context_requires_recorded_snapshot_and_detects_source_drift(self):
        from flowctl_lib.review_package import create_review_package
        from flowctl_lib.snapshot import capture_snapshot
        self.state['current_stage'] = 'flow-code'
        from flowctl_lib.artifacts import verify_artifact
        self.file, _ = write_artifact(self.root, 'code', issue='ISSUE-2', milestone='M1', name='code.md')
        self.state['artifacts'] = {'code:M1':verify_artifact(self.file)}
        source = self.root / 'feature.py'
        source.write_text('value = 42\n')
        def package():
            return create_review_package(self.state, 'cursor', 'flow-code', 'code:M1', self.prompt, [self.file, source])
        with self.assertRaisesRegex(FlowctlError, 'CODE_SNAPSHOT_REQUIRED'):
            package()
        self.state['snapshots'] = {'code:M1': capture_snapshot(self.root)}
        package().cleanup()
        source.write_text('value = 43\n')
        with self.assertRaisesRegex(FlowctlError, 'CODE_SNAPSHOT_DRIFT'):
            package()

    def test_context_excludes_ignored_sensitive_symlink_and_oversize_files(self):
        source = self.root / 'context.txt'
        (self.root / '.gitignore').write_text('ignored.txt\n')
        ignored = self.root / 'ignored.txt'
        ignored.write_text('safe text')
        secret = self.root / 'credentials.txt'
        secret.write_text('safe text')
        linked = self.root / 'linked.txt'
        linked.symlink_to(self.file)
        package = self.package([self.file, ignored, secret, linked])
        self.addCleanup(package.cleanup)
        self.assertTrue((package.workspace_path / 'ignored.txt').exists())
        self.assertFalse((package.workspace_path / 'credentials.txt').exists())
        self.assertFalse((package.workspace_path / 'linked.txt').exists())
        for text in ('password="credential-lure"', 'x' * (4 * 1024 * 1024 + 1)):
            source.write_text(text)
            package = self.package([self.file, source])
            self.assertFalse((package.workspace_path / 'context.txt').exists())
            package.cleanup()


class ReviewConsumptionTests(unittest.TestCase):
    def test_validate_then_execute_transmits_exact_multifile_set_once(self):
        from flowctl_lib.state import load_state
        from flowctl_lib.reviews import begin_review, submit_review, run_cursor_review, run_ibrain_review
        from flowctl_lib.review_package import validate_review_manifest
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = test_flowctl.ReviewAndHandoffTests()._state_with_spec(root)
            state = load_state(state_path)
            attempt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED', 'findings':[], 'reviewed_digest':attempt['artifact_digest']}))
            submit_review(state_path, attempt['attempt_id'], report, attempt['state_revision'])
            prompt, source, evidence = root / 'prompt.txt', root / 'feature.py', root / 'evidence.txt'
            prompt.write_text('Review bounded implementation context')
            source.write_text('def feature(): return 42\n')
            evidence.write_text('Fixture behavior verified')
            # Exercise real Cursor capability failure and the controller's two
            # runtime attempts before selecting the actual byte-only fallback.
            cursor_runner = test_review_runners.ROOT.parent / 'skills/cursor-review/scripts/cursor_review.py'
            for _ in range(2):
                state = load_state(state_path)
                failed = run_cursor_review(state_path, 'spec:M1', prompt, cursor_runner, 'fake', 'high', 5, state['state_revision'])
                self.assertEqual(failed['classification'], 'RUN_ERROR')
            state = load_state(state_path)
            paths = [state['artifacts']['spec:M1']['path'], str(source), str(evidence)]
            manifest = root / 'review-manifest.json'
            manifest.write_text(json.dumps(dict(backend='ibrain', stage='flow-spec', artifact_key='spec:M1', prompt_path=str(prompt), paths=paths)))
            bound = validate_review_manifest(state_path, manifest, state['state_revision'])
            runner = test_review_runners.ROOT.parent / 'skills/ibrain-review/scripts/ibrain_review.py'
            def run(binding_id=None):
                return run_ibrain_review(state_path, 'spec:M1', prompt, runner, 5, load_state(state_path)['state_revision'], binding_id=binding_id)
            with patch('flowctl_lib.reviews._run_bound_package') as no_send:
                with self.assertRaisesRegex(FlowctlError, 'REVIEW_BINDING_REQUIRED'):
                    run()
                original_source = source.read_text()
                source.write_text('def feature(): return 43\n')
                with self.assertRaisesRegex(FlowctlError, 'REVIEW_PACKAGE_DRIFT'):
                    run(bound['binding_id'])
                source.write_text(original_source)
                no_send.assert_not_called()
            module = test_review_runners.ReviewRunnerTests().load_runner('ibrain')
            real_run = subprocess.run
            def execute(command, **kwargs):
                if command[0] == 'git':
                    return real_run(command, **kwargs)
                if '--check-capabilities' in command:
                    return subprocess.CompletedProcess(command, 0, json.dumps(module.capabilities()), '')
                args = SimpleNamespace(request_file=command[4], expected_request_digest=command[command.index('--expected-request-digest') + 1],
                    workspace=command[command.index('--workspace') + 1], model='glm-5.3', timeout_seconds=5)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = module.run_review(args, 'fixture-key')
                return subprocess.CompletedProcess(command, code, stdout.getvalue(), '')
            with patch('flowctl_lib.reviews.subprocess.run', side_effect=execute), patch.object(module, 'request_json', return_value={'status':'completed','output_text':report.read_text()}) as outbound:
                result = run(bound['binding_id'])
                payload = outbound.call_args.kwargs['payload']
                self.assertEqual(set(payload), {'model','input','stream','instructions','tools'})
                sent = [json.loads(payload['input'][0]['content'].split('REVIEW MANIFEST\n')[1])]
            self.assertEqual(result['status'], 'PASSED')
            self.assertTrue({Path(p).name for p in paths}.issubset({f['path'] for f in sent[0]['files']}))
            self.assertEqual(next(f['digest'] for f in sent[0]['files'] if f['path'] == 'feature.py'), 'sha256:' + hashlib.sha256(source.read_bytes()).hexdigest())
            with patch('flowctl_lib.reviews._run_bound_package') as send:
                with self.assertRaisesRegex(FlowctlError, 'AUTHORIZATION_BINDING_STALE'):
                    run(bound['binding_id'])
                send.assert_not_called()
