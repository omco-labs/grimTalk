# grimTalk

Compressed communication mode for AI coding agents. Cuts token usage ~65% while keeping technical accuracy.

Warrior prose. No fluff. Code strong.

## What it does

- **Grim mode** — terse, fragment-heavy responses. Three intensity levels: `lite`, `full`, `ultra`
- **grim-commit** — Conventional Commits messages, ≤50 char subject
- **grim-review** — one-line PR findings with severity emoji
- **grim-compress** — compresses `.md` memory/doc files to caveman prose (~46% input token savings)
- **grim-stats** — token usage + savings for current session
- **Din-bots** — subagent presets that return compressed tool results, shrinking main context per delegation

## Install

### Kiro CLI

```bash
bash agents/kiro/install.sh
```

Reinstall: `--force`. Remove: `--uninstall`.

Writes skill files to `~/.kiro/skills/grimTalk/` and agent config to `~/.kiro/agents/grim.json`. Restart Kiro to activate.

#### Optional

Start kiro with the grimTalk agent:
```bash
kiro-cli chat --agent grimTalk
```

Set grim as the default agent:
```bash
kiro-cli settings chat.defaultAgent grimTalk
```

### Claude Code

```bash
bash agents/claude/install.sh
```

Reinstall: `--force`. Remove: `--uninstall`.

Writes skill files to `~/.claude/skills/grimTalk/` and wires `SessionStart` + `UserPromptSubmit` hooks into `~/.claude/settings.json`. Restart Claude Code to activate.

**Requires:** Python 3.10+ (for `grim-compress` only; all other sub-skills are model-driven)

## Usage

grimTalk is both a **skill** (slash command) and a **custom agent**. The `/grim` slash command activates the skill. Sub-skill behaviors are triggered by natural language keywords — the model matches them from the injected `SKILL.md`.

### Mode control

| Trigger | What happens |
|---------|-------------|
| `/grim` | Activate full mode (default) |
| `/grim lite` | Professional tight — articles kept, no filler |
| `/grim full` | Classic grim — fragments, short synonyms |
| `/grim ultra` | Max compression — arrows for causality, abbreviate prose |

Natural language also works: `"din-bot mode"`, `"talk like grim"`, `"less tokens"`, `"smash word"`.

Deactivate: say `stop grim`, `stop din-bot`, or `normal mode`.

### Sub-skills (keyword-triggered)

| Say | What happens |
|-----|-------------|
| `"write a commit"` / `"commit message"` | Terse Conventional Commits message, ≤50 char subject |
| `"review this PR"` / `"code review"` | One-line findings with severity emoji |
| `"compress memory file"` / `"grim-compress <file>"` | Compress `.md` file to caveman prose (runs `python3 -m scripts`) |
| `"grim help"` / `"what grim commands"` | Quick-reference card |
| `"grim stats"` | Token usage + savings for current session |
| `"use din-bots"` / `"delegate to subagent"` / `"save context"` | Subagent delegation guide |

## Intensity levels

| Level | Style |
|-------|-------|
| **lite** | No filler/hedging. Full sentences. Articles kept. |
| **full** | Drop articles, fragments OK, short synonyms. Warrior pride. |
| **ultra** | Abbreviate prose (DB/auth/config/req/res/fn/impl). Arrows for causality. One word when one word enough. |

Technical terms, code symbols, function names, API names, error strings: **never abbreviated** at any level.

## Configure default mode

**Environment variable** (highest priority):
```bash
export GRIM_DEFAULT_MODE=ultra
```

**Config file** (`~/.config/din-bot/config.json`):
```json
{ "defaultMode": "full" }
```

Set `"off"` to disable auto-activation. Resolution: env var > config file > `full`.

## File compression

Requires Python 3.10+. Run from project root:

```bash
python3 -m scripts <filepath>
```

Backs up original as `<name>.original.md`. Skips code/config files automatically. Refuses files likely containing secrets (`.env`, `credentials.*`, etc.).

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
```
