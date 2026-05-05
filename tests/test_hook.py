"""Tests for agents/claude/grim-mode-tracker.py via subprocess."""
import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "agents" / "claude" / "grim-mode-tracker.py"


def run_hook(prompt: str, claude_dir: Path) -> tuple[int, str]:
    payload = json.dumps({"prompt": prompt})
    env = {"CLAUDE_CONFIG_DIR": str(claude_dir), "HOME": str(claude_dir)}
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        text=True,
        capture_output=True,
        env={**__import__("os").environ, **env},
    )
    return result.returncode, result.stdout


class TestGrimModeTracker:
    def test_activate_creates_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        assert not flag.exists()
        run_hook("grim mode on", tmp_path)
        assert flag.exists()

    def test_deactivate_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook("stop grim", tmp_path)
        assert not flag.exists()

    def test_normal_mode_removes_flag(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        run_hook("normal mode", tmp_path)
        assert not flag.exists()

    def test_reinforcement_emitted_when_active(self, tmp_path):
        flag = tmp_path / ".grim-active"
        flag.touch()
        _, stdout = run_hook("what is a linked list?", tmp_path)
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "BOT MODE ACTIVE" in context

    def test_no_output_when_inactive(self, tmp_path):
        _, stdout = run_hook("what is a linked list?", tmp_path)
        assert stdout.strip() == ""

    def test_invalid_json_exits_cleanly(self, tmp_path):
        env = {"CLAUDE_CONFIG_DIR": str(tmp_path), "HOME": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json at all",
            text=True,
            capture_output=True,
            env={**__import__("os").environ, **env},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""
