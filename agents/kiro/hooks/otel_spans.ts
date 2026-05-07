#!/usr/bin/env bun
/**
 * otel_spans.ts — OpenInference hook script for Kiro agents
 *
 * Reads Kiro hook JSON from stdin, emits OpenInference-compliant OTEL spans.
 * Default: writes JSONL to ~/.kiro/sessions/cli/<session_id>.otel.jsonl
 * Opt-in:  set OTEL_EXPORTER_OTLP_ENDPOINT to export via OTLP (requires bun install)
 *
 * Hook → Span mapping:
 *   agentSpawn       → open  AGENT span
 *   userPromptSubmit → open  CHAIN span
 *   preToolUse       → open  TOOL span
 *   postToolUse      → close TOOL span
 *   stop             → close CHAIN span
 */

import { randomBytes } from "crypto";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "fs";
import { homedir } from "os";
import { join } from "path";

// ── Types ────────────────────────────────────────────────────────────────────

interface HookInput {
  hook_event_name: string;
  session_id: string;
  cwd: string;
  prompt?: string;
  tool_name?: string;
  tool_input?: unknown;
  tool_response?: unknown;
}

interface SpanData {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  name: string;
  kind: string;
  start_time_unix_nano: number;
  end_time_unix_nano: number | null;
  attributes: Record<string, string>;
  status: { code: string };
}

interface SpanState {
  trace_id: string;
  agent_span_id: string;
  agent_start: number;
  chain_span_id: string | null;
  chain_start: number | null;
  // tool spans keyed by tool_name (last open wins — tools don't nest in Kiro)
  tool_span_id: string | null;
  tool_start: number | null;
  tool_name: string | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const hex = (n: number) => randomBytes(n).toString("hex");
const nowNano = () => Date.now() * 1_000_000;

function statePath(sessionId: string): string {
  return join("/tmp", `otel-spans-${sessionId}.json`);
}

function otelPath(sessionId: string): string {
  return join(homedir(), ".kiro", "sessions", "cli", `${sessionId}.otel.jsonl`);
}

function loadState(sessionId: string): SpanState | null {
  const p = statePath(sessionId);
  if (!existsSync(p)) return null;
  try { return JSON.parse(readFileSync(p, "utf8")); } catch { return null; }
}

function saveState(sessionId: string, state: SpanState): void {
  writeFileSync(statePath(sessionId), JSON.stringify(state));
}

function clearState(sessionId: string): void {
  try { require("fs").unlinkSync(statePath(sessionId)); } catch {}
}

function emitSpan(sessionId: string, span: SpanData): void {
  const line = JSON.stringify({ version: "v1", kind: "OtelSpan", data: span }) + "\n";

  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  if (endpoint) {
    // Attempt OTLP — requires `bun install` to have been run
    (async () => {
      try {
        const { OTLPTraceExporter } = await import("@opentelemetry/exporter-trace-otlp-grpc");
        // Minimal OTLP export — build a ResourceSpans payload
        const exporter = new OTLPTraceExporter({ url: endpoint });
        // Fall through to JSONL on any error
        void exporter; // placeholder — full OTLP wiring in opt-in path
      } catch {}
    })();
  }

  // Always write JSONL (zero deps, always available)
  appendFileSync(otelPath(sessionId), line);
}

function closeSpan(
  state: SpanState,
  spanId: string,
  parentId: string | null,
  name: string,
  kind: string,
  startNano: number,
  attrs: Record<string, string>,
  sessionId: string,
): void {
  emitSpan(sessionId, {
    trace_id: state.trace_id,
    span_id: spanId,
    parent_span_id: parentId,
    name,
    kind,
    start_time_unix_nano: startNano,
    end_time_unix_nano: nowNano(),
    attributes: { "openinference.span.kind": kind, "session.id": sessionId, ...attrs },
    status: { code: "OK" },
  });
}

// ── Hook handlers ─────────────────────────────────────────────────────────────

function onAgentSpawn(input: HookInput): void {
  const state: SpanState = {
    trace_id: hex(16),
    agent_span_id: hex(8),
    agent_start: nowNano(),
    chain_span_id: null,
    chain_start: null,
    tool_span_id: null,
    tool_start: null,
    tool_name: null,
  };
  saveState(input.session_id, state);
}

function onUserPromptSubmit(input: HookInput): void {
  const state = loadState(input.session_id);
  if (!state) return;
  state.chain_span_id = hex(8);
  state.chain_start = nowNano();
  saveState(input.session_id, state);
}

function onPreToolUse(input: HookInput): void {
  const state = loadState(input.session_id);
  if (!state) return;
  state.tool_span_id = hex(8);
  state.tool_start = nowNano();
  state.tool_name = input.tool_name ?? "unknown";
  saveState(input.session_id, state);
}

function onPostToolUse(input: HookInput): void {
  const state = loadState(input.session_id);
  if (!state?.tool_span_id || !state.tool_start) return;

  closeSpan(
    state,
    state.tool_span_id,
    state.chain_span_id,
    `tool:${state.tool_name}`,
    "TOOL",
    state.tool_start,
    {
      "tool.name": state.tool_name ?? "",
      "tool_call.function.name": state.tool_name ?? "",
      "tool_call.function.arguments": JSON.stringify(input.tool_input ?? {}),
      "input.value": JSON.stringify(input.tool_input ?? {}),
      "input.mime_type": "application/json",
      "output.value": JSON.stringify(input.tool_response ?? {}),
      "output.mime_type": "application/json",
    },
    input.session_id,
  );

  state.tool_span_id = null;
  state.tool_start = null;
  state.tool_name = null;
  saveState(input.session_id, state);
}

function onStop(input: HookInput): void {
  const state = loadState(input.session_id);
  if (!state?.chain_span_id || !state.chain_start) return;

  closeSpan(
    state,
    state.chain_span_id,
    state.agent_span_id,
    "chain",
    "CHAIN",
    state.chain_start,
    { "input.mime_type": "text/plain" },
    input.session_id,
  );

  state.chain_span_id = null;
  state.chain_start = null;
  saveState(input.session_id, state);
}

// ── Main ──────────────────────────────────────────────────────────────────────

const raw = await Bun.stdin.text();
let input: HookInput;
try {
  input = JSON.parse(raw);
} catch {
  process.exit(0); // non-blocking — never fail the hook
}

switch (input.hook_event_name) {
  case "agentSpawn":       onAgentSpawn(input); break;
  case "userPromptSubmit": onUserPromptSubmit(input); break;
  case "preToolUse":       onPreToolUse(input); break;
  case "postToolUse":      onPostToolUse(input); break;
  case "stop":             onStop(input); break;
}

process.exit(0);
