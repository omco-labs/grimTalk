#!/usr/bin/env bash
# grim — agentSpawn hook
# STDOUT is injected into agent context by Kiro
SKILL_MD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/SKILL.md"
cat "$SKILL_MD"
