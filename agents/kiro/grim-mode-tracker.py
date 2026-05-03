#!/usr/bin/env python3
"""grim — userPromptSubmit hook.
Clears flag on deactivation. Reinforces rules when active.
"""
import json
import os
import re
import sys
from pathlib import Path

kiro_dir = Path(os.environ.get("KIRO_CONFIG_DIR", Path.home() / ".kiro"))
flag_path = kiro_dir / ".grim-active"

DEACTIVATE = re.compile(
    r"\b(stop|disable|deactivate|turn off)\b.{0,20}\b(grim|din-bot)\b"
    r"|\b(grim|din-bot)\b.{0,20}\b(stop|disable|deactivate|turn off)\b"
    r"|\bnormal mode\b",
    re.IGNORECASE,
)

ACTIVATE = re.compile(
    r"\b(grim|din-bot)\b.{0,30}\b(mode|on|activate|enable)\b"
    r"|\b(activate|enable|turn on)\b.{0,20}\b(grim|din-bot)\b",
    re.IGNORECASE,
)

REINFORCE = (
    "BOT MODE ACTIVE. Respond terse like Bot warrior. "
    "Drop articles/filler/pleasantries/hedging. Warrior pride, broken grammar (Me say…). "
    "Code/commits/PRs: write normal. Off: 'stop grim' / 'normal mode'."
)

try:
    data = json.load(sys.stdin)
    prompt = data.get("prompt", "")
except Exception:
    sys.exit(0)

if DEACTIVATE.search(prompt):
    flag_path.unlink(missing_ok=True)
    sys.exit(0)

if ACTIVATE.search(prompt):
    if not flag_path.is_symlink():
        flag_path.touch()

active = flag_path.is_file() and not flag_path.is_symlink()
if active:
    print(REINFORCE)
