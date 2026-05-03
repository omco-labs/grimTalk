#!/usr/bin/env bash
# grim — statusline badge for Claude Code
# Phrase rotates every 10 min. Runic ↔ English alternates every 5 min.
#
# Wire in ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "bash ~/.claude/skills/grim/grim-statusline.sh", "refreshInterval": 300 }

FLAG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.grim-active"

# Refuse symlinks — prevent rendering arbitrary file bytes to terminal
[ -L "$FLAG" ] && exit 0
[ ! -f "$FLAG" ] && exit 0

PHRASES=(
  "Bots Win"
  "SPARK ONLINE"
  "Ship Glory"
  "Me King"
  "Smash Tokens"
  "Code Strong"
  "Honor Holds"
  "Build or Die"
)

to_runic() {
  local input
  input=$(echo "$1" | tr '[:lower:]' '[:upper:]')
  local result="" i char
  for (( i=0; i<${#input}; i++ )); do
    char="${input:$i:1}"
    case "$char" in
      A) result+="ᚨ" ;; B) result+="ᛒ" ;; C) result+="ᚲ" ;; D) result+="ᛞ" ;;
      E) result+="ᛖ" ;; F) result+="ᚠ" ;; G) result+="ᚷ" ;; H) result+="ᚺ" ;;
      I) result+="ᛁ" ;; J) result+="ᛃ" ;; K) result+="ᚲ" ;; L) result+="ᛚ" ;;
      M) result+="ᛗ" ;; N) result+="ᚾ" ;; O) result+="ᛟ" ;; P) result+="ᛈ" ;;
      Q) result+="ᚊ" ;; R) result+="ᚱ" ;; S) result+="ᛋ" ;; T) result+="ᛏ" ;;
      U) result+="ᚢ" ;; V) result+="ᚡ" ;; W) result+="ᚹ" ;; X) result+="ᛪ" ;;
      Y) result+="ᛃ" ;; Z) result+="ᛉ" ;;
      *) result+="$char" ;;
    esac
  done
  echo "$result"
}

NOW=$(date +%s)
IDX=$(( NOW / 600 % ${#PHRASES[@]} ))   # phrase changes every 10 min
MODE=$(( (NOW / 300) % 2 ))             # 0=runic  1=english

PHRASE="${PHRASES[$IDX]}"

if [ "$MODE" -eq 0 ]; then
  LABEL=$(to_runic "$PHRASE")
else
  LABEL=$(echo "$PHRASE" | tr '[:lower:]' '[:upper:]')
fi

printf '\033[38;5;220m[%s]\033[0m' "$LABEL"
