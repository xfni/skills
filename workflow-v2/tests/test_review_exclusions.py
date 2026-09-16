"""Exclude data from transport, never from source mutation detection."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_flowctl as fixtures
from flowctl_lib.review_workspace import create_review_view, capture_review_snapshot, verify_review_snapshot
from flowctl_lib.review_package import create_review_package, validate_review_manifest
from flowctl_lib.state import load_state
from flowctl_lib.errors import FlowctlError


class ReviewExclusionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / 'repo'
        self.root.mkdir()
        self.state_path = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)
        self.destination = Path(tmp.name) / 'view'
        (self.root / 'tests/data').mkdir(parents=True)
        (self.root / 'tests/data/samples.jsonl').write_text('{"question":"PRIVATE_DATA_SENTINEL"}\n')
        (self.root / 'tests/test_service.py').write_text('assert 1 == 1\n')
        (self.root / 'tests/database.py').write_text('answer = 42\n')
        self.exclusions = [{'path': 'tests/data', 'kind': 'directory', 'reason': 'production test inputs'}]
        self.prompt = self.root / 'prompt.txt'
        self.prompt.write_text('Review behavior and tests; disclose excluded input coverage.')

    def test_directory_exclusion_is_component_exact_and_before_copy(self):
        view = create_review_view(self.root, self.destination, exclusions=self.exclusions)
        self.assertFalse((self.destination / 'tests/data/samples.jsonl').exists())
        self.assertTrue((self.destination / 'tests/test_service.py').exists())
        self.assertTrue((self.destination / 'tests/database.py').exists())
        self.assertIn('tests/data/samples.jsonl', [item['path'] for item in view['excluded']])
        self.assertNotIn('PRIVATE_DATA_SENTINEL', json.dumps(view))

    def test_exact_file_exclusion_preserves_other_files(self):
        create_review_view(self.root, self.destination, exclusions=[{
            'path': 'tests/data/samples.jsonl', 'kind': 'file', 'reason': 'production test inputs'}])
        self.assertFalse((self.destination / 'tests/data/samples.jsonl').exists())
        self.assertTrue((self.destination / 'tests/test_service.py').exists())

    def test_excluded_data_remains_frozen(self):
        before = capture_review_snapshot(self.root, self.state_path)
        create_review_view(self.root, self.destination, self.state_path, exclusions=self.exclusions)
        (self.root / 'tests/data/samples.jsonl').write_text('changed')
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_WORKTREE_MUTATED'):
            verify_review_snapshot(self.root, self.state_path, before)

    def test_package_binds_exclusions_for_both_backends(self):
        for backend in ('cursor', 'ibrain'):
            with self.subTest(backend=backend):
                package = create_review_package(load_state(self.state_path), backend, 'flow-spec',
                          'spec:M1', self.prompt, exclusions=self.exclusions)
                try:
                    self.assertEqual(self.exclusions, package.manifest['exclusions'])
                    self.assertFalse((package.root / 'workspace/tests/data/samples.jsonl').exists())
                    package.verify_source(self.root)
                finally:
                    package.cleanup()

    def test_required_target_cannot_be_excluded(self):
        state = load_state(self.state_path)
        relative = str(Path(state['artifacts']['spec:M1']['path']).relative_to(self.root))
        with self.assertRaisesRegex(FlowctlError, 'REVIEW_REQUIRED_INPUT_EXCLUDED'):
            create_review_package(state, 'cursor', 'flow-spec', 'spec:M1', self.prompt,
                                  exclusions=[{'path': relative, 'kind': 'file', 'reason': 'data'}])

    def test_root_absolute_and_parent_escape_are_rejected(self):
        for path in ('.', '..', '../other', str(self.root), '/tmp/outside'):
            with self.subTest(path=path), self.assertRaises(FlowctlError):
                create_review_view(self.root, self.destination / str(len(path)), exclusions=[{
                    'path': path, 'kind': 'directory', 'reason': 'data'}])

    def test_validated_binding_keeps_exclusion_inputs(self):
        state = load_state(self.state_path)
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'backend': 'cursor', 'stage': 'flow-spec', 'artifact_key': 'spec:M1',
                                       'prompt_path': str(self.prompt), 'exclusions': self.exclusions}))
        validated = validate_review_manifest(self.state_path, manifest, state['state_revision'])
        binding = next(b for b in load_state(self.state_path)['authorizations']['external_review']['bindings']
                       if b['binding_id'] == validated['binding_id'])
        self.assertEqual(self.exclusions, binding['input_manifest']['exclusions'])

    def test_actual_bound_review_passes_without_dataset_transport(self):
        from flowctl_lib.reviews import begin_review, submit_review, run_cursor_review
        state = load_state(self.state_path)
        attempt = begin_review(self.state_path, 'gpt', 'flow-spec', 'spec:M1', 'gpt-6-astra', 'medium', state['state_revision'])
        report = self.root / 'gpt-report.json'
        report.write_text(json.dumps({'status': 'PASSED', 'findings': []}))
        submit_review(self.state_path, attempt['attempt_id'], report, attempt['state_revision'])
        state = load_state(self.state_path)
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'backend': 'cursor', 'stage': 'flow-spec', 'artifact_key': 'spec:M1',
                                       'prompt_path': str(self.prompt), 'exclusions': self.exclusions}))
        bound = validate_review_manifest(self.state_path, manifest, state['state_revision'])
        def transport(package, *args):
            self.assertFalse((package.workspace_path / 'tests/data/samples.jsonl').exists())
            self.assertNotIn('PRIVATE_DATA_SENTINEL', package.request_path.read_text())
            output = json.dumps({'status': 'PASSED', 'findings': [],
                                 'reviewed_digest': package.manifest['artifact_digest']})
            return 0, 'FLOW_REVIEW_REPORT_BEGIN\n' + output + '\nFLOW_REVIEW_REPORT_END', '', False
        with patch('flowctl_lib.reviews._run_bound_package', side_effect=transport):
            result = run_cursor_review(self.state_path, 'spec:M1', self.prompt, self.root / 'unused-runner.py',
                         'cursor', 'high', 5, bound['state_revision'], binding_id=bound['binding_id'])
        self.assertEqual('PASSED', result['status'], result.get('reason'))
        self.assertEqual('review:consistency', load_state(self.state_path)['pending_action'])

    def test_reason_changes_package_binding_even_with_identical_view(self):
        state = load_state(self.state_path)
        first = create_review_package(state, 'cursor', 'flow-spec', 'spec:M1', self.prompt, exclusions=self.exclusions)
        second = create_review_package(state, 'cursor', 'flow-spec', 'spec:M1', self.prompt,
                     exclusions=[{**self.exclusions[0], 'reason': 'embedded production samples'}])
        try:
            self.assertEqual(first.manifest['files'], second.manifest['files'])
            self.assertNotEqual(first.digest, second.digest)
        finally:
            first.cleanup(); second.cleanup()

    def test_glob_is_not_silently_accepted_as_a_literal_exclusion(self):
        with self.assertRaisesRegex(FlowctlError, 'INVALID_REVIEW_EXCLUSIONS'):
            create_review_view(self.root, self.destination, exclusions=[{
                'path': 'tests/data/*', 'kind': 'file', 'reason': 'data'}])
