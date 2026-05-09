package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// TestMain enables subprocess-based tests for main() stdin/exit behavior.
func TestMain(m *testing.M) {
	if os.Getenv("TEST_MAIN") == "1" {
		main()
	}
	os.Exit(m.Run())
}

// withTempDirs redirects state and OTEL output to t.TempDir() for test isolation.
func withTempDirs(t *testing.T) {
	t.Helper()
	dir := t.TempDir()
	stateDirOverride = filepath.Join(dir, "state")
	otelDirOverride = filepath.Join(dir, "otel")
	os.MkdirAll(stateDirOverride, 0755)  //nolint:errcheck
	os.MkdirAll(otelDirOverride, 0755)   //nolint:errcheck
	t.Cleanup(func() {
		stateDirOverride = ""
		otelDirOverride = ""
	})
}

func readSpans(t *testing.T, sessionID string) []OtelRecord {
	t.Helper()
	data, err := os.ReadFile(otelPath(sessionID))
	if err != nil {
		return nil
	}
	var records []OtelRecord
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		if line == "" {
			continue
		}
		var rec OtelRecord
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			t.Fatalf("invalid JSONL: %v\nline: %s", err, line)
		}
		records = append(records, rec)
	}
	return records
}

// runMain invokes main() in a subprocess with the given stdin payload.
// Returns the exit code.
func runMain(t *testing.T, stdin string) int {
	t.Helper()
	dir := t.TempDir()
	cmd := exec.Command(os.Args[0], "-test.run=TestMain")
	cmd.Env = append(os.Environ(),
		"TEST_MAIN=1",
		"OTEL_DIR_OVERRIDE="+filepath.Join(dir, "otel"),
		"STATE_DIR_OVERRIDE="+filepath.Join(dir, "state"),
	)
	cmd.Stdin = strings.NewReader(stdin)
	err := cmd.Run()
	if err != nil {
		if exit, ok := err.(*exec.ExitError); ok {
			return exit.ExitCode()
		}
		return -1
	}
	return 0
}

// ── Unit tests ────────────────────────────────────────────────────────────────

func TestRandHex(t *testing.T) {
	if got := len(randHex(8)); got != 16 {
		t.Errorf("randHex(8): want len 16, got %d", got)
	}
	if got := len(randHex(16)); got != 32 {
		t.Errorf("randHex(16): want len 32, got %d", got)
	}
	if randHex(8) == randHex(8) {
		t.Error("randHex returned identical values (collision)")
	}
}

func TestStateRoundtrip(t *testing.T) {
	withTempDirs(t)
	sid := "rt-test"
	chainID := "chain-abc"
	state := &SpanState{
		TraceID:     "trace-xyz",
		AgentSpanID: "agent-123",
		AgentStart:  nowNano(),
		ChainSpanID: &chainID,
	}
	saveState(sid, state)
	got := loadState(sid)
	if got == nil {
		t.Fatal("loadState returned nil after saveState")
	}
	if got.TraceID != "trace-xyz" {
		t.Errorf("TraceID: want %q, got %q", "trace-xyz", got.TraceID)
	}
	if got.ChainSpanID == nil || *got.ChainSpanID != chainID {
		t.Errorf("ChainSpanID: want %q, got %v", chainID, got.ChainSpanID)
	}
}

func TestLoadState_Missing(t *testing.T) {
	withTempDirs(t)
	if loadState("does-not-exist") != nil {
		t.Error("expected nil for missing state file")
	}
}

func TestLoadState_Corrupt(t *testing.T) {
	withTempDirs(t)
	sid := "corrupt"
	os.WriteFile(statePath(sid), []byte("not json{{{"), 0600) //nolint:errcheck
	if loadState(sid) != nil {
		t.Error("expected nil for corrupt state file")
	}
}

// ── Handler tests ─────────────────────────────────────────────────────────────

func TestOnAgentSpawn_CreatesState(t *testing.T) {
	withTempDirs(t)
	sid := "spawn-test"
	onAgentSpawn(HookInput{SessionID: sid})
	state := loadState(sid)
	if state == nil {
		t.Fatal("state not created by agentSpawn")
	}
	if state.TraceID == "" {
		t.Error("TraceID empty")
	}
	if state.AgentSpanID == "" {
		t.Error("AgentSpanID empty")
	}
	if state.AgentStart == 0 {
		t.Error("AgentStart not set")
	}
	if state.ChainSpanID != nil || state.ToolSpanID != nil {
		t.Error("chain/tool fields should be nil after spawn")
	}
}

func TestOnAgentSpawn_EmitsNoSpans(t *testing.T) {
	withTempDirs(t)
	sid := "spawn-no-emit"
	onAgentSpawn(HookInput{SessionID: sid})
	if spans := readSpans(t, sid); len(spans) != 0 {
		t.Errorf("agentSpawn should emit no spans, got %d", len(spans))
	}
}

func TestOnUserPromptSubmit_NoState(t *testing.T) {
	withTempDirs(t)
	onUserPromptSubmit(HookInput{SessionID: "no-state"}) // must not panic
}

func TestOnUserPromptSubmit_SetsChain(t *testing.T) {
	withTempDirs(t)
	sid := "prompt-test"
	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid, Prompt: "hello"})
	state := loadState(sid)
	if state.ChainSpanID == nil {
		t.Error("ChainSpanID not set after userPromptSubmit")
	}
	if state.ChainStart == nil {
		t.Error("ChainStart not set after userPromptSubmit")
	}
}

func TestOnPreToolUse_SetsToolState(t *testing.T) {
	withTempDirs(t)
	sid := "pre-test"
	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Read"})
	state := loadState(sid)
	if state.ToolSpanID == nil {
		t.Error("ToolSpanID not set")
	}
	if state.ToolStart == nil {
		t.Error("ToolStart not set")
	}
	if state.ToolName == nil || *state.ToolName != "Read" {
		t.Errorf("ToolName: want %q, got %v", "Read", state.ToolName)
	}
}

func TestOnPreToolUse_EmptyNameDefaultsToUnknown(t *testing.T) {
	withTempDirs(t)
	sid := "empty-tool"
	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: ""})
	state := loadState(sid)
	if state.ToolName == nil || *state.ToolName != "unknown" {
		t.Errorf("empty ToolName: want %q, got %v", "unknown", state.ToolName)
	}
}

func TestOnPreToolUse_NoState(t *testing.T) {
	withTempDirs(t)
	onPreToolUse(HookInput{SessionID: "no-state", ToolName: "X"}) // must not panic
}

func TestOnPostToolUse_NoState(t *testing.T) {
	withTempDirs(t)
	onPostToolUse(HookInput{SessionID: "no-state"}) // must not panic
}

func TestOnPostToolUse_NoToolSpan(t *testing.T) {
	withTempDirs(t)
	sid := "no-tool-span"
	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPostToolUse(HookInput{SessionID: sid}) // preToolUse never called — must not panic
	if spans := readSpans(t, sid); len(spans) != 0 {
		t.Errorf("expected no spans, got %d", len(spans))
	}
}

func TestOnStop_NoState(t *testing.T) {
	withTempDirs(t)
	onStop(HookInput{SessionID: "no-state"}) // must not panic
}

func TestOnStop_NoChain(t *testing.T) {
	withTempDirs(t)
	sid := "no-chain"
	onAgentSpawn(HookInput{SessionID: sid})
	onStop(HookInput{SessionID: sid}) // userPromptSubmit never called — must not panic
	if spans := readSpans(t, sid); len(spans) != 0 {
		t.Errorf("expected no spans, got %d", len(spans))
	}
}

// ── Full pipeline ─────────────────────────────────────────────────────────────

func TestFullPipeline_TwoSpansEmitted(t *testing.T) {
	withTempDirs(t)
	sid := "pipeline"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid, Prompt: "build it"})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Write"})
	onPostToolUse(HookInput{
		SessionID:    sid,
		ToolName:     "Write",
		ToolInput:    map[string]string{"path": "/tmp/x"},
		ToolResponse: map[string]string{"ok": "true"},
	})
	onStop(HookInput{SessionID: sid})

	spans := readSpans(t, sid)
	if len(spans) != 2 {
		t.Fatalf("expected 2 spans, got %d", len(spans))
	}
}

func TestFullPipeline_ConsistentTraceID(t *testing.T) {
	withTempDirs(t)
	sid := "trace-consistent"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Bash"})
	onPostToolUse(HookInput{SessionID: sid, ToolName: "Bash", ToolInput: nil, ToolResponse: nil})
	onStop(HookInput{SessionID: sid})

	spans := readSpans(t, sid)
	if len(spans) < 2 {
		t.Fatalf("expected ≥2 spans, got %d", len(spans))
	}
	traceID := spans[0].Data.TraceID
	for i, s := range spans {
		if s.Data.TraceID != traceID {
			t.Errorf("span[%d] trace_id %q != %q", i, s.Data.TraceID, traceID)
		}
	}
}

func TestFullPipeline_SpanKinds(t *testing.T) {
	withTempDirs(t)
	sid := "kinds"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Read"})
	onPostToolUse(HookInput{SessionID: sid, ToolName: "Read"})
	onStop(HookInput{SessionID: sid})

	kinds := map[string]bool{}
	for _, s := range readSpans(t, sid) {
		kinds[s.Data.Kind] = true
	}
	if !kinds["TOOL"] {
		t.Error("no TOOL span emitted")
	}
	if !kinds["CHAIN"] {
		t.Error("no CHAIN span emitted")
	}
}

func TestFullPipeline_ParentLinkage(t *testing.T) {
	withTempDirs(t)
	sid := "parent-link"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Edit"})
	onPostToolUse(HookInput{SessionID: sid, ToolName: "Edit"})
	onStop(HookInput{SessionID: sid})

	var toolSpan, chainSpan SpanData
	for _, s := range readSpans(t, sid) {
		if s.Data.Kind == "TOOL" {
			toolSpan = s.Data
		} else {
			chainSpan = s.Data
		}
	}
	if toolSpan.ParentSpanID == nil || *toolSpan.ParentSpanID != chainSpan.SpanID {
		t.Errorf("TOOL parent_span_id %v != CHAIN span_id %q", toolSpan.ParentSpanID, chainSpan.SpanID)
	}
}

func TestFullPipeline_TimingValid(t *testing.T) {
	withTempDirs(t)
	sid := "timing"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Bash"})
	onPostToolUse(HookInput{SessionID: sid, ToolName: "Bash"})
	onStop(HookInput{SessionID: sid})

	for _, s := range readSpans(t, sid) {
		if s.Data.EndTimeUnixNano == nil {
			t.Errorf("span %q has nil end_time", s.Data.Name)
			continue
		}
		if *s.Data.EndTimeUnixNano < s.Data.StartTimeUnixNano {
			t.Errorf("span %q end_time < start_time", s.Data.Name)
		}
	}
}

func TestFullPipeline_RequiredAttributes(t *testing.T) {
	withTempDirs(t)
	sid := "attrs"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Bash"})
	onPostToolUse(HookInput{
		SessionID:    sid,
		ToolName:     "Bash",
		ToolInput:    map[string]string{"command": "ls"},
		ToolResponse: "output",
	})
	onStop(HookInput{SessionID: sid})

	required := []string{
		"openinference.span.kind",
		"session.id",
		"tool.name",
		"tool_call.function.name",
		"tool_call.function.arguments",
		"input.value",
		"input.mime_type",
		"output.value",
		"output.mime_type",
	}
	for _, s := range readSpans(t, sid) {
		if s.Data.Kind != "TOOL" {
			continue
		}
		for _, key := range required {
			if _, ok := s.Data.Attributes[key]; !ok {
				t.Errorf("TOOL span missing attribute %q", key)
			}
		}
		if s.Data.Attributes["session.id"] != sid {
			t.Errorf("session.id: want %q, got %q", sid, s.Data.Attributes["session.id"])
		}
		if s.Data.Attributes["tool.name"] != "Bash" {
			t.Errorf("tool.name: want %q, got %q", "Bash", s.Data.Attributes["tool.name"])
		}
	}
}

func TestFullPipeline_StateCleanedUp(t *testing.T) {
	withTempDirs(t)
	sid := "cleanup"

	onAgentSpawn(HookInput{SessionID: sid})
	onUserPromptSubmit(HookInput{SessionID: sid})
	onPreToolUse(HookInput{SessionID: sid, ToolName: "Read"})
	onPostToolUse(HookInput{SessionID: sid, ToolName: "Read"})
	onStop(HookInput{SessionID: sid})

	state := loadState(sid)
	if state == nil {
		t.Fatal("state file missing after pipeline")
	}
	if state.ToolSpanID != nil {
		t.Error("ToolSpanID should be nil after postToolUse")
	}
	if state.ChainSpanID != nil {
		t.Error("ChainSpanID should be nil after stop")
	}
}

// ── stdin / exit behavior (subprocess) ───────────────────────────────────────

func TestMain_MalformedJSON_ExitsZero(t *testing.T) {
	if code := runMain(t, "{not valid json"); code != 0 {
		t.Errorf("malformed JSON: want exit 0, got %d", code)
	}
}

func TestMain_EmptyStdin_ExitsZero(t *testing.T) {
	if code := runMain(t, ""); code != 0 {
		t.Errorf("empty stdin: want exit 0, got %d", code)
	}
}

func TestMain_UnknownEvent_ExitsZero(t *testing.T) {
	payload := `{"hook_event_name":"unknownEvent","session_id":"x","cwd":"/tmp"}`
	if code := runMain(t, payload); code != 0 {
		t.Errorf("unknown event: want exit 0, got %d", code)
	}
}
