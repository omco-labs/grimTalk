#!/usr/bin/env bash
# grim — Claude Code skill installer
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

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
INSTALL_DIR="$CLAUDE_DIR/skills/grim"
SETTINGS="$CLAUDE_DIR/settings.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 required (https://python.org)"
  exit 1
fi

# ---------- UNINSTALL ----------

if [ "$UNINSTALL" -eq 1 ]; then
  echo "Uninstalling grim..."
  rm -rf "$INSTALL_DIR"
  rm -f "${CLAUDE_DIR}/.grim-active"
  echo "  Removed: $INSTALL_DIR"

  if [ -f "$SETTINGS" ]; then
    cp "$SETTINGS" "$SETTINGS.bak"
    python3 - "$SETTINGS" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    s = json.load(f)
for event in ("SessionStart", "UserPromptSubmit"):
    h = s.get("hooks", {}).get(event, [])
    s.setdefault("hooks", {})[event] = [
        e for e in h
        if not any("grim" in (hk.get("command", "") + hk.get("statusMessage", ""))
                   for hk in e.get("hooks", []))
    ]
    if not s["hooks"][event]:
        del s["hooks"][event]
if not s.get("hooks"):
    s.pop("hooks", None)
with open(path, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
print("  Hooks removed from settings.json")
PY
  fi

  echo ""
  echo "Done. Restart Claude Code."
  exit 0
fi

# ---------- ALREADY INSTALLED CHECK ----------

if [ "$FORCE" -eq 0 ] && [ -f "$INSTALL_DIR/SKILL.md" ] && [ -f "$SETTINGS" ]; then
  if python3 - "$SETTINGS" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    s = json.load(f)
hooks = s.get("hooks", {}).get("SessionStart", [])
wired = any("grim" in hk.get("command", "")
            for e in hooks for hk in e.get("hooks", []))
sys.exit(0 if wired else 1)
PY
  then
    echo "grim already installed. Use --force to reinstall."
    exit 0
  fi
fi

# ---------- INSTALL ----------

echo "Installing grim..."

mkdir -p "$INSTALL_DIR/references"
mkdir -p "$INSTALL_DIR/scripts"

SCRIPT_DIR_REAL="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$SCRIPT_DIR")"
INSTALL_DIR_REAL="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$INSTALL_DIR")"

if [ "$SCRIPT_DIR_REAL" != "$INSTALL_DIR_REAL" ]; then
  cp "$SCRIPT_DIR/../../SKILL.md"              "$INSTALL_DIR/SKILL.md"
  cp "$SCRIPT_DIR/../../references/"*.md       "$INSTALL_DIR/references/"
  cp "$SCRIPT_DIR/../../scripts/"*.py          "$INSTALL_DIR/scripts/"
  cp "$SCRIPT_DIR/grim-statusline.sh"      "$INSTALL_DIR/grim-statusline.sh"
  cp "$SCRIPT_DIR/grim-activate.sh"        "$INSTALL_DIR/grim-activate.sh"
  cp "$SCRIPT_DIR/grim-mode-tracker.py"    "$INSTALL_DIR/grim-mode-tracker.py"
  echo "  Skill files → $INSTALL_DIR"
else
  echo "  Skill files already in place (running from install dir)"
fi

chmod +x "$INSTALL_DIR/grim-statusline.sh"
chmod +x "$INSTALL_DIR/grim-activate.sh"

[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak"

python3 - "$SETTINGS" "$INSTALL_DIR" <<'PY'
import json, sys
settings_path, install_dir = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    s = json.load(f)

s.setdefault("hooks", {})

# SessionStart — activate grim + write flag
# Always replace existing grim entry (ensures activate script is used, not old cat)
s["hooks"].setdefault("SessionStart", [])
s["hooks"]["SessionStart"] = [
    e for e in s["hooks"]["SessionStart"]
    if not any("grim" in hk.get("command", "") for hk in e.get("hooks", []))
]
s["hooks"]["SessionStart"].append({
    "hooks": [{
        "type": "command",
        "command": f'bash "{install_dir}/grim-activate.sh"',
        "timeout": 5,
        "statusMessage": "SPARK ONLINE"
    }]
})
print("  SessionStart hook → settings.json")

# UserPromptSubmit — mode tracker (deactivation + per-turn reinforce)
s["hooks"].setdefault("UserPromptSubmit", [])
has_submit = any(
    "grim" in hk.get("command", "")
    for e in s["hooks"]["UserPromptSubmit"]
    for hk in e.get("hooks", [])
)
if not has_submit:
    s["hooks"]["UserPromptSubmit"].append({
        "hooks": [{
            "type": "command",
            "command": f'python3 "{install_dir}/grim-mode-tracker.py"',
            "timeout": 5,
            "statusMessage": "Tracking grim mode"
        }]
    })
    print("  UserPromptSubmit hook → settings.json")

# statusLine — add if not set, chain if existing command
statusline_cmd = f'bash "{install_dir}/grim-statusline.sh"'
if not s.get("statusLine"):
    s["statusLine"] = {"type": "command", "command": statusline_cmd}
    print("  statusLine badge → settings.json")
else:
    existing = s["statusLine"]
    if isinstance(existing, dict) and existing.get("type") == "command":
        existing_cmd = existing.get("command", "")
        if "grim" not in existing_cmd:
            existing["command"] = existing_cmd + f'; {statusline_cmd}'
            print("  statusLine badge chained to existing statusLine")
    else:
        print(f"  NOTE: statusLine already set (non-command type). Add manually:")
        print(f"    {statusline_cmd}")

# Caveman conflict — disable if detected
caveman_disabled = []

plugins = s.get("enabledPlugins", {})
if plugins.get("caveman@caveman"):
    plugins["caveman@caveman"] = False
    caveman_disabled.append("plugin disabled")

for event in ("SessionStart", "UserPromptSubmit"):
    hooks_list = s.get("hooks", {}).get(event, [])
    filtered = [
        e for e in hooks_list
        if not any("caveman" in (hk.get("command", "") + hk.get("statusMessage", ""))
                   for hk in e.get("hooks", []))
    ]
    if len(filtered) < len(hooks_list):
        s["hooks"][event] = filtered
        caveman_disabled.append(f"{event} hook removed")

if isinstance(s.get("statusLine"), dict):
    cmd = s["statusLine"].get("command", "")
    if "caveman" in cmd:
        parts = [p.strip() for p in cmd.split(";") if "caveman" not in p]
        s["statusLine"]["command"] = "; ".join(parts)
        caveman_disabled.append("statusLine cleaned")

if caveman_disabled:
    print("  Caveman conflict resolved: " + ", ".join(caveman_disabled))

with open(settings_path, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
PY

# Remove caveman flag file so badge clears immediately
CAVEMAN_FLAG="${CLAUDE_DIR}/.caveman-active"
if [ -f "$CAVEMAN_FLAG" ] && [ ! -L "$CAVEMAN_FLAG" ]; then
  rm -f "$CAVEMAN_FLAG"
  echo "  .caveman-active flag removed"
fi

echo ""
echo "Done. Restart Claude Code to activate."
echo ""
echo "  Skill files: $INSTALL_DIR"
echo "  Badge:       [ME KING] shown in statusline when grim active"
echo ""
echo "  Deactivate:  say 'stop grim' or 'normal mode'"
echo "  Uninstall:   bash install.sh --uninstall"
