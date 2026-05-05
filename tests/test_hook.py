"""Tests for agents/claude/grim-mode-tracker.py and agents/kiro/grim-mode-tracker.py."""
import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_HOOK = Path(__file__).parent.parent / "agents" / "claude" / "grim-mode-tracker.py"
KIRO_HOOK = Path(__file__).parent.parent / "agents" / "kiro" / "grim-mode-tracker.py"


def run_hook(hook: Path, prompt: str, claude_dir: Path, extra_env: dict | None = None) -> tuple[int, str]:
    payload = json.dumps({"prompt": prompt})
    env_key = "CLAUDE_CONFIG_DIR" if "claude" in hook.parts else "KIRO_CONFIG_DIR"
    env = {env_key: str(claude_dir), "HOME": str(claude_dir)}
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=payload,
        text=True,
        capture_output=True,
        env={**os.environ, **env},
    )
    return result.returncode, result.stdout


class TestClaudeHook:
    def test_activate_creates_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        assert not flag.exists()
        run_hook(CLAUDE_HOOK, "grim mode on", tmp_path)
        assert flag.exists()

    def test_deactivate_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook(CLAUDE_HOOK, "stop grim", tmp_path)
        assert not flag.exists()

    def test_normal_mode_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook(CLAUDE_HOOK, "normal mode", tmp_path)
        assert not flag.exists()

    def test_reinforcement_emitted_when_active(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        _, stdout = run_hook(CLAUDE_HOOK, "what is a linked list?", tmp_path)
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "BOT MODE ACTIVE" in context

    def test_no_output_when_inactive(self, tmp_path):
        _, stdout = run_hook(CLAUDE_HOOK, "what is a linked list?", tmp_path)
        assert stdout.strip() == ""

    def test_invalid_json_exits_cleanly(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(CLAUDE_HOOK)],
            input="not json at all",
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_CONFIG_DIR": str(tmp_path), "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_config_dir_falls_back_to_default(self, tmp_path):
        # Empty CLAUDE_CONFIG_DIR is falsy — hook falls back to ~/.claude.
        # Flag must NOT appear in tmp_path.
        # Use a neutral prompt so no flag is written anywhere.
        flag = tmp_path / ".grim-active"
        run_hook(CLAUDE_HOOK, "what is a list?", tmp_path, extra_env={"CLAUDE_CONFIG_DIR": ""})
        assert not flag.exists()


class TestKiroHook:
    def test_activate_creates_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        assert not flag.exists()
        run_hook(KIRO_HOOK, "grim mode on", tmp_path)
        assert flag.exists()

    def test_deactivate_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook(KIRO_HOOK, "stop grim", tmp_path)
        assert not flag.exists()

    def test_normal_mode_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook(KIRO_HOOK, "normal mode", tmp_path)
        assert not flag.exists()

    def test_reinforcement_emitted_when_active(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        _, stdout = run_hook(KIRO_HOOK, "what is a linked list?", tmp_path)
        assert "BOT MODE ACTIVE" in stdout

    def test_no_output_when_inactive(self, tmp_path):
        _, stdout = run_hook(KIRO_HOOK, "what is a linked list?", tmp_path)
        assert stdout.strip() == ""

    def test_invalid_json_exits_cleanly(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(KIRO_HOOK)],
            input="not json at all",
            text=True,
            capture_output=True,
            env={**os.environ, "KIRO_CONFIG_DIR": str(tmp_path), "HOME": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_config_dir_falls_back_to_default(self, tmp_path):
        flag = tmp_path / ".grim-active"
        run_hook(KIRO_HOOK, "what is a list?", tmp_path, extra_env={"KIRO_CONFIG_DIR": ""})
        assert not flag.exists()
