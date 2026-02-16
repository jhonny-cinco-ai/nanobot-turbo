# Nanofolks Design System
## Panda CSS Integration Guide

**Version:** 1.0  
**Date:** 2026-02-16  
**Status:** Draft  

---

## 1. Overview

### 1.1 Why Panda CSS for Nanofolks

Panda CSS provides a type-safe, build-time CSS-in-JS solution that enables:

- **Design system enforcement** through tokens and recipes
- **AI-friendly development** via MCP server integration
- **Theme consistency** across the 6 crew identities
- **Type safety** that prevents AI-generated styling errors
- **Build-time optimization** with zero runtime overhead

### 1.2 Integration Architecture

**Stack:**
- **Frontend:** Svelte 5 + Panda CSS
- **Build Tool:** Vite (via Wails v2)
- **Desktop Framework:** Wails v2
- **Language:** Go (backend) + TypeScript (frontend)

**Build Pipeline:**
1. Panda generates CSS at build time (`styled-system/`)
2. Vite processes Svelte components + Panda CSS
3. Wails embeds static assets in final binary

---

## 2. Design Token Architecture

### 2.1 Three-Layer Token Hierarchy

#### Layer 1: Base Tokens (Global)

Universal design constants used across all themes:

```typescript
// Semantic color palette
colors: {
  background: { DEFAULT: '#ffffff', _dark: '#0f0f0f' },
  foreground: { DEFAULT: '#171717', _dark: '#fafafa' },
  muted: { DEFAULT: '#f5f5f5', _dark: '#262626' },
  border: { DEFAULT: '#e5e5e5', _dark: '#404040' },
  
  // Status colors (consistent across all crews)
  success: { DEFAULT: '#22c55e', foreground: '#ffffff' },
  warning: { DEFAULT: '#f59e0b', foreground: '#ffffff' },
  danger: { DEFAULT: '#ef4444', foreground: '#ffffff' },
  info: { DEFAULT: '#3b82f6', foreground: '#ffffff' }
}

// Spacing scale
spacing: {
  '0': '0px',
  '1': '4px',
  '2': '8px',
  '3': '12px',
  '4': '16px',
  '5': '20px',
  '6': '24px',
  '8': '32px',
  '10': '40px',
  '12': '48px'
}

// Typography
fonts: {
  body: 'Inter, system-ui, sans-serif',
  mono: 'JetBrains Mono, monospace'
}

// Border radius
radii: {
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px'
}
```

#### Layer 2: Crew Theme Tokens (6 Themes)

Each crew defines shape, colors, and emblem:

**Pirate Crew**
- Shape: Hexagon (8 sides, adventure symbolism)
- Primary: Deep brown (#8B4513) - leather
- Secondary: Gold (#FFD700) - treasure
- Tertiary: Red (#FF4444) - bandana
- Surface: Warm cream (#F5E6D3)
- Emblem: Skull & crossbones

**Rock Band**
- Shape: Parallelogram (dynamic, off-kilter)
- Primary: Electric red (#DC2626)
- Secondary: Gold (#FBFB24)
- Tertiary: Dark grey (#1F2937)
- Surface: Warm cream (#FEF3C7)
- Emblem: Lightning bolt

**SWAT Team**
- Shape: Square (order, structure)
- Primary: Tactical black (#1A1A1A)
- Secondary: Neon yellow (#CCFF00)
- Tertiary: Grey (#4B5563)
- Surface: Light grey (#F3F4F6)
- Emblem: Shield

**Feral Clowder**
- Shape: Inverted trapezium (chaos, instability)
- Primary: Clown orange (#FF6B35)
- Secondary: Purple (#8B5CF6)
- Tertiary: Green (#10B981)
- Surface: Off-white (#FFFBEB)
- Emblem: Jester hat

**Executive Suite**
- Shape: Circle (inclusive, continuous)
- Primary: Navy blue (#1E3A5F)
- Secondary: Gold (#D4AF37)
- Tertiary: White (#FFFFFF)
- Surface: Light grey (#F8F9FA)
- Emblem: Briefcase

**Space Crew**
- Shape: Oval (orbit, planet)
- Primary: Deep space blue (#0B1426)
- Secondary: Cyan glow (#00D9FF)
- Tertiary: Silver (#C0C0C0)
- Surface: Dark blue (#1A1F2E)
- Emblem: Planet with rings

#### Layer 3: Component Tokens

Semantic mappings that reference crew tokens:

```typescript
button: {
  primary: {
    bg: '{crew.primary}',
    color: '{crew.primary.foreground}',
    hover: '{crew.primary.dark}'
  },
  secondary: {
    bg: '{crew.surface.DEFAULT}',
    border: '{crew.primary}',
    color: '{crew.primary}'
  }
}

badge: {
  role: {
    bg: '{crew.primary}',
    color: '{crew.primary.foreground}'
  },
  status: {
    online: '{colors.success}',
    away: '{colors.warning}',
    offline: '{colors.muted}'
  }
}
```

---

## 3. Component Recipes

### 3.1 Avatar System (3-Layer Composition)

Visual structure:
```
┌─────────────────────────────────────┐
│ Layer 3: Role Detail                │
│ (Leader headband, Coder glasses)    │
├─────────────────────────────────────┤
│ Layer 2: Crew Iconic                │
│ (Rock Band lightning, Pirate skull) │
├─────────────────────────────────────┤
│ Layer 1: Base Shape                 │
│ (Hexagon, Parallelogram, Circle)    │
└─────────────────────────────────────┘
```

**Recipe Structure:**
- Base container with positioning
- Layer 1: Geometric shape (clip-path or SVG)
- Layer 2: Crew emblem overlay
- Layer 3: Role-specific detail
- Sizes: sm (24px), md (40px), lg (64px), xl (96px)

### 3.2 Badge System

**Badge Types:**

1. **Status Badges**
   - Online (green indicator)
   - Away (yellow indicator)
   - Busy (red indicator)
   - Offline (grey indicator)

2. **Role Badges**
   - Text: "LEADER", "CODER", "RESEARCHER", etc.
   - Styled with crew colors
   - Uppercase, bold

3. **Activity Badges**
   - "NEW" indicator
   - "TYPING..." animated indicator
   - Unread message count

4. **Crew Badges**
   - Small crew emblem
   - Quick crew identification
   - Used in room lists

### 3.3 Button Variants

- **Primary**: Filled with crew primary color
- **Secondary**: Outlined with crew primary border
- **Ghost**: Subtle hover with crew accent
- **Destructive**: Consistent red across all crews (for danger actions)

### 3.4 Room Header

- Background: Crew surface color
- Text: Crew foreground color
- Accent border: Crew primary color (bottom border)
- Crew emblem: Small badge indicator

---

## 4. Theme Switching

### 4.1 Global Theme Architecture

- **Single active theme** for entire application
- **Not per-room** - consistent UI across all rooms
- Stored in: `~/.nanofolks/config.json`
- Applied via CSS custom properties at document root

### 4.2 Implementation Flow

1. User selects crew theme in Settings panel
2. Theme ID written to user config file
3. Svelte store `themeStore` updated with new crew ID
4. CSS custom properties regenerated
5. All components reactively update

### 4.3 Theme Store

```typescript
// Svelte store for reactive theme management
export const themeStore = writable<CrewTheme>('pirate')

// Derived store for current crew tokens
export const currentCrewTokens = derived(themeStore, $theme => {
  return crewTokens[$theme]
})
```

### 4.4 Theme Application

**Global UI (Base Tokens):**
- Background colors
- Text colors
- Border colors
- Spacing
- Typography

**Crew Accents (Crew Tokens):**
- Bot avatars
- Buttons
- Badges
- Room header accents
- Status indicators

---

## 5. File Structure

```
frontend/
├── panda.config.ts              # Panda configuration
├── postcss.config.cjs           # PostCSS setup
├── src/
│   ├── theme/
│   │   ├── tokens/
│   │   │   ├── base.ts          # Global semantic tokens
│   │   │   ├── pirate.ts        # Pirate Crew theme
│   │   │   ├── rockband.ts      # Rock Band theme
│   │   │   ├── swat.ts          # SWAT Team theme
│   │   │   ├── feral.ts         # Feral Clowder theme
│   │   │   ├── executive.ts     # Executive Suite theme
│   │   │   └── space.ts         # Space Crew theme
│   │   ├── recipes/
│   │   │   ├── avatar.ts        # 3-layer avatar system
│   │   │   ├── badge.ts         # Badge variants
│   │   │   ├── button.ts        # Button styles
│   │   │   ├── header.ts        # Room header
│   │   │   └── index.ts         # Recipe exports
│   │   └── index.ts             # Theme exports & switching
│   ├── components/
│   │   ├── BotAvatar.svelte     # Uses avatar recipe
│   │   ├── CrewBadge.svelte     # Uses badge recipe
│   │   └── ThemeButton.svelte   # Uses button recipe
│   └── stores/
│       └── theme.ts             # Svelte theme store
└── styled-system/               # Auto-generated by Panda
    ├── css/
    ├── recipes/
    ├── tokens/
    └── types/
```

---

## 6. Build Integration

### 6.1 Wails + Panda Workflow

**Development:**
```bash
# Terminal 1: Panda watch mode
pnpm panda --watch

# Terminal 2: Wails dev
wails dev
```

**Build Process:**
1. `pnpm install` → Triggers `prepare` script
2. `pnpm panda codegen` → Generates `styled-system/`
3. `wails build` → Vite bundles everything
4. Wails embeds assets in Go binary

### 6.2 Package.json Scripts

```json
{
  "scripts": {
    "prepare": "panda codegen",
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

### 6.3 Wails Configuration

```json
// wails.json
{
  "$schema": "https://wails.io/schemas/config.v2.json",
  "name": "nanofolks",
  "frontend:build": "npm run build",
  "frontend:dev": "npm run dev",
  "frontend:install": "npm install"
}
```

---

## 7. MCP Server Integration

### 7.1 Overview

Panda CSS includes an MCP (Model Context Protocol) server that exposes your design system to AI assistants like Claude, Cursor, and Copilot.

### 7.2 Setup

```bash
# Initialize MCP configuration
pnpm panda init-mcp

# Select AI clients to configure
# - Claude (.mcp.json)
# - Cursor (.cursor/mcp.json)
# - VS Code (.vscode/mcp.json)
```

### 7.3 Available Tools

AI assistants can query:
- **Design tokens**: Colors, spacing, typography
- **Component recipes**: Available variants and props
- **Token usage**: What's used vs. unused
- **Theme definitions**: Crew-specific values

### 7.4 Example AI Prompts

- "What color tokens are available for the Rock Band theme?"
- "Show me the avatar component variants"
- "Which design tokens are unused?"
- "What breakpoints are defined?"

---

## 8. Type Safety Benefits

### 8.1 AI Error Prevention

Panda's TypeScript integration catches errors at build time:

```typescript
// ❌ TypeScript Error: 'pirat' is not a valid crew
css({ bg: 'pirat.primary' })

// ❌ TypeScript Error: 'primaryy' is not a valid token
css({ bg: 'pirate.primaryy' })

// ✅ Valid
css({ bg: 'pirate.primary' })
```

### 8.2 IDE Support

- Auto-complete for token names
- Inline documentation for design tokens
- Recipe variant suggestions
- Type checking for component props

---

## 9. Shape Implementation Strategy

### 9.1 Hybrid Approach

**CSS Clip-Path** (Simple shapes):
- Hexagon (Pirate)
- Square (SWAT)
- Circle (Executive)
- Oval (Space)

**SVG Masks** (Complex shapes):
- Parallelogram (Rock Band)
- Inverted Trapezium (Feral Clowder)

**CSS Masks** (Icons/Details):
- Emblem overlays
- Role details
- Decorative elements

### 9.2 Shape Definitions

Shapes defined as CSS custom properties or SVG paths in crew tokens, applied via recipe variants.

---

## 10. Future Extensions

### 10.1 Adding New Crews

1. Create `src/theme/tokens/newcrew.ts`
2. Define shape, colors, emblem
3. Export from `src/theme/index.ts`
4. Components automatically support new crew

### 10.2 Theme Customization

Users could potentially:
- Override specific tokens
- Create custom crew themes
- Import/export theme presets

### 10.3 Animation Tokens

Future addition:
- Crew-specific animations
- Transition timings
- Micro-interactions

---

## 11. Configuration Example

```typescript
// panda.config.ts
import { defineConfig } from '@pandacss/dev'
import { themeTokens } from './src/theme'

export default defineConfig({
  // Scan files for style extraction
  include: [
    './src/**/*.{svelte,ts}',
    './src/**/*.recipe.ts'
  ],
  
  // Exclude test files
  exclude: [],
  
  // Output directory for generated code
  outdir: 'styled-system',
  
  // Enable CSS reset
  preflight: true,
  
  // Theme configuration
  theme: {
    extend: {
      tokens: themeTokens,
      recipes: componentRecipes
    }
  },
  
  // JSX framework (Svelte)
  jsxFramework: 'svelte',
  
  // Enable strict token validation
  strictTokens: true
})
```

---

## 12. Migration Notes

When migrating existing components:
1. Replace inline styles with Panda `css()` function
2. Use semantic token references instead of hardcoded values
3. Apply crew theme via recipe variants
4. Test across all 6 crew themes
5. Verify TypeScript types resolve correctly

---

## 13. Resources

- [Panda CSS Documentation](https://panda-css.com)
- [Panda CSS + Svelte Guide](https://panda-css.com/docs/installation/svelte)
- [Panda MCP Server](https://panda-css.com/docs/ai/mcp-server)
- [Wails v2 Documentation](https://wails.io/docs/gettingstarted/installation)
