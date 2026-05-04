> **Disclaimer:** grimTalk is not affiliated with Hasbro or Transformers.

# grimTalk

Compressed bot warrior communication mode for AI coding agents based on [caveman](https://github.com/JuliusBrussee/caveman). 
Cuts token usage ~65% while keeping technical accuracy.

Warrior prose. No fluff. Code strong.

## What it does

- **Grim mode** — terse, fragment-heavy responses. Three intensity levels: `lite`, `full`, `ultra`
- **grim-commit** — Conventional Commits messages, ≤50 char subject
- **grim-review** — one-line PR findings with severity emoji
- **grim-compress** — compresses `.md` memory/doc files to caveman prose (~46% input token savings)
- **grim-stats** — token usage + savings for current session
- **Din-bots** — subagent presets that return compressed tool results, shrinking main context per delegation

## Install

| Agent | Quick start | Full guide |
|-------|------------|------------|
| Claude Code | `bash agents/claude/install.sh` | [docs/install-claude.md](docs/install-claude.md) |
| Kiro CLI | `bash agents/kiro/install.sh` | [docs/install-kiro.md](docs/install-kiro.md) |

All installers support `--force` (reinstall) and `--uninstall`. Restart your agent after install.

## Usage

grimTalk is both a **skill** (slash command) and a **custom agent**. The `/grimTalk` slash command activates the skill. Sub-skill behaviors are triggered by natural language keywords — the model matches them from the injected `SKILL.md`.

### Mode control

| Trigger | What happens |
|---------|-------------|
| `/grimTalk` | Activate full mode (default) |
| `/grimTalk lite` | Professional tight — articles kept, no filler |
| `/grimTalk full` | Classic grim — fragments, short synonyms |
| `/grimTalk ultra` | Max compression — arrows for causality, abbreviate prose |

Technical terms, code symbols, function names, API names, error strings: **never abbreviated** at any level.

Natural language also works: `"din-bot mode"`, `"talk like grim"`, `"less tokens"`, `"smash word"`.

Deactivate: say `stop grim`, `stop din-bot`, or `normal mode`.

### Sub-skills (keyword-triggered)

| Say | What happens |
|-----|-------------|
| `"write a grim-commit"` / `"commit message"` | Terse Conventional Commits message, ≤50 char subject |
| `"review this PR"` / `"code review"` | One-line findings with severity emoji |
| `"compress memory file"` / `"grim-compress <file>"` | Compress `.md` file to caveman prose (runs `python3 -m scripts`) |
| `"grim-help"` / `"what grim commands"` | Quick-reference card |
| `"grim-stats"` | Token usage + savings for current session |
| `"use din-bots"` / `"delegate to subagent"` / `"save context"` | Subagent delegation guide |

## Project structure

```
SKILL.md                  — skill definition loaded by agents
references/
  grim-commit.md          — commit message rules
  grim-review.md          — code review rules
  grim-compress.md        — compression rules
  grim-help.md            — quick-reference card
  grim-stats.md           — token stats rules
  grim-style.md           — style guide & rules for agent prompt
  din-bots.md             — subagent delegation guide
scripts/
  compress.py             — compression orchestrator
  detect.py               — file type detection
  validate.py             — output validation
  benchmark.py            — compression benchmarks
  cli.py                  — CLI entry point
agents/
  kiro/                   — Kiro CLI installer + hooks
  claude/                 — Claude Code installer + hooks
docs/
  install-claude.md       — Claude Code full install guide
  install-kiro.md         — Kiro CLI full install guide
```
