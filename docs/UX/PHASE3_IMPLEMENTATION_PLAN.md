# Phase 3: Advanced Layout - Implementation Plan

**Status**: 🚀 IN PROGRESS  
**Target Completion**: February 15, 2026  
**Estimated Duration**: 5-6 hours  
**Priority**: LOW (Optional Enhancement)

---

## Overview

Phase 3 enhances the CLI with true side-by-side layout, terminal resize handling, live sidebar updates, and smooth transitions. This builds on the completed Phase 1 & 2 foundations.

---

## Architecture

### Core Components

1. **AdvancedLayout** - Terminal layout management
   - Create Rich Layout with header/chat/sidebar/footer
   - Track terminal dimensions
   - Detect and respond to resizes
   - Responsive layout modes (full, compact, minimal)

2. **LayoutManager** - Lifecycle and updates
   - Start/stop layout mode
   - Update individual sections
   - Integrate with interactive loop

3. **SidebarManager** - Sidebar content management
   - Track team roster updates
   - Track room list updates
   - Combine into sidebar display
   - Timestamp last updates

4. **TransitionEffect** - Smooth animations
   - Fade in/out effects
   - Slide animations
   - Highlight effects

5. **ResponsiveLayout** - Adapt to terminal size
   - Determine layout mode based on width
   - Render appropriate layout for mode
   - Handle narrow terminals gracefully

---

## Implementation Tasks

### Task 1: Core Layout (2 hours)
- ✅ Create `advanced_layout.py` module
- [ ] Create Rich Layout structures
- [ ] Implement dimension tracking
- [ ] Test on various terminal sizes

**Location**: `nanofolks/cli/advanced_layout.py`

### Task 2: Resize Handling (1.5 hours)
- [ ] Implement terminal size monitoring
- [ ] Background thread for resize detection
- [ ] Callback system for resize events
- [ ] Update layout on resize

**Location**: `AdvancedLayout.start_monitoring()`

### Task 3: Live Sidebar Updates (1.5 hours)
- [ ] Hook SidebarManager into room operations
- [ ] Update roster on bot invite
- [ ] Update room list on room creation
- [ ] Timestamp tracking for updates

**Location**: `SidebarManager`, updated commands

### Task 4: Integration (1 hour)
- [ ] Integrate LayoutManager into commands.py
- [ ] Update interactive loop to use layout
- [ ] Add layout mode toggle
- [ ] Handle mode switching

**Location**: `nanofolks/cli/commands.py`

### Task 5: Transitions & Polish (0.5 hours)
- [ ] Add smooth transition effects
- [ ] Polish visual feedback
- [ ] Documentation and testing

**Location**: `TransitionEffect` class

---

## Code Changes Summary

### New File: `nanofolks/cli/advanced_layout.py`
```
✅ AdvancedLayout class (200 lines)
✅ LayoutManager class (80 lines)
✅ SidebarManager class (60 lines)
✅ TransitionEffect class (50 lines)
✅ ResponsiveLayout class (60 lines)
Total: ~450 lines
```

### Modified File: `nanofolks/cli/commands.py`
```
- Import AdvancedLayout, LayoutManager, SidebarManager
- Update interactive loop to initialize layout
- Hook sidebar updates on room operations
- Add /layout-mode command (optional)
- Add /fullscreen command (optional)
Estimated: 80-100 lines
```

### Modified File: `nanofolks/cli/room_ui.py`
```
- Add get_sidebar_content() helper
- Improve compact rendering
- Export sidebar components
Estimated: 30-40 lines
```

---

## Detailed Implementation

### 1. AdvancedLayout Class

**Responsibilities:**
- Terminal dimension tracking
- Layout creation
- Resize monitoring
- Responsive layout modes

**Key Methods:**
```python
can_use_layout() -> bool              # Check if terminal wide enough
start_monitoring() -> None            # Start resize detection
stop_monitoring() -> None             # Stop monitoring
create_layout() -> Layout             # Create Rich Layout
render_header() -> RenderableType     # Header with room status
render_sidebar() -> RenderableType    # Team + rooms sidebar
render_footer() -> RenderableType     # Input prompt
```

### 2. LayoutManager Class

**Responsibilities:**
- Manage layout lifecycle
- Update layout sections
- Integrate with Live display

**Key Methods:**
```python
start() -> None                       # Start layout mode
stop() -> None                        # Stop layout mode
update() -> None                      # Update layout sections
```

### 3. SidebarManager Class

**Responsibilities:**
- Track sidebar content
- Manage updates
- Provide combined view

**Key Methods:**
```python
update_team_roster(content) -> None   # Update roster
update_room_list(content) -> None     # Update rooms
get_content() -> str                  # Get combined content
get_last_update() -> datetime         # Track updates
```

### 4. Integration Flow

```
Interactive Loop Initialization:
1. Create AdvancedLayout
2. Create LayoutManager
3. Create SidebarManager
4. Check if layout possible (width >= 80)
5. Start layout if possible
6. Initialize sidebar content

Room Operations:
1. User creates room
2. SidebarManager.update_room_list()
3. LayoutManager.update("sidebar" section)
4. Display transition effect
5. Show new room in sidebar

Terminal Resize:
1. Monitor detects resize
2. Callback fires
3. Update layout dimensions
4. Recalculate sidebar width
5. Redraw layout
```

---

## Phase Comparison

| Aspect | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| **Scope** | Quick wins | Integration | Advanced UI |
| **Duration** | 30 mins | 2 hours | 5-6 hours |
| **Features** | 4 | 6 | 5 |
| **Breaking Changes** | None | None | None |
| **Backward Compatible** | 100% | 100% | 100% |
| **Risk Level** | Minimal | Minimal | Low |
| **Priority** | HIGH | MEDIUM | LOW |

---

## Testing Strategy

### Unit Tests
- [ ] Terminal dimension tracking
- [ ] Layout creation
- [ ] Resize callbacks
- [ ] Responsive mode selection
- [ ] Sidebar updates

### Integration Tests
- [ ] Layout works in interactive mode
- [ ] Sidebar updates on room creation
- [ ] Sidebar updates on bot invite
- [ ] Terminal resize handled gracefully
- [ ] Transitions work smoothly

### Manual Testing
- [ ] Start with narrow terminal (50-80 chars)
- [ ] Resize to wider terminal (120+ chars)
- [ ] Create rooms while in layout mode
- [ ] Switch between rooms
- [ ] Invite bots
- [ ] Verify sidebar updates in real-time

### Compatibility Testing
- [ ] macOS Terminal
- [ ] iTerm2
- [ ] Linux terminals
- [ ] Windows Terminal (WSL)
- [ ] SSH sessions

---

## Graceful Degradation

### If Layout Not Supported
```
Terminal Width < 80 chars:
1. Detect incompatibility
2. Fall back to Phase 2 display
3. Show message: "Terminal too narrow for layout"
4. Use stacked display instead
5. All features still work
```

### If Resize Monitoring Fails
```
1. Catch monitoring thread errors
2. Continue without live updates
3. Layout still works manually
4. No user-facing errors
```

---

## Feature Flags (Optional)

For production safety, add optional feature flags:

```python
# In config
features:
  advanced_layout: true     # Enable/disable Phase 3
  resize_monitoring: true   # Enable/disable resize monitoring
  transitions: true         # Enable/disable animations
```

---

## Performance Considerations

### Resize Monitoring
- Background thread: `threading.Thread(daemon=True)`
- Check interval: 500ms (balances responsiveness vs CPU)
- No blocking I/O
- Safe exception handling

### Layout Updates
- Only update changed sections
- Use Rich's efficient rendering
- Minimize console writes
- Cache static content

### Memory Impact
- Layout object: ~100KB
- Sidebar cache: ~10KB
- Monitoring thread: minimal
- Total overhead: <1MB

---

## Fallback Strategy

**If Phase 3 is too complex:**
- Keep Phase 1 & 2 as baseline
- Phase 3 becomes optional enhancement
- Can be deferred to future sprint
- All Phase 1 & 2 functionality intact

**Minimum viable Phase 3:**
- Sidebar display on startup
- Basic resize handling
- No animations/transitions
- ~200 lines of code

---

## Documentation

### Code Documentation
- [ ] Docstrings for all classes
- [ ] Method signatures documented
- [ ] Usage examples in comments
- [ ] Configuration options documented

### User Documentation
- [ ] Phase3_IMPROVEMENTS.md - Implementation notes
- [ ] Update CLI_UX_IMPLEMENTATION_STATUS.md
- [ ] Advanced layout guide
- [ ] Troubleshooting tips

---

## Success Criteria

✅ **Must Have:**
1. True side-by-side layout renders
2. Terminal resize detected
3. Sidebar content updates live
4. Graceful fallback for narrow terminals
5. No breaking changes
6. Backward compatible

✅ **Should Have:**
1. Smooth transitions
2. Visual feedback
3. Performance optimized
4. Comprehensive documentation

⚠️ **Nice to Have:**
1. Animation effects
2. Responsive layout modes
3. Team-aware rendering
4. Customizable layout

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Layout incompatible with some terminals | Medium | Low | Feature detection, fallback |
| Resize thread issues | Low | Medium | Error handling, monitoring |
| Performance impact | Low | Low | Monitoring, optimize |
| Complex to maintain | Medium | Low | Good documentation |

---

## Rollout Plan

### Phase 3a: Core Layout (Optional)
```
1. Implement AdvancedLayout
2. Test locally
3. Document
4. Code review
```

### Phase 3b: Resize Handling (Optional)
```
1. Implement monitoring
2. Test resize behavior
3. Handle edge cases
4. Performance testing
```

### Phase 3c: Sidebar Integration (Optional)
```
1. Hook into room operations
2. Live update testing
3. Visual feedback
4. Performance validation
```

### Phase 3d: Polish & Release (Optional)
```
1. Transitions
2. Final testing
3. Documentation
4. Deployment
```

---

## Next Steps

### Immediate (Today)
- [x] Create advanced_layout.py module
- [ ] Implement core classes
- [ ] Test basic layout creation
- [ ] Verify terminal detection

### Short Term (This Sprint)
- [ ] Resize monitoring
- [ ] Sidebar manager integration
- [ ] Interactive loop updates
- [ ] Comprehensive testing

### Future
- [ ] Performance optimization
- [ ] Additional animations
- [ ] Team integration
- [ ] Custom layout configurations

---

## Questions & Decisions

1. **Layout Mode Toggle**: Should we add `/layout-mode` command?
   - Allows users to switch between full/compact/minimal
   - Optional feature for power users

2. **Animation Duration**: How long for transitions?
   - Current: 100-300ms per effect
   - Could be configurable

3. **Resize Monitoring Interval**: How often to check?
   - Current: 500ms
   - Balances responsiveness vs CPU usage

4. **Feature Flag**: Should phase 3 be optional in config?
   - Safer for production
   - Allows gradual rollout

---

## Conclusion

Phase 3 enhances the CLI with advanced terminal layout capabilities while maintaining full backward compatibility with Phase 1 & 2. The implementation is modular, testable, and includes graceful degradation for incompatible terminals.

**Status**: Ready to implement when prioritized.

---

**Date**: February 15, 2026  
**Author**: Implementation Team  
**Version**: 1.0
