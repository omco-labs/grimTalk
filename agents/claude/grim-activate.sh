#!/usr/bin/env bash
# grim — SessionStart hook
# 1. Writes flag file (statusline reads this)
# 2. Emits SKILL.md as session context

FLAG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.grim-active"
SKILL_MD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/SKILL.md"

# Write flag (plain file, never symlink)
[ -L "$FLAG" ] && rm -f "$FLAG"
touch "$FLAG"

cat "$SKILL_MD"
