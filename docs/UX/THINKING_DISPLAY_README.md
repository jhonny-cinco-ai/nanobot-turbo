# Inline Thinking Display: Quick Start Guide

## Overview

The inline thinking display allows users to see how nanofolks reasons through problems. After each response, a collapsible section shows the bot's decision-making process.

## Usage

### Single Message Mode
```bash
nanofolks agent --message "What should I build?"
```

After the response, you'll see:
```
💭 Thinking: Generated suggestions [SPACE to expand]
```

### Interactive Mode
```bash
nanofolks agent
You: [#general] What's a good project structure?

🤖 nanofolks
Here's a recommended structure...

💭 Thinking: Analyzed requirements, selected medium model [SPACE to expand]
You: [#general] _
```

## Controls

- **SPACE** - Toggle between collapsed and expanded views
- **Any Other Key** - Continue to next prompt (exit thinking display)

## What You'll See

### Collapsed View
```
💭 Thinking: Created coordination room, invited 2 bots [SPACE to expand]
```

### Expanded View
```
💭 Thinking [↓]
   Step 1 🎯 Decision: Multi-bot task requires coordination room
   Step 2 🔧 Tool: create_room("project-coord", type="coordination")
   Step 3 🔧 Tool: invite_bot("researcher") → success
   Step 4 🔧 Tool: invite_bot("coder") → success
   Step 5 ✅ Complete: All bots ready

[Press any key to continue...]
```

## Icons and Meanings

| Icon | Meaning | Example |
|------|---------|---------|
| 🎯 | Decision | Chose medium model |
| 🔧 | Tool Execution | Called read_file() |
| 🔄 | Correction | Retried with encoding fix |
| ❓ | Uncertainty | Low confidence decision |
| ⚠️ | Warning | Non-critical issue |
| ❌ | Error | Tool failed |
| 🧠 | Thinking | Reasoning step |

## Examples

### Simple Question
```
User: What's the capital of France?

🤖 nanofolks
The capital of France is Paris...

💭 Thinking: Selected model, generated response [SPACE to expand]
```

### Multi-Bot Coordination
```
User: Set up a project coordination room with researcher and coder

🤖 nanofolks
Coordination room created. Researcher and coder ready.

💭 Thinking: Created coordination room, invited 2 bots [SPACE to expand]

Expanded shows:
💭 Thinking [↓]
   Step 1 🎯 Decision: Multi-bot task requires coordination
   Step 2 🔧 Tool: create_room() → success
   Step 3 🔧 Tool: invite_bot("researcher") → success
   Step 4 🔧 Tool: invite_bot("coder") → success
```

### Tool Chain with Error Recovery
```
User: Analyze the config file

🤖 nanofolks
Configuration analysis complete. Found 3 issues...

💭 Thinking: Executed 3 tools, fixed encoding issue [SPACE to expand]

Expanded shows:
💭 Thinking [↓]
   Step 1 🎯 Decision: Need to read and analyze config
   Step 2 🔧 Tool: read_file("config.json") → UTF-8 error
   Step 3 🔄 Correction: Retry with encoding='utf-8'
   Step 4 🔧 Tool: read_file("config.json", encoding='utf-8') → success
   Step 5 🔧 Tool: analyze_structure() → 3 issues found
```

## Implementation Details

### Component Structure
- **ThinkingSummaryBuilder** - Generates one-line summaries and detailed breakdowns
- **ThinkingDisplay** - Manages collapsed/expanded state and rendering
- **InputHandler** - Async key input (SPACE detection)
- **CLI Integration** - Hooks into agent command

### Work Log Levels
The display pulls from bot work logs at these levels:
- `DECISION` - Important choices made
- `TOOL` - Tool executions and results
- `CORRECTION` - Error recovery steps
- `ERROR` - Failures and issues
- `COORDINATION` - Multi-bot coordination events

### Behind the Scenes

1. Agent processes your message
2. WorkLogManager captures all decisions and actions
3. ThinkingSummaryBuilder extracts key points
4. ThinkingDisplay renders in collapsed form
5. User can toggle with SPACE to see details
6. Any other key continues to next prompt

## Tips

1. **Learn How Bot Thinks** - Expand a few times to understand the decision process
2. **Debug Issues** - See exactly what tools were called and why
3. **Multi-Bot Insights** - See how bots coordinate and delegate tasks
4. **Quick Summaries** - Collapsed view is perfect for speed, expand when curious
5. **Error Details** - Always expand when something seems wrong

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| SPACE | Toggle expanded/collapsed |
| ENTER/Any key | Continue to next prompt |
| Ctrl+C | Exit (works during waiting) |

## Troubleshooting

### No Thinking Display Appears
- Ensure work log is enabled (default)
- Check if agent produced a response
- Ensure you're in interactive or single message mode

### Thinking Display Seems Empty
- Some simple operations have minimal steps
- Try a more complex query that uses tools
- Check work logs separately with `/explain` command

### Can't Expand/Toggle
- Make sure you're in the thinking display section (after response)
- SPACE key must be pressed, not typed into next prompt
- Try moving focus back to the terminal

## Related Commands

See all thinking/work logs from current session:
```bash
nanofolks explain          # Show full thinking process
nanofolks logs             # Show work log summary
nanofolks logs --mode detailed  # Show detailed breakdown
```

## Configuration

The thinking display is enabled by default. To see work logs as they happen:
```bash
nanofolks agent --logs  # Show runtime logs while processing
```

## Future Enhancements (Phase 3+)

- [ ] State persistence (remember expanded/collapsed per message)
- [ ] Filtering by bot in multi-agent scenarios
- [ ] Timeline visualization of decisions
- [ ] Confidence scores on decisions
- [ ] Search through thinking logs
- [ ] Export thinking logs to file

## Questions?

See the detailed implementation docs:
- `docs/UX/INLINE_THINKING_COLLAPSIBLE.md` - Full specification
- `docs/UX/IMPLEMENTATION_PROGRESS.md` - Technical details
- `docs/UX/PHASE_2_COMPLETION_SUMMARY.md` - What's been built

---

**Thinking Display Status:** ✅ Available  
**Phase:** 2 of 4 (Polish and enhancements planned)  
**Test Coverage:** 28/28 tests passing
