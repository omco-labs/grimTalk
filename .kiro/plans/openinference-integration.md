# OpenInference + Kiro Integration Plan

## Goal

Instrument Kiro custom agents with OpenInference-compliant OTEL spans for observability in Arize Phoenix or any OTLP-compatible backend.

## Span Coverage

| Span Kind | Source | Status |
|---|---|---|
| `AGENT` | Kiro hooks | ✅ feasible |
| `CHAIN` | Kiro hooks | ✅ feasible (no output content) |
| `TOOL` | Kiro hooks | ✅ feasible |
| `LLM` | SDK instrumentation | ❌ Kiro owns LLM call — no entry point |
| `EMBEDDING` | SDK instrumentation | ❌ Kiro owns LLM call — no entry point |
| `GUARDRAIL` | — | ❌ no hook boundary |
| `RERANKER` | — | ❌ no hook boundary |
| `PROMPT` | — | ❌ internal to model |

## Architecture: One Layer

Kiro exposes no LLM call boundary — the model invocation is internal to Kiro. SDK instrumentation (patching an Anthropic/OpenAI client) is not possible. Only hook-based spans are feasible.

### Layer 1 — Hook-based spans (AGENT, CHAIN, TOOL)

Hook script reads JSON from stdin and emits OTEL spans.

**Hook → Span mapping:**

```
agentSpawn       → open  AGENT span   attrs: openinference.span.kind="AGENT", agent.name, session.id
userPromptSubmit → open  CHAIN span   attrs: openinference.span.kind="CHAIN", input.value, input.mime_type="text/plain", session.id
preToolUse       → open  TOOL span    attrs: openinference.span.kind="TOOL", tool.name, tool_call.function.name, tool_call.function.arguments
postToolUse      → close TOOL span    attrs: output.value, output.mime_type="application/json"
stop             → close CHAIN span   (timestamp only — response content not in hook payload)
```

**Span state:** persist open span context between hooks via a temp file keyed on `session_id` (e.g. `/tmp/otel-spans-<session_id>.json`).

**Implementation:** single Bun/TypeScript script `agents/kiro/hooks/otel_spans.ts` invoked by all 5 hook events. Hook type read from `hook_event_name` field in stdin JSON (Kiro passes hook context as JSON on stdin, same contract as Claude Code).

**Runtime:** [Bun](https://bun.sh) — no compile step, TypeScript native, zero global env pollution.

**Dep strategy — no deps by default:**
- JSONL fallback uses only Bun builtins (`Bun.stdin`, `Bun.file`, `crypto`) — zero npm packages required
- OTLP export is opt-in: run `bun install` in `agents/kiro/hooks/` to add `@opentelemetry/sdk-node` + exporter
- Script detects missing OTEL packages at runtime and falls back to JSONL silently

`install.sh` checks for Bun and prints optional OTLP install instructions:
```bash
if ! command -v bun >/dev/null 2>&1; then
  echo "ERROR: bun required for OTEL hook (https://bun.sh)"
  exit 1
fi
# JSONL mode works immediately — no bun install needed
echo "  Optional OTLP export: cd agents/kiro/hooks && bun install"
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

### Kiro vs Claude Code hook gaps

Kiro supports: `agentSpawn`, `userPromptSubmit`, `preToolUse`, `postToolUse`, `stop`.

Kiro does **not** have subagent lifecycle hooks (`SubagentStart`/`SubagentStop`). Nested AGENT spans for subagents are not possible via Kiro hooks — Claude Code-only capability. See `openinference-claude-code.md` for full subagent span implementation.

### Layer 2 — SDK instrumentation (LLM, EMBEDDING)

**Not available in Kiro.** Kiro owns the LLM call internally — there is no entry point to patch the Anthropic/OpenAI client. `LLM` and `EMBEDDING` spans cannot be emitted. This is a hard platform constraint, not a gap to be worked around.

For `LLM` span coverage, use Claude Code instead (see `openinference-claude-code.md`).

## Key Attributes (OpenInference semantic conventions)

All spans:
- `openinference.span.kind` — required
- `session.id` — from Kiro `session_id`
- `input.value`, `output.value`
- `input.mime_type`, `output.mime_type`

TOOL spans additionally:
- `tool.name`
- `tool_call.function.name`
- `tool_call.function.arguments` (JSON string)

LLM spans (Layer 2 only — **not available in Kiro**):
- `llm.model_name`, `llm.provider`
- `llm.input_messages.{i}.message.role/content`
- `llm.output_messages.{i}.message.role/content`
- `llm.token_count.prompt`, `llm.token_count.completion`
- `llm.finish_reason`

## Hard Gaps

- `stop` hook carries no response content → CHAIN span has no `output.value`
- `LLM`, `EMBEDDING` spans impossible — Kiro owns the model call, no SDK entry point
- `GUARDRAIL`, `RERANKER`, `PROMPT` spans not possible — no hook boundary
- `llm.*` attributes entirely absent (model name, token counts, messages, finish reason)
- For `LLM` span coverage, use Claude Code (see `openinference-claude-code.md`)

## Span Export: OTLP with JSONL Fallback

When `OTEL_EXPORTER_OTLP_ENDPOINT` is set and reachable → export spans via OTLP gRPC/HTTP to Phoenix or any collector.

When endpoint is absent or unreachable → write spans as JSONL to local file, mirroring Kiro's own session log pattern.

### Local JSONL format

Kiro session logs live at `~/.kiro/sessions/cli/<session-id>.jsonl`. Each line is:
```json
{"version":"v1","kind":"<EventKind>","data":{...}}
```

OTEL span fallback files follow same pattern, co-located alongside session logs:
```
~/.kiro/sessions/cli/<session-id>.otel.jsonl
```

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
      "tool.name": "bash",
      "input.value": "...",
      "output.value": "..."
    },
    "status": {"code": "OK"}
  }
}
```

Attribute names are exact OpenInference semantic convention names — file is valid OTEL JSON export format, importable into Phoenix via `phoenix.Client().log_traces()` or `otel-collector` file receiver.

### Fallback detection logic

```ts
function getExporter(sessionId: string) {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  if (endpoint) {
    try {
      // dynamic import — only works if bun install has been run
      const { OTLPTraceExporter } = await import("@opentelemetry/exporter-trace-otlp-grpc");
      return new OTLPTraceExporter({ url: endpoint });
    } catch {}
  }
  // zero-dep fallback
  const path = `${Bun.env.HOME}/.kiro/sessions/cli/${sessionId}.otel.jsonl`;
  return new JsonlFileExporter(path);
}
```

## Implementation Steps

1. `agents/kiro/hooks/otel_spans.ts` — hook script for Layer 1 (Bun/TS, JSONL default, OTLP opt-in)
2. `agents/kiro/hooks/package.json` — opt-in OTEL deps (`bun install` to enable OTLP)
3. Wire hooks into `grimTalk.json.template` (`preToolUse`, `postToolUse`, `stop` alongside existing hooks)
4. Extend `agents/kiro/install.sh` to check for Bun and copy `hooks/` to `$INSTALL_DIR/hooks/`
5. Set `OTEL_EXPORTER_OTLP_ENDPOINT` env var (optional — JSONL active by default)
6. Validate traces in Arize Phoenix UI or inspect `~/.kiro/sessions/cli/<session-id>.otel.jsonl`

Note: Layer 2 (LLM spans) is not applicable to Kiro. Use Claude Code for full span coverage.

## Files to Create

```
agents/kiro/hooks/otel_spans.ts     — Layer 1 hook script (Bun/TS, JSONL default, OTLP opt-in)
agents/kiro/hooks/package.json      — opt-in OTEL deps
docs/openinference.md               — setup + env var reference
```
