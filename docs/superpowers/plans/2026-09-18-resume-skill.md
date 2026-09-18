# Resume Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicit-only global `$resume` skill that safely prints a multi-line `codex resume` command for the active primary Codex conversation.

**Architecture:** Keep the skill package small: `SKILL.md` instructs manual invocation, `agents/openai.yaml` disables implicit selection, and one stdlib-only Python helper reads session JSONL files. The helper binds to `CODEX_THREAD_ID`, parses only literal `tools.exec_command` JSON objects from executed `exec` records, and renders a safely quoted command block without ever launching Codex.

**Tech Stack:** Markdown, YAML, Python 3 standard library (`argparse`, `json`, `os`, `pathlib`, `shlex`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-09-18-resume-skill-design.md`

## Global Constraints

- Install the verified package as `~/.codex/skills/resume`.
- Set `policy.allow_implicit_invocation: false`; invoke only as `$resume`.
- Require `CODEX_THREAD_ID`; select exactly one session with matching `payload.id`, a non-empty `payload.session_id`, `thread_source: user`, and `source: cli`.
- Read only `custom_tool_call` records named `exec`; accept literal `workdir` and literal `codex resume ... --add-dir` values only.
- Keep only existing absolute directories, omit the primary cwd, never emit `--last`, and never launch Codex.
- Print `cd -- "..."` followed by a safely double-quoted, multi-line resume command; reject paths containing newlines.

---

## File Structure

- Create: `resume/SKILL.md` — concise manual workflow and failure boundaries.
- Create: `resume/agents/openai.yaml` — UI metadata plus explicit-only policy.
- Create: `resume/scripts/resume.py` — deterministic read-only session resolver and command renderer.
- Create: `tests/test_resume_skill.py` — stdlib fixture tests for the helper.

### Task 1: Define the tested helper contract

**Files:**

- Create: `tests/test_resume_skill.py`
- Create: `resume/scripts/resume.py`

**Interfaces:**

- Produces: `resolve_session_file(sessions_root: Path, thread_id: str) -> tuple[Path, dict]`.
- Produces: `directories_from_session(session_file: Path, primary_cwd: Path) -> list[Path]`.
- Produces: `render_command(primary_cwd: Path, session_id: str, added_dirs: list[Path]) -> str`.

- [ ] **Step 1: Write failing session-selection tests**

```python
class ResumeSkillTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_resolve_session_file_accepts_only_matching_primary(self):
        tmp_path = Path(self.tempdir.name)
        primary = write_session(tmp_path, "primary.jsonl", {
            "id": "thread-1", "session_id": "resume-1", "thread_source": "user",
            "source": "cli", "cwd": str(tmp_path),
        })
        write_session(tmp_path, "child.jsonl", {
            "id": "thread-1", "session_id": "resume-1", "thread_source": "subagent",
            "source": {"subagent": {}}, "cwd": str(tmp_path),
        })
        self.assertEqual(resume.resolve_session_file(tmp_path, "thread-1")[0], primary)


    def test_resolve_session_file_rejects_missing_or_duplicate_primary(self):
        with self.assertRaises(resume.ResumeError):
            resume.resolve_session_file(Path(self.tempdir.name), "missing")
```

- [ ] **Step 2: Run the selection tests and verify they fail because `resume` does not exist**

Run: `python3 -m unittest tests/test_resume_skill.py`

Expected: FAIL with an import error for `resume/scripts/resume.py`.

- [ ] **Step 3: Implement the minimal metadata resolver**

```python
def resolve_session_file(sessions_root: Path, thread_id: str) -> tuple[Path, dict]:
    matches = []
    for path in sessions_root.rglob("*.jsonl"):
        metadata = read_first_json_object(path)
        if is_primary_metadata(metadata, thread_id):
            matches.append((path, metadata["payload"]))
    if len(matches) != 1:
        raise ResumeError(f"expected one primary session for {thread_id!r}; found {len(matches)}")
    return matches[0]
```

- [ ] **Step 4: Run the selection tests and verify they pass**

Run: `python3 -m unittest tests/test_resume_skill.py`

Expected: PASS; child, missing, and duplicate cases are rejected.

### Task 2: Parse only executed literal directory arguments

**Files:**

- Modify: `resume/scripts/resume.py`
- Modify: `tests/test_resume_skill.py`

**Interfaces:**

- Consumes: a validated session JSONL file and primary cwd from Task 1.
- Produces: ordered unique existing additional directories via `directories_from_session`.

- [ ] **Step 1: Write failing parser tests using real record shapes**

```python
def test_directories_from_session_uses_literal_exec_arguments_only(self):
    tmp_path = Path(self.tempdir.name)
    primary = tmp_path / "primary"; primary.mkdir()
    added = tmp_path / "added"; added.mkdir()
    session = write_records(tmp_path / "session.jsonl", [
        exec_record('tools.exec_command({"cmd":"pwd", "workdir":"%s"})' % added),
        exec_record('tools.exec_command({"cmd":"codex resume abc --add-dir %s"})' % added),
        user_record(f'ignore {tmp_path / "prose"}'),
        exec_record('tools.exec_command({"workdir": dynamic_path})'),
    ])
    self.assertEqual(resume.directories_from_session(session, primary), [added])
```

- [ ] **Step 2: Run parser tests and verify they fail because extraction is absent**

Run: `python3 -m unittest tests/test_resume_skill.py`

Expected: FAIL with `directories_from_session` missing or returning no directories.

- [ ] **Step 3: Implement literal extraction without evaluating source**

```python
def directories_from_session(session_file: Path, primary_cwd: Path) -> list[Path]:
    candidates = []
    for record in session_records(session_file):
        if record_name(record) != "exec":
            continue
        for call in literal_exec_calls(record_input(record)):
            candidates.extend([call.get("workdir"), *resume_add_dirs(call.get("cmd", ""))])
    return valid_unique_directories(candidates, primary_cwd)
```

`literal_exec_calls` must identify balanced braces while respecting JSON string escapes, then pass only the extracted object to `json.loads`. `resume_add_dirs` must use `shlex.split`, accept only commands whose first two tokens are `codex` and `resume`, and collect only values immediately following `--add-dir`.

- [ ] **Step 4: Run parser tests and verify they pass**

Run: `python3 -m unittest tests/test_resume_skill.py`

Expected: PASS; prose, malformed JSON, dynamic arguments, nonexistent paths, and the primary cwd are excluded.

### Task 3: Render and expose the explicit-only skill

**Files:**

- Modify: `resume/scripts/resume.py`
- Modify: `tests/test_resume_skill.py`
- Create: `resume/SKILL.md`
- Create: `resume/agents/openai.yaml`

**Interfaces:**

- Consumes: validated primary cwd, session ID, and directory list from Tasks 1–2.
- Produces: stdout-only copyable command block; non-zero errors for unsafe input.

- [ ] **Step 1: Write failing renderer and metadata tests**

```python
def test_render_command_escapes_double_quote_dollar_backtick_and_backslash(self):
    tmp_path = Path(self.tempdir.name)
    path = tmp_path / 'a"$`\\b'; path.mkdir()
    output = resume.render_command(tmp_path, "session-1", [path])
    self.assertTrue(output.splitlines()[1].endswith("\\"))
    self.assertNotIn("--last", output)
    self.assertIn('\\\\"', output)
    self.assertIn('\\$', output)
    self.assertIn('\\`', output)
    self.assertIn('\\\\', output)


def test_render_command_rejects_newline_path(self):
    tmp_path = Path(self.tempdir.name)
    with mock.patch.object(resume, "path_text", return_value="/bad\\npath"):
        with self.assertRaises(resume.ResumeError):
            resume.render_command(tmp_path, "session-1", [])
```

Also assert zero-directory output has exactly two lines, multi-directory output has a continuation after every non-final argument line, and `agents/openai.yaml` contains `policy.allow_implicit_invocation: false`.

- [ ] **Step 2: Run renderer tests and verify they fail before the renderer exists**

Run: `python3 -m unittest tests/test_resume_skill.py`

Expected: FAIL with `render_command` missing.

- [ ] **Step 3: Implement safe rendering and package metadata**

```python
def quote(value: str) -> str:
    if "\n" in value:
        raise ResumeError("newline paths cannot be rendered safely")
    for raw, escaped in (("\\", "\\\\"), ('"', '\\"'), ("$", "\\$"), ("`", "\\`")):
        value = value.replace(raw, escaped)
    return f'"{value}"'
```

Write `SKILL.md` with a `Use when...` description, a manual invocation example, the exact helper command, and the no-guess/no-launch constraints. Write `agents/openai.yaml` with display metadata and:

```yaml
policy:
  allow_implicit_invocation: false
```

- [ ] **Step 4: Run the complete tests and validator**

Run: `python3 -m unittest tests/test_resume_skill.py && /Users/nixiaofeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py resume`

Expected: all tests and the skill validator pass.

- [ ] **Step 5: Probe the installed helper without launching Codex**

Run: `CODEX_THREAD_ID="$CODEX_THREAD_ID" python3 resume/scripts/resume.py`

Expected: either a copyable command block with no `--last`, or a deliberate non-zero ambiguity/safety error.

### Task 4: Install and verify the global package

**Files:**

- Source: `resume/`
- Install target: `~/.codex/skills/resume/`

**Interfaces:**

- Consumes: verified source package from Tasks 1–3.
- Produces: global manually-invocable `$resume` package.

- [ ] **Step 1: Verify the source package is clean and validated**

Run: `git diff --check && python3 -m unittest tests/test_resume_skill.py`

Expected: no whitespace errors and all tests pass.

- [ ] **Step 2: Copy the verified package to the global skill directory after authorization**

Run: `mkdir -p ~/.codex/skills && cp -R resume ~/.codex/skills/resume`

Expected: target contains `SKILL.md`, `agents/openai.yaml`, and `scripts/resume.py`.

- [ ] **Step 3: Validate the installed package and perform a no-launch probe**

Run: `/Users/nixiaofeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/resume && CODEX_THREAD_ID="$CODEX_THREAD_ID" python3 ~/.codex/skills/resume/scripts/resume.py`

Expected: validation passes; the probe prints only a resume command block or a deliberate non-zero safety error.

- [ ] **Step 4: Ask whether to create the local commit**

List all changed source, test, spec, and plan files; obtain branch and commit confirmation before `git add`/`git commit`.

## Plan Self-Review

- Spec coverage: Task 1 implements authoritative primary-session selection; Task 2 implements the bounded history parser; Task 3 implements safe multi-line output and explicit-only metadata; Task 4 installs only after source validation.
- Placeholder scan: no deferred implementation steps or unspecified interfaces remain.
- Type consistency: Tasks 2–3 consume the exact `Path`, `str`, and `list[Path]` signatures defined in Task 1.
