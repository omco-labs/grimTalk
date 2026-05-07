# OpenInference Observability for grimTalk Agents

Emits [OpenInference](https://github.com/Arize-ai/openinference)-compliant OTEL spans from Kiro agent hooks. Spans are written to a local JSONL file by default; OTLP export to Arize Phoenix or any collector is opt-in.

## Span coverage

| Span kind | Hook | Notes |
|---|---|---|
| `AGENT` | `agentSpawn` | Root span for the session |
| `CHAIN` | `userPromptSubmit` → `stop` | One per turn; no output content (Kiro limitation) |
| `TOOL` | `preToolUse` → `postToolUse` | Full input + response |
| `LLM` | — | Not available — Kiro owns the model call |

## Default output (no setup required)

Spans are written to:
```
~/.kiro/sessions/cli/<session-id>.otel.jsonl
```

Each line follows Kiro's session log envelope:
```json
{"version":"v1","kind":"OtelSpan","data":{...}}
```

No dependencies needed. Requires only `bun` (checked by `install.sh`).

## OTLP export (opt-in)

To export spans to Arize Phoenix or any OTLP-compatible collector:

1. Install OTEL deps:
   ```bash
   cd ~/.kiro/skills/grimTalk/hooks && bun install
   ```

2. Set the endpoint before starting Kiro:
   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   ```

3. Start Phoenix locally (optional):
   ```bash
   pip install arize-phoenix
   python -m phoenix.server.main
   # UI at http://localhost:6006
   ```

If `OTEL_EXPORTER_OTLP_ENDPOINT` is set but unreachable, the script falls back to JSONL silently.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP collector URL. If unset, JSONL fallback is used |

## Import JSONL into Phoenix

```python
import phoenix as px
import json
from pathlib import Path

spans = [json.loads(l) for l in Path("~/.kiro/sessions/cli/<session-id>.otel.jsonl").expanduser().read_text().splitlines()]
# phoenix.Client().log_traces(spans)  # exact API depends on phoenix version
```

## Uninstall

```bash
bash agents/kiro/install.sh --uninstall
```

Removes `~/.kiro/skills/grimTalk` including the hooks directory.
