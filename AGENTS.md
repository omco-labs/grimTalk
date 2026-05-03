# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**grim** is a token-compression skill for AI coding agents. It wires into Claude Code (and Kiro) via hooks, emitting a terse warrior-bot communication mode. ~65% token reduction with full technical accuracy preserved.

Two layers:
1. **Model-driven** — SKILL.md prompt defines style rules; hooks inject it into context each session
2. **Python-based** — `scripts/` compresses `.md` files via Claude API with validation + retry

## Commands

### Install / Uninstall

```bash
# Claude Code
bash agents/claude/install.sh [--force | --uninstall]

# Kiro CLI
bash agents/kiro/install.sh [--force | --uninstall]
```

### File Compression (requires Python 3.10+)

```bash
# Compress a single .md file in-place (backs up original as <name>.original.md)
python3 -m scripts <filepath>
```

### Benchmark

```bash
# Compare two files (original vs compressed)
python3 scripts/benchmark.py original.md compressed.md

# Glob mode — benchmark a directory of pairs
python3 scripts/benchmark.py "references/*.md"
```

## Architecture

### Hook Flow

```
SessionStart → grim-activate.sh
  → writes ~/.claude/.grim-active flag
  → emits SKILL.md into model context

UserPromptSubmit → grim-mode-tracker.py
  → detects "stop grim" / "normal mode"  → deletes flag
  → detects "grim mode" / "activate grim" → writes flag
  → if flag exists → injects reinforcement prompt into context
```

State is flag-based (`~/.claude/.grim-active`). The model reads SKILL.md once at session start; the hook reinforces it each turn.

### Compression Pipeline (`scripts/`)

```
cli.py → detect.py (is this file compressible?)
       → compress.py → call_claude() (API or CLI fallback)
       → validate.py  (headings/code/URLs/bullets preserved?)
       → retry with cherry-pick fixes (up to 2 retries)
       → restore original on failure
```

- `compress.py` calls Claude directly via `ANTHROPIC_API_KEY` or falls back to `claude` CLI (desktop auth)
- `validate.py` checks structural invariants: heading count/order, code blocks exact, URLs exact, inline code preserved
- On validation failure, `compress.py` sends a targeted fix prompt (not a full recompress)
- Sensitive paths (`*.env`, `credentials.*`, `.ssh/`, `.aws/`) are refused before compression

### References (`references/`)

Prompt templates loaded on-demand by sub-skill triggers. Not active unless the user invokes the sub-skill:

| File | Trigger |
|------|---------|
| `grim-commit.md` | "write a commit" / `/grim-commit` |
| `grim-review.md` | "review this PR" / `/grim-review` |
| `grim-compress.md` | `/grim-compress <file>` |
| `grim-help.md` | `/grim-help` |
| `grim-stats.md` | `/grim-stats` |
| `grim-style.md` | Core styleguide (loaded with SKILL.md) |
| `dinobots.md` | "use dinobots" / "delegate to subagent" |

### SKILL.md vs CLAUDE.md

`SKILL.md` is the user-facing skill definition (used by the harness to inject context). `CLAUDE.md` is for developers working in this repo. Don't conflate them.

## Key Design Constraints

- **Intensity levels**: `lite` (articles kept, full sentences), `full` (default, fragments OK), `ultra` (abbreviate prose, arrows for causality). Code symbols, API names, error strings: never abbreviated at any level.
- **Auto-clarity**: Drop grim prose for security warnings, irreversible action confirmations, and any place compression creates ambiguous ordering.
- **Backup before compress**: `compress.py` always writes `<name>.original.md` and verifies it before touching the primary file.
- **No outer fence**: Compression prompt instructs Claude to return raw content, not wrapped in ` ```markdown ``` `, to prevent double-fencing when written to disk.
- **Caveman conflict**: Install script detects and disables the legacy `caveman` plugin (grim's predecessor).

## Default Mode Configuration

Priority order (highest first):
1. `GRIM_DEFAULT_MODE` env var
2. `~/.config/dinobot/config.json` → `{"defaultMode": "full"}`
3. Hardcoded: `full`
