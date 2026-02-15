"""Integration tests for the CLI wrapper scripts (claude-wrapper.sh and codex-wrapper.sh).

These tests invoke the bash wrapper scripts via subprocess.run() and validate
their JSON envelope output, error handling, and cross-wrapper consistency.

Since the wrappers call real CLI tools (claude / codex) which are not available
in test environments, we create lightweight stub scripts on the PATH that mimic
CLI behavior. For error-handling tests we use stubs that exit non-zero or are
absent entirely.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Skip on Windows -- these are bash scripts
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Bash wrapper scripts are not supported on Windows",
)

# Absolute paths to the wrapper scripts under test
_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
CLAUDE_WRAPPER = _SCRIPTS_DIR / "claude-wrapper.sh"
CODEX_WRAPPER = _SCRIPTS_DIR / "codex-wrapper.sh"

# Envelope schema fields that must always be present
ENVELOPE_REQUIRED_KEYS = {"status", "exit_code", "stdout", "stderr"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_wrapper(
    wrapper_path: pathlib.Path,
    payload: dict | str,
    *,
    env_overrides: dict | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run a wrapper script with the given JSON payload on stdin."""
    env = os.environ.copy()
    # Strip variables that could interfere with test isolation
    env.pop("CLAUDECODE", None)
    if env_overrides:
        env.update(env_overrides)

    stdin_data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(wrapper_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _parse_envelope(stdout: str) -> dict:
    """Parse the JSON envelope from wrapper stdout, stripping any trailing whitespace."""
    stripped = stdout.strip()
    return json.loads(stripped)


def _make_stub_cli(
    tmp_path: pathlib.Path,
    name: str,
    *,
    exit_code: int = 0,
    stdout_text: str = "",
    stderr_text: str = "",
) -> pathlib.Path:
    """Create a stub CLI executable in tmp_path/bin that prints the given text
    and exits with the given code.  Returns the bin directory (to prepend to PATH)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / name
    stub.write_text(textwrap.dedent(f"""\
        #!/bin/bash
        # Stub {name} for testing
        if [ -n "{stderr_text}" ]; then
            echo -n '{stderr_text}' >&2
        fi
        echo -n '{stdout_text}'
        exit {exit_code}
    """))
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _env_with_stub(bin_dir: pathlib.Path) -> dict:
    """Return env override dict that prepends bin_dir to PATH."""
    return {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}


def _make_sample_payload(request_text: str = "Say hello") -> dict:
    """Return a minimal valid JSON payload for wrapper stdin."""
    return {
        "request": request_text,
        "phase": "test",
        "task_id": "test-001",
    }


# ---------------------------------------------------------------------------
# Envelope validation helpers
# ---------------------------------------------------------------------------

def _assert_valid_envelope(envelope: dict) -> None:
    """Assert the envelope contains all required keys and correct types."""
    for key in ENVELOPE_REQUIRED_KEYS:
        assert key in envelope, f"Envelope missing required key: {key}"
    assert envelope["status"] in ("passed", "failed"), (
        f"Invalid envelope status: {envelope['status']}"
    )
    assert isinstance(envelope["exit_code"], int), (
        f"exit_code must be int, got {type(envelope['exit_code'])}"
    )
    assert isinstance(envelope["stdout"], str), (
        f"stdout must be str, got {type(envelope['stdout'])}"
    )
    assert isinstance(envelope["stderr"], str), (
        f"stderr must be str, got {type(envelope['stderr'])}"
    )
    # result is optional but if present must be a dict
    if "result" in envelope:
        assert isinstance(envelope["result"], dict), (
            f"result must be dict, got {type(envelope['result'])}"
        )


# ===========================================================================
# Claude Wrapper Tests
# ===========================================================================

class TestClaudeWrapper:
    """Tests for agent/scripts/claude-wrapper.sh"""

    def test_wrapper_reads_stdin_json_payload(self, tmp_path):
        """Wrapper should accept a JSON payload on stdin and use its fields
        to construct the prompt sent to the CLI."""
        cli_output = json.dumps({"echo": "received"})
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text=cli_output)
        payload = _make_sample_payload("Describe the architecture")

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))

        assert proc.returncode == 0, f"Wrapper failed: stderr={proc.stderr}"
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    def test_wrapper_outputs_valid_json_envelope(self, tmp_path):
        """Wrapper stdout must be a single JSON object conforming to the
        cli-envelope schema."""
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text="plain text output")
        payload = _make_sample_payload()

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        # When CLI output is not JSON, result should be empty dict
        assert envelope["result"] == {}

    def test_wrapper_structured_json_output_parsed(self, tmp_path):
        """When the CLI returns valid JSON, the wrapper should parse it into
        the result field of the envelope."""
        structured = {"files_changed": ["a.py"], "summary": "done"}
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text=json.dumps(structured))
        payload = _make_sample_payload()

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
        assert envelope["result"] == structured

    def test_wrapper_error_when_cli_not_found(self, tmp_path):
        """When the 'claude' command does not exist on PATH, the wrapper should
        emit a failed envelope (via the EXIT trap) with a non-zero exit_code."""
        # Create an empty bin dir with no 'claude' stub
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        env = {"PATH": f"{empty_bin}:/usr/bin:/bin"}
        payload = _make_sample_payload()

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=env)

        # The wrapper should still produce JSON output via the error trap
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "failed"
        assert envelope["exit_code"] != 0

    def test_wrapper_cli_nonzero_exit_produces_failed_status(self, tmp_path):
        """When the CLI exits non-zero, the envelope status should be 'failed'."""
        bin_dir = _make_stub_cli(
            tmp_path, "claude",
            exit_code=1,
            stdout_text="error output",
            stderr_text="something went wrong",
        )
        payload = _make_sample_payload()

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "failed"
        assert envelope["exit_code"] == 1

    def test_wrapper_empty_stdin(self, tmp_path):
        """Wrapper should handle empty stdin gracefully and produce a valid envelope."""
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text="ok")

        proc = _run_wrapper(CLAUDE_WRAPPER, "", env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        # Even with empty stdin the wrapper should not crash
        assert envelope["status"] == "passed"

    def test_wrapper_invalid_json_stdin(self, tmp_path):
        """Wrapper should handle invalid JSON on stdin and still produce an envelope."""
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text="ok")

        proc = _run_wrapper(
            CLAUDE_WRAPPER, "this is not json at all",
            env_overrides=_env_with_stub(bin_dir),
        )
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        # The wrapper should still run (with a fallback prompt)
        assert envelope["status"] == "passed"

    def test_wrapper_rich_payload_with_subtask(self, tmp_path):
        """Wrapper should handle a payload that contains phase, task_id, and
        subtask fields used to build a structured prompt."""
        bin_dir = _make_stub_cli(tmp_path, "claude", stdout_text=json.dumps({"ok": True}))
        payload = {
            "request": "Implement the feature",
            "phase": "implement",
            "task_id": "T-001",
            "subtask": {
                "subtask_id": "T-001-S01",
                "title": "Build the widget",
                "acceptance_criteria": [
                    {"description": "Widget renders correctly"},
                    "No console errors",
                ],
            },
        }

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
        assert envelope["result"] == {"ok": True}

    def test_wrapper_stderr_captured_in_envelope(self, tmp_path):
        """Any stderr output from the CLI should be captured in the
        envelope's stderr field."""
        bin_dir = _make_stub_cli(
            tmp_path, "claude",
            stdout_text="output",
            stderr_text="warning: something",
        )
        payload = _make_sample_payload()

        proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert "warning: something" in envelope["stderr"]


# ===========================================================================
# Codex Wrapper Tests
# ===========================================================================

class TestCodexWrapper:
    """Tests for agent/scripts/codex-wrapper.sh"""

    def test_wrapper_reads_stdin_json_payload(self, tmp_path):
        """Wrapper should accept a JSON payload on stdin."""
        cli_output = json.dumps({"echo": "received"})
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text=cli_output)
        payload = _make_sample_payload("Build the feature")

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        assert proc.returncode == 0, f"Wrapper failed: stderr={proc.stderr}"
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    def test_wrapper_outputs_valid_json_envelope(self, tmp_path):
        """Wrapper stdout must be a JSON object conforming to the envelope schema."""
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text="plain text")
        payload = _make_sample_payload()

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["result"] == {}

    def test_wrapper_structured_json_output_parsed(self, tmp_path):
        """When CLI returns valid JSON, result field should contain parsed data."""
        structured = {"files_changed": ["b.py"], "tests_added": 3}
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text=json.dumps(structured))
        payload = _make_sample_payload()

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
        assert envelope["result"] == structured

    def test_wrapper_error_when_cli_not_found(self, tmp_path):
        """When 'codex' is not on PATH, wrapper should emit a failed envelope."""
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        env = {"PATH": f"{empty_bin}:/usr/bin:/bin"}
        payload = _make_sample_payload()

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=env)
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "failed"
        assert envelope["exit_code"] != 0

    def test_wrapper_cli_nonzero_exit_produces_failed_status(self, tmp_path):
        """Non-zero CLI exit should produce a 'failed' envelope status."""
        bin_dir = _make_stub_cli(
            tmp_path, "codex",
            exit_code=2,
            stdout_text="",
            stderr_text="compilation error",
        )
        payload = _make_sample_payload()

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "failed"
        assert envelope["exit_code"] == 2

    def test_wrapper_empty_stdin(self, tmp_path):
        """Wrapper should handle empty stdin gracefully."""
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text="ok")

        proc = _run_wrapper(CODEX_WRAPPER, "", env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    def test_wrapper_invalid_json_stdin(self, tmp_path):
        """Wrapper should handle invalid JSON on stdin gracefully."""
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text="ok")

        proc = _run_wrapper(
            CODEX_WRAPPER, "not valid json",
            env_overrides=_env_with_stub(bin_dir),
        )
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    def test_wrapper_rich_payload_with_subtask(self, tmp_path):
        """Wrapper should handle a rich payload with subtask and acceptance_criteria."""
        bin_dir = _make_stub_cli(tmp_path, "codex", stdout_text=json.dumps({"built": True}))
        payload = {
            "request": "Implement tests",
            "phase": "implement",
            "task_id": "T-002",
            "subtask": {
                "subtask_id": "T-002-S01",
                "title": "Write unit tests",
                "acceptance_criteria": [
                    {"description": "Coverage above 80%"},
                    "All tests green",
                ],
            },
        }

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
        assert envelope["result"] == {"built": True}

    def test_wrapper_stderr_captured_in_envelope(self, tmp_path):
        """Stderr from CLI should be captured in the envelope."""
        bin_dir = _make_stub_cli(
            tmp_path, "codex",
            stdout_text="result",
            stderr_text="deprecation warning",
        )
        payload = _make_sample_payload()

        proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert "deprecation warning" in envelope["stderr"]


# ===========================================================================
# Cross-Wrapper Consistency Tests
# ===========================================================================

class TestCrossWrapperConsistency:
    """Verify that both wrappers produce structurally identical envelopes and
    behave consistently under the same conditions."""

    def _run_both_wrappers(
        self, tmp_path, payload, *, exit_code=0, stdout_text="ok", stderr_text=""
    ):
        """Run both wrappers with identical stub CLIs and return their envelopes."""
        claude_bin = _make_stub_cli(
            tmp_path / "claude_env", "claude",
            exit_code=exit_code, stdout_text=stdout_text, stderr_text=stderr_text,
        )
        codex_bin = _make_stub_cli(
            tmp_path / "codex_env", "codex",
            exit_code=exit_code, stdout_text=stdout_text, stderr_text=stderr_text,
        )

        claude_proc = _run_wrapper(
            CLAUDE_WRAPPER, payload, env_overrides=_env_with_stub(claude_bin),
        )
        codex_proc = _run_wrapper(
            CODEX_WRAPPER, payload, env_overrides=_env_with_stub(codex_bin),
        )

        claude_env = _parse_envelope(claude_proc.stdout)
        codex_env = _parse_envelope(codex_proc.stdout)
        return claude_env, codex_env

    def test_same_envelope_structure_on_success(self, tmp_path):
        """Both wrappers should produce envelopes with the same set of keys
        when the CLI succeeds."""
        payload = _make_sample_payload()
        claude_env, codex_env = self._run_both_wrappers(
            tmp_path, payload, stdout_text="hello",
        )

        _assert_valid_envelope(claude_env)
        _assert_valid_envelope(codex_env)
        assert set(claude_env.keys()) == set(codex_env.keys()), (
            f"Key mismatch: claude={set(claude_env.keys())} codex={set(codex_env.keys())}"
        )

    def test_same_envelope_structure_on_failure(self, tmp_path):
        """Both wrappers should produce envelopes with the same set of keys
        when the CLI fails."""
        payload = _make_sample_payload()
        claude_env, codex_env = self._run_both_wrappers(
            tmp_path, payload, exit_code=1, stdout_text="err", stderr_text="fail",
        )

        _assert_valid_envelope(claude_env)
        _assert_valid_envelope(codex_env)
        assert set(claude_env.keys()) == set(codex_env.keys())
        assert claude_env["status"] == codex_env["status"] == "failed"
        assert claude_env["exit_code"] == codex_env["exit_code"] == 1

    def test_both_handle_empty_stdin(self, tmp_path):
        """Both wrappers should handle empty stdin without crashing."""
        claude_bin = _make_stub_cli(tmp_path / "claude_env", "claude", stdout_text="ok")
        codex_bin = _make_stub_cli(tmp_path / "codex_env", "codex", stdout_text="ok")

        claude_proc = _run_wrapper(
            CLAUDE_WRAPPER, "", env_overrides=_env_with_stub(claude_bin),
        )
        codex_proc = _run_wrapper(
            CODEX_WRAPPER, "", env_overrides=_env_with_stub(codex_bin),
        )

        claude_env = _parse_envelope(claude_proc.stdout)
        codex_env = _parse_envelope(codex_proc.stdout)
        _assert_valid_envelope(claude_env)
        _assert_valid_envelope(codex_env)
        assert claude_env["status"] == "passed"
        assert codex_env["status"] == "passed"

    def test_both_handle_cli_not_found(self, tmp_path):
        """Both wrappers should produce a failed envelope when their CLI is missing."""
        empty_bin = tmp_path / "empty_bin"
        empty_bin.mkdir()
        env = {"PATH": f"{empty_bin}:/usr/bin:/bin"}
        payload = _make_sample_payload()

        claude_proc = _run_wrapper(CLAUDE_WRAPPER, payload, env_overrides=env)
        codex_proc = _run_wrapper(CODEX_WRAPPER, payload, env_overrides=env)

        claude_env = _parse_envelope(claude_proc.stdout)
        codex_env = _parse_envelope(codex_proc.stdout)
        _assert_valid_envelope(claude_env)
        _assert_valid_envelope(codex_env)
        assert claude_env["status"] == "failed"
        assert codex_env["status"] == "failed"

    def test_both_parse_structured_json_identically(self, tmp_path):
        """When both CLIs return the same JSON, both envelopes should have
        identical result fields."""
        structured = {"analysis": "complete", "score": 95}
        payload = _make_sample_payload()
        claude_env, codex_env = self._run_both_wrappers(
            tmp_path, payload, stdout_text=json.dumps(structured),
        )

        assert claude_env["result"] == codex_env["result"] == structured

    def test_both_produce_matching_status_for_same_exit_code(self, tmp_path):
        """Given the same exit code, both wrappers should report the same status."""
        payload = _make_sample_payload()

        # Test exit code 0 -> passed
        claude_env_pass, codex_env_pass = self._run_both_wrappers(
            tmp_path / "pass", payload, exit_code=0,
        )
        assert claude_env_pass["status"] == codex_env_pass["status"] == "passed"

        # Test exit code 1 -> failed
        claude_env_fail, codex_env_fail = self._run_both_wrappers(
            tmp_path / "fail", payload, exit_code=1,
        )
        assert claude_env_fail["status"] == codex_env_fail["status"] == "failed"

    def test_envelope_result_is_empty_dict_for_non_json_output(self, tmp_path):
        """When CLI output is not valid JSON, both wrappers should set result to {}."""
        payload = _make_sample_payload()
        claude_env, codex_env = self._run_both_wrappers(
            tmp_path, payload, stdout_text="This is not JSON at all.",
        )

        assert claude_env["result"] == {}
        assert codex_env["result"] == {}

    def test_both_preserve_exit_code_in_envelope(self, tmp_path):
        """The exit_code in the envelope should match the actual CLI exit code."""
        payload = _make_sample_payload()

        for code in [0, 1, 2, 42, 127]:
            claude_env, codex_env = self._run_both_wrappers(
                tmp_path / f"code_{code}", payload, exit_code=code,
            )
            assert claude_env["exit_code"] == code, (
                f"Claude wrapper exit_code mismatch for code {code}"
            )
            assert codex_env["exit_code"] == code, (
                f"Codex wrapper exit_code mismatch for code {code}"
            )


# ===========================================================================
# Edge Case Tests
# ===========================================================================

class TestWrapperEdgeCases:
    """Edge cases and boundary conditions for both wrappers."""

    @pytest.mark.parametrize("wrapper,cli_name", [
        (CLAUDE_WRAPPER, "claude"),
        (CODEX_WRAPPER, "codex"),
    ])
    def test_large_payload(self, tmp_path, wrapper, cli_name):
        """Wrapper should handle a large JSON payload without truncation or crash."""
        bin_dir = _make_stub_cli(tmp_path, cli_name, stdout_text='{"ok":true}')
        payload = {
            "request": "Process this large payload",
            "data": "x" * 50000,
            "items": list(range(1000)),
        }

        proc = _run_wrapper(wrapper, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    @pytest.mark.parametrize("wrapper,cli_name", [
        (CLAUDE_WRAPPER, "claude"),
        (CODEX_WRAPPER, "codex"),
    ])
    def test_cli_output_with_special_characters(self, tmp_path, wrapper, cli_name):
        """Wrapper should correctly JSON-encode CLI output containing special
        characters like quotes, newlines, and backslashes."""
        special_output = 'Line 1\nLine "2" with quotes\nLine 3 with \\backslash'
        bin_dir = _make_stub_cli(tmp_path, cli_name, stdout_text=special_output)
        payload = _make_sample_payload()

        proc = _run_wrapper(wrapper, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        # stdout should be a valid JSON string containing the special chars
        assert isinstance(envelope["stdout"], str)

    @pytest.mark.parametrize("wrapper,cli_name", [
        (CLAUDE_WRAPPER, "claude"),
        (CODEX_WRAPPER, "codex"),
    ])
    def test_cli_returns_empty_output(self, tmp_path, wrapper, cli_name):
        """Wrapper should handle empty CLI output without breaking the envelope."""
        bin_dir = _make_stub_cli(tmp_path, cli_name, stdout_text="")
        payload = _make_sample_payload()

        proc = _run_wrapper(wrapper, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
        assert envelope["result"] == {}

    @pytest.mark.parametrize("wrapper,cli_name", [
        (CLAUDE_WRAPPER, "claude"),
        (CODEX_WRAPPER, "codex"),
    ])
    def test_payload_without_request_field(self, tmp_path, wrapper, cli_name):
        """Wrapper should handle a payload with no 'request' field by using
        a default prompt."""
        bin_dir = _make_stub_cli(tmp_path, cli_name, stdout_text='{"default":true}')
        payload = {"phase": "plan", "task_id": "T-100"}

        proc = _run_wrapper(wrapper, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"

    @pytest.mark.parametrize("wrapper,cli_name", [
        (CLAUDE_WRAPPER, "claude"),
        (CODEX_WRAPPER, "codex"),
    ])
    def test_payload_with_nested_task_object(self, tmp_path, wrapper, cli_name):
        """Wrapper should handle a payload where task is a nested object
        containing task_id."""
        bin_dir = _make_stub_cli(tmp_path, cli_name, stdout_text='{"processed":true}')
        payload = {
            "request": "Handle nested task",
            "task": {"task_id": "nested-001", "title": "Nested Task"},
        }

        proc = _run_wrapper(wrapper, payload, env_overrides=_env_with_stub(bin_dir))
        envelope = _parse_envelope(proc.stdout)
        _assert_valid_envelope(envelope)
        assert envelope["status"] == "passed"
