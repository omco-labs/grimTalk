# OpenInference + Claude Code Integration Plan

## Goal

Instrument Claude Code agents with OpenInference-compliant OTEL spans for observability in Arize Phoenix or any OTLP-compatible backend.

## Span Coverage

| Span Kind | Source | Status |
|---|---|---|
| `AGENT` | `SessionStart` hook | ✅ feasible |
| `CHAIN` | `UserPromptSubmit` → `Stop` hooks | ✅ feasible (no output content) |
| `TOOL` | `PreToolUse` + `PostToolUse` hooks | ✅ feasible |
| `SUBAGENT` (nested AGENT) | `SubagentStart` + `SubagentStop` hooks | ✅ feasible (bonus vs Kiro) |
| `LLM` | SDK instrumentation | ✅ feasible (not via hooks) |
| `EMBEDDING` | SDK instrumentation | ✅ feasible (not via hooks) |
| `GUARDRAIL` | — | ❌ no hook boundary |
| `RERANKER` | — | ❌ no hook boundary |

## Architecture: Two Layers

### Layer 1 — Hook-based spans (AGENT, CHAIN, TOOL, SUBAGENT)

Hook script reads JSON from stdin (Claude Code's hook contract) and emits OTEL spans.

**Hook → Span mapping:**

```
SessionStart     → open  AGENT span    attrs: openinference.span.kind="AGENT", agent.name, session.id
UserPromptSubmit → open  CHAIN span    attrs: openinference.span.kind="CHAIN", input.value=prompt, session.id
PreToolUse       → open  TOOL span     attrs: openinference.span.kind="TOOL", tool.name, tool_call.function.arguments
PostToolUse      → close TOOL span     attrs: output.value=tool_response, output.mime_type="application/json"
Stop             → close CHAIN span    (timestamp only — last_assistant_message available but no structured output)
SubagentStart    → open  AGENT span    attrs: openinference.span.kind="AGENT", agent.name=agent_type, agent.id, parent=session CHAIN span
SubagentStop     → close AGENT span    attrs: output.value=last_assistant_message
SessionEnd       → close root AGENT span
```

**Hook input contract (stdin JSON):**

All events receive: `session_id`, `hook_event_name`, `transcript_path`, `cwd`

Additional per event:
- `UserPromptSubmit`: `prompt`
- `PreToolUse`: `tool_name`, `tool_input`, `tool_use_id`
- `PostToolUse`: `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `duration_ms`
- `Stop`: `last_assistant_message`, `stop_hook_active`
- `SubagentStart`: `agent_id`, `agent_type`
- `SubagentStop`: `agent_id`, `agent_type`, `last_assistant_message`, `agent_transcript_path`

**Span state:** persist open span context between hook invocations via temp file keyed on `session_id`:
```
/tmp/otel-spans-<session_id>.json
```

**Implementation:** single Bun/TypeScript script `agents/claude/hooks/otel_spans.ts`. Hook type read from `hook_event_name` in stdin JSON.

**Runtime:** [Bun](https://bun.sh) — no compile step, TypeScript native, zero global env pollution.

**Dep strategy — no deps by default:**
- JSONL fallback uses only Bun builtins (`Bun.stdin`, `Bun.file`, `crypto`) — zero npm packages required
- OTLP export is opt-in: run `bun install` in `agents/claude/hooks/` to add `@opentelemetry/sdk-node` + exporter
- Script detects missing OTEL packages at runtime and falls back to JSONL silently

`install.sh` checks for Bun and prints optional OTLP install instructions:
```bash
if ! command -v bun >/dev/null 2>&1; then
  echo "ERROR: bun required for OTEL hook (https://bun.sh)"
  exit 1
fi
# JSONL mode works immediately — no bun install needed
echo "  Optional OTLP export: cd agents/claude/hooks && bun install"
```

**Deps (opt-in, `hooks/package.json`):**
```json
{
  "dependencies": {
    "@opentelemetry/sdk-node": "0.57.0",
    "@opentelemetry/exporter-trace-otlp-grpc": "0.57.0"
  }
}
```

### Layer 2 — SDK instrumentation (LLM, EMBEDDING)

Patch the Anthropic client using `openinference-instrumentation-anthropic` at tool entry point:

```python
from openinference.instrumentation.anthropic import AnthropicInstrumentor
AnthropicInstrumentor().instrument()
```

Captures full `llm.*` attributes: `llm.model_name`, `llm.provider`, `llm.invocation_parameters`, `llm.input_messages.*`, `llm.output_messages.*`, `llm.token_count.*`, `llm.finish_reason`.

## Hook Configuration

### Global (all projects) — `~/.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "PreToolUse": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "SubagentStart": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "SubagentStop": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "bun run ~/.claude/hooks/otel_spans.ts", "async": true}]}]
  }
}
```

All hooks use `async: true` — span emission must not block Claude or affect hook exit codes.

### Per-subagent (optional) — `.claude/agents/<name>.md` frontmatter

Hooks can also be scoped to a specific subagent via frontmatter. `Stop` in frontmatter auto-converts to `SubagentStop` at runtime:

```yaml
---
name: my-agent
description: ...
hooks:
  PreToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: bun run ~/.claude/hooks/otel_spans.ts
          async: true
  Stop:
    - hooks:
        - type: command
          command: bun run ~/.claude/hooks/otel_spans.ts
          async: true
---
```

## Span Export: OTLP with JSONL Fallback

When `OTEL_EXPORTER_OTLP_ENDPOINT` set and reachable → export via OTLP gRPC/HTTP.

When absent or unreachable → write to local JSONL, co-located with Claude Code session logs:

```
~/.claude/projects/<project>/<session-id>.otel.jsonl
```

Session log path available from `transcript_path` in every hook input — derive `.otel.jsonl` path by replacing `.jsonl` suffix.

Each line:
```json
{
  "version": "v1",
  "kind": "OtelSpan",
  "data": {
    "trace_id": "<hex>",
    "span_id": "<hex>",
    "parent_span_id": "<hex | null>",
    "name": "<span name>",
    "kind": "AGENT | CHAIN | TOOL",
    "start_time_unix_nano": 1778113214000000000,
    "end_time_unix_nano": 1778113215000000000,
    "attributes": {
      "openinference.span.kind": "TOOL",
      "session.id": "<session-id>",
      "tool.name": "Bash",
      "input.value": "...",
      "output.value": "..."
    },
    "status": {"code": "OK"}
  }
}
```

Mirrors Claude Code's own session log envelope (`version/kind/data`). Importable into Phoenix via `phoenix.Client().log_traces()`.

### Fallback detection

```ts
async function getExporter(transcriptPath: string) {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  if (endpoint) {
    try {
      // dynamic import — only works if bun install has been run
      const { OTLPTraceExporter } = await import("@opentelemetry/exporter-trace-otlp-grpc");
      return new OTLPTraceExporter({ url: endpoint });
    } catch {}
  }
  // zero-dep fallback
  const otelPath = transcriptPath.replace(".jsonl", ".otel.jsonl");
  return new JsonlFileExporter(otelPath);
}
```

## Key Attributes (OpenInference semantic conventions)

All spans:
- `openinference.span.kind` — required
- `session.id` — from `session_id` in hook input
- `input.value`, `output.value`
- `input.mime_type`, `output.mime_type`

TOOL spans additionally:
- `tool.name` — from `tool_name`
- `tool_call.function.name` — same as `tool_name`
- `tool_call.function.arguments` — JSON string of `tool_input`

AGENT/SUBAGENT spans additionally:
- `agent.name` — from `agent_type` (SubagentStart/Stop) or session agent name
- `openinference.span.kind="AGENT"`

## Advantages Over Kiro

| Feature | Kiro | Claude Code |
|---|---|---|
| Hook input | env vars | stdin JSON (richer, typed) |
| Subagent lifecycle hooks | ❌ | ✅ `SubagentStart`/`SubagentStop` |
| `last_assistant_message` on Stop | ❌ | ✅ partial CHAIN output |
| Per-subagent hook scoping | ❌ | ✅ agent frontmatter |
| `agent_id` for span correlation | ❌ | ✅ |
| Subagent transcript path | ❌ | ✅ `agent_transcript_path` |

## Hard Gaps

- `LLM` span absent without SDK wrap
- `llm.token_count.*`, `llm.cost.*` — API response only
- `llm.input_messages.*` / `llm.output_messages.*` — not in hook payload
- `CHAIN` output: `last_assistant_message` on `Stop` is plain text, not structured
- `GUARDRAIL`, `RERANKER`, `PROMPT` spans — no hook boundary

## Implementation Steps

1. `agents/claude/hooks/otel_spans.ts` — Layer 1 hook script (Bun/TS, JSONL default, OTLP opt-in)
2. `agents/claude/hooks/package.json` — opt-in OTEL deps (`bun install` to enable OTLP)
3. Wire hooks into `~/.claude/settings.json` via `agents/claude/install.sh` (extend existing installer)
4. Extend `install.sh` to check for Bun and copy `hooks/` to `~/.claude/hooks/`
5. Add `openinference-instrumentation-anthropic` to tool deps for Layer 2
6. Patch client in tool entry point
7. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (optional — JSONL active by default)
8. Validate traces in Arize Phoenix or inspect `<session-id>.otel.jsonl`

## Files to Create

```
agents/claude/hooks/otel_spans.ts     — Layer 1 hook script (Bun/TS, JSONL default, OTLP opt-in)
agents/claude/hooks/package.json      — opt-in OTEL deps
docs/openinference-claude-code.md     — setup + env var reference
```
