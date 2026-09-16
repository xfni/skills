import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class WorktreeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.workspace = root / 'workspace'
        self.workspace.mkdir()
        raw = b'answer = 42\n'
        (self.workspace / 'caller.py').write_bytes(raw)
        self.report = {'status':'PASSED', 'findings':[], 'reviewed_digest':'sha256:' + 'a' * 64}
        data = {'schema_version':2, 'capabilities':{'workspace_exploration':True,'write_tools':False},
                'prompt':'Check callers independently.', 'manifest':{'artifact_digest':self.report['reviewed_digest']},
                'files':[{'path':'caller.py','digest':'sha256:' + hashlib.sha256(raw).hexdigest()}]}
        request = root / 'request.json'
        request.write_text(json.dumps(data))
        self.args = SimpleNamespace(request_file=str(request), workspace=str(self.workspace),
            expected_request_digest='sha256:' + hashlib.sha256(request.read_bytes()).hexdigest(),
            model='glm-5.3', effort='high', timeout_seconds=5, poll_seconds=0.01)

    def load(self, backend):
        path = ROOT / 'skills' / (backend + '-review') / 'scripts' / (backend + '_review.py')
        spec = importlib.util.spec_from_file_location(backend + '_worktree_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_ibrain_function_call_reads_frozen_file_and_continues_to_report(self):
        runner = self.load('ibrain')
        responses = [
            {'status':'completed','output':[{'type':'function_call','name':'read_file',
                'call_id':'call-1','arguments':'{"path":"caller.py"}'}]},
            {'status':'completed','output_text':json.dumps(self.report)},
        ]
        stdout = io.StringIO()
        with patch.object(runner, 'request_json', side_effect=responses) as send, contextlib.redirect_stdout(stdout):
            self.assertEqual(0, runner.run_review(self.args, 'private-key'))
        second_input = send.call_args_list[1].kwargs['payload']['input']
        result = next(item for item in second_input if item.get('type') == 'function_call_output')
        self.assertIn('answer = 42', result['output'])
        self.assertEqual(1, stdout.getvalue().count('FLOW_REVIEW_REPORT_BEGIN'))
        self.assertEqual('answer = 42\n', (self.workspace / 'caller.py').read_text())

    def test_ibrain_tools_reject_escape_and_have_no_write_or_shell_operation(self):
        runner = self.load('ibrain')
        manifest = json.loads(Path(self.args.request_file).read_text())
        with self.assertRaises(ValueError):
            runner.explore_workspace(self.workspace, manifest['files'], 'read_file', {'path':'../request.json'})
        with self.assertRaises(ValueError):
            runner.explore_workspace(self.workspace, manifest['files'], 'shell', {'command':'touch caller.py'})
        names = {tool['name'] for tool in runner.REVIEW_TOOLS}
        self.assertEqual({'list_files','read_file','search'}, names)

    def test_cursor_sdk_receives_frozen_cwd_and_only_read_tools(self):
        runner = self.load('cursor')
        class Options:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        options = []
        agent = SimpleNamespace(send=lambda *args: SimpleNamespace(id='run-1'), agent_id='agent-1')
        client = SimpleNamespace(agents=SimpleNamespace(
            create=lambda value: options.append(value) or agent,
            get_run=lambda _: SimpleNamespace(status='finished',result=json.dumps(self.report))))
        class Bridge:
            def __enter__(self): return client
            def __exit__(self, *args): pass
        sdk = SimpleNamespace(AgentOptions=Options, LocalAgentOptions=Options,
            CustomTool=Options,
            ModelSelection=Options, ModelParameterValue=Options, SendOptions=Options,
            Client=SimpleNamespace(launch_bridge=lambda **kwargs: Bridge()))
        stdout = io.StringIO()
        with patch.dict(sys.modules, {'cursor_sdk':sdk}), contextlib.redirect_stdout(stdout):
            self.assertEqual(0, runner.run_review(self.args, 'private-key'))
        self.assertEqual(str(self.workspace), options[0].local.cwd)
        self.assertEqual([], options[0].tools)
        self.assertEqual({'list_files','read_file','search'}, set(options[0].local.custom_tools))
        read = options[0].local.custom_tools['read_file']
        self.assertIn('answer = 42', json.dumps(read.execute({'path':'caller.py'})))
        self.assertEqual({'error':'READ_ONLY_SCOPE_REJECTED'}, read.execute({'path':'../request.json'}))
        self.assertEqual('plan', options[0].mode)
        self.assertEqual(1, stdout.getvalue().count('FLOW_REVIEW_REPORT_BEGIN'))

    def test_real_cursor_sdk_wire_disables_builtins_and_registers_custom_tools(self):
        try:
            import cursor_sdk
        except ImportError:
            self.skipTest('requires installed Cursor SDK runtime; no network used')
        runner = self.load('cursor')
        options = []
        agent = SimpleNamespace(send=lambda *args: SimpleNamespace(id='run-1'))
        client = SimpleNamespace(agents=SimpleNamespace(
            create=lambda value: options.append(value) or agent,
            get_run=lambda _: SimpleNamespace(status='finished', result=json.dumps(self.report))))
        class Bridge:
            def __enter__(self): return client
            def __exit__(self, *args): pass
        with patch.object(cursor_sdk.Client, 'launch_bridge', return_value=Bridge()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, runner.run_review(self.args, 'private-key'))
        wire = options[0].to_json()
        self.assertEqual({'names':[]}, wire['tools'])
        self.assertEqual({'list_files','read_file','search'}, set(wire['local']['customTools']))
        self.assertEqual(['SETTING_SOURCE_PROJECT'], wire['local']['settingSources'])
