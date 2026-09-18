from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest import mock

from resume.scripts import resume


def write_session(root: Path, relative_name: str, payload: dict) -> Path:
    path = root / relative_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": payload}) + "\n",
        encoding="utf-8",
    )
    return path


def write_records(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


class ResumeSkillTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_resolve_session_file_accepts_only_matching_primary(self):
        root = Path(self.tempdir.name)
        primary = write_session(
            root,
            "nested/primary.jsonl",
            {
                "id": "thread-1",
                "session_id": "resume-1",
                "thread_source": "user",
                "source": "cli",
                "cwd": str(root),
            },
        )
        write_session(
            root,
            "child.jsonl",
            {
                "id": "thread-1",
                "session_id": "resume-1",
                "thread_source": "subagent",
                "source": {"subagent": {}},
                "cwd": str(root),
            },
        )

        self.assertEqual(
            resume.resolve_session_file(root, "thread-1"),
            (primary, {
                "id": "thread-1",
                "session_id": "resume-1",
                "thread_source": "user",
                "source": "cli",
                "cwd": str(root),
            }),
        )

    def test_resolve_session_file_rejects_missing_or_duplicate_primary(self):
        root = Path(self.tempdir.name)

        with self.assertRaises(resume.ResumeError):
            resume.resolve_session_file(root, "missing")

        write_session(
            root,
            "first.jsonl",
            {
                "id": "thread-2",
                "session_id": "resume-2",
                "thread_source": "user",
                "source": "cli",
            },
        )
        write_session(
            root,
            "second.jsonl",
            {
                "id": "thread-2",
                "session_id": "resume-2b",
                "thread_source": "user",
                "source": "cli",
            },
        )

        with self.assertRaises(resume.ResumeError):
            resume.resolve_session_file(root, "thread-2")

    def test_resolve_session_file_requires_exact_primary_metadata(self):
        root = Path(self.tempdir.name)
        invalid_payloads = [
            {
                "id": "thread-3",
                "session_id": "resume-3",
                "thread_source": "subagent",
                "source": "cli",
            },
            {
                "id": "thread-3",
                "session_id": "resume-3",
                "thread_source": "user",
                "source": {"subagent": {}},
            },
            {
                "id": "thread-3",
                "session_id": "",
                "thread_source": "user",
                "source": "cli",
            },
            {
                "id": "other-thread",
                "session_id": "resume-3",
                "thread_source": "user",
                "source": "cli",
            },
        ]
        for index, payload in enumerate(invalid_payloads):
            write_session(root, f"invalid-{index}.jsonl", payload)

        with self.assertRaises(resume.ResumeError):
            resume.resolve_session_file(root, "thread-3")

    def test_resolve_session_file_ignores_invalid_first_records(self):
        root = Path(self.tempdir.name)
        malformed = root / "malformed.jsonl"
        malformed.write_text("not-json\n", encoding="utf-8")
        no_payload = root / "no-payload.jsonl"
        no_payload.write_text(json.dumps({"type": "message"}) + "\n", encoding="utf-8")
        primary = write_session(
            root,
            "valid.jsonl",
            {
                "id": "thread-4",
                "session_id": "resume-4",
                "thread_source": "user",
                "source": "cli",
            },
        )

        self.assertEqual(
            resume.resolve_session_file(root, "thread-4")[0],
            primary,
        )

    def test_directories_from_session_collects_literal_exec_directories_in_order(self):
        root = Path(self.tempdir.name)
        primary = root / "primary"
        first_workdir = root / "first-workdir"
        added_directory = root / "added-directory"
        equals_directory = root / "directory with spaces"
        second_workdir = root / "second-workdir"
        postfix_division_directory = root / "postfix-division-directory"
        for directory in (
            primary,
            first_workdir,
            added_directory,
            equals_directory,
            second_workdir,
            postfix_division_directory,
        ):
            directory.mkdir()
        session = root / "session.jsonl"
        first_options = {
            "workdir": str(first_workdir),
            "cmd": 'echo "quoted" \\backslash {}',
        }
        source = (
            f"tools.exec_command({json.dumps(first_options)}); "
            f"tools.exec_command({json.dumps({'cmd': f'codex resume session-id --add-dir {added_directory}'})}); "
            f"tools.exec_command({json.dumps({'cmd': f'codex resume session-id --add-dir={shlex.quote(str(equals_directory))}'})}); "
            f"tools.exec_command({json.dumps({'workdir': str(second_workdir)})}); "
            f"let n = 1; n++ / await tools.exec_command({json.dumps({'workdir': str(postfix_division_directory)})});"
        )
        write_records(
            session,
            [{
                "type": "custom_tool_call",
                "payload": {"item": {"type": "custom_tool_call", "name": "exec", "input": source}},
            }],
        )

        self.assertEqual(
            resume.directories_from_session(session, primary),
            [
                first_workdir,
                added_directory,
                equals_directory,
                second_workdir,
                postfix_division_directory,
            ],
        )

    def test_directories_from_session_ignores_nonliteral_or_invalid_candidates(self):
        root = Path(self.tempdir.name)
        primary = root / "primary"
        accepted = root / "accepted"
        duplicate = root / "duplicate"
        message_directory = root / "message-directory"
        other_tool_directory = root / "other-tool-directory"
        dynamic_directory = root / "dynamic-directory"
        non_resume_directory = root / "non-resume-directory"
        malformed_command_directory = root / "malformed-command-directory"
        string_directory = root / "string-directory"
        regex_directory = root / "regex-directory"
        relative_directory = root / "relative-directory"
        file_path = root / "not-a-directory"
        for directory in (
            primary,
            accepted,
            duplicate,
            message_directory,
            other_tool_directory,
            dynamic_directory,
            non_resume_directory,
            malformed_command_directory,
            string_directory,
            regex_directory,
            relative_directory,
        ):
            directory.mkdir()
        file_path.touch()
        missing = root / "missing"
        session = root / "session.jsonl"
        regex_options = json.dumps({"workdir": str(regex_directory)}).replace("/", r"\/")
        malformed_command = f'codex resume --add-dir "{malformed_command_directory}'
        ignored_source = " ".join([
            f"tools.exec_command({json.dumps({'workdir': str(primary)})})",
            f"tools.exec_command({json.dumps({'workdir': relative_directory.name})})",
            f"tools.exec_command({json.dumps({'workdir': str(missing)})})",
            f"tools.exec_command({json.dumps({'workdir': str(file_path)})})",
            f"tools.exec_command({json.dumps({'workdir': str(dynamic_directory)})} + options)",
            f"tools.exec_command({json.dumps({'cmd': f'echo codex resume --add-dir {non_resume_directory}'})})",
            f"tools.exec_command({json.dumps({'cmd': malformed_command})})",
            json.dumps(f"tools.exec_command({json.dumps({'workdir': str(string_directory)})})"),
            f"const pattern = /tools.exec_command({regex_options})/;",
        ])
        accepted_source = (
            f"tools.exec_command({json.dumps({'workdir': str(accepted)})}); "
            f"tools.exec_command({json.dumps({'cmd': f'codex resume session-id --add-dir {duplicate} --add-dir {accepted}'})})"
        )
        write_records(
            session,
            [
                {"payload": {"item": {"type": "message", "input": f"tools.exec_command({json.dumps({'workdir': str(message_directory)})})"}}},
                {"payload": {"item": {"type": "custom_tool_call", "name": "other", "input": f"tools.exec_command({json.dumps({'workdir': str(other_tool_directory)})})"}}},
                {"payload": {"item": {"type": "custom_tool_call", "name": "exec", "input": ignored_source}}},
                {"payload": {"item": {"type": "custom_tool_call", "name": "exec", "input": accepted_source}}},
            ],
        )

        self.assertEqual(
            resume.directories_from_session(session, primary),
            [accepted, duplicate],
        )

    def test_directories_from_session_accepts_response_item_payload_shape(self):
        root = Path(self.tempdir.name)
        primary = root / "primary"
        response_item_workdir = root / "response-item-workdir"
        primary.mkdir()
        response_item_workdir.mkdir()
        session = root / "session.jsonl"
        source = f"tools.exec_command({json.dumps({'workdir': str(response_item_workdir)})})"
        write_records(
            session,
            [{
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "input": source,
                    "call_id": "call-1",
                },
            }],
        )

        self.assertEqual(
            resume.directories_from_session(session, primary),
            [response_item_workdir],
        )

    def test_directories_from_session_accepts_nested_response_item_payload_shape(self):
        root = Path(self.tempdir.name)
        primary = root / "primary"
        nested_response_item_workdir = root / "nested-response-item-workdir"
        primary.mkdir()
        nested_response_item_workdir.mkdir()
        session = root / "session.jsonl"
        source = f"tools.exec_command({json.dumps({'workdir': str(nested_response_item_workdir)})})"
        write_records(
            session,
            [{
                "type": "response_item",
                "payload": {
                    "item": {
                        "type": "custom_tool_call",
                        "name": "exec",
                        "input": source,
                    },
                },
            }],
        )

        self.assertEqual(
            resume.directories_from_session(session, primary),
            [nested_response_item_workdir],
        )


class ResumeCommandTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def test_render_zero_one_and_multiple_directories(self):
        first = self.root / "first directory"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        for directories, expected in (
            ([], f'cd -- "{self.root}"\ncodex resume "session-1"'),
            ([first], f'cd -- "{self.root}"\ncodex resume "session-1" \\\n  --add-dir "{first}"'),
            ([first, second], f'cd -- "{self.root}"\ncodex resume "session-1" \\\n  --add-dir "{first}" \\\n  --add-dir "{second}"'),
        ):
            with self.subTest(directories=directories):
                output = resume.render_command(self.root, "session-1", directories)
                self.assertEqual(output, expected)
                self.assertNotIn("--last", output)

    def test_render_escapes_shell_metacharacters_in_every_argument(self):
        primary = self.root / 'primary"$`\\end'
        added = self.root / 'added"$`\\end'
        primary.mkdir()
        added.mkdir()
        output = resume.render_command(primary, 'session"$`\\end', [added])
        self.assertEqual(
            output,
            f'cd -- "{self.root}/primary' + r'\"\$\`\\end"' + '\n'
            + r'codex resume "session\"\$\`\\end"' + ' \\\n'
            + f'  --add-dir "{self.root}/added' + r'\"\$\`\\end"',
        )

    def test_render_rejects_newline_and_carriage_return_in_paths(self):
        for character in ("\n", "\r"):
            bad = self.root / f"bad{character}directory"
            bad.mkdir()
            for primary, added in ((bad, []), (self.root, [bad])):
                with self.subTest(primary=primary, added=added):
                    with self.assertRaises(resume.ResumeError):
                        resume.render_command(primary, "session-1", added)

    def test_render_requires_existing_absolute_primary_directory(self):
        file_path = self.root / "file"
        file_path.touch()
        for primary in (Path("."), self.root / "missing", file_path):
            with self.subTest(primary=primary):
                with self.assertRaises(resume.ResumeError):
                    resume.render_command(primary, "session-1", [])

    def test_render_rejects_unsafe_session_ids(self):
        for session_id in ("", "--last", "session\nnext", "session\rnext", "session\0next"):
            with self.subTest(session_id=session_id):
                with self.assertRaises(resume.ResumeError):
                    resume.render_command(self.root, session_id, [])

    def invoke_main(self, thread_id="thread-1"):
        stdout, stderr = io.StringIO(), io.StringIO()
        environment = {} if thread_id is None else {"CODEX_THREAD_ID": thread_id}
        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(Path, "home", return_value=self.root),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = resume.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def create_primary(self, cwd):
        return write_session(
            self.root / ".codex" / "sessions",
            "nested/primary.jsonl",
            {"id": "thread-1", "session_id": "resume-1", "thread_source": "user", "source": "cli", "cwd": cwd},
        )

    def test_main_prints_only_command_using_primary_metadata_and_history(self):
        primary = self.root / "primary"
        added = self.root / "added"
        primary.mkdir()
        added.mkdir()
        session = self.create_primary(str(primary))
        with session.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"payload": {"item": {
                "type": "custom_tool_call", "name": "exec",
                "input": f"tools.exec_command({json.dumps({'workdir': str(added)})})",
            }}}) + "\n")

        status, stdout, stderr = self.invoke_main()

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, f'cd -- "{primary}"\ncodex resume "resume-1" \\\n  --add-dir "{added}"\n')

    def test_main_requires_thread_id(self):
        status, stdout, stderr = self.invoke_main(thread_id=None)
        self.assertNotEqual(status, 0)
        self.assertEqual(stdout, "")
        self.assertIn("CODEX_THREAD_ID", stderr)

    def test_main_reports_missing_and_ambiguous_sessions(self):
        for duplicate in (False, True):
            if duplicate:
                original = self.create_primary(str(self.root))
                original.with_name("duplicate.jsonl").write_text(original.read_text(), encoding="utf-8")
            with self.subTest(duplicate=duplicate):
                status, stdout, stderr = self.invoke_main()
                self.assertNotEqual(status, 0)
                self.assertEqual(stdout, "")
                self.assertIn("expected exactly one primary session", stderr)

    def test_main_rejects_invalid_primary_metadata_cwd(self):
        for cwd in (None, 42, "", "relative", str(self.root / "missing")):
            self.create_primary(cwd)
            with self.subTest(cwd=cwd):
                status, stdout, stderr = self.invoke_main()
                self.assertNotEqual(status, 0)
                self.assertEqual(stdout, "")
                self.assertIn("cwd", stderr)


if __name__ == "__main__":
    unittest.main()
