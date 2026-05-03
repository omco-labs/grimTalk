#!/usr/bin/env bash
# grimTalk — Kiro CLI skill installer
# Usage:
#   bash install.sh              install
#   bash install.sh --force      reinstall over existing
#   bash install.sh --uninstall  remove
set -euo pipefail

FORCE=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    --uninstall) UNINSTALL=1 ;;
  esac
done

KIRO_DIR="${KIRO_CONFIG_DIR:-$HOME/.kiro}"
INSTALL_DIR="$KIRO_DIR/skills/grimTalk"
AGENT_FILE="$KIRO_DIR/agents/grim.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- UNINSTALL ----------

if [ "$UNINSTALL" -eq 1 ]; then
  echo "Uninstalling grim..."
  rm -rf "$INSTALL_DIR"
  rm -f "$AGENT_FILE"
  rm -f "$KIRO_DIR/.grim-active"
  echo "  Removed: $INSTALL_DIR"
  echo "  Removed: $AGENT_FILE"
  echo ""
  echo "Done. Restart Kiro to deactivate."
  exit 0
fi

# ---------- ALREADY INSTALLED CHECK ----------

if [ "$FORCE" -eq 0 ] && [ -f "$AGENT_FILE" ]; then
  echo "grim already installed. Use --force to reinstall."
  exit 0
fi

# ---------- INSTALL ----------

echo "Installing grimTalk..."

mkdir -p "$INSTALL_DIR/references"
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$KIRO_DIR/agents"

cp "$SCRIPT_DIR/../../SKILL.md"              "$INSTALL_DIR/SKILL.md"
cp "$SCRIPT_DIR/../../references/"*.md       "$INSTALL_DIR/references/"
cp "$SCRIPT_DIR/../../scripts/"*.py          "$INSTALL_DIR/scripts/"
cp "$SCRIPT_DIR/grim-activate.sh"        "$INSTALL_DIR/grim-activate.sh"
cp "$SCRIPT_DIR/grim-mode-tracker.py"    "$INSTALL_DIR/grim-mode-tracker.py"
echo "  Skill files → $INSTALL_DIR"

chmod +x "$INSTALL_DIR/grim-activate.sh"

# Write agent config with resolved install path
sed "s|INSTALL_DIR|$INSTALL_DIR|g" "$SCRIPT_DIR/grim.json.template" > "$AGENT_FILE"
echo "  Agent config → $AGENT_FILE"

echo ""
echo "Done. Restart Kiro to activate."
echo ""
echo "  Skill files: $INSTALL_DIR"
echo "  Agent:       $AGENT_FILE"
echo ""
echo "  Deactivate:  say 'stop grim' or 'normal mode'"
echo "  Uninstall:   bash install.sh --uninstall"
