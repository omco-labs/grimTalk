package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"time"
)

type HookInput struct {
	HookEventName string      `json:"hook_event_name"`
	SessionID     string      `json:"session_id"`
	Cwd           string      `json:"cwd"`
	Prompt        string      `json:"prompt,omitempty"`
	ToolName      string      `json:"tool_name,omitempty"`
	ToolInput     interface{} `json:"tool_input,omitempty"`
	ToolResponse  interface{} `json:"tool_response,omitempty"`
}

type SpanData struct {
	TraceID           string            `json:"trace_id"`
	SpanID            string            `json:"span_id"`
	ParentSpanID      *string           `json:"parent_span_id"`
	Name              string            `json:"name"`
	Kind              string            `json:"kind"`
	StartTimeUnixNano int64             `json:"start_time_unix_nano"`
	EndTimeUnixNano   *int64            `json:"end_time_unix_nano"`
	Attributes        map[string]string `json:"attributes"`
	Status            SpanStatus        `json:"status"`
}

type SpanStatus struct {
	Code string `json:"code"`
}

type SpanState struct {
	TraceID     string  `json:"trace_id"`
	AgentSpanID string  `json:"agent_span_id"`
	AgentStart  int64   `json:"agent_start"`
	ChainSpanID *string `json:"chain_span_id"`
	ChainStart  *int64  `json:"chain_start"`
	ToolSpanID  *string `json:"tool_span_id"`
	ToolStart   *int64  `json:"tool_start"`
	ToolName    *string `json:"tool_name"`
}

type OtelRecord struct {
	Version string   `json:"version"`
	Kind    string   `json:"kind"`
	Data    SpanData `json:"data"`
}

// overrideable in tests
var (
	stateDirOverride string
	otelDirOverride  string
)

func randHex(n int) string {
	b := make([]byte, n)
	rand.Read(b) //nolint:errcheck
	return hex.EncodeToString(b)
}

func nowNano() int64 {
	return time.Now().UnixNano()
}

func statePath(sessionID string) string {
	base := os.TempDir()
	if stateDirOverride != "" {
		base = stateDirOverride
	}
	return filepath.Join(base, "otel-spans-"+sessionID+".json")
}

func otelPath(sessionID string) string {
	if otelDirOverride != "" {
		return filepath.Join(otelDirOverride, sessionID+".otel.jsonl")
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".kiro", "sessions", "cli", sessionID+".otel.jsonl")
}

func loadState(sessionID string) *SpanState {
	data, err := os.ReadFile(statePath(sessionID))
	if err != nil {
		return nil
	}
	var s SpanState
	if err := json.Unmarshal(data, &s); err != nil {
		return nil
	}
	return &s
}

func saveState(sessionID string, state *SpanState) {
	data, _ := json.Marshal(state)
	os.WriteFile(statePath(sessionID), data, 0600) //nolint:errcheck
}

func emitSpan(sessionID string, span SpanData) {
	rec := OtelRecord{Version: "v1", Kind: "OtelSpan", Data: span}
	line, _ := json.Marshal(rec)
	line = append(line, '\n')

	p := otelPath(sessionID)
	os.MkdirAll(filepath.Dir(p), 0755) //nolint:errcheck
	f, err := os.OpenFile(p, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	f.Write(line) //nolint:errcheck
}

func closeSpan(state *SpanState, spanID string, parentID *string, name, kind string, startNano int64, attrs map[string]string, sessionID string) {
	end := nowNano()
	merged := map[string]string{
		"openinference.span.kind": kind,
		"session.id":              sessionID,
	}
	for k, v := range attrs {
		merged[k] = v
	}
	emitSpan(sessionID, SpanData{
		TraceID:           state.TraceID,
		SpanID:            spanID,
		ParentSpanID:      parentID,
		Name:              name,
		Kind:              kind,
		StartTimeUnixNano: startNano,
		EndTimeUnixNano:   &end,
		Attributes:        merged,
		Status:            SpanStatus{Code: "OK"},
	})
}

func onAgentSpawn(input HookInput) {
	state := &SpanState{
		TraceID:     randHex(16),
		AgentSpanID: randHex(8),
		AgentStart:  nowNano(),
	}
	saveState(input.SessionID, state)
}

func onUserPromptSubmit(input HookInput) {
	state := loadState(input.SessionID)
	if state == nil {
		return
	}
	id := randHex(8)
	now := nowNano()
	state.ChainSpanID = &id
	state.ChainStart = &now
	saveState(input.SessionID, state)
}

func onPreToolUse(input HookInput) {
	state := loadState(input.SessionID)
	if state == nil {
		return
	}
	id := randHex(8)
	now := nowNano()
	name := input.ToolName
	if name == "" {
		name = "unknown"
	}
	state.ToolSpanID = &id
	state.ToolStart = &now
	state.ToolName = &name
	saveState(input.SessionID, state)
}

func onPostToolUse(input HookInput) {
	state := loadState(input.SessionID)
	if state == nil || state.ToolSpanID == nil || state.ToolStart == nil {
		return
	}
	toolName := ""
	if state.ToolName != nil {
		toolName = *state.ToolName
	}
	toolInput, _ := json.Marshal(input.ToolInput)
	toolResponse, _ := json.Marshal(input.ToolResponse)
	closeSpan(state, *state.ToolSpanID, state.ChainSpanID,
		"tool:"+toolName, "TOOL", *state.ToolStart,
		map[string]string{
			"tool.name":                    toolName,
			"tool_call.function.name":      toolName,
			"tool_call.function.arguments": string(toolInput),
			"input.value":                  string(toolInput),
			"input.mime_type":              "application/json",
			"output.value":                 string(toolResponse),
			"output.mime_type":             "application/json",
		},
		input.SessionID,
	)
	state.ToolSpanID = nil
	state.ToolStart = nil
	state.ToolName = nil
	saveState(input.SessionID, state)
}

func onStop(input HookInput) {
	state := loadState(input.SessionID)
	if state == nil || state.ChainSpanID == nil || state.ChainStart == nil {
		return
	}
	closeSpan(state, *state.ChainSpanID, &state.AgentSpanID,
		"chain", "CHAIN", *state.ChainStart,
		map[string]string{"input.mime_type": "text/plain"},
		input.SessionID,
	)
	state.ChainSpanID = nil
	state.ChainStart = nil
	saveState(input.SessionID, state)
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil || len(raw) == 0 {
		os.Exit(0)
	}
	var input HookInput
	if err := json.Unmarshal(raw, &input); err != nil {
		os.Exit(0) // non-blocking — never fail the hook
	}
	switch input.HookEventName {
	case "agentSpawn":
		onAgentSpawn(input)
	case "userPromptSubmit":
		onUserPromptSubmit(input)
	case "preToolUse":
		onPreToolUse(input)
	case "postToolUse":
		onPostToolUse(input)
	case "stop":
		onStop(input)
	}
	os.Exit(0)
}
