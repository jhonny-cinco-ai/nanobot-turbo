# Dynamic Layout System Proposal

**Version:** 1.0  
**Date:** 2026-02-16  
**Status:** Proposal  

## Executive Summary

The Dynamic Layout System transforms nanofolks from a static chat interface into an adaptive workspace that morphs based on user needs and AI-driven context. By treating layout changes as first-class tools available to AI bots, we enable context-aware UI that evolves with the conversation.

## Core Concept: Layout as a Tool

Just as bots use tools like `web_search`, `file_read`, or `post_tweet`, they now have access to layout manipulation tools:

- `set_layout` - Change overall workspace configuration
- `open_panel` - Add a new panel to the workspace
- `close_panel` - Remove a panel
- `update_panel` - Modify panel content or properties
- `focus_panel` - Set keyboard/input focus

This unified architecture treats UI adaptation as just another action the AI can take, making it transparent, composable, and user-controllable.

## Layout Configurations

### Base Layouts

| Layout | Description | Use Case |
|--------|-------------|----------|
| **single** | One full-panel view | Focused chat, reading mode |
| **split-vertical** | Two panels side-by-side | Chat + editor, comparison views |
| **split-horizontal** | Two panels stacked | Chat + preview, timeline views |
| **triad-left** | One large left, two stacked right | Main work + references |
| **triad-right** | Two stacked left, one large right | References + main work |
| **quad** | Four equal panels | Dashboard, multi-tasking |
| **asymmetric** | Custom sizing (e.g., 30/70, 40/60) | Flexible workspaces |

### Layout Transitions

Layouts can transition smoothly with animations:
- **Instant** - Immediate switch (for quick context changes)
- **Animated** - Smooth morphing (300-500ms)
- **Staged** - Step-by-step panel addition/removal

## Panel Types

### Core Panels

| Panel | Description | Capabilities |
|-------|-------------|--------------|
| **chat** | Main conversation view | Messages, typing indicators, mentions |
| **editor** | Text/code editor | Syntax highlighting, collaborative editing |
| **canvas** | Visual workspace | Diagrams, whiteboard, mind maps |
| **preview** | Rendered output | Markdown, HTML, images, videos |
| **data** | Structured data views | Tables, charts, metrics, JSON |
| **browser** | Embedded web view | Documentation, external tools |
| **timeline** | Chronological views | Task history, activity logs |
| **gallery** | Media grid | Images, screenshots, assets |

### Panel Properties

Each panel has:
- **id** - Unique identifier
- **type** - Panel type
- **title** - Display title
- **content** - Current content/state
- **editable** - Can user edit?
- **closable** - Can user close?
- **collapsible** - Can minimize to sidebar?
- **participants** - Which bots are active in this panel

## Tool Specifications

### 1. set_layout

Changes the overall workspace layout configuration.

**Parameters:**
```json
{
  "layout": "split-vertical",
  "animation": "smooth",
  "panels": [
    {
      "id": "main-chat",
      "type": "chat",
      "position": "left",
      "size": "50%",
      "title": "Coffee Shop Project"
    },
    {
      "id": "name-editor",
      "type": "editor",
      "position": "right",
      "size": "50%",
      "title": "coffee-names.md",
      "file": "workspaces/branding/coffee-names.md",
      "editable": true
    }
  ],
  "persist": true
}
```

**Behavior:**
- If panels already exist with same ID, update their positions
- If new panels specified, create them
- If panels omitted, close them
- If `persist: true`, save layout to workspace state

### 2. open_panel

Adds a new panel to the current layout.

**Parameters:**
```json
{
  "panel": {
    "id": "research-data",
    "type": "data",
    "title": "Coffee Shop Research",
    "position": "right",
    "size": "40%",
    "content": {
      "type": "table",
      "data": [...],
      "columns": ["Name", "Location", "Style"]
    }
  },
  "focus": false
}
```

**Behavior:**
- Automatically adjusts existing panels to accommodate
- If no space available, converts to appropriate multi-panel layout
- If `focus: true`, immediately focuses the new panel

### 3. close_panel

Removes a panel from the workspace.

**Parameters:**
```json
{
  "panelId": "research-data",
  "confirm": false,
  "saveContent": true
}
```

**Behavior:**
- If panel has unsaved changes and `saveContent: true`, auto-save first
- If `confirm: true` and unsaved changes, prompt user
- Redistributes space to remaining panels

### 4. update_panel

Modifies panel content or properties.

**Parameters:**
```json
{
  "panelId": "name-editor",
  "updates": {
    "title": "coffee-names-final.md",
    "content": "...",
    "highlightLines": [5, 6, 7],
    "participants": ["@creative", "@user"]
  }
}
```

**Behavior:**
- Partial updates - only specified fields change
- Content updates maintain scroll position when possible
- Participant changes update @mention autocomplete

### 5. focus_panel

Sets input focus to a specific panel.

**Parameters:**
```json
{
  "panelId": "name-editor",
  "cursorPosition": "end"
}
```

## json-render Integration

The Dynamic Layout System integrates seamlessly with json-render for rich component rendering within panels.

### Component Catalog for Layouts

```typescript
const layoutComponentCatalog = {
  components: {
    LayoutContainer: {
      props: z.object({
        layout: z.enum(['single', 'split-vertical', 'split-horizontal', 'quad']),
        panels: z.array(z.object({
          id: z.string(),
          type: z.string(),
          position: z.string(),
          size: z.string()
        }))
      })
    },
    ChatPanel: {
      props: z.object({
        roomId: z.string(),
        messages: z.array(messageSchema),
        participants: z.array(z.string())
      })
    },
    EditorPanel: {
      props: z.object({
        file: z.string(),
        content: z.string(),
        language: z.string(),
        readonly: z.boolean()
      })
    },
    DataPanel: {
      props: z.object({
        viewType: z.enum(['table', 'chart', 'json', 'cards']),
        data: z.any(),
        schema: z.object({}).optional()
      })
    }
  }
};
```

### AI-Generated Layout Specs

Bots can return layout specifications as part of their response:

```json
{
  "type": "multi-part",
  "parts": [
    {
      "type": "text",
      "content": "I've gathered research on coffee shop names. Let's organize them in a document."
    },
    {
      "type": "layout_action",
      "action": "set_layout",
      "params": {
        "layout": "split-vertical",
        "panels": [
          {
            "id": "chat",
            "type": "chat",
            "position": "left"
          },
          {
            "id": "editor",
            "type": "editor",
            "position": "right",
            "file": "coffee-names.md",
            "content": "# Coffee Shop Name Ideas\n\n## Based on Research\n\n1. ..."
          }
        ]
      }
    }
  ]
}
```

## Workflow Examples

### Example 1: Coffee Shop Branding

**User:** "I want to work on the idea for my coffee shop, its going to have A and B, plus Z. So first i want to create a name."

**Leader Bot:**
1. Responds with text in chat panel
2. Calls `@researcher` to gather info
3. Researcher completes task
4. Leader calls `@creative` to generate names
5. Creative completes task
6. **Leader tool call:**
   ```json
   {
     "tool": "set_layout",
     "params": {
       "layout": "split-vertical",
       "panels": [
         {"id": "chat", "type": "chat", "position": "left"},
         {"id": "names-editor", "type": "editor", "position": "right", 
          "file": "coffee-names.md", "title": "Coffee Shop Names"}
       ]
     }
   }
   ```
7. UI transitions to split view
8. User can edit file, tag @creative with comments

### Example 2: Data Analysis

**User:** "Show me the sales data for Q4"

**Leader Bot:**
1. Calls `@researcher` to fetch data
2. **Researcher tool call:**
   ```json
   {
     "tool": "open_panel",
     "params": {
       "panel": {
         "id": "q4-data",
         "type": "data",
         "title": "Q4 Sales Data",
         "position": "right",
         "content": {
           "type": "chart",
           "chartType": "line",
           "data": [...]
         }
       }
     }
   }
   ```
3. User sees chat + chart side-by-side

### Example 3: Code Review

**User:** "Can you review this function?"

**Coder Bot:**
1. **Tool call:**
   ```json
   {
     "tool": "set_layout",
     "params": {
       "layout": "split-horizontal",
       "panels": [
         {"id": "code-view", "type": "editor", "position": "top", 
          "file": "auth.ts", "highlightLines": [45, 46, 47]},
         {"id": "chat", "type": "chat", "position": "bottom"}
       ]
     }
   }
   ```
2. Explains issues while highlighting relevant code lines

## Architecture

### Backend Integration

```go
// Tool definitions
var LayoutTools = []Tool{
    {
        Name: "set_layout",
        Description: "Change the workspace layout configuration",
        Parameters: SetLayoutParams{},
        Handler: handleSetLayout,
    },
    {
        Name: "open_panel",
        Description: "Add a new panel to the workspace",
        Parameters: OpenPanelParams{},
        Handler: handleOpenPanel,
    },
    // ... more tools
}

// WebSocket event emission
func handleSetLayout(ctx context.Context, params SetLayoutParams) error {
    event := LayoutEvent{
        Type: "layout:change",
        Data: params,
    }
    return websocket.BroadcastToRoom(ctx.RoomID, event)
}
```

### Frontend State Management

```typescript
// Svelte store for layout state
interface LayoutState {
  currentLayout: LayoutType;
  panels: Panel[];
  transitions: boolean;
}

export const layoutStore = writable<LayoutState>({
  currentLayout: 'single',
  panels: [{ id: 'chat', type: 'chat' }],
  transitions: true
});

// WebSocket handler
websocket.on('layout:change', (event) => {
  layoutStore.update(state => ({
    ...state,
    currentLayout: event.layout,
    panels: event.panels
  }));
});
```

### User Control & Overrides

Users can:
- **Accept** layout changes (default)
- **Reject** layout changes via UI prompt
- **Customize** layouts manually via drag-and-drop
- **Save** custom layouts as presets
- **Lock** layouts to prevent AI changes
- **Animate** or **instant** transition preferences

## Benefits

1. **Context-Aware** - UI adapts to task requirements automatically
2. **Transparent** - Users see *why* layout changed (bot tool call)
3. **Composable** - Layout changes chain with other bot actions
4. **Familiar** - Same mental model as other tools (web_search, file_read)
5. **Controllable** - Users can override or disable layout changes
6. **Persistent** - Layouts save per workspace/project
7. **Extensible** - New panel types added via component registry

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Layout state management in Svelte stores
- [ ] Basic layout components (SplitView, Panel)
- [ ] WebSocket events for layout changes
- [ ] Tool definitions in backend

### Phase 2: Core Panels (Weeks 3-4)
- [ ] Chat panel
- [ ] Editor panel with syntax highlighting
- [ ] Preview panel
- [ ] Data/table panel

### Phase 3: Tools Integration (Weeks 5-6)
- [ ] set_layout tool
- [ ] open_panel tool
- [ ] close_panel tool
- [ ] update_panel tool
- [ ] Bot prompt updates to include layout tools

### Phase 4: json-render Integration (Weeks 7-8)
- [ ] Component catalog for panels
- [ ] AI-generated layout specs
- [ ] Rich component rendering in panels
- [ ] Streaming layout updates

### Phase 5: Polish (Weeks 9-10)
- [ ] Smooth animations
- [ ] User layout controls (drag, resize, save)
- [ ] Layout presets
- [ ] Mobile responsive layouts

## UI Considerations

### Layout Controls
- **Visual indicator** showing current layout mode
- **Quick switcher** for common layouts (toolbar buttons)
- **Layout history** - undo/redo layout changes
- **Lock toggle** - prevent AI from changing layout

### Panel Chrome
- **Title bar** with panel name and controls
- **Drag handle** for reordering
- **Resize handle** for adjusting panel sizes
- **Close button** (if panel is closable)
- **Participant indicators** - which bots are active
- **Activity indicators** - typing, thinking, etc.

### Responsive Behavior
- **Desktop** - Full multi-panel layouts
- **Tablet** - Simplified layouts, collapsible panels
- **Mobile** - Single panel with swipe navigation

## Open Questions

1. **Permission Model** - Should all bots be able to change layouts, or only Leader?
2. **Conflict Resolution** - What if user manually adjusts layout while bot tries to change it?
3. **State Persistence** - Should layouts persist per conversation, per workspace, or globally?
4. **Performance** - How to handle rapid layout changes from streaming responses?
5. **Accessibility** - How to announce layout changes to screen readers?

## Component Library / Bento Page

To streamline development and provide a centralized view of all available UI components, we propose a dedicated **Component Library** page (codename: "Bento"). This serves as a living style guide, development sandbox, and visual inventory of the nanofolks interface.

### Purpose

- **Visual Inventory** - See all components at a glance
- **Development Playground** - Test components in isolation with different props
- **Design Consistency** - Ensure UI elements follow design system
- **Onboarding** - Help new developers understand the component architecture
- **Documentation** - Living documentation that updates with code

### Page Structure

The Bento page uses a **bento grid layout** - a modular, card-based grid system where each card showcases a component or component group.

```
┌─────────────────────────────────────────────────────────────┐
│  Component Library (Bento)                                  │
│  [Search] [Filter: All | Panels | Messages | Controls]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Chat Panel   │  │ Editor Panel     │  │ Data Panel   │  │
│  │ [preview]    │  │ [preview]        │  │ [preview]    │  │
│  │ Status: ✅   │  │ Status: ✅       │  │ Status: 🚧   │  │
│  └──────────────┘  └──────────────────┘  └──────────────┘  │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │ Message Types        │  │ Layouts      │  │ Buttons  │  │
│  │ • Text               │  │ • Single     │  │ [samples]│  │
│  │ • Code               │  │ • Split-V    │  │          │  │
│  │ • Thinking           │  │ • Split-H    │  │          │  │
│  │ • Tool Result        │  │ • Quad       │  │          │  │
│  └──────────────────────┘  └──────────────┘  └──────────┘  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Bot Avatars  │  │ Mention      │  │ json-render      │  │
│  │ [grid]       │  │ Picker       │  │ Components       │  │
│  │              │  │ [interactive]│  │ • MetricCard     │  │
│  │              │  │              │  │ • Chart          │  │
│  │              │  │              │  │ • Alert          │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component Categories

#### 1. Layout Components
Cards showcasing different layout configurations:
- **Single Panel** - Full-screen chat/editor
- **Split Vertical** - Side-by-side panels
- **Split Horizontal** - Stacked panels
- **Triad Layouts** - Asymmetric three-panel views
- **Quad Layout** - Four-panel grid
- **Responsive States** - Mobile/tablet breakpoints

Each layout card is interactive - click to expand and test different panel combinations.

#### 2. Panel Types
Individual panel showcases with live examples:
- **Chat Panel** - Show different message types, typing indicators, mentions
- **Editor Panel** - Syntax highlighting for different languages, collaborative cursors
- **Preview Panel** - Markdown rendering, HTML preview, image display
- **Data Panel** - Tables, charts (bar, line, pie), JSON viewer, metric cards
- **Canvas Panel** - Whiteboard, diagrams, mind maps
- **Browser Panel** - Web view examples

Each panel card includes:
- Visual preview with sample content
- Props documentation
- Interactive playground (edit props, see changes)
- Status indicator (✅ Complete, 🚧 In Progress, 📋 Planned)

#### 3. Message Components
All message types and variations:
- **Text Message** - Plain, markdown, with mentions
- **Code Block** - Different languages, copy button, line numbers
- **Thinking Bubble** - Collapsible reasoning display
- **Tool Result** - Success/error states, expandable details
- **File Attachment** - Images, documents, download actions
- **System Messages** - Notifications, warnings, errors

#### 4. Interactive Components
Reusable UI elements:
- **Buttons** - Primary, secondary, danger, icon buttons
- **Inputs** - Text, textarea, search, mentions
- **Selectors** - Dropdowns, tabs, radio buttons
- **Feedback** - Loading spinners, progress bars, toasts
- **Overlays** - Modals, tooltips, popovers

#### 5. json-render Components
AI-generated UI components:
- **MetricCard** - KPI displays with trends
- **Chart** - Various chart types
- **Alert** - Contextual messages
- **ProgressBar** - Task progress
- **Button** - Action triggers
- **Table** - Data grids
- **Custom Components** - User-defined additions

Each component shows:
- Visual example
- JSON schema
- Sample AI prompt that generates it
- Live playground (edit JSON, see rendered result)

### Interactive Features

#### Component Playground
Every card includes an interactive mode:
```
┌─────────────────────────────────────┐
│  Editor Panel                    [🎮]│
├─────────────────────────────────────┤
│                                     │
│  [Visual Preview]                   │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ function hello() {            │ │
│  │   return "world";             │ │
│  │ }                             │ │
│  └───────────────────────────────┘ │
│                                     │
├─────────────────────────────────────┤
│  Props:                             │
│  • language: [typescript ▼]         │
│  • readonly: [✓]                    │
│  • filename: [hello.ts     ]        │
│                                     │
│  [JSON Schema] [Reset] [Copy Code]  │
└─────────────────────────────────────┘
```

#### Status Tracking
Each component displays its development status:
- **✅ Complete** - Production ready
- **🚧 In Progress** - Currently being built
- **📋 Planned** - In backlog
- **⚠️ Deprecated** - Scheduled for removal

#### Search & Filter
- **Search** - Find components by name or description
- **Category Filters** - Show only specific types
- **Status Filters** - Show only complete, in-progress, etc.
- **Recent** - Recently viewed/updated components

### Development Workflow

#### Adding New Components

1. **Create component** in `frontend/src/lib/components/`
2. **Add to registry** in component catalog
3. **Create bento card** in Bento page
4. **Write documentation** (props, examples, usage)
5. **Set status** (usually starts as 🚧)

#### Bento Page Code Structure

```typescript
// Bento page organization
interface BentoSection {
  id: string;
  title: string;
  description: string;
  components: BentoCard[];
}

interface BentoCard {
  id: string;
  title: string;
  component: ComponentType;
  status: 'complete' | 'in-progress' | 'planned';
  props?: Record<string, any>;
  interactive?: boolean;
  examples?: Example[];
}

// Sections
const bentoSections: BentoSection[] = [
  {
    id: 'layouts',
    title: 'Layout Components',
    description: 'Workspace layout configurations',
    components: [
      { id: 'single', title: 'Single Panel', component: SinglePanelDemo, status: 'complete' },
      { id: 'split-v', title: 'Split Vertical', component: SplitVerticalDemo, status: 'complete' },
      { id: 'quad', title: 'Quad Layout', component: QuadLayoutDemo, status: 'in-progress' },
    ]
  },
  {
    id: 'panels',
    title: 'Panel Types',
    description: 'Individual panel components',
    components: [
      { id: 'chat', title: 'Chat Panel', component: ChatPanel, status: 'complete', interactive: true },
      { id: 'editor', title: 'Editor Panel', component: EditorPanel, status: 'complete', interactive: true },
      { id: 'data', title: 'Data Panel', component: DataPanel, status: 'in-progress' },
    ]
  },
  // ... more sections
];
```

### Integration with Development

#### Hot Reload
The Bento page supports hot reload - changes to component code immediately reflect in the library view.

#### Prop Type Generation
Props are automatically extracted from TypeScript definitions and displayed in the documentation panel.

#### Visual Regression Testing
The Bento page serves as a snapshot testing target - each component card can be captured for visual diff testing.

### Access & Navigation

#### Developer Menu
Access via:
- **Keyboard shortcut:** `Ctrl+Shift+B` (B for Bento)
- **Settings menu:** Developer → Component Library
- **URL:** `/dev/bento`

#### Navigation Features
- **Breadcrumbs** - Track location within categories
- **Component Count** - Show X/Y components complete
- **Progress Bar** - Overall completion percentage
- **Export** - Generate static style guide PDF

### Benefits for Dynamic Layout System

The Bento page is essential for the Dynamic Layout System because:

1. **Component Discovery** - Easy to see what panels and components are available for layouts
2. **Consistency Check** - Ensure all panels follow the same chrome/title bar patterns
3. **Props Validation** - Verify each panel accepts standard props (id, title, content, etc.)
4. **Layout Testing** - Test how components look in different layout configurations
5. **AI Training** - Use Bento page to train AI on available components (visual reference)
6. **Missing Components** - Quickly identify gaps in component library

### Implementation Notes

- **Route:** `/dev/bento` (only in dev mode or with dev flag)
- **Framework:** Svelte 5 + existing component library
- **Styling:** Same Tailwind + Skeleton setup as main app
- **Data:** Auto-generated from component registry
- **Performance:** Lazy load component previews

---

## Related Documentation

- [NANOFOLKS_GO_V1.md](./NANOFOLKS_GO_V1.md) - Main technical specification
- json-render documentation - Component rendering framework
- Wails documentation - Desktop framework

---

**Next Steps:**
1. Review and approve proposal
2. Create detailed technical specification
3. Prototype basic layout system
4. Integrate with existing bot tool system
5. Test with real use cases

**Authors:** nanofolks Team  
**Status:** Draft Proposal - Awaiting Review
