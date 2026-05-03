#!/usr/bin/env bash
# grim — statusline badge for Claude Code
# Outputs [ME KING] when grim is active.
#
# Wire in ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "bash ~/.claude/skills/grim/grim-statusline.sh" }

FLAG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.grim-active"

# Refuse symlinks — prevent rendering arbitrary file bytes to terminal
[ -L "$FLAG" ] && exit 0
[ ! -f "$FLAG" ] && exit 0

printf '\033[38;5;220m[ME KING]\033[0m'
