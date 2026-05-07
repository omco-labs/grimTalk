"""Tests for agents/kiro/hooks/otel_spans.ts via subprocess (requires bun)."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

HOOK = Path(__file__).parent.parent / "agents" / "kiro" / "hooks" / "otel_spans.ts"


def run_hook(payload: dict, tmp_path: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = {
        **os.environ,
        "HOME": str(tmp_path),
        **(env or {}),
    }
    return subprocess.run(
        ["bun", "run", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=merged,
    )


def otel_lines(tmp_path: Path, session_id: str) -> list[dict]:
    p = tmp_path / ".kiro" / "sessions" / "cli" / f"{session_id}.otel.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def state_file(session_id: str) -> Path:
    return Path(f"/tmp/otel-spans-{session_id}.json")


def cleanup_state(session_id: str) -> None:
    state_file(session_id).unlink(missing_ok=True)


# ── bun availability ──────────────────────────────────────────────────────────

def bun_available() -> bool:
    return subprocess.run(["bun", "--version"], capture_output=True).returncode == 0

pytestmark = pytest.mark.skipif(not bun_available(), reason="bun not installed")


# ── helpers ───────────────────────────────────────────────────────────────────

SESSION = "test-session-abc123"


@pytest.fixture(autouse=True)
def clean_state():
    cleanup_state(SESSION)
    yield
    cleanup_state(SESSION)


# ── exit code ─────────────────────────────────────────────────────────────────

class TestExitBehavior:
    def test_exits_zero_on_valid_input(self, tmp_path):
        r = run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        assert r.returncode == 0

    def test_exits_zero_on_invalid_json(self, tmp_path):
        r = subprocess.run(
            ["bun", "run", str(HOOK)],
            input="not json",
            text=True,
            capture_output=True,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        assert r.returncode == 0

    def test_exits_zero_on_unknown_event(self, tmp_path):
        r = run_hook({"hook_event_name": "unknownEvent", "session_id": SESSION, "cwd": "/"}, tmp_path)
        assert r.returncode == 0


# ── agentSpawn ────────────────────────────────────────────────────────────────

class TestAgentSpawn:
    def test_creates_state_file(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        assert state_file(SESSION).exists()

    def test_state_has_trace_id_and_agent_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        state = json.loads(state_file(SESSION).read_text())
        assert len(state["trace_id"]) == 32
        assert len(state["agent_span_id"]) == 16
        assert state["chain_span_id"] is None


# ── userPromptSubmit ──────────────────────────────────────────────────────────

class TestUserPromptSubmit:
    def test_opens_chain_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "hello"}, tmp_path)
        state = json.loads(state_file(SESSION).read_text())
        assert state["chain_span_id"] is not None
        assert state["chain_start"] is not None

    def test_no_op_without_prior_agent_spawn(self, tmp_path):
        # No state file — should not crash
        r = run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "hello"}, tmp_path)
        assert r.returncode == 0


# ── preToolUse ────────────────────────────────────────────────────────────────

class TestPreToolUse:
    def test_opens_tool_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "preToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {"path": "/tmp/x"}}, tmp_path)
        state = json.loads(state_file(SESSION).read_text())
        assert state["tool_span_id"] is not None
        assert state["tool_name"] == "fs_read"


# ── postToolUse ───────────────────────────────────────────────────────────────

class TestPostToolUse:
    def _setup(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "preToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {"path": "/tmp/x"}}, tmp_path)

    def test_emits_tool_span_jsonl(self, tmp_path):
        self._setup(tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {"path": "/tmp/x"}, "tool_response": {"result": "ok"}}, tmp_path)
        lines = otel_lines(tmp_path, SESSION)
        assert len(lines) == 1
        span = lines[0]
        assert span["kind"] == "OtelSpan"
        assert span["data"]["attributes"]["openinference.span.kind"] == "TOOL"
        assert span["data"]["attributes"]["tool.name"] == "fs_read"

    def test_span_has_input_and_output(self, tmp_path):
        self._setup(tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {"path": "/tmp/x"}, "tool_response": {"result": "content"}}, tmp_path)
        span = otel_lines(tmp_path, SESSION)[0]["data"]
        assert "input.value" in span["attributes"]
        assert "output.value" in span["attributes"]
        assert json.loads(span["attributes"]["output.value"])["result"] == "content"

    def test_clears_tool_state_after_emit(self, tmp_path):
        self._setup(tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {}, "tool_response": {}}, tmp_path)
        state = json.loads(state_file(SESSION).read_text())
        assert state["tool_span_id"] is None
        assert state["tool_name"] is None

    def test_span_has_valid_timestamps(self, tmp_path):
        self._setup(tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {}, "tool_response": {}}, tmp_path)
        span = otel_lines(tmp_path, SESSION)[0]["data"]
        assert span["start_time_unix_nano"] > 0
        assert span["end_time_unix_nano"] >= span["start_time_unix_nano"]

    def test_no_op_without_open_tool_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        r = run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "fs_read", "tool_input": {}, "tool_response": {}}, tmp_path)
        assert r.returncode == 0
        assert otel_lines(tmp_path, SESSION) == []


# ── stop ──────────────────────────────────────────────────────────────────────

class TestStop:
    def test_emits_chain_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "stop", "session_id": SESSION, "cwd": "/"}, tmp_path)
        lines = otel_lines(tmp_path, SESSION)
        assert len(lines) == 1
        assert lines[0]["data"]["attributes"]["openinference.span.kind"] == "CHAIN"

    def test_chain_parent_is_agent_span(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        state_before = json.loads(state_file(SESSION).read_text())
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "stop", "session_id": SESSION, "cwd": "/"}, tmp_path)
        span = otel_lines(tmp_path, SESSION)[0]["data"]
        assert span["parent_span_id"] == state_before["agent_span_id"]

    def test_clears_chain_state(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "stop", "session_id": SESSION, "cwd": "/"}, tmp_path)
        state = json.loads(state_file(SESSION).read_text())
        assert state["chain_span_id"] is None

    def test_no_op_without_open_chain(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        r = run_hook({"hook_event_name": "stop", "session_id": SESSION, "cwd": "/"}, tmp_path)
        assert r.returncode == 0
        assert otel_lines(tmp_path, SESSION) == []


# ── JSONL format ──────────────────────────────────────────────────────────────

class TestJsonlFormat:
    def test_envelope_matches_kiro_session_log_format(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "preToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "bash", "tool_input": {}}, tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "bash", "tool_input": {}, "tool_response": {}}, tmp_path)
        line = otel_lines(tmp_path, SESSION)[0]
        assert line["version"] == "v1"
        assert line["kind"] == "OtelSpan"
        assert "data" in line

    def test_span_has_session_id_attribute(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        run_hook({"hook_event_name": "preToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "bash", "tool_input": {}}, tmp_path)
        run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": "bash", "tool_input": {}, "tool_response": {}}, tmp_path)
        attrs = otel_lines(tmp_path, SESSION)[0]["data"]["attributes"]
        assert attrs["session.id"] == SESSION

    def test_multiple_tool_spans_share_trace_id(self, tmp_path):
        run_hook({"hook_event_name": "agentSpawn", "session_id": SESSION, "cwd": "/"}, tmp_path)
        run_hook({"hook_event_name": "userPromptSubmit", "session_id": SESSION, "cwd": "/", "prompt": "go"}, tmp_path)
        for tool in ("fs_read", "execute_bash"):
            run_hook({"hook_event_name": "preToolUse", "session_id": SESSION, "cwd": "/", "tool_name": tool, "tool_input": {}}, tmp_path)
            run_hook({"hook_event_name": "postToolUse", "session_id": SESSION, "cwd": "/", "tool_name": tool, "tool_input": {}, "tool_response": {}}, tmp_path)
        lines = otel_lines(tmp_path, SESSION)
        assert len(lines) == 2
        assert lines[0]["data"]["trace_id"] == lines[1]["data"]["trace_id"]
