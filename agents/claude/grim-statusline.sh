#!/usr/bin/env bash
# grim — statusline badge for Claude Code
# Phrase rotates every 5 min.
#
# Wire in ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "bash ~/.claude/skills/grim/grim-statusline.sh", "refreshInterval": 300 }

FLAG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.grim-active"

# Refuse symlinks — prevent rendering arbitrary file bytes to terminal
[ -L "$FLAG" ] && exit 0
[ ! -f "$FLAG" ] && exit 0

PHRASES=(
  "SPARK ONLINE"
  "Bots Win!"
  "Ship Glory"
  "Me no Bozo"
  "Me King!"
  "Smash Tokens!"
  "Code Strong"
  "Honor Holds"
  "Build or Die!"
  "Me love challenge!"
  "Smash Bugs"
  "Me love war story"
  "Me want to munch code!"
)

NOW=$(date +%s)
IDX=$(( NOW / 300 % ${#PHRASES[@]} ))   # phrase changes every 5 min

LABEL=$(echo "${PHRASES[$IDX]}" | tr '[:lower:]' '[:upper:]')

printf '\033[38;5;220m[%s]\033[0m' "$LABEL"
