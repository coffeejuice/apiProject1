# Playwright MCP Debug Macro

Use this when you want one prompt to run a repeatable MCP debugging pass with snapshots, network logs, and console logs.

## Prompt file
- `frontend/e2e/MCP_DEBUG_PROMPT.txt`

## Fast usage
1. Open the prompt file.
2. Copy its full content.
3. Paste it as one message to Codex.

## Adapt for other flows
Change only these parts in the prompt:
- Credentials
- Checkpoints
- Flow steps

Keep the diagnostics block unchanged:
- `browser_snapshot`
- `browser_network_requests` with `includeStatic=false`
- `browser_console_messages` with `level=info`
- `browser_take_screenshot`

## Recommended checkpoint pattern
- Before action
- Immediately after action
- After UI settles
- Final expected state

This pattern makes regressions and flaky behavior much easier to localize.
