<img src="docs/grimTalk.svg" alt="grimTalk logo" height="100" align="left">

> **Disclaimer:** grimTalk is not affiliated with Hasbro or Transformers.

# grimTalk

Turse Bot Warrior communication mode for AI coding agents based on [caveman](https://github.com/JuliusBrussee/caveman). 
Cuts token usage ~65% while keeping technical accuracy.

Warrior prose. No fluff. Code strong.

## What it does

- **Grim mode** — terse, fragment-heavy bot warrior responses.
- **grim-commit** — Conventional Commits messages, ≤50 char subject
- **grim-review** — one-line PR findings with severity emoji
- **grim-compress** — compresses `.md` memory/doc files to caveman-like prose (~46% input token savings)
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
| `/grimTalk` | Classic grim — fragments, short synonyms |

Technical terms, code symbols, function names, API names, error strings: **never abbreviated** at any level.

Natural language also works: `"din-bot mode"`, `"talk like grim"`, `"less tokens"`, `"smash word"`.

Deactivate: say `stop grim`, `stop din-bot`, or `normal mode`.

### Sub-skills (keyword-triggered)

| Say | What happens |
|-----|-------------|
| `"write a grim-commit"` / `"commit message"` | Terse Conventional Commits message, ≤50 char subject |
| `"grim-review this PR"` / `"code review"` | One-line findings with severity emoji |
| `"grim-compress file"` / `"grim-compress <file>"` | Compress `.md` file to caveman prose (runs `python3 -m scripts`) |
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
