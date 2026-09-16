import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flowctl_lib.errors import FlowctlError


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'flowctl_lib/replay.py').exists(), 'replay implementation missing')
        self.replay = importlib.import_module('flowctl_lib.replay')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('private/\n')
        (self.root / 'private').mkdir(mode=0o700)
        self.lure = 'RAW_' + 'PRIVATE_CUSTOMER_93841'
        self.state = dict(issue_id='ISSUE-2', run_id='run-2', worktree_path=str(self.root),
                          state_revision=0, authorizations={'production_replay':dict(
                              status='GRANTED', mode='SANITIZED_LOCAL_REPLAY', authorization_id='auth',
                              revision=1, issue_id='ISSUE-2', run_id='run-2', worktree_path=str(self.root), bindings=[])})
        self.commands = {}
        self.set_command('acquisition', 'import sys\nsys.stdout.write("RAW_" + "PRIVATE_CUSTOMER_93841\\n")\n')
        self.set_command('sanitizer', 'import sys\nfor line in sys.stdin: print(\'{"count":1,"category":"safe"}\', flush=True)\n')
        self.set_command('cleanup', 'pass\n')
        self.profile = dict(commands=self.commands, sanitizer_version='1', streaming=True,
            cache_disabled=True, body_logging_disabled=True, redacted_errors=True,
            stderr='discard', fields={'count':{'type':'integer','minimum':0,'maximum':10},
                                      'category':{'enum':['safe']}},
            removed_fields=['customer_id'], transformations=['remove_identifiers'],
            field_categories=['aggregate'], source_id='fixture', time_window=['2026-09-01','2026-09-02'])
        self.manifest = dict(profile='fixture-v1', **self.profile, destination='private/replay.jsonl',
            max_records=2, expected_records=1, max_bytes=1024, timeout_seconds=2,
            retention_deadline='2099-01-01T00:00:00Z')
        self.manifest_path = self.root / 'manifest.json'
        self.addCleanup(patch.stopall)
        patch.dict(self.replay.TRUSTED_PROFILES, {'fixture-v1':self.profile}).start()
        @contextlib.contextmanager
        def locked(*args):
            yield self.state
        patch('flowctl_lib.state.locked_state', locked).start()
        patch('flowctl_lib.state.reject_if_paused').start()
        patch('flowctl_lib.state.audit_state').start()
        def commit(path, state, event, data):
            self.assertNotIn(self.lure, json.dumps(data))
            state['state_revision'] += 1
            return state
        patch('flowctl_lib.state.commit_state', commit).start()

    def set_command(self, role, source):
        path = self.root / (role + '.py')
        path.write_text(source)
        self.commands[role] = dict(argv=[str(path)], digest='sha256:' + hashlib.sha256(source.encode()).hexdigest())

    def bind(self):
        self.approve_plan()
        self.manifest_path.write_text(json.dumps(self.manifest))
        return self.replay.validate_replay_manifest(self.root / 'state.json', self.manifest_path, 0)

    def approve_plan(self):
        from test_flowctl import write_artifact
        from flowctl_lib.artifacts import verify_artifact
        from flowctl_lib.review_package import canonical, digest
        constraints = {k:v for k,v in self.manifest.items() if k not in self.replay.PLAN_BINDING_KEYS}
        requirement, ref = write_artifact(self.root, 'requirement', issue='ISSUE-2')
        plan, plan_ref = write_artifact(self.root, 'plan', issue='ISSUE-2', milestone='M1', upstream={'requirement':ref},
            integration_scenarios={'schema_version':1, 'scenarios':[{'scenario_id':'TESTCASE-REPLAY',
                'production_dependency':{'required':True, 'reason':'Production distribution', 'missing_assurance':'Distribution behavior',
                    'owner':'integration', 'remediation':'Replay sanitized fixture', 'replay_manifest_digest':digest(canonical(constraints))}}]})
        self.state.update(current_stage='flow-integration', active_milestone='M1',
                          artifacts={'requirement':verify_artifact(requirement), 'plan:M1':verify_artifact(plan)})
        self.manifest.update(milestone_id='M1', scenario_id='TESTCASE-REPLAY', plan_revision=plan_ref['revision'], plan_digest=plan_ref['digest'])

    def run_replay(self):
        binding = self.bind()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = self.replay.run_replay(self.root / 'state.json', binding['binding_id'], self.state['state_revision'])
        self.assertNotIn(self.lure, json.dumps(result) + stdout.getvalue() + stderr.getvalue())
        for path in self.root.rglob('*'):
            if path.is_file():
                self.assertNotIn(self.lure.encode(), path.read_bytes(), str(path))
        return result

    def test_success_and_single_use(self):
        result = self.run_replay()
        self.assertEqual(result['status'], 'PASSED')
        self.assertEqual(result['records'], 1)
        self.assertEqual(json.loads((self.root / 'private/replay.jsonl').read_text()), {'count':1,'category':'safe'})
        self.assertEqual((self.root / 'private/replay.jsonl').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FlowctlError):
            self.replay.run_replay(self.root / 'state.json', result['binding_id'], self.state['state_revision'])

    def test_untrusted_shell_capabilities_and_destinations_rejected_before_spawn(self):
        original = json.loads(json.dumps(self.manifest))
        changes = [dict(profile='arbitrary'), dict(cache_disabled=False), dict(body_logging_disabled=False),
                   dict(redacted_errors=False), dict(destination='public.jsonl'), dict(destination='../outside'),
                   dict(commands={'acquisition':'curl source | jq .'})]
        for change in changes:
            self.manifest = {**original, **change}
            with self.subTest(change=change), patch.object(self.replay.subprocess, 'Popen') as spawn:
                with self.assertRaises(FlowctlError): self.bind()
                spawn.assert_not_called()

    def test_skip_mode_rejects_run(self):
        binding = self.bind()
        self.state['authorizations']['production_replay']['mode'] = 'SKIP_PRODUCTION_REPLAY'
        with patch.object(self.replay.subprocess, 'Popen') as spawn:
            with self.assertRaises(FlowctlError):
                self.replay.run_replay(self.root / 'state.json', binding['binding_id'], 1)
            spawn.assert_not_called()

    def test_source_error_stderr_is_discarded_and_cleaned(self):
        self.set_command('acquisition', 'import sys\nsys.stderr.write("RAW_" + "PRIVATE_CUSTOMER_93841")\nsys.exit(3)\n')
        result = self.run_replay()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_mid_transform_failure_removes_staging(self):
        self.set_command('sanitizer', 'import sys\nprint(\'{"count":1,"category":"safe"}\', flush=True)\nsys.exit(4)\n')
        self.assertEqual(self.run_replay()['status'], 'BLOCKED')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_invalid_identifier_never_reaches_disk(self):
        self.set_command('sanitizer', 'import sys,json\nprint(json.dumps({"customer_id":sys.stdin.read()}))\n')
        self.assertEqual(self.run_replay()['status'], 'BLOCKED')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_count_failure_and_publish_failure_clean_outputs(self):
        self.manifest['expected_records'] = 2
        self.assertEqual(self.run_replay()['status'], 'BLOCKED')
        self.manifest['expected_records'] = 1
        with patch.object(self.replay.os, 'link', side_effect=OSError('redacted')):
            self.assertEqual(self.run_replay()['status'], 'BLOCKED')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_cleanup_failure_is_blocker(self):
        self.set_command('cleanup', 'raise SystemExit(2)\n')
        self.assertEqual(self.run_replay()['status'], 'BLOCKED_CLEANUP')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_round1_directory_swap_never_redirects_processes_or_cleanup(self):
        original = self.root / 'private'
        moved = self.root / 'moved-private'
        public = self.root / 'public'
        public.mkdir()
        marker = public / 'cleanup-target'
        marker.write_text('competitor')
        self.set_command('cleanup', 'from pathlib import Path\np=Path("cleanup-target")\nif p.exists(): p.unlink()\n')
        real_record = self.replay._record
        real_spawn = self.replay.subprocess.Popen
        process_cwds = []
        def spawn(command, **kwargs):
            if command[0] == sys.executable:
                process_cwds.append(kwargs.get('cwd'))
            return real_spawn(command, **kwargs)
        def swap(line, manifest):
            original.rename(moved)
            original.symlink_to(public, target_is_directory=True)
            return real_record(line, manifest)
        with patch.object(self.replay, '_record', side_effect=swap), patch.object(self.replay.subprocess, 'Popen', side_effect=spawn):
            result = self.run_replay()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(marker.read_text(), 'competitor')
        self.assertFalse(list(moved.iterdir()))
        self.assertEqual(list(public.iterdir()), [marker])
        self.assertEqual(process_cwds, [Path('/')] * 3)

    def test_round1_atomic_publish_preserves_racing_destination(self):
        destination = self.root / 'private/replay.jsonl'
        real_replace, real_link = self.replay.os.replace, self.replay.os.link
        def racing(operation):
            def run(*args, **kwargs):
                destination.write_text('competitor')
                return operation(*args, **kwargs)
            return run
        with patch.object(self.replay.os, 'replace', side_effect=racing(real_replace)), patch.object(self.replay.os, 'link', side_effect=racing(real_link)):
            result = self.run_replay()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(destination.read_text(), 'competitor')
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def _drift_during_record(self, change):
        real_record = self.replay._record
        def drift(line, manifest):
            change()
            return real_record(line, manifest)
        with patch.object(self.replay, '_record', side_effect=drift):
            result = self.run_replay()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result.get('ignore_proof', False))
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_round1_mode_drift_blocks_publish(self):
        self._drift_during_record(lambda: (self.root / 'private').chmod(0o755))

    def test_round1_ignore_drift_blocks_publish(self):
        self._drift_during_record(lambda: (self.root / '.gitignore').unlink())

    def test_digest_drift_before_run_rejects_before_spawn(self):
        binding = self.bind()
        (self.root / 'acquisition.py').write_text('raise SystemExit(99)')
        with patch.object(self.replay.subprocess, 'Popen') as spawn:
            with self.assertRaises(FlowctlError):
                self.replay.run_replay(self.root / 'state.json', binding['binding_id'], 1)
            spawn.assert_not_called()

    def test_cli_commands(self):
        from flowctl_lib.cli import _parser
        for args in (['replay','validate','--manifest','m'], ['replay','run','--binding-id','b'],
                     ['authorization','validate','--kind','production_replay','--manifest','m']):
            value = _parser().parse_args(args + ['--state','s','--expected-revision','1'])
            self.assertEqual(value.expected_revision, 1)

    def test_manifest_schema_exists(self):
        schema = ROOT / 'schemas/replay-manifest.schema.json'
        self.assertTrue(schema.exists())
        value = json.loads(schema.read_text())
        self.assertFalse(value['additionalProperties'])
        self.assertEqual(set(value['required']), self.replay.MANIFEST_KEYS)

    def test_interrupted_run_blocks_future_acquisition(self):
        binding = self.bind()
        with patch.object(self.replay, '_execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replay.run_replay(self.root / 'state.json', binding['binding_id'], 1)
        next_binding = self.bind()
        with patch.object(self.replay.subprocess, 'Popen') as spawn:
            with self.assertRaises(FlowctlError):
                self.replay.run_replay(self.root / 'state.json', next_binding['binding_id'], 3)
            spawn.assert_not_called()

    def test_timeout_terminates_pipe_and_removes_staging(self):
        self.set_command('acquisition', 'import time\ntime.sleep(10)\n')
        self.manifest['timeout_seconds'] = 1
        self.assertEqual(self.run_replay()['code'], 'REPLAY_TIMEOUT')
        self.assertFalse(list((self.root / 'private').iterdir()))

    def test_private_directory_symlink_and_escape_rejected(self):
        (self.root / 'link').symlink_to(self.root / 'private', target_is_directory=True)
        for destination in ['link/data.jsonl', 'private/../escape.jsonl']:
            self.manifest['destination'] = destination
            with self.assertRaises(FlowctlError): self.bind()
        self.manifest['destination'] = 'private/replay.jsonl'
        (self.root / 'private').chmod(0o755)
        with self.assertRaises(FlowctlError): self.bind()

    def test_real_controller_persists_binding_evidence_without_source_values(self):
        self.approve_plan()
        patch.stopall()
        from flowctl_lib.state import initialize_state, read_consistent_state, audit_state, commit_state
        from flowctl_lib.artifacts import verify_artifact
        from flowctl_lib.authorizations import decide_authorization
        from test_flowctl import ResumeTests
        _, paths, refs = ResumeTests._write_resume_prefix(self.root,
            integration_scenarios=self.state['artifacts']['plan:M1']['integration_scenarios'])
        state_path = self.root / 'flow-state.json'
        initialize_state(state_path, 'BCS-710', self.root, 'feature-BCS-710-replay')
        state = read_consistent_state(state_path)
        state.update(current_stage='flow-integration', active_milestone='M1',
                     artifacts={(kind + ':M1' if kind in {'spec','plan','code'} else kind):verify_artifact(path) for kind,path in paths.items()})
        state = commit_state(state_path, state, 'FIXTURE_ADMITTED', {})
        self.manifest.update(plan_digest=refs['plan']['digest'], plan_revision=refs['plan']['revision'])
        state = decide_authorization(state_path, 'production_replay', 'SANITIZED_LOCAL_REPLAY', state['state_revision'])
        self.manifest_path.write_text(json.dumps(self.manifest))
        with patch.dict(self.replay.TRUSTED_PROFILES, {'fixture-v1':self.profile}):
            binding = self.replay.validate_replay_manifest(state_path, self.manifest_path, state['state_revision'])
            result = self.replay.run_replay(state_path, binding['binding_id'], binding['state_revision'])
        self.assertEqual(result['status'], 'PASSED')
        persisted = read_consistent_state(state_path)
        audit_state(persisted)
        self.assertEqual(persisted['authorizations']['production_replay']['bindings'][0]['evidence']['status'], 'PASSED')
        ownership = persisted['authorizations']['production_replay']['bindings'][0]['cleanup_ownership']
        destination = self.root / 'private/replay.jsonl'
        self.assertEqual(ownership['destination'], {
            'device':destination.stat().st_dev, 'inode':destination.stat().st_ino,
            'digest':'sha256:' + hashlib.sha256(destination.read_bytes()).hexdigest()})
        self.assertEqual(ownership['staging'], ownership['destination'])
        events = [json.loads(line) for line in state_path.with_name('flow-events.jsonl').read_text().splitlines()]
        self.assertEqual(sum(event['event'] == 'REPLAY_OUTPUT_OWNERSHIP' for event in events), 2)
        for path in self.root.rglob('*'):
            if path.is_file(): self.assertNotIn(self.lure.encode(), path.read_bytes())
